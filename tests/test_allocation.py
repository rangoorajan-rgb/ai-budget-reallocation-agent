"""Tests for src.allocation (Sprint 1 — Development Stage 25).

Covers CampaignAllocatedAmount/CampaignReallocationAllocation construction,
immutability, and non-negative-currency validation; campaign-ID matching
between rankings and limits (never positional); the exact
uniqueness/missing-limit validation order and error messages; the strict
dense-rank waterfall for both recipients and donors; the largest-remainder
proportional split for partially funded tied tiers (including the narrow
campaign-ID fractional-remainder tie-break); insufficient/excess-supply
behavior; reserve exclusion; the balance invariant
(sum(increase)==sum(decrease)); Decimal-only arithmetic immune to ambient
context mutation; isolation from every excluded field/type/function; and
sample-data integration.
"""

import ast
import inspect
from decimal import Decimal, getcontext, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.allocation import (
    CampaignAllocatedAmount,
    CampaignReallocationAllocation,
    allocate_campaign_reallocation,
)
from src.constants import CampaignStatus
from src.constraints import CampaignEffectiveDecreaseLimit, CampaignRawIncreaseLimit
from src.ranking import CampaignReallocationRanking, RankedCampaignPriority

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _ranked(campaign_id: str, rank: int, score: int = 100) -> RankedCampaignPriority:
    return RankedCampaignPriority(
        campaign_id=campaign_id, rank=rank, reallocation_priority_score=score
    )


def _ranking(increase=(), reduce=()) -> CampaignReallocationRanking:
    return CampaignReallocationRanking(
        increase_rankings=tuple(increase), reduce_rankings=tuple(reduce)
    )


def _increase_limit(campaign_id: str, amount: str) -> CampaignRawIncreaseLimit:
    return CampaignRawIncreaseLimit(
        campaign_id=campaign_id, raw_increase_limit=Decimal(amount)
    )


def _decrease_limit(campaign_id: str, amount: str) -> CampaignEffectiveDecreaseLimit:
    return CampaignEffectiveDecreaseLimit(
        campaign_id=campaign_id, effective_decrease_limit=Decimal(amount)
    )


_EXACT_DUP_INCREASE_MESSAGE = (
    "Increase-limit campaign IDs must be unique when allocating reallocation."
)
_EXACT_DUP_DECREASE_MESSAGE = (
    "Decrease-limit campaign IDs must be unique when allocating reallocation."
)
_EXACT_MISSING_INCREASE_MESSAGE = (
    "Every ranked increase campaign must have a matching increase limit."
)
_EXACT_MISSING_DECREASE_MESSAGE = (
    "Every ranked decrease campaign must have a matching decrease limit."
)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


def test_campaign_allocated_amount_field_shape():
    assert set(CampaignAllocatedAmount.model_fields.keys()) == {
        "campaign_id",
        "allocated_amount",
    }


def test_campaign_reallocation_allocation_field_shape():
    assert set(CampaignReallocationAllocation.model_fields.keys()) == {
        "increase_allocations",
        "decrease_allocations",
    }


def test_campaign_allocated_amount_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignAllocatedAmount(
            campaign_id="C001", allocated_amount=Decimal("10.00"), extra="x"
        )


def test_campaign_reallocation_allocation_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignReallocationAllocation(
            increase_allocations=(), decrease_allocations=(), extra="x"
        )


def test_campaign_allocated_amount_is_immutable():
    record = CampaignAllocatedAmount(campaign_id="C001", allocated_amount=Decimal("10.00"))
    with pytest.raises(ValidationError):
        record.allocated_amount = Decimal("20.00")


def test_campaign_reallocation_allocation_is_immutable():
    result = CampaignReallocationAllocation(increase_allocations=(), decrease_allocations=())
    with pytest.raises(ValidationError):
        result.increase_allocations = ()


def test_allocated_amount_is_quantised_currency():
    record = CampaignAllocatedAmount(campaign_id="C001", allocated_amount=Decimal("10.005"))
    assert record.allocated_amount == Decimal("10.01")  # ROUND_HALF_UP via Currency


def test_negative_allocation_rejected():
    with pytest.raises(ValidationError):
        CampaignAllocatedAmount(campaign_id="C001", allocated_amount=Decimal("-0.01"))


def test_zero_allocation_accepted():
    record = CampaignAllocatedAmount(campaign_id="C001", allocated_amount=Decimal("0.00"))
    assert record.allocated_amount == Decimal("0.00")


def test_tuple_serialization():
    result = CampaignReallocationAllocation(
        increase_allocations=(
            CampaignAllocatedAmount(campaign_id="C001", allocated_amount=Decimal("10.00")),
        ),
        decrease_allocations=(),
    )
    dumped = result.model_dump()
    assert dumped == {
        "increase_allocations": ({"campaign_id": "C001", "allocated_amount": Decimal("10.00")},),
        "decrease_allocations": (),
    }


def test_independently_empty_tuples():
    only_increase = CampaignReallocationAllocation(
        increase_allocations=(
            CampaignAllocatedAmount(campaign_id="C001", allocated_amount=Decimal("10.00")),
        ),
        decrease_allocations=(),
    )
    both_empty = CampaignReallocationAllocation(increase_allocations=(), decrease_allocations=())
    assert only_increase.decrease_allocations == ()
    assert both_empty.increase_allocations == () and both_empty.decrease_allocations == ()


def test_result_contains_no_forbidden_field():
    amount_fields = set(CampaignAllocatedAmount.model_fields.keys())
    batch_fields = set(CampaignReallocationAllocation.model_fields.keys())
    forbidden = {
        "recommendation_action",
        "rank",
        "reallocation_priority_score",
        "capacity",
        "remaining_capacity",
        "final_budget",
        "reserve_used",
        "final_reserve",
        "reason_codes",
        "unallocated_supply",
    }
    assert amount_fields.isdisjoint(forbidden)
    assert batch_fields.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Validation: uniqueness and missing limits
# ---------------------------------------------------------------------------


def test_duplicate_increase_limit_id_raises_exact_error():
    with pytest.raises(ValueError) as exc_info:
        allocate_campaign_reallocation(
            _ranking(increase=[_ranked("C001", 1)]),
            (_increase_limit("C001", "100.00"), _increase_limit("C001", "50.00")),
            (),
        )
    assert str(exc_info.value) == _EXACT_DUP_INCREASE_MESSAGE


def test_duplicate_decrease_limit_id_raises_exact_error():
    with pytest.raises(ValueError) as exc_info:
        allocate_campaign_reallocation(
            _ranking(),
            (),
            (_decrease_limit("C001", "100.00"), _decrease_limit("C001", "50.00")),
        )
    assert str(exc_info.value) == _EXACT_DUP_DECREASE_MESSAGE


def test_both_duplicate_conditions_increase_error_takes_precedence():
    with pytest.raises(ValueError) as exc_info:
        allocate_campaign_reallocation(
            _ranking(),
            (_increase_limit("C001", "100.00"), _increase_limit("C001", "50.00")),
            (_decrease_limit("C002", "100.00"), _decrease_limit("C002", "50.00")),
        )
    assert str(exc_info.value) == _EXACT_DUP_INCREASE_MESSAGE


def test_missing_ranked_increase_limit_raises_exact_error():
    with pytest.raises(ValueError) as exc_info:
        allocate_campaign_reallocation(
            _ranking(increase=[_ranked("C001", 1)]),
            (),
            (),
        )
    assert str(exc_info.value) == _EXACT_MISSING_INCREASE_MESSAGE


def test_missing_ranked_decrease_limit_raises_exact_error():
    with pytest.raises(ValueError) as exc_info:
        allocate_campaign_reallocation(
            _ranking(reduce=[_ranked("C001", 1)]),
            (),
            (),
        )
    assert str(exc_info.value) == _EXACT_MISSING_DECREASE_MESSAGE


def test_extra_unranked_increase_limits_accepted():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("C001", 1)]),
        (
            _increase_limit("C001", "100.00"),
            _increase_limit("UNRANKED-1", "500.00"),
            _increase_limit("UNRANKED-2", "700.00"),
        ),
        (),
    )
    assert len(result.increase_allocations) == 1


def test_extra_unranked_decrease_limits_accepted():
    result = allocate_campaign_reallocation(
        _ranking(reduce=[_ranked("C001", 1)]),
        (),
        (
            _decrease_limit("C001", "100.00"),
            _decrease_limit("UNRANKED-1", "500.00"),
        ),
    )
    assert len(result.decrease_allocations) == 1


def test_shuffled_limit_collections_matched_by_id():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("C001", 1), _ranked("C002", 2)]),
        (_increase_limit("C002", "40.00"), _increase_limit("C001", "60.00")),
        (),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    assert by_id["C001"] == Decimal("0.00")
    assert by_id["C002"] == Decimal("0.00")


def test_no_positional_zip_used():
    import src.allocation as allocation_module

    source = inspect.getsource(allocation_module)
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "zip" not in called_names


def test_both_directions_empty_returns_empty_result():
    result = allocate_campaign_reallocation(_ranking(), (), ())
    assert result == CampaignReallocationAllocation(
        increase_allocations=(), decrease_allocations=()
    )


def test_validation_before_allocation_arithmetic():
    with pytest.raises(ValueError):
        allocate_campaign_reallocation(
            _ranking(increase=[_ranked("C001", 1)]),
            (_increase_limit("C001", "10.00"), _increase_limit("C001", "20.00")),
            (),
        )


def test_none_inputs_not_silently_converted():
    with pytest.raises((TypeError, AttributeError)):
        allocate_campaign_reallocation(None, None, None)  # type: ignore[arg-type]


def test_no_broad_exception_handling_in_source():
    source = inspect.getsource(allocate_campaign_reallocation)
    assert "except" not in source


# ---------------------------------------------------------------------------
# Basic allocation
# ---------------------------------------------------------------------------


def test_equal_recipient_and_donor_capacity():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "500.00"),),
        (_decrease_limit("D1", "500.00"),),
    )
    assert result.increase_allocations[0].allocated_amount == Decimal("500.00")
    assert result.decrease_allocations[0].allocated_amount == Decimal("500.00")


def test_recipient_capacity_greater_than_donor_capacity():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "1000.00"),),
        (_decrease_limit("D1", "300.00"),),
    )
    assert result.increase_allocations[0].allocated_amount == Decimal("300.00")
    assert result.decrease_allocations[0].allocated_amount == Decimal("300.00")


def test_donor_capacity_greater_than_recipient_capacity():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "200.00"),),
        (_decrease_limit("D1", "1000.00"),),
    )
    assert result.increase_allocations[0].allocated_amount == Decimal("200.00")
    assert result.decrease_allocations[0].allocated_amount == Decimal("200.00")


def test_donor_contributes_only_actual_recipient_allocation():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1), _ranked("D2", 2)]),
        (_increase_limit("R1", "100.00"),),
        (_decrease_limit("D1", "1000.00"), _decrease_limit("D2", "1000.00")),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.decrease_allocations}
    assert by_id["D1"] == Decimal("100.00")
    assert by_id["D2"] == Decimal("0.00")


def test_recipient_never_exceeds_capacity():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "50.00"),),
        (_decrease_limit("D1", "1000.00"),),
    )
    assert result.increase_allocations[0].allocated_amount <= Decimal("50.00")


def test_donor_never_exceeds_capacity():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "1000.00"),),
        (_decrease_limit("D1", "50.00"),),
    )
    assert result.decrease_allocations[0].allocated_amount <= Decimal("50.00")


def test_totals_exactly_balance_basic():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "733.37"),),
        (_decrease_limit("D1", "1000.00"),),
    )
    total_increase = sum((r.allocated_amount for r in result.increase_allocations), Decimal("0.00"))
    total_decrease = sum((r.allocated_amount for r in result.decrease_allocations), Decimal("0.00"))
    assert total_increase == total_decrease


# ---------------------------------------------------------------------------
# Rank waterfall
# ---------------------------------------------------------------------------


def test_higher_recipient_rank_fully_funded_before_lower():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 2)],
            reduce=[_ranked("D1", 1)],
        ),
        (_increase_limit("R1", "100.00"), _increase_limit("R2", "100.00")),
        (_decrease_limit("D1", "150.00"),),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    assert by_id["R1"] == Decimal("100.00")
    assert by_id["R2"] == Decimal("50.00")


def test_partial_higher_rank_prevents_lower_rank_funding():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 2)],
            reduce=[_ranked("D1", 1)],
        ),
        (_increase_limit("R1", "200.00"), _increase_limit("R2", "100.00")),
        (_decrease_limit("D1", "50.00"),),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    assert by_id["R1"] == Decimal("50.00")
    assert by_id["R2"] == Decimal("0.00")


def test_higher_donor_rank_fully_used_before_lower():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 2)],
        ),
        (_increase_limit("R1", "150.00"),),
        (_decrease_limit("D1", "100.00"), _decrease_limit("D2", "100.00")),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.decrease_allocations}
    assert by_id["D1"] == Decimal("100.00")
    assert by_id["D2"] == Decimal("50.00")


def test_partially_used_donor_rank_prevents_lower_rank_contribution():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 2)],
        ),
        (_increase_limit("R1", "50.00"),),
        (_decrease_limit("D1", "200.00"), _decrease_limit("D2", "200.00")),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.decrease_allocations}
    assert by_id["D1"] == Decimal("50.00")
    assert by_id["D2"] == Decimal("0.00")


def test_ranks_restart_independently_through_stage_24():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (_increase_limit("R1", "10.00"),),
        (_decrease_limit("D1", "10.00"),),
    )
    assert result.increase_allocations[0].allocated_amount == Decimal("10.00")
    assert result.decrease_allocations[0].allocated_amount == Decimal("10.00")


def test_zero_capacity_tier_safely_skipped():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1), _ranked("R2", 2)]),
        (_increase_limit("R1", "0.00"), _increase_limit("R2", "100.00")),
        (),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    assert by_id["R1"] == Decimal("0.00")
    assert by_id["R2"] == Decimal("0.00")  # no supply at all


# ---------------------------------------------------------------------------
# Recipient ties
# ---------------------------------------------------------------------------


def test_recipient_tie_equal_capacities():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (_increase_limit("R1", "100.00"), _increase_limit("R2", "100.00")),
        (_decrease_limit("D1", "100.00"),),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    assert by_id["R1"] == Decimal("50.00")
    assert by_id["R2"] == Decimal("50.00")


def test_recipient_tie_unequal_capacities_exact_proportional_shares():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (_increase_limit("R1", "300.00"), _increase_limit("R2", "100.00")),
        (_decrease_limit("D1", "200.00"),),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    # total tier capacity 400.00, available 200.00 -> exactly half each's capacity
    assert by_id["R1"] == Decimal("150.00")
    assert by_id["R2"] == Decimal("50.00")
    assert by_id["R1"] + by_id["R2"] == Decimal("200.00")


def test_recipient_tie_fractional_cent_shares_largest_remainder():
    # 100.00 split 3 ways with equal capacity -> 33.33, 33.33, 33.34
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1), _ranked("R3", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (
            _increase_limit("R1", "1000.00"),
            _increase_limit("R2", "1000.00"),
            _increase_limit("R3", "1000.00"),
        ),
        (_decrease_limit("D1", "100.00"),),
    )
    amounts = sorted(r.allocated_amount for r in result.increase_allocations)
    assert amounts == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert sum(amounts, Decimal("0.00")) == Decimal("100.00")


def test_recipient_tie_exact_fractional_remainder_tie_resolved_by_campaign_id():
    # Equal capacities => identical fractional remainders; the extra penny(ies)
    # must go to the lexicographically smallest campaign_id(s) first.
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("B", 1), _ranked("A", 1), _ranked("C", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (
            _increase_limit("A", "100.00"),
            _increase_limit("B", "100.00"),
            _increase_limit("C", "100.00"),
        ),
        (_decrease_limit("D1", "10.00"),),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    # 10.00 / 3 = 3.33 each, remainder 0.01 -> smallest campaign_id "A" gets it
    assert by_id["A"] == Decimal("3.34")
    assert by_id["B"] == Decimal("3.33")
    assert by_id["C"] == Decimal("3.33")


def test_recipient_tie_no_allocation_over_capacity():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (_increase_limit("R1", "10.01"), _increase_limit("R2", "1000.00")),
        (_decrease_limit("D1", "20.00"),),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    assert by_id["R1"] <= Decimal("10.01")
    assert by_id["R2"] <= Decimal("1000.00")


def test_recipient_tie_residual_exhausted_exactly():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1), _ranked("R3", 1), _ranked("R4", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (
            _increase_limit("R1", "1000.00"),
            _increase_limit("R2", "1000.00"),
            _increase_limit("R3", "1000.00"),
            _increase_limit("R4", "1000.00"),
        ),
        (_decrease_limit("D1", "10.00"),),
    )
    total = sum((r.allocated_amount for r in result.increase_allocations), Decimal("0.00"))
    assert total == Decimal("10.00")


def test_lower_ranks_zero_after_partial_tied_tier_funding():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1), _ranked("R3", 2)],
            reduce=[_ranked("D1", 1)],
        ),
        (
            _increase_limit("R1", "100.00"),
            _increase_limit("R2", "100.00"),
            _increase_limit("R3", "500.00"),
        ),
        (_decrease_limit("D1", "50.00"),),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.increase_allocations}
    assert by_id["R3"] == Decimal("0.00")


# ---------------------------------------------------------------------------
# Donor ties (same cases, independently, on the decrease side)
# ---------------------------------------------------------------------------


def test_donor_tie_equal_capacities():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 1)],
        ),
        (_increase_limit("R1", "100.00"),),
        (_decrease_limit("D1", "1000.00"), _decrease_limit("D2", "1000.00")),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.decrease_allocations}
    assert by_id["D1"] == Decimal("50.00")
    assert by_id["D2"] == Decimal("50.00")


def test_donor_tie_unequal_capacities_exact_proportional_shares():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 1)],
        ),
        (_increase_limit("R1", "200.00"),),
        (_decrease_limit("D1", "300.00"), _decrease_limit("D2", "100.00")),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.decrease_allocations}
    assert by_id["D1"] == Decimal("150.00")
    assert by_id["D2"] == Decimal("50.00")


def test_donor_tie_fractional_cent_shares_largest_remainder():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 1), _ranked("D3", 1)],
        ),
        (_increase_limit("R1", "100.00"),),
        (
            _decrease_limit("D1", "1000.00"),
            _decrease_limit("D2", "1000.00"),
            _decrease_limit("D3", "1000.00"),
        ),
    )
    amounts = sorted(r.allocated_amount for r in result.decrease_allocations)
    assert amounts == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]


def test_donor_tie_exact_fractional_remainder_tie_resolved_by_campaign_id():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("Z", 1), _ranked("Y", 1), _ranked("X", 1)],
        ),
        (_increase_limit("R1", "10.00"),),
        (
            _decrease_limit("X", "100.00"),
            _decrease_limit("Y", "100.00"),
            _decrease_limit("Z", "100.00"),
        ),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.decrease_allocations}
    assert by_id["X"] == Decimal("3.34")
    assert by_id["Y"] == Decimal("3.33")
    assert by_id["Z"] == Decimal("3.33")


def test_donor_tie_no_allocation_over_capacity():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 1)],
        ),
        (_increase_limit("R1", "20.00"),),
        (_decrease_limit("D1", "10.01"), _decrease_limit("D2", "1000.00")),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.decrease_allocations}
    assert by_id["D1"] <= Decimal("10.01")


def test_donor_tie_residual_exhausted_exactly():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 1), _ranked("D3", 1), _ranked("D4", 1)],
        ),
        (_increase_limit("R1", "10.00"),),
        (
            _decrease_limit("D1", "1000.00"),
            _decrease_limit("D2", "1000.00"),
            _decrease_limit("D3", "1000.00"),
            _decrease_limit("D4", "1000.00"),
        ),
    )
    total = sum((r.allocated_amount for r in result.decrease_allocations), Decimal("0.00"))
    assert total == Decimal("10.00")


def test_donor_lower_ranks_zero_after_partial_tied_tier_funding():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 1), _ranked("D3", 2)],
        ),
        (_increase_limit("R1", "50.00"),),
        (
            _decrease_limit("D1", "100.00"),
            _decrease_limit("D2", "100.00"),
            _decrease_limit("D3", "500.00"),
        ),
    )
    by_id = {r.campaign_id: r.allocated_amount for r in result.decrease_allocations}
    assert by_id["D3"] == Decimal("0.00")


# ---------------------------------------------------------------------------
# Decimal policy
# ---------------------------------------------------------------------------


def test_no_float_conversion_in_source():
    import src.allocation as allocation_module

    source = inspect.getsource(allocation_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "float" not in referenced


def test_exact_two_decimal_output():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "10.00"),),
        (_decrease_limit("D1", "10.00"),),
    )
    for record in result.increase_allocations + result.decrease_allocations:
        assert record.allocated_amount.as_tuple().exponent == -2


def test_exact_decimal_zero_zero():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)]),
        (_increase_limit("R1", "100.00"),),
        (),
    )
    assert result.increase_allocations[0].allocated_amount.as_tuple() == Decimal("0.00").as_tuple()


def test_extreme_decimal_magnitudes():
    huge = "99999999999999999999999999.99"
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1), _ranked("R2", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", huge), _increase_limit("R2", huge)),
        (_decrease_limit("D1", huge),),
    )
    total = sum((r.allocated_amount for r in result.increase_allocations), Decimal("0.00"))
    assert total == Decimal(huge)


def test_large_collections():
    increase_ranked = [_ranked(f"R{i:04d}", 1) for i in range(200)]
    increase_limits = tuple(_increase_limit(f"R{i:04d}", "10.00") for i in range(200))
    result = allocate_campaign_reallocation(
        _ranking(increase=increase_ranked),
        increase_limits,
        (),
    )
    assert len(result.increase_allocations) == 200
    assert all(r.allocated_amount == Decimal("0.00") for r in result.increase_allocations)


def test_mutated_ambient_decimal_context_does_not_affect_output():
    ranking = _ranking(
        increase=[_ranked("R1", 1), _ranked("R2", 1), _ranked("R3", 1)],
        reduce=[_ranked("D1", 1)],
    )
    increase_limits = (
        _increase_limit("R1", "1000.00"),
        _increase_limit("R2", "1000.00"),
        _increase_limit("R3", "1000.00"),
    )
    decrease_limits = (_decrease_limit("D1", "100.00"),)

    baseline = allocate_campaign_reallocation(ranking, increase_limits, decrease_limits)

    # A degenerate precision (e.g. 2) would break Currency field
    # construction itself (a pre-existing characteristic of every Currency
    # field in this project, not specific to allocation) regardless of any
    # stage's own logic, so this mutation uses a realistic-but-different
    # precision/rounding pair to isolate allocation's own context immunity.
    original_prec = getcontext().prec
    original_rounding = getcontext().rounding
    try:
        getcontext().prec = 10
        getcontext().rounding = "ROUND_CEILING"
        mutated = allocate_campaign_reallocation(ranking, increase_limits, decrease_limits)
    finally:
        getcontext().prec = original_prec
        getcontext().rounding = original_rounding

    assert baseline.model_dump() == mutated.model_dump()
    assert getcontext().prec == original_prec
    assert getcontext().rounding == original_rounding


def test_repeating_decimal_split():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1), _ranked("R3", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (
            _increase_limit("R1", "1.00"),
            _increase_limit("R2", "1.00"),
            _increase_limit("R3", "1.00"),
        ),
        (_decrease_limit("D1", "1.00"),),
    )
    total = sum((r.allocated_amount for r in result.increase_allocations), Decimal("0.00"))
    assert total == Decimal("1.00")


def test_one_penny_residual():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        (_increase_limit("R1", "1.00"), _increase_limit("R2", "1.00")),
        (_decrease_limit("D1", "0.01"),),
    )
    total = sum((r.allocated_amount for r in result.increase_allocations), Decimal("0.00"))
    assert total == Decimal("0.01")


def test_multi_penny_residual():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1), _ranked("R3", 1), _ranked("R4", 1), _ranked("R5", 1)],
            reduce=[_ranked("D1", 1)],
        ),
        tuple(_increase_limit(f"R{i}", "1000.00") for i in range(1, 6)),
        (_decrease_limit("D1", "10.03"),),
    )
    total = sum((r.allocated_amount for r in result.increase_allocations), Decimal("0.00"))
    assert total == Decimal("10.03")


def test_increase_and_decrease_totals_exactly_equal():
    result = allocate_campaign_reallocation(
        _ranking(
            increase=[_ranked("R1", 1), _ranked("R2", 1)],
            reduce=[_ranked("D1", 1), _ranked("D2", 2)],
        ),
        (_increase_limit("R1", "77.77"), _increase_limit("R2", "77.77")),
        (_decrease_limit("D1", "50.00"), _decrease_limit("D2", "200.00")),
    )
    total_increase = sum((r.allocated_amount for r in result.increase_allocations), Decimal("0.00"))
    total_decrease = sum((r.allocated_amount for r in result.decrease_allocations), Decimal("0.00"))
    assert total_increase == total_decrease


# ---------------------------------------------------------------------------
# Empty and no-counterparty cases
# ---------------------------------------------------------------------------


def test_no_recipients_and_no_donors():
    result = allocate_campaign_reallocation(_ranking(), (), ())
    assert result.increase_allocations == ()
    assert result.decrease_allocations == ()


def test_recipients_with_no_donors():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1), _ranked("R2", 2)]),
        (_increase_limit("R1", "100.00"), _increase_limit("R2", "50.00")),
        (),
    )
    assert [r.allocated_amount for r in result.increase_allocations] == [
        Decimal("0.00"),
        Decimal("0.00"),
    ]
    assert result.decrease_allocations == ()


def test_donors_with_no_recipients():
    result = allocate_campaign_reallocation(
        _ranking(reduce=[_ranked("D1", 1)]),
        (),
        (_decrease_limit("D1", "500.00"),),
    )
    assert result.increase_allocations == ()
    assert [r.allocated_amount for r in result.decrease_allocations] == [Decimal("0.00")]


def test_zero_capacity_recipient():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "0.00"),),
        (_decrease_limit("D1", "500.00"),),
    )
    assert result.increase_allocations[0].allocated_amount == Decimal("0.00")
    assert result.decrease_allocations[0].allocated_amount == Decimal("0.00")


def test_zero_capacity_donor():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "500.00"),),
        (_decrease_limit("D1", "0.00"),),
    )
    assert result.increase_allocations[0].allocated_amount == Decimal("0.00")
    assert result.decrease_allocations[0].allocated_amount == Decimal("0.00")


def test_all_zero_capacities():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)]),
        (_increase_limit("R1", "0.00"),),
        (_decrease_limit("D1", "0.00"),),
    )
    assert result.increase_allocations[0].allocated_amount == Decimal("0.00")
    assert result.decrease_allocations[0].allocated_amount == Decimal("0.00")


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def test_authorised_fields_are_exactly_authorized():
    source = inspect.getsource(allocate_campaign_reallocation)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_names = [arg.arg for arg in func_def.args.args]
    assert param_names == ["ranking", "increase_limits", "decrease_limits"]

    attrs_by_name: dict[str, set[str]] = {
        "ranking": set(),
        "limit": set(),
        "ranked": set(),
    }
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "ranking":
                attrs_by_name["ranking"].add(node.attr)
            elif node.value.id == "limit":
                attrs_by_name["limit"].add(node.attr)
            elif node.value.id == "ranked":
                attrs_by_name["ranked"].add(node.attr)

    assert attrs_by_name["ranking"] == {"increase_rankings", "reduce_rankings"}
    assert attrs_by_name["ranked"] == {"campaign_id"}
    # "limit" attribute name is reused for both increase and decrease limit
    # comprehensions; confirm only the authorised field names ever appear.
    assert attrs_by_name["limit"] <= {
        "campaign_id",
        "raw_increase_limit",
        "effective_decrease_limit",
    }


def test_ranked_campaign_priority_score_never_read():
    import src.allocation as allocation_module

    source = inspect.getsource(allocation_module)
    tree = ast.parse(source)
    referenced_attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "reallocation_priority_score" not in referenced_attrs


def test_does_not_call_earlier_production_functions():
    import src.allocation as allocation_module

    source = inspect.getsource(allocation_module)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "rank_campaign_reallocation_priorities",
        "calculate_campaign_reallocation_priority_score",
        "resolve_campaign_recommendation_action",
        "resolve_campaign_recommendation_reason",
        "resolve_campaign_action_suitability",
        "resolve_campaign_action_availability",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_effective_decrease_limit",
        "assess_campaign_tracking",
        "classify_campaign_performance",
        "classify_campaign_trend",
        "classify_campaign_confidence",
        "calculate_campaign_metrics",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_module_does_not_reference_excluded_names():
    import src.allocation as allocation_module

    source = inspect.getsource(allocation_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    forbidden = {
        "ReviewSetup",
        "CampaignInput",
        "CampaignRecommendation",
        "CampaignRecommendationReason",
        "ReasonCode",
        "CampaignActionAvailability",
        "CampaignActionSuitability",
        "CampaignPerformanceClass",
        "CampaignTrendClass",
        "CampaignPacingClass",
        "CampaignConfidenceClass",
        "CampaignTrackingAssessment",
        "current_budget",
        "initial_account_reserve",
        "approved_monthly_budget",
        "final_budget",
        "conservation",
        "NO_ELIGIBLE_RECIPIENT",
        "ACCOUNT_RESERVE_REQUIRED",
        "confidence_component",
        "business_priority_component",
        "reason_codes",
        "performance_band",
        "trend_direction",
        "pacing_status",
    }
    assert referenced.isdisjoint(forbidden)


def test_module_does_not_import_excluded_types():
    import src.allocation as allocation_module

    for forbidden_name in (
        "ReviewSetup",
        "CampaignInput",
        "CampaignRecommendation",
        "CampaignRecommendationReason",
        "ReasonCode",
        "CampaignActionAvailability",
        "CampaignActionSuitability",
        "CampaignPerformanceClass",
        "CampaignTrendClass",
        "CampaignPacingClass",
        "CampaignConfidenceClass",
        "CampaignTrackingAssessment",
    ):
        assert not hasattr(allocation_module, forbidden_name)


def test_no_input_mutation():
    ranking = _ranking(increase=[_ranked("R1", 1)], reduce=[_ranked("D1", 1)])
    increase_limits = (_increase_limit("R1", "100.00"),)
    decrease_limits = (_decrease_limit("D1", "50.00"),)
    allocate_campaign_reallocation(ranking, increase_limits, decrease_limits)
    assert ranking.increase_rankings[0].campaign_id == "R1"
    assert increase_limits[0].raw_increase_limit == Decimal("100.00")
    assert decrease_limits[0].effective_decrease_limit == Decimal("50.00")


def test_no_reason_code_reference_in_module():
    import src.allocation as allocation_module

    source = inspect.getsource(allocation_module)
    tree = ast.parse(source)
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "ReasonCode" not in referenced_names


def test_no_conservation_implementation():
    import src.allocation as allocation_module

    assert not hasattr(allocation_module, "verify_conservation")
    assert not hasattr(allocation_module, "check_conservation")


def test_no_final_budget_computation():
    import src.allocation as allocation_module

    assert not hasattr(allocation_module, "calculate_final_campaign_budget")
    source = inspect.getsource(allocation_module)
    tree = ast.parse(source)
    referenced_attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "current_budget" not in referenced_attrs


def test_output_order_preserves_stage_24_ranking_order():
    result = allocate_campaign_reallocation(
        _ranking(increase=[_ranked("Z", 1), _ranked("A", 2)]),
        (_increase_limit("Z", "100.00"), _increase_limit("A", "50.00")),
        (),
    )
    assert [r.campaign_id for r in result.increase_allocations] == ["Z", "A"]


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_campaigns_csv_allocation_exact_result():
    from datetime import date

    from src.classification import (
        assess_campaign_tracking,
        classify_campaign_performance,
        classify_campaign_trend,
    )
    from src.constraints import (
        calculate_campaign_raw_percentage_movement_cap,
        calculate_campaign_static_budget_room,
        calculate_campaign_test_floor_room,
        resolve_campaign_applicable_change_percentage,
        resolve_campaign_effective_decrease_limit,
        resolve_campaign_protection_constraint,
        resolve_campaign_raw_decrease_limit,
        resolve_campaign_raw_increase_limit,
        resolve_campaign_test_aware_static_decrease_room,
    )
    from src.availability import resolve_campaign_action_availability
    from src.metrics import calculate_campaign_metrics
    from src.models import ReviewSetup
    from src.ranking import rank_campaign_reallocation_priorities
    from src.recommendation import resolve_campaign_recommendation_action
    from src.scoring import calculate_campaign_reallocation_priority_score
    from src.classification import classify_campaign_confidence
    from src.suitability import resolve_campaign_action_suitability
    from src.validation import validate_campaign_csv

    review = ReviewSetup(
        review_id="REV-1",
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
        reviewer_name="Reviewer",
        approved_monthly_budget=Decimal("10000.00"),
        initial_account_reserve=Decimal("0.00"),
        default_max_change_percentage=Decimal("0.20"),
    )
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True

    recommendations = []
    increase_limits = []
    decrease_limits = []
    scores = []
    for campaign in report.valid_campaigns:
        metrics = calculate_campaign_metrics(campaign)
        performance = classify_campaign_performance(metrics)
        trend = classify_campaign_trend(metrics)
        confidence = classify_campaign_confidence(campaign)
        static_room = calculate_campaign_static_budget_room(campaign)
        percentage = resolve_campaign_applicable_change_percentage(review, campaign)
        raw_cap = calculate_campaign_raw_percentage_movement_cap(campaign, percentage)
        test_floor_room = calculate_campaign_test_floor_room(campaign)
        decrease_room = resolve_campaign_test_aware_static_decrease_room(
            static_room, test_floor_room
        )
        protection = resolve_campaign_protection_constraint(campaign)
        raw_increase = resolve_campaign_raw_increase_limit(static_room, raw_cap)
        raw_decrease = resolve_campaign_raw_decrease_limit(decrease_room, raw_cap)
        effective_decrease = resolve_campaign_effective_decrease_limit(raw_decrease, protection)
        tracking = assess_campaign_tracking(campaign)
        availability = resolve_campaign_action_availability(
            campaign, tracking, raw_increase, effective_decrease
        )
        suitability = resolve_campaign_action_suitability(performance, trend, availability)
        recommendation = resolve_campaign_recommendation_action(campaign, suitability, tracking)
        score = calculate_campaign_reallocation_priority_score(recommendation, campaign, confidence)
        recommendations.append(recommendation)
        scores.append(score)
        increase_limits.append(raw_increase)
        decrease_limits.append(effective_decrease)

    ranking = rank_campaign_reallocation_priorities(tuple(recommendations), tuple(scores))
    result = allocate_campaign_reallocation(
        ranking, tuple(increase_limits), tuple(decrease_limits)
    )

    assert result == CampaignReallocationAllocation(
        increase_allocations=(
            CampaignAllocatedAmount(campaign_id="G002", allocated_amount=Decimal("0.00")),
        ),
        decrease_allocations=(),
    )
