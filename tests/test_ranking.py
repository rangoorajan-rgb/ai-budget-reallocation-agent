"""Tests for src.ranking (Sprint 1 — Development Stage 24).

Covers RankedCampaignPriority/CampaignReallocationRanking construction,
immutability, and range validation; value-based (never positional)
campaign-ID matching between recommendations and scores; the exact
uniqueness/mismatch validation order and error messages; the eligible-
population rule (only a strictly-positive-scored directional
recommendation is ranked; MAINTAIN/HOLD and zero-scored directional
recommendations are excluded without error, reason code, or mutation);
complete direction independence (INCREASE never compared with REDUCE, no
global rank); dense ranking with campaign-ID-ascending tied-record
serialization that never affects the assigned rank; absence of
normalisation; determinism under shuffled input order; isolation from
every excluded field/type/function; and sample-data integration.
"""

import ast
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.classification import (
    assess_campaign_tracking,
    classify_campaign_confidence,
    classify_campaign_performance,
    classify_campaign_trend,
)
from src.constants import (
    BusinessPriority,
    CampaignStatus,
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
from src.ranking import (
    CampaignReallocationRanking,
    RankedCampaignPriority,
    rank_campaign_reallocation_priorities,
)
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


def _recommendation(
    campaign_id: str = "C001",
    action: RecommendationAction = RecommendationAction.HOLD,
) -> CampaignRecommendation:
    return CampaignRecommendation(campaign_id=campaign_id, recommendation_action=action)


def _score(
    campaign_id: str = "C001", reallocation_priority_score: int = 100
) -> CampaignReallocationPriorityScore:
    return CampaignReallocationPriorityScore(
        campaign_id=campaign_id,
        confidence_component=reallocation_priority_score,
        business_priority_component=0,
        reallocation_priority_score=reallocation_priority_score,
    )


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


def _build_recommendation_and_score(campaign: CampaignInput, review: ReviewSetup):
    """Run the real Stage 3/5/6/7/8/10-23 production chain for one campaign
    and return exactly its CampaignRecommendation and
    CampaignReallocationPriorityScore."""
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
    score = calculate_campaign_reallocation_priority_score(recommendation, campaign, confidence)

    return recommendation, score


_EXACT_DUP_RECOMMENDATION_MESSAGE = (
    "Recommendation campaign IDs must be unique when ranking reallocation priorities."
)
_EXACT_DUP_SCORE_MESSAGE = (
    "Score campaign IDs must be unique when ranking reallocation priorities."
)
_EXACT_MISMATCH_MESSAGE = (
    "Recommendation and score campaign IDs must match when ranking reallocation priorities."
)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


def test_ranked_campaign_priority_field_shape():
    assert set(RankedCampaignPriority.model_fields.keys()) == {
        "campaign_id",
        "rank",
        "reallocation_priority_score",
    }


def test_campaign_reallocation_ranking_field_shape():
    assert set(CampaignReallocationRanking.model_fields.keys()) == {
        "increase_rankings",
        "reduce_rankings",
    }


def test_ranked_campaign_priority_rejects_unknown_field():
    with pytest.raises(ValidationError):
        RankedCampaignPriority(
            campaign_id="C001", rank=1, reallocation_priority_score=100, extra="x"
        )


def test_campaign_reallocation_ranking_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignReallocationRanking(
            increase_rankings=(), reduce_rankings=(), extra="x"
        )


def test_ranked_campaign_priority_is_immutable():
    record = RankedCampaignPriority(campaign_id="C001", rank=1, reallocation_priority_score=100)
    with pytest.raises(ValidationError):
        record.rank = 2


def test_campaign_reallocation_ranking_is_immutable():
    result = CampaignReallocationRanking(increase_rankings=(), reduce_rankings=())
    with pytest.raises(ValidationError):
        result.increase_rankings = ()


def test_rank_minimum_is_one():
    with pytest.raises(ValidationError):
        RankedCampaignPriority(campaign_id="C001", rank=0, reallocation_priority_score=100)


def test_score_range_one_to_hundred():
    with pytest.raises(ValidationError):
        RankedCampaignPriority(campaign_id="C001", rank=1, reallocation_priority_score=0)
    with pytest.raises(ValidationError):
        RankedCampaignPriority(campaign_id="C001", rank=1, reallocation_priority_score=101)


def test_ranking_tuple_field_types():
    result = CampaignReallocationRanking(
        increase_rankings=(RankedCampaignPriority(campaign_id="C001", rank=1, reallocation_priority_score=100),),
        reduce_rankings=(),
    )
    assert isinstance(result.increase_rankings, tuple)
    assert isinstance(result.reduce_rankings, tuple)


def test_serialization():
    result = CampaignReallocationRanking(
        increase_rankings=(RankedCampaignPriority(campaign_id="C001", rank=1, reallocation_priority_score=100),),
        reduce_rankings=(),
    )
    dumped = result.model_dump()
    assert dumped == {
        "increase_rankings": ({"campaign_id": "C001", "rank": 1, "reallocation_priority_score": 100},),
        "reduce_rankings": (),
    }


def test_independently_empty_direction_tuples():
    only_increase = CampaignReallocationRanking(
        increase_rankings=(RankedCampaignPriority(campaign_id="C001", rank=1, reallocation_priority_score=100),),
        reduce_rankings=(),
    )
    only_reduce = CampaignReallocationRanking(
        increase_rankings=(),
        reduce_rankings=(RankedCampaignPriority(campaign_id="C002", rank=1, reallocation_priority_score=60),),
    )
    both_empty = CampaignReallocationRanking(increase_rankings=(), reduce_rankings=())
    assert only_increase.reduce_rankings == ()
    assert only_reduce.increase_rankings == ()
    assert both_empty.increase_rankings == () and both_empty.reduce_rankings == ()


def test_result_contains_no_forbidden_field():
    ranked_fields = set(RankedCampaignPriority.model_fields.keys())
    batch_fields = set(CampaignReallocationRanking.model_fields.keys())
    forbidden = {
        "recommendation_action",
        "direction",
        "confidence_component",
        "business_priority_component",
        "reason_codes",
        "amount",
        "allocation",
        "excluded",
        "excluded_rankings",
        "global_rank",
    }
    assert ranked_fields.isdisjoint(forbidden)
    assert batch_fields.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Validation: duplicates and mismatches
# ---------------------------------------------------------------------------


def test_duplicate_recommendation_id_raises_exact_error():
    with pytest.raises(ValueError) as exc_info:
        rank_campaign_reallocation_priorities(
            (
                _recommendation("C001", RecommendationAction.INCREASE),
                _recommendation("C001", RecommendationAction.INCREASE),
            ),
            (_score("C001", 100),),
        )
    assert str(exc_info.value) == _EXACT_DUP_RECOMMENDATION_MESSAGE


def test_duplicate_score_id_raises_exact_error():
    with pytest.raises(ValueError) as exc_info:
        rank_campaign_reallocation_priorities(
            (_recommendation("C001", RecommendationAction.INCREASE),),
            (_score("C001", 100), _score("C001", 80)),
        )
    assert str(exc_info.value) == _EXACT_DUP_SCORE_MESSAGE


def test_duplicates_in_both_collections_recommendation_error_takes_precedence():
    with pytest.raises(ValueError) as exc_info:
        rank_campaign_reallocation_priorities(
            (
                _recommendation("C001", RecommendationAction.INCREASE),
                _recommendation("C001", RecommendationAction.INCREASE),
            ),
            (_score("C001", 100), _score("C001", 80)),
        )
    assert str(exc_info.value) == _EXACT_DUP_RECOMMENDATION_MESSAGE


def test_recommendation_without_score_raises_mismatch_error():
    with pytest.raises(ValueError) as exc_info:
        rank_campaign_reallocation_priorities(
            (_recommendation("C001", RecommendationAction.INCREASE),),
            (),
        )
    assert str(exc_info.value) == _EXACT_MISMATCH_MESSAGE


def test_score_without_recommendation_raises_mismatch_error():
    with pytest.raises(ValueError) as exc_info:
        rank_campaign_reallocation_priorities(
            (),
            (_score("C001", 100),),
        )
    assert str(exc_info.value) == _EXACT_MISMATCH_MESSAGE


def test_partially_mismatched_id_sets_raise_mismatch_error():
    with pytest.raises(ValueError) as exc_info:
        rank_campaign_reallocation_priorities(
            (
                _recommendation("C001", RecommendationAction.INCREASE),
                _recommendation("C002", RecommendationAction.REDUCE),
            ),
            (_score("C001", 100), _score("C003", 60)),
        )
    assert str(exc_info.value) == _EXACT_MISMATCH_MESSAGE


def test_empty_recommendations_with_non_empty_scores_raises_mismatch_error():
    with pytest.raises(ValueError) as exc_info:
        rank_campaign_reallocation_priorities((), (_score("C001", 100),))
    assert str(exc_info.value) == _EXACT_MISMATCH_MESSAGE


def test_non_empty_recommendations_with_empty_scores_raises_mismatch_error():
    with pytest.raises(ValueError) as exc_info:
        rank_campaign_reallocation_priorities(
            (_recommendation("C001", RecommendationAction.INCREASE),), ()
        )
    assert str(exc_info.value) == _EXACT_MISMATCH_MESSAGE


def test_both_empty_returns_valid_empty_result():
    result = rank_campaign_reallocation_priorities((), ())
    assert result == CampaignReallocationRanking(increase_rankings=(), reduce_rankings=())


def test_validation_precedes_ranking_in_source_order():
    source = inspect.getsource(rank_campaign_reallocation_priorities)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)

    raise_lines = [node.lineno for node in ast.walk(func_def) if isinstance(node, ast.Raise)]
    for_loop_lines = [node.lineno for node in ast.walk(func_def) if isinstance(node, ast.For)]

    assert len(raise_lines) == 3
    assert len(for_loop_lines) == 1
    assert max(raise_lines) < for_loop_lines[0]


def test_none_inputs_not_silently_converted():
    with pytest.raises(TypeError):
        rank_campaign_reallocation_priorities(None, None)  # type: ignore[arg-type]


def test_dict_inputs_not_silently_converted():
    with pytest.raises(AttributeError):
        rank_campaign_reallocation_priorities(  # type: ignore[arg-type]
            ({"campaign_id": "C001", "recommendation_action": RecommendationAction.INCREASE},),
            (_score("C001", 100),),
        )


def test_no_broad_exception_handling_in_source():
    source = inspect.getsource(rank_campaign_reallocation_priorities)
    assert "except" not in source


# ---------------------------------------------------------------------------
# Matching by campaign ID, never by position
# ---------------------------------------------------------------------------


def test_records_matched_by_campaign_id_not_position():
    recommendations = (
        _recommendation("C002", RecommendationAction.REDUCE),
        _recommendation("C001", RecommendationAction.INCREASE),
    )
    scores = (
        _score("C001", 100),
        _score("C002", 60),
    )
    result = rank_campaign_reallocation_priorities(recommendations, scores)
    assert result.increase_rankings == (
        RankedCampaignPriority(campaign_id="C001", rank=1, reallocation_priority_score=100),
    )
    assert result.reduce_rankings == (
        RankedCampaignPriority(campaign_id="C002", rank=1, reallocation_priority_score=60),
    )


def test_shuffled_and_reversed_input_order_yields_same_result():
    base_recommendations = (
        _recommendation("C001", RecommendationAction.INCREASE),
        _recommendation("C002", RecommendationAction.INCREASE),
        _recommendation("C003", RecommendationAction.REDUCE),
    )
    base_scores = (
        _score("C001", 100),
        _score("C002", 60),
        _score("C003", 40),
    )

    forward = rank_campaign_reallocation_priorities(base_recommendations, base_scores)
    reversed_result = rank_campaign_reallocation_priorities(
        tuple(reversed(base_recommendations)), tuple(reversed(base_scores))
    )
    unequal_order_result = rank_campaign_reallocation_priorities(
        (base_recommendations[2], base_recommendations[0], base_recommendations[1]),
        (base_scores[1], base_scores[2], base_scores[0]),
    )

    assert forward.model_dump() == reversed_result.model_dump() == unequal_order_result.model_dump()


def test_no_positional_zip_used():
    import src.ranking as ranking_module

    source = inspect.getsource(ranking_module)
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "zip" not in called_names


# ---------------------------------------------------------------------------
# Eligible population
# ---------------------------------------------------------------------------


def test_positive_increase_is_included():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", RecommendationAction.INCREASE),), (_score("C001", 60),)
    )
    assert len(result.increase_rankings) == 1
    assert result.increase_rankings[0].campaign_id == "C001"


def test_positive_reduce_is_included():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", RecommendationAction.REDUCE),), (_score("C001", 60),)
    )
    assert len(result.reduce_rankings) == 1
    assert result.reduce_rankings[0].campaign_id == "C001"


def test_zero_score_increase_excluded():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", RecommendationAction.INCREASE),), (_score("C001", 0),)
    )
    assert result.increase_rankings == ()
    assert result.reduce_rankings == ()


def test_zero_score_reduce_excluded():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", RecommendationAction.REDUCE),), (_score("C001", 0),)
    )
    assert result.increase_rankings == ()
    assert result.reduce_rankings == ()


def test_hold_excluded():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", RecommendationAction.HOLD),), (_score("C001", 0),)
    )
    assert result.increase_rankings == () and result.reduce_rankings == ()


def test_maintain_excluded():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", RecommendationAction.MAINTAIN),), (_score("C001", 0),)
    )
    assert result.increase_rankings == () and result.reduce_rankings == ()


@pytest.mark.parametrize("action", [RecommendationAction.HOLD, RecommendationAction.MAINTAIN])
def test_structurally_valid_positive_score_still_excluded_by_action(action):
    # Stage 23 never actually produces a positive score for HOLD/MAINTAIN, but
    # Stage 24 must exclude by action regardless of the paired score value.
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", action),), (_score("C001", 80),)
    )
    assert result.increase_rankings == ()
    assert result.reduce_rankings == ()


def test_no_excluded_result_records_or_reason_codes_created():
    result = CampaignReallocationRanking(increase_rankings=(), reduce_rankings=())
    assert not hasattr(result, "excluded")
    assert not hasattr(result, "reason_codes")


def test_inputs_remain_unchanged_after_ranking():
    recommendation = _recommendation("C001", RecommendationAction.INCREASE)
    score = _score("C001", 60)
    rank_campaign_reallocation_priorities((recommendation,), (score,))
    assert recommendation.recommendation_action == RecommendationAction.INCREASE
    assert score.reallocation_priority_score == 60


# ---------------------------------------------------------------------------
# Direction independence
# ---------------------------------------------------------------------------


def test_increase_and_reduce_are_separate_tuples():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.REDUCE),
        ),
        (_score("C001", 100), _score("C002", 100)),
    )
    assert len(result.increase_rankings) == 1
    assert len(result.reduce_rankings) == 1


def test_each_direction_starts_at_rank_one_independently():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.REDUCE),
        ),
        (_score("C001", 100), _score("C002", 100)),
    )
    assert result.increase_rankings[0].rank == 1
    assert result.reduce_rankings[0].rank == 1


def test_no_global_rank_field_exists():
    assert "global_rank" not in RankedCampaignPriority.model_fields
    assert "rank" in RankedCampaignPriority.model_fields
    # Only two direction-scoped fields on the batch result - no combined field.
    assert set(CampaignReallocationRanking.model_fields.keys()) == {
        "increase_rankings",
        "reduce_rankings",
    }


def test_identical_scores_across_directions_have_no_relationship():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.INCREASE),
            _recommendation("C003", RecommendationAction.REDUCE),
        ),
        (_score("C001", 100), _score("C002", 60), _score("C003", 100)),
    )
    # C003 (REDUCE, score 100) is rank 1 in its own group, independent of
    # C001 (INCREASE, score 100) also being rank 1 in its own group.
    assert result.increase_rankings[0].campaign_id == "C001"
    assert result.increase_rankings[0].rank == 1
    assert result.reduce_rankings[0].campaign_id == "C003"
    assert result.reduce_rankings[0].rank == 1


def test_no_campaign_crosses_direction():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", RecommendationAction.INCREASE),), (_score("C001", 100),)
    )
    increase_ids = {r.campaign_id for r in result.increase_rankings}
    reduce_ids = {r.campaign_id for r in result.reduce_rankings}
    assert increase_ids.isdisjoint(reduce_ids)
    assert "C001" in increase_ids


# ---------------------------------------------------------------------------
# Sorting and dense ranking
# ---------------------------------------------------------------------------


def test_descending_score_order():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.INCREASE),
            _recommendation("C003", RecommendationAction.INCREASE),
        ),
        (_score("C001", 60), _score("C002", 100), _score("C003", 80)),
    )
    assert [r.campaign_id for r in result.increase_rankings] == ["C002", "C003", "C001"]
    assert [r.rank for r in result.increase_rankings] == [1, 2, 3]


def test_dense_rank_ordinary_sequence():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.INCREASE),
            _recommendation("C003", RecommendationAction.INCREASE),
        ),
        (_score("C001", 100), _score("C002", 80), _score("C003", 60)),
    )
    assert [r.rank for r in result.increase_rankings] == [1, 2, 3]


def test_dense_rank_pattern_1_1_2():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.INCREASE),
            _recommendation("C003", RecommendationAction.INCREASE),
        ),
        (_score("C001", 100), _score("C002", 100), _score("C003", 80)),
    )
    assert [r.rank for r in result.increase_rankings] == [1, 1, 2]


def test_dense_rank_pattern_1_2_2_3():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.INCREASE),
            _recommendation("C003", RecommendationAction.INCREASE),
            _recommendation("C004", RecommendationAction.INCREASE),
        ),
        (
            _score("C001", 100),
            _score("C002", 80),
            _score("C003", 80),
            _score("C004", 60),
        ),
    )
    assert [r.rank for r in result.increase_rankings] == [1, 2, 2, 3]


def test_dense_rank_all_tied_at_rank_one():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.REDUCE),
            _recommendation("C002", RecommendationAction.REDUCE),
            _recommendation("C003", RecommendationAction.REDUCE),
        ),
        (_score("C001", 60), _score("C002", 60), _score("C003", 60)),
    )
    assert [r.rank for r in result.reduce_rankings] == [1, 1, 1]


def test_multiple_independent_ties():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.INCREASE),
            _recommendation("C003", RecommendationAction.INCREASE),
            _recommendation("C004", RecommendationAction.INCREASE),
            _recommendation("C005", RecommendationAction.INCREASE),
        ),
        (
            _score("C001", 100),
            _score("C002", 100),
            _score("C003", 80),
            _score("C004", 80),
            _score("C005", 60),
        ),
    )
    assert [(r.campaign_id, r.rank) for r in result.increase_rankings] == [
        ("C001", 1),
        ("C002", 1),
        ("C003", 2),
        ("C004", 2),
        ("C005", 3),
    ]


def test_campaign_id_ascending_serialization_inside_tied_score():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C003", RecommendationAction.INCREASE),
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.INCREASE),
        ),
        (_score("C003", 100), _score("C001", 100), _score("C002", 100)),
    )
    assert [r.campaign_id for r in result.increase_rankings] == ["C001", "C002", "C003"]
    assert [r.rank for r in result.increase_rankings] == [1, 1, 1]


def test_campaign_id_does_not_alter_tied_rank():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("Z999", RecommendationAction.INCREASE),
            _recommendation("A001", RecommendationAction.INCREASE),
        ),
        (_score("Z999", 100), _score("A001", 100)),
    )
    ranks = {r.rank for r in result.increase_rankings}
    assert ranks == {1}


def test_no_dense_rank_gaps():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("C001", RecommendationAction.INCREASE),
            _recommendation("C002", RecommendationAction.INCREASE),
        ),
        (_score("C001", 100), _score("C002", 100)),
    )
    assert [r.rank for r in result.increase_rankings] == [1, 1]
    # No rank 2 is skipped to.


def test_ranking_unaffected_by_input_order_dense_pattern():
    recs = (
        _recommendation("C001", RecommendationAction.INCREASE),
        _recommendation("C002", RecommendationAction.INCREASE),
        _recommendation("C003", RecommendationAction.INCREASE),
    )
    scores = (_score("C001", 80), _score("C002", 100), _score("C003", 80))
    forward = rank_campaign_reallocation_priorities(recs, scores)
    shuffled = rank_campaign_reallocation_priorities(
        (recs[2], recs[0], recs[1]), (scores[1], scores[2], scores[0])
    )
    assert forward.model_dump() == shuffled.model_dump()


def test_no_normalisation_score_preserved_exactly():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("C001", RecommendationAction.INCREASE),), (_score("C001", 20),)
    )
    assert result.increase_rankings[0].reallocation_priority_score == 20


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def test_authorised_fields_are_exactly_four():
    source = inspect.getsource(rank_campaign_reallocation_priorities)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)

    attrs_by_name: dict[str, set[str]] = {"recommendation": set(), "score": set()}
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in attrs_by_name:
                attrs_by_name[node.value.id].add(node.attr)

    assert attrs_by_name["recommendation"] == {"campaign_id", "recommendation_action"}
    assert attrs_by_name["score"] == {"campaign_id", "reallocation_priority_score"}


def test_does_not_call_earlier_production_functions():
    import src.ranking as ranking_module

    source = inspect.getsource(ranking_module)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "resolve_campaign_recommendation_action",
        "calculate_campaign_reallocation_priority_score",
        "resolve_campaign_action_suitability",
        "resolve_campaign_action_availability",
        "resolve_campaign_recommendation_reason",
        "assess_campaign_tracking",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "calculate_campaign_metrics",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_module_does_not_reference_excluded_names():
    import src.ranking as ranking_module

    source = inspect.getsource(ranking_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    forbidden = {
        "confidence_component",
        "business_priority_component",
        "ReasonCode",
        "CampaignRecommendationReason",
        "CampaignPerformanceClass",
        "PerformanceBand",
        "CampaignTrendClass",
        "TrendDirection",
        "CampaignPacingClass",
        "PacingStatus",
        "CampaignConfidenceClass",
        "Confidence",
        "CampaignTrackingAssessment",
        "CampaignActionAvailability",
        "CampaignActionSuitability",
        "CampaignInput",
        "BusinessPriority",
        "CampaignRawIncreaseLimit",
        "CampaignRawDecreaseLimit",
        "CampaignEffectiveDecreaseLimit",
        "CampaignStaticBudgetRoom",
        "CampaignTestFloorRoom",
        "CampaignApplicableChangePercentage",
        "CampaignRawPercentageMovementCap",
        "CampaignProtectionConstraint",
        "Decimal",
        "float",
        "normalize",
        "normalise",
        "allocate",
        "allocation",
        "conservation",
    }
    assert referenced.isdisjoint(forbidden)


def test_module_does_not_import_excluded_types():
    import src.ranking as ranking_module

    for forbidden_name in (
        "ReasonCode",
        "CampaignRecommendationReason",
        "CampaignPerformanceClass",
        "PerformanceBand",
        "CampaignTrendClass",
        "TrendDirection",
        "CampaignPacingClass",
        "PacingStatus",
        "CampaignConfidenceClass",
        "Confidence",
        "CampaignTrackingAssessment",
        "CampaignActionAvailability",
        "CampaignActionSuitability",
        "CampaignInput",
        "BusinessPriority",
    ):
        assert not hasattr(ranking_module, forbidden_name)


def test_no_float_or_decimal_in_module():
    import src.ranking as ranking_module

    source = inspect.getsource(ranking_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "Decimal" not in referenced
    assert "float" not in referenced


def test_no_monetary_arithmetic_in_module():
    import src.ranking as ranking_module

    source = inspect.getsource(ranking_module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            assert not isinstance(node.op, (ast.Mult, ast.Div, ast.FloorDiv))


def test_no_in_place_sort_mutation():
    import src.ranking as ranking_module

    source = inspect.getsource(ranking_module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "sort":
            pytest.fail("in-place .sort() must not be used; use sorted() instead")
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "sorted" in called_names


def test_no_production_batch_function_beyond_the_approved_one():
    import src.ranking as ranking_module

    assert not hasattr(ranking_module, "rank_campaign_reallocation_priorities_batch")


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_ranking_exact_result():
    review = _review(default_max_change_percentage=Decimal("0.20"))
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    assert len(report.valid_campaigns) == 4

    built = [_build_recommendation_and_score(c, review) for c in report.valid_campaigns]
    recommendations = tuple(recommendation for recommendation, _ in built)
    scores = tuple(score for _, score in built)

    result = rank_campaign_reallocation_priorities(recommendations, scores)

    assert result == CampaignReallocationRanking(
        increase_rankings=(
            RankedCampaignPriority(campaign_id="G002", rank=1, reallocation_priority_score=100),
        ),
        reduce_rankings=(),
    )


# ---------------------------------------------------------------------------
# Hypothetical portfolios
# ---------------------------------------------------------------------------


def test_hypothetical_multiple_increase_scores():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("A", RecommendationAction.INCREASE),
            _recommendation("B", RecommendationAction.INCREASE),
            _recommendation("C", RecommendationAction.INCREASE),
        ),
        (_score("A", 40), _score("B", 100), _score("C", 60)),
    )
    assert [r.campaign_id for r in result.increase_rankings] == ["B", "C", "A"]
    assert result.reduce_rankings == ()


def test_hypothetical_multiple_reduce_scores():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("A", RecommendationAction.REDUCE),
            _recommendation("B", RecommendationAction.REDUCE),
        ),
        (_score("A", 20), _score("B", 80)),
    )
    assert [r.campaign_id for r in result.reduce_rankings] == ["B", "A"]
    assert result.increase_rankings == ()


def test_hypothetical_both_directions_populated_simultaneously():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("A", RecommendationAction.INCREASE),
            _recommendation("B", RecommendationAction.REDUCE),
            _recommendation("C", RecommendationAction.MAINTAIN),
            _recommendation("D", RecommendationAction.HOLD),
        ),
        (_score("A", 60), _score("B", 40), _score("C", 0), _score("D", 0)),
    )
    assert [r.campaign_id for r in result.increase_rankings] == ["A"]
    assert [r.campaign_id for r in result.reduce_rankings] == ["B"]


def test_hypothetical_empty_direction():
    result = rank_campaign_reallocation_priorities(
        (_recommendation("A", RecommendationAction.INCREASE),), (_score("A", 60),)
    )
    assert result.reduce_rankings == ()


def test_hypothetical_zero_score_directional_records():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("A", RecommendationAction.INCREASE),
            _recommendation("B", RecommendationAction.REDUCE),
        ),
        (_score("A", 0), _score("B", 0)),
    )
    assert result.increase_rankings == ()
    assert result.reduce_rankings == ()


def test_hypothetical_no_eligible_candidates():
    result = rank_campaign_reallocation_priorities(
        (
            _recommendation("A", RecommendationAction.HOLD),
            _recommendation("B", RecommendationAction.MAINTAIN),
        ),
        (_score("A", 0), _score("B", 0)),
    )
    assert result == CampaignReallocationRanking(increase_rankings=(), reduce_rankings=())
