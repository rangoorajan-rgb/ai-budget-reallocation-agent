# Decisions Log

Each entry records a decision, its date, and its status. Frozen decisions require a new
entry (not an edit) to change.

## 2026-08-09 — Overall architecture is frozen

**Decision:** The repository structure and module boundaries defined in
[MASTER_PROJECT_PLAN.md](MASTER_PROJECT_PLAN.md) are frozen for the duration of the project.
**Status:** Frozen.

## 2026-08-09 — Deterministic-first approach

**Decision:** All budget-reallocation calculations (validation, metrics, pacing,
classification, constraints, scoring, allocation, conservation) are implemented as
deterministic Python logic. No machine-learning or AI model participates in computing the
recommended numbers.
**Status:** Frozen.

## 2026-08-09 — Financial calculations use Python `Decimal`

**Decision:** All monetary and financial-ratio calculations (spend, CPA, ROAS, budget
amounts) use Python's `Decimal` type rather than `float`, to avoid floating-point rounding
errors in financial output.
**Status:** Frozen.

## 2026-08-09 — Audit storage is JSON on local disk

**Decision:** Every approval or rejection decision is recorded as an immutable JSON audit
record under `audit_records/`. No external database is used in this phase.
**Status:** Frozen.

## 2026-08-09 — Gemini is explanation-only

**Decision:** The Gemini API is used exclusively to generate natural-language explanations
of already-computed, already-locked recommendation results. Gemini has no ability to
generate, alter, or approve budget numbers, and is not part of the decision-computation path.
**Status:** Frozen.

## 2026-08-09 — No live advertising-platform changes

**Decision:** The application never writes back to Google Ads or Meta Ads. It only reads
CSV exports of campaign data and produces CSV/JSON outputs (recommendations, exports, audit
records) for a human to act on manually outside the application.
**Status:** Frozen.
