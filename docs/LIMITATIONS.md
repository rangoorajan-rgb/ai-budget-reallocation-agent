# Limitations

> Sprint 4, Development Stage 37. Reflects the completed Sprint 1–3 implementation
> (Development Stages 1–36). This document states honest, current facts about the
> application as implemented — it does not overstate readiness. The frozen master plan's
> Sprint 3 exit criteria describe the project as ready for real-world **pilot** use, not
> as enterprise-production-ready software.

## Known Constraints

### Data ingestion

- **No live advertising-platform ingestion.** The application never reads campaign data
  directly from Google Ads, Meta Ads, or any other advertising platform's API. The only
  input channel is a manually uploaded CSV file (`data/campaign_template.csv` defines the
  required 20-column schema).
- **Deterministic recommendations depend entirely on the quality of the supplied CSV.**
  Stale, incomplete, or inaccurate uploaded data produces stale, incomplete, or inaccurate
  recommendations — the deterministic engine validates structure and type correctness
  (`src/validation.py`) but has no way to verify that uploaded performance numbers are
  themselves current or correct.

### Advertising-platform execution

- **No advertising-platform budget writeback of any kind.** No module in this repository
  writes to Google Ads, Meta Ads, or any other advertising platform. Every output —
  on-screen recommendation, Gemini explanation, audit record, or CSV export — is for a
  human to act on manually, outside this application.
- **Human approval or rejection is not an advertising-platform execution action.**
  Approving a review in this application records a decision; it does not change any
  campaign's actual budget anywhere.

### Gemini explanations

- **Gemini use is entirely optional.** No part of the deterministic pipeline, approval,
  audit, or export flow requires a Gemini explanation to have been generated, and none of
  them ever waits for or depends on one.
- **Gemini has no authority over deterministic results, allocations, approvals, or
  audits.** `ExplanationResult` (`src/gemini_analyzer.py`) has no field capable of
  representing a recommendation, amount, score, rank, approval decision, or conservation
  value — there is no code path by which a Gemini response can alter any of them.
- **An explanation may be unavailable, blocked, incomplete, or simply incorrect.**
  `ExplanationStatus` includes `UNAVAILABLE` (no API key configured) and `FAILED`
  (authentication, rate-limit, timeout, network, safety-block, or malformed-response
  errors, among others). Even a `GENERATED` explanation is an unverified, third-party
  language-model output — it is never checked for factual accuracy against the locked
  numbers beyond what the model itself infers from the supplied JSON, and a human should
  treat it as supplementary narration only, never as a verified fact.
- **Using Gemini may incur third-party cost and data-processing implications.** Every
  Gemini call sends the payload built from the locked result (campaign IDs, names,
  budgets, and computed facts) to Google's Gemini API over the network. Users and
  organizations must independently assess their own privacy, security, and data-handling
  policies before enabling and using this feature — this application makes no compliance
  claim on their behalf.

### Human approval

- **Human approval or rejection is mandatory before audit persistence or CSV export.**
  Neither an audit record nor a CSV export can exist for a review that has not been
  explicitly approved or rejected by a named human reviewer (`src/approval.py`,
  `app.py`'s persistence-success gating on the export section).
- **Approval is an all-or-nothing decision on the complete locked portfolio.** There is no
  per-campaign or partial approval — conservation is a whole-portfolio invariant, so only
  a whole-review decision preserves its meaning.

### Persistence

- **Audit records are local JSON files, not a production database.** Each finalized
  decision is written as exactly one UTF-8 JSON file under `audit_records/`, named by a
  deterministic SHA-256 digest of its content. There is no query engine, no indexing
  beyond the filesystem itself, no replication, and no backup mechanism built into the
  application.
- **CSV exports are generated in memory and downloaded by the user; nothing is written to
  the server filesystem.** No `exports/` directory exists anywhere in this repository, and
  none is ever created — the CSV bytes are handed directly to Streamlit's
  `st.download_button` and exist only for the duration of that download.

## Out of Scope

- **No authentication.** The application does not verify who is using it. The
  `reviewer_name` recorded on an approval or rejection is free-text entered by whoever is
  operating the browser session — it is not tied to any verified identity.
- **No authorization or role-based access control.** Anyone who can run or reach the
  application can validate data, generate explanations, approve or reject reviews, and
  download exports. There are no permission tiers.
- **No multi-user concurrency model.** The application is built around Streamlit's
  single-session-per-browser-tab state model (`st.session_state`); it has not been
  designed, tested, or hardened for multiple reviewers concurrently working on the same
  review, or for any locking/conflict-resolution behavior between simultaneous sessions.
- **No centralized database.** All state beyond one browser session's `st.session_state`
  is the flat-file `audit_records/` directory described above — there is no relational,
  document, or other database anywhere in the stack.
- **No distributed locking.** Because there is no shared database or multi-instance
  deployment model, no distributed-locking mechanism exists or is needed by the current
  design; this remains a gap if the application is ever deployed in a genuinely
  multi-instance configuration.
- **No cloud persistence.** Audit records are local-filesystem JSON files only, per the
  project's frozen "Audit storage is JSON on local disk" decision
  (`project_management/DECISIONS.md`). Nothing is written to any cloud storage service.
- **No automatic audit backup or retention system.** Once written, an audit JSON file is
  never automatically copied, archived, rotated, or deleted by the application — file
  lifecycle beyond the initial write is entirely the operator's own responsibility.
- **No real-time monitoring.** There is no dashboard, alerting, or health-check surface
  reporting on the application's own operation.
- **No scheduled execution.** Every review, explanation, approval, and export happens only
  in direct response to a human clicking a button in the running Streamlit session — there
  is no cron-like or background trigger anywhere in the codebase.
- **No retry queue or background job processor.** A failed audit write offers exactly one
  manual retry button in the same session; there is no durable queue, no automatic
  background retry, and no job processor of any kind.
- **No production observability/telemetry.** The application emits no structured logs,
  metrics, or traces of its own; the only feedback surface is the Streamlit UI itself
  within the active session.

## Assumptions

- **Local/single-user pilot orientation.** The application is designed to be run locally
  (or in an equivalent single-instance deployment) by one reviewer at a time, consistent
  with the master plan's Sprint 3 exit criterion describing readiness for "real-world
  pilot use" — not a claim of enterprise-scale, multi-tenant production readiness.
  Local-file audit persistence is appropriate for this scope but does not survive an
  ephemeral or stateless cloud filesystem being wiped on redeploy, and has no
  cross-process coordination beyond what a single atomic file write provides.
- **Test environment and Python-version compatibility.** The full test suite (`1715`
  tests as of Stage 36) has been developed and verified against Python 3.14 on Windows, in
  a single local environment. `pyproject.toml` declares a floor of `requires-python =
  ">=3.11"` with no upper bound and no automated cross-version or cross-platform matrix has
  been run — compatibility with other supported Python versions or non-Windows platforms
  is expected but not independently verified by this project's own test suite.
- **Reserved enum/reason-code values are not evidence of implemented behaviour.** Several
  enum members exist in `src/constants.py` for forward compatibility or documentation
  completeness but are never assigned by any current production function:
  `Confidence.NOT_ASSESSABLE`, and twelve of the twenty `ReasonCode` members
  (`BELOW_TARGET_MODERATE`, `BELOW_TARGET_SEVERE`, `STRONG_LONG_TERM_RECENT_DECLINE`,
  `CAMPAIGN_CAP_REACHED`, `CAMPAIGN_FLOOR_REACHED`, `TEST_BUDGET_FLOOR_APPLIED`,
  `MAX_CHANGE_LIMIT_APPLIED`, `NO_ELIGIBLE_RECIPIENT`, `ACCOUNT_RESERVE_REQUIRED`,
  `TRACKING_WARNING`, `INSUFFICIENT_CONVERSION_VOLUME`, `PROTECTED_FROM_REDUCTION`). Their
  presence in the enum definition is not a claim that the corresponding behavior exists —
  see `docs/ARCHITECTURE.md`'s "HOLD, Confidence.NOT_ASSESSABLE, and ReasonCode" section
  for the exact, currently-implemented state of each.
