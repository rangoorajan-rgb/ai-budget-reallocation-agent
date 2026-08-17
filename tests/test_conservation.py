"""Tests for src.conservation (Sprint 1 — Development Stage 26).

Covers CampaignReallocationConservation construction, immutability,
non-negative-total/signed-net_change validation, and model-level
consistency enforcement (net_change == total_increase - total_decrease;
is_conserved == (net_change == 0.00)); the exact conservation equation and
sign convention; exact-equality-with-no-tolerance behavior; the
always-return-a-result (never raise on imbalance) policy; complete
indifference to duplicate/overlapping campaign IDs; every empty/zero
combination; Decimal-context correctness (including precision sufficient
for many large operands, immune to ambient global context mutation); and
isolation from every excluded field/type/function.
"""

import ast
import inspect
from decimal import Decimal, getcontext, localcontext

import pytest
from pydantic import ValidationError

from src.allocation import CampaignAllocatedAmount, CampaignReallocationAllocation
from src.conservation import (
    CampaignReallocationConservation,
    verify_campaign_reallocation_conservation,
)


def _amount(campaign_id: str, amount: str) -> CampaignAllocatedAmount:
    return CampaignAllocatedAmount(campaign_id=campaign_id, allocated_amount=Decimal(amount))


def _allocation(increase=(), decrease=()) -> CampaignReallocationAllocation:
    return CampaignReallocationAllocation(
        increase_allocations=tuple(increase), decrease_allocations=tuple(decrease)
    )


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def test_result_field_shape():
    assert set(CampaignReallocationConservation.model_fields.keys()) == {
        "total_increase_allocated",
        "total_decrease_allocated",
        "net_change",
        "is_conserved",
    }


def test_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CampaignReallocationConservation(
            total_increase_allocated=Decimal("0.00"),
            total_decrease_allocated=Decimal("0.00"),
            net_change=Decimal("0.00"),
            is_conserved=True,
            extra="x",
        )


def test_is_immutable():
    result = verify_campaign_reallocation_conservation(_allocation())
    with pytest.raises(ValidationError):
        result.is_conserved = False


def test_totals_are_non_negative():
    with pytest.raises(ValidationError):
        CampaignReallocationConservation(
            total_increase_allocated=Decimal("-0.01"),
            total_decrease_allocated=Decimal("0.00"),
            net_change=Decimal("-0.01"),
            is_conserved=False,
        )
    with pytest.raises(ValidationError):
        CampaignReallocationConservation(
            total_increase_allocated=Decimal("0.00"),
            total_decrease_allocated=Decimal("-0.01"),
            net_change=Decimal("0.01"),
            is_conserved=False,
        )


def test_net_change_may_be_negative():
    result = CampaignReallocationConservation(
        total_increase_allocated=Decimal("10.00"),
        total_decrease_allocated=Decimal("20.00"),
        net_change=Decimal("-10.00"),
        is_conserved=False,
    )
    assert result.net_change == Decimal("-10.00")


def test_is_conserved_is_plain_bool():
    result = verify_campaign_reallocation_conservation(_allocation())
    assert type(result.is_conserved) is bool


def test_serialization():
    result = verify_campaign_reallocation_conservation(_allocation())
    dumped = result.model_dump()
    assert dumped == {
        "total_increase_allocated": Decimal("0.00"),
        "total_decrease_allocated": Decimal("0.00"),
        "net_change": Decimal("0.00"),
        "is_conserved": True,
    }


def test_rejects_inconsistent_net_change():
    with pytest.raises(ValidationError):
        CampaignReallocationConservation(
            total_increase_allocated=Decimal("100.00"),
            total_decrease_allocated=Decimal("50.00"),
            net_change=Decimal("49.00"),  # should be 50.00
            is_conserved=False,
        )


def test_rejects_inconsistent_is_conserved():
    with pytest.raises(ValidationError):
        CampaignReallocationConservation(
            total_increase_allocated=Decimal("100.00"),
            total_decrease_allocated=Decimal("100.00"),
            net_change=Decimal("0.00"),
            is_conserved=False,  # net_change is 0.00, must be True
        )
    with pytest.raises(ValidationError):
        CampaignReallocationConservation(
            total_increase_allocated=Decimal("100.00"),
            total_decrease_allocated=Decimal("50.00"),
            net_change=Decimal("50.00"),
            is_conserved=True,  # net_change is nonzero, must be False
        )


def test_direct_construction_balanced_consistent_succeeds():
    result = CampaignReallocationConservation(
        total_increase_allocated=Decimal("75.00"),
        total_decrease_allocated=Decimal("75.00"),
        net_change=Decimal("0.00"),
        is_conserved=True,
    )
    assert result.is_conserved is True


def test_direct_construction_imbalanced_consistent_succeeds():
    result = CampaignReallocationConservation(
        total_increase_allocated=Decimal("75.01"),
        total_decrease_allocated=Decimal("75.00"),
        net_change=Decimal("0.01"),
        is_conserved=False,
    )
    assert result.is_conserved is False
    assert result.net_change == Decimal("0.01")


def test_result_contains_no_forbidden_field():
    fields = set(CampaignReallocationConservation.model_fields.keys())
    forbidden = {
        "campaign_count",
        "campaign_id",
        "campaign_ids",
        "allocation_records",
        "reserve",
        "reserve_used",
        "capacity",
        "final_budget",
        "message",
        "issues",
        "reason_codes",
        "tolerance",
    }
    assert fields.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Balanced cases
# ---------------------------------------------------------------------------


def test_empty_allocation_is_conserved():
    result = verify_campaign_reallocation_conservation(_allocation())
    assert result.total_increase_allocated == Decimal("0.00")
    assert result.total_decrease_allocated == Decimal("0.00")
    assert result.net_change == Decimal("0.00")
    assert result.is_conserved is True


def test_all_zero_allocation_is_conserved():
    result = verify_campaign_reallocation_conservation(
        _allocation(
            increase=[_amount("R1", "0.00"), _amount("R2", "0.00")],
            decrease=[_amount("D1", "0.00")],
        )
    )
    assert result.is_conserved is True
    assert result.net_change == Decimal("0.00")


def test_one_side_empty_other_zero_valued_is_conserved():
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", "0.00")], decrease=[])
    )
    assert result.is_conserved is True


def test_one_equal_record_per_direction():
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", "500.00")], decrease=[_amount("D1", "500.00")])
    )
    assert result.is_conserved is True
    assert result.net_change == Decimal("0.00")


def test_multiple_records_per_direction():
    result = verify_campaign_reallocation_conservation(
        _allocation(
            increase=[_amount("R1", "100.00"), _amount("R2", "50.00")],
            decrease=[_amount("D1", "80.00"), _amount("D2", "70.00")],
        )
    )
    assert result.total_increase_allocated == Decimal("150.00")
    assert result.total_decrease_allocated == Decimal("150.00")
    assert result.is_conserved is True


def test_different_record_counts_equal_totals():
    result = verify_campaign_reallocation_conservation(
        _allocation(
            increase=[_amount("R1", "60.00"), _amount("R2", "40.00"), _amount("R3", "20.00")],
            decrease=[_amount("D1", "120.00")],
        )
    )
    assert result.total_increase_allocated == Decimal("120.00")
    assert result.total_decrease_allocated == Decimal("120.00")
    assert result.is_conserved is True


def test_extreme_equal_totals():
    huge = "99999999999999999999999999.99"
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", huge)], decrease=[_amount("D1", huge)])
    )
    assert result.is_conserved is True
    assert result.net_change == Decimal("0.00")


def test_duplicated_ids_with_balanced_totals():
    result = verify_campaign_reallocation_conservation(
        _allocation(
            increase=[_amount("SAME", "50.00"), _amount("SAME", "50.00")],
            decrease=[_amount("D1", "100.00")],
        )
    )
    assert result.total_increase_allocated == Decimal("100.00")
    assert result.is_conserved is True


def test_overlapping_ids_across_directions_with_balanced_totals():
    result = verify_campaign_reallocation_conservation(
        _allocation(
            increase=[_amount("X", "40.00")],
            decrease=[_amount("X", "40.00")],
        )
    )
    assert result.is_conserved is True


# ---------------------------------------------------------------------------
# Imbalanced cases
# ---------------------------------------------------------------------------


def test_increase_exceeds_decrease_by_one_penny():
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", "100.01")], decrease=[_amount("D1", "100.00")])
    )
    assert result.is_conserved is False
    assert result.net_change == Decimal("0.01")


def test_decrease_exceeds_increase_by_one_penny():
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", "100.00")], decrease=[_amount("D1", "100.01")])
    )
    assert result.is_conserved is False
    assert result.net_change == Decimal("-0.01")


def test_larger_positive_imbalance():
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", "500.00")], decrease=[_amount("D1", "125.50")])
    )
    assert result.is_conserved is False
    assert result.net_change == Decimal("374.50")


def test_larger_negative_imbalance():
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", "125.50")], decrease=[_amount("D1", "500.00")])
    )
    assert result.is_conserved is False
    assert result.net_change == Decimal("-374.50")


def test_one_positive_side_one_empty_side():
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", "10.00")], decrease=[])
    )
    assert result.is_conserved is False
    assert result.net_change == Decimal("10.00")

    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[], decrease=[_amount("D1", "10.00")])
    )
    assert result.is_conserved is False
    assert result.net_change == Decimal("-10.00")


def test_no_exception_raised_on_imbalance():
    try:
        result = verify_campaign_reallocation_conservation(
            _allocation(increase=[_amount("R1", "999.99")], decrease=[_amount("D1", "1.00")])
        )
    except Exception as exc:  # noqa: BLE001 - explicit confirmation no exception is raised
        pytest.fail(f"Imbalance raised an unexpected exception: {exc!r}")
    assert result.is_conserved is False


def test_no_repair_or_mutation_on_imbalance():
    increase_records = (_amount("R1", "999.99"),)
    decrease_records = (_amount("D1", "1.00"),)
    allocation = _allocation(increase=increase_records, decrease=decrease_records)
    verify_campaign_reallocation_conservation(allocation)
    assert allocation.increase_allocations[0].allocated_amount == Decimal("999.99")
    assert allocation.decrease_allocations[0].allocated_amount == Decimal("1.00")
    assert len(allocation.increase_allocations) == 1
    assert len(allocation.decrease_allocations) == 1


# ---------------------------------------------------------------------------
# Decimal / context policy
# ---------------------------------------------------------------------------


def test_no_float_in_source():
    import src.conservation as conservation_module

    source = inspect.getsource(conservation_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "float" not in referenced


def test_mutated_ambient_precision_and_rounding_does_not_affect_output():
    allocation = _allocation(
        increase=[_amount("R1", "333.33"), _amount("R2", "333.33"), _amount("R3", "333.34")],
        decrease=[_amount("D1", "1000.00")],
    )

    baseline = verify_campaign_reallocation_conservation(allocation)

    original_prec = getcontext().prec
    original_rounding = getcontext().rounding
    try:
        getcontext().prec = 10
        getcontext().rounding = "ROUND_CEILING"
        mutated = verify_campaign_reallocation_conservation(allocation)
    finally:
        getcontext().prec = original_prec
        getcontext().rounding = original_rounding

    assert baseline.model_dump() == mutated.model_dump()
    assert getcontext().prec == original_prec
    assert getcontext().rounding == original_rounding


def test_many_large_operands_require_additional_carry_digits():
    # 100 operands each with 18 significant digits sum to a 20-digit total
    # (both comfortably under Currency's 28-significant-digit ceiling, but
    # the sum genuinely needs more digits than any single operand has).
    large_value = "1234567890123456.78"
    increase_records = tuple(_amount(f"R{i}", large_value) for i in range(100))
    decrease_records = tuple(_amount(f"D{i}", large_value) for i in range(100))
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=increase_records, decrease=decrease_records)
    )
    expected_total = (Decimal(large_value) * 100).quantize(Decimal("0.01"))
    assert len(expected_total.as_tuple().digits) > len(Decimal(large_value).as_tuple().digits)
    assert result.total_increase_allocated == expected_total
    assert result.total_decrease_allocated == expected_total
    assert result.is_conserved is True


def test_large_collection_insufficient_with_fixed_individual_precision():
    # Each operand alone needs fewer digits than the sum of many of them
    # requires (24-digit operands summing to a 26-digit total), while
    # staying under Currency's 28-significant-digit ceiling.
    operand = "1234567890123456789012.34"
    records = tuple(_amount(f"R{i}", operand) for i in range(500))
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=records, decrease=())
    )
    expected_total = (Decimal(operand) * 500).quantize(Decimal("0.01"))
    assert len(expected_total.as_tuple().digits) > len(Decimal(operand).as_tuple().digits)
    assert result.total_increase_allocated == expected_total
    assert result.is_conserved is False
    assert result.net_change == expected_total


def test_extreme_exponent_permitted_by_model():
    huge = "99999999999999999999999999.99"
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("R1", huge)], decrease=[])
    )
    assert result.total_increase_allocated == Decimal(huge)


def test_exact_one_penny_discrepancy_preserved_under_hostile_ambient_context():
    allocation = _allocation(
        increase=[_amount("R1", "100.01")], decrease=[_amount("D1", "100.00")]
    )
    original_prec = getcontext().prec
    original_rounding = getcontext().rounding
    try:
        getcontext().prec = 10
        getcontext().rounding = "ROUND_CEILING"
        result = verify_campaign_reallocation_conservation(allocation)
    finally:
        getcontext().prec = original_prec
        getcontext().rounding = original_rounding
    assert result.is_conserved is False
    assert result.net_change == Decimal("0.01")


def test_exact_decimal_zero_zero():
    result = verify_campaign_reallocation_conservation(_allocation())
    assert result.total_increase_allocated.as_tuple() == Decimal("0.00").as_tuple()
    assert result.total_decrease_allocated.as_tuple() == Decimal("0.00").as_tuple()
    assert result.net_change.as_tuple() == Decimal("0.00").as_tuple()


def test_no_local_context_rounding_hides_imbalance():
    # A one-penny imbalance between two otherwise-large-magnitude totals
    # must never be rounded away by insufficient local precision.
    result = verify_campaign_reallocation_conservation(
        _allocation(
            increase=[_amount("R1", "99999999999999999999999999.99")],
            decrease=[_amount("D1", "99999999999999999999999999.98")],
        )
    )
    assert result.is_conserved is False
    assert result.net_change == Decimal("0.01")


# ---------------------------------------------------------------------------
# Duplicate / overlap indifference
# ---------------------------------------------------------------------------


def test_no_identity_validation_duplicate_ids_within_direction():
    # No error is raised; sums proceed as normal.
    result = verify_campaign_reallocation_conservation(
        _allocation(
            increase=[_amount("SAME", "10.00"), _amount("SAME", "10.00"), _amount("SAME", "10.00")],
            decrease=[_amount("D1", "30.00")],
        )
    )
    assert result.is_conserved is True


def test_no_identity_validation_overlapping_ids_across_directions():
    result = verify_campaign_reallocation_conservation(
        _allocation(increase=[_amount("SAME", "5.00")], decrease=[_amount("SAME", "5.00")])
    )
    assert result.is_conserved is True


def test_no_identity_validation_repeated_zero_records():
    result = verify_campaign_reallocation_conservation(
        _allocation(
            increase=[_amount("R1", "0.00"), _amount("R1", "0.00"), _amount("R2", "0.00")],
            decrease=[],
        )
    )
    assert result.is_conserved is True


def test_module_never_reads_campaign_id():
    import src.conservation as conservation_module

    source = inspect.getsource(conservation_module)
    tree = ast.parse(source)
    referenced_attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "campaign_id" not in referenced_attrs


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def test_authorised_fields_are_exactly_authorized():
    source = inspect.getsource(verify_campaign_reallocation_conservation)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    param_names = [arg.arg for arg in func_def.args.args]
    assert param_names == ["allocation"]

    attrs_by_name: dict[str, set[str]] = {"allocation": set()}
    for node in ast.walk(func_def):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "allocation":
                attrs_by_name["allocation"].add(node.attr)

    assert attrs_by_name["allocation"] == {"increase_allocations", "decrease_allocations"}


def test_record_attribute_is_only_allocated_amount():
    import src.conservation as conservation_module

    source = inspect.getsource(conservation_module)
    tree = ast.parse(source)
    referenced_attrs = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "record"
    }
    assert referenced_attrs <= {"allocated_amount"}


def test_does_not_call_earlier_production_functions():
    import src.conservation as conservation_module

    source = inspect.getsource(conservation_module)
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    forbidden_calls = {
        "allocate_campaign_reallocation",
        "rank_campaign_reallocation_priorities",
        "calculate_campaign_reallocation_priority_score",
        "resolve_campaign_recommendation_action",
        "resolve_campaign_recommendation_reason",
        "resolve_campaign_raw_increase_limit",
        "resolve_campaign_effective_decrease_limit",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_module_does_not_reference_excluded_names():
    import src.conservation as conservation_module

    source = inspect.getsource(conservation_module)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    forbidden = {
        "ReviewSetup",
        "CampaignInput",
        "CampaignRecommendation",
        "CampaignRecommendationReason",
        "ReasonCode",
        "RankedCampaignPriority",
        "CampaignReallocationRanking",
        "CampaignRawIncreaseLimit",
        "CampaignEffectiveDecreaseLimit",
        "rank",
        "reallocation_priority_score",
        "recommendation_action",
        "initial_account_reserve",
        "approved_monthly_budget",
        "current_budget",
        "tolerance",
        "epsilon",
    }
    assert referenced.isdisjoint(forbidden)


def test_module_does_not_import_excluded_types():
    import src.conservation as conservation_module

    for forbidden_name in (
        "ReviewSetup",
        "CampaignInput",
        "CampaignRecommendation",
        "CampaignRecommendationReason",
        "ReasonCode",
        "RankedCampaignPriority",
        "CampaignReallocationRanking",
        "CampaignRawIncreaseLimit",
        "CampaignEffectiveDecreaseLimit",
    ):
        assert not hasattr(conservation_module, forbidden_name)


def test_no_allocation_reconstruction_or_repair():
    import src.conservation as conservation_module

    assert not hasattr(conservation_module, "repair_allocation")
    assert not hasattr(conservation_module, "rebalance_allocation")


def test_no_input_mutation():
    increase_records = (_amount("R1", "10.00"),)
    decrease_records = (_amount("D1", "10.00"),)
    allocation = _allocation(increase=increase_records, decrease=decrease_records)
    verify_campaign_reallocation_conservation(allocation)
    assert allocation.increase_allocations == increase_records
    assert allocation.decrease_allocations == decrease_records


def test_no_broad_exception_handling_in_source():
    source = inspect.getsource(verify_campaign_reallocation_conservation)
    assert "except" not in source


def test_no_production_batch_function():
    import src.conservation as conservation_module

    assert not hasattr(conservation_module, "verify_campaign_reallocation_conservations")


# ---------------------------------------------------------------------------
# Sample-data integration
# ---------------------------------------------------------------------------


def test_sample_stage_25_result_conservation():
    allocation = CampaignReallocationAllocation(
        increase_allocations=(
            CampaignAllocatedAmount(campaign_id="G002", allocated_amount=Decimal("0.00")),
        ),
        decrease_allocations=(),
    )
    result = verify_campaign_reallocation_conservation(allocation)
    assert result == CampaignReallocationConservation(
        total_increase_allocated=Decimal("0.00"),
        total_decrease_allocated=Decimal("0.00"),
        net_change=Decimal("0.00"),
        is_conserved=True,
    )
    # Explicit confirmation: conserved zero does not mean G002 was funded.
    assert result.total_increase_allocated == Decimal("0.00")
