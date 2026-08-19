"""Tests for the Stage 33 human-approval UI wiring in app.py
(Sprint 3 — Development Stage 33).

Covers the human-approval section added after the optional explanation
section: control presence/absence, exact heading and caption, the blank-
starting approver field, successful approve/reject flows (with and
without a note), blank-name and unconserved-approval validation, one-
click/one-call discipline, finalized-decision rendering that replaces all
editable controls and cannot be silently overwritten, explanation- and
campaign-selector-independence, Gemini/API-key independence, deterministic-
result visibility and non-mutation across every outcome, the stale-review-
ID defense-in-depth check, the single unexpected-exception boundary, and
session-state lifecycle (including clearing on both a new successful and a
new invalid deterministic submission). No real Gemini/network call is ever
made.
"""

import ast
import inspect
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
import src.approval
import src.pipeline
from src.approval import CampaignReallocationApproval
from src.constants import ReviewStatus
from src.gemini_analyzer import generate_explanation

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def _audit_redirect_snippet() -> str:
    """Build a script snippet that redirects `app.record_campaign_reallocation_audit`
    to a fresh, isolated OS temp directory (never the repository's real
    `audit_records/`).

    Authorized addition (Sprint 3, Development Stage 34): every real
    approve/reject click in this file now also attempts automatic audit
    persistence, since that is part of the same click `app.py` already
    exercises here. Every `AppTest` construction site below embeds this
    snippet before `app.main()` runs, so none of this file's pre-existing
    Stage 33 tests ever write a real file into the tracked repository
    directory. This does not change what any test verifies -- only the
    harness plumbing.
    """
    audit_dir = tempfile.mkdtemp(prefix="stage33_test_audit_")
    return f'''
import src.audit as audit_module
from pathlib import Path as _AuditPath

_real_record_campaign_reallocation_audit = audit_module.record_campaign_reallocation_audit
_STAGE33_AUDIT_DIR = _AuditPath({audit_dir!r})


def _stage33_redirected_record(audit, *, directory=None):
    return _real_record_campaign_reallocation_audit(audit, directory=_STAGE33_AUDIT_DIR)


app.record_campaign_reallocation_audit = _stage33_redirected_record
'''


@pytest.fixture(autouse=True)
def _ensure_real_app_functions(monkeypatch):
    """Defensive isolation, scoped to this file.

    Several tests below replace `app.approve_campaign_reallocation_review`,
    `app.reject_campaign_reallocation_review`, or `app.generate_explanation`
    directly on the shared `app` module object from within an embedded
    `AppTest.from_string` script (mirroring the pattern already established
    in `tests/test_app_explanation.py`). Because that embedded `import app`
    resolves to the same `sys.modules["app"]` singleton used everywhere
    else in the process, an unrestored mutation from one test would
    otherwise leak into every test that runs after it -- in this file or
    any other. `monkeypatch` resets these attributes to the real
    Stage 27/31/33 functions before every test runs, regardless of order,
    and restores whatever was there at teardown.
    """
    monkeypatch.setattr(app, "approve_campaign_reallocation_review", src.approval.approve_campaign_reallocation_review)
    monkeypatch.setattr(app, "reject_campaign_reallocation_review", src.approval.reject_campaign_reallocation_review)
    monkeypatch.setattr(app, "generate_explanation", generate_explanation)
    monkeypatch.setattr(app, "run_budget_reallocation_review", src.pipeline.run_budget_reallocation_review)

VALID_REVIEW = {
    "review_id": "REV-1",
    "review_date": date(2026, 8, 5),
    "period_start": date(2026, 8, 1),
    "period_end": date(2026, 8, 10),
    "reviewer_name": "Reviewer",
    "approved_monthly_budget": "10000.00",
    "initial_account_reserve": "0.00",
}


def _fresh_app() -> AppTest:
    # AppTest.from_file executes app.py in an isolated namespace that does
    # not honor an external monkeypatch of a real approve/reject click's
    # automatic Stage 34 audit write (confirmed empirically), so this
    # helper uses AppTest.from_string with the redirect embedded directly
    # in the executed script instead -- the only mechanism that reliably
    # takes effect.
    script = "import app\n" + _audit_redirect_snippet() + "\napp.main()\n"
    at = AppTest.from_string(script)
    at.run(timeout=10)
    assert not at.exception
    return at


def _fill_review_inputs(at: AppTest, overrides: dict | None = None) -> None:
    values = dict(VALID_REVIEW)
    if overrides:
        values.update(overrides)
    at.text_input(key="review_id").set_value(values["review_id"])
    at.date_input(key="review_date").set_value(values["review_date"])
    at.date_input(key="period_start").set_value(values["period_start"])
    at.date_input(key="period_end").set_value(values["period_end"])
    at.text_input(key="reviewer_name").set_value(values["reviewer_name"])
    at.text_input(key="approved_monthly_budget").set_value(values["approved_monthly_budget"])
    at.text_input(key="initial_account_reserve").set_value(values["initial_account_reserve"])


def _upload_sample_csv(at: AppTest) -> None:
    content = (DATA_DIR / "sample_campaigns.csv").read_bytes()
    at.file_uploader(key="campaign_csv").set_value(("sample_campaigns.csv", content, "text/csv"))


def _submit(at: AppTest) -> None:
    at.button(key="submit_review").click().run(timeout=10)


def _submit_valid_sample(at: AppTest) -> None:
    _fill_review_inputs(at)
    _upload_sample_csv(at)
    _submit(at)
    assert at.session_state["locked_review_result"] is not None


def _flush_rerun_if_decided(at: AppTest) -> None:
    # A successful decision calls st.rerun(); AppTest does not fold that
    # rerun into the same .run() that triggered it, so one more explicit
    # run is needed to observe the post-rerun, controls-replaced state. A
    # failed decision schedules no rerun, and its transient st.error(...)
    # is only emitted on the run where the button was actually clicked, so
    # this second run must be skipped in that case or the failure message
    # would be lost with nothing replacing it.
    if at.session_state["approval_decision_result"] is not None:
        at.run(timeout=10)


def _approve(at: AppTest, reviewer_name: str = "Carol", note: str | None = None) -> None:
    at.text_input(key="approval_reviewer_name").set_value(reviewer_name)
    if note is not None:
        at.text_area(key="approval_note").set_value(note)
    at.button(key="approve_review").click().run(timeout=10)
    _flush_rerun_if_decided(at)


def _reject(at: AppTest, reviewer_name: str = "Carol", note: str | None = None) -> None:
    at.text_input(key="approval_reviewer_name").set_value(reviewer_name)
    if note is not None:
        at.text_area(key="approval_note").set_value(note)
    at.button(key="reject_review").click().run(timeout=10)
    _flush_rerun_if_decided(at)


_UNCONSERVED_SCRIPT_HEADER = """
import app
import streamlit as st
from decimal import Decimal
from src.conservation import CampaignReallocationConservation
from src.pipeline import BudgetReallocationReviewResult

_real_run = app.run_budget_reallocation_review

def _unconserved_run(review, campaigns):
    real = _real_run(review, campaigns)
    return BudgetReallocationReviewResult(
        review_id=real.review_id,
        campaign_results=real.campaign_results,
        total_current_budget=real.total_current_budget,
        total_recommended_budget=real.total_recommended_budget,
        conservation=CampaignReallocationConservation(
            total_increase_allocated=Decimal("100.00"),
            total_decrease_allocated=Decimal("50.00"),
            net_change=Decimal("50.00"),
            is_conserved=False,
        ),
    )

app.run_budget_reallocation_review = _unconserved_run
"""


def _unconserved_app() -> AppTest:
    script = _UNCONSERVED_SCRIPT_HEADER + _audit_redirect_snippet() + "\napp.main()\n"
    at = AppTest.from_string(script)
    at.run(timeout=10)
    return at


_APPROVAL_FAKE_HEADER = """
import app
import streamlit as st

if "fake_approve_calls" not in st.session_state:
    st.session_state["fake_approve_calls"] = []
"""


def _app_test_with_fake_approve(body: str) -> AppTest:
    """Build an AppTest running app.py with `app.approve_campaign_reallocation_review`
    replaced by a fake. `body` must define `_fake_approve(result, reviewer_name, *, note=None)`.

    `AppTest.from_string`'s embedded `import app` executes in its own
    isolated namespace (confirmed empirically: a pytest-level
    `monkeypatch.setattr(app, ...)` performed outside the script does not
    reach code running inside `AppTest.from_file`/`AppTest.from_string`),
    so the override must be applied from *within* the executed script
    itself, mirroring the pattern already established in
    `tests/test_app_explanation.py`.
    """
    script = (
        _APPROVAL_FAKE_HEADER
        + _audit_redirect_snippet()
        + body
        + "\napp.approve_campaign_reallocation_review = _fake_approve\napp.main()\n"
    )
    at = AppTest.from_string(script)
    at.run(timeout=10)
    return at


# ---------------------------------------------------------------------------
# 1-3. Presence/absence, heading, caption
# ---------------------------------------------------------------------------


def test_controls_absent_without_locked_result():
    at = _fresh_app()
    assert "Human approval" not in [s.value for s in at.subheader]
    assert not any(b.key == "approve_review" for b in at.button)
    assert not any(b.key == "reject_review" for b in at.button)


def test_exact_heading_and_caption():
    at = _fresh_app()
    _submit_valid_sample(at)
    assert "Human approval" in [s.value for s in at.subheader]
    expected_caption = (
        "Approval applies to the complete locked deterministic review. "
        "AI-generated explanations are supplementary and are not part of "
        "the approval decision."
    )
    assert expected_caption in [c.value for c in at.caption]


def test_controls_appear_after_successful_review():
    at = _fresh_app()
    _submit_valid_sample(at)
    assert any(t.key == "approval_reviewer_name" for t in at.text_input)
    assert any(t.key == "approval_note" for t in at.text_area)
    assert any(b.key == "approve_review" for b in at.button)
    assert any(b.key == "reject_review" for b in at.button)


# ---------------------------------------------------------------------------
# 4. Approver starts blank
# ---------------------------------------------------------------------------


def test_approver_starts_blank():
    at = _fresh_app()
    _submit_valid_sample(at)
    assert at.text_input(key="approval_reviewer_name").value == ""


# ---------------------------------------------------------------------------
# 5-8. Successful approve/reject, with and without a note
# ---------------------------------------------------------------------------


def test_successful_approval():
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert not at.exception
    assert "Decision: APPROVED" in [s.value for s in at.success]
    assert "Approver: Carol" in [m.value for m in at.markdown]


def test_successful_rejection():
    at = _fresh_app()
    _submit_valid_sample(at)
    _reject(at, "Dave")
    assert not at.exception
    assert "Decision: REJECTED" in [w.value for w in at.warning]
    assert "Approver: Dave" in [m.value for m in at.markdown]


def test_approval_note_optional_and_displayed_when_present():
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "Carol", note="  Looks fine  ")
    assert "Decision note: Looks fine" in [m.value for m in at.markdown]


def test_rejection_note_optional_and_displayed_when_present():
    at = _fresh_app()
    _submit_valid_sample(at)
    _reject(at, "Dave", note="  Numbers look wrong  ")
    assert "Decision note: Numbers look wrong" in [m.value for m in at.markdown]


def test_approval_without_note_shows_no_note_line():
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert not any(m.value.startswith("Decision note:") for m in at.markdown)


# ---------------------------------------------------------------------------
# 9. Blank-name validation
# ---------------------------------------------------------------------------


def test_blank_name_validation_on_approve():
    at = _fresh_app()
    _submit_valid_sample(at)
    at.button(key="approve_review").click().run(timeout=10)
    assert "Reviewer name must not be blank." in [e.value for e in at.error]
    assert at.session_state["approval_decision_result"] is None


def test_blank_name_validation_on_reject():
    at = _fresh_app()
    _submit_valid_sample(at)
    at.button(key="reject_review").click().run(timeout=10)
    assert "Reviewer name must not be blank." in [e.value for e in at.error]
    assert at.session_state["approval_decision_result"] is None


def test_whitespace_only_name_is_blank():
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "   ")
    assert "Reviewer name must not be blank." in [e.value for e in at.error]
    assert at.session_state["approval_decision_result"] is None


# ---------------------------------------------------------------------------
# 10-11. Unconserved approval blocked; unconserved rejection succeeds
# ---------------------------------------------------------------------------


def test_unconserved_approval_blocked():
    at = _unconserved_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert "An unconserved allocation cannot be approved." in [e.value for e in at.error]
    assert at.session_state["approval_decision_result"] is None
    assert any(b.key == "reject_review" for b in at.button)


def test_unconserved_rejection_succeeds():
    at = _unconserved_app()
    _submit_valid_sample(at)
    _reject(at, "Carol")
    assert "Decision: REJECTED" in [w.value for w in at.warning]
    assert at.session_state["approval_decision_result"].decision is ReviewStatus.REJECTED


# ---------------------------------------------------------------------------
# 12-13. Exactly one call per click; ordinary reruns create no decision
# ---------------------------------------------------------------------------


def test_exactly_one_domain_call_per_click():
    body = """
from src.approval import approve_campaign_reallocation_review as _real_approve

def _fake_approve(result, reviewer_name, *, note=None):
    st.session_state["fake_approve_calls"].append(1)
    return _real_approve(result, reviewer_name, note=note)
"""
    at = _app_test_with_fake_approve(body)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert len(at.session_state["fake_approve_calls"]) == 1


def test_ordinary_rerun_creates_no_decision():
    at = _fresh_app()
    _submit_valid_sample(at)
    assert at.session_state["approval_decision_result"] is None
    at.run(timeout=10)
    at.run(timeout=10)
    assert at.session_state["approval_decision_result"] is None


# ---------------------------------------------------------------------------
# 14-16. Finalized decision replaces controls; no silent overwrite
# ---------------------------------------------------------------------------


def test_finalized_approval_replaces_editable_controls():
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert not any(t.key == "approval_reviewer_name" for t in at.text_input)
    assert not any(t.key == "approval_note" for t in at.text_area)
    assert not any(b.key == "approve_review" for b in at.button)
    assert not any(b.key == "reject_review" for b in at.button)


def test_finalized_approval_cannot_be_overwritten():
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    stored = at.session_state["approval_decision_result"]
    # The approve/reject buttons are gone; further reruns must never
    # change the stored decision.
    at.run(timeout=10)
    at.run(timeout=10)
    assert at.session_state["approval_decision_result"] == stored
    assert [s.value for s in at.success].count("Decision: APPROVED") == 1


def test_finalized_rejection_cannot_be_overwritten():
    at = _fresh_app()
    _submit_valid_sample(at)
    _reject(at, "Dave")
    stored = at.session_state["approval_decision_result"]
    at.run(timeout=10)
    assert at.session_state["approval_decision_result"] == stored
    assert [w.value for w in at.warning].count("Decision: REJECTED") == 1


# ---------------------------------------------------------------------------
# 17-18. New submissions clear approval state
# ---------------------------------------------------------------------------


def test_new_successful_submission_clears_approval():
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["approval_decision_result"] is not None

    _submit_valid_sample(at)

    assert at.session_state["approval_decision_result"] is None
    assert at.text_input(key="approval_reviewer_name").value == ""
    assert not any(s.value == "Decision: APPROVED" for s in at.success)


def test_new_invalid_submission_clears_approval():
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["approval_decision_result"] is not None

    at.text_input(key="review_id").set_value("")
    at.text_input(key="reviewer_name").set_value("")
    at.button(key="submit_review").click().run(timeout=10)

    assert at.session_state["locked_review_result"] is None
    assert at.session_state["approval_decision_result"] is None


# ---------------------------------------------------------------------------
# 19-20. Explanation/campaign-selector independence
# ---------------------------------------------------------------------------


def test_explanation_generation_does_not_affect_approval():
    body = """
def _fake_generate_explanation(prompt, config):
    from src.gemini_analyzer import ExplanationResult, ExplanationStatus
    return ExplanationResult(
        status=ExplanationStatus.GENERATED,
        explanation_text="an explanation",
        model_name="gemini-2.5-flash-lite",
    )
"""
    script = "import app\n" + body + "\napp.generate_explanation = _fake_generate_explanation\napp.main()\n"
    at = AppTest.from_string(script)
    at.run(timeout=10)
    _submit_valid_sample(at)

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert at.session_state["approval_decision_result"] is None
    assert any(b.key == "approve_review" for b in at.button)


def test_campaign_selector_change_does_not_affect_approval():
    at = _fresh_app()
    _submit_valid_sample(at)
    at.selectbox(key="explanation_campaign_id").set_value("G002 — Shopping - Core Catalog")
    at.run(timeout=10)
    assert at.session_state["approval_decision_result"] is None
    assert any(b.key == "approve_review" for b in at.button)


# ---------------------------------------------------------------------------
# 21-22. Gemini independence
# ---------------------------------------------------------------------------


def test_approval_succeeds_without_gemini_configuration(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = _fresh_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert "Decision: APPROVED" in [s.value for s in at.success]


def test_failed_explanation_does_not_block_approval():
    body = """
def _fake_generate_explanation(prompt, config):
    from src.gemini_analyzer import ExplanationResult, ExplanationStatus, ErrorCategory
    return ExplanationResult(
        status=ExplanationStatus.FAILED,
        model_name="gemini-2.5-flash-lite",
        error_category=ErrorCategory.TIMEOUT,
        error_message="The request timed out.",
    )
"""
    script = (
        "import app\n"
        + body
        + _audit_redirect_snippet()
        + "\napp.generate_explanation = _fake_generate_explanation\napp.main()\n"
    )
    at = AppTest.from_string(script)
    at.run(timeout=10)
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert "The request timed out." in [e.value for e in at.error]

    _approve(at, "Carol")
    assert "Decision: APPROVED" in [s.value for s in at.success]


# ---------------------------------------------------------------------------
# 23-25. Deterministic result visibility and non-mutation
# ---------------------------------------------------------------------------


def test_deterministic_result_unchanged_after_approval():
    at = _fresh_app()
    _submit_valid_sample(at)
    snapshot = at.session_state["locked_review_result"].model_dump()
    _approve(at, "Carol")
    assert at.session_state["locked_review_result"].model_dump() == snapshot
    rows = at.dataframe[0].value.to_dict("records")
    assert [row["campaign_id"] for row in rows] == ["G001", "M001", "G002", "G003"]


def test_deterministic_result_unchanged_after_rejection():
    at = _fresh_app()
    _submit_valid_sample(at)
    snapshot = at.session_state["locked_review_result"].model_dump()
    _reject(at, "Dave")
    assert at.session_state["locked_review_result"].model_dump() == snapshot


def test_deterministic_result_visible_after_approval_error():
    at = _unconserved_app()
    _submit_valid_sample(at)
    _approve(at, "Carol")
    rows = at.dataframe[0].value.to_dict("records")
    assert [row["campaign_id"] for row in rows] == ["G001", "M001", "G002", "G003"]
    assert at.session_state["locked_review_result"] is not None


# ---------------------------------------------------------------------------
# 26. Stale review-ID decision not rendered
# ---------------------------------------------------------------------------


def test_stale_review_id_decision_not_rendered():
    at = _fresh_app()
    _submit_valid_sample(at)
    stale = CampaignReallocationApproval(
        review_id="SOME-OTHER-REVIEW-ID", decision=ReviewStatus.APPROVED, reviewer_name="Carol"
    )
    at.session_state["approval_decision_result"] = stale
    at.run(timeout=10)

    assert not any(s.value == "Decision: APPROVED" for s in at.success)
    assert any(
        "no longer matches the current locked review" in e.value for e in at.error
    )
    assert at.session_state["approval_decision_result"] is None
    # Falls through to the fresh, editable controls.
    assert any(b.key == "approve_review" for b in at.button)


# ---------------------------------------------------------------------------
# 27-28. Unexpected exception contained; no raw exception/provider/key info
# ---------------------------------------------------------------------------


def test_unexpected_approval_exception_is_contained():
    body = """
def _fake_approve(result, reviewer_name, *, note=None):
    raise RuntimeError("simulated unexpected failure")
"""
    at = _app_test_with_fake_approve(body)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    assert not at.exception
    assert at.session_state["approval_decision_result"] is None
    assert any("unexpected error" in e.value for e in at.error)
    assert not any("RuntimeError" in e.value for e in at.error)
    assert not any("simulated unexpected failure" in e.value for e in at.error)
    assert at.session_state["locked_review_result"] is not None


# ---------------------------------------------------------------------------
# 29-30. No audit/export/persistence/platform-execution behavior
# ---------------------------------------------------------------------------


def test_no_audit_export_or_platform_imports_in_app():
    # Approved exception (Sprint 3, Development Stage 34): `src.audit` was
    # removed from this forbidden set because app.py now legitimately
    # imports it for automatic audit-record persistence — see
    # tests/test_app_audit.py for that stage's own coverage. Approved
    # exception (Sprint 3, Development Stage 35): `src.exports` was
    # removed because app.py now legitimately imports it for the CSV
    # export section — see tests/test_app_exports.py for that stage's own
    # coverage. This test now has no remaining forbidden modules of its
    # own to assert, since every module it originally guarded against is
    # now a legitimate, separately-covered import.
    tree = ast.parse(inspect.getsource(app))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    assert imported_modules.isdisjoint(set())


def test_no_filesystem_or_network_calls_in_approval_section():
    tree = ast.parse(inspect.getsource(app._render_approval_section))
    tree_handler = ast.parse(inspect.getsource(app._handle_approval_decision_click))
    referenced = set()
    for t in (tree, tree_handler):
        referenced |= {node.id for node in ast.walk(t) if isinstance(node, ast.Name)}
        referenced |= {node.attr for node in ast.walk(t) if isinstance(node, ast.Attribute)}
    assert referenced.isdisjoint({"open", "write", "requests", "socket", "connect"})


# ---------------------------------------------------------------------------
# 31. Session-state lifecycle (source-level)
# ---------------------------------------------------------------------------


def test_approval_state_cleared_in_handle_submission_source():
    source = inspect.getsource(app._handle_submission)
    assert 'st.session_state[APPROVAL_DECISION_STATE_KEY] = None' in source
    assert 'st.session_state["approval_reviewer_name"] = ""' in source
    assert 'st.session_state["approval_note"] = ""' in source


def test_no_module_level_approval_singleton():
    tree = ast.parse(inspect.getsource(app))
    module_level_assigns = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    module_level_assigns.add(target.id)
    assert "APPROVAL" not in module_level_assigns
