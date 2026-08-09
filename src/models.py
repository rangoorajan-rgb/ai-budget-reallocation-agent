"""Core Pydantic input models for the AI Budget Reallocation Agent.

This module defines exactly two input-facing data shapes: the review setup entered by a
human reviewer (`ReviewSetup`) and one campaign record per row of the uploaded CSV
(`CampaignInput`). It enforces safe, model-level type and structural rules — blank checks,
currency quantisation, non-negative/positive bounds, min/max ordering, and conventional
boolean parsing — and nothing more. Business rules such as pacing, classification
thresholds, constraints, scoring, and allocation are deliberately out of scope here and are
implemented in later modules, using the frozen constants in `src.constants`.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from src.constants import (
    BusinessPriority,
    CampaignStatus,
    CURRENCY_QUANTUM,
    DEFAULT_MAX_CHANGE_PERCENTAGE,
    KPIType,
    Platform,
    TrackingStatus,
)


def _quantize_currency(value: Decimal) -> Decimal:
    """Round a currency amount to CURRENCY_QUANTUM (0.01) using ROUND_HALF_UP."""
    return value.quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)


Currency = Annotated[Decimal, AfterValidator(_quantize_currency)]
"""A monetary Decimal, always quantised to two decimal places via ROUND_HALF_UP."""


_TRUE_STRINGS = {"true", "yes", "1"}
_FALSE_STRINGS = {"false", "no", "0"}


def _parse_conventional_bool(value: object) -> object:
    """Accept only bool, 1/0, or case-insensitive true/false, yes/no, 1/0 strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
        raise ValueError(f"ambiguous boolean value: {value!r}")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_STRINGS:
            return True
        if normalized in _FALSE_STRINGS:
            return False
        raise ValueError(f"ambiguous boolean value: {value!r}")
    raise ValueError(f"ambiguous boolean value: {value!r}")


ConventionalBool = Annotated[bool, BeforeValidator(_parse_conventional_bool)]
"""A bool accepting only literal bools, 1/0, or case-insensitive true/false, yes/no."""


class ReviewSetup(BaseModel):
    """The reviewer-entered parameters that scope a single budget-reallocation review."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    review_id: str = Field(min_length=1)
    review_date: date
    period_start: date
    period_end: date
    reviewer_name: str = Field(min_length=1)
    approved_monthly_budget: Currency = Field(gt=0)
    initial_account_reserve: Currency = Field(ge=0)
    default_max_change_percentage: Decimal = Field(
        default=DEFAULT_MAX_CHANGE_PERCENTAGE, gt=0, le=1
    )
    review_notes: str | None = None

    @model_validator(mode="after")
    def _check_period_order(self) -> "ReviewSetup":
        if self.period_end < self.period_start:
            raise ValueError("period_end must not be before period_start")
        return self

    @model_validator(mode="after")
    def _check_reserve_within_budget(self) -> "ReviewSetup":
        if self.initial_account_reserve > self.approved_monthly_budget:
            raise ValueError(
                "initial_account_reserve must not exceed approved_monthly_budget"
            )
        return self


class CampaignInput(BaseModel):
    """One campaign's raw performance and configuration data, as read from the uploaded CSV."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    campaign_id: str = Field(min_length=1)
    campaign_name: str = Field(min_length=1)
    platform: Platform
    status: CampaignStatus
    kpi_type: KPIType
    kpi_target: Decimal = Field(gt=0)
    current_budget: Currency = Field(ge=0)
    minimum_budget: Currency = Field(ge=0)
    maximum_budget: Currency = Field(ge=0)
    spend_to_date: Currency = Field(ge=0)
    conversions_7d: int = Field(ge=0)
    conversions_28d: int = Field(ge=0)
    kpi_actual_7d: Decimal = Field(gt=0)
    kpi_actual_28d: Decimal = Field(gt=0)
    tracking_status: TrackingStatus
    business_priority: BusinessPriority
    is_protected: ConventionalBool = False
    is_test_campaign: ConventionalBool = False
    test_budget_floor: Currency | None = Field(default=None, ge=0)
    campaign_max_change_percentage: Decimal | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def _check_budget_bounds(self) -> "CampaignInput":
        if self.maximum_budget < self.minimum_budget:
            raise ValueError("maximum_budget must not be less than minimum_budget")
        if not (self.minimum_budget <= self.current_budget <= self.maximum_budget):
            raise ValueError(
                "current_budget must be between minimum_budget and maximum_budget"
            )
        if self.spend_to_date > self.current_budget:
            raise ValueError("spend_to_date must not exceed current_budget")
        return self

    @model_validator(mode="after")
    def _check_conversion_ordering(self) -> "CampaignInput":
        if self.conversions_7d > self.conversions_28d:
            raise ValueError("conversions_7d must not exceed conversions_28d")
        return self

    @model_validator(mode="after")
    def _check_test_budget_floor(self) -> "CampaignInput":
        if self.is_test_campaign and self.test_budget_floor is None:
            raise ValueError("is_test_campaign requires test_budget_floor to be set")
        if not self.is_test_campaign and self.test_budget_floor is not None:
            raise ValueError("test_budget_floor must be None when is_test_campaign is False")
        if self.test_budget_floor is not None and self.test_budget_floor > self.current_budget:
            raise ValueError("test_budget_floor must not exceed current_budget")
        return self
