"""Deterministic performance-ratio metric calculations for validated campaigns.

Implements Sprint 1 — Development Stage 3: for each already-validated `CampaignInput`,
calculates direction-normalised performance ratios (7-day, 28-day), a weighted blend of
the two, and a relative trend delta between them. These are facts only — this module
never classifies, scores, recommends, or assigns confidence. Comparing these facts against
`INCREASE_THRESHOLD`, `MAINTAIN_THRESHOLD`, and `TREND_THRESHOLD`, and conversion-volume
confidence assessment (`MINIMUM_CONVERSIONS`, `HIGH_CONFIDENCE_CONVERSIONS`), are
implemented in a later stage.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from pydantic import BaseModel, ConfigDict

from src.constants import KPIType, SEVEN_DAY_WEIGHT, TWENTY_EIGHT_DAY_WEIGHT
from src.models import CampaignInput


class CampaignMetrics(BaseModel):
    """Deterministic performance-ratio facts for one campaign.

    Facts only: no KPI type, raw KPI values, conversions, confidence, trend label,
    recommendation action, reason code, score, or budget field is carried here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    performance_ratio_7d: Decimal
    performance_ratio_28d: Decimal
    weighted_performance_ratio: Decimal
    trend_delta: Decimal


def calculate_campaign_metrics(campaign: CampaignInput) -> CampaignMetrics:
    """Calculate direction-normalised performance ratios, their weighted blend, and the
    relative trend delta between them, for one already-validated campaign.

    For KPIType.ROAS, a higher actual value is better, so ratio = actual / target. For
    KPIType.CPA, a lower actual value is better, so ratio = target / actual. Either way,
    a ratio > 1 means better than target and a ratio < 1 means worse than target —
    `CampaignInput` already guarantees kpi_target, kpi_actual_7d, and kpi_actual_28d are
    all strictly greater than zero, so no denominator here can be zero.
    """
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP

        if campaign.kpi_type is KPIType.ROAS:
            ratio_7d = campaign.kpi_actual_7d / campaign.kpi_target
            ratio_28d = campaign.kpi_actual_28d / campaign.kpi_target
        else:
            ratio_7d = campaign.kpi_target / campaign.kpi_actual_7d
            ratio_28d = campaign.kpi_target / campaign.kpi_actual_28d

        weighted_ratio = (
            ratio_7d * SEVEN_DAY_WEIGHT + ratio_28d * TWENTY_EIGHT_DAY_WEIGHT
        )
        trend_delta = (ratio_7d - ratio_28d) / ratio_28d

    return CampaignMetrics(
        campaign_id=campaign.campaign_id,
        performance_ratio_7d=ratio_7d,
        performance_ratio_28d=ratio_28d,
        weighted_performance_ratio=weighted_ratio,
        trend_delta=trend_delta,
    )
