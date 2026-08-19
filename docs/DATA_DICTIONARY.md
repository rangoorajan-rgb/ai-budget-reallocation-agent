# Data Dictionary

> Sprint 3, Development Stage 28 (adds the deterministic-only Streamlit
> review shell, `app.py`, consuming Sprint 2's Stage 27 final deterministic
> responsibility — end-to-end pipeline orchestration and portfolio
> reporting — `BudgetReallocationReviewResult`/
> `CampaignBudgetRecommendationResult` — from `src/pipeline.py`, which
> completed the master plan's Sprint 2 "Deterministic Core Engine" goal
> — to the Stage 1 enumerations, numerical constants, core input models,
> CSV schema, Stage 2 validation reporting, Stage 3 metric facts, Stage 4
> pacing facts, Stage 5 performance classification, Stage 6 trend
> classification, Stage 7 conversion-volume confidence classification,
> Stage 8 tracking-based assessability, Stage 9 pacing interpretation,
> Stage 10 static budget-bound facts, Stage 11 applicable-change-percentage
> resolution, Stage 12 raw percentage-based monetary movement cap, Stage
> 13 test-floor distance, Stage 14 protection constraint, Stage 15
> test-aware static decrease room, Stage 16 raw increase limit, Stage 17
> raw decrease limit, Stage 18 protection-adjusted effective decrease
> limit, Stage 19 campaign action availability, Stage 20 campaign action
> suitability, Stage 21 recommendation-action selection, Stage 22
> recommendation reasons, Stage 23 single-campaign reallocation priority
> scoring, Stage 24 cross-campaign reallocation ranking, Stage 25
> cross-campaign budget allocation, and Stage 26 independent budget
> conservation verification). Combined assessment,
> `Confidence.NOT_ASSESSABLE` ownership, the remaining `ReasonCode`
> trigger conditions, and other derived/decision fields, plus export
> fields, are pending later stages. Streamlit/UI, Gemini explanation,
> human approval, audit persistence, exports, and Sprint 4 hardening
> remain pending separate, later sprints.

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

## Campaign Recommendation Reason Fields (`src/reasons.py`)

Produced by `resolve_campaign_recommendation_reason(recommendation:
CampaignRecommendation, campaign: CampaignInput, suitability:
CampaignActionSuitability, tracking: CampaignTrackingAssessment,
performance: CampaignPerformanceClass, trend: CampaignTrendClass) ->
CampaignRecommendationReason`, one result per already-selected Stage 21
recommendation paired with the exact upstream facts Stage 21 itself
consumed or could have consumed. `CampaignRecommendationReason` is frozen
(immutable) and rejects unknown fields (`extra="forbid"`).

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `recommendation.campaign_id`, after confirming it matches `campaign.campaign_id`, `suitability.campaign_id`, `tracking.campaign_id`, `performance.campaign_id`, and `trend.campaign_id`. |
| `reason_codes` | `tuple[ReasonCode, ...]` | A non-empty, ordered, deduplicated set of `ReasonCode` explaining only the facts that causally participated in Stage 21's decision. |

**Explains, does not select.** Stage 22 explains an already-selected
`RecommendationAction`; it does not select or change it, and never calls
`resolve_campaign_recommendation_action` or any other Stage 1–21
production function.

**HOLD precedence**, mirroring Stage 21's exact rule order:

1. `campaign.status is CampaignStatus.PAUSED` → `(PAUSED_CAMPAIGN,)`.
   Remains the sole reason even when tracking is simultaneously
   unassessable — Stage 21's own short-circuit logic never reaches the
   assessability check once Paused has already resolved `HOLD`.
2. Otherwise, `not tracking.is_assessable` → `(TRACKING_UNRELIABLE,)`.
3. Otherwise (multiple-`SUITABLE` ambiguity or no valid `MAINTAIN`
   fallback — the only two remaining ways Stage 21 can produce `HOLD`) →
   `(HELD_FOR_MANUAL_REVIEW,)`. Never used for a non-HOLD action.

**INCREASE/MAINTAIN/REDUCE mapping.** Two fixed, immutable lookup tables
applied to `performance.performance_band`/`trend.trend_direction` — the
same pair Stage 20 used to determine suitability:

| `PerformanceBand` | Reason |
|---|---|
| `ABOVE_TARGET` | `ABOVE_TARGET_STRONG` |
| `ON_TARGET` | `NEAR_TARGET` |
| `BELOW_TARGET` | *(no performance reason — no approved severity classification exists)* |

| `TrendDirection` | Reason |
|---|---|
| `IMPROVING` | `RECENT_TREND_IMPROVING` |
| `STABLE` | `RECENT_TREND_STABLE` |
| `DECLINING` | `RECENT_TREND_DECLINING` |

The performance reason (when available) precedes the trend reason. This
reproduces exactly the seven approved `MAINTAIN` cells (`ABOVE_TARGET`+`STABLE`,
`ABOVE_TARGET`+`DECLINING`, `ON_TARGET`+`IMPROVING`, `ON_TARGET`+`STABLE`,
`ON_TARGET`+`DECLINING`, `BELOW_TARGET`+`IMPROVING`, `BELOW_TARGET`+`STABLE`)
and additionally, consistently, the two `MAINTAIN` outcomes reachable only
when Stage 19 availability blocks an otherwise diagonal-`SUITABLE`
direction — the identical, already-approved mapping applied unchanged, not
a new invented rule.

**Exclusions.** `TRACKING_WARNING`, `INSUFFICIENT_CONVERSION_VOLUME`, and
`PROTECTED_FROM_REDUCTION` are never emitted — none causally participates
in Stage 21's decision. `BELOW_TARGET_MODERATE`, `BELOW_TARGET_SEVERE`,
and `STRONG_LONG_TERM_RECENT_DECLINE` are never emitted — no approved
severity classification exists; this is an intentional, documented
limitation, not an invitation to invent a threshold.
`CAMPAIGN_CAP_REACHED`, `CAMPAIGN_FLOOR_REACHED`,
`TEST_BUDGET_FLOOR_APPLIED`, and `MAX_CHANGE_LIMIT_APPLIED` are never
emitted — no Stage 15–18 result preserves which constraint operand was
actually binding. `NO_ELIGIBLE_RECIPIENT` and `ACCOUNT_RESERVE_REQUIRED`
are never emitted — both are cross-campaign allocation-domain outcomes.
`recommendation_action` is never duplicated on this result — callers
retain the separately-resolved `CampaignRecommendation`.

## Campaign Reallocation Priority Score Fields (`src/scoring.py`)

Produced by `calculate_campaign_reallocation_priority_score(recommendation:
CampaignRecommendation, campaign: CampaignInput, confidence:
CampaignConfidenceClass) -> CampaignReallocationPriorityScore`, one result
per already-selected Stage 21 recommendation paired with the campaign's
`business_priority` and Stage 7 confidence classification.
`CampaignReallocationPriorityScore` is frozen (immutable) and rejects
unknown fields (`extra="forbid"`).

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | Copied from `recommendation.campaign_id`, after confirming it matches `campaign.campaign_id` and `confidence.campaign_id`. |
| `confidence_component` | int (`0..100`) | Evidence-reliability contribution — `0` for a non-directional action or a `NOT_ASSESSABLE` directional action; otherwise the fixed `Confidence` mapping value. |
| `business_priority_component` | int (`0..100`) | Direction-aware business-priority contribution — `0` under the same conditions; otherwise the fixed, direction-specific `BusinessPriority` mapping value. |
| `reallocation_priority_score` | int (`0..100`) | `confidence_component + business_priority_component`, always one of `{0, 20, 40, 60, 80, 100}`. Model-validated to equal the sum of the two components. |

**Business meaning.** The score represents the relative priority with
which an already-selected *directional* recommendation should be
considered during a later cross-campaign ranking stage. A higher score
means a stronger candidate **only within the same direction** —
`INCREASE` scores must later be compared only with other `INCREASE`
scores, and `REDUCE` scores only with other `REDUCE` scores. The score
must never be used to compare an `INCREASE` directly against a `REDUCE`;
direction remains solely and authoritatively carried by
`CampaignRecommendation.recommendation_action`, never re-encoded through
sign or magnitude here. Stage 23 never modifies the recommendation it
scores.

**Non-directional actions.** `HOLD` and `MAINTAIN` unconditionally produce
an all-zero result — not because either action is invalid, but because
neither proposes a directional budget movement for the later ranking
stage to prioritise. The confidence and business-priority mappings are
never inspected once a non-directional action is identified.

**`Confidence.NOT_ASSESSABLE` override.** An `INCREASE` or `REDUCE`
recommendation paired with `Confidence.NOT_ASSESSABLE` also produces an
all-zero result — a scoring-only override that neither changes the
existing recommendation nor raises an error.

**Exact mappings** (fixed, immutable, never derived from enum declaration
order):

| `Confidence` | `confidence_component` |
|---|---|
| `HIGH` | 60 |
| `MEDIUM` | 40 |
| `LOW` | 20 |
| `NOT_ASSESSABLE` | *(handled by the override above)* |

| `BusinessPriority` | `INCREASE` component | `REDUCE` component |
|---|---|---|
| `HIGH` | 40 | 0 |
| `MEDIUM` | 20 | 20 |
| `STANDARD` | 0 | 40 |

`INCREASE` favours higher-priority campaigns as recipients of additional
budget; `REDUCE` favours lower-priority campaigns as possible budget
donors — the same `BusinessPriority` value contributes opposite
components depending on direction, by design.

**Not double-counted.** `PerformanceBand` and `TrendDirection` already
caused Stage 20's suitability judgement and Stage 21's recommendation
selection — scoring them again would double-count the same action
evidence, so neither is read. `CampaignActionAvailability`,
`CampaignActionSuitability`, and `CampaignTrackingAssessment` are already
fully consumed downstream by Stage 21. `CampaignRecommendationReason`/
`ReasonCode` explain the decision and must never become hidden numeric
weights. `PacingStatus` has no approved direction-specific prioritisation
policy. Raw campaign metrics, `weighted_performance_ratio`, `trend_delta`,
monetary constraint results, protection, test-campaign status, and
tracking status are all excluded — they answer how much money can move or
whether an action is mechanically available, not how strongly a campaign
should be prioritised for a direction it already qualifies for.

**Not this stage's responsibility.** No sorting, normalisation, ranking,
allocation, conservation, monetary calculation, or AI explanation occurs
here. Tie-breaking among equal scores is deferred to the later
cross-campaign ranking stage. Stage 23 is completely single-campaign — no
other campaign's data is read, compared, or required.

**Numeric policy.** Plain Python `int` throughout — never `float` or
`Decimal`. The score is dimensionless; no rounding, quantisation, or
ambient `Decimal` context applies. No negative value and no value greater
than `100` is ever produced. No multiplication or division is performed.

## Campaign Reallocation Ranking Fields (`src/ranking.py`)

Produced by `rank_campaign_reallocation_priorities(recommendations:
tuple[CampaignRecommendation, ...], scores:
tuple[CampaignReallocationPriorityScore, ...]) ->
CampaignReallocationRanking`, the first genuinely cross-campaign
responsibility in this repository — every field above this section
describes a single-campaign result; this section describes a
whole-portfolio result. `RankedCampaignPriority` and
`CampaignReallocationRanking` are both frozen (immutable) and reject
unknown fields (`extra="forbid"`).

### `RankedCampaignPriority`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | The ranked campaign's identity. |
| `rank` | int (`>= 1`) | Dense rank within this campaign's own recommendation direction. Direction itself is never carried on this record — it is represented structurally by membership in `increase_rankings` or `reduce_rankings`. |
| `reallocation_priority_score` | int (`1..100`) | The unchanged Stage 23 `reallocation_priority_score` — never recalculated, never normalised. |

### `CampaignReallocationRanking`

| Field | Type | Meaning |
|-------|------|---------|
| `increase_rankings` | `tuple[RankedCampaignPriority, ...]` | Dense-ranked `INCREASE` candidates, score descending. May be empty. |
| `reduce_rankings` | `tuple[RankedCampaignPriority, ...]` | Dense-ranked `REDUCE` candidates, score descending. May be empty. |

**Direction separation.** `increase_rankings` and `reduce_rankings` are
completely independent — the first-ranked `INCREASE` campaign and the
first-ranked `REDUCE` campaign may both hold rank `1`, and their ranks
carry no relationship to one another. No global combined rank exists
anywhere on this result, and no campaign ever appears in both tuples.

**Eligible population.** Only a directional recommendation
(`INCREASE`/`REDUCE`) paired with a strictly positive
`reallocation_priority_score` is ranked. `MAINTAIN` and `HOLD` are always
excluded, regardless of score. A directional recommendation paired with a
zero score — reachable through Stage 23's `Confidence.NOT_ASSESSABLE`
override — is also excluded, because Stage 23 has already determined it
has no reliable ranking priority. Exclusion produces no output record, no
reason code, and no error, and never changes the excluded campaign's
`CampaignRecommendation` or `CampaignReallocationPriorityScore`.

**Dense ranking.** Within each direction, candidates are sorted by
`reallocation_priority_score` descending; equal scores share the same
rank with no gap in the next rank (`100, 80, 80, 60` → `1, 2, 2, 3`; all
equal → `1, 1, 1`). `campaign_id` ascending governs only the
serialization order of tied-score records — it never influences the
assigned rank and is never used as a business-priority key. No component
already reflected in the Stage 23 total (`confidence_component`,
`business_priority_component`), and no other field (input position,
platform, budget, performance, trend, pacing, monetary capacity), is ever
used as a sort key.

**No normalisation.** Stage 23's score is used completely unchanged — no
percentage, percentile, portfolio-relative transform, min-max
normalisation, z-score, or direction-relative transformation is ever
computed. A single candidate scoring `20` remains `20`.

**Matching, not positional pairing.** `recommendations` and `scores` are
matched exclusively by `campaign_id` value equality — never by tuple
position, and `zip` is never used. Both input tuples' `campaign_id`
values must each be unique, and the two tuples' `campaign_id` sets must
be exactly equal; violations raise `ValueError` before any filtering,
sorting, or rank assignment. Two empty input tuples are valid and produce
an empty (not erroneous) result.

**Determinism.** Neither input tuple nor any contained
`CampaignRecommendation`/`CampaignReallocationPriorityScore` is ever
mutated or sorted in place. Supplying the same logical records in a
different input order always produces identical serialized output.

**Monetary and allocation boundary.** No monetary constraint result
(`CampaignRawIncreaseLimit`, `CampaignRawDecreaseLimit`,
`CampaignEffectiveDecreaseLimit`, static budget room, test-floor room,
percentage movement cap), binding-constraint identity, monetary
recommendation amount, donor/recipient matching, partial allocation, or
conservation check is ever performed here. Stage 24 hands a later
allocation stage only ranked campaign IDs, their direction-scoped dense
ranks, and their unchanged Stage 23 scores.

## Campaign Reallocation Allocation Fields (`src/allocation.py`)

Produced by `allocate_campaign_reallocation(ranking:
CampaignReallocationRanking, increase_limits:
tuple[CampaignRawIncreaseLimit, ...], decrease_limits:
tuple[CampaignEffectiveDecreaseLimit, ...]) ->
CampaignReallocationAllocation`. No separate recommendation-amount stage
exists — allocation consumes Stage 24's rankings and Stage 16/18's
capacities directly. `CampaignAllocatedAmount` and
`CampaignReallocationAllocation` are both frozen (immutable) and reject
unknown fields (`extra="forbid"`).

### `CampaignAllocatedAmount`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id` | string | The campaign's identity. |
| `allocated_amount` | `Currency`, `>= 0` | The campaign's actual allocated movement — always unsigned. Direction is never carried here; it is represented structurally by tuple membership. |

### `CampaignReallocationAllocation`

| Field | Type | Meaning |
|-------|------|---------|
| `increase_allocations` | `tuple[CampaignAllocatedAmount, ...]` | One record per campaign in Stage 24's `increase_rankings`, including `Decimal("0.00")`. May be empty. |
| `decrease_allocations` | `tuple[CampaignAllocatedAmount, ...]` | One record per campaign in Stage 24's `reduce_rankings`, including `Decimal("0.00")`. May be empty. |

**Capacity is a ceiling, not a guarantee.** No campaign automatically
receives or donates its full `raw_increase_limit`/`effective_decrease_limit`
merely because it exists or is ranked first.

**Reserve is excluded entirely.** `ReviewSetup.initial_account_reserve` is
never accepted as an input, read, consumed, reduced, or returned — its
authoritative meaning (*"Budget held back from reallocation"*) treats it
as protected and unavailable for funding increases.
`ReasonCode.ACCOUNT_RESERVE_REQUIRED` remains unassigned. The only funding
source is the sum of `effective_decrease_limit` across Stage 24's
`reduce_rankings` — unranked decrease-limit records never contribute.

**Two-phase strict dense-rank waterfall.** Phase 1 funds
`increase_rankings` by ascending dense rank against total available
supply — a tier is fully funded if remaining supply covers it, or the
first tier supply cannot fully cover is split proportionally to capacity
(largest-remainder method, below), after which every lower rank receives
`Decimal("0.00")`. Phase 2 draws the exact Phase 1 total from
`reduce_rankings` by the identical waterfall — always exhausting exactly,
since Phase 1's total can never exceed total available supply. A
partially funded tier, on either side, is a valid, non-error outcome, as
are both insufficient and excess supply.

**Largest-remainder currency method.** Within a partially funded tied
tier, each campaign's exact proportional share is floored to
`CURRENCY_QUANTUM` via `ROUND_DOWN`; the shortfall (a whole number of
pennies) is distributed one at a time, in order of fractional remainder
descending, never pushing any campaign above its own capacity. If every
capacity in a tier is zero, every campaign receives `Decimal("0.00")`
without division.

**Narrow campaign-ID exception.** `campaign_id` ascending breaks only an
*exact* tie between two campaigns' fractional remainders during
indivisible-penny apportionment — nothing else. It never orders
recipients against donors, never influences which tier is funded, and is
never an ordinary financial preference, consistent with Stage 24's
"campaign ID is a serialization aid only" principle.

**Matching, not positional pairing.** `increase_limits`/`decrease_limits`
are matched by `campaign_id` value only — never `zip`. Every ID must be
unique within each limit collection; a ranked campaign missing its
direction-appropriate limit is an error. Extra, unranked limit records are
legitimate and ignored. Stage 24's own guarantees are trusted, never
recalculated.

**Numeric policy.** `Decimal` exclusively, never `float`. Every arithmetic
operation runs inside an explicitly-scoped `localcontext`, immune to
ambient global context mutation. `sum(increase_allocations) ==
sum(decrease_allocations)` always holds — constructed, not merely
checked.

**Not this stage's responsibility.** No `ReasonCode` is ever emitted, no
final campaign budget is calculated (`CampaignInput.current_budget` is
never read), and conservation verification is a separate, later,
independent stage that must never repair or mutate allocation's result.

## Campaign Reallocation Conservation Fields (`src/conservation.py`)

Produced by `verify_campaign_reallocation_conservation(allocation:
CampaignReallocationAllocation) -> CampaignReallocationConservation`.
Independently re-verifies the monetary invariant Stage 25's allocation is
already constructed to satisfy — it never reruns allocation and never
repairs an imbalance. `CampaignReallocationConservation` is frozen
(immutable) and rejects unknown fields (`extra="forbid"`).

| Field | Type | Meaning |
|-------|------|---------|
| `total_increase_allocated` | `Currency`, `>= 0` | Independently recomputed sum of `allocated_amount` across `allocation.increase_allocations`. |
| `total_decrease_allocated` | `Currency`, `>= 0` | Independently recomputed sum of `allocated_amount` across `allocation.decrease_allocations`. |
| `net_change` | `Decimal` (may be negative) | `total_increase_allocated - total_decrease_allocated`. Positive means increases exceed decreases; negative means decreases exceed increases; exactly `Decimal("0.00")` means conserved. |
| `is_conserved` | `bool` | `True` only when `net_change` is exactly `Decimal("0.00")`. |

**Model-level consistency.** A validator rejects any directly-constructed
instance where `net_change != total_increase_allocated -
total_decrease_allocated`, or where `is_conserved` does not equal
`net_change == Decimal("0.00")` — the model cannot represent an
internally contradictory conservation fact. The production function
itself always constructs a consistent result and never triggers this
validator's failure path merely because an allocation is imbalanced.

**Exact equality, no tolerance.** Every value is an exact,
currency-quantised `Decimal`. An imbalance of exactly `Decimal("0.01")`
is reported as `is_conserved=False` — no tolerance, epsilon, or rounded
comparison is ever used, since any tolerance would only conceal a genuine
implementation defect.

**Always returns a result.** An imbalanced allocation is reported as
`is_conserved=False` with its exact signed `net_change` — the function
never raises merely because totals differ, and never repairs, rebalances,
or mutates the allocation.

**Pure monetary sum check.** `campaign_id` is never read from any
allocation record. Every `allocated_amount` present is summed,
indifferent to duplicate IDs within one direction, the same ID appearing
in both directions, or repeated zero-valued records — Stage 24 and
Stage 25 already own campaign-identity structural guarantees. This stage
never duplicates Stage 25's donor/recipient matching, rank waterfall,
tied-tier allocation, or residual-penny apportionment.

**A conserved zero allocation does not mean any campaign received
funding** — an all-zero allocation is trivially conserved, reporting a
true fact about balance, not a claim that money moved.

**Not this stage's responsibility.** No `ReasonCode` is ever emitted
(`ACCOUNT_RESERVE_REQUIRED`/`NO_ELIGIBLE_RECIPIENT` remain unassigned);
reserve, final campaign budgets, ranking order, and recommendation/reason
context are all excluded, exactly as they were excluded from Stage 25.
This stage exposes only its four fields to a later deterministic
integration/reporting stage — it does not decide what that later stage
does with an unconserved result.

**Decimal and context policy.** `Decimal` exclusively, never `float`.
Every sum and the final subtraction run inside an explicitly-scoped
`localcontext`, with precision derived from the actual operands' digit
counts and record count — never a blindly assumed fixed value — so the
ambient global context can never affect the result and local-context
rounding can never make two unequal totals compare as equal.

## Budget Reallocation Review Result Fields (`src/pipeline.py`)

Produced by `run_budget_reallocation_review(review: ReviewSetup,
campaigns: tuple[CampaignInput, ...]) -> BudgetReallocationReviewResult`
— the final deterministic responsibility, orchestrating every
already-approved Stage 3–26 production function into one portfolio-level
result. Completes the master plan's Sprint 2 "Deterministic Core Engine"
goal. `CampaignBudgetRecommendationResult` and
`BudgetReallocationReviewResult` are both frozen (immutable) and reject
unknown fields (`extra="forbid"`).

### `CampaignBudgetRecommendationResult`

| Field | Type | Meaning |
|-------|------|---------|
| `campaign_id`, `campaign_name`, `platform` | — | Copied unchanged from the campaign's `CampaignInput`. |
| `current_budget` | `Currency` | Copied unchanged from `CampaignInput.current_budget`. |
| `recommendation_action` | `RecommendationAction` | Stage 21's selected action, passed through unchanged — never rewritten because allocation is zero. |
| `allocated_amount` | `Currency`, `>= 0` | Stage 25's exact allocated amount for a matched directional recommendation; exactly `Decimal("0.00")` for `HOLD`/`MAINTAIN` or an unmatched directional recommendation. Always unsigned — direction is carried only by `recommendation_action`. |
| `recommended_budget` | `Currency`, `>= 0` | `current_budget ± allocated_amount` per the exact formula below; unchanged for `MAINTAIN`/`HOLD`. |
| `reason_codes` | `tuple[ReasonCode, ...]` | Stage 22's ordered tuple, passed through unchanged — never recomputed, never appended to. |
| `performance_band`, `trend_direction`, `confidence`, `pacing_status` | — | Stage 5/6/7/9's classifications, passed through for grounding and display. |
| `reallocation_priority_score` | `int`, `0..100` | Stage 23's score, always present (including `0` for non-directional actions). |
| `rank` | `int \| None`, `>= 1` when present | Stage 24's direction-specific dense rank; `None` for `HOLD`/`MAINTAIN` and for a directional recommendation excluded from ranking because its score was zero. Never a global cross-direction rank. |

### `BudgetReallocationReviewResult`

| Field | Type | Meaning |
|-------|------|---------|
| `review_id` | `str` | Copied unchanged from `ReviewSetup.review_id`. |
| `campaign_results` | `tuple[CampaignBudgetRecommendationResult, ...]` | One record per input campaign, in the original `campaigns` input order — never re-sorted by ID, score, rank, or action. |
| `total_current_budget` | `Currency`, `>= 0` | Independently summed `current_budget` across all campaign results. |
| `total_recommended_budget` | `Currency`, `>= 0` | Independently summed `recommended_budget` across all campaign results. |
| `conservation` | `CampaignReallocationConservation` | Stage 26's result, embedded unchanged and always present — never hidden, gated, or omitted based on `is_conserved`. |

**Validation stays entirely outside this stage.** `ReviewSetup` and every
`CampaignInput` must already be valid; this stage never reads a CSV,
never calls `validate_campaign_csv`, never returns validation issues, and
never re-checks campaign-ID uniqueness (already Stage 2's responsibility).
An empty campaign tuple is valid and produces an empty portfolio result.

**Pure orchestration — no formula is duplicated.** Every fact is produced
by calling the real Stage 3–26 function that owns it; the only new
arithmetic is the final-budget formula:
```
INCREASE → current_budget + allocated_amount
REDUCE   → current_budget - allocated_amount
MAINTAIN → current_budget
HOLD     → current_budget
```

**Conservation is always exposed, never repaired.** As a defence-in-depth
check distinct from Stage 26's own invariant, a *conserved* allocation
whose recomputed totals fail to match exactly raises `RuntimeError` —
this would indicate a defect in this stage's own campaign-to-allocation
matching, never in Stage 25/26 themselves. `is_conserved=False` is never
hidden or silently ignored.

**Matching, ordering, and Decimal policy** all directly extend Stage
24–26's own established discipline: `campaign_id`-value matching only
(never tuple position), original input order preserved, `Decimal`
exclusively with every arithmetic operation inside an explicitly-scoped
`localcontext` sized from actual operand digits and collection size,
immune to ambient global context mutation.

**Excluded from this result entirely**: signed movement, raw/effective
constraint capacities, availability/suitability objects, tracking status,
validation issues, reserve, campaign count, timestamps, version fields,
and any formal audit-trace object.

## Deterministic Streamlit Review Shell (Stage 28, `app.py`)

Introduces **no new Pydantic model**. `app.py` is a pure consumer of already-frozen
models — `ReviewSetup`, `CampaignInput`, `ValidationIssue`, `ValidationReport`,
`BudgetReallocationReviewResult`, `CampaignBudgetRecommendationResult`,
`CampaignReallocationConservation` — and renders their fields directly.

**Session state.** One key, `locked_review_result` (`str`, module constant
`app.RESULT_STATE_KEY`), holding the last successfully computed
`BudgetReallocationReviewResult`, or `None`/absent when no successful submission has
completed yet. Cleared to `None` at the start of every new form submission, before
validation begins.

**Raw review-setup input mapping** (built by `_build_raw_review_setup`, passed directly
to `validate_review_setup`): `review_id`, `review_date`, `period_start`, `period_end`,
`reviewer_name`, `approved_monthly_budget` (raw string, never `float`),
`initial_account_reserve` (raw string, never `float`) are always present;
`default_max_change_percentage` (raw string) and `review_notes` are present only when
their widget's text is non-blank, so `ReviewSetup`'s own defaults apply otherwise.

**Locked-result display mapping** (`_campaign_result_row`, one row per
`CampaignBudgetRecommendationResult`, in original pipeline order): `campaign_id`,
`campaign_name`, `platform` (`.value`), `current_budget` (`format(value, "f")`),
`recommendation_action` (`.value`), `allocated_amount` (`format(value, "f")`),
`recommended_budget` (`format(value, "f")`), `reason_codes` (comma-joined `.value`s, in
order), `performance_band` (`.value`), `trend_direction` (`.value`), `confidence`
(`.value`), `pacing_status` (`.value`), `reallocation_priority_score` (`int`), `rank`
(`str(rank)` or the literal string `"Not ranked"` when absent — never a fabricated
number).

**Portfolio-level display fields**: `review_id`, `total_current_budget`,
`total_recommended_budget`, `conservation.total_increase_allocated`,
`conservation.total_decrease_allocated`, `conservation.net_change`,
`conservation.is_conserved` — all shown unconditionally for a successful result, every
Decimal formatted via `format(value, "f")`.

**Excluded from Stage 28 entirely**: `config.py`, any Gemini input/output model, any
approval-decision model, any audit-record model, any export format — none exists yet.

## Gemini Configuration Fields (Stage 29, `config.py`)

| Field | Type | Meaning |
|-------|------|---------|
| `api_key` | `SecretStr \| None` | The trimmed `GEMINI_API_KEY` value, sourced from the process environment or a local `.env` (never both — see Decision Rules); `None` is a normal, valid "Gemini unavailable" state, never an error. Redacted by `SecretStr` in `repr`/`str`/`model_dump`/`model_dump_json`; retrievable only via `.get_secret_value()`. |

`GeminiConfig` (frozen, `extra="forbid"`) has exactly this one field. Availability is a
derived function, `is_gemini_available(config) -> bool`, never a stored field — so a
result can never claim availability that disagrees with `api_key`.

**Excluded from Stage 29 entirely** (unjustified by any current evidence, or a future-stage
concern): Gemini model name, request timeout, temperature, token/output limit, retry
count, environment name, debug flag, audit/export directories, application title,
deterministic feature flags. No Gemini SDK model or request/response type exists yet.

## Explanation Payload and Prompt Fields (Stage 30, `src/explanations.py`)

**`CampaignExplanationPayload`** (frozen, `extra="forbid"`) — one locked campaign's
authorized facts, copied directly from a `CampaignBudgetRecommendationResult`, never
recalculated:

| Field | Type | Source |
|-------|------|--------|
| `campaign_id` | `str` | copied unchanged |
| `campaign_name` | `str` | copied unchanged — the sole free-text/untrusted field |
| `platform` | `Platform` | copied unchanged |
| `current_budget` | `Currency` | copied unchanged |
| `recommendation_action` | `RecommendationAction` | copied unchanged |
| `allocated_amount` | `Currency` (`>= 0`) | copied unchanged |
| `recommended_budget` | `Currency` (`>= 0`) | copied unchanged |
| `reason_codes` | `tuple[ReasonCode, ...]` | copied unchanged, order preserved |
| `performance_band` | `PerformanceBand` | copied unchanged |
| `trend_direction` | `TrendDirection` | copied unchanged |
| `confidence` | `Confidence` | copied unchanged |
| `pacing_status` | `PacingStatus` | copied unchanged |
| `reallocation_priority_score` | `int` (`0..100`) | copied unchanged |
| `rank` | `int \| None` (`>= 1` when present) | copied unchanged — `None` means "not ranked," never rank zero |

**`PortfolioExplanationPayload`** (frozen, `extra="forbid"`) — one locked portfolio's
authorized totals and conservation facts, never a campaign list:

| Field | Type | Source |
|-------|------|--------|
| `review_id` | `str` | `result.review_id` |
| `total_current_budget` | `Currency` (`>= 0`) | `result.total_current_budget` |
| `total_recommended_budget` | `Currency` (`>= 0`) | `result.total_recommended_budget` |
| `total_increase_allocated` | `Currency` (`>= 0`) | `result.conservation.total_increase_allocated` |
| `total_decrease_allocated` | `Currency` (`>= 0`) | `result.conservation.total_decrease_allocated` |
| `net_change` | `Decimal` | `result.conservation.net_change` |
| `is_conserved` | `bool` | `result.conservation.is_conserved` — never recalculated |

**`ExplanationPrompt`** (frozen, `extra="forbid"`): `system_instruction: str` (fixed,
identical across every prompt, contains no campaign or portfolio data) and
`user_content: str` (one fixed sentence plus the canonical JSON between
`BEGIN_LOCKED_DATA`/`END_LOCKED_DATA` markers).

**Excluded from Stage 30 entirely**: raw CSV data, `ReviewSetup.review_notes`, raw
`CampaignMetrics`, validation issues, intermediate constraints (Stage 10–18), availability/
suitability (Stage 19–20), the API key or any configuration, audit data, timestamps, and
any generated explanation text — none is reachable from either payload model or referenced
anywhere in the module.

## Gemini Explanation Result Fields (Stage 31, `src/gemini_analyzer.py`)

**`ExplanationStatus`** (`str, Enum`): `GENERATED`, `UNAVAILABLE`, `FAILED`.

**`ErrorCategory`** (`str, Enum`): `CONFIGURATION`, `AUTHENTICATION`, `RATE_LIMIT`,
`SERVER_ERROR`, `TIMEOUT`, `NETWORK_ERROR`, `SAFETY_BLOCK`, `EMPTY_RESPONSE`,
`MALFORMED_RESPONSE`, `UNEXPECTED_ERROR`.

**`ExplanationResult`** (frozen, `extra="forbid"`) — the only shape a Gemini explanation
attempt may take; no field can represent, replace, or reinterpret a locked value:

| Field | Type | Meaning |
|-------|------|---------|
| `status` | `ExplanationStatus` | Which of the three states this result represents. |
| `explanation_text` | `str \| None` | The stripped Gemini response text. Nonblank only when `status=GENERATED`; `None` otherwise. |
| `model_name` | `str \| None` | The requested model string. `None` only for `UNAVAILABLE`; nonblank for `GENERATED`/`FAILED`. |
| `error_category` | `ErrorCategory \| None` | `None` only for `GENERATED`; `CONFIGURATION` for `UNAVAILABLE`; any non-`CONFIGURATION` value for `FAILED`. |
| `error_message` | `str \| None` | A sanitized, nonblank message for `UNAVAILABLE`/`FAILED`; `None` for `GENERATED`. Never contains a raw API key. |

A model validator enforces these state/field combinations; an inconsistent direct
construction is rejected by normal Pydantic validation, never silently repaired.

**Excluded from Stage 31 entirely**: a prompt/request identifier, timestamps, token usage,
and the raw provider response object — none has a defined downstream consumer yet, and the
raw response is never retained regardless. `app.py`, `BudgetReallocationReviewResult`,
`CampaignBudgetRecommendationResult`, either explanation payload model, and any approval or
audit model are never imported or accepted by this module.

## Explanation UI Session State (Stage 32, `app.py`)

| Key | Type | Meaning |
|-----|------|---------|
| `locked_review_result` | `BudgetReallocationReviewResult \| None` | Unchanged since Stage 28; never mutated by the Stage 32 explanation flow. |
| `portfolio_explanation_result` | `ExplanationResult \| None` | The most recent portfolio explanation attempt's result, or `None` before any click / after a new deterministic submission. |
| `campaign_explanation_result` | `ExplanationResult \| None` | The most recent campaign explanation attempt's result. |
| `campaign_explanation_campaign_id` | `str \| None` | The `campaign_id` the stored `campaign_explanation_result` belongs to. Rendered only when this equals the selectbox's current value — a mismatch hides the stale explanation without clearing it, so reselecting the original campaign redisplays it without a new call. |

The selectbox's own widget-owned value lives only under its own Streamlit key,
`explanation_campaign_id` — it is never duplicated into another session-state key.

**Excluded from Stage 32 entirely**: any configuration object or API key in session state
(only the already-redacted `ExplanationResult` is ever stored); a batch/whole-portfolio
campaign result; any approval, audit, or export state.

## Human Approval Fields (Stage 33, `src/approval.py`)

**`CampaignReallocationApproval`** (frozen, `extra="forbid"`) — one accountable human
decision applied to the complete locked `BudgetReallocationReviewResult`, never a
per-campaign or partial-portfolio decision. Reuses the existing Stage 1 `ReviewStatus`
enum rather than a new `ApprovalDecision` enum:

| Field | Type | Meaning |
|-------|------|---------|
| `review_id` | `str` (min length 1) | Always derived from `result.review_id` — never a separate caller-supplied parameter. |
| `decision` | `ReviewStatus` | Restricted by a `@field_validator` to `ReviewStatus.APPROVED` or `ReviewStatus.REJECTED` only; direct construction with `DRAFT` or `PENDING_APPROVAL` fails Pydantic validation. |
| `reviewer_name` | `str` (min length 1) | The human approver's name; stripped, never blank. |
| `note` | `str \| None` | Optional free-form decision note; a blank value normalizes to `None`. |

**Functions**: `approve_campaign_reallocation_review(result, reviewer_name, *, note=None)`
and `reject_campaign_reallocation_review(result, reviewer_name, *, note=None)`. Both raise
exactly `ValueError("Reviewer name must not be blank.")` for a blank/whitespace-only name,
checked first. Approval additionally raises exactly `ValueError("An unconserved allocation
cannot be approved.")` when `result.conservation.is_conserved` is `False`; rejection places
no such restriction. Neither function repairs, rebalances, or reruns anything.

**Excluded from Stage 33 entirely**: any timestamp (deferred to the later audit stage); any
`config`, `src.explanations`, `src.gemini_analyzer`, `src.audit`, or `src.exports` import or
reference — structurally guaranteed via AST-based isolation tests.

## Human Approval UI Session State (Stage 33, `app.py`)

| Key | Type | Meaning |
|-----|------|---------|
| `approval_decision_result` (`APPROVAL_DECISION_STATE_KEY`) | `CampaignReallocationApproval \| None` | The finalized decision, or `None` before any click / after a new deterministic submission. Once non-`None`, it cannot be overwritten or reconsidered except by a new deterministic submission. |
| `approval_reviewer_name` | widget-owned `str` | The `st.text_input` value; starts blank on every new submission — deliberately not pre-filled from `ReviewSetup.reviewer_name`. |
| `approval_note` | widget-owned `str` | The `st.text_area` value; starts blank on every new submission. |

A stored decision whose `review_id` no longer matches the current locked result's
`review_id` is cleared with a generic mismatch error — defense-in-depth only, not a result
fingerprint; normal operation (the submission-time clearing above) never reaches this path.

**Excluded from Stage 33 entirely**: any confirmation checkbox, radio selector, or
change-decision control; any audit, export, or platform-execution state.

## Audit Record Fields (Stage 34, `src/audit.py`)

**`CampaignReallocationAudit`** (frozen, `extra="forbid"`) — the durable, structured record
of exactly one complete locked review and its finalized decision. Embeds the existing
frozen Stage 27/33 models directly — no copied result, campaign, conservation, or approval
schema exists:

| Field | Type | Meaning |
|-------|------|---------|
| `audit_id` | `str` | `f"audit_{sha256(canonical_bytes).hexdigest()}"` over the canonical JSON of `{"result": result, "approval": approval}`, excluding `recorded_at`. Also the filename stem: `audit_records/{audit_id}.json`. |
| `review_id` | `str` | Always `result.review_id`. |
| `result` | `BudgetReallocationReviewResult` | The complete locked Stage 27 result, embedded unchanged. |
| `approval` | `CampaignReallocationApproval` | The complete finalized Stage 33 decision, embedded unchanged. |
| `recorded_at` | `datetime` | Timezone-aware; a naive value is rejected by a `@field_validator`, and any aware value is normalized to UTC. The first successful write's value is authoritative — a later idempotent retry never replaces it. |

**Functions**: `build_campaign_reallocation_audit(result, approval, recorded_at)` — pure, no
file/environment/clock/network/SDK access — and `record_campaign_reallocation_audit(audit,
*, directory=None)`. `build_...` raises exactly `ValueError("Approval review_id does not
match the locked result's review_id.")` when the two disagree, and exactly
`ValueError("An unconserved allocation cannot be recorded as approved.")` when
`decision is ReviewStatus.APPROVED` but `result.conservation.is_conserved` is `False`; a
rejected unconserved result is always valid. No public read, list, delete, repair,
overwrite, or retry function exists — reserved for a later Stage 35 export stage.

**Excluded from Stage 34 entirely**: any schema version, source filename, input/result
hash, application version, export status, or Gemini explanation text/status/model
name/error — no field exists merely because audit systems often have one; every included
field has a named consumer. Any `config`, `src.explanations`, `src.gemini_analyzer`,
`src.exports`, `streamlit`, Gemini SDK, or network/database reference — structurally
guaranteed via AST-based isolation tests.

## Audit UI Session State (Stage 34, `app.py`)

| Key | Type | Meaning |
|-----|------|---------|
| `audit_record_path` (`AUDIT_RECORD_PATH_STATE_KEY`) | `str \| None` | The successfully persisted record's path (as `str`), or `None` before any attempt, after a failure, or after a new deterministic submission. Only ever set from an actual `record_campaign_reallocation_audit` return value — never fabricated. |
| `audit_record_error` (`AUDIT_RECORD_ERROR_STATE_KEY`) | `str \| None` | The one fixed sanitized failure message, or `None` on success / before any attempt / after a new submission. Never a raw exception, stack trace, or filesystem detail. |

Both keys are cleared at the start of every new deterministic-review submission, alongside
the existing locked-result, explanation, and approval state. The UI renders only the audit
ID (the filename stem) on success — the full local filesystem path is never displayed.

**Excluded from Stage 34 entirely**: any confirmation checkbox, radio selector, or
change-decision control on the audit outcome itself; any automatic retry; any export or
platform-execution state.

## Derived Fields

> Pending a later Sprint 2 stage (combined confidence/tracking/pacing assessment,
> `Confidence.NOT_ASSESSABLE` ownership, the remaining `ReasonCode` trigger
> conditions).

## Export Fields

> Pending a later Sprint 3 stage (`src/exports.py`).
