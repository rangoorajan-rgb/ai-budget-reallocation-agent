"""Tests for src.scoring (Sprint 1 — Development Stage 23).

Covers CampaignReallocationPriorityScore construction/immutability/range/
total-consistency validation, the three-way campaign-ID mismatch policy,
the non-directional HOLD/MAINTAIN all-zero rule (confirmed never to
evaluate the confidence/business-priority mappings), the
Confidence.NOT_ASSESSABLE scoring-only override, the exact INCREASE and
REDUCE confidence x business-priority matrices, isolation from every
excluded Stage 1-22 type/field/function, immutability of every mapping,
single-campaign scope, and sample-data integration.
"""

import ast
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.classification import (
    CampaignConfidenceClass,
    assess_campaign_tracking,
    classify_campaign_confidence,
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
from src.scoring import (
    CampaignReallocationPriorityScore,
    calculate_campaign_reallocation_priority_score,
)
from src.suitability import resolve_campaign_action_suitability
from src.validation import validate_campaign_csv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VALID_TOTALS = {0, 20, 40, 60, 80, 100}


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


def _confidence(**overrides) -> CampaignConfidenceClass:
    kwargs = dict(campaign_id="C001", confidence=Confidence.HIGH)
    kwargs.update(overrides)
    return CampaignConfidenceClass(**kwargs)


def _build_recommendation_and_confidence(campaign: CampaignInput, review: ReviewSetup):
    """Run the real Stage 3/5/6/7/8/10-21 production chain for one campaign
    and return exactly the two non-CampaignInput objects Stage 23 is
    approved to accept, alongside the confidence classification."""
    metrics = calculate_campaign_metrics(campaign)
    performance = classify_campaign_performance(metrics)
    trend = classify_campaign_trend(metrics)
    confidence = classify_campaign_confidence(campaign)

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

    return recommendation, confidence


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_model_accepts_exactly_four_fields():
    assert set(CampaignReallocationPriorityScore.model_fields.keys()) == {
        "campaign_id",
        "confidence_component",
        "business_priority_component",
        "reallocation_priority_score",
    }


def test_model_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignReallocationPriorityScore(
            campaign_id="C001",
            confidence_component=0,
            business_priority_component=0,
            reallocation_priority_score=0,
            extra_field="not allowed",
        )


def test_model_is_immutable():
    result = calculate_campaign_reallocation_priority_score(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(),
        _confidence(),
    )
    with pytest.raises(ValidationError):
        result.reallocation_priority_score = 50


def test_model_fields_are_plain_int():
    result = calculate_campaign_reallocation_priority_score(
        _recommendation(recommendation_action=RecommendationAction.HOLD),
        _campaign(),
        _confidence(),
    )
    assert type(result.confidence_component) is int
    assert type(result.business_priority_component) is int
    assert type(result.reallocation_priority_score) is int


@pytest.mark.parametrize("bad_value", [-1, 101, 1000])
def test_model_rejects_out_of_range_component(bad_value):
    with pytest.raises(ValidationError):
        CampaignReallocationPriorityScore(
            campaign_id="C001",
            confidence_component=bad_value,
            business_priority_component=0,
            reallocation_priority_score=max(0, min(bad_value, 100)),
        )


def test_model_rejects_inconsistent_total():
    with pytest.raises(ValidationError):
        CampaignReallocationPriorityScore(
            campaign_id="C001",
            confidence_component=60,
            business_priority_component=40,
            reallocation_priority_score=99,
        )


def test_model_serialization():
    result = calculate_campaign_reallocation_priority_score(
        _recommendation(recommendation_action=RecommendationAction.INCREASE),
        _campaign(business_priority=BusinessPriority.HIGH),
        _confidence(confidence=Confidence.HIGH),
    )
    dumped = result.model_dump()
    assert dumped == {
        "campaign_id": "C001",
        "confidence_component": 60,
        "business_priority_component": 40,
        "reallocation_priority_score": 100,
    }


def test_result_contains_no_forbidden_field():
    field_names = set(CampaignReallocationPriorityScore.model_fields.keys())
    forbidden = {
        "recommendation_action",
        "reason_codes",
        "performance_band",
        "trend_direction",
        "pacing_status",
        "rank",
        "allocation",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Campaign-ID policy
# ---------------------------------------------------------------------------

_EXACT_ERROR_MESSAGE = (
    "Campaign IDs must match when calculating reallocation priority score."
)


def test_all_ids_matching_succeeds():
    result = calculate_campaign_reallocation_priority_score(
        _recommendation(campaign_id="MATCH-1", recommendation_action=RecommendationAction.HOLD),
        _campaign(campaign_id="MATCH-1"),
        _confidence(campaign_id="MATCH-1"),
    )
    assert result.campaign_id == "MATCH-1"


def test_campaign_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        calculate_campaign_reallocation_priority_score(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="OTHER"),
            _confidence(campaign_id="C001"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_confidence_id_mismatch_raises_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        calculate_campaign_reallocation_priority_score(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="C001"),
            _confidence(campaign_id="OTHER"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_multiple_mismatches_raise_the_same_exact_value_error():
    with pytest.raises(ValueError) as exc_info:
        calculate_campaign_reallocation_priority_score(
            _recommendation(campaign_id="C001"),
            _campaign(campaign_id="A"),
            _confidence(campaign_id="B"),
        )
    assert str(exc_info.value) == _EXACT_ERROR_MESSAGE


def test_id_check_occurs_before_action_confidence_or_priority_resolution():
    source = inspect.getsource(calculate_campaign_reallocation_priority_score)
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
        campaign=_campaign(campaign_id="C001"),
        confidence=_confidence(campaign_id="C001"),
    )
    for key, mismatched in (
        ("campaign", _campaign(campaign_id="X")),
        ("confidence", _confidence(campaign_id="X")),
    ):
        args = dict(base)
        args[key] = mismatched
        with pytest.raises(ValueError):
            calculate_campaign_reallocation_priority_score(**args)


def test_no_result_returned_after_mismatch():
    try:
        calculate_campaign_reallocation_priority_score(
            _recommendation(campaign_id="A"),
            _campaign(campaign_id="B"),
            _confidence(campaign_id="A"),
        )
        assert False, "expected ValueError, no result should be returned"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# HOLD and MAINTAIN (non-directional)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action", [RecommendationAction.HOLD, RecommendationAction.MAINTAIN]
)
@pytest.mark.parametrize("confidence_value", list(Confidence))
@pytest.mark.parametrize("priority_value", list(BusinessPriority))
def test_non_directional_actions_always_score_zero(action, confidence_value, priority_value):
    result = calculate_campaign_reallocation_priority_score(
        _recommendation(recommendation_action=action),
        _campaign(business_priority=priority_value),
        _confidence(confidence=confidence_value),
    )
    assert result.confidence_component == 0
    assert result.business_priority_component == 0
    assert result.reallocation_priority_score == 0


def test_non_directional_never_evaluates_confidence_or_priority_mappings(monkeypatch):
    import src.scoring as scoring_module

    class _ExplodingMapping(dict):
        def __getitem__(self, key):  # noqa: D401 - test helper
            raise AssertionError(
                "mapping must not be evaluated for a non-directional action"
            )

    monkeypatch.setattr(scoring_module, "_CONFIDENCE_COMPONENT", _ExplodingMapping())
    monkeypatch.setattr(
        scoring_module, "_INCREASE_BUSINESS_PRIORITY_COMPONENT", _ExplodingMapping()
    )
    monkeypatch.setattr(
        scoring_module, "_REDUCE_BUSINESS_PRIORITY_COMPONENT", _ExplodingMapping()
    )

    for action in (RecommendationAction.HOLD, RecommendationAction.MAINTAIN):
        result = scoring_module.calculate_campaign_reallocation_priority_score(
            _recommendation(recommendation_action=action),
            _campaign(business_priority=BusinessPriority.HIGH),
            _confidence(confidence=Confidence.HIGH),
        )
        assert result.reallocation_priority_score == 0


# ---------------------------------------------------------------------------
# Confidence.NOT_ASSESSABLE override
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action", [RecommendationAction.INCREASE, RecommendationAction.REDUCE]
)
@pytest.mark.parametrize("priority_value", list(BusinessPriority))
def test_not_assessable_directional_action_scores_zero(action, priority_value):
    recommendation = _recommendation(recommendation_action=action)
    result = calculate_campaign_reallocation_priority_score(
        recommendation,
        _campaign(business_priority=priority_value),
        _confidence(confidence=Confidence.NOT_ASSESSABLE),
    )
    assert result.confidence_component == 0
    assert result.business_priority_component == 0
    assert result.reallocation_priority_score == 0
    # the existing recommendation is untouched
    assert recommendation.recommendation_action is action


def test_not_assessable_does_not_raise():
    try:
        calculate_campaign_reallocation_priority_score(
            _recommendation(recommendation_action=RecommendationAction.INCREASE),
            _campaign(),
            _confidence(confidence=Confidence.NOT_ASSESSABLE),
        )
    except Exception as exc:  # noqa: BLE001 - explicit confirmation no exception is raised
        pytest.fail(f"NOT_ASSESSABLE raised an unexpected exception: {exc!r}")


# ---------------------------------------------------------------------------
# INCREASE matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "confidence_value, priority_value, expected_confidence, expected_priority, expected_total",
    [
        (Confidence.HIGH, BusinessPriority.HIGH, 60, 40, 100),
        (Confidence.HIGH, BusinessPriority.MEDIUM, 60, 20, 80),
        (Confidence.HIGH, BusinessPriority.STANDARD, 60, 0, 60),
        (Confidence.MEDIUM, BusinessPriority.HIGH, 40, 40, 80),
        (Confidence.MEDIUM, BusinessPriority.MEDIUM, 40, 20, 60),
        (Confidence.MEDIUM, BusinessPriority.STANDARD, 40, 0, 40),
        (Confidence.LOW, BusinessPriority.HIGH, 20, 40, 60),
        (Confidence.LOW, BusinessPriority.MEDIUM, 20, 20, 40),
        (Confidence.LOW, BusinessPriority.STANDARD, 20, 0, 20),
    ],
)
def test_increase_matrix(
    confidence_value, priority_value, expected_confidence, expected_priority, expected_total
):
    result = calculate_campaign_reallocation_priority_score(
        _recommendation(recommendation_action=RecommendationAction.INCREASE),
        _campaign(business_priority=priority_value),
        _confidence(confidence=confidence_value),
    )
    assert result.confidence_component == expected_confidence
    assert result.business_priority_component == expected_priority
    assert result.reallocation_priority_score == expected_total


# ---------------------------------------------------------------------------
# REDUCE matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "confidence_value, priority_value, expected_confidence, expected_priority, expected_total",
    [
        (Confidence.HIGH, BusinessPriority.STANDARD, 60, 40, 100),
        (Confidence.HIGH, BusinessPriority.MEDIUM, 60, 20, 80),
        (Confidence.HIGH, BusinessPriority.HIGH, 60, 0, 60),
        (Confidence.MEDIUM, BusinessPriority.STANDARD, 40, 40, 80),
        (Confidence.MEDIUM, BusinessPriority.MEDIUM, 40, 20, 60),
        (Confidence.MEDIUM, BusinessPriority.HIGH, 40, 0, 40),
        (Confidence.LOW, BusinessPriority.STANDARD, 20, 40, 60),
        (Confidence.LOW, BusinessPriority.MEDIUM, 20, 20, 40),
        (Confidence.LOW, BusinessPriority.HIGH, 20, 0, 20),
    ],
)
def test_reduce_matrix(
    confidence_value, priority_value, expected_confidence, expected_priority, expected_total
):
    result = calculate_campaign_reallocation_priority_score(
        _recommendation(recommendation_action=RecommendationAction.REDUCE),
        _campaign(business_priority=priority_value),
        _confidence(confidence=confidence_value),
    )
    assert result.confidence_component == expected_confidence
    assert result.business_priority_component == expected_priority
    assert result.reallocation_priority_score == expected_total


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def test_authorised_fields_are_exactly_six():
    source = inspect.getsource(calculate_campaign_reallocation_priority_score)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_names = [arg.arg for arg in func_def.args.args]
    assert param_names == ["recommendation", "campaign", "confidence"]

    attrs_by_param: dict[str, set[str]] = {name: set() for name in param_names}
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in attrs_by_param:
                attrs_by_param[node.value.id].add(node.attr)

    assert attrs_by_param["recommendation"] == {"campaign_id", "recommendation_action"}
    assert attrs_by_param["campaign"] == {"campaign_id", "business_priority"}
    assert attrs_by_param["confidence"] == {"campaign_id", "confidence"}
    total = sum(len(v) for v in attrs_by_param.values())
    assert total == 6


def test_does_not_call_earlier_production_functions():
    source = inspect.getsource(calculate_campaign_reallocation_priority_score)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "resolve_campaign_recommendation_action",
        "resolve_campaign_action_suitability",
        "resolve_campaign_action_availability",
        "resolve_campaign_recommendation_reason",
        "assess_campaign_tracking",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "calculate_campaign_metrics",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_effective_decrease_limit",
        "resolve_campaign_protection_constraint",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_module_does_not_reference_excluded_names():
    import src.scoring as scoring_module

    source = inspect.getsource(scoring_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    forbidden = {
        "ReasonCode",
        "CampaignRecommendationReason",
        "CampaignPerformanceClass",
        "PerformanceBand",
        "CampaignTrendClass",
        "TrendDirection",
        "CampaignPacingClass",
        "PacingStatus",
        "CampaignTrackingAssessment",
        "CampaignActionAvailability",
        "CampaignActionSuitability",
        "Decimal",
        "float",
        "weighted_performance_ratio",
        "trend_delta",
        "performance_ratio_7d",
        "performance_ratio_28d",
        "effective_decrease_limit",
        "raw_increase_limit",
        "raw_decrease_limit",
        "is_protected",
        "is_test_campaign",
        "test_budget_floor",
        "decrease_blocked",
        "tracking_status",
        "is_assessable",
        "sorted",
        "sort",
        "rank",
        "normalize",
        "normalise",
        "allocate",
    }
    assert referenced.isdisjoint(forbidden)


def test_module_does_not_import_excluded_types():
    import src.scoring as scoring_module

    for forbidden_name in (
        "ReasonCode",
        "CampaignRecommendationReason",
        "CampaignPerformanceClass",
        "PerformanceBand",
        "CampaignTrendClass",
        "TrendDirection",
        "CampaignPacingClass",
        "PacingStatus",
        "CampaignTrackingAssessment",
        "CampaignActionAvailability",
        "CampaignActionSuitability",
    ):
        assert not hasattr(scoring_module, forbidden_name)


def test_no_float_or_decimal_in_source():
    source = inspect.getsource(calculate_campaign_reallocation_priority_score)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "Decimal" not in referenced
    assert "float" not in referenced


def test_no_multiplication_or_division_in_source():
    source = inspect.getsource(calculate_campaign_reallocation_priority_score)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            assert not isinstance(node.op, (ast.Mult, ast.Div, ast.FloorDiv))


def test_no_broad_exception_handling_in_source():
    source = inspect.getsource(calculate_campaign_reallocation_priority_score)
    assert "except" not in source


def test_no_production_batch_function():
    import src.scoring as scoring_module

    assert not hasattr(scoring_module, "calculate_campaign_reallocation_priority_scores")
    assert not hasattr(scoring_module, "score_campaigns")


def test_all_mappings_are_immutable():
    import src.scoring as scoring_module
    from types import MappingProxyType

    for mapping_name in (
        "_CONFIDENCE_COMPONENT",
        "_INCREASE_BUSINESS_PRIORITY_COMPONENT",
        "_REDUCE_BUSINESS_PRIORITY_COMPONENT",
    ):
        mapping = getattr(scoring_module, mapping_name)
        assert isinstance(mapping, MappingProxyType)
        with pytest.raises(TypeError):
            mapping[Confidence.HIGH] = 999  # type: ignore[index]


def test_none_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        calculate_campaign_reallocation_priority_score(None, None, None)  # type: ignore[arg-type]


def test_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        calculate_campaign_reallocation_priority_score(  # type: ignore[arg-type]
            _recommendation(),
            {"campaign_id": "C001", "business_priority": BusinessPriority.HIGH},
            _confidence(),
        )


# ---------------------------------------------------------------------------
# Exhaustive consistency sweep
# ---------------------------------------------------------------------------


def test_total_always_equals_component_sum_and_is_a_valid_value():
    for action in RecommendationAction:
        for confidence_value in Confidence:
            for priority_value in BusinessPriority:
                result = calculate_campaign_reallocation_priority_score(
                    _recommendation(recommendation_action=action),
                    _campaign(business_priority=priority_value),
                    _confidence(confidence=confidence_value),
                )
                assert result.reallocation_priority_score == (
                    result.confidence_component + result.business_priority_component
                )
                assert result.reallocation_priority_score in VALID_TOTALS
                assert result.confidence_component >= 0
                assert result.business_priority_component >= 0


# ---------------------------------------------------------------------------
# Single-campaign scope
# ---------------------------------------------------------------------------


def test_function_signature_has_no_collection_parameter():
    source = inspect.getsource(calculate_campaign_reallocation_priority_score)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    assert len(func_def.args.args) == 3
    for arg in func_def.args.args:
        assert arg.annotation is not None
        annotation_source = ast.unparse(arg.annotation)
        assert "list" not in annotation_source.lower()
        assert "tuple" not in annotation_source.lower()
        assert "dict" not in annotation_source.lower()


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_reallocation_priority_score_exact_values():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    built = {
        c.campaign_id: (c, *_build_recommendation_and_confidence(c, review))
        for c in report.valid_campaigns
    }

    results = {
        campaign_id: calculate_campaign_reallocation_priority_score(
            recommendation, campaign, confidence
        )
        for campaign_id, (campaign, recommendation, confidence) in built.items()
    }

    assert results["G001"].reallocation_priority_score == 0
    assert results["M001"].reallocation_priority_score == 0
    assert results["G003"].reallocation_priority_score == 0

    g002_campaign, g002_recommendation, g002_confidence = built["G002"]
    assert g002_recommendation.recommendation_action == RecommendationAction.INCREASE
    assert g002_confidence.confidence == Confidence.HIGH
    assert g002_campaign.business_priority == BusinessPriority.HIGH
    assert results["G002"].confidence_component == 60
    assert results["G002"].business_priority_component == 40
    assert results["G002"].reallocation_priority_score == 100
