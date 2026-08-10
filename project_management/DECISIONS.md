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

## 2026-08-09 — Stage 2: validation models live in src/validation.py, not src/models.py

**Decision:** `ValidationIssue` and `ValidationReport` are defined in `src/validation.py`.
`src/models.py` is unchanged and remains scoped to exactly `ReviewSetup` and
`CampaignInput`. `src/validation.py` never re-implements a structural rule already
enforced by those two models — it only invokes them and translates their
`pydantic.ValidationError` output into `ValidationIssue` records.
**Status:** Frozen.

## 2026-08-09 — Stage 2: ValidationCode enum, distinct from ReasonCode

**Decision:** `src/constants.py` adds `ValidationCode` (`INVALID_REVIEW_FIELD`,
`EMPTY_FILE`, `INVALID_HEADER`, `NO_CAMPAIGN_ROWS`, `MALFORMED_ROW`,
`INVALID_CAMPAIGN_FIELD`, `DUPLICATE_CAMPAIGN_ID`) for input-validation issues.
`ReasonCode` is not reused for this purpose — it is reserved for recommendation/allocation
outcomes in a later stage. No additional validation code is added without first
identifying a concrete case that cannot correctly use one of these seven.
**Status:** Frozen.

## 2026-08-09 — Stage 2: ValidationIssue and ValidationReport field sets

**Decision:** `ValidationIssue` has exactly `severity`, `code`, `field`, `message`,
`row_number`, `campaign_id`. Every issue Stage 2 produces has `severity =
ValidationSeverity.ERROR`. `row_number` is the physical one-based CSV line number (header
= line 1, first data row = line 2); file-level and `ReviewSetup` issues use
`row_number=None`. `ValidationReport` has exactly `issues`, `valid_campaigns`, plus
`error_count`, `warning_count`, and `is_valid` computed from `issues` on every access
(not accepted as independently trusted constructor arguments — attempting to set them
directly raises a validation error). `ValidationReport` has no `review_id` field, since
invalid raw review input may not contain a usable review ID. `valid_campaigns` preserves
original CSV order.
**Status:** Frozen.

## 2026-08-09 — Stage 2: CSV header, row-shape, and no-row rules

**Decision:** The required campaign CSV header is derived at runtime from
`CampaignInput.model_fields` (never a second hand-typed list), so the model and CSV
schema cannot silently drift. Any header not exactly equal to that order — missing,
extra, renamed, reordered, or duplicate column — produces exactly one `INVALID_HEADER`
issue at `row_number=1`, and no row is validated afterward (`valid_campaigns` stays
empty). A completely empty stream (no header) produces one `EMPTY_FILE` issue. A valid
header followed by zero data rows produces one `NO_CAMPAIGN_ROWS` issue — this is the
expected, valid outcome for `data/campaign_template.csv`. A data row whose cell count is
not exactly 20 produces one `MALFORMED_ROW` issue and is not passed to `CampaignInput`. A
row with the correct cell count but all-blank cells is attempted like any other row (it is
not treated as "no row"), and is reported via `MALFORMED_ROW`/`INVALID_CAMPAIGN_FIELD` as
applicable.
**Status:** Frozen.

## 2026-08-09 — Stage 2: row parsing, invalid-row continuation, and duplicate handling

**Decision:** For each well-shaped row, blank cells are converted to `None` only for
`test_budget_floor` and `campaign_max_change_percentage`; every other raw cell value is
passed unmodified to `CampaignInput`, which performs all numeric/enum/boolean/budget/
conversion/KPI/test-floor validation. `campaign_id` is attached to an issue (trimmed)
whenever the row has at least one cell, since it is always column 1 and its position is
stable even when the row is otherwise malformed or invalid. One invalid row does not stop
processing later rows: each underlying `pydantic.ValidationError` is translated into one
`INVALID_CAMPAIGN_FIELD` issue (so a row can produce more than one), and the row is
excluded from `valid_campaigns`. Duplicate `campaign_id` detection runs only among rows
that successfully instantiated `CampaignInput` — structurally invalid rows never
participate. Comparison uses the model's already-trimmed `campaign_id` and is
case-sensitive. If an ID occurs more than once, every occurrence (not just the 2nd and
later) receives its own `DUPLICATE_CAMPAIGN_ID` issue at its own physical line number, and
every occurrence is excluded from `valid_campaigns`; non-duplicate valid rows keep their
original CSV order.
**Status:** Frozen.

## 2026-08-09 — Stage 2: error-only severity; no raw exception leakage

**Decision:** Every issue Stage 2 produces has severity `ERROR`. No Stage-2-only
`WARNING` rule exists — `TrackingStatus.WARNING`/`UNRELIABLE` are valid enum inputs, not
validation warnings, and protected/test-campaign states are valid whenever the existing
frozen model rules pass. `ValidationReport.warning_count` remains generically derived from
`issues` rather than hardcoded to `0`, so it would reflect a future `WARNING`-severity
issue if one is ever added, but every current outcome yields `0`. Separately: where a
value is `Decimal`-coercible but an internal `decimal` operation (e.g. quantising an
extreme value like `Decimal("1E+30")`) raises a raw `decimal.DecimalException` rather than
a `pydantic.ValidationError` — a real, empirically confirmed gap in the frozen `Currency`
type's `AfterValidator`, which `src/models.py` cannot be changed to fix — `src/validation.py`
catches that specific exception type and reports one safe, generic issue instead of
leaking the internal exception. No other exception type is broadly suppressed.
**Status:** Frozen.

## 2026-08-10 — Stage 3 is metric calculation, chosen by dependency order not file-list order

**Decision:** `src/metrics.py` is Sprint 1, Development Stage 3, selected because every
one of the nine frozen numerical constants operates on `CampaignInput` KPI/conversion
fields (not budget-pacing fields), `MASTER_PROJECT_PLAN.md`'s Sprint 2 goal sentence names
"metric" logic but not pacing, and classification's `ReasonCode` members that depend on a
computed ratio/trend fact structurally require metrics to exist first. `src/pacing.py` has
no frozen constants prepared for it and remains unstarted with unresolved scope.
**Status:** Frozen.

## 2026-08-10 — Stage 3: CampaignMetrics lives in src/metrics.py; facts only, five fields

**Decision:** `CampaignMetrics` (frozen, immutable; `extra="forbid"`) is defined in
`src/metrics.py`, not `src/models.py` — following the Stage 2 precedent of keeping
`src/models.py` scoped to exactly `ReviewSetup` and `CampaignInput`. It has exactly five
fields: `campaign_id`, `performance_ratio_7d`, `performance_ratio_28d`,
`weighted_performance_ratio`, `trend_delta`. It carries no KPI type, raw KPI value,
conversions, confidence, trend label, recommendation action, reason code, score, or
budget field — Stage 3 calculates facts only and never classifies, scores, recommends, or
assigns confidence. The sole public function is `calculate_campaign_metrics(campaign:
CampaignInput) -> CampaignMetrics`; it accepts only an already-validated `CampaignInput`
instance (no raw mapping, CSV row, or unvalidated dict) and there is no batch-calculation
function in this stage — a caller iterates over validated campaigns itself.
**Status:** Frozen.

## 2026-08-10 — Stage 3: direction-normalised ratio, weighted blend, and trend-delta formulas

**Decision:** For `KPIType.ROAS`: `performance_ratio = kpi_actual / kpi_target`. For
`KPIType.CPA`: `performance_ratio = kpi_target / kpi_actual`. Computed once per window
(7-day, 28-day). By construction, `> 1` always means better than target and `< 1` always
means worse than target, identically for both KPI types — this uniformity is why a single
threshold pair can later apply to both. `weighted_performance_ratio =
performance_ratio_7d * SEVEN_DAY_WEIGHT + performance_ratio_28d *
TWENTY_EIGHT_DAY_WEIGHT`, using the existing frozen weights unchanged.
`trend_delta = (performance_ratio_7d - performance_ratio_28d) / performance_ratio_28d` —
a *relative*, not absolute, delta. The calculation is platform-independent (depends only
on `kpi_type`, `kpi_target`, `kpi_actual_7d`, `kpi_actual_28d`, never `platform`).
`INCREASE_THRESHOLD`, `MAINTAIN_THRESHOLD`, and `TREND_THRESHOLD` are not applied in
`src/metrics.py` — comparing facts against them to produce a classification is reserved
for a later stage.
**Status:** Frozen.

## 2026-08-10 — Stage 3: Decimal precision-28/ROUND_HALF_UP local context; no quantisation

**Decision:** Every calculation in `calculate_campaign_metrics` runs inside an explicit
`decimal.localcontext()` with `prec=28` and `rounding=ROUND_HALF_UP`, so the result is
identical regardless of any global `Decimal` context a caller may have mutated. No
calculated field is quantised to a fixed number of decimal places — ratios are not
currency, so `CURRENCY_QUANTUM` is never applied to them, and no new rounding or ratio
constant was added to `src/constants.py`. `float()` is never called and no `Decimal` is
ever constructed from a `float`. `CampaignInput` already guarantees `kpi_target > 0`,
`kpi_actual_7d > 0`, and `kpi_actual_28d > 0`, so `src/metrics.py` performs no zero-guard,
broad exception handling, or sentinel-value logic, and calling it with something other
than a `CampaignInput` is left to fail with a normal Python type-contract error rather
than being silently coerced.
**Status:** Frozen.

## 2026-08-10 — Stage 3 excludes confidence, trend labels, and every later-stage decision

**Decision:** `src/metrics.py` does not use `MINIMUM_CONVERSIONS` or
`HIGH_CONFIDENCE_CONVERSIONS`, and does not calculate or assign `Confidence`. It does not
compare `trend_delta` to `TREND_THRESHOLD` and does not return `IMPROVING`/`STABLE`/
`DECLINING` or any new trend enum. Which conversion window controls confidence, the exact
threshold boundaries, tracking-status effects, and `NOT_ASSESSABLE` behaviour are all
explicitly deferred to a later classification stage. Pacing, classification, constraints,
scoring, allocation, conservation, Gemini, Streamlit, approval, audit, and export logic
remain entirely out of scope for Stage 3.
**Status:** Frozen.

## 2026-08-10 — Stage 4 is campaign pacing, confirmed by weighing mixed dependency evidence

**Decision:** `src/pacing.py` is Sprint 1, Development Stage 4. Constants-readiness
evidence alone favoured classification (5 of 9 frozen constants are classification-domain,
and `CampaignMetrics` newly satisfies its prerequisite), but pacing was confirmed instead
because `README.md`'s "Proposed Solution" explicitly names pacing as one of exactly two
co-equal assessment axes ("performance against goals and pacing") — the strongest single
piece of product-intent evidence in the repository, and one that never mentions
"classification" at all — because pacing's required inputs were already fully available
from Stage 1 alone with no Stage 3 dependency, and because pacing's open questions were
comparatively few, tractable calendar/currency conventions rather than the large web of
interacting business decisions (which ratio, confidence-tier formula, trend-label
boundaries, `RecommendationAction`/`Confidence` interaction, protected-campaign boundary,
20 `ReasonCode` triggers) that classification would have required to freeze safely.
**Status:** Frozen.

## 2026-08-10 — Stage 4: CampaignPacing lives in src/pacing.py; facts only, nine fields

**Decision:** `CampaignPacing` (frozen, immutable; `extra="forbid"`) is defined in
`src/pacing.py`, not `src/models.py`, following the Stage 2/3 precedent. It has exactly
nine fields: `campaign_id`, `elapsed_days`, `total_period_days`, `elapsed_fraction`,
`expected_spend`, `spend_variance`, `pacing_ratio`, `remaining_budget`,
`projected_end_of_period_spend`. It carries no pacing status, label, classification,
confidence, recommendation action, reason code, score, eligibility, or allocation field —
Stage 4 calculates facts only. The sole public function is
`calculate_campaign_pacing(review: ReviewSetup, campaign: CampaignInput) ->
CampaignPacing`; it accepts only already-validated `ReviewSetup`/`CampaignInput`
instances (no raw mapping, CSV row, or unvalidated dict), and there is no batch-
calculation function — a caller iterates over validated campaigns itself. `src/pacing.py`
does not import `CampaignMetrics` or any later-stage module, and uses only
`ReviewSetup.review_date`/`period_start`/`period_end` and
`CampaignInput.campaign_id`/`current_budget`/`spend_to_date` — never `platform`,
`kpi_type`, KPI values, or performance/trend/conversion-volume constants.
**Status:** Frozen.

## 2026-08-10 — Stage 4: inclusive date counting and elapsed-day clamping

**Decision:** `total_period_days = (period_end - period_start).days + 1` (inclusive of
both boundary days), chosen specifically because `ReviewSetup` already permits
`period_start == period_end` (a valid one-day review period) and exclusive counting would
make that case's `total_period_days = 0`, an unavoidable zero denominator. Since
`ReviewSetup` places no frozen constraint between `review_date` and the period
boundaries, `elapsed_days` is calculated as `raw_elapsed_days = (review_date -
period_start).days + 1` then clamped: `elapsed_days = min(max(raw_elapsed_days, 0),
total_period_days)`. A `review_date` before `period_start` yields `elapsed_days = 0`; on
`period_start` yields `1`; on or after `period_end` yields `total_period_days`. This
clamping is Stage 4 calculation behaviour only — no cross-field validation was added or
modified on `ReviewSetup`.
**Status:** Frozen.

## 2026-08-10 — Stage 4: linear expected-spend, variance, pacing-ratio, remaining-budget, and projection formulas

**Decision:** `elapsed_fraction = Decimal(elapsed_days) / Decimal(total_period_days)`,
unquantised. Linear delivery is assumed: `raw_expected_spend = current_budget *
elapsed_fraction` (unquantised, used internally); the public `expected_spend =
raw_expected_spend.quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)`.
`spend_variance = (spend_to_date - raw_expected_spend).quantize(CURRENCY_QUANTUM,
rounding=ROUND_HALF_UP)` — positive means ahead of linear pace, negative means behind,
with no good/bad interpretation attached. `pacing_ratio = spend_to_date /
raw_expected_spend` when `raw_expected_spend != 0` (deliberately using the *unquantised*
expected spend so penny rounding cannot distort the ratio), else `None` — this occurs
exactly when `elapsed_days = 0` or `current_budget = Decimal("0.00")` (and since
`spend_to_date <= current_budget` is already frozen, a zero budget also forces zero
spend); never a `0/0` sentinel. `remaining_budget = (current_budget -
spend_to_date).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)` — structurally cannot
be negative given the already-frozen `spend_to_date <= current_budget`, so no new
validation was added for it. `projected_end_of_period_spend = (spend_to_date /
elapsed_fraction).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)` when
`elapsed_fraction != 0`, else `None` (before the period starts) — a factual linear
extrapolation only, never labelled as an expected overspend/underspend/risk.
**Status:** Frozen.

## 2026-08-10 — Stage 4: Decimal precision-28/ROUND_HALF_UP local context; quantisation policy

**Decision:** Every calculation in `calculate_campaign_pacing` runs inside an explicit
`decimal.localcontext()` with `prec=28` and `rounding=ROUND_HALF_UP`, identical to Stage
3's pattern, independent of any global `Decimal` context a caller may have mutated.
`expected_spend`, `spend_variance`, `remaining_budget`, and
`projected_end_of_period_spend` are quantised to the existing `CURRENCY_QUANTUM`
(`Decimal("0.01")`) since they represent money; `elapsed_fraction` and `pacing_ratio` are
not quantised, since they are ratios. No new pacing, ratio, rounding, or date constant
was added to `src/constants.py`. `float()` is never called and no `Decimal` is ever
constructed from a `float`. Calling `calculate_campaign_pacing` with something other than
`ReviewSetup`/`CampaignInput` instances is left to fail with a normal Python
type-contract error rather than being silently coerced.
**Status:** Frozen.
