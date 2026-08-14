"""Tests for src.reasons (Sprint 1 — Development Stage 22).

Covers CampaignRecommendationReason construction/immutability/serialization,
the six-way campaign-ID mismatch policy, HOLD's exact precedence mirroring
Stage 21 (Paused alone even when also unassessable, unassessable otherwise,
HELD_FOR_MANUAL_REVIEW for the remaining ambiguity/no-fallback causes),
the exact INCREASE/MAINTAIN/REDUCE mappings (including the two MAINTAIN
cells reachable only via a Stage 19 availability block on an otherwise
diagonal-SUITABLE direction), non-empty/ordered/deduplicated tuples across
every reachable production path, permanent absence of every excluded
ReasonCode and every excluded diagnostic input, AST verification of the
exactly-14 authorized field reads, AST verification that no Stage 1–21
production function is called, and sample-data integration.
"""

import ast
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

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
    ReasonCode,
    RecommendationAction,
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
from src.availability import resolve_campaign_action_availability
from src.metrics import calculate_campaign_metrics
from src.models import CampaignInput, ReviewSetup
from src.reasons import (
    CampaignRecommendationReason,
    resolve_campaign_recommendation_reason,
)
from src.recommendation import (
    CampaignRecommendation,
    resolve_campaign_recommendation_action,
)
from src.suitability import (
    CampaignActionSuitability,
    Suitability,
    resolve_campaign_action_suitability,
)
from src.validation import validate_campaign_csv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

APPROVED_REASON_CODES = {
    ReasonCode.PAUSED_CAMPAIGN,
    ReasonCode.TRACKING_UNRELIABLE,
    ReasonCode.HELD_FOR_MANUAL_REVIEW,
    ReasonCode.ABOVE_TARGET_STRONG,
    ReasonCode.NEAR_TARGET,
    ReasonCode.RECENT_TREND_IMPROVING,
    ReasonCode.RECENT_TREND_STABLE,
    ReasonCode.RECENT_TREND_DECLINING,
}

EXCLUDED_REASON_CODES = set(ReasonCode) - APPROVED_REASON_CODES


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


def _recommendation(**overrides) -> CampaignRecommendation:
    kwargs = dict(campaign_id="C001", recommendation_action=RecommendationAction.HOLD)
    kwargs.update(overrides)
    return CampaignRecommendation(**kwargs)


def _suitability(**overrides) -> CampaignActionSuitability:
    kwargs = dict(
        campaign_id="C001",
        increase_suitability=Suitability.NEUTRAL,
        maintain_suitability=Suitability.NEUTRAL,
        reduce_suitability=Suitability.NEUTRAL,
    )
    kwargs.update(overrides)
    return CampaignActionSuitability(**kwargs)


def _tracking(**overrides) -> CampaignTrackingAssessment:
    kwargs = dict(
        campaign_id="C001",
        tracking_status=TrackingStatus.HEALTHY,
        is_assessable=True,
    )
    kwargs.update(overrides)
    return CampaignTrackingAssessment(**kwargs)


def _performance(**overrides) -> CampaignPerformanceClass:
    kwargs = dict(campaign_id="C001", performance_band=PerformanceBand.ON_TARGET)
    kwargs.update(overrides)
    return CampaignPerformanceClass(**kwargs)


def _trend(**overrides) -> CampaignTrendClass:
    kwargs = dict(campaign_id="C001", trend_direction=TrendDirection.STABLE)
    kwargs.update(overrides)
    return CampaignTrendClass(**kwargs)


def _build_all(campaign: CampaignInput, review: ReviewSetup):
    """Run the real Stage 3/5/6/8/10-21 production chain for one campaign
    and return exactly the six objects Stage 22 is approved to accept."""
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
    suitability = resolve_campaign_action_suitability(performance, trend, availability)
    recommendation = resolve_campaign_recommendation_action(campaign, suitability, tracking)

    return recommendation, suitability, tracking, performance, trend


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_campaign_recommendation_reason_accepts_exactly_two_fields():
    assert set(CampaignRecommendationReason.model_fields.keys()) == {
        "campaign_id",
        "reason_codes",
    }


def test_campaign_recommendation_reason_field_types():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(),
        _tracking(),
        _performance(),
        _trend(),
    )
    assert isinstance(result.campaign_id, str)
    assert isinstance(result.reason_codes, tuple)
    assert all(isinstance(code, ReasonCode) for code in result.reason_codes)


def test_campaign_recommendation_reason_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignRecommendationReason(
            campaign_id="C001",
            reason_codes=(ReasonCode.PAUSED_CAMPAIGN,),
            extra_field="not allowed",
        )


def test_campaign_recommendation_reason_is_immutable():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(),
        _tracking(),
        _performance(),
        _trend(),
    )
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"
    with pytest.raises(ValidationError):
        result.reason_codes = (ReasonCode.TRACKING_UNRELIABLE,)


def test_reason_codes_tuple_is_immutable():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(),
        _tracking(),
        _performance(),
        _trend(),
    )
    with pytest.raises(AttributeError):
        result.reason_codes.append(ReasonCode.TRACKING_UNRELIABLE)  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        result.reason_codes[0] = ReasonCode.TRACKING_UNRELIABLE  # type: ignore[index]


def test_reason_codes_serialization_round_trip():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(),
        _tracking(),
        _performance(),
        _trend(),
    )
    dumped = result.model_dump()
    assert isinstance(dumped["reason_codes"], tuple)
    assert dumped["reason_codes"] == (ReasonCode.PAUSED_CAMPAIGN,)

    json_dumped = result.model_dump(mode="json")
    assert json_dumped["reason_codes"] == ["PAUSED_CAMPAIGN"]


def test_result_contains_no_forbidden_field():
    field_names = set(CampaignRecommendationReason.model_fields.keys())
    forbidden = {
        "recommendation_action",
        "reason_code",
        "primary_reason",
        "supporting_reasons",
        "confidence",
        "score",
        "rank",
        "priority",
        "amount",
        "monetary_amount",
        "increase_suitability",
        "maintain_suitability",
        "reduce_suitability",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Campaign-ID policy
# ---------------------------------------------------------------------------


def test_all_six_ids_matching_succeeds():
    result = resolve_campaign_recommendation_reason(
        _recommendation(campaign_id="MATCH-1", recommendation_action=RecommendationAction.HOLD),
        _campaign(campaign_id="MATCH-1", status=CampaignStatus.PAUSED),
        _suitability(campaign_id="MATCH-1"),
        _tracking(campaign_id="MATCH-1"),
        _performance(campaign_id="MATCH-1"),
        _trend(campaign_id="MATCH-1"),
    )
    assert result.campaign_id == "MATCH-1"


_EXACT_ERROR_MESSAGE = "Campaign IDs must match when resolving recommendation reasons."


def test_campaign_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_reason(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="OTHER"),
            _suitability(campaign_id="C001"),
            _tracking(campaign_id="C001"),
            _performance(campaign_id="C001"),
            _trend(campaign_id="C001"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_suitability_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_reason(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="C001"),
            _suitability(campaign_id="OTHER"),
            _tracking(campaign_id="C001"),
            _performance(campaign_id="C001"),
            _trend(campaign_id="C001"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_tracking_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_reason(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="C001"),
            _suitability(campaign_id="C001"),
            _tracking(campaign_id="OTHER"),
            _performance(campaign_id="C001"),
            _trend(campaign_id="C001"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_performance_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_reason(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="C001"),
            _suitability(campaign_id="C001"),
            _tracking(campaign_id="C001"),
            _performance(campaign_id="OTHER"),
            _trend(campaign_id="C001"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_trend_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_reason(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="C001"),
            _suitability(campaign_id="C001"),
            _tracking(campaign_id="C001"),
            _performance(campaign_id="C001"),
            _trend(campaign_id="OTHER"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_multiple_mismatches_raise_the_same_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_reason(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="A"),
            _suitability(campaign_id="B"),
            _tracking(campaign_id="C"),
            _performance(campaign_id="D"),
            _trend(campaign_id="E"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_id_check_occurs_before_reason_resolution():
    source = inspect.getsource(resolve_campaign_recommendation_reason)
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
    base = dict(
        recommendation=_recommendation(campaign_id="C001"),
        campaign=_campaign(campaign_id="C001", status=CampaignStatus.PAUSED),
        suitability=_suitability(campaign_id="C001"),
        tracking=_tracking(campaign_id="C001"),
        performance=_performance(campaign_id="C001"),
        trend=_trend(campaign_id="C001"),
    )
    for key in ("campaign", "suitability", "tracking", "performance", "trend"):
        args = dict(base)
        mismatched_kwargs = {
            "campaign": lambda: _campaign(campaign_id="X", status=CampaignStatus.PAUSED),
            "suitability": lambda: _suitability(campaign_id="X"),
            "tracking": lambda: _tracking(campaign_id="X"),
            "performance": lambda: _performance(campaign_id="X"),
            "trend": lambda: _trend(campaign_id="X"),
        }
        args[key] = mismatched_kwargs[key]()
        with pytest.raises(ValueError):
            resolve_campaign_recommendation_reason(**args)


def test_no_result_returned_after_mismatch():
    try:
        resolve_campaign_recommendation_reason(
            _recommendation(campaign_id="A"),
            _campaign(campaign_id="B", status=CampaignStatus.PAUSED),
            _suitability(campaign_id="A"),
            _tracking(campaign_id="A"),
            _performance(campaign_id="A"),
            _trend(campaign_id="A"),
        )
        assert False, "expected ValueError, no result should be returned"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# HOLD precedence
# ---------------------------------------------------------------------------


def test_paused_alone_yields_paused_campaign():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(),
        _tracking(is_assessable=True),
        _performance(),
        _trend(),
    )
    assert result.reason_codes == (ReasonCode.PAUSED_CAMPAIGN,)


def test_paused_and_unassessable_yields_paused_campaign_only():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(),
        _tracking(is_assessable=False),
        _performance(),
        _trend(),
    )
    assert result.reason_codes == (ReasonCode.PAUSED_CAMPAIGN,)
    assert ReasonCode.TRACKING_UNRELIABLE not in result.reason_codes


def test_unassessable_active_yields_tracking_unreliable():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(),
        _tracking(is_assessable=False),
        _performance(),
        _trend(),
    )
    assert result.reason_codes == (ReasonCode.TRACKING_UNRELIABLE,)


def test_multiple_suitable_ambiguity_yields_held_for_manual_review():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            maintain_suitability=Suitability.SUITABLE,
        ),
        _tracking(is_assessable=True),
        _performance(),
        _trend(),
    )
    assert result.reason_codes == (ReasonCode.HELD_FOR_MANUAL_REVIEW,)


def test_no_valid_fallback_yields_held_for_manual_review():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(
            increase_suitability=Suitability.NEUTRAL,
            maintain_suitability=Suitability.UNSUITABLE,
            reduce_suitability=Suitability.NEUTRAL,
        ),
        _tracking(is_assessable=True),
        _performance(),
        _trend(),
    )
    assert result.reason_codes == (ReasonCode.HELD_FOR_MANUAL_REVIEW,)


def test_held_for_manual_review_never_used_for_non_hold_action():
    for action, performance_band, trend_direction, expected in (
        (RecommendationAction.INCREASE, PerformanceBand.ABOVE_TARGET, TrendDirection.IMPROVING,
         (ReasonCode.ABOVE_TARGET_STRONG, ReasonCode.RECENT_TREND_IMPROVING)),
        (RecommendationAction.MAINTAIN, PerformanceBand.ON_TARGET, TrendDirection.STABLE,
         (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE)),
        (RecommendationAction.REDUCE, PerformanceBand.BELOW_TARGET, TrendDirection.DECLINING,
         (ReasonCode.RECENT_TREND_DECLINING,)),
    ):
        result = resolve_campaign_recommendation_reason(
            _recommendation(recommendation_action=action),
            _campaign(status=CampaignStatus.ACTIVE),
            _suitability(),
            _tracking(is_assessable=True),
            _performance(performance_band=performance_band),
            _trend(trend_direction=trend_direction),
        )
        assert result.reason_codes == expected
        assert ReasonCode.HELD_FOR_MANUAL_REVIEW not in result.reason_codes


# ---------------------------------------------------------------------------
# INCREASE mapping
# ---------------------------------------------------------------------------


def test_increase_mapping_direct_construction():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.INCREASE),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(increase_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
        _performance(performance_band=PerformanceBand.ABOVE_TARGET),
        _trend(trend_direction=TrendDirection.IMPROVING),
    )
    assert result.reason_codes == (
        ReasonCode.ABOVE_TARGET_STRONG,
        ReasonCode.RECENT_TREND_IMPROVING,
    )


def test_increase_mapping_production_path():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("2.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("3.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(campaign, review)
    assert recommendation.recommendation_action == RecommendationAction.INCREASE
    result = resolve_campaign_recommendation_reason(
        recommendation, campaign, suitability, tracking, performance, trend
    )
    assert result.reason_codes == (
        ReasonCode.ABOVE_TARGET_STRONG,
        ReasonCode.RECENT_TREND_IMPROVING,
    )


# ---------------------------------------------------------------------------
# MAINTAIN mapping - the seven approved cells
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "performance_band, trend_direction, expected",
    [
        (PerformanceBand.ABOVE_TARGET, TrendDirection.STABLE,
         (ReasonCode.ABOVE_TARGET_STRONG, ReasonCode.RECENT_TREND_STABLE)),
        (PerformanceBand.ABOVE_TARGET, TrendDirection.DECLINING,
         (ReasonCode.ABOVE_TARGET_STRONG, ReasonCode.RECENT_TREND_DECLINING)),
        (PerformanceBand.ON_TARGET, TrendDirection.IMPROVING,
         (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_IMPROVING)),
        (PerformanceBand.ON_TARGET, TrendDirection.STABLE,
         (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE)),
        (PerformanceBand.ON_TARGET, TrendDirection.DECLINING,
         (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_DECLINING)),
        (PerformanceBand.BELOW_TARGET, TrendDirection.IMPROVING,
         (ReasonCode.RECENT_TREND_IMPROVING,)),
        (PerformanceBand.BELOW_TARGET, TrendDirection.STABLE,
         (ReasonCode.RECENT_TREND_STABLE,)),
    ],
)
def test_maintain_mapping_direct_construction(performance_band, trend_direction, expected):
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.MAINTAIN),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(maintain_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
        _performance(performance_band=performance_band),
        _trend(trend_direction=trend_direction),
    )
    assert result.reason_codes == expected


@pytest.mark.parametrize(
    "kpi_type, kpi_target, kpi_actual_7d, kpi_actual_28d, expected",
    [
        # ABOVE_TARGET + STABLE
        (KPIType.ROAS, Decimal("2.00"), Decimal("3.00"), Decimal("3.00"),
         (ReasonCode.ABOVE_TARGET_STRONG, ReasonCode.RECENT_TREND_STABLE)),
        # ABOVE_TARGET + DECLINING
        (KPIType.ROAS, Decimal("2.00"), Decimal("3.00"), Decimal("5.00"),
         (ReasonCode.ABOVE_TARGET_STRONG, ReasonCode.RECENT_TREND_DECLINING)),
        # ON_TARGET + IMPROVING
        (KPIType.ROAS, Decimal("4.00"), Decimal("4.80"), Decimal("4.00"),
         (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_IMPROVING)),
        # ON_TARGET + STABLE (diagonal)
        (KPIType.ROAS, Decimal("4.00"), Decimal("4.00"), Decimal("4.00"),
         (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE)),
        # ON_TARGET + DECLINING
        (KPIType.ROAS, Decimal("4.00"), Decimal("3.40"), Decimal("4.00"),
         (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_DECLINING)),
        # BELOW_TARGET + IMPROVING
        (KPIType.CPA, Decimal("50.00"), Decimal("60.00"), Decimal("100.00"),
         (ReasonCode.RECENT_TREND_IMPROVING,)),
        # BELOW_TARGET + STABLE
        (KPIType.CPA, Decimal("50.00"), Decimal("100.00"), Decimal("100.00"),
         (ReasonCode.RECENT_TREND_STABLE,)),
    ],
)
def test_maintain_mapping_production_path(
    kpi_type, kpi_target, kpi_actual_7d, kpi_actual_28d, expected
):
    campaign = _campaign(
        kpi_type=kpi_type,
        kpi_target=kpi_target,
        kpi_actual_7d=kpi_actual_7d,
        kpi_actual_28d=kpi_actual_28d,
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(campaign, review)
    assert recommendation.recommendation_action == RecommendationAction.MAINTAIN
    result = resolve_campaign_recommendation_reason(
        recommendation, campaign, suitability, tracking, performance, trend
    )
    assert result.reason_codes == expected


# ---------------------------------------------------------------------------
# MAINTAIN mapping - the two cells reachable only via an availability block
# on an otherwise diagonal-SUITABLE direction (not separately enumerated by
# the approved seven-cell table, but the same approved performance/trend
# mapping applies unchanged)
# ---------------------------------------------------------------------------


def test_maintain_from_blocked_increase_on_above_target_improving():
    # Campaign already at its maximum budget: raw_increase_limit is zero, so
    # increase_available is False and increase_suitability becomes
    # NOT_APPLICABLE even though the ABOVE_TARGET+IMPROVING base table would
    # otherwise mark it SUITABLE. With no SUITABLE field and
    # maintain_suitability NEUTRAL, Stage 21's conservative fallback selects
    # MAINTAIN.
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("2.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("3.00"),
        current_budget=Decimal("2000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("1000.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(campaign, review)
    assert suitability.increase_suitability == Suitability.NOT_APPLICABLE
    assert performance.performance_band == PerformanceBand.ABOVE_TARGET
    assert trend.trend_direction == TrendDirection.IMPROVING
    assert recommendation.recommendation_action == RecommendationAction.MAINTAIN
    result = resolve_campaign_recommendation_reason(
        recommendation, campaign, suitability, tracking, performance, trend
    )
    assert result.reason_codes == (
        ReasonCode.ABOVE_TARGET_STRONG,
        ReasonCode.RECENT_TREND_IMPROVING,
    )


def test_maintain_from_blocked_reduce_on_below_target_declining():
    # Protected campaign: effective_decrease_limit is zero, so
    # reduce_available is False and reduce_suitability becomes
    # NOT_APPLICABLE even though the BELOW_TARGET+DECLINING base table would
    # otherwise mark it SUITABLE. Falls back to MAINTAIN.
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("50.00"),
        kpi_actual_7d=Decimal("100.00"),
        kpi_actual_28d=Decimal("60.00"),
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=True,
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(campaign, review)
    assert suitability.reduce_suitability == Suitability.NOT_APPLICABLE
    assert performance.performance_band == PerformanceBand.BELOW_TARGET
    assert trend.trend_direction == TrendDirection.DECLINING
    assert recommendation.recommendation_action == RecommendationAction.MAINTAIN
    result = resolve_campaign_recommendation_reason(
        recommendation, campaign, suitability, tracking, performance, trend
    )
    assert result.reason_codes == (ReasonCode.RECENT_TREND_DECLINING,)


# ---------------------------------------------------------------------------
# REDUCE mapping
# ---------------------------------------------------------------------------


def test_reduce_mapping_direct_construction():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.REDUCE),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(reduce_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
        _performance(performance_band=PerformanceBand.BELOW_TARGET),
        _trend(trend_direction=TrendDirection.DECLINING),
    )
    assert result.reason_codes == (ReasonCode.RECENT_TREND_DECLINING,)
    assert ReasonCode.BELOW_TARGET_MODERATE not in result.reason_codes
    assert ReasonCode.BELOW_TARGET_SEVERE not in result.reason_codes
    assert ReasonCode.STRONG_LONG_TERM_RECENT_DECLINE not in result.reason_codes


def test_reduce_mapping_production_path():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("50.00"),
        kpi_actual_7d=Decimal("100.00"),
        kpi_actual_28d=Decimal("60.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(campaign, review)
    assert recommendation.recommendation_action == RecommendationAction.REDUCE
    result = resolve_campaign_recommendation_reason(
        recommendation, campaign, suitability, tracking, performance, trend
    )
    assert result.reason_codes == (ReasonCode.RECENT_TREND_DECLINING,)


# ---------------------------------------------------------------------------
# Non-empty, ordering, and deduplication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "performance_band, trend_direction",
    [
        (pb, td)
        for pb in PerformanceBand
        for td in TrendDirection
    ],
)
def test_non_hold_reason_tuples_are_never_empty_and_never_have_duplicates(
    performance_band, trend_direction
):
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.MAINTAIN),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(maintain_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
        _performance(performance_band=performance_band),
        _trend(trend_direction=trend_direction),
    )
    assert len(result.reason_codes) >= 1
    assert len(result.reason_codes) == len(set(result.reason_codes))


def test_hold_reason_tuples_are_never_empty():
    for campaign_status, is_assessable, suitability_kwargs in (
        (CampaignStatus.PAUSED, True, {}),
        (CampaignStatus.PAUSED, False, {}),
        (CampaignStatus.ACTIVE, False, {}),
        (
            CampaignStatus.ACTIVE,
            True,
            dict(
                increase_suitability=Suitability.SUITABLE,
                maintain_suitability=Suitability.SUITABLE,
            ),
        ),
        (
            CampaignStatus.ACTIVE,
            True,
            dict(maintain_suitability=Suitability.UNSUITABLE),
        ),
    ):
        result = resolve_campaign_recommendation_reason(
            _recommendation(recommendation_action=RecommendationAction.HOLD),
            _campaign(status=campaign_status),
            _suitability(**suitability_kwargs),
            _tracking(is_assessable=is_assessable),
            _performance(),
            _trend(),
        )
        assert len(result.reason_codes) >= 1


def test_performance_reason_precedes_trend_reason():
    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.INCREASE),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(increase_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
        _performance(performance_band=PerformanceBand.ABOVE_TARGET),
        _trend(trend_direction=TrendDirection.IMPROVING),
    )
    assert result.reason_codes[0] == ReasonCode.ABOVE_TARGET_STRONG
    assert result.reason_codes[1] == ReasonCode.RECENT_TREND_IMPROVING


def test_ordering_is_not_derived_from_enum_declaration_order():
    # The ordering (performance reason, then trend reason) is fixed directly
    # by the code's branch structure, not by sorting on ReasonCode's
    # declared member order or any enum property.
    source = inspect.getsource(resolve_campaign_recommendation_reason)
    assert "sorted(" not in source
    assert ".value" not in source
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "sorted" not in called_names

    result = resolve_campaign_recommendation_reason(
        _recommendation(recommendation_action=RecommendationAction.MAINTAIN),
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(maintain_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
        _performance(performance_band=PerformanceBand.ON_TARGET),
        _trend(trend_direction=TrendDirection.DECLINING),
    )
    assert result.reason_codes == (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_DECLINING)


# ---------------------------------------------------------------------------
# Excluded codes never appear
# ---------------------------------------------------------------------------


def test_excluded_codes_never_appear_across_exhaustive_sweep():
    observed: set[ReasonCode] = set()

    # Every HOLD-producing scenario.
    for campaign_status, is_assessable, suitability_kwargs in (
        (CampaignStatus.PAUSED, True, {}),
        (CampaignStatus.PAUSED, False, {}),
        (CampaignStatus.ACTIVE, False, {}),
        (
            CampaignStatus.ACTIVE,
            True,
            dict(
                increase_suitability=Suitability.SUITABLE,
                maintain_suitability=Suitability.SUITABLE,
            ),
        ),
        (
            CampaignStatus.ACTIVE,
            True,
            dict(maintain_suitability=Suitability.UNSUITABLE),
        ),
        (
            CampaignStatus.ACTIVE,
            True,
            dict(maintain_suitability=Suitability.NOT_APPLICABLE),
        ),
    ):
        result = resolve_campaign_recommendation_reason(
            _recommendation(recommendation_action=RecommendationAction.HOLD),
            _campaign(status=campaign_status),
            _suitability(**suitability_kwargs),
            _tracking(is_assessable=is_assessable),
            _performance(),
            _trend(),
        )
        observed.update(result.reason_codes)

    # Every PerformanceBand x TrendDirection combination for every non-HOLD
    # action.
    for action in (
        RecommendationAction.INCREASE,
        RecommendationAction.MAINTAIN,
        RecommendationAction.REDUCE,
    ):
        for performance_band in PerformanceBand:
            for trend_direction in TrendDirection:
                result = resolve_campaign_recommendation_reason(
                    _recommendation(recommendation_action=action),
                    _campaign(status=CampaignStatus.ACTIVE),
                    _suitability(),
                    _tracking(is_assessable=True),
                    _performance(performance_band=performance_band),
                    _trend(trend_direction=trend_direction),
                )
                observed.update(result.reason_codes)

    assert observed.isdisjoint(EXCLUDED_REASON_CODES)
    assert observed.issubset(APPROVED_REASON_CODES)


def test_module_does_not_reference_excluded_names():
    import src.reasons as reasons_module

    source = inspect.getsource(reasons_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    forbidden = {
        "TRACKING_WARNING",
        "INSUFFICIENT_CONVERSION_VOLUME",
        "PROTECTED_FROM_REDUCTION",
        "BELOW_TARGET_MODERATE",
        "BELOW_TARGET_SEVERE",
        "STRONG_LONG_TERM_RECENT_DECLINE",
        "CAMPAIGN_CAP_REACHED",
        "CAMPAIGN_FLOOR_REACHED",
        "TEST_BUDGET_FLOOR_APPLIED",
        "MAX_CHANGE_LIMIT_APPLIED",
        "NO_ELIGIBLE_RECIPIENT",
        "ACCOUNT_RESERVE_REQUIRED",
        "Confidence",
        "PacingStatus",
        "BusinessPriority",
        "CampaignActionAvailability",
        "CampaignConfidenceClass",
        "CampaignPacingClass",
        "Decimal",
        "tracking_status",
        "is_protected",
        "decrease_blocked",
        "is_test_campaign",
        "test_budget_floor",
    }
    assert referenced.isdisjoint(forbidden)


def test_module_does_not_import_excluded_types():
    import src.reasons as reasons_module

    for forbidden_name in (
        "Confidence",
        "CampaignConfidenceClass",
        "CampaignPacingClass",
        "BusinessPriority",
        "CampaignActionAvailability",
    ):
        assert not hasattr(reasons_module, forbidden_name)


# ---------------------------------------------------------------------------
# Diagnostic facts never add reasons
# ---------------------------------------------------------------------------


def test_warning_tracking_does_not_add_tracking_warning():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("4.00"),
        tracking_status=TrackingStatus.WARNING,
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(campaign, review)
    assert tracking.is_assessable is True
    result = resolve_campaign_recommendation_reason(
        recommendation, campaign, suitability, tracking, performance, trend
    )
    assert ReasonCode.TRACKING_WARNING not in result.reason_codes


def test_protection_does_not_add_a_reason_when_increase_is_selected():
    protected_campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("2.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("3.00"),
        is_protected=True,
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(
        protected_campaign, review
    )
    assert recommendation.recommendation_action == RecommendationAction.INCREASE
    result = resolve_campaign_recommendation_reason(
        recommendation, protected_campaign, suitability, tracking, performance, trend
    )
    assert result.reason_codes == (
        ReasonCode.ABOVE_TARGET_STRONG,
        ReasonCode.RECENT_TREND_IMPROVING,
    )
    assert ReasonCode.PROTECTED_FROM_REDUCTION not in result.reason_codes


def test_test_campaign_status_does_not_add_a_reason():
    test_campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("4.00"),
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(test_campaign, review)
    assert recommendation.recommendation_action == RecommendationAction.MAINTAIN
    result = resolve_campaign_recommendation_reason(
        recommendation, test_campaign, suitability, tracking, performance, trend
    )
    assert result.reason_codes == (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE)
    assert ReasonCode.TEST_BUDGET_FLOOR_APPLIED not in result.reason_codes


def test_constraint_facts_do_not_add_a_reason_on_reduce():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("50.00"),
        kpi_actual_7d=Decimal("100.00"),
        kpi_actual_28d=Decimal("60.00"),
        campaign_max_change_percentage=Decimal("0.10"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    recommendation, suitability, tracking, performance, trend = _build_all(campaign, review)
    assert recommendation.recommendation_action == RecommendationAction.REDUCE
    result = resolve_campaign_recommendation_reason(
        recommendation, campaign, suitability, tracking, performance, trend
    )
    assert result.reason_codes == (ReasonCode.RECENT_TREND_DECLINING,)
    assert ReasonCode.MAX_CHANGE_LIMIT_APPLIED not in result.reason_codes
    assert ReasonCode.CAMPAIGN_FLOOR_REACHED not in result.reason_codes


# ---------------------------------------------------------------------------
# No recomputation / authorized fields
# ---------------------------------------------------------------------------


def test_does_not_call_earlier_production_functions():
    source = inspect.getsource(resolve_campaign_recommendation_reason)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "resolve_campaign_recommendation_action",
        "resolve_campaign_action_suitability",
        "resolve_campaign_action_availability",
        "assess_campaign_tracking",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "calculate_campaign_metrics",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_raw_decrease_limit",
        "resolve_campaign_effective_decrease_limit",
        "resolve_campaign_protection_constraint",
        "resolve_campaign_test_aware_static_decrease_room",
        "calculate_campaign_static_budget_room",
        "calculate_campaign_test_floor_room",
        "calculate_campaign_raw_percentage_movement_cap",
        "resolve_campaign_applicable_change_percentage",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_authorised_fields_are_exactly_fourteen():
    source = inspect.getsource(resolve_campaign_recommendation_reason)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_names = [arg.arg for arg in func_def.args.args]
    assert param_names == [
        "recommendation",
        "campaign",
        "suitability",
        "tracking",
        "performance",
        "trend",
    ]

    attrs_by_param: dict[str, set[str]] = {name: set() for name in param_names}
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in attrs_by_param:
                attrs_by_param[node.value.id].add(node.attr)

    assert attrs_by_param["recommendation"] == {"campaign_id", "recommendation_action"}
    assert attrs_by_param["campaign"] == {"campaign_id", "status"}
    assert attrs_by_param["suitability"] == {
        "campaign_id",
        "increase_suitability",
        "maintain_suitability",
        "reduce_suitability",
    }
    assert attrs_by_param["tracking"] == {"campaign_id", "is_assessable"}
    assert attrs_by_param["performance"] == {"campaign_id", "performance_band"}
    assert attrs_by_param["trend"] == {"campaign_id", "trend_direction"}

    total = sum(len(v) for v in attrs_by_param.values())
    assert total == 14


# ---------------------------------------------------------------------------
# Input contract
# ---------------------------------------------------------------------------


def test_none_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_recommendation_reason(  # type: ignore[arg-type]
            None, None, None, None, None, None
        )


def test_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_recommendation_reason(  # type: ignore[arg-type]
            _recommendation(),
            {"campaign_id": "C001", "status": CampaignStatus.PAUSED},
            _suitability(),
            _tracking(),
            _performance(),
            _trend(),
        )


def test_no_broad_exception_handling_in_source():
    source = inspect.getsource(resolve_campaign_recommendation_reason)
    assert "except" not in source


def test_no_production_batch_function():
    import src.reasons as reasons_module

    assert not hasattr(reasons_module, "resolve_campaign_recommendation_reasons")
    assert not hasattr(reasons_module, "calculate_campaign_recommendation_reasons")


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_recommendation_reason_exact_values():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    built = {c.campaign_id: (c, *_build_all(c, review)) for c in report.valid_campaigns}

    results = {
        campaign_id: resolve_campaign_recommendation_reason(
            recommendation, campaign, suitability, tracking, performance, trend
        )
        for campaign_id, (
            campaign,
            recommendation,
            suitability,
            tracking,
            performance,
            trend,
        ) in built.items()
    }

    assert results["G001"].reason_codes == (
        ReasonCode.NEAR_TARGET,
        ReasonCode.RECENT_TREND_STABLE,
    )
    assert results["M001"].reason_codes == (
        ReasonCode.NEAR_TARGET,
        ReasonCode.RECENT_TREND_STABLE,
    )
    assert results["G002"].reason_codes == (
        ReasonCode.ABOVE_TARGET_STRONG,
        ReasonCode.RECENT_TREND_IMPROVING,
    )
    assert results["G003"].reason_codes == (
        ReasonCode.NEAR_TARGET,
        ReasonCode.RECENT_TREND_STABLE,
    )
