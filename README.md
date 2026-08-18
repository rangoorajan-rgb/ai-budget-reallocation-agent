# AI Budget Reallocation Agent

## Business Problem

Advertisers running campaigns across Google Ads and Meta Ads must regularly decide how to
reallocate budget between campaigns based on performance (CPA or ROAS). This process today is
manual, inconsistent, and hard to audit: analysts eyeball spreadsheets, apply gut-feel rules,
and rarely leave a traceable record of why budget moved from one campaign to another.

## Proposed Solution

A human-in-the-loop application that:

1. Validates uploaded Google Ads and Meta Ads campaign data (CSV).
2. Assesses each campaign's CPA or ROAS performance against goals and pacing.
3. Produces constrained, fully traceable budget-reallocation recommendations using a
   deterministic allocation engine (no black-box ML in the decision path).
4. Locks the recommended results and generates a natural-language explanation of the
   already-computed numbers using the Gemini API.
5. Records the user's approval or rejection of each recommendation as an immutable JSON
   audit record.

## Human-in-the-Loop Boundary

- All budget-reallocation numbers are computed deterministically in Python using `Decimal`
  arithmetic, before any AI model is involved.
- Gemini is used **only** to explain already-locked, already-computed results in plain
  language. It never generates, alters, or approves numbers.
- A human must explicitly approve or reject every recommendation.
- **This application never changes live advertising-platform budgets.** All outputs are
  recommendations and CSV/JSON exports for the user to act on manually.

## Planned Technology

- Python 3.11
- Streamlit (interface)
- pandas (data handling)
- Pydantic (data modeling and validation)
- Python `Decimal` (financial calculations)
- Gemini API (explanation only)
- pytest (testing)
- CSV inputs/exports, JSON audit records

## Current Status

**Sprint 2 — Deterministic Core Engine complete.** Sprint 1 (Foundation) and Sprint 2
(Development Stages 1–27: validation, metrics, pacing, classification, constraints,
scoring, allocation, conservation, and final pipeline integration) are both complete, with
a verified deterministic baseline of `1258 passed`. No Streamlit interface, Gemini
integration, approval workflow, or audit/export logic exists yet — that is Sprint 3
(Explanation, Approval, and Interface), which is next.
