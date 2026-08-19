"""CSV export generation for reallocation recommendations and results.

Implements Sprint 3 — Development Stage 35: the CSV export of a
successfully persisted `CampaignReallocationAudit` — the frozen, combined
record of one complete locked `BudgetReallocationReviewResult` and its
finalized `CampaignReallocationApproval` (Stage 34). This module never
rebuilds, rereads, or reinterprets an audit; it only ever consumes one
already-validated `CampaignReallocationAudit` object and copies its
already-computed fields into flat CSV rows.

**One flat CSV, one row per campaign.** Shared audit/approval/portfolio-
total/conservation values are deliberately repeated on every campaign row
so each row is self-contained and independently usable — no summary row,
no multiple files, no `record_type` column, no separate portfolio
section. An audit with no campaigns produces a valid header-only CSV.

**No recomputation.** This module never calls any Stage 1–34 production
function and never recalculates a recommendation, score, rank,
allocation, or conservation fact, and never reopens or reinterprets the
approval decision. Both `APPROVED` and `REJECTED` audits are exportable:
for a rejected review the CSV remains a factual record of the
deterministic recommendations that were reviewed, together with the
final rejection decision — rejection never deletes, relabels, or
reinterprets them.

**No Gemini, configuration, or filesystem coupling.** This module never
imports `config`, `src.explanations`, `src.gemini_analyzer`, `streamlit`,
a Gemini SDK, or any network/database client, and performs no file I/O
of its own — `serialize_campaign_reallocation_export_csv` returns an
in-memory `str`; delivering it to the user is the Stage 35 UI boundary's
responsibility (`app.py`, via `st.download_button`), not this module's.

**Decimal, enum, timestamp policy.** Every `Decimal` value already
embedded in the audit is rendered via `format(value, "f")` — exact,
fixed-point, never scientific notation, never routed through `float`.
Enums render via `.value`. `recorded_at` (already normalized to UTC by
the Stage 34 model) renders via `.isoformat()`. `rank=None` renders as
the literal string `"Not ranked"`; a `None` decision note renders as an
empty string. No other field is ever defaulted, normalized, or repaired.

**CSV formula-injection mitigation.** Every textual cell that can carry
user-controlled or uploaded text (`review_id`, `reviewer_name`,
`decision_note`, `campaign_id`, `campaign_name`) is passed through one
private neutralization helper: if its first non-whitespace character is
`=`, `+`, `-`, or `@`, the complete original value is prefixed with a
single apostrophe — applied exactly once (idempotent, since an
apostrophe is never itself a trigger character), and never applied to
trusted enum/boolean/integer/hash/timestamp/Decimal-string values.
Quoting and escaping of commas, quotes, embedded newlines, and Unicode is
left entirely to Python's standard `csv` module — nothing here manually
escapes a delimiter or quote character.
"""

import csv
import io
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.audit import CampaignReallocationAudit

_FORMULA_TRIGGER_CHARACTERS = ("=", "+", "-", "@")

_EXPORT_COLUMNS = (
    "audit_id",
    "review_id",
    "recorded_at",
    "decision",
    "reviewer_name",
    "decision_note",
    "total_current_budget",
    "total_recommended_budget",
    "total_increase_allocated",
    "total_decrease_allocated",
    "net_change",
    "is_conserved",
    "campaign_id",
    "campaign_name",
    "platform",
    "current_budget",
    "recommendation_action",
    "allocated_amount",
    "recommended_budget",
    "reason_codes",
    "performance_band",
    "trend_direction",
    "confidence",
    "pacing_status",
    "reallocation_priority_score",
    "rank",
)


def _neutralize_formula(value: str) -> str:
    """Prefix `value` with a single apostrophe if its first non-whitespace
    character could be interpreted as a spreadsheet formula trigger
    (`=`, `+`, `-`, `@`); otherwise return it unchanged. Never strips,
    reorders, or otherwise alters the original text — only ever prepends
    one character. Idempotent: an apostrophe is never itself a trigger
    character, so re-applying this to an already-neutralized value is a
    no-op."""
    first_significant = value.lstrip()
    if first_significant and first_significant[0] in _FORMULA_TRIGGER_CHARACTERS:
        return f"'{value}"
    return value


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


class CampaignReallocationExportRow(BaseModel):
    """One self-contained, flat CSV row: one campaign's locked
    recommendation plus the shared audit/approval/portfolio context it
    was reviewed and decided under.

    Not an allocation record, a ranking record, an audit record, or an
    approval model — those remain the responsibility of their own
    already-approved stages.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_id: str
    review_id: str
    recorded_at: str
    decision: str
    reviewer_name: str
    decision_note: str
    total_current_budget: str
    total_recommended_budget: str
    total_increase_allocated: str
    total_decrease_allocated: str
    net_change: str
    is_conserved: bool
    campaign_id: str
    campaign_name: str
    platform: str
    current_budget: str
    recommendation_action: str
    allocated_amount: str
    recommended_budget: str
    reason_codes: str
    performance_band: str
    trend_direction: str
    confidence: str
    pacing_status: str
    reallocation_priority_score: int
    rank: str


def build_campaign_reallocation_export_rows(
    audit: CampaignReallocationAudit,
) -> tuple[CampaignReallocationExportRow, ...]:
    """Copy one already-built, already-persisted audit's fields into flat
    CSV rows — one row per campaign, in `campaign_results`' own original
    order.

    Never recomputes, reranks, or reinterprets anything; an audit with no
    campaigns returns an empty tuple. Both `APPROVED` and `REJECTED`
    audits are accepted identically — this function never inspects or
    branches on `decision` beyond copying its `.value`.
    """
    result = audit.result
    approval = audit.approval
    conservation = result.conservation

    shared = {
        "audit_id": audit.audit_id,
        "review_id": _neutralize_formula(audit.review_id),
        "recorded_at": audit.recorded_at.isoformat(),
        "decision": approval.decision.value,
        "reviewer_name": _neutralize_formula(approval.reviewer_name),
        "decision_note": _neutralize_formula(approval.note) if approval.note is not None else "",
        "total_current_budget": _format_decimal(result.total_current_budget),
        "total_recommended_budget": _format_decimal(result.total_recommended_budget),
        "total_increase_allocated": _format_decimal(conservation.total_increase_allocated),
        "total_decrease_allocated": _format_decimal(conservation.total_decrease_allocated),
        "net_change": _format_decimal(conservation.net_change),
        "is_conserved": conservation.is_conserved,
    }

    rows: list[CampaignReallocationExportRow] = []
    for campaign in result.campaign_results:
        rows.append(
            CampaignReallocationExportRow(
                **shared,
                campaign_id=_neutralize_formula(campaign.campaign_id),
                campaign_name=_neutralize_formula(campaign.campaign_name),
                platform=campaign.platform.value,
                current_budget=_format_decimal(campaign.current_budget),
                recommendation_action=campaign.recommendation_action.value,
                allocated_amount=_format_decimal(campaign.allocated_amount),
                recommended_budget=_format_decimal(campaign.recommended_budget),
                reason_codes=", ".join(code.value for code in campaign.reason_codes),
                performance_band=campaign.performance_band.value,
                trend_direction=campaign.trend_direction.value,
                confidence=campaign.confidence.value,
                pacing_status=campaign.pacing_status.value,
                reallocation_priority_score=campaign.reallocation_priority_score,
                rank=str(campaign.rank) if campaign.rank is not None else "Not ranked",
            )
        )
    return tuple(rows)


def serialize_campaign_reallocation_export_csv(
    rows: tuple[CampaignReallocationExportRow, ...],
) -> str:
    """Serialize export rows into one CSV string using the frozen
    `_EXPORT_COLUMNS` order — independent of Pydantic field-declaration
    order or dict ordering.

    Quoting/escaping of commas, quotes, embedded newlines, and Unicode is
    delegated entirely to Python's standard `csv` module. `is_conserved`
    is written as the raw Python `bool` the field already holds, which
    `csv.writer` renders as the literal text `True`/`False`. An empty
    `rows` tuple produces a valid header-only CSV.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_EXPORT_COLUMNS)
    for row in rows:
        writer.writerow([getattr(row, column) for column in _EXPORT_COLUMNS])
    return buffer.getvalue()
