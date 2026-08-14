"""Tests for src.availability (Sprint 1 — Development Stage 19).

Covers CampaignActionAvailability construction/immutability, the exact
increase_available/maintain_available/reduce_available mapping (active status,
tracking assessability, and positive directional monetary capacity), the
campaign-ID mismatch error (across all three non-anchor inputs), Paused-campaign
behaviour (all three False, still one result object, never an error, never HOLD,
never a reason code), unassessable-campaign behaviour (MAINTAIN remains available),
exact Decimal("0.00") boundary behaviour, Decimal-context independence,
independence from CampaignInput fields other than campaign_id/status, from
tracking_status, is_protected, decrease_blocked, is_test_campaign,
test_budget_floor, minimum_budget, maximum_budget, and from every performance/
trend/confidence/pacing/business-priority signal, consumption (not recalculation)
of Stage 8/16/18 facts, and scope boundaries (no hold_available, no eligibility
field, no monetary field, no score/RecommendationAction/ReasonCode/allocation
field, no production batch function).
"""

import ast
import decimal
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
from src.classification import CampaignTrackingAssessment, assess_campaign_tracking
from src.constants import (
    BusinessPriority,
    CampaignStatus,
    KPIType,
    Platform,
    TrackingStatus,
)
from src.constraints import (
    CampaignEffectiveDecreaseLimit,
    CampaignRawIncreaseLimit,
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
from src.models import CampaignInput, ReviewSetup
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


def _tracking(**overrides) -> CampaignTrackingAssessment:
    kwargs = dict(
        campaign_id="C001",
        tracking_status=TrackingStatus.HEALTHY,
        is_assessable=True,
    )
    kwargs.update(overrides)
    return CampaignTrackingAssessment(**kwargs)


def _raw_increase(**overrides) -> CampaignRawIncreaseLimit:
    kwargs = dict(
        campaign_id="C001",
        raw_increase_limit=Decimal("600.00"),
    )
    kwargs.update(overrides)
    return CampaignRawIncreaseLimit(**kwargs)


def _effective_decrease(**overrides) -> CampaignEffectiveDecreaseLimit:
    kwargs = dict(
        campaign_id="C001",
        effective_decrease_limit=Decimal("600.00"),
    )
    kwargs.update(overrides)
    return CampaignEffectiveDecreaseLimit(**kwargs)


def _build_tracking_and_limits(campaign: CampaignInput, review: ReviewSetup):
    """Run the real Stage 8/10-18 production path for one campaign and return
    exactly the three non-CampaignInput objects Stage 19 is approved to accept."""
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
    return tracking, raw_increase, effective_decrease


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_campaign_action_availability_accepts_exactly_four_fields():
    assert set(CampaignActionAvailability.model_fields.keys()) == {
        "campaign_id",
        "increase_available",
        "maintain_available",
        "reduce_available",
    }


def test_campaign_action_availability_field_types():
    result = resolve_campaign_action_availability(
        _campaign(), _tracking(), _raw_increase(), _effective_decrease()
    )
    assert isinstance(result.campaign_id, str)
    assert isinstance(result.increase_available, bool)
    assert isinstance(result.maintain_available, bool)
    assert isinstance(result.reduce_available, bool)


def test_campaign_action_availability_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignActionAvailability(
            campaign_id="C001",
            increase_available=True,
            maintain_available=True,
            reduce_available=True,
            extra_field="not allowed",
        )


def test_campaign_action_availability_is_immutable():
    result = resolve_campaign_action_availability(
        _campaign(), _tracking(), _raw_increase(), _effective_decrease()
    )
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_no_hold_available_field():
    assert "hold_available" not in CampaignActionAvailability.model_fields


def test_no_eligibility_or_other_forbidden_field():
    field_names = set(CampaignActionAvailability.model_fields.keys())
    forbidden = {
        "hold_available",
        "is_eligible",
        "eligible",
        "eligibility",
        "score",
        "recommendation",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
        "raw_increase_limit",
        "effective_decrease_limit",
        "performance_band",
        "trend_direction",
        "confidence",
        "pacing_status",
        "business_priority",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Campaign-ID policy
# ---------------------------------------------------------------------------


def test_all_ids_equal_succeeds():
    result = resolve_campaign_action_availability(
        _campaign(campaign_id="MATCH-1"),
        _tracking(campaign_id="MATCH-1"),
        _raw_increase(campaign_id="MATCH-1"),
        _effective_decrease(campaign_id="MATCH-1"),
    )
    assert result.campaign_id == "MATCH-1"


def test_tracking_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_action_availability(
            _campaign(campaign_id="C001"),
            _tracking(campaign_id="OTHER"),
            _raw_increase(campaign_id="C001"),
            _effective_decrease(campaign_id="C001"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving action availability."
    )


def test_raw_increase_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_action_availability(
            _campaign(campaign_id="C001"),
            _tracking(campaign_id="C001"),
            _raw_increase(campaign_id="OTHER"),
            _effective_decrease(campaign_id="C001"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving action availability."
    )


def test_effective_decrease_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_action_availability(
            _campaign(campaign_id="C001"),
            _tracking(campaign_id="C001"),
            _raw_increase(campaign_id="C001"),
            _effective_decrease(campaign_id="OTHER"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving action availability."
    )


def test_multiple_mismatches_raise_the_same_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_action_availability(
            _campaign(campaign_id="C001"),
            _tracking(campaign_id="A"),
            _raw_increase(campaign_id="B"),
            _effective_decrease(campaign_id="C"),
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving action availability."
    )


def test_id_check_occurs_before_status_assessability_or_decimal_evaluation():
    source = inspect.getsource(resolve_campaign_action_availability)
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
    # Every distinct mismatch combination raises identically - no single input's ID
    # is ever treated as authoritative over another's during the check itself.
    for mismatched_kwargs in (
        dict(tracking=_tracking(campaign_id="X")),
        dict(raw_increase=_raw_increase(campaign_id="X")),
        dict(effective_decrease=_effective_decrease(campaign_id="X")),
    ):
        args = dict(
            campaign=_campaign(campaign_id="C001"),
            tracking=_tracking(campaign_id="C001"),
            raw_increase=_raw_increase(campaign_id="C001"),
            effective_decrease=_effective_decrease(campaign_id="C001"),
        )
        args.update(mismatched_kwargs)
        with pytest.raises(ValueError):
            resolve_campaign_action_availability(**args)


# ---------------------------------------------------------------------------
# Active/assessable cases
# ---------------------------------------------------------------------------


def test_active_assessable_positive_increase_positive_decrease():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.ACTIVE),
        _tracking(is_assessable=True),
        _raw_increase(raw_increase_limit=Decimal("600.00")),
        _effective_decrease(effective_decrease_limit=Decimal("600.00")),
    )
    assert result.increase_available is True
    assert result.maintain_available is True
    assert result.reduce_available is True


def test_active_assessable_zero_increase_positive_decrease():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.ACTIVE),
        _tracking(is_assessable=True),
        _raw_increase(raw_increase_limit=Decimal("0.00")),
        _effective_decrease(effective_decrease_limit=Decimal("600.00")),
    )
    assert result.increase_available is False
    assert result.maintain_available is True
    assert result.reduce_available is True


def test_active_assessable_positive_increase_zero_decrease():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.ACTIVE),
        _tracking(is_assessable=True),
        _raw_increase(raw_increase_limit=Decimal("600.00")),
        _effective_decrease(effective_decrease_limit=Decimal("0.00")),
    )
    assert result.increase_available is True
    assert result.maintain_available is True
    assert result.reduce_available is False


def test_active_assessable_both_zero():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.ACTIVE),
        _tracking(is_assessable=True),
        _raw_increase(raw_increase_limit=Decimal("0.00")),
        _effective_decrease(effective_decrease_limit=Decimal("0.00")),
    )
    assert result.increase_available is False
    assert result.maintain_available is True
    assert result.reduce_available is False


# ---------------------------------------------------------------------------
# Active/unassessable cases
# ---------------------------------------------------------------------------


def test_active_unassessable_both_positive():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.ACTIVE),
        _tracking(is_assessable=False),
        _raw_increase(raw_increase_limit=Decimal("600.00")),
        _effective_decrease(effective_decrease_limit=Decimal("600.00")),
    )
    assert result.increase_available is False
    assert result.maintain_available is True
    assert result.reduce_available is False


@pytest.mark.parametrize(
    "increase_limit, decrease_limit",
    [
        (Decimal("0.00"), Decimal("0.00")),
        (Decimal("0.00"), Decimal("600.00")),
        (Decimal("600.00"), Decimal("0.00")),
        (Decimal("600.00"), Decimal("600.00")),
    ],
)
def test_unassessable_directional_limits_never_override_assessability_gate(
    increase_limit, decrease_limit
):
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.ACTIVE),
        _tracking(is_assessable=False),
        _raw_increase(raw_increase_limit=increase_limit),
        _effective_decrease(effective_decrease_limit=decrease_limit),
    )
    assert result.increase_available is False
    assert result.reduce_available is False
    assert result.maintain_available is True


# ---------------------------------------------------------------------------
# Paused cases
# ---------------------------------------------------------------------------


def test_paused_assessable_positive_limits():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.PAUSED),
        _tracking(is_assessable=True),
        _raw_increase(raw_increase_limit=Decimal("600.00")),
        _effective_decrease(effective_decrease_limit=Decimal("600.00")),
    )
    assert result.increase_available is False
    assert result.maintain_available is False
    assert result.reduce_available is False


def test_paused_unassessable_positive_limits():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.PAUSED),
        _tracking(is_assessable=False),
        _raw_increase(raw_increase_limit=Decimal("600.00")),
        _effective_decrease(effective_decrease_limit=Decimal("600.00")),
    )
    assert result.increase_available is False
    assert result.maintain_available is False
    assert result.reduce_available is False


def test_paused_zero_limits():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.PAUSED),
        _tracking(is_assessable=True),
        _raw_increase(raw_increase_limit=Decimal("0.00")),
        _effective_decrease(effective_decrease_limit=Decimal("0.00")),
    )
    assert result.increase_available is False
    assert result.maintain_available is False
    assert result.reduce_available is False


def test_paused_campaign_always_receives_result_object():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.PAUSED),
        _tracking(),
        _raw_increase(),
        _effective_decrease(),
    )
    assert isinstance(result, CampaignActionAvailability)
    assert result.campaign_id == "C001"


def test_paused_campaign_produces_no_hold_or_reason_code():
    result = resolve_campaign_action_availability(
        _campaign(status=CampaignStatus.PAUSED),
        _tracking(),
        _raw_increase(),
        _effective_decrease(),
    )
    assert not hasattr(result, "hold_available")
    assert not hasattr(result, "reason_code")
    assert not hasattr(result, "recommendation_action")


# ---------------------------------------------------------------------------
# Tracking cases
# ---------------------------------------------------------------------------


def test_healthy_assessable_behaves_according_to_capacity():
    campaign = _campaign(tracking_status=TrackingStatus.HEALTHY)
    tracking = assess_campaign_tracking(campaign)
    assert tracking.is_assessable is True
    result = resolve_campaign_action_availability(
        campaign,
        tracking,
        _raw_increase(raw_increase_limit=Decimal("600.00")),
        _effective_decrease(effective_decrease_limit=Decimal("600.00")),
    )
    assert result.increase_available is True
    assert result.reduce_available is True


def test_warning_assessable_behaves_according_to_capacity():
    campaign = _campaign(tracking_status=TrackingStatus.WARNING)
    tracking = assess_campaign_tracking(campaign)
    assert tracking.is_assessable is True
    result = resolve_campaign_action_availability(
        campaign,
        tracking,
        _raw_increase(raw_increase_limit=Decimal("600.00")),
        _effective_decrease(effective_decrease_limit=Decimal("0.00")),
    )
    assert result.increase_available is True
    assert result.reduce_available is False
    assert result.maintain_available is True


def test_unreliable_unassessable_blocks_both_change_directions():
    campaign = _campaign(tracking_status=TrackingStatus.UNRELIABLE)
    tracking = assess_campaign_tracking(campaign)
    assert tracking.is_assessable is False
    result = resolve_campaign_action_availability(
        campaign,
        tracking,
        _raw_increase(raw_increase_limit=Decimal("600.00")),
        _effective_decrease(effective_decrease_limit=Decimal("600.00")),
    )
    assert result.increase_available is False
    assert result.reduce_available is False
    assert result.maintain_available is True


def test_resolve_campaign_action_availability_reads_only_is_assessable_from_tracking():
    source = inspect.getsource(resolve_campaign_action_availability)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    tracking_param = func_def.args.args[1].arg
    assert tracking_param == "tracking"
    tracking_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == tracking_param:
                tracking_attrs.add(node.attr)
    assert tracking_attrs == {"campaign_id", "is_assessable"}


def test_resolve_campaign_action_availability_does_not_read_tracking_status():
    source = inspect.getsource(resolve_campaign_action_availability)
    assert "tracking_status" not in source
    assert ".tracking_status" not in source


# ---------------------------------------------------------------------------
# Capacity cases
# ---------------------------------------------------------------------------


def test_exact_decimal_zero_makes_increase_unavailable():
    result = resolve_campaign_action_availability(
        _campaign(), _tracking(), _raw_increase(raw_increase_limit=Decimal("0.00")), _effective_decrease()
    )
    assert result.increase_available is False


def test_exact_decimal_zero_makes_decrease_unavailable():
    result = resolve_campaign_action_availability(
        _campaign(), _tracking(), _raw_increase(), _effective_decrease(effective_decrease_limit=Decimal("0.00"))
    )
    assert result.reduce_available is False


def test_positive_minimum_currency_amount_makes_direction_available():
    result = resolve_campaign_action_availability(
        _campaign(),
        _tracking(),
        _raw_increase(raw_increase_limit=Decimal("0.01")),
        _effective_decrease(effective_decrease_limit=Decimal("0.01")),
    )
    assert result.increase_available is True
    assert result.reduce_available is True


def test_extreme_valid_positive_decimal_values_remain_comparable():
    extreme_value = Decimal("9" * 26 + ".99")
    result = resolve_campaign_action_availability(
        _campaign(),
        _tracking(),
        _raw_increase(raw_increase_limit=extreme_value),
        _effective_decrease(effective_decrease_limit=extreme_value),
    )
    assert result.increase_available is True
    assert result.reduce_available is True


def test_no_negative_value_correction_or_clamping_in_source():
    source = inspect.getsource(resolve_campaign_action_availability)
    assert "abs(" not in source
    assert "max(" not in source
    assert "min(" not in source


def test_no_input_monetary_value_modified():
    raw_increase = _raw_increase(raw_increase_limit=Decimal("600.00"))
    effective_decrease = _effective_decrease(effective_decrease_limit=Decimal("600.00"))
    resolve_campaign_action_availability(_campaign(), _tracking(), raw_increase, effective_decrease)
    assert raw_increase.raw_increase_limit == Decimal("600.00")
    assert effective_decrease.effective_decrease_limit == Decimal("600.00")


# ---------------------------------------------------------------------------
# Protected/test cases
# ---------------------------------------------------------------------------


def test_protected_active_campaign_positive_increase_zero_decrease():
    protected_campaign = _campaign(
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=True,
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    tracking, raw_increase, effective_decrease = _build_tracking_and_limits(
        protected_campaign, review
    )
    assert effective_decrease.effective_decrease_limit == Decimal("0.00")
    assert raw_increase.raw_increase_limit > Decimal("0.00")

    result = resolve_campaign_action_availability(
        protected_campaign, tracking, raw_increase, effective_decrease
    )
    assert result.increase_available is True
    assert result.maintain_available is True
    assert result.reduce_available is False


def test_test_campaign_positive_limits_all_true_when_active_and_assessable():
    test_campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    tracking, raw_increase, effective_decrease = _build_tracking_and_limits(
        test_campaign, review
    )
    result = resolve_campaign_action_availability(
        test_campaign, tracking, raw_increase, effective_decrease
    )
    assert result.increase_available is True
    assert result.maintain_available is True
    assert result.reduce_available is True


def test_protected_and_test_synthetic_campaign_follows_already_computed_capacities():
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
    tracking, raw_increase, effective_decrease = _build_tracking_and_limits(
        protected_test_campaign, review
    )
    result = resolve_campaign_action_availability(
        protected_test_campaign, tracking, raw_increase, effective_decrease
    )
    assert result.increase_available == (raw_increase.raw_increase_limit > Decimal("0.00"))
    assert result.reduce_available == (effective_decrease.effective_decrease_limit > Decimal("0.00"))
    assert result.maintain_available is True


def test_does_not_read_protection_or_test_fields():
    source = inspect.getsource(resolve_campaign_action_availability)
    assert "is_protected" not in source
    assert "decrease_blocked" not in source
    assert "is_test_campaign" not in source
    assert "test_budget_floor" not in source


# ---------------------------------------------------------------------------
# Excluded inputs
# ---------------------------------------------------------------------------


def test_independent_of_classification_and_priority_signals():
    source = inspect.getsource(resolve_campaign_action_availability)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    for forbidden_name in (
        "PerformanceBand",
        "TrendDirection",
        "Confidence",
        "PacingStatus",
        "BusinessPriority",
        "RecommendationAction",
        "ReasonCode",
    ):
        assert forbidden_name not in referenced_names


def test_module_does_not_import_classification_or_priority_enums():
    import src.availability as availability_module

    for forbidden_name in (
        "PerformanceBand",
        "TrendDirection",
        "Confidence",
        "PacingStatus",
        "BusinessPriority",
        "RecommendationAction",
        "ReasonCode",
    ):
        assert not hasattr(availability_module, forbidden_name)


# ---------------------------------------------------------------------------
# No earlier-stage recomputation
# ---------------------------------------------------------------------------


def test_does_not_call_earlier_production_functions():
    source = inspect.getsource(resolve_campaign_action_availability)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "assess_campaign_tracking",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_effective_decrease_limit",
        "resolve_campaign_raw_decrease_limit",
        "resolve_campaign_test_aware_static_decrease_room",
        "resolve_campaign_protection_constraint",
        "calculate_campaign_static_budget_room",
        "calculate_campaign_raw_percentage_movement_cap",
        "calculate_campaign_test_floor_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_authorised_fields_are_exactly_eight():
    source = inspect.getsource(resolve_campaign_action_availability)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_names = [arg.arg for arg in func_def.args.args]
    assert param_names == ["campaign", "tracking", "raw_increase", "effective_decrease"]

    attrs_by_param: dict[str, set[str]] = {name: set() for name in param_names}
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in attrs_by_param:
                attrs_by_param[node.value.id].add(node.attr)

    assert attrs_by_param["campaign"] == {"campaign_id", "status"}
    assert attrs_by_param["tracking"] == {"campaign_id", "is_assessable"}
    assert attrs_by_param["raw_increase"] == {"campaign_id", "raw_increase_limit"}
    assert attrs_by_param["effective_decrease"] == {"campaign_id", "effective_decrease_limit"}
    total = sum(len(v) for v in attrs_by_param.values())
    assert total == 8


# ---------------------------------------------------------------------------
# Decimal/context behaviour
# ---------------------------------------------------------------------------


def test_no_float_conversion():
    source = inspect.getsource(resolve_campaign_action_availability)
    assert "float(" not in source


def test_no_arithmetic_binop():
    source = inspect.getsource(resolve_campaign_action_availability)
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BinOp) for node in ast.walk(tree))


def test_no_rounding_or_quantisation():
    source = inspect.getsource(resolve_campaign_action_availability)
    assert "quantize" not in source
    assert "ROUND_HALF_UP" not in source
    assert "CURRENCY_QUANTUM" not in source
    assert "localcontext" not in source


def test_mutated_global_decimal_context_does_not_affect_output():
    campaign = _campaign()
    tracking = _tracking()
    raw_increase = _raw_increase(raw_increase_limit=Decimal("600.00"))
    effective_decrease = _effective_decrease(effective_decrease_limit=Decimal("600.00"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        result = resolve_campaign_action_availability(
            campaign, tracking, raw_increase, effective_decrease
        )
        assert result.increase_available is True
        assert result.reduce_available is True
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_global_decimal_context_restored_after_test():
    campaign = _campaign()
    tracking = _tracking()
    raw_increase = _raw_increase()
    effective_decrease = _effective_decrease()

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        resolve_campaign_action_availability(
            campaign, tracking, raw_increase, effective_decrease
        )
        assert decimal.getcontext().prec == 5
        assert decimal.getcontext().rounding == decimal.ROUND_DOWN
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding
    assert decimal.getcontext().prec == original_prec
    assert decimal.getcontext().rounding == original_rounding


# ---------------------------------------------------------------------------
# Input contract
# ---------------------------------------------------------------------------


def test_none_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_action_availability(None, None, None, None)  # type: ignore[arg-type]


def test_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_action_availability(  # type: ignore[arg-type]
            _campaign(),
            {"campaign_id": "C001", "is_assessable": True},
            _raw_increase(),
            _effective_decrease(),
        )


def test_incompatible_objects_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_action_availability(  # type: ignore[arg-type]
            _campaign(),
            _tracking(),
            {"campaign_id": "C001", "raw_increase_limit": Decimal("600.00")},
            _effective_decrease(),
        )


def test_no_production_batch_function():
    import src.availability as availability_module

    assert not hasattr(availability_module, "resolve_campaign_action_availabilities")
    assert not hasattr(availability_module, "calculate_campaign_action_availabilities")


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_action_availability_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    built = {
        c.campaign_id: (c, *_build_tracking_and_limits(c, review))
        for c in report.valid_campaigns
    }

    results = [
        resolve_campaign_action_availability(campaign, tracking, raw_increase, effective_decrease)
        for campaign, tracking, raw_increase, effective_decrease in built.values()
    ]
    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": (True, True, True),
        "M001": (True, True, True),
        "G002": (True, True, False),
        "G003": (True, True, True),
    }
    for result in results:
        increase, maintain, reduce = expected[result.campaign_id]
        assert result.increase_available == increase
        assert result.maintain_available == maintain
        assert result.reduce_available == reduce

    # G002: independently verify the underlying facts Stage 19 consumed, and
    # confirm no protection field was needed to reach the correct result - the
    # already-protection-adjusted effective_decrease_limit=0.00 is sufficient.
    g002_campaign, g002_tracking, g002_raw_increase, g002_effective_decrease = built["G002"]
    assert g002_campaign.status is CampaignStatus.ACTIVE
    assert g002_tracking.is_assessable is True
    assert g002_raw_increase.raw_increase_limit == Decimal("1000.00")
    assert g002_effective_decrease.effective_decrease_limit == Decimal("0.00")
    # No action is recommended anywhere in this test - only mechanical availability.


def test_synthetic_paused_campaign_integration():
    paused_campaign = _campaign(status=CampaignStatus.PAUSED)
    review = _review(default_max_change_percentage=Decimal("0.20"))
    tracking, raw_increase, effective_decrease = _build_tracking_and_limits(
        paused_campaign, review
    )
    result = resolve_campaign_action_availability(
        paused_campaign, tracking, raw_increase, effective_decrease
    )
    assert result.increase_available is False
    assert result.maintain_available is False
    assert result.reduce_available is False


def test_synthetic_unreliable_tracking_campaign_integration():
    unreliable_campaign = _campaign(tracking_status=TrackingStatus.UNRELIABLE)
    review = _review(default_max_change_percentage=Decimal("0.20"))
    tracking, raw_increase, effective_decrease = _build_tracking_and_limits(
        unreliable_campaign, review
    )
    assert tracking.is_assessable is False
    result = resolve_campaign_action_availability(
        unreliable_campaign, tracking, raw_increase, effective_decrease
    )
    assert result.increase_available is False
    assert result.reduce_available is False
    assert result.maintain_available is True


def test_synthetic_warning_tracking_campaign_integration():
    warning_campaign = _campaign(tracking_status=TrackingStatus.WARNING)
    review = _review(default_max_change_percentage=Decimal("0.20"))
    tracking, raw_increase, effective_decrease = _build_tracking_and_limits(
        warning_campaign, review
    )
    assert tracking.is_assessable is True
    result = resolve_campaign_action_availability(
        warning_campaign, tracking, raw_increase, effective_decrease
    )
    assert result.increase_available == (raw_increase.raw_increase_limit > Decimal("0.00"))
    assert result.reduce_available == (effective_decrease.effective_decrease_limit > Decimal("0.00"))
    assert result.maintain_available is True


def test_synthetic_both_directional_limits_zero_integration():
    zero_campaign = _campaign(
        current_budget=Decimal("500.00"),
        minimum_budget=Decimal("500.00"),
        maximum_budget=Decimal("500.00"),
        spend_to_date=Decimal("0.00"),
    )
    review = _review(default_max_change_percentage=Decimal("0.20"))
    tracking, raw_increase, effective_decrease = _build_tracking_and_limits(
        zero_campaign, review
    )
    assert raw_increase.raw_increase_limit == Decimal("0.00")
    assert effective_decrease.effective_decrease_limit == Decimal("0.00")
    result = resolve_campaign_action_availability(
        zero_campaign, tracking, raw_increase, effective_decrease
    )
    assert result.increase_available is False
    assert result.reduce_available is False
    assert result.maintain_available is True


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
    tracking, raw_increase, effective_decrease = _build_tracking_and_limits(
        protected_test_campaign, review
    )
    assert effective_decrease.effective_decrease_limit == Decimal("0.00")
    result = resolve_campaign_action_availability(
        protected_test_campaign, tracking, raw_increase, effective_decrease
    )
    assert result.increase_available == (raw_increase.raw_increase_limit > Decimal("0.00"))
    assert result.reduce_available is False
    assert result.maintain_available is True
