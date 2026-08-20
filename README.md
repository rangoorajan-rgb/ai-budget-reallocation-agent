# AI Budget Reallocation Agent

A human-governed budget-reallocation review application for Google Ads and Meta Ads
campaigns. It accepts campaign performance data through a CSV upload, validates the
complete portfolio, computes deterministic performance metrics and constraints,
recommends a budget action per campaign, ranks and allocates budget across the portfolio
while preserving exact monetary conservation, optionally generates a plain-language
explanation of the already-computed results using the Gemini API, requires an explicit
human approval or rejection of the complete review, writes that decision as an immutable
local JSON audit record, and makes an audited CSV available for download.

**This application never writes changes to Google Ads, Meta Ads, or any other
advertising platform, and it never reallocates a live budget autonomously.** Every output
is a recommendation, an explanation, a local audit record, or a downloadable CSV for a
human to act on manually, outside this application.

## Current Project Status

- **Sprint 1 — Foundation:** complete.
- **Sprint 2 — Deterministic Core Engine (Development Stages 1–27):** complete.
- **Sprint 3 — Explanation, Approval, and Interface (Development Stages 28–36):** complete.
- **Sprint 4 — Hardening and Documentation (Development Stages 37–42):** complete.
  - Stage 37 — Finalize the Five Living Documentation Files.
  - Stage 38 — Rewrite the Project README.
  - Stage 39 — Packaging and Dependency Hardening.
  - Stage 40 — Test-Suite Hardening and Adversarial Validation Coverage.
  - Stage 41 — Human-in-the-Loop, Audit, and Governance Completeness Review.
  - Stage 42 — Final Release Verification and Project Completion.
- Final verified baseline: `12 passed` (integration), `1743 passed` (full suite).

**Sprint 4 is complete. The planned four-sprint implementation is complete.** There is
currently no hosted CI workflow — this was never a frozen Sprint 4 exit criterion, and its
absence does not block completion; verification is local and reproducible via the
`pytest` commands documented under [Testing](#testing) below. Next work, if any, is
optional post-project maintenance or future enhancements only — no Development Stage 43
has started.

## Trust and Governance Model

Every decision the application makes passes through exactly three, strictly ordered
authority layers:

1. **Deterministic rules calculate and decide the recommendation data.** All metrics,
   classifications, constraints, recommendation actions, reason codes, scores, ranks, and
   allocated amounts are computed by plain Python using `Decimal` arithmetic — no AI
   model participates in this computation.
2. **Gemini may explain an already-locked result, but cannot alter it.** The explanation
   layer can only narrate facts the deterministic engine already locked. AI-generated
   text is supplementary only, is never stored in the audit record or the exported CSV,
   and has no field or code path through which it could change a recommendation, an
   amount, a score, a rank, an approval, or an audit record.
3. **A human must explicitly approve or reject the complete review before anything is
   persisted or exported.** Approving a review in this application records a decision —
   it does not execute any change on an advertising platform, and the application never
   calls a live advertising platform at any point.

## Features

- Review-setup validation (reviewer, period, approved budget, reserve).
- Full-portfolio CSV validation — any invalid row blocks the entire portfolio; no partial
  results are ever produced.
- Deterministic performance metrics (CPA/ROAS ratios) and pacing calculations.
- Neutral performance, trend, conversion-volume-confidence, tracking-assessability, and
  pacing classifications.
- Budget constraints (static bounds, applicable change percentage, movement caps,
  test-floor and protection rules).
- Mechanical action availability and conservative directional suitability per campaign.
- Final recommendation-action selection (`INCREASE` / `MAINTAIN` / `REDUCE` / `HOLD`) with
  an ordered, deterministic reason-code explanation.
- Per-campaign priority scoring, cross-campaign ranking, and constrained budget allocation
  with independent conservation verification.
- A Streamlit review interface presenting the complete locked, read-only result.
- Optional Gemini-generated portfolio and campaign explanations of the locked result.
- Mandatory human approval or rejection of the complete review.
- Immutable, idempotent local JSON audit persistence for every finalized decision.
- In-memory audited CSV export, available only once a decision has been persisted.
- A full automated test suite, including an end-to-end integration suite covering the
  complete upload-through-export flow.

## Architecture Overview

`app.py` orchestrates a chain of small, single-responsibility modules under `src/`: input
validation, deterministic metrics/classification/constraint calculation, recommendation
selection, cross-campaign ranking and allocation, an independent conservation check,
optional Gemini explanation, human approval, immutable audit persistence, and in-memory
CSV export. For the complete module-by-module design, trust boundaries, session-state
lifecycle, and data-flow diagram, see:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full system architecture.
- [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) — every model and field.
- [`docs/DECISION_RULES.md`](docs/DECISION_RULES.md) — every frozen business rule.
- [`docs/TEST_SCENARIOS.md`](docs/TEST_SCENARIOS.md) — the test scenario catalogue.
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — known limitations and non-goals.

## Requirements

- Python `>=3.11` (the floor declared in `pyproject.toml`; no upper bound is declared or
  verified).
- All Python packages are installed from `requirements.txt`.
- [Streamlit](https://streamlit.io/) is used to run the interface.
- A Gemini API key is **optional** — the deterministic review, approval, audit, and export
  workflow all function fully without one.

## Installation

Verified development environment: Windows, PowerShell.

```powershell
git clone https://github.com/rangoorajan-rgb/ai-budget-reallocation-agent.git
cd ai-budget-reallocation-agent
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**macOS/Linux** (equivalent virtual-environment activation; not independently verified by
this project's own test suite):

```bash
git clone https://github.com/rangoorajan-rgb/ai-budget-reallocation-agent.git
cd ai-budget-reallocation-agent
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Optional Gemini Configuration

Gemini is entirely optional. The deterministic review, human approval, audit persistence,
and CSV export all work fully without any Gemini configuration.

To enable Gemini explanations:

1. Copy `.env.example` to `.env`.
2. Set `GEMINI_API_KEY` in your local `.env` to your own key.
3. `.env` is listed in `.gitignore` and is never committed to the repository.

```text
GEMINI_API_KEY=your-own-key-here
```

**Never commit a real key, paste one into documentation or an issue, print it, or share
it.** Never place a real key directly in source code. If the key is missing or blank, the
explanation section shows an "unavailable" state — it never blocks the deterministic
review, approval, audit, or export workflow.

## Running the Application

```powershell
streamlit run app.py
```

Normal flow:

1. Enter the review details (review ID, dates, reviewer name, approved budget, reserve).
2. Upload a campaign CSV.
3. Run the deterministic review.
4. Inspect the locked recommendations and the conservation result.
5. Optionally request a portfolio explanation and/or a campaign explanation.
6. Approve or reject the review.
7. Confirm the audit record was persisted.
8. Download the audited CSV.

**Invalid review details, or any invalid row anywhere in the uploaded CSV, block the
entire portfolio** — the deterministic pipeline never runs on a partial or
partially-invalid dataset.

## CSV Input

- Start from [`data/campaign_template.csv`](data/campaign_template.csv) — a header-only
  file with the exact required column order.
- [`data/sample_campaigns.csv`](data/sample_campaigns.csv) is a small worked example.
- The exact field-by-field schema (types, bounds, and meaning of every column) is
  documented in [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) — retain the
  template's required headers exactly.

## Outputs and Persistence

- The locked review result lives only in the running Streamlit session's state — it is
  not itself written to disk.
- A successful approval or rejection is persisted as one immutable local JSON audit
  record. The default audit directory is `audit_records/`; `.gitkeep` is the only file in
  that directory tracked by Git.
- The audited CSV is generated entirely in memory and delivered directly through the
  download button — no export file is ever written to the server filesystem, and no
  `exports/` directory exists anywhere in this repository.
- The application does not use a production database or any cloud persistence.

## Testing

```powershell
python -m pytest tests/test_integration.py -q
python -m pytest -q
```

Current verified baseline (Stage 42, final release verification):

- Integration suite: `12 passed`
- Full suite: `1743 passed`

All automated tests are network-free. Gemini-dependent behavior is exercised either
through the real, network-free "unavailable" path (no API key configured) or through fake
Gemini clients/responses injected directly into the tests — no real Gemini SDK client is
ever constructed and no real API key is required to run the test suite. There is currently
no continuous-integration workflow in this repository; all test runs to date have been
performed locally.

## Security and Privacy

- Secrets belong only in local environment configuration (`.env`, environment variables)
  — never in source code, documentation, or version control.
- The application never prints, logs, or exports the Gemini API key; it is held in a
  redacted secret type and is never stored in the UI or in application state.
- When explicitly requested by a user and when Gemini is configured, the application
  sends the locked explanation payload (campaign identifiers, names, and computed
  results) to Google's Gemini API over the network.
- Organizations must independently assess privacy, internal policy, and data-processing
  suitability before enabling Gemini with real campaign data — this application makes no
  compliance claim on their behalf.
- Local audit records may contain campaign and reviewer information and should be stored
  and handled appropriately by the operator.
- The current application has no authentication, no authorization/role-based access
  control, and no multi-user isolation.

## Limitations and Non-Goals

This is a local, pilot-oriented application, not enterprise-production software. See
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for the complete list. At minimum:

- No live advertising-platform connection and no budget writeback of any kind.
- No automatic execution — every decision requires an explicit human action.
- No authentication, authorization/RBAC, or multi-user concurrency design.
- No production database and no cloud persistence.
- No real-time data ingestion and no scheduled or background execution.
- Gemini explanations may be unavailable, blocked, incomplete, or simply incorrect —
  human accountability for every approval or rejection remains mandatory regardless.

## Repository Structure

| Path | Purpose |
|---|---|
| `app.py` | Streamlit interface tying the deterministic engine, Gemini, approval, audit, and export together. |
| `config.py` | Gemini API-key configuration boundary. |
| `src/` | The deterministic core engine, Gemini payload/transport, approval, audit, and export modules. |
| `tests/` | The full automated test suite, including the end-to-end integration suite. |
| `data/` | The CSV template and a sample dataset. |
| `docs/` | Architecture, data dictionary, decision rules, test scenarios, and limitations documentation. |
| `project_management/` | The master project plan and per-stage tracking (current sprint, decisions, changelog). |
| `audit_records/` | Local JSON audit records; only `.gitkeep` is tracked by Git. |

## Pilot-Use Guidance

The frozen project plan describes this application as ready for **real-world pilot use**
— not as enterprise-production-ready software. In practice that means:

- Controlled, local evaluation by one reviewer at a time.
- Preferring non-production or already-approved-for-testing campaign data where
  appropriate.
- A human reviewing and explicitly approving or rejecting every recommendation.
- No live advertising-platform execution occurs at any point — every action remains
  manual, outside this application.
- Responsible local handling of audit files, which may contain campaign and reviewer
  information.
- Optional Gemini use only with organizational awareness and approval, given the
  third-party data-processing implications described above.

## Licence

MIT License — see [`LICENSE`](LICENSE).
