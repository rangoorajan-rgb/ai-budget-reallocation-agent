# Data Dictionary

> Sprint 1, Development Stage 6 (adds neutral deterministic trend classification to the
> Stage 1 enumerations, numerical constants, core input models, CSV schema, Stage 2
> validation reporting, Stage 3 metric facts, Stage 4 pacing facts, and Stage 5
> performance classification). Conversion-volume confidence, tracking interpretation, and
> other derived/decision fields, plus export fields, are pending later stages.

## Input CSV Schema (Google Ads and Meta Ads — shared)

One row per campaign. Google Ads and Meta Ads campaigns share a single CSV schema; the
`platform` column distinguishes them. Column order is fixed and must match exactly —
see `data/campaign_template.csv` and `src/models.py::CampaignInput`.

| # | Column | Type | Required | Description / rules |
|---|--------|------|----------|--------------|
| 1 | `campaign_id` | string | yes | Unique campaign identifier. Trimmed; must not be blank. |
| 2 | `campaign_name` | string | yes | Human-readable campaign name. Trimmed; must not be blank. |
| 3 | `platform` | enum (`Platform`) | yes | `Google Ads` or `Meta Ads`. |
| 4 | `status` | enum (`CampaignStatus`) | yes | `Active` or `Paused`. |
| 5 | `kpi_type` | enum (`KPIType`) | yes | `CPA` or `ROAS` — the objective this campaign is measured against. |
| 6 | `kpi_target` | Decimal (unquantised) | yes | Target CPA or ROAS value. Must be greater than 0. |
| 7 | `current_budget` | Decimal (currency, quantised to `0.01` via `ROUND_HALF_UP`) | yes | Campaign's current budget. Must be ≥ 0, and between `minimum_budget` and `maximum_budget` inclusive. |
| 8 | `minimum_budget` | Decimal (currency) | yes | Lowest budget this campaign may be assigned. Must be ≥ 0. |
| 9 | `maximum_budget` | Decimal (currency) | yes | Highest budget this campaign may be assigned. Must be ≥ `minimum_budget`. |
| 10 | `spend_to_date` | Decimal (currency) | yes | Spend so far in the current review period. Must be ≥ 0 and ≤ `current_budget`. |
| 11 | `conversions_7d` | integer | yes | Conversions in the trailing 7 days. Must be ≥ 0 and ≤ `conversions_28d`. |
| 12 | `conversions_28d` | integer | yes | Conversions in the trailing 28 days. Must be ≥ 0. |
| 13 | `kpi_actual_7d` | Decimal (unquantised) | yes | Actual CPA or ROAS over the trailing 7 days. Must be greater than 0. |
| 14 | `kpi_actual_28d` | Decimal (unquantised) | yes | Actual CPA or ROAS over the trailing 28 days. Must be greater than 0. |
| 15 | `tracking_status` | enum (`TrackingStatus`) | yes | `Healthy`, `Warning`, or `Unreliable`. |
| 16 | `business_priority` | enum (`BusinessPriority`) | yes | `Standard`, `Medium`, or `High`. |
| 17 | `is_protected` | boolean | yes | `True` if this campaign must never be reduced. Accepts literal booleans or case-insensitive `true`/`false`, `yes`/`no`, `1`/`0`; any other value is rejected as ambiguous. |
| 18 | `is_test_campaign` | boolean | yes | `True` if this is a test campaign subject to a budget floor. Same accepted values as `is_protected`. If `True`, `test_budget_floor` must be set; if `False`, `test_budget_floor` must be blank. |
| 19 | `test_budget_floor` | Decimal (currency) or blank | conditionally | Required and must be ≥ 0 and ≤ `current_budget` when `is_test_campaign` is `True`; must be blank when `is_test_campaign` is `False`. |
| 20 | `campaign_max_change_percentage` | Decimal (unquantised) or blank | no | Per-campaign override of the review's default max change percentage. When supplied, must satisfy `0 < value <= 1`. Blank to use the review default. |

Currency columns (`current_budget`, `minimum_budget`, `maximum_budget`, `spend_to_date`,
`test_budget_floor`) are parsed as `Decimal` and quantised to two decimal places using
`ROUND_HALF_UP`. KPI and percentage columns (`kpi_target`, `kpi_actual_7d`, `kpi_actual_28d`,
`campaign_max_change_percentage`) are parsed as `Decimal` but are **not** quantised — they
keep whatever precision was supplied. Boolean columns accept only the conventional
representations listed above.

## Review Setup Fields (entered by reviewer, not part of the campaign CSV)

Captured once per review via `src/models.py::ReviewSetup`, not uploaded as CSV.

| Field | Type | Required | Description / rules |
|-------|------|----------|--------------|
| `review_id` | string | yes | Unique identifier for this review. Trimmed; must not be blank. |
| `review_date` | date | yes | Date the review is performed. |
| `period_start` | date | yes | First day of the period under review. |
| `period_end` | date | yes | Last day of the period under review. Must not be before `period_start`. |
| `reviewer_name` | string | yes | Name of the human reviewer. Trimmed; must not be blank. |
| `approved_monthly_budget` | Decimal (currency, quantised to `0.01` via `ROUND_HALF_UP`) | yes | Total approved monthly budget across all campaigns. Must be greater than 0. |
| `initial_account_reserve` | Decimal (currency) | yes | Budget held back from reallocation. Must be ≥ 0 and ≤ `approved_monthly_budget`. |
| `default_max_change_percentage` | Decimal (unquantised) | no (default `0.20`, from `DEFAULT_MAX_CHANGE_PERCENTAGE`) | Default maximum per-campaign change percentage, used when a campaign has no override. Must satisfy `0 < value <= 1`. |
| `review_notes` | string or blank | no | Free-text notes from the reviewer. |

Both `ReviewSetup` and `CampaignInput` reject any field not in the lists above
(`extra="forbid"`).

## Validation Report Fields (`src/validation.py`)

Produced by `validate_review_setup()` and `validate_campaign_csv()`. Not part of the CSV
schema — these are the shapes returned to describe validation outcomes.

### `ValidationIssue`

| Field | Type | Description |
|-------|------|--------------|
| `severity` | enum (`ValidationSeverity`) | Always `ERROR` for every issue Stage 2 produces. |
| `code` | enum (`ValidationCode`) | One of `INVALID_REVIEW_FIELD`, `EMPTY_FILE`, `INVALID_HEADER`, `NO_CAMPAIGN_ROWS`, `MALFORMED_ROW`, `INVALID_CAMPAIGN_FIELD`, `DUPLICATE_CAMPAIGN_ID`. |
| `field` | string or `None` | Affected field name (dotted if nested), or `None` for file-level/model-level issues with no single field. |
| `message` | string | Human-readable description. Never a raw stack trace or internal exception representation. |
| `row_number` | integer or `None` | Physical one-based CSV line number (header is line 1, first data row is line 2), or `None` for file-level and `ReviewSetup` issues. |
| `campaign_id` | string or `None` | Trimmed `campaign_id` for the affected row, when it could be read; otherwise `None`. |

### `ValidationReport`

| Field | Type | Description |
|-------|------|--------------|
| `issues` | list of `ValidationIssue` | All issues found, in the order encountered. |
| `valid_campaigns` | list of `CampaignInput` | Successfully validated, non-duplicate campaigns, in original CSV order. |
| `error_count` | integer (computed) | Count of `ERROR`-severity issues. Derived from `issues` on every access; not settable independently. |
| `warning_count` | integer (computed) | Count of `WARNING`-severity issues. Derived from `issues`; always `0` for current Stage 2 outcomes. |
| `is_valid` | boolean (computed) | `True` only when `error_count == 0`. Derived from `issues`; not settable independently. |

`ValidationReport` intentionally has no `review_id` field: invalid raw review input may not
contain a usable review ID.

## Campaign Metrics Fields (`src/metrics.py`)

Produced by `calculate_campaign_metrics(campaign: CampaignInput) -> CampaignMetrics`, one
result per already-validated campaign. `CampaignMetrics` is frozen (immutable) and rejects
unknown fields (`extra="forbid"`). These are calculated **facts only** — none of them is a
classification, recommendation, confidence level, or trend label.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignInput`. |
| `performance_ratio_7d` | Decimal (unquantised) | Direction-normalised ratio of 7-day actual performance to target. `> 1` = better than target, `= 1` = exactly at target, `< 1` = worse than target — this meaning is identical for `CPA` and `ROAS`. |
| `performance_ratio_28d` | Decimal (unquantised) | Same as above, using the 28-day actual. |
| `weighted_performance_ratio` | Decimal (unquantised) | `performance_ratio_7d * SEVEN_DAY_WEIGHT + performance_ratio_28d * TWENTY_EIGHT_DAY_WEIGHT` — a single blended performance fact weighted toward the more stable 28-day window. |
| `trend_delta` | Decimal (unquantised) | `(performance_ratio_7d - performance_ratio_28d) / performance_ratio_28d` — the relative change of recent (7-day) performance versus the 28-day comparison. Positive = recent performance better than the 28-day baseline; negative = worse; zero = unchanged. Not yet classified as improving/stable/declining — see `docs/DECISION_RULES.md`. |

None of the four calculated fields is quantised to a fixed number of decimal places (no
`CURRENCY_QUANTUM` applied — these are ratios, not money) and none is ever a `float`. The
calculation is platform-independent — it depends only on `kpi_type`, `kpi_target`,
`kpi_actual_7d`, and `kpi_actual_28d`, never on `platform`.

## Campaign Pacing Fields (`src/pacing.py`)

Produced by `calculate_campaign_pacing(review: ReviewSetup, campaign: CampaignInput) ->
CampaignPacing`, one result per campaign within its review period. `CampaignPacing` is
frozen (immutable) and rejects unknown fields (`extra="forbid"`). These are calculated
**facts only** — none of them is a pacing status, label, classification, confidence
level, or recommendation. Independent of Stage 3: depends only on
`ReviewSetup.review_date`/`period_start`/`period_end` and
`CampaignInput.campaign_id`/`current_budget`/`spend_to_date` — never `platform`,
`kpi_type`, KPI actuals/targets, or `CampaignMetrics`.

| Field | Type | Units | Meaning |
|-------|------|-------|---------|
| `campaign_id` | string | — | Copied unchanged from the source `CampaignInput`. |
| `elapsed_days` | int | days | Inclusive days from `period_start` through `review_date`, clamped to `[0, total_period_days]`. `0` if `review_date` is before `period_start`; `total_period_days` if on or after `period_end`. |
| `total_period_days` | int | days | Inclusive day count of the review period: `(period_end - period_start).days + 1`. Always `>= 1`. |
| `elapsed_fraction` | Decimal (unquantised) | ratio, `0` to `1` | `elapsed_days / total_period_days`. Not quantised to fixed decimal places. |
| `expected_spend` | Decimal (currency, quantised to `0.01`) | currency | Linear-delivery expected spend: `current_budget * elapsed_fraction`, quantised for the public result. |
| `spend_variance` | Decimal (currency, quantised to `0.01`) | currency | `spend_to_date - (unquantised) expected_spend`. Positive = ahead of linear pace, negative = behind. No interpretation of good/bad. |
| `pacing_ratio` | Decimal (unquantised) or `None` | ratio | `spend_to_date / (unquantised) expected_spend`. `> 1` = spending faster than linear pace, `= 1` = exactly on pace, `< 1` = slower. **`None`** only when the unquantised expected spend is zero (i.e. `elapsed_days = 0` or `current_budget = 0.00`) — never a `0/0` sentinel. |
| `remaining_budget` | Decimal (currency, quantised to `0.01`) | currency | `current_budget - spend_to_date`. Cannot be negative — `CampaignInput` already guarantees `spend_to_date <= current_budget`. |
| `projected_end_of_period_spend` | Decimal (currency, quantised to `0.01`) or `None` | currency | Linear extrapolation: `spend_to_date / elapsed_fraction`, quantised. **`None`** only when `elapsed_fraction = 0` (before the period starts). Equals `spend_to_date` on the last day or after the period ends. |

`pacing_ratio` is computed from the **unquantised** `expected_spend` internally (not the
quantised public `expected_spend` field), so penny rounding never distorts the ratio.
All calculations run inside an explicit `decimal.localcontext()` (`prec=28`,
`ROUND_HALF_UP`), independent of any global `Decimal` context a caller may have mutated.
No field is ever a `float`.

## Campaign Performance Classification Fields (`src/classification.py`)

Produced by `classify_campaign_performance(metrics: CampaignMetrics) ->
CampaignPerformanceClass`, one result per already-calculated `CampaignMetrics` instance.
`CampaignPerformanceClass` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`). This is a **descriptive performance classification only** — it is
**not** a `RecommendationAction`, decision, constraint, score, eligibility result, or
budget action. Depends only on `CampaignMetrics.campaign_id`/`weighted_performance_ratio`
— never `CampaignInput`, `CampaignPacing`, `ReviewSetup`, `platform`, or `kpi_type`.

### `PerformanceBand` (enum)

| Member | Value | Meaning |
|--------|-------|---------|
| `ABOVE_TARGET` | `"ABOVE_TARGET"` | `weighted_performance_ratio >= INCREASE_THRESHOLD` (`1.15`). |
| `ON_TARGET` | `"ON_TARGET"` | `MAINTAIN_THRESHOLD <= weighted_performance_ratio < INCREASE_THRESHOLD` (`0.90` to just under `1.15`). |
| `BELOW_TARGET` | `"BELOW_TARGET"` | `weighted_performance_ratio < MAINTAIN_THRESHOLD` (below `0.90`). |

This is a deliberately neutral vocabulary, intentionally distinct from
`RecommendationAction` (`INCREASE`/`MAINTAIN`/`REDUCE`/`HOLD`) — `PerformanceBand` never
appears interchangeably with it, and no `RecommendationAction` is assigned anywhere in
Stage 5.

### `CampaignPerformanceClass`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignMetrics`. |
| `performance_band` | enum (`PerformanceBand`) | The classified band, per the table above. |

## Campaign Trend Classification Fields (`src/classification.py`)

Produced by `classify_campaign_trend(metrics: CampaignMetrics) -> CampaignTrendClass`,
one result per already-calculated `CampaignMetrics` instance. `CampaignTrendClass` is
frozen (immutable) and rejects unknown fields (`extra="forbid"`). This is **descriptive
evidence only** — it is independent of `PerformanceBand`/`CampaignPerformanceClass` and
is not a confidence assessment, tracking assessment, pacing interpretation, constraint,
eligibility decision, score, `RecommendationAction`, `ReasonCode`, or proposed
allocation. Depends only on `CampaignMetrics.campaign_id`/`trend_delta` — never
`CampaignInput`, `CampaignPacing`, `ReviewSetup`, `platform`, or `kpi_type`.

`trend_delta` itself (`src/metrics.py`) is a dimensionless *relative* `Decimal` ratio, not
a percentage-point value: `Decimal("0.10")` means a 10% relative change between the
7-day and 28-day normalised performance ratios, not "10 percentage points."

### `TrendDirection` (enum)

| Member | Value | Meaning |
|--------|-------|---------|
| `IMPROVING` | `"IMPROVING"` | `trend_delta >= TREND_THRESHOLD` (`0.10`). |
| `STABLE` | `"STABLE"` | `-TREND_THRESHOLD < trend_delta < TREND_THRESHOLD` (strictly between `-0.10` and `0.10`). |
| `DECLINING` | `"DECLINING"` | `trend_delta <= -TREND_THRESHOLD` (`-0.10`). |

This is deliberately descriptive evidence, not `RecommendationAction` or `ReasonCode` —
`TrendDirection` never appears interchangeably with either, and neither is assigned
anywhere in Stage 6.

### `CampaignTrendClass`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignMetrics`. |
| `trend_direction` | enum (`TrendDirection`) | The classified direction, per the table above. |

`CampaignTrendClass` is a separate, independent result model from
`CampaignPerformanceClass` — the two are never combined, and neither is required to
construct the other.

## Derived Fields

> Pending a later Sprint 1 stage (conversion-volume confidence, tracking interpretation,
> constraints, scoring, allocation).

## Export Fields

> Pending a later Sprint 1 stage (`src/exports.py`).
