"""Streamlit entry point for the AI Budget Reallocation Agent.

Implements Sprint 3 — Development Stage 28: a deterministic-only Streamlit
review shell. Collects `ReviewSetup` input and an uploaded campaign CSV,
validates both using the existing, already-approved Stage 2 validation
functions, and — only when validation permits — runs the existing Stage 27
deterministic pipeline and displays the locked, read-only result.

This module never re-implements a validation rule or business formula: it
only calls `validate_review_setup`, `validate_campaign_csv`, and
`run_budget_reallocation_review`, and renders their already-computed
output. Gemini explanation, human approval, audit recording, exports, and
configuration/secret wiring are explicitly out of scope and are not
imported, called, or stubbed here — they remain reserved for later Sprint 3
stages.
"""

import io
from datetime import date
from decimal import Decimal

import streamlit as st

from src.constants import DEFAULT_MAX_CHANGE_PERCENTAGE
from src.models import ReviewSetup
from src.pipeline import (
    BudgetReallocationReviewResult,
    CampaignBudgetRecommendationResult,
    run_budget_reallocation_review,
)
from src.validation import ValidationReport, validate_campaign_csv, validate_review_setup

RESULT_STATE_KEY = "locked_review_result"


def _format_decimal(value: Decimal) -> str:
    """Render a Decimal for display without ever converting through float."""
    return format(value, "f")


def _build_raw_review_setup(
    *,
    review_id: str,
    review_date: date,
    period_start: date,
    period_end: date,
    reviewer_name: str,
    approved_monthly_budget: str,
    initial_account_reserve: str,
    default_max_change_percentage: str,
    review_notes: str,
) -> dict:
    """Assemble the raw mapping passed to `validate_review_setup`.

    Only prepares input; every structural rule (blank checks, bounds,
    period ordering, reserve-vs-budget) is left to `validate_review_setup`.
    Blank optional fields are omitted so `ReviewSetup`'s own defaults apply,
    rather than this module inventing a substitute default.
    """
    data: dict = {
        "review_id": review_id,
        "review_date": review_date,
        "period_start": period_start,
        "period_end": period_end,
        "reviewer_name": reviewer_name,
        "approved_monthly_budget": approved_monthly_budget,
        "initial_account_reserve": initial_account_reserve,
    }

    stripped_percentage = default_max_change_percentage.strip()
    if stripped_percentage:
        data["default_max_change_percentage"] = stripped_percentage

    stripped_notes = review_notes.strip()
    if stripped_notes:
        data["review_notes"] = stripped_notes

    return data


def _decode_csv_upload(uploaded_file) -> tuple[io.StringIO | None, str | None]:
    """Decode an uploaded file's bytes into a text stream for `validate_campaign_csv`.

    Never closes or mutates `uploaded_file`, which remains owned by
    Streamlit; only its bytes are read. Returns (stream, None) on success,
    or (None, message) if the bytes are not valid UTF-8 text.
    """
    raw_bytes = uploaded_file.getvalue()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"The uploaded file could not be decoded as UTF-8 text: {exc}"
    return io.StringIO(text), None


def _may_run_pipeline(
    review: ReviewSetup | None,
    review_report: ValidationReport,
    campaign_report: ValidationReport | None,
) -> bool:
    """The frozen Stage 28 execution-gating policy, as a pure predicate.

    Requires: a resolved review with no review-setup errors; a campaign
    report with no errors (a CSV containing any error never runs a partial
    portfolio); and at least one valid campaign. Warnings never block
    execution. Does not change the lower-level pipeline's own valid
    empty-tuple behavior — this is a UI-level policy only.
    """
    if review is None or not review_report.is_valid:
        return False
    if campaign_report is None or not campaign_report.is_valid:
        return False
    if not campaign_report.valid_campaigns:
        return False
    return True


def _render_validation_report(title: str, report: ValidationReport) -> None:
    """Display every issue in a ValidationReport, in its existing order."""
    st.subheader(title)
    st.write(f"Errors: {report.error_count}  |  Warnings: {report.warning_count}")
    if not report.issues:
        st.write("No issues found.")
        return

    rows = [
        {
            "severity": issue.severity.value,
            "code": issue.code.value,
            "message": issue.message,
            "row_number": issue.row_number if issue.row_number is not None else "N/A",
            "field": issue.field if issue.field is not None else "N/A",
            "campaign_id": issue.campaign_id if issue.campaign_id is not None else "N/A",
        }
        for issue in report.issues
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def _campaign_result_row(result: CampaignBudgetRecommendationResult) -> dict:
    """Convert one locked campaign result into a flat display row.

    Never sorts, recalculates, or relabels anything — every value is taken
    directly from the already-computed result.
    """
    return {
        "campaign_id": result.campaign_id,
        "campaign_name": result.campaign_name,
        "platform": result.platform.value,
        "current_budget": _format_decimal(result.current_budget),
        "recommendation_action": result.recommendation_action.value,
        "allocated_amount": _format_decimal(result.allocated_amount),
        "recommended_budget": _format_decimal(result.recommended_budget),
        "reason_codes": ", ".join(code.value for code in result.reason_codes),
        "performance_band": result.performance_band.value,
        "trend_direction": result.trend_direction.value,
        "confidence": result.confidence.value,
        "pacing_status": result.pacing_status.value,
        "reallocation_priority_score": result.reallocation_priority_score,
        "rank": str(result.rank) if result.rank is not None else "Not ranked",
    }


def _campaign_results_table(result: BudgetReallocationReviewResult) -> list[dict]:
    """Build display rows in the locked result's own original order."""
    return [_campaign_result_row(campaign_result) for campaign_result in result.campaign_results]


def _render_conservation(conservation) -> None:
    """Render conservation status. Always visible; never hidden or repaired."""
    st.subheader("Conservation status")
    st.write(f"Total increase allocated: {_format_decimal(conservation.total_increase_allocated)}")
    st.write(f"Total decrease allocated: {_format_decimal(conservation.total_decrease_allocated)}")
    st.write(f"Net change: {_format_decimal(conservation.net_change)}")
    if conservation.is_conserved:
        st.success("Conserved: allocation totals balance exactly.")
    else:
        st.error(
            "NOT CONSERVED: this allocation does not balance. The locked result "
            "below is shown for inspection only — it has not been repaired, "
            "rebalanced, or rerun."
        )


def _render_locked_result(result: BudgetReallocationReviewResult) -> None:
    """Render the complete, read-only locked deterministic review result."""
    st.subheader("Locked deterministic review result")
    st.caption("Read-only. Nothing below can be edited.")
    st.write(f"**Review ID:** {result.review_id}")
    st.write(f"**Total current budget:** {_format_decimal(result.total_current_budget)}")
    st.write(f"**Total recommended budget:** {_format_decimal(result.total_recommended_budget)}")

    _render_conservation(result.conservation)

    st.subheader("Campaign recommendations")
    rows = _campaign_results_table(result)
    if not rows:
        st.write("No campaigns in this portfolio.")
    else:
        st.dataframe(rows, hide_index=True, width="stretch")


def _handle_submission(raw_review_data: dict, uploaded_file) -> None:
    """Validate a newly submitted form, then run the pipeline only if permitted.

    Always clears any previously stored result first, so a failed
    resubmission never leaves a stale result visible as though it belonged
    to the new submission.
    """
    st.session_state[RESULT_STATE_KEY] = None

    review, review_report = validate_review_setup(raw_review_data)
    _render_validation_report("Review setup validation", review_report)

    campaign_report: ValidationReport | None = None
    if uploaded_file is None:
        st.error("A campaign CSV file is required.")
    else:
        stream, decode_error = _decode_csv_upload(uploaded_file)
        if decode_error is not None:
            st.error(decode_error)
        else:
            campaign_report = validate_campaign_csv(stream)
            _render_validation_report("Campaign CSV validation", campaign_report)
            if not campaign_report.is_valid:
                st.error(
                    "The campaign CSV contains validation errors. Correct the "
                    "upload and resubmit — no partial portfolio is run when any "
                    "row is invalid."
                )
            elif not campaign_report.valid_campaigns:
                st.error(
                    "At least one valid campaign is required to run the "
                    "deterministic review."
                )

    if not _may_run_pipeline(review, review_report, campaign_report):
        return

    try:
        result = run_budget_reallocation_review(
            review, tuple(campaign_report.valid_campaigns)
        )
    except Exception as exc:  # noqa: BLE001 -- deliberate UI-boundary catch; see module docstring
        st.error(
            "The deterministic review could not be completed due to an "
            f"unexpected error: {exc}"
        )
        return

    st.session_state[RESULT_STATE_KEY] = result


def main() -> None:
    st.title("AI Budget Reallocation Agent")
    st.caption(
        "All recommendations below are computed deterministically using "
        "Decimal arithmetic. No AI model is involved in computing these numbers."
    )

    with st.form("review_setup_form"):
        st.subheader("Review setup")
        review_id = st.text_input("Review ID", key="review_id")
        review_date = st.date_input("Review date", value=date.today(), key="review_date")
        period_start = st.date_input("Period start", value=date.today(), key="period_start")
        period_end = st.date_input("Period end", value=date.today(), key="period_end")
        reviewer_name = st.text_input("Reviewer name", key="reviewer_name")
        approved_monthly_budget = st.text_input(
            "Approved monthly budget", key="approved_monthly_budget"
        )
        initial_account_reserve = st.text_input(
            "Initial account reserve", key="initial_account_reserve"
        )
        default_max_change_percentage = st.text_input(
            "Default max change percentage (0-1)",
            value=str(DEFAULT_MAX_CHANGE_PERCENTAGE),
            key="default_max_change_percentage",
        )
        review_notes = st.text_area("Review notes (optional)", key="review_notes")

        st.subheader("Campaign data")
        uploaded_file = st.file_uploader("Campaign CSV", type=["csv"], key="campaign_csv")

        submitted = st.form_submit_button("Run deterministic review", key="submit_review")

    if submitted:
        raw_review_data = _build_raw_review_setup(
            review_id=review_id,
            review_date=review_date,
            period_start=period_start,
            period_end=period_end,
            reviewer_name=reviewer_name,
            approved_monthly_budget=approved_monthly_budget,
            initial_account_reserve=initial_account_reserve,
            default_max_change_percentage=default_max_change_percentage,
            review_notes=review_notes,
        )
        _handle_submission(raw_review_data, uploaded_file)

    result = st.session_state.get(RESULT_STATE_KEY)
    if result is not None:
        _render_locked_result(result)


if __name__ == "__main__":
    main()
