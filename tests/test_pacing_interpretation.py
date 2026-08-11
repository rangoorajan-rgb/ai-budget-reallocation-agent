"""Tests for the Stage 9 pacing-interpretation additions to src.pacing (Sprint 1 —
Development Stage 9).

Covers PacingStatus/CampaignPacingClass construction/immutability, exact
PACING_LOWER_THRESHOLD/PACING_UPPER_THRESHOLD boundary behaviour (including the closed,
inclusive ON_PACE interval), None -> NOT_AVAILABLE handling (including upstream-produced
None from zero elapsed time and zero current budget), Decimal precision/context
independence, integration with validate_campaign_csv + calculate_campaign_pacing over
data/sample_campaigns.csv, and scope boundaries (no performance/trend/confidence/
tracking/eligibility/score/recommendation/reason-code/allocation field, no call to any
Stage 5-8 classifier, no use of spend_variance/expected_spend/elapsed_fraction/
elapsed_days/total_period_days/remaining_budget/projected_end_of_period_spend).
"""

import ast
import decimal
import inspect
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.constants import (
    BusinessPriority,
    CampaignStatus,
    KPIType,
    PACING_LOWER_THRESHOLD,
    PACING_UPPER_THRESHOLD,
    Platform,
    TrackingStatus,
)
from src.models import CampaignInput, ReviewSetup
from src.pacing import (
    CampaignPacing,
    CampaignPacingClass,
    PacingStatus,
    calculate_campaign_pacing,
    classify_campaign_pacing,
)
from src.validation import validate_campaign_csv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _review(**overrides) -> ReviewSetup:
    kwargs = dict(
        review_id="REV-1",
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
        reviewer_name="Reviewer",
        approved_monthly_budget=Decimal("10000.00"),
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


def _pacing(**overrides) -> CampaignPacing:
    kwargs = dict(
        campaign_id="P001",
        elapsed_days=5,
        total_period_days=10,
        elapsed_fraction=Decimal("0.5"),
        expected_spend=Decimal("500.00"),
        spend_variance=Decimal("0.00"),
        pacing_ratio=Decimal("1.00"),
        remaining_budget=Decimal("500.00"),
        projected_end_of_period_spend=Decimal("1000.00"),
    )
    kwargs.update(overrides)
    return CampaignPacing(**kwargs)


# ---------------------------------------------------------------------------
# Enum and thresholds
# ---------------------------------------------------------------------------


def test_pacing_status_has_exactly_four_members():
    assert {member.name for member in PacingStatus} == {
        "UNDERSPENDING",
        "ON_PACE",
        "OVERSPENDING",
        "NOT_AVAILABLE",
    }


def test_pacing_status_exact_values():
    assert PacingStatus.UNDERSPENDING.value == "Under spending"
    assert PacingStatus.ON_PACE.value == "On pace"
    assert PacingStatus.OVERSPENDING.value == "Over spending"
    assert PacingStatus.NOT_AVAILABLE.value == "Not available"


def test_pacing_thresholds_exact_values_and_type():
    assert PACING_LOWER_THRESHOLD == Decimal("0.90")
    assert PACING_UPPER_THRESHOLD == Decimal("1.10")
    assert isinstance(PACING_LOWER_THRESHOLD, Decimal)
    assert isinstance(PACING_UPPER_THRESHOLD, Decimal)
    assert not isinstance(PACING_LOWER_THRESHOLD, float)
    assert not isinstance(PACING_UPPER_THRESHOLD, float)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_campaign_pacing_class_accepts_exactly_two_fields():
    assert set(CampaignPacingClass.model_fields.keys()) == {
        "campaign_id",
        "pacing_status",
    }


def test_campaign_pacing_class_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignPacingClass(
            campaign_id="C001",
            pacing_status=PacingStatus.ON_PACE,
            extra_field="not allowed",
        )


def test_campaign_pacing_class_is_immutable():
    result = classify_campaign_pacing(_pacing())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_campaign_id_copied_exactly():
    result = classify_campaign_pacing(_pacing(campaign_id="XYZ-1"))
    assert result.campaign_id == "XYZ-1"


def test_pacing_status_is_pacing_status_instance():
    result = classify_campaign_pacing(_pacing())
    assert isinstance(result.pacing_status, PacingStatus)


def test_classify_campaign_pacing_rejects_incompatible_input():
    with pytest.raises(AttributeError):
        classify_campaign_pacing(None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        classify_campaign_pacing({"campaign_id": "C001", "pacing_ratio": Decimal("1.00")})  # type: ignore[arg-type]


def test_result_has_no_out_of_scope_fields():
    field_names = set(CampaignPacingClass.model_fields.keys())
    forbidden = {
        "pacing_ratio",
        "spend_variance",
        "expected_spend",
        "elapsed_fraction",
        "elapsed_days",
        "total_period_days",
        "remaining_budget",
        "projected_end_of_period_spend",
        "performance_band",
        "trend_direction",
        "confidence",
        "tracking_status",
        "is_assessable",
        "is_protected",
        "is_test_campaign",
        "constraint",
        "eligibility",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Exact classification (boundary table)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pacing_ratio, expected_status",
    [
        (None, PacingStatus.NOT_AVAILABLE),
        (Decimal("0"), PacingStatus.UNDERSPENDING),
        (Decimal("0.8999"), PacingStatus.UNDERSPENDING),
        (Decimal("0.90"), PacingStatus.ON_PACE),
        (Decimal("0.9001"), PacingStatus.ON_PACE),
        (Decimal("1.00"), PacingStatus.ON_PACE),
        (Decimal("1.0999"), PacingStatus.ON_PACE),
        (Decimal("1.10"), PacingStatus.ON_PACE),
        (Decimal("1.1001"), PacingStatus.OVERSPENDING),
        (Decimal("1000000.00"), PacingStatus.OVERSPENDING),
    ],
)
def test_exact_classification_boundaries(pacing_ratio, expected_status):
    result = classify_campaign_pacing(_pacing(pacing_ratio=pacing_ratio))
    assert result.pacing_status is expected_status


# ---------------------------------------------------------------------------
# Independence
# ---------------------------------------------------------------------------


def test_function_reads_only_campaign_id_and_pacing_ratio():
    source = inspect.getsource(classify_campaign_pacing)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_name = func_def.args.args[0].arg

    accessed_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == param_name:
                accessed_attrs.add(node.attr)

    assert accessed_attrs == {"campaign_id", "pacing_ratio"}


def test_no_arithmetic_or_numeric_conversion():
    source = inspect.getsource(classify_campaign_pacing)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        assert not isinstance(node, ast.BinOp)


def test_function_does_not_call_other_classifiers():
    source = inspect.getsource(classify_campaign_pacing)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "calculate_campaign_pacing",
        "calculate_campaign_metrics",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_mutated_global_decimal_context_does_not_affect_outcome():
    pacing_below = _pacing(pacing_ratio=Decimal("0.8999"))
    pacing_at_lower = _pacing(pacing_ratio=Decimal("0.90"))
    pacing_at_upper = _pacing(pacing_ratio=Decimal("1.10"))
    pacing_above = _pacing(pacing_ratio=Decimal("1.1001"))
    pacing_none = _pacing(pacing_ratio=None)

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        assert classify_campaign_pacing(pacing_below).pacing_status is PacingStatus.UNDERSPENDING
        assert classify_campaign_pacing(pacing_at_lower).pacing_status is PacingStatus.ON_PACE
        assert classify_campaign_pacing(pacing_at_upper).pacing_status is PacingStatus.ON_PACE
        assert classify_campaign_pacing(pacing_above).pacing_status is PacingStatus.OVERSPENDING
        assert classify_campaign_pacing(pacing_none).pacing_status is PacingStatus.NOT_AVAILABLE
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_platform_and_kpi_do_not_affect_outcome():
    review = _review()
    google_cpa = _campaign(
        campaign_id="G-CPA",
        platform=Platform.GOOGLE_ADS,
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10.00"),
        kpi_actual_7d=Decimal("10.00"),
        kpi_actual_28d=Decimal("10.00"),
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
    )
    meta_roas = _campaign(
        campaign_id="M-ROAS",
        platform=Platform.META_ADS,
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("3.00"),
        kpi_actual_7d=Decimal("3.00"),
        kpi_actual_28d=Decimal("3.00"),
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
    )
    result_google = classify_campaign_pacing(calculate_campaign_pacing(review, google_cpa))
    result_meta = classify_campaign_pacing(calculate_campaign_pacing(review, meta_roas))
    assert result_google.pacing_status is result_meta.pacing_status is PacingStatus.ON_PACE


def test_protected_and_test_status_do_not_affect_outcome():
    review = _review()
    plain = _campaign(
        campaign_id="C-PLAIN",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_protected=False,
        is_test_campaign=False,
    )
    protected = _campaign(
        campaign_id="C-PROTECTED",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_protected=True,
        is_test_campaign=False,
    )
    test_campaign = _campaign(
        campaign_id="C-TEST",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_protected=False,
        is_test_campaign=True,
        test_budget_floor=Decimal("100.00"),
    )
    result_plain = classify_campaign_pacing(calculate_campaign_pacing(review, plain))
    result_protected = classify_campaign_pacing(calculate_campaign_pacing(review, protected))
    result_test = classify_campaign_pacing(calculate_campaign_pacing(review, test_campaign))
    assert (
        result_plain.pacing_status
        is result_protected.pacing_status
        is result_test.pacing_status
        is PacingStatus.ON_PACE
    )


def test_projected_end_of_period_spend_does_not_affect_outcome():
    baseline = _pacing(pacing_ratio=Decimal("1.00"), projected_end_of_period_spend=Decimal("1000.00"))
    extreme = _pacing(pacing_ratio=Decimal("1.00"), projected_end_of_period_spend=Decimal("999999.99"))
    none_projection = _pacing(pacing_ratio=Decimal("1.00"), projected_end_of_period_spend=None)
    assert (
        classify_campaign_pacing(baseline).pacing_status
        is classify_campaign_pacing(extreme).pacing_status
        is classify_campaign_pacing(none_projection).pacing_status
        is PacingStatus.ON_PACE
    )


def test_different_spend_variance_same_pacing_ratio_produce_same_result():
    low_variance = _pacing(pacing_ratio=Decimal("1.00"), spend_variance=Decimal("0.00"))
    high_variance = _pacing(pacing_ratio=Decimal("1.00"), spend_variance=Decimal("50000.00"))
    negative_variance = _pacing(pacing_ratio=Decimal("1.00"), spend_variance=Decimal("-50000.00"))
    assert (
        classify_campaign_pacing(low_variance).pacing_status
        is classify_campaign_pacing(high_variance).pacing_status
        is classify_campaign_pacing(negative_variance).pacing_status
        is PacingStatus.ON_PACE
    )


def test_no_recommendation_action_or_reason_code_assigned():
    result = classify_campaign_pacing(_pacing())
    assert not hasattr(result, "recommendation_action")
    assert not hasattr(result, "reason_code")


def test_module_does_not_import_out_of_scope_modules_or_enums():
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

    forbidden_imports = {
        "src.classification",
        "src.metrics",
        "src.constraints",
        "src.scoring",
        "src.allocation",
        "src.conservation",
        "CampaignMetrics",
        "PerformanceBand",
        "CampaignPerformanceClass",
        "TrendDirection",
        "CampaignTrendClass",
        "Confidence",
        "CampaignConfidenceClass",
        "CampaignTrackingAssessment",
        "RecommendationAction",
        "ReasonCode",
    }
    assert imported_names.isdisjoint(forbidden_imports)


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_pacing_interpretation_exact_outcomes_and_order():
    review = _review(
        review_date=date(2026, 8, 10),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    pacing_results = [calculate_campaign_pacing(review, c) for c in report.valid_campaigns]
    classified = [classify_campaign_pacing(p) for p in pacing_results]

    assert [c.campaign_id for c in classified] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": PacingStatus.OVERSPENDING,
        "M001": PacingStatus.OVERSPENDING,
        "G002": PacingStatus.OVERSPENDING,
        "G003": PacingStatus.UNDERSPENDING,
    }
    for result in classified:
        assert result.pacing_status is expected[result.campaign_id]


def test_upstream_none_from_zero_elapsed_time_classifies_as_not_available():
    review = _review(
        review_date=date(2026, 7, 1),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
    )
    campaign = _campaign(
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("200.00"),
    )
    pacing = calculate_campaign_pacing(review, campaign)
    assert pacing.pacing_ratio is None

    result = classify_campaign_pacing(pacing)
    assert result.pacing_status is PacingStatus.NOT_AVAILABLE


def test_upstream_none_from_zero_current_budget_classifies_as_not_available():
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
    assert pacing.pacing_ratio is None

    result = classify_campaign_pacing(pacing)
    assert result.pacing_status is PacingStatus.NOT_AVAILABLE
