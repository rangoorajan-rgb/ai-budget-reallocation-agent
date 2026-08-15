"""Deterministic cross-campaign reallocation ranking.

Implements Sprint 1 — Development Stage 24: the first genuinely
cross-campaign responsibility in this repository. For a collection of
already-selected `CampaignRecommendation` (Stage 21) matched by
`campaign_id` against a collection of already-calculated
`CampaignReallocationPriorityScore` (Stage 23), produces two completely
independent, dense-ranked, direction-scoped sequences —
`increase_rankings` and `reduce_rankings` — for later consumption by an
allocation stage.

**Direction separation.** `INCREASE` and `REDUCE` candidates are never
compared against each other, consistent with Stage 23's frozen rule that
its score is comparable only within the same direction. The first-ranked
`INCREASE` campaign and the first-ranked `REDUCE` campaign may both hold
rank `1`; their ranks carry no relationship to one another, and no global
combined rank is ever constructed. A campaign never crosses direction.

**Eligible population.** Only a directional recommendation
(`INCREASE`/`REDUCE`) paired with a strictly positive
`reallocation_priority_score` is ranked. `MAINTAIN` and `HOLD` are always
excluded, regardless of their (always-zero, per Stage 23) score. A
directional recommendation paired with a zero score — reachable through
Stage 23's `Confidence.NOT_ASSESSABLE` override — is also excluded,
because Stage 23 has already determined it has no reliable ranking
priority. Exclusion produces no output record, no reason code, and no
error; it never changes the excluded campaign's `CampaignRecommendation`
or `CampaignReallocationPriorityScore`.

**Dense ranking.** Within each direction, candidates are sorted by
`reallocation_priority_score` descending; equal scores share the same
rank with no gap in the next rank (`100, 80, 80, 60` → `1, 2, 2, 3`; all
equal → `1, 1, 1`). Ranks start at `1` and are plain `int`. `campaign_id`
ascending governs only the serialization order of tied-score records — it
never influences the assigned rank, and it is never used as a business
priority key. No other field (confidence component, business-priority
component, input position, platform, budget, performance, trend, pacing,
or monetary capacity) is ever used as a sort key — every component the
score itself already reflects must not receive additional weight through
secondary sorting.

**No normalisation.** Stage 23's score is used completely unchanged — no
percentage, percentile, portfolio-relative transform, min-max
normalisation, z-score, or direction-relative transformation is ever
computed. A single candidate scoring `20` remains `20`.

**Matching, not positional pairing.** `recommendations` and `scores` are
matched exclusively by `campaign_id` value equality — never by tuple
position, and `zip` is never used. Both input tuples' `campaign_id` values
must each be unique, and the two tuples' `campaign_id` sets must be
exactly equal; violations raise `ValueError` before any filtering,
sorting, or rank assignment occurs. Two empty input tuples are valid and
produce an empty (but not erroneous) result.

**Determinism and immutability.** Neither input tuple nor any contained
`CampaignRecommendation`/`CampaignReallocationPriorityScore` is ever
mutated or re-sorted in place; every output object is newly constructed.
Supplying the same logical records in a different input order always
produces identical serialized output.

**Monetary and allocation boundary.** Stage 24 never imports, reads, or
infers `CampaignRawIncreaseLimit`, `CampaignRawDecreaseLimit`,
`CampaignEffectiveDecreaseLimit`, static budget room, test-floor room,
percentage movement cap, binding-constraint identity, a monetary
recommendation amount, donor/recipient matching, partial allocation, or
conservation. It hands a later allocation stage only ranked campaign IDs,
their direction-scoped dense ranks, and their unchanged Stage 23 scores —
`confidence_component`, `business_priority_component`, and every
campaign-input/classification/constraint field are never read, consistent
with the authorised-field list below.

**Authorised fields.** Exactly `recommendation.campaign_id`,
`recommendation.recommendation_action`, `score.campaign_id`, and
`score.reallocation_priority_score` are read — no other field of either
input type, and no Stage 1–23 production function is ever called.
"""

from pydantic import BaseModel, ConfigDict, Field

from src.constants import RecommendationAction
from src.recommendation import CampaignRecommendation
from src.scoring import CampaignReallocationPriorityScore


class RankedCampaignPriority(BaseModel):
    """One campaign's dense rank within its own recommendation direction.

    Direction is never carried here — it is represented structurally by
    membership in `CampaignReallocationRanking.increase_rankings` or
    `.reduce_rankings`. Not a monetary amount, an allocation, an
    exclusion, or an explanation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    rank: int = Field(ge=1)
    reallocation_priority_score: int = Field(ge=1, le=100)


class CampaignReallocationRanking(BaseModel):
    """Two completely independent, dense-ranked, direction-scoped
    campaign sequences.

    `increase_rankings` and `reduce_rankings` are never compared against
    each other and never merged into a global rank. Either or both may be
    empty.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    increase_rankings: tuple[RankedCampaignPriority, ...]
    reduce_rankings: tuple[RankedCampaignPriority, ...]


def _dense_rank(
    candidates: list[tuple[str, int]],
) -> tuple[RankedCampaignPriority, ...]:
    """Dense-rank one direction's `(campaign_id, score)` candidates.

    Sorted by score descending, `campaign_id` ascending solely for
    deterministic tied-record serialization order. Equal scores share the
    same rank with no gap before the next distinct score.
    """
    ordered = sorted(candidates, key=lambda candidate: (-candidate[1], candidate[0]))

    ranked: list[RankedCampaignPriority] = []
    previous_score: int | None = None
    current_rank = 0
    for campaign_id, score_value in ordered:
        if score_value != previous_score:
            current_rank += 1
            previous_score = score_value
        ranked.append(
            RankedCampaignPriority(
                campaign_id=campaign_id,
                rank=current_rank,
                reallocation_priority_score=score_value,
            )
        )
    return tuple(ranked)


def rank_campaign_reallocation_priorities(
    recommendations: tuple[CampaignRecommendation, ...],
    scores: tuple[CampaignReallocationPriorityScore, ...],
) -> CampaignReallocationRanking:
    """Rank eligible campaigns within their own recommendation direction.

    Matches `recommendations` and `scores` by `campaign_id` value — never
    by position. Requires every `campaign_id` to be unique within each
    tuple and the two tuples' `campaign_id` sets to match exactly, raising
    `ValueError` otherwise. Only an `INCREASE`/`REDUCE` recommendation
    paired with a strictly positive score is ranked; `MAINTAIN`, `HOLD`,
    and any directional recommendation paired with a zero score are
    excluded without error, reason code, or mutation of either input.
    """
    recommendation_ids = [recommendation.campaign_id for recommendation in recommendations]
    if len(recommendation_ids) != len(set(recommendation_ids)):
        raise ValueError(
            "Recommendation campaign IDs must be unique when ranking "
            "reallocation priorities."
        )

    score_ids = [score.campaign_id for score in scores]
    if len(score_ids) != len(set(score_ids)):
        raise ValueError(
            "Score campaign IDs must be unique when ranking reallocation "
            "priorities."
        )

    if set(recommendation_ids) != set(score_ids):
        raise ValueError(
            "Recommendation and score campaign IDs must match when "
            "ranking reallocation priorities."
        )

    scores_by_campaign_id = {
        score.campaign_id: score.reallocation_priority_score for score in scores
    }

    increase_candidates: list[tuple[str, int]] = []
    reduce_candidates: list[tuple[str, int]] = []
    for recommendation in recommendations:
        action = recommendation.recommendation_action
        score_value = scores_by_campaign_id[recommendation.campaign_id]
        if action is RecommendationAction.INCREASE and score_value > 0:
            increase_candidates.append((recommendation.campaign_id, score_value))
        elif action is RecommendationAction.REDUCE and score_value > 0:
            reduce_candidates.append((recommendation.campaign_id, score_value))

    return CampaignReallocationRanking(
        increase_rankings=_dense_rank(increase_candidates),
        reduce_rankings=_dense_rank(reduce_candidates),
    )
