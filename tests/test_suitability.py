"""Tests for src.suitability (Sprint 1 — Development Stage 20).

Covers the Suitability enum (exactly SUITABLE/NEUTRAL/UNSUITABLE/NOT_APPLICABLE,
exact string values, no numeric ordering, no RecommendationAction/HOLD member),
CampaignActionSuitability construction/immutability, the complete conservative
diagonal-only 3x3 base rule table (all nine PerformanceBand x TrendDirection
combinations, with all actions available), the availability-override rule (an
unavailable direction is always NOT_APPLICABLE, overriding the base table, in
both diagonal and conflict cells; unavailable never becomes UNSUITABLE), the
campaign-ID mismatch error, Decimal/numeric-scoring absence, independence from
Confidence/PacingStatus/BusinessPriority/CampaignTrackingAssessment/
RecommendationAction/ReasonCode/raw performance ratios/raw trend delta,
consumption (not recalculation) of Stage 5/6/19 facts, and scope boundaries (no
score, action, reason, confidence, pacing, priority, or allocation field).
"""

import ast
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.availability import (
    CampaignActionAvailability,
    resolve_campaign_action_availability,
)
from src.classification import (
    CampaignPerformanceClass,
    CampaignTrackingAssessment,
    CampaignTrendClass,
    PerformanceBand,
    TrendDirection,
    assess_campaign_tracking,
    classify_campaign_performance,
    classify_campaign_trend,
)
from src.constants import (
    BusinessPriority,
    CampaignStatus,
    Confidence,
    KPIType,
    Platform,
    RecommendationAction,
    ReasonCode,
    TrackingStatus,
)
from src.constraints import (
    calculate_campaign_raw_percentage_movement_cap,
    calculate_campaign_static_budget_room,
    calculate_campaign_test_floor_room,
    resolve_campaign_applicable_change_percentage,
    resolve_campaign_effective_decrease_limit,
    resolve_campaign_protection_constraint,
    resolve_campaign_raw_decrease_limit,
    resolve_campaign_raw_increase_limit,
    resolve_campaign_test_aware_static_decrease_room,
)
from src.metrics import calculate_campaign_metrics
from src.models import CampaignInput, ReviewSetup
from src.suitability import (
    CampaignActionSuitability,
    Suitability,
    resolve_campaign_action_suitability,
)
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


def _performance(**overrides) -> CampaignPerformanceClass:
    kwargs = dict(
        campaign_id="C001",
        performance_band=PerformanceBand.ON_TARGET,
    )
    kwargs.update(overrides)
    return CampaignPerformanceClass(**kwargs)


def _trend(**overrides) -> CampaignTrendClass:
    kwargs = dict(
        campaign_id="C001",
        trend_direction=TrendDirection.STABLE,
    )
    kwargs.update(overrides)
    return CampaignTrendClass(**kwargs)


def _availability(**overrides) -> CampaignActionAvailability:
    kwargs = dict(
        campaign_id="C001",
        increase_available=True,
        maintain_available=True,
        reduce_available=True,
    )
    kwargs.update(overrides)
    return CampaignActionAvailability(**kwargs)


def _build_performance_trend_availability(campaign: CampaignInput, review: ReviewSetup):
    """Run the real Stage 3/5/6/8/10-19 production path for one campaign and
    return exactly the three objects Stage 20 is approved to accept."""
    metrics = calculate_campaign_metrics(campaign)
    performance = classify_campaign_performance(metrics)
    trend = classify_campaign_trend(metrics)

    static_room = calculate_campaign_static_budget_room(campaign)
    percentage = resolve_campaign_applicable_change_percentage(review, campaign)
    raw_cap = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    test_floor_room = calculate_campaign_test_floor_room(campaign)
    decrease_room = resolve_campaign_test_aware_static_decrease_room(
        static_room, test_floor_room
    )
    protection = resolve_campaign_protection_constraint(campaign)
    raw_increase = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    raw_decrease = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    effective_decrease = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    tracking = assess_campaign_tracking(campaign)
    availability = resolve_campaign_action_availability(
        campaign, tracking, raw_increase, effective_decrease
    )

    return performance, trend, availability


# ---------------------------------------------------------------------------
# Suitability enum
# ---------------------------------------------------------------------------


def test_suitability_has_exactly_four_members():
    assert {member.name for member in Suitability} == {
        "SUITABLE",
        "NEUTRAL",
        "UNSUITABLE",
        "NOT_APPLICABLE",
    }


def test_suitability_exact_string_values():
    assert Suitability.SUITABLE.value == "Suitable"
    assert Suitability.NEUTRAL.value == "Neutral"
    assert Suitability.UNSUITABLE.value == "Unsuitable"
    assert Suitability.NOT_APPLICABLE.value == "Not Applicable"


def test_suitability_is_not_a_numeric_enum():
    assert not issubclass(Suitability, int)


def test_suitability_class_defines_no_ordering_methods():
    import src.suitability as suitability_module

    source = inspect.getsource(suitability_module)
    tree = ast.parse(source)
    class_def = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "Suitability"
    )
    defined_methods = {
        node.name for node in class_def.body if isinstance(node, ast.FunctionDef)
    }
    assert defined_methods.isdisjoint({"__lt__", "__gt__", "__le__", "__ge__"})


def test_suitability_has_no_recommendation_action_member():
    suitability_values = {member.value for member in Suitability}
    action_values = {member.value for member in RecommendationAction}
    assert suitability_values.isdisjoint(action_values)


def test_suitability_has_no_hold_member():
    assert "HOLD" not in {member.name for member in Suitability}
    assert not any(member.value == RecommendationAction.HOLD.value for member in Suitability)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_campaign_action_suitability_accepts_exactly_four_fields():
    assert set(CampaignActionSuitability.model_fields.keys()) == {
        "campaign_id",
        "increase_suitability",
        "maintain_suitability",
        "reduce_suitability",
    }


def test_campaign_action_suitability_field_types():
    result = resolve_campaign_action_suitability(_performance(), _trend(), _availability())
    assert isinstance(result.campaign_id, str)
    assert isinstance(result.increase_suitability, Suitability)
    assert isinstance(result.maintain_suitability, Suitability)
    assert isinstance(result.reduce_suitability, Suitability)


def test_campaign_action_suitability_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignActionSuitability(
            campaign_id="C001",
            increase_suitability=Suitability.NEUTRAL,
            maintain_suitability=Suitability.NEUTRAL,
            reduce_suitability=Suitability.NEUTRAL,
            extra_field="not allowed",
        )


def test_campaign_action_suitability_is_immutable():
    result = resolve_campaign_action_suitability(_performance(), _trend(), _availability())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_result_contains_no_forbidden_field():
    field_names = set(CampaignActionSuitability.model_fields.keys())
    forbidden = {
        "score",
        "recommendation_action",
        "recommendation",
        "hold",
        "reason_code",
        "confidence",
        "pacing_status",
        "business_priority",
        "allocation",
        "conservation",
        "rank",
        "increase_available",
        "maintain_available",
        "reduce_available",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Campaign-ID policy
# ---------------------------------------------------------------------------


def test_all_ids_equal_succeeds():
    result = resolve_campaign_action_suitability(
        _performance(campaign_id="MATCH-1"),
        _trend(campaign_id="MATCH-1"),
        _availability(campaign_id="MATCH-1"),
    )
    assert result.campaign_id == "MATCH-1"


def test_performance_trend_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_action_suitability(
            _performance(campaign_id="C001"),
            _trend(campaign_id="OTHER"),
            _availability(campaign_id="C001"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving action suitability."
    )


def test_performance_availability_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_action_suitability(
            _performance(campaign_id="C001"),
            _trend(campaign_id="C001"),
            _availability(campaign_id="OTHER"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving action suitability."
    )


def test_multiple_mismatches_raise_the_same_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_action_suitability(
            _performance(campaign_id="C001"),
            _trend(campaign_id="A"),
            _availability(campaign_id="B"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving action suitability."
    )


def test_id_check_occurs_before_any_rule_lookup_or_availability_evaluation():
    source = inspect.getsource(resolve_campaign_action_suitability)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    non_docstring_body = [
        stmt
        for stmt in func_def.body
        if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
    ]
    first_stmt = non_docstring_body[0]
    assert isinstance(first_stmt, ast.If)
    assert any(isinstance(node, ast.Raise) for node in ast.walk(first_stmt))


def test_no_input_id_silently_preferred():
    for mismatched_kwargs in (
        dict(trend=_trend(campaign_id="X")),
        dict(availability=_availability(campaign_id="X")),
    ):
        args = dict(
            performance=_performance(campaign_id="C001"),
            trend=_trend(campaign_id="C001"),
            availability=_availability(campaign_id="C001"),
        )
        args.update(mismatched_kwargs)
        with pytest.raises(ValueError):
            resolve_campaign_action_suitability(**args)


def test_no_result_returned_after_mismatch():
    try:
        resolve_campaign_action_suitability(
            _performance(campaign_id="A"), _trend(campaign_id="B"), _availability(campaign_id="A")
        )
        assert False, "expected ValueError, no result should be returned"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Complete base rule table (all actions available)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "performance_band, trend_direction, expected",
    [
        (
            PerformanceBand.ABOVE_TARGET,
            TrendDirection.IMPROVING,
            (Suitability.SUITABLE, Suitability.NEUTRAL, Suitability.UNSUITABLE),
        ),
        (
            PerformanceBand.ABOVE_TARGET,
            TrendDirection.STABLE,
            (Suitability.NEUTRAL, Suitability.NEUTRAL, Suitability.NEUTRAL),
        ),
        (
            PerformanceBand.ABOVE_TARGET,
            TrendDirection.DECLINING,
            (Suitability.NEUTRAL, Suitability.NEUTRAL, Suitability.NEUTRAL),
        ),
        (
            PerformanceBand.ON_TARGET,
            TrendDirection.IMPROVING,
            (Suitability.NEUTRAL, Suitability.NEUTRAL, Suitability.NEUTRAL),
        ),
        (
            PerformanceBand.ON_TARGET,
            TrendDirection.STABLE,
            (Suitability.NEUTRAL, Suitability.SUITABLE, Suitability.NEUTRAL),
        ),
        (
            PerformanceBand.ON_TARGET,
            TrendDirection.DECLINING,
            (Suitability.NEUTRAL, Suitability.NEUTRAL, Suitability.NEUTRAL),
        ),
        (
            PerformanceBand.BELOW_TARGET,
            TrendDirection.IMPROVING,
            (Suitability.NEUTRAL, Suitability.NEUTRAL, Suitability.NEUTRAL),
        ),
        (
            PerformanceBand.BELOW_TARGET,
            TrendDirection.STABLE,
            (Suitability.NEUTRAL, Suitability.NEUTRAL, Suitability.NEUTRAL),
        ),
        (
            PerformanceBand.BELOW_TARGET,
            TrendDirection.DECLINING,
            (Suitability.UNSUITABLE, Suitability.NEUTRAL, Suitability.SUITABLE),
        ),
    ],
)
def test_base_table_all_nine_combinations_all_available(
    performance_band, trend_direction, expected
):
    result = resolve_campaign_action_suitability(
        _performance(performance_band=performance_band),
        _trend(trend_direction=trend_direction),
        _availability(increase_available=True, maintain_available=True, reduce_available=True),
    )
    expected_increase, expected_maintain, expected_reduce = expected
    assert result.increase_suitability == expected_increase
    assert result.maintain_suitability == expected_maintain
    assert result.reduce_suitability == expected_reduce


# ---------------------------------------------------------------------------
# Availability overrides
# ---------------------------------------------------------------------------


def test_increase_unavailable_only_increase_not_applicable():
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.ABOVE_TARGET),
        _trend(trend_direction=TrendDirection.IMPROVING),
        _availability(increase_available=False, maintain_available=True, reduce_available=True),
    )
    assert result.increase_suitability == Suitability.NOT_APPLICABLE
    assert result.maintain_suitability == Suitability.NEUTRAL
    assert result.reduce_suitability == Suitability.UNSUITABLE


def test_maintain_unavailable_only_maintain_not_applicable():
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.ON_TARGET),
        _trend(trend_direction=TrendDirection.STABLE),
        _availability(increase_available=True, maintain_available=False, reduce_available=True),
    )
    assert result.increase_suitability == Suitability.NEUTRAL
    assert result.maintain_suitability == Suitability.NOT_APPLICABLE
    assert result.reduce_suitability == Suitability.NEUTRAL


def test_reduce_unavailable_only_reduce_not_applicable():
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.BELOW_TARGET),
        _trend(trend_direction=TrendDirection.DECLINING),
        _availability(increase_available=True, maintain_available=True, reduce_available=False),
    )
    assert result.increase_suitability == Suitability.UNSUITABLE
    assert result.maintain_suitability == Suitability.NEUTRAL
    assert result.reduce_suitability == Suitability.NOT_APPLICABLE


def test_all_unavailable_all_not_applicable():
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.ABOVE_TARGET),
        _trend(trend_direction=TrendDirection.IMPROVING),
        _availability(increase_available=False, maintain_available=False, reduce_available=False),
    )
    assert result.increase_suitability == Suitability.NOT_APPLICABLE
    assert result.maintain_suitability == Suitability.NOT_APPLICABLE
    assert result.reduce_suitability == Suitability.NOT_APPLICABLE


def test_only_maintain_available_increase_reduce_not_applicable_maintain_uses_table():
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.ON_TARGET),
        _trend(trend_direction=TrendDirection.STABLE),
        _availability(increase_available=False, maintain_available=True, reduce_available=False),
    )
    assert result.increase_suitability == Suitability.NOT_APPLICABLE
    assert result.maintain_suitability == Suitability.SUITABLE
    assert result.reduce_suitability == Suitability.NOT_APPLICABLE


def test_availability_override_works_in_conflict_cell():
    # ABOVE_TARGET + STABLE is a conflict cell (all NEUTRAL when available).
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.ABOVE_TARGET),
        _trend(trend_direction=TrendDirection.STABLE),
        _availability(increase_available=False, maintain_available=True, reduce_available=True),
    )
    assert result.increase_suitability == Suitability.NOT_APPLICABLE
    assert result.maintain_suitability == Suitability.NEUTRAL
    assert result.reduce_suitability == Suitability.NEUTRAL


def test_unavailable_never_becomes_unsuitable():
    # BELOW_TARGET + DECLINING gives increase=UNSUITABLE when available; confirm
    # that marking it unavailable overrides to NOT_APPLICABLE, never UNSUITABLE
    # being conflated with unavailability.
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.BELOW_TARGET),
        _trend(trend_direction=TrendDirection.DECLINING),
        _availability(increase_available=False, maintain_available=True, reduce_available=True),
    )
    assert result.increase_suitability == Suitability.NOT_APPLICABLE
    assert result.increase_suitability != Suitability.UNSUITABLE


def test_available_conflict_cells_remain_neutral():
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.BELOW_TARGET),
        _trend(trend_direction=TrendDirection.IMPROVING),
        _availability(increase_available=True, maintain_available=True, reduce_available=True),
    )
    assert result.increase_suitability == Suitability.NEUTRAL
    assert result.maintain_suitability == Suitability.NEUTRAL
    assert result.reduce_suitability == Suitability.NEUTRAL


# ---------------------------------------------------------------------------
# Stage 19 scenarios (via the real production chain)
# ---------------------------------------------------------------------------


def test_paused_campaign_availability_all_not_applicable():
    campaign = _campaign(status=CampaignStatus.PAUSED)
    review = _review(default_max_change_percentage=Decimal("0.20"))
    performance, trend, availability = _build_performance_trend_availability(campaign, review)
    assert availability.increase_available is False
    assert availability.maintain_available is False
    assert availability.reduce_available is False

    result = resolve_campaign_action_suitability(performance, trend, availability)
    assert result.increase_suitability == Suitability.NOT_APPLICABLE
    assert result.maintain_suitability == Suitability.NOT_APPLICABLE
    assert result.reduce_suitability == Suitability.NOT_APPLICABLE


def test_active_unassessable_availability_change_directions_not_applicable_maintain_uses_table():
    campaign = _campaign(tracking_status=TrackingStatus.UNRELIABLE)
    review = _review(default_max_change_percentage=Decimal("0.20"))
    performance, trend, availability = _build_performance_trend_availability(campaign, review)
    assert availability.increase_available is False
    assert availability.reduce_available is False
    assert availability.maintain_available is True

    result = resolve_campaign_action_suitability(performance, trend, availability)
    assert result.increase_suitability == Suitability.NOT_APPLICABLE
    assert result.reduce_suitability == Suitability.NOT_APPLICABLE
    # maintain uses the base table result for this campaign's own performance/trend
    increase_base, maintain_base, reduce_base = _base_table_lookup(performance, trend)
    assert result.maintain_suitability == maintain_base


def test_protected_campaign_reduce_not_applicable_increase_maintain_use_table():
    protected_campaign = _campaign(
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=True,
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    performance, trend, availability = _build_performance_trend_availability(
        protected_campaign, review
    )
    assert availability.reduce_available is False
    assert availability.increase_available is True
    assert availability.maintain_available is True

    result = resolve_campaign_action_suitability(performance, trend, availability)
    assert result.reduce_suitability == Suitability.NOT_APPLICABLE
    increase_base, maintain_base, reduce_base = _base_table_lookup(performance, trend)
    assert result.increase_suitability == increase_base
    assert result.maintain_suitability == maintain_base


def test_test_campaign_available_directions_use_table():
    test_campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    performance, trend, availability = _build_performance_trend_availability(
        test_campaign, review
    )
    assert availability.increase_available is True
    assert availability.maintain_available is True
    assert availability.reduce_available is True

    result = resolve_campaign_action_suitability(performance, trend, availability)
    increase_base, maintain_base, reduce_base = _base_table_lookup(performance, trend)
    assert result.increase_suitability == increase_base
    assert result.maintain_suitability == maintain_base
    assert result.reduce_suitability == reduce_base


def test_protected_and_test_synthetic_campaign_uses_only_supplied_availability():
    protected_test_campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_protected=True,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    performance, trend, availability = _build_performance_trend_availability(
        protected_test_campaign, review
    )
    result = resolve_campaign_action_suitability(performance, trend, availability)
    increase_base, maintain_base, reduce_base = _base_table_lookup(performance, trend)
    assert result.increase_suitability == (
        increase_base if availability.increase_available else Suitability.NOT_APPLICABLE
    )
    assert result.maintain_suitability == (
        maintain_base if availability.maintain_available else Suitability.NOT_APPLICABLE
    )
    assert result.reduce_suitability == (
        reduce_base if availability.reduce_available else Suitability.NOT_APPLICABLE
    )


def _base_table_lookup(performance: CampaignPerformanceClass, trend: CampaignTrendClass):
    """Mirror the module's own base table, for test-side expected-value
    computation only (not imported from the module, to avoid the test simply
    re-testing itself against its own source)."""
    table = {
        (PerformanceBand.ABOVE_TARGET, TrendDirection.IMPROVING): (
            Suitability.SUITABLE,
            Suitability.NEUTRAL,
            Suitability.UNSUITABLE,
        ),
        (PerformanceBand.ABOVE_TARGET, TrendDirection.STABLE): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.ABOVE_TARGET, TrendDirection.DECLINING): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.ON_TARGET, TrendDirection.IMPROVING): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.ON_TARGET, TrendDirection.STABLE): (
            Suitability.NEUTRAL,
            Suitability.SUITABLE,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.ON_TARGET, TrendDirection.DECLINING): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.BELOW_TARGET, TrendDirection.IMPROVING): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.BELOW_TARGET, TrendDirection.STABLE): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.BELOW_TARGET, TrendDirection.DECLINING): (
            Suitability.UNSUITABLE,
            Suitability.NEUTRAL,
            Suitability.SUITABLE,
        ),
    }
    return table[(performance.performance_band, trend.trend_direction)]


# ---------------------------------------------------------------------------
# Excluded inputs
# ---------------------------------------------------------------------------


def test_module_does_not_reference_excluded_types_or_decimal():
    import src.suitability as suitability_module

    source = inspect.getsource(suitability_module)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced_names |= {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for forbidden_name in (
        "CampaignConfidenceClass",
        "Confidence",
        "CampaignPacingClass",
        "PacingStatus",
        "BusinessPriority",
        "CampaignTrackingAssessment",
        "RecommendationAction",
        "ReasonCode",
        "Decimal",
    ):
        assert forbidden_name not in referenced_names


def test_module_does_not_import_excluded_types():
    import src.suitability as suitability_module

    for forbidden_name in (
        "CampaignConfidenceClass",
        "Confidence",
        "CampaignPacingClass",
        "PacingStatus",
        "BusinessPriority",
        "CampaignTrackingAssessment",
        "RecommendationAction",
        "ReasonCode",
    ):
        assert not hasattr(suitability_module, forbidden_name)


def test_function_does_not_read_raw_performance_ratio_or_trend_delta():
    source = inspect.getsource(resolve_campaign_action_suitability)
    assert "performance_ratio" not in source
    assert "weighted_performance_ratio" not in source
    assert "trend_delta" not in source


# ---------------------------------------------------------------------------
# No recomputation
# ---------------------------------------------------------------------------


def test_does_not_call_earlier_production_functions():
    source = inspect.getsource(resolve_campaign_action_suitability)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "classify_campaign_performance",
        "classify_campaign_trend",
        "resolve_campaign_action_availability",
        "calculate_campaign_metrics",
        "assess_campaign_tracking",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_effective_decrease_limit",
        "resolve_campaign_raw_decrease_limit",
        "resolve_campaign_protection_constraint",
        "calculate_campaign_static_budget_room",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_authorised_fields_are_exactly_eight():
    source = inspect.getsource(resolve_campaign_action_suitability)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_names = [arg.arg for arg in func_def.args.args]
    assert param_names == ["performance", "trend", "availability"]

    attrs_by_param: dict[str, set[str]] = {name: set() for name in param_names}
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in attrs_by_param:
                attrs_by_param[node.value.id].add(node.attr)

    assert attrs_by_param["performance"] == {"campaign_id", "performance_band"}
    assert attrs_by_param["trend"] == {"campaign_id", "trend_direction"}
    assert attrs_by_param["availability"] == {
        "campaign_id",
        "increase_available",
        "maintain_available",
        "reduce_available",
    }
    total = sum(len(v) for v in attrs_by_param.values())
    assert total == 8


# ---------------------------------------------------------------------------
# No numeric scoring
# ---------------------------------------------------------------------------


def test_no_arithmetic_binop_in_function():
    source = inspect.getsource(resolve_campaign_action_suitability)
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BinOp) for node in ast.walk(tree))


def test_no_float_conversion():
    source = inspect.getsource(resolve_campaign_action_suitability)
    assert "float(" not in source


def test_no_score_field_anywhere_in_model():
    field_names = set(CampaignActionSuitability.model_fields.keys())
    assert not any("score" in name for name in field_names)


def test_no_production_batch_function():
    import src.suitability as suitability_module

    assert not hasattr(suitability_module, "resolve_campaign_action_suitabilities")
    assert not hasattr(suitability_module, "calculate_campaign_action_suitabilities")


# ---------------------------------------------------------------------------
# Input contract
# ---------------------------------------------------------------------------


def test_none_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_action_suitability(None, None, None)  # type: ignore[arg-type]


def test_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_action_suitability(  # type: ignore[arg-type]
            _performance(),
            {"campaign_id": "C001", "trend_direction": TrendDirection.STABLE},
            _availability(),
        )


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_action_suitability_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    built = {
        c.campaign_id: _build_performance_trend_availability(c, review)
        for c in report.valid_campaigns
    }

    results = {
        campaign_id: resolve_campaign_action_suitability(performance, trend, availability)
        for campaign_id, (performance, trend, availability) in built.items()
    }
    assert list(results.keys()) == ["G001", "M001", "G002", "G003"]

    # G001
    g001_performance, g001_trend, g001_availability = built["G001"]
    assert g001_performance.performance_band == PerformanceBand.ON_TARGET
    assert g001_trend.trend_direction == TrendDirection.STABLE
    assert (
        g001_availability.increase_available,
        g001_availability.maintain_available,
        g001_availability.reduce_available,
    ) == (True, True, True)
    assert (
        results["G001"].increase_suitability,
        results["G001"].maintain_suitability,
        results["G001"].reduce_suitability,
    ) == (Suitability.NEUTRAL, Suitability.SUITABLE, Suitability.NEUTRAL)

    # M001
    m001_performance, m001_trend, m001_availability = built["M001"]
    assert m001_performance.performance_band == PerformanceBand.ON_TARGET
    assert m001_trend.trend_direction == TrendDirection.STABLE
    assert (
        m001_availability.increase_available,
        m001_availability.maintain_available,
        m001_availability.reduce_available,
    ) == (True, True, True)
    assert (
        results["M001"].increase_suitability,
        results["M001"].maintain_suitability,
        results["M001"].reduce_suitability,
    ) == (Suitability.NEUTRAL, Suitability.SUITABLE, Suitability.NEUTRAL)

    # G002 - protected
    g002_performance, g002_trend, g002_availability = built["G002"]
    assert g002_performance.performance_band == PerformanceBand.ABOVE_TARGET
    assert g002_trend.trend_direction == TrendDirection.IMPROVING
    assert (
        g002_availability.increase_available,
        g002_availability.maintain_available,
        g002_availability.reduce_available,
    ) == (True, True, False)
    g002_result = results["G002"]
    assert g002_result.increase_suitability == Suitability.SUITABLE
    assert g002_result.maintain_suitability == Suitability.NEUTRAL
    assert g002_result.reduce_suitability == Suitability.NOT_APPLICABLE
    # REDUCE is NOT_APPLICABLE, not UNSUITABLE - unavailability is never
    # represented as a negative suitability judgement.
    assert g002_result.reduce_suitability != Suitability.UNSUITABLE
    # INCREASE being SUITABLE does not select RecommendationAction.INCREASE -
    # no such field or type exists anywhere on the result.
    assert not hasattr(g002_result, "recommendation_action")

    # G003 - test campaign
    g003_performance, g003_trend, g003_availability = built["G003"]
    assert g003_performance.performance_band == PerformanceBand.ON_TARGET
    assert g003_trend.trend_direction == TrendDirection.STABLE
    assert (
        g003_availability.increase_available,
        g003_availability.maintain_available,
        g003_availability.reduce_available,
    ) == (True, True, True)
    assert (
        results["G003"].increase_suitability,
        results["G003"].maintain_suitability,
        results["G003"].reduce_suitability,
    ) == (Suitability.NEUTRAL, Suitability.SUITABLE, Suitability.NEUTRAL)


def test_g002_protection_not_read_directly_by_suitability():
    source = inspect.getsource(resolve_campaign_action_suitability)
    assert "is_protected" not in source
    assert "decrease_blocked" not in source


# ---------------------------------------------------------------------------
# Synthetic conflict-combination integration cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "performance_band, trend_direction",
    [
        (PerformanceBand.ABOVE_TARGET, TrendDirection.STABLE),
        (PerformanceBand.ABOVE_TARGET, TrendDirection.DECLINING),
        (PerformanceBand.ON_TARGET, TrendDirection.IMPROVING),
        (PerformanceBand.ON_TARGET, TrendDirection.DECLINING),
        (PerformanceBand.BELOW_TARGET, TrendDirection.IMPROVING),
        (PerformanceBand.BELOW_TARGET, TrendDirection.STABLE),
    ],
)
def test_all_six_conflict_combinations_are_neutral_when_available(
    performance_band, trend_direction
):
    result = resolve_campaign_action_suitability(
        _performance(performance_band=performance_band),
        _trend(trend_direction=trend_direction),
        _availability(increase_available=True, maintain_available=True, reduce_available=True),
    )
    assert result.increase_suitability == Suitability.NEUTRAL
    assert result.maintain_suitability == Suitability.NEUTRAL
    assert result.reduce_suitability == Suitability.NEUTRAL


@pytest.mark.parametrize(
    "increase_available, maintain_available, reduce_available",
    [
        (True, True, True),
        (False, True, True),
        (True, False, True),
        (True, True, False),
        (False, False, True),
        (False, True, False),
        (True, False, False),
        (False, False, False),
    ],
)
def test_availability_patterns_across_a_conflict_cell(
    increase_available, maintain_available, reduce_available
):
    result = resolve_campaign_action_suitability(
        _performance(performance_band=PerformanceBand.ON_TARGET),
        _trend(trend_direction=TrendDirection.DECLINING),
        _availability(
            increase_available=increase_available,
            maintain_available=maintain_available,
            reduce_available=reduce_available,
        ),
    )
    assert result.increase_suitability == (
        Suitability.NEUTRAL if increase_available else Suitability.NOT_APPLICABLE
    )
    assert result.maintain_suitability == (
        Suitability.NEUTRAL if maintain_available else Suitability.NOT_APPLICABLE
    )
    assert result.reduce_suitability == (
        Suitability.NEUTRAL if reduce_available else Suitability.NOT_APPLICABLE
    )
