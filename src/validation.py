"""Deterministic validation reporting for review setup and campaign CSV data.

Implements Sprint 1 — Development Stage 2: structured, deterministic validation of raw
`ReviewSetup` input, campaign CSV structure and rows, and duplicate campaign-ID detection.

`ReviewSetup` and `CampaignInput` (`src.models`) remain the sole authoritative source of
structural rules — this module never re-implements a rule they already enforce. It only
invokes them and translates their `pydantic.ValidationError` output into `ValidationIssue`
records. No metrics, pacing, classification, constraints, scoring, allocation,
conservation, or other later-stage logic is implemented here.
"""

import csv
from collections import Counter
from decimal import DecimalException
from typing import Any, Mapping, TextIO

from pydantic import BaseModel, ConfigDict, Field, ValidationError, computed_field

from src.constants import ValidationCode, ValidationSeverity
from src.models import CampaignInput, ReviewSetup

REQUIRED_CAMPAIGN_HEADER: tuple[str, ...] = tuple(CampaignInput.model_fields.keys())
"""The exact required CSV header, in order — derived from CampaignInput so the CSV schema
cannot silently drift from the model."""

_OPTIONAL_BLANK_FIELDS = {"test_budget_floor", "campaign_max_change_percentage"}


class ValidationIssue(BaseModel):
    """A single deterministic validation finding. All Stage 2 issues are ERROR severity."""

    model_config = ConfigDict(extra="forbid")

    severity: ValidationSeverity
    code: ValidationCode
    field: str | None = None
    message: str
    row_number: int | None = None
    campaign_id: str | None = None


class ValidationReport(BaseModel):
    """Aggregated validation result: issues found, plus the campaigns that passed.

    error_count, warning_count, and is_valid are computed from `issues` on every access —
    they are not constructor fields, so a caller cannot set them independently of the
    issues that justify them.
    """

    model_config = ConfigDict(extra="forbid")

    issues: list[ValidationIssue] = Field(default_factory=list)
    valid_campaigns: list[CampaignInput] = Field(default_factory=list)

    @computed_field
    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is ValidationSeverity.ERROR)

    @computed_field
    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity is ValidationSeverity.WARNING)

    @computed_field
    @property
    def is_valid(self) -> bool:
        return self.error_count == 0


def _field_from_loc(loc: tuple) -> str | None:
    """Translate a pydantic error's `loc` tuple into a field-name string, or None if the
    error is model-level (e.g. a cross-field check) rather than tied to one field."""
    return ".".join(str(part) for part in loc) if loc else None


def validate_review_setup(
    data: Mapping[str, Any],
) -> tuple[ReviewSetup | None, ValidationReport]:
    """Validate raw review-setup input against ReviewSetup's frozen structural rules.

    Returns (ReviewSetup instance, report with no issues) on success, or
    (None, report containing one INVALID_REVIEW_FIELD issue per violation) on failure.
    """
    try:
        review = ReviewSetup(**data)
    except ValidationError as exc:
        issues = [
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_REVIEW_FIELD,
                field=_field_from_loc(error["loc"]),
                message=error["msg"],
            )
            for error in exc.errors()
        ]
        return None, ValidationReport(issues=issues)
    except DecimalException:
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code=ValidationCode.INVALID_REVIEW_FIELD,
            message="one or more review setup values could not be processed",
        )
        return None, ValidationReport(issues=[issue])

    return review, ValidationReport()


def _campaign_id_hint(raw_row: list[str]) -> str | None:
    """Best-effort campaign_id for issue attribution: campaign_id is always the first
    column, so its position is stable even when a row has the wrong cell count."""
    if not raw_row:
        return None
    return raw_row[0].strip() or None


def validate_campaign_csv(stream: TextIO) -> ValidationReport:
    """Validate a campaign CSV from a text stream: header, then each data row.

    The caller owns `stream` (already positioned at the start) and this function never
    closes it, so it can later be reused for an uploaded file, not just a filesystem path.
    """
    reader = csv.reader(stream)

    try:
        header = next(reader)
    except StopIteration:
        return ValidationReport(
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.EMPTY_FILE,
                    message="the CSV stream is completely empty",
                )
            ]
        )

    if tuple(header) != REQUIRED_CAMPAIGN_HEADER:
        return ValidationReport(
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_HEADER,
                    message=(
                        "the CSV header must exactly match the required CampaignInput "
                        "schema, in order: " + ", ".join(REQUIRED_CAMPAIGN_HEADER)
                    ),
                    row_number=1,
                )
            ]
        )

    issues: list[ValidationIssue] = []
    parsed_rows: list[tuple[int, CampaignInput]] = []
    row_number = 1
    any_row = False

    for raw_row in reader:
        row_number += 1
        any_row = True
        campaign_id_hint = _campaign_id_hint(raw_row)

        if len(raw_row) != len(REQUIRED_CAMPAIGN_HEADER):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MALFORMED_ROW,
                    message=(
                        f"row has {len(raw_row)} cell(s); expected "
                        f"{len(REQUIRED_CAMPAIGN_HEADER)}"
                    ),
                    row_number=row_number,
                    campaign_id=campaign_id_hint,
                )
            )
            continue

        row_kwargs = dict(zip(REQUIRED_CAMPAIGN_HEADER, raw_row))
        for optional_field in _OPTIONAL_BLANK_FIELDS:
            if row_kwargs.get(optional_field) == "":
                row_kwargs[optional_field] = None

        try:
            campaign = CampaignInput(**row_kwargs)
        except ValidationError as exc:
            for error in exc.errors():
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.INVALID_CAMPAIGN_FIELD,
                        field=_field_from_loc(error["loc"]),
                        message=error["msg"],
                        row_number=row_number,
                        campaign_id=campaign_id_hint,
                    )
                )
            continue
        except DecimalException:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_CAMPAIGN_FIELD,
                    message="one or more campaign values could not be processed",
                    row_number=row_number,
                    campaign_id=campaign_id_hint,
                )
            )
            continue

        parsed_rows.append((row_number, campaign))

    if not any_row:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.NO_CAMPAIGN_ROWS,
                message="the CSV header is valid but contains no campaign data rows",
            )
        )
        return ValidationReport(issues=issues)

    id_counts = Counter(campaign.campaign_id for _, campaign in parsed_rows)
    duplicate_ids = {campaign_id for campaign_id, count in id_counts.items() if count > 1}

    valid_campaigns: list[CampaignInput] = []
    for row_number, campaign in parsed_rows:
        if campaign.campaign_id in duplicate_ids:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.DUPLICATE_CAMPAIGN_ID,
                    field="campaign_id",
                    message=(
                        f"duplicate campaign_id {campaign.campaign_id!r} found in "
                        "multiple rows"
                    ),
                    row_number=row_number,
                    campaign_id=campaign.campaign_id,
                )
            )
        else:
            valid_campaigns.append(campaign)

    return ValidationReport(issues=issues, valid_campaigns=valid_campaigns)
