# Decision Rules

> Sprint 1, Development Stage 17. Records the frozen enumerations, frozen numerical
> constants, the frozen deterministic validation rules, the frozen deterministic
> metric-calculation rules, the frozen deterministic pacing-calculation rules, the frozen
> neutral performance-, trend-, conversion-volume-confidence-, and
> tracking-assessability-classification rules, the frozen neutral pacing-interpretation
> rules, the frozen static budget-bound calculation rules, the frozen applicable-
> change-percentage resolution rule, the frozen raw percentage-based monetary
> movement-cap calculation rule, the frozen test-floor distance calculation rule, the
> frozen protection constraint rule, the frozen test-aware static decrease-room rule,
> the frozen raw increase limit rule, and the frozen raw decrease limit rule. Combined
> assessment, `Confidence.NOT_ASSESSABLE` ownership, protection application, combined
> directional limits, effective constraints, eligibility, scoring, and allocation
> rules are pending later Sprint 1 stages.

## Approved Enumerations (`src/constants.py`)

| Enum | Members and exact values |
|------|---------------------------|
| `Platform` | `GOOGLE_ADS = "Google Ads"`, `META_ADS = "Meta Ads"` |
| `KPIType` | `CPA = "CPA"`, `ROAS = "ROAS"` |
| `CampaignStatus` | `ACTIVE = "Active"`, `PAUSED = "Paused"` |
| `TrackingStatus` | `HEALTHY = "Healthy"`, `WARNING = "Warning"`, `UNRELIABLE = "Unreliable"` |
| `BusinessPriority` | `STANDARD = "Standard"`, `MEDIUM = "Medium"`, `HIGH = "High"` |
| `RecommendationAction` | `INCREASE = "INCREASE"`, `MAINTAIN = "MAINTAIN"`, `REDUCE = "REDUCE"`, `HOLD = "HOLD"` |
| `Confidence` | `HIGH = "HIGH"`, `MEDIUM = "MEDIUM"`, `LOW = "LOW"`, `NOT_ASSESSABLE = "NOT_ASSESSABLE"` |
| `ReviewStatus` | `DRAFT = "DRAFT"`, `PENDING_APPROVAL = "PENDING_APPROVAL"`, `APPROVED = "APPROVED"`, `REJECTED = "REJECTED"` |
| `ValidationSeverity` | `ERROR = "ERROR"`, `WARNING = "WARNING"` |
| `ReasonCode` | `ABOVE_TARGET_STRONG`, `BELOW_TARGET_MODERATE`, `BELOW_TARGET_SEVERE`, `NEAR_TARGET`, `RECENT_TREND_IMPROVING`, `RECENT_TREND_STABLE`, `RECENT_TREND_DECLINING`, `INSUFFICIENT_CONVERSION_VOLUME`, `TRACKING_UNRELIABLE`, `TRACKING_WARNING`, `PROTECTED_FROM_REDUCTION`, `TEST_BUDGET_FLOOR_APPLIED`, `MAX_CHANGE_LIMIT_APPLIED`, `CAMPAIGN_CAP_REACHED`, `CAMPAIGN_FLOOR_REACHED`, `PAUSED_CAMPAIGN`, `NO_ELIGIBLE_RECIPIENT`, `HELD_FOR_MANUAL_REVIEW`, `STRONG_LONG_TERM_RECENT_DECLINE`, `ACCOUNT_RESERVE_REQUIRED` (each member's value is identical to its name) |

`Platform`, `CampaignStatus`, `TrackingStatus`, and `BusinessPriority` use approved
human-readable display strings as their values (matching the CSV schema); `KPIType` and all
other enums use their member name as the value.

## Frozen Numerical Constants (`src/constants.py`)

| Constant | Value |
|----------|-------|
| `DEFAULT_MAX_CHANGE_PERCENTAGE` | `Decimal("0.20")` |
| `TREND_THRESHOLD` | `Decimal("0.10")` |
| `SEVEN_DAY_WEIGHT` | `Decimal("0.40")` |
| `TWENTY_EIGHT_DAY_WEIGHT` | `Decimal("0.60")` |
| `INCREASE_THRESHOLD` | `Decimal("1.15")` |
| `MAINTAIN_THRESHOLD` | `Decimal("0.90")` |
| `MINIMUM_CONVERSIONS` | `10` |
| `HIGH_CONFIDENCE_CONVERSIONS` | `30` |
| `CURRENCY_QUANTUM` | `Decimal("0.01")` |
| `PACING_LOWER_THRESHOLD` | `Decimal("0.90")` |
| `PACING_UPPER_THRESHOLD` | `Decimal("1.10")` |

`PACING_LOWER_THRESHOLD`/`PACING_UPPER_THRESHOLD` are Stage 9's frozen pacing-status
thresholds — a symmetric ±10% on-pace tolerance band around `1.00`, applied to
`CampaignPacing.pacing_ratio` only (see the Stage 9 rules below). The remaining
constants are reserved names and values only; no classification, constraint, scoring,
allocation, or conservation logic reads or applies them yet — that is pending later
Sprint 1 stages.

## Validation Codes (`src/constants.py`)

| Code | Meaning |
|------|---------|
| `INVALID_REVIEW_FIELD` | A `ReviewSetup` field or cross-field rule was violated. |
| `EMPTY_FILE` | The campaign CSV stream contained no content at all. |
| `INVALID_HEADER` | The CSV header did not exactly match the required `CampaignInput` schema (missing, extra, renamed, reordered, or duplicate column). |
| `NO_CAMPAIGN_ROWS` | The header was valid but no data rows followed it. |
| `MALFORMED_ROW` | A data row had the wrong number of cells (missing or surplus). |
| `INVALID_CAMPAIGN_FIELD` | A `CampaignInput` field or cross-field rule was violated for a structurally well-shaped row. |
| `DUPLICATE_CAMPAIGN_ID` | The same `campaign_id` appeared in more than one structurally valid row. |

`ValidationCode` is distinct from `ReasonCode`: `ValidationCode` describes *input data*
problems found before any recommendation logic runs; `ReasonCode` (pending) will describe
*recommendation/allocation* outcomes. They are never reused for each other's purpose.

## Deterministic Validation Rules (Sprint 1, Development Stage 2)

These rules govern `src/validation.py`, which validates raw `ReviewSetup` input and
campaign CSV data. `ReviewSetup` and `CampaignInput` (`src/models.py`) remain the sole
authoritative source of structural rules — validation.py only invokes them and translates
their `pydantic.ValidationError` output into `ValidationIssue` records; it never
re-implements a rule they already enforce.

- **Header requirement.** The campaign CSV header must exactly equal the 20
  `CampaignInput` field names, in their model-definition order (derived at runtime from
  `CampaignInput.model_fields`, never hand-typed as a second list). Any mismatch —
  missing, extra, renamed, reordered, or duplicate column — produces exactly one
  `INVALID_HEADER` issue at `row_number=1`; no per-column issues are produced, and no row
  validation occurs after an invalid header (`valid_campaigns` is empty).
- **Physical line-number convention.** `row_number` is the physical one-based CSV line
  number: the header is line 1, the first data row is line 2, and so on. File-level and
  `ReviewSetup` issues use `row_number=None`.
- **Empty-file and no-row handling.** A completely empty stream (no header at all)
  produces one `EMPTY_FILE` issue. A stream with a valid header but zero data rows
  produces one `NO_CAMPAIGN_ROWS` issue — this is the expected outcome for
  `data/campaign_template.csv`, which is intentionally header-only. A row with the correct
  cell count but all-blank cells is not treated as "no row" — it is attempted and
  reported via `MALFORMED_ROW`/`INVALID_CAMPAIGN_FIELD` like any other row.
- **Pydantic models are the authoritative structural validators.** For each row,
  `validation.py` converts blank cells to `None` only for the two genuinely optional
  fields (`test_budget_floor`, `campaign_max_change_percentage`), then passes every other
  raw cell value through to `CampaignInput` unchanged. All numeric, enum, boolean,
  budget-bound, conversion-ordering, KPI, and test-budget-floor rules are enforced solely
  by the frozen `CampaignInput`/`ReviewSetup` validators — never duplicated here.
- **Invalid-row continuation.** One invalid row does not stop processing of later rows.
  Each `pydantic.ValidationError` on a row is translated into one `INVALID_CAMPAIGN_FIELD`
  issue per underlying error (so one row can produce multiple issues), the row is excluded
  from `valid_campaigns`, and processing continues.
- **Row-shape rejection.** A data row whose cell count does not equal 20 (missing or
  surplus cells) produces one `MALFORMED_ROW` issue and is not passed to `CampaignInput`.
- **campaign_id attribution.** Where a row has at least one cell, its first cell (trimmed)
  is attached to the issue's `campaign_id` — since `campaign_id` is always column 1, its
  position is stable even when the row is otherwise malformed or invalid.
- **Duplicate handling.** Duplicates are detected only among rows that successfully
  instantiated `CampaignInput` (structurally invalid rows never participate). Comparison
  uses the model's already-trimmed `campaign_id` and is case-sensitive (`CAMP001` and
  `camp001` are distinct). If an ID occurs more than once, every occurrence — not just the
  2nd and later — receives its own `DUPLICATE_CAMPAIGN_ID` issue at its own physical line
  number, and every occurrence is excluded from `valid_campaigns`. Non-duplicate valid
  rows are preserved in original CSV order.
- **Error-only severity policy for Stage 2.** Every issue Stage 2 produces has severity
  `ERROR`. No Stage-2-only `WARNING` rules exist. In particular, `TrackingStatus.WARNING`
  and `TrackingStatus.UNRELIABLE` are valid enum inputs, not validation warnings, and a
  protected or test-campaign state is valid whenever the existing frozen model rules pass.
  `ValidationReport.warning_count` is still generically derived from `issues` (so it would
  reflect a `WARNING`-severity issue if one ever existed), but it is `0` for every outcome
  Stage 2 currently produces.
- **No raw exception leakage.** Where a value is coercible to `Decimal` but an internal
  `decimal` operation (e.g. quantising an extreme value) raises a raw
  `decimal.DecimalException` rather than a `pydantic.ValidationError`, `validation.py`
  catches it and reports one safe, generic issue (`INVALID_REVIEW_FIELD` or
  `INVALID_CAMPAIGN_FIELD`) instead of leaking the internal exception. No other exception
  types are broadly suppressed.

## Deterministic Metric Calculation Rules (Sprint 1, Development Stage 3)

These rules govern `src/metrics.py`, which calculates performance-ratio **facts** for an
already-validated `CampaignInput`. Stage 3 calculates facts only — it never classifies,
scores, recommends, or assigns confidence. `CampaignInput` (`src/models.py`) remains the
sole authoritative source of the input guarantees these formulas rely on (`kpi_target > 0`,
`kpi_actual_7d > 0`, `kpi_actual_28d > 0`); `src/metrics.py` never re-validates them.

- **Direction-normalised performance ratio.** For `KPIType.ROAS` (higher actual is
  better): `ratio = kpi_actual / kpi_target`. For `KPIType.CPA` (lower actual is better):
  `ratio = kpi_target / kpi_actual`. Computed once for the 7-day window
  (`performance_ratio_7d`) and once for the 28-day window (`performance_ratio_28d`).
- **Uniform meaning across KPI types.** By construction, a ratio `> 1` always means
  performance better than target, `= 1` means exactly at target, and `< 1` means worse
  than target — identically for `CPA` and `ROAS`. **Higher ratio always means better
  performance for both KPI types.** This uniformity is the reason a single pair of
  thresholds (`INCREASE_THRESHOLD`, `MAINTAIN_THRESHOLD`) can later apply to both.
- **Weighted performance ratio.** `weighted_performance_ratio = performance_ratio_7d *
  SEVEN_DAY_WEIGHT + performance_ratio_28d * TWENTY_EIGHT_DAY_WEIGHT`, using the existing
  frozen `SEVEN_DAY_WEIGHT = Decimal("0.40")` and `TWENTY_EIGHT_DAY_WEIGHT =
  Decimal("0.60")` — a single blended performance fact, weighted toward the longer,
  more stable 28-day window.
- **Relative trend delta.** `trend_delta = (performance_ratio_7d -
  performance_ratio_28d) / performance_ratio_28d` — the *relative* (not absolute)
  change of the 7-day ratio versus the 28-day ratio. Positive means recent performance is
  better than the 28-day comparison; negative means worse; zero means unchanged.
  `trend_delta` is a numerical fact only — it is never compared against
  `TREND_THRESHOLD` and never turned into an `IMPROVING`/`STABLE`/`DECLINING` label
  inside `src/metrics.py`.
- **Decimal precision and rounding.** Every calculation runs inside an explicit
  `decimal.localcontext()` with `prec=28` and `rounding=ROUND_HALF_UP`, so behaviour is
  identical regardless of any global `Decimal` context a caller may have mutated. No
  result is quantised to a fixed number of decimal places (unlike currency fields, no
  `RATIO_QUANTUM`-style constant exists, and `CURRENCY_QUANTUM` is never applied to a
  ratio) — exact terminating results stay numerically exact, and repeating divisions are
  rounded only by the 28-significant-digit local context.
- **Platform independence.** The calculation depends only on `kpi_type`, `kpi_target`,
  `kpi_actual_7d`, and `kpi_actual_28d` — never on `platform`. The same formulas apply
  identically to Google Ads and Meta Ads campaigns.
- **No zero-denominator or missing-data handling needed.** `CampaignInput` already
  guarantees `kpi_target > 0`, `kpi_actual_7d > 0`, `kpi_actual_28d > 0`, and that all
  three are present — `src/metrics.py` performs no zero-guard, exception handling, or
  sentinel-value logic, and duplicates none of these validators.

## Deterministic Pacing Calculation Rules (Sprint 1, Development Stage 4)

These rules govern `src/pacing.py`, which calculates calendar and linear spend-pacing
**facts** for one already-validated `ReviewSetup` and one already-validated
`CampaignInput`. Stage 4 calculates facts only — it never classifies, labels, or assigns
a pacing status. `ReviewSetup` and `CampaignInput` (`src/models.py`) remain the sole
authoritative source of the input guarantees these formulas rely on
(`spend_to_date <= current_budget`, `period_end >= period_start`); `src/pacing.py` never
re-validates them. Stage 4 is independent of Stage 3: it never imports `CampaignMetrics`
and never uses `platform`, `kpi_type`, KPI actuals/targets, or any performance/trend/
conversion-volume constant.

- **Inclusive date counting.** `total_period_days = (period_end - period_start).days + 1`
  — both boundary days count, so a valid one-day review period (`period_start ==
  period_end`, already permitted by `ReviewSetup`) gives `total_period_days = 1`, never a
  zero denominator.
- **Elapsed-day clamping.** `raw_elapsed_days = (review_date - period_start).days + 1`,
  then `elapsed_days = min(max(raw_elapsed_days, 0), total_period_days)`. `ReviewSetup`
  places no frozen constraint between `review_date` and the period boundaries, so a
  review dated before or after the period is valid input; clamping is Stage 4
  calculation behaviour only and does not change what `ReviewSetup` accepts.
  - `review_date` before `period_start` → `elapsed_days = 0`.
  - `review_date == period_start` → `elapsed_days = 1`.
  - `review_date == period_end` or after → `elapsed_days = total_period_days`.
- **Elapsed fraction.** `elapsed_fraction = Decimal(elapsed_days) /
  Decimal(total_period_days)`, in `[0, 1]`. Not quantised to fixed decimal places.
- **Linear expected-spend assumption.** `raw_expected_spend = current_budget *
  elapsed_fraction` (unquantised, used internally for ratio calculations); the public
  `expected_spend = raw_expected_spend.quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)`.
- **Spend variance.** `spend_variance = (spend_to_date -
  raw_expected_spend).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)`. Positive means
  ahead of linear pace, negative means behind — Stage 4 does not say whether either is
  good or bad.
- **Pacing ratio.** When `raw_expected_spend != 0`: `pacing_ratio = spend_to_date /
  raw_expected_spend` (unquantised — deliberately computed from the *unquantised* expected
  spend so penny rounding cannot distort the ratio). `> 1` means spending faster than
  linear pace, `= 1` means exactly on pace, `< 1` means slower — a numerical meaning only,
  not a status. When `raw_expected_spend == 0` (which happens when `elapsed_days = 0` or
  `current_budget = 0.00`; since `spend_to_date <= current_budget` is already frozen, a
  zero budget also means zero spend): `pacing_ratio = None`. Never a `0/0` sentinel.
- **Remaining budget.** `remaining_budget = (current_budget -
  spend_to_date).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)`. Cannot be negative —
  guaranteed by the already-frozen `spend_to_date <= current_budget` — so Stage 4
  duplicates no additional validation for this.
- **Projected end-of-period spend.** When `elapsed_fraction != 0`:
  `projected_end_of_period_spend = (spend_to_date /
  elapsed_fraction).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)` — a factual linear
  extrapolation only, never labelled as an expected overspend/underspend/risk. Equals
  `spend_to_date` on the last day or after the period. When `elapsed_fraction == 0`
  (before the period starts): `projected_end_of_period_spend = None`.
- **Decimal precision and rounding.** Every calculation runs inside an explicit
  `decimal.localcontext()` with `prec=28` and `rounding=ROUND_HALF_UP`, independent of any
  global `Decimal` context a caller may have mutated.
- **Quantisation policy.** `expected_spend`, `spend_variance`, `remaining_budget`, and
  `projected_end_of_period_spend` are quantised to `CURRENCY_QUANTUM` (`Decimal("0.01")`)
  since they represent money. `elapsed_fraction` and `pacing_ratio` are **not** quantised
  to any fixed number of decimal places — they are ratios, not currency. No new pacing,
  ratio, rounding, or date constant was added to `src/constants.py`; the existing
  `CURRENCY_QUANTUM` is reused as-is.
- **Platform and KPI independence.** The calculation depends only on
  `review_date`/`period_start`/`period_end` and `current_budget`/`spend_to_date` — never
  on `platform` or `kpi_type`, and never on any Stage 3 `CampaignMetrics` output.

## Deterministic Performance Classification Rules (Sprint 1, Development Stage 5)

These rules govern `src/classification.py`, which classifies one already-calculated
`CampaignMetrics` instance into a neutral `PerformanceBand`. Stage 5 is a **descriptive
classification only** — it is not a `RecommendationAction`, decision, constraint, score,
eligibility result, or budget action. `CampaignMetrics` (`src/metrics.py`) remains the
sole authoritative source of `weighted_performance_ratio`; `src/classification.py` never
recalculates it.

- **Classification input.** `weighted_performance_ratio` (from `CampaignMetrics`) is the
  sole input. No other `CampaignMetrics` field (`performance_ratio_7d`,
  `performance_ratio_28d`, `trend_delta`), and no `CampaignInput`, `CampaignPacing`, or
  `ReviewSetup` field, is used.
- **Threshold conditions and equality behaviour**, using the existing frozen
  `INCREASE_THRESHOLD = Decimal("1.15")` and `MAINTAIN_THRESHOLD = Decimal("0.90")`:
  ```
  weighted_performance_ratio >= INCREASE_THRESHOLD               → ABOVE_TARGET
  MAINTAIN_THRESHOLD <= weighted_performance_ratio < INCREASE_THRESHOLD → ON_TARGET
  weighted_performance_ratio < MAINTAIN_THRESHOLD                → BELOW_TARGET
  ```
  The threshold value itself belongs to the higher band: `weighted_performance_ratio ==
  INCREASE_THRESHOLD` is `ABOVE_TARGET`; `weighted_performance_ratio ==
  MAINTAIN_THRESHOLD` is `ON_TARGET`.
- **Direct Decimal comparison only.** No arithmetic, quantisation, or `float` conversion
  is performed — classification only compares an already-computed `Decimal` against the
  two existing constants, so no local `decimal` context is required (unlike Stages 3–4,
  which perform division/multiplication).
- **Platform and KPI independence.** The classification depends only on
  `weighted_performance_ratio` — never `platform` or `kpi_type` — and contains no
  KPI-specific branching, since Stage 3 has already direction-normalised CPA and ROAS so
  that a higher ratio always means better performance for both.
- **Neutral vocabulary, not a recommendation.** `PerformanceBand`
  (`ABOVE_TARGET`/`ON_TARGET`/`BELOW_TARGET`) is deliberately distinct from
  `RecommendationAction` (`INCREASE`/`MAINTAIN`/`REDUCE`/`HOLD`) and is never assigned to
  or confused with it. `RecommendationAction`, `Confidence`, and `ReasonCode` are not
  imported or assigned anywhere in `src/classification.py`.
- **No precedence over unresolved considerations.** A campaign receives a numerical
  performance band regardless of its trend, conversion volume, or tracking reliability —
  Stage 5 creates no precedence or override rule for those later considerations; it
  simply does not consider them.

## Deterministic Trend Classification Rules (Sprint 1, Development Stage 6)

These rules govern the trend-classification additions to `src/classification.py`, which
classify one already-calculated `CampaignMetrics` instance's `trend_delta` into a neutral
`TrendDirection`. Stage 6 is **descriptive evidence only** — it is not a confidence
assessment, tracking assessment, pacing interpretation, constraint, eligibility decision,
score, `RecommendationAction`, `ReasonCode`, or proposed allocation, and it is
independent of `PerformanceBand`/`CampaignPerformanceClass` (Stage 5). `CampaignMetrics`
(`src/metrics.py`) remains the sole authoritative source of `trend_delta`;
`src/classification.py` never recalculates it.

- **Classification input.** `CampaignMetrics.campaign_id` and `CampaignMetrics.trend_delta`
  are the only inputs read. No other `CampaignMetrics` field (`performance_ratio_7d`,
  `performance_ratio_28d`, `weighted_performance_ratio`), and no `CampaignInput`,
  `CampaignPacing`, `ReviewSetup`, or `CampaignPerformanceClass`/`PerformanceBand`, is
  used.
- **Threshold conditions and equality behaviour**, using the existing frozen
  `TREND_THRESHOLD = Decimal("0.10")`:
  ```
  trend_delta >= TREND_THRESHOLD                → IMPROVING
  -TREND_THRESHOLD < trend_delta < TREND_THRESHOLD → STABLE
  trend_delta <= -TREND_THRESHOLD               → DECLINING
  ```
  Reaching either threshold magnitude enters that directional band — consistent with the
  threshold-entry policy approved for `PerformanceBand` in Stage 5
  (`trend_delta == TREND_THRESHOLD` is `IMPROVING`; `trend_delta == -TREND_THRESHOLD` is
  `DECLINING`).
- **Negative-boundary construction.** The negative boundary is
  `TREND_THRESHOLD.copy_negate()` — an exact sign-inversion with no rounding and no
  dependence on the active `Decimal` context. No new negative-threshold constant was
  added to `src/constants.py`, and the boundary is never computed by multiplying by
  `Decimal("-1")`, converting through `float`, or recalculating from campaign data.
- **Direct Decimal comparison only.** No arithmetic or quantisation is performed on
  `trend_delta` — classification only compares an already-computed `Decimal` against
  `TREND_THRESHOLD` and its exact negation, so no local `decimal` context is required.
- **Platform and KPI independence.** The classification depends only on `trend_delta` —
  never `platform` or `kpi_type` — and contains no KPI-specific or platform-specific
  branching, since Stage 3 has already direction-normalised CPA and ROAS so that
  `trend_delta`'s sign has identical meaning for both: positive always means improving,
  negative always means declining.
- **Independent of PerformanceBand.** `TrendDirection`/`CampaignTrendClass` is a separate
  result from `PerformanceBand`/`CampaignPerformanceClass` — the two are never combined,
  and `classify_campaign_trend` never calls `classify_campaign_performance` or vice
  versa. `CampaignPerformanceClass` and `PerformanceBand` are unmodified by Stage 6.
- **Neutral vocabulary, not a recommendation or reason code.** `TrendDirection`
  (`IMPROVING`/`STABLE`/`DECLINING`) is deliberately descriptive evidence, distinct from
  `RecommendationAction` and `ReasonCode` — despite `ReasonCode` having matching member
  names (`RECENT_TREND_IMPROVING`/`STABLE`/`DECLINING`), `TrendDirection` is never
  assigned to or confused with `ReasonCode`, and neither `RecommendationAction`,
  `Confidence`, nor `ReasonCode` is imported anywhere in `src/classification.py`.
- **No precedence over unresolved considerations.** A campaign receives a numerical
  trend direction regardless of its conversion volume, tracking reliability, or pacing —
  Stage 6 creates no precedence or override rule for those later considerations.

## Deterministic Conversion-Volume Confidence Classification Rules (Sprint 1, Development Stage 7)

These rules govern the confidence-classification addition to `src/classification.py`,
which classifies one already-validated `CampaignInput` instance's `conversions_28d`
count into the existing `Confidence` enum's `HIGH`/`MEDIUM`/`LOW` members. Stage 7 is
**descriptive conversion-volume evidence only** — it is not a tracking interpretation,
assessability decision, performance classification, trend classification, pacing
interpretation, constraint, eligibility decision, score, recommendation, reason code, or
allocation, and it is independent of `PerformanceBand`/`CampaignPerformanceClass` (Stage
5) and `TrendDirection`/`CampaignTrendClass` (Stage 6). `CampaignInput` (`src/models.py`)
remains the sole authoritative source of `conversions_28d`; `src/classification.py`
never re-validates or recalculates it.

- **Classification input.** `CampaignInput.campaign_id` and
  `CampaignInput.conversions_28d` are the only inputs read. `conversions_7d` is never
  read, combined, summed, averaged, or weighted with `conversions_28d` — `conversions_28d`
  is the sole authority, since it is the fuller, more statistically stable evidence
  window and using both would double-count the nested 7-day period (`conversions_7d <=
  conversions_28d` is already a frozen `CampaignInput` invariant precisely because the
  7-day window sits inside the 28-day window, not alongside it). `SEVEN_DAY_WEIGHT` and
  `TWENTY_EIGHT_DAY_WEIGHT` (Stage 3, ratio-blending constants) are not reused here.
- **Threshold conditions and equality behaviour**, using the existing frozen
  `MINIMUM_CONVERSIONS = 10` and `HIGH_CONFIDENCE_CONVERSIONS = 30`:
  ```
  conversions_28d >= HIGH_CONFIDENCE_CONVERSIONS   → HIGH
  conversions_28d >= MINIMUM_CONVERSIONS           → MEDIUM
  otherwise (0–9)                                  → LOW
  ```
  Reaching either threshold enters the higher confidence band — consistent with the
  threshold-entry policy approved for `PerformanceBand` (Stage 5) and `TrendDirection`
  (Stage 6): `conversions_28d == 30` is `HIGH`; `conversions_28d == 10` is `MEDIUM`. Zero
  conversions produces `LOW`, not a special-cased result.
- **`Confidence.NOT_ASSESSABLE` is never assigned by Stage 7.** This is a deliberate
  scope boundary, not a claim that the value is unreachable in general. It is never
  inferred from zero conversions, low conversions, `TrackingStatus.WARNING`,
  `TrackingStatus.UNRELIABLE`, zero spend, zero budget, `PerformanceBand`,
  `TrendDirection`, `CampaignPacing`, or protected/test status. Its trigger and any
  precedence rule remain deferred until tracking interpretation or a later combined-
  assessment stage is formally approved.
- **Direct integer comparison only.** No addition, subtraction, multiplication,
  division, averaging, weighting, quantisation, or `Decimal`/`float` conversion is
  performed — `conversions_28d` and both thresholds are plain `int`, so no local
  `decimal` context is relevant and none is used.
- **Platform and KPI independence.** The classification depends only on
  `conversions_28d` — never `platform` or `kpi_type` — so the same count produces the
  same `Confidence` for CPA and ROAS campaigns and for every platform.
- **Independence from performance, trend, tracking, and pacing.** `CampaignConfidenceClass`
  is a separate result from `CampaignPerformanceClass` and `CampaignTrendClass` — the
  three are never combined, and `classify_campaign_confidence` never calls
  `classify_campaign_performance` or `classify_campaign_trend` (or vice versa). It does
  not read `tracking_status` or any `CampaignPacing` fact. `CampaignPerformanceClass`
  and `CampaignTrendClass` are unmodified by Stage 7.

## Deterministic Tracking-Based Assessability Rules (Sprint 1, Development Stage 8)

These rules govern the tracking-assessability addition to `src/classification.py`,
which determines one already-validated `CampaignInput` instance's assessability from
`tracking_status` alone. Stage 8 is a **narrow, descriptive fact only** — it is not
conversion-volume confidence, a `Confidence.NOT_ASSESSABLE` assignment, a replacement for
`CampaignConfidenceClass`, a performance classification, a trend classification, a
pacing interpretation, a combined campaign judgement, a constraint, an eligibility
decision, a score, a recommendation, a reason code, or an allocation. `CampaignInput`
(`src/models.py`) remains the sole authoritative source of `tracking_status`;
`src/classification.py` never re-validates it.

- **Classification input.** `CampaignInput.campaign_id` and
  `CampaignInput.tracking_status` are the only fields read. `conversions_7d`,
  `conversions_28d`, `CampaignMetrics`, `CampaignPacing`, `platform`, `kpi_type`,
  `is_protected`, `is_test_campaign`, and every other field are never read.
- **Exact mapping:**
  ```
  is_assessable = campaign.tracking_status is not TrackingStatus.UNRELIABLE
  ```
  Therefore: `HEALTHY → True`; `WARNING → True`; `UNRELIABLE → False`. `UNRELIABLE` is
  the sole condition producing `is_assessable=False`.
- **Rationale for `WARNING=True`.** `WARNING` represents a concern requiring later
  caution, not an explicit declaration that the evidence is unusable — it is treated as
  assessable, the same as `HEALTHY`, deliberately distinguishing it from `UNRELIABLE`.
- **Original `tracking_status` preserved in the result.** `WARNING` is never collapsed
  into `HEALTHY` — the result carries the original `TrackingStatus` value unchanged,
  keeping that distinction visible for later `ReasonCode`/recommendation logic that may
  treat `WARNING` and `HEALTHY` differently even though both are currently assessable.
- **No arithmetic, Decimal, or float conversion.** `tracking_status` is a plain enum
  comparison — no local `decimal` context is relevant and none is used.
- **Platform and KPI independence.** The result depends only on `tracking_status` — the
  same status produces the same `is_assessable` value for every platform, KPI type,
  conversion count, and protected/test state.
- **No override of performance, trend, or confidence.** `assess_campaign_tracking` never
  calls `classify_campaign_performance`, `classify_campaign_trend`, or
  `classify_campaign_confidence` (or vice versa); `CampaignPerformanceClass`,
  `CampaignTrendClass`, and `CampaignConfidenceClass` are unmodified by Stage 8, and
  Stage 7 continues to return only `Confidence.HIGH`/`MEDIUM`/`LOW` regardless of
  `tracking_status`.
- **`Confidence.NOT_ASSESSABLE` remains unowned.** Stage 8 does not read, assign, or
  otherwise touch `Confidence.NOT_ASSESSABLE`. Whether/how tracking-based assessability
  relates to it is deferred to a later combined-assessment stage, which must preserve
  the independent Stage 7 conversion-volume result rather than overwriting it.

## Deterministic Pacing Interpretation Rules (Sprint 1, Development Stage 9)

These rules govern the pacing-interpretation addition to `src/pacing.py`, which
classifies one already-calculated `CampaignPacing` instance's `pacing_ratio` into a
neutral `PacingStatus`. Stage 9 is a **narrow, descriptive classification only** — it is
not a judgement that overspending or underspending is desirable or undesirable, and it
is not a performance classification, trend classification, conversion-volume confidence
classification, tracking-based assessability result, combined campaign judgement,
constraint, eligibility decision, score, recommendation, reason code, or allocation.
`CampaignPacing` (`src/pacing.py`, Stage 4) remains the sole authoritative source of
`pacing_ratio`; Stage 9 never recalculates it.

- **`pacing_ratio` is the sole authoritative field.** `CampaignPacing.campaign_id` and
  `CampaignPacing.pacing_ratio` are the only inputs read. `spend_variance`,
  `expected_spend`, `elapsed_fraction`, `elapsed_days`, `total_period_days`,
  `remaining_budget`, and `projected_end_of_period_spend` are never read — in
  particular, `projected_end_of_period_spend` is explicitly excluded as a second pacing
  signal, and is never compared against `current_budget`, `minimum_budget`, or
  `maximum_budget`. No `CampaignInput`, `ReviewSetup`, or `CampaignMetrics` field is
  read.
- **Exact threshold conditions and equality behaviour**, using the newly frozen
  `PACING_LOWER_THRESHOLD = Decimal("0.90")` and `PACING_UPPER_THRESHOLD =
  Decimal("1.10")` — a symmetric ±10% on-pace tolerance around `1.00`:
  ```
  pacing_ratio is None                                          → NOT_AVAILABLE
  pacing_ratio < PACING_LOWER_THRESHOLD                         → UNDERSPENDING
  PACING_LOWER_THRESHOLD <= pacing_ratio <= PACING_UPPER_THRESHOLD → ON_PACE
  pacing_ratio > PACING_UPPER_THRESHOLD                         → OVERSPENDING
  ```
  The `ON_PACE` interval is **closed and inclusive on both ends**: `pacing_ratio ==
  PACING_LOWER_THRESHOLD` and `pacing_ratio == PACING_UPPER_THRESHOLD` are both
  `ON_PACE`. This is a different equality convention from Stages 5–7's single-sided
  "reaching the threshold enters the higher band" rule, because Stage 9's tolerance is a
  two-sided band around a midpoint (`1.00`) rather than a ladder of ascending bands.
- **`None` maps to `NOT_AVAILABLE`, unconditionally.** `pacing_ratio is None` is the
  upstream `CampaignPacing` zero-denominator case (zero elapsed time or zero current
  budget, per Stage 4's frozen rules). Stage 9 does not distinguish which upstream cause
  produced the `None`, does not recalculate `pacing_ratio`, and does not substitute zero
  for `None`. `PacingStatus.NOT_AVAILABLE` is a **pacing-data state only** — it is never
  represented as, mapped to, or interchangeable with `Confidence.NOT_ASSESSABLE`,
  `is_assessable=False`, `TrackingStatus.UNRELIABLE`, `RecommendationAction.HOLD`, a
  reason code, or an eligibility outcome.
- **No arithmetic, Decimal, or float conversion.** `pacing_ratio` is compared directly
  against two existing `Decimal` constants — no addition, subtraction, multiplication,
  division, quantisation, or `float` conversion is performed, so no local `decimal`
  context is relevant and none is used.
- **Platform and KPI independence.** The result depends only on `pacing_ratio` — the
  same ratio produces the same `PacingStatus` for every platform, KPI type, and
  protected/test state, since `CampaignPacing` itself is already platform/KPI-
  independent (Stage 4).
- **No override of performance, trend, confidence, or tracking.**
  `classify_campaign_pacing` never calls `classify_campaign_performance`,
  `classify_campaign_trend`, `classify_campaign_confidence`, or
  `assess_campaign_tracking` (or vice versa); `CampaignPerformanceClass`,
  `CampaignTrendClass`, `CampaignConfidenceClass`, and `CampaignTrackingAssessment` are
  unmodified by Stage 9.
- **Descriptive, not evaluative.** `PacingStatus` states a numerical relationship to
  linear pace only — it does not say whether `OVERSPENDING` or `UNDERSPENDING` is good,
  bad, expected, or a problem. Whether either is desirable, and any combined judgement
  across pacing, performance, trend, confidence, and tracking assessability, remain
  pending a later combined-assessment stage.

## Deterministic Static Budget-Bound Calculation Rules (Sprint 1, Development Stage 10)

These rules govern `src/constraints.py`, which calculates one already-validated
`CampaignInput` instance's static distance to its validated `maximum_budget` and
`minimum_budget`. Stage 10 is a **static-bound fact calculation only** — no threshold
comparison, no classification, no enum is produced, and no effective/final permissible
budget movement is determined. `CampaignInput` (`src/models.py`) remains the sole
authoritative source of `current_budget`/`minimum_budget`/`maximum_budget`;
`src/constraints.py` never re-validates them.

- **Calculation input.** `CampaignInput.campaign_id`, `current_budget`,
  `minimum_budget`, and `maximum_budget` are the only fields read. No other
  `CampaignInput` field is read — in particular, `campaign_max_change_percentage`,
  `is_protected`, `is_test_campaign`, and `test_budget_floor` are never read, and no
  `ReviewSetup` field (including `default_max_change_percentage`) is read.
- **Exact formulas:**
  ```
  room_to_static_maximum = maximum_budget - current_budget
  room_to_static_minimum = current_budget - minimum_budget
  ```
- **Existing validated budget invariant.** `CampaignInput` already guarantees
  `minimum_budget <= current_budget <= maximum_budget` (`_check_budget_bounds`,
  `src/models.py`). Therefore both `room_to_static_maximum` and `room_to_static_minimum`
  are structurally guaranteed non-negative for every valid `CampaignInput` — Stage 10
  performs no additional validation, no clamping, and no substitution of a default for a
  negative result (none can occur).
- **No thresholds or classification.** Unlike Stages 5–9, Stage 10 produces no enum and
  makes no comparison against any constant — it is pure `Decimal` subtraction of
  already-validated fields, structurally identical in kind to Stage 4's
  `remaining_budget = current_budget - spend_to_date`.
- **Boundary-zero behaviour.** `current_budget == maximum_budget` →
  `room_to_static_maximum = Decimal("0.00")`; `current_budget == minimum_budget` →
  `room_to_static_minimum = Decimal("0.00")`; `minimum_budget == current_budget ==
  maximum_budget` → both fields `Decimal("0.00")`. Zero is a valid calculated fact in
  every case — never replaced with `None` or a categorical status.
- **Static-bound terminology.** The model and function names
  (`CampaignStaticBudgetRoom`, `calculate_campaign_static_budget_room`,
  `room_to_static_maximum`, `room_to_static_minimum`) deliberately include "static" to
  distinguish these facts from a future *effective* constraint (after percentage limits,
  protection, and test-budget-floor rules are applied). The more general names
  `CampaignBudgetRoom`/`calculate_campaign_budget_room`/`room_to_increase`/
  `room_to_decrease` are deliberately not used, since they could incorrectly imply those
  later rules have already been applied.
- **Test-budget-floor exclusion.** `test_budget_floor` is never read.
  `room_to_static_minimum` is always calculated against `minimum_budget` only, even for
  a test campaign whose `test_budget_floor` exceeds `minimum_budget` (this occurs in
  `data/sample_campaigns.csv` for `G003`: `minimum_budget = Decimal("100.00")`,
  `test_budget_floor = Decimal("300.00")`, `room_to_static_minimum =
  Decimal("1100.00")`). This value is a static-bound fact only — it is **not** an
  approved decrease amount and does **not** authorise reducing a test campaign's budget
  below its `test_budget_floor`. A later effective-constraint stage must determine the
  effective decrease limit after considering `test_budget_floor`.
- **Protection exclusion.** `is_protected` is never read. A protected campaign receives
  exactly the same static-bound calculation as an otherwise identical unprotected
  campaign (confirmed for `G002` in `data/sample_campaigns.csv`, `is_protected=True`).
  This does not authorise increasing or decreasing a protected campaign — protection
  behaviour remains pending a later stage.
- **Percentage-limit exclusion.** `campaign_max_change_percentage`,
  `ReviewSetup.default_max_change_percentage`, and `DEFAULT_MAX_CHANGE_PERCENTAGE` are
  never read or applied. No percentage-based movement cap, effective increase limit,
  effective decrease limit, or intersection between a percentage limit and the static
  bounds is calculated — the percentage mechanism's application and precedence remain
  pending, exactly as recorded in the Pending section below.
- **Decimal policy.** Calculation runs inside an explicit `decimal.localcontext()`
  (`prec=28`, `rounding=ROUND_HALF_UP`), independent of any global `Decimal` context a
  caller may have mutated, following the same fixed-context pattern as Stages 3–4. No
  `float` conversion, no float literal, no re-quantisation, and no rounding of the
  output — both results are already exact to two decimal places because they are
  subtractions of two already-quantised `Currency` values.
- **Separation from Stages 3–9.** `src/constraints.py` imports no `ReviewSetup`,
  `CampaignMetrics`, `CampaignPacing`, `PerformanceBand`, `TrendDirection`, `Confidence`,
  `TrackingStatus`, `CampaignTrackingAssessment`, or `PacingStatus`, and
  `calculate_campaign_static_budget_room` never calls any Stage 3–9 function.
- **Does not authorise a budget movement.** `CampaignStaticBudgetRoom` carries no
  effective minimum/maximum budget, no final increase/decrease limit, no percentage
  limit, no eligibility field, no blocking flag, no `RecommendationAction`, no
  `ReasonCode`, no score, and no allocation field — it is strictly a pair of static
  distance facts, consumed by a later, still-undesigned effective-constraint stage.

## Deterministic Applicable Change-Percentage Resolution Rules (Sprint 1, Development Stage 11)

These rules govern the addition to `src/constraints.py` that resolves, for one
already-validated `ReviewSetup` and one already-validated `CampaignInput`, which
already-validated maximum-change percentage applies to that campaign. Stage 11 is a
**selection fact only** — no arithmetic, no monetary movement cap, and no permissible
budget movement is calculated. `CampaignInput`/`ReviewSetup` (`src/models.py`) remain
the sole authoritative source of `campaign_max_change_percentage`/
`default_max_change_percentage`; `src/constraints.py` never re-validates them.

- **Resolution input.** `CampaignInput.campaign_id`, `campaign_max_change_percentage`,
  and `ReviewSetup.default_max_change_percentage` are the only fields read. No other
  field of either model is read — in particular, `current_budget`, `minimum_budget`,
  `maximum_budget`, `room_to_static_maximum`, `room_to_static_minimum`, `is_protected`,
  `is_test_campaign`, `test_budget_floor`, `platform`, and `kpi_type` are never read.
- **Exact rule and precedence:**
  ```
  applicable_max_change_percentage = (
      campaign.campaign_max_change_percentage
      if campaign.campaign_max_change_percentage is not None
      else review.default_max_change_percentage
  )
  ```
  A non-`None` campaign override always wins; otherwise the review default applies.
  This uses an explicit `is not None` check, never a truthiness-based fallback (e.g.
  `campaign.campaign_max_change_percentage or review.default_max_change_percentage`) —
  significant because a truthiness check would behave identically for every value
  `CampaignInput` currently permits (both fields are `gt=0`, so no valid non-`None`
  value is ever falsy), but the explicit check is the correct, unambiguous expression of
  the intended precedence regardless.
- **The result is never `None`.** `campaign_max_change_percentage` may be `None`, in
  which case `review.default_max_change_percentage` applies — and that field is itself
  never `None` on a constructed `ReviewSetup` (it always has a value, defaulting to
  `DEFAULT_MAX_CHANGE_PERCENTAGE` if not supplied). No special zero handling exists or
  is needed: both source fields are constrained to `(0, 1]` by existing validation
  (`gt=0`, `le=1`), so a resolved value of exactly zero cannot occur.
- **`DEFAULT_MAX_CHANGE_PERCENTAGE` is never imported or read by this resolution.** Only
  the already-validated `review.default_max_change_percentage` is used, so a
  caller-supplied `ReviewSetup` value is always respected instead of a hard-coded
  module constant.
- **No arithmetic, quantisation, or rounding.** The resolved percentage is preserved
  exactly as a plain conditional selection — no `Decimal` arithmetic, no local
  `decimal` context, and no `float` conversion; the result is unaffected by any global
  `Decimal` context a caller may have mutated, since no computation occurs at all.
- **Independence from Stage 10.** `resolve_campaign_applicable_change_percentage` never
  reads any `CampaignStaticBudgetRoom` field and never calls
  `calculate_campaign_static_budget_room` (or vice versa); the two facts are never
  combined into one result or one call.
- **Exclusion of static-bound intersection.** Whether/how the resolved percentage
  interacts with `room_to_static_maximum`/`room_to_static_minimum` — including any
  monetary-cap formula, its base amount, and its precedence relative to the static
  bounds — is not calculated here and remains pending a later stage.
- **Exclusion of protection and test-budget-floor effects.** `is_protected`,
  `is_test_campaign`, and `test_budget_floor` are never read; changing any of them while
  holding the three authorised fields constant never changes the result. This does not
  authorise any protected-campaign or test-campaign budget behaviour.
- **Monetary-cap and effective-constraint rules remain pending.** Stage 11 resolves only
  *which* percentage value applies — the multiplication base, symmetry between
  increase/decrease, and full precedence among static bounds, percentage caps,
  protection, and test floors are all still undecided.

## Deterministic Raw Percentage-Based Monetary Movement-Cap Calculation Rules (Sprint 1, Development Stage 12)

These rules govern the addition to `src/constraints.py` that calculates, for one
already-validated `CampaignInput` and its already-resolved Stage 11
`CampaignApplicableChangePercentage`, a raw percentage-based monetary movement cap.
Stage 12 is a **raw, informational fact only** — it is not permission to increase or
decrease a campaign's budget, an effective/final permissible movement, a static-bound
intersection, a protection or test-budget-floor determination, an eligibility result,
a score, a recommendation, a reason code, or an allocation. `CampaignInput` and
`CampaignApplicableChangePercentage` remain the sole authoritative sources of
`current_budget` and `applicable_max_change_percentage`; `src/constraints.py` never
re-validates or re-resolves them.

- **Calculation input and campaign-ID matching.** `campaign.campaign_id`,
  `campaign.current_budget`, `applicable_percentage.campaign_id`, and
  `applicable_percentage.applicable_max_change_percentage` are the only fields read. No
  other field of either model is read — in particular, `minimum_budget`,
  `maximum_budget`, `room_to_static_maximum`, `room_to_static_minimum`, `is_protected`,
  `is_test_campaign`, `test_budget_floor`, `platform`, and `kpi_type` are never read,
  and no `ReviewSetup` field, `campaign.campaign_max_change_percentage`, or
  `DEFAULT_MAX_CHANGE_PERCENTAGE` is ever read. Before calculating,
  `campaign.campaign_id == applicable_percentage.campaign_id` is required; a mismatch
  raises `ValueError("campaign_id mismatch between campaign and applicable
  percentage")` and no result is returned — the two input objects independently
  identify a campaign, and silently applying one campaign's percentage to another would
  be unsafe.
- **Exact formula:**
  ```
  raw_percentage_movement_cap = quantize(
      current_budget * applicable_max_change_percentage,
      to=CURRENCY_QUANTUM,
      rounding=ROUND_HALF_UP,
  )
  ```
  `current_budget` is the calculation base — no other amount is used. Neither operand
  is quantised before the multiplication; the product is quantised exactly once, after
  multiplication, using the existing `CURRENCY_QUANTUM` constant and `ROUND_HALF_UP`.
- **Operand-derived Decimal precision policy.** `CampaignInput.current_budget` has no
  upper bound, and `applicable_max_change_percentage` has no digit-count restriction —
  so a fixed-precision `decimal` context (e.g. the `prec=28` used by Stages 3, 4, and
  10) can round the intermediate multiplication *before* the explicit final
  quantisation ever runs, silently producing an incorrect result via double rounding.
  This was empirically confirmed during Stage 12's inspection: with
  `current_budget = Decimal("99999999999999999999999999.99")` (the largest value
  `Currency` can hold under the default global context — 28 significant digits) and
  `applicable_max_change_percentage = Decimal("0.036020245307579938554529107051")`
  (a legitimately constructible percentage override, since `campaign_max_change_percentage`
  has no digit-count limit), a fixed `prec=28` local context incorrectly returns
  `Decimal("...52910.71")`, while the mathematically exact, correctly rounded result is
  `Decimal("...52910.70")` — a one-penny error. Stage 12 therefore derives the local
  context's precision from the operands themselves:
  ```
  operand_digits = len(current_budget.as_tuple().digits) + len(applicable_max_change_percentage.as_tuple().digits)
  safe_precision = max(28, operand_digits + 4)
  ```
  This guarantees the multiplication is computed **exactly** (the exact product of an
  *n*-digit and an *m*-digit decimal never needs more than *n+m* significant digits),
  leaving the explicit `.quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)` call as the
  **sole** rounding operation. The `max(28, ...)` floor preserves the repository's
  established baseline precision for ordinary-sized operands while extending it for
  extreme ones; it does not introduce a new maximum budget or percentage digit
  restriction, and `CampaignInput`/`Currency` validation is unmodified.
- **Local context only; global context untouched.** The multiplication and
  quantisation both run inside an explicit `decimal.localcontext()` scoped to the
  function body; the ambient global `Decimal` context is never mutated and cannot
  affect the result, and is provably unchanged after the function returns (verified by
  a test that mutates the global context before calling the function and asserts it is
  unchanged afterward).
- **`None` and zero behaviour.** Neither `current_budget` nor
  `applicable_max_change_percentage` may be `None` at this stage (both are guaranteed
  present by Stages 1/11); no fallback value is substituted for either.
  `applicable_max_change_percentage` is guaranteed `> 0` and `<= 1` by existing
  validation. `current_budget` may be exactly `Decimal("0.00")`, in which case the
  result is `Decimal("0.00")` — a legitimate raw cap, not an eligibility judgement or
  error; no truthiness-based fallback is applied.
- **Separation from Stage 10.** `calculate_campaign_raw_percentage_movement_cap` never
  reads `minimum_budget`, `maximum_budget`, `room_to_static_maximum`, or
  `room_to_static_minimum`, and never calls `calculate_campaign_static_budget_room` (or
  vice versa). A campaign at a static boundary (e.g. `current_budget == maximum_budget`)
  may still have a non-zero raw percentage cap — the two facts are never intersected
  here; a later effective-constraint stage must reconcile them.
- **Independence from protection and test-budget-floor rules.** `is_protected`,
  `is_test_campaign`, and `test_budget_floor` are never read; changing any of them
  while holding the four authorised fields constant never changes the result. This does
  not authorise any protected-campaign or test-campaign budget behaviour.
- **Exclusion of effective movement and later-stage judgements.** The result carries no
  effective/final permissible movement, no static-bound intersection, no eligibility
  field, no blocking flag, no `RecommendationAction`, no `ReasonCode`, no score, and no
  allocation field — it is strictly a raw, informational monetary fact, consumed by a
  later, still-undesigned effective-constraint stage.

## Deterministic Test-Floor Distance Calculation Rules (Sprint 1, Development Stage 13)

These rules govern the addition to `src/constraints.py` that calculates, for one
already-validated `CampaignInput`, a raw test-floor distance fact. Stage 13 is a
**raw, informational fact only** — it is not the effective floor, not an alternative
or additional minimum, not permissible decrease, not an effective directional
constraint, and is never combined with `minimum_budget`, Stage 10's static room, or
Stage 12's raw percentage movement cap. `CampaignInput` remains the sole authoritative
source of `is_test_campaign`/`current_budget`/`test_budget_floor`;
`src/constraints.py` never re-validates or reconstructs it.

- **Calculation input.** `campaign.campaign_id`, `campaign.is_test_campaign`,
  `campaign.current_budget`, and `campaign.test_budget_floor` are the only fields
  read. No other field is read — in particular, `minimum_budget`, `maximum_budget`,
  `is_protected`, `campaign_max_change_percentage`, `platform`, and `kpi_type` are
  never read, and no `ReviewSetup` field, `CampaignStaticBudgetRoom`,
  `CampaignApplicableChangePercentage`, or `CampaignRawPercentageMovementCap` (Stages
  10–12) is ever read or called.
- **Exact formula and non-test behaviour:**
  ```
  is_test_campaign == True  → room_to_test_floor = current_budget - test_budget_floor
  is_test_campaign == False → room_to_test_floor = None
  ```
  `test_budget_floor` is never read for arithmetic when `is_test_campaign` is `False`
  — the function returns `None` before reaching the subtraction. `None` is an
  **explicit statement that the fact does not apply** — never a fallback value, never
  `Decimal("0.00")`, never an error. A valid non-test `CampaignInput` never raises.
- **Zero behaviour.** `current_budget == test_budget_floor` produces
  `Decimal("0.00")` — a legitimate, unaltered test-floor distance, not an error,
  eligibility decision, or permission judgement.
- **No new rounding or quantisation.** `current_budget` and `test_budget_floor` are
  both already-quantised `Currency` values (2 decimal places); the subtraction is
  computed inside a fixed local `decimal.localcontext()` (`prec=28`,
  `rounding=ROUND_HALF_UP`, matching Stage 10's established policy) and the result is
  **not** re-quantised — the exact two-decimal-place exponent produced by subtracting
  two already-quantised values is preserved as-is. Unlike Stage 12's multiplication,
  no operand-derived precision is required: subtracting two values never needs more
  significant digits than the larger operand already has, so a fixed `prec=28`
  context safely supports every already-valid `Currency` value (confirmed by testing
  the largest value `Currency` can hold under the default global context — 28
  significant digits — both alone and against a non-zero floor, with all significant
  whole-number digits preserved exactly).
- **Separation from Stages 10–12.** `calculate_campaign_test_floor_room` never reads
  `room_to_static_maximum`, `room_to_static_minimum`,
  `applicable_max_change_percentage`, or `raw_percentage_movement_cap`, and never
  calls `calculate_campaign_static_budget_room`,
  `resolve_campaign_applicable_change_percentage`, or
  `calculate_campaign_raw_percentage_movement_cap` (or vice versa).
- **Protection independence.** `is_protected` is never read; changing it while
  holding the four authorised fields constant never changes the result. This does not
  approve any protected-campaign movement mechanism.
- **Effective-floor precedence remains undecided.** This approval fixes only the raw
  distance formula above — it does **not** decide whether the eventual effective
  floor is `minimum_budget`, `test_budget_floor`, `max(minimum_budget,
  test_budget_floor)`, or another formulation. That precedence, the static-bound/
  raw-cap intersection, and protected-campaign handling all remain pending later
  stages.

## Deterministic Protection Constraint Rules (Sprint 1, Development Stage 14)

These rules govern the addition to `src/constraints.py` that states, for one
already-validated `CampaignInput`, a neutral, decrease-specific protection
constraint. Stage 14 is a **boolean fact only** — it is not an eligibility decision,
a recommendation, a monetary movement amount, permissible decrease, an effective
directional limit, or an increase-side constraint, and it is never combined with
Stages 10–13. `CampaignInput` remains the sole authoritative source of
`is_protected`; `src/constraints.py` never re-validates it.

- **Calculation input.** `campaign.campaign_id` and `campaign.is_protected` are the
  only fields read. No other field is read — in particular, `current_budget`,
  `minimum_budget`, `maximum_budget`, `is_test_campaign`, `test_budget_floor`,
  `campaign_max_change_percentage`, `platform`, and `kpi_type` are never read, and no
  `CampaignStaticBudgetRoom`, `CampaignApplicableChangePercentage`,
  `CampaignRawPercentageMovementCap`, `CampaignTestFloorRoom`, or `ReviewSetup` is
  ever read or called.
- **Exact mapping:**
  ```
  decrease_blocked = campaign.is_protected
  ```
  `is_protected=True → decrease_blocked=True`; `is_protected=False →
  decrease_blocked=False`. `False` is a meaningful result, never converted to `None`.
- **Boolean representation, not a monetary room.** `is_protected` is explicitly
  defined as meaning the campaign "must never be reduced"
  (`docs/DATA_DICTIONARY.md`). Stage 14 preserves that rule as a boolean rather than
  prematurely translating it into a `Decimal` room amount (e.g. `Decimal("0.00")`) or
  an `Optional` monetary field — no `Decimal` is imported, no local context is used,
  and no rounding or quantisation occurs anywhere in this addition.
- **Protection prohibits decreases only; increase behaviour is unaddressed.** The one
  frozen sentence about `is_protected` speaks only to reduction. Stage 14 makes no
  statement about increases — this is deliberately left open, not resolved either
  way.
- **`decrease_blocked=False` is not permission to decrease.** It states only that
  protection itself does not prohibit a decrease; other constraints (static bounds,
  the percentage cap, test-floor rules, once resolved) may still apply.
  **`decrease_blocked=True` is not eligibility, a recommendation, or an allocation
  decision** — it states only that protection prohibits a decrease.
- **Separation from Stages 10–13.** `resolve_campaign_protection_constraint` never
  reads any Stage 10–13 field and never calls any Stage 10–13 function (or vice
  versa); the five facts are never combined into one result or one call.
- **Effective-floor precedence and all constraint combinations remain pending.** This
  approval fixes only the boolean protection fact — it does not decide how
  `decrease_blocked` will eventually combine with Stage 10's static room, Stage 12's
  raw cap, or Stage 13's test-floor room into any effective decrease limit.

## Deterministic Test-Aware Static Decrease Room Rules (Sprint 1, Development Stage 15)

These rules govern the addition to `src/constraints.py` that combines one
already-calculated `CampaignStaticBudgetRoom` (Stage 10) and one already-calculated
`CampaignTestFloorRoom` (Stage 13) into one neutral, test-aware static decrease-room
constraint. Stage 15 is a **raw constraint only** — it is not permissible decrease,
not an effective decrease limit, and does not mean the campaign should be reduced. It
does not account for Stage 12's percentage cap or Stage 14's protection constraint.
`CampaignStaticBudgetRoom` and `CampaignTestFloorRoom` remain the sole authoritative
sources of `room_to_static_minimum` and `room_to_test_floor`; `src/constraints.py`
never recalculates either.

- **Approved business rule: `test_budget_floor` is an additional retained-spend
  floor for test campaigns.** A non-test campaign is constrained only by
  `minimum_budget` at this stage. A test campaign is constrained by both
  `minimum_budget` and `test_budget_floor`, and the **higher monetary floor**
  controls — equivalently, the corresponding decrease room is the **smaller** of the
  two already-calculated rooms. This is the first constraints-domain precedence rule
  explicitly approved as a business decision (as opposed to a pure fact calculation)
  — every prior Stage 10–14 addition deliberately deferred this exact question.
- **Exact calculation input and authorised fields.** `static_room.campaign_id`,
  `static_room.room_to_static_minimum`, `test_floor_room.campaign_id`, and
  `test_floor_room.room_to_test_floor` are the only fields read. No other field of
  either model is read — in particular, `room_to_static_maximum` is never read. No
  `CampaignInput`, `CampaignApplicableChangePercentage`,
  `CampaignRawPercentageMovementCap`, `CampaignProtectionConstraint`, or
  `ReviewSetup` is ever read or called; `calculate_campaign_static_budget_room` and
  `calculate_campaign_test_floor_room` are never called (Stage 15 consumes their
  already-approved outputs, never recalculates them).
- **Campaign-ID policy.** `static_room.campaign_id` must equal
  `test_floor_room.campaign_id`, checked before any monetary result is resolved; a
  mismatch raises exactly `ValueError("Campaign IDs must match when resolving
  test-aware static decrease room.")`, and no result is returned. Neither ID is
  silently preferred.
- **Exact formula:**
  ```
  room_to_test_floor is None  → test_aware_static_decrease_room = room_to_static_minimum
  otherwise                   → test_aware_static_decrease_room = min(room_to_static_minimum, room_to_test_floor)
  ```
  Mathematically equivalent to `effective_decrease_floor = max(minimum_budget,
  test_budget_floor)` via the identity `c - max(a, b) = min(c - a, c - b)` — expressed
  as a room to avoid recalculating either floor distance from raw budget fields.
- **`None` and zero behaviour.** `room_to_test_floor is None` (non-test campaigns)
  resolves to `room_to_static_minimum` unchanged — never replaced with
  `Decimal("0.00")`. The Stage 15 output itself is never `None`. `Decimal("0.00")` is
  a legitimate result when the smaller applicable room is zero — it means there is no
  static room to reduce under the combined floor rule, not an eligibility or
  recommendation judgement.
- **No arithmetic.** Stage 15 performs selection and comparison only — no
  subtraction, multiplication, or division; no local `decimal` context; no
  `CURRENCY_QUANTUM`; no `ROUND_HALF_UP`; no rounding; no quantisation; no `float`
  conversion. The selected `Decimal` operand (one of the two inputs) is returned
  unchanged. Ambient global `Decimal` precision/rounding cannot affect the result,
  since no arithmetic operation is performed.
- **Separation from Stages 11, 12, and 14.** `resolve_campaign_test_aware_static_decrease_room`
  never reads `applicable_max_change_percentage`, `raw_percentage_movement_cap`, or
  `decrease_blocked`/`is_protected`, and never calls
  `resolve_campaign_applicable_change_percentage`,
  `calculate_campaign_raw_percentage_movement_cap`, or
  `resolve_campaign_protection_constraint`. A protected campaign receives exactly the
  same Stage 15 result as an otherwise identical unprotected campaign with matching
  Stage 10/13 facts — no protection-based zero is calculated here.
- **No permissible movement calculated.** The result carries no effective decrease
  limit, no percentage-cap intersection, no eligibility field, no blocking flag, no
  `RecommendationAction`, no `ReasonCode`, no score, and no allocation field. Raw
  directional intersections (with Stage 12's percentage cap) and effective
  constraints (applying Stage 14's protection) both remain pending later stages.

## Deterministic Raw Increase Limit Rules (Sprint 1, Development Stage 16)

These rules govern the addition to `src/constraints.py` that combines one
already-calculated `CampaignStaticBudgetRoom` (Stage 10) and one already-calculated
`CampaignRawPercentageMovementCap` (Stage 12) into one neutral raw increase limit.
Stage 16 is a **raw, increase-specific constraint only** — it is not permission to
increase a budget, not an effective increase, not eligibility, not a recommendation,
and not a final movement amount. It does not account for a raw decrease limit,
Stage 14's protection constraint, or Stage 15's test-aware static decrease room.
`CampaignStaticBudgetRoom` and `CampaignRawPercentageMovementCap` remain the sole
authoritative sources of `room_to_static_maximum` and `raw_percentage_movement_cap`;
`src/constraints.py` never recalculates either.

- **Approved business rule: both upward constraints apply simultaneously; the
  smaller controls.** `room_to_static_maximum` prevents exceeding `maximum_budget`;
  `raw_percentage_movement_cap` limits the size of a change under the applicable
  percentage rule. Both limits apply at once, so the binding limit is the smaller of
  the two: `raw_increase_limit = min(room_to_static_maximum,
  raw_percentage_movement_cap)`.
- **Exact calculation input and authorised fields.** `static_room.campaign_id`,
  `static_room.room_to_static_maximum`, `raw_cap.campaign_id`, and
  `raw_cap.raw_percentage_movement_cap` are the only fields read. No other field of
  either model is read — in particular, `room_to_static_minimum` is never read. No
  `CampaignInput`, `ReviewSetup`, `CampaignApplicableChangePercentage`,
  `CampaignTestFloorRoom`, `CampaignProtectionConstraint`, or
  `CampaignTestAwareStaticDecreaseRoom` is ever read or called;
  `calculate_campaign_static_budget_room` and
  `calculate_campaign_raw_percentage_movement_cap` are never called (Stage 16
  consumes their already-approved outputs, never recalculates them).
- **Campaign-ID policy.** `static_room.campaign_id` must equal `raw_cap.campaign_id`,
  checked before any Decimal selection; a mismatch raises exactly
  `ValueError("Campaign IDs must match when resolving raw increase limit.")`, and no
  result is returned. Neither ID is silently preferred.
- **Exact formula:**
  ```
  raw_increase_limit = min(room_to_static_maximum, raw_percentage_movement_cap)
  ```
- **Zero and `None` behaviour.** `Decimal("0.00")` is a legitimate result when the
  smaller applicable constraint is zero (including when `room_to_static_maximum` is
  zero, `raw_percentage_movement_cap` is zero, or both are zero) — it means no raw
  increase room remains under these two constraints, not eligibility or a
  recommendation. Neither input field is optional, and the output is never `None`; no
  fallback value is substituted for either input.
- **No arithmetic.** Stage 16 performs selection and comparison only — no
  subtraction, multiplication, or division; no local `decimal` context; no
  `CURRENCY_QUANTUM`; no `ROUND_HALF_UP`; no rounding; no quantisation; no `float`
  conversion. The selected `Decimal` operand (one of the two inputs) is returned
  unchanged. Ambient global `Decimal` precision/rounding cannot affect the result,
  since no arithmetic operation is performed.
- **Separation from Stages 11, 13, 14, and 15.** `resolve_campaign_raw_increase_limit`
  never reads `applicable_max_change_percentage`, `room_to_test_floor`,
  `decrease_blocked`, or `test_aware_static_decrease_room`, and never calls
  `resolve_campaign_applicable_change_percentage`,
  `calculate_campaign_test_floor_room`, `resolve_campaign_protection_constraint`, or
  `resolve_campaign_test_aware_static_decrease_room`. A protected campaign receives
  exactly the same Stage 16 result as an otherwise identical unprotected campaign
  with matching Stage 10/12 facts — no protection-based or test-floor-based zero is
  calculated here. **Protected status has no approved increase-side effect at Stage
  16; a protected campaign is not thereby assumed unable to be increased.**
  Test-floor rules are decrease-specific and have no bearing on this result.
- **No permissible movement calculated.** The result carries no raw decrease limit,
  no combined increase/decrease model, no effective increase, no eligibility field,
  no blocking flag, no `RecommendationAction`, no `ReasonCode`, no score, and no
  allocation field. The raw decrease intersection and effective constraints (applying
  Stage 14's protection and Stage 15's test-aware decrease room) both remain pending
  later stages.

## Deterministic Raw Decrease Limit Rules (Sprint 1, Development Stage 17)

These rules govern the addition to `src/constraints.py` that combines one
already-calculated `CampaignTestAwareStaticDecreaseRoom` (Stage 15) and one
already-calculated `CampaignRawPercentageMovementCap` (Stage 12) into one neutral
raw decrease limit. Stage 17 is a **raw, decrease-specific constraint only** — it is
not permission to decrease a budget, not an effective decrease, not eligibility, not
a recommendation, and not a final movement amount. A protected campaign still
receives its neutral Stage 17 raw result — Stage 14's protection constraint is not
applied here and remains pending a later effective-constraint stage. It does not
combine with Stage 16's raw increase limit. `CampaignTestAwareStaticDecreaseRoom` and
`CampaignRawPercentageMovementCap` remain the sole authoritative sources of
`test_aware_static_decrease_room` and `raw_percentage_movement_cap`;
`src/constraints.py` never recalculates either.

- **Approved business rule: both decrease-side constraints apply simultaneously; the
  smaller controls.** `test_aware_static_decrease_room` preserves the approved
  minimum-budget/test-floor constraint (Stage 15's frozen precedence rule);
  `raw_percentage_movement_cap` limits the size of a change under the applicable
  percentage rule (Stage 12). Both limits apply at once, so the binding limit is the
  smaller of the two: `raw_decrease_limit = min(test_aware_static_decrease_room,
  raw_percentage_movement_cap)`.
- **Exact calculation input and authorised fields.** `decrease_room.campaign_id`,
  `decrease_room.test_aware_static_decrease_room`, `raw_cap.campaign_id`, and
  `raw_cap.raw_percentage_movement_cap` are the only fields read. No other field of
  either model is read. No `CampaignInput`, `ReviewSetup`,
  `CampaignStaticBudgetRoom`, `CampaignApplicableChangePercentage`,
  `CampaignTestFloorRoom`, `CampaignProtectionConstraint`, or
  `CampaignRawIncreaseLimit` is ever read or called;
  `resolve_campaign_test_aware_static_decrease_room` and
  `calculate_campaign_raw_percentage_movement_cap` are never called (Stage 17
  consumes their already-approved outputs, never recalculates them). `minimum_budget`,
  `test_budget_floor`, `is_test_campaign`, `room_to_static_minimum`,
  `room_to_test_floor`, `current_budget`, and `applicable_max_change_percentage` are
  never reopened — Stage 15's already-resolved precedence is not duplicated.
- **Campaign-ID policy.** `decrease_room.campaign_id` must equal `raw_cap.campaign_id`,
  checked before any Decimal selection; a mismatch raises exactly
  `ValueError("Campaign IDs must match when resolving raw decrease limit.")`, and no
  result is returned. Neither ID is silently preferred.
- **Exact formula:**
  ```
  raw_decrease_limit = min(test_aware_static_decrease_room, raw_percentage_movement_cap)
  ```
- **Zero, negative, and `None` behaviour.** `Decimal("0.00")` is a legitimate result
  when the smaller applicable constraint is zero (including when either or both
  inputs are zero) — it means no raw decrease room remains under these two
  constraints, not protection, eligibility, or a recommendation. A negative result is
  structurally impossible: `test_aware_static_decrease_room` and
  `raw_percentage_movement_cap` are both guaranteed non-negative by their own
  upstream Stage 10/12/13/15 invariants, and `min()` of two non-negative Decimals is
  non-negative. Neither input field is optional, and the output is never `None`; no
  fallback value is substituted for either.
- **No arithmetic.** Stage 17 performs selection and comparison only — no
  subtraction, multiplication, or division; no local `decimal` context; no
  `CURRENCY_QUANTUM`; no `ROUND_HALF_UP`; no rounding; no quantisation; no `float`
  conversion. The selected `Decimal` operand (one of the two inputs) is returned
  unchanged. Ambient global `Decimal` precision/rounding cannot affect the result,
  since no arithmetic operation is performed.
- **Separation from Stages 10, 11, 13, 14, and 16.** `resolve_campaign_raw_decrease_limit`
  never reads `room_to_static_maximum`, `room_to_static_minimum`,
  `applicable_max_change_percentage`, `room_to_test_floor`, `decrease_blocked`,
  `is_protected`, or `raw_increase_limit`, and never calls
  `calculate_campaign_static_budget_room`,
  `resolve_campaign_applicable_change_percentage`,
  `calculate_campaign_test_floor_room`, `resolve_campaign_protection_constraint`, or
  `resolve_campaign_raw_increase_limit`. A protected campaign receives exactly the
  same Stage 17 result as an otherwise identical unprotected campaign with matching
  Stage 12/15 facts — no protection-based zero is calculated here, and the result is
  never described as usable or permissible decrease for a protected campaign.
  Test-campaign status affects Stage 17 only indirectly, through Stage 15's
  already-resolved `test_aware_static_decrease_room` value — Stage 17 itself never
  reads `is_test_campaign` or `test_budget_floor`, and never reopens Stage 15's
  stricter-floor precedence.
- **No permissible movement calculated.** The result carries no raw increase limit,
  no combined increase/decrease model, no effective decrease, no eligibility field,
  no blocking flag, no `RecommendationAction`, no `ReasonCode`, no score, and no
  allocation field. Protection application and effective directional constraints
  (combining Stage 16's raw increase limit, this Stage 17 raw decrease limit, and
  Stage 14's protection constraint) both remain pending later stages.

## Pending

- **Trend-to-ReasonCode mapping.** Stage 6 resolved how `TREND_THRESHOLD` classifies
  `trend_delta` into a neutral `TrendDirection` (see above) — but a `TrendDirection` is
  not a `ReasonCode`. Whether/how `TrendDirection.IMPROVING`/`STABLE`/`DECLINING` maps to
  `ReasonCode.RECENT_TREND_IMPROVING`/`STABLE`/`DECLINING`, and how trend combines with
  `PerformanceBand`, confidence, or tracking into any final judgement, remains pending a
  later stage.
- **Final recommendation.** Stage 5 resolved how `INCREASE_THRESHOLD`/
  `MAINTAIN_THRESHOLD` classify `weighted_performance_ratio` into a neutral
  `PerformanceBand` (see above) — but a `PerformanceBand` is not a `RecommendationAction`.
  `RecommendationAction` has a fourth member, `HOLD`, that cannot be derived from
  performance ratio thresholds alone; assigning a final `RecommendationAction` requires
  combining `PerformanceBand` with trend, confidence, tracking, and eligibility/
  constraint considerations that remain pending later stages.
- **`NOT_ASSESSABLE` trigger and combined assessment.** Stage 7 resolved
  `conversions_28d` → `Confidence.HIGH`/`MEDIUM`/`LOW`, Stage 8 resolved
  `tracking_status` → `is_assessable`/`CampaignTrackingAssessment`, and Stage 9 resolved
  `pacing_ratio` → `PacingStatus`/`CampaignPacingClass` (see above) — but none of the
  three assigns `Confidence.NOT_ASSESSABLE`, and no rule combines any of the three
  independent results with each other or with `PerformanceBand`/`TrendDirection`.
  Whether/how tracking-based assessability, conversion-volume confidence, and pacing
  status relate to `Confidence.NOT_ASSESSABLE` remains pending a later combined-
  assessment stage, which must preserve Stage 7's, Stage 8's, and Stage 9's independent
  results rather than overwriting any of them.
- **Effective constraints, eligibility.** Stage 10 resolved the static budget-bound
  distances (`room_to_static_maximum`/`room_to_static_minimum`), Stage 11 resolved
  which percentage applies to a campaign (`applicable_max_change_percentage`), Stage
  12 resolved the raw percentage-based monetary cap (`raw_percentage_movement_cap`),
  Stage 13 resolved the raw test-floor distance (`room_to_test_floor`), Stage 14
  resolved the decrease-specific protection constraint (`decrease_blocked`), Stage 15
  resolved the test-aware static decrease room (`test_aware_static_decrease_room`),
  Stage 16 resolved the raw increase limit (`raw_increase_limit`), and Stage 17
  resolved the raw decrease limit (`raw_decrease_limit`, see above), but increase-
  and decrease-side protection application is entirely unaddressed, and no rule
  computes the campaign's *effective* permissible budget movement (i.e. adjusting
  Stage 16's and Stage 17's raw limits for Stage 14's protection constraint). No
  eligibility concept is defined anywhere in the repository. All remain pending later
  stages.
- The full set of `ReasonCode` trigger conditions.
- Allocation and conservation rules.
