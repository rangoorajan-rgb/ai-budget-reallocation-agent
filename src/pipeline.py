"""Deterministic end-to-end pipeline orchestration and portfolio reporting.

Implements Sprint 1 — Development Stage 27: the final deterministic
responsibility. `run_budget_reallocation_review` orchestrates the already
fully-approved Stage 1–26 production functions, in their exact frozen
dependency order, over one already-validated `ReviewSetup` and one
already-validated `tuple[CampaignInput, ...]`, and returns one compact,
typed, auditable portfolio result. This completes the master plan's
Sprint 2 "Deterministic Core Engine" goal — it does not implement
Streamlit, Gemini explanation, human approval, audit persistence, exports,
or Sprint 4 hardening, all of which remain explicitly out of scope.

**Validation remains entirely outside this module.** `ReviewSetup` and
every `CampaignInput` are accepted only in their already-validated,
already-constructed form — this module never reads a CSV, never calls
`validate_campaign_csv`, never returns validation issues, and never
re-checks campaign-ID uniqueness (already a Stage 2 responsibility,
trusted here exactly as every downstream stage since Stage 12 has trusted
its own upstream guarantees). An empty campaign tuple is valid and
produces an empty portfolio result.

**Pure orchestration — no formula is duplicated, approximated, or
reopened.** Every deterministic fact is produced by calling the real,
already-approved Stage 1–26 function that owns it; this module never
reimplements a rule inline and never recalculates a value already
supplied by an upstream result object. The only new arithmetic introduced
here is the explicitly authorised final-budget formula below.

**Dependency order per campaign** (Stages 3–23), followed by three
portfolio-level calls (Stages 24–26), followed by final assembly in the
original input order:
```
metrics → pacing → pacing classification
        → performance classification
        → trend classification
        → confidence classification
        → tracking assessment
        → static budget room → applicable change percentage
        → raw percentage movement cap → test floor room
        → protection constraint → test-aware static decrease room
        → raw increase limit → raw decrease limit → effective decrease limit
        → action availability → action suitability
        → recommendation action → recommendation reasons
        → reallocation priority score
[once per portfolio] → ranking → allocation → conservation
```

**Final movement.** Exactly one unsigned `allocated_amount` is exposed per
campaign — direction is already fully carried by `recommendation_action`,
never re-encoded through sign. For a directional (`INCREASE`/`REDUCE`)
recommendation matched to a Stage 25 allocation record, that record's
exact `allocated_amount` is used. For `HOLD`/`MAINTAIN`, and for a
directional recommendation with no matching allocation record (excluded
from Stage 24's ranking because its Stage 23 score was zero, or ranked
but left unfunded by Stage 25's waterfall), `allocated_amount` is exactly
`Decimal("0.00")`. **A zero-funded `INCREASE`/`REDUCE` recommendation is
never rewritten to `MAINTAIN`/`HOLD`** — the campaign was assessed as
directionally appropriate; the portfolio simply moved no money this
cycle, a materially different fact. All cross-collection matching (rank,
allocation) is by `campaign_id` value, never by tuple position.

**Final-budget formula**, using only Stage 25's actual allocated amount —
never raw or effective constraint limits directly:
```
INCREASE → current_budget + allocated_amount
REDUCE   → current_budget - allocated_amount
MAINTAIN → current_budget
HOLD     → current_budget
```
Every addition, subtraction, and portfolio-level sum runs inside an
explicitly-scoped `localcontext`, with precision derived from the actual
operands' digit counts and collection size — never a blindly assumed
fixed value and never dependent on the ambient global `Decimal` context,
directly extending the corrected discipline established at Stages 25 and
26. `float` is never used.

**Conservation is always exposed, never hidden, never repaired.** The
embedded Stage 26 `CampaignReallocationConservation` result is returned
unchanged inside the portfolio result regardless of its
`is_conserved` value — this module never raises merely because an
allocation is unconserved. As a defence-in-depth check distinct from, and
never a replacement for, Stage 26's own invariant, this module verifies
that a *conserved* allocation also preserves the portfolio's total
budget (`total_recommended_budget == total_current_budget` whenever
`conservation.is_conserved`), raising `RuntimeError` only if that
narrower, additional guarantee is ever violated — which would indicate a
defect in this module's own campaign-to-allocation matching, not in
Stage 25/26 themselves.

**Reasons pass through unchanged.** Stage 22's ordered `reason_codes`
tuple is exposed exactly as produced — never recomputed, never appended
to, and no allocation-specific reason code is ever invented.

**Fails fast.** Any unexpected exception, or a `ValueError` raised by an
underlying Stage 1–26 function, propagates unchanged — there is no
`try`/`except`, no retry, and no partial portfolio result; no campaign is
ever silently dropped. No input or upstream result object is ever
mutated.
"""

from decimal import Decimal, localcontext

from pydantic import BaseModel, ConfigDict, Field

from src.allocation import allocate_campaign_reallocation
from src.availability import resolve_campaign_action_availability
from src.classification import (
    assess_campaign_tracking,
    classify_campaign_confidence,
    classify_campaign_performance,
    classify_campaign_trend,
)
from src.classification import PerformanceBand, TrendDirection
from src.conservation import (
    CampaignReallocationConservation,
    verify_campaign_reallocation_conservation,
)
from src.constants import Confidence, Platform, ReasonCode, RecommendationAction
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
from src.models import CampaignInput, Currency, ReviewSetup
from src.pacing import PacingStatus, calculate_campaign_pacing, classify_campaign_pacing
from src.ranking import rank_campaign_reallocation_priorities
from src.reasons import resolve_campaign_recommendation_reason
from src.recommendation import resolve_campaign_recommendation_action
from src.scoring import calculate_campaign_reallocation_priority_score
from src.suitability import resolve_campaign_action_suitability


def _safe_precision(operand_digit_counts: list[int], term_count: int) -> int:
    """Derive a local precision sufficient for the given operands' own
    digit counts and the number of terms being combined, immune to the
    ambient global Decimal context and never a blindly assumed fixed
    value."""
    max_operand_digits = max(operand_digit_counts) if operand_digit_counts else 1
    count_digits = len(str(max(term_count, 1)))
    return max(28, max_operand_digits + count_digits + 10)


def _sum_currency(values: list[Decimal]) -> Decimal:
    """Sum already-quantised currency values inside an explicitly-scoped
    local context sized for the actual operands and collection size."""
    if not values:
        return Decimal("0.00")

    safe_precision = _safe_precision(
        [len(value.as_tuple().digits) for value in values], len(values)
    )
    with localcontext() as ctx:
        ctx.prec = safe_precision
        total = Decimal("0.00")
        for value in values:
            total += value
    return total


def _compute_recommended_budget(
    action: RecommendationAction, current_budget: Decimal, allocated_amount: Decimal
) -> Decimal:
    """Apply the exact authorised final-budget formula, using only
    Stage 25's actual allocated amount."""
    if action is RecommendationAction.INCREASE:
        safe_precision = _safe_precision(
            [len(current_budget.as_tuple().digits), len(allocated_amount.as_tuple().digits)],
            2,
        )
        with localcontext() as ctx:
            ctx.prec = safe_precision
            return current_budget + allocated_amount
    if action is RecommendationAction.REDUCE:
        safe_precision = _safe_precision(
            [len(current_budget.as_tuple().digits), len(allocated_amount.as_tuple().digits)],
            2,
        )
        with localcontext() as ctx:
            ctx.prec = safe_precision
            return current_budget - allocated_amount
    return current_budget


class CampaignBudgetRecommendationResult(BaseModel):
    """One campaign's complete, minimal, deterministic recommendation
    result for portfolio reporting.

    Direction is carried only by `recommendation_action`; `allocated_amount`
    is always unsigned. Not an allocation record, a ranking record, an
    availability/suitability judgement, a tracking assessment, a
    validation result, or an explanation — those remain the responsibility
    of their own already-approved stages.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    campaign_name: str
    platform: Platform
    current_budget: Currency
    recommendation_action: RecommendationAction
    allocated_amount: Currency = Field(ge=0)
    recommended_budget: Currency = Field(ge=0)
    reason_codes: tuple[ReasonCode, ...]
    performance_band: PerformanceBand
    trend_direction: TrendDirection
    confidence: Confidence
    pacing_status: PacingStatus
    reallocation_priority_score: int = Field(ge=0, le=100)
    rank: int | None = Field(default=None, ge=1)


class BudgetReallocationReviewResult(BaseModel):
    """One deterministic, auditable portfolio-level result for an entire
    budget-reallocation review.

    Not a validation report, an audit record, an export, or an
    AI-generated explanation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str
    campaign_results: tuple[CampaignBudgetRecommendationResult, ...]
    total_current_budget: Currency = Field(ge=0)
    total_recommended_budget: Currency = Field(ge=0)
    conservation: CampaignReallocationConservation


def run_budget_reallocation_review(
    review: ReviewSetup,
    campaigns: tuple[CampaignInput, ...],
) -> BudgetReallocationReviewResult:
    """Orchestrate the complete Stage 1–26 deterministic chain over one
    already-validated review and campaign collection, returning one
    portfolio-level result.

    Calls every already-approved Stage 3–26 production function in its
    exact frozen dependency order; never reimplements, approximates, or
    recalculates any of their rules. `campaign_results` preserves the
    original `campaigns` order. All cross-collection matching (Stage 24
    rank, Stage 25 allocation) is by `campaign_id`, never position. Always
    returns a result, embedding Stage 26's conservation status unchanged —
    never raises merely because an allocation is unconserved. Raises
    `RuntimeError` only if a *conserved* allocation's recomputed totals
    fail to match exactly, and lets any Stage 1–26 `ValueError` or other
    unexpected exception propagate unchanged.
    """
    recommendation_by_id: dict[str, RecommendationAction] = {}
    reason_codes_by_id: dict[str, tuple[ReasonCode, ...]] = {}
    performance_by_id: dict[str, PerformanceBand] = {}
    trend_by_id: dict[str, TrendDirection] = {}
    confidence_by_id: dict[str, Confidence] = {}
    pacing_status_by_id: dict[str, PacingStatus] = {}
    score_value_by_id: dict[str, int] = {}

    recommendations = []
    scores = []
    increase_limits = []
    decrease_limits = []

    for campaign in campaigns:
        metrics = calculate_campaign_metrics(campaign)
        pacing = calculate_campaign_pacing(review, campaign)
        pacing_class = classify_campaign_pacing(pacing)
        performance = classify_campaign_performance(metrics)
        trend = classify_campaign_trend(metrics)
        confidence = classify_campaign_confidence(campaign)
        tracking = assess_campaign_tracking(campaign)

        static_room = calculate_campaign_static_budget_room(campaign)
        applicable_percentage = resolve_campaign_applicable_change_percentage(
            review, campaign
        )
        raw_cap = calculate_campaign_raw_percentage_movement_cap(
            campaign, applicable_percentage
        )
        test_floor_room = calculate_campaign_test_floor_room(campaign)
        protection = resolve_campaign_protection_constraint(campaign)
        decrease_room = resolve_campaign_test_aware_static_decrease_room(
            static_room, test_floor_room
        )
        raw_increase = resolve_campaign_raw_increase_limit(static_room, raw_cap)
        raw_decrease = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
        effective_decrease = resolve_campaign_effective_decrease_limit(
            raw_decrease, protection
        )

        availability = resolve_campaign_action_availability(
            campaign, tracking, raw_increase, effective_decrease
        )
        suitability = resolve_campaign_action_suitability(performance, trend, availability)
        recommendation = resolve_campaign_recommendation_action(
            campaign, suitability, tracking
        )
        reason = resolve_campaign_recommendation_reason(
            recommendation, campaign, suitability, tracking, performance, trend
        )
        score = calculate_campaign_reallocation_priority_score(
            recommendation, campaign, confidence
        )

        recommendations.append(recommendation)
        scores.append(score)
        increase_limits.append(raw_increase)
        decrease_limits.append(effective_decrease)

        campaign_id = campaign.campaign_id
        recommendation_by_id[campaign_id] = recommendation.recommendation_action
        reason_codes_by_id[campaign_id] = reason.reason_codes
        performance_by_id[campaign_id] = performance.performance_band
        trend_by_id[campaign_id] = trend.trend_direction
        confidence_by_id[campaign_id] = confidence.confidence
        pacing_status_by_id[campaign_id] = pacing_class.pacing_status
        score_value_by_id[campaign_id] = score.reallocation_priority_score

    ranking = rank_campaign_reallocation_priorities(tuple(recommendations), tuple(scores))
    allocation = allocate_campaign_reallocation(
        ranking, tuple(increase_limits), tuple(decrease_limits)
    )
    conservation = verify_campaign_reallocation_conservation(allocation)

    rank_by_id: dict[str, int] = {}
    for ranked in ranking.increase_rankings:
        rank_by_id[ranked.campaign_id] = ranked.rank
    for ranked in ranking.reduce_rankings:
        rank_by_id[ranked.campaign_id] = ranked.rank

    allocated_amount_by_id: dict[str, Decimal] = {}
    for record in allocation.increase_allocations:
        allocated_amount_by_id[record.campaign_id] = record.allocated_amount
    for record in allocation.decrease_allocations:
        allocated_amount_by_id[record.campaign_id] = record.allocated_amount

    campaign_results: list[CampaignBudgetRecommendationResult] = []
    current_budgets: list[Decimal] = []
    recommended_budgets: list[Decimal] = []

    for campaign in campaigns:
        campaign_id = campaign.campaign_id
        action = recommendation_by_id[campaign_id]
        allocated_amount = allocated_amount_by_id.get(campaign_id, Decimal("0.00"))
        recommended_budget = _compute_recommended_budget(
            action, campaign.current_budget, allocated_amount
        )

        campaign_results.append(
            CampaignBudgetRecommendationResult(
                campaign_id=campaign_id,
                campaign_name=campaign.campaign_name,
                platform=campaign.platform,
                current_budget=campaign.current_budget,
                recommendation_action=action,
                allocated_amount=allocated_amount,
                recommended_budget=recommended_budget,
                reason_codes=reason_codes_by_id[campaign_id],
                performance_band=performance_by_id[campaign_id],
                trend_direction=trend_by_id[campaign_id],
                confidence=confidence_by_id[campaign_id],
                pacing_status=pacing_status_by_id[campaign_id],
                reallocation_priority_score=score_value_by_id[campaign_id],
                rank=rank_by_id.get(campaign_id),
            )
        )
        current_budgets.append(campaign.current_budget)
        recommended_budgets.append(recommended_budget)

    total_current_budget = _sum_currency(current_budgets)
    total_recommended_budget = _sum_currency(recommended_budgets)

    if conservation.is_conserved and total_recommended_budget != total_current_budget:
        raise RuntimeError(
            "Conserved allocation must preserve the total campaign budget."
        )

    return BudgetReallocationReviewResult(
        review_id=review.review_id,
        campaign_results=tuple(campaign_results),
        total_current_budget=total_current_budget,
        total_recommended_budget=total_recommended_budget,
        conservation=conservation,
    )
