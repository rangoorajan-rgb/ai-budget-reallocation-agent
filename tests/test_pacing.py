"""Tests for src.pacing (Sprint 1 — Development Stage 4).

Covers CampaignPacing construction/immutability, inclusive date-arithmetic and clamping,
the linear expected-spend/variance/pacing-ratio/remaining-budget/projection formulas,
zero-denominator None behaviour, Decimal precision-28/ROUND_HALF_UP behaviour (including
isolation from a mutated global Decimal context), integration with validate_campaign_csv
over data/sample_campaigns.csv, and scope boundaries (no status/classification/
confidence/recommendation/reason-code/score field, no CampaignMetrics dependency).
"""

import decimal
import inspect
from decimal import ROUND_HALF_UP, Decimal, localcontext
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.constants import (
    BusinessPriority,
    CampaignStatus,
    CURRENCY_QUANTUM,
    KPIType,
    Platform,
    TrackingStatus,
)
from src.models import CampaignInput, ReviewSetup
from src.pacing import CampaignPacing, calculate_campaign_pacing
from src.validation import validate_campaign_csv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _review(**overrides) -> ReviewSetup:
    kwargs = dict(
        review_id="REV-1",
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
        reviewer_name="Reviewer",
        approved_monthly_budget=Decimal("100000.00"),
        initial_account_reserve=Decimal("0.00"),
    )
    kwargs.update(overrides)
    return ReviewSetup(**kwargs)


def _campaign(**overrides) -> CampaignInput:
    kwargs = dict(
        campaign_id="C001",
        campaign_name="Test Campaign",
        platform=Platform.GOOGLE_ADS,
        status=CampaignStatus.ACTIVE,
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4.00"),
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        conversions_7d=10,
        conversions_28d=40,
        kpi_actual_7d=Decimal("5.00"),
        kpi_actual_28d=Decimal("4.00"),
        tracking_status=TrackingStatus.HEALTHY,
        business_priority=BusinessPriority.STANDARD,
    )
    kwargs.update(overrides)
    return CampaignInput(**kwargs)


def _div(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Independently reproduce the function's precision-28/ROUND_HALF_UP division."""
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        return numerator / denominator


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_campaign_pacing_accepts_exactly_nine_fields():
    assert set(CampaignPacing.model_fields.keys()) == {
        "campaign_id",
        "elapsed_days",
        "total_period_days",
        "elapsed_fraction",
        "expected_spend",
        "spend_variance",
        "pacing_ratio",
        "remaining_budget",
        "projected_end_of_period_spend",
    }


def test_campaign_pacing_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignPacing(
            campaign_id="C001",
            elapsed_days=1,
            total_period_days=1,
            elapsed_fraction=Decimal("1"),
            expected_spend=Decimal("0.00"),
            spend_variance=Decimal("0.00"),
            pacing_ratio=None,
            remaining_budget=Decimal("0.00"),
            projected_end_of_period_spend=None,
            extra_field="not allowed",
        )


def test_campaign_pacing_is_immutable():
    pacing = calculate_campaign_pacing(_review(), _campaign())
    with pytest.raises(ValidationError):
        pacing.campaign_id = "C002"


def test_campaign_pacing_elapsed_days_and_total_period_days_are_int():
    pacing = calculate_campaign_pacing(_review(), _campaign())
    assert isinstance(pacing.elapsed_days, int)
    assert isinstance(pacing.total_period_days, int)


def test_campaign_pacing_present_numerical_fields_are_decimal():
    pacing = calculate_campaign_pacing(_review(), _campaign())
    for field in (
        "elapsed_fraction",
        "expected_spend",
        "spend_variance",
        "pacing_ratio",
        "remaining_budget",
        "projected_end_of_period_spend",
    ):
        value = getattr(pacing, field)
        assert isinstance(value, Decimal)
        assert not isinstance(value, float)


def test_campaign_pacing_optional_fields_accept_none():
    pacing = CampaignPacing(
        campaign_id="C001",
        elapsed_days=0,
        total_period_days=10,
        elapsed_fraction=Decimal("0"),
        expected_spend=Decimal("0.00"),
        spend_variance=Decimal("0.00"),
        pacing_ratio=None,
        remaining_budget=Decimal("1000.00"),
        projected_end_of_period_spend=None,
    )
    assert pacing.pacing_ratio is None
    assert pacing.projected_end_of_period_spend is None


def test_campaign_pacing_campaign_id_copied_from_input():
    pacing = calculate_campaign_pacing(_review(), _campaign(campaign_id="XYZ-1"))
    assert pacing.campaign_id == "XYZ-1"


# ---------------------------------------------------------------------------
# Date arithmetic (31-day period: 1-31 August 2026)
# ---------------------------------------------------------------------------


def _august_review(review_date: date) -> ReviewSetup:
    return _review(
        review_date=review_date,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )


def test_first_day_of_31_day_period():
    pacing = calculate_campaign_pacing(_august_review(date(2026, 8, 1)), _campaign())
    assert pacing.elapsed_days == 1
    assert pacing.total_period_days == 31
    assert pacing.elapsed_fraction == Decimal(1) / Decimal(31)


def test_middle_day_10_august():
    pacing = calculate_campaign_pacing(_august_review(date(2026, 8, 10)), _campaign())
    assert pacing.elapsed_days == 10
    assert pacing.elapsed_fraction == Decimal(10) / Decimal(31)


def test_last_day_31_august():
    pacing = calculate_campaign_pacing(_august_review(date(2026, 8, 31)), _campaign())
    assert pacing.elapsed_days == 31
    assert pacing.total_period_days == 31
    assert pacing.elapsed_fraction == Decimal("1")


def test_review_date_before_period():
    pacing = calculate_campaign_pacing(_august_review(date(2026, 7, 15)), _campaign())
    assert pacing.elapsed_days == 0
    assert pacing.elapsed_fraction == Decimal("0")


def test_review_date_after_period():
    pacing = calculate_campaign_pacing(_august_review(date(2026, 9, 15)), _campaign())
    assert pacing.elapsed_days == 31
    assert pacing.elapsed_fraction == Decimal("1")


def test_one_day_period():
    review = _review(
        review_date=date(2026, 8, 15),
        period_start=date(2026, 8, 15),
        period_end=date(2026, 8, 15),
    )
    pacing = calculate_campaign_pacing(review, _campaign())
    assert pacing.elapsed_days == 1
    assert pacing.total_period_days == 1
    assert pacing.elapsed_fraction == Decimal("1")


def test_leap_year_february_2028():
    review = _review(
        review_date=date(2028, 2, 15),
        period_start=date(2028, 2, 1),
        period_end=date(2028, 2, 29),
    )
    pacing = calculate_campaign_pacing(review, _campaign())
    assert pacing.total_period_days == 29
    assert pacing.elapsed_days == 15


# ---------------------------------------------------------------------------
# Exact-on-pace / below-pace / above-pace (10-day period, review on day 5)
# ---------------------------------------------------------------------------


def test_exact_on_pace_example():
    review = _review(
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("500.00"))
    pacing = calculate_campaign_pacing(review, campaign)
    assert pacing.total_period_days == 10
    assert pacing.elapsed_days == 5
    assert pacing.elapsed_fraction == Decimal("0.5")
    assert pacing.expected_spend == Decimal("500.00")
    assert pacing.spend_variance == Decimal("0.00")
    assert pacing.pacing_ratio == Decimal("1")
    assert pacing.remaining_budget == Decimal("500.00")
    assert pacing.projected_end_of_period_spend == Decimal("1000.00")


def test_below_pace_example():
    review = _review(
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("400.00"))
    pacing = calculate_campaign_pacing(review, campaign)
    assert pacing.expected_spend == Decimal("500.00")
    assert pacing.spend_variance == Decimal("-100.00")
    assert pacing.pacing_ratio == Decimal("0.8")
    assert pacing.remaining_budget == Decimal("600.00")
    assert pacing.projected_end_of_period_spend == Decimal("800.00")


def test_above_pace_example():
    review = _review(
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("600.00"))
    pacing = calculate_campaign_pacing(review, campaign)
    assert pacing.expected_spend == Decimal("500.00")
    assert pacing.spend_variance == Decimal("100.00")
    assert pacing.pacing_ratio == Decimal("1.2")
    assert pacing.remaining_budget == Decimal("400.00")
    assert pacing.projected_end_of_period_spend == Decimal("1200.00")


# ---------------------------------------------------------------------------
# Zero and boundaries
# ---------------------------------------------------------------------------


def test_zero_spend_during_active_period():
    review = _review(
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("0.00"))
    pacing = calculate_campaign_pacing(review, campaign)
    assert pacing.pacing_ratio == Decimal("0")
    assert pacing.projected_end_of_period_spend == Decimal("0.00")


def test_zero_current_budget():
    review = _review(
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
    )
    campaign = _campaign(
        current_budget=Decimal("0.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("0.00"),
        spend_to_date=Decimal("0.00"),
    )
    pacing = calculate_campaign_pacing(review, campaign)
    assert pacing.expected_spend == Decimal("0.00")
    assert pacing.spend_variance == Decimal("0.00")
    assert pacing.pacing_ratio is None
    assert pacing.remaining_budget == Decimal("0.00")
    assert pacing.projected_end_of_period_spend == Decimal("0.00")


def test_review_before_period_zero_denominators():
    review = _review(
        review_date=date(2026, 7, 1),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("0.00"))
    pacing = calculate_campaign_pacing(review, campaign)
    assert pacing.expected_spend == Decimal("0.00")
    assert pacing.pacing_ratio is None
    assert pacing.projected_end_of_period_spend is None


def test_spend_equal_to_current_budget_remaining_zero():
    review = _review(
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("1000.00"))
    pacing = calculate_campaign_pacing(review, campaign)
    assert pacing.remaining_budget == Decimal("0.00")


# ---------------------------------------------------------------------------
# Rounding and precision
# ---------------------------------------------------------------------------


def test_repeating_elapsed_fraction_exact_precision():
    review = _review(
        review_date=date(2026, 8, 10),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    pacing = calculate_campaign_pacing(review, _campaign())
    expected = _div(Decimal(10), Decimal(31))
    assert pacing.elapsed_fraction == expected
    assert str(pacing.elapsed_fraction) == str(expected)
    assert len(str(expected).split(".")[1]) == 28  # value < 1: all 28 sig figs are after "."


def test_monetary_fields_quantised_to_cents():
    review = _review(
        review_date=date(2026, 8, 10),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("322.58"))
    pacing = calculate_campaign_pacing(review, campaign)
    for field in (
        "expected_spend",
        "spend_variance",
        "remaining_budget",
        "projected_end_of_period_spend",
    ):
        value = getattr(pacing, field)
        assert value == value.quantize(CURRENCY_QUANTUM)


def test_pacing_ratio_uses_raw_not_quantised_expected_spend():
    review = _review(
        review_date=date(2026, 8, 10),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("322.58"))
    pacing = calculate_campaign_pacing(review, campaign)

    raw_expected_spend = _div(Decimal("1000.00") * Decimal(10), Decimal(31))
    ratio_from_raw = campaign.spend_to_date / raw_expected_spend
    ratio_from_quantised = campaign.spend_to_date / pacing.expected_spend

    assert ratio_from_raw != ratio_from_quantised
    assert pacing.pacing_ratio == ratio_from_raw
    assert pacing.pacing_ratio != ratio_from_quantised


def test_function_result_unaffected_by_mutated_global_decimal_context():
    review = _review(
        review_date=date(2026, 8, 10),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    campaign = _campaign(current_budget=Decimal("1000.00"), spend_to_date=Decimal("300.00"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        pacing = calculate_campaign_pacing(review, campaign)
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding

    expected_fraction = _div(Decimal(10), Decimal(31))
    assert pacing.elapsed_fraction == expected_fraction
    assert len(str(pacing.elapsed_fraction).split(".")[1]) == 28


def test_no_float_in_result():
    pacing = calculate_campaign_pacing(_review(), _campaign())
    for field in (
        "elapsed_fraction",
        "expected_spend",
        "spend_variance",
        "pacing_ratio",
        "remaining_budget",
        "projected_end_of_period_spend",
    ):
        assert not isinstance(getattr(pacing, field), float)


# ---------------------------------------------------------------------------
# Integration with validated CSV data
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_pacing_exact_values_and_order():
    review = _review(
        review_date=date(2026, 8, 10),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    results = [calculate_campaign_pacing(review, c) for c in report.valid_campaigns]
    assert [p.campaign_id for p in results] == ["G001", "M001", "G002", "G003"]

    expected_budgets_spends = {
        "G001": (Decimal("3000.00"), Decimal("2850.00")),
        "M001": (Decimal("2500.00"), Decimal("2400.00")),
        "G002": (Decimal("5000.00"), Decimal("4950.00")),
        "G003": (Decimal("1200.00"), Decimal("300.00")),
    }

    for pacing in results:
        budget, spend = expected_budgets_spends[pacing.campaign_id]
        with localcontext() as ctx:
            ctx.prec = 28
            ctx.rounding = ROUND_HALF_UP
            fraction = Decimal(10) / Decimal(31)
            raw_expected_spend = budget * fraction
            exp_expected_spend = raw_expected_spend.quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)
            exp_variance = (spend - raw_expected_spend).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)
            exp_ratio = spend / raw_expected_spend
            exp_remaining = (budget - spend).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)
            exp_projected = (spend / fraction).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)

        assert pacing.total_period_days == 31
        assert pacing.elapsed_days == 10
        assert pacing.elapsed_fraction == fraction
        assert pacing.expected_spend == exp_expected_spend
        assert pacing.spend_variance == exp_variance
        assert pacing.pacing_ratio == exp_ratio
        assert pacing.remaining_budget == exp_remaining
        assert pacing.projected_end_of_period_spend == exp_projected


# ---------------------------------------------------------------------------
# Scope boundaries
# ---------------------------------------------------------------------------


def test_no_performance_status_confidence_recommendation_reason_code_or_score_fields():
    field_names = set(CampaignPacing.model_fields.keys())
    forbidden = {
        "performance_ratio",
        "performance_ratio_7d",
        "performance_ratio_28d",
        "weighted_performance_ratio",
        "trend_delta",
        "pacing_status",
        "pacing_label",
        "status",
        "recommendation_action",
        "confidence",
        "reason_code",
        "score",
        "eligibility",
        "proposed_budget",
        "allocation",
    }
    assert field_names.isdisjoint(forbidden)


def test_pacing_module_does_not_import_campaign_metrics_or_later_stage_modules():
    import ast

    import src.pacing as pacing_module

    tree = ast.parse(inspect.getsource(pacing_module))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.add(node.module)
            imported_names.update(alias.name for alias in node.names)

    assert "CampaignMetrics" not in imported_names
    assert "src.metrics" not in imported_names
    assert "src.classification" not in imported_names


def test_calculate_campaign_pacing_rejects_invalid_types():
    with pytest.raises(AttributeError):
        calculate_campaign_pacing(None, None)  # type: ignore[arg-type]
