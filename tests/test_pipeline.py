"""Tests for src.pipeline (Sprint 1 — Development Stage 27).

Covers CampaignBudgetRecommendationResult/BudgetReallocationReviewResult
construction, immutability, and validation; the exact real
Stage 1-26 sample-data result; a balanced non-zero allocation where final
budgets change and portfolio totals remain equal; directional
zero-allocation recommendations retaining their action; HOLD/MAINTAIN
producing zero movement; optional-rank behavior; empty-portfolio
handling; original input-order preservation; ID-based matching; Decimal-
context correctness immune to hostile ambient precision/rounding; extreme
budget magnitudes; the conservation and total-budget invariants; input/
upstream-object immutability; fail-fast exception propagation; and
isolation from AI/UI/approval/audit/export/CSV-reading/validation logic
and from any duplicated Stage 1-26 formula.
"""

import ast
import inspect
from datetime import date
from decimal import Decimal, getcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.classification import PerformanceBand, TrendDirection
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
from src.models import CampaignInput, ReviewSetup
from src.pacing import PacingStatus
from src.pipeline import (
    BudgetReallocationReviewResult,
    CampaignBudgetRecommendationResult,
    run_budget_reallocation_review,
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
        default_max_change_percentage=Decimal("0.20"),
    )
    kwargs.update(overrides)
    return ReviewSetup(**kwargs)


def _sample_result() -> BudgetReallocationReviewResult:
    review = _review()
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    return run_budget_reallocation_review(review, tuple(report.valid_campaigns))


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


def test_campaign_result_field_shape():
    assert set(CampaignBudgetRecommendationResult.model_fields.keys()) == {
        "campaign_id",
        "campaign_name",
        "platform",
        "current_budget",
        "recommendation_action",
        "allocated_amount",
        "recommended_budget",
        "reason_codes",
        "performance_band",
        "trend_direction",
        "confidence",
        "pacing_status",
        "reallocation_priority_score",
        "rank",
    }


def test_review_result_field_shape():
    assert set(BudgetReallocationReviewResult.model_fields.keys()) == {
        "review_id",
        "campaign_results",
        "total_current_budget",
        "total_recommended_budget",
        "conservation",
    }


def test_campaign_result_rejects_unknown_field():
    result = _sample_result()
    dumped = result.campaign_results[0].model_dump()
    dumped["extra_field"] = "not allowed"
    with pytest.raises(ValidationError):
        CampaignBudgetRecommendationResult(**dumped)


def test_review_result_rejects_unknown_field():
    result = _sample_result()
    with pytest.raises(ValidationError):
        BudgetReallocationReviewResult(
            review_id=result.review_id,
            campaign_results=result.campaign_results,
            total_current_budget=result.total_current_budget,
            total_recommended_budget=result.total_recommended_budget,
            conservation=result.conservation,
            extra="x",
        )


def test_campaign_result_is_immutable():
    result = _sample_result()
    with pytest.raises(ValidationError):
        result.campaign_results[0].recommendation_action = RecommendationAction.HOLD


def test_review_result_is_immutable():
    result = _sample_result()
    with pytest.raises(ValidationError):
        result.total_current_budget = Decimal("0.00")


def test_rank_ge_one_when_present():
    with pytest.raises(ValidationError):
        CampaignBudgetRecommendationResult(
            campaign_id="C001",
            campaign_name="X",
            platform=Platform.GOOGLE_ADS,
            current_budget=Decimal("100.00"),
            recommendation_action=RecommendationAction.INCREASE,
            allocated_amount=Decimal("10.00"),
            recommended_budget=Decimal("110.00"),
            reason_codes=(ReasonCode.ABOVE_TARGET_STRONG,),
            performance_band=PerformanceBand.ABOVE_TARGET,
            trend_direction=TrendDirection.IMPROVING,
            confidence=Confidence.HIGH,
            pacing_status=PacingStatus.ON_PACE,
            reallocation_priority_score=100,
            rank=0,
        )


def test_rank_none_accepted():
    result = CampaignBudgetRecommendationResult(
        campaign_id="C001",
        campaign_name="X",
        platform=Platform.GOOGLE_ADS,
        current_budget=Decimal("100.00"),
        recommendation_action=RecommendationAction.MAINTAIN,
        allocated_amount=Decimal("0.00"),
        recommended_budget=Decimal("100.00"),
        reason_codes=(ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE),
        performance_band=PerformanceBand.ON_TARGET,
        trend_direction=TrendDirection.STABLE,
        confidence=Confidence.HIGH,
        pacing_status=PacingStatus.ON_PACE,
        reallocation_priority_score=0,
        rank=None,
    )
    assert result.rank is None


def test_score_range_enforced():
    with pytest.raises(ValidationError):
        CampaignBudgetRecommendationResult(
            campaign_id="C001",
            campaign_name="X",
            platform=Platform.GOOGLE_ADS,
            current_budget=Decimal("100.00"),
            recommendation_action=RecommendationAction.HOLD,
            allocated_amount=Decimal("0.00"),
            recommended_budget=Decimal("100.00"),
            reason_codes=(ReasonCode.PAUSED_CAMPAIGN,),
            performance_band=PerformanceBand.ON_TARGET,
            trend_direction=TrendDirection.STABLE,
            confidence=Confidence.HIGH,
            pacing_status=PacingStatus.ON_PACE,
            reallocation_priority_score=101,
        )


def test_result_contains_no_forbidden_field():
    campaign_fields = set(CampaignBudgetRecommendationResult.model_fields.keys())
    review_fields = set(BudgetReallocationReviewResult.model_fields.keys())
    forbidden = {
        "signed_movement",
        "net_movement",
        "raw_increase_limit",
        "effective_decrease_limit",
        "availability",
        "suitability",
        "tracking_status",
        "validation_issues",
        "reserve",
        "campaign_count",
        "generated_at",
        "timestamp",
        "version",
        "allocated_increase_amount",
        "allocated_decrease_amount",
    }
    assert campaign_fields.isdisjoint(forbidden)
    assert review_fields.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Exact real sample-data result
# ---------------------------------------------------------------------------


def test_sample_result_exact_values():
    result = _sample_result()
    by_id = {r.campaign_id: r for r in result.campaign_results}

    assert by_id["G001"].recommendation_action == RecommendationAction.MAINTAIN
    assert by_id["G001"].reason_codes == (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE)
    assert by_id["G001"].reallocation_priority_score == 0
    assert by_id["G001"].rank is None
    assert by_id["G001"].allocated_amount == Decimal("0.00")
    assert by_id["G001"].current_budget == Decimal("3000.00")
    assert by_id["G001"].recommended_budget == Decimal("3000.00")

    assert by_id["M001"].recommendation_action == RecommendationAction.MAINTAIN
    assert by_id["M001"].reason_codes == (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE)
    assert by_id["M001"].reallocation_priority_score == 0
    assert by_id["M001"].rank is None
    assert by_id["M001"].allocated_amount == Decimal("0.00")
    assert by_id["M001"].current_budget == Decimal("2500.00")
    assert by_id["M001"].recommended_budget == Decimal("2500.00")

    assert by_id["G002"].recommendation_action == RecommendationAction.INCREASE
    assert by_id["G002"].reason_codes == (
        ReasonCode.ABOVE_TARGET_STRONG,
        ReasonCode.RECENT_TREND_IMPROVING,
    )
    assert by_id["G002"].reallocation_priority_score == 100
    assert by_id["G002"].rank == 1
    assert by_id["G002"].allocated_amount == Decimal("0.00")
    assert by_id["G002"].current_budget == Decimal("5000.00")
    assert by_id["G002"].recommended_budget == Decimal("5000.00")

    assert by_id["G003"].recommendation_action == RecommendationAction.MAINTAIN
    assert by_id["G003"].reason_codes == (ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE)
    assert by_id["G003"].reallocation_priority_score == 0
    assert by_id["G003"].rank is None
    assert by_id["G003"].allocated_amount == Decimal("0.00")
    assert by_id["G003"].current_budget == Decimal("1200.00")
    assert by_id["G003"].recommended_budget == Decimal("1200.00")

    assert result.conservation.total_increase_allocated == Decimal("0.00")
    assert result.conservation.total_decrease_allocated == Decimal("0.00")
    assert result.conservation.net_change == Decimal("0.00")
    assert result.conservation.is_conserved is True

    assert result.total_current_budget == Decimal("11700.00")
    assert result.total_recommended_budget == Decimal("11700.00")


def test_g002_remains_increase_despite_zero_allocation():
    result = _sample_result()
    g002 = next(r for r in result.campaign_results if r.campaign_id == "G002")
    assert g002.recommendation_action == RecommendationAction.INCREASE
    assert g002.recommendation_action != RecommendationAction.MAINTAIN
    assert g002.recommendation_action != RecommendationAction.HOLD


# ---------------------------------------------------------------------------
# Balanced, non-zero allocation
# ---------------------------------------------------------------------------


def test_balanced_non_zero_allocation_changes_final_budgets():
    review = _review()
    recipient = _campaign(
        campaign_id="R1",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("2.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("3.00"),
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        conversions_28d=40,
    )
    donor = _campaign(
        campaign_id="D1",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("50.00"),
        kpi_actual_7d=Decimal("100.00"),
        kpi_actual_28d=Decimal("60.00"),
        current_budget=Decimal("1000.00"),
        minimum_budget=Decimal("100.00"),
        maximum_budget=Decimal("2000.00"),
        spend_to_date=Decimal("500.00"),
        conversions_28d=40,
    )
    result = run_budget_reallocation_review(review, (recipient, donor))
    by_id = {r.campaign_id: r for r in result.campaign_results}

    assert by_id["R1"].recommendation_action == RecommendationAction.INCREASE
    assert by_id["D1"].recommendation_action == RecommendationAction.REDUCE
    assert by_id["R1"].allocated_amount > Decimal("0.00")
    assert by_id["D1"].allocated_amount > Decimal("0.00")
    assert by_id["R1"].recommended_budget == by_id["R1"].current_budget + by_id["R1"].allocated_amount
    assert by_id["D1"].recommended_budget == by_id["D1"].current_budget - by_id["D1"].allocated_amount
    assert by_id["R1"].recommended_budget != by_id["R1"].current_budget
    assert by_id["D1"].recommended_budget != by_id["D1"].current_budget

    assert result.conservation.is_conserved is True
    assert result.total_recommended_budget == result.total_current_budget


# ---------------------------------------------------------------------------
# HOLD / MAINTAIN / zero-allocation directional
# ---------------------------------------------------------------------------


def test_hold_produces_zero_movement_and_unchanged_budget():
    review = _review()
    campaign = _campaign(status=CampaignStatus.PAUSED, current_budget=Decimal("777.00"))
    result = run_budget_reallocation_review(review, (campaign,))
    r = result.campaign_results[0]
    assert r.recommendation_action == RecommendationAction.HOLD
    assert r.allocated_amount == Decimal("0.00")
    assert r.recommended_budget == Decimal("777.00")
    assert r.rank is None


def test_maintain_produces_zero_movement_and_unchanged_budget():
    review = _review()
    campaign = _campaign(
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("4.00"),
        current_budget=Decimal("888.00"),
    )
    result = run_budget_reallocation_review(review, (campaign,))
    r = result.campaign_results[0]
    assert r.recommendation_action == RecommendationAction.MAINTAIN
    assert r.allocated_amount == Decimal("0.00")
    assert r.recommended_budget == Decimal("888.00")
    assert r.rank is None


# ---------------------------------------------------------------------------
# Rank behavior
# ---------------------------------------------------------------------------


def test_optional_rank_absent_for_non_directional():
    result = _sample_result()
    for r in result.campaign_results:
        if r.recommendation_action in (RecommendationAction.HOLD, RecommendationAction.MAINTAIN):
            assert r.rank is None


def test_rank_present_for_ranked_directional():
    result = _sample_result()
    g002 = next(r for r in result.campaign_results if r.campaign_id == "G002")
    assert g002.rank is not None
    assert g002.rank >= 1


# ---------------------------------------------------------------------------
# Empty portfolio
# ---------------------------------------------------------------------------


def test_empty_portfolio():
    review = _review()
    result = run_budget_reallocation_review(review, ())
    assert result.campaign_results == ()
    assert result.total_current_budget == Decimal("0.00")
    assert result.total_recommended_budget == Decimal("0.00")
    assert result.conservation.is_conserved is True


# ---------------------------------------------------------------------------
# Order preservation / ID-based matching
# ---------------------------------------------------------------------------


def test_original_input_order_preserved():
    review = _review()
    c1 = _campaign(campaign_id="Z999")
    c2 = _campaign(campaign_id="A001")
    c3 = _campaign(campaign_id="M500")
    result = run_budget_reallocation_review(review, (c1, c2, c3))
    assert [r.campaign_id for r in result.campaign_results] == ["Z999", "A001", "M500"]


def test_id_based_matching_not_positional():
    # Two campaigns whose alphabetical/ID order differs from the order in
    # which they naturally rank; confirm results are matched correctly
    # regardless of internal Stage 24/25 reordering.
    review = _review()
    increase_campaign = _campaign(
        campaign_id="B",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("2.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("3.00"),
    )
    maintain_campaign = _campaign(
        campaign_id="A",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("4.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("4.00"),
    )
    result = run_budget_reallocation_review(review, (increase_campaign, maintain_campaign))
    by_id = {r.campaign_id: r for r in result.campaign_results}
    assert by_id["B"].recommendation_action == RecommendationAction.INCREASE
    assert by_id["A"].recommendation_action == RecommendationAction.MAINTAIN
    assert [r.campaign_id for r in result.campaign_results] == ["B", "A"]


# ---------------------------------------------------------------------------
# Decimal / context policy
# ---------------------------------------------------------------------------


def test_no_float_in_source():
    import src.pipeline as pipeline_module

    source = inspect.getsource(pipeline_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "float" not in referenced


def test_mutated_ambient_precision_and_rounding_restored():
    review = _review()
    recipient = _campaign(
        campaign_id="R1",
        kpi_type=KPIType.ROAS,
        kpi_target=Decimal("2.00"),
        kpi_actual_7d=Decimal("4.00"),
        kpi_actual_28d=Decimal("3.00"),
    )
    donor = _campaign(
        campaign_id="D1",
        kpi_type=KPIType.CPA,
        kpi_target=Decimal("50.00"),
        kpi_actual_7d=Decimal("100.00"),
        kpi_actual_28d=Decimal("60.00"),
    )
    baseline = run_budget_reallocation_review(review, (recipient, donor))

    original_prec = getcontext().prec
    original_rounding = getcontext().rounding
    try:
        getcontext().prec = 10
        getcontext().rounding = "ROUND_CEILING"
        mutated = run_budget_reallocation_review(review, (recipient, donor))
    finally:
        getcontext().prec = original_prec
        getcontext().rounding = original_rounding

    assert baseline.model_dump() == mutated.model_dump()
    assert getcontext().prec == original_prec
    assert getcontext().rounding == original_rounding


def test_extreme_budget_magnitudes():
    review = _review()
    huge = Decimal("99999999999999999999999999.99")
    campaign = _campaign(
        current_budget=huge,
        minimum_budget=Decimal("0.00"),
        maximum_budget=huge,
        spend_to_date=Decimal("0.00"),
    )
    result = run_budget_reallocation_review(review, (campaign,))
    r = result.campaign_results[0]
    assert r.current_budget == huge
    assert r.recommended_budget in (huge,)  # MAINTAIN/HOLD/unfunded directional -> unchanged
    assert result.total_current_budget == huge


# ---------------------------------------------------------------------------
# Conservation and total-budget invariants
# ---------------------------------------------------------------------------


def test_conservation_always_exposed_never_hidden():
    result = _sample_result()
    assert hasattr(result, "conservation")
    assert result.conservation.is_conserved is True


def test_total_budget_invariant_holds_for_real_chain():
    result = _sample_result()
    assert result.conservation.is_conserved is True
    assert result.total_recommended_budget == result.total_current_budget


def test_does_not_raise_for_real_conserved_chain():
    # The real production chain is always conserved by construction; this
    # confirms the defence-in-depth check never fires spuriously.
    try:
        _sample_result()
    except RuntimeError as exc:
        pytest.fail(f"Unexpected RuntimeError for a genuinely conserved chain: {exc!r}")


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_inputs_not_mutated():
    review = _review()
    campaign = _campaign(campaign_id="R1", current_budget=Decimal("1000.00"))
    run_budget_reallocation_review(review, (campaign,))
    assert campaign.current_budget == Decimal("1000.00")
    assert review.review_id == "REV-1"


# ---------------------------------------------------------------------------
# Error policy
# ---------------------------------------------------------------------------


def test_no_broad_exception_handling_in_source():
    source = inspect.getsource(run_budget_reallocation_review)
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.Try) for node in ast.walk(tree))


def test_unexpected_exception_propagates_unchanged():
    review = _review()
    with pytest.raises(AttributeError):
        run_budget_reallocation_review(review, (None,))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def test_module_does_not_reference_excluded_names():
    import src.pipeline as pipeline_module

    source = inspect.getsource(pipeline_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    forbidden = {
        "genai",
        "generativeai",
        "gemini",
        "Streamlit",
        "streamlit",
        "st",
        "approval",
        "audit",
        "exports",
        "validate_campaign_csv",
        "validate_review_setup",
        "ValidationReport",
        "ValidationIssue",
        "ValidationCode",
        "ValidationSeverity",
    }
    assert referenced.isdisjoint(forbidden)


def test_module_does_not_import_ai_ui_or_validation():
    import src.pipeline as pipeline_module

    tree = ast.parse(inspect.getsource(pipeline_module))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)

    forbidden_modules = {
        "src.validation",
        "src.gemini_analyzer",
        "src.explanations",
        "src.approval",
        "src.audit",
        "src.exports",
        "streamlit",
        "google.generativeai",
    }
    assert imported_modules.isdisjoint(forbidden_modules)


def test_no_duplicated_formula_arithmetic_beyond_final_budget():
    # The only BinOp arithmetic anywhere in the module must belong to the
    # explicitly authorised final-budget/summation helpers, never a
    # reimplementation of an upstream Stage 1-26 formula.
    import src.pipeline as pipeline_module

    tree = ast.parse(inspect.getsource(pipeline_module))
    binop_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if isinstance(inner, ast.BinOp):
                    binop_functions.add(node.name)
    assert binop_functions <= {"_compute_recommended_budget", "_sum_currency", "_safe_precision"}


def test_no_stage_1_26_production_function_reimplemented():
    import src.pipeline as pipeline_module

    tree = ast.parse(inspect.getsource(pipeline_module))
    defined_functions = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    stage_function_names = {
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "calculate_campaign_static_budget_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_raw_percentage_movement_cap",
        "calculate_campaign_test_floor_room",
        "resolve_campaign_protection_constraint",
        "resolve_campaign_test_aware_static_decrease_room",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_raw_decrease_limit",
        "resolve_campaign_effective_decrease_limit",
        "resolve_campaign_action_availability",
        "resolve_campaign_action_suitability",
        "resolve_campaign_recommendation_action",
        "resolve_campaign_recommendation_reason",
        "calculate_campaign_reallocation_priority_score",
        "rank_campaign_reallocation_priorities",
        "allocate_campaign_reallocation",
        "verify_campaign_reallocation_conservation",
    }
    assert defined_functions.isdisjoint(stage_function_names)


def test_calls_every_required_stage_function():
    import src.pipeline as pipeline_module

    source = inspect.getsource(pipeline_module.run_budget_reallocation_review)
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    required_calls = {
        "calculate_campaign_metrics",
        "calculate_campaign_pacing",
        "classify_campaign_pacing",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "assess_campaign_tracking",
        "calculate_campaign_static_budget_room",
        "resolve_campaign_applicable_change_percentage",
        "calculate_campaign_raw_percentage_movement_cap",
        "calculate_campaign_test_floor_room",
        "resolve_campaign_protection_constraint",
        "resolve_campaign_test_aware_static_decrease_room",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_raw_decrease_limit",
        "resolve_campaign_effective_decrease_limit",
        "resolve_campaign_action_availability",
        "resolve_campaign_action_suitability",
        "resolve_campaign_recommendation_action",
        "resolve_campaign_recommendation_reason",
        "calculate_campaign_reallocation_priority_score",
        "rank_campaign_reallocation_priorities",
        "allocate_campaign_reallocation",
        "verify_campaign_reallocation_conservation",
    }
    assert required_calls <= called_names


def test_no_production_batch_wrapper_beyond_the_approved_one():
    import src.pipeline as pipeline_module

    assert not hasattr(pipeline_module, "run_budget_reallocation_reviews")
