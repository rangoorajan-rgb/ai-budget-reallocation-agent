"""Deterministic cross-campaign budget allocation.

Implements Sprint 1 — Development Stage 25: converts Stage 24's
direction-separated, dense-ranked candidate populations into actual,
balanced, campaign-level monetary movements, consuming Stage 16's
`CampaignRawIncreaseLimit` and Stage 18's `CampaignEffectiveDecreaseLimit`
as maximum capacities — never guaranteed movements. No separate
recommendation-amount stage exists; allocation consumes these existing
typed results directly, per the approved post-Stage-24 boundary decision.

**Reserve is excluded entirely.** `ReviewSetup.initial_account_reserve` is
never accepted, read, consumed, reduced, or returned — its authoritative
meaning (`docs/DATA_DICTIONARY.md`: *"Budget held back from
reallocation"*) treats it as protected and unavailable for funding
increases. `ReasonCode.ACCOUNT_RESERVE_REQUIRED` remains unassigned.

**The only funding source is ranked `REDUCE` capacity.** Total available
supply is the sum of `effective_decrease_limit` across every campaign in
`ranking.reduce_rankings` — unranked decrease-limit records never
contribute, and reserve never contributes.

**Allocation proceeds in two phases**, both a strict, dense-rank-tier
waterfall:

1. **Recipients.** `ranking.increase_rankings` is processed by ascending
   dense rank. Each rank tier is either fully funded (every campaign
   receives its exact `raw_increase_limit`) if remaining supply covers the
   whole tier, or — the first tier remaining supply cannot fully cover —
   split proportionally to capacity across that tied tier using the
   largest-remainder method below, after which every lower-ranked
   recipient receives `Decimal("0.00")`. A partially funded tier is a
   valid outcome, never an error.
2. **Donors.** The exact total allocated to recipients in Phase 1 becomes
   Phase 2's target. `ranking.reduce_rankings` is processed by the same
   ascending-dense-rank waterfall, drawing only that exact total from
   donor capacity — never more. Because Phase 1's total can never exceed
   total available supply (it is capped by that very supply), Phase 2
   always exhausts its target exactly across donor tiers; unused donor
   capacity beyond that target is left unused and is not returned as a
   separate field.

This structurally guarantees `sum(increase_allocations) ==
sum(decrease_allocations)` — a hard allocation invariant, not a
post-hoc check. Stage 26 conservation independently re-verifies this same
invariant as a separate, later responsibility; allocation itself never
reports a conservation status, and conservation must never repair or
mutate allocation's result.

**Largest-remainder currency method** (used only when a tied rank tier is
partially funded): each campaign's exact proportional share
(`available × capacity ÷ tier capacity`) is computed at high local
precision, then rounded down to `CURRENCY_QUANTUM` via `ROUND_DOWN`. The
sum of these floors is short of the exact available amount by a whole
number of pennies; those pennies are distributed one at a time, in order
of each campaign's fractional remainder descending, to the campaigns that
lost the most to rounding — never adding a penny that would push a
campaign's allocation above its own capacity. `campaign_id` ascending
breaks only an *exact* tie between two campaigns' fractional remainders;
it has no other role anywhere in this module, is never used to order
recipients against donors, and never influences which rank tier is
funded or by how much — a narrow exception to this project's "campaign ID
is a serialization aid only" principle, confined entirely to resolving
literal ties in indivisible-penny apportionment. If every capacity in a
tier is exactly zero, every campaign in it receives `Decimal("0.00")`
without performing any division.

**Insufficient and excess supply are both valid allocation outcomes, not
exceptions.** When total recipient capacity exceeds available supply, the
waterfall funds higher ranks first and may leave lower ranks at zero —
this is a legitimate partial result. When available supply exceeds total
recipient capacity, only what recipients can actually absorb is drawn
from donors; unused donor capacity is left with the donor. Neither
condition produces a `ReasonCode` — `NO_ELIGIBLE_RECIPIENT` and
`ACCOUNT_RESERVE_REQUIRED` remain unassigned, and this module never
imports, references, or assigns any `ReasonCode` member.

**Every campaign appearing in a Stage 24 ranking tuple appears exactly
once in the corresponding allocation tuple, including a
`Decimal("0.00")` allocation** — no campaign is silently dropped for
being unfunded. Output order exactly preserves Stage 24's own ranking
order; this module never reorders by allocated amount, capacity, or
campaign ID.

**Matching, not positional pairing.** `increase_limits` and
`decrease_limits` are matched to `ranking.increase_rankings`/
`.reduce_rankings` exclusively by `campaign_id` value — never by tuple
position, and `zip` is never used. Every `campaign_id` must be unique
within each limit collection; a ranked campaign missing its
direction-appropriate limit is an error. Extra, unranked limit records
are legitimate and silently ignored — Stage 16/18 compute a limit for
every campaign in a review, while Stage 24 ranks only a subset. Stage 24's
own already-validated guarantees (uniqueness within ranking tuples,
direction separation, rank correctness, deterministic ordering) are
trusted, never recalculated or revalidated here.

**Excluded from this module entirely:** `ReviewSetup`, `CampaignInput`,
`CampaignRecommendation`, `CampaignRecommendationReason`, `ReasonCode`,
`CampaignActionAvailability`, `CampaignActionSuitability`,
`CampaignPerformanceClass`, `CampaignTrendClass`, `CampaignPacingClass`,
`CampaignConfidenceClass`, `CampaignTrackingAssessment`, raw campaign
metrics, `reallocation_priority_score` (Stage 24's dense `rank` is
authoritative; the score is never re-read), final campaign budgets, and
any conservation logic. `float` is never used anywhere in this module —
`Decimal` exclusively, with every arithmetic operation performed inside
an explicitly-precision-scoped `localcontext`, so the ambient global
`Decimal` context can never affect the result and is never mutated.
"""

from decimal import ROUND_DOWN, Decimal, localcontext

from pydantic import BaseModel, ConfigDict, Field

from src.constants import CURRENCY_QUANTUM
from src.constraints import CampaignEffectiveDecreaseLimit, CampaignRawIncreaseLimit
from src.models import Currency
from src.ranking import CampaignReallocationRanking, RankedCampaignPriority


class CampaignAllocatedAmount(BaseModel):
    """One campaign's actual allocated movement within one direction.

    Always unsigned and non-negative. Direction is represented
    structurally by membership in `CampaignReallocationAllocation`'s
    `increase_allocations` or `decrease_allocations` — never through a
    negative sign. Not a final budget, a capacity, a remaining-capacity
    figure, a rank, a score, or an explanation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    allocated_amount: Currency = Field(ge=0)


class CampaignReallocationAllocation(BaseModel):
    """Two direction-separated, dense-rank-ordered sets of actual
    campaign movements.

    Every campaign appearing in the corresponding Stage 24 ranking tuple
    appears exactly once here, including at `Decimal("0.00")`. Either or
    both tuples may be empty. `sum(increase_allocations) ==
    sum(decrease_allocations)` always holds — a constructed invariant,
    not merely a hope.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    increase_allocations: tuple[CampaignAllocatedAmount, ...]
    decrease_allocations: tuple[CampaignAllocatedAmount, ...]


def _sum_currency(values: list[Decimal]) -> Decimal:
    """Sum already-quantised currency values inside an explicitly-scoped
    local context, immune to the ambient global Decimal context."""
    with localcontext() as ctx:
        ctx.prec = 28
        total = Decimal("0.00")
        for value in values:
            total += value
    return total


def _group_by_rank(
    ranked_campaigns: tuple[RankedCampaignPriority, ...],
    capacity_by_id: dict[str, Decimal],
) -> list[list[tuple[str, Decimal]]]:
    """Group already rank-ordered campaigns into consecutive dense-rank
    tiers, trusting Stage 24's own ordering guarantee rather than
    re-deriving it."""
    tiers: list[list[tuple[str, Decimal]]] = []
    current_rank: int | None = None
    for ranked in ranked_campaigns:
        if ranked.rank != current_rank:
            tiers.append([])
            current_rank = ranked.rank
        tiers[-1].append((ranked.campaign_id, capacity_by_id[ranked.campaign_id]))
    return tiers


def _largest_remainder_split(
    tier: list[tuple[str, Decimal]], available: Decimal
) -> dict[str, Decimal]:
    """Split `available` across one tied tier, proportional to capacity,
    using the largest-remainder currency method.

    `campaign_id` ascending is used only to break an exact tie between
    two campaigns' fractional remainders during penny apportionment.
    """
    total_capacity = _sum_currency([capacity for _, capacity in tier])
    if total_capacity == Decimal("0.00"):
        return {campaign_id: Decimal("0.00") for campaign_id, _ in tier}

    operand_digits = (
        max(
            len(available.as_tuple().digits) + len(capacity.as_tuple().digits)
            for _, capacity in tier
        )
        + len(total_capacity.as_tuple().digits)
    )
    safe_precision = max(28, operand_digits + 10)

    # The entire computation — including the residual/penny bookkeeping and
    # apportionment below, not only the initial division — runs inside this
    # one explicitly-scoped context, so no step is ever exposed to the
    # ambient global Decimal context.
    with localcontext() as ctx:
        ctx.prec = safe_precision
        ctx.rounding = ROUND_DOWN

        exact_shares: dict[str, Decimal] = {}
        rounded_down: dict[str, Decimal] = {}
        for campaign_id, capacity in tier:
            exact_share = (available * capacity) / total_capacity
            exact_shares[campaign_id] = exact_share
            rounded_down[campaign_id] = exact_share.quantize(
                CURRENCY_QUANTUM, rounding=ROUND_DOWN
            )

        sum_rounded_down = Decimal("0.00")
        for value in rounded_down.values():
            sum_rounded_down += value
        residual = available - sum_rounded_down
        residual_pennies = int(residual / CURRENCY_QUANTUM)

        ordering = sorted(
            tier,
            key=lambda item: (-(exact_shares[item[0]] - rounded_down[item[0]]), item[0]),
        )

        allocations = dict(rounded_down)
        capacity_by_id = dict(tier)
        remaining_pennies = residual_pennies
        while remaining_pennies > 0:
            progressed = False
            for campaign_id, _ in ordering:
                if remaining_pennies <= 0:
                    break
                candidate = allocations[campaign_id] + CURRENCY_QUANTUM
                if candidate <= capacity_by_id[campaign_id]:
                    allocations[campaign_id] = candidate
                    remaining_pennies -= 1
                    progressed = True
            if not progressed:
                break

    return allocations


def _waterfall_allocate(
    tiers: list[list[tuple[str, Decimal]]], available: Decimal
) -> dict[str, Decimal]:
    """Fund dense-rank tiers in ascending order: fully fund a tier while
    supply covers it, split the first tier supply cannot fully cover, then
    zero every lower tier."""
    allocations: dict[str, Decimal] = {}
    with localcontext() as ctx:
        ctx.prec = 28
        remaining = available
        for tier in tiers:
            tier_total = Decimal("0.00")
            for _, capacity in tier:
                tier_total += capacity
            if remaining >= tier_total:
                for campaign_id, capacity in tier:
                    allocations[campaign_id] = capacity
                remaining -= tier_total
            else:
                allocations.update(_largest_remainder_split(tier, remaining))
                remaining = Decimal("0.00")
    return allocations


def allocate_campaign_reallocation(
    ranking: CampaignReallocationRanking,
    increase_limits: tuple[CampaignRawIncreaseLimit, ...],
    decrease_limits: tuple[CampaignEffectiveDecreaseLimit, ...],
) -> CampaignReallocationAllocation:
    """Allocate actual, balanced campaign movements from Stage 24's
    rankings and Stage 16/18's capacities.

    Requires every `campaign_id` to be unique within `increase_limits`
    and within `decrease_limits`, and every ranked campaign to have a
    matching direction-appropriate limit, raising `ValueError` otherwise
    before any allocation arithmetic runs. Extra, unranked limit records
    are ignored. Available supply is the sum of `effective_decrease_limit`
    across `ranking.reduce_rankings` only. Recipients are funded first, by
    a strict dense-rank waterfall bounded by that supply; the exact total
    funded is then drawn from donors by the same waterfall, guaranteeing
    `sum(increase_allocations) == sum(decrease_allocations)`.
    """
    increase_limit_ids = [limit.campaign_id for limit in increase_limits]
    if len(increase_limit_ids) != len(set(increase_limit_ids)):
        raise ValueError(
            "Increase-limit campaign IDs must be unique when allocating "
            "reallocation."
        )

    decrease_limit_ids = [limit.campaign_id for limit in decrease_limits]
    if len(decrease_limit_ids) != len(set(decrease_limit_ids)):
        raise ValueError(
            "Decrease-limit campaign IDs must be unique when allocating "
            "reallocation."
        )

    increase_limit_by_id = {
        limit.campaign_id: limit.raw_increase_limit for limit in increase_limits
    }
    for ranked in ranking.increase_rankings:
        if ranked.campaign_id not in increase_limit_by_id:
            raise ValueError(
                "Every ranked increase campaign must have a matching "
                "increase limit."
            )

    decrease_limit_by_id = {
        limit.campaign_id: limit.effective_decrease_limit for limit in decrease_limits
    }
    for ranked in ranking.reduce_rankings:
        if ranked.campaign_id not in decrease_limit_by_id:
            raise ValueError(
                "Every ranked decrease campaign must have a matching "
                "decrease limit."
            )

    increase_tiers = _group_by_rank(ranking.increase_rankings, increase_limit_by_id)
    decrease_tiers = _group_by_rank(ranking.reduce_rankings, decrease_limit_by_id)

    available_supply = _sum_currency(
        [decrease_limit_by_id[ranked.campaign_id] for ranked in ranking.reduce_rankings]
    )

    increase_allocation_by_id = _waterfall_allocate(increase_tiers, available_supply)
    total_allocated = _sum_currency(list(increase_allocation_by_id.values()))
    decrease_allocation_by_id = _waterfall_allocate(decrease_tiers, total_allocated)

    increase_allocations = tuple(
        CampaignAllocatedAmount(
            campaign_id=ranked.campaign_id,
            allocated_amount=increase_allocation_by_id[ranked.campaign_id],
        )
        for ranked in ranking.increase_rankings
    )
    decrease_allocations = tuple(
        CampaignAllocatedAmount(
            campaign_id=ranked.campaign_id,
            allocated_amount=decrease_allocation_by_id[ranked.campaign_id],
        )
        for ranked in ranking.reduce_rankings
    )

    return CampaignReallocationAllocation(
        increase_allocations=increase_allocations,
        decrease_allocations=decrease_allocations,
    )
