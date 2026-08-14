"""Deterministic campaign action availability.

Implements Sprint 1 — Development Stage 19: for one already-validated `CampaignInput`
and three already-approved result objects (`CampaignTrackingAssessment` from Stage 8,
`CampaignRawIncreaseLimit` from Stage 16, `CampaignEffectiveDecreaseLimit` from Stage
18), determines whether `INCREASE`, `MAINTAIN`, and `REDUCE` are each mechanically and
operationally available for that campaign. Availability means an action is not
prevented by campaign status, tracking-based assessability, or the relevant approved
monetary capacity — it does **not** mean the action is advisable, suitable, or
recommended. Positive capacity establishes only that a direction is mechanically
possible; it is never a recommendation.

Stage 19 does **not** decide which available action is suitable, which action should
be recommended, `HOLD`, scoring, priority, ranking, `ReasonCode`, or allocation. `HOLD`
is excluded entirely — it is a later review/deferral or recommendation outcome whose
exact trigger remains undecided.

`increase_available` requires active status, tracking assessability, and
`raw_increase_limit > Decimal("0.00")`. `reduce_available` requires active status,
tracking assessability, and `effective_decrease_limit > Decimal("0.00")`.
`maintain_available` requires only active status — for an Active campaign it remains
mechanically available regardless of tracking assessability or directional monetary
capacity; for a Paused campaign it is not available through the active budget-review
process. A Paused campaign receives `increase_available=False`,
`maintain_available=False`, `reduce_available=False` — never omitted, never an error,
never `HOLD`, never a reason code.

Stage 19 consumes Stage 8's, Stage 16's, and Stage 18's already-approved result objects
directly — it never calls `assess_campaign_tracking`,
`resolve_campaign_raw_increase_limit`, `resolve_campaign_effective_decrease_limit`, or
any other Stage 1–18 production function, and never recalculates tracking
assessability, static budget rooms, percentage caps, test-floor constraints,
protection, raw increase, raw decrease, or effective decrease. It reads only
`campaign.campaign_id`/`campaign.status`, `tracking.campaign_id`/`tracking.is_assessable`,
`raw_increase.campaign_id`/`raw_increase.raw_increase_limit`, and
`effective_decrease.campaign_id`/`effective_decrease.effective_decrease_limit` — never
`tracking_status`, `is_protected`, `decrease_blocked`, `is_test_campaign`,
`test_budget_floor`, `minimum_budget`, `maximum_budget`, or any performance, trend,
confidence, pacing, or business-priority field. It requires all four `campaign_id`
values to match, raising `ValueError` otherwise. No monetary arithmetic is performed —
only enum-identity comparison, Boolean conjunction, and `Decimal` comparison against
`Decimal("0.00")` — so no local `decimal` context, quantisation, or rounding is used.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.constraints import CampaignEffectiveDecreaseLimit, CampaignRawIncreaseLimit
from src.classification import CampaignTrackingAssessment
from src.constants import CampaignStatus
from src.models import CampaignInput


class CampaignActionAvailability(BaseModel):
    """Deterministic action-availability facts for one campaign.

    Availability means an action is not prevented by campaign status, tracking-based
    assessability, or the relevant approved monetary capacity — it does not mean the
    action is advisable. Not suitability, a recommendation, `HOLD`, a score, a
    priority, a ranking, a reason code, or an allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    increase_available: bool
    maintain_available: bool
    reduce_available: bool


def resolve_campaign_action_availability(
    campaign: CampaignInput,
    tracking: CampaignTrackingAssessment,
    raw_increase: CampaignRawIncreaseLimit,
    effective_decrease: CampaignEffectiveDecreaseLimit,
) -> CampaignActionAvailability:
    """Determine one campaign's `INCREASE`/`MAINTAIN`/`REDUCE` action availability.

    `increase_available` and `reduce_available` each require active status, tracking
    assessability, and positive directional monetary capacity.
    `maintain_available` requires only active status. Requires
    `campaign.campaign_id == tracking.campaign_id == raw_increase.campaign_id ==
    effective_decrease.campaign_id`, raising `ValueError` otherwise.
    """
    if not (
        tracking.campaign_id == campaign.campaign_id
        and raw_increase.campaign_id == campaign.campaign_id
        and effective_decrease.campaign_id == campaign.campaign_id
    ):
        raise ValueError(
            "Campaign IDs must match when resolving action availability."
        )

    is_active = campaign.status is CampaignStatus.ACTIVE

    increase_available = (
        is_active
        and tracking.is_assessable
        and raw_increase.raw_increase_limit > Decimal("0.00")
    )

    maintain_available = is_active

    reduce_available = (
        is_active
        and tracking.is_assessable
        and effective_decrease.effective_decrease_limit > Decimal("0.00")
    )

    return CampaignActionAvailability(
        campaign_id=campaign.campaign_id,
        increase_available=increase_available,
        maintain_available=maintain_available,
        reduce_available=reduce_available,
    )
