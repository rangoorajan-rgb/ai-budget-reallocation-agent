"""Deterministic per-campaign recommendation-action selection.

Implements Sprint 1 — Development Stage 21: for one already-validated
`CampaignInput`, one already-calculated `CampaignActionSuitability` (Stage 20),
and one already-calculated `CampaignTrackingAssessment` (Stage 8), selects
exactly one `RecommendationAction` — `INCREASE`, `MAINTAIN`, `REDUCE`, or
`HOLD` — per campaign.

`MAINTAIN` means the campaign was eligible for automated assessment, no
available action had a uniquely stronger directional suitability, and keeping
the budget unchanged is the selected recommendation. `HOLD` means the engine
must not make an automated directional budget recommendation for this review
— because the campaign is paused, its tracking is unassessable, its
suitability input is ambiguous, or no valid fallback action is available.
`HOLD` is a review/deferral outcome; `MAINTAIN` is an assessed no-change
recommendation.

Exact ordered policy, applied after campaign-ID validation:

1. **Paused override.** `campaign.status is CampaignStatus.PAUSED` →
   `HOLD`, overriding all suitability values. Read directly from
   `CampaignInput.status` — never inferred from suitability shape.
2. **Tracking-assessability override.** `not tracking.is_assessable` →
   `HOLD`, overriding all suitability values. `TrackingStatus.WARNING`
   remains assessable because Stage 8 already maps it to
   `is_assessable=True` — only `is_assessable` is read, never
   `tracking_status`.
3. **Unique-SUITABLE selection.** Exactly one of
   `increase_suitability`/`maintain_suitability`/`reduce_suitability` equals
   `Suitability.SUITABLE` → select the corresponding action.
4. **Multiple-SUITABLE ambiguity.** More than one field equals `SUITABLE`
   → `HOLD`. No fixed precedence, no first-field selection, no MAINTAIN
   default, no error, and no dependence on enum declaration order — although
   this cannot arise through the approved Stage 20 production table, a
   directly constructed `CampaignActionSuitability` could contain it, and
   `HOLD` is the approved deterministic ambiguity outcome.
5. **Conservative MAINTAIN fallback.** No field is `SUITABLE`, and
   `maintain_suitability is Suitability.NEUTRAL` → `MAINTAIN`. `INCREASE`'s
   and `REDUCE`'s own values are irrelevant to this fallback — they may be
   `NEUTRAL`, `UNSUITABLE`, or `NOT_APPLICABLE`.
6. **Final HOLD fallback.** No field is `SUITABLE`, and
   `maintain_suitability` is `UNSUITABLE` or `NOT_APPLICABLE` → `HOLD`.
   `MAINTAIN` is never selected when it is itself explicitly unavailable or
   unsuitable.

A `Suitability.NOT_APPLICABLE` value is never selected as an action — it
participates only by preventing that direction from being uniquely
`SUITABLE`. Stage 21 does not produce `ReasonCode`, calculate monetary
movement, score or rank campaigns, apply `BusinessPriority`, or use pacing or
confidence — `CampaignConfidenceClass`, `Confidence`, `CampaignPacingClass`,
`PacingStatus`, `BusinessPriority`, and `CampaignActionAvailability` are never
read or imported. It reads only `campaign.campaign_id`/`campaign.status`,
`suitability.campaign_id`/`increase_suitability`/`maintain_suitability`/
`reduce_suitability`, and `tracking.campaign_id`/`is_assessable` — never
`is_protected`, `decrease_blocked`, `is_test_campaign`, `test_budget_floor`,
or `tracking_status`; those effects are already fully absorbed upstream into
availability and suitability. It never calls `assess_campaign_tracking`,
`resolve_campaign_action_suitability`, `resolve_campaign_action_availability`,
or any other Stage 1–20 production function. It requires all three
`campaign_id` values to match, raising `ValueError` otherwise. No `Decimal`
calculation occurs anywhere in this module.
"""

from pydantic import BaseModel, ConfigDict

from src.classification import CampaignTrackingAssessment
from src.constants import CampaignStatus, RecommendationAction
from src.models import CampaignInput
from src.suitability import CampaignActionSuitability, Suitability


class CampaignRecommendation(BaseModel):
    """The selected, provisional `RecommendationAction` for one campaign.

    Not a `ReasonCode`, a monetary amount, a score, a rank, a priority, or a
    final allocated movement.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str
    recommendation_action: RecommendationAction


def resolve_campaign_recommendation_action(
    campaign: CampaignInput,
    suitability: CampaignActionSuitability,
    tracking: CampaignTrackingAssessment,
) -> CampaignRecommendation:
    """Select one campaign's `RecommendationAction` from its status, Stage 20
    suitability, and Stage 8 tracking assessability.

    Applies, in order: a Paused override, a tracking-assessability override,
    unique-SUITABLE selection, multiple-SUITABLE ambiguity resolution (always
    `HOLD`), a conservative `MAINTAIN` fallback when `maintain_suitability`
    is `NEUTRAL`, and a final `HOLD` fallback otherwise. Requires
    `campaign.campaign_id == suitability.campaign_id ==
    tracking.campaign_id`, raising `ValueError` otherwise.
    """
    if not (
        suitability.campaign_id == campaign.campaign_id
        and tracking.campaign_id == campaign.campaign_id
    ):
        raise ValueError(
            "Campaign IDs must match when resolving recommendation action."
        )

    if campaign.status is CampaignStatus.PAUSED:
        recommendation_action = RecommendationAction.HOLD
    elif not tracking.is_assessable:
        recommendation_action = RecommendationAction.HOLD
    else:
        suitable_count = sum(
            1
            for value in (
                suitability.increase_suitability,
                suitability.maintain_suitability,
                suitability.reduce_suitability,
            )
            if value is Suitability.SUITABLE
        )

        if suitable_count == 1:
            if suitability.increase_suitability is Suitability.SUITABLE:
                recommendation_action = RecommendationAction.INCREASE
            elif suitability.maintain_suitability is Suitability.SUITABLE:
                recommendation_action = RecommendationAction.MAINTAIN
            else:
                recommendation_action = RecommendationAction.REDUCE
        elif suitable_count > 1:
            recommendation_action = RecommendationAction.HOLD
        elif suitability.maintain_suitability is Suitability.NEUTRAL:
            recommendation_action = RecommendationAction.MAINTAIN
        else:
            recommendation_action = RecommendationAction.HOLD

    return CampaignRecommendation(
        campaign_id=campaign.campaign_id,
        recommendation_action=recommendation_action,
    )
