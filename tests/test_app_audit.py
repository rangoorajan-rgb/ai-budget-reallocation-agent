"""Tests for the Stage 34 automatic audit-recording UI wiring in app.py
(Sprint 3 — Development Stage 34).

Covers: an approved or rejected decision automatically builds and
persists exactly one audit record from the same click, with the correct
locked result and finalized approval reaching the builder; ordinary
reruns and repeated successful reruns never write again; the exact
success rendering (message + audit ID, never the full path); a failed
write leaving the finalized decision fully intact with the exact
sanitized failure message, no raw exception, and exactly one retry
control; retry behavior (no re-approval, no automatic loop, success
clears the error); audit-state clearing on both a new successful and a
new invalid deterministic submission; independence from Gemini
explanation actions; and full deterministic-result visibility and
non-mutation throughout. No test ever writes to the real repository
`audit_records/` directory, makes a network call, or uses a real Gemini
client/API key.
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
import src.approval
import src.audit
import src.pipeline
from src.gemini_analyzer import generate_explanation

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VALID_REVIEW = {
    "review_id": "REV-1",
    "review_date": date(2026, 8, 5),
    "period_start": date(2026, 8, 1),
    "period_end": date(2026, 8, 10),
    "reviewer_name": "Reviewer",
    "approved_monthly_budget": "10000.00",
    "initial_account_reserve": "0.00",
}


@pytest.fixture(autouse=True)
def _ensure_real_app_functions(monkeypatch):
    """Defensive isolation, scoped to this file.

    Every test below overrides `app.record_campaign_reallocation_audit`
    (and sometimes `app.build_campaign_reallocation_audit` or
    `app.approve_campaign_reallocation_review`) directly on the shared
    `app` module object from within an embedded `AppTest.from_string`
    script -- the only way to make an override actually take effect
    inside an `AppTest` run, since `AppTest`'s embedded `import app`
    resolves to the same `sys.modules["app"]` singleton used everywhere
    else in the process. Because that mutation is not undone by pytest's
    own `monkeypatch` bookkeeping, it would otherwise leak into every
    test that runs after it -- in this file or any other. This fixture
    resets those attributes to their real Stage 27/31/33/34
    implementations before every test, regardless of order.
    """
    monkeypatch.setattr(app, "approve_campaign_reallocation_review", src.approval.approve_campaign_reallocation_review)
    monkeypatch.setattr(app, "reject_campaign_reallocation_review", src.approval.reject_campaign_reallocation_review)
    monkeypatch.setattr(app, "generate_explanation", generate_explanation)
    monkeypatch.setattr(app, "run_budget_reallocation_review", src.pipeline.run_budget_reallocation_review)
    monkeypatch.setattr(app, "build_campaign_reallocation_audit", src.audit.build_campaign_reallocation_audit)
    monkeypatch.setattr(app, "record_campaign_reallocation_audit", src.audit.record_campaign_reallocation_audit)


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


def _submit_valid_sample(at: AppTest, overrides: dict | None = None) -> None:
    _fill_review_inputs(at, overrides)
    _upload_sample_csv(at)
    _submit(at)
    assert at.session_state["locked_review_result"] is not None


def _flush_rerun_if_decided(at: AppTest) -> None:
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


_AUDIT_HEADER = """
import app
import streamlit as st
import src.audit as audit_module
from pathlib import Path

_real_record = audit_module.record_campaign_reallocation_audit
_AUDIT_DIR = Path({tmp_path_repr})

if "fake_audit_calls" not in st.session_state:
    st.session_state["fake_audit_calls"] = 0
"""

_REDIRECT_TO_TMP_BODY = """
def _record(audit, *, directory=None):
    st.session_state["fake_audit_calls"] += 1
    return _real_record(audit, directory=_AUDIT_DIR)

app.record_campaign_reallocation_audit = _record
"""

_ALWAYS_FAIL_BODY = """
def _record(audit, *, directory=None):
    st.session_state["fake_audit_calls"] += 1
    raise OSError("simulated disk failure")

app.record_campaign_reallocation_audit = _record
"""

_FAIL_FIRST_CALL_BODY = """
def _record(audit, *, directory=None):
    st.session_state["fake_audit_calls"] += 1
    if st.session_state["fake_audit_calls"] == 1:
        raise OSError("simulated disk failure")
    return _real_record(audit, directory=_AUDIT_DIR)

app.record_campaign_reallocation_audit = _record
"""

_CAPTURE_BUILD_ARGS_BODY = """
_real_build = app.build_campaign_reallocation_audit

def _capture_build(result, approval, recorded_at):
    st.session_state["captured_review_id"] = result.review_id
    st.session_state["captured_reviewer_name"] = approval.reviewer_name
    st.session_state["captured_decision"] = approval.decision.value
    return _real_build(result, approval, recorded_at)

app.build_campaign_reallocation_audit = _capture_build
"""

_COUNT_APPROVE_CALLS_BODY = """
from src.approval import approve_campaign_reallocation_review as _real_approve

def _counting_approve(result, reviewer_name, *, note=None):
    st.session_state["fake_approve_calls"] = st.session_state.get("fake_approve_calls", 0) + 1
    return _real_approve(result, reviewer_name, note=note)

app.approve_campaign_reallocation_review = _counting_approve
"""


def _build_script(tmp_path: Path, *bodies: str) -> str:
    header = _AUDIT_HEADER.format(tmp_path_repr=repr(str(tmp_path)))
    return header + "".join(bodies) + "\napp.main()\n"


def _app_with_redirect(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(_build_script(tmp_path, _REDIRECT_TO_TMP_BODY))
    at.run(timeout=10)
    return at


def _app_with_always_fail(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(_build_script(tmp_path, _ALWAYS_FAIL_BODY))
    at.run(timeout=10)
    return at


def _app_with_fail_first_call(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(_build_script(tmp_path, _FAIL_FIRST_CALL_BODY))
    at.run(timeout=10)
    return at


def _app_with_capture_and_redirect(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(
        _build_script(tmp_path, _REDIRECT_TO_TMP_BODY, _CAPTURE_BUILD_ARGS_BODY)
    )
    at.run(timeout=10)
    return at


def _app_with_redirect_and_approve_counter(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(
        _build_script(tmp_path, _REDIRECT_TO_TMP_BODY, _COUNT_APPROVE_CALLS_BODY)
    )
    at.run(timeout=10)
    return at


def _app_with_fail_first_and_approve_counter(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(
        _build_script(tmp_path, _FAIL_FIRST_CALL_BODY, _COUNT_APPROVE_CALLS_BODY)
    )
    at.run(timeout=10)
    return at


# ---------------------------------------------------------------------------
# 1-2. Approved/rejected decision automatically creates exactly one record
# ---------------------------------------------------------------------------


def test_approved_decision_automatically_creates_one_audit_record(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    assert at.session_state["fake_audit_calls"] == 1
    assert at.session_state["audit_record_path"] is not None
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1


def test_rejected_decision_automatically_creates_one_audit_record(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _reject(at, "Dave")

    assert at.session_state["fake_audit_calls"] == 1
    assert at.session_state["audit_record_path"] is not None
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1


# ---------------------------------------------------------------------------
# 3. Correct result and approval reach the audit builder
# ---------------------------------------------------------------------------


def test_correct_result_and_approval_reach_the_builder(tmp_path):
    at = _app_with_capture_and_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol", note="looks fine")

    assert at.session_state["captured_review_id"] == "REV-1"
    assert at.session_state["captured_reviewer_name"] == "Carol"
    assert at.session_state["captured_decision"] == "APPROVED"


# ---------------------------------------------------------------------------
# 4. One decision click causes one persistence call
# ---------------------------------------------------------------------------


def test_one_click_causes_one_persistence_call(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["fake_audit_calls"] == 1


# ---------------------------------------------------------------------------
# 5. Successful ordinary reruns cause zero additional writes
# ---------------------------------------------------------------------------


def test_ordinary_reruns_cause_zero_additional_writes(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["fake_audit_calls"] == 1

    at.run(timeout=10)
    at.run(timeout=10)
    at.run(timeout=10)
    assert at.session_state["fake_audit_calls"] == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


# ---------------------------------------------------------------------------
# 6. Success rendering: exact message and audit ID, never the full path
# ---------------------------------------------------------------------------


def test_success_renders_exact_message_and_audit_id_not_full_path(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    assert "Audit record written." in [s.value for s in at.success]
    stored_path = at.session_state["audit_record_path"]
    audit_id = Path(stored_path).stem
    expected_caption = f"Audit ID: {audit_id}"
    assert expected_caption in [c.value for c in at.caption]

    # The full local filesystem path must never be rendered anywhere.
    rendered_text = "\n".join(
        [c.value for c in at.caption]
        + [s.value for s in at.success]
        + [m.value for m in at.markdown]
    )
    assert str(tmp_path) not in rendered_text
    assert stored_path not in rendered_text


# ---------------------------------------------------------------------------
# 7-9. Failure: approval remains finalized, exact sanitized message, retry button
# ---------------------------------------------------------------------------


def test_failure_leaves_approval_finalized(tmp_path):
    at = _app_with_always_fail(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    assert "Decision: APPROVED" in [s.value for s in at.success]
    assert "Approver: Carol" in [m.value for m in at.markdown]


def test_failure_renders_exact_sanitized_message_no_raw_exception(tmp_path):
    at = _app_with_always_fail(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    errors = [e.value for e in at.error]
    assert "The decision was finalized, but its audit record could not be written." in errors
    joined = "\n".join(errors)
    assert "OSError" not in joined
    assert "simulated disk failure" not in joined
    assert "Traceback" not in joined
    assert str(tmp_path) not in joined


def test_failure_renders_exactly_one_retry_button(tmp_path):
    at = _app_with_always_fail(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    retry_buttons = [b for b in at.button if b.key == "retry_audit_recording"]
    assert len(retry_buttons) == 1
    assert not any(b.key == "approve_review" for b in at.button)
    assert not any(b.key == "reject_review" for b in at.button)


def test_failure_stores_no_success_path(tmp_path):
    at = _app_with_always_fail(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["audit_record_path"] is None
    assert at.session_state["audit_record_error"] is not None
    assert list(tmp_path.glob("*.json")) == []


# ---------------------------------------------------------------------------
# 10-12. Retry behavior
# ---------------------------------------------------------------------------


def test_retry_performs_no_second_approval_call(tmp_path):
    at = _app_with_fail_first_and_approve_counter(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["fake_approve_calls"] == 1

    at.button(key="retry_audit_recording").click().run(timeout=10)
    at.run(timeout=10)

    assert at.session_state["fake_approve_calls"] == 1


def test_retry_success_clears_error_and_records_path(tmp_path):
    at = _app_with_fail_first_call(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["audit_record_error"] is not None
    assert at.session_state["fake_audit_calls"] == 1

    at.button(key="retry_audit_recording").click().run(timeout=10)
    at.run(timeout=10)

    assert at.session_state["fake_audit_calls"] == 2
    assert at.session_state["audit_record_error"] is None
    assert at.session_state["audit_record_path"] is not None
    assert "Audit record written." in [s.value for s in at.success]
    assert not any(e.value.startswith("The decision was finalized") for e in at.error)
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_no_automatic_retry_on_ordinary_rerun(tmp_path):
    at = _app_with_always_fail(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["fake_audit_calls"] == 1

    at.run(timeout=10)
    at.run(timeout=10)
    assert at.session_state["fake_audit_calls"] == 1


# ---------------------------------------------------------------------------
# 13-14. New submission clears audit state
# ---------------------------------------------------------------------------


def test_new_valid_submission_clears_audit_state(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["audit_record_path"] is not None

    _submit_valid_sample(at)

    assert at.session_state["audit_record_path"] is None
    assert at.session_state["audit_record_error"] is None
    assert not any(s.value == "Audit record written." for s in at.success)


def test_new_invalid_submission_clears_audit_state(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["audit_record_path"] is not None

    at.text_input(key="review_id").set_value("")
    at.text_input(key="reviewer_name").set_value("")
    at.button(key="submit_review").click().run(timeout=10)

    assert at.session_state["locked_review_result"] is None
    assert at.session_state["audit_record_path"] is None
    assert at.session_state["audit_record_error"] is None


# ---------------------------------------------------------------------------
# 15. Gemini explanation state and audit state remain independent
# ---------------------------------------------------------------------------


_FAKE_EXPLANATION_BODY = """
def _fake_generate_explanation(prompt, config):
    from src.gemini_analyzer import ExplanationResult, ExplanationStatus
    return ExplanationResult(
        status=ExplanationStatus.GENERATED,
        explanation_text="an explanation",
        model_name="gemini-2.5-flash-lite",
    )

app.generate_explanation = _fake_generate_explanation
"""


def test_explanation_click_does_not_affect_audit_state(tmp_path):
    at = AppTest.from_string(
        _build_script(tmp_path, _REDIRECT_TO_TMP_BODY, _FAKE_EXPLANATION_BODY)
    )
    at.run(timeout=10)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["fake_audit_calls"] == 1

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)

    assert at.session_state["fake_audit_calls"] == 1
    assert "Audit record written." in [s.value for s in at.success]


def test_audit_recording_does_not_affect_explanation_state(tmp_path):
    at = AppTest.from_string(
        _build_script(tmp_path, _REDIRECT_TO_TMP_BODY, _FAKE_EXPLANATION_BODY)
    )
    at.run(timeout=10)
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert at.session_state["portfolio_explanation_result"] is not None

    _approve(at, "Carol")

    assert at.session_state["portfolio_explanation_result"] is not None
    assert at.session_state["audit_record_path"] is not None


# ---------------------------------------------------------------------------
# 16. Deterministic result unchanged throughout
# ---------------------------------------------------------------------------


def test_locked_result_unchanged_after_audit_success(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    snapshot = at.session_state["locked_review_result"].model_dump()

    _approve(at, "Carol")

    assert at.session_state["locked_review_result"].model_dump() == snapshot
    rows = at.dataframe[0].value.to_dict("records")
    assert [row["campaign_id"] for row in rows] == ["G001", "M001", "G002", "G003"]


def test_locked_result_unchanged_after_audit_failure(tmp_path):
    at = _app_with_always_fail(tmp_path)
    _submit_valid_sample(at)
    snapshot = at.session_state["locked_review_result"].model_dump()

    _approve(at, "Carol")

    assert at.session_state["locked_review_result"].model_dump() == snapshot


# ---------------------------------------------------------------------------
# 17. No real filesystem write, network call, Gemini client, or real API key
# ---------------------------------------------------------------------------


def test_no_write_to_real_audit_records_directory(tmp_path, monkeypatch):
    real_records_dir = Path(__file__).resolve().parent.parent / "audit_records"
    before = set(real_records_dir.glob("*.json")) if real_records_dir.exists() else set()

    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    after = set(real_records_dir.glob("*.json")) if real_records_dir.exists() else set()
    assert after == before


def test_no_gemini_api_key_required_for_audit_success(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert "Audit record written." in [s.value for s in at.success]
