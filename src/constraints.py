"""Reallocation constraints (e.g. min/max shift caps, campaign floors).

Implements Sprint 1 — Development Stage 10: for one already-validated `CampaignInput`,
calculates the static distance from `current_budget` to the campaign's validated static
`maximum_budget` and `minimum_budget`. These are neutral static-bound facts only — they
are the campaign's already-validated budget-assignment bounds, not a final permissible
budget movement. `campaign_max_change_percentage`, `ReviewSetup.default_max_change_percentage`,
`DEFAULT_MAX_CHANGE_PERCENTAGE`, `is_protected`, `is_test_campaign`, and `test_budget_floor`
are all deliberately ignored: the percentage-limit mechanism, protection rules, and
test-budget-floor enforcement all remain pending a later effective-constraint stage.
Reporting a static distance to `minimum_budget` never authorises a reduction below a
campaign's `test_budget_floor`, and reporting a static distance to `maximum_budget` never
authorises an increase — Stage 10 calculates facts only, independent of Stages 3–9.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from pydantic import BaseModel, ConfigDict

from src.models import CampaignInput


class CampaignStaticBudgetRoom(BaseModel):
    """Neutral static budget-bound distances for one campaign.

    Not an effective/final permissible budget movement, a percentage-based limit, a
    protection or test-budget-floor determination, an eligibility result, a blocking
    flag, a recommendation, a reason code, a score, or an allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    room_to_static_maximum: Decimal
    room_to_static_minimum: Decimal


def calculate_campaign_static_budget_room(
    campaign: CampaignInput,
) -> CampaignStaticBudgetRoom:
    """Calculate one campaign's static distance to its validated `maximum_budget` and
    `minimum_budget`.

    `room_to_static_maximum = maximum_budget - current_budget`;
    `room_to_static_minimum = current_budget - minimum_budget`. Both are guaranteed
    non-negative by `CampaignInput`'s already-validated `minimum_budget <= current_budget
    <= maximum_budget` invariant, and `Decimal("0.00")` is a valid, unaltered outcome
    exactly at either bound — never replaced with `None` or a categorical status.
    `campaign_max_change_percentage`, `is_protected`, `is_test_campaign`, and
    `test_budget_floor` are never read.
    """
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        room_to_static_maximum = campaign.maximum_budget - campaign.current_budget
        room_to_static_minimum = campaign.current_budget - campaign.minimum_budget

    return CampaignStaticBudgetRoom(
        campaign_id=campaign.campaign_id,
        room_to_static_maximum=room_to_static_maximum,
        room_to_static_minimum=room_to_static_minimum,
    )
