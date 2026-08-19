"""Tests for the Stage 35 CSV-export UI wiring in app.py
(Sprint 3 — Development Stage 35).

Covers: the "CSV export" section is absent without a locked result,
before a decision, and while audit recording has failed or has not yet
succeeded; it appears only once `record_campaign_reallocation_audit` has
actually returned a path, identically for `APPROVED` and `REJECTED`
audits; the exact download-button label, and — via source-level
inspection, since `AppTest` does not expose `st.download_button`'s
underlying bytes/filename/MIME through any stable public property in
this Streamlit version — the exact literal `file_name`/`mime` arguments
used; the exact rows/CSV text actually built from the exact stored
`CampaignReallocationAudit` object (verified via a capturing wrapper
around the real Stage 35 functions); deterministic, non-duplicated
generation across reruns; audit-retry interaction; session-state
clearing on new submissions; sanitized failure rendering; and isolation
from Gemini, the network, and any real filesystem write. No test ever
writes to the real repository `audit_records/` directory.
"""

import ast
import inspect
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
import src.approval
import src.audit
import src.exports
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

    Mirrors the established pattern in `tests/test_app_audit.py`: several
    tests below override `app.record_campaign_reallocation_audit` and/or
    the Stage 35 export functions directly on the shared `app` module
    object from within an embedded `AppTest.from_string` script. Because
    that mutation is not undone by pytest's own `monkeypatch` bookkeeping,
    it would otherwise leak into every test that runs after it -- in this
    file or any other. This fixture resets all of them to their real
    Stage 27/31/33/34/35 implementations before every test, regardless of
    order.
    """
    monkeypatch.setattr(app, "approve_campaign_reallocation_review", src.approval.approve_campaign_reallocation_review)
    monkeypatch.setattr(app, "reject_campaign_reallocation_review", src.approval.reject_campaign_reallocation_review)
    monkeypatch.setattr(app, "generate_explanation", generate_explanation)
    monkeypatch.setattr(app, "run_budget_reallocation_review", src.pipeline.run_budget_reallocation_review)
    monkeypatch.setattr(app, "build_campaign_reallocation_audit", src.audit.build_campaign_reallocation_audit)
    monkeypatch.setattr(app, "record_campaign_reallocation_audit", src.audit.record_campaign_reallocation_audit)
    monkeypatch.setattr(app, "build_campaign_reallocation_export_rows", src.exports.build_campaign_reallocation_export_rows)
    monkeypatch.setattr(app, "serialize_campaign_reallocation_export_csv", src.exports.serialize_campaign_reallocation_export_csv)


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

_ALWAYS_FAIL_AUDIT_BODY = """
def _record(audit, *, directory=None):
    st.session_state["fake_audit_calls"] += 1
    raise OSError("simulated disk failure")

app.record_campaign_reallocation_audit = _record
"""

_FAIL_FIRST_CALL_AUDIT_BODY = """
def _record(audit, *, directory=None):
    st.session_state["fake_audit_calls"] += 1
    if st.session_state["fake_audit_calls"] == 1:
        raise OSError("simulated disk failure")
    return _real_record(audit, directory=_AUDIT_DIR)

app.record_campaign_reallocation_audit = _record
"""

_CAPTURE_EXPORT_BODY = """
_real_build_rows = app.build_campaign_reallocation_export_rows
_real_serialize = app.serialize_campaign_reallocation_export_csv

if "export_build_calls" not in st.session_state:
    st.session_state["export_build_calls"] = 0

def _capture_build_rows(audit):
    st.session_state["export_build_calls"] += 1
    st.session_state["captured_export_audit_id"] = audit.audit_id
    rows = _real_build_rows(audit)
    return rows

def _capture_serialize(rows):
    csv_text = _real_serialize(rows)
    st.session_state["captured_export_csv"] = csv_text
    return csv_text

app.build_campaign_reallocation_export_rows = _capture_build_rows
app.serialize_campaign_reallocation_export_csv = _capture_serialize
"""

_EXPORT_ALWAYS_FAIL_BODY = """
def _raising_build_rows(audit):
    raise RuntimeError("simulated export failure")

app.build_campaign_reallocation_export_rows = _raising_build_rows
"""


def _build_script(tmp_path: Path, *bodies: str) -> str:
    header = _AUDIT_HEADER.format(tmp_path_repr=repr(str(tmp_path)))
    return header + "".join(bodies) + "\napp.main()\n"


def _app_with_redirect(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(_build_script(tmp_path, _REDIRECT_TO_TMP_BODY))
    at.run(timeout=10)
    return at


def _app_with_redirect_and_capture(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(
        _build_script(tmp_path, _REDIRECT_TO_TMP_BODY, _CAPTURE_EXPORT_BODY)
    )
    at.run(timeout=10)
    return at


def _app_with_always_fail_audit(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(_build_script(tmp_path, _ALWAYS_FAIL_AUDIT_BODY))
    at.run(timeout=10)
    return at


def _app_with_fail_first_audit(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(_build_script(tmp_path, _FAIL_FIRST_CALL_AUDIT_BODY))
    at.run(timeout=10)
    return at


def _app_with_redirect_and_export_failure(tmp_path: Path) -> AppTest:
    at = AppTest.from_string(
        _build_script(tmp_path, _REDIRECT_TO_TMP_BODY, _EXPORT_ALWAYS_FAIL_BODY)
    )
    at.run(timeout=10)
    return at


def _download_labels(at: AppTest) -> list[str]:
    return [b.label for b in at.download_button]


# ---------------------------------------------------------------------------
# 1-3. Export section absent without a locked result, before a decision,
# and while audit recording has failed
# ---------------------------------------------------------------------------


def test_export_absent_without_locked_result(tmp_path):
    at = _app_with_redirect(tmp_path)
    assert "CSV export" not in [s.value for s in at.subheader]
    assert _download_labels(at) == []


def test_export_absent_before_decision(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    assert "CSV export" not in [s.value for s in at.subheader]
    assert _download_labels(at) == []


def test_export_absent_while_audit_recording_failed(tmp_path):
    at = _app_with_always_fail_audit(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    assert at.session_state["audit_record_path"] is None
    assert at.session_state["audit_record"] is None
    assert "CSV export" not in [s.value for s in at.subheader]
    assert _download_labels(at) == []


# ---------------------------------------------------------------------------
# 4-6. Present only after persistence succeeds; approved and rejected
# ---------------------------------------------------------------------------


def test_export_present_after_approved_audit_success(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    assert at.session_state["audit_record_path"] is not None
    assert at.session_state["audit_record"] is not None
    assert "CSV export" in [s.value for s in at.subheader]
    assert _download_labels(at) == ["Download audited recommendations CSV"]


def test_export_present_after_rejected_audit_success(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _reject(at, "Dave")

    assert at.session_state["audit_record_path"] is not None
    assert at.session_state["audit_record"] is not None
    assert "CSV export" in [s.value for s in at.subheader]
    assert _download_labels(at) == ["Download audited recommendations CSV"]


# ---------------------------------------------------------------------------
# 7. Exact download-button label
# ---------------------------------------------------------------------------


def test_exact_download_button_label(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    buttons = list(at.download_button)
    assert len(buttons) == 1
    assert buttons[0].label == "Download audited recommendations CSV"
    assert buttons[0].key == "download_export_csv"


# ---------------------------------------------------------------------------
# 8-9. Exact filename and MIME type (source-level, since AppTest exposes
# no stable public accessor for a download_button's file_name/mime/data)
# ---------------------------------------------------------------------------


def test_exact_filename_and_mime_in_source():
    tree = ast.parse(inspect.getsource(app._render_export_section))
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "download_button"
    )
    keyword_names = {kw.arg for kw in call.keywords}
    assert "file_name" in keyword_names
    assert "mime" in keyword_names

    file_name_node = next(kw.value for kw in call.keywords if kw.arg == "file_name")
    assert isinstance(file_name_node, ast.JoinedStr)
    rendered_source = ast.unparse(file_name_node)
    assert rendered_source == "f'{audit.audit_id}.csv'"

    mime_node = next(kw.value for kw in call.keywords if kw.arg == "mime")
    assert isinstance(mime_node, ast.Constant)
    assert mime_node.value == "text/csv"


# ---------------------------------------------------------------------------
# 10-11. Exact CSV content and exact source audit object
# ---------------------------------------------------------------------------


def test_export_uses_exact_stored_audit_and_produces_matching_csv(tmp_path):
    at = _app_with_redirect_and_capture(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol", note="fine")

    stored_audit = at.session_state["audit_record"]
    assert at.session_state["captured_export_audit_id"] == stored_audit.audit_id

    expected_csv = src.exports.serialize_campaign_reallocation_export_csv(
        src.exports.build_campaign_reallocation_export_rows(stored_audit)
    )
    assert at.session_state["captured_export_csv"] == expected_csv
    assert "REV-1" in at.session_state["captured_export_csv"]
    assert "Carol" in at.session_state["captured_export_csv"]


# ---------------------------------------------------------------------------
# 12-13. Deterministic across reruns; no rebuild/rewrite on ordinary reruns
# ---------------------------------------------------------------------------


def test_repeated_reruns_produce_identical_export_content(tmp_path):
    at = _app_with_redirect_and_capture(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    first_csv = at.session_state["captured_export_csv"]
    first_build_calls = at.session_state["export_build_calls"]

    at.run(timeout=10)
    at.run(timeout=10)

    assert at.session_state["captured_export_csv"] == first_csv
    # The export is rebuilt from the same stored audit on each render pass
    # (cheap, in-memory, deterministic) but never triggers a new audit
    # write or a different result.
    assert at.session_state["fake_audit_calls"] == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_ordinary_reruns_do_not_rewrite_audit_file(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    written_before = list(tmp_path.glob("*.json"))

    at.run(timeout=10)
    at.run(timeout=10)
    at.run(timeout=10)

    written_after = list(tmp_path.glob("*.json"))
    assert written_after == written_before
    assert at.session_state["fake_audit_calls"] == 1


# ---------------------------------------------------------------------------
# 14. Successful audit retry makes the export appear
# ---------------------------------------------------------------------------


def test_successful_audit_retry_makes_export_appear(tmp_path):
    at = _app_with_fail_first_audit(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert "CSV export" not in [s.value for s in at.subheader]

    at.button(key="retry_audit_recording").click().run(timeout=10)
    at.run(timeout=10)

    assert at.session_state["audit_record_path"] is not None
    assert at.session_state["audit_record"] is not None
    assert "CSV export" in [s.value for s in at.subheader]
    assert _download_labels(at) == ["Download audited recommendations CSV"]


# ---------------------------------------------------------------------------
# 15-16. New submissions clear the export audit-object state
# ---------------------------------------------------------------------------


def test_new_valid_submission_clears_export_audit_state(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["audit_record"] is not None

    _submit_valid_sample(at)

    assert at.session_state["audit_record"] is None
    assert "CSV export" not in [s.value for s in at.subheader]
    assert _download_labels(at) == []


def test_new_invalid_submission_clears_export_audit_state(tmp_path):
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["audit_record"] is not None

    at.text_input(key="review_id").set_value("")
    at.text_input(key="reviewer_name").set_value("")
    at.button(key="submit_review").click().run(timeout=10)

    assert at.session_state["locked_review_result"] is None
    assert at.session_state["audit_record"] is None


# ---------------------------------------------------------------------------
# 17-18. Export failure: generic message only; nothing else mutated
# ---------------------------------------------------------------------------


def test_export_failure_displays_only_generic_message(tmp_path):
    at = _app_with_redirect_and_export_failure(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    errors = [e.value for e in at.error]
    assert (
        "The CSV export could not be prepared. The finalized review and "
        "audit record remain unchanged."
    ) in errors
    joined = "\n".join(errors)
    assert "RuntimeError" not in joined
    assert "simulated export failure" not in joined
    assert "Traceback" not in joined
    assert _download_labels(at) == []


def test_export_failure_leaves_locked_result_approval_and_audit_unchanged(tmp_path):
    at = _app_with_redirect_and_export_failure(tmp_path)
    _submit_valid_sample(at)
    result_snapshot = at.session_state["locked_review_result"].model_dump()

    _approve(at, "Carol")

    assert at.session_state["locked_review_result"].model_dump() == result_snapshot
    assert "Decision: APPROVED" in [s.value for s in at.success]
    assert at.session_state["audit_record_path"] is not None
    assert at.session_state["audit_record"] is not None
    assert not at.exception


# ---------------------------------------------------------------------------
# 19-20. No Gemini invocation; no pipeline rerun
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

_COUNT_PIPELINE_CALLS_BODY = """
from src.pipeline import run_budget_reallocation_review as _real_run

if "pipeline_calls" not in st.session_state:
    st.session_state["pipeline_calls"] = 0

def _counting_run(review, campaigns):
    st.session_state["pipeline_calls"] += 1
    return _real_run(review, campaigns)

app.run_budget_reallocation_review = _counting_run
"""


def test_export_section_never_triggers_gemini(tmp_path):
    at = AppTest.from_string(
        _build_script(tmp_path, _REDIRECT_TO_TMP_BODY, _FAKE_EXPLANATION_BODY)
    )
    at.run(timeout=10)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    # The export section rendered without ever calling the explanation
    # click handler.
    assert at.session_state["portfolio_explanation_result"] is None
    assert "CSV export" in [s.value for s in at.subheader]


def test_export_section_never_reruns_the_pipeline(tmp_path):
    at = AppTest.from_string(
        _build_script(tmp_path, _REDIRECT_TO_TMP_BODY, _COUNT_PIPELINE_CALLS_BODY)
    )
    at.run(timeout=10)
    _submit_valid_sample(at)
    assert at.session_state["pipeline_calls"] == 1

    _approve(at, "Carol")
    at.run(timeout=10)
    at.run(timeout=10)

    assert at.session_state["pipeline_calls"] == 1


# ---------------------------------------------------------------------------
# 21-23. No real API key exposure; no real export/audit file left behind
# ---------------------------------------------------------------------------


def test_no_gemini_api_key_required_for_export(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert "CSV export" in [s.value for s in at.subheader]


def test_no_write_to_real_audit_records_directory(tmp_path):
    real_records_dir = Path(__file__).resolve().parent.parent / "audit_records"
    before = set(real_records_dir.glob("*.json")) if real_records_dir.exists() else set()

    at = _app_with_redirect_and_capture(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    at.run(timeout=10)

    after = set(real_records_dir.glob("*.json")) if real_records_dir.exists() else set()
    assert after == before


def test_no_export_directory_created_anywhere(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    before = {p.name for p in repo_root.iterdir()}

    at = _app_with_redirect(tmp_path)
    _submit_valid_sample(at)
    _approve(at, "Carol")

    after = {p.name for p in repo_root.iterdir()}
    assert after == before
    assert not (repo_root / "exports").exists()
