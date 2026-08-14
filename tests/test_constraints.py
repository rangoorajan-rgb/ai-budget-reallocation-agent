"""Tests for src.constraints (Sprint 1 — Development Stages 10, 11, 12, 13, 14, 15, 16, 17, and 18).

Covers CampaignStaticBudgetRoom construction/immutability, the exact
room_to_static_maximum/room_to_static_minimum formulas, boundary-zero behaviour
(exactly at minimum_budget, exactly at maximum_budget, and minimum_budget ==
current_budget == maximum_budget), zero and large valid Decimal currency values,
Decimal-context independence, integration with validate_campaign_csv over
data/sample_campaigns.csv, and scope boundaries (no percentage-limit, protection,
test-budget-floor, eligibility, score, recommendation, reason-code, allocation, or
Stage 3-9 field or function usage).

Also covers Stage 11's CampaignApplicableChangePercentage construction/immutability,
the exact campaign-override-first/review-default-fallback precedence, explicit
None-check behaviour (not truthiness), Decimal preservation with no arithmetic/
quantisation/rounding, Decimal-context independence, independence from Stage 10's
static budget-bound facts and from every other CampaignInput/ReviewSetup field, and
scope boundaries (no monetary cap, no static-bound intersection, no protection or
test-budget-floor effect, no eligibility/score/recommendation/reason-code/allocation
field).

Also covers Stage 12's CampaignRawPercentageMovementCap construction/immutability, the
exact current_budget * applicable_max_change_percentage formula, campaign_id-mismatch
error behaviour, ROUND_HALF_UP quantisation to CURRENCY_QUANTUM applied exactly once,
the operand-derived local Decimal precision policy (which prevents an intermediate
double-rounding error reachable by an already-valid extreme CampaignInput), Decimal-
context independence, independence from Stage 10's static-room facts and from
protected/test fields, and scope boundaries (no effective movement, static-bound
intersection, eligibility, score, recommendation, reason code, allocation, or
conservation field).

Also covers Stage 13's CampaignTestFloorRoom construction/immutability, the exact
current_budget - test_budget_floor formula for test campaigns, explicit None for
non-test campaigns, zero behaviour, fixed-precision-28 Decimal-context independence,
independence from minimum_budget/maximum_budget/is_protected and from Stage 10-12
results, and scope boundaries (no effective floor, no effective movement, no
eligibility/score/recommendation/reason-code/allocation/conservation field).

Also covers Stage 14's CampaignProtectionConstraint construction/immutability, the
exact decrease_blocked = is_protected mapping, independence from current_budget/
minimum_budget/maximum_budget/is_test_campaign/test_budget_floor/
campaign_max_change_percentage/platform/kpi_type and from Stage 10-13 results, the
absence of any Decimal/monetary output, and scope boundaries (no eligibility, score,
recommendation, reason code, allocation, or conservation field).

Also covers Stage 15's CampaignTestAwareStaticDecreaseRoom construction/immutability,
the exact room_to_static_minimum/min(room_to_static_minimum, room_to_test_floor)
precedence formula, the campaign-ID mismatch error, non-test None-fallback behaviour,
zero behaviour, no-arithmetic Decimal selection (no subtraction, quantisation or
rounding), Decimal-context independence, independence from CampaignInput and from
Stage 11/12/14 results, consumption (not recalculation) of Stage 10/13 facts, and
scope boundaries (no percentage-cap intersection, no protection application, no
effective movement, no eligibility/score/recommendation/reason-code/allocation/
conservation field).

Also covers Stage 16's CampaignRawIncreaseLimit construction/immutability, the exact
min(room_to_static_maximum, raw_percentage_movement_cap) formula, the campaign-ID
mismatch error, zero behaviour, no-arithmetic Decimal selection, Decimal-context
independence, independence from CampaignInput/ReviewSetup and from Stage 11/13/14/15
results, consumption (not recalculation) of Stage 10/12 facts, and scope boundaries
(no raw decrease result, no protection or test-floor effect, no effective increase,
no eligibility/score/recommendation/reason-code/allocation/conservation field).

Also covers Stage 17's CampaignRawDecreaseLimit construction/immutability, the exact
min(test_aware_static_decrease_room, raw_percentage_movement_cap) formula, the
campaign-ID mismatch error, zero behaviour, no-arithmetic Decimal selection,
Decimal-context independence, independence from CampaignInput/ReviewSetup and from
Stage 10/11/13/14/16 results, consumption (not recalculation) of Stage 12/15 facts,
protection independence, test-campaign handling through the Stage 15 result only, and
scope boundaries (no raw increase result, no combined directional model, no effective
decrease, no eligibility/score/recommendation/reason-code/allocation/conservation
field).

Also covers Stage 18's CampaignEffectiveDecreaseLimit construction/immutability, the
exact Decimal("0.00")-if-decrease_blocked-else-raw_decrease_limit mapping, the
campaign-ID mismatch error, the exact two-decimal zero exponent for the protected
branch, unprotected-operand preservation, Decimal-context independence,
independence from CampaignInput/ReviewSetup and from Stage 10-13/15/16 results,
consumption (not recalculation) of Stage 14/17 facts, raw-fact traceability across
the separately-held Stage 14/17/18 result objects, the eligibility boundary (no
eligible/ineligible output), and scope boundaries (no effective increase, no
combined directional model, no eligibility/score/recommendation/reason-code/
allocation/conservation field).
"""

import ast
import decimal
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.constants import (
    BusinessPriority,
    CampaignStatus,
    CURRENCY_QUANTUM,
    KPIType,
    Platform,
    TrackingStatus,
)
from src.constraints import (
    CampaignApplicableChangePercentage,
    CampaignEffectiveDecreaseLimit,
    CampaignProtectionConstraint,
    CampaignRawDecreaseLimit,
    CampaignRawIncreaseLimit,
    CampaignRawPercentageMovementCap,
    CampaignStaticBudgetRoom,
    CampaignTestAwareStaticDecreaseRoom,
    CampaignTestFloorRoom,
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


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_campaign_static_budget_room_accepts_exactly_three_fields():
    assert set(CampaignStaticBudgetRoom.model_fields.keys()) == {
        "campaign_id",
        "room_to_static_maximum",
        "room_to_static_minimum",
    }


def test_campaign_static_budget_room_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignStaticBudgetRoom(
            campaign_id="C001",
            room_to_static_maximum=Decimal("100.00"),
            room_to_static_minimum=Decimal("100.00"),
            extra_field="not allowed",
        )


def test_campaign_static_budget_room_is_immutable():
    result = calculate_campaign_static_budget_room(_campaign())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_campaign_id_copied_exactly():
    result = calculate_campaign_static_budget_room(_campaign(campaign_id="XYZ-1"))
    assert result.campaign_id == "XYZ-1"


def test_result_fields_are_decimal_and_never_float():
    result = calculate_campaign_static_budget_room(_campaign())
    assert isinstance(result.room_to_static_maximum, Decimal)
    assert isinstance(result.room_to_static_minimum, Decimal)
    assert not isinstance(result.room_to_static_maximum, float)
    assert not isinstance(result.room_to_static_minimum, float)


def test_calculate_campaign_static_budget_room_rejects_incompatible_input():
    with pytest.raises(AttributeError):
        calculate_campaign_static_budget_room(None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        calculate_campaign_static_budget_room(  # type: ignore[arg-type]
            {"current_budget": Decimal("1000.00")}
        )


def test_result_has_no_out_of_scope_fields():
    field_names = set(CampaignStaticBudgetRoom.model_fields.keys())
    forbidden = {
        "effective_minimum_budget",
        "effective_maximum_budget",
        "max_increase",
        "max_decrease",
        "increase_limit",
        "decrease_limit",
        "room_to_increase",
        "room_to_decrease",
        "is_protected",
        "is_test_campaign",
        "test_budget_floor",
        "campaign_max_change_percentage",
        "eligibility",
        "blocked",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Exact calculations and boundaries
# ---------------------------------------------------------------------------


def test_campaign_strictly_between_bounds():
    campaign = _campaign(
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
    )
    result = calculate_campaign_static_budget_room(campaign)
    assert result.room_to_static_maximum == Decimal("1000.00")
    assert result.room_to_static_minimum == Decimal("900.00")


def test_campaign_exactly_at_minimum_budget():
    campaign = _campaign(
        current_budget=Decimal("100.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("50.00"),
    )
    result = calculate_campaign_static_budget_room(campaign)
    assert result.room_to_static_minimum == Decimal("0.00")
    assert result.room_to_static_maximum == Decimal("1900.00")


def test_campaign_exactly_at_maximum_budget():
    campaign = _campaign(
        current_budget=Decimal("2000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
    )
    result = calculate_campaign_static_budget_room(campaign)
    assert result.room_to_static_maximum == Decimal("0.00")
    assert result.room_to_static_minimum == Decimal("1900.00")


def test_minimum_equals_current_equals_maximum():
    campaign = _campaign(
        current_budget=Decimal("500.00"),
        minimum_budget=Decimal("500.00"),
        maximum_budget=Decimal("500.00"),
        spend_to_date=Decimal("500.00"),
    )
    result = calculate_campaign_static_budget_room(campaign)
    assert result.room_to_static_maximum == Decimal("0.00")
    assert result.room_to_static_minimum == Decimal("0.00")


def test_zero_valued_bounds():
    campaign = _campaign(
        current_budget=Decimal("0.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("0.00"),
        spend_to_date=Decimal("0.00"),
    )
    result = calculate_campaign_static_budget_room(campaign)
    assert result.room_to_static_maximum == Decimal("0.00")
    assert result.room_to_static_minimum == Decimal("0.00")


def test_large_valid_decimal_currency_values():
    campaign = _campaign(
        current_budget=Decimal("500000000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("1000000000.00"),
        spend_to_date=Decimal("100000000.00"),
    )
    result = calculate_campaign_static_budget_room(campaign)
    assert result.room_to_static_maximum == Decimal("500000000.00")
    assert result.room_to_static_minimum == Decimal("500000000.00")


def test_exact_two_decimal_results():
    campaign = _campaign(
        current_budget=Decimal("1234.56"),
        minimum_budget=Decimal("100.01"),
        maximum_budget=Decimal("2345.67"),
        spend_to_date=Decimal("0.00"),
    )
    result = calculate_campaign_static_budget_room(campaign)
    assert result.room_to_static_maximum == Decimal("1111.11")
    assert result.room_to_static_minimum == Decimal("1134.55")


# ---------------------------------------------------------------------------
# Independence
# ---------------------------------------------------------------------------


def test_function_reads_only_the_four_authorised_fields():
    source = inspect.getsource(calculate_campaign_static_budget_room)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_name = func_def.args.args[0].arg

    accessed_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == param_name:
                accessed_attrs.add(node.attr)

    assert accessed_attrs == {"campaign_id", "current_budget", "minimum_budget", "maximum_budget"}


def test_function_does_not_call_stage_3_to_9_functions():
    source = inspect.getsource(calculate_campaign_static_budget_room)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_module_does_not_import_out_of_scope_modules():
    # NOTE: "ReviewSetup" was removed from this forbidden set for Stage 11, which
    # legitimately requires it as `resolve_campaign_applicable_change_percentage`'s
    # first parameter type (approved narrowing — every other forbidden entry below,
    # including "DEFAULT_MAX_CHANGE_PERCENTAGE", remains enforced unchanged).
    import src.constraints as constraints_module

    tree = ast.parse(inspect.getsource(constraints_module))
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
        "src.pacing",
        "src.scoring",
        "src.allocation",
        "src.conservation",
        "CampaignMetrics",
        "CampaignPacing",
        "PerformanceBand",
        "TrendDirection",
        "Confidence",
        "TrackingStatus",
        "CampaignTrackingAssessment",
        "PacingStatus",
        "RecommendationAction",
        "ReasonCode",
        "DEFAULT_MAX_CHANGE_PERCENTAGE",
    }
    assert imported_names.isdisjoint(forbidden_imports)


def test_platform_does_not_affect_result():
    google = _campaign(campaign_id="G", platform=Platform.GOOGLE_ADS)
    meta = _campaign(campaign_id="M", platform=Platform.META_ADS)
    result_google = calculate_campaign_static_budget_room(google)
    result_meta = calculate_campaign_static_budget_room(meta)
    assert result_google.room_to_static_maximum == result_meta.room_to_static_maximum
    assert result_google.room_to_static_minimum == result_meta.room_to_static_minimum


def test_kpi_type_does_not_affect_result():
    cpa = _campaign(
        campaign_id="C-CPA",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10.00"),
        kpi_actual_7d=Decimal("10.00"),
        kpi_actual_28d=Decimal("10.00"),
    )
    roas = _campaign(
        campaign_id="C-ROAS",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("3.00"),
        kpi_actual_7d=Decimal("3.00"),
        kpi_actual_28d=Decimal("3.00"),
    )
    result_cpa = calculate_campaign_static_budget_room(cpa)
    result_roas = calculate_campaign_static_budget_room(roas)
    assert result_cpa.room_to_static_maximum == result_roas.room_to_static_maximum
    assert result_cpa.room_to_static_minimum == result_roas.room_to_static_minimum


def test_is_protected_does_not_affect_result():
    unprotected = _campaign(campaign_id="C-U", is_protected=False)
    protected = _campaign(campaign_id="C-P", is_protected=True)
    result_unprotected = calculate_campaign_static_budget_room(unprotected)
    result_protected = calculate_campaign_static_budget_room(protected)
    assert result_unprotected.room_to_static_maximum == result_protected.room_to_static_maximum
    assert result_unprotected.room_to_static_minimum == result_protected.room_to_static_minimum


def test_is_test_campaign_and_test_budget_floor_do_not_affect_result():
    non_test = _campaign(
        campaign_id="C-NONTEST",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_test_campaign=False,
        test_budget_floor=None,
    )
    test_campaign = _campaign(
        campaign_id="C-TEST",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    result_non_test = calculate_campaign_static_budget_room(non_test)
    result_test = calculate_campaign_static_budget_room(test_campaign)
    assert result_non_test.room_to_static_maximum == result_test.room_to_static_maximum
    assert result_non_test.room_to_static_minimum == result_test.room_to_static_minimum
    assert result_test.room_to_static_minimum == Decimal("900.00")


def test_campaign_max_change_percentage_does_not_affect_result():
    no_override = _campaign(campaign_id="C-NO-OVR", campaign_max_change_percentage=None)
    with_override = _campaign(campaign_id="C-OVR", campaign_max_change_percentage=Decimal("0.05"))
    result_no_override = calculate_campaign_static_budget_room(no_override)
    result_with_override = calculate_campaign_static_budget_room(with_override)
    assert result_no_override.room_to_static_maximum == result_with_override.room_to_static_maximum
    assert result_no_override.room_to_static_minimum == result_with_override.room_to_static_minimum


def test_no_recommendation_reason_code_eligibility_score_allocation_or_conservation_field():
    result = calculate_campaign_static_budget_room(_campaign())
    for attr in (
        "recommendation_action",
        "reason_code",
        "eligibility",
        "score",
        "allocation",
        "conservation",
        "blocked",
        "effective_minimum_budget",
        "effective_maximum_budget",
    ):
        assert not hasattr(result, attr)


def test_mutated_global_decimal_context_does_not_affect_outcome():
    campaign = _campaign(
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
    )

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        result = calculate_campaign_static_budget_room(campaign)
        assert result.room_to_static_maximum == Decimal("1000.00")
        assert result.room_to_static_minimum == Decimal("900.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_static_budget_room_exact_values_and_order():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    results = [calculate_campaign_static_budget_room(c) for c in report.valid_campaigns]
    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": (Decimal("3000.00"), Decimal("2500.00")),
        "M001": (Decimal("2500.00"), Decimal("2000.00")),
        "G002": (Decimal("3000.00"), Decimal("4000.00")),
        "G003": (Decimal("800.00"), Decimal("1100.00")),
    }
    for result in results:
        exp_max, exp_min = expected[result.campaign_id]
        assert result.room_to_static_maximum == exp_max
        assert result.room_to_static_minimum == exp_min

    # G002 is protected (is_protected=True in the source data) — confirm the static
    # facts are unaffected: no different formula, no blocking, no eligibility field.
    g002 = next(c for c in report.valid_campaigns if c.campaign_id == "G002")
    assert g002.is_protected is True

    # G003 is a test campaign with test_budget_floor=300.00 — confirm
    # room_to_static_minimum (1100.00, against minimum_budget=100.00) is unaffected by
    # test_budget_floor and is NOT a claim that reducing by 1100.00 is permissible; the
    # effective decrease limit (which must respect test_budget_floor=300.00) remains a
    # pending, later-stage decision.
    g003 = next(c for c in report.valid_campaigns if c.campaign_id == "G003")
    assert g003.is_test_campaign is True
    assert g003.test_budget_floor == Decimal("300.00")


# ---------------------------------------------------------------------------
# Stage 11 — CampaignApplicableChangePercentage result model
# ---------------------------------------------------------------------------


def test_campaign_applicable_change_percentage_accepts_exactly_two_fields():
    assert set(CampaignApplicableChangePercentage.model_fields.keys()) == {
        "campaign_id",
        "applicable_max_change_percentage",
    }


def test_campaign_applicable_change_percentage_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignApplicableChangePercentage(
            campaign_id="C001",
            applicable_max_change_percentage=Decimal("0.20"),
            extra_field="not allowed",
        )


def test_campaign_applicable_change_percentage_is_immutable():
    result = resolve_campaign_applicable_change_percentage(_review(), _campaign())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_applicable_change_percentage_campaign_id_copied_exactly():
    result = resolve_campaign_applicable_change_percentage(
        _review(), _campaign(campaign_id="XYZ-1")
    )
    assert result.campaign_id == "XYZ-1"


def test_applicable_change_percentage_is_decimal_never_float_never_none():
    result = resolve_campaign_applicable_change_percentage(_review(), _campaign())
    assert isinstance(result.applicable_max_change_percentage, Decimal)
    assert not isinstance(result.applicable_max_change_percentage, float)
    assert result.applicable_max_change_percentage is not None


def test_resolve_campaign_applicable_change_percentage_rejects_incompatible_input():
    with pytest.raises(AttributeError):
        resolve_campaign_applicable_change_percentage(None, None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        resolve_campaign_applicable_change_percentage(  # type: ignore[arg-type]
            _review(), {"campaign_max_change_percentage": Decimal("0.20")}
        )
    with pytest.raises(AttributeError):
        resolve_campaign_applicable_change_percentage(  # type: ignore[arg-type]
            {"default_max_change_percentage": Decimal("0.20")}, _campaign()
        )


def test_applicable_change_percentage_has_no_out_of_scope_fields():
    field_names = set(CampaignApplicableChangePercentage.model_fields.keys())
    forbidden = {
        "room_to_static_maximum",
        "room_to_static_minimum",
        "monetary_cap",
        "max_change_amount",
        "effective_minimum_budget",
        "effective_maximum_budget",
        "is_protected",
        "is_test_campaign",
        "test_budget_floor",
        "eligibility",
        "blocked",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Stage 11 — exact resolution and precedence
# ---------------------------------------------------------------------------


def test_no_campaign_override_uses_review_default():
    review = _review(default_max_change_percentage=Decimal("0.35"))
    campaign = _campaign(campaign_max_change_percentage=None)
    result = resolve_campaign_applicable_change_percentage(review, campaign)
    assert result.applicable_max_change_percentage == Decimal("0.35")


def test_campaign_override_present_wins_over_review_default():
    review = _review(default_max_change_percentage=Decimal("0.35"))
    campaign = _campaign(campaign_max_change_percentage=Decimal("0.05"))
    result = resolve_campaign_applicable_change_percentage(review, campaign)
    assert result.applicable_max_change_percentage == Decimal("0.05")


def test_campaign_override_of_one_is_accepted_and_selected():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    campaign = _campaign(campaign_max_change_percentage=Decimal("1"))
    result = resolve_campaign_applicable_change_percentage(review, campaign)
    assert result.applicable_max_change_percentage == Decimal("1")


def test_small_valid_positive_override_preserved_exactly():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    campaign = _campaign(campaign_max_change_percentage=Decimal("0.0001"))
    result = resolve_campaign_applicable_change_percentage(review, campaign)
    assert result.applicable_max_change_percentage == Decimal("0.0001")


def test_resolution_uses_explicit_none_check_not_truthiness():
    source = inspect.getsource(resolve_campaign_applicable_change_percentage)
    tree = ast.parse(source)

    assert not any(isinstance(node, ast.BoolOp) for node in ast.walk(tree))

    has_is_not_none_check = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            ops = node.ops
            comparators = node.comparators
            if len(ops) == 1 and isinstance(ops[0], (ast.Is, ast.IsNot)):
                if isinstance(comparators[0], ast.Constant) and comparators[0].value is None:
                    has_is_not_none_check = True
    assert has_is_not_none_check


def test_no_arithmetic_quantisation_or_rounding_in_resolution():
    source = inspect.getsource(resolve_campaign_applicable_change_percentage)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        assert not isinstance(node, ast.BinOp)
    assert "quantize" not in source
    assert "ROUND_" not in source


# ---------------------------------------------------------------------------
# Stage 11 — independence
# ---------------------------------------------------------------------------


def test_applicable_change_percentage_function_reads_only_three_authorised_fields():
    source = inspect.getsource(resolve_campaign_applicable_change_percentage)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    review_param, campaign_param = (arg.arg for arg in func_def.args.args)

    review_attrs: set[str] = set()
    campaign_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == review_param:
                review_attrs.add(node.attr)
            elif node.value.id == campaign_param:
                campaign_attrs.add(node.attr)

    assert review_attrs == {"default_max_change_percentage"}
    assert campaign_attrs == {"campaign_id", "campaign_max_change_percentage"}


def test_applicable_change_percentage_does_not_call_stage_10_or_stage_3_to_9_functions():
    source = inspect.getsource(resolve_campaign_applicable_change_percentage)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "calculate_campaign_static_budget_room",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_mutated_global_decimal_context_does_not_affect_applicable_percentage():
    review = _review(default_max_change_percentage=Decimal("0.35"))
    campaign_with_override = _campaign(campaign_max_change_percentage=Decimal("0.05"))
    campaign_without_override = _campaign(campaign_max_change_percentage=None)

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        result = resolve_campaign_applicable_change_percentage(review, campaign_with_override)
        assert result.applicable_max_change_percentage == Decimal("0.05")

        no_override_result = resolve_campaign_applicable_change_percentage(
            review, campaign_without_override
        )
        assert no_override_result.applicable_max_change_percentage == Decimal("0.35")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_platform_does_not_affect_applicable_change_percentage():
    review = _review()
    google = _campaign(campaign_id="G", platform=Platform.GOOGLE_ADS, campaign_max_change_percentage=None)
    meta = _campaign(campaign_id="M", platform=Platform.META_ADS, campaign_max_change_percentage=None)
    result_google = resolve_campaign_applicable_change_percentage(review, google)
    result_meta = resolve_campaign_applicable_change_percentage(review, meta)
    assert (
        result_google.applicable_max_change_percentage
        == result_meta.applicable_max_change_percentage
    )


def test_kpi_type_does_not_affect_applicable_change_percentage():
    review = _review()
    cpa = _campaign(
        campaign_id="C-CPA",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10.00"),
        kpi_actual_7d=Decimal("10.00"),
        kpi_actual_28d=Decimal("10.00"),
        campaign_max_change_percentage=None,
    )
    roas = _campaign(
        campaign_id="C-ROAS",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("3.00"),
        kpi_actual_7d=Decimal("3.00"),
        kpi_actual_28d=Decimal("3.00"),
        campaign_max_change_percentage=None,
    )
    result_cpa = resolve_campaign_applicable_change_percentage(review, cpa)
    result_roas = resolve_campaign_applicable_change_percentage(review, roas)
    assert (
        result_cpa.applicable_max_change_percentage
        == result_roas.applicable_max_change_percentage
    )


def test_budget_fields_do_not_affect_applicable_change_percentage():
    review = _review()
    small_budget = _campaign(
        campaign_id="C-SMALL",
        current_budget=Decimal("10.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("20.00"),
        spend_to_date=Decimal("0.00"),
        campaign_max_change_percentage=None,
    )
    large_budget = _campaign(
        campaign_id="C-LARGE",
        current_budget=Decimal("500000000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("1000000000.00"),
        spend_to_date=Decimal("0.00"),
        campaign_max_change_percentage=None,
    )
    result_small = resolve_campaign_applicable_change_percentage(review, small_budget)
    result_large = resolve_campaign_applicable_change_percentage(review, large_budget)
    assert (
        result_small.applicable_max_change_percentage
        == result_large.applicable_max_change_percentage
    )


def test_stage_10_static_room_neither_read_nor_called():
    review = _review()
    campaign = _campaign()
    # Confirms both functions can run independently on the same campaign without
    # either affecting the other's result — no combined model, no shared state.
    room = calculate_campaign_static_budget_room(campaign)
    percentage = resolve_campaign_applicable_change_percentage(review, campaign)
    assert isinstance(room, CampaignStaticBudgetRoom)
    assert isinstance(percentage, CampaignApplicableChangePercentage)
    assert not hasattr(percentage, "room_to_static_maximum")
    assert not hasattr(percentage, "room_to_static_minimum")


def test_is_protected_does_not_affect_applicable_change_percentage():
    review = _review()
    unprotected = _campaign(campaign_id="C-U", is_protected=False, campaign_max_change_percentage=None)
    protected = _campaign(campaign_id="C-P", is_protected=True, campaign_max_change_percentage=None)
    result_unprotected = resolve_campaign_applicable_change_percentage(review, unprotected)
    result_protected = resolve_campaign_applicable_change_percentage(review, protected)
    assert (
        result_unprotected.applicable_max_change_percentage
        == result_protected.applicable_max_change_percentage
    )


def test_is_test_campaign_and_test_budget_floor_do_not_affect_applicable_change_percentage():
    review = _review()
    non_test = _campaign(
        campaign_id="C-NONTEST",
        is_test_campaign=False,
        test_budget_floor=None,
        campaign_max_change_percentage=None,
    )
    test_campaign = _campaign(
        campaign_id="C-TEST",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
        campaign_max_change_percentage=None,
    )
    result_non_test = resolve_campaign_applicable_change_percentage(review, non_test)
    result_test = resolve_campaign_applicable_change_percentage(review, test_campaign)
    assert (
        result_non_test.applicable_max_change_percentage
        == result_test.applicable_max_change_percentage
    )


def test_no_score_recommendation_reason_code_eligibility_or_allocation_output():
    result = resolve_campaign_applicable_change_percentage(_review(), _campaign())
    for attr in (
        "recommendation_action",
        "reason_code",
        "eligibility",
        "score",
        "allocation",
        "conservation",
        "blocked",
        "monetary_cap",
    ):
        assert not hasattr(result, attr)


# ---------------------------------------------------------------------------
# Stage 11 — sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_applicable_change_percentage_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    results = [
        resolve_campaign_applicable_change_percentage(review, c)
        for c in report.valid_campaigns
    ]
    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected_overrides = {
        "G001": None,
        "M001": Decimal("0.15"),
        "G002": None,
        "G003": None,
    }
    expected_applicable = {
        "G001": Decimal("0.20"),
        "M001": Decimal("0.15"),
        "G002": Decimal("0.20"),
        "G003": Decimal("0.20"),
    }
    for campaign in report.valid_campaigns:
        assert campaign.campaign_max_change_percentage == expected_overrides[campaign.campaign_id]
    for result in results:
        assert result.applicable_max_change_percentage == expected_applicable[result.campaign_id]


# ---------------------------------------------------------------------------
# Stage 12 — CampaignRawPercentageMovementCap result model
# ---------------------------------------------------------------------------


def _applicable_percentage(**overrides) -> CampaignApplicableChangePercentage:
    kwargs = dict(
        campaign_id="C001",
        applicable_max_change_percentage=Decimal("0.20"),
    )
    kwargs.update(overrides)
    return CampaignApplicableChangePercentage(**kwargs)


def test_campaign_raw_percentage_movement_cap_accepts_exactly_two_fields():
    assert set(CampaignRawPercentageMovementCap.model_fields.keys()) == {
        "campaign_id",
        "raw_percentage_movement_cap",
    }


def test_campaign_raw_percentage_movement_cap_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignRawPercentageMovementCap(
            campaign_id="C001",
            raw_percentage_movement_cap=Decimal("600.00"),
            extra_field="not allowed",
        )


def test_campaign_raw_percentage_movement_cap_is_immutable():
    result = calculate_campaign_raw_percentage_movement_cap(
        _campaign(), _applicable_percentage()
    )
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_raw_movement_cap_campaign_id_copied_exactly_from_campaign_input():
    result = calculate_campaign_raw_percentage_movement_cap(
        _campaign(campaign_id="XYZ-1"), _applicable_percentage(campaign_id="XYZ-1")
    )
    assert result.campaign_id == "XYZ-1"


def test_raw_movement_cap_is_decimal_never_float_never_none_and_two_decimal_places():
    result = calculate_campaign_raw_percentage_movement_cap(
        _campaign(), _applicable_percentage()
    )
    assert isinstance(result.raw_percentage_movement_cap, Decimal)
    assert not isinstance(result.raw_percentage_movement_cap, float)
    assert result.raw_percentage_movement_cap is not None
    assert result.raw_percentage_movement_cap == result.raw_percentage_movement_cap.quantize(
        CURRENCY_QUANTUM
    )
    assert result.raw_percentage_movement_cap.as_tuple().exponent == -2


def test_calculate_campaign_raw_percentage_movement_cap_rejects_incompatible_input():
    with pytest.raises(AttributeError):
        calculate_campaign_raw_percentage_movement_cap(None, None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        calculate_campaign_raw_percentage_movement_cap(  # type: ignore[arg-type]
            _campaign(), {"applicable_max_change_percentage": Decimal("0.20")}
        )
    with pytest.raises(AttributeError):
        calculate_campaign_raw_percentage_movement_cap(  # type: ignore[arg-type]
            {"current_budget": Decimal("1000.00")}, _applicable_percentage()
        )


def test_raw_movement_cap_has_no_out_of_scope_fields():
    field_names = set(CampaignRawPercentageMovementCap.model_fields.keys())
    forbidden = {
        "room_to_static_maximum",
        "room_to_static_minimum",
        "effective_minimum_budget",
        "effective_maximum_budget",
        "permissible_movement",
        "is_protected",
        "is_test_campaign",
        "test_budget_floor",
        "eligibility",
        "blocked",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Stage 12 — exact calculation
# ---------------------------------------------------------------------------


def test_exact_whole_penny_multiplication():
    campaign = _campaign(
        current_budget=Decimal("3000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("6000.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("0.20"))
    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    assert result.raw_percentage_movement_cap == Decimal("600.00")


def test_fractional_penny_rounds_up_under_round_half_up():
    # 333.33 * 0.20 = 66.666 -> discarded portion (.006 relative to 66.66) exceeds
    # half a cent, so this rounds up regardless of tie-breaking rule.
    campaign = _campaign(
        current_budget=Decimal("333.33"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("0.20"))
    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    assert result.raw_percentage_movement_cap == Decimal("66.67")


def test_value_below_half_penny_rounds_down():
    # 1.00 * 0.004 = 0.004 -> exactly below half a cent, rounds down to 0.00.
    campaign = _campaign(
        current_budget=Decimal("1.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("1.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("0.004"))
    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    assert result.raw_percentage_movement_cap == Decimal("0.00")


def test_exact_half_penny_rounds_up_under_round_half_up():
    # 1.00 * 0.005 = 0.005 -> an exact tie at the half-cent boundary, ROUND_HALF_UP
    # rounds away from zero to 0.01.
    campaign = _campaign(
        current_budget=Decimal("1.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("1.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("0.005"))
    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    assert result.raw_percentage_movement_cap == Decimal("0.01")


def test_percentage_of_one_returns_current_budget_exactly():
    campaign = _campaign(
        current_budget=Decimal("3000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("6000.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("1"))
    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    assert result.raw_percentage_movement_cap == Decimal("3000.00")


def test_small_positive_percentage_handled_and_quantised_correctly():
    # 12345.00 * 0.0001 = 1.2345 -> third decimal digit is 4, rounds down to 1.23.
    campaign = _campaign(
        current_budget=Decimal("12345.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("20000.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("0.0001"))
    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    assert result.raw_percentage_movement_cap == Decimal("1.23")


def test_zero_current_budget_returns_zero():
    campaign = _campaign(
        current_budget=Decimal("0.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("0.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("0.20"))
    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    assert result.raw_percentage_movement_cap == Decimal("0.00")


def test_no_float_conversion_in_calculation():
    source = inspect.getsource(calculate_campaign_raw_percentage_movement_cap)
    assert "float(" not in source


def test_quantize_is_called_exactly_once():
    source = inspect.getsource(calculate_campaign_raw_percentage_movement_cap)
    tree = ast.parse(source)
    quantize_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "quantize"
    ]
    assert len(quantize_calls) == 1


# ---------------------------------------------------------------------------
# Stage 12 — campaign-ID validation
# ---------------------------------------------------------------------------


def test_matching_campaign_ids_calculate_normally():
    result = calculate_campaign_raw_percentage_movement_cap(
        _campaign(campaign_id="MATCH-1"), _applicable_percentage(campaign_id="MATCH-1")
    )
    assert result.campaign_id == "MATCH-1"


def test_mismatched_campaign_ids_raise_value_error_with_exact_message():
    with pytest.raises(ValueError) as exc_info:
        calculate_campaign_raw_percentage_movement_cap(
            _campaign(campaign_id="A"), _applicable_percentage(campaign_id="B")
        )
    assert str(exc_info.value) == "campaign_id mismatch between campaign and applicable percentage"


def test_no_result_returned_for_mismatched_campaign_ids():
    try:
        calculate_campaign_raw_percentage_movement_cap(
            _campaign(campaign_id="A"), _applicable_percentage(campaign_id="B")
        )
        assert False, "expected ValueError, no result should be returned"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Stage 12 — Decimal context and the operand-derived precision policy
# ---------------------------------------------------------------------------


def test_mutated_global_decimal_context_does_not_affect_raw_movement_cap():
    campaign = _campaign(
        current_budget=Decimal("3000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("6000.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("0.20"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
        assert result.raw_percentage_movement_cap == Decimal("600.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_global_decimal_context_unchanged_after_function_returns():
    campaign = _campaign(
        current_budget=Decimal("3000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("6000.00"),
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(applicable_max_change_percentage=Decimal("0.20"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        calculate_campaign_raw_percentage_movement_cap(campaign, percentage)

        assert decimal.getcontext().prec == 5
        assert decimal.getcontext().rounding == decimal.ROUND_DOWN
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_extreme_operand_derived_precision_regression():
    """Regression test for the double-rounding bug found during the Stage 12
    inspection: an already-valid CampaignInput's current_budget can hold up to 28
    significant digits, and applicable_max_change_percentage has no digit-count
    restriction. Under a naive fixed local precision of 28, the intermediate
    multiplication is rounded before the explicit final quantisation ever runs,
    incorrectly returning Decimal("...52910.71"). The operand-derived precision policy
    (max(28, operand_digits + 4)) computes the multiplication exactly, correctly
    returning Decimal("...52910.70").
    """
    extreme_current_budget = Decimal("9" * 26 + ".99")
    extreme_percentage = Decimal("0.036020245307579938554529107051")

    # Confirm the operand-derived policy is actually exercised here (not merely
    # falling back to the max(28, ...) floor).
    operand_digits = len(extreme_current_budget.as_tuple().digits) + len(
        extreme_percentage.as_tuple().digits
    )
    assert operand_digits + 4 > 28

    campaign = _campaign(
        campaign_id="EXTREME-1",
        current_budget=extreme_current_budget,
        minimum_budget=Decimal("0.00"),
        maximum_budget=extreme_current_budget,
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(
        campaign_id="EXTREME-1",
        applicable_max_change_percentage=extreme_percentage,
    )

    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)

    assert result.raw_percentage_movement_cap == Decimal("3602024530757993855452910.70")
    assert result.raw_percentage_movement_cap != Decimal("3602024530757993855452910.71")


def test_extreme_operand_derived_precision_regression_under_altered_global_context():
    extreme_current_budget = Decimal("9" * 26 + ".99")
    extreme_percentage = Decimal("0.036020245307579938554529107051")

    campaign = _campaign(
        campaign_id="EXTREME-1",
        current_budget=extreme_current_budget,
        minimum_budget=Decimal("0.00"),
        maximum_budget=extreme_current_budget,
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(
        campaign_id="EXTREME-1",
        applicable_max_change_percentage=extreme_percentage,
    )

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
        assert result.raw_percentage_movement_cap == Decimal("3602024530757993855452910.70")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_extreme_value_preserves_significant_whole_number_digits():
    extreme_current_budget = Decimal("9" * 26 + ".99")
    campaign = _campaign(
        campaign_id="EXTREME-2",
        current_budget=extreme_current_budget,
        minimum_budget=Decimal("0.00"),
        maximum_budget=extreme_current_budget,
        spend_to_date=Decimal("0.00"),
    )
    percentage = _applicable_percentage(
        campaign_id="EXTREME-2",
        applicable_max_change_percentage=Decimal("1"),
    )
    result = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    # 100% of the extreme budget must equal the extreme budget exactly - no
    # whole-number digit may be silently rounded or dropped.
    assert result.raw_percentage_movement_cap == extreme_current_budget


# ---------------------------------------------------------------------------
# Stage 12 — independence
# ---------------------------------------------------------------------------


def test_raw_movement_cap_function_reads_only_four_authorised_fields():
    source = inspect.getsource(calculate_campaign_raw_percentage_movement_cap)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    campaign_param, applicable_percentage_param = (arg.arg for arg in func_def.args.args)
    assert campaign_param == "campaign"
    assert applicable_percentage_param == "applicable_percentage"

    campaign_attrs: set[str] = set()
    percentage_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == campaign_param:
                campaign_attrs.add(node.attr)
            elif node.value.id == applicable_percentage_param:
                percentage_attrs.add(node.attr)

    assert campaign_attrs == {"campaign_id", "current_budget"}
    assert percentage_attrs == {"campaign_id", "applicable_max_change_percentage"}


def test_raw_movement_cap_does_not_reference_review_setup():
    source = inspect.getsource(calculate_campaign_raw_percentage_movement_cap)
    tree = ast.parse(source)
    referenced_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert "ReviewSetup" not in referenced_names
    assert "review" not in referenced_names


def test_raw_movement_cap_does_not_call_stage_10_11_or_stage_3_to_9_functions():
    source = inspect.getsource(calculate_campaign_raw_percentage_movement_cap)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "calculate_campaign_static_budget_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_platform_does_not_affect_raw_movement_cap():
    percentage = _applicable_percentage()
    google = _campaign(campaign_id="C001", platform=Platform.GOOGLE_ADS)
    meta = _campaign(campaign_id="C001", platform=Platform.META_ADS)
    result_google = calculate_campaign_raw_percentage_movement_cap(google, percentage)
    result_meta = calculate_campaign_raw_percentage_movement_cap(meta, percentage)
    assert result_google.raw_percentage_movement_cap == result_meta.raw_percentage_movement_cap


def test_kpi_type_does_not_affect_raw_movement_cap():
    percentage = _applicable_percentage()
    cpa = _campaign(
        campaign_id="C001",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10.00"),
        kpi_actual_7d=Decimal("10.00"),
        kpi_actual_28d=Decimal("10.00"),
    )
    roas = _campaign(
        campaign_id="C001",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("3.00"),
        kpi_actual_7d=Decimal("3.00"),
        kpi_actual_28d=Decimal("3.00"),
    )
    result_cpa = calculate_campaign_raw_percentage_movement_cap(cpa, percentage)
    result_roas = calculate_campaign_raw_percentage_movement_cap(roas, percentage)
    assert result_cpa.raw_percentage_movement_cap == result_roas.raw_percentage_movement_cap


def test_minimum_and_maximum_budget_do_not_affect_raw_movement_cap():
    percentage = _applicable_percentage()
    narrow_bounds = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("999.00"),
        maximum_budget=Decimal("1001.00"),
        spend_to_date=Decimal("0.00"),
    )
    wide_bounds = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("1000000.00"),
        spend_to_date=Decimal("0.00"),
    )
    result_narrow = calculate_campaign_raw_percentage_movement_cap(narrow_bounds, percentage)
    result_wide = calculate_campaign_raw_percentage_movement_cap(wide_bounds, percentage)
    assert result_narrow.raw_percentage_movement_cap == result_wide.raw_percentage_movement_cap


def test_stage_10_results_neither_read_nor_called_for_raw_movement_cap():
    campaign = _campaign()
    percentage = _applicable_percentage()
    room = calculate_campaign_static_budget_room(campaign)
    cap = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    assert isinstance(room, CampaignStaticBudgetRoom)
    assert isinstance(cap, CampaignRawPercentageMovementCap)
    assert not hasattr(cap, "room_to_static_maximum")
    assert not hasattr(cap, "room_to_static_minimum")


def test_is_protected_does_not_affect_raw_movement_cap():
    percentage = _applicable_percentage()
    unprotected = _campaign(campaign_id="C001", is_protected=False)
    protected = _campaign(campaign_id="C001", is_protected=True)
    result_unprotected = calculate_campaign_raw_percentage_movement_cap(unprotected, percentage)
    result_protected = calculate_campaign_raw_percentage_movement_cap(protected, percentage)
    assert (
        result_unprotected.raw_percentage_movement_cap
        == result_protected.raw_percentage_movement_cap
    )


def test_is_test_campaign_and_test_budget_floor_do_not_affect_raw_movement_cap():
    percentage = _applicable_percentage()
    non_test = _campaign(
        campaign_id="C001",
        is_test_campaign=False,
        test_budget_floor=None,
    )
    test_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    result_non_test = calculate_campaign_raw_percentage_movement_cap(non_test, percentage)
    result_test = calculate_campaign_raw_percentage_movement_cap(test_campaign, percentage)
    assert (
        result_non_test.raw_percentage_movement_cap == result_test.raw_percentage_movement_cap
    )


def test_no_effective_movement_eligibility_score_recommendation_reason_code_allocation_or_conservation():
    result = calculate_campaign_raw_percentage_movement_cap(_campaign(), _applicable_percentage())
    for attr in (
        "effective_movement",
        "permissible_movement",
        "eligibility",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
        "blocked",
    ):
        assert not hasattr(result, attr)


# ---------------------------------------------------------------------------
# Stage 12 — sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_raw_percentage_movement_cap_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    percentages = [
        resolve_campaign_applicable_change_percentage(review, c)
        for c in report.valid_campaigns
    ]
    caps = [
        calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
        for campaign, percentage in zip(report.valid_campaigns, percentages)
    ]
    assert [c.campaign_id for c in caps] == ["G001", "M001", "G002", "G003"]

    expected_current_budget = {
        "G001": Decimal("3000.00"),
        "M001": Decimal("2500.00"),
        "G002": Decimal("5000.00"),
        "G003": Decimal("1200.00"),
    }
    expected_applicable_percentage = {
        "G001": Decimal("0.20"),
        "M001": Decimal("0.15"),
        "G002": Decimal("0.20"),
        "G003": Decimal("0.20"),
    }
    expected_raw_cap = {
        "G001": Decimal("600.00"),
        "M001": Decimal("375.00"),
        "G002": Decimal("1000.00"),
        "G003": Decimal("240.00"),
    }
    for campaign in report.valid_campaigns:
        assert campaign.current_budget == expected_current_budget[campaign.campaign_id]
    for percentage in percentages:
        assert (
            percentage.applicable_max_change_percentage
            == expected_applicable_percentage[percentage.campaign_id]
        )
    for cap in caps:
        assert cap.raw_percentage_movement_cap == expected_raw_cap[cap.campaign_id]

    # Retain and independently verify Stage 10's static-room results, kept fully
    # separate from Stage 11/12 — never intersected, never combined into one object.
    room_results = [calculate_campaign_static_budget_room(c) for c in report.valid_campaigns]
    expected_room = {
        "G001": (Decimal("3000.00"), Decimal("2500.00")),
        "M001": (Decimal("2500.00"), Decimal("2000.00")),
        "G002": (Decimal("3000.00"), Decimal("4000.00")),
        "G003": (Decimal("800.00"), Decimal("1100.00")),
    }
    for room in room_results:
        exp_max, exp_min = expected_room[room.campaign_id]
        assert room.room_to_static_maximum == exp_max
        assert room.room_to_static_minimum == exp_min

    # None of Stage 12's raw caps is a permissible movement amount - they are
    # informational only, kept conceptually separate from Stage 10's static room.

    # Retain and verify Stage 10's existing static-room results via separate calls —
    # the two stages are never combined into one model or one call.
    room_results = [calculate_campaign_static_budget_room(c) for c in report.valid_campaigns]
    expected_room = {
        "G001": (Decimal("3000.00"), Decimal("2500.00")),
        "M001": (Decimal("2500.00"), Decimal("2000.00")),
        "G002": (Decimal("3000.00"), Decimal("4000.00")),
        "G003": (Decimal("800.00"), Decimal("1100.00")),
    }
    for room in room_results:
        exp_max, exp_min = expected_room[room.campaign_id]
        assert room.room_to_static_maximum == exp_max
        assert room.room_to_static_minimum == exp_min


# ---------------------------------------------------------------------------
# Stage 13 — CampaignTestFloorRoom result model
# ---------------------------------------------------------------------------


def test_campaign_test_floor_room_accepts_exactly_two_fields():
    assert set(CampaignTestFloorRoom.model_fields.keys()) == {
        "campaign_id",
        "room_to_test_floor",
    }


def test_campaign_test_floor_room_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignTestFloorRoom(
            campaign_id="C001",
            room_to_test_floor=Decimal("900.00"),
            extra_field="not allowed",
        )


def test_campaign_test_floor_room_is_immutable():
    result = calculate_campaign_test_floor_room(
        _campaign(
            is_test_campaign=True,
            test_budget_floor=Decimal("300.00"),
        )
    )
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_test_floor_room_campaign_id_copied_exactly():
    result = calculate_campaign_test_floor_room(
        _campaign(
            campaign_id="XYZ-1",
            is_test_campaign=True,
            test_budget_floor=Decimal("300.00"),
        )
    )
    assert result.campaign_id == "XYZ-1"


def test_test_campaign_result_is_decimal_never_float():
    result = calculate_campaign_test_floor_room(
        _campaign(is_test_campaign=True, test_budget_floor=Decimal("300.00"))
    )
    assert isinstance(result.room_to_test_floor, Decimal)
    assert not isinstance(result.room_to_test_floor, float)


def test_non_test_result_is_exactly_none_not_zero():
    result = calculate_campaign_test_floor_room(
        _campaign(is_test_campaign=False, test_budget_floor=None)
    )
    assert result.room_to_test_floor is None
    assert result.room_to_test_floor != Decimal("0.00")


def test_test_campaign_result_retains_exactly_two_decimal_places():
    result = calculate_campaign_test_floor_room(
        _campaign(is_test_campaign=True, test_budget_floor=Decimal("300.00"))
    )
    assert result.room_to_test_floor.as_tuple().exponent == -2


def test_calculate_campaign_test_floor_room_rejects_incompatible_input():
    with pytest.raises(AttributeError):
        calculate_campaign_test_floor_room(None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        calculate_campaign_test_floor_room(  # type: ignore[arg-type]
            {"is_test_campaign": True, "test_budget_floor": Decimal("300.00")}
        )


def test_test_floor_room_has_no_out_of_scope_fields():
    field_names = set(CampaignTestFloorRoom.model_fields.keys())
    forbidden = {
        "effective_floor",
        "minimum_budget",
        "room_to_static_maximum",
        "room_to_static_minimum",
        "raw_percentage_movement_cap",
        "is_protected",
        "eligibility",
        "blocked",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Stage 13 — exact calculation
# ---------------------------------------------------------------------------


def test_ordinary_test_campaign_exact_subtraction():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor == Decimal("900.00")


def test_test_floor_of_zero():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("0.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("0.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("0.00"),
    )
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor == Decimal("1200.00")


def test_test_floor_below_minimum_budget():
    campaign = _campaign(
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("200.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("100.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("100.00"),
    )
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor == Decimal("900.00")


def test_test_floor_equal_to_minimum_budget():
    campaign = _campaign(
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("200.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("200.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("200.00"),
    )
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor == Decimal("800.00")


def test_test_floor_above_minimum_budget():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor == Decimal("900.00")
    assert campaign.test_budget_floor > campaign.minimum_budget


def test_test_floor_equal_to_current_budget_returns_zero():
    campaign = _campaign(
        current_budget=Decimal("500.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("500.00"),
    )
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor == Decimal("0.00")


def test_no_float_conversion_in_test_floor_calculation():
    source = inspect.getsource(calculate_campaign_test_floor_room)
    assert "float(" not in source


def test_no_quantize_call_in_test_floor_calculation():
    source = inspect.getsource(calculate_campaign_test_floor_room)
    tree = ast.parse(source)
    quantize_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "quantize"
    ]
    assert len(quantize_calls) == 0


# ---------------------------------------------------------------------------
# Stage 13 — non-test behaviour
# ---------------------------------------------------------------------------


def test_valid_non_test_campaign_returns_none_without_raising():
    campaign = _campaign(is_test_campaign=False, test_budget_floor=None)
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor is None
    assert campaign.test_budget_floor is None
    assert campaign.is_test_campaign is False


def test_non_test_campaign_not_rejected_or_reconstructed():
    campaign = _campaign(campaign_id="NON-TEST-1", is_test_campaign=False, test_budget_floor=None)
    result = calculate_campaign_test_floor_room(campaign)
    assert result.campaign_id == "NON-TEST-1"
    assert isinstance(result, CampaignTestFloorRoom)


# ---------------------------------------------------------------------------
# Stage 13 — Decimal context and precision
# ---------------------------------------------------------------------------


def test_mutated_global_decimal_context_does_not_affect_test_floor_room():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        result = calculate_campaign_test_floor_room(campaign)
        assert result.room_to_test_floor == Decimal("900.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_global_decimal_context_unchanged_after_test_floor_function_returns():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        calculate_campaign_test_floor_room(campaign)

        assert decimal.getcontext().prec == 5
        assert decimal.getcontext().rounding == decimal.ROUND_DOWN
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_extreme_valid_currency_operands_preserve_significant_digits():
    extreme_current_budget = Decimal("9" * 26 + ".99")
    campaign = _campaign(
        campaign_id="EXTREME-TEST-1",
        current_budget=extreme_current_budget,
        minimum_budget=Decimal("0.00"),
        maximum_budget=extreme_current_budget,
        spend_to_date=Decimal("0.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("1.00"),
    )
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor == Decimal("9" * 25 + "8.99")


def test_extreme_valid_currency_floor_equal_to_zero_returns_full_budget():
    extreme_current_budget = Decimal("9" * 26 + ".99")
    campaign = _campaign(
        campaign_id="EXTREME-TEST-2",
        current_budget=extreme_current_budget,
        minimum_budget=Decimal("0.00"),
        maximum_budget=extreme_current_budget,
        spend_to_date=Decimal("0.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("0.00"),
    )
    result = calculate_campaign_test_floor_room(campaign)
    assert result.room_to_test_floor == extreme_current_budget


# ---------------------------------------------------------------------------
# Stage 13 — independence
# ---------------------------------------------------------------------------


def test_minimum_budget_does_not_affect_test_floor_room():
    percentage_shared_kwargs = dict(
        current_budget=Decimal("1200.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    low_minimum = _campaign(campaign_id="C001", minimum_budget=Decimal("0.00"), **percentage_shared_kwargs)
    high_minimum = _campaign(campaign_id="C001", minimum_budget=Decimal("300.00"), **percentage_shared_kwargs)
    result_low = calculate_campaign_test_floor_room(low_minimum)
    result_high = calculate_campaign_test_floor_room(high_minimum)
    assert result_low.room_to_test_floor == result_high.room_to_test_floor


def test_maximum_budget_does_not_affect_test_floor_room():
    shared_kwargs = dict(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    narrow_maximum = _campaign(campaign_id="C001", maximum_budget=Decimal("1500.00"), **shared_kwargs)
    wide_maximum = _campaign(campaign_id="C001", maximum_budget=Decimal("1000000.00"), **shared_kwargs)
    result_narrow = calculate_campaign_test_floor_room(narrow_maximum)
    result_wide = calculate_campaign_test_floor_room(wide_maximum)
    assert result_narrow.room_to_test_floor == result_wide.room_to_test_floor


def test_stage_10_12_results_neither_read_nor_called_for_test_floor_room():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    room = calculate_campaign_static_budget_room(campaign)
    test_floor_room = calculate_campaign_test_floor_room(campaign)
    assert isinstance(room, CampaignStaticBudgetRoom)
    assert isinstance(test_floor_room, CampaignTestFloorRoom)
    assert not hasattr(test_floor_room, "room_to_static_maximum")
    assert not hasattr(test_floor_room, "room_to_static_minimum")
    assert not hasattr(test_floor_room, "applicable_max_change_percentage")
    assert not hasattr(test_floor_room, "raw_percentage_movement_cap")


def test_is_protected_does_not_affect_test_floor_room():
    shared_kwargs = dict(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    unprotected = _campaign(campaign_id="C001", is_protected=False, **shared_kwargs)
    protected = _campaign(campaign_id="C001", is_protected=True, **shared_kwargs)
    result_unprotected = calculate_campaign_test_floor_room(unprotected)
    result_protected = calculate_campaign_test_floor_room(protected)
    assert result_unprotected.room_to_test_floor == result_protected.room_to_test_floor


def test_platform_does_not_affect_test_floor_room():
    shared_kwargs = dict(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    google = _campaign(campaign_id="C001", platform=Platform.GOOGLE_ADS, **shared_kwargs)
    meta = _campaign(campaign_id="C001", platform=Platform.META_ADS, **shared_kwargs)
    result_google = calculate_campaign_test_floor_room(google)
    result_meta = calculate_campaign_test_floor_room(meta)
    assert result_google.room_to_test_floor == result_meta.room_to_test_floor


def test_kpi_type_does_not_affect_test_floor_room():
    shared_kwargs = dict(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    cpa = _campaign(
        campaign_id="C001",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10.00"),
        kpi_actual_7d=Decimal("10.00"),
        kpi_actual_28d=Decimal("10.00"),
        **shared_kwargs,
    )
    roas = _campaign(
        campaign_id="C001",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("3.00"),
        kpi_actual_7d=Decimal("3.00"),
        kpi_actual_28d=Decimal("3.00"),
        **shared_kwargs,
    )
    result_cpa = calculate_campaign_test_floor_room(cpa)
    result_roas = calculate_campaign_test_floor_room(roas)
    assert result_cpa.room_to_test_floor == result_roas.room_to_test_floor


def test_campaign_max_change_percentage_does_not_affect_test_floor_room():
    shared_kwargs = dict(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    no_override = _campaign(campaign_id="C001", campaign_max_change_percentage=None, **shared_kwargs)
    with_override = _campaign(
        campaign_id="C001", campaign_max_change_percentage=Decimal("0.05"), **shared_kwargs
    )
    result_no_override = calculate_campaign_test_floor_room(no_override)
    result_with_override = calculate_campaign_test_floor_room(with_override)
    assert result_no_override.room_to_test_floor == result_with_override.room_to_test_floor


def test_test_floor_room_function_reads_only_four_authorised_fields():
    source = inspect.getsource(calculate_campaign_test_floor_room)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_name = func_def.args.args[0].arg

    accessed_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == param_name:
                accessed_attrs.add(node.attr)

    assert accessed_attrs == {"campaign_id", "is_test_campaign", "current_budget", "test_budget_floor"}


def test_test_floor_room_does_not_reference_review_setup():
    source = inspect.getsource(calculate_campaign_test_floor_room)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "ReviewSetup" not in referenced_names
    assert "review" not in referenced_names


def test_test_floor_room_does_not_call_stage_10_11_12_or_stage_3_to_9_functions():
    source = inspect.getsource(calculate_campaign_test_floor_room)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "calculate_campaign_static_budget_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_raw_percentage_movement_cap",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_no_effective_floor_or_movement_output_for_test_floor_room():
    result = calculate_campaign_test_floor_room(
        _campaign(is_test_campaign=True, test_budget_floor=Decimal("300.00"))
    )
    for attr in (
        "effective_floor",
        "permissible_decrease",
        "effective_movement",
        "eligibility",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
        "blocked",
    ):
        assert not hasattr(result, attr)


# ---------------------------------------------------------------------------
# Stage 13 — sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_test_floor_room_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    test_floor_results = [
        calculate_campaign_test_floor_room(c) for c in report.valid_campaigns
    ]
    assert [r.campaign_id for r in test_floor_results] == ["G001", "M001", "G002", "G003"]

    expected_is_test = {
        "G001": False,
        "M001": False,
        "G002": False,
        "G003": True,
    }
    expected_test_budget_floor = {
        "G001": None,
        "M001": None,
        "G002": None,
        "G003": Decimal("300.00"),
    }
    expected_room_to_test_floor = {
        "G001": None,
        "M001": None,
        "G002": None,
        "G003": Decimal("900.00"),
    }
    for campaign in report.valid_campaigns:
        assert campaign.is_test_campaign == expected_is_test[campaign.campaign_id]
        assert campaign.test_budget_floor == expected_test_budget_floor[campaign.campaign_id]
    for result in test_floor_results:
        assert result.room_to_test_floor == expected_room_to_test_floor[result.campaign_id]

    g003 = next(c for c in report.valid_campaigns if c.campaign_id == "G003")
    assert g003.current_budget == Decimal("1200.00")

    # Retain and independently verify Stages 10-12's existing sample results via
    # separate calls — none of Stage 10, 11, 12, or 13's results is combined or
    # intersected here. Decimal("900.00") for G003 is a raw, informational
    # test-floor distance only, never described as a permissible decrease.
    room_results = [calculate_campaign_static_budget_room(c) for c in report.valid_campaigns]
    expected_room = {
        "G001": (Decimal("3000.00"), Decimal("2500.00")),
        "M001": (Decimal("2500.00"), Decimal("2000.00")),
        "G002": (Decimal("3000.00"), Decimal("4000.00")),
        "G003": (Decimal("800.00"), Decimal("1100.00")),
    }
    for room in room_results:
        exp_max, exp_min = expected_room[room.campaign_id]
        assert room.room_to_static_maximum == exp_max
        assert room.room_to_static_minimum == exp_min

    percentages = [
        resolve_campaign_applicable_change_percentage(review, c)
        for c in report.valid_campaigns
    ]
    expected_applicable_percentage = {
        "G001": Decimal("0.20"),
        "M001": Decimal("0.15"),
        "G002": Decimal("0.20"),
        "G003": Decimal("0.20"),
    }
    for percentage in percentages:
        assert (
            percentage.applicable_max_change_percentage
            == expected_applicable_percentage[percentage.campaign_id]
        )

    caps = [
        calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
        for campaign, percentage in zip(report.valid_campaigns, percentages)
    ]
    expected_raw_cap = {
        "G001": Decimal("600.00"),
        "M001": Decimal("375.00"),
        "G002": Decimal("1000.00"),
        "G003": Decimal("240.00"),
    }
    for cap in caps:
        assert cap.raw_percentage_movement_cap == expected_raw_cap[cap.campaign_id]


# ---------------------------------------------------------------------------
# Stage 14 — CampaignProtectionConstraint result model
# ---------------------------------------------------------------------------


def test_campaign_protection_constraint_accepts_exactly_two_fields():
    assert set(CampaignProtectionConstraint.model_fields.keys()) == {
        "campaign_id",
        "decrease_blocked",
    }


def test_campaign_protection_constraint_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignProtectionConstraint(
            campaign_id="C001",
            decrease_blocked=True,
            extra_field="not allowed",
        )


def test_campaign_protection_constraint_is_immutable():
    result = resolve_campaign_protection_constraint(_campaign(is_protected=True))
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_protection_constraint_campaign_id_copied_exactly():
    result = resolve_campaign_protection_constraint(_campaign(campaign_id="XYZ-1"))
    assert result.campaign_id == "XYZ-1"


def test_decrease_blocked_is_bool():
    result = resolve_campaign_protection_constraint(_campaign(is_protected=True))
    assert isinstance(result.decrease_blocked, bool)
    result_false = resolve_campaign_protection_constraint(_campaign(is_protected=False))
    assert isinstance(result_false.decrease_blocked, bool)


def test_no_decimal_or_optional_monetary_field_exists():
    field_names = set(CampaignProtectionConstraint.model_fields.keys())
    forbidden = {
        "room_to_protection_limit",
        "room_to_static_maximum",
        "room_to_static_minimum",
        "room_to_test_floor",
        "raw_percentage_movement_cap",
        "applicable_max_change_percentage",
        "eligibility",
        "blocked",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
    }
    assert field_names.isdisjoint(forbidden)
    for field_info in CampaignProtectionConstraint.model_fields.values():
        assert field_info.annotation is not Decimal


def test_calculate_campaign_protection_constraint_rejects_incompatible_input():
    with pytest.raises(AttributeError):
        resolve_campaign_protection_constraint(None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        resolve_campaign_protection_constraint({"is_protected": True})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Stage 14 — exact mapping
# ---------------------------------------------------------------------------


def test_protected_campaign_returns_decrease_blocked_true():
    result = resolve_campaign_protection_constraint(_campaign(is_protected=True))
    assert result.decrease_blocked is True


def test_non_protected_campaign_returns_decrease_blocked_false():
    result = resolve_campaign_protection_constraint(_campaign(is_protected=False))
    assert result.decrease_blocked is False


def test_false_is_not_converted_to_none():
    result = resolve_campaign_protection_constraint(_campaign(is_protected=False))
    assert result.decrease_blocked is not None
    assert result.decrease_blocked is False


def test_true_is_not_converted_to_decimal_zero():
    result = resolve_campaign_protection_constraint(_campaign(is_protected=True))
    assert result.decrease_blocked is True
    assert not isinstance(result.decrease_blocked, Decimal)


def test_no_truthiness_fallback_source():
    source = inspect.getsource(resolve_campaign_protection_constraint)
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BoolOp) for node in ast.walk(tree))


def test_no_monetary_calculation_in_protection_constraint():
    source = inspect.getsource(resolve_campaign_protection_constraint)
    assert "Decimal" not in source
    assert "quantize" not in source
    assert "float(" not in source
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BinOp) for node in ast.walk(tree))


# ---------------------------------------------------------------------------
# Stage 14 — independence
# ---------------------------------------------------------------------------


def test_is_test_campaign_does_not_affect_protection_constraint():
    non_test = _campaign(campaign_id="C001", is_protected=True, is_test_campaign=False, test_budget_floor=None)
    test_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_protected=True,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    result_non_test = resolve_campaign_protection_constraint(non_test)
    result_test = resolve_campaign_protection_constraint(test_campaign)
    assert result_non_test.decrease_blocked == result_test.decrease_blocked


def test_test_budget_floor_does_not_affect_protection_constraint():
    campaign = _campaign(
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_protected=False,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    result = resolve_campaign_protection_constraint(campaign)
    assert result.decrease_blocked is False


def test_campaign_both_protected_and_test_returns_decrease_blocked_true():
    campaign = _campaign(
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        is_protected=True,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    result = resolve_campaign_protection_constraint(campaign)
    assert result.decrease_blocked is True


def test_current_budget_does_not_affect_protection_constraint():
    low_budget = _campaign(
        campaign_id="C001",
        current_budget=Decimal("150.00"),
        spend_to_date=Decimal("100.00"),
        is_protected=True,
    )
    high_budget = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1900.00"),
        spend_to_date=Decimal("500.00"),
        is_protected=True,
    )
    result_low = resolve_campaign_protection_constraint(low_budget)
    result_high = resolve_campaign_protection_constraint(high_budget)
    assert result_low.decrease_blocked == result_high.decrease_blocked


def test_minimum_budget_does_not_affect_protection_constraint():
    shared = dict(current_budget=Decimal("1000.00"), maximum_budget=Decimal("2000.00"), is_protected=True)
    low_minimum = _campaign(campaign_id="C001", minimum_budget=Decimal("0.00"), **shared)
    high_minimum = _campaign(campaign_id="C001", minimum_budget=Decimal("500.00"), **shared)
    result_low = resolve_campaign_protection_constraint(low_minimum)
    result_high = resolve_campaign_protection_constraint(high_minimum)
    assert result_low.decrease_blocked == result_high.decrease_blocked


def test_maximum_budget_does_not_affect_protection_constraint():
    shared = dict(current_budget=Decimal("1000.00"), minimum_budget=Decimal("100.00"), is_protected=True)
    narrow_maximum = _campaign(campaign_id="C001", maximum_budget=Decimal("1500.00"), **shared)
    wide_maximum = _campaign(campaign_id="C001", maximum_budget=Decimal("1000000.00"), **shared)
    result_narrow = resolve_campaign_protection_constraint(narrow_maximum)
    result_wide = resolve_campaign_protection_constraint(wide_maximum)
    assert result_narrow.decrease_blocked == result_wide.decrease_blocked


def test_platform_does_not_affect_protection_constraint():
    google = _campaign(campaign_id="C001", platform=Platform.GOOGLE_ADS, is_protected=True)
    meta = _campaign(campaign_id="C001", platform=Platform.META_ADS, is_protected=True)
    result_google = resolve_campaign_protection_constraint(google)
    result_meta = resolve_campaign_protection_constraint(meta)
    assert result_google.decrease_blocked == result_meta.decrease_blocked


def test_kpi_type_does_not_affect_protection_constraint():
    cpa = _campaign(
        campaign_id="C001",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("10.00"),
        kpi_actual_7d=Decimal("10.00"),
        kpi_actual_28d=Decimal("10.00"),
        is_protected=True,
    )
    roas = _campaign(
        campaign_id="C001",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("3.00"),
        kpi_actual_7d=Decimal("3.00"),
        kpi_actual_28d=Decimal("3.00"),
        is_protected=True,
    )
    result_cpa = resolve_campaign_protection_constraint(cpa)
    result_roas = resolve_campaign_protection_constraint(roas)
    assert result_cpa.decrease_blocked == result_roas.decrease_blocked


def test_campaign_max_change_percentage_not_read_for_protection_constraint():
    no_override = _campaign(campaign_id="C001", campaign_max_change_percentage=None, is_protected=True)
    with_override = _campaign(
        campaign_id="C001", campaign_max_change_percentage=Decimal("0.05"), is_protected=True
    )
    result_no_override = resolve_campaign_protection_constraint(no_override)
    result_with_override = resolve_campaign_protection_constraint(with_override)
    assert result_no_override.decrease_blocked == result_with_override.decrease_blocked


def test_protection_constraint_function_reads_only_two_authorised_fields():
    source = inspect.getsource(resolve_campaign_protection_constraint)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_name = func_def.args.args[0].arg

    accessed_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == param_name:
                accessed_attrs.add(node.attr)

    assert accessed_attrs == {"campaign_id", "is_protected"}


def test_protection_constraint_does_not_reference_review_setup():
    source = inspect.getsource(resolve_campaign_protection_constraint)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "ReviewSetup" not in referenced_names
    assert "review" not in referenced_names


def test_protection_constraint_does_not_call_stage_10_to_13_or_stage_3_to_9_functions():
    source = inspect.getsource(resolve_campaign_protection_constraint)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "calculate_campaign_static_budget_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_raw_percentage_movement_cap",
        "calculate_campaign_test_floor_room",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_stage_10_13_results_neither_read_nor_called_for_protection_constraint():
    campaign = _campaign(is_protected=True)
    room = calculate_campaign_static_budget_room(campaign)
    protection = resolve_campaign_protection_constraint(campaign)
    assert isinstance(room, CampaignStaticBudgetRoom)
    assert isinstance(protection, CampaignProtectionConstraint)
    assert not hasattr(protection, "room_to_static_maximum")
    assert not hasattr(protection, "room_to_static_minimum")
    assert not hasattr(protection, "applicable_max_change_percentage")
    assert not hasattr(protection, "raw_percentage_movement_cap")
    assert not hasattr(protection, "room_to_test_floor")


# ---------------------------------------------------------------------------
# Stage 14 — scope protection
# ---------------------------------------------------------------------------


def test_no_eligibility_score_recommendation_reason_code_allocation_or_conservation_output():
    result = resolve_campaign_protection_constraint(_campaign(is_protected=True))
    for attr in (
        "room_to_protection_limit",
        "effective_floor",
        "permissible_decrease",
        "effective_movement",
        "eligibility",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
        "blocked",
    ):
        assert not hasattr(result, attr)


# ---------------------------------------------------------------------------
# Stage 14 — sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_protection_constraint_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    protection_results = [
        resolve_campaign_protection_constraint(c) for c in report.valid_campaigns
    ]
    assert [r.campaign_id for r in protection_results] == ["G001", "M001", "G002", "G003"]

    expected_is_protected = {
        "G001": False,
        "M001": False,
        "G002": True,
        "G003": False,
    }
    expected_decrease_blocked = {
        "G001": False,
        "M001": False,
        "G002": True,
        "G003": False,
    }
    for campaign in report.valid_campaigns:
        assert campaign.is_protected == expected_is_protected[campaign.campaign_id]
    for result in protection_results:
        assert result.decrease_blocked == expected_decrease_blocked[result.campaign_id]

    # decrease_blocked=False for G001/M001/G003 is not permission to reduce those
    # campaigns; decrease_blocked=True for G002 is not eligibility, a recommendation,
    # or final movement — it states only the protection constraint itself.

    # Retain and independently verify Stages 10-13's existing sample results via
    # separate calls — none of Stage 10, 11, 12, 13, or 14's results is combined or
    # intersected here.
    room_results = [calculate_campaign_static_budget_room(c) for c in report.valid_campaigns]
    expected_room = {
        "G001": (Decimal("3000.00"), Decimal("2500.00")),
        "M001": (Decimal("2500.00"), Decimal("2000.00")),
        "G002": (Decimal("3000.00"), Decimal("4000.00")),
        "G003": (Decimal("800.00"), Decimal("1100.00")),
    }
    for room in room_results:
        exp_max, exp_min = expected_room[room.campaign_id]
        assert room.room_to_static_maximum == exp_max
        assert room.room_to_static_minimum == exp_min

    percentages = [
        resolve_campaign_applicable_change_percentage(review, c)
        for c in report.valid_campaigns
    ]
    expected_applicable_percentage = {
        "G001": Decimal("0.20"),
        "M001": Decimal("0.15"),
        "G002": Decimal("0.20"),
        "G003": Decimal("0.20"),
    }
    for percentage in percentages:
        assert (
            percentage.applicable_max_change_percentage
            == expected_applicable_percentage[percentage.campaign_id]
        )

    caps = [
        calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
        for campaign, percentage in zip(report.valid_campaigns, percentages)
    ]
    expected_raw_cap = {
        "G001": Decimal("600.00"),
        "M001": Decimal("375.00"),
        "G002": Decimal("1000.00"),
        "G003": Decimal("240.00"),
    }
    for cap in caps:
        assert cap.raw_percentage_movement_cap == expected_raw_cap[cap.campaign_id]

    test_floor_results = [
        calculate_campaign_test_floor_room(c) for c in report.valid_campaigns
    ]
    expected_room_to_test_floor = {
        "G001": None,
        "M001": None,
        "G002": None,
        "G003": Decimal("900.00"),
    }
    for result in test_floor_results:
        assert result.room_to_test_floor == expected_room_to_test_floor[result.campaign_id]


# ---------------------------------------------------------------------------
# Stage 15 — CampaignTestAwareStaticDecreaseRoom result model
# ---------------------------------------------------------------------------


def _static_room(**overrides) -> CampaignStaticBudgetRoom:
    kwargs = dict(
        campaign_id="C001",
        room_to_static_maximum=Decimal("1000.00"),
        room_to_static_minimum=Decimal("900.00"),
    )
    kwargs.update(overrides)
    return CampaignStaticBudgetRoom(**kwargs)


def _test_floor_room(**overrides) -> CampaignTestFloorRoom:
    kwargs = dict(
        campaign_id="C001",
        room_to_test_floor=None,
    )
    kwargs.update(overrides)
    return CampaignTestFloorRoom(**kwargs)


def test_campaign_test_aware_static_decrease_room_accepts_exactly_two_fields():
    assert set(CampaignTestAwareStaticDecreaseRoom.model_fields.keys()) == {
        "campaign_id",
        "test_aware_static_decrease_room",
    }


def test_result_campaign_id_is_str_and_room_is_decimal():
    result = resolve_campaign_test_aware_static_decrease_room(
        _static_room(), _test_floor_room()
    )
    assert isinstance(result.campaign_id, str)
    assert isinstance(result.test_aware_static_decrease_room, Decimal)


def test_test_aware_static_decrease_room_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignTestAwareStaticDecreaseRoom(
            campaign_id="C001",
            test_aware_static_decrease_room=Decimal("900.00"),
            extra_field="not allowed",
        )


def test_test_aware_static_decrease_room_is_immutable():
    result = resolve_campaign_test_aware_static_decrease_room(
        _static_room(), _test_floor_room()
    )
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_test_aware_static_decrease_room_has_no_optional_monetary_output():
    for field_info in CampaignTestAwareStaticDecreaseRoom.model_fields.values():
        if field_info.annotation is Decimal:
            continue
        assert field_info.annotation is str


def test_test_aware_static_decrease_room_has_no_eligibility_action_or_judgement_field():
    field_names = set(CampaignTestAwareStaticDecreaseRoom.model_fields.keys())
    forbidden = {
        "effective_decrease_floor",
        "effective_decrease_room",
        "permissible_decrease",
        "raw_percentage_movement_cap",
        "applicable_max_change_percentage",
        "decrease_blocked",
        "is_protected",
        "eligibility",
        "blocked",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Stage 15 — campaign identity
# ---------------------------------------------------------------------------


def test_matching_campaign_ids_return_the_exact_campaign_id():
    result = resolve_campaign_test_aware_static_decrease_room(
        _static_room(campaign_id="MATCH-1"), _test_floor_room(campaign_id="MATCH-1")
    )
    assert result.campaign_id == "MATCH-1"


def test_mismatched_campaign_ids_raise_value_error_with_exact_message():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_test_aware_static_decrease_room(
            _static_room(campaign_id="A"), _test_floor_room(campaign_id="B")
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving test-aware static decrease room."
    )


def test_no_monetary_result_resolved_after_id_mismatch():
    try:
        resolve_campaign_test_aware_static_decrease_room(
            _static_room(campaign_id="A"), _test_floor_room(campaign_id="B")
        )
        assert False, "expected ValueError, no result should be resolved"
    except ValueError:
        pass


def test_neither_input_campaign_id_silently_preferred_on_mismatch():
    source = inspect.getsource(resolve_campaign_test_aware_static_decrease_room)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    # The ID-equality guard (an `if` raising ValueError) must precede any Decimal
    # selection (an `Assign` to test_aware_static_decrease_room) in the function body.
    non_docstring_body = [
        stmt
        for stmt in func_def.body
        if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
    ]
    first_stmt = non_docstring_body[0]
    assert isinstance(first_stmt, ast.If)
    raises_value_error = any(
        isinstance(node, ast.Raise) for node in ast.walk(first_stmt)
    )
    assert raises_value_error


# ---------------------------------------------------------------------------
# Stage 15 — non-test behaviour
# ---------------------------------------------------------------------------


def test_none_room_to_test_floor_returns_room_to_static_minimum():
    static_room = _static_room(room_to_static_minimum=Decimal("2500.00"))
    test_floor_room = _test_floor_room(room_to_test_floor=None)
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("2500.00")


def test_non_test_returned_decimal_is_unchanged_object_value():
    static_room = _static_room(room_to_static_minimum=Decimal("2500.00"))
    result = resolve_campaign_test_aware_static_decrease_room(
        static_room, _test_floor_room(room_to_test_floor=None)
    )
    assert result.test_aware_static_decrease_room == static_room.room_to_static_minimum


def test_none_is_not_converted_to_zero():
    static_room = _static_room(room_to_static_minimum=Decimal("2500.00"))
    result = resolve_campaign_test_aware_static_decrease_room(
        static_room, _test_floor_room(room_to_test_floor=None)
    )
    assert result.test_aware_static_decrease_room != Decimal("0.00")


def test_stage_15_output_is_never_none():
    result = resolve_campaign_test_aware_static_decrease_room(
        _static_room(), _test_floor_room(room_to_test_floor=None)
    )
    assert result.test_aware_static_decrease_room is not None


# ---------------------------------------------------------------------------
# Stage 15 — test-campaign precedence
# ---------------------------------------------------------------------------


def test_test_floor_room_greater_than_static_minimum_returns_static_minimum():
    static_room = _static_room(room_to_static_minimum=Decimal("900.00"))
    test_floor_room = _test_floor_room(room_to_test_floor=Decimal("1100.00"))
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("900.00")


def test_test_floor_room_equal_to_static_minimum_returns_equal_value():
    static_room = _static_room(room_to_static_minimum=Decimal("1000.00"))
    test_floor_room = _test_floor_room(room_to_test_floor=Decimal("1000.00"))
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("1000.00")


def test_test_floor_room_smaller_than_static_minimum_returns_test_floor_room():
    static_room = _static_room(room_to_static_minimum=Decimal("1100.00"))
    test_floor_room = _test_floor_room(room_to_test_floor=Decimal("900.00"))
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("900.00")


def test_test_floor_room_zero_returns_zero():
    static_room = _static_room(room_to_static_minimum=Decimal("500.00"))
    test_floor_room = _test_floor_room(room_to_test_floor=Decimal("0.00"))
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("0.00")


def test_static_minimum_room_zero_returns_zero():
    static_room = _static_room(room_to_static_minimum=Decimal("0.00"))
    test_floor_room = _test_floor_room(room_to_test_floor=Decimal("500.00"))
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("0.00")


def test_both_rooms_zero_returns_zero():
    static_room = _static_room(room_to_static_minimum=Decimal("0.00"))
    test_floor_room = _test_floor_room(room_to_test_floor=Decimal("0.00"))
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("0.00")


@pytest.mark.parametrize(
    "static_min, test_floor, expected",
    [
        (Decimal("900.00"), Decimal("1100.00"), Decimal("900.00")),
        (Decimal("1000.00"), Decimal("1000.00"), Decimal("1000.00")),
        (Decimal("1100.00"), Decimal("900.00"), Decimal("900.00")),
        (Decimal("0.00"), Decimal("500.00"), Decimal("0.00")),
        (Decimal("500.00"), Decimal("0.00"), Decimal("0.00")),
    ],
)
def test_result_is_always_the_smaller_applicable_room(static_min, test_floor, expected):
    static_room = _static_room(room_to_static_minimum=static_min)
    test_floor_room = _test_floor_room(room_to_test_floor=test_floor)
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == expected
    assert result.test_aware_static_decrease_room == min(static_min, test_floor)


# ---------------------------------------------------------------------------
# Stage 15 — Decimal behaviour
# ---------------------------------------------------------------------------


def test_no_float_conversion_in_test_aware_static_decrease_room():
    source = inspect.getsource(resolve_campaign_test_aware_static_decrease_room)
    assert "float(" not in source


def test_no_arithmetic_subtraction_quantisation_or_rounding():
    source = inspect.getsource(resolve_campaign_test_aware_static_decrease_room)
    assert "quantize" not in source
    assert "ROUND_HALF_UP" not in source
    assert "CURRENCY_QUANTUM" not in source
    assert "localcontext" not in source
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BinOp) for node in ast.walk(tree))


def test_mutated_global_decimal_context_does_not_affect_selection():
    static_room = _static_room(room_to_static_minimum=Decimal("1100.00"))
    test_floor_room = _test_floor_room(room_to_test_floor=Decimal("900.00"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
        assert result.test_aware_static_decrease_room == Decimal("900.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_global_decimal_context_unchanged_after_function_returns():
    static_room = _static_room()
    test_floor_room = _test_floor_room()

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN

        resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)

        assert decimal.getcontext().prec == 5
        assert decimal.getcontext().rounding == decimal.ROUND_DOWN
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_extreme_already_valid_stage_10_and_stage_13_values_handled_safely():
    extreme_value = Decimal("9" * 26 + ".99")
    static_room = _static_room(
        room_to_static_maximum=Decimal("0.00"),
        room_to_static_minimum=extreme_value,
    )
    test_floor_room = _test_floor_room(room_to_test_floor=extreme_value)
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == extreme_value

    smaller_extreme = Decimal("9" * 25 + "8.99")
    test_floor_room_smaller = _test_floor_room(room_to_test_floor=smaller_extreme)
    result_smaller = resolve_campaign_test_aware_static_decrease_room(
        static_room, test_floor_room_smaller
    )
    assert result_smaller.test_aware_static_decrease_room == smaller_extreme


# ---------------------------------------------------------------------------
# Stage 15 — authorised access
# ---------------------------------------------------------------------------


def test_function_reads_only_four_authorised_fields():
    source = inspect.getsource(resolve_campaign_test_aware_static_decrease_room)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    static_room_param, test_floor_room_param = (arg.arg for arg in func_def.args.args)
    assert static_room_param == "static_room"
    assert test_floor_room_param == "test_floor_room"

    static_room_attrs: set[str] = set()
    test_floor_room_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == static_room_param:
                static_room_attrs.add(node.attr)
            elif node.value.id == test_floor_room_param:
                test_floor_room_attrs.add(node.attr)

    assert static_room_attrs == {"campaign_id", "room_to_static_minimum"}
    assert test_floor_room_attrs == {"campaign_id", "room_to_test_floor"}


# ---------------------------------------------------------------------------
# Stage 15 — earlier-stage separation
# ---------------------------------------------------------------------------


def test_does_not_call_stage_10_stage_13_or_other_earlier_stage_functions():
    source = inspect.getsource(resolve_campaign_test_aware_static_decrease_room)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "calculate_campaign_static_budget_room",
        "calculate_campaign_test_floor_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_raw_percentage_movement_cap",
        "resolve_campaign_protection_constraint",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_does_not_reference_campaign_input_or_review_setup():
    source = inspect.getsource(resolve_campaign_test_aware_static_decrease_room)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "CampaignInput" not in referenced_names
    assert "ReviewSetup" not in referenced_names
    assert "review" not in referenced_names
    assert "campaign" not in referenced_names


def test_stage_11_12_14_results_unused():
    result = resolve_campaign_test_aware_static_decrease_room(
        _static_room(), _test_floor_room()
    )
    assert not hasattr(result, "applicable_max_change_percentage")
    assert not hasattr(result, "raw_percentage_movement_cap")
    assert not hasattr(result, "decrease_blocked")


# ---------------------------------------------------------------------------
# Stage 15 — protection independence
# ---------------------------------------------------------------------------


def test_protected_and_unprotected_source_campaigns_produce_identical_results():
    unprotected_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_protected=False,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    protected_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_protected=True,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    result_unprotected = resolve_campaign_test_aware_static_decrease_room(
        calculate_campaign_static_budget_room(unprotected_campaign),
        calculate_campaign_test_floor_room(unprotected_campaign),
    )
    result_protected = resolve_campaign_test_aware_static_decrease_room(
        calculate_campaign_static_budget_room(protected_campaign),
        calculate_campaign_test_floor_room(protected_campaign),
    )
    assert (
        result_unprotected.test_aware_static_decrease_room
        == result_protected.test_aware_static_decrease_room
    )


def test_protected_status_unavailable_to_function():
    source = inspect.getsource(resolve_campaign_test_aware_static_decrease_room)
    assert "is_protected" not in source
    assert "decrease_blocked" not in source
    assert "CampaignProtectionConstraint" not in source


def test_campaign_both_test_and_protected_resolved_only_from_stage_10_and_13_facts():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_protected=True,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    static_room = calculate_campaign_static_budget_room(campaign)
    test_floor_room = calculate_campaign_test_floor_room(campaign)
    protection = resolve_campaign_protection_constraint(campaign)
    assert protection.decrease_blocked is True

    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("900.00")


def test_no_protection_based_zero_calculated():
    # A protected campaign whose floors are both non-zero must not receive a
    # protection-driven zero result.
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_protected=True,
        is_test_campaign=False,
        test_budget_floor=None,
    )
    static_room = calculate_campaign_static_budget_room(campaign)
    test_floor_room = calculate_campaign_test_floor_room(campaign)
    result = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    assert result.test_aware_static_decrease_room == Decimal("1100.00")
    assert result.test_aware_static_decrease_room != Decimal("0.00")


# ---------------------------------------------------------------------------
# Stage 15 — scope protection
# ---------------------------------------------------------------------------


def test_no_percentage_cap_effective_constraint_or_later_judgement_output():
    result = resolve_campaign_test_aware_static_decrease_room(
        _static_room(), _test_floor_room()
    )
    for attr in (
        "raw_percentage_movement_cap",
        "applicable_max_change_percentage",
        "effective_decrease_room",
        "effective_decrease_floor",
        "permissible_decrease",
        "decrease_blocked",
        "eligibility",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
        "blocked",
    ):
        assert not hasattr(result, attr)


# ---------------------------------------------------------------------------
# Stage 15 — input contract
# ---------------------------------------------------------------------------


def test_none_and_dict_inputs_are_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_test_aware_static_decrease_room(None, None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        resolve_campaign_test_aware_static_decrease_room(  # type: ignore[arg-type]
            _static_room(), {"room_to_test_floor": None, "campaign_id": "C001"}
        )
    with pytest.raises(AttributeError):
        resolve_campaign_test_aware_static_decrease_room(  # type: ignore[arg-type]
            {"campaign_id": "C001", "room_to_static_minimum": Decimal("900.00")},
            _test_floor_room(),
        )


# ---------------------------------------------------------------------------
# Stage 15 — sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_test_aware_static_decrease_room_exact_values_and_order():
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    static_rooms = {
        c.campaign_id: calculate_campaign_static_budget_room(c) for c in report.valid_campaigns
    }
    test_floor_rooms = {
        c.campaign_id: calculate_campaign_test_floor_room(c) for c in report.valid_campaigns
    }
    results = [
        resolve_campaign_test_aware_static_decrease_room(
            static_rooms[c.campaign_id], test_floor_rooms[c.campaign_id]
        )
        for c in report.valid_campaigns
    ]
    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": Decimal("2500.00"),
        "M001": Decimal("2000.00"),
        "G002": Decimal("4000.00"),
        "G003": Decimal("900.00"),
    }
    for result in results:
        assert result.test_aware_static_decrease_room == expected[result.campaign_id]

    # Independently preserve and verify the existing Stage 10-14 sample outcomes -
    # never combined with Stage 15's result.
    expected_static_minimum = {
        "G001": Decimal("2500.00"),
        "M001": Decimal("2000.00"),
        "G002": Decimal("4000.00"),
        "G003": Decimal("1100.00"),
    }
    for campaign_id, room in static_rooms.items():
        assert room.room_to_static_minimum == expected_static_minimum[campaign_id]

    expected_test_floor = {
        "G001": None,
        "M001": None,
        "G002": None,
        "G003": Decimal("900.00"),
    }
    for campaign_id, room in test_floor_rooms.items():
        assert room.room_to_test_floor == expected_test_floor[campaign_id]

    protection_results = [
        resolve_campaign_protection_constraint(c) for c in report.valid_campaigns
    ]
    expected_decrease_blocked = {
        "G001": False,
        "M001": False,
        "G002": True,
        "G003": False,
    }
    for result in protection_results:
        assert result.decrease_blocked == expected_decrease_blocked[result.campaign_id]

    # G002: protection remains decrease_blocked=True, Stage 15's result remains
    # 4000.00 - the two are never combined, and 4000.00 is never described as
    # permissible decrease.
    g002_result = next(r for r in results if r.campaign_id == "G002")
    assert g002_result.test_aware_static_decrease_room == Decimal("4000.00")
    g002_protection = next(r for r in protection_results if r.campaign_id == "G002")
    assert g002_protection.decrease_blocked is True

    # G003: Stage 10's room_to_static_minimum (1100.00) and Stage 13's
    # room_to_test_floor (900.00) both remain visible and unaltered; Stage 15
    # selects the smaller (900.00), never described as permissible decrease.
    assert static_rooms["G003"].room_to_static_minimum == Decimal("1100.00")
    assert test_floor_rooms["G003"].room_to_test_floor == Decimal("900.00")
    g003_result = next(r for r in results if r.campaign_id == "G003")
    assert g003_result.test_aware_static_decrease_room == Decimal("900.00")


# ---------------------------------------------------------------------------
# Stage 16 — CampaignRawIncreaseLimit result model
# ---------------------------------------------------------------------------


def _raw_cap(**overrides) -> CampaignRawPercentageMovementCap:
    kwargs = dict(
        campaign_id="C001",
        raw_percentage_movement_cap=Decimal("600.00"),
    )
    kwargs.update(overrides)
    return CampaignRawPercentageMovementCap(**kwargs)


def _decrease_room(**overrides) -> CampaignTestAwareStaticDecreaseRoom:
    kwargs = dict(
        campaign_id="C001",
        test_aware_static_decrease_room=Decimal("900.00"),
    )
    kwargs.update(overrides)
    return CampaignTestAwareStaticDecreaseRoom(**kwargs)


def _protection(**overrides) -> CampaignProtectionConstraint:
    kwargs = dict(
        campaign_id="C001",
        decrease_blocked=False,
    )
    kwargs.update(overrides)
    return CampaignProtectionConstraint(**kwargs)


def _raw_decrease(**overrides) -> CampaignRawDecreaseLimit:
    kwargs = dict(
        campaign_id="C001",
        raw_decrease_limit=Decimal("600.00"),
    )
    kwargs.update(overrides)
    return CampaignRawDecreaseLimit(**kwargs)


def test_campaign_raw_increase_limit_accepts_exactly_two_fields():
    assert set(CampaignRawIncreaseLimit.model_fields.keys()) == {
        "campaign_id",
        "raw_increase_limit",
    }


def test_raw_increase_limit_campaign_id_is_str_and_limit_is_decimal():
    result = resolve_campaign_raw_increase_limit(_static_room(), _raw_cap())
    assert isinstance(result.campaign_id, str)
    assert isinstance(result.raw_increase_limit, Decimal)


def test_campaign_raw_increase_limit_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignRawIncreaseLimit(
            campaign_id="C001",
            raw_increase_limit=Decimal("600.00"),
            extra_field="not allowed",
        )


def test_campaign_raw_increase_limit_is_immutable():
    result = resolve_campaign_raw_increase_limit(_static_room(), _raw_cap())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_raw_increase_limit_has_no_optional_monetary_field():
    for field_info in CampaignRawIncreaseLimit.model_fields.values():
        if field_info.annotation is Decimal:
            continue
        assert field_info.annotation is str


def test_raw_increase_limit_has_no_decrease_eligibility_action_or_judgement_field():
    field_names = set(CampaignRawIncreaseLimit.model_fields.keys())
    forbidden = {
        "raw_decrease_limit",
        "test_aware_static_decrease_room",
        "room_to_static_minimum",
        "room_to_test_floor",
        "decrease_blocked",
        "is_protected",
        "effective_increase",
        "permissible_increase",
        "eligibility",
        "blocked",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Stage 16 — campaign identity
# ---------------------------------------------------------------------------


def test_matching_campaign_ids_preserve_campaign_id_exactly():
    result = resolve_campaign_raw_increase_limit(
        _static_room(campaign_id="MATCH-1"), _raw_cap(campaign_id="MATCH-1")
    )
    assert result.campaign_id == "MATCH-1"


def test_raw_increase_limit_mismatched_campaign_ids_raise_value_error_with_exact_message():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_raw_increase_limit(
            _static_room(campaign_id="A"), _raw_cap(campaign_id="B")
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving raw increase limit."
    )


def test_id_validation_occurs_before_decimal_selection():
    source = inspect.getsource(resolve_campaign_raw_increase_limit)
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


def test_neither_campaign_id_silently_preferred_after_mismatch():
    with pytest.raises(ValueError):
        resolve_campaign_raw_increase_limit(
            _static_room(campaign_id="A"), _raw_cap(campaign_id="B")
        )


def test_no_result_returned_after_raw_increase_limit_mismatch():
    try:
        resolve_campaign_raw_increase_limit(
            _static_room(campaign_id="A"), _raw_cap(campaign_id="B")
        )
        assert False, "expected ValueError, no result should be returned"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Stage 16 — comparison
# ---------------------------------------------------------------------------


def test_static_maximum_room_smaller_returns_static_maximum_room():
    static_room = _static_room(room_to_static_maximum=Decimal("600.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("1000.00"))
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == Decimal("600.00")


def test_static_maximum_room_equal_to_raw_cap_returns_equal_value():
    static_room = _static_room(room_to_static_maximum=Decimal("800.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("800.00"))
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == Decimal("800.00")


def test_raw_cap_smaller_returns_raw_cap():
    static_room = _static_room(room_to_static_maximum=Decimal("3000.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("600.00"))
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == Decimal("600.00")


def test_static_maximum_room_zero_returns_zero():
    static_room = _static_room(room_to_static_maximum=Decimal("0.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("500.00"))
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == Decimal("0.00")


def test_raw_cap_zero_returns_zero():
    static_room = _static_room(room_to_static_maximum=Decimal("500.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("0.00"))
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == Decimal("0.00")


def test_both_values_zero_returns_zero():
    static_room = _static_room(room_to_static_maximum=Decimal("0.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("0.00"))
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == Decimal("0.00")


@pytest.mark.parametrize(
    "static_max, cap, expected",
    [
        (Decimal("600.00"), Decimal("1000.00"), Decimal("600.00")),
        (Decimal("800.00"), Decimal("800.00"), Decimal("800.00")),
        (Decimal("3000.00"), Decimal("600.00"), Decimal("600.00")),
        (Decimal("0.00"), Decimal("500.00"), Decimal("0.00")),
        (Decimal("500.00"), Decimal("0.00"), Decimal("0.00")),
    ],
)
def test_smaller_approved_operand_always_selected(static_max, cap, expected):
    static_room = _static_room(room_to_static_maximum=static_max)
    raw_cap = _raw_cap(raw_percentage_movement_cap=cap)
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == expected
    assert result.raw_increase_limit == min(static_max, cap)


def test_selected_decimal_operand_returned_unchanged():
    static_room = _static_room(room_to_static_maximum=Decimal("600.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("1000.00"))
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == static_room.room_to_static_maximum


# ---------------------------------------------------------------------------
# Stage 16 — Decimal behaviour
# ---------------------------------------------------------------------------


def test_no_float_conversion_in_raw_increase_limit():
    source = inspect.getsource(resolve_campaign_raw_increase_limit)
    assert "float(" not in source


def test_no_arithmetic_rounding_or_quantisation_in_raw_increase_limit():
    source = inspect.getsource(resolve_campaign_raw_increase_limit)
    assert "quantize" not in source
    assert "ROUND_HALF_UP" not in source
    assert "CURRENCY_QUANTUM" not in source
    assert "localcontext" not in source
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BinOp) for node in ast.walk(tree))


def test_mutated_global_decimal_precision_does_not_affect_raw_increase_limit():
    static_room = _static_room(room_to_static_maximum=Decimal("600.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("1000.00"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
        assert result.raw_increase_limit == Decimal("600.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_mutated_global_decimal_rounding_does_not_affect_raw_increase_limit():
    static_room = _static_room(room_to_static_maximum=Decimal("3000.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("600.00"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
        assert result.raw_increase_limit == Decimal("600.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_global_decimal_context_restored_after_raw_increase_limit_test():
    static_room = _static_room()
    raw_cap = _raw_cap()

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        resolve_campaign_raw_increase_limit(static_room, raw_cap)
        assert decimal.getcontext().prec == 5
        assert decimal.getcontext().rounding == decimal.ROUND_DOWN
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding
    assert decimal.getcontext().prec == original_prec
    assert decimal.getcontext().rounding == original_rounding


def test_extreme_already_valid_stage_10_and_stage_12_values_handled_safely():
    extreme_value = Decimal("9" * 26 + ".99")
    static_room = _static_room(
        room_to_static_maximum=extreme_value,
        room_to_static_minimum=Decimal("0.00"),
    )
    raw_cap = _raw_cap(raw_percentage_movement_cap=extreme_value)
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == extreme_value

    smaller_extreme = Decimal("9" * 25 + "8.99")
    raw_cap_smaller = _raw_cap(raw_percentage_movement_cap=smaller_extreme)
    result_smaller = resolve_campaign_raw_increase_limit(static_room, raw_cap_smaller)
    assert result_smaller.raw_increase_limit == smaller_extreme


# ---------------------------------------------------------------------------
# Stage 16 — authorised access
# ---------------------------------------------------------------------------


def test_raw_increase_limit_function_reads_only_four_authorised_fields():
    source = inspect.getsource(resolve_campaign_raw_increase_limit)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    static_room_param, raw_cap_param = (arg.arg for arg in func_def.args.args)
    assert static_room_param == "static_room"
    assert raw_cap_param == "raw_cap"

    static_room_attrs: set[str] = set()
    raw_cap_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == static_room_param:
                static_room_attrs.add(node.attr)
            elif node.value.id == raw_cap_param:
                raw_cap_attrs.add(node.attr)

    assert static_room_attrs == {"campaign_id", "room_to_static_maximum"}
    assert raw_cap_attrs == {"campaign_id", "raw_percentage_movement_cap"}


# ---------------------------------------------------------------------------
# Stage 16 — earlier-stage separation
# ---------------------------------------------------------------------------


def test_does_not_call_stage_10_stage_12_or_other_earlier_stage_functions():
    source = inspect.getsource(resolve_campaign_raw_increase_limit)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "calculate_campaign_static_budget_room",
        "calculate_campaign_raw_percentage_movement_cap",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_test_floor_room",
        "resolve_campaign_protection_constraint",
        "resolve_campaign_test_aware_static_decrease_room",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_raw_increase_limit_does_not_reference_campaign_input_or_review_setup():
    source = inspect.getsource(resolve_campaign_raw_increase_limit)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "CampaignInput" not in referenced_names
    assert "ReviewSetup" not in referenced_names
    assert "review" not in referenced_names
    assert "campaign" not in referenced_names


def test_stage_11_13_14_15_results_unused_in_raw_increase_limit():
    result = resolve_campaign_raw_increase_limit(_static_room(), _raw_cap())
    assert not hasattr(result, "applicable_max_change_percentage")
    assert not hasattr(result, "room_to_test_floor")
    assert not hasattr(result, "decrease_blocked")
    assert not hasattr(result, "test_aware_static_decrease_room")


# ---------------------------------------------------------------------------
# Stage 16 — protected/test independence
# ---------------------------------------------------------------------------


def test_protected_and_unprotected_source_campaigns_produce_identical_raw_increase_limit():
    unprotected_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=False,
    )
    protected_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=True,
    )
    percentage = _applicable_percentage(campaign_id="C001", applicable_max_change_percentage=Decimal("0.20"))

    result_unprotected = resolve_campaign_raw_increase_limit(
        calculate_campaign_static_budget_room(unprotected_campaign),
        calculate_campaign_raw_percentage_movement_cap(unprotected_campaign, percentage),
    )
    result_protected = resolve_campaign_raw_increase_limit(
        calculate_campaign_static_budget_room(protected_campaign),
        calculate_campaign_raw_percentage_movement_cap(protected_campaign, percentage),
    )
    assert result_unprotected.raw_increase_limit == result_protected.raw_increase_limit


def test_test_and_non_test_source_campaigns_produce_identical_raw_increase_limit():
    non_test_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=False,
        test_budget_floor=None,
    )
    test_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    percentage = _applicable_percentage(campaign_id="C001", applicable_max_change_percentage=Decimal("0.20"))

    result_non_test = resolve_campaign_raw_increase_limit(
        calculate_campaign_static_budget_room(non_test_campaign),
        calculate_campaign_raw_percentage_movement_cap(non_test_campaign, percentage),
    )
    result_test = resolve_campaign_raw_increase_limit(
        calculate_campaign_static_budget_room(test_campaign),
        calculate_campaign_raw_percentage_movement_cap(test_campaign, percentage),
    )
    assert result_non_test.raw_increase_limit == result_test.raw_increase_limit


def test_campaign_both_protected_and_test_produces_same_result_with_unchanged_stage_10_12_facts():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_protected=True,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    percentage = _applicable_percentage(
        campaign_id=campaign.campaign_id, applicable_max_change_percentage=Decimal("0.20")
    )
    static_room = calculate_campaign_static_budget_room(campaign)
    raw_cap = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit == min(
        static_room.room_to_static_maximum, raw_cap.raw_percentage_movement_cap
    )


def test_no_protection_or_test_floor_based_zero_introduced():
    campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_protected=True,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    percentage = _applicable_percentage(
        campaign_id=campaign.campaign_id, applicable_max_change_percentage=Decimal("0.20")
    )
    static_room = calculate_campaign_static_budget_room(campaign)
    raw_cap = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert result.raw_increase_limit != Decimal("0.00")


# ---------------------------------------------------------------------------
# Stage 16 — scope protection
# ---------------------------------------------------------------------------


def test_no_raw_decrease_combined_or_later_judgement_output():
    result = resolve_campaign_raw_increase_limit(_static_room(), _raw_cap())
    for attr in (
        "raw_decrease_limit",
        "test_aware_static_decrease_room",
        "decrease_blocked",
        "is_protected",
        "effective_increase",
        "permissible_increase",
        "eligibility",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
        "blocked",
    ):
        assert not hasattr(result, attr)


# ---------------------------------------------------------------------------
# Stage 16 — input contract
# ---------------------------------------------------------------------------


def test_raw_increase_limit_none_and_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_raw_increase_limit(None, None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        resolve_campaign_raw_increase_limit(  # type: ignore[arg-type]
            _static_room(), {"raw_percentage_movement_cap": Decimal("600.00"), "campaign_id": "C001"}
        )
    with pytest.raises(AttributeError):
        resolve_campaign_raw_increase_limit(  # type: ignore[arg-type]
            {"campaign_id": "C001", "room_to_static_maximum": Decimal("600.00")},
            _raw_cap(),
        )


# ---------------------------------------------------------------------------
# Stage 16 — sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_raw_increase_limit_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    static_rooms = {
        c.campaign_id: calculate_campaign_static_budget_room(c) for c in report.valid_campaigns
    }
    percentages = {
        c.campaign_id: resolve_campaign_applicable_change_percentage(review, c)
        for c in report.valid_campaigns
    }
    raw_caps = {
        c.campaign_id: calculate_campaign_raw_percentage_movement_cap(c, percentages[c.campaign_id])
        for c in report.valid_campaigns
    }
    results = [
        resolve_campaign_raw_increase_limit(static_rooms[c.campaign_id], raw_caps[c.campaign_id])
        for c in report.valid_campaigns
    ]
    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": Decimal("600.00"),
        "M001": Decimal("375.00"),
        "G002": Decimal("1000.00"),
        "G003": Decimal("240.00"),
    }
    for result in results:
        assert result.raw_increase_limit == expected[result.campaign_id]

    # Independently preserve and verify the existing Stage 10-15 sample outcomes -
    # never combined with Stage 16's result.
    expected_static_maximum = {
        "G001": Decimal("3000.00"),
        "M001": Decimal("2500.00"),
        "G002": Decimal("3000.00"),
        "G003": Decimal("800.00"),
    }
    for campaign_id, room in static_rooms.items():
        assert room.room_to_static_maximum == expected_static_maximum[campaign_id]

    for campaign_id, cap in raw_caps.items():
        assert cap.raw_percentage_movement_cap == expected[campaign_id]

    protection_results = {
        c.campaign_id: resolve_campaign_protection_constraint(c) for c in report.valid_campaigns
    }
    expected_decrease_blocked = {
        "G001": False,
        "M001": False,
        "G002": True,
        "G003": False,
    }
    for campaign_id, protection in protection_results.items():
        assert protection.decrease_blocked == expected_decrease_blocked[campaign_id]

    test_floor_rooms = {
        c.campaign_id: calculate_campaign_test_floor_room(c) for c in report.valid_campaigns
    }
    decrease_rooms = {
        c.campaign_id: resolve_campaign_test_aware_static_decrease_room(
            static_rooms[c.campaign_id], test_floor_rooms[c.campaign_id]
        )
        for c in report.valid_campaigns
    }
    expected_decrease_room = {
        "G001": Decimal("2500.00"),
        "M001": Decimal("2000.00"),
        "G002": Decimal("4000.00"),
        "G003": Decimal("900.00"),
    }
    for campaign_id, decrease_room in decrease_rooms.items():
        assert decrease_room.test_aware_static_decrease_room == expected_decrease_room[campaign_id]

    # G002: decrease_blocked=True and raw_increase_limit=1000.00 both hold
    # simultaneously and separately - never combined, and no increase-side
    # protection rule is inferred.
    assert protection_results["G002"].decrease_blocked is True
    g002_result = next(r for r in results if r.campaign_id == "G002")
    assert g002_result.raw_increase_limit == Decimal("1000.00")

    # G003: Stage 13/15 remain decrease-specific; Stage 16's raw_increase_limit
    # (240.00) is unaffected by the test floor.
    assert test_floor_rooms["G003"].room_to_test_floor == Decimal("900.00")
    assert decrease_rooms["G003"].test_aware_static_decrease_room == Decimal("900.00")
    g003_result = next(r for r in results if r.campaign_id == "G003")
    assert g003_result.raw_increase_limit == Decimal("240.00")


# ---------------------------------------------------------------------------
# Stage 17 — CampaignRawDecreaseLimit result model
# ---------------------------------------------------------------------------


def test_campaign_raw_decrease_limit_accepts_exactly_two_fields():
    assert set(CampaignRawDecreaseLimit.model_fields.keys()) == {
        "campaign_id",
        "raw_decrease_limit",
    }


def test_raw_decrease_limit_campaign_id_is_str_and_limit_is_decimal():
    result = resolve_campaign_raw_decrease_limit(_decrease_room(), _raw_cap())
    assert isinstance(result.campaign_id, str)
    assert isinstance(result.raw_decrease_limit, Decimal)


def test_campaign_raw_decrease_limit_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignRawDecreaseLimit(
            campaign_id="C001",
            raw_decrease_limit=Decimal("600.00"),
            extra_field="not allowed",
        )


def test_campaign_raw_decrease_limit_is_immutable():
    result = resolve_campaign_raw_decrease_limit(_decrease_room(), _raw_cap())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_raw_decrease_limit_has_no_optional_output():
    for field_info in CampaignRawDecreaseLimit.model_fields.values():
        assert field_info.is_required()


def test_raw_decrease_limit_has_no_increase_protection_eligibility_action_or_allocation_field():
    field_names = set(CampaignRawDecreaseLimit.model_fields.keys())
    forbidden = {
        "raw_increase_limit",
        "room_to_static_maximum",
        "room_to_static_minimum",
        "decrease_blocked",
        "is_protected",
        "effective_decrease",
        "permissible_decrease",
        "eligibility",
        "blocked",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Stage 17 — campaign identity
# ---------------------------------------------------------------------------


def test_matching_campaign_ids_preserve_campaign_id_exactly_stage17():
    result = resolve_campaign_raw_decrease_limit(
        _decrease_room(campaign_id="MATCH-1"), _raw_cap(campaign_id="MATCH-1")
    )
    assert result.campaign_id == "MATCH-1"


def test_raw_decrease_limit_mismatched_campaign_ids_raise_value_error_with_exact_message():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_raw_decrease_limit(
            _decrease_room(campaign_id="A"), _raw_cap(campaign_id="B")
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving raw decrease limit."
    )


def test_id_validation_occurs_before_decimal_selection_stage17():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
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


def test_neither_campaign_id_silently_preferred_after_mismatch_stage17():
    with pytest.raises(ValueError):
        resolve_campaign_raw_decrease_limit(
            _decrease_room(campaign_id="A"), _raw_cap(campaign_id="B")
        )


def test_no_result_returned_after_raw_decrease_limit_mismatch():
    try:
        resolve_campaign_raw_decrease_limit(
            _decrease_room(campaign_id="A"), _raw_cap(campaign_id="B")
        )
        assert False, "expected ValueError, no result should be returned"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Stage 17 — comparison
# ---------------------------------------------------------------------------


def test_decrease_room_smaller_returns_decrease_room():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("600.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("1000.00"))
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == Decimal("600.00")


def test_decrease_room_equal_to_raw_cap_returns_equal_value():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("800.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("800.00"))
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == Decimal("800.00")


def test_raw_cap_smaller_than_decrease_room_returns_raw_cap():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("3000.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("600.00"))
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == Decimal("600.00")


def test_decrease_room_zero_returns_zero():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("0.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("500.00"))
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == Decimal("0.00")


def test_raw_cap_zero_returns_zero_stage17():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("500.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("0.00"))
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == Decimal("0.00")


def test_both_values_zero_returns_zero_stage17():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("0.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("0.00"))
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == Decimal("0.00")


@pytest.mark.parametrize(
    "decrease_room_value, cap, expected",
    [
        (Decimal("600.00"), Decimal("1000.00"), Decimal("600.00")),
        (Decimal("800.00"), Decimal("800.00"), Decimal("800.00")),
        (Decimal("3000.00"), Decimal("600.00"), Decimal("600.00")),
        (Decimal("0.00"), Decimal("500.00"), Decimal("0.00")),
        (Decimal("500.00"), Decimal("0.00"), Decimal("0.00")),
    ],
)
def test_smaller_approved_operand_always_selected_stage17(decrease_room_value, cap, expected):
    decrease_room = _decrease_room(test_aware_static_decrease_room=decrease_room_value)
    raw_cap = _raw_cap(raw_percentage_movement_cap=cap)
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == expected
    assert result.raw_decrease_limit == min(decrease_room_value, cap)


def test_selected_decimal_operand_returned_unchanged_stage17():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("600.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("1000.00"))
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == decrease_room.test_aware_static_decrease_room


# ---------------------------------------------------------------------------
# Stage 17 — Decimal behaviour
# ---------------------------------------------------------------------------


def test_no_float_conversion_in_raw_decrease_limit():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    assert "float(" not in source


def test_no_arithmetic_rounding_or_quantisation_in_raw_decrease_limit():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    assert "quantize" not in source
    assert "ROUND_HALF_UP" not in source
    assert "CURRENCY_QUANTUM" not in source
    assert "localcontext" not in source
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BinOp) for node in ast.walk(tree))


def test_mutated_global_decimal_precision_does_not_affect_raw_decrease_limit():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("600.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("1000.00"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
        assert result.raw_decrease_limit == Decimal("600.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_mutated_global_decimal_rounding_does_not_affect_raw_decrease_limit():
    decrease_room = _decrease_room(test_aware_static_decrease_room=Decimal("3000.00"))
    raw_cap = _raw_cap(raw_percentage_movement_cap=Decimal("600.00"))

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
        assert result.raw_decrease_limit == Decimal("600.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_global_decimal_context_restored_after_raw_decrease_limit_test():
    decrease_room = _decrease_room()
    raw_cap = _raw_cap()

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
        assert decimal.getcontext().prec == 5
        assert decimal.getcontext().rounding == decimal.ROUND_DOWN
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding
    assert decimal.getcontext().prec == original_prec
    assert decimal.getcontext().rounding == original_rounding


def test_extreme_already_valid_stage_12_and_stage_15_values_handled_safely():
    extreme_value = Decimal("9" * 26 + ".99")
    decrease_room = _decrease_room(test_aware_static_decrease_room=extreme_value)
    raw_cap = _raw_cap(raw_percentage_movement_cap=extreme_value)
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == extreme_value

    smaller_extreme = Decimal("9" * 25 + "8.99")
    raw_cap_smaller = _raw_cap(raw_percentage_movement_cap=smaller_extreme)
    result_smaller = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap_smaller)
    assert result_smaller.raw_decrease_limit == smaller_extreme


# ---------------------------------------------------------------------------
# Stage 17 — authorised access
# ---------------------------------------------------------------------------


def test_raw_decrease_limit_function_reads_only_four_authorised_fields():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    decrease_room_param, raw_cap_param = (arg.arg for arg in func_def.args.args)
    assert decrease_room_param == "decrease_room"
    assert raw_cap_param == "raw_cap"

    decrease_room_attrs: set[str] = set()
    raw_cap_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == decrease_room_param:
                decrease_room_attrs.add(node.attr)
            elif node.value.id == raw_cap_param:
                raw_cap_attrs.add(node.attr)

    assert decrease_room_attrs == {"campaign_id", "test_aware_static_decrease_room"}
    assert raw_cap_attrs == {"campaign_id", "raw_percentage_movement_cap"}


# ---------------------------------------------------------------------------
# Stage 17 — earlier-stage separation
# ---------------------------------------------------------------------------


def test_does_not_call_stage_12_stage_15_or_other_earlier_stage_functions():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "resolve_campaign_test_aware_static_decrease_room",
        "calculate_campaign_raw_percentage_movement_cap",
        "calculate_campaign_static_budget_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_test_floor_room",
        "resolve_campaign_protection_constraint",
        "resolve_campaign_raw_increase_limit",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_raw_decrease_limit_does_not_reference_campaign_input_or_review_setup():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "CampaignInput" not in referenced_names
    assert "ReviewSetup" not in referenced_names
    assert "review" not in referenced_names
    assert "campaign" not in referenced_names


def test_stage_10_11_13_14_16_results_unused_in_raw_decrease_limit():
    result = resolve_campaign_raw_decrease_limit(_decrease_room(), _raw_cap())
    assert not hasattr(result, "room_to_static_maximum")
    assert not hasattr(result, "room_to_static_minimum")
    assert not hasattr(result, "applicable_max_change_percentage")
    assert not hasattr(result, "room_to_test_floor")
    assert not hasattr(result, "decrease_blocked")
    assert not hasattr(result, "raw_increase_limit")


def test_raw_decrease_limit_function_does_not_reopen_minimum_budget_or_test_floor_fields():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    assert "minimum_budget" not in source
    assert "test_budget_floor" not in source
    assert "is_test_campaign" not in source
    assert "room_to_static_minimum" not in source
    assert "room_to_test_floor" not in source
    assert "current_budget" not in source
    assert "applicable_max_change_percentage" not in source


# ---------------------------------------------------------------------------
# Stage 17 — protection independence
# ---------------------------------------------------------------------------


def test_protected_and_unprotected_source_campaigns_produce_identical_raw_decrease_limit():
    unprotected_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=False,
    )
    protected_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=True,
    )
    percentage = _applicable_percentage(campaign_id="C001", applicable_max_change_percentage=Decimal("0.20"))

    def _stage17_for(campaign: CampaignInput) -> CampaignRawDecreaseLimit:
        static_room = calculate_campaign_static_budget_room(campaign)
        test_floor_room = calculate_campaign_test_floor_room(campaign)
        decrease_room = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
        raw_cap = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
        return resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)

    result_unprotected = _stage17_for(unprotected_campaign)
    result_protected = _stage17_for(protected_campaign)
    assert result_unprotected.raw_decrease_limit == result_protected.raw_decrease_limit


def test_protected_campaign_still_receives_neutral_raw_decrease_limit():
    protected_campaign = _campaign(
        current_budget=5000,
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=True,
    )
    percentage = _applicable_percentage(
        campaign_id=protected_campaign.campaign_id,
        applicable_max_change_percentage=Decimal("0.20"),
    )
    static_room = calculate_campaign_static_budget_room(protected_campaign)
    test_floor_room = calculate_campaign_test_floor_room(protected_campaign)
    decrease_room = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    raw_cap = calculate_campaign_raw_percentage_movement_cap(protected_campaign, percentage)
    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    assert result.raw_decrease_limit == min(
        decrease_room.test_aware_static_decrease_room, raw_cap.raw_percentage_movement_cap
    )
    assert result.raw_decrease_limit != Decimal("0.00")


def test_decrease_blocked_and_is_protected_never_read_in_raw_decrease_limit_source():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    assert "decrease_blocked" not in source
    assert "is_protected" not in source


def test_protection_never_converts_raw_decrease_limit_to_zero():
    campaign = _campaign(
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=True,
    )
    percentage = _applicable_percentage(
        campaign_id=campaign.campaign_id, applicable_max_change_percentage=Decimal("0.20")
    )
    static_room = calculate_campaign_static_budget_room(campaign)
    test_floor_room = calculate_campaign_test_floor_room(campaign)
    decrease_room = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    raw_cap = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
    protection = resolve_campaign_protection_constraint(campaign)

    result = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)

    assert protection.decrease_blocked is True
    assert result.raw_decrease_limit == Decimal("1000.00")


# ---------------------------------------------------------------------------
# Stage 17 — test-campaign ownership
# ---------------------------------------------------------------------------


def test_test_status_affects_stage17_only_through_stage15_result():
    non_test_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=False,
        test_budget_floor=None,
    )
    test_campaign = _campaign(
        campaign_id="C001",
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    percentage = _applicable_percentage(campaign_id="C001", applicable_max_change_percentage=Decimal("0.20"))

    def _stage15_and_stage17(campaign: CampaignInput):
        static_room = calculate_campaign_static_budget_room(campaign)
        test_floor_room = calculate_campaign_test_floor_room(campaign)
        decrease_room = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
        raw_cap = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
        return decrease_room, resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)

    non_test_decrease_room, non_test_result = _stage15_and_stage17(non_test_campaign)
    test_decrease_room, test_result = _stage15_and_stage17(test_campaign)

    # Test status changes Stage 15's result (900.00 vs 1100.00), which Stage 17
    # then intersects with the raw cap - Stage 17 itself never reads
    # is_test_campaign/test_budget_floor directly.
    assert non_test_decrease_room.test_aware_static_decrease_room == Decimal("1100.00")
    assert test_decrease_room.test_aware_static_decrease_room == Decimal("900.00")
    assert non_test_result.raw_decrease_limit == min(Decimal("1100.00"), Decimal("240.00"))
    assert test_result.raw_decrease_limit == min(Decimal("900.00"), Decimal("240.00"))


def test_raw_decrease_limit_does_not_accept_or_call_stage13():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    tree = ast.parse(source)
    func_def = tree.body[0]
    param_names = {arg.arg for arg in func_def.args.args}
    assert "campaign" not in param_names
    assert "calculate_campaign_test_floor_room" not in source


def test_raw_decrease_limit_does_not_reopen_stage15_precedence():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    assert "min(" in source
    # Only one min() call site is present (the Stage 17 formula itself) -
    # Stage 15's own min(room_to_static_minimum, room_to_test_floor) precedence
    # is not reimplemented here.
    tree = ast.parse(source)
    min_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "min"
    ]
    assert len(min_calls) == 1


# ---------------------------------------------------------------------------
# Stage 17 — Stage 16 separation
# ---------------------------------------------------------------------------


def test_raw_decrease_limit_does_not_accept_campaign_raw_increase_limit():
    source = inspect.getsource(resolve_campaign_raw_decrease_limit)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "CampaignRawIncreaseLimit" not in referenced_names
    assert "raw_increase_limit" not in referenced_names
    assert "resolve_campaign_raw_increase_limit" not in referenced_names


def test_no_combined_directional_result_model_created():
    field_names = set(CampaignRawDecreaseLimit.model_fields.keys())
    assert "raw_increase_limit" not in field_names


# ---------------------------------------------------------------------------
# Stage 17 — scope protection
# ---------------------------------------------------------------------------


def test_no_raw_increase_effective_or_later_judgement_output_stage17():
    result = resolve_campaign_raw_decrease_limit(_decrease_room(), _raw_cap())
    for attr in (
        "raw_increase_limit",
        "room_to_static_maximum",
        "decrease_blocked",
        "is_protected",
        "effective_decrease",
        "permissible_decrease",
        "eligibility",
        "score",
        "recommendation_action",
        "reason_code",
        "allocation",
        "conservation",
        "blocked",
    ):
        assert not hasattr(result, attr)


# ---------------------------------------------------------------------------
# Stage 17 — input contract
# ---------------------------------------------------------------------------


def test_raw_decrease_limit_none_and_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_raw_decrease_limit(None, None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        resolve_campaign_raw_decrease_limit(  # type: ignore[arg-type]
            _decrease_room(), {"raw_percentage_movement_cap": Decimal("600.00"), "campaign_id": "C001"}
        )
    with pytest.raises(AttributeError):
        resolve_campaign_raw_decrease_limit(  # type: ignore[arg-type]
            {"campaign_id": "C001", "test_aware_static_decrease_room": Decimal("600.00")},
            _raw_cap(),
        )


# ---------------------------------------------------------------------------
# Stage 17 — sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_raw_decrease_limit_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    static_rooms = {
        c.campaign_id: calculate_campaign_static_budget_room(c) for c in report.valid_campaigns
    }
    percentages = {
        c.campaign_id: resolve_campaign_applicable_change_percentage(review, c)
        for c in report.valid_campaigns
    }
    raw_caps = {
        c.campaign_id: calculate_campaign_raw_percentage_movement_cap(c, percentages[c.campaign_id])
        for c in report.valid_campaigns
    }
    test_floor_rooms = {
        c.campaign_id: calculate_campaign_test_floor_room(c) for c in report.valid_campaigns
    }
    decrease_rooms = {
        c.campaign_id: resolve_campaign_test_aware_static_decrease_room(
            static_rooms[c.campaign_id], test_floor_rooms[c.campaign_id]
        )
        for c in report.valid_campaigns
    }
    protection_results = {
        c.campaign_id: resolve_campaign_protection_constraint(c) for c in report.valid_campaigns
    }
    increase_results = {
        c.campaign_id: resolve_campaign_raw_increase_limit(
            static_rooms[c.campaign_id], raw_caps[c.campaign_id]
        )
        for c in report.valid_campaigns
    }

    results = [
        resolve_campaign_raw_decrease_limit(decrease_rooms[c.campaign_id], raw_caps[c.campaign_id])
        for c in report.valid_campaigns
    ]
    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": Decimal("600.00"),
        "M001": Decimal("375.00"),
        "G002": Decimal("1000.00"),
        "G003": Decimal("240.00"),
    }
    for result in results:
        assert result.raw_decrease_limit == expected[result.campaign_id]

    # Independently preserve and verify existing Stage 10-16 sample outcomes -
    # never combined with Stage 17's result.
    expected_decrease_room = {
        "G001": Decimal("2500.00"),
        "M001": Decimal("2000.00"),
        "G002": Decimal("4000.00"),
        "G003": Decimal("900.00"),
    }
    for campaign_id, decrease_room in decrease_rooms.items():
        assert decrease_room.test_aware_static_decrease_room == expected_decrease_room[campaign_id]

    expected_decrease_blocked = {
        "G001": False,
        "M001": False,
        "G002": True,
        "G003": False,
    }
    for campaign_id, protection in protection_results.items():
        assert protection.decrease_blocked == expected_decrease_blocked[campaign_id]

    for campaign_id, cap in raw_caps.items():
        assert cap.raw_percentage_movement_cap == expected[campaign_id]

    for campaign_id, increase_result in increase_results.items():
        assert increase_result.raw_increase_limit == expected[campaign_id]

    # G002: decrease_blocked=True and raw_decrease_limit=1000.00 both hold
    # simultaneously and separately - never combined, and Decimal("1000.00") is
    # never described as permissible decrease.
    assert protection_results["G002"].decrease_blocked is True
    g002_result = next(r for r in results if r.campaign_id == "G002")
    assert g002_result.raw_decrease_limit == Decimal("1000.00")

    # G003: Stage 13's room_to_test_floor (900.00) and Stage 15's
    # test_aware_static_decrease_room (900.00) remain unaltered; Stage 17's
    # raw_decrease_limit (240.00) is bound by the percentage cap - the test-floor
    # rule is not reopened or recalculated.
    assert test_floor_rooms["G003"].room_to_test_floor == Decimal("900.00")
    assert decrease_rooms["G003"].test_aware_static_decrease_room == Decimal("900.00")
    g003_result = next(r for r in results if r.campaign_id == "G003")
    assert g003_result.raw_decrease_limit == Decimal("240.00")


# ---------------------------------------------------------------------------
# Stage 18 — CampaignEffectiveDecreaseLimit result model
# ---------------------------------------------------------------------------


def test_campaign_effective_decrease_limit_accepts_exactly_two_fields():
    assert set(CampaignEffectiveDecreaseLimit.model_fields.keys()) == {
        "campaign_id",
        "effective_decrease_limit",
    }


def test_effective_decrease_limit_campaign_id_is_str_and_limit_is_decimal():
    result = resolve_campaign_effective_decrease_limit(_raw_decrease(), _protection())
    assert isinstance(result.campaign_id, str)
    assert isinstance(result.effective_decrease_limit, Decimal)


def test_campaign_effective_decrease_limit_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignEffectiveDecreaseLimit(
            campaign_id="C001",
            effective_decrease_limit=Decimal("600.00"),
            extra_field="not allowed",
        )


def test_campaign_effective_decrease_limit_is_immutable():
    result = resolve_campaign_effective_decrease_limit(_raw_decrease(), _protection())
    with pytest.raises(ValidationError):
        result.campaign_id = "C002"


def test_effective_decrease_limit_does_not_repeat_raw_decrease_limit_field():
    assert "raw_decrease_limit" not in CampaignEffectiveDecreaseLimit.model_fields


def test_effective_decrease_limit_does_not_repeat_decrease_blocked_field():
    assert "decrease_blocked" not in CampaignEffectiveDecreaseLimit.model_fields


def test_effective_decrease_limit_has_no_increase_eligibility_action_score_or_allocation_field():
    field_names = set(CampaignEffectiveDecreaseLimit.model_fields.keys())
    forbidden = {
        "raw_increase_limit",
        "effective_increase_limit",
        "raw_decrease_limit",
        "decrease_blocked",
        "is_protected",
        "eligibility",
        "eligible",
        "action",
        "recommendation_action",
        "reason_code",
        "score",
        "allocation",
        "conservation",
        "blocked",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Stage 18 — campaign identity
# ---------------------------------------------------------------------------


def test_matching_campaign_ids_preserve_campaign_id_exactly_stage18():
    result = resolve_campaign_effective_decrease_limit(
        _raw_decrease(campaign_id="MATCH-1"), _protection(campaign_id="MATCH-1")
    )
    assert result.campaign_id == "MATCH-1"


def test_effective_decrease_limit_mismatched_campaign_ids_raise_value_error_with_exact_message():
    with pytest.raises(ValueError) as exc_info:
        resolve_campaign_effective_decrease_limit(
            _raw_decrease(campaign_id="A"), _protection(campaign_id="B")
        )
    assert (
        str(exc_info.value)
        == "Campaign IDs must match when resolving effective decrease limit."
    )


def test_id_validation_occurs_before_boolean_and_decimal_selection_stage18():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
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


def test_neither_campaign_id_silently_preferred_after_mismatch_stage18():
    with pytest.raises(ValueError):
        resolve_campaign_effective_decrease_limit(
            _raw_decrease(campaign_id="A"), _protection(campaign_id="B")
        )


def test_no_result_returned_after_effective_decrease_limit_mismatch():
    try:
        resolve_campaign_effective_decrease_limit(
            _raw_decrease(campaign_id="A"), _protection(campaign_id="B")
        )
        assert False, "expected ValueError, no result should be returned"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Stage 18 — Boolean mapping
# ---------------------------------------------------------------------------


def test_protected_positive_raw_value_returns_zero():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == Decimal("0.00")


def test_unprotected_positive_raw_value_returns_raw_value_unchanged():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=False)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == Decimal("600.00")


def test_protected_zero_raw_value_returns_zero():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("0.00"))
    protection = _protection(decrease_blocked=True)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == Decimal("0.00")


def test_unprotected_zero_raw_value_returns_existing_zero_unchanged():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("0.00"))
    protection = _protection(decrease_blocked=False)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == Decimal("0.00")


@pytest.mark.parametrize("decrease_blocked", [True, False])
def test_true_and_false_behaviours_are_exhaustive(decrease_blocked):
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("750.00"))
    protection = _protection(decrease_blocked=decrease_blocked)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    if decrease_blocked:
        assert result.effective_decrease_limit == Decimal("0.00")
    else:
        assert result.effective_decrease_limit == Decimal("750.00")


def test_no_truthiness_fallback_changes_approved_boolean_meaning():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BoolOp) for node in ast.walk(tree))


# ---------------------------------------------------------------------------
# Stage 18 — exact zero representation
# ---------------------------------------------------------------------------


def test_protected_result_has_same_tuple_as_decimal_zero_dot_zero_zero():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit.as_tuple() == Decimal("0.00").as_tuple()


def test_protected_result_does_not_use_decimal_zero_without_exponent():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit.as_tuple() != Decimal("0").as_tuple()


def test_protected_result_is_never_none():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit is not None


def test_protected_campaign_does_not_raise():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == Decimal("0.00")


# ---------------------------------------------------------------------------
# Stage 18 — Decimal behaviour
# ---------------------------------------------------------------------------


def test_no_float_conversion_in_effective_decrease_limit():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
    assert "float(" not in source


def test_no_arithmetic_rounding_or_quantisation_in_effective_decrease_limit():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
    assert "quantize" not in source
    assert "ROUND_HALF_UP" not in source
    assert "CURRENCY_QUANTUM" not in source
    assert "localcontext" not in source
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.BinOp) for node in ast.walk(tree))


def test_unprotected_operand_returned_unchanged():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=False)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == raw_decrease.raw_decrease_limit


def test_mutated_global_decimal_precision_does_not_affect_effective_decrease_limit():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=False)

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 2
        result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
        assert result.effective_decrease_limit == Decimal("600.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_mutated_global_decimal_rounding_does_not_affect_protected_branch():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
        assert result.effective_decrease_limit == Decimal("0.00")
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding


def test_global_decimal_context_restored_after_effective_decrease_limit_test():
    raw_decrease = _raw_decrease()
    protection = _protection()

    original_prec = decimal.getcontext().prec
    original_rounding = decimal.getcontext().rounding
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_DOWN
        resolve_campaign_effective_decrease_limit(raw_decrease, protection)
        assert decimal.getcontext().prec == 5
        assert decimal.getcontext().rounding == decimal.ROUND_DOWN
    finally:
        decimal.getcontext().prec = original_prec
        decimal.getcontext().rounding = original_rounding
    assert decimal.getcontext().prec == original_prec
    assert decimal.getcontext().rounding == original_rounding


def test_extreme_valid_raw_decrease_value_unchanged_when_unprotected():
    extreme_value = Decimal("9" * 26 + ".99")
    raw_decrease = _raw_decrease(raw_decrease_limit=extreme_value)
    protection = _protection(decrease_blocked=False)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == extreme_value


def test_extreme_valid_raw_decrease_value_becomes_zero_when_protected():
    extreme_value = Decimal("9" * 26 + ".99")
    raw_decrease = _raw_decrease(raw_decrease_limit=extreme_value)
    protection = _protection(decrease_blocked=True)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == Decimal("0.00")


# ---------------------------------------------------------------------------
# Stage 18 — authorised access
# ---------------------------------------------------------------------------


def test_effective_decrease_limit_function_reads_only_four_authorised_fields():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    raw_decrease_param, protection_param = (arg.arg for arg in func_def.args.args)
    assert raw_decrease_param == "raw_decrease"
    assert protection_param == "protection"

    raw_decrease_attrs: set[str] = set()
    protection_attrs: set[str] = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == raw_decrease_param:
                raw_decrease_attrs.add(node.attr)
            elif node.value.id == protection_param:
                protection_attrs.add(node.attr)

    assert raw_decrease_attrs == {"campaign_id", "raw_decrease_limit"}
    assert protection_attrs == {"campaign_id", "decrease_blocked"}


# ---------------------------------------------------------------------------
# Stage 18 — earlier-stage separation
# ---------------------------------------------------------------------------


def test_does_not_call_stage_14_stage_17_or_other_earlier_stage_functions():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "resolve_campaign_protection_constraint",
        "resolve_campaign_raw_decrease_limit",
        "calculate_campaign_static_budget_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_raw_percentage_movement_cap",
        "calculate_campaign_test_floor_room",
        "resolve_campaign_test_aware_static_decrease_room",
        "resolve_campaign_raw_increase_limit",
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "classify_campaign_pacing",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_effective_decrease_limit_does_not_reference_campaign_input_or_review_setup():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "CampaignInput" not in referenced_names
    assert "ReviewSetup" not in referenced_names
    assert "review" not in referenced_names
    assert "campaign" not in referenced_names


def test_effective_decrease_limit_does_not_reopen_upstream_fields():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
    assert "is_protected" not in source
    assert "current_budget" not in source
    assert "minimum_budget" not in source
    assert "maximum_budget" not in source
    assert "test_budget_floor" not in source
    assert "is_test_campaign" not in source
    assert "applicable_max_change_percentage" not in source
    assert "room_to_static_minimum" not in source
    assert "room_to_test_floor" not in source
    assert "test_aware_static_decrease_room" not in source
    assert "raw_percentage_movement_cap" not in source


def test_stage_10_11_12_13_15_16_results_unused_in_effective_decrease_limit():
    result = resolve_campaign_effective_decrease_limit(_raw_decrease(), _protection())
    assert not hasattr(result, "room_to_static_maximum")
    assert not hasattr(result, "room_to_static_minimum")
    assert not hasattr(result, "applicable_max_change_percentage")
    assert not hasattr(result, "raw_percentage_movement_cap")
    assert not hasattr(result, "room_to_test_floor")
    assert not hasattr(result, "test_aware_static_decrease_room")
    assert not hasattr(result, "raw_increase_limit")


# ---------------------------------------------------------------------------
# Stage 18 — increase-side separation
# ---------------------------------------------------------------------------


def test_effective_decrease_limit_does_not_accept_campaign_raw_increase_limit():
    source = inspect.getsource(resolve_campaign_effective_decrease_limit)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "CampaignRawIncreaseLimit" not in referenced_names
    assert "raw_increase_limit" not in referenced_names
    assert "resolve_campaign_raw_increase_limit" not in referenced_names


def test_no_effective_increase_limit_field_or_model_exists():
    assert "effective_increase_limit" not in CampaignEffectiveDecreaseLimit.model_fields
    import src.constraints as constraints_module

    assert not hasattr(constraints_module, "CampaignEffectiveIncreaseLimit")
    assert not hasattr(constraints_module, "resolve_campaign_effective_increase_limit")


def test_protected_status_given_no_increase_side_meaning():
    protected_campaign = _campaign(
        current_budget=Decimal("5000.00"),
        minimum_budget=Decimal("1000.00"),
        maximum_budget=Decimal("8000.00"),
        spend_to_date=Decimal("4950.00"),
        is_protected=True,
    )
    percentage = _applicable_percentage(
        campaign_id=protected_campaign.campaign_id,
        applicable_max_change_percentage=Decimal("0.20"),
    )
    static_room = calculate_campaign_static_budget_room(protected_campaign)
    raw_cap = calculate_campaign_raw_percentage_movement_cap(protected_campaign, percentage)
    increase_result = resolve_campaign_raw_increase_limit(static_room, raw_cap)
    assert increase_result.raw_increase_limit == min(
        static_room.room_to_static_maximum, raw_cap.raw_percentage_movement_cap
    )


def test_no_combined_directional_result_created():
    field_names = set(CampaignEffectiveDecreaseLimit.model_fields.keys())
    assert "raw_increase_limit" not in field_names
    assert "effective_increase_limit" not in field_names


# ---------------------------------------------------------------------------
# Stage 18 — traceability
# ---------------------------------------------------------------------------


def test_stage14_boolean_remains_preserved_separately():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert protection.decrease_blocked is True


def test_stage17_raw_decimal_remains_preserved_separately():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert raw_decrease.raw_decrease_limit == Decimal("600.00")


def test_resolving_effective_decrease_limit_does_not_mutate_either_input():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    with pytest.raises(ValidationError):
        raw_decrease.raw_decrease_limit = Decimal("999.00")
    with pytest.raises(ValidationError):
        protection.decrease_blocked = False


# ---------------------------------------------------------------------------
# Stage 18 — eligibility boundary
# ---------------------------------------------------------------------------


def test_no_eligible_or_ineligible_output():
    result = resolve_campaign_effective_decrease_limit(_raw_decrease(), _protection())
    assert not hasattr(result, "eligible")
    assert not hasattr(result, "ineligible")
    assert not hasattr(result, "eligibility")


def test_zero_effective_decrease_does_not_imply_whole_campaign_ineligibility():
    raw_decrease = _raw_decrease(raw_decrease_limit=Decimal("600.00"))
    protection = _protection(decrease_blocked=True)
    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == Decimal("0.00")
    # No eligibility field exists anywhere on the result - a zero
    # effective_decrease_limit says only that no decrease room remains; it
    # says nothing about MAINTAIN or INCREASE eligibility.
    assert set(CampaignEffectiveDecreaseLimit.model_fields.keys()) == {
        "campaign_id",
        "effective_decrease_limit",
    }


def test_no_recommendation_action_reason_code_score_or_allocation_output():
    result = resolve_campaign_effective_decrease_limit(_raw_decrease(), _protection())
    for attr in (
        "recommendation_action",
        "reason_code",
        "score",
        "prioritisation",
        "allocation",
        "conservation",
    ):
        assert not hasattr(result, attr)


# ---------------------------------------------------------------------------
# Stage 18 — input contract
# ---------------------------------------------------------------------------


def test_effective_decrease_limit_none_and_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        resolve_campaign_effective_decrease_limit(None, None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        resolve_campaign_effective_decrease_limit(  # type: ignore[arg-type]
            _raw_decrease(), {"decrease_blocked": True, "campaign_id": "C001"}
        )
    with pytest.raises(AttributeError):
        resolve_campaign_effective_decrease_limit(  # type: ignore[arg-type]
            {"campaign_id": "C001", "raw_decrease_limit": Decimal("600.00")},
            _protection(),
        )


def test_no_production_batch_function_for_effective_decrease_limit():
    import src.constraints as constraints_module

    assert not hasattr(constraints_module, "resolve_campaign_effective_decrease_limits")
    assert not hasattr(constraints_module, "calculate_effective_decrease_limits")


# ---------------------------------------------------------------------------
# Stage 18 — protected test campaign
# ---------------------------------------------------------------------------


def test_protected_test_campaign_produces_zero_effective_decrease_limit():
    protected_test_campaign = _campaign(
        current_budget=Decimal("1200.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("300.00"),
        is_protected=True,
        is_test_campaign=True,
        test_budget_floor=Decimal("300.00"),
    )
    percentage = _applicable_percentage(
        campaign_id=protected_test_campaign.campaign_id,
        applicable_max_change_percentage=Decimal("0.20"),
    )
    static_room = calculate_campaign_static_budget_room(protected_test_campaign)
    test_floor_room = calculate_campaign_test_floor_room(protected_test_campaign)
    decrease_room = resolve_campaign_test_aware_static_decrease_room(static_room, test_floor_room)
    raw_cap = calculate_campaign_raw_percentage_movement_cap(protected_test_campaign, percentage)
    raw_decrease = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
    protection = resolve_campaign_protection_constraint(protected_test_campaign)

    assert protection.decrease_blocked is True
    assert raw_decrease.raw_decrease_limit == min(
        decrease_room.test_aware_static_decrease_room, raw_cap.raw_percentage_movement_cap
    )

    result = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
    assert result.effective_decrease_limit == Decimal("0.00")
    # Raw value remains independently approved and unaltered - not recalculated
    # inside Stage 18.
    assert raw_decrease.raw_decrease_limit != Decimal("0.00")


# ---------------------------------------------------------------------------
# Stage 18 — sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_effective_decrease_limit_exact_values_and_order():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    static_rooms = {
        c.campaign_id: calculate_campaign_static_budget_room(c) for c in report.valid_campaigns
    }
    percentages = {
        c.campaign_id: resolve_campaign_applicable_change_percentage(review, c)
        for c in report.valid_campaigns
    }
    raw_caps = {
        c.campaign_id: calculate_campaign_raw_percentage_movement_cap(c, percentages[c.campaign_id])
        for c in report.valid_campaigns
    }
    test_floor_rooms = {
        c.campaign_id: calculate_campaign_test_floor_room(c) for c in report.valid_campaigns
    }
    decrease_rooms = {
        c.campaign_id: resolve_campaign_test_aware_static_decrease_room(
            static_rooms[c.campaign_id], test_floor_rooms[c.campaign_id]
        )
        for c in report.valid_campaigns
    }
    protection_results = {
        c.campaign_id: resolve_campaign_protection_constraint(c) for c in report.valid_campaigns
    }
    increase_results = {
        c.campaign_id: resolve_campaign_raw_increase_limit(
            static_rooms[c.campaign_id], raw_caps[c.campaign_id]
        )
        for c in report.valid_campaigns
    }
    raw_decrease_results = {
        c.campaign_id: resolve_campaign_raw_decrease_limit(
            decrease_rooms[c.campaign_id], raw_caps[c.campaign_id]
        )
        for c in report.valid_campaigns
    }

    results = [
        resolve_campaign_effective_decrease_limit(
            raw_decrease_results[c.campaign_id], protection_results[c.campaign_id]
        )
        for c in report.valid_campaigns
    ]
    assert [r.campaign_id for r in results] == ["G001", "M001", "G002", "G003"]

    expected = {
        "G001": Decimal("600.00"),
        "M001": Decimal("375.00"),
        "G002": Decimal("0.00"),
        "G003": Decimal("240.00"),
    }
    for result in results:
        assert result.effective_decrease_limit == expected[result.campaign_id]

    # Independently preserve and verify existing Stage 10-17 sample outcomes -
    # never combined with Stage 18's result.
    expected_raw_decrease = {
        "G001": Decimal("600.00"),
        "M001": Decimal("375.00"),
        "G002": Decimal("1000.00"),
        "G003": Decimal("240.00"),
    }
    for campaign_id, raw_result in raw_decrease_results.items():
        assert raw_result.raw_decrease_limit == expected_raw_decrease[campaign_id]

    expected_decrease_blocked = {
        "G001": False,
        "M001": False,
        "G002": True,
        "G003": False,
    }
    for campaign_id, protection in protection_results.items():
        assert protection.decrease_blocked == expected_decrease_blocked[campaign_id]

    for campaign_id, increase_result in increase_results.items():
        assert increase_result.raw_increase_limit == expected_raw_decrease[campaign_id]

    # G002: decrease_blocked=True, raw_decrease_limit=1000.00, and
    # effective_decrease_limit=0.00 all hold simultaneously and separately.
    # Stage 17 remains unchanged; no increase-side rule is applied; zero is not
    # described as whole-campaign ineligibility.
    assert protection_results["G002"].decrease_blocked is True
    assert raw_decrease_results["G002"].raw_decrease_limit == Decimal("1000.00")
    g002_result = next(r for r in results if r.campaign_id == "G002")
    assert g002_result.effective_decrease_limit == Decimal("0.00")
    assert increase_results["G002"].raw_increase_limit == Decimal("1000.00")

    # G003: test campaign, unprotected. raw_decrease_limit=240.00 passes through
    # unchanged; Stage 15's test-floor logic is not reopened.
    assert protection_results["G003"].decrease_blocked is False
    assert raw_decrease_results["G003"].raw_decrease_limit == Decimal("240.00")
    g003_result = next(r for r in results if r.campaign_id == "G003")
    assert g003_result.effective_decrease_limit == Decimal("240.00")
