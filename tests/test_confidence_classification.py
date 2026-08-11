"""Tests for the Stage 7 conversion-volume confidence-classification additions to
src.classification (Sprint 1 — Development Stage 7).

Covers CampaignConfidenceClass shape and immutability, exact threshold-boundary equality
behaviour (reaching a threshold enters the higher confidence band), campaign_id
propagation, conversions_28d-only window selection (including a conflicting 7-day/28-day
example), platform/KPI independence, integration with validate_campaign_csv over
data/sample_campaigns.csv, and scope boundaries (no CampaignMetrics/CampaignPacing/
ReviewSetup/TrackingStatus/PerformanceBand/TrendDirection usage, no arithmetic, no float,
no Decimal, no global Decimal context dependence, NOT_ASSESSABLE never assigned, existing
Stages 5-6 behaviour unchanged).
"""

import ast
import decimal
import inspect
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.classification import (
    CampaignConfidenceClass,
    CampaignPerformanceClass,
    CampaignTrendClass,
    PerformanceBand,
    TrendDirection,
    classify_campaign_confidence,
    classify_campaign_performance,
    classify_campaign_trend,
)
from src.constants import (
    BusinessPriority,
    CampaignStatus,
    Confidence,
    HIGH_CONFIDENCE_CONVERSIONS,
    KPIType,
    MINIMUM_CONVERSIONS,
    Platform,
    TrackingStatus,
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
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        conversions_7d=0,
        conversions_28d=0,
        kpi_actual_7d=Decimal("5.00"),
        kpi_actual_28d=Decimal("4.00"),
        tracking_status=TrackingStatus.HEALTHY,
        business_priority=BusinessPriority.STANDARD,
    )
    kwargs.update(overrides)
    return CampaignInput(**kwargs)


# ---------------------------------------------------------------------------
# Result structure and enum
# ---------------------------------------------------------------------------


def test_confidence_retains_exactly_four_members_matching_names():
    assert {member.name: member.value for member in Confidence} == {
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
        "NOT_ASSESSABLE": "NOT_ASSESSABLE",
    }


def test_campaign_confidence_class_accepts_exactly_two_fields():
    assert set(CampaignConfidenceClass.model_fields.keys()) == {
        "campaign_id",
        "confidence",
    }


def test_campaign_confidence_class_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignConfidenceClass(
            campaign_id="C001",
            confidence=Confidence.LOW,
            extra_field="not allowed",
        )


def test_campaign_confidence_class_is_immutable():
    result = classify_campaign_confidence(_campaign(conversions_28d=0))
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_confidence_field_is_confidence_instance():
    result = classify_campaign_confidence(_campaign(conversions_28d=0))
    assert isinstance(result.confidence, Confidence)


def test_campaign_id_copied_exactly_from_campaign_input():
    result = classify_campaign_confidence(_campaign(campaign_id="XYZ-1", conversions_28d=0))
    assert result.campaign_id == "XYZ-1"


def test_invalid_input_is_not_silently_coerced():
    with pytest.raises(AttributeError):
        classify_campaign_confidence({"conversions_28d": 0})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Exact boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "conversions_28d,expected_confidence",
    [
        (0, Confidence.LOW),
        (1, Confidence.LOW),
        (9, Confidence.LOW),
        (10, Confidence.MEDIUM),
        (11, Confidence.MEDIUM),
        (29, Confidence.MEDIUM),
        (30, Confidence.HIGH),
        (31, Confidence.HIGH),
        (1000000, Confidence.HIGH),
    ],
)
def test_confidence_boundaries(conversions_28d, expected_confidence):
    conversions_7d = min(conversions_28d, 0)
    result = classify_campaign_confidence(
        _campaign(conversions_7d=conversions_7d, conversions_28d=conversions_28d)
    )
    assert result.confidence == expected_confidence


def test_threshold_constants_used_directly():
    assert MINIMUM_CONVERSIONS == 10
    assert HIGH_CONFIDENCE_CONVERSIONS == 30
    at_minimum = classify_campaign_confidence(
        _campaign(conversions_7d=0, conversions_28d=MINIMUM_CONVERSIONS)
    )
    at_high = classify_campaign_confidence(
        _campaign(conversions_7d=0, conversions_28d=HIGH_CONFIDENCE_CONVERSIONS)
    )
    assert at_minimum.confidence == Confidence.MEDIUM
    assert at_high.confidence == Confidence.HIGH


def test_zero_conversions_produces_low():
    result = classify_campaign_confidence(_campaign(conversions_7d=0, conversions_28d=0))
    assert result.confidence == Confidence.LOW


# ---------------------------------------------------------------------------
# Window selection (conversions_28d only)
# ---------------------------------------------------------------------------


def test_same_conversions_28d_different_conversions_7d_give_same_confidence():
    campaign_a = _campaign(campaign_id="A", conversions_7d=0, conversions_28d=20)
    campaign_b = _campaign(campaign_id="B", conversions_7d=15, conversions_28d=20)
    result_a = classify_campaign_confidence(campaign_a)
    result_b = classify_campaign_confidence(campaign_b)
    assert result_a.confidence == result_b.confidence == Confidence.MEDIUM


def test_conflicting_window_example_uses_28d_only():
    # conversions_7d=5 alone would suggest LOW; conversions_28d=20 is authoritative.
    campaign = _campaign(conversions_7d=5, conversions_28d=20)
    result = classify_campaign_confidence(campaign)
    assert result.confidence == Confidence.MEDIUM


def test_function_does_not_read_conversions_7d():
    source = inspect.getsource(classify_campaign_confidence)
    tree = ast.parse(source)
    accessed_attrs = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "campaign"
    }
    assert accessed_attrs == {"campaign_id", "conversions_28d"}
    assert "conversions_7d" not in source


def test_function_does_not_combine_conversion_windows():
    source = inspect.getsource(classify_campaign_confidence)
    tree = ast.parse(source)
    binary_ops = [node for node in ast.walk(tree) if isinstance(node, ast.BinOp)]
    assert binary_ops == []


# ---------------------------------------------------------------------------
# Platform and KPI independence
# ---------------------------------------------------------------------------


def test_platform_and_kpi_independence():
    google_cpa = _campaign(
        campaign_id="G",
        platform=Platform.GOOGLE_ADS,
        kpi_type=KPIType.CPA,
        conversions_7d=0,
        conversions_28d=20,
    )
    meta_roas = _campaign(
        campaign_id="M",
        platform=Platform.META_ADS,
        kpi_type=KPIType.ROAS,
        conversions_7d=0,
        conversions_28d=20,
    )
    result_google = classify_campaign_confidence(google_cpa)
    result_meta = classify_campaign_confidence(meta_roas)
    assert result_google.confidence == result_meta.confidence == Confidence.MEDIUM


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_confidence_order_and_exact_results():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    results = [classify_campaign_confidence(c) for c in report.valid_campaigns]

    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": (155, Confidence.HIGH),
        "M001": (210, Confidence.HIGH),
        "G002": (520, Confidence.HIGH),
        "G003": (20, Confidence.MEDIUM),
    }
    for campaign, result in zip(report.valid_campaigns, results):
        expected_conversions, expected_confidence = expected[campaign.campaign_id]
        assert campaign.conversions_28d == expected_conversions
        assert result.confidence == expected_confidence


# ---------------------------------------------------------------------------
# Scope boundaries
# ---------------------------------------------------------------------------


def test_campaign_confidence_class_has_no_out_of_scope_fields():
    field_names = set(CampaignConfidenceClass.model_fields.keys())
    forbidden = {
        "performance_band",
        "trend_direction",
        "tracking_status",
        "assessable",
        "pacing_ratio",
        "recommendation_action",
        "reason_code",
        "constraint",
        "score",
        "eligibility",
        "allocation",
        "conversions_7d",
        "conversions_28d",
    }
    assert field_names.isdisjoint(forbidden)


def test_not_assessable_never_assigned():
    for conversions_28d in (0, 1, 9, 10, 11, 29, 30, 31, 1000000):
        result = classify_campaign_confidence(
            _campaign(conversions_7d=0, conversions_28d=conversions_28d)
        )
        assert result.confidence != Confidence.NOT_ASSESSABLE


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
        "src.pacing",
        "src.validation",
        "src.constraints",
        "src.scoring",
        "src.allocation",
        "src.conservation",
        "CampaignPacing",
        "ReviewSetup",
        "TrackingStatus",
        "RecommendationAction",
        "ReasonCode",
    }
    assert imported_names.isdisjoint(forbidden_imports)


def test_classify_campaign_confidence_does_not_call_other_classifiers():
    source = inspect.getsource(classify_campaign_confidence)
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "classify_campaign_performance" not in called_names
    assert "classify_campaign_trend" not in called_names


def test_no_float_or_decimal_in_result():
    result = classify_campaign_confidence(_campaign(conversions_28d=0))
    assert not isinstance(result.campaign_id, float)
    assert not isinstance(result.confidence.value, float)
    assert not isinstance(result.confidence.value, Decimal)


def test_mutated_global_decimal_context_does_not_affect_outcome():
    # Build the fixture under the normal global context first — CampaignInput's own
    # (untouched) currency quantisation also reads the ambient global context, and
    # mutating it beforehand would break fixture construction for unrelated reasons.
    campaign = _campaign(conversions_7d=0, conversions_28d=30)

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 1
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        result = classify_campaign_confidence(campaign)
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding

    assert result.confidence == Confidence.HIGH


def test_existing_stage5_classification_behaviour_unchanged():
    metrics = CampaignMetrics(
        campaign_id="C001",
        performance_ratio_7d=Decimal("1"),
        performance_ratio_28d=Decimal("1"),
        weighted_performance_ratio=Decimal("1.15"),
        trend_delta=Decimal("0"),
    )
    result = classify_campaign_performance(metrics)
    assert result.performance_band == PerformanceBand.ABOVE_TARGET


def test_existing_stage6_classification_behaviour_unchanged():
    metrics = CampaignMetrics(
        campaign_id="C001",
        performance_ratio_7d=Decimal("1"),
        performance_ratio_28d=Decimal("1"),
        weighted_performance_ratio=Decimal("1"),
        trend_delta=Decimal("0.10"),
    )
    result = classify_campaign_trend(metrics)
    assert result.trend_direction == TrendDirection.IMPROVING
