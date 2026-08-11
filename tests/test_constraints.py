"""Tests for src.constraints (Sprint 1 — Development Stages 10, 11, 12, and 13).

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
    CampaignRawPercentageMovementCap,
    CampaignStaticBudgetRoom,
    CampaignTestFloorRoom,
    calculate_campaign_raw_percentage_movement_cap,
    calculate_campaign_static_budget_room,
    calculate_campaign_test_floor_room,
    resolve_campaign_applicable_change_percentage,
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
