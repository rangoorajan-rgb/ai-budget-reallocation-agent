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

## 2026-08-09 — CampaignInput CSV schema is a fixed 20-field set, in this exact order

**Decision:** The campaign CSV schema (`CampaignInput` in `src/models.py`, and both
`data/campaign_template.csv` and `data/sample_campaigns.csv`) uses exactly these 20 fields
in this exact order: `campaign_id`, `campaign_name`, `platform`, `status`, `kpi_type`,
`kpi_target`, `current_budget`, `minimum_budget`, `maximum_budget`, `spend_to_date`,
`conversions_7d`, `conversions_28d`, `kpi_actual_7d`, `kpi_actual_28d`, `tracking_status`,
`business_priority`, `is_protected`, `is_test_campaign`, `test_budget_floor`,
`campaign_max_change_percentage`. No impressions or clicks columns. Field names use
`status` (not `campaign_status`), `kpi_target` (not `target_kpi`), `kpi_actual_7d` /
`kpi_actual_28d` (not `kpi_7d` / `kpi_28d`), `minimum_budget` / `maximum_budget` (not
`campaign_min_budget` / `campaign_max_budget`), and `campaign_max_change_percentage` (not
`campaign_max_change_pct`).
**Status:** Frozen.

## 2026-08-09 — CSV enum values are approved human-readable strings, not Python member names

**Decision:** `Platform`, `CampaignStatus`, `TrackingStatus`, and `BusinessPriority` are
`str, Enum` classes whose values are the approved human-readable display strings used in
CSV data — e.g. `Platform.GOOGLE_ADS = "Google Ads"`, `CampaignStatus.ACTIVE = "Active"`,
`TrackingStatus.HEALTHY = "Healthy"`, `BusinessPriority.HIGH = "High"` — not the Python
member names. `KPIType` (`CPA`, `ROAS`) is unchanged since its member names and values are
identical. This keeps CSV files human-readable while the member names stay used in code.
**Status:** Frozen.

## 2026-08-09 — Input models scope is limited to ReviewSetup and CampaignInput; unknown fields rejected

**Decision:** This stage authorises exactly two Pydantic input models: `ReviewSetup` and
`CampaignInput`. No other model (including a `ValidationIssue` model considered and then
removed during this stage) is added until a later stage explicitly requires it. Both models
use `extra="forbid"` so unrecognized CSV columns or typos fail loudly instead of being
silently dropped. Pydantic's conventional numeric parsing (`str`/`int`/`float`/`Decimal`
compatible input coerced to `Decimal`) is used as-is — there is no blanket rejection of
`float` input.
**Status:** Frozen.

## 2026-08-09 — Currency fields are quantised; KPI and percentage fields are not

**Decision:** `ReviewSetup.approved_monthly_budget`, `ReviewSetup.initial_account_reserve`,
and `CampaignInput.current_budget` / `minimum_budget` / `maximum_budget` / `spend_to_date` /
`test_budget_floor` are true currency amounts: `Decimal`, quantised to `CURRENCY_QUANTUM`
(`Decimal("0.01")`) using `ROUND_HALF_UP` at the model boundary. KPI and percentage fields —
`kpi_target`, `kpi_actual_7d`, `kpi_actual_28d`, `default_max_change_percentage`,
`campaign_max_change_percentage` — remain plain, unquantised `Decimal`. A single shared
"Money" type covering both categories was rejected as incorrect: currency and ratio/
percentage values have different rounding semantics and must not share one type.
**Status:** Frozen.

## 2026-08-09 — Nine frozen numerical constants reserved in src/constants.py

**Decision:** `src/constants.py` reserves nine named numerical constants for use by later
Sprint 1 stages (pacing, classification, scoring, allocation, conservation), with no
calculation logic attached to them yet: `DEFAULT_MAX_CHANGE_PERCENTAGE = Decimal("0.20")`,
`TREND_THRESHOLD = Decimal("0.10")`, `SEVEN_DAY_WEIGHT = Decimal("0.40")`,
`TWENTY_EIGHT_DAY_WEIGHT = Decimal("0.60")`, `INCREASE_THRESHOLD = Decimal("1.15")`,
`MAINTAIN_THRESHOLD = Decimal("0.90")`, `MINIMUM_CONVERSIONS = 10`,
`HIGH_CONFIDENCE_CONVERSIONS = 30`, `CURRENCY_QUANTUM = Decimal("0.01")`.
**Status:** Frozen.

## 2026-08-09 — ReviewSetup and CampaignInput structural rules and field names

**Decision:** `ReviewSetup` uses `initial_account_reserve` (not `account_reserve`) and
`default_max_change_percentage` (not `default_max_change_pct`), for naming consistency with
`CampaignInput.campaign_max_change_percentage`. Both models enforce these structural rules
at the model level, in addition to blank/type/currency checks: `ReviewSetup.period_end >=
period_start`; `ReviewSetup.approved_monthly_budget > 0`; `ReviewSetup.initial_account_reserve
>= 0` and `<= approved_monthly_budget`; `0 < default_max_change_percentage <= 1`;
`CampaignInput.maximum_budget >= minimum_budget`; `minimum_budget <= current_budget <=
maximum_budget`; `spend_to_date <= current_budget`; `conversions_7d <= conversions_28d`;
`kpi_target > 0`; `kpi_actual_7d > 0` and `kpi_actual_28d > 0`; `0 <
campaign_max_change_percentage <= 1` when supplied; a test campaign requires
`test_budget_floor` to be set, a non-test campaign requires it to be `None`, and when set it
must be `>= 0` and `<= current_budget`. `is_protected` and `is_test_campaign` accept only
conventional boolean input — literal `bool`, `1`/`0`, or case-insensitive `true`/`false`/
`yes`/`no` — and reject all other values (including `"t"`, `"on"`, `2`, `3.5`) as ambiguous.
**Status:** Frozen.
