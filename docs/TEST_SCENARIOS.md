# Test Scenarios

> Sprint 1, Development Stage 20 populates the Campaign Action Suitability
> Scenarios section below, backed by the new `tests/test_suitability.py` (67
> tests, a dedicated file for the new `src/suitability.py` module — Stage 20 does
> not extend `tests/test_availability.py`, which remains unchanged at 61 tests,
> nor `tests/test_constraints.py`, which remains unchanged at 322 tests: 25 Stage
> 10 + 24 Stage 11 + 35 Stage 12 + 35 Stage 13 + 28 Stage 14 + 39 Stage 15 + 40
> Stage 16 + 46 Stage 17 + 50 Stage 18), in addition to the Campaign Action
> Availability Scenarios (Stage 19, below), the Effective Decrease Limit Scenarios
> (Stage 18, below), the Raw Decrease Limit Scenarios (Stage 17, below), the Raw
> Increase Limit Scenarios (Stage 16, below), the Test-Aware Static Decrease Room
> Scenarios (Stage 15, below), the Protection Constraint Scenarios (Stage 14,
> below), the Test-Floor Room Scenarios (Stage 13, below), the Raw Percentage
> Movement-Cap Scenarios (Stage 12, below), the Applicable Change-Percentage
> Resolution Scenarios (Stage 11, below), the Static Budget-Bound Scenarios (Stage
> 10, below), the Stage 9 Pacing
> Interpretation Scenarios (`tests/test_pacing_interpretation.py`, 33 tests), the
> Stage 8 Tracking Assessability Scenarios (`tests/test_tracking_assessment.py`, 30
> tests), the Stage 7 Conversion-Volume Confidence Classification Scenarios
> (`tests/test_confidence_classification.py`, 32 tests), the Stage 6 Trend
> Classification Scenarios (`tests/test_trend_classification.py`, 29 tests), the Stage 5
> Performance Classification Scenarios (`tests/test_classification.py`, 23 tests), the
> Stage 4 Pacing Calculation Scenarios (`tests/test_pacing.py`, 30 tests), the Stage 3
> Metric Calculation Scenarios (`tests/test_metrics.py`, 28 tests), and the Stage 2
> Validation Scenarios (`tests/test_validation.py`, 44 tests). Allocation and
> Approval/Audit scenarios are pending later stages.

## Validation Scenarios

All scenarios below produce only `ValidationSeverity.ERROR` issues — Stage 2 defines no
warning-level rules. "Report" means the `ValidationReport` returned by
`validate_review_setup()` or `validate_campaign_csv()`.

### ValidationIssue / ValidationReport shape

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | Construct a `ValidationIssue` with all fields set | All fields readable back as given. |
| 2 | Construct a `ValidationIssue` with only required fields | `field`, `row_number`, `campaign_id` default to `None`. |
| 3 | `ValidationReport` with 2 ERROR issues | `error_count == 2`. |
| 4 | `ValidationReport` with 1 WARNING + 1 ERROR issue | `warning_count == 1`, `error_count == 1`. |
| 5 | `ValidationReport` with no issues | `is_valid is True`. |
| 6 | `ValidationReport` with any ERROR issue | `is_valid is False`. |
| 7 | `ValidationReport` constructed with a list of `CampaignInput` | `valid_campaigns` preserves the given order exactly. |
| 8 | Attempt to construct `ValidationReport(error_count=99, ...)` | Rejected — `error_count`/`warning_count`/`is_valid` are computed, not settable. |

### Review setup validation (`validate_review_setup`)

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 9 | All fields valid | Returns `(ReviewSetup instance, report)`; `report.issues == []`. |
| 10 | `review_id` blank | Returns `(None, report)`; one `INVALID_REVIEW_FIELD` issue, `field="review_id"`. |
| 11 | Three fields invalid at once (`review_id`, `reviewer_name`, `approved_monthly_budget`) | Three `INVALID_REVIEW_FIELD` issues, one per field. |
| 12 | `period_end` before `period_start` (cross-field rule) | One `INVALID_REVIEW_FIELD` issue with `field is None` (model-level, not one field). |
| 13 | Any invalid review | Every issue has `row_number is None`. |
| 14 | `approved_monthly_budget = Decimal("1E+30")` (quantisation overflow) | One `INVALID_REVIEW_FIELD` issue with a safe message; no raw `decimal` exception text. |

### Campaign CSV — header (`validate_campaign_csv`)

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 15 | Completely empty stream | One `EMPTY_FILE` issue, `row_number=None`. |
| 16 | Valid header, zero data rows (`data/campaign_template.csv`) | One `NO_CAMPAIGN_ROWS` issue, `row_number=None`, `valid_campaigns == []`. |
| 17 | Header missing a column | One `INVALID_HEADER` issue, `row_number=1`. |
| 18 | Header with an extra column | One `INVALID_HEADER` issue. |
| 19 | Header with a renamed column (e.g. `status` → `campaign_status`) | One `INVALID_HEADER` issue. |
| 20 | Header with two columns swapped | One `INVALID_HEADER` issue. |
| 21 | Header with a duplicate column name | One `INVALID_HEADER` issue. |
| 22 | Invalid header followed by a garbage row | Exactly one issue total (`INVALID_HEADER`) — the row is never inspected. |

### Campaign CSV — row parsing and field validation

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 23 | `data/sample_campaigns.csv` (4 valid rows) | `is_valid is True`, `len(valid_campaigns) == 4`, `issues == []`. |
| 24 | Row with 19 cells (missing one) | One `MALFORMED_ROW` issue at the row's physical line number. |
| 25 | Row with 21 cells (one surplus) | One `MALFORMED_ROW` issue. |
| 26 | Row with blank `campaign_id` | One `INVALID_CAMPAIGN_FIELD` issue, `field="campaign_id"`, correct `row_number`. |
| 27 | Row with two invalid fields (`campaign_id` blank and `kpi_target=0`) | Two `INVALID_CAMPAIGN_FIELD` issues, same `row_number`, different `field`. |
| 28 | Valid, invalid, valid rows (3 total) | `valid_campaigns` has the 2 valid ones in order; 1 issue for the invalid row. |
| 29 | Blank `test_budget_floor` and `campaign_max_change_percentage` cells | Both parse to `None` on the resulting `CampaignInput`. |
| 30 | `is_protected="yes"`, `is_test_campaign="0"` | Parsed as `True`/`False` via `CampaignInput`'s conventional boolean rule. |
| 31 | `is_protected="maybe"` | One `INVALID_CAMPAIGN_FIELD` issue, `field="is_protected"`. |
| 32 | `platform="Bing Ads"` (invalid enum) | One `INVALID_CAMPAIGN_FIELD` issue, `field="platform"`. |
| 33 | `kpi_target="not-a-number"` | One `INVALID_CAMPAIGN_FIELD` issue, `field="kpi_target"`. |
| 34 | `minimum_budget > maximum_budget` (cross-field) | One `INVALID_CAMPAIGN_FIELD` issue, `field is None`. |
| 35 | Valid, invalid, valid rows | Issue's `row_number` matches the invalid row's physical line; valid rows keep their own correct IDs. |
| 36 | `current_budget="1E+30"` (quantisation overflow) | One `INVALID_CAMPAIGN_FIELD` issue with a safe message; no raw `decimal` exception text. |

### Duplicate campaign IDs

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 37 | Two rows, same `campaign_id`, both otherwise valid | Both rows get a `DUPLICATE_CAMPAIGN_ID` issue; `valid_campaigns == []`. |
| 38 | Three rows, same `campaign_id` | All three get a `DUPLICATE_CAMPAIGN_ID` issue. |
| 39 | Duplicate pair among 3 rows | All occurrences of the duplicated ID excluded from `valid_campaigns`. |
| 40 | Two unique rows + one duplicate pair | The two unique rows remain, in original CSV order. |
| 41 | One structurally invalid row and one valid row sharing the same `campaign_id` text | No `DUPLICATE_CAMPAIGN_ID` issue — the invalid row never became a `CampaignInput`; only its own `INVALID_CAMPAIGN_FIELD` issue is produced. |
| 42 | `CAMP001` vs. `camp001` | Not duplicates — both retained (case-sensitive comparison). |
| 43 | `" CAMP001 "` vs. `"CAMP001"` | Duplicates — compared after `CampaignInput`'s own whitespace trimming. |

## Metric Calculation Scenarios

All scenarios below use `calculate_campaign_metrics(campaign: CampaignInput) ->
CampaignMetrics` from `src/metrics.py`. Every result is a **fact only** — none of these
scenarios produces a classification, recommendation, confidence level, or trend label.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignMetrics` field set | Exactly `campaign_id`, `performance_ratio_7d`, `performance_ratio_28d`, `weighted_performance_ratio`, `trend_delta`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignMetrics` instance | Rejected (`frozen=True`). |
| 4 | All four calculated fields | Each is a `Decimal`, never a `float`. |
| 5 | ROAS, target 4, actual 5 (7d) / 4 (28d) | `performance_ratio_7d = 1.25`, `performance_ratio_28d = 1`. |
| 6 | ROAS below target | Both ratios `< 1`. |
| 7 | ROAS exactly at target | Both ratios `= 1`. |
| 8 | CPA, target 20, actual 16 (7d) / 20 (28d) | `performance_ratio_7d = 1.25`, `performance_ratio_28d = 1`. |
| 9 | CPA worse than target (higher actual) | Both ratios `< 1`. |
| 10 | CPA exactly at target | Both ratios `= 1`. |
| 11 | 25% outperformance expressed as ROAS vs. as CPA | Both produce `performance_ratio_7d = 1.25` — direction normalisation makes CPA and ROAS comparable. |
| 12 | Better vs. worse actual, for both KPI types | Higher `performance_ratio_7d` consistently corresponds to the better actual, for both CPA and ROAS. |
| 13 | `ratio_7d = 1.25`, `ratio_28d = 1` | `weighted_performance_ratio = 1.10`. |
| 14 | `ratio_7d = 0.80`, `ratio_28d = 1` | `weighted_performance_ratio = 0.92`. |
| 15 | `ratio_7d == ratio_28d` | `weighted_performance_ratio` equals that same value (unchanged by weighting). |
| 16 | Arbitrary distinct ratios | `weighted_performance_ratio` matches `ratio_7d * SEVEN_DAY_WEIGHT + ratio_28d * TWENTY_EIGHT_DAY_WEIGHT` computed independently from the frozen constants. |
| 17 | `ratio_7d = 1.25`, `ratio_28d = 1` | `trend_delta = 0.25`. |
| 18 | `ratio_7d = 0.80`, `ratio_28d = 1` | `trend_delta = -0.20`. |
| 19 | `ratio_7d == ratio_28d` | `trend_delta = 0` exactly. |
| 20 | `ratio_7d = 1.44`, `ratio_28d = 1.24` | `trend_delta = 0.20 / 1.24` (not `0.20`) — proves the formula is relative, not a simple subtraction. |
| 21 | Repeating division (e.g. ROAS target 3, actual 1) | Result matches an independently-computed `Decimal` under `prec=28`/`ROUND_HALF_UP`, to all 28 significant digits. |
| 22 | Global `decimal` context mutated to `prec=2`/`ROUND_DOWN` before calling the function | Result is unaffected — still matches the `prec=28`/`ROUND_HALF_UP` expectation, proving `localcontext()` isolation. |
| 23 | Any ratio with a non-terminating decimal expansion | Not quantised to 2 decimal places; differs from its own `.quantize(Decimal("0.01"))`. |
| 24 | All four `CampaignMetrics` fields | None is a `float`, under any input. |
| 25 | `data/sample_campaigns.csv` validated via `validate_campaign_csv`, then all 4 valid campaigns passed to `calculate_campaign_metrics` | `campaign_id` order preserved (`G001`, `M001`, `G002`, `G003`); each of the four ratios/weighted ratio/trend delta matches hand-calculation exactly. |
| 26 | `CampaignMetrics.model_fields` | Contains no `recommendation_action`, `confidence`, `reason_code`, `trend_label`/`trend`, `score`, `budget`, or raw KPI/conversion field. |
| 27 | `calculate_campaign_metrics(not_a_campaign_input)` | Raises a normal Python `AttributeError` (no silent coercion, no broad exception handling). |

## Pacing Calculation Scenarios

All scenarios below use `calculate_campaign_pacing(review: ReviewSetup, campaign:
CampaignInput) -> CampaignPacing` from `src/pacing.py`. Every result is a **fact only**
— none of these scenarios produces a pacing status, label, or recommendation.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignPacing` field set | Exactly the 9 approved fields. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignPacing` instance | Rejected (`frozen=True`). |
| 4 | `elapsed_days`, `total_period_days` | Both `int`. |
| 5 | All present calculated numerical fields | Each is a `Decimal`, never a `float`. |
| 6 | `pacing_ratio`/`projected_end_of_period_spend` constructed directly as `None` | Accepted. |
| 7 | Period 1–31 August, `review_date = 1 August` | `elapsed_days = 1`, `total_period_days = 31`, `elapsed_fraction = 1/31`. |
| 8 | `review_date = 10 August` | `elapsed_days = 10`, `elapsed_fraction = 10/31`. |
| 9 | `review_date = 31 August` | `elapsed_days = 31 = total_period_days`, `elapsed_fraction = 1`. |
| 10 | `review_date` before `period_start` | `elapsed_days = 0`, `elapsed_fraction = 0`. |
| 11 | `review_date` after `period_end` | `elapsed_days = total_period_days`, `elapsed_fraction = 1`. |
| 12 | One-day period, reviewed on that day | `elapsed_days = 1`, `total_period_days = 1`, `elapsed_fraction = 1`. |
| 13 | February 2028 (leap year), period 1–29 Feb | `total_period_days = 29`. |
| 14 | 10-day period, day 5, budget 1000.00, spend 500.00 | `expected_spend=500.00`, `spend_variance=0.00`, `pacing_ratio=1`, `remaining_budget=500.00`, `projected=1000.00`. |
| 15 | Same, spend 400.00 (below pace) | `expected_spend=500.00`, `spend_variance=-100.00`, `pacing_ratio=0.8`, `remaining_budget=600.00`, `projected=800.00`. |
| 16 | Same, spend 600.00 (above pace) | `expected_spend=500.00`, `spend_variance=100.00`, `pacing_ratio=1.2`, `remaining_budget=400.00`, `projected=1200.00`. |
| 17 | Zero spend, active period | `pacing_ratio = 0`, `projected_end_of_period_spend = 0.00`. |
| 18 | `current_budget = 0.00` | `expected_spend=0.00`, `spend_variance=0.00`, `pacing_ratio=None`, `remaining_budget=0.00`, `projected=0.00` (elapsed_fraction nonzero). |
| 19 | `review_date` before the period | `expected_spend=0.00`, `pacing_ratio=None`, `projected_end_of_period_spend=None`. |
| 20 | `spend_to_date == current_budget` | `remaining_budget = 0.00`. |
| 21 | Spend above `current_budget` | Not constructible — `CampaignInput` already forbids it; not a Stage 4 case. |
| 22 | Repeating `elapsed_fraction` (e.g. `10/31`) | Matches an independently-computed `Decimal` under `prec=28`/`ROUND_HALF_UP` to all 28 significant digits. |
| 23 | `expected_spend`, `spend_variance`, `remaining_budget`, `projected_end_of_period_spend` | Each equals its own `.quantize(Decimal("0.01"))` (already 2 d.p.). |
| 24 | `pacing_ratio` vs. a ratio computed from the *quantised* `expected_spend` | Differ — proves `pacing_ratio` uses the unquantised internal value. |
| 25 | Global `decimal` context mutated to `prec=2`/`ROUND_DOWN` before calling the function | Result unaffected — still matches `prec=28`/`ROUND_HALF_UP`, proving `localcontext()` isolation. |
| 26 | All present numerical fields | None is a `float`, under any input. |
| 27 | `data/sample_campaigns.csv` validated via `validate_campaign_csv`, paired with one constructed `ReviewSetup` (10 elapsed of 31 days) | Campaign order preserved (`G001`, `M001`, `G002`, `G003`); every field matches hand-calculation exactly. |
| 28 | `CampaignPacing.model_fields` | Contains no performance ratio, pacing status/label, `RecommendationAction`, `Confidence`, `ReasonCode`, score, eligibility, or allocation field. |
| 29 | `src/pacing.py` source | Does not import `CampaignMetrics`, `src.metrics`, or `src.classification`. |
| 30 | `calculate_campaign_pacing(None, None)` | Raises a normal Python `AttributeError` (no silent coercion, no broad exception handling). |

## Performance Classification Scenarios

All scenarios below use `classify_campaign_performance(metrics: CampaignMetrics) ->
CampaignPerformanceClass` from `src/classification.py`. Every result is a **neutral
descriptive classification only** — none of these scenarios produces a
`RecommendationAction`, `Confidence`, `ReasonCode`, trend label, tracking interpretation,
score, eligibility, or allocation outcome.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `PerformanceBand` members | Exactly `ABOVE_TARGET`, `ON_TARGET`, `BELOW_TARGET`. |
| 2 | `CampaignPerformanceClass` field set | Exactly `campaign_id`, `performance_band`. |
| 3 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 4 | Attempt to mutate a `CampaignPerformanceClass` instance | Rejected (`frozen=True`). |
| 5 | `performance_band` | Always a `PerformanceBand` instance. |
| 6 | `classify_campaign_performance({"weighted_performance_ratio": ...})` (dict, not `CampaignMetrics`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 7 | `weighted_performance_ratio = Decimal("1.1500000000000000000000000001")` | `ABOVE_TARGET`. |
| 8 | `weighted_performance_ratio = Decimal("1.15")` (exactly `INCREASE_THRESHOLD`) | `ABOVE_TARGET` — the threshold belongs to the higher band. |
| 9 | `weighted_performance_ratio = Decimal("1.1499999999999999999999999999")` | `ON_TARGET`. |
| 10 | `weighted_performance_ratio = Decimal("1.00")` | `ON_TARGET`. |
| 11 | `weighted_performance_ratio = Decimal("0.9000000000000000000000000001")` | `ON_TARGET`. |
| 12 | `weighted_performance_ratio = Decimal("0.90")` (exactly `MAINTAIN_THRESHOLD`) | `ON_TARGET` — the threshold belongs to the higher band. |
| 13 | `weighted_performance_ratio = Decimal("0.8999999999999999999999999999")` | `BELOW_TARGET`. |
| 14 | `weighted_performance_ratio = Decimal("0.50")` | `BELOW_TARGET`. |
| 15 | `campaign_id` on the result | Copied exactly from the source `CampaignMetrics`. |
| 16 | 25%-better-than-target expressed as ROAS vs. as CPA, carried through `CampaignInput` → `calculate_campaign_metrics` → `classify_campaign_performance` | Both produce `weighted_performance_ratio = 1.25` and both classify as `ABOVE_TARGET` — KPI origin established via the real Stage 1/3 path, not asserted on `CampaignMetrics` alone (which carries no `kpi_type`). |
| 17 | `data/sample_campaigns.csv` validated, then each campaign run through `calculate_campaign_metrics` → `classify_campaign_performance`, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`); bands: `G001=ON_TARGET`, `M001=ON_TARGET`, `G002=ABOVE_TARGET`, `G003=ON_TARGET`. |
| 18 | `CampaignPerformanceClass.model_fields` | Contains no `recommendation_action`, `confidence`, `reason_code`, trend/tracking/pacing field, `score`, `eligibility`, or `allocation` field. |
| 19 | `src/classification.py` imports | Does not import `CampaignInput`, `CampaignPacing`, `ReviewSetup`, `RecommendationAction`, `Confidence`, `ReasonCode`, or any later-stage module (verified via AST import inspection). |
| 20 | Any result | No `float` anywhere. |
| 21 | Classification call | Performs no arithmetic — input `Decimal` value is unchanged after the call. |
| 22 | Global `decimal` context mutated (`prec=1`, `ROUND_DOWN`) before calling the function | Result unaffected — classification is comparison-only and needs no local context. |

## Trend Classification Scenarios

All scenarios below use `classify_campaign_trend(metrics: CampaignMetrics) ->
CampaignTrendClass` from `src/classification.py`. Every result is **descriptive evidence
only**, independent of `PerformanceBand` — none of these scenarios produces a
`RecommendationAction`, `Confidence`, `ReasonCode`, performance band, tracking
interpretation, score, eligibility, or allocation outcome.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `TrendDirection` members | Exactly `IMPROVING`, `STABLE`, `DECLINING`, each value equal to its name. |
| 2 | `CampaignTrendClass` field set | Exactly `campaign_id`, `trend_direction`. |
| 3 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 4 | Attempt to mutate a `CampaignTrendClass` instance | Rejected (`frozen=True`). |
| 5 | `trend_direction` | Always a `TrendDirection` instance. |
| 6 | `campaign_id` on the result | Copied exactly from the source `CampaignMetrics`. |
| 7 | `classify_campaign_trend({"trend_delta": ...})` (dict, not `CampaignMetrics`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 8 | `trend_delta = Decimal("0.1000000000000000000000000001")` | `IMPROVING`. |
| 9 | `trend_delta = Decimal("0.10")` (exactly `TREND_THRESHOLD`) | `IMPROVING` — the threshold belongs to the directional band. |
| 10 | `trend_delta = Decimal("0.0999999999999999999999999999")` | `STABLE`. |
| 11 | `trend_delta = Decimal("0.05")` | `STABLE`. |
| 12 | `trend_delta = Decimal("0")` | `STABLE`. |
| 13 | `trend_delta = Decimal("-0.05")` | `STABLE`. |
| 14 | `trend_delta = Decimal("-0.0999999999999999999999999999")` | `STABLE`. |
| 15 | `trend_delta = Decimal("-0.10")` (exactly `-TREND_THRESHOLD`) | `DECLINING` — this is a **synthetic case, since no sample campaign has a negative `trend_delta`** (all four sample campaigns have 7-day performance better than 28-day). |
| 16 | `trend_delta = Decimal("-0.1000000000000000000000000001")` | `DECLINING`. |
| 17 | `trend_delta = Decimal("1000000")` | `IMPROVING` (very large positive). |
| 18 | `trend_delta = Decimal("-1000000")` | `DECLINING` (very large negative). |
| 19 | 25%-better 7-day-vs-28-day ratio expressed as ROAS vs. as CPA, carried through `CampaignInput` → `calculate_campaign_metrics` → `classify_campaign_trend` | Both produce `trend_delta = 0.25` and both classify as `IMPROVING` — KPI origin established via the real Stage 1/3 path, not asserted on `CampaignMetrics` alone. |
| 20 | `data/sample_campaigns.csv` validated, then each campaign run through `calculate_campaign_metrics` → `classify_campaign_trend`, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`); `G001`/`M001`/`G003` = `STABLE`, `G002` = `IMPROVING`; exact `trend_delta` values match Stage 3's documented outputs. |
| 21 | `CampaignTrendClass.model_fields` | Contains no `performance_band`, `confidence`, `tracking_status`, `pacing_ratio`, `recommendation_action`, `reason_code`, `score`, `eligibility`, or `allocation` field. |
| 22 | `src/classification.py` imports | Still does not import `CampaignInput`, `CampaignPacing`, `ReviewSetup`, `RecommendationAction`, `Confidence`, `ReasonCode`, or any later-stage module (AST-verified). |
| 23 | `classify_campaign_trend` body | Does not call `classify_campaign_performance` (AST-verified); reads only `metrics.campaign_id` and `metrics.trend_delta` (AST-verified). |
| 24 | Any result | No `float` anywhere; no arithmetic or quantisation performed on `trend_delta` (input value unchanged after the call). |
| 25 | Global `decimal` context mutated (`prec=1`, `ROUND_DOWN`) before calling the function | Result unaffected for both a stable value and the exact negative boundary `Decimal("-0.10")` — classification is comparison-only and needs no local context. |
| 26 | `classify_campaign_performance` (Stage 5) | Unchanged behaviour after the Stage 6 additions — regression-checked. |

## Conversion-Volume Confidence Classification Scenarios

All scenarios below use `classify_campaign_confidence(campaign: CampaignInput) ->
CampaignConfidenceClass` from `src/classification.py`. Every result is **descriptive
conversion-volume evidence only**, independent of `PerformanceBand`/`TrendDirection` —
none of these scenarios produces a tracking interpretation, assessability decision,
pacing interpretation, `RecommendationAction`, `ReasonCode`, score, eligibility, or
allocation outcome, and none ever assigns `Confidence.NOT_ASSESSABLE`.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `Confidence` members | Still exactly `HIGH`, `MEDIUM`, `LOW`, `NOT_ASSESSABLE` (unchanged, Stage 1). |
| 2 | `CampaignConfidenceClass` field set | Exactly `campaign_id`, `confidence`. |
| 3 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 4 | Attempt to mutate a `CampaignConfidenceClass` instance | Rejected (`frozen=True`). |
| 5 | `confidence` | Always a `Confidence` instance. |
| 6 | `campaign_id` on the result | Copied exactly from the source `CampaignInput`. |
| 7 | `classify_campaign_confidence({"conversions_28d": 0})` (dict, not `CampaignInput`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 8 | `conversions_28d = 0` | `LOW` — zero conversions is not special-cased. |
| 9 | `conversions_28d = 1` | `LOW`. |
| 10 | `conversions_28d = 9` (one below `MINIMUM_CONVERSIONS`) | `LOW`. |
| 11 | `conversions_28d = 10` (exactly `MINIMUM_CONVERSIONS`) | `MEDIUM` — the threshold belongs to the higher band. |
| 12 | `conversions_28d = 11` | `MEDIUM`. |
| 13 | `conversions_28d = 29` (one below `HIGH_CONFIDENCE_CONVERSIONS`) | `MEDIUM`. |
| 14 | `conversions_28d = 30` (exactly `HIGH_CONFIDENCE_CONVERSIONS`) | `HIGH` — the threshold belongs to the higher band. |
| 15 | `conversions_28d = 31` | `HIGH`. |
| 16 | `conversions_28d = 1000000` | `HIGH`. |
| 17 | Two campaigns with the same `conversions_28d` but different valid `conversions_7d` | Same `Confidence` — `conversions_7d` has no effect. |
| 18 | Conflicting-window example: `conversions_7d=5`, `conversions_28d=20` | `MEDIUM` — proves `conversions_28d` alone is authoritative (`conversions_7d=5` alone would suggest a lower band, but is never consulted). |
| 19 | `classify_campaign_confidence` source | Reads only `campaign.campaign_id`/`campaign.conversions_28d` (AST-verified); never reads `conversions_7d`; contains no binary arithmetic operation (AST-verified) — no summing/averaging/weighting of the two windows. |
| 20 | CPA vs. ROAS, and Google Ads vs. Meta Ads, with the same `conversions_28d` | Same `Confidence` in every combination. |
| 21 | `data/sample_campaigns.csv` validated, then each `CampaignInput` classified directly (no `CampaignMetrics` calculated), iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`); `G001` (155) / `M001` (210) / `G002` (520) = `HIGH`; `G003` (20) = `MEDIUM`. |
| 22 | `CampaignConfidenceClass.model_fields` | Contains no `performance_band`, `trend_direction`, `tracking_status`, `pacing_ratio`, `recommendation_action`, `reason_code`, `score`, `eligibility`, `allocation`, `conversions_7d`, or `conversions_28d` field. |
| 23 | `classify_campaign_confidence` result, for every boundary value tested | Never equals `Confidence.NOT_ASSESSABLE`. |
| 24 | `src/classification.py` imports | Does not import `CampaignPacing`, `ReviewSetup`, `TrackingStatus`, `RecommendationAction`, or `ReasonCode` (AST-verified; `CampaignInput`/`Confidence` are now legitimately imported for Stage 7). |
| 25 | `classify_campaign_confidence` body | Does not call `classify_campaign_performance` or `classify_campaign_trend` (AST-verified). |
| 26 | Any result | No `float` or `Decimal` anywhere. |
| 27 | Global `decimal` context mutated (`prec=1`, `ROUND_DOWN`) before calling the function | Result unaffected — classification is plain integer comparison, no `Decimal` involved at all. |
| 28 | `classify_campaign_performance` (Stage 5) and `classify_campaign_trend` (Stage 6) | Unchanged behaviour after the Stage 7 additions — regression-checked. |

## Tracking Assessability Scenarios

All scenarios below use `assess_campaign_tracking(campaign: CampaignInput) ->
CampaignTrackingAssessment` from `src/classification.py`. Every result is a **narrow
tracking-based assessability fact only** — none of these scenarios produces conversion-
volume confidence, `Confidence.NOT_ASSESSABLE`, a performance/trend classification, a
pacing interpretation, a combined judgement, `RecommendationAction`, `ReasonCode`,
score, eligibility, or allocation outcome.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignTrackingAssessment` field set | Exactly `campaign_id`, `tracking_status`, `is_assessable`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignTrackingAssessment` instance | Rejected (`frozen=True`). |
| 4 | `tracking_status` | Always a `TrackingStatus` instance. |
| 5 | `is_assessable` | Always a `bool`. |
| 6 | `campaign_id`, `tracking_status` on the result | Both copied exactly from the source `CampaignInput`. |
| 7 | `assess_campaign_tracking({"tracking_status": "Healthy"})` (dict, not `CampaignInput`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 8 | `tracking_status = HEALTHY` | `is_assessable = True`. |
| 9 | `tracking_status = WARNING` | `is_assessable = True` — and the result's `tracking_status` is `WARNING`, not silently converted to `HEALTHY`. |
| 10 | `tracking_status = UNRELIABLE` | `is_assessable = False` — the sole `False` condition. |
| 11 | Two campaigns with the same `tracking_status` but different `conversions_28d` | Same `is_assessable`. |
| 12 | Two campaigns with the same `tracking_status` but different `conversions_7d` | Same `is_assessable`. |
| 13 | CPA vs. ROAS, same `tracking_status` | Same `is_assessable`. |
| 14 | Google Ads vs. Meta Ads, same `tracking_status` | Same `is_assessable`. |
| 15 | Protected vs. unprotected vs. test campaign, same `tracking_status` | Same `is_assessable` in all three. |
| 16 | `assess_campaign_tracking` source | Reads only `campaign.campaign_id`/`campaign.tracking_status` (AST-verified); calls none of `classify_campaign_performance`/`classify_campaign_trend`/`classify_campaign_confidence`/`calculate_campaign_metrics`/`calculate_campaign_pacing` (AST-verified); contains no binary arithmetic operation (AST-verified). |
| 17 | `data/sample_campaigns.csv` validated, then each `CampaignInput` assessed directly, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`); all four have `tracking_status=Healthy` and `is_assessable=True` (no `Warning`/`Unreliable` example exists in the sample data — exercised only via synthetic fixtures, scenarios 8–10). |
| 18 | `CampaignTrackingAssessment.model_fields` | Contains no `confidence`, `performance_band`, `trend_direction`, `pacing_ratio`, `score`, `reason_code`, `recommendation_action`, `constraint`, `eligibility`, `allocation`, `conversions_7d`, or `conversions_28d` field. |
| 19 | `Confidence.NOT_ASSESSABLE` | Never assigned or read by `assess_campaign_tracking`, across every `TrackingStatus` value. |
| 20 | `classify_campaign_confidence`, `classify_campaign_performance`, `classify_campaign_trend` | Unchanged behaviour after the Stage 8 additions — regression-checked; Stage 7 continues returning only `HIGH`/`MEDIUM`/`LOW` regardless of `tracking_status`. |
| 21 | Global `decimal` context mutated (`prec=1`, `ROUND_DOWN`) before calling the function | Result unaffected — assessment is plain enum comparison, no `Decimal` involved at all. |

## Pacing Interpretation Scenarios

All scenarios below use `classify_campaign_pacing(pacing: CampaignPacing) ->
CampaignPacingClass` from `src/pacing.py`. Every result is a **neutral, descriptive
pacing classification only** — none of these scenarios produces a performance/trend/
confidence classification, tracking-based assessability result, combined judgement,
`RecommendationAction`, `ReasonCode`, score, eligibility, or allocation outcome, and
none states whether overspending or underspending is desirable.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `PacingStatus` members | Exactly `UNDERSPENDING`, `ON_PACE`, `OVERSPENDING`, `NOT_AVAILABLE`, with exact values `"Under spending"`, `"On pace"`, `"Over spending"`, `"Not available"`. |
| 2 | `PACING_LOWER_THRESHOLD`/`PACING_UPPER_THRESHOLD` | Exactly `Decimal("0.90")`/`Decimal("1.10")`; both `Decimal` instances, never `float`. |
| 3 | `CampaignPacingClass` field set | Exactly `campaign_id`, `pacing_status`. |
| 4 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 5 | Attempt to mutate a `CampaignPacingClass` instance | Rejected (`frozen=True`). |
| 6 | `campaign_id` on the result | Copied exactly from the source `CampaignPacing`. |
| 7 | `pacing_status` on the result | Always a `PacingStatus` instance. |
| 8 | `classify_campaign_pacing(None)` / `classify_campaign_pacing({"pacing_ratio": ...})` (not `CampaignPacing`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 9 | `pacing_ratio = None` | `NOT_AVAILABLE`. |
| 10 | `pacing_ratio = Decimal("0")` | `UNDERSPENDING`. |
| 11 | `pacing_ratio = Decimal("0.8999")` (immediately below the lower threshold) | `UNDERSPENDING`. |
| 12 | `pacing_ratio = Decimal("0.90")` (exactly the lower threshold) | `ON_PACE`. |
| 13 | `pacing_ratio = Decimal("0.9001")` | `ON_PACE`. |
| 14 | `pacing_ratio = Decimal("1.00")` | `ON_PACE`. |
| 15 | `pacing_ratio = Decimal("1.0999")` | `ON_PACE`. |
| 16 | `pacing_ratio = Decimal("1.10")` (exactly the upper threshold) | `ON_PACE`. |
| 17 | `pacing_ratio = Decimal("1.1001")` (immediately above the upper threshold) | `OVERSPENDING`. |
| 18 | `pacing_ratio = Decimal("1000000.00")` (very large valid value) | `OVERSPENDING`. |
| 19 | `classify_campaign_pacing` source | Reads only `pacing.campaign_id`/`pacing.pacing_ratio` (AST-verified); contains no binary arithmetic operation (AST-verified); calls none of `classify_campaign_performance`/`classify_campaign_trend`/`classify_campaign_confidence`/`assess_campaign_tracking`/`calculate_campaign_pacing`/`calculate_campaign_metrics` (AST-verified). |
| 20 | Global `decimal` context mutated (`prec=2`, `ROUND_DOWN`) before calling the function, across `UNDERSPENDING`/`ON_PACE` (both boundaries)/`OVERSPENDING`/`NOT_AVAILABLE` | Every result unaffected — classification is plain `Decimal` comparison, no local context is used. |
| 21 | Google Ads/CPA vs. Meta Ads/ROAS campaigns with equal `pacing_ratio` | Same `PacingStatus`. |
| 22 | Protected vs. unprotected vs. test campaign with equal `pacing_ratio` | Same `PacingStatus` in all three. |
| 23 | Same `pacing_ratio` with different `projected_end_of_period_spend` (including `None`) | Same `PacingStatus` — `projected_end_of_period_spend` is never read. |
| 24 | Same `pacing_ratio` with widely different `spend_variance` (including negative) | Same `PacingStatus` — `spend_variance` is never read. |
| 25 | `CampaignPacingClass.model_fields` | Contains no `pacing_ratio`, `spend_variance`, `expected_spend`, `elapsed_fraction`, `elapsed_days`, `total_period_days`, `remaining_budget`, `projected_end_of_period_spend`, `performance_band`, `trend_direction`, `confidence`, `tracking_status`, `is_assessable`, `score`, `reason_code`, `recommendation_action`, `constraint`, `eligibility`, or `allocation` field. |
| 26 | `data/sample_campaigns.csv` validated, `CampaignPacing` calculated for each (`review_date=2026-08-10`, `period_start=2026-08-01`, `period_end=2026-08-31`, matching the existing Stage 4 fixture), then classified, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`); `G001`, `M001`, `G002` = `OVERSPENDING` (`pacing_ratio` ≈ `2.9455`/`2.9760`/`3.0690`); `G003` = `UNDERSPENDING` (`pacing_ratio` ≈ `0.7750`) — asserted against the exact `CampaignPacing` result, not a hard-coded rounded approximation. |
| 27 | Upstream `pacing_ratio = None` from zero elapsed time (`review_date` before `period_start`) | `NOT_AVAILABLE`. |
| 28 | Upstream `pacing_ratio = None` from zero current budget (`current_budget = Decimal("0.00")`) | `NOT_AVAILABLE`. |
| 29 | `classify_campaign_performance`, `classify_campaign_trend`, `classify_campaign_confidence`, `assess_campaign_tracking` | Unchanged behaviour after the Stage 9 additions — regression-checked. |

## Static Budget-Bound Scenarios

All scenarios below use `calculate_campaign_static_budget_room(campaign: CampaignInput)
-> CampaignStaticBudgetRoom` from `src/constraints.py`. Every result is a **static
budget-bound distance fact only** — none of these scenarios produces an effective/final
permissible budget movement, a percentage-based limit, a protection or
test-budget-floor determination, an eligibility result, a blocking flag, a score, a
recommendation, a reason code, or an allocation outcome.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignStaticBudgetRoom` field set | Exactly `campaign_id`, `room_to_static_maximum`, `room_to_static_minimum`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignStaticBudgetRoom` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied exactly from the source `CampaignInput`. |
| 5 | `room_to_static_maximum`/`room_to_static_minimum` | Always `Decimal`, never `float`. |
| 6 | `calculate_campaign_static_budget_room(None)` / `calculate_campaign_static_budget_room({"current_budget": ...})` (not `CampaignInput`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 7 | `current_budget` strictly between `minimum_budget` and `maximum_budget` (e.g. `current=1000.00`, `min=100.00`, `max=2000.00`) | `room_to_static_maximum = 1000.00`, `room_to_static_minimum = 900.00`. |
| 8 | `current_budget == minimum_budget` (e.g. `current=min=100.00`, `max=2000.00`) | `room_to_static_minimum = Decimal("0.00")`; `room_to_static_maximum = 1900.00`. |
| 9 | `current_budget == maximum_budget` (e.g. `current=max=2000.00`, `min=100.00`) | `room_to_static_maximum = Decimal("0.00")`; `room_to_static_minimum = 1900.00`. |
| 10 | `minimum_budget == current_budget == maximum_budget` | Both fields `Decimal("0.00")`. |
| 11 | `minimum_budget == current_budget == maximum_budget == Decimal("0.00")` | Both fields `Decimal("0.00")`. |
| 12 | Large valid `Decimal` currency values (e.g. `current=500000000.00`, `min=0.00`, `max=1000000000.00`) | `room_to_static_maximum = 500000000.00`, `room_to_static_minimum = 500000000.00`. |
| 13 | Non-round currency values (e.g. `current=1234.56`, `min=100.01`, `max=2345.67`) | Exact two-decimal results: `room_to_static_maximum = 1111.11`, `room_to_static_minimum = 1134.55`. |
| 14 | `calculate_campaign_static_budget_room` source | Reads only `campaign.campaign_id`/`campaign.current_budget`/`campaign.minimum_budget`/`campaign.maximum_budget` (AST-verified); calls none of `calculate_campaign_metrics`/`calculate_campaign_pacing`/`classify_campaign_performance`/`classify_campaign_trend`/`classify_campaign_confidence`/`assess_campaign_tracking`/`classify_campaign_pacing` (AST-verified); `src/constraints.py` imports none of `ReviewSetup`/`CampaignMetrics`/`CampaignPacing`/`PerformanceBand`/`TrendDirection`/`Confidence`/`TrackingStatus`/`CampaignTrackingAssessment`/`PacingStatus`/`RecommendationAction`/`ReasonCode`/`DEFAULT_MAX_CHANGE_PERCENTAGE` (AST-verified). |
| 15 | Global `decimal` context mutated (`prec=2`, `ROUND_DOWN`) before calling the function | Result unaffected — calculation runs inside its own fixed `localcontext()` (`prec=28`, `ROUND_HALF_UP`). |
| 16 | Google Ads vs. Meta Ads, otherwise identical budgets | Same `room_to_static_maximum`/`room_to_static_minimum`. |
| 17 | CPA vs. ROAS, otherwise identical budgets | Same `room_to_static_maximum`/`room_to_static_minimum`. |
| 18 | `is_protected=False` vs. `is_protected=True`, otherwise identical budgets | Same `room_to_static_maximum`/`room_to_static_minimum` — protection never read. |
| 19 | Non-test campaign vs. test campaign with a `test_budget_floor`, otherwise identical `current_budget`/`minimum_budget`/`maximum_budget` | Same `room_to_static_maximum`/`room_to_static_minimum` — `is_test_campaign`/`test_budget_floor` never read. |
| 20 | `campaign_max_change_percentage = None` vs. a supplied override, otherwise identical budgets | Same `room_to_static_maximum`/`room_to_static_minimum` — never read. |
| 21 | `CampaignStaticBudgetRoom.model_fields` / result attributes | Contains no `effective_minimum_budget`, `effective_maximum_budget`, `room_to_increase`, `room_to_decrease`, `is_protected`, `is_test_campaign`, `test_budget_floor`, `campaign_max_change_percentage`, `eligibility`, `blocked`, `score`, `recommendation_action`, `reason_code`, or `allocation` field. |
| 22 | `data/sample_campaigns.csv` validated, then each `CampaignInput` processed directly, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001`: `room_to_static_maximum=3000.00`, `room_to_static_minimum=2500.00`. `M001`: `2500.00`/`2000.00`. `G002` (protected): `3000.00`/`4000.00` — unaffected by `is_protected=True`. `G003` (test campaign, `test_budget_floor=300.00`): `800.00`/`1100.00` — the `1100.00` figure is a static-bound fact only, not an approved decrease amount; it does not authorise reducing `G003` below its `300.00` test floor. |

## Applicable Change-Percentage Resolution Scenarios

All scenarios below use `resolve_campaign_applicable_change_percentage(review:
ReviewSetup, campaign: CampaignInput) -> CampaignApplicableChangePercentage` from
`src/constraints.py`. Every result is a **neutral `Decimal` configuration fact only** —
none of these scenarios produces a monetary movement cap, a static-bound intersection,
a protection or test-budget-floor determination, an eligibility result, a score, a
recommendation, a reason code, or an allocation outcome.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignApplicableChangePercentage` field set | Exactly `campaign_id`, `applicable_max_change_percentage`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignApplicableChangePercentage` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied exactly from the source `CampaignInput`. |
| 5 | `applicable_max_change_percentage` | Always `Decimal`, never `float`, never `None`. |
| 6 | `resolve_campaign_applicable_change_percentage(None, None)` / dict inputs (not `ReviewSetup`/`CampaignInput`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 7 | `campaign_max_change_percentage=None`, `review.default_max_change_percentage=Decimal("0.35")` (a non-default value) | `applicable_max_change_percentage = Decimal("0.35")` — proves the review default is used, not a hard-coded `0.20`. |
| 8 | `campaign_max_change_percentage=Decimal("0.05")`, `review.default_max_change_percentage=Decimal("0.35")` (deliberately different values) | `applicable_max_change_percentage = Decimal("0.05")` — proves campaign-override-first precedence. |
| 9 | `campaign_max_change_percentage=Decimal("1")` (upper boundary) | `applicable_max_change_percentage = Decimal("1")`. |
| 10 | `campaign_max_change_percentage=Decimal("0.0001")` (small valid positive value) | Preserved exactly, no rounding. |
| 11 | Resolution source | Uses an explicit `is not None` check, not a truthiness fallback (AST-verified: no `BoolOp`, an `Is`/`IsNot`-against-`None` comparison is present); contains no binary arithmetic operation and no `quantize`/`ROUND_` text (AST- and source-verified). |
| 12 | Global `decimal` context mutated (`prec=2`, `ROUND_DOWN`) before calling the function, for both an override and a no-override case | Result unaffected in both cases — resolution is plain conditional selection, no `Decimal` computation occurs. |
| 13 | Google Ads vs. Meta Ads, otherwise identical | Same `applicable_max_change_percentage`. |
| 14 | CPA vs. ROAS, otherwise identical | Same `applicable_max_change_percentage`. |
| 15 | A campaign with a very small budget vs. a very large budget, otherwise identical | Same `applicable_max_change_percentage` — `current_budget`/`minimum_budget`/`maximum_budget` never read. |
| 16 | `calculate_campaign_static_budget_room` and `resolve_campaign_applicable_change_percentage` called on the same campaign | Both succeed independently; neither result contains the other's fields; Stage 10's function is neither called from nor combined with Stage 11's. |
| 17 | `is_protected=False` vs. `is_protected=True`, otherwise identical | Same `applicable_max_change_percentage` — never read. |
| 18 | Non-test campaign vs. test campaign with a `test_budget_floor`, otherwise identical | Same `applicable_max_change_percentage` — `is_test_campaign`/`test_budget_floor` never read. |
| 19 | `CampaignApplicableChangePercentage.model_fields` / result attributes | Contains no `room_to_static_maximum`, `room_to_static_minimum`, `monetary_cap`, `max_change_amount`, `effective_minimum_budget`, `effective_maximum_budget`, `is_protected`, `is_test_campaign`, `test_budget_floor`, `eligibility`, `blocked`, `score`, `recommendation_action`, `reason_code`, or `allocation` field. |
| 20 | `resolve_campaign_applicable_change_percentage` source | Reads only `campaign.campaign_id`/`campaign.campaign_max_change_percentage`/`review.default_max_change_percentage` (AST-verified); calls none of `calculate_campaign_static_budget_room`/`calculate_campaign_metrics`/`calculate_campaign_pacing`/`classify_campaign_performance`/`classify_campaign_trend`/`classify_campaign_confidence`/`assess_campaign_tracking`/`classify_campaign_pacing` (AST-verified); `src/constraints.py`'s module-level import list omits `DEFAULT_MAX_CHANGE_PERCENTAGE` and every Stage 3–9 model/enum (AST-verified — `ReviewSetup` is the one approved exception, narrowed from the prior forbidden set). |
| 21 | `data/sample_campaigns.csv` validated, a `ReviewSetup` fixture with `default_max_change_percentage=Decimal("0.20")`, then each `CampaignInput` processed directly, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001` (no override) = `0.20`. `M001` (`campaign_max_change_percentage=0.15`) = `0.15`. `G002` (no override) = `0.20`. `G003` (no override) = `0.20`. Stage 10's static-room results for all four are independently re-verified via separate `calculate_campaign_static_budget_room` calls in the same test, without combining the two stages' results into one object. |

## Raw Percentage Movement-Cap Scenarios

All scenarios below use `calculate_campaign_raw_percentage_movement_cap(campaign:
CampaignInput, applicable_percentage: CampaignApplicableChangePercentage) ->
CampaignRawPercentageMovementCap` from `src/constraints.py`. Every result is a **raw,
informational monetary fact only** — none of these scenarios produces an effective/
final permissible movement, a static-bound intersection, a protection or
test-budget-floor determination, an eligibility result, a score, a recommendation, a
reason code, or an allocation outcome.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignRawPercentageMovementCap` field set | Exactly `campaign_id`, `raw_percentage_movement_cap`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignRawPercentageMovementCap` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied exactly from the source `CampaignInput`. |
| 5 | `raw_percentage_movement_cap` | Always `Decimal`, never `float`, never `None`, always quantised to exactly two decimal places. |
| 6 | `calculate_campaign_raw_percentage_movement_cap(None, None)` / dict inputs (not `CampaignInput`/`CampaignApplicableChangePercentage`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 7 | `current_budget=3000.00`, `applicable_max_change_percentage=0.20` | Exact whole-penny result: `600.00`. |
| 8 | `current_budget=333.33`, `applicable_max_change_percentage=0.20` | `333.33 * 0.20 = 66.666` — discarded portion exceeds half a cent, rounds up to `66.67`. |
| 9 | `current_budget=1.00`, `applicable_max_change_percentage=0.004` | `0.004` — below half a cent, rounds down to `0.00`. |
| 10 | `current_budget=1.00`, `applicable_max_change_percentage=0.005` | `0.005` — an exact half-cent tie, `ROUND_HALF_UP` rounds away from zero to `0.01`. |
| 11 | `applicable_max_change_percentage=Decimal("1")` | Returns `current_budget` exactly. |
| 12 | `applicable_max_change_percentage=Decimal("0.0001")` | Handled and quantised correctly (e.g. `12345.00 * 0.0001 = 1.2345` → `1.23`). |
| 13 | `current_budget=Decimal("0.00")` | `Decimal("0.00")` — a legitimate result, not an error or eligibility judgement. |
| 14 | Matching `campaign_id` on both inputs | Calculates normally. |
| 15 | Mismatched `campaign_id` between the two inputs | Raises `ValueError("campaign_id mismatch between campaign and applicable percentage")`; no result is returned. |
| 16 | Global `decimal` context mutated (`prec=2`, `ROUND_DOWN`) before calling the function | Result unaffected — calculation runs inside its own local context. |
| 17 | Global `decimal` context mutated before calling the function | The global context's `prec`/`rounding` remain exactly as the caller set them after the function returns — no leakage from the function's local context. |
| 18 | Extreme-value regression: `current_budget=Decimal("99999999999999999999999999.99")` (28 significant digits — the largest `Currency` can hold under the default global context), `applicable_max_change_percentage=Decimal("0.036020245307579938554529107051")` | `Decimal("3602024530757993855452910.70")` — proven exact; a naive fixed `prec=28` context incorrectly returns `Decimal("3602024530757993855452910.71")` (one penny high), demonstrated and explicitly asserted against in a dedicated regression test. |
| 19 | Same extreme-value case, under a deliberately altered ambient global context (`prec=5`, `ROUND_DOWN`) | Same correct result (`...52910.70`) — proving independence from the ambient context even in the extreme case. |
| 20 | Same extreme-value case, with `applicable_max_change_percentage=Decimal("1")` | Result equals the extreme `current_budget` exactly — no significant whole-number digit is silently rounded or dropped. |
| 21 | `calculate_campaign_raw_percentage_movement_cap` source | Reads only `campaign.campaign_id`/`campaign.current_budget`/`applicable_percentage.campaign_id`/`applicable_percentage.applicable_max_change_percentage` (AST-verified); never references `ReviewSetup` or a `review` name (AST-verified); calls none of `calculate_campaign_static_budget_room`/`resolve_campaign_applicable_change_percentage`/`calculate_campaign_metrics`/`calculate_campaign_pacing`/`classify_campaign_performance`/`classify_campaign_trend`/`classify_campaign_confidence`/`assess_campaign_tracking`/`classify_campaign_pacing` (AST-verified); calls `.quantize(...)` exactly once (AST-verified); contains no `float(` conversion (source-verified). |
| 22 | Google Ads vs. Meta Ads, otherwise identical | Same `raw_percentage_movement_cap`. |
| 23 | CPA vs. ROAS, otherwise identical | Same `raw_percentage_movement_cap`. |
| 24 | Narrow vs. wide `minimum_budget`/`maximum_budget`, same `current_budget` | Same `raw_percentage_movement_cap` — static bounds never read. |
| 25 | `calculate_campaign_static_budget_room` and `calculate_campaign_raw_percentage_movement_cap` called on the same campaign | Both succeed independently; the raw-cap result contains no `room_to_static_maximum`/`room_to_static_minimum` field. |
| 26 | `is_protected=False` vs. `is_protected=True`, otherwise identical | Same `raw_percentage_movement_cap` — never read. |
| 27 | Non-test campaign vs. test campaign with a `test_budget_floor`, otherwise identical | Same `raw_percentage_movement_cap` — `is_test_campaign`/`test_budget_floor` never read. |
| 28 | `CampaignRawPercentageMovementCap.model_fields` / result attributes | Contains no `room_to_static_maximum`, `room_to_static_minimum`, `effective_minimum_budget`, `effective_maximum_budget`, `permissible_movement`, `is_protected`, `is_test_campaign`, `test_budget_floor`, `eligibility`, `blocked`, `score`, `recommendation_action`, `reason_code`, `allocation`, or `conservation` field. |
| 29 | `data/sample_campaigns.csv` validated, `default_max_change_percentage=Decimal("0.20")` `ReviewSetup` fixture, each campaign's applicable percentage resolved via Stage 11 then passed to Stage 12, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`); `G001 = 600.00`, `M001 = 375.00`, `G002 = 1000.00`, `G003 = 240.00`. Stage 10's static-room results for all four independently re-verified via separate calls in the same test, never intersected or combined with Stage 12's results. None of the four figures is described as a permissible movement. |

## Test-Floor Room Scenarios

All scenarios below use `calculate_campaign_test_floor_room(campaign: CampaignInput)
-> CampaignTestFloorRoom` from `src/constraints.py`. Every result is a **raw,
informational test-floor distance fact only** — none of these scenarios produces the
effective floor, an alternative or additional minimum, permissible decrease, an
effective directional constraint, or any combination with `minimum_budget`, Stage
10's static room, or Stage 12's raw percentage movement cap.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignTestFloorRoom` field set | Exactly `campaign_id`, `room_to_test_floor`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignTestFloorRoom` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied exactly from the source `CampaignInput`. |
| 5 | Test campaign, ordinary case (`current_budget=1200.00`, `test_budget_floor=300.00`) | `room_to_test_floor = 900.00`. |
| 6 | Test campaign, `test_budget_floor=Decimal("0.00")` | `room_to_test_floor = current_budget` exactly. |
| 7 | Test campaign, floor below `minimum_budget` | `room_to_test_floor` computed by the formula alone — `minimum_budget` never read or compared. |
| 8 | Test campaign, floor equal to `minimum_budget` | Same. |
| 9 | Test campaign, floor above `minimum_budget` (e.g. G003's actual shape) | Same. |
| 10 | Test campaign, floor equal to `current_budget` | `room_to_test_floor = Decimal("0.00")` — a legitimate result, not an error or eligibility judgement. |
| 11 | Non-test campaign (`is_test_campaign=False`, `test_budget_floor=None`) | `room_to_test_floor = None` — an explicit "not applicable" statement, never `Decimal("0.00")`, never an error. |
| 12 | `calculate_campaign_test_floor_room(None)` / dict input (not `CampaignInput`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 13 | Extreme valid `current_budget` (`Decimal("99999999999999999999999999.99")`, 28 significant digits — the largest `Currency` can hold under the default global context), `test_budget_floor=Decimal("1.00")` | Exact result with every significant whole-number digit preserved; the same extreme budget against `test_budget_floor=Decimal("0.00")` returns the full extreme budget exactly. |
| 14 | Global `decimal` context mutated (`prec=2`, `ROUND_DOWN`) before calling the function | Result unaffected — calculation runs inside its own fixed `localcontext()` (`prec=28`, `ROUND_HALF_UP`); the global context's `prec`/`rounding` remain exactly as the caller set them after the function returns. |
| 15 | `calculate_campaign_test_floor_room` source | Reads only `campaign.campaign_id`/`campaign.is_test_campaign`/`campaign.current_budget`/`campaign.test_budget_floor` (AST-verified); never references `ReviewSetup` or a `review` name (AST-verified); calls none of `calculate_campaign_static_budget_room`/`resolve_campaign_applicable_change_percentage`/`calculate_campaign_raw_percentage_movement_cap`/Stage 3–9 functions (AST-verified); contains no `.quantize(...)` call and no `float(` conversion (AST/source-verified). |
| 16 | `minimum_budget` varied, all other authorised fields identical | Same `room_to_test_floor` — never read. |
| 17 | `maximum_budget` varied, all other authorised fields identical | Same `room_to_test_floor` — never read. |
| 18 | `is_protected=False` vs. `is_protected=True`, otherwise identical | Same `room_to_test_floor` — never read. |
| 19 | Google Ads vs. Meta Ads, otherwise identical | Same `room_to_test_floor`. |
| 20 | CPA vs. ROAS, otherwise identical | Same `room_to_test_floor`. |
| 21 | `campaign_max_change_percentage` varied, otherwise identical | Same `room_to_test_floor` — never read. |
| 22 | `calculate_campaign_static_budget_room` and `calculate_campaign_test_floor_room` called on the same campaign | Both succeed independently; the test-floor result contains no `room_to_static_maximum`/`room_to_static_minimum`/`applicable_max_change_percentage`/`raw_percentage_movement_cap` field. |
| 23 | `CampaignTestFloorRoom.model_fields` / result attributes | Contains no `effective_floor`, `minimum_budget`, `room_to_static_maximum`, `room_to_static_minimum`, `raw_percentage_movement_cap`, `is_protected`, `eligibility`, `blocked`, `score`, `recommendation_action`, `reason_code`, `allocation`, or `conservation` field. |
| 24 | `data/sample_campaigns.csv` validated, each `CampaignInput` processed directly, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001`/`M001`/`G002` (all `is_test_campaign=False`) → `room_to_test_floor=None`. `G003` (`is_test_campaign=True`, `test_budget_floor=300.00`, `current_budget=1200.00`) → `room_to_test_floor=Decimal("900.00")`. Stages 10, 11, and 12's existing sample results for all four independently re-verified via separate calls in the same test, never combined or intersected with Stage 13's result. `Decimal("900.00")` for G003 is never described as a permissible decrease. |

## Protection Constraint Scenarios

All scenarios below use `resolve_campaign_protection_constraint(campaign:
CampaignInput) -> CampaignProtectionConstraint` from `src/constraints.py`. Every
result is a **neutral, decrease-specific fact only** — none of these scenarios
produces eligibility, a recommendation, a monetary movement amount, permissible
decrease, an effective directional limit, an increase-side constraint, or a
combination with Stages 10–13.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignProtectionConstraint` field set | Exactly `campaign_id`, `decrease_blocked`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignProtectionConstraint` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied exactly from the source `CampaignInput`. |
| 5 | Protected campaign (`is_protected=True`) | `decrease_blocked=True`. |
| 6 | Non-protected campaign (`is_protected=False`) | `decrease_blocked=False` — not converted to `None`; not permission to decrease. |
| 7 | `resolve_campaign_protection_constraint(None)` / dict input (not `CampaignInput`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 8 | Campaign both protected and test (`is_protected=True`, `is_test_campaign=True`, `test_budget_floor` set) | `decrease_blocked=True` — unaffected by `is_test_campaign`/`test_budget_floor`. |
| 9 | `resolve_campaign_protection_constraint` source | Reads only `campaign.campaign_id`/`campaign.is_protected` (AST-verified); never references `ReviewSetup` or a `review` name (AST-verified); calls none of Stage 10–13's or Stage 3–9's functions (AST-verified); contains no `Decimal`, `quantize`, `float(`, or binary arithmetic (source/AST-verified); no `BoolOp`-based truthiness fallback (AST-verified). |
| 10 | `current_budget` varied, otherwise identical | Same `decrease_blocked` — never read. |
| 11 | `minimum_budget` varied, otherwise identical | Same `decrease_blocked` — never read. |
| 12 | `maximum_budget` varied, otherwise identical | Same `decrease_blocked` — never read. |
| 13 | Google Ads vs. Meta Ads, otherwise identical | Same `decrease_blocked`. |
| 14 | CPA vs. ROAS, otherwise identical | Same `decrease_blocked`. |
| 15 | `campaign_max_change_percentage` varied, otherwise identical | Same `decrease_blocked` — never read. |
| 16 | `calculate_campaign_static_budget_room` and `resolve_campaign_protection_constraint` called on the same campaign | Both succeed independently; the protection result contains no `room_to_static_maximum`/`room_to_static_minimum`/`applicable_max_change_percentage`/`raw_percentage_movement_cap`/`room_to_test_floor` field. |
| 17 | `CampaignProtectionConstraint.model_fields` / result attributes | Contains no `Decimal`-typed field, no `room_to_protection_limit`, `effective_floor`, `permissible_decrease`, `eligibility`, `blocked`, `score`, `recommendation_action`, `reason_code`, `allocation`, or `conservation` field. |
| 18 | `data/sample_campaigns.csv` validated, each `CampaignInput` processed directly, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001`/`M001`/`G003` (`is_protected=False`) → `decrease_blocked=False`. `G002` (`is_protected=True`) → `decrease_blocked=True`. Stages 10, 11, 12, and 13's existing sample results for all four independently re-verified via separate calls in the same test, never combined or intersected with Stage 14's result. `decrease_blocked=False` is never described as permission to reduce a campaign; `decrease_blocked=True` is never described as eligibility, a recommendation, or final movement. |

## Test-Aware Static Decrease Room Scenarios

All scenarios below use `resolve_campaign_test_aware_static_decrease_room(static_room:
CampaignStaticBudgetRoom, test_floor_room: CampaignTestFloorRoom) ->
CampaignTestAwareStaticDecreaseRoom` from `src/constraints.py`. Every result is a
**raw, test-aware static constraint only** — none of these scenarios produces
permissible decrease, an effective decrease limit, a percentage-cap intersection, a
protection application, eligibility, a recommendation, or an allocation outcome.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignTestAwareStaticDecreaseRoom` field set | Exactly `campaign_id`, `test_aware_static_decrease_room`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignTestAwareStaticDecreaseRoom` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied from `static_room.campaign_id`, after confirming it matches `test_floor_room.campaign_id`. |
| 5 | Matching campaign IDs on both inputs | Resolves normally. |
| 6 | Mismatched campaign IDs (e.g. `"A"` vs. `"B"`) | Raises `ValueError("Campaign IDs must match when resolving test-aware static decrease room.")`; no result is resolved; neither ID is silently preferred. |
| 7 | `resolve_campaign_test_aware_static_decrease_room(None, None)` / dict inputs (not `CampaignStaticBudgetRoom`/`CampaignTestFloorRoom`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 8 | `test_floor_room.room_to_test_floor is None` (non-test campaign) | Returns `static_room.room_to_static_minimum` unchanged — never converted to `Decimal("0.00")`; the output itself is never `None`. |
| 9 | `room_to_test_floor` greater than `room_to_static_minimum` | Returns `room_to_static_minimum` (the smaller room). |
| 10 | `room_to_test_floor` equal to `room_to_static_minimum` | Returns the equal value. |
| 11 | `room_to_test_floor` smaller than `room_to_static_minimum` | Returns `room_to_test_floor` (the smaller room) — G003's actual case. |
| 12 | `room_to_test_floor = Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 13 | `room_to_static_minimum = Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 14 | Both rooms `Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 15 | Parametrised precedence sweep (five static-minimum/test-floor pairs) | Result always equals `min(room_to_static_minimum, room_to_test_floor)`. |
| 16 | `resolve_campaign_test_aware_static_decrease_room` source | Reads only `static_room.campaign_id`/`static_room.room_to_static_minimum`/`test_floor_room.campaign_id`/`test_floor_room.room_to_test_floor` (AST-verified); never references `CampaignInput` or `ReviewSetup` (AST-verified); calls none of Stage 10/13's or Stage 3–9's functions (AST-verified); contains no binary arithmetic, `quantize`, `ROUND_HALF_UP`, `CURRENCY_QUANTUM`, `localcontext`, or `float(` (source/AST-verified). |
| 17 | Global `decimal` context mutated (`prec=2`, `ROUND_DOWN`) before calling the function | Result unaffected — no arithmetic occurs; the global context's `prec`/`rounding` remain exactly as the caller set them after the function returns. |
| 18 | Extreme already-valid Stage 10/13 values (28-significant-digit `Decimal`) | Handled safely and exactly — the larger or smaller extreme value is selected unchanged, with no precision loss. |
| 19 | `calculate_campaign_static_budget_room`/`calculate_campaign_test_floor_room` not called by Stage 15 | Confirmed via AST — Stage 15 consumes their already-computed results without recalculating either room from raw budget fields. |
| 20 | `is_protected=False` vs. `is_protected=True`, same Stage 10/13 facts | Same `test_aware_static_decrease_room` — `is_protected`/`decrease_blocked` never read; no protection-based zero is calculated. |
| 21 | Campaign both test and protected | Resolved only from its Stage 10/13 facts — `resolve_campaign_protection_constraint`'s `decrease_blocked=True` for the same campaign has no bearing on the Stage 15 result. |
| 22 | `CampaignTestAwareStaticDecreaseRoom.model_fields` / result attributes | Contains no `effective_decrease_floor`, `effective_decrease_room`, `permissible_decrease`, `raw_percentage_movement_cap`, `applicable_max_change_percentage`, `decrease_blocked`, `is_protected`, `eligibility`, `blocked`, `score`, `recommendation_action`, `reason_code`, `allocation`, or `conservation` field. |
| 23 | `data/sample_campaigns.csv` validated; Stage 10 and Stage 13 results independently calculated per campaign, then passed to Stage 15, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001 = 2500.00`, `M001 = 2000.00`, `G002 = 4000.00`, `G003 = 900.00`. Stages 10–14's existing sample results independently re-verified via separate calls, never combined. For G002, `decrease_blocked=True` and `test_aware_static_decrease_room=4000.00` both hold simultaneously and separately — `4000.00` is never described as permissible decrease. For G003, `room_to_static_minimum=1100.00` and `room_to_test_floor=900.00` both remain visible; Stage 15 selects `900.00`, never described as permissible decrease. |

## Raw Increase Limit Scenarios

All scenarios below use `resolve_campaign_raw_increase_limit(static_room:
CampaignStaticBudgetRoom, raw_cap: CampaignRawPercentageMovementCap) ->
CampaignRawIncreaseLimit` from `src/constraints.py`. Every result is a **raw,
increase-specific constraint only** — none of these scenarios produces permission to
increase a budget, an effective increase, eligibility, a recommendation, or a final
movement amount.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignRawIncreaseLimit` field set | Exactly `campaign_id`, `raw_increase_limit`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignRawIncreaseLimit` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied from `static_room.campaign_id`, after confirming it matches `raw_cap.campaign_id`. |
| 5 | Matching campaign IDs on both inputs | Resolves normally. |
| 6 | Mismatched campaign IDs (e.g. `"A"` vs. `"B"`) | Raises `ValueError("Campaign IDs must match when resolving raw increase limit.")`; no result is resolved; neither ID is silently preferred. |
| 7 | `resolve_campaign_raw_increase_limit(None, None)` / dict inputs (not `CampaignStaticBudgetRoom`/`CampaignRawPercentageMovementCap`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 8 | `room_to_static_maximum` smaller than `raw_percentage_movement_cap` | Returns `room_to_static_maximum`. |
| 9 | `room_to_static_maximum` equal to `raw_percentage_movement_cap` | Returns the equal value. |
| 10 | `raw_percentage_movement_cap` smaller than `room_to_static_maximum` | Returns `raw_percentage_movement_cap`. |
| 11 | `room_to_static_maximum = Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 12 | `raw_percentage_movement_cap = Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 13 | Both values `Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 14 | Parametrised sweep (five static-maximum/raw-cap pairs) | Result always equals `min(room_to_static_maximum, raw_percentage_movement_cap)`. |
| 15 | Selected operand | Returned unchanged — equals `static_room.room_to_static_maximum` when that is the smaller value. |
| 16 | `resolve_campaign_raw_increase_limit` source | Reads only `static_room.campaign_id`/`static_room.room_to_static_maximum`/`raw_cap.campaign_id`/`raw_cap.raw_percentage_movement_cap` (AST-verified); never references `CampaignInput` or `ReviewSetup` (AST-verified); calls none of `calculate_campaign_static_budget_room`/`calculate_campaign_raw_percentage_movement_cap`/Stage 11/13/14/15's or Stage 3–9's functions (AST-verified); contains no binary arithmetic, `quantize`, `ROUND_HALF_UP`, `CURRENCY_QUANTUM`, `localcontext`, or `float(` (source/AST-verified); the campaign-ID equality guard is verified via AST to precede any Decimal selection. |
| 17 | Global `decimal` context mutated (`prec`/`rounding`) before calling the function | Result unaffected — no arithmetic occurs; the global context's `prec`/`rounding` remain exactly as the caller set them after the function returns. |
| 18 | Extreme already-valid Stage 10/12 values (28-significant-digit `Decimal`) | Handled safely and exactly — the larger or smaller extreme value is selected unchanged, with no precision loss. |
| 19 | `calculate_campaign_static_budget_room`/`calculate_campaign_raw_percentage_movement_cap` not called by Stage 16 | Confirmed via AST — Stage 16 consumes their already-computed results without recalculating either fact from raw budget/percentage fields. |
| 20 | `is_protected=False` vs. `is_protected=True`, same Stage 10/12 facts | Same `raw_increase_limit` — `is_protected`/`decrease_blocked` never read; no protection-based zero is calculated; no increase-side protection rule is inferred. |
| 21 | Non-test vs. test campaign, same Stage 10/12 facts | Same `raw_increase_limit` — `is_test_campaign`/`test_budget_floor`/`room_to_test_floor` never read; test-floor rules have no bearing on this result. |
| 22 | Campaign both protected and test | Resolved only from its Stage 10/12 facts — Stage 14's `decrease_blocked=True` and Stage 15's `test_aware_static_decrease_room` for the same campaign have no bearing on the Stage 16 result. |
| 23 | `CampaignRawIncreaseLimit.model_fields` / result attributes | Contains no `raw_decrease_limit`, `test_aware_static_decrease_room`, `decrease_blocked`, `is_protected`, `effective_increase`, `permissible_increase`, `eligibility`, `blocked`, `score`, `recommendation_action`, `reason_code`, `allocation`, or `conservation` field. |
| 24 | `data/sample_campaigns.csv` validated; Stage 10, Stage 11, and Stage 12 results independently calculated per campaign, then only Stage 10 and Stage 12 passed to Stage 16, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001=600.00`, `M001=375.00`, `G002=1000.00`, `G003=240.00`. Stages 10–15's existing sample results independently re-verified via separate calls, never combined. For G002, `decrease_blocked=True` and `raw_increase_limit=1000.00` both hold simultaneously and separately — never combined, and no increase-side protection rule is inferred. For G003, Stage 13's `room_to_test_floor=900.00` and Stage 15's `test_aware_static_decrease_room=900.00` remain decrease-specific; Stage 16's `raw_increase_limit=240.00` is unaffected by the test floor. |

## Raw Decrease Limit Scenarios

All scenarios below use `resolve_campaign_raw_decrease_limit(decrease_room:
CampaignTestAwareStaticDecreaseRoom, raw_cap: CampaignRawPercentageMovementCap) ->
CampaignRawDecreaseLimit` from `src/constraints.py`. Every result is a **raw,
decrease-specific constraint only** — none of these scenarios produces permission to
decrease a budget, an effective decrease, eligibility, a recommendation, or a final
movement amount.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignRawDecreaseLimit` field set | Exactly `campaign_id`, `raw_decrease_limit`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignRawDecreaseLimit` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied from `decrease_room.campaign_id`, after confirming it matches `raw_cap.campaign_id`. |
| 5 | Matching campaign IDs on both inputs | Resolves normally. |
| 6 | Mismatched campaign IDs (e.g. `"A"` vs. `"B"`) | Raises `ValueError("Campaign IDs must match when resolving raw decrease limit.")`; no result is resolved; neither ID is silently preferred. |
| 7 | `resolve_campaign_raw_decrease_limit(None, None)` / dict inputs (not `CampaignTestAwareStaticDecreaseRoom`/`CampaignRawPercentageMovementCap`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 8 | Stage 15 room smaller than the raw cap | Returns `test_aware_static_decrease_room`. |
| 9 | Stage 15 room equal to the raw cap | Returns the equal value. |
| 10 | Raw cap smaller than the Stage 15 room | Returns `raw_percentage_movement_cap`. |
| 11 | Stage 15 room `Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 12 | Raw cap `Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 13 | Both values `Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 14 | Parametrised sweep (five room/cap pairs) | Result always equals `min(test_aware_static_decrease_room, raw_percentage_movement_cap)`. |
| 15 | Selected operand | Returned unchanged — equals `decrease_room.test_aware_static_decrease_room` when that is the smaller value. |
| 16 | `resolve_campaign_raw_decrease_limit` source | Reads only `decrease_room.campaign_id`/`decrease_room.test_aware_static_decrease_room`/`raw_cap.campaign_id`/`raw_cap.raw_percentage_movement_cap` (AST-verified); never references `CampaignInput` or `ReviewSetup` (AST-verified); calls none of `resolve_campaign_test_aware_static_decrease_room`/`calculate_campaign_raw_percentage_movement_cap`/Stage 10/11/13/14/16's or Stage 3–9's functions (AST-verified); contains no binary arithmetic, `quantize`, `ROUND_HALF_UP`, `CURRENCY_QUANTUM`, `localcontext`, or `float(` (source/AST-verified); the campaign-ID equality guard is verified via AST to precede any Decimal selection; source text contains no reference to `minimum_budget`/`test_budget_floor`/`is_test_campaign`/`room_to_static_minimum`/`room_to_test_floor`/`current_budget`/`applicable_max_change_percentage`, confirming Stage 15's precedence is not reopened; exactly one `min()` call site is present. |
| 17 | Global `decimal` context mutated (`prec`/`rounding`) before calling the function | Result unaffected — no arithmetic occurs; the global context's `prec`/`rounding` remain exactly as the caller set them after the function returns. |
| 18 | Extreme already-valid Stage 12/15 values (28-significant-digit `Decimal`) | Handled safely and exactly — the larger or smaller extreme value is selected unchanged, with no precision loss. |
| 19 | `resolve_campaign_test_aware_static_decrease_room`/`calculate_campaign_raw_percentage_movement_cap` not called by Stage 17 | Confirmed via AST — Stage 17 consumes their already-computed results without recalculating either fact. |
| 20 | `is_protected=False` vs. `is_protected=True`, same Stage 12/15 facts | Same `raw_decrease_limit` — `is_protected`/`decrease_blocked` never read; no protection-based zero is calculated; the result is never described as usable or permissible decrease for a protected campaign. |
| 21 | Protected campaign in isolation | Still receives its neutral `raw_decrease_limit`, matching `min(test_aware_static_decrease_room, raw_percentage_movement_cap)` — not converted to zero. |
| 22 | Non-test vs. test campaign, same underlying budget facts | Stage 15's result differs (test-floor precedence applied upstream); Stage 17 intersects whichever Stage 15 value it is given, without reading `is_test_campaign`/`test_budget_floor` directly. |
| 23 | Stage 13 (`CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`) | Never accepted or called by Stage 17 — `campaign` is not a parameter name. |
| 24 | `CampaignRawIncreaseLimit`/`raw_increase_limit`/`resolve_campaign_raw_increase_limit` | Never referenced by Stage 17's source (AST-verified); `CampaignRawDecreaseLimit.model_fields` contains no `raw_increase_limit` field — no combined directional model is created. |
| 25 | `CampaignRawDecreaseLimit.model_fields` / result attributes | Contains no `raw_increase_limit`, `room_to_static_maximum`, `decrease_blocked`, `is_protected`, `effective_decrease`, `permissible_decrease`, `eligibility`, `blocked`, `score`, `recommendation_action`, `reason_code`, `allocation`, or `conservation` field. |
| 26 | `data/sample_campaigns.csv` validated; Stage 10–16 results independently calculated per campaign, then only the Stage 15 and Stage 12 result objects passed to Stage 17, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001=600.00`, `M001=375.00`, `G002=1000.00`, `G003=240.00`. Stages 10–16's existing sample results independently re-verified via separate calls, never combined. For G002, `decrease_blocked=True` and `raw_decrease_limit=1000.00` both hold simultaneously and separately — never combined, and `Decimal("1000.00")` is never described as permissible decrease. For G003, Stage 13's `room_to_test_floor=900.00` and Stage 15's `test_aware_static_decrease_room=900.00` remain unaltered; Stage 17's `raw_decrease_limit=240.00` is bound by the percentage cap, and the test-floor rule is not reopened or recalculated. |

## Effective Decrease Limit Scenarios

All scenarios below use `resolve_campaign_effective_decrease_limit(raw_decrease:
CampaignRawDecreaseLimit, protection: CampaignProtectionConstraint) ->
CampaignEffectiveDecreaseLimit` from `src/constraints.py`. Every result represents
the effective decrease limit under the currently approved static minimum-budget,
test-floor, percentage movement, and protection constraints — none of these
scenarios produces eligibility, a recommendation, a final movement amount, an
allocation, or a decision to decrease the campaign.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignEffectiveDecreaseLimit` field set | Exactly `campaign_id`, `effective_decrease_limit`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignEffectiveDecreaseLimit` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied from `raw_decrease.campaign_id`, after confirming it matches `protection.campaign_id`. |
| 5 | Matching campaign IDs on both inputs | Resolves normally. |
| 6 | Mismatched campaign IDs (e.g. `"A"` vs. `"B"`) | Raises `ValueError("Campaign IDs must match when resolving effective decrease limit.")`; no result is resolved; neither ID is silently preferred. |
| 7 | `resolve_campaign_effective_decrease_limit(None, None)` / dict inputs (not `CampaignRawDecreaseLimit`/`CampaignProtectionConstraint`) | Raises a normal Python `AttributeError` — no silent coercion. |
| 8 | Protected campaign (`decrease_blocked=True`), positive raw decrease value | Returns `Decimal("0.00")`. |
| 9 | Unprotected campaign (`decrease_blocked=False`), positive raw decrease value | Returns the raw value unchanged. |
| 10 | Protected campaign, raw decrease value already `Decimal("0.00")` | Returns `Decimal("0.00")`. |
| 11 | Unprotected campaign, raw decrease value already `Decimal("0.00")` | Returns the existing zero unchanged. |
| 12 | `decrease_blocked` at every value (`True`/`False`), exhaustive parametrised sweep | `True` always yields `Decimal("0.00")`; `False` always yields the raw value unchanged — no `BoolOp`/truthiness fallback alters the mapping (AST-verified). |
| 13 | Protected result's `Decimal` tuple | Equals `Decimal("0.00").as_tuple()` exactly — the two-decimal currency exponent is preserved, never `Decimal("0")`'s zero-exponent tuple. |
| 14 | Protected campaign | Never returns `None`; never raises. |
| 15 | Unprotected operand | Returned unchanged — equals `raw_decrease.raw_decrease_limit` by identity of value. |
| 16 | `resolve_campaign_effective_decrease_limit` source | Reads only `raw_decrease.campaign_id`/`raw_decrease.raw_decrease_limit`/`protection.campaign_id`/`protection.decrease_blocked` (AST-verified); never references `CampaignInput` or `ReviewSetup` (AST-verified); calls none of `resolve_campaign_raw_decrease_limit`/`resolve_campaign_protection_constraint`/Stage 10/11/12/13/15/16/3–9's functions (AST-verified); contains no binary arithmetic, `quantize`, `ROUND_HALF_UP`, `CURRENCY_QUANTUM`, `localcontext`, or `float(` (source/AST-verified); the campaign-ID equality guard is verified via AST to precede any Boolean/Decimal selection; source text contains no reference to `is_protected`/`current_budget`/`minimum_budget`/`maximum_budget`/`test_budget_floor`/`is_test_campaign`/`applicable_max_change_percentage`/`room_to_static_minimum`/`room_to_test_floor`/`test_aware_static_decrease_room`/`raw_percentage_movement_cap`, confirming no upstream fact is reopened. |
| 17 | Global `decimal` context mutated (`prec`/`rounding`) before calling the function, for both the protected and unprotected branches | Result unaffected in both branches — no arithmetic occurs; the global context's `prec`/`rounding` remain exactly as the caller set them after the function returns. |
| 18 | Extreme already-valid Stage 17 value (28-significant-digit `Decimal`), unprotected | Passed through unchanged, no precision loss. |
| 19 | Extreme already-valid Stage 17 value, protected | Becomes `Decimal("0.00")` regardless of magnitude. |
| 20 | `resolve_campaign_raw_decrease_limit`/`resolve_campaign_protection_constraint` not called by Stage 18 | Confirmed via AST — Stage 18 consumes their already-computed results without recalculating either fact. |
| 21 | `CampaignRawIncreaseLimit`/`raw_increase_limit`/`resolve_campaign_raw_increase_limit` | Never referenced by Stage 18's source (AST-verified); no `effective_increase_limit` field or `CampaignEffectiveIncreaseLimit` model exists anywhere in `src/constraints.py`; protected status is never given increase-side meaning; no combined directional result is created. |
| 22 | Protected test campaign (synthetic fixture: `is_protected=True`, `is_test_campaign=True`, `test_budget_floor` set) | Produces `Decimal("0.00")` — Stage 15's test-floor precedence and Stage 14's protection are each independently resolved upstream and simply consumed, never recalculated inside Stage 18. |
| 23 | Stage 14 `CampaignProtectionConstraint.decrease_blocked` and Stage 17 `CampaignRawDecreaseLimit.raw_decrease_limit`, after resolving Stage 18 | Both remain unchanged on their own frozen objects — Stage 18 never mutates either input. |
| 24 | `CampaignEffectiveDecreaseLimit.model_fields` / result attributes | Contains no `raw_decrease_limit`, `decrease_blocked`, `raw_increase_limit`, `effective_increase_limit`, `eligible`, `eligibility`, `recommendation_action`, `reason_code`, `score`, `allocation`, or `conservation` field. |
| 25 | `effective_decrease_limit == Decimal("0.00")` | Does not imply whole-campaign ineligibility — no eligibility field exists anywhere on the result, and the zero states only that no decrease room remains under this constraint; `MAINTAIN`/`INCREASE` eligibility remains an entirely open, later-stage question. |
| 26 | `data/sample_campaigns.csv` validated; Stage 10–17 results independently calculated per campaign, then only the Stage 17 and Stage 14 result objects passed to Stage 18, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001=600.00`, `M001=375.00`, `G002=0.00`, `G003=240.00`. Stages 10–17's existing sample results independently re-verified via separate calls, never combined. For G002: `decrease_blocked=True`, `raw_decrease_limit=1000.00`, and `effective_decrease_limit=0.00` all hold simultaneously and separately; Stage 17 remains unchanged; no increase-side rule is applied (`raw_increase_limit=1000.00` unaffected); zero is not described as whole-campaign ineligibility. For G003 (test campaign, unprotected): `raw_decrease_limit=240.00` passes through unchanged to `effective_decrease_limit=240.00`, and Stage 15's test-floor logic is not reopened. |

## Campaign Action Availability Scenarios

All scenarios below use `resolve_campaign_action_availability(campaign:
CampaignInput, tracking: CampaignTrackingAssessment, raw_increase:
CampaignRawIncreaseLimit, effective_decrease: CampaignEffectiveDecreaseLimit) ->
CampaignActionAvailability` from `src/availability.py` (`tests/test_availability.py`
— a dedicated test file, not an extension of `tests/test_constraints.py`). Every
result represents mechanical, operational availability only — none of these
scenarios produces suitability, a recommendation, `HOLD`, a score, a ranking, a
reason code, or an allocation.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `CampaignActionAvailability` field set | Exactly `campaign_id`, `increase_available`, `maintain_available`, `reduce_available`. |
| 2 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 3 | Attempt to mutate a `CampaignActionAvailability` instance | Rejected (`frozen=True`). |
| 4 | `campaign_id` on the result | Copied from `campaign.campaign_id`, after confirming it matches `tracking.campaign_id`, `raw_increase.campaign_id`, and `effective_decrease.campaign_id`. |
| 5 | All four IDs equal | Resolves normally. |
| 6 | `tracking.campaign_id` mismatched | Raises `ValueError("Campaign IDs must match when resolving action availability.")`. |
| 7 | `raw_increase.campaign_id` mismatched | Raises the same exact `ValueError`. |
| 8 | `effective_decrease.campaign_id` mismatched | Raises the same exact `ValueError`. |
| 9 | Multiple inputs mismatched simultaneously | Raises the same exact `ValueError` — no per-object mismatch reporting, no result returned, no ID silently preferred. |
| 10 | ID-equality guard | Verified via AST to be the first statement, preceding any read of `campaign.status`/`tracking.is_assessable`/either Decimal comparison. |
| 11 | `resolve_campaign_action_availability(None, None, None, None)` / dict inputs | Raises a normal Python `AttributeError` — no silent coercion. |
| 12 | Active, assessable, positive increase, positive decrease | `(True, True, True)`. |
| 13 | Active, assessable, zero increase, positive decrease | `(False, True, True)`. |
| 14 | Active, assessable, positive increase, zero decrease | `(True, True, False)`. |
| 15 | Active, assessable, both zero | `(False, True, False)`. |
| 16 | Active, unassessable, both positive | `(False, True, False)` — `MAINTAIN` unaffected. |
| 17 | Active, unassessable, every zero/positive directional combination (parametrised) | Directional limits never override the assessability gate; `increase_available`/`reduce_available` always `False`, `maintain_available` always `True`. |
| 18 | Paused, assessable, positive limits | `(False, False, False)`. |
| 19 | Paused, unassessable, positive limits | `(False, False, False)`. |
| 20 | Paused, zero limits | `(False, False, False)`. |
| 21 | Paused campaign | Always receives one `CampaignActionAvailability` object — never omitted, never an error, never `HOLD`, never a reason code. |
| 22 | `Healthy`/assessable tracking, via the real `assess_campaign_tracking` path | Behaves per capacity — `is_assessable=True` confirmed independently. |
| 23 | `Warning`/assessable tracking, via the real `assess_campaign_tracking` path | Behaves per capacity — `is_assessable=True` confirmed (inherited from Stage 8, not re-derived). |
| 24 | `Unreliable`/unassessable tracking, via the real `assess_campaign_tracking` path | Blocks both `increase_available` and `reduce_available`; `maintain_available` remains `True`. |
| 25 | `resolve_campaign_action_availability` source | Reads only `campaign.campaign_id`/`campaign.status`, `tracking.campaign_id`/`tracking.is_assessable`, `raw_increase.campaign_id`/`raw_increase.raw_increase_limit`, `effective_decrease.campaign_id`/`effective_decrease.effective_decrease_limit` — exactly eight authorised field accesses (AST-verified); never references `tracking_status` (source-verified); calls none of `assess_campaign_tracking`/`resolve_campaign_raw_increase_limit`/`resolve_campaign_effective_decrease_limit`/any other Stage 1–18 production function (AST-verified); contains no binary arithmetic, `quantize`, `ROUND_HALF_UP`, `CURRENCY_QUANTUM`, `localcontext`, `float(`, `abs(`, `max(`, or `min(` (source/AST-verified). |
| 26 | `Decimal("0.00")` exactly, for either limit | Makes that direction unavailable. |
| 27 | `Decimal("0.01")` (smallest positive currency amount), for either limit | Makes that direction available when status/assessability gates pass. |
| 28 | Extreme valid positive `Decimal` values (28 significant digits), for either limit | Remain comparable; direction available when other gates pass. |
| 29 | Global `decimal` context mutated (`prec`/`rounding`) before calling the function | Result unaffected; the global context's `prec`/`rounding` remain exactly as the caller set them after the function returns. |
| 30 | Protected active campaign, positive raw increase, zero effective decrease | `increase_available=True` (protection has no increase-side effect); `reduce_available=False` (already protection-adjusted upstream at Stage 18); Stage 19 never reads `is_protected`/`decrease_blocked` directly. |
| 31 | Test campaign, positive limits, active and assessable | `(True, True, True)`; Stage 19 never reads `is_test_campaign`/`test_budget_floor` directly — the test-floor effect is already fully absorbed into `effective_decrease_limit`. |
| 32 | Synthetic campaign both protected and test | Follows only the already-computed Stage 16/18 capacities; no new interaction is introduced. |
| 33 | `PerformanceBand`/`TrendDirection`/`Confidence`/`PacingStatus`/`BusinessPriority`/`RecommendationAction`/`ReasonCode` | Never referenced anywhere in `src/availability.py`'s source (AST-verified) or imported into the module (`hasattr` on the module confirms absence). |
| 34 | `CampaignActionAvailability.model_fields` / result attributes | Contains no `hold_available`, `is_eligible`, `eligible`, `eligibility`, `score`, `recommendation`, `recommendation_action`, `reason_code`, `allocation`, `conservation`, `raw_increase_limit`, or `effective_decrease_limit` field. |
| 35 | `data/sample_campaigns.csv` validated; Stage 8/10–18 results independently calculated per campaign, then only the four approved Stage 19 inputs passed, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001=(True, True, True)`, `M001=(True, True, True)`, `G002=(True, True, False)`, `G003=(True, True, True)`. For G002: `status=Active`, `tracking.is_assessable=True`, `raw_increase_limit=1000.00`, `effective_decrease_limit=0.00` independently re-verified; no protection field is read; no action is recommended anywhere. |
| 36 | Synthetic integration: Paused campaign | `(False, False, False)`. |
| 37 | Synthetic integration: unreliable-tracking campaign | `(False, True, False)`. |
| 38 | Synthetic integration: warning-tracking campaign | Matches capacity-only outcome; `maintain_available=True`. |
| 39 | Synthetic integration: both directional limits zero | `(False, True, False)`. |
| 40 | Synthetic integration: protected-and-test campaign | `reduce_available=False`; `increase_available` matches the already-computed raw increase capacity; `maintain_available=True`. |

## Campaign Action Suitability Scenarios

All scenarios below use `resolve_campaign_action_suitability(performance:
CampaignPerformanceClass, trend: CampaignTrendClass, availability:
CampaignActionAvailability) -> CampaignActionSuitability` from
`src/suitability.py` (`tests/test_suitability.py` — a dedicated test file, not
an extension of `tests/test_availability.py` or `tests/test_constraints.py`).
Every result is a categorical directional signal only — none of these scenarios
produces a recommendation, `RecommendationAction`, `HOLD`, a numeric score, a
ranking, a reason code, or an allocation.

| # | Scenario | Expected outcome |
|---|----------|-------------------|
| 1 | `Suitability` members | Exactly `SUITABLE`/`"Suitable"`, `NEUTRAL`/`"Neutral"`, `UNSUITABLE`/`"Unsuitable"`, `NOT_APPLICABLE`/`"Not Applicable"`; no numeric base class; no `__lt__`/`__gt__`/`__le__`/`__ge__` defined; disjoint from `RecommendationAction`'s values; no `HOLD` member. |
| 2 | `CampaignActionSuitability` field set | Exactly `campaign_id`, `increase_suitability`, `maintain_suitability`, `reduce_suitability`. |
| 3 | Construct with an unknown field | Rejected (`extra="forbid"`). |
| 4 | Attempt to mutate a `CampaignActionSuitability` instance | Rejected (`frozen=True`). |
| 5 | `campaign_id` on the result | Copied from `performance.campaign_id`, after confirming it matches `trend.campaign_id` and `availability.campaign_id`. |
| 6 | All three IDs equal | Resolves normally. |
| 7 | `trend.campaign_id` mismatched | Raises `ValueError("Campaign IDs must match when resolving action suitability.")`. |
| 8 | `availability.campaign_id` mismatched | Raises the same exact `ValueError`. |
| 9 | Multiple inputs mismatched simultaneously | Raises the same exact `ValueError` — no per-object mismatch reporting, no result returned, no ID silently preferred. |
| 10 | ID-equality guard | Verified via AST to be the first statement, preceding any `performance_band`/`trend_direction` read, rule-table lookup, or availability-field read. |
| 11–19 | All nine `PerformanceBand`×`TrendDirection` combinations, all three actions available | `ABOVE_TARGET`+`IMPROVING`=`(SUITABLE, NEUTRAL, UNSUITABLE)`; `ABOVE_TARGET`+`STABLE`=`(NEUTRAL, NEUTRAL, NEUTRAL)`; `ABOVE_TARGET`+`DECLINING`=`(NEUTRAL, NEUTRAL, NEUTRAL)`; `ON_TARGET`+`IMPROVING`=`(NEUTRAL, NEUTRAL, NEUTRAL)`; `ON_TARGET`+`STABLE`=`(NEUTRAL, SUITABLE, NEUTRAL)`; `ON_TARGET`+`DECLINING`=`(NEUTRAL, NEUTRAL, NEUTRAL)`; `BELOW_TARGET`+`IMPROVING`=`(NEUTRAL, NEUTRAL, NEUTRAL)`; `BELOW_TARGET`+`STABLE`=`(NEUTRAL, NEUTRAL, NEUTRAL)`; `BELOW_TARGET`+`DECLINING`=`(UNSUITABLE, NEUTRAL, SUITABLE)`. |
| 20 | Increase unavailable only | `increase_suitability=NOT_APPLICABLE`; maintain/reduce follow the base table. |
| 21 | Maintain unavailable only | `maintain_suitability=NOT_APPLICABLE`; increase/reduce follow the base table. |
| 22 | Reduce unavailable only | `reduce_suitability=NOT_APPLICABLE`; increase/maintain follow the base table. |
| 23 | All three unavailable | All three `NOT_APPLICABLE`. |
| 24 | Only maintain available | increase/reduce `NOT_APPLICABLE`; maintain follows the base table. |
| 25 | Availability override in a diagonal cell (e.g. `ABOVE_TARGET`+`IMPROVING`, reduce unavailable) | `reduce_suitability=NOT_APPLICABLE`, never `UNSUITABLE`. |
| 26 | Availability override in a conflict cell (e.g. `ABOVE_TARGET`+`STABLE`, increase unavailable) | `increase_suitability=NOT_APPLICABLE`, not `NEUTRAL`. |
| 27 | Unavailable direction | Never becomes `UNSUITABLE` — confirmed explicitly even where the base table would otherwise say `UNSUITABLE`. |
| 28 | Available conflict cells | Remain `NEUTRAL` for all three directions. |
| 29 | Paused campaign, via the real Stage 8/10–19 production path | `CampaignActionAvailability` = `(False, False, False)`; Stage 20 output = all three `NOT_APPLICABLE`. |
| 30 | Active, unassessable (`TrackingStatus.UNRELIABLE`), via the real production path | `increase_available=False`, `reduce_available=False`, `maintain_available=True`; Stage 20 returns `NOT_APPLICABLE` for increase/reduce, and the base-table result for maintain. |
| 31 | Protected active campaign, via the real production path | `reduce_available=False`; Stage 20 returns `NOT_APPLICABLE` for reduce and base-table results for increase/maintain; `is_protected`/`decrease_blocked` never read directly by Stage 20. |
| 32 | Test campaign, via the real production path | All three directions available; Stage 20 returns base-table results for all three. |
| 33 | Synthetic campaign both protected and test | Follows only the already-computed Stage 19 availability values supplied — no new interaction. |
| 34 | `resolve_campaign_action_suitability` source | Reads only `performance.campaign_id`/`performance.performance_band`, `trend.campaign_id`/`trend.trend_direction`, `availability.campaign_id`/`availability.increase_available`/`availability.maintain_available`/`availability.reduce_available` — exactly eight authorised field accesses (AST-verified); never references `performance_ratio`/`weighted_performance_ratio`/`trend_delta` (source-verified); calls none of `classify_campaign_performance`/`classify_campaign_trend`/`resolve_campaign_action_availability`/any other Stage 1–19 production function (AST-verified); contains no binary arithmetic, no `float(` conversion (source/AST-verified). |
| 35 | `Confidence`/`CampaignConfidenceClass`/`PacingStatus`/`CampaignPacingClass`/`BusinessPriority`/`CampaignTrackingAssessment`/`RecommendationAction`/`ReasonCode`/`Decimal` | Never referenced anywhere in `src/suitability.py`'s source (AST-verified) or imported into the module (`hasattr` on the module confirms absence). |
| 36 | `CampaignActionSuitability.model_fields` / result attributes | Contains no `score`, `recommendation_action`, `recommendation`, `hold`, `reason_code`, `confidence`, `pacing_status`, `business_priority`, `allocation`, `conservation`, `rank`, `increase_available`, `maintain_available`, or `reduce_available` field. |
| 37 | `data/sample_campaigns.csv` validated; Stage 5/6/19 results independently calculated per campaign through the real production path, then only those three results passed, iterating in the test (no production batch function) | Order preserved (`G001`, `M001`, `G002`, `G003`). `G001`: `ON_TARGET`/`STABLE`/`(True,True,True)` → `(NEUTRAL, SUITABLE, NEUTRAL)`. `M001`: same shape → `(NEUTRAL, SUITABLE, NEUTRAL)`. `G002` (protected): `ABOVE_TARGET`/`IMPROVING`/`(True,True,False)` → `(SUITABLE, NEUTRAL, NOT_APPLICABLE)` — `REDUCE` is `NOT_APPLICABLE`, never `UNSUITABLE`; protection is never read directly; `INCREASE` being `SUITABLE` does not select `RecommendationAction.INCREASE` (no such field exists). `G003` (test): `ON_TARGET`/`STABLE`/`(True,True,True)` → `(NEUTRAL, SUITABLE, NEUTRAL)`. |
| 38 | Synthetic integration: all six conflicting/mixed `PerformanceBand`×`TrendDirection` combinations, all available | All three directions `NEUTRAL` in every case. |
| 39 | Synthetic integration: every availability pattern (8 combinations of the three Booleans) applied to a conflict cell | Each direction is `NEUTRAL` when available and `NOT_APPLICABLE` when unavailable, independently per direction. |

## Allocation Scenarios

> Pending a later Sprint 1 stage.

## Approval / Audit Scenarios

> Pending a later Sprint 1 stage.
