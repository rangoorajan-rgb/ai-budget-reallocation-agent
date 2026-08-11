"""Deterministic, neutral performance, trend, and conversion-volume-confidence
classification for calculated campaign metrics and validated campaign input.

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

Also implements Sprint 1 — Development Stage 7: for one already-validated `CampaignInput`
instance, classifies `conversions_28d` into the existing `Confidence` enum's `HIGH`/
`MEDIUM`/`LOW` members, using the existing frozen `MINIMUM_CONVERSIONS`/
`HIGH_CONFIDENCE_CONVERSIONS` constants. This is descriptive conversion-volume evidence
only — it is independent of `PerformanceBand`/`TrendDirection`, does not read
`conversions_7d`, `tracking_status`, or any other field, and never assigns
`Confidence.NOT_ASSESSABLE` (that trigger remains deferred to a later stage).

Also implements Sprint 1 — Development Stage 8: for one already-validated `CampaignInput`
instance, determines a narrow tracking-based assessability fact from `tracking_status`
alone. `TrackingStatus.UNRELIABLE` is the sole condition producing `is_assessable=False`;
`HEALTHY` and `WARNING` both produce `is_assessable=True` — `WARNING` represents a
concern requiring later caution, not a declaration that the evidence is unusable, and the
original `tracking_status` is preserved in the result so `WARNING` is never collapsed
into `HEALTHY`. This is independent of `CampaignConfidenceClass`; it never assigns or
reads `Confidence.NOT_ASSESSABLE`, and does not replace or override Stage 7.

Tracking-effects on confidence/performance/trend, `Confidence.NOT_ASSESSABLE` assignment,
combined campaign judgement, pacing interpretation, and any final
`RecommendationAction`/`ReasonCode` assignment are all explicitly deferred to later
stages. Each classification here depends only on its own narrow input — never
`CampaignPacing`, `ReviewSetup`, or any KPI-type-specific/platform-specific branching
(Stage 3 has already direction-normalised CPA and ROAS).
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict

from src.constants import (
    Confidence,
    HIGH_CONFIDENCE_CONVERSIONS,
    INCREASE_THRESHOLD,
    MAINTAIN_THRESHOLD,
    MINIMUM_CONVERSIONS,
    TrackingStatus,
    TREND_THRESHOLD,
)
from src.metrics import CampaignMetrics
from src.models import CampaignInput


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


class CampaignConfidenceClass(BaseModel):
    """Neutral, descriptive conversion-volume confidence classification for one
    campaign.

    Independent of `PerformanceBand`/`CampaignPerformanceClass` and
    `TrendDirection`/`CampaignTrendClass`. Not a tracking interpretation, assessability
    decision, pacing interpretation, constraint, eligibility decision, score,
    recommendation, reason code, or allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    confidence: Confidence


def classify_campaign_confidence(
    campaign: CampaignInput,
) -> CampaignConfidenceClass:
    """Classify one campaign's `conversions_28d` into a neutral conversion-volume
    confidence band.

    Uses `conversions_28d` only — the fuller, more stable evidence window, which also
    avoids double-counting the nested 7-day period. Reaching either threshold enters the
    higher confidence band: `>= HIGH_CONFIDENCE_CONVERSIONS` is `HIGH`,
    `>= MINIMUM_CONVERSIONS` is `MEDIUM`, otherwise `LOW`. Direct integer comparison
    only — no arithmetic, weighting, quantisation, or Decimal/float conversion.
    `Confidence.NOT_ASSESSABLE` is never assigned here; its trigger remains deferred.
    """
    conversions_28d = campaign.conversions_28d

    if conversions_28d >= HIGH_CONFIDENCE_CONVERSIONS:
        confidence = Confidence.HIGH
    elif conversions_28d >= MINIMUM_CONVERSIONS:
        confidence = Confidence.MEDIUM
    else:
        confidence = Confidence.LOW

    return CampaignConfidenceClass(
        campaign_id=campaign.campaign_id,
        confidence=confidence,
    )


class CampaignTrackingAssessment(BaseModel):
    """Narrow, deterministic tracking-based assessability fact for one campaign.

    Not conversion-volume confidence, a `Confidence.NOT_ASSESSABLE` assignment, a
    replacement for `CampaignConfidenceClass`, a performance/trend classification, a
    pacing interpretation, a combined campaign judgement, a constraint, eligibility, a
    score, a recommendation, a reason code, or an allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    tracking_status: TrackingStatus
    is_assessable: bool


def assess_campaign_tracking(
    campaign: CampaignInput,
) -> CampaignTrackingAssessment:
    """Determine one campaign's tracking-based assessability from `tracking_status`
    alone.

    `TrackingStatus.UNRELIABLE` is the sole condition producing `is_assessable=False`.
    `HEALTHY` and `WARNING` both produce `is_assessable=True` — `WARNING` represents a
    concern requiring later caution, not a declaration that the evidence is unusable.
    The original `tracking_status` is preserved in the result so `WARNING` is never
    collapsed into `HEALTHY`, keeping it visible for later `ReasonCode`/recommendation
    logic. No arithmetic, Decimal/float conversion, weighting, or quantisation is
    performed.
    """
    is_assessable = campaign.tracking_status is not TrackingStatus.UNRELIABLE

    return CampaignTrackingAssessment(
        campaign_id=campaign.campaign_id,
        tracking_status=campaign.tracking_status,
        is_assessable=is_assessable,
    )
