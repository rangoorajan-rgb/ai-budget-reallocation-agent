# Data Dictionary

> Sprint 1, Development Stage 21 (adds deterministic per-campaign
> `RecommendationAction` selection — `INCREASE`, `MAINTAIN`, `REDUCE`, or
> `HOLD` — from `src/recommendation.py` — to the Stage 1 enumerations,
> numerical constants, core input models, CSV schema, Stage 2 validation reporting,
> Stage 3 metric facts, Stage 4 pacing facts, Stage 5 performance classification,
> Stage 6 trend classification, Stage 7 conversion-volume confidence classification,
> Stage 8 tracking-based assessability, Stage 9 pacing interpretation, Stage 10
> static budget-bound facts, Stage 11 applicable-change-percentage resolution, Stage
> 12 raw percentage-based monetary movement cap, Stage 13 test-floor distance, Stage
> 14 protection constraint, Stage 15 test-aware static decrease room, Stage 16 raw
> increase limit, Stage 17 raw decrease limit, Stage 18 protection-adjusted
> effective decrease limit, Stage 19 campaign action availability, and Stage 20
> campaign action suitability). Combined assessment, `Confidence.NOT_ASSESSABLE`
> ownership, `ReasonCode`, numeric prioritisation scoring, ranking, allocation,
> and other derived/decision fields, plus export fields, are pending later stages.

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

## Campaign Protection Constraint Fields (`src/constraints.py`)

Produced by `resolve_campaign_protection_constraint(campaign: CampaignInput) ->
CampaignProtectionConstraint`, one result per already-validated `CampaignInput`.
`CampaignProtectionConstraint` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`). This is a **neutral, decrease-specific fact only** — it is
**not** an eligibility decision, a recommendation, a monetary movement amount,
permissible decrease, an effective directional limit, or an increase-side constraint,
and it is **never** combined with Stages 10–13. Depends only on
`CampaignInput.campaign_id`/`is_protected` — never `current_budget`,
`minimum_budget`, `maximum_budget`, `is_test_campaign`, `test_budget_floor`,
`campaign_max_change_percentage`, `platform`, `kpi_type`, `ReviewSetup`, or any Stage
3–9/Stage 10–13 result.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied unchanged from the source `CampaignInput`. |
| `decrease_blocked` | boolean | `campaign.is_protected`, unchanged. `True` means only that protection prohibits a decrease — it does not determine eligibility, recommendation action, allocation, or any other judgement. `False` means only that protection itself does not prohibit a decrease — it is **not** permission to reduce the campaign's budget; other constraints may still apply. |

**No monetary amount is calculated.** Stage 14 performs no `Decimal` arithmetic and
produces no currency-shaped field — `decrease_blocked` is a plain boolean, directly
derived from `is_protected`'s frozen meaning ("`True` if this campaign must never be
reduced," row 17 above) without translating it into a room amount or any other
monetary representation.

**Decrease-specific; increase behaviour unaddressed.** The frozen `is_protected`
meaning speaks only to reduction — `CampaignProtectionConstraint` says nothing about
whether a protected campaign may receive an increase. This is deliberately left
unaddressed, not assumed either way.

**Does not decide the effective floor.** `CampaignProtectionConstraint` is a
separate, independent result model from `CampaignStaticBudgetRoom`,
`CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`, and
`CampaignTestFloorRoom` — none of the five is required to construct another, and none
is modified by this addition. How `decrease_blocked` eventually combines with Stage
10's static room, Stage 12's raw cap, and Stage 13's test-floor room into any
effective decrease limit remains an explicitly undecided later-stage question.

## Campaign Test-Aware Static Decrease Room Fields (`src/constraints.py`)

Produced by `resolve_campaign_test_aware_static_decrease_room(static_room:
CampaignStaticBudgetRoom, test_floor_room: CampaignTestFloorRoom) ->
CampaignTestAwareStaticDecreaseRoom`, one result per already-calculated Stage 10 and
Stage 13 result pair. `CampaignTestAwareStaticDecreaseRoom` is frozen (immutable) and
rejects unknown fields (`extra="forbid"`). This is a **raw, test-aware static
constraint only** — it is **not** permissible decrease, **not** an effective
decrease limit, and does **not** mean the campaign should be reduced. It does not
account for Stage 12's percentage cap or Stage 14's protection constraint. Depends
only on `CampaignStaticBudgetRoom.campaign_id`/`room_to_static_minimum` and
`CampaignTestFloorRoom.campaign_id`/`room_to_test_floor` — never `CampaignInput`,
`CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`,
`CampaignProtectionConstraint`, or `ReviewSetup`. Stage 15 consumes Stage 10's and
Stage 13's already-approved facts directly — it never calls
`calculate_campaign_static_budget_room` or `calculate_campaign_test_floor_room`, and
never recalculates either room from raw budget fields.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `static_room.campaign_id`, after confirming it matches `test_floor_room.campaign_id`. |
| `test_aware_static_decrease_room` | Decimal | `room_to_static_minimum` when `room_to_test_floor is None` (non-test campaigns); otherwise `min(room_to_static_minimum, room_to_test_floor)`. Never `None`. |

**Business meaning.** `test_budget_floor` is treated as an *additional* retained-spend
floor for test campaigns — a non-test campaign is constrained only by
`minimum_budget` at this stage; a test campaign is constrained by both
`minimum_budget` and `test_budget_floor`, and the stricter (higher) floor controls.
This is mathematically equivalent to `effective_decrease_floor =
max(minimum_budget, test_budget_floor)`, expressed instead as the smaller of the two
already-calculated rooms to avoid recalculating either floor distance.

**Campaign-ID policy.** `static_room.campaign_id` and `test_floor_room.campaign_id`
must match; a mismatch raises `ValueError("Campaign IDs must match when resolving
test-aware static decrease room.")` before any monetary result is resolved — neither
ID is silently preferred.

**Zero behaviour.** `Decimal("0.00")` is a legitimate result when the smaller
applicable room is zero — it means there is no static room to reduce under the
combined floor rule, not an eligibility or recommendation judgement.

**No arithmetic is performed.** The selected `Decimal` operand (`room_to_static_minimum`
or `room_to_test_floor`) is returned unchanged — no subtraction, multiplication,
division, quantisation, or rounding occurs, and no `Decimal` context is used.

**Separation from percentage caps and protection.** `CampaignTestAwareStaticDecreaseRoom`
is a separate, independent result model from `CampaignRawPercentageMovementCap` and
`CampaignProtectionConstraint` — neither is read, and neither is combined with this
result. Whether/how this constraint eventually intersects with Stage 12's percentage
cap, or is overridden by Stage 14's protection constraint, remains pending later
stages.

## Campaign Raw Increase Limit Fields (`src/constraints.py`)

Produced by `resolve_campaign_raw_increase_limit(static_room: CampaignStaticBudgetRoom,
raw_cap: CampaignRawPercentageMovementCap) -> CampaignRawIncreaseLimit`, one result per
already-calculated Stage 10 and Stage 12 result pair. `CampaignRawIncreaseLimit` is
frozen (immutable) and rejects unknown fields (`extra="forbid"`). This is a **raw,
increase-specific constraint only** — it is **not** permission to increase a budget,
**not** an effective increase, **not** eligibility, **not** a recommendation, and
**not** a final movement amount. Depends only on
`CampaignStaticBudgetRoom.campaign_id`/`room_to_static_maximum` and
`CampaignRawPercentageMovementCap.campaign_id`/`raw_percentage_movement_cap` — never
`CampaignInput`, `ReviewSetup`, `room_to_static_minimum`,
`applicable_max_change_percentage`, `room_to_test_floor`, `decrease_blocked`, or
`test_aware_static_decrease_room`. Stage 16 consumes Stage 10's and Stage 12's
already-approved facts directly — it never calls
`calculate_campaign_static_budget_room` or
`calculate_campaign_raw_percentage_movement_cap`, and never recalculates either fact.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `static_room.campaign_id`, after confirming it matches `raw_cap.campaign_id`. |
| `raw_increase_limit` | Decimal | `min(room_to_static_maximum, raw_percentage_movement_cap)`. Never `None`. |

**Business meaning.** Both upward constraints apply simultaneously —
`room_to_static_maximum` prevents exceeding `maximum_budget`;
`raw_percentage_movement_cap` limits the size of a change under the applicable
percentage rule — so the smaller value is the binding limit.

**Campaign-ID policy.** `static_room.campaign_id` and `raw_cap.campaign_id` must
match; a mismatch raises `ValueError("Campaign IDs must match when resolving raw
increase limit.")` before any Decimal selection — neither ID is silently preferred.

**Zero behaviour.** `Decimal("0.00")` is a legitimate result when the smaller
applicable constraint is zero — it means no raw increase room remains under these two
constraints, not eligibility or a recommendation.

**No arithmetic is performed.** The selected `Decimal` operand
(`room_to_static_maximum` or `raw_percentage_movement_cap`) is returned unchanged —
no subtraction, multiplication, division, quantisation, or rounding occurs, and no
`Decimal` context is used.

**Separation from protection and test-floor rules.** `CampaignRawIncreaseLimit` is a
separate, independent result model from `CampaignProtectionConstraint` and
`CampaignTestFloorRoom`/`CampaignTestAwareStaticDecreaseRoom` — neither is read, and
neither is combined with this result. Protected status has no approved increase-side
effect here, and test-floor rules are decrease-specific — this does not infer any
protection-based or test-floor-based increase rule. Whether/how this constraint
eventually intersects with a raw decrease limit, or is adjusted for effective
constraints, remains pending later stages.

## Campaign Raw Decrease Limit Fields (`src/constraints.py`)

Produced by `resolve_campaign_raw_decrease_limit(decrease_room:
CampaignTestAwareStaticDecreaseRoom, raw_cap: CampaignRawPercentageMovementCap) ->
CampaignRawDecreaseLimit`, one result per already-calculated Stage 15 and Stage 12
result pair. `CampaignRawDecreaseLimit` is frozen (immutable) and rejects unknown
fields (`extra="forbid"`). This is a **raw, decrease-specific constraint only** — it
is **not** permission to decrease a budget, **not** an effective decrease, **not**
eligibility, **not** a recommendation, and **not** a final movement amount. Depends
only on `CampaignTestAwareStaticDecreaseRoom.campaign_id`/
`test_aware_static_decrease_room` and
`CampaignRawPercentageMovementCap.campaign_id`/`raw_percentage_movement_cap` — never
`CampaignInput`, `ReviewSetup`, `CampaignStaticBudgetRoom`,
`CampaignApplicableChangePercentage`, `CampaignTestFloorRoom`,
`CampaignProtectionConstraint`, `decrease_blocked`, `is_protected`, or
`CampaignRawIncreaseLimit`/`raw_increase_limit`. Stage 17 consumes Stage 15's and
Stage 12's already-approved facts directly — it never calls
`resolve_campaign_test_aware_static_decrease_room` or
`calculate_campaign_raw_percentage_movement_cap`, and never recalculates either fact.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `decrease_room.campaign_id`, after confirming it matches `raw_cap.campaign_id`. |
| `raw_decrease_limit` | Decimal | `min(test_aware_static_decrease_room, raw_percentage_movement_cap)`. Never `None`. |

**Business meaning.** Both decrease-side constraints apply simultaneously —
`test_aware_static_decrease_room` preserves the approved minimum-budget/test-floor
constraint (Stage 15); `raw_percentage_movement_cap` limits the size of a change
under the applicable percentage rule (Stage 12) — so the smaller value is the
binding limit. A protected campaign still receives its neutral Stage 17 raw result;
Stage 14's protection constraint is not applied here.

**Campaign-ID policy.** `decrease_room.campaign_id` and `raw_cap.campaign_id` must
match; a mismatch raises `ValueError("Campaign IDs must match when resolving raw
decrease limit.")` before any Decimal selection — neither ID is silently preferred.

**Zero and negative behaviour.** `Decimal("0.00")` is a legitimate result when the
smaller applicable constraint is zero — it means no raw decrease room remains under
these two constraints, not protection, eligibility, or a recommendation. A negative
result is structurally impossible: both inputs are guaranteed non-negative by their
own upstream Stage 10/12/13/15 invariants, and `min()` of two non-negative Decimals
is non-negative.

**No arithmetic is performed.** The selected `Decimal` operand
(`test_aware_static_decrease_room` or `raw_percentage_movement_cap`) is returned
unchanged — no subtraction, multiplication, division, quantisation, or rounding
occurs, and no `Decimal` context is used.

**Separation from protection and the increase side.** `CampaignRawDecreaseLimit` is
a separate, independent result model from `CampaignProtectionConstraint` and
`CampaignRawIncreaseLimit` — neither is read, and neither is combined with this
result. `decrease_blocked`/`is_protected` have no effect on this result, and no
combined increase/decrease model is produced. Whether/how this constraint eventually
combines with Stage 14's protection constraint, or is adjusted for effective
constraints, remains pending later stages.

## Campaign Effective Decrease Limit Fields (`src/constraints.py`)

Produced by `resolve_campaign_effective_decrease_limit(raw_decrease:
CampaignRawDecreaseLimit, protection: CampaignProtectionConstraint) ->
CampaignEffectiveDecreaseLimit`, one result per already-calculated Stage 17 and
Stage 14 result pair. `CampaignEffectiveDecreaseLimit` is frozen (immutable) and
rejects unknown fields (`extra="forbid"`). The output represents the effective
decrease limit under the currently approved static minimum-budget constraint,
test-floor constraint, percentage movement constraint, and protection constraint.
It is **still not** eligibility, a recommendation, a final movement amount, an
allocation, or a decision to decrease the campaign — a campaign with
`effective_decrease_limit == Decimal("0.00")` may still later be eligible for
`MAINTAIN` or `INCREASE`. Depends only on
`CampaignRawDecreaseLimit.campaign_id`/`raw_decrease_limit` and
`CampaignProtectionConstraint.campaign_id`/`decrease_blocked` — never
`CampaignInput`, `ReviewSetup`, `CampaignStaticBudgetRoom`,
`CampaignApplicableChangePercentage`, `CampaignRawPercentageMovementCap`,
`CampaignTestFloorRoom`, `CampaignTestAwareStaticDecreaseRoom`, or
`CampaignRawIncreaseLimit`/`raw_increase_limit`. Stage 18 consumes Stage 17's and
Stage 14's already-approved facts directly — it never calls
`resolve_campaign_raw_decrease_limit` or `resolve_campaign_protection_constraint`,
and never recalculates either fact.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `raw_decrease.campaign_id`, after confirming it matches `protection.campaign_id`. |
| `effective_decrease_limit` | Decimal | `Decimal("0.00")` when `decrease_blocked` is `True`; otherwise `raw_decrease_limit` unchanged. Never `None`. |

**Protected mapping.** When `decrease_blocked=True`, protection prohibits reducing
the campaign, so `effective_decrease_limit = Decimal("0.00")` — a deliberate,
computed effective constraint, never missing data, regardless of whether
`raw_decrease_limit` was positive, zero, or an extreme valid monetary value. The
raw Stage 17 decrease limit remains preserved separately and unaltered in
`CampaignRawDecreaseLimit`.

**Unprotected mapping.** When `decrease_blocked=False`, protection itself adds no
further restriction — `effective_decrease_limit = raw_decrease_limit`, returned
unchanged. This does not mean that a decrease should occur.

**Zero and `None` behaviour.** `Decimal("0.00")` is always a legitimate effective
result, whether it originates from the protected branch or from an already-zero raw
decrease limit passing through unchanged (Stage 18 does not distinguish or record
which cause produced it — that distinction remains independently visible via the
separately-held Stage 14/17 results). Neither input field is optional, and the
output is never `None` — no fallback value is ever substituted.

**No arithmetic is performed.** The unprotected branch returns the selected
`Decimal` operand unchanged; the protected branch constructs the literal
`Decimal("0.00")`. No subtraction, multiplication, division, quantisation, or
rounding occurs, and no `Decimal` context is used.

**Raw and protection facts remain separate.** `CampaignEffectiveDecreaseLimit` does
not repeat `raw_decrease_limit` or `decrease_blocked` as fields — a caller retains
traceability by holding `CampaignProtectionConstraint` (Stage 14),
`CampaignRawDecreaseLimit` (Stage 17), and `CampaignEffectiveDecreaseLimit` (Stage
18) as three separate, independently inspectable result objects.

**No effective increase is produced.** Stage 18 does not create
`CampaignEffectiveIncreaseLimit`, an `effective_increase_limit` field, or any
combined effective-directional result. No approved constraint remains to transform
Stage 16's raw increase limit, and protection has no approved increase-side effect
— `CampaignRawIncreaseLimit` remains the authoritative increase-side constraint
unless a later approved rule changes it.

## Campaign Action Availability Fields (`src/availability.py`)

Produced by `resolve_campaign_action_availability(campaign: CampaignInput, tracking:
CampaignTrackingAssessment, raw_increase: CampaignRawIncreaseLimit,
effective_decrease: CampaignEffectiveDecreaseLimit) -> CampaignActionAvailability`,
one result per already-validated `CampaignInput` paired with its already-calculated
Stage 8, Stage 16, and Stage 18 results. `CampaignActionAvailability` is frozen
(immutable) and rejects unknown fields (`extra="forbid"`).

**Definition of availability.** An action is *available* when it is not prevented by
campaign status, tracking-based assessability, or the relevant approved monetary
capacity. Availability does **not** mean the action is advisable — positive capacity
establishes only that a direction is mechanically possible, never a recommendation.
This is a **narrow mechanical gate only** — it is not suitability, a recommendation,
`HOLD`, a score, a priority, a ranking, a reason code, or an allocation.

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `campaign.campaign_id`, after confirming it matches `tracking.campaign_id`, `raw_increase.campaign_id`, and `effective_decrease.campaign_id`. |
| `increase_available` | boolean | `True` only when the campaign is `Active`, `tracking.is_assessable` is `True`, and `raw_increase_limit > Decimal("0.00")`. |
| `maintain_available` | boolean | `True` only when the campaign is `Active`. Unaffected by tracking assessability or either directional monetary capacity. |
| `reduce_available` | boolean | `True` only when the campaign is `Active`, `tracking.is_assessable` is `True`, and `effective_decrease_limit > Decimal("0.00")`. |

**Active/Paused policy.** For `CampaignStatus.PAUSED`, all three fields are `False`
— `increase_available=False`, `maintain_available=False`, `reduce_available=False`.
A Paused campaign is never omitted, never raises an error, and never results in
`HOLD` or a reason code being produced — it simply receives the same
`CampaignActionAvailability` shape as every other campaign, with all three flags
`False`. `MAINTAIN` is described as "not available through the active
budget-review process" for a Paused campaign, not as an error condition.

**Assessability policy.** For an `Active` campaign with `tracking.is_assessable ==
False`, `increase_available=False` and `reduce_available=False`, while
`maintain_available` remains `True` — leaving the budget unchanged requires no
confidence in the underlying data, and is the natural safe default when tracking
cannot be trusted. `TrackingStatus.WARNING` remains assessable because Stage 8
already returns `is_assessable=True` for it; Stage 19 does not re-derive this — it
consumes `is_assessable` only, never `tracking_status` itself.

**Directional-capacity policy.** `raw_increase_limit > Decimal("0.00")` means
positive increase capacity exists; `raw_increase_limit == Decimal("0.00")` means
`INCREASE` is unavailable. `effective_decrease_limit > Decimal("0.00")` means
positive decrease capacity exists; `effective_decrease_limit == Decimal("0.00")`
means `REDUCE` is unavailable. Positive capacity is necessary for directional
availability but is never a recommendation. Upstream invariants make negative
values structurally impossible; no correction, clamping, or fallback logic is
present.

**`MAINTAIN` meaning.** A concrete decision to leave the budget unchanged — for an
`Active` campaign it remains mechanically available regardless of tracking
assessability or directional monetary capacity, since "doing nothing" requires
neither.

**`HOLD` exclusion.** `hold_available` does not exist anywhere on this model.
`HOLD` is excluded entirely from Stage 19 — it is a later review/deferral or
recommendation outcome whose exact trigger remains undecided, not a capacity-gated
action in the same sense as `INCREASE`/`MAINTAIN`/`REDUCE`.

**Separation from suitability and recommendation.** `PerformanceBand`,
`TrendDirection`, `Confidence`, `PacingStatus`, and `BusinessPriority` are never
read — these are suitability/scoring signals, not availability inputs. No
`RecommendationAction` or `ReasonCode` is produced. `CampaignActionAvailability` is
a separate, independent result model from every Stage 8–18 result — none is
modified by this addition, and traceability to the underlying facts (tracking
assessability, raw increase limit, effective decrease limit) is preserved by
holding those result objects separately, not by repeating their fields here.

## Campaign Action Suitability Fields (`src/suitability.py`)

Produced by `resolve_campaign_action_suitability(performance:
CampaignPerformanceClass, trend: CampaignTrendClass, availability:
CampaignActionAvailability) -> CampaignActionSuitability`, one result per
already-calculated Stage 5, Stage 6, and Stage 19 result triple.
`CampaignActionSuitability` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`).

**Definition of suitability.** Availability answers "can this action be taken
mechanically and operationally?" Suitability answers "do the approved
performance and trend classifications provide a clear directional signal
supporting this available action?" Suitability does **not** mean recommendation
— a `SUITABLE` action is not automatically selected, a `NEUTRAL` action is not
automatically rejected, and an `UNSUITABLE` action is not a final prohibition.

### `Suitability` (enum)

| Member | Value | Meaning |
|--------|-------|---------|
| `SUITABLE` | `"Suitable"` | Performance and trend clearly agree in favour of this direction. |
| `NEUTRAL` | `"Neutral"` | Performance and trend do not clearly agree, or the diagonal case does not favour this direction. |
| `UNSUITABLE` | `"Unsuitable"` | Performance and trend clearly agree against this direction. |
| `NOT_APPLICABLE` | `"Not Applicable"` | The action is unavailable under Stage 19 and therefore receives no suitability judgement. |

`Suitability` is purely categorical — it carries no numeric value, no ordering,
and no `SUITABLE > NEUTRAL`-style comparison is defined or implied.

### `CampaignActionSuitability`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `performance.campaign_id`, after confirming it matches `trend.campaign_id` and `availability.campaign_id`. |
| `increase_suitability` | `Suitability` | Base-table result for `PerformanceBand`/`TrendDirection`, or `NOT_APPLICABLE` if `availability.increase_available` is `False`. |
| `maintain_suitability` | `Suitability` | Base-table result, or `NOT_APPLICABLE` if `availability.maintain_available` is `False`. |
| `reduce_suitability` | `Suitability` | Base-table result, or `NOT_APPLICABLE` if `availability.reduce_available` is `False`. |

**Complete 3×3 base rule table** (a conservative, diagonal-only policy — before
applying the availability override):

| PerformanceBand \ TrendDirection | IMPROVING | STABLE | DECLINING |
|---|---|---|---|
| `ABOVE_TARGET` | increase=`SUITABLE`, maintain=`NEUTRAL`, reduce=`UNSUITABLE` | increase=`NEUTRAL`, maintain=`NEUTRAL`, reduce=`NEUTRAL` | increase=`NEUTRAL`, maintain=`NEUTRAL`, reduce=`NEUTRAL` |
| `ON_TARGET` | increase=`NEUTRAL`, maintain=`NEUTRAL`, reduce=`NEUTRAL` | increase=`NEUTRAL`, maintain=`SUITABLE`, reduce=`NEUTRAL` | increase=`NEUTRAL`, maintain=`NEUTRAL`, reduce=`NEUTRAL` |
| `BELOW_TARGET` | increase=`NEUTRAL`, maintain=`NEUTRAL`, reduce=`NEUTRAL` | increase=`NEUTRAL`, maintain=`NEUTRAL`, reduce=`NEUTRAL` | increase=`UNSUITABLE`, maintain=`NEUTRAL`, reduce=`SUITABLE` |

Only the three diagonal cells (`ABOVE_TARGET`+`IMPROVING`, `ON_TARGET`+`STABLE`,
`BELOW_TARGET`+`DECLINING`) — where performance and trend clearly agree —
produce a directional `SUITABLE`/`UNSUITABLE` result. All six conflicting or
mixed combinations resolve to `NEUTRAL` for every direction. This deliberately
avoids deciding whether performance or trend has precedence when they disagree.

**Availability override.** After the base-table lookup, availability is applied
independently per direction: if `availability.increase_available` is `False`,
`increase_suitability = Suitability.NOT_APPLICABLE`, overriding whatever the
base table would otherwise say — the same rule applies independently to
`maintain_suitability`/`maintain_available` and
`reduce_suitability`/`reduce_available`. `NOT_APPLICABLE` is never represented
as `None`, a numeric zero, or `UNSUITABLE`.

**Exclusions.** `Confidence`, `PacingStatus`, and `BusinessPriority` are never
read — these remain deferred suitability/scoring inputs. `CampaignTrackingAssessment`
is never accepted — Stage 19's already-resolved availability is consumed
directly instead, so an Active-but-unassessable campaign's `MAINTAIN` still
receives its base-table result (since `maintain_available` is unaffected by
assessability) while `INCREASE`/`REDUCE` become `NOT_APPLICABLE` purely because
Stage 19 already marked them unavailable. Stage 20 never decides `MAINTAIN`
versus `HOLD`. No `RecommendationAction`, `HOLD`, `ReasonCode`, numeric score,
ranking, or allocation field exists anywhere on this result.

## Campaign Recommendation Fields (`src/recommendation.py`)

Produced by `resolve_campaign_recommendation_action(campaign: CampaignInput,
suitability: CampaignActionSuitability, tracking: CampaignTrackingAssessment)
-> CampaignRecommendation`, one result per already-validated `CampaignInput`
paired with its already-calculated Stage 20 and Stage 8 results.
`CampaignRecommendation` is frozen (immutable) and rejects unknown fields
(`extra="forbid"`).

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `campaign.campaign_id`, after confirming it matches `suitability.campaign_id` and `tracking.campaign_id`. |
| `recommendation_action` | `RecommendationAction` | Exactly one of `INCREASE`, `MAINTAIN`, `REDUCE`, or `HOLD`, selected by the ordered policy below. |

**HOLD versus MAINTAIN.** `MAINTAIN` means the campaign was eligible for
automated assessment, no available action had a uniquely stronger directional
suitability, and keeping the budget unchanged is the selected recommendation
— an *assessed* no-change decision. `HOLD` means the engine must not make an
automated directional budget recommendation for this review — because the
campaign is paused, its tracking is unassessable, its suitability input is
ambiguous, or no valid fallback action is available. `HOLD` is a
review/deferral outcome; `MAINTAIN` is an assessed no-change recommendation.
Neither changes the actual budget.

**Complete ordered action-selection policy**, applied after campaign-ID
validation:

1. **Paused override.** `campaign.status is CampaignStatus.PAUSED` →
   `HOLD`, overriding all suitability values. Read directly from
   `CampaignInput.status`.
2. **Tracking-assessability override.** `not tracking.is_assessable` →
   `HOLD`, overriding all suitability values. `TrackingStatus.WARNING`
   remains assessable (inherited unchanged from Stage 8).
3. **Unique-`SUITABLE` selection.** Exactly one of
   `increase_suitability`/`maintain_suitability`/`reduce_suitability` equals
   `Suitability.SUITABLE` → select the corresponding action.
4. **Multiple-`SUITABLE` ambiguity.** More than one field equals `SUITABLE`
   → `HOLD`. No fixed precedence, no first-field selection, no `MAINTAIN`
   default, and no error — this cannot arise through the approved Stage 20
   production table, but a directly constructed `CampaignActionSuitability`
   could contain it.
5. **Conservative `MAINTAIN` fallback.** No field is `SUITABLE`, and
   `maintain_suitability is Suitability.NEUTRAL` → `MAINTAIN`.
   `INCREASE`'s and `REDUCE`'s own values are irrelevant to this fallback.
6. **Final `HOLD` fallback.** No field is `SUITABLE`, and
   `maintain_suitability` is `UNSUITABLE` or `NOT_APPLICABLE` → `HOLD`.

A `Suitability.NOT_APPLICABLE` value is never selected as an action — it
participates only by preventing that direction from being uniquely
`SUITABLE`.

**Explicit status ownership.** Stage 21 accepts `CampaignInput` directly for
campaign status — Paused status is never inferred from suitability shape;
`CampaignActionAvailability` is not accepted separately, since Stage 20 has
already applied availability through `NOT_APPLICABLE`.

**Exclusions.** No `ReasonCode`, monetary amount, score, rank, priority,
`Confidence`, `PacingStatus`, or `BusinessPriority` is read or produced
anywhere. `RecommendationAction` selection here is a **provisional
direction only** — not a final allocated movement, not a monetary amount,
and not a cross-campaign judgement.

## Derived Fields

> Pending a later Sprint 1 stage (combined confidence/tracking/pacing assessment,
> `Confidence.NOT_ASSESSABLE` ownership, `ReasonCode`, numeric prioritisation
> scoring, ranking, allocation).

## Export Fields

> Pending a later Sprint 1 stage (`src/exports.py`).
