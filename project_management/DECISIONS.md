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

## 2026-08-10 — Stage 5 is neutral performance classification, narrower than "classification"

**Decision:** Sprint 1, Development Stage 5 is scoped to *neutral performance
classification only* — not the full "classification" responsibility named in
`MASTER_PROJECT_PLAN.md`. Trend classification, conversion-volume confidence, and
tracking-status interpretation are each deferred to a later stage, because each has its
own unresolved formula or boundary question (trend's equality-boundary convention;
confidence's conversion-window choice and the structural gap between two thresholds and
four `Confidence` tiers; tracking's undefined precedence relative to a numerical
performance class) that cannot be safely frozen without inventing a rule. Splitting
avoids silently choosing among multiple plausible formulas for any of those three.
**Status:** Frozen.

## 2026-08-10 — Stage 5: PerformanceBand and CampaignPerformanceClass, in src/classification.py

**Decision:** `PerformanceBand` (`str, Enum`: `ABOVE_TARGET`, `ON_TARGET`,
`BELOW_TARGET`) and `CampaignPerformanceClass` (frozen, immutable; `extra="forbid"`;
exactly `campaign_id`, `performance_band`) are defined in `src/classification.py`, not
`src/models.py`, following the Stage 2/3/4 precedent. `PerformanceBand` is deliberately a
neutral vocabulary distinct from `RecommendationAction` — it is never assigned to or
confused with `RecommendationAction`, `Confidence`, or `ReasonCode`, none of which is
imported by `src/classification.py`. This is because `RecommendationAction` has a fourth
member, `HOLD`, that cannot be derived from a performance-ratio threshold split alone, so
treating a performance band as if it were already a final recommendation would
misrepresent a single-factor, provisional judgement as a multi-factor decision. The sole
public function is `classify_campaign_performance(metrics: CampaignMetrics) ->
CampaignPerformanceClass`; it accepts only an already-calculated `CampaignMetrics`
instance (no `CampaignInput`, `CampaignPacing`, `ReviewSetup`, raw mapping, or
unvalidated dict), and there is no batch-calculation function — a caller iterates over
calculated metrics itself.
**Status:** Frozen.

## 2026-08-10 — Stage 5: exact threshold conditions and equality behaviour

**Decision:** Classification applies directly to `CampaignMetrics.weighted_performance_ratio`
using the existing frozen `INCREASE_THRESHOLD` and `MAINTAIN_THRESHOLD`, with the
threshold value itself belonging to the higher band:
```
weighted_performance_ratio >= INCREASE_THRESHOLD               → ABOVE_TARGET
MAINTAIN_THRESHOLD <= weighted_performance_ratio < INCREASE_THRESHOLD → ON_TARGET
weighted_performance_ratio < MAINTAIN_THRESHOLD                → BELOW_TARGET
```
No other `CampaignMetrics` field (`performance_ratio_7d`, `performance_ratio_28d`,
`trend_delta`) is used. Classification performs direct `Decimal` comparison only — no
arithmetic, quantisation, `float` conversion, or local `decimal` context, since no
computation is performed. The calculation is platform- and KPI-independent by
construction, since Stage 3 already direction-normalised CPA and ROAS so that a higher
ratio always means better performance for both; `src/classification.py` contains no
KPI-specific branching. A campaign receives a numerical performance band regardless of
its trend, conversion volume, or tracking reliability — Stage 5 creates no precedence or
override rule for those later considerations.
**Status:** Frozen.

## 2026-08-10 — Stage 6 is neutral trend classification, independent of PerformanceBand

**Decision:** Sprint 1, Development Stage 6 adds neutral trend classification to
`src/classification.py`, as an *addition* alongside Stage 5's performance
classification — not a modification of it. `CampaignPerformanceClass` and
`PerformanceBand` are unmodified. Confidence, tracking interpretation, pacing
interpretation, and every combined campaign judgement remain deferred, for the same
reasons established when Stage 5 was scoped narrower than "classification": each has its
own unresolved formula or boundary question that would require inventing a rule to
resolve now.
**Status:** Frozen.

## 2026-08-10 — Stage 6: TrendDirection and CampaignTrendClass, separate from PerformanceBand

**Decision:** `TrendDirection` (`str, Enum`: `IMPROVING`, `STABLE`, `DECLINING`) and
`CampaignTrendClass` (frozen, immutable; `extra="forbid"`; exactly `campaign_id`,
`trend_direction`) are defined in `src/classification.py`, alongside but fully separate
from `PerformanceBand`/`CampaignPerformanceClass`. Despite `ReasonCode` having matching
member names (`RECENT_TREND_IMPROVING`/`STABLE`/`DECLINING`), `TrendDirection` is not
`ReasonCode` and is never assigned to it; `RecommendationAction`, `Confidence`, and
`ReasonCode` remain unimported by `src/classification.py`. The sole public function is
`classify_campaign_trend(metrics: CampaignMetrics) -> CampaignTrendClass`; it accepts
only an already-calculated `CampaignMetrics` instance (no `CampaignInput`,
`CampaignPacing`, `ReviewSetup`, `CampaignPerformanceClass`, raw mapping, or unvalidated
dict) and reads only `campaign_id` and `trend_delta` from it — no other `CampaignMetrics`
field. There is no batch-calculation function, and `classify_campaign_trend` never calls
`classify_campaign_performance` (or vice versa).
**Status:** Frozen.

## 2026-08-10 — Stage 6: exact threshold conditions, equality behaviour, and negative-boundary construction

**Decision:** Trend classification applies directly to `CampaignMetrics.trend_delta`
using the existing frozen `TREND_THRESHOLD`, with the threshold magnitude itself
belonging to the directional band in both directions (equality Policy A, chosen for
consistency with Stage 5's identical "reaching the threshold qualifies" convention):
```
trend_delta >= TREND_THRESHOLD                → IMPROVING
-TREND_THRESHOLD < trend_delta < TREND_THRESHOLD → STABLE
trend_delta <= -TREND_THRESHOLD               → DECLINING
```
The negative boundary is constructed as `TREND_THRESHOLD.copy_negate()` — an exact
sign-inversion with no rounding and no dependence on the active `Decimal` context — never
a new constant, `Decimal("-1")` multiplication, `float` conversion, or recalculation from
campaign data. No arithmetic or quantisation is performed on `trend_delta` itself;
classification is comparison-only. The calculation is platform- and KPI-independent by
construction, since Stage 3 already direction-normalised CPA and ROAS so that
`trend_delta`'s sign has identical meaning for both.
**Status:** Frozen.

## 2026-08-11 — Stage 7 is conversion-volume confidence only; independent of Stage 5/6 classifications

**Decision:** Sprint 1, Development Stage 7 adds conversion-volume confidence
classification to `src/classification.py`, as an *addition* alongside Stage 5's
performance classification and Stage 6's trend classification — not a modification of
either. `CampaignPerformanceClass`, `PerformanceBand`, `CampaignTrendClass`, and
`TrendDirection` are unmodified. Tracking-status interpretation and every combined
campaign judgement remain deferred, for the same reasons established when Stages 5 and 6
were each scoped narrower than "classification": tracking has no frozen precedence rule
anywhere in the repository.
**Status:** Frozen.

## 2026-08-11 — Stage 7: conversions_28d-only window policy; no summing or weighting

**Decision:** `classify_campaign_confidence` uses `CampaignInput.conversions_28d` only.
`conversions_7d` is never read, combined, summed, averaged, or weighted with
`conversions_28d`. This is because `conversions_28d` is the fuller, more statistically
stable evidence window, and `conversions_7d <= conversions_28d` is already a frozen
`CampaignInput` invariant precisely because the 7-day window is temporally nested inside
the 28-day window (the same underlying conversion events), not an independent period —
so summing the two would double-count. `SEVEN_DAY_WEIGHT`/`TWENTY_28_DAY_WEIGHT` (Stage
3's ratio-blending constants) are not reused for this purpose.
**Status:** Frozen.

## 2026-08-11 — Stage 7: CampaignConfidenceClass reuses the existing Confidence enum

**Decision:** `CampaignConfidenceClass` (frozen, immutable; `extra="forbid"`; exactly
`campaign_id`, `confidence`) is defined in `src/classification.py`, alongside but fully
separate from `CampaignPerformanceClass` and `CampaignTrendClass`. Unlike Stages 5–6
(which introduced new neutral enums, `PerformanceBand`/`TrendDirection`, specifically to
avoid conflating a classification with `RecommendationAction`/`ReasonCode`), Stage 7
reuses the existing `Confidence` enum directly — `Confidence` is already a neutral
evidence-quality vocabulary, not a recommendation-shaped one, so reuse does not risk the
same premature-recommendation conflation. The sole public function is
`classify_campaign_confidence(campaign: CampaignInput) -> CampaignConfidenceClass`; it
accepts only an already-validated `CampaignInput` instance (no `CampaignMetrics`,
`CampaignPacing`, `CampaignPerformanceClass`, `CampaignTrendClass`, `ReviewSetup`, raw
mapping, or unvalidated dict) and reads only `campaign_id` and `conversions_28d` from
it. There is no batch-calculation function, and `classify_campaign_confidence` never
calls `classify_campaign_performance` or `classify_campaign_trend` (or vice versa).
**Status:** Frozen.

## 2026-08-11 — Stage 7: exact HIGH/MEDIUM/LOW bands, equality, and NOT_ASSESSABLE deferral

**Decision:** Using the existing frozen `MINIMUM_CONVERSIONS = 10` and
`HIGH_CONFIDENCE_CONVERSIONS = 30`, with the threshold magnitude belonging to the higher
band in both cases (consistent with Stages 5–6's identical "reaching the threshold
qualifies" convention):
```
conversions_28d >= HIGH_CONFIDENCE_CONVERSIONS   → HIGH
conversions_28d >= MINIMUM_CONVERSIONS           → MEDIUM
otherwise (0–9, including zero)                  → LOW
```
Zero conversions produces `LOW`, not a special case. `Confidence.NOT_ASSESSABLE` is
never assigned by Stage 7 — this is a deliberate scope boundary (the enum member remains
valid and unmodified; Stage 7 simply never produces it), not an inference from zero/low
conversions, `TrackingStatus.WARNING`/`UNRELIABLE`, zero spend, zero budget,
`PerformanceBand`, `TrendDirection`, `CampaignPacing`, or protected/test status. Its
trigger and any precedence rule remain deferred until tracking interpretation or a later
combined-assessment stage is formally approved. No arithmetic, quantisation, or
`Decimal`/`float` conversion is performed — `conversions_28d` and both thresholds are
plain `int`; classification is direct integer comparison only. The calculation is
platform- and KPI-independent — it depends only on `conversions_28d`.
**Status:** Frozen.

## 2026-08-11 — Stage 7: two Stage 5/6 AST scope-boundary tests narrowed by explicit approval

**Decision:** Implementing the approved Stage 7 specification required importing
`CampaignInput` (`src.models`) and `Confidence` (`src.constants`) into
`src/classification.py`. This broke a pre-existing assertion in both
`tests/test_classification.py` and `tests/test_trend_classification.py` —
`test_classification_module_does_not_import_out_of_scope_modules_or_enums` — which had
forbidden those exact imports because, at the time Stages 5 and 6 were written,
`src/classification.py` legitimately had no reason to import either. This was identified
as a genuine conflict (not silently resolved): implementing Stage 7 as specified and
never modifying those two test files are mutually incompatible given their existing
content. With explicit approval, both tests' `forbidden_imports` sets were narrowed to
remove only `"src.models"`, `"CampaignInput"`, and `"Confidence"`; every other forbidden
entry (`CampaignPacing`, `ReviewSetup`, `RecommendationAction`, `ReasonCode`, and the
out-of-scope `src.*` modules) is unchanged and still enforced by both tests.
**Status:** Frozen.

## 2026-08-11 — Stage 8 is narrow tracking-based assessability, not full tracking interpretation

**Decision:** Sprint 1, Development Stage 8 adds a narrow tracking-based assessability
fact to `src/classification.py`, as an *addition* alongside Stages 5–7's independent
results — not a modification of any of them. `CampaignPerformanceClass`,
`PerformanceBand`, `CampaignTrendClass`, `TrendDirection`, `CampaignConfidenceClass`, and
`classify_campaign_confidence` are all unmodified; Stage 7 continues returning only
`Confidence.HIGH`/`MEDIUM`/`LOW` regardless of `tracking_status`. This is deliberately
narrower than "tracking interpretation" broadly — it resolves only the binary
assessable/not-assessable question from `tracking_status` alone, not severity ranking,
overrides of other classifications, or `Confidence.NOT_ASSESSABLE` ownership, each of
which remains a genuinely unresolved decision deferred to a later combined-assessment
stage.
**Status:** Frozen.

## 2026-08-11 — Stage 8: exact HEALTHY/WARNING/UNRELIABLE mapping and information preservation

**Decision:** `is_assessable = campaign.tracking_status is not TrackingStatus.UNRELIABLE`.
Therefore `HEALTHY → True`, `WARNING → True`, `UNRELIABLE → False` — `UNRELIABLE` is the
sole condition producing `is_assessable=False`. `WARNING` is treated as assessable
because it represents a concern requiring later caution, not an explicit declaration
that the evidence is unusable. The original `TrackingStatus` value is preserved
unchanged in the result (`CampaignTrackingAssessment.tracking_status`) specifically so
`WARNING` is never collapsed into `HEALTHY` — this keeps the distinction visible for
later `ReasonCode`/recommendation logic that may treat the two differently even though
both are currently assessable. No severity score, ranking, or replacement enum is
produced; `TrackingStatus` itself is reused unchanged, no new enum is created.
**Status:** Frozen.

## 2026-08-11 — Stage 8: CampaignTrackingAssessment, exactly three fields, independent of Stages 3–7

**Decision:** `CampaignTrackingAssessment` (frozen, immutable; `extra="forbid"`; exactly
`campaign_id`, `tracking_status`, `is_assessable`) is defined in `src/classification.py`,
alongside but fully separate from `CampaignPerformanceClass`, `CampaignTrendClass`, and
`CampaignConfidenceClass`. The sole public function is `assess_campaign_tracking(campaign:
CampaignInput) -> CampaignTrackingAssessment`; it accepts only an already-validated
`CampaignInput` instance (no `CampaignMetrics`, `CampaignPacing`, `CampaignPerformanceClass`,
`CampaignTrendClass`, `CampaignConfidenceClass`, `ReviewSetup`, raw mapping, or unvalidated
dict) and reads only `campaign_id` and `tracking_status` from it — never
`conversions_7d`/`conversions_28d`, `platform`, `kpi_type`, `is_protected`,
`is_test_campaign`, spend, or budget fields. There is no batch-calculation function, no
arithmetic/Decimal/float conversion, and `assess_campaign_tracking` never calls
`classify_campaign_performance`, `classify_campaign_trend`, or
`classify_campaign_confidence` (or vice versa). The same `TrackingStatus` produces the
same `is_assessable` for every platform, KPI type, conversion count, and protected/test
state.
**Status:** Frozen.

## 2026-08-11 — Stage 8: Confidence.NOT_ASSESSABLE ownership remains deferred

**Decision:** Stage 8 does not read, assign, or otherwise touch
`Confidence.NOT_ASSESSABLE` — it remains a valid, unmodified `Confidence` enum member.
Whether/how tracking-based assessability (Stage 8) and conversion-volume confidence
(Stage 7) relate to `Confidence.NOT_ASSESSABLE` is deferred to a later combined-
assessment stage, which is required to preserve both Stage 7's and Stage 8's independent
results rather than overwriting either — consistent with the information-preservation
principle already established when Stage 7 declined to infer `NOT_ASSESSABLE` from zero/
low conversions. Pacing interpretation likewise remains deferred, unrelated to this
decision.
**Status:** Frozen.

## 2026-08-11 — Stage 8: one Stage 7 AST scope-boundary test narrowed by explicit approval

**Decision:** Implementing the approved Stage 8 specification required importing
`TrackingStatus` (`src.constants`) into `src/classification.py`. This broke a
pre-existing assertion in `tests/test_confidence_classification.py` —
`test_classification_module_does_not_import_out_of_scope_modules_or_enums` — which had
forbidden that exact import because, when Stage 7 was written, `src/classification.py`
legitimately had no reason to import it. This was identified as a genuine conflict (not
silently resolved) and reported before any test file was touched, mirroring the
precedent set when Stage 7 itself required narrowing two Stage 5/6 assertions. With
explicit approval, only `"TrackingStatus"` was removed from that one test's
`forbidden_imports` set; every other forbidden entry (`CampaignPacing`, `ReviewSetup`,
`RecommendationAction`, `ReasonCode`, and the out-of-scope `src.*` modules) is unchanged
and still enforced. `tests/test_classification.py` and `tests/test_trend_classification.py`
were not affected (neither ever forbade `TrackingStatus`) and were not modified.
**Status:** Frozen.

## 2026-08-11 — Stage 9 is deterministic pacing interpretation, using pacing_ratio only

**Decision:** Sprint 1, Development Stage 9 adds a neutral pacing-status classification
to `src/pacing.py`, as an *addition* alongside Stage 4's `CampaignPacing`/
`calculate_campaign_pacing` — not a modification of either. `CampaignPacing` and its
calculation formulas are unmodified. `CampaignPacing.pacing_ratio` is the sole
classification input (plus `campaign_id` for result identity); `spend_variance`,
`expected_spend`, `elapsed_fraction`, `elapsed_days`, `total_period_days`,
`remaining_budget`, and `projected_end_of_period_spend` are never read by the
classification function. `projected_end_of_period_spend` is explicitly excluded as a
second pacing signal and is never compared against `current_budget`, `minimum_budget`,
or `maximum_budget`. `CampaignInput`, `ReviewSetup`, `CampaignMetrics`, and every Stage
5–8 result (`PerformanceBand`, `TrendDirection`, `Confidence`, `TrackingStatus`,
`CampaignTrackingAssessment`, `is_assessable`) are never read, and `is_protected`/
`is_test_campaign`/`test_budget_floor` are never read — Stage 9 remains fully
independent of constraints, protected/test handling, eligibility, scoring,
`RecommendationAction`, `ReasonCode`, and allocation, none of which is implemented or
extended by this stage.
**Status:** Frozen.

## 2026-08-11 — Stage 9: approved ±10% on-pace tolerance and exact inclusive-boundary precedence

**Decision:** Two new frozen constants are added to `src/constants.py`:
`PACING_LOWER_THRESHOLD = Decimal("0.90")` and `PACING_UPPER_THRESHOLD =
Decimal("1.10")` — a symmetric ±10% on-pace tolerance band around `1.00`, applied only
to `CampaignPacing.pacing_ratio`. `PacingStatus` (`str, Enum`: `UNDERSPENDING = "Under
spending"`, `ON_PACE = "On pace"`, `OVERSPENDING = "Over spending"`, `NOT_AVAILABLE =
"Not available"`) is added to `src/pacing.py`, with exact precedence:
```
pacing_ratio is None                                            → NOT_AVAILABLE
pacing_ratio < PACING_LOWER_THRESHOLD                            → UNDERSPENDING
PACING_LOWER_THRESHOLD <= pacing_ratio <= PACING_UPPER_THRESHOLD  → ON_PACE
pacing_ratio > PACING_UPPER_THRESHOLD                             → OVERSPENDING
```
The `ON_PACE` interval is **closed and inclusive on both ends** — `pacing_ratio ==
PACING_LOWER_THRESHOLD` and `pacing_ratio == PACING_UPPER_THRESHOLD` are both
`ON_PACE`. This is a deliberately different equality convention from Stages 5–7's
single-sided "reaching the threshold enters the higher band" rule, because this
threshold pair defines a two-sided tolerance band around a midpoint (`1.00`) rather than
an ascending ladder of bands. Direct `Decimal` comparison only — no arithmetic,
weighting, quantisation, or `float` conversion; `pacing_ratio` is never recalculated.
`PacingStatus` is deliberately descriptive only: it never states whether `OVERSPENDING`
or `UNDERSPENDING` is desirable, expected, or a problem — that judgement, if any, is
deferred to a later stage.
**Status:** Frozen.

## 2026-08-11 — Stage 9: NOT_AVAILABLE is a pacing-data state only, never substituted for zero

**Decision:** `pacing_ratio is None` (Stage 4's frozen zero-denominator case — zero
elapsed time or zero current budget) maps unconditionally to
`PacingStatus.NOT_AVAILABLE`. Stage 9 does not distinguish which upstream cause produced
the `None`, does not recalculate `pacing_ratio`, and does not substitute `Decimal("0")`
for `None`. `PacingStatus.NOT_AVAILABLE` is explicitly **not** interchangeable with, and
must never be represented as, `Confidence.NOT_ASSESSABLE`, `is_assessable=False`,
`TrackingStatus.UNRELIABLE`, `RecommendationAction.HOLD`, a reason code, or an
eligibility outcome — it is a narrower, pacing-specific data-availability fact only.
**Status:** Frozen.

## 2026-08-11 — Stage 9: CampaignPacingClass, exactly two fields, independent of Stages 5–8

**Decision:** `CampaignPacingClass` (frozen, immutable; `extra="forbid"`; exactly
`campaign_id`, `pacing_status`) is defined in `src/pacing.py`, alongside but fully
separate from `CampaignPacing`. The sole public function is
`classify_campaign_pacing(pacing: CampaignPacing) -> CampaignPacingClass`; it accepts
only an already-calculated `CampaignPacing` instance (no `CampaignInput`, `ReviewSetup`,
`CampaignMetrics`, or any Stage 5–8 result) and reads only `pacing.campaign_id`/
`pacing.pacing_ratio`. There is no batch-calculation function, no revalidation of
upstream inputs, and no recalculation of any Stage 4 field.
`classify_campaign_pacing` never calls `classify_campaign_performance`,
`classify_campaign_trend`, `classify_campaign_confidence`, or
`assess_campaign_tracking` (or vice versa); `CampaignPerformanceClass`,
`CampaignTrendClass`, `CampaignConfidenceClass`, and `CampaignTrackingAssessment` are
unmodified by Stage 9. Combined campaign assessment, `Confidence.NOT_ASSESSABLE`
ownership, constraints, protected/test handling, eligibility, scoring,
`RecommendationAction`, `ReasonCode`, and allocation remain deferred to later stages.
No existing test file required modification for Stage 9 — no approved exception was
needed, unlike Stages 7 and 8.
**Status:** Frozen.

## 2026-08-11 — Stage 10 is static budget-bound calculation only, not effective constraints

**Decision:** Sprint 1, Development Stage 10 populates `src/constraints.py` (previously
a bare placeholder) with a narrow, deterministic **static** budget-bound fact
calculation — not the full "constraints" responsibility named in `MASTER_PROJECT_PLAN.md`.
For one already-validated `CampaignInput`, it calculates the distance from
`current_budget` to the campaign's validated static `maximum_budget` and the distance
from `current_budget` to `minimum_budget`. These are neutral static-bound facts only —
Stage 10 does **not** calculate the campaign's final permissible budget movement,
because the percentage-change limit mechanism, protection rules, and test-campaign
rules all remain undecided and are explicitly deferred to a later effective-constraint
stage.
**Status:** Frozen.

## 2026-08-11 — Stage 10: exact model, formulas, and approved static-bound terminology

**Decision:** `CampaignStaticBudgetRoom` (frozen, immutable; `extra="forbid"`; exactly
`campaign_id`, `room_to_static_maximum`, `room_to_static_minimum`) is defined in
`src/constraints.py`. The sole public function is
`calculate_campaign_static_budget_room(campaign: CampaignInput) ->
CampaignStaticBudgetRoom`; it reads only `campaign.campaign_id`,
`campaign.current_budget`, `campaign.minimum_budget`, and `campaign.maximum_budget`.
Exact formulas:
```
room_to_static_maximum = maximum_budget - current_budget
room_to_static_minimum = current_budget - minimum_budget
```
Both are structurally guaranteed non-negative by `CampaignInput`'s already-validated
`minimum_budget <= current_budget <= maximum_budget` invariant (`src/models.py`,
`_check_budget_bounds`); Stage 10 adds no new validation and performs no clamping.
`Decimal("0.00")` is a valid calculated fact exactly at either bound (including the
`minimum_budget == current_budget == maximum_budget` case), and is never replaced with
`None` or a categorical status. The approved names
(`CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room`/
`room_to_static_maximum`/`room_to_static_minimum`) deliberately include "static" to
distinguish these facts from a future effective constraint; the more general names
considered during inspection (`CampaignBudgetRoom`/`calculate_campaign_budget_room`/
`room_to_increase`/`room_to_decrease`) were rejected specifically because they could
incorrectly imply percentage limits, protection, and test-budget-floor rules have
already been applied. Calculation runs inside an explicit `decimal.localcontext()`
(`prec=28`, `rounding=ROUND_HALF_UP`), matching the fixed-context pattern already used
by Stages 3–4; no `float`, no re-quantisation, no rounding of the output.
**Status:** Frozen.

## 2026-08-11 — Stage 10: minimum_budget used, not test_budget_floor; no reduction thereby authorised

**Decision:** `room_to_static_minimum` is always calculated against `minimum_budget`
only; `test_budget_floor` is never read by Stage 10. This is deliberate, not an
oversight: for `G003` in `data/sample_campaigns.csv` (`current_budget=1200.00`,
`minimum_budget=100.00`, `test_budget_floor=300.00`), `room_to_static_minimum =
Decimal("1100.00")`. This figure is a static-bound fact only — it is **not** an
approved decrease amount and does **not** authorise reducing `G003`'s budget by
`1100.00`, nor below its `300.00` test floor. A later effective-constraint stage must
determine the effective decrease limit after considering `test_budget_floor`, which may
be stricter than `minimum_budget` for a test campaign (as it is for `G003`).
**Status:** Frozen.

## 2026-08-11 — Stage 10: percentage-limit and protection exclusions

**Decision:** `campaign_max_change_percentage`, `ReviewSetup.default_max_change_percentage`,
and `DEFAULT_MAX_CHANGE_PERCENTAGE` are never read or applied by Stage 10 — no
percentage-based movement cap, effective increase/decrease limit, or intersection
between a percentage limit and the static bounds is calculated; the percentage
mechanism's application and precedence remain pending. `is_protected` is likewise never
read: a protected campaign (e.g. `G002` in `data/sample_campaigns.csv`) receives
exactly the same static-bound calculation as an otherwise identical unprotected
campaign, and this does not authorise increasing or decreasing a protected campaign —
protection behaviour remains pending a later stage. All effective-constraint,
protected/test-handling, and action-oriented logic (eligibility, scoring,
`RecommendationAction`, `ReasonCode`, allocation, conservation) remains deferred to
later stages. No existing test file required modification for Stage 10 —
`tests/test_constraints.py` was a bare placeholder with zero prior tests, so populating
it was not a modification of prior-stage behaviour.
**Status:** Frozen.

## 2026-08-11 — Stage 11 is applicable maximum-change-percentage resolution only

**Decision:** Sprint 1, Development Stage 11 adds a narrow, deterministic percentage-
resolution fact to `src/constraints.py`, as an *addition* alongside Stage 10's
`CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room` — not a modification
of either. For one already-validated `ReviewSetup` and one already-validated
`CampaignInput`, it selects which already-validated maximum-change percentage applies —
it does **not** calculate a monetary movement cap, does **not** multiply by
`current_budget` or any other amount, and does **not** determine any permissible budget
movement. This is deliberately narrower than "percentage-based constraints" broadly;
the monetary-cap formula, its base amount, symmetry between increase/decrease, and its
precedence relative to Stage 10's static bounds are all explicitly deferred, since none
is frozen anywhere and implementing them now would require inventing a rule.
**Status:** Frozen.

## 2026-08-11 — Stage 11: exact model, function signature, and override-first precedence

**Decision:** `CampaignApplicableChangePercentage` (frozen, immutable; `extra="forbid"`;
exactly `campaign_id`, `applicable_max_change_percentage`) is defined in
`src/constraints.py`, alongside but fully separate from `CampaignStaticBudgetRoom`. The
sole public function is `resolve_campaign_applicable_change_percentage(review:
ReviewSetup, campaign: CampaignInput) -> CampaignApplicableChangePercentage`; it reads
only `campaign.campaign_id`, `campaign.campaign_max_change_percentage`, and
`review.default_max_change_percentage` — no other field of either model, and no Stage
3–9 result. Exact rule:
```
applicable_max_change_percentage = (
    campaign.campaign_max_change_percentage
    if campaign.campaign_max_change_percentage is not None
    else review.default_max_change_percentage
)
```
A non-`None` campaign override always wins; otherwise the review default applies. This
uses an explicit `is not None` check, never a truthiness-based fallback (e.g. `campaign
override or review default`) — the distinction is currently unobservable in practice
(both source fields are `gt=0`, so no valid non-`None` override is ever falsy), but the
explicit check is the unambiguous, correct expression of the intended precedence
regardless of that coincidence. The result is never `None`, since
`review.default_max_change_percentage` itself is never `None` on a constructed
`ReviewSetup`. No special zero handling exists or is needed, since both source fields
are already constrained to `(0, 1]`.
**Status:** Frozen.

## 2026-08-11 — Stage 11: DEFAULT_MAX_CHANGE_PERCENTAGE prohibition and no arithmetic

**Decision:** `DEFAULT_MAX_CHANGE_PERCENTAGE` (`src/constants.py`) is never imported or
read by Stage 11 — only the already-validated `review.default_max_change_percentage` is
used, ensuring a caller-supplied `ReviewSetup` value is always respected instead of a
hard-coded module constant. Stage 11 performs no arithmetic, quantisation, or rounding:
it is a plain conditional selection, so no local `Decimal` context is used and the
result is unaffected by any global `Decimal` context a caller may have mutated. Stage 11
remains fully independent of Stage 10 — it never reads `current_budget`,
`minimum_budget`, `maximum_budget`, `room_to_static_maximum`, or
`room_to_static_minimum`, and never calls `calculate_campaign_static_budget_room` (or
vice versa); the two facts are never combined into one result or one call. `is_protected`,
`is_test_campaign`, and `test_budget_floor` are likewise never read — changing any of
them while holding the three authorised fields constant never changes the result. This
does not authorise any protected-campaign or test-campaign budget behaviour; those
rules, along with the percentage monetary-cap formula and the full effective-constraint
precedence, remain deferred to later stages.
**Status:** Frozen.

## 2026-08-11 — Stage 11: one Stage 10 AST scope-boundary test narrowed by explicit approval

**Decision:** Implementing the approved Stage 11 specification required importing
`ReviewSetup` (`src.models`) into `src/constraints.py`. This broke a pre-existing
assertion in `tests/test_constraints.py` —
`test_module_does_not_import_out_of_scope_modules` — which had forbidden that exact
import because, when Stage 10 was written, `src/constraints.py` legitimately had no
reason to import it. This was identified as a genuine conflict and reported before any
test file was touched, mirroring the precedent set by Stages 7, 8, and 9's equivalent
narrowings. With explicit approval, only `"ReviewSetup"` was removed from that one
test's `forbidden_imports` set; every other forbidden entry (`src.classification`,
`src.metrics`, `src.pacing`, `src.scoring`, `src.allocation`, `src.conservation`,
`CampaignMetrics`, `CampaignPacing`, `PerformanceBand`, `TrendDirection`, `Confidence`,
`TrackingStatus`, `CampaignTrackingAssessment`, `PacingStatus`, `RecommendationAction`,
`ReasonCode`, and — critically — `DEFAULT_MAX_CHANGE_PERCENTAGE`) remains unchanged and
still enforced. All 25 of Stage 10's existing tests in `tests/test_constraints.py` were
preserved unmodified; only this one assertion's forbidden-name set was narrowed.
**Status:** Frozen.

## 2026-08-11 — Stage 12 is a raw, informational percentage-based monetary movement-cap fact only

**Decision:** Sprint 1, Development Stage 12 adds a narrow, deterministic raw
percentage-based monetary movement-cap calculation to `src/constraints.py`, as an
*addition* alongside Stage 10's `CampaignStaticBudgetRoom`/
`calculate_campaign_static_budget_room` and Stage 11's
`CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage` —
not a modification of either. For one already-validated `CampaignInput` and its
already-resolved Stage 11 result, it calculates `current_budget *
applicable_max_change_percentage`, quantised once to `CURRENCY_QUANTUM` using
`ROUND_HALF_UP`. This is explicitly **not** permission to increase or decrease a
campaign's budget, an effective/final permissible movement, a static-bound
intersection, a protection or test-budget-floor determination, an eligibility result,
a score, a recommendation, a reason code, or an allocation — those all remain deferred
to a later effective-constraint stage.
**Status:** Frozen.

## 2026-08-11 — Stage 12: exact model, function, campaign-ID matching, and input ownership

**Decision:** `CampaignRawPercentageMovementCap` (frozen, immutable; `extra="forbid"`;
exactly `campaign_id`, `raw_percentage_movement_cap`) is defined in
`src/constraints.py`, alongside but fully separate from `CampaignStaticBudgetRoom` and
`CampaignApplicableChangePercentage`. The sole public function is
`calculate_campaign_raw_percentage_movement_cap(campaign: CampaignInput,
applicable_percentage: CampaignApplicableChangePercentage) ->
CampaignRawPercentageMovementCap`; it reads only `campaign.campaign_id`,
`campaign.current_budget`, `applicable_percentage.campaign_id`, and
`applicable_percentage.applicable_max_change_percentage`. Stage 12 consumes Stage 11's
already-resolved result directly, by design: it never accepts `ReviewSetup`, never
reads `campaign.campaign_max_change_percentage` or
`review.default_max_change_percentage`, never imports `DEFAULT_MAX_CHANGE_PERCENTAGE`,
and never calls `resolve_campaign_applicable_change_percentage` internally — this
avoids duplicating Stage 11's override/default precedence logic in a second place.
Before calculating, `campaign.campaign_id == applicable_percentage.campaign_id` is
required; a mismatch raises `ValueError("campaign_id mismatch between campaign and
applicable percentage")` and no result is returned — the two input objects
independently identify a campaign, and silently applying one campaign's percentage to
another would be unsafe.
**Status:** Frozen.

## 2026-08-11 — Stage 12: operand-derived Decimal precision policy (double-rounding bug found and fixed pre-implementation)

**Decision:** Before implementing Stage 12, the fixed `prec=28` local-context pattern
used by Stages 3, 4, and 10 was investigated rather than assumed safe, per explicit
instruction. This investigation found a genuine, reproducible double-rounding bug:
`CampaignInput.current_budget` has no upper bound (only the `Currency` type's own
construction-time `quantize()` call limits it — empirically confirmed to cap out at 28
significant digits under the default, unmutated global `Decimal` context), and
`applicable_max_change_percentage` has no digit-count restriction beyond `gt=0, le=1`.
With `current_budget = Decimal("99999999999999999999999999.99")` (28 significant
digits — the maximum `Currency` can hold under the default context) and
`applicable_max_change_percentage = Decimal("0.036020245307579938554529107051")` (a
legitimately constructible override), both independently valid under existing,
unmodified `CampaignInput` validation, a fixed `prec=28` local context rounds the
*intermediate multiplication* before the explicit final `.quantize()` call ever runs,
incorrectly returning `Decimal("...52910.71")`; the mathematically exact, correctly
rounded result is `Decimal("...52910.70")` — a one-penny error, confirmed stable under
progressively larger precision buffers. The approved fix derives the local context's
precision from the operands' own digit counts:
```
operand_digits = len(current_budget.as_tuple().digits) + len(applicable_max_change_percentage.as_tuple().digits)
safe_precision = max(28, operand_digits + 4)
```
This guarantees the multiplication is computed exactly (an *n*-digit value times an
*m*-digit value never needs more than *n+m* significant digits to represent exactly),
leaving the explicit `.quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)` call as the
sole rounding operation. The `max(28, ...)` floor preserves the repository's
established baseline precision for ordinary operands. No new maximum budget or
percentage digit restriction was introduced, and `CampaignInput`/`Currency` validation
was not modified or weakened. The local context is scoped entirely inside the
function's `with localcontext() as ctx:` block; the ambient global `Decimal` context is
never mutated and is provably unaffected (regression-tested both for the extreme case
and for an ordinary case, including confirming the global context's `prec`/`rounding`
are unchanged after the function returns).
**Status:** Frozen.

## 2026-08-11 — Stage 12: zero/None behaviour, Stage 10 separation, and protected/test exclusion

**Decision:** Neither `current_budget` nor `applicable_max_change_percentage` may be
`None` at Stage 12 (both are guaranteed present by Stages 1 and 11); no fallback value
is substituted for either. `current_budget` may be exactly `Decimal("0.00")`, in which
case the result is `Decimal("0.00")` — a legitimate raw cap, not an eligibility
judgement or error; no truthiness-based fallback is used anywhere.
`calculate_campaign_raw_percentage_movement_cap` never reads `minimum_budget`,
`maximum_budget`, `room_to_static_maximum`, or `room_to_static_minimum`, and never
calls `calculate_campaign_static_budget_room` (or vice versa) — a campaign at a static
boundary may still have a non-zero raw percentage cap, since the two facts are never
intersected here. `is_protected`, `is_test_campaign`, and `test_budget_floor` are
likewise never read — changing any of them while holding the four authorised fields
constant never changes the result. This does not authorise any protected-campaign or
test-campaign budget behaviour; those rules, the static-bound intersection, and the
full effective-constraint precedence remain deferred to later stages. No existing test
file required modification for Stage 12 — no approved AST-narrowing exception was
needed, since `CURRENCY_QUANTUM` was not previously forbidden and no new out-of-scope
name needed importing.
**Status:** Frozen.

## 2026-08-11 — Stage 13 is a raw, informational test-floor distance fact only

**Decision:** Sprint 1, Development Stage 13 adds a narrow, deterministic test-floor
distance calculation to `src/constraints.py`, as an *addition* alongside Stage 10's
`CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room`, Stage 11's
`CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
and Stage 12's `CampaignRawPercentageMovementCap`/
`calculate_campaign_raw_percentage_movement_cap` — not a modification of any of them.
For one already-validated `CampaignInput`, it calculates `current_budget -
test_budget_floor` for test campaigns only. This is explicitly **not** the effective
floor, **not** an alternative or additional minimum, **not** permissible decrease,
**not** an effective directional constraint, and is **never** combined with
`minimum_budget`, Stage 10's static room, or Stage 12's raw percentage movement cap.
This approval fixes only the raw distance formula — it does **not** decide whether the
eventual effective floor is `minimum_budget`, `test_budget_floor`, `max(minimum_budget,
test_budget_floor)`, or another formulation; that precedence remains an open decision
for a later stage.
**Status:** Frozen.

## 2026-08-11 — Stage 13: exact model, function, four authorised fields, and non-test None behaviour

**Decision:** `CampaignTestFloorRoom` (frozen, immutable; `extra="forbid"`; exactly
`campaign_id: str`, `room_to_test_floor: Decimal | None`) is defined in
`src/constraints.py`, alongside but fully separate from `CampaignStaticBudgetRoom`,
`CampaignApplicableChangePercentage`, and `CampaignRawPercentageMovementCap`. The sole
public function is `calculate_campaign_test_floor_room(campaign: CampaignInput) ->
CampaignTestFloorRoom`; it reads only `campaign.campaign_id`,
`campaign.is_test_campaign`, `campaign.current_budget`, and
`campaign.test_budget_floor` — never `minimum_budget`, `maximum_budget`,
`is_protected`, `campaign_max_change_percentage`, `platform`, `kpi_type`,
`ReviewSetup`, or any Stage 3–9/Stage 10–12 result, and never calls
`calculate_campaign_static_budget_room`,
`resolve_campaign_applicable_change_percentage`, or
`calculate_campaign_raw_percentage_movement_cap`. Exact rule:
```
is_test_campaign == True  → room_to_test_floor = current_budget - test_budget_floor
is_test_campaign == False → room_to_test_floor = None
```
For a non-test campaign, the function returns `room_to_test_floor=None` without
raising an error, without revalidating or reconstructing `CampaignInput`, and without
any new business-rule validator — `None` is an explicit statement that the fact does
not apply, never a fallback value, never `Decimal("0.00")`, never an error.
`test_budget_floor` is never read for arithmetic when `is_test_campaign` is `False`
(the function returns before reaching the subtraction). Zero is a legitimate result:
`current_budget == test_budget_floor` produces `Decimal("0.00")`, not an error,
eligibility decision, or permission judgement.
**Status:** Frozen.

## 2026-08-11 — Stage 13: Decimal policy (fixed prec=28, not Stage 12's operand-derived policy)

**Decision:** The subtraction runs inside a fixed local `decimal.localcontext()`
(`prec=28`, `rounding=ROUND_HALF_UP`), matching Stage 10's established defensive
policy — **not** Stage 12's operand-derived precision policy, since subtracting two
already-quantised `Currency` values never needs more significant digits than the
larger operand already has (unlike Stage 12's multiplication, whose result can need
more digits than either operand alone). This was verified empirically before
implementation: `current_budget` at the maximum digit count `Currency` can hold under
the default global context (`Decimal("99999999999999999999999999.99")`, 28
significant digits) subtracted against both `Decimal("0.00")` and a non-zero floor
produces an exact result with every significant whole-number digit preserved, under
fixed `prec=28`. Neither operand is re-quantised before the subtraction, and the
result is not re-quantised afterward — the two-decimal-place exponent already
produced by subtracting two already-quantised values is preserved exactly. The global
`Decimal` context is never mutated and is unaffected by the function call
(regression-tested, including confirming the global context's `prec`/`rounding` are
unchanged after the function returns).
**Status:** Frozen.

## 2026-08-11 — Stage 13: separation from Stages 10–12, protection independence, and deferred precedence

**Decision:** `calculate_campaign_test_floor_room` never reads
`room_to_static_maximum`, `room_to_static_minimum`, `applicable_max_change_percentage`,
or `raw_percentage_movement_cap`, and never calls any Stage 10–12 function (or vice
versa) — the four facts are never combined into one result or one call.
`is_protected` is never read — changing it while holding the four authorised fields
constant never changes the result; this does not approve any protected-campaign
movement mechanism. The effective-floor precedence, the static-room/raw-cap/test-floor
intersection (now a genuine three-way combination once Stage 13 exists), and
protected-campaign handling all remain deferred to later stages. No existing test file
required modification for Stage 13 — no approved AST-narrowing exception was needed,
since Stage 13 introduces no new import beyond what `src/constraints.py` already had
available.
**Status:** Frozen.

## 2026-08-11 — Stage 14 is a neutral, decrease-specific protection constraint only

**Decision:** Sprint 1, Development Stage 14 adds a narrow, deterministic protection
constraint to `src/constraints.py`, as an *addition* alongside Stage 10's
`CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room`, Stage 11's
`CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
Stage 12's `CampaignRawPercentageMovementCap`/
`calculate_campaign_raw_percentage_movement_cap`, and Stage 13's
`CampaignTestFloorRoom`/`calculate_campaign_test_floor_room` — not a modification of
any of them. For one already-validated `CampaignInput`, it states
`decrease_blocked = campaign.is_protected`. This is explicitly **not** an eligibility
decision, a recommendation, a monetary movement amount, permissible decrease, an
effective directional limit, or an increase-side constraint, and is **never** combined
with Stages 10–13.
**Status:** Frozen.

## 2026-08-11 — Stage 14: exact model, function, two authorised fields, and Boolean representation

**Decision:** `CampaignProtectionConstraint` (frozen, immutable; `extra="forbid"`;
exactly `campaign_id: str`, `decrease_blocked: bool`) is defined in
`src/constraints.py`, alongside but fully separate from `CampaignStaticBudgetRoom`,
`CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`, and
`CampaignTestFloorRoom`. The sole public function is
`resolve_campaign_protection_constraint(campaign: CampaignInput) ->
CampaignProtectionConstraint`; it reads only `campaign.campaign_id` and
`campaign.is_protected` — never `current_budget`, `minimum_budget`,
`maximum_budget`, `is_test_campaign`, `test_budget_floor`,
`campaign_max_change_percentage`, `platform`, `kpi_type`, `ReviewSetup`, or any Stage
3–9/Stage 10–13 result, and never calls any Stage 10–13 function. Exact mapping:
`decrease_blocked = campaign.is_protected` (`True → True`, `False → False`). `False`
is a meaningful result, never converted to `None`; no truthiness-based fallback is
used.
**Reason for rejecting a Decimal/`None` room representation:** `is_protected` is
explicitly defined as meaning the campaign "must never be reduced"
(`docs/DATA_DICTIONARY.md`). A Boolean preserves that rule directly, without
prematurely translating it into a monetary "room" amount (`Decimal("0.00")`/`None`,
as the Stage 14 inspection had tentatively proposed) — the exact numeric
representation, if any is ever needed, is deferred to whichever later stage actually
combines protection with Stage 10/12/13's monetary facts, avoiding a premature and
potentially incorrect translation now.
**Status:** Frozen.

## 2026-08-11 — Stage 14: no Decimal policy, decrease-only scope, and deferred combination

**Decision:** Stage 14 performs no `Decimal` calculation whatsoever — no `Decimal`
import, no local `decimal` context, no `CURRENCY_QUANTUM`, no `ROUND_HALF_UP`, no
rounding, no quantisation, and no `float` conversion anywhere in the addition; it is a
plain boolean selection. `decrease_blocked=False` means only that protection itself
does not prohibit a decrease — it is **not** permission to reduce the campaign's
budget, since other constraints (static bounds, the percentage cap, test-floor rules)
may still apply once resolved. `decrease_blocked=True` means only that protection
prohibits a decrease — it does **not** determine eligibility, recommendation action,
allocation, or any other judgement. The frozen `is_protected` meaning is explicitly
decrease-specific; Stage 14 makes no statement about increases, which remain entirely
unaddressed rather than assumed permitted or blocked.
`resolve_campaign_protection_constraint` never reads any Stage 10–13 field and never
calls any Stage 10–13 function (or vice versa) — the five facts are never combined
into one result or one call. The effective-floor precedence, the static-room/raw-cap/
test-floor/protection intersection (now a genuine four-way combination once Stage 14
exists), and all later constraint/eligibility/scoring/recommendation/allocation logic
remain deferred to later stages. No existing test file required modification for
Stage 14 — no approved AST-narrowing exception was needed, since Stage 14 introduces
no new import beyond what `src/constraints.py` already had available.
**Status:** Frozen.

## 2026-08-11 — Stage 15: test_budget_floor approved as an additional retained-spend floor for test campaigns

**Decision:** Sprint 1, Development Stage 15 approves the first constraints-domain
business precedence rule: for a test campaign, `test_budget_floor` is an *additional*
retained-spend floor alongside `minimum_budget` — not an alternative that replaces
it, and not a decrease-only-vs-general distinction left unresolved. The **higher**
monetary floor controls (`effective_decrease_floor = max(minimum_budget,
test_budget_floor)`), equivalently expressed as the **smaller** of the two
already-calculated rooms (`min(room_to_static_minimum, room_to_test_floor)`) via the
identity `c - max(a, b) = min(c - a, c - b)`. A non-test campaign is constrained only
by `minimum_budget` at this stage (`test_aware_static_decrease_room =
room_to_static_minimum`). This resolves the precedence question every prior Stage
10–14 addition deliberately deferred (see each stage's own decision entries above).
The result remains a **raw, test-aware static constraint only** — not permissible
decrease, not an effective decrease limit, and it does not mean the campaign should
be reduced. It does not account for Stage 12's percentage cap or Stage 14's
protection constraint.
**Status:** Frozen.

## 2026-08-11 — Stage 15: exact model, function, and consumption of Stage 10/13 outputs (not recalculation)

**Decision:** `CampaignTestAwareStaticDecreaseRoom` (frozen, immutable;
`extra="forbid"`; exactly `campaign_id: str`, `test_aware_static_decrease_room:
Decimal`) is defined in `src/constraints.py`, alongside but fully separate from
`CampaignStaticBudgetRoom`, `CampaignApplicableChangePercentage`,
`CampaignRawPercentageMovementCap`, `CampaignTestFloorRoom`, and
`CampaignProtectionConstraint`. The sole public function is
`resolve_campaign_test_aware_static_decrease_room(static_room:
CampaignStaticBudgetRoom, test_floor_room: CampaignTestFloorRoom) ->
CampaignTestAwareStaticDecreaseRoom`; it reads only `static_room.campaign_id`,
`static_room.room_to_static_minimum`, `test_floor_room.campaign_id`, and
`test_floor_room.room_to_test_floor`. **Stage 15 consumes Stage 10's and Stage 13's
already-approved result objects directly, rather than reading `CampaignInput` and
recalculating either room** — it never accepts or reads `CampaignInput`, and never
calls `calculate_campaign_static_budget_room` or `calculate_campaign_test_floor_room`.
This avoids duplicating either stage's already-tested calculation in a second place,
consistent with the same reasoning that led Stage 12 to consume Stage 11's result
rather than re-resolving percentage precedence itself. Exact formula:
```
room_to_test_floor is None  → test_aware_static_decrease_room = room_to_static_minimum
otherwise                   → test_aware_static_decrease_room = min(room_to_static_minimum, room_to_test_floor)
```
Before resolving any monetary result, `static_room.campaign_id` must equal
`test_floor_room.campaign_id`; a mismatch raises exactly `ValueError("Campaign IDs
must match when resolving test-aware static decrease room.")`, checked as the first
statement in the function body, with no result returned and neither ID silently
preferred.
**Status:** Frozen.

## 2026-08-11 — Stage 15: None/zero behaviour, no-arithmetic Decimal policy, and separation from Stages 11, 12, 14

**Decision:** `room_to_test_floor is None` (non-test campaigns) resolves to
`room_to_static_minimum` unchanged — never replaced with `Decimal("0.00")`; the
Stage 15 output itself is never `None`. `Decimal("0.00")` is a legitimate result when
the smaller applicable room is zero — it means there is no static room to reduce
under the combined floor rule, not an eligibility or recommendation judgement. Stage
15 performs selection and comparison only: no subtraction, multiplication, or
division; no local `decimal` context; no `CURRENCY_QUANTUM`; no `ROUND_HALF_UP`; no
rounding; no quantisation; no `float` conversion. The selected `Decimal` operand is
returned unchanged, and ambient global `Decimal` precision/rounding cannot affect the
result, since no arithmetic operation is performed at all.
`resolve_campaign_test_aware_static_decrease_room` never reads
`applicable_max_change_percentage`, `raw_percentage_movement_cap`, `decrease_blocked`,
or `is_protected`, and never calls `resolve_campaign_applicable_change_percentage`,
`calculate_campaign_raw_percentage_movement_cap`, or
`resolve_campaign_protection_constraint` (or vice versa) — a protected campaign
receives exactly the same Stage 15 result as an otherwise identical unprotected
campaign with matching Stage 10/13 facts; no protection-based zero is calculated
here. The percentage-cap intersection, protection application, raw increase
intersection, effective directional constraints, and all later
eligibility/scoring/recommendation/allocation logic remain deferred to later stages.
No existing test file required modification for Stage 15 — no approved AST-narrowing
exception was needed, since Stage 15 introduces no new import beyond what
`src/constraints.py` already had available.
**Status:** Frozen.

## 2026-08-14 — Stage 16: both upward constraints apply simultaneously; the smaller controls

**Decision:** Sprint 1, Development Stage 16 approves the raw increase limit business
rule: `room_to_static_maximum` (Stage 10) and `raw_percentage_movement_cap` (Stage
12) are two independent upward constraints that apply simultaneously — the smaller of
the two is the binding limit: `raw_increase_limit = min(room_to_static_maximum,
raw_percentage_movement_cap)`. The result is a **raw, increase-specific constraint
only** — not permission to increase a budget, not an effective increase, not
eligibility, not a recommendation, and not a final movement amount. It does not
account for a raw decrease limit, Stage 14's protection constraint, or Stage 15's
test-aware static decrease room.
**Status:** Frozen.

## 2026-08-14 — Stage 16: exact model, function, and consumption of Stage 10/12 outputs (not recalculation)

**Decision:** `CampaignRawIncreaseLimit` (frozen, immutable; `extra="forbid"`;
exactly `campaign_id: str`, `raw_increase_limit: Decimal`) is defined in
`src/constraints.py`, alongside but fully separate from `CampaignStaticBudgetRoom`,
`CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`,
`CampaignTestFloorRoom`, `CampaignProtectionConstraint`, and
`CampaignTestAwareStaticDecreaseRoom`. The sole public function is
`resolve_campaign_raw_increase_limit(static_room: CampaignStaticBudgetRoom, raw_cap:
CampaignRawPercentageMovementCap) -> CampaignRawIncreaseLimit`; it reads only
`static_room.campaign_id`, `static_room.room_to_static_maximum`,
`raw_cap.campaign_id`, and `raw_cap.raw_percentage_movement_cap`. **Stage 16 consumes
Stage 10's and Stage 12's already-approved result objects directly, rather than
reading `CampaignInput`/`ReviewSetup` and recalculating either fact** — it never
calls `calculate_campaign_static_budget_room` or
`calculate_campaign_raw_percentage_movement_cap`, consistent with the consumption
pattern established at Stage 12 (consuming Stage 11) and reaffirmed at Stage 15
(consuming Stage 10/13). Exact formula:
```
raw_increase_limit = min(room_to_static_maximum, raw_percentage_movement_cap)
```
Before resolving any Decimal selection, `static_room.campaign_id` must equal
`raw_cap.campaign_id`; a mismatch raises exactly `ValueError("Campaign IDs must
match when resolving raw increase limit.")`, checked as the first statement in the
function body, with no result returned and neither ID silently preferred.
**Status:** Frozen.

## 2026-08-14 — Stage 16: zero/None behaviour, no-arithmetic Decimal policy, and separation from Stages 11, 13, 14, and 15

**Decision:** `Decimal("0.00")` is a legitimate result when the smaller applicable
constraint is zero (including when `room_to_static_maximum` is zero,
`raw_percentage_movement_cap` is zero, or both are zero) — it means no raw increase
room remains under these two constraints, not eligibility or a recommendation.
Neither input field is optional, and the output is never `None`. Stage 16 performs
selection and comparison only: no subtraction, multiplication, or division; no local
`decimal` context; no `CURRENCY_QUANTUM`; no `ROUND_HALF_UP`; no rounding; no
quantisation; no `float` conversion. The selected `Decimal` operand is returned
unchanged, and ambient global `Decimal` precision/rounding cannot affect the result,
since no arithmetic operation is performed at all.
`resolve_campaign_raw_increase_limit` never reads `applicable_max_change_percentage`,
`room_to_test_floor`, `decrease_blocked`, or `test_aware_static_decrease_room`, and
never calls `resolve_campaign_applicable_change_percentage`,
`calculate_campaign_test_floor_room`, `resolve_campaign_protection_constraint`, or
`resolve_campaign_test_aware_static_decrease_room` (or vice versa) — a protected
campaign receives exactly the same Stage 16 result as an otherwise identical
unprotected campaign with matching Stage 10/12 facts; no protection-based or
test-floor-based zero is calculated here, and **no increase-side protection rule is
inferred** — a protected campaign is not thereby assumed unable to be increased. The
raw decrease intersection, protection application, effective directional
constraints, and all later eligibility/scoring/recommendation/allocation logic
remain deferred to later stages. No existing test file required modification for
Stage 16 — no approved AST-narrowing exception was needed, since Stage 16 introduces
no new import beyond what `src/constraints.py` already had available.
**Status:** Frozen.

## 2026-08-14 — Stage 17: both decrease-side constraints apply simultaneously; the smaller controls

**Decision:** Sprint 1, Development Stage 17 approves the raw decrease limit
business rule: `test_aware_static_decrease_room` (Stage 15) and
`raw_percentage_movement_cap` (Stage 12) are two independent decrease-side
constraints that apply simultaneously — the smaller of the two is the binding
limit: `raw_decrease_limit = min(test_aware_static_decrease_room,
raw_percentage_movement_cap)`. The result is a **raw, decrease-specific constraint
only** — not permission to decrease a budget, not an effective decrease, not
eligibility, not a recommendation, and not a final movement amount. A protected
campaign still receives its neutral Stage 17 raw result; Stage 14's protection
constraint is not applied until a later effective-constraint stage. It does not
combine with Stage 16's raw increase limit.
**Status:** Frozen.

## 2026-08-14 — Stage 17: exact model, function, and consumption of Stage 12/15 outputs (not recalculation)

**Decision:** `CampaignRawDecreaseLimit` (frozen, immutable; `extra="forbid"`;
exactly `campaign_id: str`, `raw_decrease_limit: Decimal`) is defined in
`src/constraints.py`, alongside but fully separate from `CampaignStaticBudgetRoom`,
`CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`,
`CampaignTestFloorRoom`, `CampaignProtectionConstraint`,
`CampaignTestAwareStaticDecreaseRoom`, and `CampaignRawIncreaseLimit`. The sole
public function is `resolve_campaign_raw_decrease_limit(decrease_room:
CampaignTestAwareStaticDecreaseRoom, raw_cap: CampaignRawPercentageMovementCap) ->
CampaignRawDecreaseLimit`; it reads only `decrease_room.campaign_id`,
`decrease_room.test_aware_static_decrease_room`, `raw_cap.campaign_id`, and
`raw_cap.raw_percentage_movement_cap`. **Stage 17 consumes Stage 15's and Stage 12's
already-approved result objects directly, rather than reading
`CampaignInput`/`ReviewSetup` and recalculating either fact** — it never calls
`resolve_campaign_test_aware_static_decrease_room` or
`calculate_campaign_raw_percentage_movement_cap`, and never reopens
`minimum_budget`, `test_budget_floor`, `is_test_campaign`, `room_to_static_minimum`,
`room_to_test_floor`, `current_budget`, or `applicable_max_change_percentage`,
consistent with the consumption pattern established at Stage 12 (consuming Stage
11), Stage 15 (consuming Stage 10/13), and Stage 16 (consuming Stage 10/12). Exact
formula:
```
raw_decrease_limit = min(test_aware_static_decrease_room, raw_percentage_movement_cap)
```
Before resolving any Decimal selection, `decrease_room.campaign_id` must equal
`raw_cap.campaign_id`; a mismatch raises exactly `ValueError("Campaign IDs must
match when resolving raw decrease limit.")`, checked as the first statement in the
function body, with no result returned and neither ID silently preferred.
**Status:** Frozen.

## 2026-08-14 — Stage 17: zero/negative/None behaviour, no-arithmetic Decimal policy, and separation from Stages 10, 11, 13, 14, and 16

**Decision:** `Decimal("0.00")` is a legitimate result when the smaller applicable
constraint is zero (including when `test_aware_static_decrease_room` is zero,
`raw_percentage_movement_cap` is zero, or both are zero) — it means no raw decrease
room remains under these two constraints, not protection, eligibility, or a
recommendation. A negative result is structurally impossible: both inputs are
guaranteed non-negative by their own upstream Stage 10/12/13/15 invariants, and
`min()` of two non-negative Decimals is non-negative. Neither input field is
optional, and the output is never `None`. Stage 17 performs selection and
comparison only: no subtraction, multiplication, or division; no local `decimal`
context; no `CURRENCY_QUANTUM`; no `ROUND_HALF_UP`; no rounding; no quantisation; no
`float` conversion. The selected `Decimal` operand is returned unchanged, and
ambient global `Decimal` precision/rounding cannot affect the result, since no
arithmetic operation is performed at all.
`resolve_campaign_raw_decrease_limit` never reads `room_to_static_maximum`,
`room_to_static_minimum`, `applicable_max_change_percentage`, `room_to_test_floor`,
`decrease_blocked`, `is_protected`, or `raw_increase_limit`, and never calls
`calculate_campaign_static_budget_room`,
`resolve_campaign_applicable_change_percentage`,
`calculate_campaign_test_floor_room`, `resolve_campaign_protection_constraint`, or
`resolve_campaign_raw_increase_limit` (or vice versa) — a protected campaign
receives exactly the same Stage 17 result as an otherwise identical unprotected
campaign with matching Stage 12/15 facts; no protection-based zero is calculated
here, and the result is **never described as usable or permissible decrease** for a
protected campaign. Test-campaign status affects Stage 17 only indirectly, through
Stage 15's already-resolved `test_aware_static_decrease_room` value — Stage 17
itself never reads `is_test_campaign` or `test_budget_floor`, and Stage 15's
stricter-floor precedence is not reopened. Protection application, a combined
increase/decrease model, effective directional constraints, and all later
eligibility/scoring/recommendation/allocation logic remain deferred to later
stages. No existing test file required modification for Stage 17 — no approved
AST-narrowing exception was needed, since Stage 17 introduces no new import beyond
what `src/constraints.py` already had available.
**Status:** Frozen.

## 2026-08-14 — Stage 18 is protection-adjusted effective decrease only; no effective increase field is created

**Decision:** Sprint 1, Development Stage 18 applies Stage 14's
`CampaignProtectionConstraint` to Stage 17's `CampaignRawDecreaseLimit`, producing
one protection-adjusted effective decrease limit — `effective_decrease_limit =
Decimal("0.00")` when `decrease_blocked` is `True`, otherwise `raw_decrease_limit`
unchanged. This is **still not** eligibility, a recommendation, a final movement
amount, an allocation, or a decision to decrease the campaign — a campaign with
`effective_decrease_limit == Decimal("0.00")` may still later be eligible for
`MAINTAIN` or `INCREASE`. Stage 18 does **not** create
`CampaignEffectiveIncreaseLimit`, an `effective_increase_limit` field, or any
combined effective-directional result: no approved constraint remains to transform
Stage 16's raw increase limit, and protection has no approved increase-side effect,
so `CampaignRawIncreaseLimit` remains the authoritative increase-side constraint
unless a later approved rule changes it.
**Status:** Frozen.

## 2026-08-14 — Stage 18: Decimal("0.00") used instead of None for a protection-blocked decrease

**Decision:** When `decrease_blocked=True`, the effective decrease limit is
represented as `Decimal("0.00")`, not `None`. Every existing `None` in the
repository (Stage 4's `pacing_ratio`, Stage 13's `room_to_test_floor`) means "this
fact does not apply / could not be computed." A protection-triggered zero is the
opposite: a computed, deterministic decision that a definite quantity of decrease
room (zero) is available under this constraint. Using `None` here would misuse the
established non-applicability vocabulary; `Decimal("0.00")` correctly signals a
valid, deliberate effective constraint, consistent with the zero-is-meaningful
pattern already established at Stages 10, 12, 15, 16, and 17. `Decimal("0.00")` is
constructed as a literal using the existing `Decimal` import — no new `ZERO`
constant is added to `src/constants.py`, and `src/constants.py` is not modified.
**Status:** Frozen.

## 2026-08-14 — Stage 18: exact model, function, and consumption of Stage 14/17 outputs (not recalculation)

**Decision:** `CampaignEffectiveDecreaseLimit` (frozen, immutable; `extra="forbid"`;
exactly `campaign_id: str`, `effective_decrease_limit: Decimal`) is defined in
`src/constraints.py`, alongside but fully separate from `CampaignStaticBudgetRoom`,
`CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`,
`CampaignTestFloorRoom`, `CampaignProtectionConstraint`,
`CampaignTestAwareStaticDecreaseRoom`, `CampaignRawIncreaseLimit`, and
`CampaignRawDecreaseLimit`. The sole public function is
`resolve_campaign_effective_decrease_limit(raw_decrease: CampaignRawDecreaseLimit,
protection: CampaignProtectionConstraint) -> CampaignEffectiveDecreaseLimit`; it
reads only `raw_decrease.campaign_id`, `raw_decrease.raw_decrease_limit`,
`protection.campaign_id`, and `protection.decrease_blocked`. **Stage 18 consumes
Stage 17's and Stage 14's already-approved result objects directly, rather than
reading `CampaignInput`/`ReviewSetup` and recalculating either fact** — it never
calls `resolve_campaign_raw_decrease_limit` or
`resolve_campaign_protection_constraint`, and never reopens `is_protected`,
`current_budget`, `minimum_budget`, `maximum_budget`, `test_budget_floor`,
`is_test_campaign`, `applicable_max_change_percentage`, `room_to_static_minimum`,
`room_to_test_floor`, `test_aware_static_decrease_room`, or
`raw_percentage_movement_cap`, consistent with the consumption pattern established
at Stage 12 (consuming Stage 11), Stage 15 (consuming Stage 10/13), Stage 16
(consuming Stage 10/12), and Stage 17 (consuming Stage 12/15). Exact mapping:
```
effective_decrease_limit = (
    Decimal("0.00")
    if protection.decrease_blocked
    else raw_decrease.raw_decrease_limit
)
```
Before reading `decrease_blocked` for selection or resolving any Decimal result,
`raw_decrease.campaign_id` must equal `protection.campaign_id`; a mismatch raises
exactly `ValueError("Campaign IDs must match when resolving effective decrease
limit.")`, checked as the first statement in the function body, with no result
returned and neither ID silently preferred.
**Status:** Frozen.

## 2026-08-14 — Stage 18: True/False/zero/None behaviour, no-arithmetic Decimal/Boolean policy, and raw-fact preservation

**Decision:** `decrease_blocked=True` always produces exactly `Decimal("0.00")`,
regardless of whether `raw_decrease_limit` was positive, zero, or an extreme valid
monetary value — the zero uses the two-decimal currency exponent
(`Decimal("0.00")`, never `Decimal("0")`), is never `None`, and never raises.
`decrease_blocked=False` always returns `raw_decrease.raw_decrease_limit`
unchanged — not reconstructed, re-quantised, rounded, or copied through `float`.
Neither input field is optional, and the output is never `None`; no fallback value
is substituted. Stage 18 performs conditional selection only: no subtraction,
multiplication, or division; no local `decimal` context; no `CURRENCY_QUANTUM`; no
`ROUND_HALF_UP`; no rounding; no quantisation; no `float` conversion. Ambient
global `Decimal` precision/rounding cannot affect either branch, since no
arithmetic operation is performed.
`CampaignEffectiveDecreaseLimit` does not repeat `raw_decrease_limit` or
`decrease_blocked` as fields, and Stage 18 does not mutate either input (both are
`frozen=True`, and Stage 18 constructs an entirely new result object) — a caller
retains full traceability by holding `CampaignProtectionConstraint` (Stage 14),
`CampaignRawDecreaseLimit` (Stage 17), and `CampaignEffectiveDecreaseLimit` (Stage
18) as three separate, independently-inspectable objects. A campaign with
`effective_decrease_limit == Decimal("0.00")` does not imply whole-campaign
ineligibility — no eligibility field exists anywhere on the result, and
`MAINTAIN`/`INCREASE` eligibility remains an entirely open, later-stage question.
Effective increase, combined effective-directional constraints, eligibility, the
combined campaign-assessment question, scoring, `RecommendationAction`,
`ReasonCode`, allocation, and conservation all remain deferred to later stages. No
existing test file required modification for Stage 18 — no approved AST-narrowing
exception was needed, since Stage 18 introduces no new import beyond what
`src/constraints.py` already had available.
**Status:** Frozen.
