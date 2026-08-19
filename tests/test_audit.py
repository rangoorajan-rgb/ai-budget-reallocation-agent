"""Tests for src.audit (Sprint 3 — Development Stage 34).

Covers `CampaignReallocationAudit` (exact fields, `extra="forbid"`, frozen,
embedding of the existing frozen Stage 27/33 models directly, aware-UTC
timestamp normalization, naive-timestamp rejection); the two public
functions `build_campaign_reallocation_audit`/`record_campaign_reallocation_audit`
(exact signatures, review-ID/conservation consistency checks with exact
messages, deterministic content-derived audit-ID construction excluding
`recorded_at`, canonical serialization, atomic idempotent persistence,
conflict/malformed-record rejection, and failure cleanup); and isolation
from Gemini, configuration, exports, the network, and any public
read/list/delete surface. No test ever writes outside `tmp_path`.
"""

import ast
import inspect
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.audit as audit_module
from src.audit import (
    CampaignReallocationAudit,
    build_campaign_reallocation_audit,
    record_campaign_reallocation_audit,
)
from src.approval import (
    CampaignReallocationApproval,
    approve_campaign_reallocation_review,
    reject_campaign_reallocation_review,
)
from src.conservation import CampaignReallocationConservation
from src.constants import (
    Confidence,
    Platform,
    ReasonCode,
    RecommendationAction,
    ReviewStatus,
)
from src.pacing import PacingStatus
from src.classification import PerformanceBand, TrendDirection
from src.pipeline import BudgetReallocationReviewResult, CampaignBudgetRecommendationResult

_UTC_TS = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)


def _conservation(is_conserved: bool = True) -> CampaignReallocationConservation:
    if is_conserved:
        return CampaignReallocationConservation(
            total_increase_allocated=Decimal("0.00"),
            total_decrease_allocated=Decimal("0.00"),
            net_change=Decimal("0.00"),
            is_conserved=True,
        )
    return CampaignReallocationConservation(
        total_increase_allocated=Decimal("100.00"),
        total_decrease_allocated=Decimal("50.00"),
        net_change=Decimal("50.00"),
        is_conserved=False,
    )


def _campaign_result(**overrides) -> CampaignBudgetRecommendationResult:
    defaults = dict(
        campaign_id="C1",
        campaign_name="Campaign One",
        platform=Platform.GOOGLE_ADS,
        current_budget=Decimal("1000.00"),
        recommendation_action=RecommendationAction.INCREASE,
        allocated_amount=Decimal("100.10"),
        recommended_budget=Decimal("1100.10"),
        reason_codes=(ReasonCode.ABOVE_TARGET_STRONG,),
        performance_band=PerformanceBand.ABOVE_TARGET,
        trend_direction=TrendDirection.IMPROVING,
        confidence=Confidence.HIGH,
        pacing_status=PacingStatus.ON_PACE,
        reallocation_priority_score=90,
        rank=1,
    )
    defaults.update(overrides)
    return CampaignBudgetRecommendationResult(**defaults)


def _locked_result(
    review_id: str = "REV-1",
    *,
    is_conserved: bool = True,
    campaign_results: tuple = (),
) -> BudgetReallocationReviewResult:
    return BudgetReallocationReviewResult(
        review_id=review_id,
        campaign_results=campaign_results,
        total_current_budget=Decimal("1000.00") if campaign_results else Decimal("0.00"),
        total_recommended_budget=Decimal("1100.10") if campaign_results else Decimal("0.00"),
        conservation=_conservation(is_conserved),
    )


def _approval(result: BudgetReallocationReviewResult, **kwargs) -> CampaignReallocationApproval:
    return approve_campaign_reallocation_review(result, kwargs.pop("reviewer_name", "Alice"), **kwargs)


# ---------------------------------------------------------------------------
# 1-2. Exact model fields, extra="forbid", frozen
# ---------------------------------------------------------------------------


def test_exact_model_fields():
    assert set(CampaignReallocationAudit.model_fields.keys()) == {
        "audit_id",
        "review_id",
        "result",
        "approval",
        "recorded_at",
    }


def test_model_rejects_unknown_field():
    result = _locked_result()
    approval = _approval(result)
    with pytest.raises(ValidationError):
        CampaignReallocationAudit(
            audit_id="audit_x",
            review_id=result.review_id,
            result=result,
            approval=approval,
            recorded_at=_UTC_TS,
            extra_field="not allowed",
        )


def test_model_is_frozen():
    result = _locked_result()
    approval = _approval(result)
    audit = CampaignReallocationAudit(
        audit_id="audit_x",
        review_id=result.review_id,
        result=result,
        approval=approval,
        recorded_at=_UTC_TS,
    )
    with pytest.raises(ValidationError):
        audit.review_id = "other"


def test_result_and_approval_are_the_same_embedded_types():
    result = _locked_result()
    approval = _approval(result)
    audit = CampaignReallocationAudit(
        audit_id="audit_x",
        review_id=result.review_id,
        result=result,
        approval=approval,
        recorded_at=_UTC_TS,
    )
    assert isinstance(audit.result, BudgetReallocationReviewResult)
    assert isinstance(audit.approval, CampaignReallocationApproval)
    assert audit.result == result
    assert audit.approval == approval


# ---------------------------------------------------------------------------
# 3-5. Timestamp acceptance/rejection/normalization
# ---------------------------------------------------------------------------


def test_aware_utc_timestamp_accepted():
    result = _locked_result()
    approval = _approval(result)
    audit = CampaignReallocationAudit(
        audit_id="audit_x", review_id=result.review_id, result=result, approval=approval,
        recorded_at=_UTC_TS,
    )
    assert audit.recorded_at == _UTC_TS
    assert audit.recorded_at.tzinfo == timezone.utc


def test_naive_timestamp_rejected():
    result = _locked_result()
    approval = _approval(result)
    with pytest.raises(ValidationError):
        CampaignReallocationAudit(
            audit_id="audit_x", review_id=result.review_id, result=result, approval=approval,
            recorded_at=datetime(2026, 8, 18, 12, 0, 0),
        )


def test_non_utc_aware_timestamp_normalized_to_utc():
    result = _locked_result()
    approval = _approval(result)
    plus_five = timezone(timedelta(hours=5))
    local_ts = datetime(2026, 8, 18, 17, 0, 0, tzinfo=plus_five)
    audit = CampaignReallocationAudit(
        audit_id="audit_x", review_id=result.review_id, result=result, approval=approval,
        recorded_at=local_ts,
    )
    assert audit.recorded_at.tzinfo == timezone.utc
    assert audit.recorded_at == _UTC_TS


# ---------------------------------------------------------------------------
# 6-7. Exact consistency-check error messages
# ---------------------------------------------------------------------------


def test_review_id_mismatch_raises_exact_message():
    result = _locked_result(review_id="REV-1")
    other_result = _locked_result(review_id="REV-2")
    approval = _approval(other_result)
    with pytest.raises(
        ValueError,
        match=r"^Approval review_id does not match the locked result's review_id\.$",
    ):
        build_campaign_reallocation_audit(result, approval, _UTC_TS)


def test_unconserved_approval_raises_exact_message():
    result = _locked_result(is_conserved=False)
    approval = CampaignReallocationApproval(
        review_id=result.review_id, decision=ReviewStatus.APPROVED, reviewer_name="Alice"
    )
    with pytest.raises(
        ValueError,
        match=r"^An unconserved allocation cannot be recorded as approved\.$",
    ):
        build_campaign_reallocation_audit(result, approval, _UTC_TS)


def test_conserved_approval_builds_successfully():
    result = _locked_result(is_conserved=True)
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    assert audit.review_id == result.review_id
    assert audit.approval.decision is ReviewStatus.APPROVED


# ---------------------------------------------------------------------------
# 8. Rejected unconserved result is always valid
# ---------------------------------------------------------------------------


def test_rejected_unconserved_result_builds_successfully():
    result = _locked_result(is_conserved=False)
    approval = reject_campaign_reallocation_review(result, "Alice")
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    assert audit.approval.decision is ReviewStatus.REJECTED
    assert audit.result.conservation.is_conserved is False


# ---------------------------------------------------------------------------
# 9-11. Deterministic, content-derived audit ID
# ---------------------------------------------------------------------------


def test_audit_id_deterministic_across_calls():
    result = _locked_result()
    approval = _approval(result)
    audit1 = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    audit2 = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    assert audit1.audit_id == audit2.audit_id


def test_audit_id_excludes_recorded_at():
    result = _locked_result()
    approval = _approval(result)
    audit1 = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    audit2 = build_campaign_reallocation_audit(result, approval, _UTC_TS + timedelta(days=1))
    assert audit1.audit_id == audit2.audit_id
    assert audit1.recorded_at != audit2.recorded_at


def test_audit_id_changes_with_reviewer_name():
    result = _locked_result()
    approval_a = approve_campaign_reallocation_review(result, "Alice")
    approval_b = approve_campaign_reallocation_review(result, "Bob")
    audit_a = build_campaign_reallocation_audit(result, approval_a, _UTC_TS)
    audit_b = build_campaign_reallocation_audit(result, approval_b, _UTC_TS)
    assert audit_a.audit_id != audit_b.audit_id


def test_audit_id_changes_with_note():
    result = _locked_result()
    approval_a = approve_campaign_reallocation_review(result, "Alice", note="fine")
    approval_b = approve_campaign_reallocation_review(result, "Alice", note="not fine")
    audit_a = build_campaign_reallocation_audit(result, approval_a, _UTC_TS)
    audit_b = build_campaign_reallocation_audit(result, approval_b, _UTC_TS)
    assert audit_a.audit_id != audit_b.audit_id


def test_audit_id_changes_with_result_content():
    result_a = _locked_result(campaign_results=(_campaign_result(),))
    result_b = _locked_result(campaign_results=(_campaign_result(campaign_id="C2"),))
    approval_a = _approval(result_a)
    approval_b = _approval(result_b)
    audit_a = build_campaign_reallocation_audit(result_a, approval_a, _UTC_TS)
    audit_b = build_campaign_reallocation_audit(result_b, approval_b, _UTC_TS)
    assert audit_a.audit_id != audit_b.audit_id


def test_audit_id_prefixed_and_hex():
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    assert audit.audit_id.startswith("audit_")
    hex_part = audit.audit_id[len("audit_") :]
    assert len(hex_part) == 64
    int(hex_part, 16)  # raises ValueError if not valid hex


# ---------------------------------------------------------------------------
# 12-14. Canonical serialization: Decimal/enum/tuple/datetime, determinism
# ---------------------------------------------------------------------------


def test_decimal_preserved_as_fixed_point_with_trailing_zeros(tmp_path):
    result = _locked_result(campaign_results=(_campaign_result(allocated_amount=Decimal("100.10")),))
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path = record_campaign_reallocation_audit(audit, directory=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["result"]["campaign_results"][0]["allocated_amount"] == "100.10"


def test_decimal_extreme_value_preserved(tmp_path):
    big = Decimal("99999999999999999999999999.99")
    result = _locked_result(
        campaign_results=(
            _campaign_result(current_budget=big, allocated_amount=Decimal("0.00"), recommended_budget=big),
        )
    )
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path = record_campaign_reallocation_audit(audit, directory=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["result"]["campaign_results"][0]["current_budget"] == "99999999999999999999999999.99"


def test_no_float_or_scientific_notation_in_serialized_output(tmp_path):
    result = _locked_result(campaign_results=(_campaign_result(),))
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path = record_campaign_reallocation_audit(audit, directory=tmp_path)
    raw = path.read_text(encoding="utf-8")
    assert "e+" not in raw.lower()
    assert "e-" not in raw.lower()


def test_enum_and_tuple_serialized(tmp_path):
    result = _locked_result(campaign_results=(_campaign_result(),))
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path = record_campaign_reallocation_audit(audit, directory=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    campaign = data["result"]["campaign_results"][0]
    assert campaign["platform"] == "Google Ads"
    assert campaign["recommendation_action"] == "INCREASE"
    assert campaign["reason_codes"] == ["ABOVE_TARGET_STRONG"]
    assert isinstance(campaign["reason_codes"], list)


def test_recorded_at_serialized_with_utc_offset(tmp_path):
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path = record_campaign_reallocation_audit(audit, directory=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["recorded_at"] == "2026-08-18T12:00:00+00:00"


def test_canonical_json_is_byte_for_byte_deterministic(tmp_path):
    result = _locked_result(campaign_results=(_campaign_result(),))
    approval = _approval(result)
    audit1 = build_campaign_reallocation_audit(result, approval, _UTC_TS)

    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    path_a = record_campaign_reallocation_audit(audit1, directory=dir_a)
    path_b = record_campaign_reallocation_audit(audit1, directory=dir_b)
    assert path_a.read_bytes() == path_b.read_bytes()


# ---------------------------------------------------------------------------
# 15-16. Missing-directory creation; successful write under tmp_path
# ---------------------------------------------------------------------------


def test_missing_directory_is_created(tmp_path):
    target = tmp_path / "nested" / "audit_records"
    assert not target.exists()
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path = record_campaign_reallocation_audit(audit, directory=target)
    assert target.exists()
    assert path.parent == target
    assert path.exists()


def test_successful_write_returns_path_named_by_audit_id(tmp_path):
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path = record_campaign_reallocation_audit(audit, directory=tmp_path)
    assert path.name == f"{audit.audit_id}.json"
    assert path.exists()


# ---------------------------------------------------------------------------
# 17-18. Idempotent retry behavior
# ---------------------------------------------------------------------------


def test_identical_retry_with_same_timestamp_is_idempotent(tmp_path):
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path1 = record_campaign_reallocation_audit(audit, directory=tmp_path)
    original_bytes = path1.read_bytes()
    original_mtime = path1.stat().st_mtime_ns

    path2 = record_campaign_reallocation_audit(audit, directory=tmp_path)
    assert path2 == path1
    assert path2.read_bytes() == original_bytes
    assert path2.stat().st_mtime_ns == original_mtime


def test_retry_with_different_timestamp_returns_original_path_unchanged(tmp_path):
    result = _locked_result()
    approval = _approval(result)
    audit1 = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    path1 = record_campaign_reallocation_audit(audit1, directory=tmp_path)
    original_bytes = path1.read_bytes()

    audit2 = build_campaign_reallocation_audit(result, approval, _UTC_TS + timedelta(hours=1))
    path2 = record_campaign_reallocation_audit(audit2, directory=tmp_path)

    assert path2 == path1
    assert path2.read_bytes() == original_bytes
    data = json.loads(path2.read_text(encoding="utf-8"))
    assert data["recorded_at"] == "2026-08-18T12:00:00+00:00"


# ---------------------------------------------------------------------------
# 19-20. Conflict and malformed-record rejection
# ---------------------------------------------------------------------------


def test_conflicting_existing_content_rejected(tmp_path):
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)

    other_result = _locked_result(review_id="REV-OTHER")
    other_approval = _approval(other_result)
    forged = CampaignReallocationAudit(
        audit_id=audit.audit_id,  # deliberately mismatched with its own content
        review_id=other_result.review_id,
        result=other_result,
        approval=other_approval,
        recorded_at=_UTC_TS,
    )
    forged_path = tmp_path / f"{audit.audit_id}.json"
    tmp_path.mkdir(parents=True, exist_ok=True)
    fields = {
        field_name: audit_module._normalize_value(getattr(forged, field_name))
        for field_name in type(forged).model_fields
    }
    forged_path.write_bytes(audit_module._canonical_bytes(fields))

    with pytest.raises(
        ValueError,
        match=r"^An audit record with this audit_id already exists with different content\.$",
    ):
        record_campaign_reallocation_audit(audit, directory=tmp_path)

    # The forged file must remain untouched.
    assert json.loads(forged_path.read_text(encoding="utf-8"))["review_id"] == "REV-OTHER"


def test_malformed_existing_record_rejected_without_overwrite(tmp_path):
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)

    tmp_path.mkdir(parents=True, exist_ok=True)
    malformed_path = tmp_path / f"{audit.audit_id}.json"
    malformed_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(Exception):
        record_campaign_reallocation_audit(audit, directory=tmp_path)

    assert malformed_path.read_text(encoding="utf-8") == "{not valid json"


# ---------------------------------------------------------------------------
# 21. Failure cleanup: no partial temporary or final file
# ---------------------------------------------------------------------------


def test_finalization_failure_leaves_no_partial_or_final_file(tmp_path, monkeypatch):
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)

    def _raise_replace(*args, **kwargs):
        raise OSError("simulated finalization failure")

    monkeypatch.setattr(audit_module.os, "replace", _raise_replace)

    with pytest.raises(OSError):
        record_campaign_reallocation_audit(audit, directory=tmp_path)

    final_path = tmp_path / f"{audit.audit_id}.json"
    assert not final_path.exists()
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []


def test_serialization_failure_leaves_no_file(tmp_path, monkeypatch):
    result = _locked_result()
    approval = _approval(result)
    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)

    def _raise_normalize(value):
        raise TypeError("simulated serialization failure")

    monkeypatch.setattr(audit_module, "_normalize_value", _raise_normalize)

    with pytest.raises(TypeError):
        record_campaign_reallocation_audit(audit, directory=tmp_path)

    assert list(tmp_path.glob("*")) == []


# ---------------------------------------------------------------------------
# 22. No mutation of result or approval
# ---------------------------------------------------------------------------


def test_result_and_approval_unchanged_after_build_and_record(tmp_path):
    result = _locked_result(campaign_results=(_campaign_result(),))
    approval = _approval(result)
    result_snapshot = result.model_dump()
    approval_snapshot = approval.model_dump()

    audit = build_campaign_reallocation_audit(result, approval, _UTC_TS)
    record_campaign_reallocation_audit(audit, directory=tmp_path)

    assert result.model_dump() == result_snapshot
    assert approval.model_dump() == approval_snapshot


# ---------------------------------------------------------------------------
# 23. Isolation: no Gemini/config/exports/network/database coupling
# ---------------------------------------------------------------------------


def test_no_gemini_config_or_export_imports():
    tree = ast.parse(inspect.getsource(audit_module))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    forbidden_modules = {
        "config",
        "src.explanations",
        "src.gemini_analyzer",
        "src.exports",
        "google.generativeai",
        "google.genai",
        "streamlit",
        "requests",
        "httpx",
        "socket",
        "sqlite3",
    }
    assert imported_modules.isdisjoint(forbidden_modules)


def test_no_forbidden_names_referenced():
    tree = ast.parse(inspect.getsource(audit_module))
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden = {"genai", "generativeai", "gemini", "explanations", "exports", "SecretStr", "api_key"}
    assert referenced.isdisjoint(forbidden)


def test_no_timestamp_generation_inside_module():
    # The module must never call the clock itself -- `recorded_at` is
    # always supplied by the caller.
    tree = ast.parse(inspect.getsource(audit_module))
    referenced = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "now" not in referenced
    assert "utcnow" not in referenced


def test_no_public_read_list_delete_export_functions():
    tree = ast.parse(inspect.getsource(audit_module))
    top_level_function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    forbidden_prefixes = ("read_", "list_", "delete_", "export_", "repair_", "retry_", "overwrite_")
    for name in top_level_function_names:
        if not name.startswith("_"):
            assert not name.startswith(forbidden_prefixes), name

    public_names = {name for name in top_level_function_names if not name.startswith("_")}
    assert public_names == {"build_campaign_reallocation_audit", "record_campaign_reallocation_audit"}


# ---------------------------------------------------------------------------
# Exact public function signatures
# ---------------------------------------------------------------------------


def test_exact_build_function_signature():
    sig = inspect.signature(build_campaign_reallocation_audit)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["result", "approval", "recorded_at"]
    for p in params:
        assert p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_exact_record_function_signature():
    sig = inspect.signature(record_campaign_reallocation_audit)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["audit", "directory"]
    assert params[0].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params[1].kind == inspect.Parameter.KEYWORD_ONLY
    assert params[1].default is None
