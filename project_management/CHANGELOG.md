# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Initialized repository structure for the AI Budget Reallocation Agent: `src/`, `tests/`,
  `data/`, `audit_records/`, `docs/`, `assets/`, and `project_management/` directories with
  placeholder modules and documentation.
- Root project files: `app.py`, `config.py`, `requirements.txt`, `pyproject.toml`,
  `README.md`, `LICENSE` (MIT, 2026 Rangoo Rajan), `.gitignore`, `.env.example`.
- Project-management documentation: master project plan, current sprint tracker, decisions
  log, and this changelog.
- Sprint 1, Development Stage 1: frozen enumerations in `src/constants.py` (`Platform`,
  `KPIType`, `CampaignStatus`, `TrackingStatus`, `BusinessPriority`, `RecommendationAction`,
  `Confidence`, `ReviewStatus`, `ValidationSeverity`, `ReasonCode`) plus nine frozen
  numerical constants (`DEFAULT_MAX_CHANGE_PERCENTAGE`, `TREND_THRESHOLD`,
  `SEVEN_DAY_WEIGHT`, `TWENTY_EIGHT_DAY_WEIGHT`, `INCREASE_THRESHOLD`,
  `MAINTAIN_THRESHOLD`, `MINIMUM_CONVERSIONS`, `HIGH_CONFIDENCE_CONVERSIONS`,
  `CURRENCY_QUANTUM`).
- Sprint 1, Development Stage 1: exactly two Pydantic v2 input models in `src/models.py`
  (`ReviewSetup`, `CampaignInput`) with currency fields quantised to `CURRENCY_QUANTUM` via
  `ROUND_HALF_UP`, KPI/percentage fields left unquantised, conventional boolean parsing for
  `is_protected`/`is_test_campaign`, and full model-level structural validation (budget
  bounds, spend/conversion ordering, period ordering, reserve-vs-budget, percentage bounds,
  test-budget-floor requiredness).
- Sprint 1, Development Stage 1: exact 20-field `CampaignInput` CSV schema;
  `data/campaign_template.csv` (header only) and `data/sample_campaigns.csv` (4 synthetic
  rows covering an active Google Ads CPA campaign, an active Meta Ads ROAS campaign, a
  protected active campaign, and a test campaign with a `test_budget_floor`).
- Sprint 1, Development Stage 1: `tests/test_models.py` (92 tests) covering enum values,
  frozen constants, model structural rules, currency quantisation, conventional boolean
  parsing, and CSV-schema consistency.
- Updated `docs/DATA_DICTIONARY.md` and `docs/DECISION_RULES.md` with the CSV schema,
  `ReviewSetup` fields, approved enums, and the nine frozen constants; added
  `pythonpath = ["."]` to `pyproject.toml` so `src` imports resolve under pytest; pinned
  `pydantic>=2,<3` in `requirements.txt`.

### Fixed
- Corrected an earlier draft of this stage that had used unapproved 24-field/renamed
  `CampaignInput` columns, `SCREAMING_SNAKE` CSV enum values instead of approved
  human-readable values, an unauthorised `ValidationIssue` model, a blanket rejection of
  `float` input, and an incorrect "Sprint 2" classification for this work.

- Sprint 1, Development Stage 2: added `ValidationCode` enum to `src/constants.py`
  (`INVALID_REVIEW_FIELD`, `EMPTY_FILE`, `INVALID_HEADER`, `NO_CAMPAIGN_ROWS`,
  `MALFORMED_ROW`, `INVALID_CAMPAIGN_FIELD`, `DUPLICATE_CAMPAIGN_ID`), distinct from
  `ReasonCode`. `src/models.py` unchanged.
- Sprint 1, Development Stage 2: implemented `src/validation.py` — `ValidationIssue` and
  `ValidationReport` models (with `error_count`/`warning_count`/`is_valid` computed from
  `issues`, not independently settable); `validate_review_setup(data)` translating
  `ReviewSetup`'s `pydantic.ValidationError` into `INVALID_REVIEW_FIELD` issues; and
  `validate_campaign_csv(stream)` (stdlib `csv`, caller-owned stream, never closed)
  performing exact-header validation (`INVALID_HEADER`, derived from
  `CampaignInput.model_fields`, no manually duplicated header list), row-shape validation
  (`MALFORMED_ROW`), per-row `CampaignInput` translation (`INVALID_CAMPAIGN_FIELD`) with
  physical one-based line numbers, empty-file/no-row handling (`EMPTY_FILE`,
  `NO_CAMPAIGN_ROWS`), and case-sensitive duplicate `campaign_id` detection among
  structurally valid rows (`DUPLICATE_CAMPAIGN_ID`, every occurrence flagged and
  excluded). All Stage 2 issues are `ERROR` severity; no new warning rules were added.
  Also catches a real, empirically confirmed `decimal.DecimalException` leak from the
  frozen `Currency` type's quantisation (e.g. for `Decimal("1E+30")`), reporting it safely
  instead of leaking the raw exception, without modifying `src/models.py`.
- Sprint 1, Development Stage 2: `tests/test_validation.py` (44 tests) covering
  `ValidationIssue`/`ValidationReport` construction and derived fields, review validation,
  CSV header/row/duplicate handling, and physical line-number correctness. `data/
  sample_campaigns.csv` validates with 4 campaigns and zero issues; `data/
  campaign_template.csv` correctly yields one `NO_CAMPAIGN_ROWS` issue. Full suite: 136
  tests passing (92 Stage 1 + 44 Stage 2).
- Updated `docs/DATA_DICTIONARY.md` (`ValidationIssue`/`ValidationReport` fields),
  `docs/DECISION_RULES.md` (frozen Stage 2 validation rules and `ValidationCode` table),
  and `docs/TEST_SCENARIOS.md` (43 concrete Stage 2 scenarios).

- Sprint 1, Development Stage 3: implemented `src/metrics.py` — `CampaignMetrics` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `performance_ratio_7d`,
  `performance_ratio_28d`, `weighted_performance_ratio`, `trend_delta` — facts only, no
  KPI type, raw KPI values, conversions, confidence, trend label, recommendation action,
  reason code, score, or budget field) and `calculate_campaign_metrics(campaign:
  CampaignInput) -> CampaignMetrics`. Direction-normalised performance ratio:
  `kpi_actual / kpi_target` for `ROAS`, `kpi_target / kpi_actual` for `CPA`, so `> 1`
  always means better than target for both KPI types. Weighted performance ratio using
  the existing frozen `SEVEN_DAY_WEIGHT`/`TWENTY_EIGHT_DAY_WEIGHT`; relative trend delta
  between the two normalised ratios. `INCREASE_THRESHOLD`, `MAINTAIN_THRESHOLD`, and
  `TREND_THRESHOLD` are deliberately not applied — Stage 3 calculates facts only. Every
  calculation runs inside an explicit `decimal.localcontext()` (`prec=28`,
  `ROUND_HALF_UP`), isolated from a mutated global context; no quantisation, no `float`,
  no `CURRENCY_QUANTUM`, no new rounding/ratio constant. `src/constants.py`,
  `src/models.py`, and `src/validation.py` are unchanged.
- Sprint 1, Development Stage 3: `tests/test_metrics.py` (28 tests) covering result-model
  shape/immutability, ROAS and CPA ratio calculation, direction-normalisation parity
  between KPI types, the weighted-ratio and trend-delta formulas (including a relative-
  not-subtractive trend proof), Decimal precision-28/ROUND_HALF_UP behaviour (including a
  mutated-global-context isolation proof), integration with `validate_campaign_csv` over
  `data/sample_campaigns.csv` (exact hand-calculated values, order preserved), and scope
  boundaries (no recommendation/confidence/reason-code/trend-label/budget field). Full
  suite: 164 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignMetrics` fields), `docs/DECISION_RULES.md`
  (frozen Stage 3 metric-calculation rules; trend interpretation and conversion-volume
  confidence explicitly re-confirmed as pending classification), and
  `docs/TEST_SCENARIOS.md` (27 concrete Stage 3 scenarios).

- Sprint 1, Development Stage 4: implemented `src/pacing.py` — `CampaignPacing` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `elapsed_days`, `total_period_days`,
  `elapsed_fraction`, `expected_spend`, `spend_variance`, `pacing_ratio`,
  `remaining_budget`, `projected_end_of_period_spend` — facts only, no pacing status,
  label, classification, confidence, recommendation, reason code, score, eligibility, or
  allocation field) and `calculate_campaign_pacing(review: ReviewSetup, campaign:
  CampaignInput) -> CampaignPacing`. Inclusive date counting
  (`total_period_days = (period_end - period_start).days + 1`, avoiding a zero
  denominator for the already-valid one-day-period case); `elapsed_days` clamped to
  `[0, total_period_days]` since `review_date` has no frozen relationship to the period
  boundaries. Linear expected-spend assumption; `pacing_ratio` computed from the
  unquantised internal expected spend so penny rounding cannot distort it; public
  monetary fields quantised to the existing `CURRENCY_QUANTUM`. `pacing_ratio`/
  `projected_end_of_period_spend` are `None` only on their exact zero-denominator
  condition (`current_budget = 0.00` or `elapsed_days = 0` / `elapsed_fraction = 0`) —
  never a `0/0` sentinel. `remaining_budget` is structurally non-negative given the
  already-frozen `spend_to_date <= current_budget`. Every calculation runs inside an
  explicit `decimal.localcontext()` (`prec=28`, `ROUND_HALF_UP`), isolated from a mutated
  global context; no `float`, no new pacing/ratio/rounding/date constant.
  `src/constants.py`, `src/models.py`, `src/validation.py`, and `src/metrics.py` are
  unchanged; `src/pacing.py` imports neither `CampaignMetrics` nor any later-stage
  module, and never uses `platform`, `kpi_type`, KPI values, or performance/trend/
  conversion-volume constants — Stage 4 is independent of Stage 3.
- Sprint 1, Development Stage 4: `tests/test_pacing.py` (30 tests) covering result-model
  shape/immutability, inclusive date arithmetic and clamping (first/middle/last day,
  before/after the period, one-day periods, a leap-year February), the exact-on-pace/
  below-pace/above-pace worked examples, zero-denominator `None` behaviour, Decimal
  precision-28/ROUND_HALF_UP behaviour (including a mutated-global-context isolation
  proof and a proof that `pacing_ratio` uses the unquantised expected spend), integration
  with `validate_campaign_csv` over `data/sample_campaigns.csv` (exact hand-calculated
  values, order preserved), and scope boundaries (no performance/status/confidence/
  recommendation/reason-code/score field; no `CampaignMetrics` import). Full suite: 194
  tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30 Stage 4).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignPacing` fields), `docs/DECISION_RULES.md`
  (frozen Stage 4 pacing-calculation rules; pacing interpretation explicitly confirmed as
  pending a later classification/constraints stage), and `docs/TEST_SCENARIOS.md` (30
  concrete Stage 4 scenarios).

- Sprint 1, Development Stage 5: implemented `src/classification.py` — `PerformanceBand`
  enum (`ABOVE_TARGET`, `ON_TARGET`, `BELOW_TARGET` — deliberately distinct from
  `RecommendationAction`) and `CampaignPerformanceClass` (frozen, immutable,
  `extra="forbid"`: `campaign_id`, `performance_band` only) and
  `classify_campaign_performance(metrics: CampaignMetrics) -> CampaignPerformanceClass`.
  Classifies `weighted_performance_ratio` only, using the existing frozen
  `INCREASE_THRESHOLD`/`MAINTAIN_THRESHOLD`, with the threshold value belonging to the
  higher band (`>= INCREASE_THRESHOLD` → `ABOVE_TARGET`; `>= MAINTAIN_THRESHOLD` →
  `ON_TARGET`; otherwise `BELOW_TARGET`). Direct `Decimal` comparison only — no
  arithmetic, quantisation, `float`, or local `decimal` context. Depends only on
  `CampaignMetrics`; does not import `CampaignInput`, `CampaignPacing`, `ReviewSetup`,
  `RecommendationAction`, `Confidence`, or `ReasonCode`, and contains no KPI-specific
  branching (Stage 3 already normalised CPA/ROAS direction). Scoped deliberately
  narrower than "classification" as named in `MASTER_PROJECT_PLAN.md`: trend
  classification, conversion-volume confidence, and tracking-status interpretation are
  each deferred to a later stage, since each has its own unresolved formula/boundary
  question that would otherwise require inventing a rule. `src/constants.py`,
  `src/models.py`, `src/validation.py`, `src/metrics.py`, and `src/pacing.py` are
  unchanged.
- Sprint 1, Development Stage 5: `tests/test_classification.py` (23 tests) covering
  result-model shape/immutability, exact threshold-boundary equality behaviour (all 8
  boundary values one `Decimal` increment either side of both thresholds),
  `campaign_id` propagation, CPA/ROAS normalisation-independence established through the
  full `CampaignInput` → `calculate_campaign_metrics` → `classify_campaign_performance`
  path (not asserted on `CampaignMetrics` alone), integration with
  `validate_campaign_csv` + `calculate_campaign_metrics` over `data/sample_campaigns.csv`
  (order preserved, exact bands `G001=ON_TARGET`, `M001=ON_TARGET`, `G002=ABOVE_TARGET`,
  `G003=ON_TARGET`), and scope boundaries (no out-of-scope field; AST-verified import
  restrictions; no float; comparison-only with no arithmetic side effects; unaffected by
  a mutated global `Decimal` context). Full suite: 217 tests passing (92 Stage 1 + 44
  Stage 2 + 28 Stage 3 + 30 Stage 4 + 23 Stage 5).
- Updated `docs/DATA_DICTIONARY.md` (`PerformanceBand`/`CampaignPerformanceClass`
  fields, explicitly distinguished from `RecommendationAction`), `docs/DECISION_RULES.md`
  (frozen Stage 5 classification rule; trend/confidence/tracking interpretation and final
  recommendation explicitly re-confirmed as pending later stages), and
  `docs/TEST_SCENARIOS.md` (22 concrete Stage 5 scenarios).

- Sprint 1, Development Stage 6: added `TrendDirection` enum (`IMPROVING`, `STABLE`,
  `DECLINING`) and `CampaignTrendClass` (frozen, immutable, `extra="forbid"`:
  `campaign_id`, `trend_direction` only) and `classify_campaign_trend(metrics:
  CampaignMetrics) -> CampaignTrendClass` to `src/classification.py`, alongside but fully
  separate from Stage 5's `PerformanceBand`/`CampaignPerformanceClass`/
  `classify_campaign_performance`, which are unmodified. Classifies `trend_delta` only,
  using the existing frozen `TREND_THRESHOLD`, with the threshold magnitude belonging to
  the directional band in both directions (`>= TREND_THRESHOLD` → `IMPROVING`;
  `<= TREND_THRESHOLD.copy_negate()` → `DECLINING`; otherwise `STABLE`) — consistent
  with Stage 5's threshold-entry equality convention. The negative boundary is built via
  `.copy_negate()` (exact sign-inversion, no rounding, no new constant). Direct `Decimal`
  comparison only — no arithmetic, quantisation, `float`, or local `decimal` context;
  `trend_delta` itself is never touched. Reads only `campaign_id`/`trend_delta` from
  `CampaignMetrics`; does not import `CampaignInput`, `CampaignPacing`, `ReviewSetup`,
  `RecommendationAction`, `Confidence`, or `ReasonCode`, and never calls
  `classify_campaign_performance`. `src/constants.py`, `src/models.py`,
  `src/validation.py`, `src/metrics.py`, and `src/pacing.py` are unchanged.
- Sprint 1, Development Stage 6: `tests/test_trend_classification.py` (29 tests)
  covering result-model shape/immutability, exact threshold-boundary equality behaviour
  (all 11 boundary/large-magnitude values), `campaign_id` propagation, CPA/ROAS
  normalisation-independence established through the full `CampaignInput` →
  `calculate_campaign_metrics` → `classify_campaign_trend` path, integration with
  `validate_campaign_csv` + `calculate_campaign_metrics` over `data/sample_campaigns.csv`
  (order preserved; `G001`/`M001`/`G003` = `STABLE`, `G002` = `IMPROVING`), and scope
  boundaries (no out-of-scope field; AST-verified import restrictions and
  no-call-to-`classify_campaign_performance` check; AST-verified `metrics`
  attribute-access restricted to `campaign_id`/`trend_delta`; no float; comparison-only
  with no arithmetic side effects; unaffected by a mutated global `Decimal` context,
  including at the exact negative boundary). `tests/test_classification.py` (Stage 5)
  re-run unchanged and confirmed still passing (23 tests) — no regression. Full suite:
  246 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30 Stage 4 + 23 Stage 5 + 29
  Stage 6).
- Updated `docs/DATA_DICTIONARY.md` (`TrendDirection`/`CampaignTrendClass` fields,
  explicitly distinguished from `PerformanceBand`/`RecommendationAction`/`ReasonCode`;
  `trend_delta`'s dimensionless relative-ratio unit clarified), `docs/DECISION_RULES.md`
  (frozen Stage 6 trend-classification rule; confidence/tracking/pacing interpretation
  and the trend-to-`ReasonCode` mapping explicitly re-confirmed as pending later
  stages), and `docs/TEST_SCENARIOS.md` (26 concrete Stage 6 scenarios, including a
  synthetic `DECLINING` case since no sample campaign has a negative `trend_delta`).

- Sprint 1, Development Stage 7: added `CampaignConfidenceClass` (frozen, immutable,
  `extra="forbid"`: `campaign_id`, `confidence` only, reusing the existing `Confidence`
  enum unchanged) and `classify_campaign_confidence(campaign: CampaignInput) ->
  CampaignConfidenceClass` to `src/classification.py`, alongside but fully separate from
  Stage 5's `PerformanceBand`/`CampaignPerformanceClass`/`classify_campaign_performance`
  and Stage 6's `TrendDirection`/`CampaignTrendClass`/`classify_campaign_trend`, all of
  which are unmodified. Classifies `conversions_28d` only (the fuller, more stable
  evidence window; `conversions_7d` is never read, summed, averaged, or combined —
  avoiding double-counting the nested 7-day period), using the existing frozen
  `MINIMUM_CONVERSIONS`/`HIGH_CONFIDENCE_CONVERSIONS`, with the threshold magnitude
  belonging to the higher band (`>= HIGH_CONFIDENCE_CONVERSIONS` → `HIGH`;
  `>= MINIMUM_CONVERSIONS` → `MEDIUM`; otherwise, including zero, → `LOW`) — consistent
  with Stages 5–6's threshold-entry equality convention. `Confidence.NOT_ASSESSABLE` is
  never assigned — a deliberate, documented scope boundary, not inferred from zero/low
  conversions, tracking status, pacing, or protected/test status. Direct integer
  comparison only — no arithmetic, weighting, quantisation, or `Decimal`/`float`
  conversion. Reads only `campaign_id`/`conversions_28d` from `CampaignInput`; does not
  import `CampaignPacing`, `ReviewSetup`, `TrackingStatus`, `RecommendationAction`, or
  `ReasonCode`, and never calls `classify_campaign_performance`/`classify_campaign_trend`.
  `src/constants.py`, `src/models.py`, `src/validation.py`, `src/metrics.py`, and
  `src/pacing.py` are unchanged.
- **Approved exception:** implementing Stage 7 required `src/classification.py` to
  import `CampaignInput`/`Confidence`, which broke a pre-existing AST-based scope check
  in both `tests/test_classification.py` and `tests/test_trend_classification.py` that
  had forbidden those imports (correct when Stages 5–6 were written, obsolete once Stage
  7 legitimately needed them). With explicit approval, both tests' forbidden-import sets
  were narrowed to drop only `CampaignInput`/`Confidence`/`src.models`; every other
  forbidden entry is unchanged and still enforced.
- Sprint 1, Development Stage 7: `tests/test_confidence_classification.py` (32 tests)
  covering result-model shape/immutability, exact threshold-boundary equality behaviour
  (all 9 boundary/large-magnitude values, including zero), `campaign_id` propagation,
  `conversions_28d`-only window selection (including a conflicting `conversions_7d=5`/
  `conversions_28d=20` example proving 28-day-only behaviour, and AST verification that
  `conversions_7d` is never read and no binary arithmetic occurs), platform/KPI
  independence, integration with `validate_campaign_csv` over
  `data/sample_campaigns.csv` (order preserved; `G001`/`M001`/`G002` = `HIGH`,
  `G003` = `MEDIUM`), and scope boundaries (no out-of-scope field; `NOT_ASSESSABLE`
  never assigned across every tested value; AST-verified import restrictions and
  no-call-to-other-classifiers check; no float/Decimal; unaffected by a mutated global
  `Decimal` context). `tests/test_classification.py` (Stage 5, 23 tests) and
  `tests/test_trend_classification.py` (Stage 6, 29 tests) re-run and confirmed passing
  after the approved narrowing above — no behavioural regression. Full suite: 278 tests
  passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30 Stage 4 + 23 Stage 5 + 29 Stage 6 +
  32 Stage 7).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignConfidenceClass` fields; `Confidence`
  table with each member's Stage-7 meaning and whether Stage 7 assigns it),
  `docs/DECISION_RULES.md` (frozen Stage 7 confidence-classification rule; tracking
  interpretation and the `NOT_ASSESSABLE` trigger explicitly re-confirmed as pending
  later stages), and `docs/TEST_SCENARIOS.md` (28 concrete Stage 7 scenarios).

- Sprint 1, Development Stage 8: added `CampaignTrackingAssessment` (frozen, immutable,
  `extra="forbid"`: `campaign_id`, `tracking_status`, `is_assessable` only) and
  `assess_campaign_tracking(campaign: CampaignInput) -> CampaignTrackingAssessment` to
  `src/classification.py`, alongside but fully separate from Stage 5's
  `PerformanceBand`/`CampaignPerformanceClass`/`classify_campaign_performance`, Stage 6's
  `TrendDirection`/`CampaignTrendClass`/`classify_campaign_trend`, and Stage 7's
  `CampaignConfidenceClass`/`classify_campaign_confidence`, all of which are unmodified.
  Determines assessability from `tracking_status` alone:
  `is_assessable = tracking_status is not TrackingStatus.UNRELIABLE`, so `HEALTHY` → `True`,
  `WARNING` → `True` (a concern requiring later caution, not unusable evidence), and
  `UNRELIABLE` → `False` (the sole condition producing `False`). The original
  `tracking_status` is preserved unchanged in the result so `WARNING` is never collapsed
  into `HEALTHY`. `Confidence.NOT_ASSESSABLE` is never read or assigned — a deliberate,
  documented scope boundary, deferred to a later combined-assessment stage that must
  preserve both Stage 7's and Stage 8's independent results. No arithmetic, weighting,
  quantisation, or `Decimal`/`float` conversion. Reads only
  `campaign_id`/`tracking_status` from `CampaignInput`; does not import `CampaignMetrics`,
  `CampaignPacing`, `ReviewSetup`, `RecommendationAction`, or `ReasonCode`, and never calls
  `classify_campaign_performance`/`classify_campaign_trend`/`classify_campaign_confidence`.
  `src/constants.py`, `src/models.py`, `src/validation.py`, `src/metrics.py`, and
  `src/pacing.py` are unchanged.
- **Approved exception:** implementing Stage 8 required `src/classification.py` to import
  `TrackingStatus`, which broke a pre-existing AST-based scope check in
  `tests/test_confidence_classification.py` that had forbidden that import (correct when
  Stage 7 was written, obsolete once Stage 8 legitimately needed it). With explicit
  approval, that test's forbidden-import set was narrowed to drop only `TrackingStatus`;
  every other forbidden entry is unchanged and still enforced.
  `tests/test_classification.py` and `tests/test_trend_classification.py` were not
  affected and were not modified.
- Sprint 1, Development Stage 8: `tests/test_tracking_assessment.py` (30 tests) covering
  result-model shape/immutability, exact `HEALTHY`/`WARNING`/`UNRELIABLE` →
  `True`/`True`/`False` mapping, `campaign_id` propagation, information preservation
  (`WARNING` never collapsed into `HEALTHY`; no severity score or replacement enum
  produced), independence from `conversions_7d`/`conversions_28d`, CPA/ROAS, platform,
  and protected/test status, integration with `validate_campaign_csv` over
  `data/sample_campaigns.csv` (order preserved; all four sample campaigns are `HEALTHY`
  → `is_assessable=True`, with synthetic fixtures covering `WARNING`/`UNRELIABLE`), and
  scope boundaries (no out-of-scope field; `NOT_ASSESSABLE` never touched; AST-verified
  restriction to reading only `campaign_id`/`tracking_status` and to calling no other
  classifier; AST-verified zero binary-arithmetic nodes; unaffected by a mutated global
  `Decimal` context). `tests/test_classification.py` (Stage 5, 23 tests),
  `tests/test_trend_classification.py` (Stage 6, 29 tests), and
  `tests/test_confidence_classification.py` (Stage 7, 32 tests) re-run and confirmed
  passing after the approved narrowing above — no behavioural regression. Full suite:
  308 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30 Stage 4 + 23 Stage 5 + 29
  Stage 6 + 32 Stage 7 + 30 Stage 8).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignTrackingAssessment` fields; `TrackingStatus`
  outcome table), `docs/DECISION_RULES.md` (frozen Stage 8 tracking-assessability rule;
  `NOT_ASSESSABLE` trigger and combined assessment, and pacing interpretation, explicitly
  re-confirmed as pending later stages), and `docs/TEST_SCENARIOS.md` (21 concrete Stage
  8 scenarios).

- Sprint 1, Development Stage 9: added `PACING_LOWER_THRESHOLD = Decimal("0.90")` and
  `PACING_UPPER_THRESHOLD = Decimal("1.10")` to `src/constants.py` (a symmetric +/-10%
  on-pace tolerance around `1.00`), and `PacingStatus` enum (`UNDERSPENDING = "Under
  spending"`, `ON_PACE = "On pace"`, `OVERSPENDING = "Over spending"`, `NOT_AVAILABLE =
  "Not available"`), `CampaignPacingClass` (frozen, immutable, `extra="forbid"`:
  `campaign_id`, `pacing_status` only), and `classify_campaign_pacing(pacing:
  CampaignPacing) -> CampaignPacingClass` to `src/pacing.py`, alongside but fully
  separate from Stage 4's `CampaignPacing`/`calculate_campaign_pacing`, which are
  unmodified. Classifies `pacing_ratio` only (`campaign_id` otherwise, for result
  identity) — `spend_variance`, `expected_spend`, `elapsed_fraction`, `elapsed_days`,
  `total_period_days`, `remaining_budget`, and `projected_end_of_period_spend` are never
  read; `CampaignInput`, `ReviewSetup`, `CampaignMetrics`, and every Stage 5–8 result are
  never read. Exact precedence: `pacing_ratio is None` → `NOT_AVAILABLE`; `<
  PACING_LOWER_THRESHOLD` → `UNDERSPENDING`; `PACING_LOWER_THRESHOLD <= pacing_ratio <=
  PACING_UPPER_THRESHOLD` → `ON_PACE` (closed, inclusive interval on both boundaries);
  otherwise → `OVERSPENDING` — a deliberately different, two-sided equality convention
  from Stages 5–7's single-sided threshold-entry rule. `PacingStatus.NOT_AVAILABLE` is a
  pacing-data state only — never substituted for `Confidence.NOT_ASSESSABLE`,
  `is_assessable=False`, `TrackingStatus.UNRELIABLE`, `RecommendationAction.HOLD`, a
  reason code, or an eligibility outcome; the upstream `None` cause is never
  distinguished and `pacing_ratio` is never recalculated. Direct `Decimal` comparison
  only — no arithmetic, weighting, quantisation, or `float` conversion.
  `classify_campaign_pacing` never calls `classify_campaign_performance`,
  `classify_campaign_trend`, `classify_campaign_confidence`, or
  `assess_campaign_tracking` (or vice versa). Descriptive only — does not judge whether
  overspending or underspending is desirable. `src/models.py`, `src/validation.py`,
  `src/metrics.py`, and `src/classification.py` are unchanged.
- Sprint 1, Development Stage 9: `tests/test_pacing_interpretation.py` (33 tests)
  covering enum members/values, threshold constants (exact `Decimal`, never `float`),
  result-model shape/immutability/`campaign_id` copying, incompatible-input rejection
  (`AttributeError`, no silent coercion), exact boundary classification (immediately
  below/at/immediately above both thresholds, `None`, zero, and a very large valid
  value), independence (AST-verified restriction to reading only `campaign_id`/
  `pacing_ratio`, AST-verified zero binary-arithmetic nodes, AST-verified no call to any
  Stage 5–8 classifier, unaffected by a mutated global `Decimal` context across every
  outcome, platform/KPI independence and protected/test independence proven through the
  full `CampaignInput` → `calculate_campaign_pacing` → `classify_campaign_pacing` path,
  independence from `projected_end_of_period_spend` and `spend_variance`), integration
  with `validate_campaign_csv` + `calculate_campaign_pacing` over
  `data/sample_campaigns.csv` at the existing Stage 4 review-period fixture (order
  preserved; `G001`/`M001`/`G002` = `OVERSPENDING`, `G003` = `UNDERSPENDING`, asserted
  against the exact calculated result, not a hard-coded rounded approximation), and two
  upstream-`None` integration cases (zero elapsed time, zero current budget), both
  `NOT_AVAILABLE`. `tests/test_pacing.py` (Stage 4, 30 tests), `tests/test_classification.py`
  (Stage 5, 23 tests), `tests/test_trend_classification.py` (Stage 6, 29 tests),
  `tests/test_confidence_classification.py` (Stage 7, 32 tests), and
  `tests/test_tracking_assessment.py` (Stage 8, 30 tests) re-run and confirmed passing —
  no behavioural regression, and no existing test file required modification this stage.
  Full suite: 341 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30 Stage 4 + 23
  Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9).
- Updated `docs/DATA_DICTIONARY.md` (`PacingStatus`/`CampaignPacingClass` fields; exact
  thresholds and inclusive `ON_PACE` interval), `docs/DECISION_RULES.md` (frozen Stage 9
  pacing-interpretation rule; combined assessment, `Confidence.NOT_ASSESSABLE`
  ownership, constraints, protected/test handling, and eligibility explicitly
  re-confirmed as pending later stages), and `docs/TEST_SCENARIOS.md` (29 concrete Stage
  9 scenarios).

- Sprint 1, Development Stage 10: populated the previously-placeholder `src/constraints.py`
  with `CampaignStaticBudgetRoom` (frozen, immutable, `extra="forbid"`: `campaign_id`,
  `room_to_static_maximum`, `room_to_static_minimum` only) and
  `calculate_campaign_static_budget_room(campaign: CampaignInput) ->
  CampaignStaticBudgetRoom`. Calculates static-bound distance facts only —
  `room_to_static_maximum = maximum_budget - current_budget`,
  `room_to_static_minimum = current_budget - minimum_budget` — both structurally
  guaranteed non-negative by `CampaignInput`'s already-validated `minimum_budget <=
  current_budget <= maximum_budget` invariant, with no new validation, clamping, or
  default substitution; `Decimal("0.00")` is a valid outcome exactly at either bound,
  never replaced with `None` or a categorical status. Reads only `campaign_id`/
  `current_budget`/`minimum_budget`/`maximum_budget` — `campaign_max_change_percentage`,
  `ReviewSetup.default_max_change_percentage`, `DEFAULT_MAX_CHANGE_PERCENTAGE`,
  `is_protected`, `is_test_campaign`, and `test_budget_floor` are all deliberately never
  read; no `ReviewSetup` or Stage 3–9 result is used and no Stage 3–9 function is
  called. The approved "static" terminology
  (`CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room`/
  `room_to_static_maximum`/`room_to_static_minimum`) deliberately distinguishes these
  facts from a future *effective* constraint that must still consider percentage
  limits, protection, and test-budget-floor rules — none of which is calculated or
  authorised here. Calculation runs inside an explicit `decimal.localcontext()`
  (`prec=28`, `ROUND_HALF_UP`), matching the fixed-context pattern already used by
  Stages 3–4; no `float`, no re-quantisation, no rounding of the output. `src/constants.py`,
  `src/models.py`, `src/validation.py`, `src/metrics.py`, `src/pacing.py`, and
  `src/classification.py` are unchanged.
- Sprint 1, Development Stage 10: populated the previously-placeholder
  `tests/test_constraints.py` (25 tests) covering result-model shape/immutability/
  `campaign_id` copying, incompatible-input rejection (`AttributeError`, no silent
  coercion), exact calculations for a campaign strictly between bounds, exactly at
  `minimum_budget`, exactly at `maximum_budget`, `minimum_budget == current_budget ==
  maximum_budget` (including the all-zero case), large valid Decimal currency values,
  and exact two-decimal non-round results, independence (AST-verified restriction to
  reading only the four authorised `CampaignInput` fields, AST-verified no call to any
  Stage 3–9 function, AST-verified `src/constraints.py` imports none of Stage 3–9's
  models/enums, platform/KPI independence, `is_protected` independence,
  `is_test_campaign`/`test_budget_floor` independence, `campaign_max_change_percentage`
  independence, unaffected by a mutated global `Decimal` context), integration with
  `validate_campaign_csv` over `data/sample_campaigns.csv` (order preserved; `G001` =
  `3000.00`/`2500.00`, `M001` = `2500.00`/`2000.00`, `G002` (protected) =
  `3000.00`/`4000.00` unaffected by `is_protected=True`, `G003` (test campaign,
  `test_budget_floor=300.00`) = `800.00`/`1100.00`, with an explicit note that the
  `1100.00` figure is a static-bound fact only, not an approved decrease amount).
  `tests/test_models.py` (Stage 1, 92 tests), `tests/test_validation.py` (Stage 2, 44
  tests), `tests/test_metrics.py` (Stage 3, 28 tests), `tests/test_pacing.py` (Stage 4,
  30 tests), `tests/test_classification.py` (Stage 5, 23 tests),
  `tests/test_trend_classification.py` (Stage 6, 29 tests),
  `tests/test_confidence_classification.py` (Stage 7, 32 tests),
  `tests/test_tracking_assessment.py` (Stage 8, 30 tests), and
  `tests/test_pacing_interpretation.py` (Stage 9, 33 tests) re-run and confirmed
  passing — no behavioural regression, and no existing test file required modification.
  Full suite: 366 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30 Stage 4 + 23
  Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 25 Stage 10).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignStaticBudgetRoom` fields; explicit
  confirmation these are static-bound distances, not final permissible movements),
  `docs/DECISION_RULES.md` (frozen Stage 10 static budget-bound calculation rule;
  effective constraints, protected/test handling, and eligibility explicitly
  re-confirmed as pending later stages), and `docs/TEST_SCENARIOS.md` (22 concrete
  Stage 10 scenarios).

- Sprint 1, Development Stage 11: added `CampaignApplicableChangePercentage` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `applicable_max_change_percentage` only)
  and `resolve_campaign_applicable_change_percentage(review: ReviewSetup, campaign:
  CampaignInput) -> CampaignApplicableChangePercentage` to `src/constraints.py`,
  alongside but fully separate from Stage 10's `CampaignStaticBudgetRoom`/
  `calculate_campaign_static_budget_room`, which are unmodified. Resolves which
  already-validated maximum-change percentage applies to a campaign — a non-`None`
  `campaign.campaign_max_change_percentage` always wins; otherwise
  `review.default_max_change_percentage` applies, via an explicit `is not None` check
  (never a truthiness-based fallback). The result is never `None`; no special zero
  handling exists or is needed, since both source fields are already constrained to
  `(0, 1]`. `DEFAULT_MAX_CHANGE_PERCENTAGE` is never imported or read — only the
  already-validated `review.default_max_change_percentage` is used, so a
  caller-supplied `ReviewSetup` value is always respected instead of a hard-coded
  module constant. Reads only `campaign.campaign_id`,
  `campaign.campaign_max_change_percentage`, and `review.default_max_change_percentage`
  — `current_budget`, `minimum_budget`, `maximum_budget`, `room_to_static_maximum`,
  `room_to_static_minimum`, `is_protected`, `is_test_campaign`, `test_budget_floor`,
  `platform`, `kpi_type`, and every Stage 3–9 result are all deliberately never read. No
  arithmetic, quantisation, or rounding is performed — a plain conditional selection,
  so no local `Decimal` context is used and the result is unaffected by a mutated
  global `Decimal` context. Never calls `calculate_campaign_static_budget_room` or any
  Stage 3–9 function; does not calculate a monetary movement cap, a static-bound
  intersection, or any permissible budget movement. `src/constants.py`,
  `src/models.py`, `src/validation.py`, `src/metrics.py`, `src/pacing.py`, and
  `src/classification.py` are unchanged.
- Sprint 1, Development Stage 11: extended `tests/test_constraints.py` with 24 new
  tests (all 25 existing Stage 10 tests preserved unchanged; 49 tests total) covering
  result-model shape/immutability/`campaign_id` copying/no-`None`-result,
  incompatible-input rejection (`AttributeError`, no silent coercion), exact
  override-first/default-fallback precedence (including a non-default review value of
  `0.35` to prove the default isn't hard-coded, deliberately different campaign/review
  values to prove precedence, the `Decimal("1")` upper boundary, and a small valid
  `Decimal("0.0001")` value preserved exactly), an AST-verified explicit-`is not
  None`-check proof (no `BoolOp`, an `Is`/`IsNot`-against-`None` comparison present)
  and an AST/source-verified no-arithmetic/no-`quantize`/no-`ROUND_` proof,
  independence (AST-verified restriction to reading only the three authorised fields,
  AST-verified no call to `calculate_campaign_static_budget_room` or any Stage 3–9
  function, unaffected by a mutated global `Decimal` context across both an override
  and a no-override case, platform/KPI independence, budget-field independence,
  protected/test independence, no combination with Stage 10's result), and integration
  with `validate_campaign_csv` over `data/sample_campaigns.csv` with a
  `default_max_change_percentage=Decimal("0.20")` `ReviewSetup` fixture (order
  preserved; `G001`/`G002`/`G003` = `0.20`, `M001` = `0.15`; Stage 10's static-room
  results for all four independently re-verified via separate calls in the same test,
  never combined into one object). **One approved exception:**
  `tests/test_constraints.py`'s pre-existing
  `test_module_does_not_import_out_of_scope_modules` AST check was narrowed (removing
  only `"ReviewSetup"` from its forbidden-import set) because it was written when
  `src/constraints.py` legitimately had no reason to import it — Stage 11 requires it,
  per your explicit approval; every other forbidden import
  (`DEFAULT_MAX_CHANGE_PERCENTAGE` included) is unchanged and still enforced.
  `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
  `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
  `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
  (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
  behavioural regression. Full suite: 390 tests passing (92 Stage 1 + 44 Stage 2 + 28
  Stage 3 + 30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9
  + 49 Stage 10/11 combined in `tests/test_constraints.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignApplicableChangePercentage` fields;
  exact override/default rule; confirmation no monetary cap or permissible movement is
  calculated), `docs/DECISION_RULES.md` (frozen Stage 11 applicable-change-percentage
  resolution rule; monetary-cap formula, effective constraints, protected/test
  handling, and eligibility explicitly re-confirmed as pending later stages), and
  `docs/TEST_SCENARIOS.md` (21 concrete Stage 11 scenarios).

- Sprint 1, Development Stage 12: added `CampaignRawPercentageMovementCap` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `raw_percentage_movement_cap` only) and
  `calculate_campaign_raw_percentage_movement_cap(campaign: CampaignInput,
  applicable_percentage: CampaignApplicableChangePercentage) ->
  CampaignRawPercentageMovementCap` to `src/constraints.py`, alongside but fully
  separate from Stage 10's `CampaignStaticBudgetRoom`/
  `calculate_campaign_static_budget_room` and Stage 11's
  `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
  which are unmodified. Calculates a raw, informational percentage-based monetary
  movement cap: `current_budget * applicable_max_change_percentage`, quantised once to
  `CURRENCY_QUANTUM` using `ROUND_HALF_UP` — explicitly not permission to increase or
  decrease a campaign's budget, an effective/final permissible movement, a
  static-bound intersection, a protection or test-budget-floor determination, an
  eligibility result, a score, a recommendation, a reason code, or an allocation.
  Consumes Stage 11's already-resolved result directly (never accepts `ReviewSetup`,
  never reads `campaign.campaign_max_change_percentage` or
  `review.default_max_change_percentage`, never imports
  `DEFAULT_MAX_CHANGE_PERCENTAGE`, never re-resolves override/default precedence).
  Requires `campaign.campaign_id == applicable_percentage.campaign_id`, raising
  `ValueError("campaign_id mismatch between campaign and applicable percentage")`
  otherwise with no result returned. **Decimal precision investigated before
  implementation, per explicit instruction, rather than assumed safe:** found that a
  fixed `prec=28` local context (the pattern used by Stages 3, 4, and 10) incorrectly
  rounds the intermediate multiplication for an already-valid extreme `CampaignInput`
  (`current_budget=Decimal("99999999999999999999999999.99")`, 28 significant digits —
  the largest `Currency` can hold under the default global context, empirically
  confirmed) paired with a many-decimal-digit percentage
  (`Decimal("0.036020245307579938554529107051")`), returning
  `Decimal("...52910.71")` instead of the mathematically exact
  `Decimal("...52910.70")` — a one-penny double-rounding error. Fixed with an approved
  operand-derived precision policy: `safe_precision = max(28,
  len(current_budget.as_tuple().digits) +
  len(applicable_max_change_percentage.as_tuple().digits) + 4)`, used only inside a
  local `decimal` context for the multiplication and final quantisation, guaranteeing
  an exact intermediate product and leaving the explicit `.quantize(...)` call as the
  sole rounding operation; the global `Decimal` context is never mutated and is
  unaffected by the call. No new maximum budget or percentage digit restriction was
  introduced; `CampaignInput`/`Currency` validation is unmodified. Independent of
  Stage 10 (never reads `minimum_budget`/`maximum_budget`/`room_to_static_maximum`/
  `room_to_static_minimum`, never calls `calculate_campaign_static_budget_room`) and
  ignores `is_protected`/`is_test_campaign`/`test_budget_floor`. `src/constants.py`,
  `src/models.py`, `src/validation.py`, `src/metrics.py`, `src/pacing.py`, and
  `src/classification.py` are unchanged.
- Sprint 1, Development Stage 12: extended `tests/test_constraints.py` with 35 new
  tests (all 49 existing Stage 10/11 tests preserved unchanged; 84 tests total)
  covering result-model shape/immutability/`campaign_id` copying/no-`None`-result/
  two-decimal-place quantisation, incompatible-input rejection (`AttributeError`, no
  silent coercion), exact calculation (whole-penny, fractional-penny `ROUND_HALF_UP`
  rounding both below and exactly at the half-cent boundary, the `Decimal("1")`
  boundary, a small positive percentage, a zero-budget result, no float conversion,
  `.quantize()` called exactly once), campaign-ID matching (matching IDs calculate
  normally, mismatched IDs raise the exact approved `ValueError` message with no
  result returned), Decimal-context behaviour (mutated global context does not affect
  results, the global context's `prec`/`rounding` are unchanged after the function
  returns, and a dedicated **extreme-value regression test** using the exact
  double-rounding-bug input, asserting the correct `Decimal("...52910.70")` result and
  explicitly asserting the incorrect fixed-precision-28 result
  `Decimal("...52910.71")` is *not* returned, both under the default context and under
  a deliberately altered ambient global context, plus a whole-number-digit-preservation
  proof at 100% of the extreme budget), independence (AST-verified restriction to
  reading only the four authorised fields, AST-verified no reference to `ReviewSetup`/
  `review`, AST-verified no call to Stage 10/11/3–9 functions, platform/KPI
  independence, static-bound independence, protected/test independence, no
  combination with Stage 10's result), and integration with `validate_campaign_csv` +
  `resolve_campaign_applicable_change_percentage` over `data/sample_campaigns.csv`
  (order preserved; `G001=600.00`, `M001=375.00`, `G002=1000.00`, `G003=240.00`;
  Stage 10's static-room results for all four independently re-verified via separate
  calls, never intersected or combined). `tests/test_models.py` (Stage 1),
  `tests/test_validation.py` (Stage 2), `tests/test_metrics.py` (Stage 3),
  `tests/test_pacing.py` (Stage 4), `tests/test_classification.py` (Stage 5),
  `tests/test_trend_classification.py` (Stage 6),
  `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
  behavioural regression, and no existing test file required modification this stage.
  Full suite: 425 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30 Stage 4 + 23
  Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 84 Stage 10/11/12
  combined in `tests/test_constraints.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignRawPercentageMovementCap` fields; exact
  current-budget multiplication rule; campaign-ID matching requirement; confirmation
  the result is informational only), `docs/DECISION_RULES.md` (frozen Stage 12 raw
  percentage-based monetary movement-cap calculation rule, including the full
  operand-derived Decimal precision policy and its empirical justification;
  static-bound intersection, effective constraints, protected/test handling, and
  eligibility explicitly re-confirmed as pending later stages), and
  `docs/TEST_SCENARIOS.md` (29 concrete Stage 12 scenarios).

- Sprint 1, Development Stage 13: added `CampaignTestFloorRoom` (frozen, immutable,
  `extra="forbid"`: `campaign_id`, `room_to_test_floor: Decimal | None` only) and
  `calculate_campaign_test_floor_room(campaign: CampaignInput) ->
  CampaignTestFloorRoom` to `src/constraints.py`, alongside but fully separate from
  Stage 10's `CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room`, Stage
  11's `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
  and Stage 12's `CampaignRawPercentageMovementCap`/
  `calculate_campaign_raw_percentage_movement_cap`, all unmodified. Calculates a raw,
  informational test-floor distance: `room_to_test_floor = current_budget -
  test_budget_floor` for test campaigns (`is_test_campaign=True`); `None` for
  non-test campaigns — an explicit "not applicable" statement, never a fallback,
  never `Decimal("0.00")`, never an error; a valid non-test `CampaignInput` never
  raises. Explicitly not the effective floor, not an alternative or additional
  minimum, not permissible decrease, not an effective directional constraint, and
  never combined with `minimum_budget`, Stage 10's static room, or Stage 12's raw
  percentage movement cap — this approval fixes only the raw distance formula, not
  the eventual effective-floor precedence. Reads only `campaign_id`,
  `is_test_campaign`, `current_budget`, `test_budget_floor` — `minimum_budget`,
  `maximum_budget`, `is_protected`, `campaign_max_change_percentage`, `platform`,
  `kpi_type`, `ReviewSetup`, and every Stage 3–9/Stage 10–12 result are all
  deliberately never read. **Decimal policy:** subtraction runs inside a fixed local
  `decimal.localcontext()` (`prec=28`, `ROUND_HALF_UP`), matching Stage 10's
  established policy rather than Stage 12's operand-derived policy — subtracting two
  already-quantised `Currency` values never needs more significant digits than the
  larger operand already has (verified empirically before implementation against the
  largest value `Currency` can hold under the default global context, 28 significant
  digits, with all whole-number digits preserved). Neither operand nor the result is
  re-quantised. The global `Decimal` context is never mutated and is unaffected by
  the call. `src/constants.py`, `src/models.py`, `src/validation.py`,
  `src/metrics.py`, `src/pacing.py`, and `src/classification.py` are unchanged.
- Sprint 1, Development Stage 13: extended `tests/test_constraints.py` with 35 new
  tests (all 84 existing Stage 10/11/12 tests preserved unchanged; 119 tests total)
  covering result-model shape/immutability/`campaign_id` copying/two-decimal-place
  preservation, incompatible-input rejection (`AttributeError`, no silent coercion),
  exact calculation (ordinary subtraction, zero floor, floor below/equal-to/above
  `minimum_budget`, floor equal to `current_budget` returning `Decimal("0.00")`, no
  float conversion, no `.quantize()` call), non-test behaviour (`None` returned
  without raising, without substituting zero, without reconstructing
  `CampaignInput`), Decimal-context behaviour (mutated global context does not affect
  results, the global context's `prec`/`rounding` are unchanged after the function
  returns, and extreme-valid-currency tests preserving significant whole-number
  digits at the 28-significant-digit ceiling), independence (AST-verified
  restriction to reading only the four authorised fields, AST-verified no reference
  to `ReviewSetup`/`review`, AST-verified no call to Stage 10/11/12/3–9 functions,
  `minimum_budget`/`maximum_budget`/`is_protected`/platform/KPI/
  `campaign_max_change_percentage` independence, no combination with Stage 10–12
  results), and integration with `validate_campaign_csv` over
  `data/sample_campaigns.csv` (order preserved; `G001`/`M001`/`G002`
  (`is_test_campaign=False`) = `None`, `G003` (`is_test_campaign=True`,
  `test_budget_floor=300.00`) = `Decimal("900.00")`; Stages 10, 11, and 12's existing
  sample results independently re-verified via separate calls, never combined or
  intersected). `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage
  2), `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
  `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
  (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
  behavioural regression, and no existing test file required modification this
  stage. Full suite: 460 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30
  Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 119
  Stage 10/11/12/13 combined in `tests/test_constraints.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignTestFloorRoom` fields; exact
  subtraction rule; non-test `None` behaviour; confirmation the result is
  informational only and does not decide the effective floor),
  `docs/DECISION_RULES.md` (frozen Stage 13 test-floor distance calculation rule;
  effective-floor precedence, static-bound/raw-cap/test-floor intersection, and
  protected-campaign handling explicitly re-confirmed as pending later stages), and
  `docs/TEST_SCENARIOS.md` (24 concrete Stage 13 scenarios).

- Sprint 1, Development Stage 14: added `CampaignProtectionConstraint` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `decrease_blocked: bool` only) and
  `resolve_campaign_protection_constraint(campaign: CampaignInput) ->
  CampaignProtectionConstraint` to `src/constraints.py`, alongside but fully separate
  from Stage 10's `CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room`,
  Stage 11's `CampaignApplicableChangePercentage`/
  `resolve_campaign_applicable_change_percentage`, Stage 12's
  `CampaignRawPercentageMovementCap`/`calculate_campaign_raw_percentage_movement_cap`,
  and Stage 13's `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, all
  unmodified. States a neutral, decrease-specific protection constraint:
  `decrease_blocked = campaign.is_protected` — explicitly not an eligibility
  decision, a recommendation, a monetary movement amount, permissible decrease, an
  effective directional limit, or an increase-side constraint, and never combined
  with Stages 10–13. `decrease_blocked=True` means only that protection prohibits a
  decrease (not eligibility/recommendation/allocation); `decrease_blocked=False`
  means only that protection itself does not prohibit a decrease (not permission to
  reduce the budget) — `False` is a meaningful result, never converted to `None`.
  **Boolean representation approved over a Decimal/`None` monetary "room"** to
  preserve the frozen "must never be reduced" rule directly, without prematurely
  translating it into a numeric amount before a later stage actually needs one.
  Reads only `campaign_id`, `is_protected` — `current_budget`, `minimum_budget`,
  `maximum_budget`, `is_test_campaign`, `test_budget_floor`,
  `campaign_max_change_percentage`, `platform`, `kpi_type`, `ReviewSetup`, and every
  Stage 3–9/Stage 10–13 result are all deliberately never read. No `Decimal` import,
  local context, rounding, quantisation, or float conversion anywhere — a plain
  boolean selection. Decrease-specific only; increase-side protection behaviour
  remains entirely unaddressed rather than assumed either way. `src/constants.py`,
  `src/models.py`, `src/validation.py`, `src/metrics.py`, `src/pacing.py`, and
  `src/classification.py` are unchanged.
- Sprint 1, Development Stage 14: extended `tests/test_constraints.py` with 28 new
  tests (all 119 existing Stage 10/11/12/13 tests preserved unchanged; 147 tests
  total) covering result-model shape/immutability/`campaign_id` copying/no-Decimal-
  field confirmation, incompatible-input rejection (`AttributeError`, no silent
  coercion), exact mapping (protected → `True`, non-protected → `False`, `False` not
  converted to `None`, `True` not converted to `Decimal("0.00")`, no truthiness
  fallback, no monetary calculation), independence (AST-verified restriction to
  reading only `campaign_id`/`is_protected`, AST-verified no reference to
  `ReviewSetup`/`review`, AST-verified no call to any Stage 10–13 or Stage 3–9
  function, a campaign both protected and test returning `decrease_blocked=True`
  unaffected by `is_test_campaign`/`test_budget_floor`, `current_budget`/
  `minimum_budget`/`maximum_budget`/platform/KPI/`campaign_max_change_percentage`
  independence, no combination with Stage 10–13 results), and integration with
  `validate_campaign_csv` over `data/sample_campaigns.csv` (order preserved;
  `G001`/`M001`/`G003` (`is_protected=False`) = `False`, `G002` (`is_protected=True`)
  = `True`; Stages 10, 11, 12, and 13's existing sample results independently
  re-verified via separate calls, never combined or intersected).
  `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
  `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
  `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
  (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
  behavioural regression, and no existing test file required modification this
  stage. Full suite: 488 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30
  Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 147
  Stage 10/11/12/13/14 combined in `tests/test_constraints.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignProtectionConstraint` fields; exact
  Boolean mapping; confirmation `False` is not permission to decrease; confirmation
  no monetary amount is calculated; confirmation the fact is decrease-specific and
  says nothing about increases), `docs/DECISION_RULES.md` (frozen Stage 14
  protection constraint rule; effective-floor precedence, the four-way static-bound/
  raw-cap/test-floor/protection intersection, increase-side protection behaviour,
  and eligibility explicitly re-confirmed as pending later stages), and
  `docs/TEST_SCENARIOS.md` (18 concrete Stage 14 scenarios).
