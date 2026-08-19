"""End-to-end integration tests for the AI Budget Reallocation Agent
(Sprint 3 — Development Stage 36).

Proves the complete frozen Sprint 3 flow works together through real
Streamlit `AppTest` widget interaction — not that any individual
component is correct (that is each earlier stage's own focused test
file's responsibility):

    CSV upload -> review-setup validation -> campaign validation
    -> deterministic pipeline -> locked result -> optional Gemini
    explanation -> human approval or rejection -> immutable audit
    construction -> successful audit persistence -> audited CSV export
    availability

Every scenario that approves or rejects uses `AppTest.from_string` with
the established Stage 34/35 embedded audit-directory redirect (never
`AppTest.from_file`, which does not honor an external monkeypatch of a
real approve/reject click's automatic audit write). No real Gemini SDK
client is ever constructed, no real network call is ever made, no real
API key is used or required, and no test ever writes into the
repository's real `audit_records/` directory or creates an `exports/`
directory.
"""

import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import sys

import pytest
from streamlit.testing.v1 import AppTest

import app
import src.approval
import src.audit
import src.exports
import src.gemini_analyzer
import src.pipeline
from src.gemini_analyzer import generate_explanation

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_ORIGINAL_GEMINI_ANALYZER_MODULE = src.gemini_analyzer


@pytest.fixture(autouse=True)
def _ensure_stable_gemini_analyzer_module():
    """Defensive isolation, scoped to this file.

    `tests/test_gemini_analyzer.py::test_import_performs_no_client_construction_environment_or_network`
    pops `src.gemini_analyzer` from `sys.modules` and reimports it fresh,
    to prove import-time side-effect freedom -- leaving a *different*
    module object (with a *different* `ExplanationStatus` class) installed
    under that name for the rest of the process. `app.py`'s own
    module-level `ExplanationStatus`/`ExplanationResult` name bindings were
    already captured from the original module when `app` was first
    imported, so a fake `generate_explanation` built in this file that
    does `from src.gemini_analyzer import ExplanationStatus` at call time
    would otherwise pick up the reimported class, breaking `app.py`'s own
    `is ExplanationStatus.GENERATED` identity check with no error raised
    at the click boundary (the failure surfaces deep inside rendering,
    outside that boundary's own `try/except`). This fixture restores
    `sys.modules["src.gemini_analyzer"]` to the original module object
    (captured at this file's own import/collection time, before any test
    body runs) before every test, regardless of order. This does not
    modify `tests/test_gemini_analyzer.py` or any other file.
    """
    sys.modules["src.gemini_analyzer"] = _ORIGINAL_GEMINI_ANALYZER_MODULE
    yield
    sys.modules["src.gemini_analyzer"] = _ORIGINAL_GEMINI_ANALYZER_MODULE


@pytest.fixture(autouse=True)
def _ensure_real_app_functions(monkeypatch):
    """Defensive isolation, scoped to this file.

    Every scenario below overrides one or more of `app.record_campaign_reallocation_audit`,
    `app.generate_explanation`, `app.run_budget_reallocation_review`,
    `app.build_campaign_reallocation_export_rows`, and
    `app.serialize_campaign_reallocation_export_csv` directly on the shared
    `app` module object from within an embedded `AppTest.from_string`
    script -- the only mechanism that reliably takes effect, since
    `AppTest.from_file` executes in a namespace that does not honor an
    external monkeypatch of these functions (confirmed empirically at
    Stage 34). Because that mutation is not undone by pytest's own
    `monkeypatch` bookkeeping, it would otherwise leak from one scenario
    into every scenario that runs after it. This fixture resets all five
    to their real Stage 27/31/33/34/35 implementations before every test,
    regardless of order, mirroring the identical established pattern in
    `tests/test_app_audit.py` and `tests/test_app_exports.py`.
    """
    monkeypatch.setattr(app, "approve_campaign_reallocation_review", src.approval.approve_campaign_reallocation_review)
    monkeypatch.setattr(app, "reject_campaign_reallocation_review", src.approval.reject_campaign_reallocation_review)
    monkeypatch.setattr(app, "generate_explanation", generate_explanation)
    monkeypatch.setattr(app, "run_budget_reallocation_review", src.pipeline.run_budget_reallocation_review)
    monkeypatch.setattr(app, "build_campaign_reallocation_audit", src.audit.build_campaign_reallocation_audit)
    monkeypatch.setattr(app, "record_campaign_reallocation_audit", src.audit.record_campaign_reallocation_audit)
    monkeypatch.setattr(app, "build_campaign_reallocation_export_rows", src.exports.build_campaign_reallocation_export_rows)
    monkeypatch.setattr(app, "serialize_campaign_reallocation_export_csv", src.exports.serialize_campaign_reallocation_export_csv)

VALID_REVIEW = {
    "review_id": "REV-1",
    "review_date": date(2026, 8, 5),
    "period_start": date(2026, 8, 1),
    "period_end": date(2026, 8, 10),
    "reviewer_name": "Reviewer",
    "approved_monthly_budget": "10000.00",
    "initial_account_reserve": "0.00",
}


# ---------------------------------------------------------------------------
# Real-widget UI helpers (mirrors the established pattern already used in
# tests/test_app.py, tests/test_app_explanation.py, tests/test_app_approval.py,
# tests/test_app_audit.py, and tests/test_app_exports.py)
# ---------------------------------------------------------------------------


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


def _upload_csv(at: AppTest, content: bytes, filename: str = "campaigns.csv") -> None:
    at.file_uploader(key="campaign_csv").set_value((filename, content, "text/csv"))


def _upload_sample_csv(at: AppTest) -> None:
    _upload_csv(at, (DATA_DIR / "sample_campaigns.csv").read_bytes(), "sample_campaigns.csv")


def _submit(at: AppTest) -> None:
    at.button(key="submit_review").click().run(timeout=10)


def _submit_valid_sample(at: AppTest, overrides: dict | None = None) -> None:
    _fill_review_inputs(at, overrides)
    _upload_sample_csv(at)
    _submit(at)
    assert at.session_state["locked_review_result"] is not None


def _flush_rerun_if_decided(at: AppTest) -> None:
    # A successful decision calls st.rerun(); AppTest does not fold that
    # rerun into the same .run() that triggered it, so one more explicit
    # run is needed to observe the post-rerun, controls-replaced state.
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


def _parse_csv(csv_text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(csv_text)))


def _download_labels(at: AppTest) -> list[str]:
    return [b.label for b in at.download_button]


# ---------------------------------------------------------------------------
# Embedded-script header and composable bodies -- every scenario below
# builds its own AppTest.from_string script from these pieces, mirroring
# the established Stage 34/35 pattern verbatim.
# ---------------------------------------------------------------------------

_HEADER = """
import app
import streamlit as st
import src.audit as audit_module
from pathlib import Path

_real_record = audit_module.record_campaign_reallocation_audit
_AUDIT_DIR = Path({tmp_path_repr})

if "audit_calls" not in st.session_state:
    st.session_state["audit_calls"] = 0
"""

_REDIRECT_AUDIT_BODY = """
def _record(audit, *, directory=None):
    st.session_state["audit_calls"] += 1
    return _real_record(audit, directory=_AUDIT_DIR)

app.record_campaign_reallocation_audit = _record
"""

_FAIL_FIRST_AUDIT_BODY = """
def _record(audit, *, directory=None):
    st.session_state["audit_calls"] += 1
    if st.session_state["audit_calls"] == 1:
        raise OSError("simulated disk failure")
    return _real_record(audit, directory=_AUDIT_DIR)

app.record_campaign_reallocation_audit = _record
"""

_CAPTURE_EXPORT_BODY = """
_real_build_rows = app.build_campaign_reallocation_export_rows
_real_serialize = app.serialize_campaign_reallocation_export_csv

def _capture_build_rows(audit):
    return _real_build_rows(audit)

def _capture_serialize(rows):
    csv_text = _real_serialize(rows)
    st.session_state["captured_export_csv"] = csv_text
    return csv_text

app.build_campaign_reallocation_export_rows = _capture_build_rows
app.serialize_campaign_reallocation_export_csv = _capture_serialize
"""

_FAKE_GENERATED_EXPLANATION_BODY = """
if "explanation_calls" not in st.session_state:
    st.session_state["explanation_calls"] = 0

def _fake_generate_explanation(prompt, config):
    from src.gemini_analyzer import ExplanationResult, ExplanationStatus
    st.session_state["explanation_calls"] += 1
    return ExplanationResult(
        status=ExplanationStatus.GENERATED,
        explanation_text="INTEGRATION_FAKE_EXPLANATION_TEXT",
        model_name="gemini-2.5-flash-lite",
    )

app.generate_explanation = _fake_generate_explanation
"""

_UNCONSERVED_PIPELINE_BODY = """
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

_COUNT_PIPELINE_CALLS_BODY = """
from src.pipeline import run_budget_reallocation_review as _real_pipeline_run

if "pipeline_calls" not in st.session_state:
    st.session_state["pipeline_calls"] = 0

def _counting_run(review, campaigns):
    st.session_state["pipeline_calls"] += 1
    return _real_pipeline_run(review, campaigns)

app.run_budget_reallocation_review = _counting_run
"""


def _build_script(tmp_path: Path, *bodies: str) -> str:
    header = _HEADER.format(tmp_path_repr=repr(str(tmp_path)))
    return header + "".join(bodies) + "\napp.main()\n"


def _launch(tmp_path: Path, *bodies: str) -> AppTest:
    at = AppTest.from_string(_build_script(tmp_path, *bodies))
    at.run(timeout=10)
    assert not at.exception
    return at


# ---------------------------------------------------------------------------
# Scenario A -- approved flow, upload through export
# ---------------------------------------------------------------------------


def test_scenario_a_approved_flow_upload_through_export(tmp_path):
    at = _launch(tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY)

    _submit_valid_sample(at)
    result = at.session_state["locked_review_result"]
    assert result is not None
    assert result.total_current_budget == Decimal("11700.00")
    assert result.total_recommended_budget == Decimal("11700.00")
    assert result.conservation.is_conserved is True

    _approve(at, "Carol", note="Looks good")

    assert at.session_state["audit_calls"] == 1
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1

    assert "Decision: APPROVED" in [s.value for s in at.success]
    assert "Approver: Carol" in [m.value for m in at.markdown]

    audit = at.session_state["audit_record"]
    assert audit is not None
    assert audit.review_id == "REV-1"
    assert audit.approval.decision.value == "APPROVED"
    assert audit.approval.reviewer_name == "Carol"
    assert audit.approval.note == "Looks good"

    assert _download_labels(at) == ["Download audited recommendations CSV"]

    rows = _parse_csv(at.session_state["captured_export_csv"])
    assert len(rows) == 4
    assert [r["campaign_id"] for r in rows] == ["G001", "M001", "G002", "G003"]

    for row in rows:
        assert row["audit_id"] == audit.audit_id
        assert row["review_id"] == "REV-1"
        assert row["decision"] == "APPROVED"
        assert row["reviewer_name"] == "Carol"
        assert row["decision_note"] == "Looks good"
        assert row["total_current_budget"] == "11700.00"
        assert row["total_recommended_budget"] == "11700.00"
        assert row["is_conserved"] == "True"

    by_id = {r["campaign_id"]: r for r in rows}
    assert by_id["G001"]["recommendation_action"] == "MAINTAIN"
    assert by_id["G001"]["allocated_amount"] == "0.00"
    assert by_id["G001"]["recommended_budget"] == "3000.00"
    assert by_id["G001"]["rank"] == "Not ranked"
    assert by_id["G001"]["reason_codes"] == "NEAR_TARGET, RECENT_TREND_STABLE"

    assert by_id["M001"]["recommendation_action"] == "MAINTAIN"
    assert by_id["M001"]["allocated_amount"] == "0.00"
    assert by_id["M001"]["recommended_budget"] == "2500.00"
    assert by_id["M001"]["rank"] == "Not ranked"
    assert by_id["M001"]["reason_codes"] == "NEAR_TARGET, RECENT_TREND_STABLE"

    assert by_id["G002"]["recommendation_action"] == "INCREASE"
    assert by_id["G002"]["allocated_amount"] == "0.00"
    assert by_id["G002"]["recommended_budget"] == "5000.00"
    assert by_id["G002"]["rank"] == "1"
    assert by_id["G002"]["reason_codes"] == "ABOVE_TARGET_STRONG, RECENT_TREND_IMPROVING"

    assert by_id["G003"]["recommendation_action"] == "MAINTAIN"
    assert by_id["G003"]["allocated_amount"] == "0.00"
    assert by_id["G003"]["recommended_budget"] == "1200.00"
    assert by_id["G003"]["rank"] == "Not ranked"
    assert by_id["G003"]["reason_codes"] == "NEAR_TARGET, RECENT_TREND_STABLE"


# ---------------------------------------------------------------------------
# Scenario B -- rejected flow, upload through export
# ---------------------------------------------------------------------------


def test_scenario_b_rejected_flow_upload_through_export(tmp_path):
    at = _launch(tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY)

    _submit_valid_sample(at)
    result_snapshot = at.session_state["locked_review_result"].model_dump()

    _reject(at, "Dave", note="Budget too tight this month")

    assert at.session_state["locked_review_result"].model_dump() == result_snapshot
    assert "Decision: REJECTED" in [w.value for w in at.warning]

    assert at.session_state["audit_calls"] == 1
    assert len(list(tmp_path.glob("*.json"))) == 1

    audit = at.session_state["audit_record"]
    assert audit.approval.decision.value == "REJECTED"

    assert _download_labels(at) == ["Download audited recommendations CSV"]
    rows = _parse_csv(at.session_state["captured_export_csv"])
    assert len(rows) == 4
    for row in rows:
        assert row["decision"] == "REJECTED"

    # No reconsider/overwrite controls, and no advertising-platform action
    # path exists anywhere in this codebase.
    assert not any(b.key in ("approve_review", "reject_review") for b in at.button)


# ---------------------------------------------------------------------------
# Scenario C -- generated explanation remains supplementary
# ---------------------------------------------------------------------------


def test_scenario_c_generated_explanation_remains_supplementary(tmp_path):
    at = _launch(
        tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY, _FAKE_GENERATED_EXPLANATION_BODY
    )
    _submit_valid_sample(at)
    snapshot = at.session_state["locked_review_result"].model_dump()

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert at.session_state["explanation_calls"] == 1
    assert "INTEGRATION_FAKE_EXPLANATION_TEXT" in [m.value for m in at.markdown]
    assert any("AI-generated using" in c.value for c in at.caption)

    at.selectbox(key="explanation_campaign_id").set_value("G002 — Shopping - Core Catalog")
    at.button(key="generate_campaign_explanation").click().run(timeout=10)
    assert at.session_state["explanation_calls"] == 2

    # A bare rerun (no click) must never call Gemini again.
    at.run(timeout=10)
    assert at.session_state["explanation_calls"] == 2

    assert at.session_state["locked_review_result"].model_dump() == snapshot

    _approve(at, "Carol")
    assert at.session_state["audit_calls"] == 1

    audit_json_text = list(tmp_path.glob("*.json"))[0].read_text(encoding="utf-8")
    assert "INTEGRATION_FAKE_EXPLANATION_TEXT" not in audit_json_text

    csv_text = at.session_state["captured_export_csv"]
    assert "INTEGRATION_FAKE_EXPLANATION_TEXT" not in csv_text
    assert _download_labels(at) == ["Download audited recommendations CSV"]


# ---------------------------------------------------------------------------
# Scenario D -- Gemini unavailable does not block the workflow
# ---------------------------------------------------------------------------


def test_scenario_d_gemini_unavailable_does_not_block_workflow(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = _launch(tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY)
    _submit_valid_sample(at)

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert not at.exception
    assert any("not configured" in i.value for i in at.info)

    _approve(at, "Carol")

    assert at.session_state["audit_calls"] == 1
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert _download_labels(at) == ["Download audited recommendations CSV"]


# ---------------------------------------------------------------------------
# Scenario E -- unconserved result blocks approval, permits rejection
# ---------------------------------------------------------------------------


def test_scenario_e_unconserved_result_blocks_approval_but_allows_rejection(tmp_path):
    at = _launch(
        tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY, _UNCONSERVED_PIPELINE_BODY
    )
    _submit_valid_sample(at)
    assert at.session_state["locked_review_result"].conservation.is_conserved is False

    _approve(at, "Carol")
    assert "An unconserved allocation cannot be approved." in [e.value for e in at.error]
    assert at.session_state["approval_decision_result"] is None
    assert at.session_state["audit_calls"] == 0

    _reject(at, "Carol")
    assert "Decision: REJECTED" in [w.value for w in at.warning]
    assert at.session_state["audit_calls"] == 1
    assert len(list(tmp_path.glob("*.json"))) == 1

    audit = at.session_state["audit_record"]
    assert audit.approval.decision.value == "REJECTED"
    assert audit.result.conservation.is_conserved is False

    rows = _parse_csv(at.session_state["captured_export_csv"])
    for row in rows:
        assert row["decision"] == "REJECTED"
        assert row["is_conserved"] == "False"
        # Nothing is repaired, rebalanced, recalculated, or rerun -- the
        # recommendations are the same ones the pipeline actually produced.
    assert {row["recommendation_action"] for row in rows} == {"MAINTAIN", "INCREASE"}


# ---------------------------------------------------------------------------
# Scenario F -- audit failure then retry
# ---------------------------------------------------------------------------


def test_scenario_f_audit_failure_then_retry(tmp_path):
    at = _launch(tmp_path, _FAIL_FIRST_AUDIT_BODY, _CAPTURE_EXPORT_BODY)
    _submit_valid_sample(at)
    result_snapshot = at.session_state["locked_review_result"].model_dump()

    _approve(at, "Carol")
    assert "Decision: APPROVED" in [s.value for s in at.success]
    approval_snapshot = at.session_state["approval_decision_result"]

    errors = [e.value for e in at.error]
    assert (
        "The decision was finalized, but its audit record could not be written."
    ) in errors
    joined = "\n".join(errors)
    assert "OSError" not in joined
    assert "Traceback" not in joined
    assert str(tmp_path) not in joined
    assert _download_labels(at) == []

    at.button(key="retry_audit_recording").click().run(timeout=10)
    at.run(timeout=10)

    assert at.session_state["audit_record_path"] is not None
    assert at.session_state["audit_record"] is not None
    assert _download_labels(at) == ["Download audited recommendations CSV"]
    assert len(list(tmp_path.glob("*.json"))) == 1

    assert at.session_state["locked_review_result"].model_dump() == result_snapshot
    assert at.session_state["approval_decision_result"] == approval_snapshot


# ---------------------------------------------------------------------------
# Scenario G -- invalid ReviewSetup blocks everything
# ---------------------------------------------------------------------------


def test_scenario_g_invalid_review_setup_blocks_everything(tmp_path):
    at = _launch(tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY)

    _fill_review_inputs(at, {"review_id": "", "reviewer_name": ""})
    _upload_sample_csv(at)
    _submit(at)

    assert len(at.dataframe) >= 1
    assert len(at.dataframe[0].value) >= 1  # at least one genuine validation issue rendered

    assert at.session_state["locked_review_result"] is None
    assert at.session_state["portfolio_explanation_result"] is None
    assert at.session_state["campaign_explanation_result"] is None
    assert at.session_state["campaign_explanation_campaign_id"] is None
    assert at.session_state["approval_decision_result"] is None
    assert at.session_state["audit_record_path"] is None
    assert at.session_state["audit_record_error"] is None
    assert at.session_state["audit_record"] is None
    assert _download_labels(at) == []
    assert at.session_state["audit_calls"] == 0
    assert list(tmp_path.glob("*.json")) == []


# ---------------------------------------------------------------------------
# Scenario H -- mixed valid/invalid CSV blocks the whole portfolio
# ---------------------------------------------------------------------------


def test_scenario_h_mixed_valid_invalid_csv_blocks_whole_portfolio(tmp_path):
    at = _launch(tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY)

    header = (DATA_DIR / "campaign_template.csv").read_text(encoding="utf-8").splitlines()[0]
    good_row = (
        "G001,Search - Brand,Google Ads,Active,CPA,45.00,3000.00,500.00,6000.00,2850.00,"
        "40,155,42.10,44.80,Healthy,High,False,False,,"
    )
    bad_row = "BADROW,short,row"
    csv_bytes = f"{header}\n{good_row}\n{bad_row}\n".encode("utf-8")

    _fill_review_inputs(at)
    _upload_csv(at, csv_bytes)
    _submit(at)

    assert any("no partial portfolio is run" in e.value for e in at.error)
    assert at.session_state["locked_review_result"] is None
    assert at.session_state["portfolio_explanation_result"] is None
    assert at.session_state["approval_decision_result"] is None
    assert at.session_state["audit_record_path"] is None
    assert at.session_state["audit_record"] is None
    assert _download_labels(at) == []
    assert list(tmp_path.glob("*.json")) == []


# ---------------------------------------------------------------------------
# Scenario I -- new-submission state reset (valid and invalid)
# ---------------------------------------------------------------------------


def test_scenario_i_new_valid_submission_resets_downstream_state(tmp_path):
    at = _launch(
        tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY, _FAKE_GENERATED_EXPLANATION_BODY
    )
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    at.selectbox(key="explanation_campaign_id").set_value("G002 — Shopping - Core Catalog")
    at.button(key="generate_campaign_explanation").click().run(timeout=10)
    _approve(at, "Carol")

    assert at.session_state["portfolio_explanation_result"] is not None
    assert at.session_state["campaign_explanation_result"] is not None
    assert at.session_state["campaign_explanation_campaign_id"] == "G002"
    assert at.session_state["approval_decision_result"] is not None
    assert at.session_state["audit_record_path"] is not None
    assert at.session_state["audit_record"] is not None
    assert _download_labels(at) == ["Download audited recommendations CSV"]

    _submit_valid_sample(at, {"review_id": "REV-2"})

    assert at.session_state["locked_review_result"].review_id == "REV-2"
    assert at.session_state["portfolio_explanation_result"] is None
    assert at.session_state["campaign_explanation_result"] is None
    assert at.session_state["campaign_explanation_campaign_id"] is None
    assert at.session_state["approval_decision_result"] is None
    assert at.session_state["audit_record_path"] is None
    assert at.session_state["audit_record_error"] is None
    assert at.session_state["audit_record"] is None
    assert _download_labels(at) == []


def test_scenario_i_new_invalid_submission_also_resets_downstream_state(tmp_path):
    at = _launch(tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY)
    _submit_valid_sample(at)
    _approve(at, "Carol")
    assert at.session_state["audit_record"] is not None

    _fill_review_inputs(at, {"review_id": ""})
    _upload_sample_csv(at)
    _submit(at)

    assert at.session_state["locked_review_result"] is None
    assert at.session_state["approval_decision_result"] is None
    assert at.session_state["audit_record_path"] is None
    assert at.session_state["audit_record"] is None
    assert _download_labels(at) == []


# ---------------------------------------------------------------------------
# Scenario J -- ordinary rerun preserves finalized state without recompute
# ---------------------------------------------------------------------------


def test_scenario_j_ordinary_rerun_preserves_state_without_recompute(tmp_path):
    at = _launch(
        tmp_path,
        _REDIRECT_AUDIT_BODY,
        _CAPTURE_EXPORT_BODY,
        _FAKE_GENERATED_EXPLANATION_BODY,
        _COUNT_PIPELINE_CALLS_BODY,
    )
    _submit_valid_sample(at)
    assert at.session_state["pipeline_calls"] == 1

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert at.session_state["explanation_calls"] == 1

    _approve(at, "Carol")
    assert at.session_state["audit_calls"] == 1

    result_snapshot = at.session_state["locked_review_result"].model_dump()
    explanation_snapshot = at.session_state["portfolio_explanation_result"]
    approval_snapshot = at.session_state["approval_decision_result"]
    audit_path_snapshot = at.session_state["audit_record_path"]
    audit_object_snapshot = at.session_state["audit_record"]
    csv_snapshot = at.session_state["captured_export_csv"]
    files_before = list(tmp_path.glob("*.json"))

    at.run(timeout=10)  # bare rerun -- no button clicked

    assert at.session_state["locked_review_result"].model_dump() == result_snapshot
    assert at.session_state["portfolio_explanation_result"] == explanation_snapshot
    assert at.session_state["approval_decision_result"] == approval_snapshot
    assert at.session_state["audit_record_path"] == audit_path_snapshot
    assert at.session_state["audit_record"] == audit_object_snapshot
    assert at.session_state["captured_export_csv"] == csv_snapshot
    assert list(tmp_path.glob("*.json")) == files_before

    assert at.session_state["pipeline_calls"] == 1
    assert at.session_state["explanation_calls"] == 1
    assert at.session_state["audit_calls"] == 1


# ---------------------------------------------------------------------------
# Cross-cutting: no secret exposure; real repository artifacts untouched
# ---------------------------------------------------------------------------


def test_no_secret_exposure_and_no_real_repository_artifacts(tmp_path, monkeypatch):
    fake_key = "integration-fake-key-not-real-123"
    monkeypatch.setenv("GEMINI_API_KEY", fake_key)

    real_audit_records_dir = Path(__file__).resolve().parent.parent / "audit_records"
    before = (
        set(real_audit_records_dir.glob("*.json")) if real_audit_records_dir.exists() else set()
    )
    repo_root = Path(__file__).resolve().parent.parent
    entries_before = {p.name for p in repo_root.iterdir()}

    at = _launch(
        tmp_path, _REDIRECT_AUDIT_BODY, _CAPTURE_EXPORT_BODY, _FAKE_GENERATED_EXPLANATION_BODY
    )
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    _approve(at, "Carol", note="fine")

    rendered = " ".join(
        [m.value for m in at.markdown]
        + [c.value for c in at.caption]
        + [e.value for e in at.error]
        + [i.value for i in at.info]
        + [s.value for s in at.success]
        + [w.value for w in at.warning]
    )
    assert fake_key not in rendered
    for value in at.session_state.filtered_state.values():
        assert fake_key not in repr(value)

    audit = at.session_state["audit_record"]
    audit_json_text = list(tmp_path.glob("*.json"))[0].read_text(encoding="utf-8")
    csv_text = at.session_state["captured_export_csv"]
    assert fake_key not in audit_json_text
    assert fake_key not in csv_text
    assert "INTEGRATION_FAKE_EXPLANATION_TEXT" not in audit_json_text
    assert "INTEGRATION_FAKE_EXPLANATION_TEXT" not in csv_text
    assert str(tmp_path) not in rendered

    after = (
        set(real_audit_records_dir.glob("*.json")) if real_audit_records_dir.exists() else set()
    )
    assert after == before
    entries_after = {p.name for p in repo_root.iterdir()}
    assert entries_after == entries_before
    assert not (repo_root / "exports").exists()
