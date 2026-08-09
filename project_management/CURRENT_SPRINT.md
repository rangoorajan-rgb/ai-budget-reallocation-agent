# Current Sprint

**Active sprint:** Sprint 1 — Development Stage 1
**Status:** Active (Stage 1 complete)
**Reference:** See [MASTER_PROJECT_PLAN.md](MASTER_PROJECT_PLAN.md) for the full frozen plan.

The repository foundation (directory structure, root project files, placeholder modules,
and initial project-management documentation) is complete and is not re-tracked here.

## Stage 1 — Enumerations, Frozen Constants, Core Input Models, CSV Schema (complete)

- [x] `src/constants.py` — frozen `str, Enum` enumerations: `Platform`, `KPIType`,
      `CampaignStatus`, `TrackingStatus`, `BusinessPriority`, `RecommendationAction`,
      `Confidence`, `ReviewStatus`, `ValidationSeverity`, `ReasonCode`. Plus nine frozen
      numerical constants (`DEFAULT_MAX_CHANGE_PERCENTAGE`, `TREND_THRESHOLD`,
      `SEVEN_DAY_WEIGHT`, `TWENTY_EIGHT_DAY_WEIGHT`, `INCREASE_THRESHOLD`,
      `MAINTAIN_THRESHOLD`, `MINIMUM_CONVERSIONS`, `HIGH_CONFIDENCE_CONVERSIONS`,
      `CURRENCY_QUANTUM`). No decision, calculation, or allocation logic.
- [x] `src/models.py` — exactly two input-focused Pydantic v2 models: `ReviewSetup` and
      `CampaignInput`. Enforces only safe, model-level type and structural rules: blank
      checks, currency quantisation to `CURRENCY_QUANTUM` via `ROUND_HALF_UP`, KPI/
      percentage fields left unquantised, `maximum_budget >= minimum_budget`,
      `minimum_budget <= current_budget <= maximum_budget`, `spend_to_date <=
      current_budget`, `conversions_7d <= conversions_28d`, `period_end >= period_start`,
      `initial_account_reserve <= approved_monthly_budget`, percentage fields bounded
      `0 < x <= 1`, test-campaign/`test_budget_floor` requiredness in both directions, and
      conventional boolean parsing (bool, 1/0, case-insensitive true/false, yes/no; all
      other values rejected as ambiguous). No validation workflow, metrics, pacing,
      classification, constraints, scoring, allocation, or conservation logic.
- [x] Exact 20-field CSV schema for `CampaignInput`, in a fixed column order, using
      approved human-readable enum values (e.g. `Google Ads`, `Active`, `Healthy`, `High`)
      rather than Python enum member names.
- [x] `data/campaign_template.csv` — header row only, no data rows.
- [x] `data/sample_campaigns.csv` — 4 synthetic rows covering: active Google Ads CPA
      campaign, active Meta Ads ROAS campaign, protected active campaign, test campaign
      with a `test_budget_floor`.
- [x] `tests/test_models.py` — enum value/membership tests, frozen-constant tests,
      `ReviewSetup`/`CampaignInput` structural-rule tests (including currency
      quantisation, unquantised KPI/percentage fields, conventional boolean parsing, and
      every cross-field rule), and CSV-schema cross-checks against both CSV files.
      92 tests, all passing.
- [x] `docs/DATA_DICTIONARY.md` and `docs/DECISION_RULES.md` updated to document the CSV
      schema, `ReviewSetup` fields, approved enums, and the nine frozen constants.

## Explicitly Out of Scope for Stage 1

- CSV validation workflow (`src/validation.py`).
- CPA/ROAS metric calculations (`src/metrics.py`).
- Pacing, classification, constraints, scoring, allocation, conservation.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Next Stage

Stage 2 (not started): CSV validation workflow (`src/validation.py`).
