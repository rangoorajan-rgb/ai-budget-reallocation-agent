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

Also implements Sprint 1 — Development Stage 15: for one already-calculated
`CampaignStaticBudgetRoom` (Stage 10's result) and one already-calculated
`CampaignTestFloorRoom` (Stage 13's result), combines the two into one neutral,
test-aware static decrease-room constraint — treating `test_budget_floor` as an
*additional* retained-spend floor for test campaigns, so the higher of
`minimum_budget`/`test_budget_floor` controls, equivalently expressed as the smaller
of the two already-calculated rooms:
`test_aware_static_decrease_room = room_to_static_minimum` when
`room_to_test_floor is None` (non-test campaigns), otherwise
`min(room_to_static_minimum, room_to_test_floor)`. This is a **raw, test-aware static
constraint only** — not permissible decrease, not an effective decrease limit, and it
does not mean the campaign should be reduced. It does not account for Stage 12's
percentage cap or Stage 14's protection constraint. Stage 15 consumes Stage 10's and
Stage 13's already-approved result objects directly — it never accepts or reads
`CampaignInput`, never calls `calculate_campaign_static_budget_room` or
`calculate_campaign_test_floor_room`, and never reads or imports
`CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`,
`CampaignProtectionConstraint`, or `ReviewSetup`. It requires
`static_room.campaign_id == test_floor_room.campaign_id`, raising `ValueError`
otherwise. No arithmetic is performed — the selected `Decimal` operand is returned
unchanged, so no local `decimal` context, quantisation, or rounding is used.

Also implements Sprint 1 — Development Stage 16: for one already-calculated
`CampaignStaticBudgetRoom` (Stage 10's result) and one already-calculated
`CampaignRawPercentageMovementCap` (Stage 12's result), combines the two into one
neutral raw increase limit — both upward constraints apply simultaneously
(`room_to_static_maximum` prevents exceeding `maximum_budget`;
`raw_percentage_movement_cap` limits the size of a change under the applicable
percentage rule), so the smaller value is the binding limit:
`raw_increase_limit = min(room_to_static_maximum, raw_percentage_movement_cap)`.
This is a **raw, increase-specific constraint only** — not permission to increase a
budget, not an effective increase, not eligibility, not a recommendation, and not a
final movement amount. Stage 16 consumes Stage 10's and Stage 12's already-approved
result objects directly — it never accepts or reads `CampaignInput` or `ReviewSetup`,
never calls `calculate_campaign_static_budget_room` or
`calculate_campaign_raw_percentage_movement_cap`, and never reads or imports
`CampaignApplicableChangePercentage`, `CampaignTestFloorRoom`,
`CampaignProtectionConstraint`, or `CampaignTestAwareStaticDecreaseRoom`. Protected
status has no approved increase-side effect here, and test-floor rules are
decrease-specific — neither is read. It requires `static_room.campaign_id ==
raw_cap.campaign_id`, raising `ValueError` otherwise. No arithmetic is performed —
the selected `Decimal` operand is returned unchanged, so no local `decimal` context,
quantisation, or rounding is used.

Also implements Sprint 1 — Development Stage 17: for one already-calculated
`CampaignTestAwareStaticDecreaseRoom` (Stage 15's result) and one already-calculated
`CampaignRawPercentageMovementCap` (Stage 12's result), combines the two into one
neutral raw decrease limit — both decrease-side constraints apply simultaneously
(`test_aware_static_decrease_room` preserves the approved minimum-budget/test-floor
constraint; `raw_percentage_movement_cap` limits the size of a change under the
applicable percentage rule), so the smaller value is the binding limit:
`raw_decrease_limit = min(test_aware_static_decrease_room,
raw_percentage_movement_cap)`. This is a **raw, decrease-specific constraint only**
— not permission to decrease a budget, not an effective decrease, not eligibility,
not a recommendation, and not a final movement amount. A protected campaign still
receives its neutral Stage 17 raw result — Stage 14's protection constraint is not
applied here and remains pending a later effective-constraint stage. Stage 17
consumes Stage 15's and Stage 12's already-approved result objects directly — it
never accepts or reads `CampaignInput` or `ReviewSetup`, never calls
`resolve_campaign_test_aware_static_decrease_room` or
`calculate_campaign_raw_percentage_movement_cap`, and never reads or imports
`CampaignStaticBudgetRoom`, `CampaignApplicableChangePercentage`,
`CampaignTestFloorRoom`, `CampaignProtectionConstraint`, or
`CampaignRawIncreaseLimit`. It requires `decrease_room.campaign_id ==
raw_cap.campaign_id`, raising `ValueError` otherwise. No arithmetic is performed —
the selected `Decimal` operand is returned unchanged, so no local `decimal` context,
quantisation, or rounding is used.
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


class CampaignTestAwareStaticDecreaseRoom(BaseModel):
    """A raw, test-aware static decrease-room constraint for one campaign.

    Not permissible decrease, not an effective decrease limit, and does not mean the
    campaign should be reduced. Does not account for the Stage 12 percentage cap or
    the Stage 14 protection constraint.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    test_aware_static_decrease_room: Decimal


def resolve_campaign_test_aware_static_decrease_room(
    static_room: CampaignStaticBudgetRoom,
    test_floor_room: CampaignTestFloorRoom,
) -> CampaignTestAwareStaticDecreaseRoom:
    """Combine one campaign's Stage 10 static-minimum room and Stage 13 test-floor
    room into one raw, test-aware static decrease-room constraint.

    `test_budget_floor` is treated as an additional retained-spend floor for test
    campaigns, so the higher of `minimum_budget`/`test_budget_floor` controls —
    equivalently, the smaller of the two already-calculated rooms:
    `room_to_static_minimum` when `room_to_test_floor is None` (non-test campaigns),
    otherwise `min(room_to_static_minimum, room_to_test_floor)`. Requires
    `static_room.campaign_id == test_floor_room.campaign_id`, raising `ValueError`
    otherwise. The selected `Decimal` operand is returned unchanged — no arithmetic,
    quantisation, or rounding is performed.
    """
    if static_room.campaign_id != test_floor_room.campaign_id:
        raise ValueError(
            "Campaign IDs must match when resolving test-aware static decrease room."
        )

    if test_floor_room.room_to_test_floor is None:
        test_aware_static_decrease_room = static_room.room_to_static_minimum
    else:
        test_aware_static_decrease_room = min(
            static_room.room_to_static_minimum,
            test_floor_room.room_to_test_floor,
        )

    return CampaignTestAwareStaticDecreaseRoom(
        campaign_id=static_room.campaign_id,
        test_aware_static_decrease_room=test_aware_static_decrease_room,
    )


class CampaignRawIncreaseLimit(BaseModel):
    """A raw increase limit for one campaign, intersecting Stage 10's static-maximum
    room and Stage 12's raw percentage movement cap.

    Not permission to increase a budget, an effective increase, eligibility, a
    recommendation, or a final movement amount.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    raw_increase_limit: Decimal


def resolve_campaign_raw_increase_limit(
    static_room: CampaignStaticBudgetRoom,
    raw_cap: CampaignRawPercentageMovementCap,
) -> CampaignRawIncreaseLimit:
    """Combine one campaign's Stage 10 static-maximum room and Stage 12 raw
    percentage movement cap into one raw increase limit.

    Both upward constraints apply simultaneously — `room_to_static_maximum` prevents
    exceeding `maximum_budget`, and `raw_percentage_movement_cap` limits the size of a
    change under the applicable percentage rule — so the smaller value is the binding
    limit: `raw_increase_limit = min(room_to_static_maximum,
    raw_percentage_movement_cap)`. Requires `static_room.campaign_id ==
    raw_cap.campaign_id`, raising `ValueError` otherwise. The selected `Decimal`
    operand is returned unchanged — no arithmetic, quantisation, or rounding is
    performed.
    """
    if static_room.campaign_id != raw_cap.campaign_id:
        raise ValueError(
            "Campaign IDs must match when resolving raw increase limit."
        )

    raw_increase_limit = min(
        static_room.room_to_static_maximum,
        raw_cap.raw_percentage_movement_cap,
    )

    return CampaignRawIncreaseLimit(
        campaign_id=static_room.campaign_id,
        raw_increase_limit=raw_increase_limit,
    )


class CampaignRawDecreaseLimit(BaseModel):
    """A raw decrease limit for one campaign, intersecting Stage 15's test-aware
    static decrease room and Stage 12's raw percentage movement cap.

    Not permission to decrease a budget, an effective decrease, eligibility, a
    recommendation, or a final movement amount.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    raw_decrease_limit: Decimal


def resolve_campaign_raw_decrease_limit(
    decrease_room: CampaignTestAwareStaticDecreaseRoom,
    raw_cap: CampaignRawPercentageMovementCap,
) -> CampaignRawDecreaseLimit:
    """Combine one campaign's Stage 15 test-aware static decrease room and Stage 12
    raw percentage movement cap into one raw decrease limit.

    Both decrease-side constraints apply simultaneously —
    `test_aware_static_decrease_room` preserves the approved minimum-budget/test-floor
    constraint, and `raw_percentage_movement_cap` limits the size of a change under the
    applicable percentage rule — so the smaller value is the binding limit:
    `raw_decrease_limit = min(test_aware_static_decrease_room,
    raw_percentage_movement_cap)`. Requires `decrease_room.campaign_id ==
    raw_cap.campaign_id`, raising `ValueError` otherwise. The selected `Decimal`
    operand is returned unchanged — no arithmetic, quantisation, or rounding is
    performed.
    """
    if decrease_room.campaign_id != raw_cap.campaign_id:
        raise ValueError(
            "Campaign IDs must match when resolving raw decrease limit."
        )

    raw_decrease_limit = min(
        decrease_room.test_aware_static_decrease_room,
        raw_cap.raw_percentage_movement_cap,
    )

    return CampaignRawDecreaseLimit(
        campaign_id=decrease_room.campaign_id,
        raw_decrease_limit=raw_decrease_limit,
    )
