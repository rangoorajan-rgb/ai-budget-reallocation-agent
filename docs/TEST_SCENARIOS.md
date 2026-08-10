# Test Scenarios

> Sprint 1, Development Stage 6 populates the Trend Classification Scenarios section
> below, backed by `tests/test_trend_classification.py` (29 tests), in addition to the
> Stage 5 Performance Classification Scenarios (`tests/test_classification.py`, 23
> tests), the Stage 4 Pacing Calculation Scenarios (`tests/test_pacing.py`, 30 tests),
> the Stage 3 Metric Calculation Scenarios (`tests/test_metrics.py`, 28 tests), and the
> Stage 2 Validation Scenarios (`tests/test_validation.py`, 44 tests). Allocation and
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

## Allocation Scenarios

> Pending a later Sprint 1 stage.

## Approval / Audit Scenarios

> Pending a later Sprint 1 stage.
