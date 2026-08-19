"""Tests for app.py (Sprint 3 — Development Stage 28).

Covers the deterministic-only Streamlit review shell: widget presence and
raw-input assembly; the frozen pipeline execution-gating policy as a pure
predicate; validation-issue rendering and ordering; the real deterministic
chain over the sample data (exact portfolio totals, exact campaign rows,
ordered reason codes, unranked-campaign display, G002's zero-funded
INCREASE); conservation rendering for both conserved and unconserved
results; the pipeline-exception UI boundary; session-state clear-before-
validate and no-recompute-on-plain-rerun behavior; Decimal-only formatting;
input-order preservation; and isolation from Gemini/config/explanations/
approval/audit/exports and from any duplicated Stage 1-27 business formula.
"""

import ast
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

from streamlit.testing.v1 import AppTest

import app
from src.conservation import CampaignReallocationConservation
from src.constants import ValidationCode, ValidationSeverity
from src.validation import ValidationIssue, ValidationReport, validate_campaign_csv, validate_review_setup

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

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
    at = AppTest.from_file(str(APP_PATH))
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


def _upload_csv(at: AppTest, content: bytes, filename: str = "campaigns.csv") -> None:
    at.file_uploader(key="campaign_csv").set_value((filename, content, "text/csv"))


def _upload_sample_csv(at: AppTest) -> None:
    _upload_csv(at, (DATA_DIR / "sample_campaigns.csv").read_bytes(), "sample_campaigns.csv")


def _submit(at: AppTest) -> None:
    at.button(key="submit_review").click().run(timeout=10)


# ---------------------------------------------------------------------------
# 1. Isolation: imports and runs without later-Sprint-3 dependencies
# ---------------------------------------------------------------------------


def test_app_imports_and_runs_without_exception():
    at = _fresh_app()
    assert not at.exception
    assert [t.value for t in at.title] == ["AI Budget Reallocation Agent"]


def test_module_does_not_import_forbidden_modules():
    # Approved exceptions: `config`, `src.gemini_analyzer`, and
    # `src.explanations` were removed at Sprint 3, Development Stage 32
    # because app.py now legitimately imports all three for the optional
    # Gemini explanation UI (`load_gemini_config`, the Stage 30
    # payload/prompt builders, and `generate_explanation`). `src.approval`
    # was removed at Sprint 3, Development Stage 33 because app.py now
    # legitimately imports it for the human approval workflow
    # (`approve_campaign_reallocation_review`/
    # `reject_campaign_reallocation_review`). `src.audit` was removed at
    # Sprint 3, Development Stage 34 because app.py now legitimately
    # imports it for automatic audit-record persistence
    # (`build_campaign_reallocation_audit`/
    # `record_campaign_reallocation_audit`). `src.exports` was removed at
    # Sprint 3, Development Stage 35 because app.py now legitimately
    # imports it for the CSV export section
    # (`build_campaign_reallocation_export_rows`/
    # `serialize_campaign_reallocation_export_csv`). Every other forbidden
    # import below — any Gemini SDK module — is unchanged and still
    # enforced.
    tree = ast.parse(inspect.getsource(app))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)

    forbidden_modules = {
        "google.generativeai",
        "genai",
    }
    assert imported_modules.isdisjoint(forbidden_modules)


def test_module_does_not_reference_forbidden_names():
    # Approved exceptions: `config` was removed at Sprint 3, Development
    # Stage 32 because app.py now legitimately binds a local
    # `config = load_gemini_config()` variable for the optional Gemini
    # explanation UI — see tests/test_app_explanation.py for the current
    # guarantee that app.py never references `config.api_key`,
    # `SecretStr`, or `get_secret_value()`. `approval` was removed at
    # Sprint 3, Development Stage 33 because app.py now legitimately calls
    # the human-approval domain functions directly by name. `audit` was
    # removed at Sprint 3, Development Stage 34 because app.py now
    # legitimately binds a local `audit = build_campaign_reallocation_audit(...)`
    # variable inside its one audit-action boundary — see
    # tests/test_app_audit.py for that stage's own coverage. Every other
    # forbidden name below is unchanged and still enforced.
    tree = ast.parse(inspect.getsource(app))
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    forbidden = {
        "genai",
        "generativeai",
        "gemini",
        "exports",
        "explanations",
    }
    assert referenced.isdisjoint(forbidden)


def test_no_arithmetic_in_app_source():
    # app.py performs no arithmetic of its own — it only formats and
    # forwards already-computed Decimal values from Stage 1-27 results.
    # `X | None` union type annotations parse as BinOp/BitOr and are not
    # arithmetic, so only genuine arithmetic operators are checked here.
    arithmetic_ops = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
    tree = ast.parse(inspect.getsource(app))
    assert not any(
        isinstance(node, ast.BinOp) and isinstance(node.op, arithmetic_ops)
        for node in ast.walk(tree)
    )


def test_no_stage_1_27_production_function_reimplemented():
    tree = ast.parse(inspect.getsource(app))
    defined_functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    stage_function_names = {
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
        "validate_review_setup",
        "validate_campaign_csv",
    }
    assert defined_functions.isdisjoint(stage_function_names)


def test_no_float_in_source():
    tree = ast.parse(inspect.getsource(app))
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "float" not in referenced


def test_no_attribute_assignment_in_source():
    # No `x.field = value` anywhere -- confirms no model mutation. Session
    # state writes are subscript assignments (st.session_state[key] = ...),
    # which are deliberately not flagged here.
    tree = ast.parse(inspect.getsource(app))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                assert not isinstance(target, ast.Attribute)


def test_pipeline_call_is_guarded_by_submitted_check():
    source = inspect.getsource(app.main)
    tree = ast.parse(source)
    # `_handle_submission` must only be called inside an `if` block, never
    # unconditionally -- this is the structural half of the "no recompute
    # on plain rerun" guarantee.
    calls_inside_if = False
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Name)
                    and inner.func.id == "_handle_submission"
                ):
                    calls_inside_if = True
    assert calls_inside_if


# Retired (Sprint 3, Development Stage 36): `test_test_integration_remains_untouched`
# asserted `tests/test_integration.py` contained no function/class
# definitions, guarding against premature implementation before Stage 36.
# Stage 36 has now legitimately populated that file with the final
# end-to-end integration suite -- see `tests/test_integration.py` for
# that stage's own coverage -- so the guard's condition is permanently
# false by design and is retired rather than replaced.


# ---------------------------------------------------------------------------
# 2 & 3. Initial render does not run the pipeline; explicit submission required
# ---------------------------------------------------------------------------


def test_initial_render_does_not_run_pipeline():
    at = _fresh_app()
    assert "locked_review_result" not in at.session_state
    assert len(at.dataframe) == 0
    assert len(at.error) == 0
    assert len(at.success) == 0


# ---------------------------------------------------------------------------
# 4. Every ReviewSetup input is collected
# ---------------------------------------------------------------------------


def test_every_review_setup_widget_present():
    at = _fresh_app()
    expected_keys = {
        "review_id",
        "review_date",
        "period_start",
        "period_end",
        "reviewer_name",
        "approved_monthly_budget",
        "initial_account_reserve",
        "default_max_change_percentage",
        "review_notes",
    }
    present = {w.key for w in list(at.text_input) + list(at.date_input) + list(at.text_area)}
    assert expected_keys <= present


def test_default_max_change_percentage_prefilled_with_model_default():
    at = _fresh_app()
    from src.constants import DEFAULT_MAX_CHANGE_PERCENTAGE

    assert at.text_input(key="default_max_change_percentage").value == str(
        DEFAULT_MAX_CHANGE_PERCENTAGE
    )


def test_build_raw_review_setup_collects_every_field():
    data = app._build_raw_review_setup(
        review_id="R1",
        review_date=date(2026, 1, 1),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 5),
        reviewer_name="Name",
        approved_monthly_budget="100.00",
        initial_account_reserve="0.00",
        default_max_change_percentage="0.20",
        review_notes="notes",
    )
    assert data == {
        "review_id": "R1",
        "review_date": date(2026, 1, 1),
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 5),
        "reviewer_name": "Name",
        "approved_monthly_budget": "100.00",
        "initial_account_reserve": "0.00",
        "default_max_change_percentage": "0.20",
        "review_notes": "notes",
    }


def test_build_raw_review_setup_omits_blank_optional_fields():
    data = app._build_raw_review_setup(
        review_id="R1",
        review_date=date(2026, 1, 1),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 5),
        reviewer_name="Name",
        approved_monthly_budget="100.00",
        initial_account_reserve="0.00",
        default_max_change_percentage="   ",
        review_notes="   ",
    )
    assert "default_max_change_percentage" not in data
    assert "review_notes" not in data


# ---------------------------------------------------------------------------
# 5. Missing CSV handled visibly
# ---------------------------------------------------------------------------


def test_missing_csv_blocks_execution_with_visible_error():
    at = _fresh_app()
    _fill_review_inputs(at)
    _submit(at)
    assert any("campaign CSV file is required" in e.value for e in at.error)
    assert at.session_state["locked_review_result"] is None


# ---------------------------------------------------------------------------
# 6. Invalid review setup: ordered issues displayed, execution blocked
# ---------------------------------------------------------------------------


def test_invalid_review_setup_displays_ordered_issues_and_blocks():
    at = _fresh_app()
    _fill_review_inputs(at, overrides={"review_id": "", "reviewer_name": ""})
    _upload_sample_csv(at)
    _submit(at)

    assert at.session_state["locked_review_result"] is None

    expected_data = dict(VALID_REVIEW)
    expected_data["review_id"] = ""
    expected_data["reviewer_name"] = ""
    _, expected_report = validate_review_setup(expected_data)
    assert len(expected_report.issues) >= 1

    rendered_rows = at.dataframe[0].value.to_dict("records")
    assert [row["code"] for row in rendered_rows] == [
        issue.code.value for issue in expected_report.issues
    ]
    assert [row["field"] for row in rendered_rows] == [
        issue.field for issue in expected_report.issues
    ]


# ---------------------------------------------------------------------------
# 7. Invalid CSV blocks the entire portfolio, even with some valid rows
# ---------------------------------------------------------------------------


def test_invalid_csv_blocks_entire_portfolio_even_with_valid_rows():
    at = _fresh_app()
    _fill_review_inputs(at)
    header = ",".join(
        (DATA_DIR / "campaign_template.csv").read_text(encoding="utf-8").splitlines()[0:1]
    )
    good_row = (
        "G001,Search - Brand,Google Ads,Active,CPA,45.00,3000.00,500.00,6000.00,2850.00,"
        "40,155,42.10,44.80,Healthy,High,False,False,,"
    )
    bad_row = "BADROW,short,row"
    csv_bytes = f"{header}\n{good_row}\n{bad_row}\n".encode("utf-8")

    _upload_csv(at, csv_bytes)
    _submit(at)

    assert at.session_state["locked_review_result"] is None
    assert any("no partial portfolio is run" in e.value for e in at.error)
    rendered_rows = at.dataframe[0].value.to_dict("records")
    assert rendered_rows[0]["code"] == "MALFORMED_ROW"
    assert rendered_rows[0]["campaign_id"] == "BADROW"


# ---------------------------------------------------------------------------
# 8. Warnings alone are structurally non-blocking (pure predicate)
# ---------------------------------------------------------------------------


def test_warnings_alone_do_not_block_pipeline_execution():
    review, review_report = validate_review_setup(dict(VALID_REVIEW))
    assert review is not None

    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        base_report = validate_campaign_csv(f)
    assert base_report.is_valid

    warning_report = ValidationReport(
        issues=[
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.INVALID_CAMPAIGN_FIELD,
                message="synthetic warning for gating test",
            )
        ],
        valid_campaigns=base_report.valid_campaigns,
    )
    assert warning_report.error_count == 0
    assert warning_report.warning_count == 1
    assert app._may_run_pipeline(review, review_report, warning_report) is True


# ---------------------------------------------------------------------------
# 9. Empty valid-campaign collection is blocked at the UI boundary
# ---------------------------------------------------------------------------


def test_empty_valid_campaigns_blocks_pipeline_execution():
    review, review_report = validate_review_setup(dict(VALID_REVIEW))
    assert review is not None

    empty_report = ValidationReport(issues=[], valid_campaigns=[])
    assert empty_report.is_valid is True
    assert app._may_run_pipeline(review, review_report, empty_report) is False


def test_may_run_pipeline_requires_review():
    _, review_report = validate_review_setup({})
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        campaign_report = validate_campaign_csv(f)
    assert app._may_run_pipeline(None, review_report, campaign_report) is False


def test_may_run_pipeline_requires_campaign_report():
    review, review_report = validate_review_setup(dict(VALID_REVIEW))
    assert app._may_run_pipeline(review, review_report, None) is False


# ---------------------------------------------------------------------------
# 10-15. Valid sample submission: real deterministic chain, exact rendering
# ---------------------------------------------------------------------------


def test_valid_sample_submission_renders_exact_locked_result():
    at = _fresh_app()
    _fill_review_inputs(at)
    _upload_sample_csv(at)
    _submit(at)

    result = at.session_state["locked_review_result"]
    assert result is not None
    assert result.review_id == "REV-1"
    assert result.total_current_budget == Decimal("11700.00")
    assert result.total_recommended_budget == Decimal("11700.00")
    assert result.conservation.is_conserved is True

    rows = at.dataframe[0].value.to_dict("records")
    assert [row["campaign_id"] for row in rows] == ["G001", "M001", "G002", "G003"]
    by_id = {row["campaign_id"]: row for row in rows}

    assert by_id["G002"]["recommendation_action"] == "INCREASE"
    assert by_id["G002"]["allocated_amount"] == "0.00"
    assert by_id["G002"]["recommended_budget"] == "5000.00"
    assert by_id["G002"]["current_budget"] == "5000.00"
    assert by_id["G002"]["rank"] == "1"
    assert by_id["G002"]["reason_codes"] == "ABOVE_TARGET_STRONG, RECENT_TREND_IMPROVING"

    for campaign_id, budget in (("G001", "3000.00"), ("M001", "2500.00"), ("G003", "1200.00")):
        assert by_id[campaign_id]["recommendation_action"] == "MAINTAIN"
        assert by_id[campaign_id]["allocated_amount"] == "0.00"
        assert by_id[campaign_id]["recommended_budget"] == budget
        assert by_id[campaign_id]["rank"] == "Not ranked"
        assert by_id[campaign_id]["reason_codes"] == "NEAR_TARGET, RECENT_TREND_STABLE"

    assert any("Conserved" in s.value for s in at.success)
    assert len(at.error) == 0


def test_g002_action_not_relabeled_despite_zero_allocation():
    at = _fresh_app()
    _fill_review_inputs(at)
    _upload_sample_csv(at)
    _submit(at)

    result = at.session_state["locked_review_result"]
    g002 = next(r for r in result.campaign_results if r.campaign_id == "G002")
    assert g002.recommendation_action.value == "INCREASE"
    assert g002.allocated_amount == Decimal("0.00")
    assert g002.recommended_budget == g002.current_budget


# ---------------------------------------------------------------------------
# 16. Unconserved result: prominently flagged, still inspectable, not repaired
# ---------------------------------------------------------------------------


def _unconserved_conservation_script() -> None:
    from decimal import Decimal as _Decimal

    import app as _app
    from src.conservation import CampaignReallocationConservation as _Conservation

    conservation = _Conservation(
        total_increase_allocated=_Decimal("100.00"),
        total_decrease_allocated=_Decimal("50.00"),
        net_change=_Decimal("50.00"),
        is_conserved=False,
    )
    _app._render_conservation(conservation)


def test_unconserved_result_is_prominently_flagged_and_not_repaired():
    at = AppTest.from_function(_unconserved_conservation_script)
    at.run(timeout=10)
    assert not at.exception
    assert any("NOT CONSERVED" in e.value for e in at.error)
    assert len(at.success) == 0


def test_conservation_model_used_directly_not_recalculated():
    # Sanity check on the fixture itself: it is a real, validated
    # CampaignReallocationConservation instance, not a hand-rolled dict.
    conservation = CampaignReallocationConservation(
        total_increase_allocated=Decimal("100.00"),
        total_decrease_allocated=Decimal("50.00"),
        net_change=Decimal("50.00"),
        is_conserved=False,
    )
    assert conservation.is_conserved is False


# ---------------------------------------------------------------------------
# 17. Pipeline exception produces a visible UI error and no locked result
# ---------------------------------------------------------------------------


def test_pipeline_exception_produces_visible_error_and_no_locked_result():
    script = """
import app

def _boom(review, campaigns):
    raise ValueError("synthetic failure for exception-path test")

app.run_budget_reallocation_review = _boom
app.main()
"""
    at = AppTest.from_string(script)
    at.run(timeout=10)
    _fill_review_inputs(at)
    _upload_sample_csv(at)
    _submit(at)

    assert at.session_state["locked_review_result"] is None
    assert any(
        "deterministic review could not be completed" in e.value
        and "synthetic failure for exception-path test" in e.value
        for e in at.error
    )


# ---------------------------------------------------------------------------
# 18. A new failed submission clears a previous successful result
# ---------------------------------------------------------------------------


def test_new_failed_submission_clears_previous_successful_result():
    at = _fresh_app()
    _fill_review_inputs(at)
    _upload_sample_csv(at)
    _submit(at)
    assert at.session_state["locked_review_result"] is not None

    at.text_input(key="review_id").set_value("")
    at.text_input(key="reviewer_name").set_value("")
    _submit(at)

    assert at.session_state["locked_review_result"] is None


# ---------------------------------------------------------------------------
# 19. A normal rerun without submission does not recompute the pipeline
# ---------------------------------------------------------------------------


def test_plain_rerun_after_success_does_not_recompute():
    at = _fresh_app()
    _fill_review_inputs(at)
    _upload_sample_csv(at)
    _submit(at)

    first_result = at.session_state["locked_review_result"]
    assert first_result is not None

    # A bare rerun, not triggered by clicking the submit button again.
    at.run(timeout=10)

    assert at.button(key="submit_review").value is False
    second_result = at.session_state["locked_review_result"]
    assert second_result == first_result


# ---------------------------------------------------------------------------
# 21. Input campaign order is preserved (not sorted)
# ---------------------------------------------------------------------------


def test_input_campaign_order_preserved_for_non_alphabetical_input():
    at = _fresh_app()
    _fill_review_inputs(at)
    header = (DATA_DIR / "campaign_template.csv").read_text(encoding="utf-8").splitlines()[0]
    rows = [
        "Z999,Zeta,Google Ads,Active,CPA,45.00,3000.00,500.00,6000.00,2850.00,40,155,42.10,44.80,Healthy,High,False,False,,",
        "A001,Alpha,Google Ads,Active,CPA,45.00,3000.00,500.00,6000.00,2850.00,40,155,42.10,44.80,Healthy,High,False,False,,",
        "M500,Mid,Google Ads,Active,CPA,45.00,3000.00,500.00,6000.00,2850.00,40,155,42.10,44.80,Healthy,High,False,False,,",
    ]
    csv_bytes = (header + "\n" + "\n".join(rows) + "\n").encode("utf-8")
    _upload_csv(at, csv_bytes)
    _submit(at)

    result = at.session_state["locked_review_result"]
    assert result is not None
    assert [r.campaign_id for r in result.campaign_results] == ["Z999", "A001", "M500"]

    rendered_ids = [row["campaign_id"] for row in at.dataframe[0].value.to_dict("records")]
    assert rendered_ids == ["Z999", "A001", "M500"]


# ---------------------------------------------------------------------------
# Invalid UTF-8 upload is a visible failure, pipeline never called
# ---------------------------------------------------------------------------


def test_invalid_utf8_csv_upload_blocks_with_visible_error():
    at = _fresh_app()
    _fill_review_inputs(at)
    _upload_csv(at, b"\xff\xfe\x00invalid-utf8")
    _submit(at)

    assert at.session_state["locked_review_result"] is None
    assert any("could not be decoded as UTF-8" in e.value for e in at.error)


def test_decode_csv_upload_does_not_close_or_mutate_source():
    class _FakeUploadedFile:
        def __init__(self, content: bytes):
            self._content = content
            self.closed = False

        def getvalue(self) -> bytes:
            return self._content

        def close(self) -> None:
            self.closed = True

    fake_file = _FakeUploadedFile(b"a,b\n1,2\n")
    stream, error = app._decode_csv_upload(fake_file)
    assert error is None
    assert stream.read() == "a,b\n1,2\n"
    assert fake_file.closed is False
