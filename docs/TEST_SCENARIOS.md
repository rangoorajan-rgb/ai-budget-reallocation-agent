# Test Scenarios

> Sprint 1, Development Stage 2 populates the Validation Scenarios section below, backed
> by `tests/test_validation.py` (44 tests). Metric, Allocation, and Approval/Audit
> scenarios are pending later stages.

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

> Pending a later Sprint 1 stage.

## Allocation Scenarios

> Pending a later Sprint 1 stage.

## Approval / Audit Scenarios

> Pending a later Sprint 1 stage.
