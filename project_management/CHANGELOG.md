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
- Sprint 2, Development Stage 1: frozen enumerations in `src/constants.py` (`Platform`,
  `KPIType`, `CampaignStatus`, `TrackingStatus`, `BusinessPriority`, `RecommendationAction`,
  `Confidence`, `ReviewStatus`, `ValidationSeverity`, `ReasonCode`) plus nine frozen
  numerical constants (`DEFAULT_MAX_CHANGE_PERCENTAGE`, `TREND_THRESHOLD`,
  `SEVEN_DAY_WEIGHT`, `TWENTY_EIGHT_DAY_WEIGHT`, `INCREASE_THRESHOLD`,
  `MAINTAIN_THRESHOLD`, `MINIMUM_CONVERSIONS`, `HIGH_CONFIDENCE_CONVERSIONS`,
  `CURRENCY_QUANTUM`).
- Sprint 2, Development Stage 1: exactly two Pydantic v2 input models in `src/models.py`
  (`ReviewSetup`, `CampaignInput`) with currency fields quantised to `CURRENCY_QUANTUM` via
  `ROUND_HALF_UP`, KPI/percentage fields left unquantised, conventional boolean parsing for
  `is_protected`/`is_test_campaign`, and full model-level structural validation (budget
  bounds, spend/conversion ordering, period ordering, reserve-vs-budget, percentage bounds,
  test-budget-floor requiredness).
- Sprint 2, Development Stage 1: exact 20-field `CampaignInput` CSV schema;
  `data/campaign_template.csv` (header only) and `data/sample_campaigns.csv` (4 synthetic
  rows covering an active Google Ads CPA campaign, an active Meta Ads ROAS campaign, a
  protected active campaign, and a test campaign with a `test_budget_floor`).
- Sprint 2, Development Stage 1: `tests/test_models.py` (92 tests) covering enum values,
  frozen constants, model structural rules, currency quantisation, conventional boolean
  parsing, and CSV-schema consistency.
- Updated `docs/DATA_DICTIONARY.md` and `docs/DECISION_RULES.md` with the CSV schema,
  `ReviewSetup` fields, approved enums, and the nine frozen constants; added
  `pythonpath = ["."]` to `pyproject.toml` so `src` imports resolve under pytest; pinned
  `pydantic>=2,<3` in `requirements.txt`.

### Fixed
- Corrected an earlier draft of this stage that had used unapproved 24-field/renamed
  `CampaignInput` columns, `SCREAMING_SNAKE` CSV enum values instead of approved
  human-readable values, an unauthorised `ValidationIssue` model, and a blanket rejection of
  `float` input. That same earlier correction also relabelled this work from "Sprint 2" to
  "Sprint 1" — a 2026-08-18 consistency audit against the frozen master plan found that
  relabelling was itself mistaken: this work is Sprint 2 (Deterministic Core Engine) content.
  See the 2026-08-18 documentation-correction entry below.

- Sprint 2, Development Stage 2: added `ValidationCode` enum to `src/constants.py`
  (`INVALID_REVIEW_FIELD`, `EMPTY_FILE`, `INVALID_HEADER`, `NO_CAMPAIGN_ROWS`,
  `MALFORMED_ROW`, `INVALID_CAMPAIGN_FIELD`, `DUPLICATE_CAMPAIGN_ID`), distinct from
  `ReasonCode`. `src/models.py` unchanged.
- Sprint 2, Development Stage 2: implemented `src/validation.py` — `ValidationIssue` and
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
- Sprint 2, Development Stage 2: `tests/test_validation.py` (44 tests) covering
  `ValidationIssue`/`ValidationReport` construction and derived fields, review validation,
  CSV header/row/duplicate handling, and physical line-number correctness. `data/
  sample_campaigns.csv` validates with 4 campaigns and zero issues; `data/
  campaign_template.csv` correctly yields one `NO_CAMPAIGN_ROWS` issue. Full suite: 136
  tests passing (92 Stage 1 + 44 Stage 2).
- Updated `docs/DATA_DICTIONARY.md` (`ValidationIssue`/`ValidationReport` fields),
  `docs/DECISION_RULES.md` (frozen Stage 2 validation rules and `ValidationCode` table),
  and `docs/TEST_SCENARIOS.md` (43 concrete Stage 2 scenarios).

- Sprint 2, Development Stage 3: implemented `src/metrics.py` — `CampaignMetrics` (frozen,
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
- Sprint 2, Development Stage 3: `tests/test_metrics.py` (28 tests) covering result-model
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

- Sprint 2, Development Stage 4: implemented `src/pacing.py` — `CampaignPacing` (frozen,
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
- Sprint 2, Development Stage 4: `tests/test_pacing.py` (30 tests) covering result-model
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

- Sprint 2, Development Stage 5: implemented `src/classification.py` — `PerformanceBand`
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
- Sprint 2, Development Stage 5: `tests/test_classification.py` (23 tests) covering
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

- Sprint 2, Development Stage 6: added `TrendDirection` enum (`IMPROVING`, `STABLE`,
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
- Sprint 2, Development Stage 6: `tests/test_trend_classification.py` (29 tests)
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

- Sprint 2, Development Stage 7: added `CampaignConfidenceClass` (frozen, immutable,
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
- Sprint 2, Development Stage 7: `tests/test_confidence_classification.py` (32 tests)
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

- Sprint 2, Development Stage 8: added `CampaignTrackingAssessment` (frozen, immutable,
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
- Sprint 2, Development Stage 8: `tests/test_tracking_assessment.py` (30 tests) covering
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

- Sprint 2, Development Stage 9: added `PACING_LOWER_THRESHOLD = Decimal("0.90")` and
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
- Sprint 2, Development Stage 9: `tests/test_pacing_interpretation.py` (33 tests)
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

- Sprint 2, Development Stage 10: populated the previously-placeholder `src/constraints.py`
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
- Sprint 2, Development Stage 10: populated the previously-placeholder
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

- Sprint 2, Development Stage 11: added `CampaignApplicableChangePercentage` (frozen,
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
- Sprint 2, Development Stage 11: extended `tests/test_constraints.py` with 24 new
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

- Sprint 2, Development Stage 12: added `CampaignRawPercentageMovementCap` (frozen,
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
- Sprint 2, Development Stage 12: extended `tests/test_constraints.py` with 35 new
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

- Sprint 2, Development Stage 13: added `CampaignTestFloorRoom` (frozen, immutable,
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
- Sprint 2, Development Stage 13: extended `tests/test_constraints.py` with 35 new
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

- Sprint 2, Development Stage 14: added `CampaignProtectionConstraint` (frozen,
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
- Sprint 2, Development Stage 14: extended `tests/test_constraints.py` with 28 new
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

- Sprint 2, Development Stage 15: added `CampaignTestAwareStaticDecreaseRoom` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `test_aware_static_decrease_room:
  Decimal` only) and `resolve_campaign_test_aware_static_decrease_room(static_room:
  CampaignStaticBudgetRoom, test_floor_room: CampaignTestFloorRoom) ->
  CampaignTestAwareStaticDecreaseRoom` to `src/constraints.py`, alongside but fully
  separate from Stage 10's `CampaignStaticBudgetRoom`/
  `calculate_campaign_static_budget_room`, Stage 11's
  `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
  Stage 12's `CampaignRawPercentageMovementCap`/
  `calculate_campaign_raw_percentage_movement_cap`, Stage 13's
  `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, and Stage 14's
  `CampaignProtectionConstraint`/`resolve_campaign_protection_constraint`, all
  unmodified. **First approved constraints-domain business precedence rule:**
  `test_budget_floor` is an *additional* retained-spend floor for test campaigns —
  the higher of `minimum_budget`/`test_budget_floor` controls, equivalently the
  smaller of the two already-calculated rooms — resolving the exact question every
  prior Stage 10–14 addition had deliberately deferred. Exact formula:
  `test_aware_static_decrease_room = room_to_static_minimum` when
  `room_to_test_floor is None` (non-test campaigns); otherwise
  `min(room_to_static_minimum, room_to_test_floor)` — mathematically equivalent to
  `max(minimum_budget, test_budget_floor)` via `c - max(a, b) = min(c-a, c-b)`. A
  raw, test-aware static constraint only — not permissible decrease, not an
  effective decrease limit, does not mean the campaign should be reduced, and does
  not account for Stage 12's percentage cap or Stage 14's protection constraint.
  **Consumes Stage 10's and Stage 13's already-approved result objects directly**
  (never accepts or reads `CampaignInput`, never calls
  `calculate_campaign_static_budget_room` or `calculate_campaign_test_floor_room`,
  never recalculates either room) to avoid duplicating their already-tested
  calculations. Requires `static_room.campaign_id == test_floor_room.campaign_id`,
  checked before any monetary result is resolved, raising exactly
  `ValueError("Campaign IDs must match when resolving test-aware static decrease
  room.")` otherwise with neither ID silently preferred. No arithmetic is performed
  — the selected `Decimal` operand is returned unchanged; no local `decimal`
  context, `CURRENCY_QUANTUM`, `ROUND_HALF_UP`, rounding, quantisation, or `float`
  conversion; ambient global `Decimal` precision cannot affect the result. Fully
  independent of Stages 11, 12, and 14 — never reads
  `applicable_max_change_percentage`, `raw_percentage_movement_cap`,
  `decrease_blocked`, or `is_protected`; a protected campaign receives exactly the
  same Stage 15 result as an otherwise identical unprotected campaign with matching
  Stage 10/13 facts. `src/constants.py`, `src/models.py`, `src/validation.py`,
  `src/metrics.py`, `src/pacing.py`, and `src/classification.py` are unchanged.
- Sprint 2, Development Stage 15: extended `tests/test_constraints.py` with 39 new
  tests (all 147 existing Stage 10/11/12/13/14 tests preserved unchanged; 186 tests
  total) covering result-model shape/immutability/field-type confirmation,
  incompatible-input rejection (`AttributeError`, no silent coercion), campaign-ID
  matching (matching IDs resolve normally, mismatched IDs raise the exact approved
  `ValueError` message with no result resolved and neither ID silently preferred,
  the ID-equality guard verified via AST to precede any Decimal selection),
  non-test `None`-fallback to `room_to_static_minimum` (never converted to zero, the
  output itself never `None`), test-campaign precedence (test-floor room above,
  equal to, and below static-minimum room; both individually zero; both
  simultaneously zero; a parametrised sweep proving the result always equals
  `min()` of the two inputs), Decimal behaviour (no float conversion, no
  arithmetic/subtraction/quantisation/rounding via AST and source-text checks,
  Decimal-context independence including confirming the global context's
  `prec`/`rounding` are unchanged after the function returns, extreme
  28-significant-digit Stage 10/13 values handled exactly), authorised-field-access
  verification (AST: exactly the four approved fields), earlier-stage separation
  (AST-verified no call to `calculate_campaign_static_budget_room`/
  `calculate_campaign_test_floor_room`/Stage 11/12/14/3–9 functions, no reference to
  `CampaignInput`/`ReviewSetup`), protection independence (protected and
  unprotected source campaigns with identical Stage 10/13 facts produce identical
  Stage 15 results, `is_protected`/`decrease_blocked` absent from the function
  source entirely, a campaign both test and protected resolved only from its Stage
  10/13 facts, no protection-based zero calculated), and integration with
  `validate_campaign_csv` + `calculate_campaign_static_budget_room` +
  `calculate_campaign_test_floor_room` over `data/sample_campaigns.csv` (order
  preserved; `G001=2500.00`, `M001=2000.00`, `G002=4000.00`, `G003=900.00`; Stages
  10–14's existing sample results independently re-verified via separate calls,
  never combined; G002's `decrease_blocked=True` and `4000.00` result both
  preserved separately; G003's `1100.00` static-minimum room and `900.00`
  test-floor room both remain visible, with Stage 15 selecting `900.00`).
  `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
  `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
  `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
  (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
  behavioural regression, and no existing test file required modification this
  stage. Full suite: 527 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30
  Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 186
  Stage 10/11/12/13/14/15 combined in `tests/test_constraints.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignTestAwareStaticDecreaseRoom` fields;
  exact non-test/test-campaign formulas; confirmation the output is never `None`;
  zero meaning; confirmation the result is a raw constraint only; separation from
  percentage caps and protection), `docs/DECISION_RULES.md` (frozen Stage 15
  test-aware static decrease-room rule, including the approved retained-spend-floor
  business meaning; percentage-cap intersection, protection application, raw
  directional intersections, and eligibility explicitly re-confirmed as pending
  later stages), and `docs/TEST_SCENARIOS.md` (23 concrete Stage 15 scenarios).

- Sprint 2, Development Stage 16: added `CampaignRawIncreaseLimit` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `raw_increase_limit: Decimal` only) and
  `resolve_campaign_raw_increase_limit(static_room: CampaignStaticBudgetRoom,
  raw_cap: CampaignRawPercentageMovementCap) -> CampaignRawIncreaseLimit` to
  `src/constraints.py`, alongside but fully separate from Stage 10's
  `CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room`, Stage 11's
  `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
  Stage 12's `CampaignRawPercentageMovementCap`/
  `calculate_campaign_raw_percentage_movement_cap`, Stage 13's
  `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, Stage 14's
  `CampaignProtectionConstraint`/`resolve_campaign_protection_constraint`, and Stage
  15's `CampaignTestAwareStaticDecreaseRoom`/
  `resolve_campaign_test_aware_static_decrease_room`, all unmodified. **Approved
  business rule:** `room_to_static_maximum` (Stage 10) and
  `raw_percentage_movement_cap` (Stage 12) are two independent upward constraints
  that apply simultaneously — the smaller controls: `raw_increase_limit =
  min(room_to_static_maximum, raw_percentage_movement_cap)`. A raw,
  increase-specific constraint only — not permission to increase a budget, not an
  effective increase, not eligibility, not a recommendation, and not a final
  movement amount; does not account for a raw decrease limit, Stage 14's protection
  constraint, or Stage 15's test-aware static decrease room. **Consumes Stage 10's
  and Stage 12's already-approved result objects directly** (never accepts or reads
  `CampaignInput`/`ReviewSetup`, never calls `calculate_campaign_static_budget_room`
  or `calculate_campaign_raw_percentage_movement_cap`, never recalculates either
  fact) to avoid duplicating their already-tested calculations. Requires
  `static_room.campaign_id == raw_cap.campaign_id`, checked before any Decimal
  selection, raising exactly `ValueError("Campaign IDs must match when resolving
  raw increase limit.")` otherwise with neither ID silently preferred. No arithmetic
  is performed — the selected `Decimal` operand is returned unchanged; no local
  `decimal` context, `CURRENCY_QUANTUM`, `ROUND_HALF_UP`, rounding, quantisation, or
  `float` conversion; ambient global `Decimal` precision cannot affect the result.
  Fully independent of Stages 11, 13, 14, and 15 — never reads
  `applicable_max_change_percentage`, `room_to_test_floor`, `decrease_blocked`, or
  `test_aware_static_decrease_room`; a protected campaign receives exactly the same
  Stage 16 result as an otherwise identical unprotected campaign with matching Stage
  10/12 facts, and no increase-side protection rule is inferred. `src/constants.py`,
  `src/models.py`, `src/validation.py`, `src/metrics.py`, `src/pacing.py`, and
  `src/classification.py` are unchanged.
- Sprint 2, Development Stage 16: extended `tests/test_constraints.py` with 40 new
  tests (all 186 existing Stage 10/11/12/13/14/15 tests preserved unchanged; 226
  tests total) covering result-model shape/immutability/field-type confirmation,
  incompatible-input rejection (`AttributeError`, no silent coercion), campaign-ID
  matching (matching IDs resolve normally, mismatched IDs raise the exact approved
  `ValueError` message with no result resolved and neither ID silently preferred,
  the ID-equality guard verified via AST to precede any Decimal selection),
  comparison (static-maximum-smaller, equal, raw-cap-smaller, static-maximum-zero,
  raw-cap-zero, both zero, a parametrised sweep proving the result always equals
  `min()` of the two inputs, the selected operand returned unchanged), Decimal
  behaviour (no float conversion, no arithmetic/rounding/quantisation via AST and
  source-text checks, Decimal-context independence including confirming the global
  context's `prec`/`rounding` are unchanged after the function returns, extreme
  28-significant-digit Stage 10/12 values handled exactly), authorised-field-access
  verification (AST: exactly the four approved fields), earlier-stage separation
  (AST-verified no call to `calculate_campaign_static_budget_room`/
  `calculate_campaign_raw_percentage_movement_cap`/Stage 11/13/14/15/3–9 functions,
  no reference to `CampaignInput`/`ReviewSetup`), protection/test independence
  (protected and unprotected source campaigns with identical Stage 10/12 facts
  produce identical Stage 16 results, non-test and test source campaigns likewise,
  a campaign both protected and test resolved only from its Stage 10/12 facts, no
  protection- or test-floor-based zero introduced), scope protection (no batch
  function, no raw decrease/combined model/effective-increase/eligibility/score/
  `RecommendationAction`/`ReasonCode`/allocation/conservation field), and
  integration with `validate_campaign_csv` + `resolve_campaign_applicable_change_percentage`
  + `calculate_campaign_raw_percentage_movement_cap` over `data/sample_campaigns.csv`
  (order preserved; `G001=600.00`, `M001=375.00`, `G002=1000.00`, `G003=240.00`;
  Stages 10–15's existing sample results independently re-verified via separate
  calls, never combined; G002's `decrease_blocked=True` and `1000.00` result both
  preserved separately; G003's Stage 13/15 decrease-specific facts preserved
  separately from the unaffected `240.00` result). `tests/test_models.py` (Stage 1),
  `tests/test_validation.py` (Stage 2), `tests/test_metrics.py` (Stage 3),
  `tests/test_pacing.py` (Stage 4), `tests/test_classification.py` (Stage 5),
  `tests/test_trend_classification.py` (Stage 6),
  `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
  behavioural regression, and no existing test file required modification this
  stage. Full suite: 567 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30
  Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 226
  Stage 10/11/12/13/14/15/16 combined in `tests/test_constraints.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignRawIncreaseLimit` fields; exact
  simultaneous-constraint business meaning; confirmation the output is never `None`;
  zero meaning; confirmation the result is a raw, increase-specific constraint only;
  separation from protection and test-floor rules), `docs/DECISION_RULES.md` (frozen
  Stage 16 raw increase limit rule, including the approved
  both-constraints-apply-simultaneously business meaning; raw decrease
  intersection, protection application, effective constraints, and eligibility
  explicitly re-confirmed as pending later stages), and `docs/TEST_SCENARIOS.md` (24
  concrete Stage 16 scenarios).

- Sprint 2, Development Stage 17: added `CampaignRawDecreaseLimit` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `raw_decrease_limit: Decimal` only)
  and `resolve_campaign_raw_decrease_limit(decrease_room:
  CampaignTestAwareStaticDecreaseRoom, raw_cap: CampaignRawPercentageMovementCap) ->
  CampaignRawDecreaseLimit` to `src/constraints.py`, alongside but fully separate
  from Stage 10's `CampaignStaticBudgetRoom`/`calculate_campaign_static_budget_room`,
  Stage 11's `CampaignApplicableChangePercentage`/
  `resolve_campaign_applicable_change_percentage`, Stage 12's
  `CampaignRawPercentageMovementCap`/`calculate_campaign_raw_percentage_movement_cap`,
  Stage 13's `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, Stage 14's
  `CampaignProtectionConstraint`/`resolve_campaign_protection_constraint`, Stage 15's
  `CampaignTestAwareStaticDecreaseRoom`/`resolve_campaign_test_aware_static_decrease_room`,
  and Stage 16's `CampaignRawIncreaseLimit`/`resolve_campaign_raw_increase_limit`,
  all unmodified. **Approved business rule:** `test_aware_static_decrease_room`
  (Stage 15) and `raw_percentage_movement_cap` (Stage 12) are two independent
  decrease-side constraints that apply simultaneously — the smaller controls:
  `raw_decrease_limit = min(test_aware_static_decrease_room,
  raw_percentage_movement_cap)`. A raw, decrease-specific constraint only — not
  permission to decrease a budget, not an effective decrease, not eligibility, not a
  recommendation, and not a final movement amount; a protected campaign still
  receives its neutral Stage 17 raw result, since Stage 14's protection constraint is
  not applied here. **Consumes Stage 15's and Stage 12's already-approved result
  objects directly** (never accepts or reads `CampaignInput`/`ReviewSetup`, never
  calls `resolve_campaign_test_aware_static_decrease_room` or
  `calculate_campaign_raw_percentage_movement_cap`, never reopens `minimum_budget`,
  `test_budget_floor`, `is_test_campaign`, `room_to_static_minimum`,
  `room_to_test_floor`, `current_budget`, or `applicable_max_change_percentage`) to
  avoid duplicating their already-tested calculations. Requires
  `decrease_room.campaign_id == raw_cap.campaign_id`, checked before any Decimal
  selection, raising exactly `ValueError("Campaign IDs must match when resolving raw
  decrease limit.")` otherwise with neither ID silently preferred. No arithmetic is
  performed — the selected `Decimal` operand is returned unchanged; no local
  `decimal` context, `CURRENCY_QUANTUM`, `ROUND_HALF_UP`, rounding, quantisation, or
  `float` conversion; ambient global `Decimal` precision cannot affect the result.
  Fully independent of Stages 10, 11, 13, 14, and 16 — never reads
  `room_to_static_maximum`, `room_to_static_minimum`,
  `applicable_max_change_percentage`, `room_to_test_floor`, `decrease_blocked`,
  `is_protected`, or `raw_increase_limit`; a protected campaign receives exactly the
  same Stage 17 result as an otherwise identical unprotected campaign with matching
  Stage 12/15 facts, and the result is never described as usable or permissible
  decrease. `src/constants.py`, `src/models.py`, `src/validation.py`,
  `src/metrics.py`, `src/pacing.py`, and `src/classification.py` are unchanged.
- Sprint 2, Development Stage 17: extended `tests/test_constraints.py` with 46 new
  tests (all 226 existing Stage 10/11/12/13/14/15/16 tests preserved unchanged; 272
  tests total) covering result-model shape/immutability/field-type confirmation,
  incompatible-input rejection (`AttributeError`, no silent coercion), campaign-ID
  matching (matching IDs resolve normally, mismatched IDs raise the exact approved
  `ValueError` message with no result resolved and neither ID silently preferred,
  the ID-equality guard verified via AST to precede any Decimal selection),
  comparison (Stage-15-room-smaller, equal, raw-cap-smaller, Stage-15-room-zero,
  raw-cap-zero, both zero, a parametrised sweep proving the result always equals
  `min()` of the two inputs, the selected operand returned unchanged), Decimal
  behaviour (no float conversion, no arithmetic/rounding/quantisation via AST and
  source-text checks, Decimal-context independence including confirming the global
  context's `prec`/`rounding` are unchanged after the function returns, extreme
  28-significant-digit Stage 12/15 values handled exactly), authorised-field-access
  verification (AST: exactly the four approved fields), earlier-stage separation
  (AST-verified no call to `resolve_campaign_test_aware_static_decrease_room`/
  `calculate_campaign_raw_percentage_movement_cap`/Stage 10/11/13/14/16/3–9
  functions, no reference to `CampaignInput`/`ReviewSetup`, source-text confirmation
  that `minimum_budget`/`test_budget_floor`/`is_test_campaign`/
  `room_to_static_minimum`/`room_to_test_floor`/`current_budget`/
  `applicable_max_change_percentage` are never reopened, and confirmation that only
  one `min()` call site exists), protection independence (protected and unprotected
  source campaigns with identical Stage 12/15 facts produce identical Stage 17
  results, a protected campaign still receives its neutral raw limit unconverted to
  zero, `decrease_blocked`/`is_protected` never read), test-campaign ownership
  (test status affects Stage 17 only through the completed Stage 15 result, Stage 13
  neither accepted nor called, Stage 15's precedence not reopened), Stage 16
  separation (`CampaignRawIncreaseLimit`/`raw_increase_limit` never referenced, no
  combined directional result model), scope protection (no batch function, no raw
  increase/effective/permissible-movement/eligibility/score/`RecommendationAction`/
  `ReasonCode`/allocation/conservation field), and integration with
  `validate_campaign_csv` + Stage 10–16's approved functions over
  `data/sample_campaigns.csv` (order preserved; `G001=600.00`, `M001=375.00`,
  `G002=1000.00`, `G003=240.00`; Stages 10–16's existing sample results
  independently re-verified via separate calls, never combined; G002's
  `decrease_blocked=True` and `1000.00` result both preserved separately; G003's
  Stage 13/15 decrease-specific facts (`900.00`) preserved separately from the
  percentage-cap-bound `240.00` result). `tests/test_models.py` (Stage 1),
  `tests/test_validation.py` (Stage 2), `tests/test_metrics.py` (Stage 3),
  `tests/test_pacing.py` (Stage 4), `tests/test_classification.py` (Stage 5),
  `tests/test_trend_classification.py` (Stage 6),
  `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
  behavioural regression, and no existing test file required modification this
  stage. Full suite: 613 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30
  Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 272
  Stage 10/11/12/13/14/15/16/17 combined in `tests/test_constraints.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignRawDecreaseLimit` fields; exact
  simultaneous-constraint business meaning; confirmation the output is never `None`
  and cannot be negative; zero meaning; confirmation the result is a raw,
  decrease-specific constraint only; separation from protection and the increase
  side), `docs/DECISION_RULES.md` (frozen Stage 17 raw decrease limit rule,
  including the approved both-constraints-apply-simultaneously business meaning;
  protection application, combined directional limits, effective constraints, and
  eligibility explicitly re-confirmed as pending later stages), and
  `docs/TEST_SCENARIOS.md` (26 concrete Stage 17 scenarios).

- Sprint 2, Development Stage 18: added `CampaignEffectiveDecreaseLimit` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `effective_decrease_limit: Decimal`
  only) and `resolve_campaign_effective_decrease_limit(raw_decrease:
  CampaignRawDecreaseLimit, protection: CampaignProtectionConstraint) ->
  CampaignEffectiveDecreaseLimit` to `src/constraints.py`, alongside but fully
  separate from Stage 10's `CampaignStaticBudgetRoom`/
  `calculate_campaign_static_budget_room`, Stage 11's
  `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
  Stage 12's `CampaignRawPercentageMovementCap`/
  `calculate_campaign_raw_percentage_movement_cap`, Stage 13's
  `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, Stage 14's
  `CampaignProtectionConstraint`/`resolve_campaign_protection_constraint`, Stage 15's
  `CampaignTestAwareStaticDecreaseRoom`/`resolve_campaign_test_aware_static_decrease_room`,
  Stage 16's `CampaignRawIncreaseLimit`/`resolve_campaign_raw_increase_limit`, and
  Stage 17's `CampaignRawDecreaseLimit`/`resolve_campaign_raw_decrease_limit`, all
  unmodified. **Approved business rule:** `decrease_blocked=True` means protection
  prohibits reducing the campaign, so `effective_decrease_limit = Decimal("0.00")`
  — a deliberate, computed effective constraint, never missing data, regardless of
  whether the raw value was positive, zero, or extreme; `decrease_blocked=False`
  means protection adds no further restriction, so `raw_decrease_limit` passes
  through unchanged. Still not eligibility, a recommendation, a final movement
  amount, an allocation, or a decision to decrease the campaign — a campaign with
  `effective_decrease_limit == Decimal("0.00")` may still later be eligible for
  `MAINTAIN` or `INCREASE`. `Decimal("0.00")` is used instead of `None` because
  protection-triggered zero is a computed, deliberate fact, not a
  non-applicability signal. **Consumes Stage 17's and Stage 14's already-approved
  result objects directly** (never accepts or reads `CampaignInput`/`ReviewSetup`,
  never calls `resolve_campaign_raw_decrease_limit` or
  `resolve_campaign_protection_constraint`, never reopens `is_protected`,
  `current_budget`, `minimum_budget`, `maximum_budget`, `test_budget_floor`,
  `is_test_campaign`, `applicable_max_change_percentage`, `room_to_static_minimum`,
  `room_to_test_floor`, `test_aware_static_decrease_room`, or
  `raw_percentage_movement_cap`) to avoid duplicating their already-tested
  calculations. Requires `raw_decrease.campaign_id == protection.campaign_id`,
  checked before reading `decrease_blocked` for selection or resolving any Decimal
  result, raising exactly `ValueError("Campaign IDs must match when resolving
  effective decrease limit.")` otherwise with neither ID silently preferred. No
  arithmetic is performed — the unprotected branch returns the selected `Decimal`
  operand unchanged, the protected branch constructs the literal `Decimal("0.00")`
  using the existing `Decimal` import (no new `ZERO` constant added to
  `src/constants.py`, which is unmodified); no local `decimal` context,
  `CURRENCY_QUANTUM`, `ROUND_HALF_UP`, rounding, quantisation, or `float`
  conversion; ambient global `Decimal` precision cannot affect either branch. Does
  **not** create `CampaignEffectiveIncreaseLimit`, `effective_increase_limit`, or a
  combined effective-directional result — no approved constraint remains to
  transform Stage 16's raw increase limit, and protection has no approved
  increase-side effect, so `CampaignRawIncreaseLimit` remains the authoritative
  increase-side constraint. `src/constants.py`, `src/models.py`,
  `src/validation.py`, `src/metrics.py`, `src/pacing.py`, and
  `src/classification.py` are unchanged.
- Sprint 2, Development Stage 18: extended `tests/test_constraints.py` with 50 new
  tests (all 272 existing Stage 10/11/12/13/14/15/16/17 tests preserved unchanged;
  322 tests total) covering result-model shape/immutability/field-type
  confirmation (no `raw_decrease_limit`/`decrease_blocked`/`raw_increase_limit`/
  `effective_increase_limit`/eligibility/action/score/allocation field),
  incompatible-input rejection (`AttributeError`, no silent coercion), campaign-ID
  matching (matching IDs resolve normally, mismatched IDs raise the exact approved
  `ValueError` message with no result resolved and neither ID silently preferred,
  the ID-equality guard verified via AST to precede any Boolean/Decimal
  selection), Boolean mapping (protected positive-raw, unprotected positive-raw,
  protected zero-raw, unprotected zero-raw, an exhaustive True/False parametrised
  sweep, no `BoolOp`/truthiness fallback), exact zero representation (protected
  result's `Decimal` tuple equals `Decimal("0.00")`'s exactly, never
  `Decimal("0")`'s, never `None`, never raises), Decimal behaviour (no float
  conversion, no arithmetic/rounding/quantisation via AST and source-text checks,
  unprotected operand returned unchanged, Decimal-context independence including
  confirming the global context's `prec`/`rounding` are unchanged after the
  function returns, extreme 28-significant-digit Stage 17 values handled exactly
  in both branches), authorised-field-access verification (AST: exactly the four
  approved fields), earlier-stage separation (AST-verified no call to
  `resolve_campaign_raw_decrease_limit`/`resolve_campaign_protection_constraint`/
  Stage 10/11/12/13/15/16/3–9 functions, no reference to `CampaignInput`/
  `ReviewSetup`, source-text confirmation that `is_protected`/`current_budget`/
  `minimum_budget`/`maximum_budget`/`test_budget_floor`/`is_test_campaign`/
  `applicable_max_change_percentage`/`room_to_static_minimum`/`room_to_test_floor`/
  `test_aware_static_decrease_room`/`raw_percentage_movement_cap` are never
  reopened), increase-side separation (`CampaignRawIncreaseLimit`/
  `raw_increase_limit` never referenced, no `effective_increase_limit` field or
  `CampaignEffectiveIncreaseLimit` model exists, protected status given no
  increase-side meaning, no combined directional result), traceability (Stage 14's
  Boolean and Stage 17's raw Decimal remain preserved and unmutated on their own
  frozen objects after Stage 18 resolves), eligibility boundary (no eligible/
  ineligible output, a zero effective decrease limit does not imply whole-campaign
  ineligibility, no `RecommendationAction`/`ReasonCode`/score/allocation/
  conservation output), a synthetic protected-test-campaign case (Stage 15's
  precedence and Stage 14's protection each independently resolved upstream, not
  recalculated inside Stage 18), no production batch function, and integration
  with `validate_campaign_csv` + Stage 10–17's approved functions over
  `data/sample_campaigns.csv` (order preserved; `G001=600.00`, `M001=375.00`,
  `G002=0.00`, `G003=240.00`; Stages 10–17's existing sample results independently
  re-verified via separate calls, never combined; G002's `decrease_blocked=True`,
  `raw_decrease_limit=1000.00`, and `effective_decrease_limit=0.00` all hold
  simultaneously and separately, with `raw_increase_limit=1000.00` confirmed
  unaffected; G003's `raw_decrease_limit=240.00` passes through unchanged to
  `effective_decrease_limit=240.00`, with Stage 15's test-floor logic not
  reopened). `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage
  2), `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
  `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
  (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
  behavioural regression, and no existing test file required modification this
  stage. Full suite: 663 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30
  Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 322
  Stage 10/11/12/13/14/15/16/17/18 combined in `tests/test_constraints.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignEffectiveDecreaseLimit` fields; exact
  protected/unprotected mapping; meaning of `effective_decrease_limit`; exact zero
  and `None` behaviour; confirmation raw/protection facts remain separate;
  confirmation no effective increase is produced; confirmation this is not
  eligibility or a recommendation), `docs/DECISION_RULES.md` (frozen Stage 18
  protection-adjusted effective decrease limit rule, including why `Decimal("0.00")`
  is used instead of `None`; separation from Stage 16; confirmation protection has
  no approved increase-side effect; deferral of eligibility and combined campaign
  assessment explicitly re-confirmed as pending later stages), and
  `docs/TEST_SCENARIOS.md` (26 concrete Stage 18 scenarios).

- Sprint 2, Development Stage 19: added a new dedicated module,
  `src/availability.py`, containing `CampaignActionAvailability` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `increase_available: bool`,
  `maintain_available: bool`, `reduce_available: bool` only) and
  `resolve_campaign_action_availability(campaign: CampaignInput, tracking:
  CampaignTrackingAssessment, raw_increase: CampaignRawIncreaseLimit,
  effective_decrease: CampaignEffectiveDecreaseLimit) ->
  CampaignActionAvailability`. Determines whether `INCREASE`, `MAINTAIN`, and
  `REDUCE` are each mechanically and operationally available — using the term
  **"availability,"** never "eligibility." Availability means an action is not
  prevented by campaign status, tracking-based assessability, or the relevant
  approved monetary capacity; it does **not** mean the action is advisable —
  positive capacity establishes only that a direction is mechanically possible,
  never a recommendation. Does not decide which available action is suitable,
  which action should be recommended, `HOLD`, scoring, priority, ranking,
  `ReasonCode`, or allocation; `hold_available` is deliberately excluded, since
  `HOLD` is a later review/deferral or recommendation outcome whose exact trigger
  remains undecided. **Approved mapping:** `is_active = campaign.status is
  CampaignStatus.ACTIVE`; `increase_available = is_active and
  tracking.is_assessable and raw_increase.raw_increase_limit >
  Decimal("0.00")`; `maintain_available = is_active`; `reduce_available =
  is_active and tracking.is_assessable and
  effective_decrease.effective_decrease_limit > Decimal("0.00")`. Paused
  campaigns receive all three fields `False` — always one result object, never
  an error, never `HOLD`, never a reason code. Unassessable Active campaigns get
  `increase_available=False`/`reduce_available=False` while
  `maintain_available=True` remains unaffected, since leaving the budget
  unchanged requires no data confidence. **Consumes Stage 8's, Stage 16's, and
  Stage 18's already-approved result objects directly** (never calls
  `assess_campaign_tracking`, `resolve_campaign_raw_increase_limit`,
  `resolve_campaign_effective_decrease_limit`, or any other Stage 1–18
  production function) plus `CampaignInput` directly for identity/status — no
  new status-wrapper model was created, since one would only duplicate
  `campaign_id`/`status` without producing a new fact, mirroring the Stage 14
  precedent of consuming `CampaignInput` directly. Requires all four
  `campaign_id` values to match via one combined equality check anchored to
  `campaign.campaign_id`, checked before any status/assessability/Decimal
  evaluation, raising exactly `ValueError("Campaign IDs must match when
  resolving action availability.")` otherwise, with the same exact message
  regardless of which input(s) mismatch. No arithmetic is performed — only
  enum-identity comparison, Boolean conjunction, and `Decimal` comparison
  against `Decimal("0.00")`; no local `decimal` context, `CURRENCY_QUANTUM`,
  `ROUND_HALF_UP`, rounding, quantisation, or `float` conversion; ambient
  global `Decimal` precision cannot affect the result. Never reads
  `tracking_status`, `is_protected`, `decrease_blocked`, `is_test_campaign`,
  `test_budget_floor`, `minimum_budget`, `maximum_budget`, `PerformanceBand`,
  `TrendDirection`, `Confidence`, `PacingStatus`, or `BusinessPriority` —
  these are suitability/scoring inputs, not availability inputs. A dedicated
  module was chosen over `src/constraints.py`/`src/classification.py`/
  `src/scoring.py` because action availability spans campaign status, tracking
  assessability, and both directional monetary constraints simultaneously, and
  is not purely a monetary constraint, a descriptive classification, or a
  score. `src/constraints.py`, `src/classification.py`, `src/constants.py`,
  `src/models.py`, `src/validation.py`, `src/metrics.py`, and `src/pacing.py`
  are unchanged.
- Sprint 2, Development Stage 19: added a new dedicated test file,
  `tests/test_availability.py` (61 tests, all passing;
  `tests/test_constraints.py` unchanged at 322 tests) covering result-model
  shape/immutability/field-type confirmation (no `hold_available`/eligibility/
  monetary/classification/priority field), incompatible-input rejection
  (`AttributeError`, no silent coercion), campaign-ID matching (all four IDs
  equal resolves normally; mismatch on any one of the three non-anchor inputs,
  or multiple simultaneous mismatches, raises the exact approved `ValueError`
  message with no result resolved and no ID silently preferred; the
  ID-equality guard verified via AST to precede any status/assessability/
  Decimal evaluation), the full active/assessable decision-table sweep (four
  positive/zero increase-and-decrease combinations), active/unassessable
  behaviour (directional limits never override the assessability gate;
  `maintain_available` unaffected, parametrised across every zero/positive
  combination), Paused behaviour (assessable/unassessable/zero-limit cases all
  producing `(False, False, False)`; a Paused campaign always receives one
  result object; no `HOLD`/reason-code field present), tracking cases via the
  real `assess_campaign_tracking` production path (`Healthy`/`Warning` both
  assessable per Stage 8's own frozen rule, `Unreliable` blocking both
  directions while `maintain_available` remains `True`; AST-verified that only
  `is_assessable` is read from the tracking object and that `tracking_status`
  is never referenced), capacity cases (exact `Decimal("0.00")` boundary,
  smallest positive currency amount, extreme 28-significant-digit values, no
  negative-value correction/clamping, no input monetary value mutated),
  protected/test cases (a protected active campaign built through the real
  Stage 10–18 production chain showing `increase_available=True`/
  `reduce_available=False`; a test campaign showing all three `True`; a
  synthetic protected-and-test campaign following only its already-computed
  capacities; source-verified absence of `is_protected`/`decrease_blocked`/
  `is_test_campaign`/`test_budget_floor`), independence from
  `PerformanceBand`/`TrendDirection`/`Confidence`/`PacingStatus`/
  `BusinessPriority`/`RecommendationAction`/`ReasonCode` (AST- and
  module-attribute-verified), earlier-stage separation (AST-verified no call
  to `assess_campaign_tracking`/`resolve_campaign_raw_increase_limit`/
  `resolve_campaign_effective_decrease_limit`/any other Stage 1–18 function;
  exactly eight authorised field accesses verified via AST), Decimal-context
  independence (including a mutated-global-context test and confirmation the
  global context's `prec`/`rounding` are unchanged after the function
  returns), no production batch function, and sample-data integration through
  `validate_campaign_csv` + the real Stage 8/10–18 production chain over
  `data/sample_campaigns.csv` (order preserved; `G001=(True, True, True)`,
  `M001=(True, True, True)`, `G002=(True, True, False)`,
  `G003=(True, True, True)`; G002's underlying facts — `status=Active`,
  `tracking.is_assessable=True`, `raw_increase_limit=1000.00`,
  `effective_decrease_limit=0.00` — independently re-verified, with no
  protection field read and no action recommended), plus five synthetic
  integration cases (Paused, unreliable tracking, warning tracking, both
  directional limits zero, protected-and-test). `tests/test_models.py`
  (Stage 1), `tests/test_validation.py` (Stage 2), `tests/test_metrics.py`
  (Stage 3), `tests/test_pacing.py` (Stage 4), `tests/test_classification.py`
  (Stage 5), `tests/test_trend_classification.py` (Stage 6),
  `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed
  passing — no behavioural regression, and no existing test file required
  modification this stage. Full suite: 724 tests passing (92 Stage 1 + 44
  Stage 2 + 28 Stage 3 + 30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30
  Stage 8 + 33 Stage 9 + 322 Stage 10–18 combined in `tests/test_constraints.py`
  + 61 Stage 19 in `tests/test_availability.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignActionAvailability` fields; the
  definition of availability; exact active/paused policy; exact assessability
  policy; exact directional-capacity rules; `MAINTAIN` meaning; `HOLD`
  exclusion; separation from suitability and recommendation),
  `docs/DECISION_RULES.md` (frozen Stage 19 campaign action availability rule,
  including the exact mapping, the exact eight authorised fields, the
  campaign-ID policy and error, the status/assessability/capacity policies,
  the exclusion of confidence/pacing/performance/trend/priority, the
  `ReasonCode`/`HOLD` deferral, the `CampaignInput`-ownership decision, the
  dedicated-module decision, and the corrected cross-campaign-boundary note),
  and `docs/TEST_SCENARIOS.md` (40 concrete Stage 19 scenarios).

- Sprint 2, Development Stage 20: added a new dedicated module,
  `src/suitability.py`, containing `Suitability` (`str, Enum`: `SUITABLE =
  "Suitable"`, `NEUTRAL = "Neutral"`, `UNSUITABLE = "Unsuitable"`,
  `NOT_APPLICABLE = "Not Applicable"` — purely categorical, no numeric value,
  no ordering, no `SUITABLE > NEUTRAL`-style comparison), `CampaignActionSuitability`
  (frozen, immutable, `extra="forbid"`: `campaign_id`, `increase_suitability:
  Suitability`, `maintain_suitability: Suitability`, `reduce_suitability:
  Suitability` only), and `resolve_campaign_action_suitability(performance:
  CampaignPerformanceClass, trend: CampaignTrendClass, availability:
  CampaignActionAvailability) -> CampaignActionSuitability`. Determines a
  categorical, per-direction suitability for `INCREASE`, `MAINTAIN`, and
  `REDUCE` — availability answers "can this action be taken mechanically and
  operationally?"; suitability answers "do the approved performance and trend
  classifications provide a clear directional signal supporting this
  available action?" Suitability does **not** mean recommendation — a
  `SUITABLE` action is not automatically selected, a `NEUTRAL` action is not
  automatically rejected, and an `UNSUITABLE` action is not a final
  prohibition. **Approved conservative diagonal-only rule:** only the three
  cells where `PerformanceBand` and `TrendDirection` clearly agree
  (`ABOVE_TARGET`+`IMPROVING`, `ON_TARGET`+`STABLE`,
  `BELOW_TARGET`+`DECLINING`) produce a directional `SUITABLE`/`UNSUITABLE`
  result; all six conflicting or mixed combinations resolve to `NEUTRAL` for
  every direction, deliberately avoiding a performance-vs-trend precedence
  decision. Exact complete nine-cell base table:
  ```
  ABOVE_TARGET + IMPROVING  → SUITABLE,   NEUTRAL, UNSUITABLE
  ABOVE_TARGET + STABLE     → NEUTRAL,    NEUTRAL, NEUTRAL
  ABOVE_TARGET + DECLINING  → NEUTRAL,    NEUTRAL, NEUTRAL
  ON_TARGET    + IMPROVING  → NEUTRAL,    NEUTRAL, NEUTRAL
  ON_TARGET    + STABLE     → NEUTRAL,    SUITABLE, NEUTRAL
  ON_TARGET    + DECLINING  → NEUTRAL,    NEUTRAL, NEUTRAL
  BELOW_TARGET + IMPROVING  → NEUTRAL,    NEUTRAL, NEUTRAL
  BELOW_TARGET + STABLE     → NEUTRAL,    NEUTRAL, NEUTRAL
  BELOW_TARGET + DECLINING  → UNSUITABLE, NEUTRAL, SUITABLE
  ```
  implemented as a module-level immutable `MappingProxyType` containing
  exactly all nine `PerformanceBand`×`TrendDirection` keys, never mutated at
  runtime, no numeric weight, no `RecommendationAction`/`ReasonCode`, and no
  dependency on enum declaration order. **Availability-first override:**
  applied independently per direction after the base-table lookup — an
  unavailable direction is always `Suitability.NOT_APPLICABLE`, overriding
  the base table; never `None`, a numeric zero, or `UNSUITABLE`. For an
  Active but unassessable campaign, Stage 19 already makes
  `INCREASE`/`REDUCE` unavailable, so Stage 20 returns `NOT_APPLICABLE` for
  both while `MAINTAIN` still receives its base-table result — Stage 20
  never decides `MAINTAIN` versus `HOLD`. **Consumes Stage 5's, Stage 6's,
  and Stage 19's already-approved result objects directly** (never calls
  `classify_campaign_performance`, `classify_campaign_trend`, or
  `resolve_campaign_action_availability`, and never accepts
  `CampaignInput`/`ReviewSetup`/`CampaignTrackingAssessment`) — no
  combined-assessment data-carrier model was created. Requires all three
  `campaign_id` values to match via one combined equality check anchored to
  `performance.campaign_id`, checked before any rule-table lookup or
  availability evaluation, raising exactly `ValueError("Campaign IDs must
  match when resolving action suitability.")` otherwise with the same exact
  message regardless of which input(s) mismatch. Excludes `Confidence`
  (including any `Confidence.NOT_ASSESSABLE` relationship), `PacingStatus`,
  and `BusinessPriority` entirely; outputs no `ReasonCode`; selects no
  `RecommendationAction`/`HOLD`. No `Decimal` import, arithmetic, local
  Decimal context, `CURRENCY_QUANTUM`, `ROUND_HALF_UP`, or `float`
  conversion is used anywhere — only enum-identity comparison, a fixed
  mapping lookup, and Boolean gating. A dedicated module was chosen over
  `src/classification.py`/`src/constraints.py`/`src/availability.py`/
  `src/scoring.py` because suitability combines classification-domain
  performance, classification-domain trend, and availability-domain action
  gates simultaneously, and is not a raw classification, a monetary
  constraint, availability, or numeric scoring; `src/scoring.py` remains
  unchanged, reserved for later numeric prioritisation-scoring work.
  `src/classification.py`, `src/constraints.py`, `src/availability.py`,
  `src/constants.py`, `src/models.py`, `src/validation.py`, `src/metrics.py`,
  and `src/pacing.py` are unchanged.
- Sprint 2, Development Stage 20: added a new dedicated test file,
  `tests/test_suitability.py` (67 tests, all passing;
  `tests/test_availability.py` unchanged at 61 tests,
  `tests/test_constraints.py` unchanged at 322 tests) covering the
  `Suitability` enum (exactly four members with exact string values, no
  numeric base class, no `__lt__`/`__gt__`/`__le__`/`__ge__` defined, disjoint
  from `RecommendationAction`'s values, no `HOLD` member), result-model
  shape/immutability/field-type confirmation (no score/action/reason/
  confidence/pacing/priority/allocation/availability-boolean field),
  incompatible-input rejection (`AttributeError`, no silent coercion),
  campaign-ID matching (all three IDs equal resolves normally; performance/
  trend and performance/availability mismatches, and multiple simultaneous
  mismatches, each raise the exact approved `ValueError` message with no
  result resolved and no ID silently preferred; the ID-equality guard
  verified via AST to precede any rule-table lookup or availability read),
  the complete nine-cell base table with all actions available (all nine
  `PerformanceBand`×`TrendDirection` combinations asserted exactly),
  availability overrides (each direction independently `NOT_APPLICABLE` when
  unavailable, in both diagonal and conflict cells; unavailable never becomes
  `UNSUITABLE`; available conflict cells remain `NEUTRAL`; an "only maintain
  available" case; an "all unavailable" case), Stage 19 scenarios via the
  real Stage 3/5/6/8/10–19 production path (a Paused campaign producing all
  `NOT_APPLICABLE`; an unassessable-tracking campaign producing
  `NOT_APPLICABLE` for increase/reduce with maintain using the base table; a
  protected campaign producing `NOT_APPLICABLE` for reduce only, with
  `is_protected`/`decrease_blocked` never read directly; a test campaign
  using the base table for all three; a synthetic protected-and-test
  campaign following only its supplied availability), independence from
  `Confidence`/`CampaignConfidenceClass`/`PacingStatus`/`CampaignPacingClass`/
  `BusinessPriority`/`CampaignTrackingAssessment`/`RecommendationAction`/
  `ReasonCode`/`Decimal`/raw performance ratios/raw trend delta (AST- and
  module-attribute-verified), earlier-stage separation (AST-verified no call
  to `classify_campaign_performance`/`classify_campaign_trend`/
  `resolve_campaign_action_availability`/any other Stage 1–19 function;
  exactly eight authorised field accesses verified via AST), no numeric
  scoring (no arithmetic `BinOp`, no `float` conversion, no `score`-named
  field, no production batch function), and sample-data integration through
  `validate_campaign_csv` + the real production chain over
  `data/sample_campaigns.csv` (order preserved; `G001`/`M001`/`G003` all
  producing `(NEUTRAL, SUITABLE, NEUTRAL)`; `G002` producing `(SUITABLE,
  NEUTRAL, NOT_APPLICABLE)` with `REDUCE` explicitly confirmed as
  `NOT_APPLICABLE` rather than `UNSUITABLE`, protection never read directly,
  and `INCREASE` being `SUITABLE` confirmed not to select any
  `RecommendationAction`), plus synthetic integration cases for all six
  conflicting/mixed combinations (all `NEUTRAL` for every direction when
  available) and every availability pattern applied to a conflict cell.
  `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
  `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
  `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
  (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed
  passing — no behavioural regression, and no existing test file required
  modification this stage. Full suite: 791 tests passing (92 Stage 1 + 44
  Stage 2 + 28 Stage 3 + 30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 +
  30 Stage 8 + 33 Stage 9 + 322 Stage 10–18 combined in
  `tests/test_constraints.py` + 61 Stage 19 in `tests/test_availability.py` +
  67 Stage 20 in `tests/test_suitability.py`).
- Updated `docs/DATA_DICTIONARY.md` (`Suitability` enum; `CampaignActionSuitability`
  fields; the definition of suitability; the complete 3×3 rule table; the
  availability override; `NOT_APPLICABLE` meaning; exclusion of confidence,
  pacing, priority, `HOLD`, action, and reason codes),
  `docs/DECISION_RULES.md` (frozen Stage 20 conservative diagonal-only
  campaign action suitability rule, including the exact nine-cell table, the
  exact three inputs and eight authorised fields, the campaign-ID policy and
  error, the availability-first override rule, confirmation the six conflict
  cells remain `NEUTRAL` with no performance/trend precedence decided, no
  numeric weights, and the deferral of confidence, pacing, priority,
  `RecommendationAction`, and `ReasonCode` explicitly re-confirmed as pending
  later stages), and `docs/TEST_SCENARIOS.md` (39 concrete Stage 20
  scenarios).

- Sprint 2, Development Stage 21: added a new dedicated module,
  `src/recommendation.py`, containing `CampaignRecommendation` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `recommendation_action:
  RecommendationAction` only, reusing the existing `RecommendationAction`
  enum unchanged) and `resolve_campaign_recommendation_action(campaign:
  CampaignInput, suitability: CampaignActionSuitability, tracking:
  CampaignTrackingAssessment) -> CampaignRecommendation`. Selects exactly
  one `RecommendationAction` (`INCREASE`/`MAINTAIN`/`REDUCE`/`HOLD`) per
  campaign, using campaign status, tracking assessability, and Stage 20
  action suitability. **Approved HOLD-versus-MAINTAIN meaning:** `MAINTAIN`
  means the campaign was eligible for automated assessment, no available
  action had a uniquely stronger directional suitability, and keeping the
  budget unchanged is the selected recommendation — an assessed no-change
  decision; `HOLD` means the engine must not make an automated directional
  budget recommendation for this review — because the campaign is paused,
  its tracking is unassessable, its suitability input is ambiguous, or no
  valid fallback action is available. `RecommendationAction` selection here
  is a **provisional direction only** — no monetary amount is calculated.
  **Approved exact ordered policy**, applied after campaign-ID validation:
  (1) Paused override — `campaign.status is CampaignStatus.PAUSED` →
  `HOLD`, overriding all suitability, read explicitly from
  `CampaignInput.status`, never inferred from suitability shape even though
  such an inference is currently structurally valid under Stage 19's frozen
  rule; (2) tracking-assessability override — `not tracking.is_assessable`
  → `HOLD`, overriding all suitability, with `WARNING` remaining assessable
  per Stage 8's frozen rule and only `is_assessable` ever read, never
  `tracking_status`; (3) unique-`SUITABLE` selection — exactly one field
  `SUITABLE` → that action; (4) multiple-`SUITABLE` ambiguity — more than
  one field `SUITABLE` → `HOLD`, with no fixed precedence, no first-field
  selection, no `MAINTAIN` default, and no error, since this cannot arise
  through the approved Stage 20 production table but a directly
  constructed `CampaignActionSuitability` could contain it; (5)
  conservative `MAINTAIN` fallback — no `SUITABLE`, `maintain_suitability
  is Suitability.NEUTRAL` → `MAINTAIN`, regardless of
  `increase_suitability`/`reduce_suitability`'s own values; (6) final
  `HOLD` fallback — no `SUITABLE`, `maintain_suitability` is `UNSUITABLE`
  or `NOT_APPLICABLE` → `HOLD`. A `Suitability.NOT_APPLICABLE` value is
  never selected as an action — `RecommendationAction` has no
  `NOT_APPLICABLE` member. **Consumes Stage 20's and Stage 8's
  already-approved result objects directly** (never calls
  `resolve_campaign_action_suitability`, `assess_campaign_tracking`,
  `resolve_campaign_action_availability`, or any other Stage 1–20
  production function) plus `CampaignInput` directly for explicit status —
  `CampaignActionAvailability` is not accepted separately, since Stage 20
  has already applied availability through `NOT_APPLICABLE`. Requires all
  three `campaign_id` values to match via one combined equality check
  anchored to `campaign.campaign_id`, checked before any
  status/assessability/suitability evaluation, raising exactly
  `ValueError("Campaign IDs must match when resolving recommendation
  action.")` otherwise with the same exact message regardless of which
  input(s) mismatch. Never reads `is_protected`, `decrease_blocked`,
  `is_test_campaign`, or `test_budget_floor` — a protected campaign may
  still receive `INCREASE` or `MAINTAIN`, while `REDUCE` is structurally
  unavailable for a protected campaign through the approved Stage 18–20
  path. Excludes `Confidence`, `PacingStatus`, and `BusinessPriority`
  entirely; outputs no `ReasonCode`. A dedicated module was chosen over
  `src/suitability.py`/`src/availability.py`/`src/scoring.py`/
  `src/classification.py`/`src/constraints.py` because Stage 21 selects a
  recommendation outcome, separate from classification, constraints,
  availability, suitability, scoring, and allocation. No `Decimal`
  calculation occurs anywhere. `src/suitability.py`, `src/availability.py`,
  `src/scoring.py`, `src/classification.py`, `src/constraints.py`,
  `src/constants.py`, `src/models.py`, `src/validation.py`,
  `src/metrics.py`, and `src/pacing.py` are unchanged.
- Sprint 2, Development Stage 21: added a new dedicated test file,
  `tests/test_recommendation.py` (84 tests, all passing;
  `tests/test_suitability.py` unchanged at 67 tests,
  `tests/test_availability.py` unchanged at 61 tests,
  `tests/test_constraints.py` unchanged at 322 tests) covering result-model
  shape/immutability/field-type confirmation (no reason/confidence/score/
  rank/priority/monetary/availability-or-suitability field),
  incompatible-input rejection (`AttributeError`, no silent coercion, no
  broad exception handling), campaign-ID matching (all three IDs equal
  resolves normally; suitability/tracking mismatches and multiple
  simultaneous mismatches each raise the exact approved `ValueError`
  message with no result resolved and no ID silently preferred; the
  ID-equality guard verified via AST to precede any
  status/assessability/suitability evaluation), the Paused override (all
  three single-direction `SUITABLE` cases, unassessable, all-`NEUTRAL`, and
  multiple-`SUITABLE` cases each producing `HOLD` unconditionally; Paused
  confirmed never to raise), the tracking-assessability override (the same
  five sub-cases for an Active-but-unassessable campaign, each producing
  `HOLD`; `WARNING`/assessable confirmed to follow ordinary selection via
  the real `assess_campaign_tracking` path; source-verified that only
  `is_assessable` is read, never `tracking_status`), unique-`SUITABLE`
  selection (each of `INCREASE`/`MAINTAIN`/`REDUCE` selected when uniquely
  `SUITABLE`, parametrised across every combination of the other two
  fields' `NEUTRAL`/`UNSUITABLE`/`NOT_APPLICABLE` values, and confirmed
  independent of `Suitability`'s enum declaration order), the no-`SUITABLE`
  fallback (all-`NEUTRAL`, and `INCREASE`-or-`REDUCE`-`UNSUITABLE`-or-
  `NOT_APPLICABLE`-with-`maintain`-`NEUTRAL` cases all producing
  `MAINTAIN`; `maintain`-`UNSUITABLE`, `maintain`-`NOT_APPLICABLE`,
  all-`NOT_APPLICABLE`, and all-`UNSUITABLE` cases all producing `HOLD`),
  the multiple-`SUITABLE` ambiguity rule (every pairwise and three-way
  `SUITABLE` combination producing `HOLD`, with explicit confirmation of no
  fixed precedence, no error, and no silent `MAINTAIN`/`INCREASE`
  fallback), production-path cases via the real Stage 3/5/6/8/10–20 chain
  (the three diagonal cells selecting `INCREASE`/`MAINTAIN`/`REDUCE`
  respectively; all six mixed/conflicting cells selecting `MAINTAIN` when
  Active and assessable; a protected campaign confirmed unable to resolve
  `REDUCE`; a test campaign and a protected-and-test campaign both
  following ordinary resolution from their supplied suitability),
  independence from `ReasonCode`/`Confidence`/`CampaignConfidenceClass`/
  `PacingStatus`/`CampaignPacingClass`/`BusinessPriority`/
  `CampaignActionAvailability`/raw monetary limit fields/`is_protected`/
  `decrease_blocked`/`is_test_campaign`/`test_budget_floor` (AST- and
  module-attribute-verified), earlier-stage separation (AST-verified no
  call to `resolve_campaign_action_suitability`/`assess_campaign_tracking`/
  `resolve_campaign_action_availability`/any other Stage 1–20 function;
  exactly eight authorised field accesses verified via AST), no production
  batch function, and sample-data integration through
  `validate_campaign_csv` + the real production chain over
  `data/sample_campaigns.csv` (order preserved; `G001`/`M001`/`G003` all
  `MAINTAIN`; `G002` `INCREASE`, with its underlying facts — `status=Active`,
  `tracking.is_assessable=True`,
  `suitability=(SUITABLE, NEUTRAL, NOT_APPLICABLE)` — independently
  re-verified, no monetary amount calculated, no `ReasonCode` produced),
  plus eight synthetic integration cases (Paused, unreliable tracking,
  warning tracking, `BELOW_TARGET`+`DECLINING` with `REDUCE`
  available/unavailable, a manually constructed multiple-`SUITABLE` input,
  and a protected-and-test campaign). `tests/test_models.py` (Stage 1),
  `tests/test_validation.py` (Stage 2), `tests/test_metrics.py` (Stage 3),
  `tests/test_pacing.py` (Stage 4), `tests/test_classification.py` (Stage
  5), `tests/test_trend_classification.py` (Stage 6),
  `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed
  passing — no behavioural regression, and no existing test file required
  modification this stage. Full suite: 875 tests passing (92 Stage 1 + 44
  Stage 2 + 28 Stage 3 + 30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 +
  30 Stage 8 + 33 Stage 9 + 322 Stage 10–18 combined in
  `tests/test_constraints.py` + 61 Stage 19 in `tests/test_availability.py`
  + 67 Stage 20 in `tests/test_suitability.py` + 84 Stage 21 in
  `tests/test_recommendation.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignRecommendation` fields; the
  HOLD-versus-MAINTAIN meaning; the complete ordered action-selection
  policy; the Paused and assessability overrides; the unique/multiple/no-
  `SUITABLE` rules; explicit-status ownership; reason-code and monetary
  exclusions), `docs/DECISION_RULES.md` (frozen Stage 21 ordered campaign
  recommendation-action selection rule, including the exact six-rule
  policy, the exact three inputs and eight authorised fields, the
  campaign-ID policy and error, the explicit Paused rule, the tracking-
  assessability override, the unique-suitable mapping, the multiple-
  suitable `HOLD` rule, the `MAINTAIN` fallback boundary, the final `HOLD`
  fallback, and the deferral of confidence, pacing, priority, and
  `ReasonCode` explicitly re-confirmed as pending later stages), and
  `docs/TEST_SCENARIOS.md` (58 concrete Stage 21 scenarios).

- Sprint 2, Development Stage 22: added a new dedicated module,
  `src/reasons.py`, containing `CampaignRecommendationReason` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `reason_codes:
  tuple[ReasonCode, ...]` only — does not duplicate `recommendation_action`)
  and `resolve_campaign_recommendation_reason(recommendation:
  CampaignRecommendation, campaign: CampaignInput, suitability:
  CampaignActionSuitability, tracking: CampaignTrackingAssessment,
  performance: CampaignPerformanceClass, trend: CampaignTrendClass) ->
  CampaignRecommendationReason`. Explains, for one already-selected
  `CampaignRecommendation` (Stage 21), why that action was selected — a
  non-empty, ordered, deduplicated tuple of `ReasonCode` containing only
  facts that causally participated in Stage 21's decision. **Approved HOLD
  precedence**, mirroring Stage 21's exact rule order: `campaign.status is
  CampaignStatus.PAUSED` → `(PAUSED_CAMPAIGN,)`, remaining the sole reason
  even when tracking is also unassessable, since Stage 21's own
  short-circuit logic never reaches the assessability check once Paused has
  already resolved `HOLD`; otherwise `not tracking.is_assessable` →
  `(TRACKING_UNRELIABLE,)`; otherwise (multiple-`SUITABLE` ambiguity or no
  valid `MAINTAIN` fallback — the only two remaining ways Stage 21 can
  produce `HOLD`) → `(HELD_FOR_MANUAL_REVIEW,)`, never used for a non-HOLD
  action. **Approved INCREASE/MAINTAIN/REDUCE mapping**: two fixed,
  immutable lookup tables applied to `performance.performance_band`/
  `trend.trend_direction` — the same pair Stage 20 used to determine
  suitability — `ABOVE_TARGET`→`ABOVE_TARGET_STRONG`, `ON_TARGET`→
  `NEAR_TARGET`, `BELOW_TARGET`→no performance reason (no approved severity
  classification exists to choose between `BELOW_TARGET_MODERATE` and
  `BELOW_TARGET_SEVERE` — a documented limitation, not an invitation to
  invent a threshold); `IMPROVING`/`STABLE`/`DECLINING`→
  `RECENT_TREND_IMPROVING`/`STABLE`/`DECLINING` unconditionally; the
  performance reason (when available) precedes the trend reason. This
  table-driven approach reproduces exactly the seven approved `MAINTAIN`
  mappings and additionally, consistently, the two `MAINTAIN` outcomes
  reachable only when Stage 19 availability blocks an otherwise
  diagonal-`SUITABLE` direction (`ABOVE_TARGET`+`IMPROVING` with `INCREASE`
  unavailable; `BELOW_TARGET`+`DECLINING` with `REDUCE` unavailable) — the
  identical, already-approved mapping applied unchanged, not a new invented
  rule. **Approved reason-code scope**: exactly eight existing `ReasonCode`
  members may be emitted (`PAUSED_CAMPAIGN`, `TRACKING_UNRELIABLE`,
  `HELD_FOR_MANUAL_REVIEW`, `ABOVE_TARGET_STRONG`, `NEAR_TARGET`,
  `RECENT_TREND_IMPROVING`, `RECENT_TREND_STABLE`, `RECENT_TREND_DECLINING`)
  — no new enum member added, no severity threshold invented.
  `TRACKING_WARNING`, `INSUFFICIENT_CONVERSION_VOLUME`,
  `PROTECTED_FROM_REDUCTION`, `BELOW_TARGET_MODERATE`,
  `BELOW_TARGET_SEVERE`, `STRONG_LONG_TERM_RECENT_DECLINE`,
  `CAMPAIGN_CAP_REACHED`, `CAMPAIGN_FLOOR_REACHED`,
  `TEST_BUDGET_FLOOR_APPLIED`, `MAX_CHANGE_LIMIT_APPLIED`,
  `NO_ELIGIBLE_RECIPIENT`, and `ACCOUNT_RESERVE_REQUIRED` are never
  emitted — the first three because none causally participates in Stage
  21's decision even though each is diagnostically true in some cases; the
  next three pending an approved performance-severity classification; the
  next four pending preserved constraint binding-source identity (no Stage
  15–18 result exposes which operand was actually binding); the last two
  as cross-campaign allocation-domain outcomes. Under this scope, the
  result tuple is never empty for any reachable production path. **Consumes
  Stage 21's, Stage 20's, Stage 8's, Stage 5's, and Stage 6's
  already-approved result objects directly** (never calls
  `resolve_campaign_recommendation_action` or any other Stage 1–21
  production function). Requires all six `campaign_id` values to match via
  one combined equality check anchored to `recommendation.campaign_id`,
  checked before any reason is resolved, raising exactly
  `ValueError("Campaign IDs must match when resolving recommendation
  reasons.")` otherwise with the same exact message regardless of which
  input(s) mismatch. Reads exactly fourteen authorised fields across six
  input objects — the largest interface of any stage to date. A dedicated
  module was chosen over `src/recommendation.py`/`src/suitability.py`/
  `src/availability.py`/`src/classification.py`/`src/constraints.py`/
  `src/scoring.py` because Stage 22 explains an already-selected action, a
  responsibility separate from selecting it. No `Decimal` calculation
  occurs anywhere. `src/recommendation.py`, `src/suitability.py`,
  `src/availability.py`, `src/scoring.py`, `src/classification.py`,
  `src/constraints.py`, `src/constants.py` (including the existing
  `ReasonCode` enum, unmodified), `src/models.py`, `src/validation.py`,
  `src/metrics.py`, and `src/pacing.py` are unchanged.
- Sprint 2, Development Stage 22: added a new dedicated test file,
  `tests/test_reasons.py` (69 tests, all passing;
  `tests/test_recommendation.py` unchanged at 84 tests,
  `tests/test_suitability.py` unchanged at 67 tests,
  `tests/test_availability.py` unchanged at 61 tests,
  `tests/test_constraints.py` unchanged at 322 tests) covering result-model
  shape/immutability/tuple-serialization (no `recommendation_action`,
  `reason_code`, `primary_reason`, `supporting_reasons`, confidence, score,
  rank, priority, amount, or suitability field), incompatible-input
  rejection (`AttributeError`, no silent coercion, no broad exception
  handling), campaign-ID matching (all six IDs equal resolves normally;
  each of the five non-anchor mismatches and a five-way simultaneous
  mismatch each raise the exact approved `ValueError` message with no
  result resolved and no ID silently preferred; the ID-equality guard
  verified via AST to precede any reason resolution), the exact HOLD
  precedence (Paused alone; Paused-and-unassessable yielding
  `PAUSED_CAMPAIGN` only; unassessable alone; multiple-`SUITABLE`
  ambiguity; no-valid-fallback — the last two both producing
  `HELD_FOR_MANUAL_REVIEW`; confirmed never used for a non-HOLD action),
  the exact INCREASE mapping, all seven approved `MAINTAIN` mappings via
  both direct construction and the real Stage 3/5/6/8/10–21 production
  path (reusing Stage 21's exact KPI fixtures), the exact REDUCE mapping,
  the two additional `MAINTAIN` outcomes reachable only via a Stage 19
  availability block on an otherwise diagonal-`SUITABLE` direction (a
  campaign at maximum budget blocking `INCREASE` on
  `ABOVE_TARGET`+`IMPROVING`; a protected campaign blocking `REDUCE` on
  `BELOW_TARGET`+`DECLINING`), non-empty/deduplicated tuples across every
  `PerformanceBand`×`TrendDirection` combination and every HOLD-producing
  scenario, performance-reason-precedes-trend-reason ordering confirmed
  independent of `ReasonCode`'s enum declaration order and not derived
  from any `sorted()` call, an exhaustive sweep confirming only the eight
  approved codes ever appear and the remaining twelve never appear,
  diagnostic-fact independence (`WARNING` tracking, protection, test
  status, and a tighter `campaign_max_change_percentage` each confirmed to
  add no reason), earlier-stage separation (AST-verified no call to
  `resolve_campaign_recommendation_action`/any other Stage 1–21 function;
  exactly fourteen authorised field accesses verified via AST), no
  production batch function, and sample-data integration through
  `validate_campaign_csv` + the real production chain over
  `data/sample_campaigns.csv` (`G001`/`M001`/`G003` all
  `(NEAR_TARGET, RECENT_TREND_STABLE)`; `G002`
  `(ABOVE_TARGET_STRONG, RECENT_TREND_IMPROVING)`). `tests/test_models.py`
  (Stage 1), `tests/test_validation.py` (Stage 2), `tests/test_metrics.py`
  (Stage 3), `tests/test_pacing.py` (Stage 4), `tests/test_classification.py`
  (Stage 5), `tests/test_trend_classification.py` (Stage 6),
  `tests/test_confidence_classification.py` (Stage 7),
  `tests/test_tracking_assessment.py` (Stage 8), and
  `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed
  passing — no behavioural regression, and no existing test file required
  modification this stage. Full suite: 944 tests passing (92 Stage 1 + 44
  Stage 2 + 28 Stage 3 + 30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 +
  30 Stage 8 + 33 Stage 9 + 322 Stage 10–18 combined in
  `tests/test_constraints.py` + 61 Stage 19 in `tests/test_availability.py`
  + 67 Stage 20 in `tests/test_suitability.py` + 84 Stage 21 in
  `tests/test_recommendation.py` + 69 Stage 22 in `tests/test_reasons.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignRecommendationReason` fields;
  the HOLD-precedence mirroring Stage 21; the INCREASE/MAINTAIN/REDUCE
  performance/trend mapping tables; the approved reason-code scope and
  exclusions), `docs/DECISION_RULES.md` (frozen Stage 22 deterministic
  campaign recommendation reasons rule, including the exact HOLD
  precedence, the exact INCREASE/MAINTAIN/REDUCE mapping, the exact six
  inputs and fourteen authorised fields, the campaign-ID policy and error,
  the approved reason-code scope, the permanent exclusions and their
  reasons, and the revised Pending section reflecting the eight now-frozen
  `ReasonCode` trigger conditions and the twelve still-pending), and
  `docs/TEST_SCENARIOS.md` (53 concrete Stage 22 scenarios).

- Sprint 2, Development Stage 23: filled in the Sprint 1 placeholder pair
  `src/scoring.py`/`tests/test_scoring.py` for the first time — no new
  module was created, unlike Stages 19–22, since the master plan already
  reserved this exact module for "campaign prioritization scoring."
  Added `CampaignReallocationPriorityScore` (frozen, immutable,
  `extra="forbid"`: `campaign_id`, `confidence_component: int`,
  `business_priority_component: int`, `reallocation_priority_score: int`
  only — does not duplicate `recommendation_action`; each numeric field
  constrained to `0..100`, and a model validator rejects any instance
  where the total does not equal the sum of the two components) and
  `calculate_campaign_reallocation_priority_score(recommendation:
  CampaignRecommendation, campaign: CampaignInput, confidence:
  CampaignConfidenceClass) -> CampaignReallocationPriorityScore`. Computes
  one deterministic, campaign-level, dimensionless `int` reallocation
  priority score for one already-selected `CampaignRecommendation` (Stage
  21), consumed later by a cross-campaign ranking stage. **Approved
  business meaning:** the relative priority with which an already-selected
  *directional* recommendation should be considered during later
  cross-campaign ranking — a higher score means a stronger candidate only
  within the same direction; `INCREASE` scores are compared only with
  other `INCREASE` scores, `REDUCE` scores only with other `REDUCE`
  scores, and the score must never compare an `INCREASE` directly against
  a `REDUCE`. Direction remains solely and authoritatively carried by
  `CampaignRecommendation.recommendation_action`, never re-encoded through
  sign or magnitude. **Approved non-directional rule:** `HOLD`/`MAINTAIN`
  unconditionally produce `(0, 0, 0)`, without inspecting or applying
  either mapping (confirmed by test via mapping stand-ins that raise if
  evaluated) — this does not mean either action is invalid, only that
  neither proposes a directional budget movement to prioritise.
  **Approved `Confidence.NOT_ASSESSABLE` override:** an `INCREASE`/`REDUCE`
  recommendation paired with `NOT_ASSESSABLE` also produces `(0, 0, 0)` — a
  scoring-only override, no exception, no change to the existing
  recommendation. **Approved exact mappings**, two fixed, immutable
  `MappingProxyType` lookups independent of enum declaration order:
  confidence `HIGH`→60/`MEDIUM`→40/`LOW`→20; business priority for
  `INCREASE` `HIGH`→40/`MEDIUM`→20/`STANDARD`→0; business priority for
  `REDUCE` `STANDARD`→40/`MEDIUM`→20/`HIGH`→0 — the same `BusinessPriority`
  value therefore contributes opposite components depending on direction,
  by design. `reallocation_priority_score = confidence_component +
  business_priority_component`, always a member of `{20, 40, 60, 80, 100}`
  for assessable directional recommendations, always `0` otherwise. Plain
  Python `int` throughout — never `float`/`Decimal`; no rounding,
  quantisation, or ambient `Decimal` context; no multiplication or
  division; no negative value or value above `100`; tie-breaking among
  equal scores explicitly deferred to the later ranking stage. **Consumes
  Stage 21's and Stage 7's already-approved result objects directly**
  (never calls `resolve_campaign_recommendation_action`,
  `classify_campaign_confidence`, or any other Stage 1–22 production
  function). Requires all three `campaign_id` values to match via one
  combined equality check anchored to `recommendation.campaign_id`,
  checked before any action, confidence, or priority value is read,
  raising exactly `ValueError("Campaign IDs must match when calculating
  reallocation priority score.")` otherwise with the same exact message
  regardless of which input(s) mismatch. Reads exactly six authorised
  fields across three input objects. **Excludes**
  `PerformanceBand`/`CampaignPerformanceClass` and
  `TrendDirection`/`CampaignTrendClass` (already caused Stage 20/21, would
  double-count the same action evidence), `CampaignActionAvailability`,
  `CampaignActionSuitability`, `CampaignTrackingAssessment` (already fully
  consumed downstream by Stage 21), `CampaignRecommendationReason`/
  `ReasonCode` (explanatory, must never become hidden numeric weights),
  `PacingStatus`/`CampaignPacingClass` (no approved direction-specific
  policy), and raw campaign metrics, monetary constraint results,
  protection, test-campaign status, and tracking status (answer capacity
  or availability, not priority). No enum was added or changed —
  `Confidence` and `BusinessPriority` are reused exactly as already frozen
  in `src/constants.py`. Completely single-campaign, consistent with the
  Stage 19 cross-campaign-boundary correction. `src/recommendation.py`,
  `src/reasons.py`, `src/suitability.py`, `src/availability.py`,
  `src/constraints.py`, `src/classification.py`, `src/constants.py`, and
  `src/models.py` are unchanged.
- Sprint 2, Development Stage 23: added 81 new tests to
  `tests/test_scoring.py` (Sprint 1 placeholder filled in for the first
  time; all passing), covering result-model shape/immutability/range-and-
  total-consistency validation/serialization (no `recommendation_action`,
  `reason_codes`, `performance_band`, `trend_direction`, `pacing_status`,
  `rank`, or `allocation` field), incompatible-input rejection
  (`AttributeError`, no silent coercion, no broad exception handling),
  campaign-ID matching (all three IDs equal resolves normally; each
  non-anchor mismatch and a simultaneous two-way mismatch each raise the
  exact approved `ValueError` message with no result resolved and no ID
  silently preferred; the ID-equality guard verified via AST to precede
  any action/confidence/priority read), `HOLD`/`MAINTAIN` always
  all-zero across every `Confidence`×`BusinessPriority` combination with
  the mappings confirmed never evaluated (exploding mapping stand-ins),
  `Confidence.NOT_ASSESSABLE` always all-zero for both directional actions
  across every `BusinessPriority` with no exception and the existing
  recommendation left untouched, the complete `INCREASE` and `REDUCE`
  nine-cell confidence×business-priority matrices, earlier-stage
  separation and excluded-type/field absence (AST- and
  module-attribute-verified against every listed exclusion, `Decimal`,
  and `float`), immutability of all three mappings (`MappingProxyType`,
  mutation raises `TypeError`), an exhaustive
  `RecommendationAction`×`Confidence`×`BusinessPriority` sweep confirming
  the total always equals the component sum and always belongs to `{0,
  20, 40, 60, 80, 100}`, absence of multiplication/division and of any
  collection-typed parameter, no production batch function, and
  sample-data integration through `validate_campaign_csv` + the real
  production chain over `data/sample_campaigns.csv` (`G001`/`M001`/`G003`
  all `0`; `G002` `INCREASE`/`Confidence.HIGH`/`BusinessPriority.HIGH` →
  `confidence_component=60`, `business_priority_component=40`,
  `reallocation_priority_score=100`).
  `tests/test_reasons.py` unchanged at 69 tests,
  `tests/test_recommendation.py` unchanged at 84 tests,
  `tests/test_suitability.py` unchanged at 67 tests,
  `tests/test_availability.py` unchanged at 61 tests,
  `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
  (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
  re-run and confirmed passing — no behavioural regression, and no
  existing non-placeholder test file required modification this stage.
  Full suite: 1025 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 +
  30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33
  Stage 9 + 322 Stage 10–18 combined in `tests/test_constraints.py` + 61
  Stage 19 in `tests/test_availability.py` + 67 Stage 20 in
  `tests/test_suitability.py` + 84 Stage 21 in
  `tests/test_recommendation.py` + 69 Stage 22 in `tests/test_reasons.py`
  + 81 Stage 23 in `tests/test_scoring.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignReallocationPriorityScore`
  fields; the approved business meaning and same-direction-only
  comparability; the non-directional and `NOT_ASSESSABLE`-override rules;
  the exact confidence and direction-aware business-priority mapping
  tables; the double-counting/exclusion rationale; the numeric policy),
  `docs/DECISION_RULES.md` (frozen Stage 23 deterministic campaign
  reallocation priority scoring rule, including the exact non-directional
  rule, the exact `NOT_ASSESSABLE` override, the exact confidence and
  business-priority mappings, the exact three inputs and six authorised
  fields, the campaign-ID policy and error, the numeric policy, the
  exclusion rationale, and the revised Pending section reflecting that
  single-campaign scoring is now frozen while cross-campaign ranking,
  allocation, and conservation remain pending), and `docs/TEST_SCENARIOS.md`
  (42 concrete Stage 23 scenarios).

- Sprint 2, Development Stage 24: added a new dedicated module,
  `src/ranking.py` — the first genuinely cross-campaign responsibility in
  this repository — containing `RankedCampaignPriority` (frozen,
  immutable, `extra="forbid"`: `campaign_id`, `rank: int` `>= 1`,
  `reallocation_priority_score: int` `1..100` only — does not carry
  `RecommendationAction`; direction is represented structurally by tuple
  membership), `CampaignReallocationRanking` (frozen, immutable,
  `extra="forbid"`: `increase_rankings: tuple[RankedCampaignPriority,
  ...]`, `reduce_rankings: tuple[RankedCampaignPriority, ...]`, either or
  both legitimately empty), and
  `rank_campaign_reallocation_priorities(recommendations:
  tuple[CampaignRecommendation, ...], scores:
  tuple[CampaignReallocationPriorityScore, ...]) ->
  CampaignReallocationRanking`. Matches each already-selected
  `CampaignRecommendation` (Stage 21) with its already-calculated
  `CampaignReallocationPriorityScore` (Stage 23) by `campaign_id`, groups
  directional candidates into two completely independent populations
  (`INCREASE`, `REDUCE`), excludes non-directional campaigns, ranks
  eligible campaigns by score within their own direction, preserves
  genuine score ties, and returns an immutable, deterministic result for
  later allocation. **Approved direction separation:** `INCREASE` and
  `REDUCE` are never compared; the first-ranked campaign in each
  direction may both hold rank `1` with no relationship between them; no
  global combined rank exists; no campaign ever crosses direction.
  **Approved eligible population:**
  `INCREASE`/`REDUCE`+score>0→included; `INCREASE`/`REDUCE`+score==0→excluded;
  `MAINTAIN`/`HOLD` (any score)→excluded — a zero-scored directional
  recommendation (reachable via Stage 23's `NOT_ASSESSABLE` override) is
  excluded because Stage 23 already determined it has no reliable ranking
  priority; exclusion produces no output record, no reason code, no
  error, and no mutation of the excluded campaign's recommendation or
  score, and no excluded-campaign collection is created. **Approved
  matching policy:** exclusively by `campaign_id` value equality, never
  by tuple position (`zip` never used, AST-verified); every `campaign_id`
  unique within each tuple; the two tuples' `campaign_id` sets must match
  exactly; validation completes fully, in exact order (AST-verified),
  before any filtering, sorting, or rank assignment — a repeated ID
  within `recommendations` raises exactly `ValueError("Recommendation
  campaign IDs must be unique when ranking reallocation priorities.")`; a
  repeated ID within `scores` raises exactly `ValueError("Score campaign
  IDs must be unique when ranking reallocation priorities.")`; a
  mismatched ID set raises exactly `ValueError("Recommendation and score
  campaign IDs must match when ranking reallocation priorities.")`; both
  tuples empty returns a valid empty result, not an error. **Approved
  sorting and dense-ranking policy:** within each direction, sort by
  `reallocation_priority_score` descending, then `campaign_id` ascending
  solely for deterministic tied-record serialization — `campaign_id`
  never affects the assigned rank and is never a business-priority key;
  no component already reflected in the Stage 23 total, and no other
  field (input position, platform, budget, performance, trend, pacing,
  monetary capacity), is ever used as a sort key; ranks are dense,
  `1`-based, plain `int`, with equal scores sharing the same rank and no
  gap before the next distinct score. **Approved no-normalisation rule:**
  Stage 23's score is used completely unchanged — no percentage,
  percentile, portfolio-relative, min-max, z-score, or direction-relative
  transform is ever computed. **Consumes Stage 21's and Stage 23's
  already-approved result objects directly** (never calls
  `resolve_campaign_recommendation_action`,
  `calculate_campaign_reallocation_priority_score`, or any other Stage
  1–23 production function). Reads exactly four authorised fields across
  two input tuple types. Never reads `confidence_component`,
  `business_priority_component`, any campaign-input field, or any
  performance/trend/pacing/confidence/suitability/availability/tracking/
  reason/monetary field; never imports, reads, or infers any
  raw/effective monetary constraint result, binding-constraint identity,
  monetary recommendation amount, donor/recipient matching, partial
  allocation, or conservation. Neither input tuple nor any contained
  model is ever mutated or sorted in place (`sorted()`, never in-place
  `.sort()`); every output object is newly constructed; identical
  serialized output regardless of input order. No enum was added or
  changed. A dedicated module was chosen over `src/scoring.py`/
  `src/recommendation.py`/`src/reasons.py`/`src/allocation.py` because
  Stage 24 ranks already-scored campaigns across a portfolio, a
  responsibility separate from single-campaign scoring and from the later
  monetary allocation decision. `src/scoring.py`, `src/recommendation.py`,
  `src/reasons.py`, `src/allocation.py`, `src/conservation.py`, and
  `src/constants.py` are unchanged.
- Sprint 2, Development Stage 24: added 69 new tests to
  `tests/test_ranking.py` (new dedicated test file; all passing),
  covering result-model shape/immutability/range validation/serialization
  (no `recommendation_action`, `direction`, `confidence_component`,
  `business_priority_component`, `reason_codes`, `amount`, `allocation`,
  `excluded`, or `global_rank` field), independently-empty direction
  tuples, duplicate-recommendation-ID/duplicate-score-ID/mismatched-ID-set
  validation with exact error messages and confirmed validation order
  (recommendation-uniqueness checked first when both collections contain
  duplicates; all validation confirmed via AST to precede the
  candidate-building loop), both-empty-returns-valid-empty-result,
  `None`/dict-input rejection without silent coercion, campaign-ID-value
  matching regardless of tuple position/order (shuffled, reversed, and
  independently-reordered inputs all producing identical serialized
  output; `zip` confirmed absent via AST), the complete eligible-
  population truth table (positive `INCREASE`/`REDUCE` included; zero
  `INCREASE`/`REDUCE` excluded; `HOLD`/`MAINTAIN` excluded regardless of a
  synthetic positive paired score; inputs confirmed unchanged after
  ranking), direction independence (separate tuples; each starting at
  rank `1`; no global rank field; identical cross-direction scores
  confirmed unrelated; no campaign ever appearing in both tuples),
  dense-ranking patterns (`1,2,3`; `1,1,2`; `1,2,2,3`; all-tied `1,1,1`;
  multiple independent ties), campaign-ID-ascending tied-record
  serialization confirmed never to alter the assigned rank, absence of
  normalisation (an unchanged single score preserved exactly),
  earlier-stage separation and excluded-type/field absence (AST- and
  module-attribute-verified against every listed exclusion, `Decimal`,
  and `float`), confirmation `sorted()` (never in-place `.sort()`) is
  used and no `Mult`/`Div`/`FloorDiv` binary operation exists, no
  production batch function beyond the approved one, sample-data
  integration through `validate_campaign_csv` + the real production chain
  over `data/sample_campaigns.csv` (`increase_rankings` containing only
  `G002` at rank `1`/score `100`; `reduce_rankings` empty;
  `G001`/`M001`/`G003` absent from both), and seven test-only hypothetical
  portfolios (multiple `INCREASE` scores, multiple `REDUCE` scores, both
  directions populated simultaneously alongside excluded `MAINTAIN`/`HOLD`
  campaigns, an empty direction, zero-scored directional records in both
  directions, and no eligible candidates at all).
  `tests/test_scoring.py` unchanged at 81 tests,
  `tests/test_reasons.py` unchanged at 69 tests,
  `tests/test_recommendation.py` unchanged at 84 tests,
  `tests/test_suitability.py` unchanged at 67 tests,
  `tests/test_availability.py` unchanged at 61 tests,
  `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
  (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
  re-run and confirmed passing — no behavioural regression, and no
  existing non-placeholder test file required modification this stage.
  Full suite: 1094 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 +
  30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33
  Stage 9 + 322 Stage 10–18 combined in `tests/test_constraints.py` + 61
  Stage 19 in `tests/test_availability.py` + 67 Stage 20 in
  `tests/test_suitability.py` + 84 Stage 21 in
  `tests/test_recommendation.py` + 69 Stage 22 in `tests/test_reasons.py`
  + 81 Stage 23 in `tests/test_scoring.py` + 69 Stage 24 in
  `tests/test_ranking.py`).
- Updated `docs/DATA_DICTIONARY.md` (`RankedCampaignPriority`/
  `CampaignReallocationRanking` fields; the direction-separation and
  eligible-population rules; the dense-ranking and campaign-ID-tiebreak
  policy; the no-normalisation rule; the matching/determinism policy; the
  monetary/allocation boundary), `docs/DECISION_RULES.md` (frozen Stage 24
  deterministic cross-campaign reallocation ranking rule, including the
  exact eligible-population table, the exact sorting/dense-ranking/
  no-normalisation policy, the exact two inputs and four authorised
  fields, the matching/uniqueness/mismatch validation policy and exact
  error messages, the determinism and monetary-boundary guarantees, and
  the revised Pending section reflecting that cross-campaign ranking is
  now frozen while a distinct monetary-amount stage, allocation, and
  conservation remain pending), and `docs/TEST_SCENARIOS.md` (47 concrete
  Stage 24 scenarios).

- Sprint 2, Development Stage 25: filled in the Sprint 1 placeholder pair
  `src/allocation.py`/`tests/test_allocation.py` for the first time — no
  new module was created and no separate monetary recommendation-amount
  stage exists, per the accepted post-Stage-24 boundary decision.
  Added `CampaignAllocatedAmount` (frozen, immutable, `extra="forbid"`:
  `campaign_id`, `allocated_amount: Currency` constrained `>= 0` only —
  never carries direction, rank, score, or capacity; direction is
  represented structurally by tuple membership, never a sign) and
  `CampaignReallocationAllocation` (frozen, immutable, `extra="forbid"`:
  `increase_allocations: tuple[CampaignAllocatedAmount, ...]`,
  `decrease_allocations: tuple[CampaignAllocatedAmount, ...]`, either
  legitimately empty, containing exactly one record per campaign in the
  corresponding Stage 24 ranking tuple including at `Decimal("0.00")`)
  and `allocate_campaign_reallocation(ranking: CampaignReallocationRanking,
  increase_limits: tuple[CampaignRawIncreaseLimit, ...], decrease_limits:
  tuple[CampaignEffectiveDecreaseLimit, ...]) ->
  CampaignReallocationAllocation`. Converts Stage 24's direction-separated,
  dense-ranked candidate populations into actual, balanced, campaign-level
  monetary movements, consuming Stage 16's `CampaignRawIncreaseLimit` and
  Stage 18's `CampaignEffectiveDecreaseLimit` as maximum capacities —
  never guaranteed movements; no campaign automatically receives or
  donates its full capacity merely because it exists or is ranked first.
  **Approved reserve exclusion:** `ReviewSetup.initial_account_reserve` is
  never accepted, read, consumed, reduced, or returned — authoritative
  meaning *"Budget held back from reallocation"* treats it as protected;
  `ReviewSetup` is never accepted as an input at all;
  `ReasonCode.ACCOUNT_RESERVE_REQUIRED` remains unassigned. **The only
  funding source is the sum of `effective_decrease_limit` across Stage
  24's `reduce_rankings`** — unranked decrease-limit records and reserve
  never contribute. **Approved two-phase strict dense-rank waterfall:**
  Phase 1 funds `increase_rankings` by ascending dense rank against total
  available supply (full-tier funding while supply covers it,
  largest-remainder proportional split on the first tier it cannot fully
  cover, then `Decimal("0.00")` for every lower rank); Phase 2 draws the
  exact Phase 1 total from `reduce_rankings` by the identical waterfall,
  always exhausting exactly since Phase 1's total can never exceed total
  supply; unused donor capacity beyond that target is left unused, not
  returned separately. Insufficient and excess supply are both valid,
  non-error outcomes; neither produces a `ReasonCode`. **Approved
  largest-remainder currency method:** exact proportional shares at
  operand-derived local precision, floored to `CURRENCY_QUANTUM` via
  `ROUND_DOWN`; the whole-penny shortfall distributed by
  fractional-remainder descending, `campaign_id` ascending breaking only
  an *exact* remainder tie — a narrow, explicitly scoped exception to
  "campaign ID is a serialization aid only," never used to order
  recipients against donors or influence which tier is funded; never adds
  a penny above a campaign's own capacity; an all-zero-capacity tier
  allocates zero to every campaign without division. **Consumes Stage
  24's, Stage 16's, and Stage 18's already-approved result objects
  directly** (never calls `rank_campaign_reallocation_priorities`,
  `calculate_campaign_reallocation_priority_score`,
  `resolve_campaign_recommendation_action`, or any other Stage 1–24
  production function). Matches `increase_limits`/`decrease_limits` to
  the rankings exclusively by `campaign_id` value — never `zip`. Requires
  uniqueness within each limit collection and a matching
  direction-appropriate limit for every ranked campaign, raising exactly
  `ValueError("Increase-limit campaign IDs must be unique when allocating
  reallocation.")`, `ValueError("Decrease-limit campaign IDs must be
  unique when allocating reallocation.")`, `ValueError("Every ranked
  increase campaign must have a matching increase limit.")`, or
  `ValueError("Every ranked decrease campaign must have a matching
  decrease limit.")` otherwise, checked before any allocation arithmetic.
  Extra, unranked limit records are accepted and ignored. Stage 24's own
  guarantees (uniqueness, direction separation, rank correctness,
  ordering) are trusted, never recalculated. Reads exactly the authorised
  fields — `ranking.increase_rankings`/`.reduce_rankings`,
  `ranked.campaign_id`/`.rank` (never `.reallocation_priority_score`),
  `limit.campaign_id`/`.raw_increase_limit`/`.effective_decrease_limit` —
  and never reads `ReviewSetup`, `CampaignInput`, `CampaignRecommendation`,
  or `CampaignRecommendationReason`. Plain `Decimal` throughout — never
  `float`; every arithmetic operation, including simple sums and penny
  apportionment, runs inside an explicitly-scoped `localcontext`, immune
  to ambient global context mutation. `sum(increase_allocations) ==
  sum(decrease_allocations)` always holds by construction, not as a
  post-hoc check. Output order exactly preserves Stage 24's own ranking
  order. No `ReasonCode` is ever emitted; no final campaign budget is
  calculated (`CampaignInput.current_budget` never read); conservation
  verification remains entirely separate — Stage 26 will independently
  re-verify the same invariant, never repairing or mutating allocation's
  result. No enum was added or changed. `src/ranking.py`, `src/scoring.py`,
  `src/recommendation.py`, `src/reasons.py`, `src/constraints.py`,
  `src/conservation.py`, `src/constants.py`, and `src/models.py` are
  unchanged.
- Sprint 2, Development Stage 25: added 79 new tests to
  `tests/test_allocation.py` (Sprint 1 placeholder filled in for the first
  time; all passing), covering result-model shape/immutability/
  non-negative-currency validation/quantisation/serialization (no
  `recommendation_action`, `rank`, `reallocation_priority_score`,
  `capacity`, `remaining_capacity`, `final_budget`, `reserve_used`,
  `final_reserve`, `reason_codes`, or `unallocated_supply` field),
  independently-empty direction tuples, duplicate-increase-limit-ID/
  duplicate-decrease-limit-ID/missing-ranked-limit validation with exact
  error messages and confirmed validation order (increase-limit-uniqueness
  checked first when both collections contain duplicates), extra unranked
  limit records accepted and ignored, campaign-ID-value matching
  regardless of shuffled collection order (`zip` confirmed absent via
  AST), both-directions-empty returning a valid empty result, basic
  equal/greater/lesser recipient-vs-donor-capacity allocation with exact
  balance confirmation, the strict dense-rank waterfall on both the
  recipient and donor sides independently (higher rank fully funded
  before lower, partial higher rank zeroing every lower rank,
  zero-capacity tiers safely skipped), tied-tier proportional allocation
  for both recipients and donors independently (equal and unequal
  capacities, fractional-cent largest-remainder splits, an exact
  fractional-remainder tie resolved by `campaign_id` ascending, no
  allocation ever exceeding capacity, exact residual exhaustion, zeroed
  lower ranks after a partial tied-tier funding), Decimal policy (no
  `float`, exact two-decimal exponents, extreme 28-significant-digit
  magnitudes, a 200-campaign collection, mutated ambient
  precision/rounding confirmed not to affect the result and confirmed
  restored afterward, repeating-decimal splits, one-penny and multi-penny
  residuals, exact increase/decrease total equality), every empty/
  no-counterparty/zero-capacity combination, earlier-stage separation and
  excluded-type/field absence (AST- and module-attribute-verified,
  including confirmation `reallocation_priority_score` is never read), no
  input mutation, no reason-code reference, no conservation or
  final-budget implementation, output order exactly preserving Stage 24's
  ranking order, and sample-data integration through
  `validate_campaign_csv` + the real production chain over
  `data/sample_campaigns.csv` (`increase_allocations` containing only
  `G002` at `Decimal("0.00")`; `decrease_allocations` empty — reflecting
  the complete absence of ranked `REDUCE` supply in this exact portfolio,
  not a changed recommendation, an error, or whole-campaign
  ineligibility). `tests/test_ranking.py` unchanged at 69 tests,
  `tests/test_scoring.py` unchanged at 81 tests,
  `tests/test_reasons.py` unchanged at 69 tests,
  `tests/test_recommendation.py` unchanged at 84 tests,
  `tests/test_suitability.py` unchanged at 67 tests,
  `tests/test_availability.py` unchanged at 61 tests,
  `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
  (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
  re-run and confirmed passing — no behavioural regression, and no
  existing non-placeholder test file required modification this stage.
  Full suite: 1173 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 +
  30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33
  Stage 9 + 322 Stage 10–18 combined in `tests/test_constraints.py` + 61
  Stage 19 in `tests/test_availability.py` + 67 Stage 20 in
  `tests/test_suitability.py` + 84 Stage 21 in
  `tests/test_recommendation.py` + 69 Stage 22 in `tests/test_reasons.py`
  + 81 Stage 23 in `tests/test_scoring.py` + 69 Stage 24 in
  `tests/test_ranking.py` + 79 Stage 25 in `tests/test_allocation.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignAllocatedAmount`/
  `CampaignReallocationAllocation` fields; the reserve-exclusion rule; the
  two-phase waterfall and largest-remainder policy; the narrow
  campaign-ID exception; the matching/determinism policy; the boundaries
  excluding reason codes, final budgets, and conservation),
  `docs/DECISION_RULES.md` (frozen Stage 25 deterministic cross-campaign
  budget allocation rule, including the exact reserve exclusion, the
  exact two-phase waterfall and largest-remainder currency method, the
  exact three inputs and authorised fields, the matching/uniqueness/
  missing-limit validation policy and exact error messages, the numeric
  policy and balance invariant, and the revised Pending section reflecting
  that allocation is now frozen while conservation remains the sole
  outstanding downstream stage), and `docs/TEST_SCENARIOS.md` (60 concrete
  Stage 25 scenarios, superseding the earlier placeholder "Allocation
  Scenarios" heading).

- Sprint 2, Development Stage 26: filled in the Sprint 1 placeholder pair
  `src/conservation.py`/`tests/test_conservation.py` for the first time —
  no new module was created. Added `CampaignReallocationConservation`
  (frozen, immutable, `extra="forbid"`: `total_increase_allocated:
  Currency` constrained `>= 0`, `total_decrease_allocated: Currency`
  constrained `>= 0`, `net_change: Decimal` — plain, since it may be
  negative — `is_conserved: bool` only, with a model-level validator
  rejecting any instance where `net_change != total_increase_allocated -
  total_decrease_allocated` or `is_conserved` is inconsistent with
  `net_change == Decimal("0.00")`) and
  `verify_campaign_reallocation_conservation(allocation:
  CampaignReallocationAllocation) -> CampaignReallocationConservation`.
  Independently verifies the monetary invariant of one already-produced
  Stage 25 allocation — a pure, read-only checker that never reruns
  allocation, never repairs an imbalance, and never mutates the
  allocation it inspects. **Approved conservation equation:**
  `total_increase_allocated`/`total_decrease_allocated` are independently
  recomputed by summing `allocated_amount` across
  `allocation.increase_allocations`/`.decrease_allocations` — never
  trusting a portfolio total from Stage 25, which returns none;
  `net_change = total_increase_allocated - total_decrease_allocated`;
  `is_conserved = (net_change == Decimal("0.00"))`. **Approved sign
  convention:** positive `net_change` means increases exceed decreases,
  negative means decreases exceed increases — never left ambiguous, never
  returned as an absolute difference. **Approved exact-equality policy:**
  no tolerance, epsilon, absolute-difference threshold, or rounded
  comparison — an imbalance of exactly `Decimal("0.01")` is reported as
  not conserved. **Approved always-return-a-result policy:** the
  production function never raises merely because an allocation is
  imbalanced; `is_conserved=False` with the exact signed `net_change` is
  a valid, auditable result; only a directly-constructed, internally
  *inconsistent* result model is rejected, via ordinary Pydantic
  validation. **Approved duplicate/overlap indifference:** `campaign_id`
  is never read from any allocation record; every `allocated_amount`
  present is summed regardless of duplicate IDs within one direction, the
  same ID in both directions, or repeated zero records — trusting Stage
  24/25's own structural identity guarantees rather than re-validating
  them; Stage 26 never duplicates Stage 25's own donor/recipient
  matching, rank waterfall, tied-tier proportional allocation, or
  residual-penny apportionment. **Consumes only Stage 25's
  `CampaignReallocationAllocation`** — never `ReviewSetup`,
  `CampaignInput`, Stage 16/18 capacity results, Stage 24's ranking,
  `CampaignRecommendation`, or `CampaignRecommendationReason`; never
  calls `allocate_campaign_reallocation` or any other Stage 1–25
  production function. Reads exactly `allocation.increase_allocations`,
  `allocation.decrease_allocations`, and each record's `allocated_amount`.
  Plain `Decimal` throughout — never `float`; every sum and the final
  subtraction run inside an explicitly-scoped `localcontext`, with local
  precision derived from the actual operands' digit counts and record
  count — never a blindly assumed fixed value — directly responding to
  the real ambient-context arithmetic defect discovered and corrected
  during Stage 25's own implementation. No `ReasonCode` is ever emitted
  (`ACCOUNT_RESERVE_REQUIRED`/`NO_ELIGIBLE_RECIPIENT` remain unassigned);
  no final campaign budget is calculated. A conserved zero allocation does
  not mean any campaign received funding. No enum was added or changed.
  `src/allocation.py`, `src/ranking.py`, `src/scoring.py`,
  `src/recommendation.py`, `src/reasons.py`, `src/constraints.py`,
  `src/constants.py`, and `src/models.py` are unchanged.
- Sprint 2, Development Stage 26: added 50 new tests to
  `tests/test_conservation.py` (Sprint 1 placeholder filled in for the
  first time; all passing), covering result-model shape/immutability/
  non-negative-total validation/serialization (no `campaign_count`,
  `campaign_id`, individual allocation records, reserve, capacity, final
  budget, message, issue, reason-code, or tolerance field), model-level
  rejection of an inconsistent `net_change` or `is_conserved`, direct
  construction of both balanced and imbalanced internally-consistent
  results, every balanced case (empty allocation, all-zero allocation,
  one side empty with zero-valued records on the other, equal
  single/multiple records, different record counts with equal totals,
  extreme equal totals, duplicated and overlapping IDs with balanced
  totals), every imbalanced case (one-penny imbalances in both
  directions, larger positive/negative imbalances, one positive side vs.
  an empty side, exact signed `net_change`, confirmed no exception raised
  and no repair/mutation performed), Decimal-context correctness (no
  `float`; mutated ambient precision/rounding confirmed not to affect the
  result and confirmed restored afterward; many large operands whose sum
  requires more digits than any individual operand — 100 × 18-digit
  values summing to a 20-digit total; a large collection where
  fixed-per-operand precision alone would be insufficient — 500 ×
  24-digit values summing to a 26-digit total; a one-penny discrepancy
  between large-magnitude totals preserved exactly under a hostile
  mutated ambient context; exact `Decimal("0.00")`), complete indifference
  to duplicate/overlapping campaign IDs and repeated zero records with no
  identity validation added, earlier-stage separation and excluded-type/
  field absence (AST- and module-attribute-verified, including
  confirmation `campaign_id` is never read anywhere in the module), no
  input mutation, no broad exception handling, no production batch
  function, and sample-data integration reproducing the real Stage 25
  result for `data/sample_campaigns.csv` (`total_increase_allocated=0.00`,
  `total_decrease_allocated=0.00`, `net_change=0.00`, `is_conserved=True`
  — explicitly confirmed not to mean G002 received funding).
  `tests/test_allocation.py` unchanged at 79 tests,
  `tests/test_ranking.py` unchanged at 69 tests,
  `tests/test_scoring.py` unchanged at 81 tests,
  `tests/test_reasons.py` unchanged at 69 tests,
  `tests/test_recommendation.py` unchanged at 84 tests,
  `tests/test_suitability.py` unchanged at 67 tests,
  `tests/test_availability.py` unchanged at 61 tests,
  `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
  (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
  re-run and confirmed passing — no behavioural regression, and no
  existing non-placeholder test file required modification this stage.
  Full suite: 1223 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 +
  30 Stage 4 + 23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33
  Stage 9 + 322 Stage 10–18 combined in `tests/test_constraints.py` + 61
  Stage 19 in `tests/test_availability.py` + 67 Stage 20 in
  `tests/test_suitability.py` + 84 Stage 21 in
  `tests/test_recommendation.py` + 69 Stage 22 in `tests/test_reasons.py`
  + 81 Stage 23 in `tests/test_scoring.py` + 69 Stage 24 in
  `tests/test_ranking.py` + 79 Stage 25 in `tests/test_allocation.py` +
  50 Stage 26 in `tests/test_conservation.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignReallocationConservation`
  fields; the conservation equation and sign convention; the
  exact-equality and always-return-a-result policies; the duplicate/
  overlap indifference; the Decimal/context policy; the boundaries
  excluding reason codes, reserve, final budgets, and identity
  validation), `docs/DECISION_RULES.md` (frozen Stage 26 deterministic,
  independent budget conservation verification rule, including the exact
  conservation equation, the exact sign convention, the exact-equality
  and always-return-a-result policies, the exact single input and
  authorised fields, the Decimal/context precision-derivation policy, and
  the revised Pending section reflecting that the deterministic ranking →
  allocation → conservation sequence is now complete while final
  deterministic integration/reporting remains the sole outstanding
  downstream stage), and `docs/TEST_SCENARIOS.md` (37 concrete Stage 26
  scenarios).

- Sprint 2, Development Stage 27: added a new dedicated module,
  `src/pipeline.py` — the final deterministic responsibility, completing
  the master plan's Sprint 2 "Deterministic Core Engine" goal in full —
  containing `CampaignBudgetRecommendationResult` (frozen, immutable,
  `extra="forbid"`: `campaign_id`, `campaign_name`, `platform`,
  `current_budget: Currency`, `recommendation_action`, `allocated_amount:
  Currency` constrained `>= 0`, `recommended_budget: Currency`
  constrained `>= 0`, `reason_codes: tuple[ReasonCode, ...]`,
  `performance_band`, `trend_direction`, `confidence`, `pacing_status`,
  `reallocation_priority_score: int` constrained `0..100`, `rank: int |
  None` constrained `>= 1` when present only), `BudgetReallocationReviewResult`
  (frozen, immutable, `extra="forbid"`: `review_id`, `campaign_results:
  tuple[CampaignBudgetRecommendationResult, ...]`, `total_current_budget:
  Currency` constrained `>= 0`, `total_recommended_budget: Currency`
  constrained `>= 0`, `conservation: CampaignReallocationConservation`
  only), and `run_budget_reallocation_review(review: ReviewSetup,
  campaigns: tuple[CampaignInput, ...]) -> BudgetReallocationReviewResult`.
  Orchestrates every already-approved Stage 3–26 production function, in
  their exact frozen dependency order, over one already-validated review
  and campaign collection. **Approved validation boundary:** validation
  remains entirely outside this stage — never reads a CSV, never calls
  `validate_campaign_csv`, never returns validation issues, never
  re-checks campaign-ID uniqueness (already Stage 2's responsibility); an
  empty campaign tuple is valid and returns an empty portfolio result.
  **Pure orchestration:** every fact is produced by calling the real,
  already-approved function that owns it — no formula duplicated,
  approximated, reopened, or recalculated from an upstream result object.
  **Approved final-movement policy:** exactly one unsigned
  `allocated_amount` per campaign — direction carried only by
  `recommendation_action`, never re-encoded through sign; `Decimal("0.00")`
  for `HOLD`/`MAINTAIN` and for any directional recommendation with no
  matching Stage 25 allocation record (excluded from ranking because its
  score was zero, or ranked but unfunded); a zero-funded `INCREASE`/`REDUCE`
  is never rewritten to `MAINTAIN`/`HOLD` — confirmed against the real
  G002 sample result, which remains `INCREASE` with `allocated_amount=0.00`.
  **Approved final-budget formula**, using only Stage 25's actual
  allocated amount, never raw or effective constraint limits directly:
  `INCREASE → current_budget + allocated_amount`; `REDUCE →
  current_budget - allocated_amount`; `MAINTAIN`/`HOLD → current_budget`
  unchanged. **Approved conservation policy:** the embedded Stage 26
  `CampaignReallocationConservation` result is always present regardless
  of `is_conserved` — never hidden, gated, or omitted; never raises
  merely because an allocation is unconserved. A defence-in-depth check,
  distinct from and never a replacement for Stage 26's own invariant,
  raises exactly `RuntimeError("Conserved allocation must preserve the
  total campaign budget.")` only if a *conserved* allocation's recomputed
  portfolio totals fail to match exactly. **Approved matching/ordering:**
  all cross-collection matching (rank, allocation) is by `campaign_id`
  value, never tuple position; `campaign_results` preserves the original
  `campaigns` input order; Stage 24's increase/reduce rankings remain
  independent, with no global cross-direction rank ever constructed.
  Plain `Decimal` throughout — never `float`; every addition, subtraction,
  and portfolio-level sum runs inside an explicitly-scoped `localcontext`,
  with precision derived from the actual operands' digit counts and
  collection size, immune to ambient global context mutation, directly
  extending the corrected discipline established at Stages 25 and 26.
  Stage 22's ordered `reason_codes` are passed through unchanged; no
  allocation-specific reason code is ever invented. Fails fast on any
  unexpected exception or upstream `ValueError` — no `try`/`except`, no
  retry, no partial result, no campaign ever silently dropped, no input
  or upstream result object ever mutated. No enum was added or changed.
  No existing Stage 1–26 production or test module was modified.
- Sprint 2, Development Stage 27: added 35 new tests to
  `tests/test_pipeline.py` (new dedicated test file, deliberately distinct
  from `tests/test_integration.py`, which remains reserved for the later,
  materially larger AI/UI-inclusive end-to-end flow and was not modified;
  all passing), covering result-model shape/immutability/range validation
  (no signed movement, raw/effective capacity, availability/suitability,
  tracking status, validation issue, reserve, campaign count, timestamp,
  version, or audit-trace field), the exact real Stage 3–26 sample-data
  result over `data/sample_campaigns.csv` (G001/M001/G002/G003 actions,
  reasons, scores, ranks, allocated/current/recommended budgets; portfolio
  totals `11700.00`/`11700.00`; conservation `0.00`/`0.00`/`0.00`/`True`),
  explicit confirmation G002 remains `INCREASE` despite
  `allocated_amount=0.00`, a balanced non-zero recipient/donor pair where
  final budgets change exactly by the allocated amount and portfolio
  totals remain equal, `HOLD`/`MAINTAIN` producing zero movement and an
  unchanged recommended budget, optional-rank behavior (present only for
  ranked directional campaigns, always `None` for `HOLD`/`MAINTAIN` and
  for zero-score-excluded directional campaigns), empty-portfolio
  handling, original input-order preservation under arbitrary campaign
  ordering, `campaign_id`-based matching confirmed independent of
  internal Stage 24/25 reordering, Decimal-context correctness (no
  `float`; mutated ambient precision/rounding confirmed not to affect the
  result and confirmed restored afterward; extreme
  28-significant-digit budget magnitudes), the conservation and
  total-budget invariants (conservation always exposed; the
  defence-in-depth check confirmed never to raise for a genuinely
  conserved real chain), input/upstream-object immutability, fail-fast
  propagation of an unexpected exception with no `try`/`except` anywhere
  in the function's source (AST-verified via absence of any `ast.Try`
  node), and isolation from AI/UI/approval/audit/export/CSV-
  reading/validation imports and calls, from any duplicated Stage 1–26
  formula (AST-verified — every `BinOp` in the module belongs only to the
  explicitly authorised final-budget/summation helpers), and confirmation
  every required Stage 3–26 production function is actually called
  (AST-verified). `tests/test_conservation.py` unchanged at 50 tests,
  `tests/test_allocation.py` unchanged at 79 tests,
  `tests/test_ranking.py` unchanged at 69 tests,
  `tests/test_scoring.py` unchanged at 81 tests,
  `tests/test_reasons.py` unchanged at 69 tests,
  `tests/test_recommendation.py` unchanged at 84 tests,
  `tests/test_suitability.py` unchanged at 67 tests,
  `tests/test_availability.py` unchanged at 61 tests,
  `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
  (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
  re-run and confirmed passing — no behavioural regression, and no
  existing test module required modification this stage. Full suite:
  1258 tests passing (92 Stage 1 + 44 Stage 2 + 28 Stage 3 + 30 Stage 4 +
  23 Stage 5 + 29 Stage 6 + 32 Stage 7 + 30 Stage 8 + 33 Stage 9 + 322
  Stage 10–18 combined in `tests/test_constraints.py` + 61 Stage 19 in
  `tests/test_availability.py` + 67 Stage 20 in `tests/test_suitability.py`
  + 84 Stage 21 in `tests/test_recommendation.py` + 69 Stage 22 in
  `tests/test_reasons.py` + 81 Stage 23 in `tests/test_scoring.py` + 69
  Stage 24 in `tests/test_ranking.py` + 79 Stage 25 in
  `tests/test_allocation.py` + 50 Stage 26 in `tests/test_conservation.py`
  + 35 Stage 27 in `tests/test_pipeline.py`).
- Updated `docs/DATA_DICTIONARY.md` (`CampaignBudgetRecommendationResult`/
  `BudgetReallocationReviewResult` fields; the validation boundary; the
  final-movement and final-budget policies; the conservation policy; the
  matching/ordering/Decimal policy; the complete exclusion list),
  `docs/DECISION_RULES.md` (frozen Stage 27 final deterministic pipeline
  integration and reporting rule, including the exact dependency order,
  the exact final-movement and final-budget formulas, the exact
  conservation and defence-in-depth policies, the exact result models,
  and the revised Pending section confirming the deterministic core
  engine is now complete while Streamlit/UI, Gemini explanation, human
  approval, audit persistence, exports, and Sprint 4 hardening remain
  pending separate, later sprints), and `docs/TEST_SCENARIOS.md` (28
  concrete Stage 27 scenarios).

## [Unreleased] — 2026-08-18 — Sprint-label documentation correction

### Fixed
- A consistency audit against the frozen `MASTER_PROJECT_PLAN.md` found that Development
  Stages 1–27 throughout this changelog had been incorrectly labelled "Sprint 1" — the
  master plan's Sprint 1 is the pre-development repository-foundation/scaffolding phase
  only, and its Sprint 2 ("Deterministic Core Engine") planned scope explicitly names the
  modules Stages 1–27 implemented (`src/models.py`, `src/validation.py`, `src/metrics.py`,
  `src/pacing.py`, `src/classification.py`, `src/constraints.py`, `src/scoring.py`,
  `src/allocation.py`, `src/conservation.py`, culminating in Stage 27's
  `src/pipeline.py`). Every "Sprint 1, Development Stage N" label for Stages 1–27 was
  corrected to "Sprint 2, Development Stage N", including the Stage 1 fix note above. No
  stage number, implementation behaviour, test result, or code changed as part of this
  correction; Sprint 1 remains, unchanged, the pre-development foundation phase.

## [Unreleased] — 2026-08-18 — Sprint 3, Development Stage 28

### Added
- Sprint 3, Development Stage 28: filled in the Sprint 1 placeholder `app.py` as a
  deterministic-only Streamlit review shell — the first Sprint 3 implementation stage.
  Collects raw `ReviewSetup` input (`review_id`, `review_date`, `period_start`,
  `period_end`, `reviewer_name`, `approved_monthly_budget`, `initial_account_reserve`,
  `default_max_change_percentage`, `review_notes`) and an uploaded campaign CSV, calls the
  existing `validate_review_setup`/`validate_campaign_csv` (Stage 2) and
  `run_budget_reallocation_review` (Stage 27) functions, and renders their already-computed
  output. Reimplements no validation rule and no Stage 1–27 business formula. Currency and
  percentage text inputs are passed through as raw strings straight into the existing
  validator, never converted through `float`.
- Sprint 3, Development Stage 28: frozen execution-gating policy implemented as a pure,
  independently-testable predicate, `_may_run_pipeline` — the pipeline runs only when the
  form was explicitly submitted, review-setup validation returned a non-`None` review with
  no errors, a CSV was supplied and decoded as UTF-8, the campaign validation report
  contains no errors, and `valid_campaigns` is non-empty. A campaign CSV with any error —
  even alongside otherwise-valid rows — blocks the entire portfolio; warnings alone never
  block execution. Does not alter `run_budget_reallocation_review`'s own valid empty-tuple
  behavior.
- Sprint 3, Development Stage 28: explicit `st.form_submit_button` submission and
  session-state policy — `_handle_submission` runs only inside `if submitted:` (AST-
  verified), so an ordinary rerun never recomputes the pipeline; the locked result is held
  under session-state key `locked_review_result`, cleared to `None` at the start of every
  new submission before validation begins. One deliberate `except Exception` at the
  Streamlit UI boundary around the pipeline call keeps `locked_review_result` empty and
  shows an `st.error` with the exception's own message on an unexpected failure, without
  retrying, reclassifying, or fabricating a result; `run_budget_reallocation_review` itself
  remains unchanged and fail-fast.
- Sprint 3, Development Stage 28: read-only locked-result rendering — portfolio totals and
  every `conservation` field, plus every campaign result in original pipeline order (never
  sorted) with all fourteen `CampaignBudgetRecommendationResult` fields, ordered
  `reason_codes` preserved, and a missing `rank` shown as "Not ranked" rather than a
  fabricated number. Conservation is always visible for a successful result — an
  unconserved result is prominently flagged and remains fully inspectable, never concealed,
  repaired, rebalanced, or rerun; Stage 28 has no approval controls at all. All Decimal
  values are formatted via `format(value, "f")`; `float` is never referenced anywhere in
  the module.
- Sprint 3, Development Stage 28: added a new dedicated test file, `tests/test_app.py` — 31
  new tests using Streamlit `AppTest` (confirmed available and sufficient in the installed
  `streamlit==1.59.2`, including programmatic `file_uploader` population, so no
  widget-boundary mocking was needed). The real deterministic chain is exercised for every
  successful-path test; the sole deliberate mock replaces `run_budget_reallocation_review`
  in one dedicated exception-path test. Covers: widget presence and raw-input assembly;
  the execution-gating predicate (including warnings-non-blocking and
  empty-valid-campaigns-blocked cases); ordered validation-issue rendering for both invalid
  review setup and invalid/partially-valid CSV uploads; the exact real sample-data
  portfolio result (G001/M001/G002/G003, totals `11700.00`/`11700.00`, G002 remaining
  `INCREASE` with `allocated_amount=0.00` and `rank=1`); unranked-campaign display;
  conserved and unconserved conservation rendering; the pipeline-exception UI boundary;
  clear-before-validate and no-recompute-on-plain-rerun session-state behavior; Decimal-only
  formatting; non-alphabetical input-order preservation; invalid-UTF-8 upload handling; and
  AST-based isolation from Gemini/`config`/`src.explanations`/`src.approval`/`src.audit`/
  `src.exports` and from any duplicated Stage 1–27 formula or model mutation.
  `tests/test_integration.py` remains the untouched Sprint 3 full-flow placeholder
  (AST-confirmed: no function or class definitions). Stage 1–27 regression re-confirmed
  unchanged at 1258 tests. Full suite: 1289 tests passing (1258 + 31).
- Updated `docs/DATA_DICTIONARY.md` (Stage 28's consumed-model mapping and session-state
  key), `docs/DECISION_RULES.md` (frozen Stage 28 execution-gating, submission/session-state,
  exception, and rendering policies), and `docs/TEST_SCENARIOS.md` (Stage 28 scenarios).

## [Unreleased] — 2026-08-18 — Sprint 3, Development Stage 29

### Added
- Sprint 3, Development Stage 29: filled in the Sprint 1 placeholder `config.py` as a
  narrow, explicit, side-effect-controlled configuration boundary for Gemini API-key
  availability only — `GeminiConfig` (frozen, `extra="forbid"`, exactly one field:
  `api_key: SecretStr | None`), `load_gemini_config(dotenv_path: str | Path | None = None)
  -> GeminiConfig`, and `is_gemini_available(config: GeminiConfig) -> bool`. No Gemini
  model name, timeout, temperature, token limit, retry count, environment name, debug
  flag, audit/export directory, application title, or feature flag was added — none is
  justified by current repository evidence. No Gemini SDK is imported; no prompt
  construction, API call, or UI wiring is implemented. `app.py` is untouched and does not
  import `config` (AST-verified).
- Sprint 3, Development Stage 29: exact two-source precedence — the process environment
  variable `GEMINI_API_KEY` (checked for presence in `os.environ`, not truthiness) is
  authoritative whenever it exists, including when explicitly blank, in which case it does
  not fall back to `.env`; only when the variable is entirely absent is a local `.env` file
  consulted, read via `dotenv_values(...)` (never `load_dotenv(...)`, so `os.environ` is
  never mutated). Default `.env` path — used only when `dotenv_path` is not supplied — is
  `Path(__file__).resolve().parent / ".env"`, deterministic and independent of the current
  working directory, never searched in parent directories. Normalization is
  whitespace-trimming only; missing, blank, and whitespace-only keys are all normal, valid
  `GeminiConfig(api_key=None)` states and never raise.
- Sprint 3, Development Stage 29: `pydantic.SecretStr` redacts the key in `repr`, `str`,
  `model_dump()`, and `model_dump_json()`; retrievable only via the existing
  `config.api_key.get_secret_value()`, with no alternative accessor added.
  `is_gemini_available` never calls `get_secret_value()`; availability is derived
  (`api_key is not None`), never a stored field. Importing `config` performs no
  filesystem read, loads no `.env`, reads no environment variable, imports no Streamlit,
  imports no Gemini SDK, and creates no module-level configuration singleton.
- Sprint 3, Development Stage 29: recorded (not resolved) the `google-generativeai`
  (declared in `requirements.txt`, not installed) versus `google-genai` (installed
  instead) SDK mismatch — deferred to the future Gemini API-integration stage; Stage 29
  imports no Gemini SDK at all.
- Sprint 3, Development Stage 29: added a new dedicated test file, `tests/test_config.py`
  — 45 new tests, all passing, using only synthetic fake keys (no real secret is ever
  read, printed, or asserted against). Covers: the `GeminiConfig` schema, `extra="forbid"`,
  frozen behavior, and valid/invalid direct construction; every combination of
  present/absent/blank/whitespace-only environment and `.env` values and the exact
  precedence between them; explicit-`dotenv_path` and deterministic-default-path
  behavior with no parent/cwd search; zero `os.environ` mutation; zero import-time side
  effects and no module-level singleton; no `streamlit`/Gemini-SDK import; secret
  non-disclosure across `repr`/`str`/`model_dump()`/`model_dump_json()`; no exception on
  absent/blank loading; `app.py` independence (AST-verified no `config` import, and a real
  `AppTest` run with no `GEMINI_API_KEY` set); and confirmation that no real `.env` is ever
  created or modified. `tests/test_app.py` (Stage 28, 31 tests) and
  `tests/test_integration.py` (untouched placeholder) confirmed unmodified. Stage 1–27
  regression re-confirmed unchanged at 1258 tests; full Stage 1–28 suite re-confirmed
  unchanged at 1289 tests. Full suite: 1334 tests passing (1289 + 45).
- Updated `docs/DATA_DICTIONARY.md` (the `GeminiConfig` field and Stage 29's excluded
  values), `docs/DECISION_RULES.md` (frozen Stage 29 source-precedence, normalization,
  secret-protection, import/side-effect, deterministic-independence, and deferred-SDK
  policies), and `docs/TEST_SCENARIOS.md` (Stage 29 scenarios).

## [Unreleased] — 2026-08-18 — Sprint 3, Development Stage 30

### Added
- Sprint 3, Development Stage 30: filled in the Sprint 1 placeholder `src/explanations.py`
  as a pure, deterministic boundary between an already-locked pipeline result and whatever
  future stage actually calls Gemini — `CampaignExplanationPayload`,
  `PortfolioExplanationPayload`, `ExplanationPrompt` (all frozen, `extra="forbid"`), and
  exactly five public functions: `build_campaign_explanation_payload`,
  `build_portfolio_explanation_payload`, `serialize_explanation_payload`,
  `build_campaign_explanation_prompt`, `build_portfolio_explanation_prompt` — no
  orchestration wrapper. Never calls Gemini; never imports `config`, `GeminiConfig`,
  `is_gemini_available`, or `GEMINI_API_KEY`; never imports Streamlit or any Gemini SDK;
  never mutates a locked result. `app.py` is untouched.
- Sprint 3, Development Stage 30: frozen the Gemini boundary and the authorized-field
  set — `CampaignExplanationPayload` copies exactly fourteen authorized campaign fields
  directly from one locked `CampaignBudgetRecommendationResult`;
  `PortfolioExplanationPayload` copies `review_id`, both totals, and all four conservation
  fields directly from `result.conservation`, never recalculated. Raw CSV data,
  `ReviewSetup.review_notes`, raw metrics, validation issues, intermediate constraints,
  availability/suitability, the API key, and audit data are all excluded and unreachable.
  Campaign and portfolio payloads are structurally separate — no sibling-campaign data in
  one, no campaign list in the other, and no function loops over the full campaign
  collection to build a combined prompt, structurally preventing unsupported
  cross-campaign comparison.
- Sprint 3, Development Stage 30: canonical, deterministic, compact JSON serialization —
  key order matches Pydantic model field declaration order (never sorted),
  `ensure_ascii=False`, separators exactly `(",", ":")`, no indentation. `Decimal`/
  `Currency` values serialize as fixed-point strings via `format(value, "f")` (reusing the
  exact convention proven in `app.py` at Stage 28) — never a JSON number, never `float`,
  never scientific notation. Enums serialize to `.value`; tuples to JSON arrays, order
  preserved; `None` to `null`. Identical input produces byte-for-byte identical output.
- Sprint 3, Development Stage 30: one fixed, shared system-instruction constant — identical
  regardless of payload contents, containing no campaign/portfolio data, API key, SDK
  detail, model name, or generation parameter — states that supplied values are locked and
  authoritative, that the assistant explains but never decides, that reason-code order is
  authoritative, that a missing rank means "not ranked" (never rank zero), that a
  zero-funded directional action is not `MAINTAIN`/`HOLD`, and that an unconserved
  portfolio must be disclosed plainly, never concealed or repaired. User content contains
  one fixed sentence plus the canonical JSON between fixed
  `BEGIN_LOCKED_DATA`/`END_LOCKED_DATA` markers — no field interpolated individually into
  prose. `campaign_name` is treated as untrusted data; JSON escaping plus system/user
  separation are documented as containment, not elimination, of prompt injection — the
  decisive protection remains structural: no Gemini output ever has a path back into a
  locked deterministic model.
- Sprint 3, Development Stage 30: the output contract (response parsing, a response model,
  structured output, retries, timeouts, fallback explanations, API-error handling,
  persistence) and the `google-generativeai`/`google-genai` dependency mismatch recorded at
  Stage 29 both remain explicitly deferred to the future Gemini API-integration stage.
- Sprint 3, Development Stage 30: added a new dedicated test file,
  `tests/test_explanations.py` — 93 new tests, all passing. Real Stage 27 sample-data
  results used for primary success-path coverage (including the G002 zero-funded-INCREASE
  and G001 unranked cases); hand-built frozen fixtures used only for states unreachable
  through the real pipeline (an unconserved portfolio, extreme 28-significant-digit Decimal
  magnitudes, an empty portfolio). Covers: exact model schemas, `extra="forbid"`, frozen
  behavior, and exact function signatures; authorized-field copying with no recalculation
  and no unauthorized field; missing-rank and reason-code-order preservation; zero-funded
  `INCREASE` retained; no input mutation; canonical JSON (key order, separators, no
  indentation, enum/tuple/`None`/Decimal serialization, no float, no scientific notation,
  byte-for-byte determinism); shared fixed system instruction containing every frozen
  boundary rule and no campaign/portfolio/secret/SDK data; single-JSON-block user content;
  adversarial-campaign-name containment (quotes, backslashes, braces, newlines, Markdown,
  Unicode, literal marker text, instruction-like phrasing) with exact JSON round-tripping
  and structural marker-line safety; unconserved and empty-portfolio normal-state handling;
  and AST-based isolation from `config`, secrets, Streamlit, any Gemini SDK, the network,
  timestamps, randomness, logging, and broad exception handling. No Gemini output
  fabricated; no SDK mocked. `tests/test_app.py`, `tests/test_config.py`, and
  `tests/test_integration.py` confirmed unmodified. Stage 1–29 regression re-confirmed
  unchanged at 1334 tests. Full suite: 1427 tests passing (1334 + 93).
- Updated `docs/DATA_DICTIONARY.md` (the three payload/prompt models' fields and Stage 30's
  excluded values), `docs/DECISION_RULES.md` (frozen Stage 30 Gemini-boundary, granularity,
  serialization, prompt-architecture, injection-containment, and deferred-output-contract
  policies), and `docs/TEST_SCENARIOS.md` (Stage 30 scenarios).

## [Unreleased] — 2026-08-18 — Sprint 3, Development Stage 31

### Changed
- Sprint 3, Development Stage 31: resolved the recorded SDK dependency mismatch —
  `requirements.txt` now declares `google-genai>=2,<3`, replacing `google-generativeai`
  (never actually installed in this environment; officially documented as not actively
  maintained, with legacy libraries deprecated as of 2025-11-30). `pyproject.toml` is
  unchanged (no dependency section). No package was installed, removed, or upgraded — the
  already-installed `google-genai==2.12.1` satisfies the new pin. No code anywhere imports
  the legacy `google.generativeai`.

### Added
- Sprint 3, Development Stage 31: filled in the Sprint 1 placeholder `src/gemini_analyzer.py`
  as the transport/service layer sending one Stage 30 `ExplanationPrompt` to Gemini and
  returning a typed `ExplanationResult` — `ExplanationStatus` (`GENERATED`/`UNAVAILABLE`/
  `FAILED`), `ErrorCategory` (ten frozen values), and `ExplanationResult` (frozen,
  `extra="forbid"`, with a model validator enforcing exact state/field invariants for each
  status). One generic public function, `generate_explanation(prompt, config, *,
  client=None, model="gemini-2.5-flash-lite")` — no separate campaign/portfolio transport
  functions, no batch function. Accepts only `ExplanationPrompt`/`GeminiConfig`(+optional
  client/model override) — never a locked pipeline result, payload model, approval model,
  audit model, or Streamlit; `ExplanationResult` has no field capable of representing an
  action, budget, allocation, score, rank, reason, or conservation value. `app.py` is
  untouched.
- Sprint 3, Development Stage 31: frozen model/settings — default model
  `gemini-2.5-flash-lite` in one private module constant, overridable via the keyword-only
  `model` parameter; `temperature=0.2`; `max_output_tokens=512`; exactly one candidate; a
  `30_000`-millisecond timeout via `GenerateContentConfig.http_options=HttpOptions(...)`.
  No structured output, no safety-setting override, no seed, no stop sequences.
  `is_gemini_available` checked first — unavailable means zero client construction and zero
  API attempt, returning `UNAVAILABLE`/`CONFIGURATION` immediately.
- Sprint 3, Development Stage 31: client lifecycle — an injected client is used as-is and
  never closed; when none is injected, `config.api_key.get_secret_value()` is called at
  exactly one production call site to build one fresh `google.genai.Client` for that call
  only, always closed in `finally` on both success and failure. No module-level client or
  config singleton; importing the module performs no environment read, client construction,
  or network call.
- Sprint 3, Development Stage 31: failure mapping to ten frozen `ErrorCategory` values using
  the SDK's public exception/status interfaces (`ClientError`/`ServerError` by status code,
  `httpx.TimeoutException`/`NetworkError`, explicit safety-block signals via
  `finish_reason`/`prompt_feedback`, and structural extraction failures) — never a private
  undocumented internal. Exactly one provider invocation per call, no automatic retry, and
  no fabricated deterministic fallback explanation text. Any exception message from the
  owned-client path is sanitized — the known secret value replaced with `[REDACTED]` —
  before entering `error_message`; the raw provider response, request, headers, and
  credentials are never stored.
- Sprint 3, Development Stage 31: added a new dedicated test file,
  `tests/test_gemini_analyzer.py` — 61 new tests, all passing, using explicit fake
  clients/responses (never loose `MagicMock`) and zero real network/API calls. A real Stage
  27 sample-data campaign (G002), built through the real Stage 30 payload/prompt chain, is
  used for the primary success-path test. Covers: exact model schemas, `extra="forbid"`,
  frozen behavior, every valid state, and rejection of every inconsistent state; exact
  function signature; missing/blank-configuration unavailability with zero client
  construction/invocation; exact request-forwarding (system instruction, user content,
  model, temperature, token limit, timeout); injected-vs-owned client lifecycle including
  close-on-success/failure; every frozen failure category (authentication, rate limit,
  server error, timeout, network error, safety block via both finish-reason and
  prompt-feedback, empty/whitespace response, malformed-response extraction, unexpected
  exception) each with exactly-one-invocation verification; synthetic-key redaction through
  the owned-client path; no raw provider response retention; no mutation of locked inputs;
  import-time side-effect freedom; and AST-based isolation (single `get_secret_value()`
  call site, no logging/print, no locked-result/approval/audit/Streamlit/legacy-SDK
  references, no module-level singleton, no retry loop). `tests/test_config.py`,
  `tests/test_explanations.py`, and `tests/test_integration.py` confirmed unmodified. Stage
  1–30 regression re-confirmed unchanged at 1427 tests. Full suite: 1488 tests passing
  (1427 + 61).
- Updated `docs/DATA_DICTIONARY.md` (the `ExplanationResult`/`ExplanationStatus`/
  `ErrorCategory` fields and Stage 31's excluded values), `docs/DECISION_RULES.md` (frozen
  Stage 31 SDK-decision, transport-boundary, model/settings, failure-mapping, and
  client-lifecycle/secret-redaction policies), and `docs/TEST_SCENARIOS.md` (Stage 31
  scenarios).

## [Unreleased] — 2026-08-18 — Sprint 3, Development Stage 32

### Added
- Sprint 3, Development Stage 32: extended `app.py` with one optional, click-only Gemini
  explanation section, rendered strictly after the complete locked deterministic result —
  one portfolio-level explanation and one explanation for a user-selected campaign, never a
  batch across the whole portfolio and never generated automatically. The required section
  header ("Optional AI-generated explanations"), exact trust caption ("Gemini explanations
  are supplementary and may be inaccurate. The deterministic recommendations above remain
  authoritative."), and exact widget keys (`generate_portfolio_explanation`,
  `explanation_campaign_id`, `generate_campaign_explanation`) are implemented exactly as
  specified; the campaign selector is formatted `{campaign_id} — {campaign_name}`. Both
  buttons appear only with a locked result, remain enabled regardless of Gemini
  configuration, and are never placed inside the deterministic-review form; each is its own
  manual retry/regenerate control — no separate retry control exists.
- Sprint 3, Development Stage 32: added `portfolio_explanation_result`,
  `campaign_explanation_result`, and `campaign_explanation_campaign_id` session-state keys
  alongside the existing `locked_review_result`. All four are cleared at the very start of
  every new deterministic-review submission, before validation, so a failed resubmission
  never leaves a stale explanation visible. Ordinary reruns preserve stored explanations and
  trigger no Gemini call. Each click clears, then rebuilds and replaces, only its own
  result. The stored campaign explanation renders only when its recorded campaign ID
  matches the current selection — changing the selector hides a mismatched explanation
  without a call, and reselecting the original campaign redisplays it without regenerating.
- Sprint 3, Development Stage 32: portfolio and campaign flows call only the existing
  Stage 29/30/31 boundary — `build_portfolio_explanation_payload` →
  `build_portfolio_explanation_prompt` → `load_gemini_config()` →
  `generate_explanation(prompt, config)` (and its campaign-level counterpart) —
  `generate_explanation` receives only the resulting `ExplanationPrompt` and `GeminiConfig`,
  never a locked result or payload model. A shared private rendering helper handles every
  `ExplanationResult` consistently: `GENERATED` shows a local heading, `explanation_text`
  via `st.markdown(..., unsafe_allow_html=False)` (never `True`), and an "AI-generated
  using {model_name}" caption; `UNAVAILABLE`/`FAILED` show only the already-sanitized
  `error_message`; `error_category` is never displayed. The locked deterministic totals,
  conservation result, and campaign table remain fully visible and authoritative in every
  explanation state. `app.py` never accesses `config.api_key`, references `SecretStr`,
  calls `get_secret_value()`, inspects an environment variable, or reads `.env` directly. An
  unexpected failure while building a payload/prompt or calling the transport is caught only
  at one click-handler boundary per action — a concise generic error is shown, no fabricated
  result is stored, the locked result is preserved untouched, and no automatic retry occurs.

### Fixed
- Sprint 3, Development Stage 32: one approved, narrow exception to three pre-existing
  tests. `tests/test_app.py`'s `test_module_does_not_import_forbidden_modules` and
  `test_module_does_not_reference_forbidden_names`, and `tests/test_config.py`'s former
  `test_app_module_does_not_import_config` (renamed
  `test_app_module_imports_config_but_never_touches_the_raw_key`), were written when
  `app.py` legitimately had no reason to import `config`, `src.explanations`, or
  `src.gemini_analyzer`. Per explicit approval, each test's forbidden set was narrowed to
  remove only those three entries; every other forbidden entry in all three tests is
  unchanged and still enforced — mirroring the identical pattern already used at Stages 7,
  8, and 11.

### Added
- Sprint 3, Development Stage 32: added a new dedicated test file,
  `tests/test_app_explanation.py` — 35 new tests, all passing, using explicit
  fake/monkeypatched generation behavior and zero real Gemini/network calls. Covers:
  section/widget presence and absence without a locked result; widget and trust-caption
  presence after a successful review; real Stage 30 payload/prompt construction reaching
  the real Stage 31 transport boundary unchanged; campaign-selector formatting and
  exact-campaign resolution; rendering of `GENERATED`/`UNAVAILABLE`/`FAILED` for both flows;
  `error_category` never rendered and sanitized-message-only verification; one-click/
  one-call and zero-additional-call-on-rerun discipline; re-click replacement of a prior
  result; no-call-on-selector-change, stale-explanation hiding, and no-regeneration
  redisplay on returning to the original selection; explanation-state clearing on both a
  new successful and a new invalid deterministic submission; full deterministic-result
  visibility and non-mutation across explanation actions; the real, network-free
  `UNAVAILABLE` path; API-key absence from every rendered element and from session state;
  no `unsafe_allow_html=True`; the single explanation-action exception boundary; and
  AST-based isolation (no secret access, no direct environment/`.env` access, no automatic
  generation outside button branches, no retry loop, no approval/audit/export imports). A
  file-scoped autouse fixture defensively restores `app.run_budget_reallocation_review`
  before every test in this file, since `AppTest`'s embedded `import app` resolves to the
  same process-wide module object used everywhere else — this protects only this file's own
  tests and modifies no other file. `tests/test_config.py`, `tests/test_explanations.py`,
  `tests/test_gemini_analyzer.py`, and `tests/test_integration.py` confirmed unmodified
  beyond the one approved exception above. Stage 1–31 regression re-confirmed unchanged at
  1488 tests. Full suite: 1523 tests passing (1488 + 35).
- Updated `docs/DATA_DICTIONARY.md` (the four explanation-related session-state keys and
  Stage 32's excluded state), `docs/DECISION_RULES.md` (frozen Stage 32 widget, lifecycle,
  rendering, secret-boundary, exception-containment, and approved-test-exception policies),
  and `docs/TEST_SCENARIOS.md` (Stage 32 scenarios).

### Changed
- Sprint 3, Development Stage 33: one approved, narrow exception to three pre-existing
  tests. `tests/test_app.py`'s `test_module_does_not_import_forbidden_modules` and
  `test_module_does_not_reference_forbidden_names`, and `tests/test_app_explanation.py`'s
  `test_no_approval_audit_or_export_imports` (renamed `test_no_audit_or_export_imports`),
  were written when `app.py` legitimately had no reason to import `src.approval`. Per
  explicit pre-approval, each test's forbidden set was narrowed to remove only
  `src.approval`/`approval`; every other forbidden entry in all three tests is unchanged
  and still enforced — mirroring the identical pattern already used at Stages 7, 8, 11, and
  32.

### Added
- Sprint 3, Development Stage 33: implemented `src/approval.py` (placeholder replaced) —
  the human approval/rejection workflow applied to the complete locked
  `BudgetReallocationReviewResult` only, never per-campaign or partial. Reuses the existing
  Stage 1 `ReviewStatus` enum rather than a new `ApprovalDecision` enum, restricted via a
  `@field_validator` to `APPROVED`/`REJECTED` only. `CampaignReallocationApproval` (frozen,
  `extra="forbid"`: `review_id`, `decision`, `reviewer_name`, `note: str | None = None`).
  `approve_campaign_reallocation_review(result, reviewer_name, *, note=None)` refuses an
  unconserved result with exactly `ValueError("An unconserved allocation cannot be
  approved.")`; `reject_campaign_reallocation_review(result, reviewer_name, *, note=None)`
  places no such restriction. Both raise exactly `ValueError("Reviewer name must not be
  blank.")` for a blank/whitespace-only name, checked first. `review_id` is always derived
  from the locked result, never a separate parameter. No timestamp, no Gemini/config/audit/
  export coupling, no repair/rebalance/rerun behavior.
- Sprint 3, Development Stage 33: extended `app.py` with a new "Human approval" section
  rendered immediately after the optional explanation section. Exact caption: "Approval
  applies to the complete locked deterministic review. AI-generated explanations are
  supplementary and are not part of the approval decision." Exact widgets:
  `st.text_input("Approver name", key="approval_reviewer_name")` (starts blank — not
  pre-filled from `ReviewSetup.reviewer_name`, per explicit approval), `st.text_area("Decision
  note (optional)", key="approval_note")`, `st.button("Approve deterministic review",
  key="approve_review")`, `st.button("Reject deterministic review", key="reject_review")`.
  No confirmation checkbox, radio selector, reconsider button, or change-decision control.
  New session-state key `APPROVAL_DECISION_STATE_KEY = "approval_decision_result"`, cleared
  (alongside the approval widget values) at the very start of every new deterministic
  submission, immediately after the existing explanation-state clears. A successful decision
  triggers one immediate `st.rerun()` so the finalized view (`st.success("Decision:
  APPROVED")`/`st.warning("Decision: REJECTED")`, approver, and optional note) fully replaces
  the editable controls within a single clean run — Streamlit cannot retroactively remove
  elements already emitted earlier in the same run. A finalized decision cannot be
  overwritten or reconsidered; a defense-in-depth check clears a stored decision whose
  `review_id` no longer matches the current locked result, with a generic mismatch error
  (explicitly not a result fingerprint). Exactly one domain-function call per click, with a
  `ValueError` shown verbatim and any other exception contained behind a generic message —
  no raw exception, traceback, or provider detail exposed, no fabricated decision stored.
- Sprint 3, Development Stage 33: added `tests/test_approval.py` (placeholder replaced) —
  31 new tests, all passing. Covers exact model fields, `extra="forbid"`, frozen,
  `APPROVED`/`REJECTED` valid and `DRAFT`/`PENDING_APPROVAL` rejected, blank-field rejection
  and whitespace-stripping, note normalization, exact function signatures, conserved/
  unconserved approve/reject behavior, exact error messages, check-ordering, `review_id`
  derivation from the locked result only, non-mutation of the locked result, and AST-based
  isolation (no Gemini/config/audit/export/filesystem/network/wall-clock/random/uuid
  reference anywhere in the module).
- Sprint 3, Development Stage 33: added a new dedicated test file,
  `tests/test_app_approval.py` — 34 new tests, all passing, using `AppTest` with explicit
  fixtures/monkeypatches and zero live network calls/real API key. Covers control
  presence/absence, the exact heading/caption, the approver field starting blank,
  successful approve/reject with and without a note, blank-name and unconserved-approval
  validation, unconserved-rejection success, one-click/one-call and
  zero-call-on-ordinary-rerun discipline, finalized-decision rendering that replaces all
  editable controls and cannot be overwritten, approval-state clearing on new successful and
  new invalid submissions, explanation-generation and campaign-selector independence,
  Gemini/API-key independence, deterministic-result visibility and non-mutation across every
  outcome, the stale-review-ID defense-in-depth path, the single unexpected-exception
  boundary with no raw exception/provider detail exposed, no audit/export/
  platform-execution behavior, and the session-state clearing lifecycle at the source level.
  A file-scoped autouse fixture restores `app.approve_campaign_reallocation_review`,
  `app.reject_campaign_reallocation_review`, `app.generate_explanation`, and
  `app.run_budget_reallocation_review` to their real implementations before every test,
  mirroring the established Stage 32 defensive pattern against `AppTest`'s shared
  `sys.modules["app"]` singleton. Stage 1–32 regression re-confirmed unchanged at 1523
  tests. Full suite: 1588 tests passing (1523 + 31 + 34).
- Updated `docs/DATA_DICTIONARY.md` (the approval session-state keys and `CampaignReallocationApproval`
  model fields), `docs/DECISION_RULES.md` (frozen Stage 33 model, function, conservation,
  UI, lifecycle, and approved-test-exception policies), and `docs/TEST_SCENARIOS.md` (Stage
  33 scenarios).

### Changed
- Sprint 3, Development Stage 34: one approved, narrow exception to four pre-existing
  tests. `tests/test_app.py`'s `test_module_does_not_import_forbidden_modules` and
  `test_module_does_not_reference_forbidden_names`, `tests/test_app_explanation.py`'s
  `test_no_audit_or_export_imports`, and `tests/test_app_approval.py`'s
  `test_no_audit_export_or_platform_imports_in_app` were narrowed to permit `src.audit`
  only; `src.exports` remains forbidden and enforced in all four — mirroring the identical
  pattern already used at Stages 7, 8, 11, 32, and 33.
- Sprint 3, Development Stage 34: one additional authorized test-harness change in
  `tests/test_app_approval.py`. Its `_fresh_app()` and `_unconserved_app()` helpers were
  converted from `AppTest.from_file` to `AppTest.from_string`, with
  `app.record_campaign_reallocation_audit` redirected to an isolated OS temp directory
  embedded directly in the executed script. Required because Stage 34 made every real
  approve/reject click also attempt automatic audit persistence; without this change all 34
  pre-existing Stage 33 UI tests would write real files into the repository's tracked
  `audit_records/` directory on every run, since `AppTest.from_file` executes app.py in a
  namespace that does not honor an external `monkeypatch` of this function (confirmed
  empirically). All 34 existing tests and their assertions are unchanged; only the harness
  plumbing changed.

### Added
- Sprint 3, Development Stage 34: implemented `src/audit.py` (placeholder replaced) — the
  durable, structured JSON record of exactly one complete locked
  `BudgetReallocationReviewResult` and its finalized `CampaignReallocationApproval`, the
  only component in the project that persists anything to disk. `CampaignReallocationAudit`
  (frozen, `extra="forbid"`: `audit_id`, `review_id`, `result`, `approval`, `recorded_at`)
  embeds the existing frozen Stage 27/33 models directly rather than copying their fields.
  A `@field_validator` rejects a naive `recorded_at` and normalizes any aware timestamp to
  UTC. `build_campaign_reallocation_audit(result, approval, recorded_at)` is pure and
  enforces `approval.review_id == result.review_id` (else exactly `ValueError("Approval
  review_id does not match the locked result's review_id.")`) and, only for an `APPROVED`
  decision, `result.conservation.is_conserved` (else exactly `ValueError("An unconserved
  allocation cannot be recorded as approved.")`); a rejected unconserved result is always
  recordable. `audit_id` is a SHA-256 digest of the canonical JSON of `{"result": result,
  "approval": approval}`, excluding `recorded_at`, prefixed `audit_`. No wall-clock call
  exists anywhere in this module. `record_campaign_reallocation_audit(audit, *,
  directory=None)` writes one UTF-8 JSON file per record at `audit_records/{audit_id}.json`
  (default directory resolved from the module's own location), atomically via a temporary
  file plus `os.replace`; a pre-existing file with matching substantive content is an
  idempotent no-op returning the original path, a pre-existing file with different content
  raises exactly `ValueError("An audit record with this audit_id already exists with
  different content.")`, and a malformed existing file raises without being overwritten. No
  public read, list, delete, repair, overwrite, or retry function exists — reserved for
  Stage 35. No Gemini, configuration, export, network, or database coupling anywhere.
- Sprint 3, Development Stage 34: extended `app.py` so audit persistence happens
  automatically from the same approve/reject click, not a separate confirmation action.
  New session-state keys `AUDIT_RECORD_PATH_STATE_KEY = "audit_record_path"` and
  `AUDIT_RECORD_ERROR_STATE_KEY = "audit_record_error"`, cleared at the start of every new
  deterministic submission. The one production `datetime.now(timezone.utc)` call lives in
  the new `_attempt_audit_recording` helper, the single Stage 34 audit-action boundary. On
  success: `st.success("Audit record written.")` plus a caption `Audit ID: {audit_id}` (the
  filename stem — the full local filesystem path is never displayed). On failure: the
  finalized decision remains fully visible and unchanged; `st.error("The decision was
  finalized, but its audit record could not be written.")` with no raw exception, stack
  trace, or filesystem detail exposed, and exactly one `st.button("Retry audit recording",
  key="retry_audit_recording")` that performs no new approval/rejection, relies on the
  stage's own idempotency, and never fires automatically.
- Sprint 3, Development Stage 34: added `tests/test_audit.py` (placeholder replaced) — 38
  new tests, all passing. Covers exact model fields, `extra="forbid"`, frozen, aware-UTC
  timestamp acceptance, naive-timestamp rejection, non-UTC-aware normalization, the exact
  ID-mismatch and unconserved-approval error messages, rejected-unconserved acceptance,
  deterministic content-derived audit-ID construction (excluding `recorded_at`; changing
  with reviewer/note/result content), fixed-point `Decimal` preservation including trailing
  zeros and extreme values, enum/tuple/datetime preservation, byte-for-byte canonical-JSON
  determinism, missing-directory creation, successful `tmp_path` writes, identical- and
  different-timestamp idempotent retries, conflicting- and malformed-existing-record
  rejection without overwrite, serialization/finalization-failure cleanup leaving no
  partial file, non-mutation of `result`/`approval`, isolation from Gemini/config/exports/
  network/database, and the absence of any public read/list/delete/export function.
- Sprint 3, Development Stage 34: added a new dedicated test file, `tests/test_app_audit.py`
  — 21 new tests, all passing, using `AppTest.from_string` with the audit-directory redirect
  embedded directly in each script and zero real network/filesystem/Gemini calls. Covers an
  approved or rejected decision automatically creating exactly one record; the correct
  locked result and finalized approval reaching the builder; one click causing one
  persistence call; zero additional writes on ordinary and repeated reruns; the exact
  success message and audit ID (never the full path); a failed write leaving the decision
  fully finalized with the exact sanitized message, no raw exception, and exactly one retry
  control; retry performing no second approval call and clearing the error on success; no
  automatic retry on ordinary reruns; audit-state clearing on both a new valid and a new
  invalid submission; independence from Gemini explanation actions; and full
  deterministic-result visibility and non-mutation throughout. A file-scoped autouse
  fixture restores `app.build_campaign_reallocation_audit`,
  `app.record_campaign_reallocation_audit`, and the Stage 27/31/33 functions to their real
  implementations before every test. Stage 1–33 regression re-confirmed unchanged at 1588
  tests. Full suite: 1647 tests passing (1588 + 38 + 21). Zero test-created files under the
  repository's real `audit_records/` directory across every verification pass.
- Updated `docs/DATA_DICTIONARY.md` (the `CampaignReallocationAudit` model fields and the
  Stage 34 audit session-state keys), `docs/DECISION_RULES.md` (frozen Stage 34 model,
  function, consistency-check, ID/idempotency, persistence, UI, and approved-test-exception
  policies), and `docs/TEST_SCENARIOS.md` (Stage 34 scenarios).

### Changed
- Sprint 3, Development Stage 35: one approved, narrow exception to three pre-existing
  tests. `tests/test_app.py`'s `test_module_does_not_import_forbidden_modules`,
  `tests/test_app_explanation.py`'s `test_no_audit_or_export_imports`, and
  `tests/test_app_approval.py`'s `test_no_audit_export_or_platform_imports_in_app` were
  narrowed to remove only `src.exports`, because `app.py` now legitimately imports it for
  the CSV export section. For the latter two, `src.exports` was the sole remaining member
  of their forbidden sets, so both assertions are now `isdisjoint(set())` — a faithful
  record that every module they originally guarded against is now a legitimate,
  separately-covered import. The anticipated bare-name narrowing in
  `tests/test_app.py::test_module_does_not_reference_forbidden_names` was confirmed not
  required — no bare `exports` identifier exists in `app.py`'s AST.

### Added
- Sprint 3, Development Stage 35: implemented `src/exports.py` (placeholder replaced) — the
  CSV export of a successfully persisted `CampaignReallocationAudit`, the frozen, combined
  Stage 34 record of one locked result and its finalized approval. Never rebuilds, rereads,
  or reinterprets an audit; consumes exactly one `CampaignReallocationAudit` object, never
  separate `result`/`approval` arguments, and never calls any Stage 1–34 production
  function. `CampaignReallocationExportRow` (frozen, `extra="forbid"`, 26 fields).
  `build_campaign_reallocation_export_rows(audit) -> tuple[CampaignReallocationExportRow,
  ...]` and `serialize_campaign_reallocation_export_csv(rows) -> str` are the only two
  public functions. One flat CSV, one row per campaign, in `campaign_results`' own original
  order, with shared audit/approval/portfolio-total/conservation values repeated on every
  row; an audit with no campaigns produces a valid header-only CSV. Exact frozen column
  order: `audit_id, review_id, recorded_at, decision, reviewer_name, decision_note,
  total_current_budget, total_recommended_budget, total_increase_allocated,
  total_decrease_allocated, net_change, is_conserved, campaign_id, campaign_name, platform,
  current_budget, recommendation_action, allocated_amount, recommended_budget,
  reason_codes, performance_band, trend_direction, confidence, pacing_status,
  reallocation_priority_score, rank`. `Decimal` values via `format(value, "f")`; enums via
  `.value`; `recorded_at` via `.isoformat()`; `rank=None` → `"Not ranked"`; `note=None` →
  `""`; `is_conserved` written as the raw `bool` (`csv.writer` renders `True`/`False`). One
  private CSV formula-injection neutralization helper applied to `review_id`,
  `reviewer_name`, `decision_note`, `campaign_id`, and `campaign_name` (single apostrophe
  prefix when the first non-whitespace character is `=`/`+`/`-`/`@`, idempotent, applied to
  no other field type). No JSON export, no local export persistence, no `exports/`
  directory, no `.gitignore` change, no Gemini/config/secret coupling.
- Sprint 3, Development Stage 35: extended `app.py` with a new "CSV export" section,
  rendered only once an audit record has actually been persisted (never merely built or
  merely approved), immediately after the human-approval section, identically for
  `APPROVED` and `REJECTED` audits. New session-state key `AUDIT_RECORD_STATE_KEY =
  "audit_record"` holds the exact successfully persisted `CampaignReallocationAudit`
  object, populated only after `record_campaign_reallocation_audit` succeeds inside
  `_attempt_audit_recording`, and cleared at the start of every audit-recording attempt and
  every new deterministic submission. Exact download button: label `"Download audited
  recommendations CSV"`, `file_name=f"{audit.audit_id}.csv"`, `mime="text/csv"` — no
  separate "Generate export" or retry control, since generation is fully in-memory and
  deterministic. On an unexpected export-construction failure: exactly `st.error("The CSV
  export could not be prepared. The finalized review and audit record remain unchanged.")`
  — no raw exception, traceback, or absolute path exposed; the locked result, approval, and
  audit object are all left unchanged.
- Sprint 3, Development Stage 35: added `tests/test_exports.py` (new — no placeholder
  previously existed) — 40 new tests, all passing. Covers exact model fields,
  `extra="forbid"`, frozen, exact function signatures, exact column order, header-only CSV
  for an empty campaign tuple, approved and rejected audits (including a rejected,
  unconserved audit), exact audit/approval/portfolio and campaign field copying, preserved
  campaign and reason-code order, `rank=None`/`note=None` handling, exact `Decimal`
  fixed-point formatting (trailing zeros, extreme precision, no scientific notation), exact
  UTC ISO timestamp, deterministic repeated builds/serialization, special characters
  round-tripped through `csv.DictReader`, CSV formula-injection neutralization for all four
  trigger characters (including after leading whitespace, safe/empty text unchanged, no
  double-neutralization), exact `is_conserved` Boolean text, non-mutation of the input
  audit, and isolation from `float`, the filesystem, the network, Gemini/config/secrets,
  and every Stage 1–34 production function.
- Sprint 3, Development Stage 35: added a new dedicated test file,
  `tests/test_app_exports.py` — 20 new tests, all passing, using `AppTest.from_string` with
  the established Stage 34 audit-directory redirect embedded directly in each script and
  zero real network/filesystem/Gemini calls. Covers the export section's absence without a
  locked result, before a decision, and while audit recording has failed; its presence only
  once persistence actually succeeds, identically for approved and rejected audits; the
  exact download-button label; the exact literal `file_name`/`mime` arguments (verified via
  AST source inspection, since `AppTest` exposes no stable public accessor for a download
  button's underlying bytes/filename/MIME in this Streamlit version); the exact CSV content
  built from the exact stored audit object (verified via a capturing wrapper around the
  real Stage 35 functions); deterministic, non-duplicated generation across reruns; a
  successful audit retry making the export appear; session-state clearing on both a new
  valid and a new invalid submission; sanitized failure rendering with no raw exception; no
  Gemini invocation and no pipeline rerun triggered by the export section; and no real
  audit/export file left behind. Stage 1–34 regression re-confirmed unchanged at 1647
  tests. Full suite: 1707 tests passing (1647 + 40 + 20). Zero test-created files under the
  repository's real `audit_records/` directory, and no `exports/` directory ever created,
  across every verification pass.
- Updated `docs/DATA_DICTIONARY.md` (the `CampaignReallocationExportRow` model fields and
  the exact CSV column order), `docs/DECISION_RULES.md` (frozen Stage 35 format, source-of-
  truth, gating, schema, serialization, formula-injection, and approved-test-exception
  policies), and `docs/TEST_SCENARIOS.md` (Stage 35 scenarios).

### Changed
- Sprint 3, Development Stage 36: one approved exception, retiring four now-obsolete guard
  assertions rather than duplicating unit-level coverage. `tests/test_app.py`'s
  `test_test_integration_remains_untouched`, and `tests/test_app_explanation.py`'s,
  `tests/test_config.py`'s, and `tests/test_explanations.py`'s respective
  `test_test_integration_remains_unchanged`, each asserted that `tests/test_integration.py`
  contained zero function/class definitions, guarding against premature implementation
  before Stage 36. Since Stage 36 legitimately populates that file for the first time, the
  guard's condition is now permanently false by design; all four were retired (removed,
  with an explanatory comment pointing to `tests/test_integration.py`) rather than replaced.
  No other assertion in any of the four files was touched.

### Added
- Sprint 3, Development Stage 36: implemented `tests/test_integration.py` (placeholder
  replaced) — 12 focused end-to-end integration tests, all passing, proving the complete
  frozen Sprint 3 flow works together through real Streamlit `AppTest` widget interaction:
  CSV upload → review-setup validation → campaign validation → deterministic pipeline →
  locked result → optional Gemini explanation → human approval or rejection → immutable
  audit construction → successful audit persistence → audited CSV export availability.
  Every scenario that approves or rejects uses `AppTest.from_string` with
  `app.record_campaign_reallocation_audit` redirected to the test's own `tmp_path`, never
  `AppTest.from_file`. Zero real Gemini SDK client construction, zero real network calls,
  zero real API key used or required, zero real `.env` created. Covers: the approved flow
  from upload through export against the real sample data and the real deterministic
  pipeline, asserting the exact, independently pre-established stable sample contract
  (total budgets, conservation, exact campaign outcomes and reason codes) without
  re-deriving any formula; the rejected flow with unchanged recommendations, a persisted
  `REJECTED` audit, and every exported CSV row recording `REJECTED`; a fake generated
  explanation proven supplementary and structurally absent from both the audit JSON and the
  CSV, with call-count and rerun discipline; the real, network-free Gemini-unavailable path
  not blocking approval, audit, or export; an injected unconserved result blocking approval
  with the exact existing error while permitting and finalizing rejection; an audit
  failure-then-successful-retry cycle leaving exactly one audit JSON and the export control
  appearing only after success; an invalid `ReviewSetup` and a mixed valid/invalid CSV both
  blocking the entire portfolio with zero downstream state; new valid and invalid
  submissions clearing every downstream state key; a bare rerun after a completed cycle
  leaving every piece of state byte-identical with zero additional pipeline/Gemini/audit
  calls; and a cross-cutting sweep confirming no synthetic key, fake explanation text, raw
  exception, or absolute path ever appears in any rendered element, session-state value,
  the audit JSON, or the CSV, and that the real repository `audit_records/` directory and
  overall file listing are unchanged before and after the full scenario set. One additional
  defensive isolation fixture, scoped entirely to this new file, restores
  `sys.modules["src.gemini_analyzer"]` to its original module object before and after every
  test — required because `tests/test_gemini_analyzer.py`'s own reimport test otherwise
  silently breaks `app.py`'s cached `ExplanationStatus` identity check for any fake
  explanation built afterward; no existing test file was modified for this purpose. Stage
  1–35 regression re-run and confirmed passing at `1703 passed` (the prior `1707` baseline
  minus the four retired guard tests above). Full suite: `1715 passed` (1703 + 12). Zero
  test-created files under the repository's real `audit_records/` directory, no `exports/`
  directory ever created, and no real `.env` ever created, across every verification pass.
- Updated `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md` (frozen Stage 36 execution
  strategy, zero-network-Gemini policy, and approved-test-exception decisions), and
  `docs/TEST_SCENARIOS.md` (Stage 36 scenarios).

## Sprint 3 — Explanation, Approval, and Interface: Complete

All frozen Sprint 3 exit criteria (`project_management/MASTER_PROJECT_PLAN.md`) are now
satisfied and demonstrated together by Stage 36's own integration suite: the complete
upload → validate → assess → recommend → lock → explain (Gemini) → approve/reject → audit
record written → CSV export available flow works end-to-end; Gemini remains verifiably
confined to explanation of locked numbers with no path to alter recommendations or touch
live advertising-platform budgets; and every approval or rejection produces a traceable
JSON audit record. Sprint 4 — Hardening and Documentation is next and has not yet started.

## Sprint 4 — Hardening and Documentation (in progress)

### Changed
- Sprint 4, Development Stage 37: corrected the stale top-of-file status headers in
  `docs/DATA_DICTIONARY.md` (previously frozen at "Sprint 3, Development Stage 28"),
  `docs/DECISION_RULES.md` (previously frozen at "Sprint 2, Development Stage 21"), and
  `docs/TEST_SCENARIOS.md` (previously frozen at "Sprint 2, Development Stage 21") to
  accurately state Sprint 3 (Stages 28–36) complete, Sprint 4 active, and Stage 37's role
  finalizing all five living documentation files — each file's own body already correctly
  documented through Stage 36 and was left completely untouched; only the header
  blockquote changed in each of the three files.

### Added
- Sprint 4, Development Stage 37: fully replaced the Sprint 1 placeholder content of
  `docs/ARCHITECTURE.md` with an accurate architecture document grounded directly in the
  completed Stage 1–36 source code — system purpose and three-tier trust model
  (deterministic core / Gemini explanation / human decision); the full module-to-stage
  responsibility table; the deterministic core pipeline (validation boundary, metrics and
  classifications, constraints, availability/suitability/recommendation/reasons/scoring,
  ranking/allocation/conservation, Stage 27 orchestration); the Streamlit interface and
  its eight-key session-state lifecycle; optional Gemini configuration, locked explanation
  payload/prompt construction, and the Gemini transport boundary; human approval/
  rejection; immutable audit construction and local JSON persistence; in-memory audited
  CSV export; a Mermaid end-to-end data-flow diagram; the human-in-the-loop boundary; AI
  isolation and structural lack of authority over deterministic results; security/
  secret-handling and persistence boundaries; failure behaviour; the explicit absence of
  advertising-platform integrations; the fake-client/network-free test architecture; and a
  dedicated section documenting the actual, currently-implemented state of
  `RecommendationAction.HOLD` (fully implemented via a six-step ordered policy in
  `src/recommendation.py` — not pending), `Confidence.NOT_ASSESSABLE` (a reserved
  `src/constants.py` enum member never assigned by `classify_campaign_confidence` or any
  other current production function), and `ReasonCode` (exactly 8 of 20 members currently
  emitted by `src/reasons.py`, with the remaining 12 named individually as
  reserved-but-unemitted or intentionally excluded) — every claim verified directly
  against source before being written; no enum member added, removed, or altered, and no
  new business logic invented.
- Sprint 4, Development Stage 37: fully replaced the Sprint 1 placeholder content of
  `docs/LIMITATIONS.md` with honest, current-fact limitations and non-goals: no live
  advertising-platform ingestion or budget writeback; uploaded-CSV-only data-quality
  dependency; Gemini's optional, non-authoritative role and its possible unavailable/
  blocked/incomplete/incorrect states, plus its third-party cost/data-processing
  implications; mandatory human approval/rejection before audit persistence or export;
  approval is not a platform-execution action; local JSON audit storage rather than a
  production database; in-memory-only CSV export; no authentication, authorization/RBAC,
  multi-user concurrency model, centralized database, distributed locking, cloud
  persistence, automatic audit backup/retention, real-time monitoring, scheduled
  execution, retry queue/background job processor, or production observability; explicit
  local/single-user pilot orientation (not an enterprise-production-readiness claim,
  matching the master plan's own "ready for real-world pilot use" wording); the current
  Python 3.14-on-Windows-only verified test environment; and an explicit statement that
  reserved enum/`ReasonCode` values are not evidence of implemented behaviour.
- Documentation-only stage: no production file, test file, or application behaviour
  changed. Exactly eight files touched (the five documentation files above plus
  `project_management/CURRENT_SPRINT.md`/`DECISIONS.md`/`CHANGELOG.md`); every other file
  — `app.py`, `config.py`, all of `src/` and `tests/`, `README.md`, `requirements.txt`,
  `pyproject.toml`, `.env.example`, `.gitignore`, all `data/` files, and
  `project_management/MASTER_PROJECT_PLAN.md` — confirmed at zero diff. No API key was
  created, read, requested, or used; no network call of any kind occurred. Full suite
  re-confirmed unchanged at `1715 passed`. `audit_records/` confirmed to still contain
  only `.gitkeep`; no `exports/` directory exists; no real `.env` exists. Sprint 4 remains
  incomplete: a `README.md` rewrite, packaging/dependency-consistency hardening, and
  test-suite hardening (including adversarial/edge-case CSV inputs) all remain future
  Sprint 4 work, not started by this stage.

### Changed
- Sprint 4, Development Stage 38: fully replaced the stale `README.md`. The previous
  content still described the project as "Sprint 2 — Deterministic Core Engine complete...
  Sprint 3... is next" with a `1258 passed` baseline, listed only a 5-item solution
  summary omitting CSV export, and contained no installation, Gemini-configuration,
  testing, or limitations guidance of any kind. The new README accurately reflects the
  completed Stage 1–36 implementation and current Stage 38 status: project description and
  the explicit never-writes-to-a-live-platform boundary; the three-layer trust and
  governance model (deterministic rules decide, Gemini only explains, human approval is
  mandatory before persistence/export); an accurate feature summary; a compact
  architecture overview linking to all five `docs/` files; repository-evidenced
  requirements; copyable Windows PowerShell installation steps plus an unverified-but-
  equivalent macOS/Linux note; optional Gemini configuration guidance using only
  placeholder key text with an explicit never-commit/print/share warning; the
  `streamlit run app.py` command and the 8-step normal workflow, including the
  invalid-input portfolio-blocking rule; CSV input guidance linking to the real template
  and sample files and the data dictionary; accurate outputs/persistence facts
  (session-state-only locked result, `audit_records/` as the default local audit
  directory with `.gitkeep` as its only tracked file, in-memory-only CSV export, no
  `exports/` directory, no production database); verified testing commands and exact
  current counts (`12 passed` integration, `1715 passed` full suite) with an explicit
  no-CI-workflow statement; security and privacy disclosures; a limitations/non-goals
  summary linking to `docs/LIMITATIONS.md`; a repository-structure table; pilot-use
  guidance explicitly distinguishing real-world pilot readiness from
  enterprise-production readiness; and the correct MIT licence reference.

### Notes
- Documentation-only stage: no production file, test file, dependency, or application
  behaviour changed. Exactly four files touched (`README.md` and the three
  project-management tracking files); every other file — `app.py`, `config.py`, all of
  `src/` and `tests/`, all of `docs/`, `requirements.txt`, `pyproject.toml`,
  `.env.example`, `.gitignore`, all `data/` files, and
  `project_management/MASTER_PROJECT_PLAN.md` — confirmed at zero diff. No API key was
  created, read, requested, or used; no network call of any kind occurred; no `.env` file
  was created. Full suite re-confirmed unchanged at `1715 passed`. `audit_records/`
  confirmed to still contain only `.gitkeep`; no `exports/` directory exists; no real
  `.env` exists. Sprint 4 remains incomplete: packaging/dependency-consistency hardening
  and test-suite hardening remain future Sprint 4 work, not started by this stage. No
  stage after Stage 38 is completed.

## Sprint 4, Development Stage 39 — Packaging and Dependency Hardening

### Changed
- `requirements.txt` converted to bounded compatible version ranges for every declared
  package: `streamlit>=1.59,<2`, `pydantic>=2,<3`, `google-genai>=2,<3`,
  `httpx>=0.28,<1`, `python-dotenv>=1,<2`, `pytest>=8,<10`. Previously `streamlit`,
  `pandas`, and `pytest` were entirely unpinned while `pydantic` and `google-genai` were
  already range-pinned; every package now uses the same bounded-range convention, with no
  exact patch-version lock anywhere. `requirements.txt` remains the repository's sole
  dependency-installation mechanism; `pyproject.toml` was not touched and gained no
  `[project.dependencies]` table.
- The explicit `pandas` line was removed after verifying (repository-wide search across
  `app.py`, `config.py`, `src/`, and `tests/`) that no direct import or pandas-specific
  API usage exists anywhere, and confirming via local Streamlit package metadata that
  Streamlit itself declares `pandas` as one of its own dependencies — installation
  behaviour is unchanged, only the unused explicit declaration is gone.

### Added
- `httpx>=0.28,<1` added to `requirements.txt` as a sixth, genuine direct dependency.
  Discovered during Stage 39's required dependency inspection: `src/gemini_analyzer.py`
  directly imports `httpx` and directly references `httpx.TimeoutException`/
  `httpx.NetworkError` to classify Gemini transport failures, and
  `tests/test_gemini_analyzer.py` directly imports and directly uses `httpx.ReadTimeout`/
  `httpx.ConnectError` — real, direct usage that had been silently satisfied only through
  `google-genai`'s own transitive dependency declaration, with no guarantee in this
  repository's own dependency file. Flagged and explicitly approved before editing
  `requirements.txt`; the installed `httpx==0.28.1` satisfies the approved range.
- `.gitattributes` (new file) — the repository's first explicit line-ending policy:
  `* text=auto` as the default, explicit `eol=lf` for `.py`/`.md`/`.txt`/`.toml`/`.csv`/
  `.json`/`.yml`/`.yaml` text files, and explicit `binary` handling for
  `.png`/`.jpg`/`.jpeg`/`.gif`/`.ico`/`.pdf`/`.docx`. No repository-wide renormalization
  was run and no existing file was touched to normalize its line endings.

### Notes
- Packaging/dependency-only stage: no production file and no test file changed. Exactly
  five authorized files/paths touched (`requirements.txt`, new `.gitattributes`, and the
  three project-management tracking files); every other file confirmed at zero diff. No
  package was installed, removed, or upgraded in the environment — all version
  verification used only local `pip show` metadata. No Gemini API key or network call was
  used at any point. Python's declared minimum version (`pyproject.toml`'s
  `requires-python = ">=3.11"`) was not changed; no upper Python-version bound was added;
  no CI workflow was added. Integration suite re-confirmed unchanged at `12 passed`; full
  suite re-confirmed unchanged at `1715 passed`; the recurring external `google-genai`
  deprecation warning remains present and remains harmless. `audit_records/` confirmed to
  still contain only `.gitkeep`; no `exports/` directory exists; no real `.env` exists.
  Sprint 4 remains incomplete: test-suite hardening and CI remain future work, not
  addressed by this stage.

## Sprint 4, Development Stage 40 — Test-Suite Hardening and Adversarial Validation Coverage

### Fixed
- `tests/test_gemini_analyzer.py` and `tests/test_config.py`: the existing fresh-reimport
  tests (proving import-time side-effect freedom by popping their own module from
  `sys.modules` and reimporting it) previously left a different module object installed
  under the canonical name for the rest of the process, since nothing restored the
  original afterward. Both now wrap the pop/reimport in `try/finally`, restore
  `sys.modules[...]` to the exact module object captured at each file's own collection
  time, and assert that restoration explicitly. No existing assertion was weakened; the
  reimport itself is still genuine. Confirmed order-independent in both run orders
  (`105 passed` either way).
- `tests/test_app_approval.py`: `_audit_redirect_snippet()` and its three calling helpers
  (`_fresh_app`, `_unconserved_app`, `_app_test_with_fake_approve`) previously called
  `tempfile.mkdtemp(prefix="stage33_test_audit_")` on every invocation, leaking a real,
  never-cleaned-up directory on each of roughly 27 test runs — 928 such directories were
  confirmed to have accumulated in the OS temp folder from prior sessions. Replaced with
  pytest-managed `tmp_path`, threaded through every helper and calling test function;
  `import tempfile` removed entirely. Every existing Stage 33 assertion/scenario is
  preserved unchanged.

### Added
- `tests/test_app_approval.py`: `test_no_tempfile_mkdtemp_used_in_module_source` — an AST-
  based check confirming neither `tempfile` nor `mkdtemp` is referenced anywhere in the
  module source, guarding against the leak this stage fixed.
- `tests/test_validation.py`: 27 new adversarial/edge-case CSV tests (44 pre-existing →
  71 passed), satisfying the master plan's explicit Sprint 4 "adversarial/edge-case CSV
  inputs" requirement. Covers a leading UTF-8 BOM, quoted fields containing a comma / an
  embedded double quote / an embedded newline, CRLF line endings, blank lines in three
  positions (between rows, immediately after the header, and a trailing newline at EOF),
  whitespace-only required string fields, an unclosed quote, scientific notation for both
  a plain `Decimal` field and a quantized `Currency` field, a 28-significant-digit extreme
  Decimal value, negative monetary/count values, `NaN`/`Infinity`/`-Infinity`,
  formula-like strings in identifier/name fields, a mix of valid and invalid rows in one
  stream, and empty/header-only/whitespace-only full input. Every expected outcome was
  verified against the real `validate_campaign_csv`/`CampaignInput` interface via ad-hoc
  probe scripts before being written; no validation rule was reimplemented or invented.

### Notes
- Test-suite-only stage: no production file changed. Exactly four authorized test files
  touched (`tests/test_gemini_analyzer.py`, `tests/test_config.py`,
  `tests/test_app_approval.py`, `tests/test_validation.py`), plus the three
  project-management tracking files; every other file confirmed at zero diff. No existing
  test was deleted, skipped, xfailed, or collapsed. No production defect was found during
  the adversarial-CSV probing — the stop-on-defect policy was never triggered; formula-like
  strings in `campaign_id`/`campaign_name` are confirmed accepted at the validation layer
  by design, since formula-injection neutralization is exclusively a Stage 35 export-time
  concern. No dependency, Gemini API key, or network call was used at any point.
  Integration suite re-confirmed unchanged at `12 passed`; full suite grew from `1715
  passed` to `1743 passed` (27 new validation tests + 1 new app-approval test); the
  recurring external `google-genai` deprecation warning remains present and unsuppressed.
  `audit_records/` confirmed to still contain only `.gitkeep`; no `exports/` directory
  exists; no real `.env` exists; no unexpected temporary directory was created inside the
  repository. Sprint 4 remains incomplete: CI and a review of the human-in-the-loop
  boundary and audit-trail completeness remain future work, not addressed by this stage.
  No stage after Stage 40 has been started.

## Sprint 4, Development Stage 41 — Human-in-the-Loop, Audit, and Governance Completeness Review

### Fixed
- `docs/DECISION_RULES.md`: the "Pending" section's "Final recommendation" bullet
  described `RecommendationAction.HOLD` as an unresolved question, predating Stage 21's
  actual resolution — a staleness identified but left uncorrected (out of Stage 37's
  header-only scope) at Stage 37. Rewritten to state the resolution plainly, referencing
  Stage 21's own (already-correct) body section and `docs/ARCHITECTURE.md`'s HOLD summary.
  No enum member or production behaviour changed.
- `docs/ARCHITECTURE.md`, `docs/DECISION_RULES.md`, `docs/LIMITATIONS.md`: top-of-file
  status blockquotes, frozen at Stage-37-era language, understated completed Sprint 4
  progress (Stages 38–40 were already complete). Updated to reflect Stages 37–40 complete
  and Stage 41's own role, while continuing to state that Sprint 4 remains incomplete.

### Added
- `docs/ARCHITECTURE.md`: three narrow, source-verified clarifications following a
  governance completeness review of `src/pipeline.py`, `src/approval.py`, `src/audit.py`,
  `src/exports.py`, `src/explanations.py`, `src/gemini_analyzer.py`, the relevant sections
  of `app.py`, and the approval/audit/export/explanation/integration test modules — the
  Audit section now states that `recorded_at` must be timezone-aware and is normalized to
  UTC on construction (a naive value is rejected); the Human Approval section now states
  that `reviewer_name`/`note` are captured on `CampaignReallocationApproval` and travel
  unchanged into the same-click audit record; the Export section now states explicitly
  that both `APPROVED` and `REJECTED` audits are exportable identically and that
  `src/exports.py` can never trigger a Gemini call, recompute a recommendation, or mutate
  the audit it reads. Each addition documents existing, already-implemented behaviour;
  none is new production behaviour.

### Notes
- Documentation/governance-review-only stage: no production or test file changed. Exactly
  three `docs/` files touched (`docs/ARCHITECTURE.md`, `docs/DECISION_RULES.md`,
  `docs/LIMITATIONS.md`), plus the three project-management tracking files; every other
  file confirmed at zero diff. This stage implements no new feature — it verifies that the
  completed human-decision, audit-persistence, export, AI-isolation, and governance
  boundaries already accurately and consistently documented against source and tests, and
  corrects the one genuine staleness and three narrow gaps found. No CI workflow was
  added — its continued absence is recorded as optional future infrastructure, not a
  Sprint 4 blocker. No dependency, Gemini API key, or network call was used at any point.
  Integration suite re-confirmed unchanged at `12 passed`; full suite re-confirmed
  unchanged at `1743 passed` (the exact Stage 40 baseline, since no test file changed).
  `audit_records/` confirmed to still contain only `.gitkeep`; no `exports/` directory
  exists; no real `.env` exists. Sprint 4 remains incomplete: CI and Stage 42 (provisional
  final release verification and Sprint 4 closure) remain future work, not addressed by
  this stage. No stage after Stage 41 has been started.
