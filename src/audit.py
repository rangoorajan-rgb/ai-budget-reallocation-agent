"""Immutable JSON audit record creation and storage.

Implements Sprint 3 — Development Stage 34: the durable, structured record
of exactly one complete locked `BudgetReallocationReviewResult` and its
finalized `CampaignReallocationApproval`. This is the only component in
the project that persists anything to disk — every earlier deterministic,
explanation, and approval stage returns a value and never writes a file.

**Embeds, never copies.** `CampaignReallocationAudit.result` and `.approval`
embed the existing frozen Stage 27/33 models directly. No parallel
result, campaign, conservation, or approval schema is created here, so
there is no way for an audit record to drift from what was actually
locked and decided.

**No wall-clock call anywhere in this module.** `recorded_at` is always
supplied by the caller — the one production call to
`datetime.now(timezone.utc)` belongs to the Stage 34 UI action boundary in
`app.py`, never here. This module is deterministic and fully testable
with injected timestamps, mirroring the "no hidden non-determinism in a
domain module" discipline enforced everywhere else in this project.

**No Gemini, configuration, export, or network coupling.** This module
never imports `config`, `src.explanations`, `src.gemini_analyzer`,
`src.exports`, `streamlit`, a Gemini SDK, or any network/database client.
An audit record contains only the locked deterministic result, the human
decision, an audit identifier, and a timestamp — nothing else can
structurally enter it.

**Consistency, not re-decision.** `build_campaign_reallocation_audit`
re-asserts, at the one place a bad record would become permanent, the
same two invariants `src/approval.py` already enforces at decision time:
the approval must reference the same review as the result, and an
`APPROVED` decision must be conserved. Neither input is ever repaired,
rebalanced, rerun, reinterpreted, or mutated; a rejected unconserved
result is always a valid record.

**Deterministic, content-derived audit ID.** `audit_id` is a SHA-256
digest, prefixed `audit_`, of the canonical JSON of exactly `{"result":
result, "approval": approval}` — excluding `recorded_at` entirely, so a
retried write of the *same* decision (whatever wall-clock moment it
happens to retry at) always resolves to the same file. No UUID, no
`hash()`, no raw `review_id` used as a path component, and no timestamp
ever contributes to the ID.

**Canonical serialization**, matching the policy already established in
`src/explanations.py`: field order follows Pydantic model declaration
order (never alphabetical), `ensure_ascii=False`, compact separators
`(",", ":")`, no indentation. `Decimal` values serialize as fixed-point
strings via `format(value, "f")` — never a JSON number, never `float`.
Enums serialize to `.value`; tuples serialize as JSON arrays; nested
frozen models serialize recursively as plain objects in their own
declared field order; `recorded_at` serializes as an ISO-8601 string with
an explicit UTC offset.

**Persistence: one JSON file per record, atomic, idempotent.** Exactly
one UTF-8 file per audit record, named `{audit_id}.json`, written to a
temporary file in the same directory, flushed and closed, then finalized
via `os.replace` (atomic on both POSIX and Windows) — no reader can ever
observe a partially written file, and a failure during serialization or
finalization leaves no temporary or final file behind. A pre-existing
file with the same `audit_id` and the same substantive content (ignoring
`recorded_at`, which is treated as the authoritative first-write moment)
is treated as an idempotent success, returning the original path
unchanged — this is what makes a Streamlit rerun or a manual retry safe.
A pre-existing file with genuinely different content under the same
`audit_id`, or one that cannot be parsed and validated back into
`CampaignReallocationAudit`, is never silently overwritten or repaired —
both raise.

**No read/list/delete/export surface here.** Enumerating or exporting
audit records is explicitly reserved for a later Stage 35 export stage,
which can rely on this module's frozen schema and filename convention
without this module growing a repository abstraction it does not yet
need.
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

from src.approval import CampaignReallocationApproval
from src.constants import ReviewStatus
from src.pipeline import BudgetReallocationReviewResult

_DEFAULT_DIRECTORY = Path(__file__).resolve().parent.parent / "audit_records"


class CampaignReallocationAudit(BaseModel):
    """One immutable, durable record of a complete locked review and its
    finalized human decision.

    Not a repair, an export, an explanation, or a second decision — the
    embedded `result` and `approval` are exactly the same frozen objects
    Stage 27 and Stage 33 already produced.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_id: str
    review_id: str
    result: BudgetReallocationReviewResult
    approval: CampaignReallocationApproval
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def _require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        return value.astimezone(timezone.utc)


def _normalize_value(value: object) -> object:
    """Recursively convert one field value into a JSON-safe, canonical
    form. Supports only the types the embedded Stage 27/33 models and
    `CampaignReallocationAudit` itself actually use."""
    if isinstance(value, BaseModel):
        return {
            field_name: _normalize_value(getattr(value, field_name))
            for field_name in type(value).model_fields
        }
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"unsupported type for audit record serialization: {type(value)!r}")


def _canonical_bytes(fields: dict) -> bytes:
    return json.dumps(
        fields, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    ).encode("utf-8")


def _compute_audit_id(
    result: BudgetReallocationReviewResult, approval: CampaignReallocationApproval
) -> str:
    fields = {"result": _normalize_value(result), "approval": _normalize_value(approval)}
    digest = hashlib.sha256(_canonical_bytes(fields)).hexdigest()
    return f"audit_{digest}"


def build_campaign_reallocation_audit(
    result: BudgetReallocationReviewResult,
    approval: CampaignReallocationApproval,
    recorded_at: datetime,
) -> CampaignReallocationAudit:
    """Build one audit record from an already-locked result and its
    already-finalized approval.

    Pure — no file, environment, clock, network, or SDK access. Raises
    exactly `ValueError("Approval review_id does not match the locked
    result's review_id.")` when the two disagree, checked first, and
    exactly `ValueError("An unconserved allocation cannot be recorded as
    approved.")` when `approval.decision is ReviewStatus.APPROVED` but
    `result.conservation.is_conserved` is `False`. A rejected unconserved
    result is always valid. Neither input is mutated, repaired, or
    rerun.
    """
    if approval.review_id != result.review_id:
        raise ValueError("Approval review_id does not match the locked result's review_id.")
    if approval.decision is ReviewStatus.APPROVED and not result.conservation.is_conserved:
        raise ValueError("An unconserved allocation cannot be recorded as approved.")

    audit_id = _compute_audit_id(result, approval)
    return CampaignReallocationAudit(
        audit_id=audit_id,
        review_id=result.review_id,
        result=result,
        approval=approval,
        recorded_at=recorded_at,
    )


def _read_existing_audit(path: Path) -> CampaignReallocationAudit:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    return CampaignReallocationAudit(**data)


def _same_substantive_content(
    existing: CampaignReallocationAudit, candidate: CampaignReallocationAudit
) -> bool:
    """Compare everything except `recorded_at` — the first successful
    write's timestamp is authoritative; a retry at a later moment with
    the same result and approval is still an idempotent success."""
    return (
        existing.audit_id == candidate.audit_id
        and existing.review_id == candidate.review_id
        and existing.result == candidate.result
        and existing.approval == candidate.approval
    )


def record_campaign_reallocation_audit(
    audit: CampaignReallocationAudit,
    *,
    directory: Path | None = None,
) -> Path:
    """Persist one audit record as `{directory}/{audit.audit_id}.json`.

    `directory` defaults to the repository-root-relative `audit_records/`,
    resolved from this module's own location, never the current working
    directory. Writes to a temporary file in the same directory, flushes
    and closes it, then finalizes atomically via `os.replace`; a failure
    during serialization or finalization leaves no temporary or final
    file behind. A pre-existing file with the same `audit_id` and the
    same substantive content is an idempotent no-op, returning the
    existing path unchanged. A pre-existing file with different content
    raises exactly `ValueError("An audit record with this audit_id
    already exists with different content.")`; a pre-existing file that
    cannot be parsed and validated raises without being overwritten.
    """
    target_directory = Path(directory) if directory is not None else _DEFAULT_DIRECTORY
    target_directory.mkdir(parents=True, exist_ok=True)
    final_path = target_directory / f"{audit.audit_id}.json"

    if final_path.exists():
        existing = _read_existing_audit(final_path)
        if _same_substantive_content(existing, audit):
            return final_path
        raise ValueError(
            "An audit record with this audit_id already exists with different content."
        )

    fields = {
        field_name: _normalize_value(getattr(audit, field_name))
        for field_name in type(audit).model_fields
    }
    serialized = _canonical_bytes(fields)

    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=target_directory, prefix=f".{audit.audit_id}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "wb") as handle:
            handle.write(serialized)
            handle.flush()
        os.replace(tmp_path, final_path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return final_path
