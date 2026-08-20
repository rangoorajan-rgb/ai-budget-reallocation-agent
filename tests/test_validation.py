"""Tests for src.validation (Sprint 1 — Development Stage 2).

Covers ValidationIssue/ValidationReport construction and derived fields, deterministic
ReviewSetup validation, campaign CSV structural validation (header, row shape, row field
translation), and duplicate campaign-ID handling. Stage 1 tests (tests/test_models.py) are
untouched and continue to pass; this file only tests new Stage 2 behaviour.
"""

import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.constants import ValidationCode, ValidationSeverity
from src.models import CampaignInput
from src.validation import (
    REQUIRED_CAMPAIGN_HEADER,
    ValidationIssue,
    ValidationReport,
    validate_campaign_csv,
    validate_review_setup,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# CSV row-building helpers (test-only; not the production CSV parser)
# ---------------------------------------------------------------------------

_BASE_ROW = dict(
    zip(
        REQUIRED_CAMPAIGN_HEADER,
        [
            "G001", "Search - Brand", "Google Ads", "Active", "CPA", "45.00",
            "3000.00", "500.00", "6000.00", "2850.00", "40", "155", "42.10",
            "44.80", "Healthy", "High", "False", "False", "", "",
        ],
    )
)


def _row(**overrides) -> list:
    merged = dict(_BASE_ROW)
    merged.update(overrides)
    return [merged[field] for field in REQUIRED_CAMPAIGN_HEADER]


def _csv_text(rows: list[list], header: list[str] | None = None) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header if header is not None else list(REQUIRED_CAMPAIGN_HEADER))
    writer.writerows(rows)
    return buf.getvalue()


def _stream(rows: list[list], header: list[str] | None = None) -> io.StringIO:
    return io.StringIO(_csv_text(rows, header))


# ---------------------------------------------------------------------------
# ValidationIssue / ValidationReport
# ---------------------------------------------------------------------------


def test_validation_issue_construction():
    issue = ValidationIssue(
        severity=ValidationSeverity.ERROR,
        code=ValidationCode.INVALID_CAMPAIGN_FIELD,
        field="kpi_target",
        message="kpi_target must be greater than 0",
        row_number=5,
        campaign_id="G001",
    )
    assert issue.severity is ValidationSeverity.ERROR
    assert issue.code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert issue.field == "kpi_target"
    assert issue.row_number == 5
    assert issue.campaign_id == "G001"


def test_validation_issue_optional_fields_default_none():
    issue = ValidationIssue(
        severity=ValidationSeverity.ERROR,
        code=ValidationCode.EMPTY_FILE,
        message="the CSV stream is completely empty",
    )
    assert issue.field is None
    assert issue.row_number is None
    assert issue.campaign_id is None


def test_validation_report_error_count_derived():
    issues = [
        ValidationIssue(
            severity=ValidationSeverity.ERROR, code=ValidationCode.MALFORMED_ROW, message="a"
        ),
        ValidationIssue(
            severity=ValidationSeverity.ERROR, code=ValidationCode.MALFORMED_ROW, message="b"
        ),
    ]
    report = ValidationReport(issues=issues)
    assert report.error_count == 2


def test_validation_report_warning_count_derived():
    issues = [
        ValidationIssue(
            severity=ValidationSeverity.WARNING, code=ValidationCode.MALFORMED_ROW, message="a"
        ),
        ValidationIssue(
            severity=ValidationSeverity.ERROR, code=ValidationCode.MALFORMED_ROW, message="b"
        ),
    ]
    report = ValidationReport(issues=issues)
    assert report.warning_count == 1
    assert report.error_count == 1


def test_validation_report_is_valid_true_when_no_errors():
    report = ValidationReport(issues=[])
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.warning_count == 0


def test_validation_report_is_valid_false_when_errors_present():
    report = ValidationReport(
        issues=[
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.EMPTY_FILE,
                message="x",
            )
        ]
    )
    assert report.is_valid is False


def test_validation_report_valid_campaigns_preserved_in_order():
    campaign_kwargs = dict(_BASE_ROW)
    del campaign_kwargs["test_budget_floor"]
    del campaign_kwargs["campaign_max_change_percentage"]
    campaign_a = CampaignInput(
        **campaign_kwargs, test_budget_floor=None, campaign_max_change_percentage=None
    )
    campaign_b = campaign_a.model_copy(update={"campaign_id": "G002"})
    report = ValidationReport(issues=[], valid_campaigns=[campaign_a, campaign_b])
    assert report.valid_campaigns == [campaign_a, campaign_b]


def test_validation_report_rejects_directly_set_derived_fields():
    with pytest.raises(ValidationError):
        ValidationReport(issues=[], error_count=99)


# ---------------------------------------------------------------------------
# Review validation
# ---------------------------------------------------------------------------


def _valid_review_kwargs(**overrides) -> dict:
    kwargs = dict(
        review_id="REV-1",
        review_date=date(2026, 8, 9),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        reviewer_name="Rangoo Rajan",
        approved_monthly_budget=Decimal("50000.00"),
        initial_account_reserve=Decimal("2500.00"),
    )
    kwargs.update(overrides)
    return kwargs


def test_validate_review_setup_valid_returns_instance_and_no_issues():
    review, report = validate_review_setup(_valid_review_kwargs())
    assert review is not None
    assert review.review_id == "REV-1"
    assert report.issues == []
    assert report.is_valid is True


def test_validate_review_setup_invalid_returns_none():
    review, report = validate_review_setup(_valid_review_kwargs(review_id=""))
    assert review is None
    assert report.is_valid is False


def test_validate_review_setup_multiple_invalid_fields_produce_multiple_issues():
    review, report = validate_review_setup(
        _valid_review_kwargs(
            review_id="",
            reviewer_name="",
            approved_monthly_budget=Decimal("0"),
        )
    )
    assert review is None
    assert report.error_count == 3
    assert all(issue.code is ValidationCode.INVALID_REVIEW_FIELD for issue in report.issues)


def test_validate_review_setup_field_names_translated_correctly():
    review, report = validate_review_setup(
        _valid_review_kwargs(
            review_id="",
            reviewer_name="",
            approved_monthly_budget=Decimal("0"),
        )
    )
    fields = {issue.field for issue in report.issues}
    assert fields == {"review_id", "reviewer_name", "approved_monthly_budget"}


def test_validate_review_setup_model_level_error_has_no_field():
    review, report = validate_review_setup(
        _valid_review_kwargs(
            period_start=date(2026, 8, 31), period_end=date(2026, 8, 1)
        )
    )
    assert review is None
    assert len(report.issues) == 1
    assert report.issues[0].field is None


def test_validate_review_setup_row_number_is_none():
    _, report = validate_review_setup(_valid_review_kwargs(review_id=""))
    assert all(issue.row_number is None for issue in report.issues)


def test_validate_review_setup_does_not_leak_raw_decimal_exception():
    review, report = validate_review_setup(
        _valid_review_kwargs(approved_monthly_budget=Decimal("1E+30"))
    )
    assert review is None
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_REVIEW_FIELD
    assert "InvalidOperation" not in report.issues[0].message
    assert "Traceback" not in report.issues[0].message


# ---------------------------------------------------------------------------
# CSV: header handling
# ---------------------------------------------------------------------------


def test_validate_campaign_csv_sample_file_valid():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert report.issues == []
    assert len(report.valid_campaigns) == 4


def test_validate_campaign_csv_empty_stream():
    report = validate_campaign_csv(io.StringIO(""))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.EMPTY_FILE
    assert report.issues[0].row_number is None
    assert report.valid_campaigns == []


def test_validate_campaign_csv_template_file_produces_no_campaign_rows():
    with open(DATA_DIR / "campaign_template.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.NO_CAMPAIGN_ROWS
    assert report.issues[0].row_number is None
    assert report.valid_campaigns == []


def test_validate_campaign_csv_missing_header_column():
    header = list(REQUIRED_CAMPAIGN_HEADER[:-1])
    report = validate_campaign_csv(_stream([], header=header))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_HEADER
    assert report.issues[0].row_number == 1


def test_validate_campaign_csv_extra_header_column():
    header = list(REQUIRED_CAMPAIGN_HEADER) + ["extra_column"]
    report = validate_campaign_csv(_stream([], header=header))
    assert report.issues[0].code is ValidationCode.INVALID_HEADER
    assert report.issues[0].row_number == 1


def test_validate_campaign_csv_renamed_header_column():
    header = list(REQUIRED_CAMPAIGN_HEADER)
    header[3] = "campaign_status"  # was "status"
    report = validate_campaign_csv(_stream([], header=header))
    assert report.issues[0].code is ValidationCode.INVALID_HEADER


def test_validate_campaign_csv_reordered_header():
    header = list(REQUIRED_CAMPAIGN_HEADER)
    header[0], header[1] = header[1], header[0]
    report = validate_campaign_csv(_stream([], header=header))
    assert report.issues[0].code is ValidationCode.INVALID_HEADER


def test_validate_campaign_csv_duplicate_header_name():
    header = list(REQUIRED_CAMPAIGN_HEADER)
    header[1] = header[0]  # campaign_name renamed to duplicate campaign_id
    report = validate_campaign_csv(_stream([], header=header))
    assert report.issues[0].code is ValidationCode.INVALID_HEADER


def test_validate_campaign_csv_no_row_validation_after_invalid_header():
    header = list(REQUIRED_CAMPAIGN_HEADER)
    header[0], header[1] = header[1], header[0]
    report = validate_campaign_csv(_stream([["bad", "row", "shape"]], header=header))
    assert len(report.issues) == 1
    assert report.issues[0].code is ValidationCode.INVALID_HEADER
    assert report.valid_campaigns == []


# ---------------------------------------------------------------------------
# CSV: row shape and field translation
# ---------------------------------------------------------------------------


def test_validate_campaign_csv_missing_row_cell_is_malformed():
    row = _row()[:-1]  # 19 cells
    report = validate_campaign_csv(_stream([row]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.MALFORMED_ROW
    assert report.issues[0].row_number == 2
    assert report.valid_campaigns == []


def test_validate_campaign_csv_surplus_row_cell_is_malformed():
    row = _row() + ["extra"]  # 21 cells
    report = validate_campaign_csv(_stream([row]))
    assert report.issues[0].code is ValidationCode.MALFORMED_ROW
    assert report.issues[0].row_number == 2


def test_validate_campaign_csv_single_invalid_field():
    report = validate_campaign_csv(_stream([_row(campaign_id="")]))
    assert report.error_count == 1
    issue = report.issues[0]
    assert issue.code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert issue.field == "campaign_id"
    assert issue.row_number == 2


def test_validate_campaign_csv_multiple_field_errors_in_one_row():
    report = validate_campaign_csv(
        _stream([_row(campaign_id="", kpi_target="0")])
    )
    assert report.error_count == 2
    fields = {issue.field for issue in report.issues}
    assert fields == {"campaign_id", "kpi_target"}
    assert all(issue.row_number == 2 for issue in report.issues)


def test_validate_campaign_csv_invalid_row_excluded_valid_rows_retained():
    rows = [
        _row(campaign_id="G001"),
        _row(campaign_id="", campaign_name="Bad Row"),
        _row(campaign_id="G002"),
    ]
    report = validate_campaign_csv(_stream(rows))
    assert len(report.valid_campaigns) == 2
    assert [c.campaign_id for c in report.valid_campaigns] == ["G001", "G002"]
    assert report.error_count == 1
    assert report.issues[0].row_number == 3


def test_validate_campaign_csv_blank_optional_fields_become_none():
    report = validate_campaign_csv(
        _stream([_row(test_budget_floor="", campaign_max_change_percentage="")])
    )
    assert report.is_valid is True
    campaign = report.valid_campaigns[0]
    assert campaign.test_budget_floor is None
    assert campaign.campaign_max_change_percentage is None


def test_validate_campaign_csv_conventional_boolean_accepted():
    report = validate_campaign_csv(
        _stream([_row(is_protected="yes", is_test_campaign="0")])
    )
    assert report.is_valid is True
    assert report.valid_campaigns[0].is_protected is True
    assert report.valid_campaigns[0].is_test_campaign is False


def test_validate_campaign_csv_ambiguous_boolean_rejected():
    report = validate_campaign_csv(_stream([_row(is_protected="maybe")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "is_protected"


def test_validate_campaign_csv_invalid_enum_value_reported():
    report = validate_campaign_csv(_stream([_row(platform="Bing Ads")]))
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "platform"


def test_validate_campaign_csv_invalid_numeric_input_reported():
    report = validate_campaign_csv(_stream([_row(kpi_target="not-a-number")]))
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "kpi_target"


def test_validate_campaign_csv_cross_field_failure_reported():
    report = validate_campaign_csv(
        _stream([_row(minimum_budget="9000.00", maximum_budget="6000.00")])
    )
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field is None  # model-level check, no single field
    assert report.issues[0].row_number == 2


def test_validate_campaign_csv_physical_line_numbers_correct():
    rows = [
        _row(campaign_id="G001"),
        _row(campaign_id="", campaign_name="Bad"),
        _row(campaign_id="G003"),
    ]
    report = validate_campaign_csv(_stream(rows))
    assert report.issues[0].row_number == 3
    assert [c.campaign_id for c in report.valid_campaigns] == ["G001", "G003"]


def test_validate_campaign_csv_does_not_leak_raw_decimal_exception():
    # current_budget is a quantised Currency field; kpi_target is not, so an absurd
    # exponent there would simply pass through unquantised rather than raising.
    report = validate_campaign_csv(_stream([_row(current_budget="1E+30")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert "InvalidOperation" not in report.issues[0].message


# ---------------------------------------------------------------------------
# Duplicate campaign IDs
# ---------------------------------------------------------------------------


def test_duplicate_campaign_id_two_rows_both_flagged():
    rows = [_row(campaign_id="G001"), _row(campaign_id="G001")]
    report = validate_campaign_csv(_stream(rows))
    assert report.error_count == 2
    assert all(i.code is ValidationCode.DUPLICATE_CAMPAIGN_ID for i in report.issues)
    assert [i.row_number for i in report.issues] == [2, 3]
    assert report.valid_campaigns == []


def test_duplicate_campaign_id_three_rows_all_flagged():
    rows = [_row(campaign_id="G001") for _ in range(3)]
    report = validate_campaign_csv(_stream(rows))
    assert report.error_count == 3
    assert [i.row_number for i in report.issues] == [2, 3, 4]


def test_duplicate_campaign_id_all_occurrences_excluded_from_valid_campaigns():
    rows = [_row(campaign_id="G001"), _row(campaign_id="G001"), _row(campaign_id="G002")]
    report = validate_campaign_csv(_stream(rows))
    assert [c.campaign_id for c in report.valid_campaigns] == ["G002"]


def test_non_duplicate_valid_rows_remain_in_original_order():
    rows = [
        _row(campaign_id="G001"),
        _row(campaign_id="G002"),
        _row(campaign_id="G001"),
        _row(campaign_id="G003"),
    ]
    report = validate_campaign_csv(_stream(rows))
    assert [c.campaign_id for c in report.valid_campaigns] == ["G002", "G003"]


def test_invalid_rows_do_not_participate_in_duplicate_detection():
    rows = [
        _row(campaign_id="G001", kpi_target="0"),  # structurally invalid
        _row(campaign_id="G001"),  # otherwise identical id, but valid
    ]
    report = validate_campaign_csv(_stream(rows))
    assert [c.campaign_id for c in report.valid_campaigns] == ["G001"]
    codes = [issue.code for issue in report.issues]
    assert ValidationCode.DUPLICATE_CAMPAIGN_ID not in codes
    assert ValidationCode.INVALID_CAMPAIGN_FIELD in codes


def test_duplicate_comparison_is_case_sensitive():
    rows = [_row(campaign_id="CAMP001"), _row(campaign_id="camp001")]
    report = validate_campaign_csv(_stream(rows))
    assert report.is_valid is True
    assert {c.campaign_id for c in report.valid_campaigns} == {"CAMP001", "camp001"}


def test_duplicate_ids_compared_after_model_trimming():
    rows = [_row(campaign_id=" CAMP001 "), _row(campaign_id="CAMP001")]
    report = validate_campaign_csv(_stream(rows))
    assert report.error_count == 2
    assert all(i.code is ValidationCode.DUPLICATE_CAMPAIGN_ID for i in report.issues)
    assert report.valid_campaigns == []


# ---------------------------------------------------------------------------
# Sprint 4, Development Stage 40 — adversarial and edge-case CSV coverage
#
# Every outcome below was directly observed against the real
# `validate_campaign_csv`/`CampaignInput` before being written into an
# assertion — none is inferred from the source code alone. No new
# validation rule is introduced or asserted; each test documents the
# existing behaviour exactly as the production validator already produces
# it. Formula-like strings (`=`, `+`, `-`, `@` leading characters) are
# deliberately asserted as *accepted* here — CSV formula-injection
# neutralization is a Stage 35 export-time concern (`src/exports.py`),
# never a Stage 2 input-validation rule.
# ---------------------------------------------------------------------------


def test_csv_with_leading_utf8_bom_fails_header_match():
    # A BOM prepended to the stream becomes part of the first header
    # cell's text ("﻿campaign_id"), which does not exactly equal
    # "campaign_id" -- the existing exact-match header policy (not a new
    # BOM-specific rule) is what rejects it.
    text = "﻿" + _csv_text([_row()])
    report = validate_campaign_csv(io.StringIO(text))
    assert report.is_valid is False
    assert report.issues[0].code is ValidationCode.INVALID_HEADER
    assert report.issues[0].row_number == 1
    assert report.valid_campaigns == []


def test_quoted_field_containing_a_comma_is_preserved_exactly():
    report = validate_campaign_csv(_stream([_row(campaign_name="Brand, Inc.")]))
    assert report.is_valid is True
    assert report.valid_campaigns[0].campaign_name == "Brand, Inc."


def test_quoted_field_containing_embedded_double_quotes_is_preserved_exactly():
    report = validate_campaign_csv(
        _stream([_row(campaign_name='Brand "Premium" Search')])
    )
    assert report.is_valid is True
    assert report.valid_campaigns[0].campaign_name == 'Brand "Premium" Search'


def test_quoted_field_containing_an_embedded_newline_is_preserved_exactly():
    report = validate_campaign_csv(
        _stream([_row(campaign_name="Brand\nSecond Line")])
    )
    assert report.is_valid is True
    assert report.valid_campaigns[0].campaign_name == "Brand\nSecond Line"


def test_crlf_line_endings_parse_identically_to_lf():
    text = _csv_text([_row(campaign_id="G001"), _row(campaign_id="G002")]).replace(
        "\n", "\r\n"
    )
    report = validate_campaign_csv(io.StringIO(text))
    assert report.is_valid is True
    assert [c.campaign_id for c in report.valid_campaigns] == ["G001", "G002"]


def test_blank_line_between_data_rows_is_one_malformed_row_others_still_parse():
    header_line = ",".join(REQUIRED_CAMPAIGN_HEADER)
    row_one = ",".join(_row(campaign_id="G001"))
    row_two = ",".join(_row(campaign_id="G002"))
    text = f"{header_line}\n{row_one}\n\n{row_two}\n"
    report = validate_campaign_csv(io.StringIO(text))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.MALFORMED_ROW
    assert report.issues[0].row_number == 3
    assert [c.campaign_id for c in report.valid_campaigns] == ["G001", "G002"]


def test_blank_line_immediately_after_header_is_malformed_row():
    header_line = ",".join(REQUIRED_CAMPAIGN_HEADER)
    row_one = ",".join(_row(campaign_id="G001"))
    text = f"{header_line}\n\n{row_one}\n"
    report = validate_campaign_csv(io.StringIO(text))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.MALFORMED_ROW
    assert report.issues[0].row_number == 2
    assert [c.campaign_id for c in report.valid_campaigns] == ["G001"]


def test_trailing_newline_at_end_of_file_produces_no_extra_row():
    # A single trailing "\n" is ordinary file formatting, not a blank
    # data row -- csv.reader does not yield an empty final row for it.
    report = validate_campaign_csv(_stream([_row(campaign_id="G001")]))
    assert report.is_valid is True
    assert [c.campaign_id for c in report.valid_campaigns] == ["G001"]


def test_whitespace_only_campaign_id_is_rejected_as_blank():
    report = validate_campaign_csv(_stream([_row(campaign_id="   ")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "campaign_id"


def test_whitespace_only_campaign_name_is_rejected_as_blank():
    report = validate_campaign_csv(_stream([_row(campaign_name="   ")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "campaign_name"


def test_whitespace_only_review_id_is_rejected_as_blank():
    review, report = validate_review_setup(_valid_review_kwargs(review_id="   "))
    assert review is None
    assert report.issues[0].code is ValidationCode.INVALID_REVIEW_FIELD
    assert report.issues[0].field == "review_id"


def test_malformed_unclosed_quote_is_reported_as_malformed_row_no_crash():
    # An unclosed quote makes Python's csv.reader consume the rest of the
    # stream into that one field -- no exception is ever raised by
    # validate_campaign_csv; the resulting short row is reported the same
    # way any other wrong-cell-count row is.
    header_line = ",".join(REQUIRED_CAMPAIGN_HEADER)
    bad_row = (
        'G001,"Unclosed Name,Google Ads,Active,CPA,45.00,3000.00,500.00,'
        "6000.00,2850.00,40,155,42.10,44.80,Healthy,High,False,False,,"
    )
    text = f"{header_line}\n{bad_row}\n"
    report = validate_campaign_csv(io.StringIO(text))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.MALFORMED_ROW
    assert report.valid_campaigns == []


def test_scientific_notation_accepted_for_unquantized_decimal_field():
    report = validate_campaign_csv(_stream([_row(kpi_target="4.5E1")]))
    assert report.is_valid is True
    assert report.valid_campaigns[0].kpi_target == Decimal("45")


def test_scientific_notation_accepted_and_quantized_for_currency_field():
    report = validate_campaign_csv(_stream([_row(current_budget="3E3")]))
    assert report.is_valid is True
    assert report.valid_campaigns[0].current_budget == Decimal("3000.00")


def test_very_large_valid_decimal_within_model_contract_preserved_exactly():
    # The largest value Decimal/Currency can hold under the project's
    # established default global context (28 significant digits) -- the
    # same extreme value already used as the project's own precision
    # regression fixture elsewhere (e.g. src/constraints.py's own tests).
    big = "99999999999999999999999999.99"
    report = validate_campaign_csv(
        _stream(
            [
                _row(
                    current_budget=big,
                    minimum_budget="0.00",
                    maximum_budget=big,
                    spend_to_date="0.00",
                )
            ]
        )
    )
    assert report.is_valid is True
    assert report.valid_campaigns[0].current_budget == Decimal(big)


def test_negative_current_budget_rejected():
    report = validate_campaign_csv(_stream([_row(current_budget="-100.00")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "current_budget"


def test_negative_conversions_rejected():
    report = validate_campaign_csv(_stream([_row(conversions_7d="-5")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "conversions_7d"


def test_nan_kpi_target_rejected():
    report = validate_campaign_csv(_stream([_row(kpi_target="NaN")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "kpi_target"


def test_infinity_current_budget_rejected():
    report = validate_campaign_csv(_stream([_row(current_budget="Infinity")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "current_budget"


def test_negative_infinity_kpi_target_rejected():
    report = validate_campaign_csv(_stream([_row(kpi_target="-Infinity")]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_CAMPAIGN_FIELD
    assert report.issues[0].field == "kpi_target"


def test_formula_like_campaign_id_and_name_are_accepted_by_validation():
    # Formula-injection neutralization is a Stage 35 export-time policy
    # (src/exports.py), never a Stage 2 input-validation rule -- a
    # leading =/+/-/@ is ordinary, structurally valid text at this layer.
    report = validate_campaign_csv(
        _stream([_row(campaign_id="=SUM(A1)", campaign_name="+HYPERLINK(x)")])
    )
    assert report.is_valid is True
    assert report.valid_campaigns[0].campaign_id == "=SUM(A1)"
    assert report.valid_campaigns[0].campaign_name == "+HYPERLINK(x)"


def test_mixed_valid_and_invalid_rows_retains_valid_records_at_validator_level():
    # The validator itself never blocks the whole portfolio -- it reports
    # both the invalid row and the still-parsed valid one side by side.
    # Whole-portfolio blocking on any error is a separate, UI-level policy
    # (app.py's own _may_run_pipeline), never implemented in this module.
    rows = [_row(campaign_id="G001"), _row(campaign_id="", campaign_name="Bad Row")]
    report = validate_campaign_csv(_stream(rows))
    assert report.is_valid is False
    assert [c.campaign_id for c in report.valid_campaigns] == ["G001"]
    assert report.error_count == 1


def test_empty_stream_input():
    report = validate_campaign_csv(io.StringIO(""))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.EMPTY_FILE
    assert report.valid_campaigns == []


def test_header_only_input():
    report = validate_campaign_csv(_stream([]))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.NO_CAMPAIGN_ROWS
    assert report.valid_campaigns == []


def test_whitespace_only_input_fails_header_match():
    report = validate_campaign_csv(io.StringIO("   \n   \n"))
    assert report.error_count == 1
    assert report.issues[0].code is ValidationCode.INVALID_HEADER
    assert report.valid_campaigns == []


def test_adversarial_inputs_never_mutate_the_supplied_text():
    original_bytes = _csv_text([_row(campaign_name='Brand, "Premium"\nSecond')])
    stream = io.StringIO(original_bytes)
    validate_campaign_csv(stream)
    # The stream's own already-consumed text content is never rewritten in
    # place -- re-reading the same underlying value confirms it is
    # unchanged by having been validated.
    assert stream.getvalue() == original_bytes


def test_adversarial_inputs_never_convert_through_float():
    report = validate_campaign_csv(
        _stream([_row(current_budget="3000.10", kpi_target="0.30000000000000004")])
    )
    assert report.is_valid is True
    assert report.valid_campaigns[0].current_budget == Decimal("3000.10")
    assert report.valid_campaigns[0].kpi_target == Decimal("0.30000000000000004")
    # The classic float-imprecision value (0.1 + 0.2 in binary float) is
    # preserved exactly as typed -- proof no float round-trip occurred.
    assert str(report.valid_campaigns[0].kpi_target) == "0.30000000000000004"
