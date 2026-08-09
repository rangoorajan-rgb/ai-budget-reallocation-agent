# Master Project Plan — AI Budget Reallocation Agent

**Status:** Frozen. This four-sprint plan and its exit criteria are the agreed scope for the
project. Changes to sprint scope must be recorded in [DECISIONS.md](DECISIONS.md).

## Sprint 1 — Foundation

**Goal:** Establish repository structure and project-management documentation before any
application code is written.

**Deliverables:**
- Full repository directory structure (`src/`, `tests/`, `data/`, `audit_records/`, `docs/`,
  `assets/`, `project_management/`).
- Placeholder Python modules (docstring only, no logic).
- Root project files: `README.md`, `LICENSE`, `.gitignore`, `.env.example`,
  `requirements.txt`, `pyproject.toml`.
- Placeholder documentation headings in `docs/`.
- Project-management documentation (this plan, current sprint tracker, decision log, changelog).

**Exit criteria:**
- Every file and directory in the agreed structure exists.
- No business logic, data models, calculation engine, Streamlit interface, or Gemini
  integration has been implemented.
- README and project-management docs accurately describe project purpose, boundaries, and
  status.

## Sprint 2 — Deterministic Core Engine

**Goal:** Implement the fully deterministic, `Decimal`-based data validation, metric,
classification, constraint, scoring, allocation, and conservation logic — with no AI
involvement — plus its test coverage.

**Planned scope:**
- `src/models.py` — Pydantic models for campaign records and recommendations.
- `src/validation.py` — CSV/schema validation for Google Ads and Meta Ads inputs.
- `src/metrics.py` — CPA and ROAS calculations using `Decimal`.
- `src/pacing.py` — Budget pacing assessment.
- `src/classification.py` — Performance classification rules.
- `src/constraints.py` — Reallocation constraint rules.
- `src/scoring.py` — Campaign prioritization scoring.
- `src/allocation.py` — Constrained budget-reallocation engine.
- `src/conservation.py` — Total-budget conservation checks.
- `data/campaign_template.csv`, `data/sample_campaigns.csv` — populated with real template
  columns and representative sample data.
- Corresponding unit tests in `tests/`.

**Exit criteria:**
- All deterministic modules pass unit tests with representative and edge-case data.
- Allocation recommendations are fully traceable to input data and rules, with no live
  advertising-platform calls anywhere in the module set.

## Sprint 3 — Explanation, Approval, and Interface

**Goal:** Add the Gemini explanation layer (explanation-only, operating on already-locked
results), the human approval/rejection workflow, audit recording, exports, and the Streamlit
interface tying it all together.

**Planned scope:**
- `src/explanations.py` — Construction of explanation payloads from locked results.
- `src/gemini_analyzer.py` — Gemini API integration, explanation-only.
- `src/approval.py` — Human approval/rejection workflow.
- `src/audit.py` — Immutable JSON audit record creation and storage.
- `src/exports.py` — CSV export of recommendations and outcomes.
- `app.py`, `config.py` — Streamlit interface and configuration wiring.
- Integration tests in `tests/test_integration.py`.

**Exit criteria:**
- End-to-end flow works: upload → validate → assess → recommend → lock → explain (Gemini) →
  approve/reject → audit record written → CSV export available.
- Gemini is verifiably confined to explanation of locked numbers; no path exists by which it
  can alter recommendations or touch live advertising-platform budgets.
- Every approval or rejection produces a traceable JSON audit record.

## Sprint 4 — Hardening and Documentation

**Goal:** Close out edge cases, finalize documentation, and confirm the system is safe and
well-understood before being considered complete.

**Planned scope:**
- Full test coverage review, including adversarial/edge-case CSV inputs.
- Finalize `docs/ARCHITECTURE.md`, `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
  `docs/TEST_SCENARIOS.md`, `docs/LIMITATIONS.md`.
- Review of the human-in-the-loop boundary and audit-trail completeness.
- General cleanup and packaging.

**Exit criteria:**
- All planned tests pass.
- All five `docs/` files contain complete, accurate content.
- No known path exists for the application to alter live advertising-platform budgets.
- Project is ready for real-world pilot use.
