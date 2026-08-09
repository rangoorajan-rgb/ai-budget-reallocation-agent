"""Frozen enumerations and numerical constants shared across the AI Budget Reallocation Agent.

All enumerations are string-based (`str, Enum`) so that members serialize to stable,
CSV-friendly values that round-trip cleanly through pandas/CSV without extra encoding.
The numerical constants below are frozen threshold/weight values reserved for use by
later Sprint 1 stages (pacing, classification, scoring, allocation, conservation). This
module defines controlled vocabularies and named constants only — it must not contain
calculation or decision logic itself. That is implemented in `classification.py`,
`constraints.py`, `scoring.py`, and related modules in a later stage.
"""

from decimal import Decimal
from enum import Enum


class Platform(str, Enum):
    """Advertising platform a campaign runs on."""

    GOOGLE_ADS = "Google Ads"
    META_ADS = "Meta Ads"


class KPIType(str, Enum):
    """The performance objective a campaign is measured against."""

    CPA = "CPA"
    ROAS = "ROAS"


class CampaignStatus(str, Enum):
    """Current operational status of a campaign on its platform."""

    ACTIVE = "Active"
    PAUSED = "Paused"


class TrackingStatus(str, Enum):
    """Reliability of a campaign's conversion tracking data."""

    HEALTHY = "Healthy"
    WARNING = "Warning"
    UNRELIABLE = "Unreliable"


class BusinessPriority(str, Enum):
    """Business importance assigned to a campaign by the reviewer."""

    STANDARD = "Standard"
    MEDIUM = "Medium"
    HIGH = "High"


class RecommendationAction(str, Enum):
    """Direction of a proposed budget change for a campaign."""

    INCREASE = "INCREASE"
    MAINTAIN = "MAINTAIN"
    REDUCE = "REDUCE"
    HOLD = "HOLD"


class Confidence(str, Enum):
    """Confidence level attached to a recommendation."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class ReviewStatus(str, Enum):
    """Lifecycle status of a budget review."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ValidationSeverity(str, Enum):
    """Severity of a data validation issue."""

    ERROR = "ERROR"
    WARNING = "WARNING"


class ReasonCode(str, Enum):
    """Stable, traceable reason codes explaining a recommendation or constraint outcome."""

    ABOVE_TARGET_STRONG = "ABOVE_TARGET_STRONG"
    BELOW_TARGET_MODERATE = "BELOW_TARGET_MODERATE"
    BELOW_TARGET_SEVERE = "BELOW_TARGET_SEVERE"
    NEAR_TARGET = "NEAR_TARGET"
    RECENT_TREND_IMPROVING = "RECENT_TREND_IMPROVING"
    RECENT_TREND_STABLE = "RECENT_TREND_STABLE"
    RECENT_TREND_DECLINING = "RECENT_TREND_DECLINING"
    INSUFFICIENT_CONVERSION_VOLUME = "INSUFFICIENT_CONVERSION_VOLUME"
    TRACKING_UNRELIABLE = "TRACKING_UNRELIABLE"
    TRACKING_WARNING = "TRACKING_WARNING"
    PROTECTED_FROM_REDUCTION = "PROTECTED_FROM_REDUCTION"
    TEST_BUDGET_FLOOR_APPLIED = "TEST_BUDGET_FLOOR_APPLIED"
    MAX_CHANGE_LIMIT_APPLIED = "MAX_CHANGE_LIMIT_APPLIED"
    CAMPAIGN_CAP_REACHED = "CAMPAIGN_CAP_REACHED"
    CAMPAIGN_FLOOR_REACHED = "CAMPAIGN_FLOOR_REACHED"
    PAUSED_CAMPAIGN = "PAUSED_CAMPAIGN"
    NO_ELIGIBLE_RECIPIENT = "NO_ELIGIBLE_RECIPIENT"
    HELD_FOR_MANUAL_REVIEW = "HELD_FOR_MANUAL_REVIEW"
    STRONG_LONG_TERM_RECENT_DECLINE = "STRONG_LONG_TERM_RECENT_DECLINE"
    ACCOUNT_RESERVE_REQUIRED = "ACCOUNT_RESERVE_REQUIRED"


# ---------------------------------------------------------------------------
# Frozen numerical constants
#
# Reserved for use by later Sprint 1 stages (pacing, classification, scoring,
# allocation, conservation). No calculation or decision logic is implemented here.
# ---------------------------------------------------------------------------

DEFAULT_MAX_CHANGE_PERCENTAGE = Decimal("0.20")
TREND_THRESHOLD = Decimal("0.10")
SEVEN_DAY_WEIGHT = Decimal("0.40")
TWENTY_EIGHT_DAY_WEIGHT = Decimal("0.60")
INCREASE_THRESHOLD = Decimal("1.15")
MAINTAIN_THRESHOLD = Decimal("0.90")
MINIMUM_CONVERSIONS = 10
HIGH_CONFIDENCE_CONVERSIONS = 30
CURRENCY_QUANTUM = Decimal("0.01")
