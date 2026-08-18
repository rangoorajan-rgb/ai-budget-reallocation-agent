# Decision Rules

> Sprint 2, Development Stage 21. Records the frozen enumerations, frozen numerical
> constants, the frozen deterministic validation rules, the frozen deterministic
> metric-calculation rules, the frozen deterministic pacing-calculation rules, the frozen
> neutral performance-, trend-, conversion-volume-confidence-, and
> tracking-assessability-classification rules, the frozen neutral pacing-interpretation
> rules, the frozen static budget-bound calculation rules, the frozen applicable-
> change-percentage resolution rule, the frozen raw percentage-based monetary
> movement-cap calculation rule, the frozen test-floor distance calculation rule, the
> frozen protection constraint rule, the frozen test-aware static decrease-room rule,
> the frozen raw increase limit rule, the frozen raw decrease limit rule, the frozen
> protection-adjusted effective decrease limit rule, the frozen campaign action
> availability rule, the frozen conservative diagonal-only campaign action
> suitability rule, and the frozen ordered campaign recommendation-action
> selection rule. Combined assessment, `Confidence.NOT_ASSESSABLE` ownership,
> `ReasonCode`, numeric prioritisation scoring, ranking, and allocation rules are
> pending later Sprint 2 stages.

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
Sprint 2 stages.

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

## Deterministic Validation Rules (Sprint 2, Development Stage 2)

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

## Deterministic Metric Calculation Rules (Sprint 2, Development Stage 3)

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

## Deterministic Pacing Calculation Rules (Sprint 2, Development Stage 4)

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

## Deterministic Performance Classification Rules (Sprint 2, Development Stage 5)

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

## Deterministic Trend Classification Rules (Sprint 2, Development Stage 6)

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

## Deterministic Conversion-Volume Confidence Classification Rules (Sprint 2, Development Stage 7)

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

## Deterministic Tracking-Based Assessability Rules (Sprint 2, Development Stage 8)

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

## Deterministic Pacing Interpretation Rules (Sprint 2, Development Stage 9)

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

## Deterministic Static Budget-Bound Calculation Rules (Sprint 2, Development Stage 10)

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

## Deterministic Applicable Change-Percentage Resolution Rules (Sprint 2, Development Stage 11)

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

## Deterministic Raw Percentage-Based Monetary Movement-Cap Calculation Rules (Sprint 2, Development Stage 12)

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

## Deterministic Test-Floor Distance Calculation Rules (Sprint 2, Development Stage 13)

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

## Deterministic Protection Constraint Rules (Sprint 2, Development Stage 14)

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

## Deterministic Test-Aware Static Decrease Room Rules (Sprint 2, Development Stage 15)

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

## Deterministic Raw Increase Limit Rules (Sprint 2, Development Stage 16)

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

## Deterministic Raw Decrease Limit Rules (Sprint 2, Development Stage 17)

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

## Deterministic Protection-Adjusted Effective Decrease Limit Rules (Sprint 2, Development Stage 18)

These rules govern the addition to `src/constraints.py` that applies one
already-calculated `CampaignProtectionConstraint` (Stage 14) to one already-
calculated `CampaignRawDecreaseLimit` (Stage 17), producing one protection-adjusted
effective decrease limit. The output represents the effective decrease limit under
the currently approved static minimum-budget constraint, test-floor constraint,
percentage movement constraint, and protection constraint. It is **still not**
eligibility, a recommendation, a final movement amount, an allocation, or a decision
to decrease the campaign — a campaign with `effective_decrease_limit ==
Decimal("0.00")` may still later be eligible for `MAINTAIN` or `INCREASE`. Stage 18
does not produce an effective increase limit. `CampaignRawDecreaseLimit` and
`CampaignProtectionConstraint` remain the sole authoritative sources of
`raw_decrease_limit` and `decrease_blocked`; `src/constraints.py` never recalculates
either.

- **Approved business rule.** `decrease_blocked=True` means only that protection
  prohibits reducing the campaign; the effective decrease limit under that
  constraint is therefore `Decimal("0.00")`, a deliberate, computed effective
  constraint, never missing data. `decrease_blocked=False` means protection itself
  adds no further restriction beyond what Stage 17 already computed, so
  `raw_decrease_limit` passes through unchanged — this does not mean a decrease
  should occur.
- **Why `Decimal("0.00")` is used instead of `None`.** Every existing `None` in the
  repository (Stage 4's `pacing_ratio`, Stage 13's `room_to_test_floor`) means "this
  fact does not apply / could not be computed." Protection-triggered zero is the
  opposite: a computed, deterministic decision that a definite quantity of decrease
  room (zero) is available under this constraint. Using `None` here would misuse
  the established non-applicability vocabulary; `Decimal("0.00")` correctly signals
  a valid, deliberate effective constraint, consistent with the zero-is-meaningful
  pattern already established at Stages 10, 12, 15, 16, and 17.
- **Exact calculation input and authorised fields.** `raw_decrease.campaign_id`,
  `raw_decrease.raw_decrease_limit`, `protection.campaign_id`, and
  `protection.decrease_blocked` are the only fields read. No other field of either
  model is read. No `CampaignInput`, `ReviewSetup`, `CampaignStaticBudgetRoom`,
  `CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`,
  `CampaignTestFloorRoom`, `CampaignTestAwareStaticDecreaseRoom`, or
  `CampaignRawIncreaseLimit` is ever read or called;
  `resolve_campaign_raw_decrease_limit` and `resolve_campaign_protection_constraint`
  are never called (Stage 18 consumes their already-approved outputs, never
  recalculates them). `is_protected`, `current_budget`, `minimum_budget`,
  `maximum_budget`, `test_budget_floor`, `is_test_campaign`,
  `applicable_max_change_percentage`, `room_to_static_minimum`,
  `room_to_test_floor`, `test_aware_static_decrease_room`, and
  `raw_percentage_movement_cap` are never reopened.
- **Campaign-ID policy.** `raw_decrease.campaign_id` must equal
  `protection.campaign_id`, checked before reading `decrease_blocked` for selection
  or resolving any Decimal result; a mismatch raises exactly
  `ValueError("Campaign IDs must match when resolving effective decrease limit.")`,
  and no result is returned. Neither ID is silently preferred.
- **Exact mapping:**
  ```
  effective_decrease_limit = (
      Decimal("0.00")
      if protection.decrease_blocked
      else raw_decrease.raw_decrease_limit
  )
  ```
- **Decimal/Boolean policy.** Only conditional selection is performed — no
  subtraction, multiplication, or division; no local `decimal` context; no
  `CURRENCY_QUANTUM`; no `ROUND_HALF_UP`; no rounding; no quantisation; no `float`
  conversion. The literal `Decimal("0.00")` is constructed only for the protected
  branch, using the existing `Decimal` import (no new `ZERO` constant is added to
  `src/constants.py`); the unprotected branch returns the selected `Decimal`
  operand unchanged. Ambient global `Decimal` precision/rounding cannot affect
  either branch, since no arithmetic operation is performed.
- **Raw-fact preservation.** `CampaignEffectiveDecreaseLimit` does not repeat
  `raw_decrease_limit` or `decrease_blocked` as fields, and neither input is
  mutated (both are `frozen=True`, and Stage 18 constructs an entirely new result
  object). A caller retains full traceability by holding
  `CampaignProtectionConstraint` (Stage 14), `CampaignRawDecreaseLimit` (Stage 17),
  and `CampaignEffectiveDecreaseLimit` (Stage 18) as three separate,
  independently-inspectable objects.
- **Separation from Stage 16.** Stage 18 never reads or accepts
  `CampaignRawIncreaseLimit` or `raw_increase_limit`, and produces no
  `effective_increase_limit` field or `CampaignEffectiveIncreaseLimit` model. No
  approved constraint remains to transform Stage 16's raw increase limit, and
  **protection has no approved increase-side effect** — `CampaignRawIncreaseLimit`
  remains the authoritative increase-side constraint unless a later approved rule
  changes it.
- **No permissible movement, eligibility, or later judgement calculated.** The
  result carries no eligibility field, no blocking flag beyond the Decimal itself,
  no `RecommendationAction`, no `ReasonCode`, no score, and no allocation field. A
  campaign with `effective_decrease_limit == Decimal("0.00")` may still later be
  eligible for `MAINTAIN` or `INCREASE` — zero in the decrease direction does not
  make the whole campaign ineligible. Eligibility and the combined campaign-
  assessment question (performance, trend, confidence, tracking, pacing) both
  remain deferred to later stages.

## Deterministic Campaign Action Availability Rules (Sprint 2, Development Stage 19)

These rules govern `src/availability.py`, a new dedicated module, which determines
for one already-validated `CampaignInput` and its already-approved Stage 8, Stage
16, and Stage 18 results whether `INCREASE`, `MAINTAIN`, and `REDUCE` are each
mechanically and operationally available. Stage 19 is a **narrow mechanical gate
only** — it does not decide which available action is suitable, which action
should be recommended, `HOLD`, scoring, priority, ranking, `ReasonCode`, or
allocation. The term **"availability,"** never "eligibility," is used throughout.
Availability means an action is not prevented by campaign status, tracking-based
assessability, or the relevant approved monetary capacity — it does not mean the
action is advisable. Positive capacity means only that the direction is
mechanically possible, never a recommendation.

- **Exact calculation input and authorised fields.** `campaign.campaign_id`,
  `campaign.status`, `tracking.campaign_id`, `tracking.is_assessable`,
  `raw_increase.campaign_id`, `raw_increase.raw_increase_limit`,
  `effective_decrease.campaign_id`, and `effective_decrease.effective_decrease_limit`
  are the only eight fields read, across exactly four input objects
  (`CampaignInput`, `CampaignTrackingAssessment`, `CampaignRawIncreaseLimit`,
  `CampaignEffectiveDecreaseLimit`). No other field of any of the four is read —
  in particular, `tracking_status`, `is_protected`, `decrease_blocked`,
  `is_test_campaign`, `test_budget_floor`, `minimum_budget`, `maximum_budget`, and
  every performance/trend/confidence/pacing/business-priority field are never
  read. `assess_campaign_tracking`, `resolve_campaign_raw_increase_limit`, and
  `resolve_campaign_effective_decrease_limit` are never called (Stage 19 consumes
  their already-approved outputs, never recalculates them), nor is any other
  Stage 1–18 production function.
- **Campaign-ID policy.** All four `campaign_id` values must match, checked as
  the first statement before reading `campaign.status`, `tracking.is_assessable`,
  or comparing either `Decimal` limit — one combined equality check anchored to
  `campaign.campaign_id`. A mismatch raises exactly
  `ValueError("Campaign IDs must match when resolving action availability.")`,
  with no result returned, no ID silently preferred, and no partial evaluation.
  The same exact message is used regardless of which input(s) mismatch or how
  many — no per-object mismatch reporting exists.
- **Exact mapping:**
  ```
  is_active = campaign.status is CampaignStatus.ACTIVE

  increase_available = (
      is_active
      and tracking.is_assessable
      and raw_increase.raw_increase_limit > Decimal("0.00")
  )

  maintain_available = is_active

  reduce_available = (
      is_active
      and tracking.is_assessable
      and effective_decrease.effective_decrease_limit > Decimal("0.00")
  )
  ```
- **Status policy.** For `CampaignStatus.PAUSED`, all three fields are `False`.
  A Paused campaign always receives one `CampaignActionAvailability` result
  object — it is never omitted, and Paused status never raises an error, never
  selects `HOLD`, and never produces a reason code.
- **Tracking-assessability policy.** `is_assessable=False` on an `Active`
  campaign blocks `increase_available` and `reduce_available` but not
  `maintain_available` — acting on unreliable data is prevented in both budget-
  change directions equally, while leaving the budget unchanged requires no data
  confidence. `TrackingStatus.WARNING` remains assessable purely because Stage 8
  already returns `is_assessable=True` for it — Stage 19 consumes
  `is_assessable` only and never reopens or reproduces Stage 8's
  `tracking_status`-to-`is_assessable` mapping.
- **Zero/positive capacity policy.** `raw_increase_limit > Decimal("0.00")` and
  `effective_decrease_limit > Decimal("0.00")` are each necessary (alongside
  active status and assessability) for their respective direction's
  availability; exactly `Decimal("0.00")` makes that direction unavailable.
  Positive capacity is never a recommendation. Upstream Stage 10–18 invariants
  make negative values structurally impossible, so no new negative-value
  correction, clamping, or fallback logic is introduced.
- **Exclusion of confidence, pacing, performance, trend, and priority.**
  `Confidence` (including any `Confidence.NOT_ASSESSABLE` relationship),
  `PacingStatus` (including `PacingStatus.NOT_AVAILABLE`), `PerformanceBand`,
  `TrendDirection`, and `BusinessPriority` are never read anywhere in Stage 19 —
  these are suitability/scoring inputs, not availability inputs, and no rule
  combining them with availability is invented here.
- **No `ReasonCode` or `HOLD` mapping.** Stage 19 outputs no reason codes.
  `PAUSED_CAMPAIGN`, `TRACKING_UNRELIABLE`, `PROTECTED_FROM_REDUCTION`, and every
  other `ReasonCode` member remain unassigned and unmapped by this stage — that
  mapping is deferred until a later outcome/recommendation stage.
  `RecommendationAction.HOLD` is never created or selected by Stage 19; `HOLD`'s
  exact trigger remains undecided, reserved for a later review/deferral or
  recommendation stage.
- **Separation from scoring and `RecommendationAction`.** `CampaignActionAvailability`
  carries no score, priority, ranking, `RecommendationAction`, or allocation
  field — it is strictly a mechanical availability fact, consumed by a later,
  still-undesigned suitability/scoring stage that combines it with the excluded
  classification signals to select exactly one final action per campaign.
- **`CampaignInput` ownership.** Stage 19 accepts `CampaignInput` directly for
  campaign identity and status — no separate status-wrapper model was created,
  since one would only duplicate `campaign_id` and `status` without producing
  any new fact. This mirrors the precedent already established at Stage 14
  (`resolve_campaign_protection_constraint(campaign: CampaignInput)`), which
  also resolves a raw `CampaignInput` field into a new result without an
  intermediate wrapper.
- **Dedicated module.** `src/availability.py` is a new production module,
  distinct from `src/constraints.py`, `src/classification.py`, and
  `src/scoring.py` — action availability spans campaign status, tracking
  assessability, and both directional monetary constraints simultaneously, and
  is not purely a monetary constraint, a descriptive classification, or a score.

## Deterministic Conservative Diagonal-Only Campaign Action Suitability Rules (Sprint 2, Development Stage 20)

These rules govern `src/suitability.py`, a new dedicated module, which
determines for one already-calculated `CampaignPerformanceClass` (Stage 5), one
already-calculated `CampaignTrendClass` (Stage 6), and one already-calculated
`CampaignActionAvailability` (Stage 19) a categorical, per-direction suitability
for `INCREASE`, `MAINTAIN`, and `REDUCE`. Availability answers "can this action
be taken mechanically and operationally?"; suitability answers "do the approved
performance and trend classifications provide a clear directional signal
supporting this available action?" Suitability does **not** mean recommendation
— a `SUITABLE` action is not automatically selected, a `NEUTRAL` action is not
automatically rejected, and an `UNSUITABLE` action is not a final prohibition.
Stage 20 must not select `RecommendationAction`, select `HOLD`, produce
`ReasonCode`, produce a numeric score, rank campaigns, or apply `Confidence`,
`PacingStatus`, or `BusinessPriority`.

- **Approved rule approach: conservative diagonal-only policy.** Only the three
  cells where `PerformanceBand` and `TrendDirection` clearly agree
  (`ABOVE_TARGET`+`IMPROVING`, `ON_TARGET`+`STABLE`, `BELOW_TARGET`+`DECLINING`)
  produce a directional `SUITABLE`/`UNSUITABLE` result. All six conflicting or
  mixed combinations resolve to `NEUTRAL` for every direction. This
  deliberately avoids deciding whether performance or trend has precedence
  when they disagree.
- **Exact nine-cell base rule table** (before applying the availability
  override; each cell is `(increase, maintain, reduce)`):
  ```
  ABOVE_TARGET + IMPROVING  → SUITABLE,   NEUTRAL, UNSUITABLE
  ABOVE_TARGET + STABLE     → NEUTRAL,    NEUTRAL, NEUTRAL
  ABOVE_TARGET + DECLINING  → NEUTRAL,    NEUTRAL, NEUTRAL
  ON_TARGET    + IMPROVING  → NEUTRAL,    NEUTRAL, NEUTRAL
  ON_TARGET    + STABLE     → NEUTRAL,    SUITABLE, NEUTRAL
  ON_TARGET    + DECLINING  → NEUTRAL,    NEUTRAL, NEUTRAL
  BELOW_TARGET + IMPROVING  → NEUTRAL,    NEUTRAL, NEUTRAL
  BELOW_TARGET + STABLE     → NEUTRAL,    NEUTRAL, NEUTRAL
  BELOW_TARGET + DECLINING  → UNSUITABLE, NEUTRAL, SUITABLE
  ```
  The table is implemented as a module-level immutable mapping
  (`MappingProxyType`), containing exactly all nine
  `PerformanceBand`×`TrendDirection` keys, never mutated at runtime, and
  containing no numeric weight, `RecommendationAction`, or `ReasonCode`. No
  enum declaration order is depended upon — the table is keyed by explicit
  enum-value tuples, not iteration order.
- **Availability-first override rule.** After the base-table lookup,
  availability is applied independently per direction: if
  `availability.increase_available` is `False`,
  `increase_suitability = Suitability.NOT_APPLICABLE`, overriding whatever the
  base table would otherwise say — the same independent rule applies to
  `maintain_suitability`/`maintain_available` and
  `reduce_suitability`/`reduce_available`. Availability always overrides the
  base suitability table. `NOT_APPLICABLE` is never represented as `None`, a
  numeric zero, or `UNSUITABLE`.
- **Exact calculation input and authorised fields.** `performance.campaign_id`,
  `performance.performance_band`, `trend.campaign_id`,
  `trend.trend_direction`, `availability.campaign_id`,
  `availability.increase_available`, `availability.maintain_available`, and
  `availability.reduce_available` are the only eight fields read, across
  exactly three input objects (`CampaignPerformanceClass`,
  `CampaignTrendClass`, `CampaignActionAvailability`). No `CampaignInput` or
  `ReviewSetup` is accepted. `classify_campaign_performance`,
  `classify_campaign_trend`, and `resolve_campaign_action_availability` are
  never called (Stage 20 consumes their already-approved outputs, never
  recalculates them), nor is any other Stage 1–19 production function.
- **Campaign-ID policy.** All three `campaign_id` values must match, checked
  as the first statement before reading `performance_band`, `trend_direction`,
  looking up the rule table, or reading any availability field — one combined
  equality check anchored to `performance.campaign_id`. A mismatch raises
  exactly `ValueError("Campaign IDs must match when resolving action
  suitability.")`, with no result returned, no ID silently preferred, and the
  same exact message regardless of which input(s) mismatch.
- **`Suitability` enum policy.** `SUITABLE`, `NEUTRAL`, `UNSUITABLE`, and
  `NOT_APPLICABLE` are purely categorical — no numeric value, no ordering, and
  no `SUITABLE > NEUTRAL`-style comparison is defined or implied anywhere.
- **Exclusion of confidence, pacing, and business priority.** `Confidence`
  (including any `Confidence.NOT_ASSESSABLE` relationship), `PacingStatus`,
  and `BusinessPriority` are never read anywhere in Stage 20 — these remain
  suitability/scoring inputs deferred to a later stage. The
  `Confidence.NOT_ASSESSABLE` trigger is not derived from
  `tracking.is_assessable` here, and remains unresolved.
- **Tracking and MAINTAIN.** Stage 20 does not accept
  `CampaignTrackingAssessment` — it consumes Stage 19's already-resolved
  availability only. For an Active but unassessable campaign, Stage 19 already
  makes `INCREASE` and `REDUCE` unavailable, so Stage 20 returns
  `NOT_APPLICABLE` for both; `MAINTAIN` remains available under Stage 19 and
  receives its base-table result. This does not prevent a later
  `RecommendationAction` stage from selecting `HOLD` because the data is
  unreliable — Stage 20 never decides `MAINTAIN` versus `HOLD`.
- **No `ReasonCode` output.** Stage 20 does not map suitability to
  `ABOVE_TARGET_STRONG`, `BELOW_TARGET_MODERATE`, `BELOW_TARGET_SEVERE`,
  `NEAR_TARGET`, `RECENT_TREND_IMPROVING`, `RECENT_TREND_STABLE`,
  `RECENT_TREND_DECLINING`, or any tracking/constraint/availability reason —
  reason codes require a later `RecommendationAction` or outcome context.
- **No combined-assessment model.** Stage 20 does not create a data-carrier
  model copying `PerformanceBand`, `TrendDirection`, `Confidence`,
  `PacingStatus`, or tracking facts — it consumes the three approved result
  objects directly.
- **No numeric scoring or weights.** No `Decimal` import, arithmetic, local
  Decimal context, `CURRENCY_QUANTUM`, `ROUND_HALF_UP`, or `float` conversion
  is used anywhere — only enum-identity comparison, a fixed mapping lookup,
  and Boolean gating.
- **Dedicated module.** `src/suitability.py` is a new production module,
  distinct from `src/classification.py`, `src/constraints.py`,
  `src/availability.py`, and `src/scoring.py` — suitability combines
  classification-domain performance, classification-domain trend, and
  availability-domain action gates, and is not a raw classification, a
  monetary constraint, availability, or numeric scoring. `src/scoring.py`
  remains unchanged, reserved for later numeric prioritisation-scoring work.

## Deterministic Ordered Campaign Recommendation-Action Selection Rules (Sprint 2, Development Stage 21)

These rules govern `src/recommendation.py`, a new dedicated module, which
selects for one already-validated `CampaignInput`, one already-calculated
`CampaignActionSuitability` (Stage 20), and one already-calculated
`CampaignTrackingAssessment` (Stage 8) exactly one `RecommendationAction` —
`INCREASE`, `MAINTAIN`, `REDUCE`, or `HOLD` — per campaign.
`RecommendationAction` selection here is a **provisional direction only** —
not a monetary amount, not a `ReasonCode`, not a score, not a rank, and not a
final allocated movement.

- **HOLD versus MAINTAIN.** `MAINTAIN` means the campaign was eligible for
  automated assessment, no available action had a uniquely stronger
  directional suitability, and keeping the budget unchanged is the selected
  recommendation — an assessed no-change decision. `HOLD` means the engine
  must not make an automated directional budget recommendation for this
  review — because the campaign is paused, its tracking is unassessable, its
  suitability input is ambiguous, or no valid fallback action is available.
  `HOLD` is a review/deferral outcome; `MAINTAIN` is an assessed no-change
  recommendation.
- **Exact ordered policy**, applied after campaign-ID validation:
  ```
  1. Paused override:            campaign.status is PAUSED           → HOLD
  2. Assessability override:     not tracking.is_assessable          → HOLD
  3. Unique-SUITABLE selection:  exactly one field is SUITABLE       → that action
  4. Multiple-SUITABLE ambiguity: more than one field is SUITABLE    → HOLD
  5. Conservative MAINTAIN:      no SUITABLE, maintain is NEUTRAL    → MAINTAIN
  6. Final HOLD fallback:        no SUITABLE, maintain is UNSUITABLE
                                  or NOT_APPLICABLE                  → HOLD
  ```
  Rules 1 and 2 override every suitability value unconditionally. Rule 4
  applies no fixed precedence, no first-field selection, no `MAINTAIN`
  default, and raises no error — although multiple `SUITABLE` values cannot
  arise through the approved Stage 20 production table, a directly
  constructed `CampaignActionSuitability` could contain them, and `HOLD` is
  the approved deterministic ambiguity outcome. Rule 5's `MAINTAIN` fallback
  does not require `increase_suitability`/`reduce_suitability` to be
  `NEUTRAL` — they may independently be `NEUTRAL`, `UNSUITABLE`, or
  `NOT_APPLICABLE`. `MAINTAIN` is never selected when it is itself
  explicitly `UNSUITABLE` or `NOT_APPLICABLE` (Rule 6).
- **`NOT_APPLICABLE` policy.** `RecommendationAction` has no
  `NOT_APPLICABLE` member. A suitability value of `NOT_APPLICABLE` is never
  selected as an action — it participates only by preventing that direction
  from being uniquely `SUITABLE`. If all three suitability fields are
  `NOT_APPLICABLE`, Rule 6 resolves to `HOLD`.
- **Exact calculation input and authorised fields.** `campaign.campaign_id`,
  `campaign.status`, `suitability.campaign_id`,
  `suitability.increase_suitability`, `suitability.maintain_suitability`,
  `suitability.reduce_suitability`, `tracking.campaign_id`, and
  `tracking.is_assessable` are the only eight fields read, across exactly
  three input objects (`CampaignInput`, `CampaignActionSuitability`,
  `CampaignTrackingAssessment`). `CampaignActionAvailability` is not
  accepted separately, since Stage 20 has already applied availability
  through `NOT_APPLICABLE`. `assess_campaign_tracking`,
  `resolve_campaign_action_suitability`, and
  `resolve_campaign_action_availability` are never called (Stage 21
  consumes their already-approved outputs, never recalculates them), nor is
  any other Stage 1–20 production function. `is_protected`,
  `decrease_blocked`, `is_test_campaign`, `test_budget_floor`, and
  `tracking_status` are never read — their effects are already fully
  absorbed upstream into availability and suitability.
- **Campaign-ID policy.** All three `campaign_id` values must match, checked
  as the first statement before reading `campaign.status`,
  `tracking.is_assessable`, or any suitability field — one combined equality
  check anchored to `campaign.campaign_id`. A mismatch raises exactly
  `ValueError("Campaign IDs must match when resolving recommendation
  action.")`, with no result returned, no ID silently preferred, and the
  same exact message regardless of which input(s) mismatch.
- **Explicit status ownership.** `campaign.status` is read directly from
  `CampaignInput` — Paused status is never inferred from suitability shape
  (e.g. from `maintain_suitability == NOT_APPLICABLE`), even though such an
  inference happens to be structurally valid under Stage 19's current
  frozen rule; explicit reading was chosen for clarity and independence
  from any future change to that rule.
- **Protected and test campaigns.** No protection or test field is read
  directly. A protected campaign may still receive `INCREASE` or
  `MAINTAIN`; `REDUCE` is structurally unavailable for a protected campaign
  through the approved Stage 18–20 path (its `reduce_suitability` is always
  `NOT_APPLICABLE`), so Rule 6/3 never selects it. A test campaign follows
  ordinary Stage 21 selection from its supplied suitability, with no
  special-case logic.
- **Exclusion of confidence, pacing, and business priority.** `Confidence`,
  `PacingStatus`, and `BusinessPriority` are never read anywhere in Stage
  21 — no `LOW`-confidence-to-`HOLD`, `NOT_ASSESSABLE`-confidence-to-`HOLD`,
  `NOT_AVAILABLE`-pacing-to-`HOLD`, or priority-based selection rule is
  inferred; all remain unresolved and deferred.
- **No `ReasonCode` output.** Stage 21 does not map Paused to
  `PAUSED_CAMPAIGN`, unassessable to `TRACKING_UNRELIABLE`, protected to
  `PROTECTED_FROM_REDUCTION`, suitability to any performance/trend reason
  code, or `HOLD` to `HELD_FOR_MANUAL_REVIEW` — `ReasonCode` remains a
  separate Stage 22 responsibility.
- **Enum policy.** The existing `RecommendationAction` enum is reused
  unchanged — no second action enum, no numeric ordering or weights, and no
  dependence on enum declaration order. No `Decimal` calculation occurs
  anywhere in Stage 21.
- **Dedicated module.** `src/recommendation.py` is a new production module,
  distinct from `src/classification.py`, `src/constraints.py`,
  `src/availability.py`, `src/suitability.py`, and `src/scoring.py` —
  Stage 21 selects a recommendation outcome, a responsibility separate from
  classification, constraints, availability, suitability, scoring, or
  allocation.

### Stage 22 — Deterministic Campaign Recommendation Reasons

- **Rule.** For one already-selected `CampaignRecommendation` (Stage 21),
  `resolve_campaign_recommendation_reason` produces a non-empty, ordered,
  deduplicated tuple of `ReasonCode` explaining only the facts that
  causally participated in Stage 21's decision — never a diagnostic fact
  Stage 21 never consulted, an explanation for an unavailable alternative
  action, or a monetary constraint.
- **HOLD precedence**, mirroring Stage 21's exact rule order:
  ```
  1. campaign.status is PAUSED           → (PAUSED_CAMPAIGN,)
  2. not tracking.is_assessable          → (TRACKING_UNRELIABLE,)
  3. otherwise (multiple-SUITABLE ambiguity,
     or no valid MAINTAIN fallback)      → (HELD_FOR_MANUAL_REVIEW,)
  ```
  Rule 1 remains the sole reason even when tracking is simultaneously
  unassessable — Stage 21's own short-circuit logic never reaches the
  assessability check once Paused has already resolved `HOLD`, so citing
  `TRACKING_UNRELIABLE` too would cite a fact Stage 21 never actually
  consulted on that execution path. Rule 3 covers both remaining ways
  Stage 21 can produce `HOLD` (multiple-`SUITABLE` ambiguity and no valid
  `MAINTAIN` fallback) with the same code, since no more specific approved
  code exists for either. `HELD_FOR_MANUAL_REVIEW` is never used for a
  non-HOLD action — `MAINTAIN` is itself an assessed, confident decision,
  not a deferral.
- **INCREASE/MAINTAIN/REDUCE mapping.** Two fixed, immutable lookup
  tables, applied to `performance.performance_band`/`trend.trend_direction`
  — the same pair Stage 20 used to determine suitability — with the
  performance reason (when available) preceding the trend reason:
  ```
  ABOVE_TARGET → ABOVE_TARGET_STRONG      BELOW_TARGET → (no performance reason)
  ON_TARGET    → NEAR_TARGET

  IMPROVING → RECENT_TREND_IMPROVING
  STABLE    → RECENT_TREND_STABLE
  DECLINING → RECENT_TREND_DECLINING
  ```
  `BELOW_TARGET` intentionally omits a performance reason — no approved
  severity classification exists to choose between `BELOW_TARGET_MODERATE`
  and `BELOW_TARGET_SEVERE`; this is a documented limitation, not an
  invitation to invent a threshold. This produces exactly the seven
  approved `MAINTAIN` mappings (`ABOVE_TARGET`+`STABLE`,
  `ABOVE_TARGET`+`DECLINING`, `ON_TARGET`+`IMPROVING`, `ON_TARGET`+`STABLE`,
  `ON_TARGET`+`DECLINING`, `BELOW_TARGET`+`IMPROVING`,
  `BELOW_TARGET`+`STABLE`) and additionally, consistently, the two
  `MAINTAIN` outcomes reachable only when Stage 19 availability blocks an
  otherwise diagonal-`SUITABLE` direction (`ABOVE_TARGET`+`IMPROVING` with
  `INCREASE` unavailable; `BELOW_TARGET`+`DECLINING` with `REDUCE`
  unavailable) — the identical, already-approved performance/trend mapping
  applied unchanged, not a new invented rule.
- **Exact calculation input and authorised fields.**
  `recommendation.campaign_id`, `recommendation.recommendation_action`,
  `campaign.campaign_id`, `campaign.status`, `suitability.campaign_id`,
  `suitability.increase_suitability`, `suitability.maintain_suitability`,
  `suitability.reduce_suitability`, `tracking.campaign_id`,
  `tracking.is_assessable`, `performance.campaign_id`,
  `performance.performance_band`, `trend.campaign_id`, and
  `trend.trend_direction` are the only fourteen fields read, across
  exactly six input objects (`CampaignRecommendation`, `CampaignInput`,
  `CampaignActionSuitability`, `CampaignTrackingAssessment`,
  `CampaignPerformanceClass`, `CampaignTrendClass`).
  `resolve_campaign_recommendation_action` and every other Stage 1–21
  production function are never called — Stage 22 consumes their
  already-approved outputs, never recalculates them. No raw metric,
  monetary constraint result, `Confidence`, `PacingStatus`,
  `tracking_status`, `is_protected`, `is_test_campaign`,
  `test_budget_floor`, or `BusinessPriority` is read.
- **Campaign-ID policy.** All six `campaign_id` values must match, checked
  as the first statement before any reason is resolved — one combined
  equality check anchored to `recommendation.campaign_id`. A mismatch
  raises exactly `ValueError("Campaign IDs must match when resolving
  recommendation reasons.")`, with no result returned, no ID silently
  preferred, and the same exact message regardless of which input(s)
  mismatch.
- **Approved reason-code scope.** Exactly eight existing `ReasonCode`
  members may be emitted: `PAUSED_CAMPAIGN`, `TRACKING_UNRELIABLE`,
  `HELD_FOR_MANUAL_REVIEW`, `ABOVE_TARGET_STRONG`, `NEAR_TARGET`,
  `RECENT_TREND_IMPROVING`, `RECENT_TREND_STABLE`, and
  `RECENT_TREND_DECLINING`. No new `ReasonCode` member is added and no
  severity threshold is invented.
- **Permanent exclusions.** `TRACKING_WARNING`,
  `INSUFFICIENT_CONVERSION_VOLUME`, and `PROTECTED_FROM_REDUCTION` are
  never emitted — none causally participates in Stage 21's decision, even
  though each is diagnostically true in some cases (`WARNING` tracking,
  low `Confidence`, or a protected campaign's blocked `REDUCE`).
  `BELOW_TARGET_MODERATE`, `BELOW_TARGET_SEVERE`, and
  `STRONG_LONG_TERM_RECENT_DECLINE` are never emitted — no approved
  severity classification exists. `CAMPAIGN_CAP_REACHED`,
  `CAMPAIGN_FLOOR_REACHED`, `TEST_BUDGET_FLOOR_APPLIED`, and
  `MAX_CHANGE_LIMIT_APPLIED` are never emitted — no Stage 15–18 result
  preserves which constraint operand was actually binding.
  `NO_ELIGIBLE_RECIPIENT` and `ACCOUNT_RESERVE_REQUIRED` are never
  emitted — both are cross-campaign allocation-domain outcomes, out of
  scope for a single-campaign explanation.
- **Result model.** `CampaignRecommendationReason` (frozen, immutable,
  `extra="forbid"`; exactly `campaign_id: str`, `reason_codes:
  tuple[ReasonCode, ...]`) does not duplicate `recommendation_action` —
  callers retain the separately-resolved `CampaignRecommendation` for
  that. The tuple is never empty under this scope, since every reachable
  HOLD cause and every `PerformanceBand`×`TrendDirection` combination has
  at least one approved code (trend always supplies one).
- **Dedicated module.** `src/reasons.py` is a new production module,
  distinct from `src/recommendation.py`, `src/suitability.py`,
  `src/availability.py`, `src/classification.py`, `src/constraints.py`,
  and `src/scoring.py` — Stage 22 explains an already-selected action, a
  responsibility separate from selecting it.

### Stage 23 — Deterministic Campaign Reallocation Priority Scoring

- **Rule and business meaning.** For one already-selected
  `CampaignRecommendation` (Stage 21), `calculate_campaign_reallocation_priority_score`
  computes one campaign-level, dimensionless `int` score expressing *"the
  relative priority with which an already-selected directional
  recommendation should be considered during later cross-campaign
  ranking."* A higher score means a stronger candidate **only within the
  same recommendation direction** — `INCREASE` scores must later be
  compared only with other `INCREASE` scores, and `REDUCE` scores only with
  other `REDUCE` scores. The score must never be used to compare an
  `INCREASE` directly against a `REDUCE`; direction remains solely and
  authoritatively carried by `CampaignRecommendation.recommendation_action`,
  never re-encoded through sign or magnitude here.
- **Non-directional actions.** `HOLD` and `MAINTAIN` unconditionally
  produce `confidence_component=0`, `business_priority_component=0`,
  `reallocation_priority_score=0` — not because either action is invalid,
  but because neither proposes a directional budget movement for the later
  ranking stage to prioritise. The confidence and business-priority
  mappings are never inspected or applied once a non-directional action is
  identified.
- **`Confidence.NOT_ASSESSABLE` override.** An `INCREASE` or `REDUCE`
  recommendation paired with `Confidence.NOT_ASSESSABLE` also produces an
  all-zero result — a scoring-only override that neither changes the
  existing `recommendation_action` nor raises an error.
- **Confidence component** (evidence reliability), fixed and immutable:
  ```
  HIGH   → 60
  MEDIUM → 40
  LOW    → 20
  ```
  (`NOT_ASSESSABLE` is handled by the override above, never through this
  mapping.)
- **Business-priority component** (direction-aware), fixed and immutable:
  ```
  INCREASE:  HIGH → 40,     MEDIUM → 20,     STANDARD → 0
  REDUCE:    STANDARD → 40, MEDIUM → 20,     HIGH → 0
  ```
  `INCREASE` favours higher-priority campaigns as recipients of additional
  budget; `REDUCE` favours lower-priority campaigns as possible budget
  donors — the same `BusinessPriority` value therefore contributes
  opposite components depending on direction, by design.
- **Total.** For an assessable directional recommendation,
  `reallocation_priority_score = confidence_component +
  business_priority_component`, always one of `{20, 40, 60, 80, 100}`;
  non-directional or `NOT_ASSESSABLE`-overridden results are always `0`.
- **Exact calculation input and authorised fields.**
  `recommendation.campaign_id`, `recommendation.recommendation_action`,
  `campaign.campaign_id`, `campaign.business_priority`,
  `confidence.campaign_id`, and `confidence.confidence` are the only six
  fields read, across exactly three input objects (`CampaignRecommendation`,
  `CampaignInput`, `CampaignConfidenceClass`). No Stage 1–22 production
  function is ever called — Stage 23 consumes their already-approved
  outputs directly.
- **Campaign-ID policy.** All three `campaign_id` values must match,
  checked as the first statement before any action, confidence, or
  priority value is read — one combined equality check anchored to
  `recommendation.campaign_id`. A mismatch raises exactly
  `ValueError("Campaign IDs must match when calculating reallocation
  priority score.")`, with no result returned, no ID silently preferred,
  and the same exact message regardless of which input(s) mismatch.
- **Numeric policy.** Plain Python `int` throughout — never `float` or
  `Decimal`; the score is dimensionless, requires no rounding or
  quantisation, and no ambient `Decimal` context affects it. No negative
  value and no value greater than `100` is ever produced (model-enforced
  via `Field(ge=0, le=100)`); no multiplication or division is performed
  anywhere. Direction is never encoded through sign. Tie-breaking among
  equal scores is explicitly deferred to the later cross-campaign ranking
  stage, not decided here.
- **Not double-counted.** `PerformanceBand`/`CampaignPerformanceClass` and
  `TrendDirection`/`CampaignTrendClass` already caused Stage 20's
  suitability judgement and Stage 21's recommendation selection — scoring
  them again would double-count the same action evidence, so neither is
  read. `CampaignActionAvailability`, `CampaignActionSuitability`, and
  `CampaignTrackingAssessment` are already fully consumed downstream by
  Stage 21 and are not re-read. `CampaignRecommendationReason`/`ReasonCode`
  explain the decision and must never become hidden numeric weights, so
  neither is read. `PacingStatus`/`CampaignPacingClass` has no approved
  direction-specific prioritisation policy and is excluded. Raw campaign
  metrics, `weighted_performance_ratio`, `trend_delta`, monetary constraint
  results (raw/effective increase/decrease limits), protection,
  test-campaign status, and tracking status are all excluded — they answer
  how much money can move or whether an action is mechanically available,
  not how strongly a campaign should be prioritised for a direction it
  already qualifies for.
- **Result model.** `CampaignReallocationPriorityScore` (frozen, immutable,
  `extra="forbid"`; exactly `campaign_id: str`, `confidence_component: int`,
  `business_priority_component: int`, `reallocation_priority_score: int`,
  each of the three numeric fields constrained to `0..100` and the total
  model-validated to equal the sum of the two components) does not
  duplicate `recommendation_action` — callers retain the
  separately-resolved `CampaignRecommendation` for that.
- **Not this stage's responsibility.** Stage 23 performs no sorting,
  normalisation, ranking, allocation, conservation, monetary calculation,
  or AI explanation, and it never modifies the recommendation it scores.
  It is completely single-campaign — no other campaign's data is read,
  compared, or required.
- **Fills an existing placeholder.** `src/scoring.py` and
  `tests/test_scoring.py` — placeholder since Sprint 1 — are filled in for
  the first time at Stage 23, rather than a new dedicated module being
  created as at Stages 19–22.

### Stage 24 — Deterministic Cross-Campaign Reallocation Ranking

- **Rule.** Stage 24 is the first genuinely cross-campaign responsibility
  in this repository. For a collection of already-selected
  `CampaignRecommendation` (Stage 21) matched by `campaign_id` against a
  collection of already-calculated `CampaignReallocationPriorityScore`
  (Stage 23), `rank_campaign_reallocation_priorities` produces two
  completely independent, dense-ranked, direction-scoped sequences —
  `increase_rankings` and `reduce_rankings` — for later consumption by an
  allocation stage. It never changes any recommendation, recalculates any
  score, normalises any score, or calculates any monetary amount.
- **Direction separation.** `INCREASE` and `REDUCE` candidates are never
  compared against each other, consistent with Stage 23's frozen rule that
  its score is comparable only within the same direction. The
  first-ranked `INCREASE` campaign and the first-ranked `REDUCE` campaign
  may both hold rank `1`; their ranks carry no relationship to one
  another. No global combined rank is ever constructed, and no campaign
  ever crosses direction.
- **Eligible population.** Only a directional recommendation
  (`INCREASE`/`REDUCE`) paired with a strictly positive
  `reallocation_priority_score` is ranked:
  ```
  INCREASE + score > 0   → included in increase_rankings
  REDUCE   + score > 0   → included in reduce_rankings
  INCREASE + score == 0  → excluded
  REDUCE   + score == 0  → excluded
  MAINTAIN (any score)   → excluded
  HOLD     (any score)   → excluded
  ```
  A zero-scored directional recommendation — reachable through Stage 23's
  `Confidence.NOT_ASSESSABLE` override — is excluded because Stage 23 has
  already determined it has no reliable ranking priority. Exclusion
  produces no output record, no reason code, and no error, and never
  changes the excluded campaign's `CampaignRecommendation` or
  `CampaignReallocationPriorityScore`. No excluded-campaign collection is
  created.
- **Sorting and dense ranking.** Within each direction: sort by
  `reallocation_priority_score` descending, then by `campaign_id`
  ascending solely to fix the serialization order of tied-score records —
  `campaign_id` never affects the assigned rank and is never used as a
  business-priority key. Ranks are dense, start at `1`, and are plain
  `int`: equal scores share the same rank with no gap in the next rank
  (`100, 80, 80, 60` → `1, 2, 2, 3`; all equal → `1, 1, 1`). No other
  field — `confidence_component`, `business_priority_component`, input
  position, platform, budget, performance, trend, pacing, or monetary
  capacity — is ever used as a sort key, since every component the score
  already reflects must not receive additional weight through secondary
  sorting.
- **No normalisation.** Stage 23's score is used completely unchanged —
  no percentage, percentile, portfolio-relative transform, min-max
  normalisation, z-score, or direction-relative transformation is ever
  computed. A single candidate scoring `20` remains `20`.
- **Matching, not positional pairing.** `recommendations` and `scores`
  are matched exclusively by `campaign_id` value equality — never by
  tuple position, and `zip` is never used. Every `campaign_id` must be
  unique within each tuple, and the two tuples' `campaign_id` sets must
  be exactly equal. Validation completes fully before any filtering,
  sorting, or rank assignment: a repeated `campaign_id` within
  `recommendations` raises exactly `ValueError("Recommendation campaign
  IDs must be unique when ranking reallocation priorities.")`; a repeated
  `campaign_id` within `scores` raises exactly `ValueError("Score
  campaign IDs must be unique when ranking reallocation priorities.")`
  (checked only after recommendation-uniqueness passes); a mismatched
  `campaign_id` set between the two tuples raises exactly
  `ValueError("Recommendation and score campaign IDs must match when
  ranking reallocation priorities.")`. Two empty input tuples are valid
  and return `CampaignReallocationRanking(increase_rankings=(),
  reduce_rankings=())` without error.
- **Exact calculation input and authorised fields.**
  `recommendation.campaign_id`, `recommendation.recommendation_action`,
  `score.campaign_id`, and `score.reallocation_priority_score` are the
  only four fields read, across exactly two input tuple types
  (`tuple[CampaignRecommendation, ...]`,
  `tuple[CampaignReallocationPriorityScore, ...]`). No Stage 1–23
  production function is ever called — Stage 24 consumes their
  already-approved outputs directly. `confidence_component`,
  `business_priority_component`, every campaign-input field, and every
  performance/trend/pacing/confidence/suitability/availability/tracking/
  reason/monetary field are never read.
- **Determinism and immutability.** Neither input tuple nor any contained
  `CampaignRecommendation`/`CampaignReallocationPriorityScore` is ever
  mutated or sorted in place; every output object is newly constructed.
  Supplying the same logical records in a different input order always
  produces identical serialized output.
- **Monetary and allocation boundary.** Stage 24 never imports, reads, or
  infers `CampaignRawIncreaseLimit`, `CampaignRawDecreaseLimit`,
  `CampaignEffectiveDecreaseLimit`, static budget room, test-floor room,
  percentage movement cap, binding-constraint identity, a monetary
  recommendation amount, donor/recipient matching, partial allocation, or
  conservation. It hands a later allocation stage only ranked campaign
  IDs, their direction-scoped dense ranks, and their unchanged Stage 23
  scores.
- **Result models.** `RankedCampaignPriority` (frozen, immutable,
  `extra="forbid"`; exactly `campaign_id: str`, `rank: int` (`>= 1`),
  `reallocation_priority_score: int` (`1..100`)) does not carry
  `RecommendationAction` — direction is represented structurally by
  membership in `CampaignReallocationRanking.increase_rankings` or
  `.reduce_rankings`. `CampaignReallocationRanking` (frozen, immutable,
  `extra="forbid"`; exactly `increase_rankings:
  tuple[RankedCampaignPriority, ...]`, `reduce_rankings:
  tuple[RankedCampaignPriority, ...]`) permits either or both tuples to be
  empty.
- **Dedicated module.** `src/ranking.py` is a new production module,
  distinct from `src/scoring.py`, `src/recommendation.py`,
  `src/reasons.py`, and `src/allocation.py` — Stage 24 ranks
  already-scored campaigns across a portfolio, a responsibility separate
  from single-campaign scoring and from the later monetary allocation
  decision.

### Stage 25 — Deterministic Cross-Campaign Budget Allocation

- **Rule.** For one Stage 24 `CampaignReallocationRanking`, matched by
  `campaign_id` against Stage 16's `CampaignRawIncreaseLimit` and Stage
  18's `CampaignEffectiveDecreaseLimit`, `allocate_campaign_reallocation`
  converts ranked directional capacities into actual, balanced,
  campaign-level movements. No separate recommendation-amount stage
  exists — allocation consumes these existing typed results directly, per
  the approved post-Stage-24 boundary decision. A capacity is a maximum,
  never a guaranteed movement: no campaign automatically receives or
  donates its full limit merely because it is ranked.
- **Reserve is excluded entirely.** `ReviewSetup.initial_account_reserve`
  is never accepted as an input, read, consumed, reduced, or returned —
  its authoritative meaning (*"Budget held back from reallocation"*)
  treats it as protected and unavailable for funding increases.
  `ReasonCode.ACCOUNT_RESERVE_REQUIRED` remains unassigned.
- **The only funding source is ranked `REDUCE` capacity.** Total
  available supply is the sum of `effective_decrease_limit` across every
  campaign in `ranking.reduce_rankings` only — unranked decrease-limit
  records never contribute, and reserve never contributes.
- **Two-phase strict dense-rank waterfall.** Phase 1 funds
  `ranking.increase_rankings` by ascending dense rank against total
  available supply: a tier is either fully funded (every campaign
  receives its exact capacity) if remaining supply covers it, or — the
  first tier supply cannot fully cover — split proportionally to capacity
  across that tied tier via the largest-remainder method below, after
  which every lower-ranked recipient receives `Decimal("0.00")`. Phase 2
  draws the *exact* total allocated in Phase 1 from
  `ranking.reduce_rankings`, by the identical ascending-dense-rank
  waterfall against donor capacity. Because Phase 1's total can never
  exceed total available supply, Phase 2 always exhausts its target
  exactly; unused donor capacity beyond that target is left unused and is
  not returned as a separate field. A partially funded tier — on either
  side — is a valid, non-error outcome.
- **Largest-remainder currency method**, used only when a tied rank tier
  is partially funded: each campaign's exact proportional share
  (`available × capacity ÷ tier capacity`) is computed at operand-derived
  local precision, then floored to `CURRENCY_QUANTUM` via `ROUND_DOWN`.
  The shortfall between the sum of these floors and the exact available
  amount is a whole number of pennies, distributed one at a time — in
  order of each campaign's fractional remainder descending — to the
  campaigns that lost the most to rounding, never adding a penny that
  would push a campaign above its own capacity. If every capacity in a tier is
  exactly zero, every campaign receives `Decimal("0.00")` without
  performing any division.
- **Narrow campaign-ID exception.** `campaign_id` ascending breaks only
  an *exact* tie between two campaigns' fractional remainders during
  indivisible-penny apportionment — it has no other role anywhere in this
  stage, never orders recipients against donors, never influences which
  tier is funded or by how much, and is never used as an ordinary
  financial preference. This is a narrow, explicitly scoped exception to
  the "campaign ID is a serialization aid only" principle established at
  Stage 24.
- **Insufficient and excess supply are both valid outcomes, never
  errors.** When total recipient capacity exceeds available supply, the
  waterfall funds higher ranks first and may leave lower ranks at zero.
  When available supply exceeds total recipient capacity, only what
  recipients can actually absorb is drawn from donors; unused donor
  capacity is left with the donor. Neither condition produces a
  `ReasonCode`.
- **Exact calculation input and authorised fields.**
  `ranking.increase_rankings`, `ranking.reduce_rankings`,
  `ranked.campaign_id`, `ranked.rank` (never
  `ranked.reallocation_priority_score` — Stage 24's dense rank is
  authoritative), `limit.campaign_id`, `limit.raw_increase_limit`, and
  `limit.effective_decrease_limit` are the only fields read, across
  exactly three input types (`CampaignReallocationRanking`,
  `tuple[CampaignRawIncreaseLimit, ...]`,
  `tuple[CampaignEffectiveDecreaseLimit, ...]`). `ReviewSetup`,
  `CampaignInput`, `CampaignRecommendation`, and
  `CampaignRecommendationReason` are never accepted. No Stage 1–24
  production function is ever called.
- **Matching, not positional pairing.** `increase_limits`/
  `decrease_limits` are matched to the rankings exclusively by
  `campaign_id` value — never by tuple position, and `zip` is never used.
  Every `campaign_id` must be unique within each limit collection,
  checked before any allocation arithmetic: a repeated ID within
  `increase_limits` raises exactly `ValueError("Increase-limit campaign
  IDs must be unique when allocating reallocation.")`; a repeated ID
  within `decrease_limits` raises exactly `ValueError("Decrease-limit
  campaign IDs must be unique when allocating reallocation.")`; a ranked
  campaign missing its direction-appropriate limit raises exactly
  `ValueError("Every ranked increase campaign must have a matching
  increase limit.")` or `ValueError("Every ranked decrease campaign must
  have a matching decrease limit.")`. Extra, unranked limit records are
  legitimate and silently ignored. Stage 24's own already-validated
  guarantees (uniqueness within ranking tuples, direction separation,
  rank correctness, deterministic ordering) are trusted, never
  recalculated or revalidated. Both ranking tuples empty is valid and
  returns two empty allocation tuples.
- **Numeric policy.** `Decimal` exclusively, never `float`. Every
  arithmetic operation — including simple sums and penny apportionment,
  not only the initial proportional division — runs inside an
  explicitly-scoped `localcontext`, so the ambient global `Decimal`
  context can never affect the result and is never mutated. All returned
  amounts are quantized to `CURRENCY_QUANTUM`; zero is always exactly
  `Decimal("0.00")`. No allocation is ever negative or above its
  direction-appropriate capacity. `sum(increase_allocations) ==
  sum(decrease_allocations)` always holds — a constructed invariant, not
  a post-hoc check.
- **Result models.** `CampaignAllocatedAmount` (frozen, immutable,
  `extra="forbid"`; exactly `campaign_id: str`, `allocated_amount:
  Currency` constrained `>= 0`) never carries direction, rank, score,
  capacity, or an explanation — direction is represented structurally by
  membership in `CampaignReallocationAllocation.increase_allocations` or
  `.decrease_allocations`, never through a negative sign.
  `CampaignReallocationAllocation` (frozen, immutable, `extra="forbid"`;
  exactly `increase_allocations: tuple[CampaignAllocatedAmount, ...]`,
  `decrease_allocations: tuple[CampaignAllocatedAmount, ...]`) contains
  exactly one record per campaign appearing in the corresponding Stage 24
  ranking tuple, including at `Decimal("0.00")` — no campaign is silently
  dropped for being unfunded. Output order exactly preserves Stage 24's
  own ranking order; this stage never reorders by allocated amount,
  capacity, or campaign ID.
- **Not this stage's responsibility.** No `ReasonCode` is ever emitted
  (`NO_ELIGIBLE_RECIPIENT` and `ACCOUNT_RESERVE_REQUIRED` remain
  unassigned), no final campaign budget is calculated
  (`CampaignInput.current_budget` is never read), and no conservation
  verification is performed or returned as part of this result — Stage 26
  conservation independently re-verifies the same balance invariant this
  stage already constructs, as a separate, later responsibility;
  conservation must never repair or mutate allocation's result.
- **Dedicated module, existing placeholder filled in.** `src/allocation.py`
  and `tests/test_allocation.py` — placeholder since Sprint 1, reserved
  by the master plan for exactly this responsibility — are filled in for
  the first time at Stage 25, rather than a new module being created.

### Stage 26 — Deterministic, Independent Budget Conservation Verification

- **Rule.** For one already-produced Stage 25 `CampaignReallocationAllocation`,
  `verify_campaign_reallocation_conservation` independently recomputes its
  total allocated increases and total allocated decreases, and reports
  whether they are exactly conserved. Conservation is a pure, read-only
  checker, never an enforcer: it never reruns allocation, never repairs
  an imbalance, and never mutates the allocation it inspects.
- **Exact conservation equation.**
  ```
  total_increase_allocated = sum(record.allocated_amount for record in allocation.increase_allocations)
  total_decrease_allocated = sum(record.allocated_amount for record in allocation.decrease_allocations)
  net_change = total_increase_allocated - total_decrease_allocated
  is_conserved = (net_change == Decimal("0.00"))
  ```
  Both totals are independently recomputed from the individual records —
  Stage 25 deliberately returns no portfolio-total field to trust.
- **Sign convention**, never left ambiguous: `net_change =
  total_increase_allocated - total_decrease_allocated`. Positive means
  increases exceed decreases; negative means decreases exceed increases;
  exactly `Decimal("0.00")` means conserved. No absolute difference is
  ever returned, and imbalance direction is never encoded anywhere except
  in `net_change`'s own sign.
- **Exact equality, no tolerance.** Every value is an exact,
  currency-quantised `Decimal` — there is no numeric noise a tolerance
  would legitimately need to absorb, and any tolerance would only ever
  conceal a genuine one-penny implementation defect. An imbalance of
  exactly `Decimal("0.01")` is reported as not conserved. No `float`,
  epsilon, absolute-difference threshold, or rounded comparison is ever
  used.
- **Always returns a result — never raises merely because the allocation
  is imbalanced.** An imbalanced allocation is reported as
  `is_conserved=False` with its exact signed `net_change`. If a caller
  directly constructs an internally inconsistent
  `CampaignReallocationConservation` (`net_change` not equal to
  `total_increase_allocated - total_decrease_allocated`, or
  `is_conserved` not equal to `net_change == Decimal("0.00")`), ordinary
  Pydantic validation failure applies — a model-level validator enforces
  both relationships. The production verification function itself always
  constructs an internally consistent result and therefore never
  triggers that validator's failure path.
- **Pure monetary sum check — campaign identity is never inspected.**
  `campaign_id` is never read from any allocation record; every
  `allocated_amount` present is summed, indifferent to duplicate IDs
  within one direction, the same ID appearing in both directions, or
  repeated zero-valued records. Stage 24 and Stage 25 already own
  campaign-identity structural guarantees; re-validating them here would
  duplicate upstream responsibility this stage does not own. This stage
  also never duplicates Stage 25's own donor/recipient matching, rank
  waterfall, tied-tier proportional allocation, or residual-penny
  apportionment.
- **Exact calculation input and authorised fields.**
  `allocation.increase_allocations`, `allocation.decrease_allocations`,
  and each record's `allocated_amount` are the only fields read, across
  exactly one input type (`CampaignReallocationAllocation`). `ReviewSetup`,
  `CampaignInput`, Stage 16/18 capacity results, Stage 24's ranking,
  `CampaignRecommendation`, and `CampaignRecommendationReason` are never
  accepted. No Stage 1–25 production function is ever called.
- **Decimal and context policy.** `Decimal` exclusively, never `float`.
  Every sum and the final subtraction run inside an explicitly-scoped
  `localcontext`, with local precision derived from the actual operands'
  digit counts and the number of records being summed — never a blindly
  assumed fixed value — so the ambient global `Decimal` context can never
  affect the result, is never mutated, and local-context rounding can
  never make two genuinely unequal totals compare as equal. This
  precision-derivation discipline directly responds to the real
  ambient-context arithmetic defect discovered and corrected during
  Stage 25's own implementation. Zero is always exactly `Decimal("0.00")`.
- **Result model.** `CampaignReallocationConservation` (frozen, immutable,
  `extra="forbid"`; exactly `total_increase_allocated: Currency` (`>= 0`),
  `total_decrease_allocated: Currency` (`>= 0`), `net_change: Decimal`
  (plain, since it may be negative), `is_conserved: bool`) carries no
  campaign count, campaign IDs, individual allocation records, reserve
  field, capacity field, final budget, message, issue, reason code, or
  tolerance field.
- **A conserved zero allocation does not mean any campaign received
  funding** — an all-zero allocation is trivially conserved
  (`Decimal("0.00") == Decimal("0.00")`), reporting a true fact about
  balance, not a claim that money moved.
- **Not this stage's responsibility.** No `ReasonCode` is ever emitted or
  referenced (`ACCOUNT_RESERVE_REQUIRED` and `NO_ELIGIBLE_RECIPIENT`
  remain unassigned); reserve, final campaign budgets, ranking order, and
  recommendation/reason context are all outside this stage, exactly as
  they were outside Stage 25's. This stage exposes only the two totals,
  `net_change`, and `is_conserved` to a later deterministic
  integration/reporting stage — it does not decide what that later stage
  should do with an unconserved result (publication gating, final
  budgets, and reporting are not implemented here).
- **Dedicated module, existing placeholder filled in.** `src/conservation.py`
  and `tests/test_conservation.py` — placeholder since Sprint 1, reserved
  by the master plan for exactly this responsibility — are filled in for
  the first time at Stage 26, rather than a new module being created.

### Stage 27 — Final Deterministic Pipeline Integration and Reporting

- **Rule.** `run_budget_reallocation_review(review: ReviewSetup,
  campaigns: tuple[CampaignInput, ...]) -> BudgetReallocationReviewResult`
  orchestrates every already-approved Stage 3–26 production function, in
  their exact frozen dependency order, over one already-validated review
  and campaign collection, and returns one compact, typed, auditable
  portfolio result. This completes the master plan's Sprint 2
  "Deterministic Core Engine" goal. It never implements Streamlit,
  Gemini explanation, human approval, audit persistence, exports, or
  Sprint 4 hardening.
- **Validation remains entirely outside this stage.** `ReviewSetup` and
  every `CampaignInput` are accepted only in already-validated form; this
  stage never reads a CSV, never calls `validate_campaign_csv`, never
  returns validation issues, and never re-checks campaign-ID uniqueness
  — already a Stage 2 responsibility, trusted here exactly as every
  downstream stage has trusted its own upstream guarantees since Stage
  12. An empty campaign tuple is valid and produces an empty portfolio
  result.
- **Pure orchestration.** Every deterministic fact is produced by calling
  the real, already-approved Stage 3–26 function that owns it — no
  formula is duplicated, approximated, reopened, or recalculated from an
  upstream result object. The only new arithmetic is the explicitly
  authorised final-budget formula below.
- **Dependency order**: per campaign — metrics → pacing → pacing
  classification → performance classification → trend classification →
  confidence classification → tracking assessment → static budget room →
  applicable change percentage → raw percentage movement cap → test
  floor room → protection constraint → test-aware static decrease room →
  raw increase limit → raw decrease limit → effective decrease limit →
  action availability → action suitability → recommendation action →
  recommendation reasons → reallocation priority score; then once per
  portfolio — ranking → allocation → conservation; then final assembly in
  the original input order.
- **Final movement.** Exactly one unsigned `allocated_amount` per
  campaign — direction is carried only by `recommendation_action`, never
  re-encoded through sign. For a directional recommendation matched to a
  Stage 25 allocation record, that record's exact amount is used. For
  `HOLD`/`MAINTAIN`, and for a directional recommendation with no
  matching allocation record (excluded from Stage 24's ranking because
  its Stage 23 score was zero, or ranked but left unfunded), the amount
  is exactly `Decimal("0.00")`. **A zero-funded `INCREASE`/`REDUCE`
  recommendation is never rewritten to `MAINTAIN`/`HOLD`.** All
  cross-collection matching (rank, allocation) is by `campaign_id`
  value, never tuple position.
- **Final-budget formula**, using only Stage 25's actual allocated
  amount — never raw or effective constraint limits directly:
  ```
  INCREASE → current_budget + allocated_amount
  REDUCE   → current_budget - allocated_amount
  MAINTAIN → current_budget
  HOLD     → current_budget
  ```
  Every addition, subtraction, and portfolio-level sum runs inside an
  explicitly-scoped `localcontext`, with precision derived from the
  actual operands' digit counts and collection size — never a blindly
  assumed fixed value and never dependent on the ambient global `Decimal`
  context, directly extending the corrected discipline established at
  Stages 25 and 26. `float` is never used.
- **Conservation is always exposed, never hidden, never repaired.** The
  embedded Stage 26 `CampaignReallocationConservation` result is returned
  unchanged regardless of its `is_conserved` value — this stage never
  raises merely because an allocation is unconserved. As a defence-in-depth
  check distinct from, and never a replacement for, Stage 26's own
  invariant, this stage verifies that a *conserved* allocation also
  preserves the portfolio's total budget
  (`total_recommended_budget == total_current_budget` whenever
  `conservation.is_conserved`), raising exactly
  `RuntimeError("Conserved allocation must preserve the total campaign
  budget.")` only if that narrower, additional guarantee is ever
  violated — which would indicate a defect in this stage's own
  campaign-to-allocation matching, never in Stage 25/26 themselves.
- **Reasons pass through unchanged.** Stage 22's ordered `reason_codes`
  tuple is exposed exactly as produced — never recomputed, never
  appended to, and no allocation-specific reason code is ever invented.
- **Order and determinism.** `campaign_results` preserves the original
  `campaigns` input order — never re-sorted by ID, score, rank, or
  action. Stage 24's increase and reduce rankings remain independent; no
  global cross-direction rank is ever constructed.
- **Fails fast.** Any unexpected exception, or a `ValueError` raised by
  an underlying Stage 1–26 function, propagates unchanged — no
  `try`/`except`, no retry, no partial portfolio result; no campaign is
  ever silently dropped. No input or upstream result object is ever
  mutated.
- **Result models.** `CampaignBudgetRecommendationResult` (frozen,
  `extra="forbid"`: `campaign_id`, `campaign_name`, `platform`,
  `current_budget: Currency`, `recommendation_action`,
  `allocated_amount: Currency` `>= 0`, `recommended_budget: Currency`
  `>= 0`, `reason_codes: tuple[ReasonCode, ...]`, `performance_band`,
  `trend_direction`, `confidence`, `pacing_status`,
  `reallocation_priority_score: int` `0..100`, `rank: int | None` `>= 1`
  when present) carries no signed movement, raw/effective capacity,
  availability/suitability object, tracking status, validation issue,
  reserve, or explanatory text. `BudgetReallocationReviewResult` (frozen,
  `extra="forbid"`: `review_id`, `campaign_results:
  tuple[CampaignBudgetRecommendationResult, ...]`,
  `total_current_budget: Currency` `>= 0`, `total_recommended_budget:
  Currency` `>= 0`, `conservation: CampaignReallocationConservation`)
  carries no campaign count, timestamp, version field, or formal
  audit-trace object.
- **Dedicated module.** `src/pipeline.py` is a new production module — no
  existing placeholder (`app.py`, `config.py`,
  `src/explanations.py`/`gemini_analyzer.py`/`approval.py`/`audit.py`/
  `exports.py`) is scoped for deterministic orchestration; each remains
  reserved for its own Sprint 3 responsibility, untouched.
  `tests/test_pipeline.py` is a new dedicated test file, distinct from
  `tests/test_integration.py`, which remains reserved for the later,
  materially larger AI/UI-inclusive end-to-end flow.

## Stage 28 — Deterministic Streamlit Review Shell

**Rule.** `app.py` (Sprint 3, Development Stage 28) is a deterministic-only Streamlit
review shell. It collects raw `ReviewSetup` input and an uploaded campaign CSV, calls the
existing `validate_review_setup`, `validate_campaign_csv` (Stage 2), and
`run_budget_reallocation_review` (Stage 27) functions unmodified, and renders their
already-computed output. It reimplements no validation rule and no Stage 1–27 business
formula; every currency/percentage input is passed through as a raw string directly into
the existing validator, never converted through `float`.

**Excluded.** `config.py`, Gemini/`google-generativeai`, `src.explanations`,
`src.approval`, `src.audit`, `src.exports` are neither imported nor referenced. Stage 28
adds no explanation, approval, audit, or export control.

**Frozen execution-gating policy.** The pipeline runs only when all seven conditions hold
simultaneously: (1) the form was explicitly submitted; (2) `validate_review_setup`
returned a non-`None` review; (3) the review validation report contains no errors; (4) a
CSV file was supplied; (5) CSV decoding succeeded; (6) the campaign validation report
contains no errors; (7) `valid_campaigns` is non-empty. Warnings alone never block
execution. A campaign CSV containing any error — even alongside otherwise-valid rows —
never runs a partial portfolio; the whole upload must be corrected and resubmitted. An
empty `valid_campaigns` collection is blocked at the UI boundary with a clear message,
without changing `run_budget_reallocation_review`'s own valid empty-tuple behavior.
Implemented as one pure predicate, `_may_run_pipeline`, independent of any Streamlit
rendering.

**Submission and session-state policy.** An explicit `st.form_submit_button` ("Run
deterministic review") is the sole trigger for pipeline execution; `_handle_submission` is
never called unconditionally, so an ordinary Streamlit rerun never recomputes the
pipeline. The locked result is held under session-state key `locked_review_result`,
explicitly cleared to `None` at the start of every new submission, before validation
begins, so a failed resubmission never leaves a stale result visible as though it
belonged to the new submission. No `st.cache_data`/`st.cache_resource` is used.

**Pipeline-exception policy.** `run_budget_reallocation_review` itself remains unchanged
and fail-fast (no internal `try`/`except`). `app.py` adds exactly one deliberate `except
Exception` at the Streamlit UI boundary, around the pipeline call only. On an unexpected
exception: `locked_review_result` stays empty, a clear `st.error` is shown including the
exception's own message, and the exception is never retried, reclassified, wrapped in a
new business exception type, or swallowed into a fabricated result.

**Locked-result rendering.** Read-only; no control edits any locked value. Portfolio-level
`review_id`, `total_current_budget`, `total_recommended_budget`, and every `conservation`
field are shown. Every campaign result is shown in original pipeline order (never
sorted) with all fourteen `CampaignBudgetRecommendationResult` fields; ordered
`reason_codes` are preserved in order; a missing `rank` is shown as "Not ranked" rather
than a fabricated number; a zero-funded `INCREASE`/`REDUCE` is never relabeled as
`MAINTAIN`/`HOLD`. Every Decimal value is formatted via `format(value, "f")` — `float` is
never referenced anywhere in the module.

**Conservation rendering.** Always visible for a successful result. A conserved result
shows a clear success state. An unconserved result shows a prominent error state, states
plainly that the allocation is not conserved, and continues to display the full locked
result for inspection — never concealed, repaired, rebalanced, or rerun. Stage 28 has no
approval controls at all, regardless of conservation status.

## Stage 29 — Gemini Configuration Foundation

**Rule.** `config.py` (Sprint 3, Development Stage 29) implements a narrow, explicit,
side-effect-controlled configuration boundary for Gemini API-key availability only —
`GeminiConfig` (frozen, `extra="forbid"`, exactly one field: `api_key: SecretStr | None`),
`load_gemini_config(dotenv_path: str | Path | None = None) -> GeminiConfig`, and
`is_gemini_available(config: GeminiConfig) -> bool`. No Gemini SDK is imported; no prompt
construction, API call, or UI wiring is implemented.

**Source precedence.** Exactly two sources, in order: the process environment variable
`GEMINI_API_KEY` (checked for *presence*, not truthiness) is authoritative whenever it
exists — including when explicitly blank, in which case it does **not** fall back to
`.env`. Only when the variable is entirely absent from `os.environ` is a local `.env`
file consulted. If neither source yields a non-blank value, the result is
`GeminiConfig(api_key=None)` — a normal, valid, non-raising state.

**`.env` behavior.** Read via `dotenv_values(...)`, never `load_dotenv(...)`, so
`os.environ` is never mutated merely to read configuration. The default path — used only
when `dotenv_path` is not supplied — is `Path(__file__).resolve().parent / ".env"`,
derived deterministically from `config.py`'s own location, independent of the process's
current working directory and never searched in parent directories. A missing `.env`
file, a `.env` without `GEMINI_API_KEY`, and a blank/whitespace-only `.env` value all
resolve to the same unavailable state as the equivalent environment-variable cases.

**Normalization.** Whitespace-trimming only — no case transformation, no format/prefix
validation, no live API check. A key is never logged or included in an exception message.

**Secret protection.** `SecretStr` masks the value in `repr`, `str`, `model_dump()`, and
`model_dump_json()`; the raw value is retrievable only via the existing
`config.api_key.get_secret_value()` — no alternative accessor is added.
`is_gemini_available` never calls `get_secret_value()`; availability is derived from
`api_key is not None`, never stored as a separate field, so the two can never disagree.

**Import and side-effect policy.** Importing `config` performs no filesystem read, loads
no `.env`, reads no environment variable, imports no Streamlit, imports no Gemini SDK,
and creates no module-level configuration singleton (no `CONFIG = load_gemini_config()`).
Configuration is loaded only through an explicit call to `load_gemini_config()`.

**Deterministic independence.** `app.py` is not modified and does not import `config`
(AST-verified). Every Stage 28 capability — importing `app.py`, review-setup inputs, CSV
validation, deterministic pipeline execution, locked-result rendering — remains fully
functional with no Gemini key present. No missing-key warning is added to the Stage 28 UI
yet; that is reserved for a later Sprint 3 stage.

**SDK mismatch deferred.** `requirements.txt` declares `google-generativeai`, which is not
installed in this environment; `google-genai` is installed instead. Stage 29 does not
resolve this — it imports no Gemini SDK at all. Resolving the mismatch (choosing and
declaring the correct dependency) is deferred to the future Gemini API-integration stage.

## Stage 30 — Explanation Payload and Prompt Construction

**Rule.** `src/explanations.py` (Sprint 3, Development Stage 30) is a pure, deterministic
boundary between an already-locked pipeline result and whatever future stage actually calls
Gemini. It projects locked results into explicitly authorized payload models
(`CampaignExplanationPayload`, `PortfolioExplanationPayload`), serializes them to canonical
JSON (`serialize_explanation_payload`), and constructs prompt content
(`build_campaign_explanation_prompt`, `build_portfolio_explanation_prompt`) as a typed
`ExplanationPrompt` bundle. It never calls Gemini, never reads `config`/`GeminiConfig`/
`is_gemini_available`/`GEMINI_API_KEY`, and never mutates a locked result. No public
orchestration wrapper is added.

**Frozen Gemini boundary.** Gemini is explanation-only: it may explain only the locked
facts supplied in a payload. It must never select or change an action; change an
allocation, current budget, or recommended budget; change a score or rank; add, remove, or
reorder reason codes; change a classification; hide, repair, or reinterpret conservation;
rewrite a zero-funded directional action to `MAINTAIN`/`HOLD`; approve or reject; create
audit facts; infer causes from data outside the payload; or introduce unsupported claims.
Stage 30 creates prompts only — it never generates or fabricates an explanation itself.

**Authorized fields only.** `CampaignExplanationPayload` copies exactly the fourteen
authorized campaign fields (`campaign_id`, `campaign_name`, `platform`, `current_budget`,
`recommendation_action`, `allocated_amount`, `recommended_budget`, `reason_codes`,
`performance_band`, `trend_direction`, `confidence`, `pacing_status`,
`reallocation_priority_score`, `rank`) directly from one locked
`CampaignBudgetRecommendationResult`. `PortfolioExplanationPayload` copies exactly
`review_id`, `total_current_budget`, `total_recommended_budget`, and all four conservation
fields (`total_increase_allocated`, `total_decrease_allocated`, `net_change`,
`is_conserved`), read directly from `result.conservation` — never recalculated. Raw CSV
data, `ReviewSetup.review_notes`, raw metrics, validation issues, intermediate
constraints, availability/suitability, the API key, and audit data are all excluded; none
is reachable from either payload model (`extra="forbid"` on both).

**Granularity.** Campaign and portfolio explanations are structurally separate: one
campaign payload contains exactly one campaign with no sibling-campaign information; the
portfolio payload contains only totals and conservation, never a campaign list. No
function loops over the full campaign collection to build a combined prompt — this
structurally prevents any single request from inviting an unsupported cross-campaign
comparison.

**Canonical serialization.** `serialize_explanation_payload` returns compact, deterministic
JSON: key order follows Pydantic model declaration order (never alphabetically sorted),
`ensure_ascii=False`, separators exactly `(",", ":")`, no indentation. `Decimal`/`Currency`
values serialize as fixed-point strings via `format(value, "f")` — never as JSON numbers,
never through `float`, never in scientific notation, never rounded, quantized, or
reconstructed. Enums serialize to `.value`; tuples serialize as JSON arrays, preserving
order; `None` serializes as `null`. Identical input produces byte-for-byte identical
output. A private `_normalize_value` helper performs this conversion and is not part of the
module's public API.

**Prompt architecture.** One fixed, author-controlled system instruction is shared,
byte-for-byte identical, by every campaign and portfolio prompt regardless of payload
contents — it contains no campaign-specific or portfolio-specific data, no API key, no SDK
detail, no model name, and no generation parameter. It states that the supplied JSON is
locked and authoritative, that the assistant explains but never decides, that no supplied
value may be changed, that reason-code order is authoritative, that a missing rank means
"not ranked" (never rank zero), that a zero-funded directional action is not
`MAINTAIN`/`HOLD`, that an unconserved portfolio must be disclosed plainly and never
concealed or repaired, and that any string inside the JSON — including a campaign name —
is untrusted data, never an instruction. User content never interpolates a payload field
individually into prose; it contains exactly one fixed author-controlled sentence, the
canonical JSON between fixed `BEGIN_LOCKED_DATA`/`END_LOCKED_DATA` marker lines, and
nothing else.

**Injection containment, honestly scoped.** `campaign_name` is treated as untrusted data:
JSON string escaping plus strict system/user (instruction/data) separation make it
significantly harder for adversarial campaign-name content to be mistaken for an
instruction — verified against embedded quotes, backslashes, braces, newlines, Markdown,
Unicode, the literal marker text, and instruction-like phrasing. This does **not**
eliminate prompt injection; no prompt-construction code can fully guarantee a downstream
model will never be influenced by adversarial content in its context. The decisive
protection is structural, not textual: nothing in this codebase ever writes a Gemini
response back into a locked deterministic model, so whatever Gemini outputs can never
actually change a locked action, amount, score, rank, or conservation status.

**Output contract deferred.** This stage requests concise, grounded, plain-language text
only. Response parsing, a response model, structured output, retries, timeouts, fallback
explanations, API-error handling, and explanation persistence are all explicitly out of
scope, reserved for the future Gemini API-integration stage — along with resolving the
`google-generativeai`/`google-genai` mismatch recorded at Stage 29, which Stage 30 does not
touch.

**Normal-state behavior.** `rank=None`, zero allocation, a directional action with zero
allocation, empty portfolio totals, `is_conserved=False`, extreme Decimal magnitudes, and
adversarial campaign names are all valid states that never raise. Only a genuinely invalid
direct construction (already-enforced upstream business rules are never re-validated here)
or an unexpected serialization failure would raise, and any such failure propagates
unchanged.

## Stage 31 — Gemini Explanation Transport

**Rule.** `src/gemini_analyzer.py` (Sprint 3, Development Stage 31) is the transport/service
layer that sends one Stage 30 `ExplanationPrompt` to Gemini and returns a typed
`ExplanationResult`. It consumes only `ExplanationPrompt` and `GeminiConfig` (plus an
optional injected client and a model-name override) — never a locked pipeline result, a
payload model, an approval model, an audit model, or Streamlit. `ExplanationResult` has no
field capable of representing an action, budget, allocation, score, rank, reason, or
conservation value, so there is structurally no path back into a locked deterministic
result. One generic `generate_explanation` function is used for both campaign and
portfolio prompts — no separate campaign/portfolio transport functions, no batch function.

**SDK decision.** Uses `google.genai` exclusively — the current, actively-maintained,
General Availability Google Gen AI SDK. The legacy `google.generativeai` (declared in
`requirements.txt` since Stage 1, never actually installed) is removed;
`requirements.txt` now declares `google-genai>=2,<3`. The legacy SDK is officially
documented as not actively maintained, with legacy libraries deprecated as of
2025-11-30. No code anywhere imports `google.generativeai`.

**Exact model and settings, all frozen.** Default model `gemini-2.5-flash-lite`, held in
one private module constant, overridable via the function's keyword-only `model`
parameter; `temperature=0.2`; `max_output_tokens=512`; exactly one candidate
(`candidate_count=1`); a `30_000`-millisecond timeout via `GenerateContentConfig.http_options
= HttpOptions(timeout=...)`. No structured output, no safety-setting overrides, no seed, no
stop sequences, no top-p/top-k — none is justified by current evidence.

**Availability guard.** `is_gemini_available(config)` is checked first. When unavailable: no
SDK client is constructed, no API call is attempted, and the result is
`UNAVAILABLE`/`CONFIGURATION` with no explanation text or model name.

**Client lifecycle.** An injected `client` (satisfying the narrow structural `GeminiClient`
protocol) is used as-is and is never closed by this module. When no client is injected,
`config.api_key.get_secret_value()` is called at exactly one production call site, to build
one fresh `google.genai.Client` for that call only; that internally-owned client is always
closed in a `finally` block, on both success and failure. No client or configuration is
cached at module level; importing this module performs no environment read, no client
construction, and no network call.

**Provider call and extraction.** `prompt.user_content` is sent as the content;
`prompt.system_instruction` is forwarded through `GenerateContentConfig.system_instruction`
unchanged. Only `response.text` is ever extracted; the raw provider response object is
never retained or returned. A nonblank result is stripped at its outer boundaries and
returned as `GENERATED`; Markdown inside it is permitted. Response text is never scanned
for "unsupported" content — the only guarantee this module makes is structural (no path
back into a locked result), never a claim that generated text has been fact-checked.

**Failure mapping, no retries, no fabricated fallback.** Every failure returns `FAILED` with
one of the ten frozen `ErrorCategory` values — `CONFIGURATION` (unavailable), `AUTHENTICATION`
(401/403), `RATE_LIMIT` (429), `SERVER_ERROR` (5xx), `TIMEOUT`, `NETWORK_ERROR`,
`SAFETY_BLOCK` (explicit provider safety signal, detected before falling through to an
empty-response check), `EMPTY_RESPONSE` (`None`/blank/whitespace text with no safety
signal), `MALFORMED_RESPONSE` (extraction itself raises), and `UNEXPECTED_ERROR` (anything
else). There is no automatic retry — exactly one provider invocation per call, regardless
of outcome — and no deterministic fallback explanation text is ever fabricated; a
non-`GENERATED` result carries no `explanation_text`, leaving any user-facing fallback copy
to a future UI stage.

**Secret redaction.** The raw key exists only inside the one owned-client construction path.
Any exception message captured while using an internally-owned client has the known secret
value replaced with a fixed `[REDACTED]` marker before it is placed into `error_message`; no
raw SDK request, response, header, or credential is ever stored. The injected-client path
never reads `config.api_key` at all.

**Result-state invariants.** `ExplanationResult` (frozen, `extra="forbid"`) enforces by
model validator: `GENERATED` requires nonblank `explanation_text` and `model_name` and both
error fields `None`; `UNAVAILABLE` requires `explanation_text=None`, `model_name=None`,
`error_category=CONFIGURATION`, and a nonblank `error_message`; `FAILED` requires
`explanation_text=None`, a nonblank `model_name`, a non-`CONFIGURATION` `error_category`,
and a nonblank `error_message`. An inconsistent direct construction is rejected by normal
Pydantic validation, never silently repaired.

## Stage 32 — Explanation UI Wiring

**Rule.** `app.py` (Sprint 3, Development Stage 32) adds one optional, click-only Gemini
explanation section, rendered strictly after the complete locked deterministic result:
one portfolio-level explanation and one explanation for a user-selected campaign. Nothing
is generated automatically — every Gemini call happens only inside a button's own click
branch, exactly once per click, never on an ordinary rerun and never merely from changing
the campaign selector. The same two buttons (`generate_portfolio_explanation`,
`generate_campaign_explanation`) serve as the only manual retry/regenerate controls; no
separate retry control exists, and no automatic retry is ever performed. No campaign call
is ever batched across the whole portfolio.

**Required section and trust labeling.** A `st.subheader("Optional AI-generated
explanations")` followed immediately by the fixed caption "Gemini explanations are
supplementary and may be inaccurate. The deterministic recommendations above remain
authoritative." An explanation is never labeled verified, validated, checked, authoritative,
approved, or deterministic.

**Exact widgets.** `st.button("Generate portfolio explanation",
key="generate_portfolio_explanation")`; `st.selectbox("Campaign to explain",
options=<campaign IDs>, format_func=<"{campaign_id} — {campaign_name}">,
key="explanation_campaign_id")`; `st.button("Generate campaign explanation",
key="generate_campaign_explanation")`. Both buttons appear only when a locked result
exists, remain enabled regardless of Gemini configuration, and are never placed inside the
deterministic-review form.

**Session-state keys and lifecycle.** `PORTFOLIO_EXPLANATION_STATE_KEY =
"portfolio_explanation_result"`, `CAMPAIGN_EXPLANATION_STATE_KEY =
"campaign_explanation_result"`, `CAMPAIGN_EXPLANATION_ID_STATE_KEY =
"campaign_explanation_campaign_id"` — alongside the existing `RESULT_STATE_KEY`. All four
are cleared at the very start of every new deterministic-review submission, before
validation or pipeline execution, so a failed resubmission never leaves a stale
explanation visible. Ordinary reruns preserve stored explanations and trigger no Gemini
call. A portfolio click clears, then rebuilds and replaces, the portfolio result. A
campaign click clears, then rebuilds and replaces, both the campaign result and its
recorded campaign ID. The stored campaign explanation renders only when its recorded
campaign ID equals the currently selected campaign ID — changing the selector alone hides
a mismatched explanation (never calling Gemini), and reselecting the original campaign
redisplays its still-current stored explanation without regenerating it. The widget-owned
selection value itself is never duplicated under another session-state key. The locked
result itself, and every campaign result within it, is never mutated.

**Exact call chains, no duplicated logic.** Portfolio:
`build_portfolio_explanation_payload` → `build_portfolio_explanation_prompt` →
`load_gemini_config()` → `generate_explanation(prompt, config)`. Campaign: the selected
existing locked `CampaignBudgetRecommendationResult` → `build_campaign_explanation_payload`
→ `build_campaign_explanation_prompt` → `load_gemini_config()` →
`generate_explanation(prompt, config)`. `generate_explanation` receives only the resulting
`ExplanationPrompt` and `GeminiConfig` — never a locked result, a payload model, or any
other object. No Stage 29/30/31 formula, payload, prompt, or transport rule is
reimplemented in `app.py`.

**Rendering policy.** A shared private helper renders every `ExplanationResult`
consistently. `GENERATED`: a local heading identifying the portfolio or the selected
campaign, `explanation_text` via `st.markdown(...)` with the default
`unsafe_allow_html=False` (never `True`), and a caption "AI-generated using
{model_name}" — `error_category` is never displayed. `UNAVAILABLE`/`FAILED`: only the
already-sanitized `error_message` via `st.info(...)`/`st.error(...)` respectively — never
`error_category`, a raw exception, configuration, or the API key. The locked deterministic
totals, conservation result, and campaign table remain fully visible and authoritative in
every explanation state.

**Configuration and secret boundary.** `app.py` calls `load_gemini_config()` fresh inside
each click handler — never cached, never stored in session state (only the resulting
`ExplanationResult` is kept). `app.py` never accesses `config.api_key`, never references
`SecretStr`, never calls `get_secret_value()`, never inspects an environment variable or
reads `.env` directly, and never logs or prints configuration.

**Single explanation-action exception boundary.** An unexpected failure while building a
payload, prompt, or calling the transport is caught only at the one click-handler boundary
per action (mirroring Stage 28's own single pipeline-exception boundary): a concise generic
`st.error` is shown, no fabricated `ExplanationResult` is stored, the locked result is
preserved untouched, no raw secret/traceback/configuration/provider object is exposed, and
no automatic retry occurs. Stage 31's own typed-result failure mapping is never
reimplemented here.

**One approved test exception.** Three pre-existing AST-based isolation assertions —
`tests/test_app.py`'s `test_module_does_not_import_forbidden_modules` and
`test_module_does_not_reference_forbidden_names`, and `tests/test_config.py`'s
former `test_app_module_does_not_import_config` (renamed
`test_app_module_imports_config_but_never_touches_the_raw_key`) — were narrowed to remove
only `config`/`src.explanations`/`src.gemini_analyzer` from their forbidden sets, per
explicit approval, because `app.py` now legitimately imports exactly those three for the
explanation UI. Every other forbidden entry in all three tests (`src.approval`,
`src.audit`, `src.exports`, any Gemini SDK module, `api_key`, `get_secret_value`,
`SecretStr`) is unchanged and still enforced.

## Pending

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
- **Effective increase, `ReasonCode`, scoring, allocation.** Stage 10 resolved the
  static budget-bound distances (`room_to_static_maximum`/`room_to_static_minimum`),
  Stage 11 resolved which percentage applies to a campaign
  (`applicable_max_change_percentage`), Stage 12 resolved the raw percentage-based
  monetary cap (`raw_percentage_movement_cap`), Stage 13 resolved the raw test-floor
  distance (`room_to_test_floor`), Stage 14 resolved the decrease-specific
  protection constraint (`decrease_blocked`), Stage 15 resolved the test-aware
  static decrease room (`test_aware_static_decrease_room`), Stage 16 resolved the
  raw increase limit (`raw_increase_limit`), Stage 17 resolved the raw decrease
  limit (`raw_decrease_limit`), Stage 18 resolved the protection-adjusted effective
  decrease limit (`effective_decrease_limit`), Stage 19 resolved mechanical action
  availability (`increase_available`/`maintain_available`/`reduce_available`),
  Stage 20 resolved conservative, diagonal-only per-action suitability
  (`increase_suitability`/`maintain_suitability`/`reduce_suitability`), and Stage
  21 resolved the ordered `RecommendationAction` selection rule (see above), but
  no rule computes an *effective* increase limit — protection has no approved
  increase-side effect, so `raw_increase_limit` remains the authoritative
  increase-side constraint. `RecommendationAction` is a provisional direction
  only — no monetary amount is calculated. The six conflicting performance/trend
  cells' precedence remains deliberately left `NEUTRAL` rather than resolved;
  `Confidence.NOT_ASSESSABLE` ownership, `PacingStatus` effects, and the
  remaining `ReasonCode` trigger conditions (see below) all remain pending
  later stages. Stage 23 resolved single-campaign reallocation priority
  scoring using `Confidence` and `BusinessPriority`, Stage 24 resolved
  cross-campaign, direction-separated dense ranking of those scores,
  Stage 25 resolved cross-campaign budget allocation using Stage 16/18's
  existing capacities directly, and Stage 26 resolved independent
  monetary conservation verification of that allocation (see above) —
  confirming no separate monetary recommendation-amount stage was ever
  required, and completing the deterministic ranking → allocation →
  conservation sequence. Per-campaign scoring is not itself known to
  require cross-campaign data; ranking and allocation are the two
  responsibilities that genuinely do. Portfolio-wide or percentile normalisation remains
  unused — Stage 24 confirmed the fixed Stage 23 `0..100` scale is used
  unchanged, and normalising small or single-candidate groups would
  distort that fixed meaning. `ReviewSetup.initial_account_reserve`
  remains unused by any deterministic stage — Stage 25 explicitly excluded
  it as protected, non-reallocatable budget.
- **Remaining `ReasonCode` trigger conditions.** Stage 22 resolved the trigger
  conditions for `PAUSED_CAMPAIGN`, `TRACKING_UNRELIABLE`,
  `HELD_FOR_MANUAL_REVIEW`, `ABOVE_TARGET_STRONG`, `NEAR_TARGET`,
  `RECENT_TREND_IMPROVING`, `RECENT_TREND_STABLE`, and
  `RECENT_TREND_DECLINING` (see above). The remaining twelve members stay
  pending: `BELOW_TARGET_MODERATE`, `BELOW_TARGET_SEVERE`, and
  `STRONG_LONG_TERM_RECENT_DECLINE` pending an approved performance-severity
  classification (`PerformanceBand` currently has only three bands,
  insufficient to distinguish them); `CAMPAIGN_CAP_REACHED`,
  `CAMPAIGN_FLOOR_REACHED`, `TEST_BUDGET_FLOOR_APPLIED`, and
  `MAX_CHANGE_LIMIT_APPLIED` pending a redesign that preserves which Stage
  15–18 constraint operand was actually binding (no current result exposes
  this); `NO_ELIGIBLE_RECIPIENT` and `ACCOUNT_RESERVE_REQUIRED` pending a
  later cross-campaign allocation/conservation stage; `INSUFFICIENT_CONVERSION_VOLUME`,
  `TRACKING_WARNING`, and `PROTECTED_FROM_REDUCTION` intentionally and
  permanently excluded from Stage 22's action-reason scope — each is
  diagnostically true in some cases but never causally participates in
  Stage 21's decision.
- Stage 27 resolved final deterministic integration and portfolio
  reporting, including final campaign-budget computation and always-exposed
  (never gated/hidden) conservation status (see above). The deterministic
  core engine is now complete.
- Stage 28 resolved the first Sprint 3 increment: a deterministic-only
  Streamlit review shell consuming Stage 2 validation and the Stage 27
  pipeline (see above). Configuration wiring, Gemini explanation, human
  approval, audit persistence, exports, and Sprint 4 hardening all remain
  pending later, separate stages/sprints — none is implemented by Stage
  28. Approval granularity, rejection-comment requirement, and audit-record
  content also remain open, reserved for their own later stages.
- Stage 29 resolved the Gemini API-key configuration boundary (see above):
  source precedence, blank-value normalization, `.env` behavior,
  `SecretStr` redaction, and import-time side-effect freedom. It does not
  resolve the `google-generativeai`/`google-genai` dependency mismatch,
  does not construct any Gemini request, and does not wire anything into
  `app.py`.
- Stage 30 resolved explanation payload and prompt construction (see
  above): the authorized-field boundary, the campaign/portfolio
  granularity split, canonical JSON serialization, and the shared,
  data-free system instruction with its injection-containment measures.
  It does not resolve the `google-generativeai`/`google-genai` dependency
  mismatch, does not call Gemini, does not define a response contract,
  and does not wire anything into `app.py`.
- Stage 31 resolved the Gemini transport layer and the SDK dependency
  mismatch (see above): `google-genai` is now the sole declared and used
  SDK; `generate_explanation` sends one Stage 30 prompt and returns a
  typed `ExplanationResult`, with the frozen model/settings, availability
  guard, client lifecycle, failure-category mapping, and secret-redaction
  policy all recorded above. It does not wire anything into `app.py`,
  does not implement approval, audit, or exports, and defines no response
  contract beyond the plain-text `explanation_text` field already
  specified.
- Stage 32 resolved explanation UI wiring (see above): the optional,
  click-only portfolio and campaign explanation section, its exact
  widgets and session-state lifecycle, stale-explanation prevention, the
  shared rendering policy for every status, and the single
  explanation-action exception boundary. It does not implement human
  approval, audit persistence, exports, or the full integration test, and
  it never generates an explanation automatically or in a batch. Human
  approval, audit persistence, exports, and Sprint 4 hardening all remain
  pending later, separate stages/sprints.
