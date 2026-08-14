"""Deterministic per-campaign recommendation reasons.

Implements Sprint 1 — Development Stage 22: for one already-selected
`CampaignRecommendation` (Stage 21), together with the exact upstream facts
Stage 21 itself consumed or could have consumed —
`CampaignInput`, `CampaignActionSuitability` (Stage 20),
`CampaignTrackingAssessment` (Stage 8), `CampaignPerformanceClass` (Stage 5),
and `CampaignTrendClass` (Stage 6) — produces a non-empty, ordered,
deduplicated tuple of `ReasonCode` explaining *why* that action was selected.

Stage 22 explains an already-selected action; it does not select or change
it, and it never calls `resolve_campaign_recommendation_action` or any other
Stage 1–21 production function. Reasons include only facts that causally
participated in Stage 21's decision — never a diagnostic fact Stage 21 never
consulted, an explanation for an unavailable alternative action, or a
monetary constraint.

**HOLD** mirrors Stage 21's exact precedence:

1. `campaign.status is CampaignStatus.PAUSED` → `(PAUSED_CAMPAIGN,)`. This
   remains the sole reason even when tracking is simultaneously unassessable
   — Stage 21's own short-circuit logic never reaches the assessability
   check once Paused has already resolved `HOLD`, so citing
   `TRACKING_UNRELIABLE` too would cite a fact Stage 21 never actually
   consulted on that execution path.
2. Otherwise, `not tracking.is_assessable` → `(TRACKING_UNRELIABLE,)`.
3. Otherwise (multiple-`SUITABLE` ambiguity or no valid `MAINTAIN`
   fallback — the only two remaining ways Stage 21 can produce `HOLD`) →
   `(HELD_FOR_MANUAL_REVIEW,)`. Never used for a non-HOLD action, since
   `MAINTAIN` is itself an assessed, confident decision, not a deferral.

**INCREASE**, **MAINTAIN**, and **REDUCE** are explained by the same
`PerformanceBand`/`TrendDirection` pair Stage 20 used to determine
suitability, via two fixed, immutable lookup tables:
`PerformanceBand.ABOVE_TARGET` → `ABOVE_TARGET_STRONG`,
`PerformanceBand.ON_TARGET` → `NEAR_TARGET`, `PerformanceBand.BELOW_TARGET`
→ no performance reason (an approved severity classification distinguishing
`BELOW_TARGET_MODERATE`/`BELOW_TARGET_SEVERE` does not exist — this is an
intentional, documented limitation, not an invitation to invent a
threshold); `TrendDirection.IMPROVING`/`STABLE`/`DECLINING` map 1:1 to
`RECENT_TREND_IMPROVING`/`RECENT_TREND_STABLE`/`RECENT_TREND_DECLINING`
unconditionally. The performance reason (when available) precedes the trend
reason. This table-driven approach reproduces every mapping explicitly
approved for Stage 22, including the seven enumerated `MAINTAIN` cells, and
extends the identical, already-approved logic to the two `MAINTAIN` cells
that share a `PerformanceBand`/`TrendDirection` pair with `INCREASE`'s or
`REDUCE`'s own diagonal (reachable when Stage 19 availability blocks the
otherwise-`SUITABLE` direction) — not a new invented rule, the same
performance/trend mapping already governing every other cell.

Stage 22 never emits `TRACKING_WARNING`, `INSUFFICIENT_CONVERSION_VOLUME`,
`PROTECTED_FROM_REDUCTION`, `BELOW_TARGET_MODERATE`, `BELOW_TARGET_SEVERE`,
`STRONG_LONG_TERM_RECENT_DECLINE`, `CAMPAIGN_CAP_REACHED`,
`CAMPAIGN_FLOOR_REACHED`, `TEST_BUDGET_FLOOR_APPLIED`,
`MAX_CHANGE_LIMIT_APPLIED`, `NO_ELIGIBLE_RECIPIENT`, or
`ACCOUNT_RESERVE_REQUIRED` — these remain deferred pending an approved
severity classification, preserved constraint binding-source identity, or a
later cross-campaign allocation stage; none is read, imported, or emitted
here. It never reads raw metrics, monetary constraint results, `Confidence`,
`PacingStatus`, `tracking_status`, `is_protected`, `is_test_campaign`,
`test_budget_floor`, `BusinessPriority`, or allocation data — only the 14
fields named above. It requires all six `campaign_id` values to match
`recommendation.campaign_id`, raising `ValueError` otherwise, checked before
any reason is resolved. No `Decimal` calculation occurs anywhere in this
module.
"""

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from src.classification import (
    CampaignPerformanceClass,
    CampaignTrackingAssessment,
    CampaignTrendClass,
    PerformanceBand,
    TrendDirection,
)
from src.constants import CampaignStatus, ReasonCode, RecommendationAction
from src.models import CampaignInput
from src.recommendation import CampaignRecommendation
from src.suitability import CampaignActionSuitability, Suitability

# Fixed, immutable performance-reason lookup. BELOW_TARGET maps to None
# because no approved severity classification exists to choose between
# BELOW_TARGET_MODERATE and BELOW_TARGET_SEVERE.
_PERFORMANCE_REASON_CODES: "MappingProxyType[PerformanceBand, ReasonCode | None]" = MappingProxyType(
    {
        PerformanceBand.ABOVE_TARGET: ReasonCode.ABOVE_TARGET_STRONG,
        PerformanceBand.ON_TARGET: ReasonCode.NEAR_TARGET,
        PerformanceBand.BELOW_TARGET: None,
    }
)

# Fixed, immutable trend-reason lookup. Every TrendDirection member maps
# unconditionally to a ReasonCode.
_TREND_REASON_CODES: "MappingProxyType[TrendDirection, ReasonCode]" = MappingProxyType(
    {
        TrendDirection.IMPROVING: ReasonCode.RECENT_TREND_IMPROVING,
        TrendDirection.STABLE: ReasonCode.RECENT_TREND_STABLE,
        TrendDirection.DECLINING: ReasonCode.RECENT_TREND_DECLINING,
    }
)


class CampaignRecommendationReason(BaseModel):
    """Non-empty, ordered, deduplicated `ReasonCode` tuple explaining one
    campaign's already-selected `RecommendationAction`.

    Not the `RecommendationAction` itself (retained separately on
    `CampaignRecommendation`), a monetary amount, a score, a rank, a
    priority, or an allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    reason_codes: tuple[ReasonCode, ...]


def resolve_campaign_recommendation_reason(
    recommendation: CampaignRecommendation,
    campaign: CampaignInput,
    suitability: CampaignActionSuitability,
    tracking: CampaignTrackingAssessment,
    performance: CampaignPerformanceClass,
    trend: CampaignTrendClass,
) -> CampaignRecommendationReason:
    """Explain one campaign's already-selected `RecommendationAction`.

    For `HOLD`, mirrors Stage 21's exact precedence: a Paused campaign
    yields `(PAUSED_CAMPAIGN,)` alone even when tracking is also
    unassessable; otherwise unassessable tracking yields
    `(TRACKING_UNRELIABLE,)`; otherwise (multiple-SUITABLE ambiguity or no
    valid MAINTAIN fallback) yields `(HELD_FOR_MANUAL_REVIEW,)`. For
    `INCREASE`, `MAINTAIN`, and `REDUCE`, looks up a performance reason
    (omitted for `BELOW_TARGET`) and a trend reason from
    `performance.performance_band`/`trend.trend_direction`, performance
    first. Requires `campaign.campaign_id == suitability.campaign_id ==
    tracking.campaign_id == performance.campaign_id == trend.campaign_id ==
    recommendation.campaign_id`, raising `ValueError` otherwise.
    """
    if not (
        campaign.campaign_id == recommendation.campaign_id
        and suitability.campaign_id == recommendation.campaign_id
        and tracking.campaign_id == recommendation.campaign_id
        and performance.campaign_id == recommendation.campaign_id
        and trend.campaign_id == recommendation.campaign_id
    ):
        raise ValueError(
            "Campaign IDs must match when resolving recommendation reasons."
        )

    if recommendation.recommendation_action is RecommendationAction.HOLD:
        if campaign.status is CampaignStatus.PAUSED:
            reason_codes: tuple[ReasonCode, ...] = (ReasonCode.PAUSED_CAMPAIGN,)
        elif not tracking.is_assessable:
            reason_codes = (ReasonCode.TRACKING_UNRELIABLE,)
        else:
            suitable_count = sum(
                1
                for value in (
                    suitability.increase_suitability,
                    suitability.maintain_suitability,
                    suitability.reduce_suitability,
                )
                if value is Suitability.SUITABLE
            )
            if suitable_count > 1:
                reason_codes = (ReasonCode.HELD_FOR_MANUAL_REVIEW,)
            else:
                reason_codes = (ReasonCode.HELD_FOR_MANUAL_REVIEW,)
    else:
        performance_reason = _PERFORMANCE_REASON_CODES[performance.performance_band]
        trend_reason = _TREND_REASON_CODES[trend.trend_direction]
        if performance_reason is not None:
            reason_codes = (performance_reason, trend_reason)
        else:
            reason_codes = (trend_reason,)

    reason_codes = tuple(dict.fromkeys(reason_codes))

    return CampaignRecommendationReason(
        campaign_id=recommendation.campaign_id,
        reason_codes=reason_codes,
    )
