"""Deterministic calendar and spend-pacing calculations for validated campaigns.

Implements Sprint 1 — Development Stage 4: for one already-validated `ReviewSetup` and
one already-validated `CampaignInput`, calculates calendar and linear spend-pacing facts —
elapsed/total period days, elapsed fraction, expected spend, spend variance, pacing
ratio, remaining budget, and projected end-of-period spend. These are facts only — this
module never classifies, labels, or recommends. It is independent of Stage 3
`CampaignMetrics`: it depends only on `ReviewSetup.review_date`/`period_start`/
`period_end` and `CampaignInput.campaign_id`/`current_budget`/`spend_to_date`.

Also implements Sprint 1 — Development Stage 9: for one already-calculated
`CampaignPacing` instance, classifies `pacing_ratio` alone into a neutral `PacingStatus`
using the existing frozen `PACING_LOWER_THRESHOLD`/`PACING_UPPER_THRESHOLD` constants
(a symmetric +/-10% on-pace tolerance around 1.00). This is descriptive pacing evidence
only — it is independent of `PerformanceBand`, `TrendDirection`, `Confidence`,
`TrackingStatus`/`CampaignTrackingAssessment`, protected/test status, constraints,
eligibility, score, `RecommendationAction`, `ReasonCode`, and allocation. It never reads
`spend_variance`, `expected_spend`, `elapsed_fraction`, `elapsed_days`,
`total_period_days`, `remaining_budget`, or `projected_end_of_period_spend`, and never
recalculates `pacing_ratio`. `pacing_ratio is None` (the upstream zero-denominator case)
maps to `PacingStatus.NOT_AVAILABLE` — a pacing-data state only, never
`Confidence.NOT_ASSESSABLE`, `is_assessable=False`, `TrackingStatus.UNRELIABLE`,
`RecommendationAction.HOLD`, a reason code, or an eligibility outcome. Whether
overspending or underspending is desirable, and any combined campaign judgement, remain
deferred to a later stage.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import Enum

from pydantic import BaseModel, ConfigDict

from src.constants import CURRENCY_QUANTUM, PACING_LOWER_THRESHOLD, PACING_UPPER_THRESHOLD
from src.models import CampaignInput, ReviewSetup


class CampaignPacing(BaseModel):
    """Deterministic calendar/spend pacing facts for one campaign within its review
    period.

    Facts only: no pacing status, label, classification, confidence, recommendation
    action, reason code, score, eligibility, or allocation field is carried here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    elapsed_days: int
    total_period_days: int
    elapsed_fraction: Decimal
    expected_spend: Decimal
    spend_variance: Decimal
    pacing_ratio: Decimal | None
    remaining_budget: Decimal
    projected_end_of_period_spend: Decimal | None


def calculate_campaign_pacing(
    review: ReviewSetup,
    campaign: CampaignInput,
) -> CampaignPacing:
    """Calculate calendar and linear spend-pacing facts for one campaign within one
    review period.

    Inclusive day counting: `total_period_days` counts both `period_start` and
    `period_end`. `elapsed_days` is clamped to `[0, total_period_days]`, so a
    `review_date` before the period gives 0 and a `review_date` on or after
    `period_end` gives `total_period_days`. `pacing_ratio` and
    `projected_end_of_period_spend` are `None` only when their respective denominator
    (`raw_expected_spend`, `elapsed_fraction`) is zero — never a 0/0 sentinel.
    """
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP

        total_period_days = (review.period_end - review.period_start).days + 1
        raw_elapsed_days = (review.review_date - review.period_start).days + 1
        elapsed_days = min(max(raw_elapsed_days, 0), total_period_days)

        elapsed_fraction = Decimal(elapsed_days) / Decimal(total_period_days)

        raw_expected_spend = campaign.current_budget * elapsed_fraction
        expected_spend = raw_expected_spend.quantize(
            CURRENCY_QUANTUM, rounding=ROUND_HALF_UP
        )

        spend_variance = (campaign.spend_to_date - raw_expected_spend).quantize(
            CURRENCY_QUANTUM, rounding=ROUND_HALF_UP
        )

        if raw_expected_spend == 0:
            pacing_ratio = None
        else:
            pacing_ratio = campaign.spend_to_date / raw_expected_spend

        remaining_budget = (campaign.current_budget - campaign.spend_to_date).quantize(
            CURRENCY_QUANTUM, rounding=ROUND_HALF_UP
        )

        if elapsed_fraction == 0:
            projected_end_of_period_spend = None
        else:
            raw_projected_end_of_period_spend = campaign.spend_to_date / elapsed_fraction
            projected_end_of_period_spend = raw_projected_end_of_period_spend.quantize(
                CURRENCY_QUANTUM, rounding=ROUND_HALF_UP
            )

    return CampaignPacing(
        campaign_id=campaign.campaign_id,
        elapsed_days=elapsed_days,
        total_period_days=total_period_days,
        elapsed_fraction=elapsed_fraction,
        expected_spend=expected_spend,
        spend_variance=spend_variance,
        pacing_ratio=pacing_ratio,
        remaining_budget=remaining_budget,
        projected_end_of_period_spend=projected_end_of_period_spend,
    )


class PacingStatus(str, Enum):
    """Neutral pacing-status vocabulary, descriptive only — not a judgement that
    spending is good or bad, and not a recommendation, confidence, tracking, or
    eligibility outcome."""

    UNDERSPENDING = "Under spending"
    ON_PACE = "On pace"
    OVERSPENDING = "Over spending"
    NOT_AVAILABLE = "Not available"


class CampaignPacingClass(BaseModel):
    """Neutral, descriptive pacing classification for one campaign.

    Not a performance/trend/confidence/tracking-assessability result, a combined
    campaign judgement, a constraint, an eligibility decision, a score, a
    recommendation, a reason code, or an allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    pacing_status: PacingStatus


def classify_campaign_pacing(
    pacing: CampaignPacing,
) -> CampaignPacingClass:
    """Classify one campaign's `pacing_ratio` into a neutral pacing status.

    `pacing_ratio` is the sole classification input (`campaign_id` only otherwise, for
    result identity). `None` (the upstream zero-denominator case) maps to
    `PacingStatus.NOT_AVAILABLE` without distinguishing its cause and without
    recalculating `pacing_ratio`. The on-pace interval is closed and inclusive:
    `PACING_LOWER_THRESHOLD <= pacing_ratio <= PACING_UPPER_THRESHOLD` is `ON_PACE`;
    below is `UNDERSPENDING`; above is `OVERSPENDING`. Direct `Decimal` comparison only
    — no arithmetic, quantisation, or float conversion, so no local `Decimal` context is
    required.
    """
    if pacing.pacing_ratio is None:
        pacing_status = PacingStatus.NOT_AVAILABLE
    elif pacing.pacing_ratio < PACING_LOWER_THRESHOLD:
        pacing_status = PacingStatus.UNDERSPENDING
    elif pacing.pacing_ratio <= PACING_UPPER_THRESHOLD:
        pacing_status = PacingStatus.ON_PACE
    else:
        pacing_status = PacingStatus.OVERSPENDING

    return CampaignPacingClass(
        campaign_id=pacing.campaign_id,
        pacing_status=pacing_status,
    )
