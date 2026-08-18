"""Tests for src.approval (Sprint 3 — Development Stage 33).

Covers `CampaignReallocationApproval` (exact fields, `extra="forbid"`,
frozen, reuse of the existing `ReviewStatus` enum restricted to
`APPROVED`/`REJECTED`, whitespace stripping, and blank-note
normalization); the two public domain functions (`approve_...`/
`reject_...`) — exact signatures, review-ID derivation from the locked
result only, the conservation gate on approval only, the exact blank-
reviewer-name message from both functions, and non-mutation of the
locked result; and isolation from Gemini, configuration, audit, exports,
persistence, the network, and any wall-clock call.
"""

import ast
import inspect
from decimal import Decimal

import pytest
from pydantic import ValidationError

import src.approval as approval_module
from src.approval import (
    CampaignReallocationApproval,
    approve_campaign_reallocation_review,
    reject_campaign_reallocation_review,
)
from src.conservation import CampaignReallocationConservation
from src.constants import ReviewStatus
from src.pipeline import BudgetReallocationReviewResult


def _conservation(is_conserved: bool) -> CampaignReallocationConservation:
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


def _locked_result(review_id: str = "REV-1", *, is_conserved: bool = True) -> BudgetReallocationReviewResult:
    return BudgetReallocationReviewResult(
        review_id=review_id,
        campaign_results=(),
        total_current_budget=Decimal("0.00"),
        total_recommended_budget=Decimal("0.00"),
        conservation=_conservation(is_conserved),
    )


# ---------------------------------------------------------------------------
# 1-3. Exact model fields, extra="forbid", frozen
# ---------------------------------------------------------------------------


def test_exact_model_fields():
    assert set(CampaignReallocationApproval.model_fields.keys()) == {
        "review_id",
        "decision",
        "reviewer_name",
        "note",
    }


def test_model_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignReallocationApproval(
            review_id="R1",
            decision=ReviewStatus.APPROVED,
            reviewer_name="Alice",
            extra_field="not allowed",
        )


def test_model_is_frozen():
    approval = CampaignReallocationApproval(
        review_id="R1", decision=ReviewStatus.APPROVED, reviewer_name="Alice"
    )
    with pytest.raises(ValidationError):
        approval.reviewer_name = "Bob"


# ---------------------------------------------------------------------------
# 4-7. ReviewStatus reuse: APPROVED/REJECTED valid, DRAFT/PENDING_APPROVAL rejected
# ---------------------------------------------------------------------------


def test_decision_approved_is_valid():
    approval = CampaignReallocationApproval(
        review_id="R1", decision=ReviewStatus.APPROVED, reviewer_name="Alice"
    )
    assert approval.decision is ReviewStatus.APPROVED


def test_decision_rejected_is_valid():
    approval = CampaignReallocationApproval(
        review_id="R1", decision=ReviewStatus.REJECTED, reviewer_name="Alice"
    )
    assert approval.decision is ReviewStatus.REJECTED


def test_decision_draft_rejected():
    with pytest.raises(ValidationError):
        CampaignReallocationApproval(
            review_id="R1", decision=ReviewStatus.DRAFT, reviewer_name="Alice"
        )


def test_decision_pending_approval_rejected():
    with pytest.raises(ValidationError):
        CampaignReallocationApproval(
            review_id="R1", decision=ReviewStatus.PENDING_APPROVAL, reviewer_name="Alice"
        )


# ---------------------------------------------------------------------------
# 8-12. Blank/stripping/note-normalization behavior
# ---------------------------------------------------------------------------


def test_blank_review_id_rejected():
    with pytest.raises(ValidationError):
        CampaignReallocationApproval(
            review_id="   ", decision=ReviewStatus.APPROVED, reviewer_name="Alice"
        )


def test_blank_reviewer_name_rejected():
    with pytest.raises(ValidationError):
        CampaignReallocationApproval(
            review_id="R1", decision=ReviewStatus.APPROVED, reviewer_name="   "
        )


def test_review_id_and_reviewer_name_stripped():
    approval = CampaignReallocationApproval(
        review_id="  R1  ", decision=ReviewStatus.APPROVED, reviewer_name="  Alice  "
    )
    assert approval.review_id == "R1"
    assert approval.reviewer_name == "Alice"


def test_note_is_stripped():
    approval = CampaignReallocationApproval(
        review_id="R1",
        decision=ReviewStatus.APPROVED,
        reviewer_name="Alice",
        note="  looks fine  ",
    )
    assert approval.note == "looks fine"


def test_blank_note_normalizes_to_none():
    approval = CampaignReallocationApproval(
        review_id="R1", decision=ReviewStatus.APPROVED, reviewer_name="Alice", note="   "
    )
    assert approval.note is None


def test_note_defaults_to_none():
    approval = CampaignReallocationApproval(
        review_id="R1", decision=ReviewStatus.APPROVED, reviewer_name="Alice"
    )
    assert approval.note is None


# ---------------------------------------------------------------------------
# 13. Exact public function signatures
# ---------------------------------------------------------------------------


def test_exact_function_signatures():
    approve_sig = inspect.signature(approve_campaign_reallocation_review)
    reject_sig = inspect.signature(reject_campaign_reallocation_review)

    for sig in (approve_sig, reject_sig):
        params = list(sig.parameters.values())
        assert [p.name for p in params] == ["result", "reviewer_name", "note"]
        assert params[0].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert params[1].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert params[2].kind == inspect.Parameter.KEYWORD_ONLY
        assert params[2].default is None


# ---------------------------------------------------------------------------
# 14-17. Conserved/unconserved approval and rejection
# ---------------------------------------------------------------------------


def test_conserved_approval_succeeds():
    result = _locked_result(is_conserved=True)
    approval = approve_campaign_reallocation_review(result, "Alice")
    assert approval.decision is ReviewStatus.APPROVED
    assert approval.review_id == result.review_id


def test_conserved_rejection_succeeds():
    result = _locked_result(is_conserved=True)
    approval = reject_campaign_reallocation_review(result, "Alice")
    assert approval.decision is ReviewStatus.REJECTED


def test_unconserved_approval_raises_exact_message():
    result = _locked_result(is_conserved=False)
    with pytest.raises(ValueError, match=r"^An unconserved allocation cannot be approved\.$"):
        approve_campaign_reallocation_review(result, "Alice")


def test_unconserved_rejection_succeeds():
    result = _locked_result(is_conserved=False)
    approval = reject_campaign_reallocation_review(result, "Alice")
    assert approval.decision is ReviewStatus.REJECTED
    assert approval.review_id == result.review_id


# ---------------------------------------------------------------------------
# 18. Blank reviewer raises the exact message from both functions
# ---------------------------------------------------------------------------


def test_approve_blank_reviewer_raises_exact_message():
    result = _locked_result(is_conserved=True)
    with pytest.raises(ValueError, match=r"^Reviewer name must not be blank\.$"):
        approve_campaign_reallocation_review(result, "   ")


def test_reject_blank_reviewer_raises_exact_message():
    result = _locked_result(is_conserved=True)
    with pytest.raises(ValueError, match=r"^Reviewer name must not be blank\.$"):
        reject_campaign_reallocation_review(result, "")


def test_approve_blank_reviewer_checked_before_conservation():
    # A blank reviewer name on an unconserved result must still raise the
    # blank-reviewer message, not the conservation message -- reviewer
    # validity is checked first in both functions.
    result = _locked_result(is_conserved=False)
    with pytest.raises(ValueError, match=r"^Reviewer name must not be blank\.$"):
        approve_campaign_reallocation_review(result, "   ")


# ---------------------------------------------------------------------------
# 19. review_id derived from the locked result only
# ---------------------------------------------------------------------------


def test_review_id_derived_from_locked_result():
    result = _locked_result(review_id="REV-XYZ", is_conserved=True)
    approval = approve_campaign_reallocation_review(result, "Alice")
    assert approval.review_id == "REV-XYZ"


def test_functions_accept_no_separate_review_id_parameter():
    for func in (approve_campaign_reallocation_review, reject_campaign_reallocation_review):
        params = set(inspect.signature(func).parameters)
        assert "review_id" not in params


# ---------------------------------------------------------------------------
# 20. Locked result unchanged
# ---------------------------------------------------------------------------


def test_locked_result_unchanged_after_approval():
    result = _locked_result(is_conserved=True)
    snapshot = result.model_dump()
    approve_campaign_reallocation_review(result, "Alice", note="fine")
    assert result.model_dump() == snapshot


def test_locked_result_unchanged_after_rejection():
    result = _locked_result(is_conserved=False)
    snapshot = result.model_dump()
    reject_campaign_reallocation_review(result, "Alice", note="not fine")
    assert result.model_dump() == snapshot


def test_no_attribute_assignment_in_module_source():
    tree = ast.parse(inspect.getsource(approval_module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                assert not isinstance(target, ast.Attribute)


# ---------------------------------------------------------------------------
# 21-23. Isolation: no explanation/config/Gemini/audit/export/persistence/
# network/wall-clock reference
# ---------------------------------------------------------------------------


def test_no_explanation_config_or_gemini_imports():
    tree = ast.parse(inspect.getsource(approval_module))
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
    }
    assert imported_modules.isdisjoint(forbidden_modules)


def test_no_audit_export_persistence_or_network_behavior():
    tree = ast.parse(inspect.getsource(approval_module))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    forbidden_modules = {
        "src.audit",
        "src.exports",
        "os",
        "pathlib",
        "json",
        "sqlite3",
        "requests",
        "httpx",
        "socket",
    }
    assert imported_modules.isdisjoint(forbidden_modules)

    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert referenced.isdisjoint({"open", "write", "dump", "connect"})


def test_no_wall_clock_or_random_reference():
    tree = ast.parse(inspect.getsource(approval_module))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    assert imported_modules.isdisjoint({"datetime", "time", "random", "uuid"})

    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert referenced.isdisjoint({"now", "utcnow", "time", "random", "uuid4"})


def test_no_timestamp_version_audit_id_or_fingerprint_field():
    forbidden = {
        "timestamp",
        "approved_at",
        "audit_id",
        "version",
        "explanation",
        "explanation_text",
        "campaign_ids",
        "approved_campaign_ids",
        "rejected_campaign_ids",
        "fingerprint",
        "result",
        "model_name",
    }
    assert forbidden.isdisjoint(CampaignReallocationApproval.model_fields.keys())


def test_no_broad_exception_handling_in_domain_functions():
    for func in (approve_campaign_reallocation_review, reject_campaign_reallocation_review):
        tree = ast.parse(inspect.getsource(func))
        assert not any(isinstance(node, ast.Try) for node in ast.walk(tree))
