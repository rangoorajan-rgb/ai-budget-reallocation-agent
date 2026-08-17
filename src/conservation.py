"""Deterministic, independent budget-conservation verification.

Implements Sprint 1 — Development Stage 26: independently verifies the
monetary invariant of one already-produced Stage 25
`CampaignReallocationAllocation` — that its total allocated increases
exactly equal its total allocated decreases. Conservation is a pure,
read-only checker, never an enforcer: it never reruns allocation, never
repairs an imbalance, and never mutates the allocation it inspects. An
imbalanced allocation is reported as `is_conserved=False` with its exact
signed `net_change` — the function itself never raises merely because
totals differ, since Stage 25's allocation is expected (but not blindly
trusted) to already balance, and an imbalance is a fact to report, not an
input error.

**Only one input is accepted** — `CampaignReallocationAllocation` itself.
`ReviewSetup`, `CampaignInput`, Stage 16/18 capacity results, Stage 24's
ranking, `CampaignRecommendation`, and `CampaignRecommendationReason` are
never accepted, read, or imported: reserve, final campaign budgets,
ranking order, and recommendation/reason context are all outside this
stage's responsibility, exactly as they were outside Stage 25's.

**Exact equality, no tolerance.** Every value here is an exact,
currency-quantised `Decimal` — there is no numeric noise a tolerance
would legitimately need to absorb, and any tolerance would only ever
serve to conceal a genuine one-penny implementation defect, precisely the
class of bug this stage exists to catch. An imbalance of exactly
`Decimal("0.01")` is reported as not conserved. `float` is never used
anywhere in this module.

**Sign convention.** `net_change = total_increase_allocated -
total_decrease_allocated`: positive means increases exceed decreases,
negative means decreases exceed increases, and exactly `Decimal("0.00")`
means conserved. No absolute difference is ever returned, and imbalance
direction is never encoded anywhere except in `net_change`'s own sign.

**Pure monetary sum check — campaign identity is never inspected.**
`campaign_id` is never read from any allocation record; this stage sums
every `allocated_amount` present, indifferent to duplicate IDs within one
direction, the same ID appearing in both directions, or repeated
zero-valued records. Stage 24 and Stage 25 already own campaign-identity
structural guarantees (uniqueness, direction separation, exactly one
record per ranked campaign); re-validating them here would duplicate
upstream responsibility this stage does not own. This stage also never
duplicates Stage 25's own donor/recipient matching, rank waterfall,
tied-tier proportional allocation, or residual-penny apportionment — it
only ever sums the amounts Stage 25 already decided.

**Decimal and context policy.** All arithmetic — every sum and the final
subtraction — runs inside an explicitly-scoped `localcontext`, with local
precision derived from the actual operands' digit counts and the number
of records being summed (never a blindly assumed fixed 28), so the
ambient global `Decimal` context can never affect the result, is never
mutated, and local-context rounding can never make two genuinely unequal
totals compare as equal. This mirrors, and is a direct response to, the
real ambient-context arithmetic defect discovered and corrected during
Stage 25's own implementation.

**A conserved zero allocation does not mean any campaign received
funding** — an all-zero allocation (e.g. no ranked `REDUCE` supply
existed to fund a ranked `INCREASE` candidate) is trivially conserved
(`Decimal("0.00") == Decimal("0.00")`), which reports a true fact about
balance, not a claim that money moved.

**No `ReasonCode` is ever emitted or referenced** — `ACCOUNT_RESERVE_REQUIRED`,
`NO_ELIGIBLE_RECIPIENT`, every constraint code, and every Stage 21/22
recommendation reason remain entirely outside this stage's scope; no new
enum member is added anywhere. This stage exposes only
`total_increase_allocated`, `total_decrease_allocated`, `net_change`, and
`is_conserved` to a later deterministic integration/reporting stage — it
does not decide what that later stage should do with an unconserved
result (publication gating, final budgets, and reporting are explicitly
not implemented here).
"""

from decimal import Decimal, localcontext

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.allocation import CampaignAllocatedAmount, CampaignReallocationAllocation
from src.models import Currency


def _safe_precision(operand_digit_counts: list[int], term_count: int) -> int:
    """Derive a local precision sufficient for the given operands' own
    digit counts and the number of terms being combined, so summing many
    large values never loses carry digits regardless of the ambient
    global context."""
    max_operand_digits = max(operand_digit_counts) if operand_digit_counts else 1
    count_digits = len(str(max(term_count, 1)))
    return max(28, max_operand_digits + count_digits + 10)


def _sum_allocated_amounts(records: tuple[CampaignAllocatedAmount, ...]) -> Decimal:
    """Sum one direction's `allocated_amount` values inside an
    explicitly-scoped local context, immune to the ambient global Decimal
    context and sized for the actual operands and record count."""
    if not records:
        return Decimal("0.00")

    amounts = [record.allocated_amount for record in records]
    safe_precision = _safe_precision(
        [len(amount.as_tuple().digits) for amount in amounts], len(amounts)
    )

    with localcontext() as ctx:
        ctx.prec = safe_precision
        total = Decimal("0.00")
        for amount in amounts:
            total += amount

    return total


class CampaignReallocationConservation(BaseModel):
    """Independently verified portfolio-level monetary conservation facts
    for one Stage 25 allocation.

    Not a repair, an allocation, a ranking, a recommendation, an
    explanation, or a decision about what a later stage should do with an
    unconserved result.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_increase_allocated: Currency = Field(ge=0)
    total_decrease_allocated: Currency = Field(ge=0)
    net_change: Decimal
    is_conserved: bool

    @model_validator(mode="after")
    def _check_conservation_consistency(self) -> "CampaignReallocationConservation":
        safe_precision = _safe_precision(
            [
                len(self.total_increase_allocated.as_tuple().digits),
                len(self.total_decrease_allocated.as_tuple().digits),
            ],
            2,
        )
        with localcontext() as ctx:
            ctx.prec = safe_precision
            expected_net_change = (
                self.total_increase_allocated - self.total_decrease_allocated
            )

        if self.net_change != expected_net_change:
            raise ValueError(
                "net_change must equal total_increase_allocated - "
                "total_decrease_allocated"
            )

        expected_is_conserved = self.net_change == Decimal("0.00")
        if self.is_conserved is not expected_is_conserved:
            raise ValueError(
                "is_conserved must equal (net_change == Decimal('0.00'))"
            )

        return self


def verify_campaign_reallocation_conservation(
    allocation: CampaignReallocationAllocation,
) -> CampaignReallocationConservation:
    """Independently recompute and verify one Stage 25 allocation's
    monetary conservation invariant.

    Sums `allocated_amount` across `increase_allocations` and
    `decrease_allocations` independently, never reading `campaign_id` or
    trusting any portfolio total from Stage 25 (Stage 25 returns none).
    `net_change = total_increase_allocated - total_decrease_allocated`;
    `is_conserved` is `True` only when `net_change` is exactly
    `Decimal("0.00")`. Always returns a result — never raises merely
    because the allocation is imbalanced.
    """
    total_increase_allocated = _sum_allocated_amounts(allocation.increase_allocations)
    total_decrease_allocated = _sum_allocated_amounts(allocation.decrease_allocations)

    safe_precision = _safe_precision(
        [
            len(total_increase_allocated.as_tuple().digits),
            len(total_decrease_allocated.as_tuple().digits),
        ],
        2,
    )
    with localcontext() as ctx:
        ctx.prec = safe_precision
        net_change = total_increase_allocated - total_decrease_allocated

    is_conserved = net_change == Decimal("0.00")

    return CampaignReallocationConservation(
        total_increase_allocated=total_increase_allocated,
        total_decrease_allocated=total_decrease_allocated,
        net_change=net_change,
        is_conserved=is_conserved,
    )
