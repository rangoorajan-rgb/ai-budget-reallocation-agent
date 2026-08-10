"""Deterministic, neutral performance and trend classification for calculated campaign
metrics.

Implements Sprint 1 — Development Stage 5: for one already-calculated `CampaignMetrics`
instance, classifies `weighted_performance_ratio` into one neutral `PerformanceBand`
using the existing frozen `INCREASE_THRESHOLD`/`MAINTAIN_THRESHOLD` constants. This is a
descriptive performance classification only — it is not a recommendation, decision,
constraint, score, eligibility result, or budget action.

Also implements Sprint 1 — Development Stage 6: for the same kind of already-calculated
`CampaignMetrics` instance, classifies `trend_delta` into one neutral `TrendDirection`
using the existing frozen `TREND_THRESHOLD` constant. This is descriptive evidence only
— it is independent of `PerformanceBand`/`CampaignPerformanceClass` and is not a
confidence assessment, tracking assessment, pacing interpretation, constraint,
eligibility decision, score, recommendation, reason code, or proposed allocation.

Conversion-volume confidence, tracking-status interpretation, pacing interpretation, and
any final `RecommendationAction`/`ReasonCode` assignment or combined campaign judgement
are all explicitly deferred to later stages. Depends only on `CampaignMetrics` —
never `CampaignInput`, `CampaignPacing`, `ReviewSetup`, or any KPI-type-specific/
platform-specific branching (Stage 3 has already direction-normalised CPA and ROAS).
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict

from src.constants import INCREASE_THRESHOLD, MAINTAIN_THRESHOLD, TREND_THRESHOLD
from src.metrics import CampaignMetrics


class PerformanceBand(str, Enum):
    """Neutral performance-band vocabulary, intentionally distinct from
    `RecommendationAction`."""

    ABOVE_TARGET = "ABOVE_TARGET"
    ON_TARGET = "ON_TARGET"
    BELOW_TARGET = "BELOW_TARGET"


class CampaignPerformanceClass(BaseModel):
    """Neutral, descriptive performance classification for one campaign.

    Not a recommendation, decision, constraint, score, eligibility result, or budget
    action.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    performance_band: PerformanceBand


def classify_campaign_performance(
    metrics: CampaignMetrics,
) -> CampaignPerformanceClass:
    """Classify one campaign's `weighted_performance_ratio` into a neutral performance
    band.

    The threshold belongs to the higher band because reaching the declared threshold
    qualifies for that band: `>= INCREASE_THRESHOLD` is `ABOVE_TARGET`,
    `>= MAINTAIN_THRESHOLD` (and below `INCREASE_THRESHOLD`) is `ON_TARGET`, otherwise
    `BELOW_TARGET`. Direct `Decimal` comparison only — no arithmetic, quantisation, or
    float conversion, so no local `Decimal` context is required.
    """
    ratio: Decimal = metrics.weighted_performance_ratio

    if ratio >= INCREASE_THRESHOLD:
        performance_band = PerformanceBand.ABOVE_TARGET
    elif ratio >= MAINTAIN_THRESHOLD:
        performance_band = PerformanceBand.ON_TARGET
    else:
        performance_band = PerformanceBand.BELOW_TARGET

    return CampaignPerformanceClass(
        campaign_id=metrics.campaign_id,
        performance_band=performance_band,
    )


class TrendDirection(str, Enum):
    """Neutral trend-direction vocabulary. Descriptive evidence only — not a
    recommendation or reason code."""

    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"


class CampaignTrendClass(BaseModel):
    """Neutral, descriptive trend classification for one campaign.

    Independent of `PerformanceBand`/`CampaignPerformanceClass`. Not a confidence
    assessment, tracking assessment, pacing interpretation, constraint, eligibility
    decision, score, recommendation, reason code, or proposed allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    trend_direction: TrendDirection


def classify_campaign_trend(
    metrics: CampaignMetrics,
) -> CampaignTrendClass:
    """Classify one campaign's `trend_delta` into a neutral trend direction.

    Reaching the threshold magnitude in either direction enters that directional band,
    consistent with the threshold-entry policy approved for `PerformanceBand`:
    `>= TREND_THRESHOLD` is `IMPROVING`, `<= -TREND_THRESHOLD` is `DECLINING`, otherwise
    `STABLE`. The negative boundary is `TREND_THRESHOLD.copy_negate()` — an exact
    sign-inversion with no rounding and no dependence on the active `Decimal` context.
    Direct `Decimal` comparison only — no arithmetic or quantisation is performed on
    `trend_delta`.
    """
    negative_trend_threshold = TREND_THRESHOLD.copy_negate()

    if metrics.trend_delta >= TREND_THRESHOLD:
        trend_direction = TrendDirection.IMPROVING
    elif metrics.trend_delta <= negative_trend_threshold:
        trend_direction = TrendDirection.DECLINING
    else:
        trend_direction = TrendDirection.STABLE

    return CampaignTrendClass(
        campaign_id=metrics.campaign_id,
        trend_direction=trend_direction,
    )
