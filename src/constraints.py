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

Also implements Sprint 1 — Development Stage 11: for one already-validated `ReviewSetup`
and one already-validated `CampaignInput`, resolves which already-validated
maximum-change percentage applies to that campaign — `campaign.campaign_max_change_percentage`
when it is not `None`, otherwise `review.default_max_change_percentage`. This is a
neutral `Decimal` configuration fact only — no monetary movement cap, no multiplication
by `current_budget` or any other amount, no static-bound intersection, and no
increase/decrease symmetry rule is calculated. `DEFAULT_MAX_CHANGE_PERCENTAGE` is never
imported or read, so a caller-supplied `ReviewSetup` value is always respected instead of
a hard-coded default. Stage 11 is independent of Stage 10: it never reads
`current_budget`, `minimum_budget`, `maximum_budget`, `room_to_static_maximum`, or
`room_to_static_minimum`, and never calls `calculate_campaign_static_budget_room`. It
also ignores `is_protected`, `is_test_campaign`, and `test_budget_floor` — protection and
test-campaign effective-floor rules remain pending a later stage.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from pydantic import BaseModel, ConfigDict

from src.models import CampaignInput, ReviewSetup


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


class CampaignApplicableChangePercentage(BaseModel):
    """The applicable maximum-change percentage resolved for one campaign.

    Not a monetary movement cap, a static-bound intersection, a protection or
    test-budget-floor determination, an eligibility result, a score, a recommendation,
    a reason code, or an allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    applicable_max_change_percentage: Decimal


def resolve_campaign_applicable_change_percentage(
    review: ReviewSetup,
    campaign: CampaignInput,
) -> CampaignApplicableChangePercentage:
    """Resolve which already-validated maximum-change percentage applies to one
    campaign.

    `campaign.campaign_max_change_percentage` wins when it is not `None`; otherwise
    `review.default_max_change_percentage` applies. This is a plain conditional
    selection — no arithmetic, quantisation, or `Decimal` context is required, and the
    selected value is preserved exactly.
    """
    applicable_max_change_percentage = (
        campaign.campaign_max_change_percentage
        if campaign.campaign_max_change_percentage is not None
        else review.default_max_change_percentage
    )

    return CampaignApplicableChangePercentage(
        campaign_id=campaign.campaign_id,
        applicable_max_change_percentage=applicable_max_change_percentage,
    )
