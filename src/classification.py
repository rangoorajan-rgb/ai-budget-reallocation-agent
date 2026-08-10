"""Deterministic, neutral performance classification for calculated campaign metrics.

Implements Sprint 1 — Development Stage 5: for one already-calculated `CampaignMetrics`
instance, classifies `weighted_performance_ratio` into one neutral `PerformanceBand`
using the existing frozen `INCREASE_THRESHOLD`/`MAINTAIN_THRESHOLD` constants. This is a
descriptive performance classification only — it is not a recommendation, decision,
constraint, score, eligibility result, or budget action. Trend classification,
conversion-volume confidence, tracking-status interpretation, and any final
`RecommendationAction`/`ReasonCode` assignment are all explicitly deferred to later
stages. Depends only on `CampaignMetrics.campaign_id`/`weighted_performance_ratio` — never
`CampaignInput`, `CampaignPacing`, `ReviewSetup`, or any KPI-type-specific branching
(Stage 3 has already direction-normalised CPA and ROAS).
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict

from src.constants import INCREASE_THRESHOLD, MAINTAIN_THRESHOLD
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
