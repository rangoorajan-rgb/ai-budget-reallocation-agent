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

Also implements Sprint 1 — Development Stage 12: for one already-validated
`CampaignInput` and one already-resolved `CampaignApplicableChangePercentage` (Stage
11's result), calculates a raw, informational percentage-based monetary movement cap —
`current_budget * applicable_max_change_percentage`, quantised once to `CURRENCY_QUANTUM`
using `ROUND_HALF_UP`. This is **not** permission to increase or decrease a campaign's
budget, an effective/final permissible movement, a static-bound intersection, a
protection or test-budget-floor determination, an eligibility result, a score, a
recommendation, a reason code, or an allocation. Stage 12 consumes Stage 11's already-
resolved result directly — it never accepts `ReviewSetup`, never reads
`campaign.campaign_max_change_percentage` or `review.default_max_change_percentage`,
never imports `DEFAULT_MAX_CHANGE_PERCENTAGE`, and never re-resolves override/default
precedence. It requires `campaign.campaign_id == applicable_percentage.campaign_id`,
raising `ValueError` otherwise. The multiplication and quantisation both run inside a
local `decimal` context whose precision is derived from the operands' own digit counts
(`max(28, digits(current_budget) + digits(applicable_max_change_percentage) + 4)`) —
`CampaignInput.current_budget` has no upper bound, and `applicable_max_change_percentage`
has no digit-count restriction, so a fixed `prec=28` context can round the intermediate
multiplication before the explicit final quantisation ever runs, silently producing a
one-penny error via double rounding (empirically confirmed and regression-tested). The
operand-derived precision guarantees the multiplication is computed exactly, leaving the
explicit `.quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)` call as the sole rounding
operation. Stage 12 is independent of Stage 10: it never reads `minimum_budget`,
`maximum_budget`, `room_to_static_maximum`, or `room_to_static_minimum`, and never calls
`calculate_campaign_static_budget_room`. It also ignores `is_protected`,
`is_test_campaign`, and `test_budget_floor` — static-bound intersection, protection, and
test-floor effects on the raw cap all remain pending a later effective-constraint stage.

Also implements Sprint 1 — Development Stage 13: for one already-validated
`CampaignInput`, calculates a raw, informational test-floor distance —
`current_budget - test_budget_floor` — for test campaigns only
(`is_test_campaign=True`); `room_to_test_floor` is `None` for non-test campaigns, an
explicit statement that the fact does not apply, never a fallback or an error. This is
**not** the effective floor, not an alternative or additional minimum, not permissible
decrease, not an effective directional constraint, and is never combined with
`minimum_budget`, Stage 10's static room, or Stage 12's raw percentage movement cap.
Stage 13 reads only `campaign_id`, `is_test_campaign`, `current_budget`, and
`test_budget_floor` — never `minimum_budget`, `maximum_budget`, `is_protected`,
`campaign_max_change_percentage`, `platform`, `kpi_type`, or any Stage 3–9 result, and
never imports or calls anything from Stages 10–12 or `ReviewSetup`. The subtraction runs
inside a fixed local `decimal` context (`prec=28`, `ROUND_HALF_UP`, matching Stage 10's
established policy) — unlike Stage 12's multiplication, subtracting two already-
quantised `Currency` values never needs more significant digits than the larger
operand already has, so no operand-derived precision is required here.

Also implements Sprint 1 — Development Stage 14: for one already-validated
`CampaignInput`, states one neutral, deterministic protection constraint —
`decrease_blocked = campaign.is_protected`. This is a **decrease-specific fact only**,
directly derived from `is_protected`'s frozen meaning ("must never be reduced",
`docs/DATA_DICTIONARY.md`) — it is not an eligibility decision, a recommendation, a
monetary movement amount, permissible decrease, an effective directional limit, or an
increase-side constraint, and it is never combined with Stages 10–13.
`decrease_blocked=False` means only that protection itself does not prohibit a
decrease — it does not mean a decrease is permissible.
`decrease_blocked=True` means only that protection prohibits a decrease — it does not
determine eligibility, recommendation action, allocation, or any other judgement.
Stage 14 reads only `campaign_id` and `is_protected` — never `current_budget`,
`minimum_budget`, `maximum_budget`, `is_test_campaign`, `test_budget_floor`,
`campaign_max_change_percentage`, `platform`, `kpi_type`, or any Stage 3–9 result, and
never imports or calls anything from Stages 10–13 or `ReviewSetup`. Stage 14 performs
no `Decimal` calculation — it is a plain boolean selection, so no `Decimal` import,
local context, quantisation, or rounding is used. Increase-side protection behaviour
remains entirely unaddressed, since the one frozen sentence about `is_protected` is
decrease-specific only.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from pydantic import BaseModel, ConfigDict

from src.constants import CURRENCY_QUANTUM
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


class CampaignRawPercentageMovementCap(BaseModel):
    """A raw, informational percentage-based monetary movement cap for one campaign.

    Not permission to increase or decrease a campaign's budget, an effective/final
    permissible movement, a static-bound intersection, a protection or
    test-budget-floor determination, an eligibility result, a score, a recommendation,
    a reason code, or an allocation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    raw_percentage_movement_cap: Decimal


def calculate_campaign_raw_percentage_movement_cap(
    campaign: CampaignInput,
    applicable_percentage: CampaignApplicableChangePercentage,
) -> CampaignRawPercentageMovementCap:
    """Calculate one campaign's raw percentage-based monetary movement cap:
    `current_budget * applicable_max_change_percentage`, quantised once to
    `CURRENCY_QUANTUM` using `ROUND_HALF_UP`.

    Requires `campaign.campaign_id == applicable_percentage.campaign_id`, raising
    `ValueError` otherwise — the two input objects independently identify a campaign,
    and silently applying one campaign's percentage to another would be unsafe.

    `current_budget` has no upper bound and `applicable_max_change_percentage` has no
    digit-count restriction, so a fixed-precision `Decimal` context can round the
    intermediate multiplication before the final quantisation ever runs, silently
    producing an incorrect result via double rounding. The local context's precision is
    therefore derived from the operands' own digit counts
    (`max(28, digits(current_budget) + digits(applicable_max_change_percentage) + 4)`),
    guaranteeing the multiplication is computed exactly and leaving the explicit
    `quantize` call as the sole rounding operation. The global `Decimal` context is
    never mutated and cannot affect the result.
    """
    if campaign.campaign_id != applicable_percentage.campaign_id:
        raise ValueError("campaign_id mismatch between campaign and applicable percentage")

    current_budget = campaign.current_budget
    applicable_max_change_percentage = applicable_percentage.applicable_max_change_percentage

    operand_digits = len(current_budget.as_tuple().digits) + len(
        applicable_max_change_percentage.as_tuple().digits
    )
    safe_precision = max(28, operand_digits + 4)

    with localcontext() as ctx:
        ctx.prec = safe_precision
        ctx.rounding = ROUND_HALF_UP
        product = current_budget * applicable_max_change_percentage
        raw_percentage_movement_cap = product.quantize(
            CURRENCY_QUANTUM, rounding=ROUND_HALF_UP
        )

    return CampaignRawPercentageMovementCap(
        campaign_id=campaign.campaign_id,
        raw_percentage_movement_cap=raw_percentage_movement_cap,
    )


class CampaignTestFloorRoom(BaseModel):
    """A raw, informational test-floor distance for one campaign.

    Not the effective floor, not an alternative or additional minimum, not
    permissible decrease, not an effective directional constraint, and never
    combined with `minimum_budget`, Stage 10's static room, or Stage 12's raw
    percentage movement cap.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    room_to_test_floor: Decimal | None


def calculate_campaign_test_floor_room(
    campaign: CampaignInput,
) -> CampaignTestFloorRoom:
    """Calculate one campaign's raw distance from `current_budget` to
    `test_budget_floor`, for test campaigns only.

    `room_to_test_floor = current_budget - test_budget_floor` when
    `campaign.is_test_campaign` is `True` — guaranteed non-negative by
    `CampaignInput`'s already-validated `test_budget_floor <= current_budget`
    invariant, and `Decimal("0.00")` is a valid, unaltered outcome when
    `current_budget == test_budget_floor`. For a non-test campaign,
    `room_to_test_floor` is `None` — an explicit statement that the fact does not
    apply, never a fallback value or an error.
    """
    if not campaign.is_test_campaign:
        return CampaignTestFloorRoom(
            campaign_id=campaign.campaign_id,
            room_to_test_floor=None,
        )

    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        room_to_test_floor = campaign.current_budget - campaign.test_budget_floor

    return CampaignTestFloorRoom(
        campaign_id=campaign.campaign_id,
        room_to_test_floor=room_to_test_floor,
    )


class CampaignProtectionConstraint(BaseModel):
    """A neutral, decrease-specific protection constraint for one campaign.

    Not an eligibility decision, a recommendation, a monetary movement amount,
    permissible decrease, an effective directional limit, an increase-side
    constraint, or a combination with Stages 10-13.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    decrease_blocked: bool


def resolve_campaign_protection_constraint(
    campaign: CampaignInput,
) -> CampaignProtectionConstraint:
    """State one campaign's decrease-specific protection constraint:
    `decrease_blocked = campaign.is_protected`.

    `decrease_blocked=False` means only that protection itself does not prohibit a
    decrease — it does not mean a decrease is permissible. `decrease_blocked=True`
    means only that protection prohibits a decrease — it does not determine
    eligibility, recommendation action, allocation, or any other judgement.
    """
    return CampaignProtectionConstraint(
        campaign_id=campaign.campaign_id,
        decrease_blocked=campaign.is_protected,
    )
