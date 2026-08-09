"""Tests for src.constants (enumerations and frozen numerical constants) and src.models
(ReviewSetup, CampaignInput).

Covers: enum membership and CSV-friendly values, the nine frozen numerical constants,
ReviewSetup and CampaignInput type/structural validation (currency quantisation, KPI/
percentage fields left unquantised, conventional boolean parsing, all cross-field rules),
and cross-checks against data/campaign_template.csv and data/sample_campaigns.csv to keep
the CSV schema and the Pydantic model in lockstep.
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.constants import (
    BusinessPriority,
    CampaignStatus,
    Confidence,
    CURRENCY_QUANTUM,
    DEFAULT_MAX_CHANGE_PERCENTAGE,
    HIGH_CONFIDENCE_CONVERSIONS,
    INCREASE_THRESHOLD,
    KPIType,
    MAINTAIN_THRESHOLD,
    MINIMUM_CONVERSIONS,
    Platform,
    ReasonCode,
    RecommendationAction,
    ReviewStatus,
    SEVEN_DAY_WEIGHT,
    TrackingStatus,
    TREND_THRESHOLD,
    TWENTY_EIGHT_DAY_WEIGHT,
    ValidationSeverity,
)
from src.models import CampaignInput, ReviewSetup

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


def test_platform_values():
    assert Platform.GOOGLE_ADS.value == "Google Ads"
    assert Platform.META_ADS.value == "Meta Ads"


def test_campaign_status_values():
    assert CampaignStatus.ACTIVE.value == "Active"
    assert CampaignStatus.PAUSED.value == "Paused"


def test_tracking_status_values():
    assert TrackingStatus.HEALTHY.value == "Healthy"
    assert TrackingStatus.WARNING.value == "Warning"
    assert TrackingStatus.UNRELIABLE.value == "Unreliable"


def test_business_priority_values():
    assert BusinessPriority.STANDARD.value == "Standard"
    assert BusinessPriority.MEDIUM.value == "Medium"
    assert BusinessPriority.HIGH.value == "High"


def test_kpi_type_values_unchanged():
    assert KPIType.CPA.value == "CPA"
    assert KPIType.ROAS.value == "ROAS"


def test_validation_severity_members():
    assert {m.value for m in ValidationSeverity} == {"ERROR", "WARNING"}


def test_recommendation_action_members():
    assert {m.value for m in RecommendationAction} == {
        "INCREASE",
        "MAINTAIN",
        "REDUCE",
        "HOLD",
    }


def test_confidence_members():
    assert {m.value for m in Confidence} == {"HIGH", "MEDIUM", "LOW", "NOT_ASSESSABLE"}


def test_review_status_members():
    assert {m.value for m in ReviewStatus} == {
        "DRAFT",
        "PENDING_APPROVAL",
        "APPROVED",
        "REJECTED",
    }


def test_reason_code_has_all_twenty_members():
    assert len(list(ReasonCode)) == 20
    assert ReasonCode.ABOVE_TARGET_STRONG.value == "ABOVE_TARGET_STRONG"
    assert ReasonCode.ACCOUNT_RESERVE_REQUIRED.value == "ACCOUNT_RESERVE_REQUIRED"


# ---------------------------------------------------------------------------
# Frozen numerical constants
# ---------------------------------------------------------------------------


def test_frozen_numerical_constants_exact_values():
    assert DEFAULT_MAX_CHANGE_PERCENTAGE == Decimal("0.20")
    assert TREND_THRESHOLD == Decimal("0.10")
    assert SEVEN_DAY_WEIGHT == Decimal("0.40")
    assert TWENTY_EIGHT_DAY_WEIGHT == Decimal("0.60")
    assert INCREASE_THRESHOLD == Decimal("1.15")
    assert MAINTAIN_THRESHOLD == Decimal("0.90")
    assert MINIMUM_CONVERSIONS == 10
    assert HIGH_CONFIDENCE_CONVERSIONS == 30
    assert CURRENCY_QUANTUM == Decimal("0.01")


def test_frozen_numerical_constants_are_decimal_where_specified():
    for value in (
        DEFAULT_MAX_CHANGE_PERCENTAGE,
        TREND_THRESHOLD,
        SEVEN_DAY_WEIGHT,
        TWENTY_EIGHT_DAY_WEIGHT,
        INCREASE_THRESHOLD,
        MAINTAIN_THRESHOLD,
        CURRENCY_QUANTUM,
    ):
        assert isinstance(value, Decimal)
    assert isinstance(MINIMUM_CONVERSIONS, int)
    assert isinstance(HIGH_CONFIDENCE_CONVERSIONS, int)


# ---------------------------------------------------------------------------
# ReviewSetup
# ---------------------------------------------------------------------------


def _valid_review_setup_kwargs(**overrides):
    kwargs = dict(
        review_id="REV-2026-08",
        review_date=date(2026, 8, 9),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        reviewer_name="Rangoo Rajan",
        approved_monthly_budget=Decimal("50000.00"),
        initial_account_reserve=Decimal("2500.00"),
    )
    kwargs.update(overrides)
    return kwargs


def test_review_setup_valid_construction():
    review = ReviewSetup(**_valid_review_setup_kwargs())
    assert review.default_max_change_percentage == Decimal("0.20")
    assert review.review_notes is None


def test_review_setup_default_max_change_percentage_can_be_overridden():
    review = ReviewSetup(
        **_valid_review_setup_kwargs(default_max_change_percentage=Decimal("0.35"))
    )
    assert review.default_max_change_percentage == Decimal("0.35")


def test_review_setup_blank_review_id_rejected():
    with pytest.raises(ValidationError):
        ReviewSetup(**_valid_review_setup_kwargs(review_id="   "))


def test_review_setup_blank_reviewer_name_rejected():
    with pytest.raises(ValidationError):
        ReviewSetup(**_valid_review_setup_kwargs(reviewer_name=""))


def test_review_setup_reviewer_name_is_trimmed():
    review = ReviewSetup(**_valid_review_setup_kwargs(reviewer_name="  Rangoo Rajan  "))
    assert review.reviewer_name == "Rangoo Rajan"


def test_review_setup_period_end_before_period_start_rejected():
    with pytest.raises(ValidationError):
        ReviewSetup(
            **_valid_review_setup_kwargs(
                period_start=date(2026, 8, 31), period_end=date(2026, 8, 1)
            )
        )


def test_review_setup_period_end_equal_to_period_start_accepted():
    review = ReviewSetup(
        **_valid_review_setup_kwargs(
            period_start=date(2026, 8, 1), period_end=date(2026, 8, 1)
        )
    )
    assert review.period_start == review.period_end


def test_review_setup_approved_monthly_budget_must_be_positive():
    with pytest.raises(ValidationError):
        ReviewSetup(**_valid_review_setup_kwargs(approved_monthly_budget=Decimal("0")))


def test_review_setup_initial_account_reserve_negative_rejected():
    with pytest.raises(ValidationError):
        ReviewSetup(**_valid_review_setup_kwargs(initial_account_reserve=Decimal("-1")))


def test_review_setup_initial_account_reserve_zero_accepted():
    review = ReviewSetup(**_valid_review_setup_kwargs(initial_account_reserve=Decimal("0")))
    assert review.initial_account_reserve == Decimal("0.00")


def test_review_setup_reserve_exceeding_budget_rejected():
    with pytest.raises(ValidationError):
        ReviewSetup(
            **_valid_review_setup_kwargs(
                approved_monthly_budget=Decimal("1000.00"),
                initial_account_reserve=Decimal("1000.01"),
            )
        )


def test_review_setup_reserve_equal_to_budget_accepted():
    review = ReviewSetup(
        **_valid_review_setup_kwargs(
            approved_monthly_budget=Decimal("1000.00"),
            initial_account_reserve=Decimal("1000.00"),
        )
    )
    assert review.initial_account_reserve == review.approved_monthly_budget


@pytest.mark.parametrize("bad_pct", [Decimal("0"), Decimal("-0.1"), Decimal("1.01")])
def test_review_setup_default_max_change_percentage_out_of_range_rejected(bad_pct):
    with pytest.raises(ValidationError):
        ReviewSetup(**_valid_review_setup_kwargs(default_max_change_percentage=bad_pct))


def test_review_setup_default_max_change_percentage_of_one_accepted():
    review = ReviewSetup(
        **_valid_review_setup_kwargs(default_max_change_percentage=Decimal("1"))
    )
    assert review.default_max_change_percentage == Decimal("1")


def test_review_setup_rejects_unknown_field():
    with pytest.raises(ValidationError):
        ReviewSetup(**_valid_review_setup_kwargs(unexpected_field="oops"))


def test_review_setup_currency_fields_quantised_round_half_up():
    review = ReviewSetup(
        **_valid_review_setup_kwargs(
            approved_monthly_budget=Decimal("50000.005"),
            initial_account_reserve=Decimal("2500.004"),
        )
    )
    assert review.approved_monthly_budget == Decimal("50000.01")
    assert review.initial_account_reserve == Decimal("2500.00")


# ---------------------------------------------------------------------------
# CampaignInput
# ---------------------------------------------------------------------------


def _valid_campaign_kwargs(**overrides):
    kwargs = dict(
        campaign_id="G001",
        campaign_name="Search - Brand",
        platform=Platform.GOOGLE_ADS,
        status=CampaignStatus.ACTIVE,
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("45.00"),
        current_budget=Decimal("3000.00"),
        minimum_budget=Decimal("500.00"),
        maximum_budget=Decimal("6000.00"),
        spend_to_date=Decimal("2850.00"),
        conversions_7d=40,
        conversions_28d=155,
        kpi_actual_7d=Decimal("42.10"),
        kpi_actual_28d=Decimal("44.80"),
        tracking_status=TrackingStatus.HEALTHY,
        business_priority=BusinessPriority.HIGH,
    )
    kwargs.update(overrides)
    return kwargs


def test_campaign_input_valid_construction():
    campaign = CampaignInput(**_valid_campaign_kwargs())
    assert campaign.is_protected is False
    assert campaign.is_test_campaign is False
    assert campaign.test_budget_floor is None
    assert campaign.campaign_max_change_percentage is None


def test_campaign_input_accepts_enum_values_as_strings():
    campaign = CampaignInput(
        **_valid_campaign_kwargs(
            platform="Google Ads",
            status="Active",
            kpi_type="CPA",
            tracking_status="Healthy",
            business_priority="High",
        )
    )
    assert campaign.platform is Platform.GOOGLE_ADS
    assert campaign.status is CampaignStatus.ACTIVE


def test_campaign_input_blank_campaign_id_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(campaign_id=""))


def test_campaign_input_blank_campaign_name_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(campaign_name="   "))


def test_campaign_input_campaign_id_is_trimmed():
    campaign = CampaignInput(**_valid_campaign_kwargs(campaign_id="  G001  "))
    assert campaign.campaign_id == "G001"


def test_campaign_input_negative_current_budget_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(current_budget=Decimal("-1")))


def test_campaign_input_kpi_target_must_be_positive():
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(kpi_target=Decimal("0")))


@pytest.mark.parametrize("field", ["kpi_actual_7d", "kpi_actual_28d"])
def test_campaign_input_actual_kpi_values_must_be_positive(field):
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(**{field: Decimal("0")}))


def test_campaign_input_maximum_budget_below_minimum_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(
            **_valid_campaign_kwargs(
                minimum_budget=Decimal("1000.00"), maximum_budget=Decimal("500.00")
            )
        )


def test_campaign_input_current_budget_below_minimum_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(
            **_valid_campaign_kwargs(
                current_budget=Decimal("400.00"),
                minimum_budget=Decimal("500.00"),
                maximum_budget=Decimal("6000.00"),
            )
        )


def test_campaign_input_current_budget_above_maximum_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(
            **_valid_campaign_kwargs(
                current_budget=Decimal("7000.00"),
                minimum_budget=Decimal("500.00"),
                maximum_budget=Decimal("6000.00"),
            )
        )


def test_campaign_input_spend_to_date_exceeding_current_budget_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(
            **_valid_campaign_kwargs(
                current_budget=Decimal("1000.00"), spend_to_date=Decimal("1000.01")
            )
        )


def test_campaign_input_spend_to_date_equal_to_current_budget_accepted():
    campaign = CampaignInput(
        **_valid_campaign_kwargs(
            current_budget=Decimal("1000.00"), spend_to_date=Decimal("1000.00")
        )
    )
    assert campaign.spend_to_date == campaign.current_budget


def test_campaign_input_conversions_7d_exceeding_28d_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(conversions_7d=200, conversions_28d=100))


def test_campaign_input_conversions_7d_equal_to_28d_accepted():
    campaign = CampaignInput(**_valid_campaign_kwargs(conversions_7d=50, conversions_28d=50))
    assert campaign.conversions_7d == campaign.conversions_28d


def test_campaign_input_negative_conversions_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(conversions_7d=-1))


@pytest.mark.parametrize("bad_pct", [Decimal("0"), Decimal("-0.1"), Decimal("1.01")])
def test_campaign_input_max_change_percentage_out_of_range_rejected(bad_pct):
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(campaign_max_change_percentage=bad_pct))


def test_campaign_input_max_change_percentage_of_one_accepted():
    campaign = CampaignInput(
        **_valid_campaign_kwargs(campaign_max_change_percentage=Decimal("1"))
    )
    assert campaign.campaign_max_change_percentage == Decimal("1")


def test_campaign_input_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(impressions_7d=1000))


def test_campaign_input_test_campaign_with_budget_floor():
    campaign = CampaignInput(
        **_valid_campaign_kwargs(
            campaign_id="G003",
            is_test_campaign=True,
            test_budget_floor=Decimal("300.00"),
        )
    )
    assert campaign.is_test_campaign is True
    assert campaign.test_budget_floor == Decimal("300.00")


def test_campaign_input_test_campaign_without_floor_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(is_test_campaign=True))


def test_campaign_input_non_test_campaign_with_floor_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(
            **_valid_campaign_kwargs(
                is_test_campaign=False, test_budget_floor=Decimal("300.00")
            )
        )


def test_campaign_input_test_budget_floor_exceeding_current_budget_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(
            **_valid_campaign_kwargs(
                is_test_campaign=True,
                current_budget=Decimal("1000.00"),
                minimum_budget=Decimal("500.00"),
                maximum_budget=Decimal("2000.00"),
                test_budget_floor=Decimal("1000.01"),
            )
        )


def test_campaign_input_negative_test_budget_floor_rejected():
    with pytest.raises(ValidationError):
        CampaignInput(
            **_valid_campaign_kwargs(
                is_test_campaign=True, test_budget_floor=Decimal("-1")
            )
        )


def test_campaign_input_protected_campaign():
    campaign = CampaignInput(**_valid_campaign_kwargs(is_protected=True))
    assert campaign.is_protected is True


def test_campaign_input_currency_fields_quantised_round_half_up():
    campaign = CampaignInput(
        **_valid_campaign_kwargs(
            current_budget=Decimal("3000.005"),
            minimum_budget=Decimal("500.004"),
            maximum_budget=Decimal("6000.005"),
            spend_to_date=Decimal("2850.004"),
        )
    )
    assert campaign.current_budget == Decimal("3000.01")
    assert campaign.minimum_budget == Decimal("500.00")
    assert campaign.maximum_budget == Decimal("6000.01")
    assert campaign.spend_to_date == Decimal("2850.00")


def test_campaign_input_kpi_and_percentage_fields_not_quantised():
    campaign = CampaignInput(
        **_valid_campaign_kwargs(
            kpi_target=Decimal("45.123456"),
            kpi_actual_7d=Decimal("42.987654"),
            kpi_actual_28d=Decimal("44.111111"),
            campaign_max_change_percentage=Decimal("0.123456"),
        )
    )
    assert campaign.kpi_target == Decimal("45.123456")
    assert campaign.kpi_actual_7d == Decimal("42.987654")
    assert campaign.kpi_actual_28d == Decimal("44.111111")
    assert campaign.campaign_max_change_percentage == Decimal("0.123456")


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("yes", True),
        ("YES", True),
        ("no", False),
        ("NO", False),
        ("1", True),
        ("0", False),
    ],
)
def test_campaign_input_accepts_conventional_boolean_representations(value, expected):
    campaign = CampaignInput(**_valid_campaign_kwargs(is_protected=value))
    assert campaign.is_protected is expected


@pytest.mark.parametrize("value", ["maybe", "t", "f", "on", "off", "y", "n", 2, -1, 3.5])
def test_campaign_input_rejects_ambiguous_boolean_representations(value):
    with pytest.raises(ValidationError):
        CampaignInput(**_valid_campaign_kwargs(is_protected=value))


# ---------------------------------------------------------------------------
# CSV schema: exact 20-field order shared by CampaignInput and both CSV files
# ---------------------------------------------------------------------------

EXPECTED_CSV_FIELDS = [
    "campaign_id",
    "campaign_name",
    "platform",
    "status",
    "kpi_type",
    "kpi_target",
    "current_budget",
    "minimum_budget",
    "maximum_budget",
    "spend_to_date",
    "conversions_7d",
    "conversions_28d",
    "kpi_actual_7d",
    "kpi_actual_28d",
    "tracking_status",
    "business_priority",
    "is_protected",
    "is_test_campaign",
    "test_budget_floor",
    "campaign_max_change_percentage",
]

_DECIMAL_FIELDS = {
    "kpi_target",
    "current_budget",
    "minimum_budget",
    "maximum_budget",
    "spend_to_date",
    "kpi_actual_7d",
    "kpi_actual_28d",
    "test_budget_floor",
    "campaign_max_change_percentage",
}
_INT_FIELDS = {"conversions_7d", "conversions_28d"}
_OPTIONAL_FIELDS = {"test_budget_floor", "campaign_max_change_percentage"}


def _row_to_campaign_kwargs(row: dict) -> dict:
    kwargs = {}
    for key, value in row.items():
        if key in _OPTIONAL_FIELDS and value == "":
            kwargs[key] = None
        elif key in _DECIMAL_FIELDS:
            kwargs[key] = Decimal(value)
        elif key in _INT_FIELDS:
            kwargs[key] = int(value)
        else:
            # platform/status/kpi_type/tracking_status/business_priority strings, and
            # is_protected/is_test_campaign raw "True"/"False" strings, pass through
            # unconverted so the model's own parsing/validation is exercised end to end.
            kwargs[key] = value
    return kwargs


def test_campaign_input_field_order_matches_expected_csv_schema():
    assert list(CampaignInput.model_fields.keys()) == EXPECTED_CSV_FIELDS


def test_campaign_template_csv_header_matches_model_fields():
    with open(DATA_DIR / "campaign_template.csv", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == EXPECTED_CSV_FIELDS
        assert next(reader, None) is None  # template has no data rows


def test_sample_campaigns_csv_header_matches_model_fields():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == EXPECTED_CSV_FIELDS


def test_sample_campaigns_csv_has_exactly_four_rows():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4


def test_sample_campaigns_csv_rows_construct_valid_campaign_inputs():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        rows = [_row_to_campaign_kwargs(row) for row in csv.DictReader(f)]
    campaigns = [CampaignInput(**kwargs) for kwargs in rows]
    assert len(campaigns) == 4


def test_sample_campaigns_csv_covers_required_scenarios():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        rows = [_row_to_campaign_kwargs(row) for row in csv.DictReader(f)]
    campaigns = {c.campaign_id: c for c in (CampaignInput(**kwargs) for kwargs in rows)}

    google_cpa_active = [
        c
        for c in campaigns.values()
        if c.platform is Platform.GOOGLE_ADS
        and c.kpi_type is KPIType.CPA
        and c.status is CampaignStatus.ACTIVE
    ]
    meta_roas_active = [
        c
        for c in campaigns.values()
        if c.platform is Platform.META_ADS
        and c.kpi_type is KPIType.ROAS
        and c.status is CampaignStatus.ACTIVE
    ]
    protected_active = [
        c for c in campaigns.values() if c.is_protected and c.status is CampaignStatus.ACTIVE
    ]
    test_campaigns_with_floor = [
        c
        for c in campaigns.values()
        if c.is_test_campaign and c.test_budget_floor is not None
    ]

    assert len(google_cpa_active) >= 1
    assert len(meta_roas_active) >= 1
    assert len(protected_active) >= 1
    assert len(test_campaigns_with_floor) >= 1
