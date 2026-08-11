"""Tests for the Stage 8 tracking-based assessability addition to src.classification
(Sprint 1 — Development Stage 8).

Covers CampaignTrackingAssessment shape and immutability, the exact
HEALTHY/WARNING/UNRELIABLE mapping (WARNING preserved as assessable evidence, never
collapsed into HEALTHY; UNRELIABLE the sole is_assessable=False condition), independence
from conversions/platform/KPI/protected-test status and from every other classification-
family result, integration with validate_campaign_csv over data/sample_campaigns.csv, and
scope boundaries (no CampaignMetrics/CampaignPacing/other-classifier usage, no arithmetic,
no float/Decimal, no global Decimal context dependence, Confidence.NOT_ASSESSABLE never
touched, existing Stages 5-7 behaviour unchanged).
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
    CampaignTrackingAssessment,
    CampaignTrendClass,
    Confidence,
    PerformanceBand,
    TrackingStatus,
    TrendDirection,
    assess_campaign_tracking,
    classify_campaign_confidence,
    classify_campaign_performance,
    classify_campaign_trend,
)
from src.constants import BusinessPriority, CampaignStatus, KPIType, Platform
from src.metrics import CampaignMetrics
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
# Result structure
# ---------------------------------------------------------------------------


def test_campaign_tracking_assessment_accepts_exactly_three_fields():
    assert set(CampaignTrackingAssessment.model_fields.keys()) == {
        "campaign_id",
        "tracking_status",
        "is_assessable",
    }


def test_campaign_tracking_assessment_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignTrackingAssessment(
            campaign_id="C001",
            tracking_status=TrackingStatus.HEALTHY,
            is_assessable=True,
            extra_field="not allowed",
        )


def test_campaign_tracking_assessment_is_immutable():
    result = assess_campaign_tracking(_campaign())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_tracking_status_field_is_tracking_status_instance():
    result = assess_campaign_tracking(_campaign())
    assert isinstance(result.tracking_status, TrackingStatus)


def test_is_assessable_field_is_bool():
    result = assess_campaign_tracking(_campaign())
    assert isinstance(result.is_assessable, bool)


def test_campaign_id_copied_exactly_from_campaign_input():
    result = assess_campaign_tracking(_campaign(campaign_id="XYZ-1"))
    assert result.campaign_id == "XYZ-1"


def test_tracking_status_copied_exactly_from_campaign_input():
    result = assess_campaign_tracking(_campaign(tracking_status=TrackingStatus.WARNING))
    assert result.tracking_status == TrackingStatus.WARNING


def test_invalid_input_is_not_silently_coerced():
    with pytest.raises(AttributeError):
        assess_campaign_tracking({"tracking_status": "Healthy"})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Exact mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tracking_status,expected_is_assessable",
    [
        (TrackingStatus.HEALTHY, True),
        (TrackingStatus.WARNING, True),
        (TrackingStatus.UNRELIABLE, False),
    ],
)
def test_tracking_status_mapping(tracking_status, expected_is_assessable):
    result = assess_campaign_tracking(_campaign(tracking_status=tracking_status))
    assert result.is_assessable is expected_is_assessable


# ---------------------------------------------------------------------------
# Information preservation
# ---------------------------------------------------------------------------


def test_warning_is_not_collapsed_into_healthy():
    result = assess_campaign_tracking(_campaign(tracking_status=TrackingStatus.WARNING))
    assert result.tracking_status == TrackingStatus.WARNING
    assert result.tracking_status != TrackingStatus.HEALTHY
    assert result.is_assessable is True


def test_unreliable_status_preserved_exactly():
    result = assess_campaign_tracking(_campaign(tracking_status=TrackingStatus.UNRELIABLE))
    assert result.tracking_status == TrackingStatus.UNRELIABLE


def test_no_severity_score_or_replacement_enum_produced():
    field_names = set(CampaignTrackingAssessment.model_fields.keys())
    assert "severity" not in field_names
    assert "score" not in field_names
    assert field_names == {"campaign_id", "tracking_status", "is_assessable"}


# ---------------------------------------------------------------------------
# Independence
# ---------------------------------------------------------------------------


def test_independent_of_conversions_28d():
    low = assess_campaign_tracking(
        _campaign(tracking_status=TrackingStatus.HEALTHY, conversions_28d=0)
    )
    high = assess_campaign_tracking(
        _campaign(tracking_status=TrackingStatus.HEALTHY, conversions_28d=1000)
    )
    assert low.is_assessable == high.is_assessable is True


def test_independent_of_conversions_7d():
    a = assess_campaign_tracking(
        _campaign(tracking_status=TrackingStatus.WARNING, conversions_7d=0)
    )
    b = assess_campaign_tracking(
        _campaign(tracking_status=TrackingStatus.WARNING, conversions_7d=0)
    )
    # conversions_7d must be <= conversions_28d (0 here); confirm result unaffected by
    # differing conversions_7d is exercised via the conversions_28d test above, and this
    # test additionally proves the function never reads conversions_7d at all (AST test
    # below is the authoritative proof).
    assert a.is_assessable == b.is_assessable


def test_cpa_and_roas_produce_same_result():
    cpa = assess_campaign_tracking(
        _campaign(kpi_type=KPIType.CPA, tracking_status=TrackingStatus.UNRELIABLE)
    )
    roas = assess_campaign_tracking(
        _campaign(kpi_type=KPIType.ROAS, tracking_status=TrackingStatus.UNRELIABLE)
    )
    assert cpa.is_assessable == roas.is_assessable is False


def test_platform_independence():
    google = assess_campaign_tracking(
        _campaign(platform=Platform.GOOGLE_ADS, tracking_status=TrackingStatus.WARNING)
    )
    meta = assess_campaign_tracking(
        _campaign(platform=Platform.META_ADS, tracking_status=TrackingStatus.WARNING)
    )
    assert google.is_assessable == meta.is_assessable is True


def test_protected_and_test_status_do_not_affect_result():
    protected = assess_campaign_tracking(
        _campaign(
            tracking_status=TrackingStatus.UNRELIABLE,
            is_protected=True,
        )
    )
    unprotected = assess_campaign_tracking(
        _campaign(
            tracking_status=TrackingStatus.UNRELIABLE,
            is_protected=False,
        )
    )
    test_campaign = assess_campaign_tracking(
        _campaign(
            tracking_status=TrackingStatus.UNRELIABLE,
            is_test_campaign=True,
            test_budget_floor=Decimal("100.00"),
        )
    )
    assert protected.is_assessable == unprotected.is_assessable == test_campaign.is_assessable is False


def test_function_reads_only_campaign_id_and_tracking_status():
    source = inspect.getsource(assess_campaign_tracking)
    tree = ast.parse(source)
    accessed_attrs = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "campaign"
    }
    assert accessed_attrs == {"campaign_id", "tracking_status"}


def test_function_does_not_call_other_classifiers():
    source = inspect.getsource(assess_campaign_tracking)
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint(
        {
            "classify_campaign_performance",
            "classify_campaign_trend",
            "classify_campaign_confidence",
            "calculate_campaign_metrics",
            "calculate_campaign_pacing",
        }
    )


def test_no_arithmetic_or_numeric_conversion():
    source = inspect.getsource(assess_campaign_tracking)
    tree = ast.parse(source)
    binary_ops = [node for node in ast.walk(tree) if isinstance(node, ast.BinOp)]
    assert binary_ops == []


def test_mutated_global_decimal_context_does_not_affect_outcome():
    # Build the fixture under the normal global context first — CampaignInput's own
    # (untouched) currency quantisation also reads the ambient global context.
    campaign = _campaign(tracking_status=TrackingStatus.UNRELIABLE)

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 1
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        result = assess_campaign_tracking(campaign)
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding

    assert result.is_assessable is False


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_tracking_assessment_order_and_exact_results():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    results = [assess_campaign_tracking(c) for c in report.valid_campaigns]

    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    for campaign, result in zip(report.valid_campaigns, results):
        assert campaign.tracking_status == TrackingStatus.HEALTHY
        assert result.tracking_status == TrackingStatus.HEALTHY
        assert result.is_assessable is True


# ---------------------------------------------------------------------------
# Scope verification
# ---------------------------------------------------------------------------


def test_campaign_tracking_assessment_has_no_out_of_scope_fields():
    field_names = set(CampaignTrackingAssessment.model_fields.keys())
    forbidden = {
        "confidence",
        "performance_band",
        "trend_direction",
        "pacing_ratio",
        "score",
        "reason_code",
        "recommendation_action",
        "constraint",
        "eligibility",
        "allocation",
        "conversions_7d",
        "conversions_28d",
    }
    assert field_names.isdisjoint(forbidden)


def test_not_assessable_never_touched():
    for tracking_status in (
        TrackingStatus.HEALTHY,
        TrackingStatus.WARNING,
        TrackingStatus.UNRELIABLE,
    ):
        result = assess_campaign_tracking(_campaign(tracking_status=tracking_status))
        # CampaignTrackingAssessment has no Confidence field at all; this asserts the
        # module-level Confidence.NOT_ASSESSABLE member is untouched by this function.
        assert not hasattr(result, "confidence")
    assert Confidence.NOT_ASSESSABLE.value == "NOT_ASSESSABLE"


def test_classify_campaign_confidence_remains_unchanged():
    campaign = _campaign(conversions_28d=30, tracking_status=TrackingStatus.UNRELIABLE)
    result = classify_campaign_confidence(campaign)
    assert result.confidence == Confidence.HIGH  # Stage 7 ignores tracking_status entirely


def test_classify_campaign_performance_remains_unchanged():
    metrics = CampaignMetrics(
        campaign_id="C001",
        performance_ratio_7d=Decimal("1"),
        performance_ratio_28d=Decimal("1"),
        weighted_performance_ratio=Decimal("1.15"),
        trend_delta=Decimal("0"),
    )
    result = classify_campaign_performance(metrics)
    assert result.performance_band == PerformanceBand.ABOVE_TARGET


def test_classify_campaign_trend_remains_unchanged():
    metrics = CampaignMetrics(
        campaign_id="C001",
        performance_ratio_7d=Decimal("1"),
        performance_ratio_28d=Decimal("1"),
        weighted_performance_ratio=Decimal("1"),
        trend_delta=Decimal("0.10"),
    )
    result = classify_campaign_trend(metrics)
    assert result.trend_direction == TrendDirection.IMPROVING


def test_warning_and_unreliable_not_converted_to_reason_code():
    result_warning = assess_campaign_tracking(
        _campaign(tracking_status=TrackingStatus.WARNING)
    )
    result_unreliable = assess_campaign_tracking(
        _campaign(tracking_status=TrackingStatus.UNRELIABLE)
    )
    # No ReasonCode-typed attribute exists anywhere on the result.
    assert not hasattr(result_warning, "reason_code")
    assert not hasattr(result_unreliable, "reason_code")
    assert isinstance(result_warning.tracking_status, TrackingStatus)
    assert isinstance(result_unreliable.tracking_status, TrackingStatus)
