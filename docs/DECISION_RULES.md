# Decision Rules

> Sprint 1, Development Stage 5. Records the frozen enumerations, frozen numerical
> constants, the frozen deterministic validation rules, the frozen deterministic
> metric-calculation rules, the frozen deterministic pacing-calculation rules, and the
> frozen neutral performance-classification rule. Trend classification, conversion-volume
> confidence, tracking interpretation, constraint, scoring, and allocation rules are
> pending later Sprint 1 stages.

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

These constants are reserved names and values only. No pacing, classification, scoring,
constraint, allocation, or conservation logic reads or applies them yet — that is pending
later Sprint 1 stages.

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

## Pending

- **Pacing interpretation.** Whether a given `pacing_ratio`, `spend_variance`, or
  `projected_end_of_period_spend` means a campaign is "on pace," "underspending,"
  "overspending," "under-delivering," "over-delivering," or "at risk" — any status,
  label, or recommendation built from Stage 4's pacing facts — is deferred entirely to a
  later classification/constraints stage. Stage 4 returns numbers only.
- **Trend interpretation.** How `trend_delta` (Stage 3 fact) is compared against
  `TREND_THRESHOLD` to determine `RECENT_TREND_IMPROVING` / `STABLE` / `DECLINING` — this
  interpretation, and any resulting `ReasonCode`, is explicitly deferred to the later
  classification stage.
- **Final recommendation.** Stage 5 resolved how `INCREASE_THRESHOLD`/
  `MAINTAIN_THRESHOLD` classify `weighted_performance_ratio` into a neutral
  `PerformanceBand` (see above) — but a `PerformanceBand` is not a `RecommendationAction`.
  `RecommendationAction` has a fourth member, `HOLD`, that cannot be derived from
  performance ratio thresholds alone; assigning a final `RecommendationAction` requires
  combining `PerformanceBand` with trend, confidence, tracking, and eligibility/
  constraint considerations that remain pending later stages.
- **Conversion-volume confidence.** How `MINIMUM_CONVERSIONS` and
  `HIGH_CONFIDENCE_CONVERSIONS` map `conversions_7d`/`conversions_28d` to `Confidence`
  levels — including which conversion window controls confidence, exact threshold
  boundaries, tracking-status effects, and `NOT_ASSESSABLE` behaviour — remains pending
  classification. Stage 3 does not use either constant.
- How `DEFAULT_MAX_CHANGE_PERCENTAGE` and per-campaign overrides constrain a recommended
  budget change.
- The full set of `ReasonCode` trigger conditions.
- Allocation and conservation rules.
