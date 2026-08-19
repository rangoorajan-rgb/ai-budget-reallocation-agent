"""Tests for src.exports (Sprint 3 — Development Stage 35).

Covers `CampaignReallocationExportRow` (exact field set, `extra="forbid"`,
frozen); `build_campaign_reallocation_export_rows`/
`serialize_campaign_reallocation_export_csv` (exact signatures, exact
column order independent of Pydantic/dict ordering, exact audit/approval/
portfolio/campaign field copying for both approved and rejected audits —
including a rejected, unconserved audit, header-only output for an empty
campaign tuple, preserved campaign and reason-code order, `rank=None` →
`"Not ranked"`, `note=None` → `""`, exact `Decimal`/enum/UTC-timestamp/
Boolean serialization, CSV formula-injection neutralization, a valid
`csv.DictReader` round-trip, non-mutation of the input audit, and
isolation from `float`, the filesystem, the network, Gemini/config/
secrets, and every Stage 1–34 production function.
"""

import ast
import csv
import inspect
import io
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

import src.exports as exports_module
from src.exports import (
    CampaignReallocationExportRow,
    build_campaign_reallocation_export_rows,
    serialize_campaign_reallocation_export_csv,
)
from src.audit import CampaignReallocationAudit, build_campaign_reallocation_audit
from src.approval import (
    CampaignReallocationApproval,
    approve_campaign_reallocation_review,
    reject_campaign_reallocation_review,
)
from src.classification import PerformanceBand, TrendDirection
from src.conservation import CampaignReallocationConservation
from src.constants import Confidence, Platform, ReasonCode, RecommendationAction, ReviewStatus
from src.pacing import PacingStatus
from src.pipeline import BudgetReallocationReviewResult, CampaignBudgetRecommendationResult

_UTC_TS = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

_EXPECTED_COLUMNS = (
    "audit_id",
    "review_id",
    "recorded_at",
    "decision",
    "reviewer_name",
    "decision_note",
    "total_current_budget",
    "total_recommended_budget",
    "total_increase_allocated",
    "total_decrease_allocated",
    "net_change",
    "is_conserved",
    "campaign_id",
    "campaign_name",
    "platform",
    "current_budget",
    "recommendation_action",
    "allocated_amount",
    "recommended_budget",
    "reason_codes",
    "performance_band",
    "trend_direction",
    "confidence",
    "pacing_status",
    "reallocation_priority_score",
    "rank",
)


def _conservation(is_conserved: bool = True) -> CampaignReallocationConservation:
    if is_conserved:
        return CampaignReallocationConservation(
            total_increase_allocated=Decimal("100.10"),
            total_decrease_allocated=Decimal("100.10"),
            net_change=Decimal("0.00"),
            is_conserved=True,
        )
    return CampaignReallocationConservation(
        total_increase_allocated=Decimal("100.00"),
        total_decrease_allocated=Decimal("50.00"),
        net_change=Decimal("50.00"),
        is_conserved=False,
    )


def _campaign(**overrides) -> CampaignBudgetRecommendationResult:
    defaults = dict(
        campaign_id="C1",
        campaign_name="Campaign One",
        platform=Platform.GOOGLE_ADS,
        current_budget=Decimal("1000.00"),
        recommendation_action=RecommendationAction.INCREASE,
        allocated_amount=Decimal("100.10"),
        recommended_budget=Decimal("1100.10"),
        reason_codes=(ReasonCode.ABOVE_TARGET_STRONG, ReasonCode.RECENT_TREND_IMPROVING),
        performance_band=PerformanceBand.ABOVE_TARGET,
        trend_direction=TrendDirection.IMPROVING,
        confidence=Confidence.HIGH,
        pacing_status=PacingStatus.ON_PACE,
        reallocation_priority_score=90,
        rank=1,
    )
    defaults.update(overrides)
    return CampaignBudgetRecommendationResult(**defaults)


def _result(
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


def _audit(
    *,
    is_conserved: bool = True,
    approved: bool = True,
    campaign_results: tuple = (),
    reviewer_name: str = "Alice",
    note: str | None = None,
    recorded_at: datetime = _UTC_TS,
) -> CampaignReallocationAudit:
    result = _result(is_conserved=is_conserved, campaign_results=campaign_results)
    if approved:
        approval = approve_campaign_reallocation_review(result, reviewer_name, note=note)
    else:
        approval = reject_campaign_reallocation_review(result, reviewer_name, note=note)
    return build_campaign_reallocation_audit(result, approval, recorded_at)


# ---------------------------------------------------------------------------
# 1-3. Exact model fields, extra="forbid", frozen
# ---------------------------------------------------------------------------


def test_exact_model_fields():
    assert set(CampaignReallocationExportRow.model_fields.keys()) == set(_EXPECTED_COLUMNS)


def test_model_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignReallocationExportRow(
            **{name: "x" for name in _EXPECTED_COLUMNS if name != "is_conserved"},
            is_conserved=True,
            extra_field="not allowed",
        )


def test_model_is_frozen():
    kwargs = {name: "x" for name in _EXPECTED_COLUMNS if name != "is_conserved"}
    kwargs["is_conserved"] = True
    kwargs["reallocation_priority_score"] = 0
    row = CampaignReallocationExportRow(**kwargs)
    with pytest.raises(ValidationError):
        row.campaign_id = "other"


# ---------------------------------------------------------------------------
# 4. Exact function signatures
# ---------------------------------------------------------------------------


def test_exact_build_function_signature():
    sig = inspect.signature(build_campaign_reallocation_export_rows)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["audit"]
    assert params[0].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_exact_serialize_function_signature():
    sig = inspect.signature(serialize_campaign_reallocation_export_csv)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["rows"]
    assert params[0].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_only_expected_public_names_defined_in_module():
    tree = ast.parse(inspect.getsource(exports_module))
    public_top_level = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith("_")
    }
    assert public_top_level == {
        "CampaignReallocationExportRow",
        "build_campaign_reallocation_export_rows",
        "serialize_campaign_reallocation_export_csv",
    }


# ---------------------------------------------------------------------------
# 5. Exact CSV column order
# ---------------------------------------------------------------------------


def test_csv_header_matches_exact_column_order():
    csv_text = serialize_campaign_reallocation_export_csv(())
    header_line = csv_text.splitlines()[0]
    assert header_line.split(",") == list(_EXPECTED_COLUMNS)


def test_column_order_independent_of_dict_construction_order():
    audit = _audit(campaign_results=(_campaign(),))
    rows = build_campaign_reallocation_export_rows(audit)
    csv_text = serialize_campaign_reallocation_export_csv(rows)
    header = csv_text.splitlines()[0].split(",")
    assert header == list(_EXPECTED_COLUMNS)


# ---------------------------------------------------------------------------
# 6. Header-only CSV for an empty campaign tuple
# ---------------------------------------------------------------------------


def test_empty_campaign_audit_produces_header_only_rows():
    audit = _audit(campaign_results=())
    rows = build_campaign_reallocation_export_rows(audit)
    assert rows == ()


def test_empty_rows_produce_valid_header_only_csv():
    csv_text = serialize_campaign_reallocation_export_csv(())
    lines = csv_text.splitlines()
    assert len(lines) == 1
    assert lines[0].split(",") == list(_EXPECTED_COLUMNS)


# ---------------------------------------------------------------------------
# 7-9. Approved, rejected, conserved, and unconserved-rejected audits
# ---------------------------------------------------------------------------


def test_approved_conserved_audit_builds_rows():
    audit = _audit(approved=True, is_conserved=True, campaign_results=(_campaign(),))
    rows = build_campaign_reallocation_export_rows(audit)
    assert len(rows) == 1
    assert rows[0].decision == "APPROVED"
    assert rows[0].is_conserved is True


def test_rejected_conserved_audit_builds_rows():
    audit = _audit(approved=False, is_conserved=True, campaign_results=(_campaign(),))
    rows = build_campaign_reallocation_export_rows(audit)
    assert rows[0].decision == "REJECTED"


def test_rejected_unconserved_audit_builds_rows():
    audit = _audit(approved=False, is_conserved=False, campaign_results=(_campaign(),))
    rows = build_campaign_reallocation_export_rows(audit)
    assert rows[0].decision == "REJECTED"
    assert rows[0].is_conserved is False
    # The recommendations themselves are unchanged by rejection.
    assert rows[0].campaign_id == "C1"
    assert rows[0].recommendation_action == "INCREASE"


# ---------------------------------------------------------------------------
# 10-11. Exact audit/approval/portfolio field copying; exact campaign field copying
# ---------------------------------------------------------------------------


def test_exact_shared_field_copying():
    audit = _audit(
        approved=True,
        is_conserved=True,
        campaign_results=(_campaign(),),
        reviewer_name="Bob",
        note="looks fine",
        recorded_at=_UTC_TS,
    )
    rows = build_campaign_reallocation_export_rows(audit)
    row = rows[0]
    assert row.audit_id == audit.audit_id
    assert row.review_id == audit.review_id
    assert row.recorded_at == _UTC_TS.isoformat()
    assert row.decision == "APPROVED"
    assert row.reviewer_name == "Bob"
    assert row.decision_note == "looks fine"
    assert row.total_current_budget == "1000.00"
    assert row.total_recommended_budget == "1100.10"
    assert row.total_increase_allocated == "100.10"
    assert row.total_decrease_allocated == "100.10"
    assert row.net_change == "0.00"
    assert row.is_conserved is True


def test_exact_campaign_field_copying():
    campaign = _campaign(
        campaign_id="C42",
        campaign_name="Big Campaign",
        platform=Platform.META_ADS,
        current_budget=Decimal("500.00"),
        recommendation_action=RecommendationAction.REDUCE,
        allocated_amount=Decimal("25.50"),
        recommended_budget=Decimal("474.50"),
        reason_codes=(ReasonCode.BELOW_TARGET_SEVERE,),
        performance_band=PerformanceBand.BELOW_TARGET,
        trend_direction=TrendDirection.DECLINING,
        confidence=Confidence.LOW,
        pacing_status=PacingStatus.OVERSPENDING,
        reallocation_priority_score=42,
        rank=3,
    )
    audit = _audit(campaign_results=(campaign,))
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.campaign_id == "C42"
    assert row.campaign_name == "Big Campaign"
    assert row.platform == "Meta Ads"
    assert row.current_budget == "500.00"
    assert row.recommendation_action == "REDUCE"
    assert row.allocated_amount == "25.50"
    assert row.recommended_budget == "474.50"
    assert row.reason_codes == "BELOW_TARGET_SEVERE"
    assert row.performance_band == "BELOW_TARGET"
    assert row.trend_direction == "DECLINING"
    assert row.confidence == "LOW"
    assert row.pacing_status == "Over spending"
    assert row.reallocation_priority_score == 42
    assert row.rank == "3"


# ---------------------------------------------------------------------------
# 12-13. Preserved campaign order and reason-code order
# ---------------------------------------------------------------------------


def test_preserved_campaign_order():
    campaigns = (
        _campaign(campaign_id="C3", rank=None),
        _campaign(campaign_id="C1", rank=1),
        _campaign(campaign_id="C2", rank=2),
    )
    audit = _audit(campaign_results=campaigns)
    rows = build_campaign_reallocation_export_rows(audit)
    assert [row.campaign_id for row in rows] == ["C3", "C1", "C2"]


def test_preserved_reason_code_order():
    campaign = _campaign(
        reason_codes=(
            ReasonCode.RECENT_TREND_DECLINING,
            ReasonCode.ABOVE_TARGET_STRONG,
            ReasonCode.TRACKING_WARNING,
        )
    )
    audit = _audit(campaign_results=(campaign,))
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.reason_codes == "RECENT_TREND_DECLINING, ABOVE_TARGET_STRONG, TRACKING_WARNING"


# ---------------------------------------------------------------------------
# 14-15. rank=None -> "Not ranked"; note=None -> ""
# ---------------------------------------------------------------------------


def test_rank_none_becomes_not_ranked():
    campaign = _campaign(rank=None)
    audit = _audit(campaign_results=(campaign,))
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.rank == "Not ranked"


def test_note_none_becomes_empty_string():
    audit = _audit(campaign_results=(_campaign(),), note=None)
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.decision_note == ""


# ---------------------------------------------------------------------------
# 16-18. Decimal formatting: trailing zeros, extreme precision, no scientific notation
# ---------------------------------------------------------------------------


def test_decimal_trailing_zeros_preserved():
    campaign = _campaign(current_budget=Decimal("100.10"), allocated_amount=Decimal("0.00"))
    audit = _audit(campaign_results=(campaign,))
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.current_budget == "100.10"
    assert row.allocated_amount == "0.00"


def test_decimal_extreme_precision_preserved():
    big = Decimal("99999999999999999999999999.99")
    campaign = _campaign(current_budget=big, recommended_budget=big, allocated_amount=Decimal("0.00"))
    audit = _audit(campaign_results=(campaign,))
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.current_budget == "99999999999999999999999999.99"
    assert row.recommended_budget == "99999999999999999999999999.99"


def test_no_scientific_notation_anywhere_in_csv():
    big = Decimal("99999999999999999999999999.99")
    campaign = _campaign(current_budget=big, recommended_budget=big, allocated_amount=Decimal("0.00"))
    audit = _audit(campaign_results=(campaign,))
    rows = build_campaign_reallocation_export_rows(audit)
    csv_text = serialize_campaign_reallocation_export_csv(rows)
    assert "e+" not in csv_text.lower()
    assert "e-" not in csv_text.lower()


# ---------------------------------------------------------------------------
# 19. Exact UTC ISO timestamp
# ---------------------------------------------------------------------------


def test_exact_utc_iso_timestamp():
    audit = _audit(campaign_results=(_campaign(),), recorded_at=_UTC_TS)
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.recorded_at == "2026-08-19T12:00:00+00:00"


# ---------------------------------------------------------------------------
# 20. Deterministic repeated builds/serialization
# ---------------------------------------------------------------------------


def test_deterministic_repeated_build_and_serialize():
    audit = _audit(campaign_results=(_campaign(), _campaign(campaign_id="C2")))
    rows1 = build_campaign_reallocation_export_rows(audit)
    rows2 = build_campaign_reallocation_export_rows(audit)
    assert rows1 == rows2
    csv1 = serialize_campaign_reallocation_export_csv(rows1)
    csv2 = serialize_campaign_reallocation_export_csv(rows2)
    assert csv1 == csv2


# ---------------------------------------------------------------------------
# 21. Special characters: commas, quotes, embedded newlines, backslashes,
# Markdown-like content, Unicode
# ---------------------------------------------------------------------------


def test_special_characters_round_trip_correctly():
    campaign = _campaign(campaign_name='Campaign, "Special" \\ Name\nSecond line — 日本語 **bold**')
    audit = _audit(campaign_results=(campaign,), reviewer_name="O'Brien, Jr.", note="Note with, comma")
    rows = build_campaign_reallocation_export_rows(audit)
    csv_text = serialize_campaign_reallocation_export_csv(rows)

    reader = csv.DictReader(io.StringIO(csv_text))
    parsed = list(reader)
    assert len(parsed) == 1
    assert parsed[0]["campaign_name"] == 'Campaign, "Special" \\ Name\nSecond line — 日本語 **bold**'
    assert parsed[0]["reviewer_name"] == "O'Brien, Jr."
    assert parsed[0]["decision_note"] == "Note with, comma"


# ---------------------------------------------------------------------------
# 22-25. CSV formula-injection neutralization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_formula_injection_neutralized_for_all_four_prefixes(prefix):
    audit = _audit(
        campaign_results=(_campaign(campaign_id=f"{prefix}CMD", campaign_name=f"{prefix}SUM(A1)"),),
        reviewer_name=f"{prefix}cmd|calc",
        note=f"{prefix}HYPERLINK(x)",
    )
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.campaign_id == f"'{prefix}CMD"
    assert row.campaign_name == f"'{prefix}SUM(A1)"
    assert row.reviewer_name == f"'{prefix}cmd|calc"
    assert row.decision_note == f"'{prefix}HYPERLINK(x)"


def test_formula_injection_neutralized_after_leading_whitespace():
    audit = _audit(campaign_results=(_campaign(campaign_name="  =SUM(A1)"),))
    row = build_campaign_reallocation_export_rows(audit)[0]
    assert row.campaign_name == "'  =SUM(A1)"


def test_safe_text_unchanged():
    audit = _audit(campaign_results=(_campaign(campaign_name="Search - Brand Campaign"),))
    row = build_campaign_reallocation_export_rows(audit)[0]
    # A hyphen not in the leading position must never be neutralized.
    assert row.campaign_name == "Search - Brand Campaign"


def test_empty_text_unchanged():
    from src.exports import _neutralize_formula

    assert _neutralize_formula("") == ""


def test_no_double_neutralization_on_value_already_apostrophe_prefixed():
    from src.exports import _neutralize_formula

    already_safe = "'=SUM(A1)"
    assert _neutralize_formula(already_safe) == already_safe
    assert _neutralize_formula(_neutralize_formula("=SUM(A1)")) == _neutralize_formula("=SUM(A1)")


def test_is_conserved_emitted_as_python_bool_string():
    audit_true = _audit(is_conserved=True, campaign_results=(_campaign(),))
    audit_false = _audit(approved=False, is_conserved=False, campaign_results=(_campaign(),))
    csv_true = serialize_campaign_reallocation_export_csv(
        build_campaign_reallocation_export_rows(audit_true)
    )
    csv_false = serialize_campaign_reallocation_export_csv(
        build_campaign_reallocation_export_rows(audit_false)
    )
    assert ",True," in csv_true.splitlines()[1]
    assert ",False," in csv_false.splitlines()[1]


# ---------------------------------------------------------------------------
# 26. Valid round-trip through csv.DictReader
# ---------------------------------------------------------------------------


def test_valid_round_trip_through_dictreader():
    audit = _audit(campaign_results=(_campaign(), _campaign(campaign_id="C2", rank=None)))
    rows = build_campaign_reallocation_export_rows(audit)
    csv_text = serialize_campaign_reallocation_export_csv(rows)

    reader = csv.DictReader(io.StringIO(csv_text))
    assert reader.fieldnames == list(_EXPECTED_COLUMNS)
    parsed = list(reader)
    assert len(parsed) == 2
    assert parsed[0]["campaign_id"] == "C1"
    assert parsed[1]["campaign_id"] == "C2"
    assert parsed[1]["rank"] == "Not ranked"


# ---------------------------------------------------------------------------
# 27. Input audit/result/approval unchanged after construction and serialization
# ---------------------------------------------------------------------------


def test_input_audit_unchanged_after_build_and_serialize():
    audit = _audit(campaign_results=(_campaign(),))
    snapshot = audit.model_dump()

    rows = build_campaign_reallocation_export_rows(audit)
    serialize_campaign_reallocation_export_csv(rows)

    assert audit.model_dump() == snapshot


# ---------------------------------------------------------------------------
# 28-31. Isolation: no float, no filesystem, no network, no Gemini/config/secrets,
# no Stage 1-34 function calls
# ---------------------------------------------------------------------------


def test_no_float_reference_in_module():
    tree = ast.parse(inspect.getsource(exports_module))
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "float" not in referenced


def test_no_filesystem_network_gemini_config_or_secret_imports():
    tree = ast.parse(inspect.getsource(exports_module))
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
        "google.generativeai",
        "google.genai",
        "streamlit",
        "os",
        "pathlib",
        "requests",
        "httpx",
        "socket",
        "sqlite3",
    }
    assert imported_modules.isdisjoint(forbidden_modules)


def test_no_secret_or_gemini_name_referenced():
    tree = ast.parse(inspect.getsource(exports_module))
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden = {
        "api_key",
        "get_secret_value",
        "SecretStr",
        "genai",
        "generativeai",
        "gemini",
        "explanation_text",
        "model_name",
        "open",
        "write",
        "connect",
    }
    assert referenced.isdisjoint(forbidden)


def test_no_stage_1_34_production_function_called():
    tree = ast.parse(inspect.getsource(exports_module))
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    forbidden_functions = {
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "resolve_campaign_action_availability",
        "resolve_campaign_action_suitability",
        "resolve_campaign_recommendation_action",
        "resolve_campaign_recommendation_reason",
        "calculate_campaign_reallocation_priority_score",
        "rank_campaign_reallocation_priorities",
        "allocate_campaign_reallocation",
        "verify_campaign_reallocation_conservation",
        "run_budget_reallocation_review",
        "approve_campaign_reallocation_review",
        "reject_campaign_reallocation_review",
        "build_campaign_reallocation_audit",
        "record_campaign_reallocation_audit",
        "validate_review_setup",
        "validate_campaign_csv",
    }
    assert called_names.isdisjoint(forbidden_functions)
