"""Deterministic per-campaign reallocation priority scoring.

Implements Sprint 1 — Development Stage 23: for one already-selected
`CampaignRecommendation` (Stage 21), one already-validated `CampaignInput`,
and one already-calculated `CampaignConfidenceClass` (Stage 7), computes a
single campaign-level, dimensionless `int` score expressing the relative
priority with which an already-selected *directional* recommendation should
be considered during a later cross-campaign ranking stage.

**Comparable only within the same direction.** A higher score means a
stronger candidate *within the same recommendation direction* — `INCREASE`
scores must later be compared only with other `INCREASE` scores, and
`REDUCE` scores must later be compared only with other `REDUCE` scores. The
score must never be used to compare an `INCREASE` directly against a
`REDUCE`; direction remains solely and authoritatively carried by
`CampaignRecommendation.recommendation_action`, never re-encoded through
sign or magnitude here.

**Non-directional actions.** `HOLD` and `MAINTAIN` propose no directional
budget movement for the later ranking stage, so both receive an all-zero
result unconditionally — this does not mean either action is invalid, only
that neither has anything to prioritise directionally. Confidence and
business-priority mappings are never inspected or applied once a
non-directional action is identified.

**`Confidence.NOT_ASSESSABLE` override.** An `INCREASE` or `REDUCE`
recommendation paired with `Confidence.NOT_ASSESSABLE` also receives an
all-zero result — a scoring-only override that neither changes the existing
`recommendation_action` nor raises an error.

**Confidence measures evidence reliability**, via a fixed, immutable
mapping: `HIGH` → 60, `MEDIUM` → 40, `LOW` → 20.

**Business priority is direction-aware** — it answers two different
questions depending on direction, via two fixed, immutable mappings.
For `INCREASE` (favouring higher-priority campaigns as recipients of
additional budget): `HIGH` → 40, `MEDIUM` → 20, `STANDARD` → 0. For
`REDUCE` (favouring lower-priority campaigns as possible budget donors):
`STANDARD` → 40, `MEDIUM` → 20, `HIGH` → 0.

For an assessable directional recommendation, `reallocation_priority_score
= confidence_component + business_priority_component`, always one of `{20,
40, 60, 80, 100}`; non-directional or `NOT_ASSESSABLE`-overridden results
are always `0`. All three fields are plain Python `int`, never `float` or
`Decimal` — the score is dimensionless, requires no rounding or
quantisation, and no ambient `Decimal` context affects it.

**Not double-counted.** `PerformanceBand`/`CampaignPerformanceClass` and
`TrendDirection`/`CampaignTrendClass` already caused Stage 20's suitability
judgement and Stage 21's recommendation selection — scoring them again here
would double-count the same action evidence, so neither is read or
imported. `CampaignActionAvailability`, `CampaignActionSuitability`, and
`CampaignTrackingAssessment` have already been fully consumed downstream by
Stage 21's action selection and are not re-read here.
`CampaignRecommendationReason`/`ReasonCode` explain the decision and must
never become hidden numeric weights, so neither is read or imported.
`PacingStatus`/`CampaignPacingClass` has no approved direction-specific
prioritisation policy and is excluded. Raw campaign metrics, weighted
performance ratio, trend delta, monetary constraint results (raw/effective
increase/decrease limits), protection, test-campaign status, and tracking
status are all excluded — they answer how much money can move or whether an
action is mechanically available, not how strongly a campaign should be
prioritised for a direction it already qualifies for.

**Not this stage's responsibility.** Stage 23 performs no sorting,
normalisation, ranking, allocation, conservation, monetary calculation, or
AI explanation, and it never modifies the recommendation it scores.
Tie-breaking among equal scores is deferred entirely to the later
cross-campaign ranking stage. It requires all three `campaign_id` values to
match, raising `ValueError` otherwise, checked before any action,
confidence, or priority value is read. It never calls
`resolve_campaign_recommendation_action` or any other Stage 1–22 production
function — it consumes their already-approved outputs directly. It is
completely single-campaign: no other campaign's data is read, compared, or
required.
"""

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.classification import CampaignConfidenceClass
from src.constants import BusinessPriority, Confidence, RecommendationAction
from src.models import CampaignInput
from src.recommendation import CampaignRecommendation

# Fixed, immutable confidence-component lookup. NOT_ASSESSABLE is handled by
# the dedicated override in calculate_campaign_reallocation_priority_score,
# never through this mapping.
_CONFIDENCE_COMPONENT: "MappingProxyType[Confidence, int]" = MappingProxyType(
    {
        Confidence.HIGH: 60,
        Confidence.MEDIUM: 40,
        Confidence.LOW: 20,
    }
)

# Fixed, immutable business-priority-component lookup for INCREASE —
# favours higher-priority campaigns as recipients of additional budget.
_INCREASE_BUSINESS_PRIORITY_COMPONENT: "MappingProxyType[BusinessPriority, int]" = MappingProxyType(
    {
        BusinessPriority.HIGH: 40,
        BusinessPriority.MEDIUM: 20,
        BusinessPriority.STANDARD: 0,
    }
)

# Fixed, immutable business-priority-component lookup for REDUCE —
# favours lower-priority campaigns as possible budget donors.
_REDUCE_BUSINESS_PRIORITY_COMPONENT: "MappingProxyType[BusinessPriority, int]" = MappingProxyType(
    {
        BusinessPriority.STANDARD: 40,
        BusinessPriority.MEDIUM: 20,
        BusinessPriority.HIGH: 0,
    }
)


class CampaignReallocationPriorityScore(BaseModel):
    """Deterministic, campaign-level reallocation priority score for one
    campaign's already-selected `RecommendationAction`.

    Comparable only within the same direction — never between `INCREASE`
    and `REDUCE`. Not a monetary amount, a rank, an allocation, or a
    duplicate of `RecommendationAction` (never carried here).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    confidence_component: int = Field(ge=0, le=100)
    business_priority_component: int = Field(ge=0, le=100)
    reallocation_priority_score: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _check_total_consistency(self) -> "CampaignReallocationPriorityScore":
        if self.reallocation_priority_score != (
            self.confidence_component + self.business_priority_component
        ):
            raise ValueError(
                "reallocation_priority_score must equal confidence_component "
                "+ business_priority_component"
            )
        return self


def calculate_campaign_reallocation_priority_score(
    recommendation: CampaignRecommendation,
    campaign: CampaignInput,
    confidence: CampaignConfidenceClass,
) -> CampaignReallocationPriorityScore:
    """Score one campaign's already-selected `RecommendationAction` for
    later same-direction cross-campaign ranking.

    `HOLD`/`MAINTAIN` and `Confidence.NOT_ASSESSABLE`-paired `INCREASE`/
    `REDUCE` all yield an all-zero result. Otherwise, `confidence_component`
    comes from the fixed `Confidence` mapping and `business_priority_component`
    from the fixed, direction-specific `BusinessPriority` mapping; their sum
    is `reallocation_priority_score`. Requires `campaign.campaign_id ==
    confidence.campaign_id == recommendation.campaign_id`, raising
    `ValueError` otherwise.
    """
    if not (
        campaign.campaign_id == recommendation.campaign_id
        and confidence.campaign_id == recommendation.campaign_id
    ):
        raise ValueError(
            "Campaign IDs must match when calculating reallocation priority score."
        )

    action = recommendation.recommendation_action

    if action is RecommendationAction.HOLD or action is RecommendationAction.MAINTAIN:
        confidence_component = 0
        business_priority_component = 0
    elif confidence.confidence is Confidence.NOT_ASSESSABLE:
        confidence_component = 0
        business_priority_component = 0
    else:
        confidence_component = _CONFIDENCE_COMPONENT[confidence.confidence]
        if action is RecommendationAction.INCREASE:
            business_priority_component = _INCREASE_BUSINESS_PRIORITY_COMPONENT[
                campaign.business_priority
            ]
        else:
            business_priority_component = _REDUCE_BUSINESS_PRIORITY_COMPONENT[
                campaign.business_priority
            ]

    reallocation_priority_score = confidence_component + business_priority_component

    return CampaignReallocationPriorityScore(
        campaign_id=recommendation.campaign_id,
        confidence_component=confidence_component,
        business_priority_component=business_priority_component,
        reallocation_priority_score=reallocation_priority_score,
    )
