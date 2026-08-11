"""Tests for src.constraints (Sprint 1 — Development Stages 10 and 11).

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
"""

import ast
import decimal
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.constants import BusinessPriority, CampaignStatus, KPIType, Platform, TrackingStatus
from src.constraints import (
    CampaignApplicableChangePercentage,
    CampaignStaticBudgetRoom,
    calculate_campaign_static_budget_room,
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
