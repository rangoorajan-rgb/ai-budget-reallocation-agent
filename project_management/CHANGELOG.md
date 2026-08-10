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
