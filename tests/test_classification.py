"""Tests for src.classification (Sprint 1 — Development Stage 5).

Covers PerformanceBand/CampaignPerformanceClass shape and immutability, exact threshold-
boundary equality behaviour, campaign_id propagation, CPA/ROAS normalisation-independence
established through the full Stage 3 calculation path, integration with
validate_campaign_csv + calculate_campaign_metrics over data/sample_campaigns.csv, and
scope boundaries (no CampaignInput/CampaignPacing/ReviewSetup/later-stage-enum usage, no
arithmetic, no float, no global Decimal context dependence).
"""

import ast
import decimal
import inspect
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.classification import (
    CampaignPerformanceClass,
    PerformanceBand,
    classify_campaign_performance,
)
from src.constants import (
    BusinessPriority,
    CampaignStatus,
    INCREASE_THRESHOLD,
    KPIType,
    MAINTAIN_THRESHOLD,
    Platform,
    TrackingStatus,
)
from src.metrics import CampaignMetrics, calculate_campaign_metrics
from src.models import CampaignInput
from src.validation import validate_campaign_csv
from pathlib import Path

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


def test_performance_band_has_exactly_three_members():
    assert {member.value for member in PerformanceBand} == {
        "ABOVE_TARGET",
        "ON_TARGET",
        "BELOW_TARGET",
    }


def test_campaign_performance_class_accepts_exactly_two_fields():
    assert set(CampaignPerformanceClass.model_fields.keys()) == {
        "campaign_id",
        "performance_band",
    }


def test_campaign_performance_class_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignPerformanceClass(
            campaign_id="C001",
            performance_band=PerformanceBand.ON_TARGET,
            extra_field="not allowed",
        )


def test_campaign_performance_class_is_immutable():
    result = classify_campaign_performance(_metrics())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_performance_band_field_is_performance_band_instance():
    result = classify_campaign_performance(_metrics())
    assert isinstance(result.performance_band, PerformanceBand)


def test_invalid_input_is_not_silently_coerced():
    with pytest.raises(AttributeError):
        classify_campaign_performance({"weighted_performance_ratio": Decimal("1")})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Threshold boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ratio,expected_band",
    [
        (Decimal("1.1500000000000000000000000001"), PerformanceBand.ABOVE_TARGET),
        (Decimal("1.15"), PerformanceBand.ABOVE_TARGET),
        (Decimal("1.1499999999999999999999999999"), PerformanceBand.ON_TARGET),
        (Decimal("1.00"), PerformanceBand.ON_TARGET),
        (Decimal("0.9000000000000000000000000001"), PerformanceBand.ON_TARGET),
        (Decimal("0.90"), PerformanceBand.ON_TARGET),
        (Decimal("0.8999999999999999999999999999"), PerformanceBand.BELOW_TARGET),
        (Decimal("0.50"), PerformanceBand.BELOW_TARGET),
    ],
)
def test_threshold_boundaries(ratio, expected_band):
    result = classify_campaign_performance(_metrics(weighted_performance_ratio=ratio))
    assert result.performance_band == expected_band


def test_threshold_constants_used_directly():
    assert INCREASE_THRESHOLD == Decimal("1.15")
    assert MAINTAIN_THRESHOLD == Decimal("0.90")
    at_increase = classify_campaign_performance(
        _metrics(weighted_performance_ratio=INCREASE_THRESHOLD)
    )
    at_maintain = classify_campaign_performance(
        _metrics(weighted_performance_ratio=MAINTAIN_THRESHOLD)
    )
    assert at_increase.performance_band == PerformanceBand.ABOVE_TARGET
    assert at_maintain.performance_band == PerformanceBand.ON_TARGET


# ---------------------------------------------------------------------------
# Campaign identity
# ---------------------------------------------------------------------------


def test_campaign_id_copied_exactly_from_metrics():
    result = classify_campaign_performance(_metrics(campaign_id="XYZ-1"))
    assert result.campaign_id == "XYZ-1"


# ---------------------------------------------------------------------------
# KPI independence (established through the full Stage 3 calculation path)
# ---------------------------------------------------------------------------


def test_cpa_and_roas_produce_same_band_after_full_stage3_normalisation():
    # 25% better than target, expressed as ROAS (actual = target * 1.25) and as
    # CPA (actual = target / 1.25) — CampaignInput/calculate_campaign_metrics establish
    # the KPI origin; CampaignMetrics itself carries no kpi_type.
    roas_campaign = _campaign(
        campaign_id="ROAS-1",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("10"),
        kpi_actual_7d=Decimal("12.5"),
        kpi_actual_28d=Decimal("12.5"),
    )
    cpa_campaign = _campaign(
        campaign_id="CPA-1",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10"),
        kpi_actual_7d=Decimal("8"),
        kpi_actual_28d=Decimal("8"),
    )
    roas_metrics = calculate_campaign_metrics(roas_campaign)
    cpa_metrics = calculate_campaign_metrics(cpa_campaign)

    assert roas_metrics.weighted_performance_ratio == cpa_metrics.weighted_performance_ratio

    roas_result = classify_campaign_performance(roas_metrics)
    cpa_result = classify_campaign_performance(cpa_metrics)

    assert roas_result.performance_band == cpa_result.performance_band == PerformanceBand.ABOVE_TARGET


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_classification_order_and_exact_bands():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    results = [
        classify_campaign_performance(calculate_campaign_metrics(campaign))
        for campaign in report.valid_campaigns
    ]

    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected_bands = {
        "G001": PerformanceBand.ON_TARGET,
        "M001": PerformanceBand.ON_TARGET,
        "G002": PerformanceBand.ABOVE_TARGET,
        "G003": PerformanceBand.ON_TARGET,
    }
    for result in results:
        assert result.performance_band == expected_bands[result.campaign_id]


# ---------------------------------------------------------------------------
# Scope boundaries
# ---------------------------------------------------------------------------


def test_campaign_performance_class_has_no_out_of_scope_fields():
    field_names = set(CampaignPerformanceClass.model_fields.keys())
    forbidden = {
        "recommendation_action",
        "confidence",
        "reason_code",
        "trend",
        "trend_delta",
        "trend_label",
        "tracking_status",
        "pacing_ratio",
        "score",
        "eligibility",
        "allocation",
        "kpi_type",
        "weighted_performance_ratio",
    }
    assert field_names.isdisjoint(forbidden)


def test_classification_module_does_not_import_out_of_scope_modules_or_enums():
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
        "src.models",
        "src.pacing",
        "src.validation",
        "src.constraints",
        "src.scoring",
        "src.allocation",
        "src.conservation",
        "CampaignInput",
        "CampaignPacing",
        "ReviewSetup",
        "RecommendationAction",
        "Confidence",
        "ReasonCode",
    }
    assert imported_names.isdisjoint(forbidden_imports)


def test_no_float_in_result_or_inputs():
    result = classify_campaign_performance(_metrics())
    assert not isinstance(result.campaign_id, float)
    assert not isinstance(result.performance_band.value, float)


def test_classification_is_pure_comparison_no_arithmetic_side_effects():
    metrics = _metrics(weighted_performance_ratio=Decimal("1.2345678901234567890123456789"))
    ratio_before = metrics.weighted_performance_ratio
    classify_campaign_performance(metrics)
    assert metrics.weighted_performance_ratio == ratio_before  # untouched, no mutation


def test_mutated_global_decimal_context_does_not_affect_outcome():
    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 1
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        result = classify_campaign_performance(
            _metrics(weighted_performance_ratio=Decimal("1.1499999999999999999999999999"))
        )
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding

    assert result.performance_band == PerformanceBand.ON_TARGET
