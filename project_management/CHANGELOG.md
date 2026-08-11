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
