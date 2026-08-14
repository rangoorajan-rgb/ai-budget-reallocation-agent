"""Tests for src.recommendation (Sprint 1 — Development Stage 21).

Covers CampaignRecommendation construction/immutability, the exact ordered
action-selection policy (Paused override, tracking-assessability override,
unique-SUITABLE selection, multiple-SUITABLE ambiguity resolved to HOLD, the
conservative MAINTAIN fallback when maintain_suitability is NEUTRAL, and the
final HOLD fallback otherwise), the campaign-ID mismatch error, independence
from Confidence/PacingStatus/BusinessPriority/CampaignActionAvailability/
raw monetary limits/ReasonCode, consumption (not recalculation) of Stage 5/6/
8/19/20 facts, and scope boundaries (no reason, confidence, score, rank,
priority, or monetary field).
"""

import ast
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.classification import (
    CampaignTrackingAssessment,
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
from src.recommendation import (
    CampaignRecommendation,
    resolve_campaign_recommendation_action,
)
from src.suitability import (
    CampaignActionSuitability,
    PerformanceBand,
    Suitability,
    TrendDirection,
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


def _build_suitability_and_tracking(campaign: CampaignInput, review: ReviewSetup):
    """Run the real Stage 3/5/6/8/10-20 production path for one campaign and
    return exactly the two non-CampaignInput objects Stage 21 is approved to
    accept, alongside the campaign itself."""
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

    return suitability, tracking


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_campaign_recommendation_accepts_exactly_two_fields():
    assert set(CampaignRecommendation.model_fields.keys()) == {
        "campaign_id",
        "recommendation_action",
    }


def test_campaign_recommendation_field_types():
    result = resolve_campaign_recommendation_action(_campaign(), _suitability(), _tracking())
    assert isinstance(result.campaign_id, str)
    assert isinstance(result.recommendation_action, RecommendationAction)


def test_campaign_recommendation_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignRecommendation(
            campaign_id="C001",
            recommendation_action=RecommendationAction.HOLD,
            extra_field="not allowed",
        )


def test_campaign_recommendation_is_immutable():
    result = resolve_campaign_recommendation_action(_campaign(), _suitability(), _tracking())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_result_contains_no_forbidden_field():
    field_names = set(CampaignRecommendation.model_fields.keys())
    forbidden = {
        "reason_code",
        "reason_codes",
        "requires_manual_review",
        "confidence",
        "score",
        "rank",
        "priority",
        "amount",
        "monetary_amount",
        "raw_increase_limit",
        "effective_decrease_limit",
        "increase_available",
        "maintain_available",
        "reduce_available",
        "increase_suitability",
        "maintain_suitability",
        "reduce_suitability",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Campaign-ID policy
# ---------------------------------------------------------------------------


def test_all_ids_matching_succeeds():
    result = resolve_campaign_recommendation_action(
        _campaign(campaign_id="MATCH-1"),
        _suitability(campaign_id="MATCH-1"),
        _tracking(campaign_id="MATCH-1"),
    )
    assert result.campaign_id == "MATCH-1"


def test_suitability_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_action(
            _campaign(campaign_id="C001"),
            _suitability(campaign_id="OTHER"),
            _tracking(campaign_id="C001"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving recommendation action."
    )


def test_tracking_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_action(
            _campaign(campaign_id="C001"),
            _suitability(campaign_id="C001"),
            _tracking(campaign_id="OTHER"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving recommendation action."
    )


def test_multiple_mismatches_raise_the_same_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_recommendation_action(
            _campaign(campaign_id="C001"),
            _suitability(campaign_id="A"),
            _tracking(campaign_id="B"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving recommendation action."
    )


def test_id_check_occurs_before_status_assessability_or_suitability_evaluation():
    source = inspect.getsource(resolve_campaign_recommendation_action)
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
        dict(suitability=_suitability(campaign_id="X")),
        dict(tracking=_tracking(campaign_id="X")),
    ):
        args = dict(
            campaign=_campaign(campaign_id="C001"),
            suitability=_suitability(campaign_id="C001"),
            tracking=_tracking(campaign_id="C001"),
        )
        args.update(mismatched_kwargs)
        with pytest.raises(ValueError):
            resolve_campaign_recommendation_action(**args)


def test_no_result_returned_after_mismatch():
    try:
        resolve_campaign_recommendation_action(
            _campaign(campaign_id="A"), _suitability(campaign_id="B"), _tracking(campaign_id="A")
        )
        assert False, "expected ValueError, no result should be returned"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Paused override
# ---------------------------------------------------------------------------


def test_paused_assessable_increase_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(increase_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_paused_assessable_maintain_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(maintain_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_paused_assessable_reduce_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(reduce_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=True),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_paused_unassessable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(),
        _tracking(is_assessable=False),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_paused_all_neutral_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(
            increase_suitability=Suitability.NEUTRAL,
            maintain_suitability=Suitability.NEUTRAL,
            reduce_suitability=Suitability.NEUTRAL,
        ),
        _tracking(is_assessable=True),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_paused_multiple_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.PAUSED),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            maintain_suitability=Suitability.SUITABLE,
        ),
        _tracking(is_assessable=True),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_paused_is_never_an_error():
    try:
        result = resolve_campaign_recommendation_action(
            _campaign(status=CampaignStatus.PAUSED), _suitability(), _tracking()
        )
    except Exception as exc:  # noqa: BLE001 - explicit confirmation no exception is raised
        pytest.fail(f"Paused campaign raised an unexpected exception: {exc!r}")
    assert result.recommendation_action == RecommendationAction.HOLD


# ---------------------------------------------------------------------------
# Assessability override
# ---------------------------------------------------------------------------


def test_active_unassessable_increase_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(increase_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=False),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_active_unassessable_maintain_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(maintain_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=False),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_active_unassessable_reduce_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(reduce_suitability=Suitability.SUITABLE),
        _tracking(is_assessable=False),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_active_unassessable_all_neutral_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.ACTIVE), _suitability(), _tracking(is_assessable=False)
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_active_unassessable_multiple_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(status=CampaignStatus.ACTIVE),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            reduce_suitability=Suitability.SUITABLE,
        ),
        _tracking(is_assessable=False),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_warning_assessable_follows_ordinary_selection():
    campaign = _campaign(status=CampaignStatus.ACTIVE, tracking_status=TrackingStatus.WARNING)
    tracking = assess_campaign_tracking(campaign)
    assert tracking.is_assessable is True
    result = resolve_campaign_recommendation_action(
        campaign,
        _suitability(maintain_suitability=Suitability.SUITABLE),
        tracking,
    )
    assert result.recommendation_action == RecommendationAction.MAINTAIN


def test_reads_is_assessable_only_not_tracking_status():
    source = inspect.getsource(resolve_campaign_recommendation_action)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    tracking_param = func_def.args.args[2].arg
    assert tracking_param == "tracking"
    tracking_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == tracking_param:
                tracking_attrs.add(node.attr)
    assert tracking_attrs == {"campaign_id", "is_assessable"}
    assert "tracking_status" not in source


# ---------------------------------------------------------------------------
# Unique-SUITABLE selection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "maintain_value, reduce_value",
    [
        (Suitability.NEUTRAL, Suitability.NEUTRAL),
        (Suitability.UNSUITABLE, Suitability.UNSUITABLE),
        (Suitability.NOT_APPLICABLE, Suitability.NOT_APPLICABLE),
        (Suitability.NEUTRAL, Suitability.UNSUITABLE),
        (Suitability.NOT_APPLICABLE, Suitability.NEUTRAL),
    ],
)
def test_increase_only_suitable_selects_increase(maintain_value, reduce_value):
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            maintain_suitability=maintain_value,
            reduce_suitability=reduce_value,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.INCREASE


@pytest.mark.parametrize(
    "increase_value, reduce_value",
    [
        (Suitability.NEUTRAL, Suitability.NEUTRAL),
        (Suitability.UNSUITABLE, Suitability.UNSUITABLE),
        (Suitability.NOT_APPLICABLE, Suitability.NOT_APPLICABLE),
        (Suitability.NEUTRAL, Suitability.UNSUITABLE),
        (Suitability.NOT_APPLICABLE, Suitability.NEUTRAL),
    ],
)
def test_maintain_only_suitable_selects_maintain(increase_value, reduce_value):
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=increase_value,
            maintain_suitability=Suitability.SUITABLE,
            reduce_suitability=reduce_value,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.MAINTAIN


@pytest.mark.parametrize(
    "increase_value, maintain_value",
    [
        (Suitability.NEUTRAL, Suitability.NEUTRAL),
        (Suitability.UNSUITABLE, Suitability.UNSUITABLE),
        (Suitability.NOT_APPLICABLE, Suitability.NOT_APPLICABLE),
        (Suitability.NEUTRAL, Suitability.UNSUITABLE),
        (Suitability.NOT_APPLICABLE, Suitability.NEUTRAL),
    ],
)
def test_reduce_only_suitable_selects_reduce(increase_value, maintain_value):
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=increase_value,
            maintain_suitability=maintain_value,
            reduce_suitability=Suitability.SUITABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.REDUCE


def test_unique_suitable_selection_independent_of_enum_declaration_order():
    # The Suitability enum's declared order is SUITABLE, NEUTRAL, UNSUITABLE,
    # NOT_APPLICABLE - confirm REDUCE (last field, and its SUITABLE match is
    # not first in declaration order) is still selected correctly.
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.UNSUITABLE,
            maintain_suitability=Suitability.NOT_APPLICABLE,
            reduce_suitability=Suitability.SUITABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.REDUCE


# ---------------------------------------------------------------------------
# No-SUITABLE fallback
# ---------------------------------------------------------------------------


def test_all_neutral_with_maintain_neutral_maintains():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.NEUTRAL,
            maintain_suitability=Suitability.NEUTRAL,
            reduce_suitability=Suitability.NEUTRAL,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.MAINTAIN


def test_increase_unsuitable_maintain_neutral_reduce_neutral_maintains():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.UNSUITABLE,
            maintain_suitability=Suitability.NEUTRAL,
            reduce_suitability=Suitability.NEUTRAL,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.MAINTAIN


def test_increase_neutral_maintain_neutral_reduce_unsuitable_maintains():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.NEUTRAL,
            maintain_suitability=Suitability.NEUTRAL,
            reduce_suitability=Suitability.UNSUITABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.MAINTAIN


def test_increase_and_reduce_not_applicable_maintain_neutral_maintains():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.NOT_APPLICABLE,
            maintain_suitability=Suitability.NEUTRAL,
            reduce_suitability=Suitability.NOT_APPLICABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.MAINTAIN


def test_maintain_unsuitable_with_no_suitable_action_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.NEUTRAL,
            maintain_suitability=Suitability.UNSUITABLE,
            reduce_suitability=Suitability.NEUTRAL,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_maintain_not_applicable_with_no_suitable_action_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.NEUTRAL,
            maintain_suitability=Suitability.NOT_APPLICABLE,
            reduce_suitability=Suitability.NEUTRAL,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_all_not_applicable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.NOT_APPLICABLE,
            maintain_suitability=Suitability.NOT_APPLICABLE,
            reduce_suitability=Suitability.NOT_APPLICABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_all_unsuitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.UNSUITABLE,
            maintain_suitability=Suitability.UNSUITABLE,
            reduce_suitability=Suitability.UNSUITABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


# ---------------------------------------------------------------------------
# Multiple-SUITABLE ambiguity
# ---------------------------------------------------------------------------


def test_increase_and_maintain_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            maintain_suitability=Suitability.SUITABLE,
            reduce_suitability=Suitability.NEUTRAL,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_increase_and_reduce_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            maintain_suitability=Suitability.NEUTRAL,
            reduce_suitability=Suitability.SUITABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_maintain_and_reduce_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.NEUTRAL,
            maintain_suitability=Suitability.SUITABLE,
            reduce_suitability=Suitability.SUITABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_all_three_suitable_holds():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            maintain_suitability=Suitability.SUITABLE,
            reduce_suitability=Suitability.SUITABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_no_fixed_precedence_no_error_no_silent_maintain_fallback():
    # Confirm the multiple-SUITABLE case never raises and never silently
    # resolves to MAINTAIN or the "first" field's action (INCREASE).
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            maintain_suitability=Suitability.SUITABLE,
            reduce_suitability=Suitability.NEUTRAL,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD
    assert result.recommendation_action != RecommendationAction.INCREASE
    assert result.recommendation_action != RecommendationAction.MAINTAIN


# ---------------------------------------------------------------------------
# Production-path cases (real Stage 3/5/6/8/10-20 chain)
# ---------------------------------------------------------------------------


def test_above_target_improving_all_applicable_selects_increase():
    # ROAS campaign, actual well above target for both windows, improving.
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("2.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("3.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(campaign, review)
    assert suitability.increase_suitability == Suitability.SUITABLE
    result = resolve_campaign_recommendation_action(campaign, suitability, tracking)
    assert result.recommendation_action == RecommendationAction.INCREASE


def test_on_target_stable_all_applicable_selects_maintain():
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("4.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(campaign, review)
    assert suitability.maintain_suitability == Suitability.SUITABLE
    result = resolve_campaign_recommendation_action(campaign, suitability, tracking)
    assert result.recommendation_action == RecommendationAction.MAINTAIN


def test_below_target_declining_all_applicable_selects_reduce():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("50.00"),
        kpi_actual_7d=Decimal("100.00"),
        kpi_actual_28d=Decimal("60.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(campaign, review)
    assert suitability.reduce_suitability == Suitability.SUITABLE
    result = resolve_campaign_recommendation_action(campaign, suitability, tracking)
    assert result.recommendation_action == RecommendationAction.REDUCE


@pytest.mark.parametrize(
    "kpi_type, kpi_target, kpi_actual_7d, kpi_actual_28d",
    [
        # ABOVE_TARGET + STABLE
        (KPIType.ROAS, Decimal("2.00"), Decimal("3.00"), Decimal("3.00")),
        # ABOVE_TARGET + DECLINING
        (KPIType.ROAS, Decimal("2.00"), Decimal("3.00"), Decimal("5.00")),
        # ON_TARGET + IMPROVING
        (KPIType.ROAS, Decimal("4.00"), Decimal("4.80"), Decimal("4.00")),
        # ON_TARGET + DECLINING
        (KPIType.ROAS, Decimal("4.00"), Decimal("3.40"), Decimal("4.00")),
        # BELOW_TARGET + IMPROVING
        (KPIType.CPA, Decimal("50.00"), Decimal("60.00"), Decimal("100.00")),
        # BELOW_TARGET + STABLE
        (KPIType.CPA, Decimal("50.00"), Decimal("100.00"), Decimal("100.00")),
    ],
)
def test_each_mixed_cell_maintains_when_active_and_assessable(
    kpi_type, kpi_target, kpi_actual_7d, kpi_actual_28d
):
    campaign = _campaign(
        kpi_type=kpi_type,
        kpi_target=kpi_target,
        kpi_actual_7d=kpi_actual_7d,
        kpi_actual_28d=kpi_actual_28d,
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(campaign, review)
    assert suitability.increase_suitability != Suitability.SUITABLE
    assert suitability.maintain_suitability != Suitability.SUITABLE
    assert suitability.reduce_suitability != Suitability.SUITABLE
    result = resolve_campaign_recommendation_action(campaign, suitability, tracking)
    assert result.recommendation_action == RecommendationAction.MAINTAIN


def test_protected_campaign_cannot_resolve_reduce():
    protected_campaign = _campaign(
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
    suitability, tracking = _build_suitability_and_tracking(protected_campaign, review)
    assert suitability.reduce_suitability == Suitability.NOT_APPLICABLE
    result = resolve_campaign_recommendation_action(protected_campaign, suitability, tracking)
    assert result.recommendation_action != RecommendationAction.REDUCE


def test_test_campaign_follows_ordinary_resolution():
    test_campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(test_campaign, review)
    result = resolve_campaign_recommendation_action(test_campaign, suitability, tracking)
    assert result.recommendation_action in {
        RecommendationAction.INCREASE,
        RecommendationAction.MAINTAIN,
        RecommendationAction.REDUCE,
        RecommendationAction.HOLD,
    }


def test_protected_test_campaign_follows_ordinary_upstream_suitability():
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
    suitability, tracking = _build_suitability_and_tracking(protected_test_campaign, review)
    assert suitability.reduce_suitability == Suitability.NOT_APPLICABLE
    result = resolve_campaign_recommendation_action(
        protected_test_campaign, suitability, tracking
    )
    assert result.recommendation_action != RecommendationAction.REDUCE


# ---------------------------------------------------------------------------
# Excluded inputs
# ---------------------------------------------------------------------------


def test_module_does_not_reference_excluded_types():
    import src.recommendation as recommendation_module

    source = inspect.getsource(recommendation_module)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced_names |= {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for forbidden_name in (
        "ReasonCode",
        "CampaignConfidenceClass",
        "Confidence",
        "CampaignPacingClass",
        "PacingStatus",
        "BusinessPriority",
        "CampaignActionAvailability",
        "raw_increase_limit",
        "effective_decrease_limit",
        "Decimal",
    ):
        assert forbidden_name not in referenced_names


def test_module_does_not_import_excluded_types():
    import src.recommendation as recommendation_module

    for forbidden_name in (
        "ReasonCode",
        "CampaignConfidenceClass",
        "Confidence",
        "CampaignPacingClass",
        "PacingStatus",
        "BusinessPriority",
        "CampaignActionAvailability",
    ):
        assert not hasattr(recommendation_module, forbidden_name)


def test_does_not_read_protection_or_test_fields():
    source = inspect.getsource(resolve_campaign_recommendation_action)
    assert "is_protected" not in source
    assert "decrease_blocked" not in source
    assert "is_test_campaign" not in source
    assert "test_budget_floor" not in source


# ---------------------------------------------------------------------------
# No recomputation
# ---------------------------------------------------------------------------


def test_does_not_call_earlier_production_functions():
    source = inspect.getsource(resolve_campaign_recommendation_action)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "assess_campaign_tracking",
        "resolve_campaign_action_suitability",
        "resolve_campaign_action_availability",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "calculate_campaign_metrics",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_effective_decrease_limit",
        "resolve_campaign_protection_constraint",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_authorised_fields_are_exactly_eight():
    source = inspect.getsource(resolve_campaign_recommendation_action)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_names = [arg.arg for arg in func_def.args.args]
    assert param_names == ["campaign", "suitability", "tracking"]

    attrs_by_param: dict[str, set[str]] = {name: set() for name in param_names}
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in attrs_by_param:
                attrs_by_param[node.value.id].add(node.attr)

    assert attrs_by_param["campaign"] == {"campaign_id", "status"}
    assert attrs_by_param["suitability"] == {
        "campaign_id",
        "increase_suitability",
        "maintain_suitability",
        "reduce_suitability",
    }
    assert attrs_by_param["tracking"] == {"campaign_id", "is_assessable"}
    total = sum(len(v) for v in attrs_by_param.values())
    assert total == 8


# ---------------------------------------------------------------------------
# Input contract
# ---------------------------------------------------------------------------


def test_none_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_recommendation_action(None, None, None)  # type: ignore[arg-type]


def test_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_recommendation_action(  # type: ignore[arg-type]
            _campaign(),
            {"campaign_id": "C001", "increase_suitability": Suitability.SUITABLE},
            _tracking(),
        )


def test_no_broad_exception_handling_in_source():
    source = inspect.getsource(resolve_campaign_recommendation_action)
    assert "except" not in source


def test_no_production_batch_function():
    import src.recommendation as recommendation_module

    assert not hasattr(recommendation_module, "resolve_campaign_recommendation_actions")
    assert not hasattr(recommendation_module, "calculate_campaign_recommendations")


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_recommendation_action_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    built = {
        c.campaign_id: (c, *_build_suitability_and_tracking(c, review))
        for c in report.valid_campaigns
    }

    results = {
        campaign_id: resolve_campaign_recommendation_action(campaign, suitability, tracking)
        for campaign_id, (campaign, suitability, tracking) in built.items()
    }
    assert list(results.keys()) == ["G001", "M001", "G002", "G003"]

    assert results["G001"].recommendation_action == RecommendationAction.MAINTAIN
    assert results["M001"].recommendation_action == RecommendationAction.MAINTAIN
    assert results["G002"].recommendation_action == RecommendationAction.INCREASE
    assert results["G003"].recommendation_action == RecommendationAction.MAINTAIN

    # G002 independent verification
    g002_campaign, g002_suitability, g002_tracking = built["G002"]
    assert g002_campaign.status is CampaignStatus.ACTIVE
    assert g002_tracking.is_assessable is True
    assert (
        g002_suitability.increase_suitability,
        g002_suitability.maintain_suitability,
        g002_suitability.reduce_suitability,
    ) == (Suitability.SUITABLE, Suitability.NEUTRAL, Suitability.NOT_APPLICABLE)
    assert results["G002"].recommendation_action == RecommendationAction.INCREASE
    # No monetary amount is calculated - result carries only campaign_id and
    # recommendation_action.
    assert set(CampaignRecommendation.model_fields.keys()) == {
        "campaign_id",
        "recommendation_action",
    }
    # No ReasonCode is produced anywhere on the result.
    assert not hasattr(results["G002"], "reason_code")


# ---------------------------------------------------------------------------
# Synthetic integration cases
# ---------------------------------------------------------------------------


def test_synthetic_paused_campaign_integration():
    paused_campaign = _campaign(status=CampaignStatus.PAUSED)
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(paused_campaign, review)
    result = resolve_campaign_recommendation_action(paused_campaign, suitability, tracking)
    assert result.recommendation_action == RecommendationAction.HOLD


def test_synthetic_unreliable_tracking_campaign_integration():
    unreliable_campaign = _campaign(tracking_status=TrackingStatus.UNRELIABLE)
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(unreliable_campaign, review)
    assert tracking.is_assessable is False
    result = resolve_campaign_recommendation_action(unreliable_campaign, suitability, tracking)
    assert result.recommendation_action == RecommendationAction.HOLD


def test_synthetic_warning_tracking_campaign_integration():
    warning_campaign = _campaign(tracking_status=TrackingStatus.WARNING)
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(warning_campaign, review)
    assert tracking.is_assessable is True
    result = resolve_campaign_recommendation_action(warning_campaign, suitability, tracking)
    assert result.recommendation_action in {
        RecommendationAction.INCREASE,
        RecommendationAction.MAINTAIN,
        RecommendationAction.REDUCE,
        RecommendationAction.HOLD,
    }


def test_synthetic_below_target_declining_reduce_available_integration():
    campaign = _campaign(
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("50.00"),
        kpi_actual_7d=Decimal("100.00"),
        kpi_actual_28d=Decimal("60.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    suitability, tracking = _build_suitability_and_tracking(campaign, review)
    assert suitability.reduce_suitability == Suitability.SUITABLE
    result = resolve_campaign_recommendation_action(campaign, suitability, tracking)
    assert result.recommendation_action == RecommendationAction.REDUCE


def test_synthetic_below_target_declining_reduce_unavailable_integration():
    protected_campaign = _campaign(
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
    suitability, tracking = _build_suitability_and_tracking(protected_campaign, review)
    assert suitability.reduce_suitability == Suitability.NOT_APPLICABLE
    result = resolve_campaign_recommendation_action(protected_campaign, suitability, tracking)
    assert result.recommendation_action != RecommendationAction.REDUCE


def test_synthetic_multiple_suitable_input_integration():
    result = resolve_campaign_recommendation_action(
        _campaign(),
        _suitability(
            increase_suitability=Suitability.SUITABLE,
            maintain_suitability=Suitability.NEUTRAL,
            reduce_suitability=Suitability.SUITABLE,
        ),
        _tracking(),
    )
    assert result.recommendation_action == RecommendationAction.HOLD


def test_synthetic_protected_test_campaign_integration():
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
    suitability, tracking = _build_suitability_and_tracking(protected_test_campaign, review)
    result = resolve_campaign_recommendation_action(
        protected_test_campaign, suitability, tracking
    )
    assert result.recommendation_action != RecommendationAction.REDUCE
