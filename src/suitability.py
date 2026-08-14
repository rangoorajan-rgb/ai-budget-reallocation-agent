"""Deterministic per-action campaign suitability.

Implements Sprint 1 — Development Stage 20: for one already-calculated
`CampaignPerformanceClass` (Stage 5), one already-calculated `CampaignTrendClass`
(Stage 6), and one already-calculated `CampaignActionAvailability` (Stage 19),
determines a categorical, per-direction suitability for `INCREASE`, `MAINTAIN`,
and `REDUCE`. Availability answers "can this action be taken mechanically and
operationally?"; suitability answers "do the approved performance and trend
classifications provide a clear directional signal supporting this available
action?" Suitability does **not** mean recommendation — a `SUITABLE` action is not
automatically selected, a `NEUTRAL` action is not automatically rejected, and an
`UNSUITABLE` action is not a final prohibition. `NOT_APPLICABLE` means the action
is unavailable under Stage 19 and therefore receives no suitability judgement.

Stage 20 uses a **conservative, diagonal-only rule**: only the three cells where
`PerformanceBand` and `TrendDirection` clearly agree
(`ABOVE_TARGET`+`IMPROVING`, `ON_TARGET`+`STABLE`, `BELOW_TARGET`+`DECLINING`)
produce a directional `SUITABLE`/`UNSUITABLE` result; all six conflicting or mixed
combinations resolve to `NEUTRAL` for every direction. This deliberately avoids
deciding whether performance or trend has precedence. After the base-table lookup,
availability is applied independently per direction — an unavailable direction is
always `NOT_APPLICABLE`, overriding whatever the base table would otherwise say;
`NOT_APPLICABLE` is never represented as `None`, a numeric zero, or `UNSUITABLE`.

Stage 20 does not select `RecommendationAction`, select `HOLD`, produce
`ReasonCode`, produce a numeric score, rank campaigns, or apply `Confidence`,
`PacingStatus`, or `BusinessPriority` — none of these is read anywhere in this
module. Stage 20 does not accept `CampaignTrackingAssessment`, `CampaignInput`, or
`ReviewSetup`; it consumes Stage 19's already-approved availability result
directly, so an Active-but-unassessable campaign's `MAINTAIN` still receives its
base-table result while `INCREASE`/`REDUCE` become `NOT_APPLICABLE` purely because
Stage 19 already marked them unavailable — Stage 20 never decides `MAINTAIN`
versus `HOLD`. It requires all three input objects' `campaign_id` values to match,
raising `ValueError` otherwise. No `Decimal`, arithmetic, numeric weight, or
ordering is used anywhere — only enum-identity comparison, a fixed mapping lookup,
and Boolean gating.
"""

from enum import Enum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from src.availability import CampaignActionAvailability
from src.classification import (
    CampaignPerformanceClass,
    CampaignTrendClass,
    PerformanceBand,
    TrendDirection,
)


class Suitability(str, Enum):
    """Categorical, per-action suitability signal. Not a recommendation, not
    ordered, and not comparable numerically — SUITABLE is not "greater than"
    NEUTRAL."""

    SUITABLE = "Suitable"
    NEUTRAL = "Neutral"
    UNSUITABLE = "Unsuitable"
    NOT_APPLICABLE = "Not Applicable"


# Conservative, diagonal-only base rule table: only the three cells where
# PerformanceBand and TrendDirection clearly agree produce a directional
# SUITABLE/UNSUITABLE result; every other combination is NEUTRAL for all three
# directions. Each value is a (increase, maintain, reduce) tuple of Suitability.
# Exactly all nine PerformanceBand x TrendDirection keys are present. This table
# is never mutated at runtime (MappingProxyType) and contains no numeric weight,
# RecommendationAction, or ReasonCode.
_BASE_SUITABILITY_TABLE: "MappingProxyType[tuple[PerformanceBand, TrendDirection], tuple[Suitability, Suitability, Suitability]]" = MappingProxyType(
    {
        (PerformanceBand.ABOVE_TARGET, TrendDirection.IMPROVING): (
            Suitability.SUITABLE,
            Suitability.NEUTRAL,
            Suitability.UNSUITABLE,
        ),
        (PerformanceBand.ABOVE_TARGET, TrendDirection.STABLE): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.ABOVE_TARGET, TrendDirection.DECLINING): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.ON_TARGET, TrendDirection.IMPROVING): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.ON_TARGET, TrendDirection.STABLE): (
            Suitability.NEUTRAL,
            Suitability.SUITABLE,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.ON_TARGET, TrendDirection.DECLINING): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.BELOW_TARGET, TrendDirection.IMPROVING): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.BELOW_TARGET, TrendDirection.STABLE): (
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
            Suitability.NEUTRAL,
        ),
        (PerformanceBand.BELOW_TARGET, TrendDirection.DECLINING): (
            Suitability.UNSUITABLE,
            Suitability.NEUTRAL,
            Suitability.SUITABLE,
        ),
    }
)


class CampaignActionSuitability(BaseModel):
    """Categorical, per-action suitability facts for one campaign.

    Not a recommendation, a numeric score, `RecommendationAction`, `HOLD`,
    `ReasonCode`, a ranking, or an allocation. `NOT_APPLICABLE` means the action
    is unavailable under Stage 19 and receives no suitability judgement.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    increase_suitability: Suitability
    maintain_suitability: Suitability
    reduce_suitability: Suitability


def resolve_campaign_action_suitability(
    performance: CampaignPerformanceClass,
    trend: CampaignTrendClass,
    availability: CampaignActionAvailability,
) -> CampaignActionSuitability:
    """Determine one campaign's per-action `INCREASE`/`MAINTAIN`/`REDUCE`
    suitability.

    Looks up `(performance.performance_band, trend.trend_direction)` in the
    conservative, diagonal-only base rule table, then overrides any direction
    marked unavailable by `availability` with `Suitability.NOT_APPLICABLE`.
    Requires `performance.campaign_id == trend.campaign_id ==
    availability.campaign_id`, raising `ValueError` otherwise.
    """
    if not (
        trend.campaign_id == performance.campaign_id
        and availability.campaign_id == performance.campaign_id
    ):
        raise ValueError(
            "Campaign IDs must match when resolving action suitability."
        )

    increase_base, maintain_base, reduce_base = _BASE_SUITABILITY_TABLE[
        (performance.performance_band, trend.trend_direction)
    ]

    increase_suitability = (
        increase_base if availability.increase_available else Suitability.NOT_APPLICABLE
    )
    maintain_suitability = (
        maintain_base if availability.maintain_available else Suitability.NOT_APPLICABLE
    )
    reduce_suitability = (
        reduce_base if availability.reduce_available else Suitability.NOT_APPLICABLE
    )

    return CampaignActionSuitability(
        campaign_id=performance.campaign_id,
        increase_suitability=increase_suitability,
        maintain_suitability=maintain_suitability,
        reduce_suitability=reduce_suitability,
    )
