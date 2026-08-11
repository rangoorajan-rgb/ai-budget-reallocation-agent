# Data Dictionary

> Sprint 1, Development Stage 13 (adds a neutral, informational test-floor distance
> calculation to the Stage 1 enumerations, numerical constants, core input models, CSV
> schema, Stage 2 validation reporting, Stage 3 metric facts, Stage 4 pacing facts,
> Stage 5 performance classification, Stage 6 trend classification, Stage 7
> conversion-volume confidence classification, Stage 8 tracking-based assessability,
> Stage 9 pacing interpretation, Stage 10 static budget-bound facts, Stage 11
> applicable-change-percentage resolution, and Stage 12 raw percentage-based monetary
> movement cap). Combined assessment, `Confidence.NOT_ASSESSABLE` ownership,
> effective-floor precedence, static-bound/raw-cap intersection, effective constraints,
> protected-campaign handling, eligibility, and other derived/decision fields, plus
> export fields, are pending later stages.

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

## Campaign Conversion-Volume Confidence Fields (`src/classification.py`)

Produced by `classify_campaign_confidence(campaign: CampaignInput) ->
CampaignConfidenceClass`, one result per already-validated `CampaignInput` instance.
`CampaignConfidenceClass` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`). This is **descriptive conversion-volume evidence only** — it is
independent of `PerformanceBand`/`CampaignPerformanceClass` and
`TrendDirection`/`CampaignTrendClass`, and is not a tracking interpretation,
assessability decision, pacing interpretation, constraint, eligibility decision, score,
recommendation, reason code, or allocation. Depends only on
`CampaignInput.campaign_id`/`conversions_28d` — never `conversions_7d`,
`CampaignMetrics`, `CampaignPacing`, `ReviewSetup`, `tracking_status`, `platform`, or
`kpi_type`.

### `Confidence` (existing enum, reused — not redefined)

| Member | Value | Meaning as conversion-volume evidence | Assigned by Stage 7? |
|--------|-------|----------------------------------------|------------------------|
| `HIGH` | `"HIGH"` | `conversions_28d >= HIGH_CONFIDENCE_CONVERSIONS` (`30`) — ample trailing-28-day conversion evidence. | Yes |
| `MEDIUM` | `"MEDIUM"` | `MINIMUM_CONVERSIONS <= conversions_28d < HIGH_CONFIDENCE_CONVERSIONS` (`10`–`29`) — moderate evidence. | Yes |
| `LOW` | `"LOW"` | `conversions_28d < MINIMUM_CONVERSIONS` (`0`–`9`), including zero. | Yes |
| `NOT_ASSESSABLE` | `"NOT_ASSESSABLE"` | Reserved for a later stage. | **No — Stage 7 never assigns this member.** This is a deliberate scope boundary, not a claim that the value is unreachable in general; its trigger (potentially involving tracking reliability or another combined judgement) remains pending. |

### `CampaignConfidenceClass`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignInput`. |
| `confidence` | enum (`Confidence`) | The classified conversion-volume band, per the table above. |

`CampaignConfidenceClass` is a separate, independent result model from
`CampaignPerformanceClass` and `CampaignTrendClass` — none of the three is required to
construct another, and none is modified by this addition. `Confidence` is descriptive
evidence, not `RecommendationAction` or `ReasonCode`.

## Campaign Tracking Assessment Fields (`src/classification.py`)

Produced by `assess_campaign_tracking(campaign: CampaignInput) ->
CampaignTrackingAssessment`, one result per already-validated `CampaignInput` instance.
`CampaignTrackingAssessment` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`). This is a **narrow tracking-based assessability fact only** — it is
not conversion-volume confidence, a `Confidence.NOT_ASSESSABLE` assignment, a
replacement for `CampaignConfidenceClass`, a performance classification, a trend
classification, a pacing interpretation, a combined campaign judgement, a constraint, an
eligibility decision, a score, a recommendation, a reason code, or an allocation.
Depends only on `CampaignInput.campaign_id`/`tracking_status` — never
`conversions_7d`/`conversions_28d`, `CampaignMetrics`, `CampaignPacing`, `platform`,
`kpi_type`, or protected/test status.

### `TrackingStatus` (existing enum, reused — not redefined)

| Member | Value | Stage 8 `is_assessable` outcome |
|--------|-------|-----------------------------------|
| `HEALTHY` | `"Healthy"` | `True` |
| `WARNING` | `"Warning"` | `True` — represents a concern requiring later caution, not a declaration that the evidence is unusable. |
| `UNRELIABLE` | `"Unreliable"` | `False` — the sole condition producing `is_assessable=False`. |

### `CampaignTrackingAssessment`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignInput`. |
| `tracking_status` | enum (`TrackingStatus`) | Copied unchanged from the source `CampaignInput` — **`WARNING` is never collapsed into `HEALTHY`**, preserving that distinction for later `ReasonCode`/recommendation logic. |
| `is_assessable` | boolean | `campaign.tracking_status is not TrackingStatus.UNRELIABLE`. |

`CampaignTrackingAssessment` is a separate, independent result model from
`CampaignPerformanceClass`, `CampaignTrendClass`, and `CampaignConfidenceClass` — none of
the four is required to construct another, and none is modified by this addition.
**`Confidence.NOT_ASSESSABLE` is not assigned anywhere in Stage 8** — it remains a valid,
unmodified `Confidence` member whose trigger and ownership remain pending a later
combined-assessment stage.

## Campaign Pacing Interpretation Fields (`src/pacing.py`)

Produced by `classify_campaign_pacing(pacing: CampaignPacing) -> CampaignPacingClass`,
one result per already-calculated `CampaignPacing` instance. `CampaignPacingClass` is
frozen (immutable) and rejects unknown fields (`extra="forbid"`). This is a **neutral,
descriptive pacing classification only** — it is not a judgement that overspending or
underspending is desirable or undesirable, and it is not a performance classification,
trend classification, conversion-volume confidence classification, tracking-based
assessability result, combined campaign judgement, constraint, eligibility decision,
score, recommendation, reason code, or allocation. Depends only on
`CampaignPacing.campaign_id`/`pacing_ratio` — never `spend_variance`, `expected_spend`,
`elapsed_fraction`, `elapsed_days`, `total_period_days`, `remaining_budget`,
`projected_end_of_period_spend`, `CampaignInput`, `ReviewSetup`, `CampaignMetrics`, or
any Stage 5–8 result.

### `PacingStatus` (enum)

| Member | Value | Meaning |
|--------|-------|---------|
| `UNDERSPENDING` | `"Under spending"` | `pacing_ratio < PACING_LOWER_THRESHOLD` (`0.90`). |
| `ON_PACE` | `"On pace"` | `PACING_LOWER_THRESHOLD <= pacing_ratio <= PACING_UPPER_THRESHOLD` (`0.90` to `1.10` inclusive — a closed, symmetric ±10% tolerance band around `1.00`). |
| `OVERSPENDING` | `"Over spending"` | `pacing_ratio > PACING_UPPER_THRESHOLD` (`1.10`). |
| `NOT_AVAILABLE` | `"Not available"` | `pacing_ratio is None` — a **pacing-data state only**, produced when the upstream `CampaignPacing` calculation could not compute a meaningful ratio (zero elapsed time or zero current budget). It is never `Confidence.NOT_ASSESSABLE`, `is_assessable=False`, `TrackingStatus.UNRELIABLE`, `RecommendationAction.HOLD`, a reason code, or an eligibility outcome. |

The threshold values themselves belong to `ON_PACE`: `pacing_ratio == PACING_LOWER_THRESHOLD`
and `pacing_ratio == PACING_UPPER_THRESHOLD` are both `ON_PACE` — the on-pace interval is
closed and inclusive on both ends, unlike Stages 5–7's single-sided threshold-entry
convention.

### `CampaignPacingClass`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignPacing`. |
| `pacing_status` | enum (`PacingStatus`) | The classified pacing status, per the table above. |

`classify_campaign_pacing` reads only `pacing.campaign_id` and `pacing.pacing_ratio` —
no other `CampaignPacing` field, and no `CampaignInput`, `ReviewSetup`, `CampaignMetrics`,
or Stage 5–8 result. No arithmetic, quantisation, or `Decimal`/`float` conversion is
performed; `pacing_ratio` is never recalculated. `CampaignPacingClass` is a separate,
independent result model from `CampaignPerformanceClass`, `CampaignTrendClass`,
`CampaignConfidenceClass`, and `CampaignTrackingAssessment` — none of the five is
required to construct another, and none is modified by this addition. Whether/how
pacing status combines with performance, trend, confidence, or tracking assessability
into any final judgement remains pending a later combined-assessment stage.

## Campaign Static Budget Room Fields (`src/constraints.py`)

Produced by `calculate_campaign_static_budget_room(campaign: CampaignInput) ->
CampaignStaticBudgetRoom`, one result per already-validated `CampaignInput` instance.
`CampaignStaticBudgetRoom` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`). These are **static budget-bound distance facts only** — they are
**not** the campaign's final permissible budget movement, an effective minimum/maximum
budget, a percentage-based limit, a protection or test-budget-floor determination, an
eligibility result, a blocking flag, a score, a recommendation, a reason code, or an
allocation. Depends only on `CampaignInput.campaign_id`/`current_budget`/
`minimum_budget`/`maximum_budget` — never `campaign_max_change_percentage`,
`is_protected`, `is_test_campaign`, `test_budget_floor`, `ReviewSetup`, or any Stage 3–9
result.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignInput`. |
| `room_to_static_maximum` | Decimal | `maximum_budget - current_budget`. The static distance from the campaign's current budget to its validated `maximum_budget`. Guaranteed `>= 0` by `CampaignInput`'s validated `current_budget <= maximum_budget` invariant; `Decimal("0.00")` exactly when `current_budget == maximum_budget` — a valid calculated fact, never replaced with `None` or a categorical status. |
| `room_to_static_minimum` | Decimal | `current_budget - minimum_budget`. The static distance from the campaign's current budget to its validated `minimum_budget`. Guaranteed `>= 0` by `CampaignInput`'s validated `minimum_budget <= current_budget` invariant; `Decimal("0.00")` exactly when `current_budget == minimum_budget`. |

**These are static-bound distances, not final permissible movements.**
`campaign_max_change_percentage`, `ReviewSetup.default_max_change_percentage`, and
`DEFAULT_MAX_CHANGE_PERCENTAGE` are never read or applied — the percentage-limit
mechanism and its precedence relative to these static bounds remain pending a later
effective-constraint stage. `is_protected` and `is_test_campaign`/`test_budget_floor`
are likewise never read: reporting `room_to_static_minimum` against `minimum_budget`
does **not** authorise reducing a test campaign below its `test_budget_floor`, and
reporting `room_to_static_maximum` does **not** authorise increasing a protected
campaign — both remain pending a later effective-constraint stage that must consider
protection and test-floor rules before any budget movement is proposed.
`CampaignStaticBudgetRoom` is a separate, independent result model from
`CampaignPerformanceClass`, `CampaignTrendClass`, `CampaignConfidenceClass`,
`CampaignTrackingAssessment`, and `CampaignPacingClass` — none of the six is required to
construct another, and none is modified by this addition.

## Campaign Applicable Change-Percentage Fields (`src/constraints.py`)

Produced by `resolve_campaign_applicable_change_percentage(review: ReviewSetup,
campaign: CampaignInput) -> CampaignApplicableChangePercentage`, one result per
already-validated `ReviewSetup`/`CampaignInput` pair. `CampaignApplicableChangePercentage`
is frozen (immutable) and rejects unknown fields (`extra="forbid"`). This is a **neutral
`Decimal` configuration fact only** — it is **not** a monetary movement cap, a
multiplication by `current_budget` or any other amount, a static-bound intersection, an
increase/decrease symmetry rule, a protection or test-budget-floor determination, an
eligibility result, a score, a recommendation, a reason code, or an allocation. Depends
only on `CampaignInput.campaign_id`/`campaign_max_change_percentage` and
`ReviewSetup.default_max_change_percentage` — never `current_budget`, `minimum_budget`,
`maximum_budget`, `room_to_static_maximum`, `room_to_static_minimum`, `is_protected`,
`is_test_campaign`, `test_budget_floor`, `platform`, `kpi_type`, or any Stage 3–9
result. The module-level `DEFAULT_MAX_CHANGE_PERCENTAGE` constant is never imported or
read — only the already-validated `review.default_max_change_percentage` value is used,
so a caller-supplied `ReviewSetup` is always respected.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignInput`. |
| `applicable_max_change_percentage` | Decimal | `campaign.campaign_max_change_percentage` when it is not `None`; otherwise `review.default_max_change_percentage`. Never `None`. Preserved exactly — no arithmetic, quantisation, or rounding is performed. |

**Exact override/default rule:** the campaign-level override always wins when present
(explicit `is not None` check, not a truthiness check); otherwise the review's default
applies. This selects **which already-validated percentage applies** — it does **not**
calculate a monetary cap or determine any permissible budget movement.
`CampaignApplicableChangePercentage` is a separate, independent result model from
`CampaignStaticBudgetRoom` — the two are never combined, and neither is required to
construct the other.

## Campaign Raw Percentage Movement-Cap Fields (`src/constraints.py`)

Produced by `calculate_campaign_raw_percentage_movement_cap(campaign: CampaignInput,
applicable_percentage: CampaignApplicableChangePercentage) ->
CampaignRawPercentageMovementCap`, one result per already-validated `CampaignInput`
paired with its already-resolved Stage 11 `CampaignApplicableChangePercentage`.
`CampaignRawPercentageMovementCap` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`). This is a **raw, informational monetary fact only** — it is **not**
permission to increase or decrease a campaign's budget, an effective/final permissible
movement, a static-bound intersection, a protection or test-budget-floor
determination, an eligibility result, a score, a recommendation, a reason code, or an
allocation. Depends only on `CampaignInput.campaign_id`/`current_budget` and
`CampaignApplicableChangePercentage.campaign_id`/`applicable_max_change_percentage` —
never `minimum_budget`, `maximum_budget`, `room_to_static_maximum`,
`room_to_static_minimum`, `is_protected`, `is_test_campaign`, `test_budget_floor`,
`platform`, `kpi_type`, `ReviewSetup`, `campaign_max_change_percentage`, or any Stage
3–9 result. Stage 12 consumes Stage 11's already-resolved result directly — it never
re-resolves campaign-override/review-default precedence.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignInput`. |
| `raw_percentage_movement_cap` | Decimal | `current_budget * applicable_max_change_percentage`, quantised once to two decimal places using `ROUND_HALF_UP`. Never `None`. `Decimal("0.00")` when `current_budget = Decimal("0.00")` — a legitimate result, not an error or eligibility judgement. |

**Exact current-budget multiplication rule.** The percentage is multiplied against
`CampaignInput.current_budget` — no other base amount is used. **Campaign-ID matching
requirement:** `calculate_campaign_raw_percentage_movement_cap` requires
`campaign.campaign_id == applicable_percentage.campaign_id`; a mismatch raises
`ValueError("campaign_id mismatch between campaign and applicable percentage")` and no
result is returned — the two input objects independently identify a campaign, and
silently applying one campaign's percentage to another would be unsafe.

**Decimal type and quantisation.** `raw_percentage_movement_cap` is always a `Decimal`,
never `float`, and always quantised to exactly two decimal places (reusing the existing
`CURRENCY_QUANTUM` constant) via `ROUND_HALF_UP`. The multiplication and quantisation
both run inside a local `decimal` context whose precision is derived from the operands'
own digit counts (`max(28, digits(current_budget) + digits(applicable_max_change_percentage)
+ 4)`) rather than a fixed value — `current_budget` has no upper bound and
`applicable_max_change_percentage` has no digit-count restriction, so a fixed
`prec=28` context can round the intermediate multiplication before the final
quantisation ever runs, producing an incorrect result via double rounding. The
operand-derived precision guarantees the multiplication is computed exactly, leaving
the explicit final `quantize` call as the sole rounding operation; this is empirically
verified by a regression test using the largest `current_budget` `Currency` can hold
under the default global context (`Decimal("99999999999999999999999999.99")`, 28
significant digits) paired with a many-decimal-digit percentage
(`Decimal("0.036020245307579938554529107051")`) — a fixed `prec=28` context incorrectly
returns `...52910.71`, while the correct, exact result is `...52910.70`.

**The result is informational only.** `CampaignRawPercentageMovementCap` is a separate,
independent result model from `CampaignStaticBudgetRoom` and
`CampaignApplicableChangePercentage` — none of the three is required to construct
another, and none is modified by this addition. Whether/how the raw cap combines with
Stage 10's static room, protection, or test-budget-floor rules into any effective,
permissible movement remains pending a later stage.

## Campaign Test-Floor Room Fields (`src/constraints.py`)

Produced by `calculate_campaign_test_floor_room(campaign: CampaignInput) ->
CampaignTestFloorRoom`, one result per already-validated `CampaignInput`.
`CampaignTestFloorRoom` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`). This is a **raw, informational test-floor distance fact only** —
it is **not** the effective floor, **not** an alternative or additional minimum,
**not** permissible decrease, **not** an effective directional constraint, and is
**never** combined with `minimum_budget`, Stage 10's static room, or Stage 12's raw
percentage movement cap. Depends only on `CampaignInput.campaign_id`/
`is_test_campaign`/`current_budget`/`test_budget_floor` — never `minimum_budget`,
`maximum_budget`, `is_protected`, `campaign_max_change_percentage`, `platform`,
`kpi_type`, `ReviewSetup`, or any Stage 3–9/Stage 10–12 result.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignInput`. |
| `room_to_test_floor` | Decimal or `None` | `current_budget - test_budget_floor` when `is_test_campaign` is `True`. Guaranteed `>= 0` by `CampaignInput`'s already-validated `test_budget_floor <= current_budget` invariant; `Decimal("0.00")` is a valid, unaltered outcome when `current_budget == test_budget_floor`. `None` when `is_test_campaign` is `False` — an explicit statement that the fact does not apply, never a fallback value, zero, or an error. |

**Exact subtraction rule and non-test behaviour.** For a test campaign,
`room_to_test_floor = current_budget - test_budget_floor`, computed inside a fixed
local `decimal` context (`prec=28`, `ROUND_HALF_UP`, matching Stage 10's established
policy — no operand-derived precision is needed, since subtracting two already-
quantised `Currency` values never needs more significant digits than the larger
operand already has). Neither operand is re-quantised, and the result is not
re-quantised — the two-decimal-place exponent already produced by the subtraction is
preserved exactly. For a non-test campaign, `calculate_campaign_test_floor_room`
returns `room_to_test_floor=None` without raising an error and without any special
validation.

**The output is informational only and does not decide the effective floor.**
`CampaignTestFloorRoom` is a separate, independent result model from
`CampaignStaticBudgetRoom`, `CampaignApplicableChangePercentage`, and
`CampaignRawPercentageMovementCap` — none of the four is required to construct
another, and none is modified by this addition. Whether the eventual effective floor
is `minimum_budget`, `test_budget_floor`, `max(minimum_budget, test_budget_floor)`, or
another formulation remains an explicitly undecided later-stage question — this
approval resolves only the raw distance fact, not that precedence.

## Derived Fields

> Pending a later Sprint 1 stage (combined confidence/tracking/pacing assessment,
> `Confidence.NOT_ASSESSABLE` ownership, effective-floor precedence, static-bound/
> raw-cap intersection, effective constraints, protected-campaign handling,
> eligibility, scoring, allocation).

## Export Fields

> Pending a later Sprint 1 stage (`src/exports.py`).
