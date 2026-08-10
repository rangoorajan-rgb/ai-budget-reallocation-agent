"""Tests for src.metrics (Sprint 1 — Development Stage 3).

Covers CampaignMetrics construction/immutability, direction-normalised performance
ratios for both KPI types, the weighted blend, the relative trend delta, Decimal
precision-28/ROUND_HALF_UP behaviour (including isolation from a mutated global Decimal
context), integration with validate_campaign_csv over data/sample_campaigns.csv, and
scope boundaries (no classification/confidence/recommendation/score/budget fields).
"""

import decimal
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.constants import (
    BusinessPriority,
    CampaignStatus,
    KPIType,
    Platform,
    SEVEN_DAY_WEIGHT,
    TrackingStatus,
    TWENTY_EIGHT_DAY_WEIGHT,
)
from src.metrics import CampaignMetrics, calculate_campaign_metrics
from src.models import CampaignInput
from src.validation import validate_campaign_csv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _campaign(**overrides) -> CampaignInput:
    kwargs = dict(
        campaign_id="C001",
        campaign_name="Test Campaign",
        platform=Platform.GOOGLE_ADS,
        status=CampaignStatus.ACTIVE,
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4.00"),
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
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


def _expected(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Independently reproduce the function's precision-28/ROUND_HALF_UP division."""
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        return numerator / denominator


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_campaign_metrics_accepts_exactly_five_fields():
    assert set(CampaignMetrics.model_fields.keys()) == {
        "campaign_id",
        "performance_ratio_7d",
        "performance_ratio_28d",
        "weighted_performance_ratio",
        "trend_delta",
    }


def test_campaign_metrics_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignMetrics(
            campaign_id="C001",
            performance_ratio_7d=Decimal("1"),
            performance_ratio_28d=Decimal("1"),
            weighted_performance_ratio=Decimal("1"),
            trend_delta=Decimal("0"),
            extra_field="not allowed",
        )


def test_campaign_metrics_is_immutable():
    metrics = calculate_campaign_metrics(_campaign())
    with pytest.raises(ValidationError):
        metrics.campaign_id = "C002"


def test_campaign_metrics_calculated_values_are_decimal():
    metrics = calculate_campaign_metrics(_campaign())
    for field in (
        "performance_ratio_7d",
        "performance_ratio_28d",
        "weighted_performance_ratio",
        "trend_delta",
    ):
        value = getattr(metrics, field)
        assert isinstance(value, Decimal)
        assert not isinstance(value, float)


def test_campaign_metrics_campaign_id_copied_from_input():
    metrics = calculate_campaign_metrics(_campaign(campaign_id="XYZ-1"))
    assert metrics.campaign_id == "XYZ-1"


# ---------------------------------------------------------------------------
# ROAS ratios
# ---------------------------------------------------------------------------


def test_roas_ratios_target_4_actual_5_and_4():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("5"),
        kpi_actual_28d=Decimal("4"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d == Decimal("1.25")
    assert metrics.performance_ratio_28d == Decimal("1")


def test_roas_below_target_ratio_below_one():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("3"),
        kpi_actual_28d=Decimal("3"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d < Decimal("1")
    assert metrics.performance_ratio_28d < Decimal("1")


def test_roas_exact_target_ratio_equals_one():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("4"),
        kpi_actual_28d=Decimal("4"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d == Decimal("1")
    assert metrics.performance_ratio_28d == Decimal("1")


# ---------------------------------------------------------------------------
# CPA ratios
# ---------------------------------------------------------------------------


def test_cpa_ratios_target_20_actual_16_and_20():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("20"),
        kpi_actual_7d=Decimal("16"),
        kpi_actual_28d=Decimal("20"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d == Decimal("1.25")
    assert metrics.performance_ratio_28d == Decimal("1")


def test_cpa_worse_than_target_ratio_below_one():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("20"),
        kpi_actual_7d=Decimal("25"),
        kpi_actual_28d=Decimal("25"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d < Decimal("1")
    assert metrics.performance_ratio_28d < Decimal("1")


def test_cpa_exact_target_ratio_equals_one():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("20"),
        kpi_actual_7d=Decimal("20"),
        kpi_actual_28d=Decimal("20"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d == Decimal("1")
    assert metrics.performance_ratio_28d == Decimal("1")


# ---------------------------------------------------------------------------
# Direction normalisation
# ---------------------------------------------------------------------------


def test_equivalent_outperformance_produces_same_normalised_ratio_cpa_vs_roas():
    # 25% better than target: ROAS actual = target * 1.25; CPA actual = target / 1.25
    roas_campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("10"),
        kpi_actual_7d=Decimal("12.5"),
        kpi_actual_28d=Decimal("12.5"),
    )
    cpa_campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10"),
        kpi_actual_7d=Decimal("8"),
        kpi_actual_28d=Decimal("8"),
    )
    roas_metrics = calculate_campaign_metrics(roas_campaign)
    cpa_metrics = calculate_campaign_metrics(cpa_campaign)
    assert roas_metrics.performance_ratio_7d == Decimal("1.25")
    assert cpa_metrics.performance_ratio_7d == Decimal("1.25")


def test_higher_ratio_means_better_performance_for_both_kpi_types():
    roas_better = calculate_campaign_metrics(
        _campaign(
            kpi_type=KPIType.ROAS,
            kpi_target=Decimal("4"),
            kpi_actual_7d=Decimal("6"),
            kpi_actual_28d=Decimal("6"),
        )
    )
    roas_worse = calculate_campaign_metrics(
        _campaign(
            kpi_type=KPIType.ROAS,
            kpi_target=Decimal("4"),
            kpi_actual_7d=Decimal("2"),
            kpi_actual_28d=Decimal("2"),
        )
    )
    cpa_better = calculate_campaign_metrics(
        _campaign(
            kpi_type=KPIType.CPA,
            kpi_target=Decimal("20"),
            kpi_actual_7d=Decimal("10"),
            kpi_actual_28d=Decimal("10"),
        )
    )
    cpa_worse = calculate_campaign_metrics(
        _campaign(
            kpi_type=KPIType.CPA,
            kpi_target=Decimal("20"),
            kpi_actual_7d=Decimal("40"),
            kpi_actual_28d=Decimal("40"),
        )
    )
    assert roas_better.performance_ratio_7d > roas_worse.performance_ratio_7d
    assert cpa_better.performance_ratio_7d > cpa_worse.performance_ratio_7d


# ---------------------------------------------------------------------------
# Weighted performance ratio
# ---------------------------------------------------------------------------


def test_weighted_ratio_1_25_and_1_gives_1_10():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("5"),
        kpi_actual_28d=Decimal("4"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d == Decimal("1.25")
    assert metrics.performance_ratio_28d == Decimal("1")
    assert metrics.weighted_performance_ratio == Decimal("1.10")


def test_weighted_ratio_0_80_and_1_gives_0_92():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("5"),
        kpi_actual_28d=Decimal("4"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d == Decimal("0.80")
    assert metrics.performance_ratio_28d == Decimal("1")
    assert metrics.weighted_performance_ratio == Decimal("0.92")


def test_weighted_ratio_equal_inputs_unchanged_by_weighting():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("6"),
        kpi_actual_28d=Decimal("6"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d == metrics.performance_ratio_28d == Decimal("1.5")
    assert metrics.weighted_performance_ratio == Decimal("1.5")


def test_weighted_ratio_uses_frozen_weight_constants():
    assert SEVEN_DAY_WEIGHT == Decimal("0.40")
    assert TWENTY_EIGHT_DAY_WEIGHT == Decimal("0.60")
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("1"),
        kpi_actual_7d=Decimal("2"),
        kpi_actual_28d=Decimal("3"),
    )
    metrics = calculate_campaign_metrics(campaign)
    expected = Decimal("2") * SEVEN_DAY_WEIGHT + Decimal("3") * TWENTY_EIGHT_DAY_WEIGHT
    assert metrics.weighted_performance_ratio == expected


# ---------------------------------------------------------------------------
# Relative trend delta
# ---------------------------------------------------------------------------


def test_trend_delta_1_25_and_1_gives_0_25():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("5"),
        kpi_actual_28d=Decimal("4"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.trend_delta == Decimal("0.25")


def test_trend_delta_0_80_and_1_gives_negative_0_20():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("5"),
        kpi_actual_28d=Decimal("4"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.trend_delta == Decimal("-0.20")


def test_trend_delta_equal_ratios_gives_exactly_zero():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4"),
        kpi_actual_7d=Decimal("6"),
        kpi_actual_28d=Decimal("6"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.trend_delta == Decimal("0")


def test_trend_delta_is_relative_not_simple_subtraction():
    # ratio_7d=1.44, ratio_28d=1.24: subtraction would give 0.20, the relative
    # formula gives (1.44 - 1.24) / 1.24 = 0.20 / 1.24, which is not 0.20.
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("2.50"),
        kpi_actual_7d=Decimal("3.60"),
        kpi_actual_28d=Decimal("3.10"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d == Decimal("1.44")
    assert metrics.performance_ratio_28d == Decimal("1.24")
    expected = _expected(Decimal("0.20"), Decimal("1.24"))
    assert metrics.trend_delta == expected
    assert metrics.trend_delta != Decimal("0.20")


# ---------------------------------------------------------------------------
# Precision and rounding
# ---------------------------------------------------------------------------


def test_repeating_division_matches_precision_28_round_half_up():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("3"),
        kpi_actual_7d=Decimal("1"),
        kpi_actual_28d=Decimal("1"),
    )
    metrics = calculate_campaign_metrics(campaign)
    expected = _expected(Decimal("1"), Decimal("3"))
    assert metrics.performance_ratio_7d == expected
    assert str(metrics.performance_ratio_7d) == str(expected)
    assert len(str(expected).split(".")[1]) == 28


def test_function_result_unaffected_by_mutated_global_decimal_context():
    # Build the fixture under the normal global context first — CampaignInput's own
    # (untouched) currency quantisation also reads the ambient global context, and
    # mutating it beforehand would break fixture construction for unrelated reasons.
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("3"),
        kpi_actual_7d=Decimal("1"),
        kpi_actual_28d=Decimal("1"),
    )

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        metrics = calculate_campaign_metrics(campaign)
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding

    expected = _expected(Decimal("1"), Decimal("3"))
    assert metrics.performance_ratio_7d == expected
    assert len(str(metrics.performance_ratio_7d).split(".")[1]) == 28


def test_no_currency_quantisation_applied_to_ratios():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("45.00"),
        kpi_actual_7d=Decimal("42.10"),
        kpi_actual_28d=Decimal("44.80"),
    )
    metrics = calculate_campaign_metrics(campaign)
    assert metrics.performance_ratio_7d != metrics.performance_ratio_7d.quantize(
        Decimal("0.01")
    )
    assert len(str(metrics.performance_ratio_7d).split(".")[1]) > 2


def test_no_float_in_result():
    metrics = calculate_campaign_metrics(_campaign())
    for field in (
        "performance_ratio_7d",
        "performance_ratio_28d",
        "weighted_performance_ratio",
        "trend_delta",
    ):
        assert not isinstance(getattr(metrics, field), float)


# ---------------------------------------------------------------------------
# Integration with validated CSV data
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_metrics_exact_values_and_order():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    results = [calculate_campaign_metrics(c) for c in report.valid_campaigns]

    assert [m.campaign_id for m in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": {
            "performance_ratio_7d": Decimal("45.00") / Decimal("42.10"),
            "performance_ratio_28d": Decimal("45.00") / Decimal("44.80"),
        },
        "M001": {
            "performance_ratio_7d": Decimal("4.20") / Decimal("3.50"),
            "performance_ratio_28d": Decimal("3.90") / Decimal("3.50"),
        },
        "G002": {
            "performance_ratio_7d": Decimal("3.60") / Decimal("2.50"),
            "performance_ratio_28d": Decimal("3.10") / Decimal("2.50"),
        },
        "G003": {
            "performance_ratio_7d": Decimal("60.00") / Decimal("58.00"),
            "performance_ratio_28d": Decimal("60.00") / Decimal("61.00"),
        },
    }

    for metrics in results:
        with localcontext() as ctx:
            ctx.prec = 28
            ctx.rounding = ROUND_HALF_UP
            exp_7d = expected[metrics.campaign_id]["performance_ratio_7d"]
            exp_28d = expected[metrics.campaign_id]["performance_ratio_28d"]
            exp_weighted = exp_7d * SEVEN_DAY_WEIGHT + exp_28d * TWENTY_EIGHT_DAY_WEIGHT
            exp_trend = (exp_7d - exp_28d) / exp_28d

        assert metrics.performance_ratio_7d == exp_7d
        assert metrics.performance_ratio_28d == exp_28d
        assert metrics.weighted_performance_ratio == exp_weighted
        assert metrics.trend_delta == exp_trend


# ---------------------------------------------------------------------------
# Scope boundaries
# ---------------------------------------------------------------------------


def test_no_recommendation_action_confidence_reason_code_trend_label_or_budget_fields():
    metrics = calculate_campaign_metrics(_campaign())
    field_names = set(CampaignMetrics.model_fields.keys())
    forbidden = {
        "recommendation_action",
        "confidence",
        "reason_code",
        "trend_label",
        "trend",
        "score",
        "budget",
        "kpi_type",
        "kpi_target",
        "kpi_actual_7d",
        "kpi_actual_28d",
        "conversions_7d",
        "conversions_28d",
    }
    assert field_names.isdisjoint(forbidden)
    assert not hasattr(metrics, "recommendation_action")
    assert not hasattr(metrics, "confidence")


def test_calculate_campaign_metrics_rejects_non_campaign_input():
    with pytest.raises(AttributeError):
        calculate_campaign_metrics({"kpi_type": "CPA"})  # type: ignore[arg-type]
