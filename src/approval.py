"""Human approval/rejection workflow for budget-reallocation recommendations.

Implements Sprint 3 — Development Stage 33: one accountable human decision
— approve or reject — applied to the complete locked
`BudgetReallocationReviewResult`, never a per-campaign or partial-portfolio
decision. Conservation is a whole-portfolio invariant, so only a
whole-review decision preserves its meaning.

**Reuses the existing Stage 1 `ReviewStatus` enum** rather than inventing a
new one. `CampaignReallocationApproval.decision` is typed `ReviewStatus`,
but a model validator permits only `ReviewStatus.APPROVED` or
`ReviewStatus.REJECTED` — direct construction with `DRAFT` or
`PENDING_APPROVAL` fails through normal Pydantic validation.

**Conservation policy.** `approve_campaign_reallocation_review` refuses an
unconserved result outright — it is fail-fast domain validation, not a
soft warning: certifying a mathematically broken allocation as approved
would contradict the deterministic-authority guarantee this project
enforces everywhere else. `reject_campaign_reallocation_review` places no
such restriction — a human may reject a result regardless of its
conservation status. Neither function repairs, rebalances, or reruns
anything.

**No Gemini, configuration, audit, or export coupling.** This module
never imports `config`, `src.explanations`, `src.gemini_analyzer`,
`src.audit`, or `src.exports`, and never performs filesystem, database, or
network I/O. An explanation's existence, status, or content is never
inspected — approval works identically whether Gemini is unconfigured,
unavailable, failed, or never invoked at all.

**No hidden wall-clock call.** Stage 33 records no timestamp; that
responsibility belongs to the later audit stage, which is also the only
component that persists anything — this module returns a value, it never
writes to disk. `review_id` is always derived from the locked result
itself, never from a separate, independently-suppliable parameter, so
there is no possibility of a review-ID mismatch to guard against here.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.constants import ReviewStatus
from src.pipeline import BudgetReallocationReviewResult

_VALID_DECISIONS = (ReviewStatus.APPROVED, ReviewStatus.REJECTED)


class CampaignReallocationApproval(BaseModel):
    """One accountable human decision on one complete locked review.

    Not a wrapper around the locked result — it references one by
    `review_id` only, never embedding or duplicating it. Not an audit
    record, a timestamp, a version, or an explanation reference.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    review_id: str = Field(min_length=1)
    decision: ReviewStatus
    reviewer_name: str = Field(min_length=1)
    note: str | None = None

    @field_validator("decision")
    @classmethod
    def _validate_decision(cls, value: ReviewStatus) -> ReviewStatus:
        if value not in _VALID_DECISIONS:
            raise ValueError("decision must be ReviewStatus.APPROVED or ReviewStatus.REJECTED")
        return value

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value or None


def approve_campaign_reallocation_review(
    result: BudgetReallocationReviewResult,
    reviewer_name: str,
    *,
    note: str | None = None,
) -> CampaignReallocationApproval:
    """Approve one complete locked review.

    Raises `ValueError("Reviewer name must not be blank.")` for a
    blank/whitespace-only name, and
    `ValueError("An unconserved allocation cannot be approved.")` when
    `result.conservation.is_conserved` is `False` — no approval object is
    returned in either case. Never mutates or reconstructs `result`.
    """
    if not reviewer_name.strip():
        raise ValueError("Reviewer name must not be blank.")
    if not result.conservation.is_conserved:
        raise ValueError("An unconserved allocation cannot be approved.")
    return CampaignReallocationApproval(
        review_id=result.review_id,
        decision=ReviewStatus.APPROVED,
        reviewer_name=reviewer_name,
        note=note,
    )


def reject_campaign_reallocation_review(
    result: BudgetReallocationReviewResult,
    reviewer_name: str,
    *,
    note: str | None = None,
) -> CampaignReallocationApproval:
    """Reject one complete locked review — conserved or not.

    Raises `ValueError("Reviewer name must not be blank.")` for a
    blank/whitespace-only name. Never mutates or reconstructs `result`.
    """
    if not reviewer_name.strip():
        raise ValueError("Reviewer name must not be blank.")
    return CampaignReallocationApproval(
        review_id=result.review_id,
        decision=ReviewStatus.REJECTED,
        reviewer_name=reviewer_name,
        note=note,
    )
