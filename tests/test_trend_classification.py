"""Tests for the Stage 6 trend-classification additions to src.classification
(Sprint 1 — Development Stage 6).

Covers TrendDirection/CampaignTrendClass shape and immutability, exact threshold-boundary
equality behaviour (Policy A: reaching the threshold magnitude enters the directional
band), campaign_id propagation, CPA/ROAS normalisation-independence established through
the full Stage 3 calculation path, integration with validate_campaign_csv +
calculate_campaign_metrics over data/sample_campaigns.csv, and scope boundaries (no
CampaignInput/CampaignPacing/ReviewSetup/PerformanceBand usage, no arithmetic, no float,
no global Decimal context dependence, existing Stage 5 behaviour unchanged).
"""

import ast
import decimal
import inspect
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.classification import (
    CampaignTrendClass,
    PerformanceBand,
    TrendDirection,
    classify_campaign_performance,
    classify_campaign_trend,
)
from src.constants import (
    BusinessPriority,
    CampaignStatus,
    KPIType,
    Platform,
    TrackingStatus,
    TREND_THRESHOLD,
)
from src.metrics import CampaignMetrics, calculate_campaign_metrics
from src.models import CampaignInput
from src.validation import validate_campaign_csv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _metrics(**overrides) -> CampaignMetrics:
    kwargs = dict(
        campaign_id="C001",
        performance_ratio_7d=Decimal("1"),
        performance_ratio_28d=Decimal("1"),
        weighted_performance_ratio=Decimal("1"),
        trend_delta=Decimal("0"),
    )
    kwargs.update(overrides)
    return CampaignMetrics(**kwargs)


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


# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------


def test_trend_direction_has_exactly_three_members_matching_names():
    assert {member.name: member.value for member in TrendDirection} == {
        "IMPROVING": "IMPROVING",
        "STABLE": "STABLE",
        "DECLINING": "DECLINING",
    }


def test_campaign_trend_class_accepts_exactly_two_fields():
    assert set(CampaignTrendClass.model_fields.keys()) == {
        "campaign_id",
        "trend_direction",
    }


def test_campaign_trend_class_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignTrendClass(
            campaign_id="C001",
            trend_direction=TrendDirection.STABLE,
            extra_field="not allowed",
        )


def test_campaign_trend_class_is_immutable():
    result = classify_campaign_trend(_metrics())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_trend_direction_field_is_trend_direction_instance():
    result = classify_campaign_trend(_metrics())
    assert isinstance(result.trend_direction, TrendDirection)


def test_campaign_id_copied_exactly_from_metrics():
    result = classify_campaign_trend(_metrics(campaign_id="XYZ-1"))
    assert result.campaign_id == "XYZ-1"


def test_invalid_input_is_not_silently_coerced():
    with pytest.raises(AttributeError):
        classify_campaign_trend({"trend_delta": Decimal("0")})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Exact boundaries (Policy A)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "trend_delta,expected_direction",
    [
        (Decimal("0.1000000000000000000000000001"), TrendDirection.IMPROVING),
        (Decimal("0.10"), TrendDirection.IMPROVING),
        (Decimal("0.0999999999999999999999999999"), TrendDirection.STABLE),
        (Decimal("0.05"), TrendDirection.STABLE),
        (Decimal("0"), TrendDirection.STABLE),
        (Decimal("-0.05"), TrendDirection.STABLE),
        (Decimal("-0.0999999999999999999999999999"), TrendDirection.STABLE),
        (Decimal("-0.10"), TrendDirection.DECLINING),
        (Decimal("-0.1000000000000000000000000001"), TrendDirection.DECLINING),
        (Decimal("1000000"), TrendDirection.IMPROVING),
        (Decimal("-1000000"), TrendDirection.DECLINING),
    ],
)
def test_trend_boundaries(trend_delta, expected_direction):
    result = classify_campaign_trend(_metrics(trend_delta=trend_delta))
    assert result.trend_direction == expected_direction


def test_threshold_constant_used_directly():
    assert TREND_THRESHOLD == Decimal("0.10")
    at_positive = classify_campaign_trend(_metrics(trend_delta=TREND_THRESHOLD))
    at_negative = classify_campaign_trend(
        _metrics(trend_delta=TREND_THRESHOLD.copy_negate())
    )
    assert at_positive.trend_direction == TrendDirection.IMPROVING
    assert at_negative.trend_direction == TrendDirection.DECLINING


# ---------------------------------------------------------------------------
# KPI independence (established through the full Stage 3 calculation path)
# ---------------------------------------------------------------------------


def test_cpa_and_roas_produce_same_trend_direction_after_full_stage3_normalisation():
    # 7-day ratio 25% better than 28-day ratio, expressed as ROAS and as CPA using exact
    # terminating decimals (avoids double-rounding a repeating decimal across the two
    # independently-normalised paths) — CampaignInput/calculate_campaign_metrics
    # establish the KPI origin; CampaignMetrics itself carries no kpi_type.
    roas_campaign = _campaign(
        campaign_id="ROAS-1",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("10"),
        kpi_actual_7d=Decimal("12.5"),
        kpi_actual_28d=Decimal("10"),
    )
    cpa_campaign = _campaign(
        campaign_id="CPA-1",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10"),
        kpi_actual_7d=Decimal("8"),
        kpi_actual_28d=Decimal("10"),
    )
    roas_metrics = calculate_campaign_metrics(roas_campaign)
    cpa_metrics = calculate_campaign_metrics(cpa_campaign)

    assert roas_metrics.trend_delta == cpa_metrics.trend_delta == Decimal("0.25")

    roas_result = classify_campaign_trend(roas_metrics)
    cpa_result = classify_campaign_trend(cpa_metrics)

    assert roas_result.trend_direction == cpa_result.trend_direction == TrendDirection.IMPROVING


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_trend_order_and_exact_results():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    metrics_list = [calculate_campaign_metrics(c) for c in report.valid_campaigns]
    results = [classify_campaign_trend(m) for m in metrics_list]

    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": (Decimal("0.06413301662707838479809976233"), TrendDirection.STABLE),
        "M001": (Decimal("0.07692307692307692307692307720"), TrendDirection.STABLE),
        "G002": (Decimal("0.1612903225806451612903225806"), TrendDirection.IMPROVING),
        "G003": (Decimal("0.05172413793103448275862068951"), TrendDirection.STABLE),
    }
    for metrics, result in zip(metrics_list, results):
        expected_delta, expected_direction = expected[metrics.campaign_id]
        assert metrics.trend_delta == expected_delta
        assert result.trend_direction == expected_direction


# ---------------------------------------------------------------------------
# Scope boundaries
# ---------------------------------------------------------------------------


def test_campaign_trend_class_has_no_out_of_scope_fields():
    field_names = set(CampaignTrendClass.model_fields.keys())
    forbidden = {
        "performance_band",
        "confidence",
        "tracking_status",
        "pacing_ratio",
        "recommendation_action",
        "reason_code",
        "constraint",
        "score",
        "eligibility",
        "allocation",
        "trend_delta",
        "kpi_type",
    }
    assert field_names.isdisjoint(forbidden)


def test_classification_module_does_not_import_out_of_scope_modules_or_enums():
    # NOTE: src/classification.py now also implements Stage 7 (conversion-volume
    # confidence classification), which legitimately requires importing CampaignInput
    # (src.models) and Confidence (src.constants) — narrowed here accordingly. This
    # test still forbids every import that remains out of scope for the module as a
    # whole: CampaignPacing, ReviewSetup, RecommendationAction, and ReasonCode.
    import src.classification as classification_module

    tree = ast.parse(inspect.getsource(classification_module))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.add(node.module)
            imported_names.update(alias.name for alias in node.names)

    forbidden_imports = {
        "src.pacing",
        "src.validation",
        "src.constraints",
        "src.scoring",
        "src.allocation",
        "src.conservation",
        "CampaignPacing",
        "ReviewSetup",
        "RecommendationAction",
        "ReasonCode",
    }
    assert imported_names.isdisjoint(forbidden_imports)


def test_classify_campaign_trend_does_not_call_classify_campaign_performance():
    import src.classification as classification_module

    source = inspect.getsource(classification_module.classify_campaign_trend)
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "classify_campaign_performance" not in called_names


def test_classify_campaign_trend_reads_only_campaign_id_and_trend_delta():
    import src.classification as classification_module

    source = inspect.getsource(classification_module.classify_campaign_trend)
    tree = ast.parse(source)
    accessed_attrs = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "metrics"
    }
    assert accessed_attrs == {"campaign_id", "trend_delta"}


def test_no_float_in_result():
    result = classify_campaign_trend(_metrics())
    assert not isinstance(result.campaign_id, float)
    assert not isinstance(result.trend_direction.value, float)


def test_no_arithmetic_or_quantisation_on_trend_delta():
    metrics = _metrics(trend_delta=Decimal("0.1234567890123456789012345678"))
    delta_before = metrics.trend_delta
    classify_campaign_trend(metrics)
    assert metrics.trend_delta == delta_before  # untouched, no mutation


def test_mutated_global_decimal_context_does_not_affect_outcome():
    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 1
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        stable_result = classify_campaign_trend(
            _metrics(trend_delta=Decimal("0.0999999999999999999999999999"))
        )
        negative_boundary_result = classify_campaign_trend(
            _metrics(trend_delta=Decimal("-0.10"))
        )
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding

    assert stable_result.trend_direction == TrendDirection.STABLE
    assert negative_boundary_result.trend_direction == TrendDirection.DECLINING


def test_existing_stage5_classification_behaviour_unchanged():
    result = classify_campaign_performance(_metrics(weighted_performance_ratio=Decimal("1.15")))
    assert result.performance_band == PerformanceBand.ABOVE_TARGET
