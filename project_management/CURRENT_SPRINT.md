# Current Sprint

**Active sprint:** Sprint 1 — Development
**Status:** Active (Development Stages 1, 2, 3, 4, 5, and 6 complete)
**Reference:** See [MASTER_PROJECT_PLAN.md](MASTER_PROJECT_PLAN.md) for the full frozen plan.

The repository foundation (directory structure, root project files, placeholder modules,
and initial project-management documentation) is complete and is not re-tracked here.

## Development Stage 1 — Enumerations, Frozen Constants, Core Input Models, CSV Schema (complete)

- [x] `src/constants.py` — frozen `str, Enum` enumerations: `Platform`, `KPIType`,
      `CampaignStatus`, `TrackingStatus`, `BusinessPriority`, `RecommendationAction`,
      `Confidence`, `ReviewStatus`, `ValidationSeverity`, `ReasonCode`. Plus nine frozen
      numerical constants (`DEFAULT_MAX_CHANGE_PERCENTAGE`, `TREND_THRESHOLD`,
      `SEVEN_DAY_WEIGHT`, `TWENTY_EIGHT_DAY_WEIGHT`, `INCREASE_THRESHOLD`,
      `MAINTAIN_THRESHOLD`, `MINIMUM_CONVERSIONS`, `HIGH_CONFIDENCE_CONVERSIONS`,
      `CURRENCY_QUANTUM`). No decision, calculation, or allocation logic.
- [x] `src/models.py` — exactly two input-focused Pydantic v2 models: `ReviewSetup` and
      `CampaignInput`, enforcing only safe, model-level type and structural rules. No
      validation workflow, metrics, pacing, classification, constraints, scoring,
      allocation, or conservation logic.
- [x] Exact 20-field CSV schema for `CampaignInput`, fixed column order, approved
      human-readable enum values.
- [x] `data/campaign_template.csv` (header only) and `data/sample_campaigns.csv` (4 rows).
- [x] `tests/test_models.py` — 92 tests, all passing.
- [x] `docs/DATA_DICTIONARY.md` and `docs/DECISION_RULES.md` updated.

## Development Stage 2 — Deterministic Validation Reporting (complete)

- [x] `src/constants.py` — added `ValidationCode` enum (`INVALID_REVIEW_FIELD`,
      `EMPTY_FILE`, `INVALID_HEADER`, `NO_CAMPAIGN_ROWS`, `MALFORMED_ROW`,
      `INVALID_CAMPAIGN_FIELD`, `DUPLICATE_CAMPAIGN_ID`). `src/models.py` left unchanged.
- [x] `src/validation.py` — `ValidationIssue` and `ValidationReport` models;
      `validate_review_setup(data)` and `validate_campaign_csv(stream)`. Both functions
      only invoke `ReviewSetup`/`CampaignInput` and translate their
      `pydantic.ValidationError` output into `ValidationIssue` records — no structural
      rule is re-implemented outside `src/models.py`.
- [x] CSV header must exactly match `CampaignInput.model_fields` order (derived at
      runtime, never hand-typed); any mismatch is one file-level `INVALID_HEADER` issue
      with no row validation afterward.
- [x] Row-level parsing: physical one-based line numbers (header = line 1), malformed row
      shapes rejected as `MALFORMED_ROW`, blank optional cells (`test_budget_floor`,
      `campaign_max_change_percentage`) converted to `None`, every other cell passed
      through unmodified to `CampaignInput` for authoritative validation.
- [x] Duplicate `campaign_id` detection among structurally valid rows only — every
      occurrence flagged and excluded, case-sensitive, compared after model trimming.
- [x] All Stage 2 issues are `ValidationSeverity.ERROR`; `warning_count` remains
      generically derived but is `0` for every currently authorised outcome.
- [x] `tests/test_validation.py` — 44 tests, all passing. `tests/test_models.py` (Stage 1)
      unchanged and still passing.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 3 — Deterministic Metric Calculations (complete)

- [x] `src/metrics.py` — `CampaignMetrics` (frozen, `extra="forbid"`: `campaign_id`,
      `performance_ratio_7d`, `performance_ratio_28d`, `weighted_performance_ratio`,
      `trend_delta`) and `calculate_campaign_metrics(campaign: CampaignInput) ->
      CampaignMetrics`. `src/constants.py`, `src/models.py`, `src/validation.py`
      unchanged.
- [x] Direction-normalised performance ratios: `kpi_actual / kpi_target` for `ROAS`,
      `kpi_target / kpi_actual` for `CPA` — uniformly, `> 1` means better than target for
      both KPI types, `< 1` means worse. Platform-independent.
- [x] Weighted performance ratio using the existing frozen `SEVEN_DAY_WEIGHT` /
      `TWENTY_EIGHT_DAY_WEIGHT`; relative trend delta between the two normalised ratios.
      Neither `INCREASE_THRESHOLD`/`MAINTAIN_THRESHOLD` nor `TREND_THRESHOLD` is applied
      in this stage — Stage 3 calculates facts only, no classification.
- [x] All calculations run inside an explicit `decimal.localcontext()` (`prec=28`,
      `ROUND_HALF_UP`), isolated from any mutated global `Decimal` context; no
      quantisation, no `float`, no `CURRENCY_QUANTUM`.
- [x] No conversion-volume confidence (`MINIMUM_CONVERSIONS`/`HIGH_CONFIDENCE_CONVERSIONS`
      not used); no pacing, classification, constraints, scoring, allocation,
      conservation, Gemini, Streamlit, approval, audit, or export logic.
- [x] `tests/test_metrics.py` — 28 tests, all passing. `tests/test_models.py` (Stage 1)
      and `tests/test_validation.py` (Stage 2) unchanged and still passing.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 4 — Deterministic Campaign Pacing (complete)

- [x] `src/pacing.py` — `CampaignPacing` (frozen, `extra="forbid"`: `campaign_id`,
      `elapsed_days`, `total_period_days`, `elapsed_fraction`, `expected_spend`,
      `spend_variance`, `pacing_ratio`, `remaining_budget`,
      `projected_end_of_period_spend`) and `calculate_campaign_pacing(review:
      ReviewSetup, campaign: CampaignInput) -> CampaignPacing`. `src/constants.py`,
      `src/models.py`, `src/validation.py`, `src/metrics.py` unchanged.
- [x] Inclusive date counting (`total_period_days = (period_end - period_start).days +
      1`); `elapsed_days` clamped to `[0, total_period_days]` since `review_date` has no
      frozen relationship to the period boundaries.
- [x] Linear expected-spend assumption; `pacing_ratio` and `projected_end_of_period_spend`
      computed from the unquantised internal expected spend so penny rounding doesn't
      distort them; public monetary fields quantised to `CURRENCY_QUANTUM`.
  `pacing_ratio`/`projected_end_of_period_spend` are `None` only on their exact
      zero-denominator condition — never a `0/0` sentinel.
- [x] All calculations run inside an explicit `decimal.localcontext()` (`prec=28`,
      `ROUND_HALF_UP`), isolated from any mutated global `Decimal` context; no `float`.
- [x] Independent of Stage 3 — no `CampaignMetrics` import, no `platform`/`kpi_type`/KPI
      value/performance-threshold/trend-threshold/conversion-volume-constant usage.
- [x] No pacing status, label, classification, confidence, recommendation, reason code,
      score, eligibility, or allocation logic.
- [x] `tests/test_pacing.py` — 30 tests, all passing. `tests/test_models.py` (Stage 1),
      `tests/test_validation.py` (Stage 2), and `tests/test_metrics.py` (Stage 3)
      unchanged and still passing.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 5 — Neutral Deterministic Performance Classification (complete)

- [x] `src/classification.py` — `PerformanceBand` enum (`ABOVE_TARGET`, `ON_TARGET`,
      `BELOW_TARGET`; deliberately distinct from `RecommendationAction`) and
      `CampaignPerformanceClass` (frozen, `extra="forbid"`: `campaign_id`,
      `performance_band`) and `classify_campaign_performance(metrics: CampaignMetrics)
      -> CampaignPerformanceClass`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py` unchanged.
- [x] Classifies `weighted_performance_ratio` only, using the existing frozen
      `INCREASE_THRESHOLD`/`MAINTAIN_THRESHOLD`: `>= INCREASE_THRESHOLD` →
      `ABOVE_TARGET`; `>= MAINTAIN_THRESHOLD` (and `< INCREASE_THRESHOLD`) →
      `ON_TARGET`; otherwise `BELOW_TARGET`. Each threshold belongs to the higher band.
- [x] Direct `Decimal` comparison only — no arithmetic, quantisation, `float`
      conversion, or local `decimal` context.
- [x] Depends only on `CampaignMetrics.campaign_id`/`weighted_performance_ratio` — no
      `CampaignInput`, `CampaignPacing`, or `ReviewSetup`; no `platform`/`kpi_type`
      branching (Stage 3 already normalised CPA/ROAS direction).
- [x] No trend classification, conversion-volume confidence, tracking interpretation,
      `NOT_ASSESSABLE` behaviour, `RecommendationAction`, `Confidence`, `ReasonCode`,
      constraints, scoring, allocation, conservation, or later-stage logic.
- [x] `tests/test_classification.py` — 23 tests, all passing. `tests/test_models.py`
      (Stage 1), `tests/test_validation.py` (Stage 2), `tests/test_metrics.py` (Stage 3),
      and `tests/test_pacing.py` (Stage 4) unchanged and still passing.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 6 — Neutral Deterministic Trend Classification (complete)

- [x] `src/classification.py` (additions only — Stage 5's `PerformanceBand`/
      `CampaignPerformanceClass`/`classify_campaign_performance` unmodified) —
      `TrendDirection` enum (`IMPROVING`, `STABLE`, `DECLINING`) and
      `CampaignTrendClass` (frozen, `extra="forbid"`: `campaign_id`, `trend_direction`)
      and `classify_campaign_trend(metrics: CampaignMetrics) -> CampaignTrendClass`.
      `src/constants.py`, `src/models.py`, `src/validation.py`, `src/metrics.py`,
      `src/pacing.py` unchanged.
- [x] Classifies `trend_delta` only, using the existing frozen `TREND_THRESHOLD`:
      `>= TREND_THRESHOLD` → `IMPROVING`; `<= TREND_THRESHOLD.copy_negate()` →
      `DECLINING`; otherwise `STABLE`. Reaching either threshold magnitude enters the
      directional band, consistent with Stage 5's threshold-entry policy. Negative
      boundary built via `.copy_negate()` — no new constant, no arithmetic on it.
- [x] Direct `Decimal` comparison only — no arithmetic, quantisation, `float`
      conversion, or local `decimal` context; `trend_delta` itself is never touched.
- [x] Depends only on `CampaignMetrics.campaign_id`/`trend_delta` — no `CampaignInput`,
      `CampaignPacing`, `ReviewSetup`, `CampaignPerformanceClass`, or `PerformanceBand`;
      no `platform`/`kpi_type` branching; independent of Stage 5's classification.
- [x] No confidence, tracking interpretation, pacing interpretation, combined
      performance-and-trend judgement, `RecommendationAction`, `Confidence`,
      `ReasonCode`, constraints, scoring, allocation, conservation, or later-stage logic.
- [x] `tests/test_trend_classification.py` — 29 tests, all passing.
      `tests/test_classification.py` (Stage 5) re-run unchanged and still passing (23
      tests) — Stage 5 behaviour confirmed intact. `tests/test_models.py` (Stage 1),
      `tests/test_validation.py` (Stage 2), `tests/test_metrics.py` (Stage 3), and
      `tests/test_pacing.py` (Stage 4) unchanged and still passing.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 6 (and not yet started)

- Conversion-volume confidence (including conversion-window choice), tracking-status
  interpretation, `NOT_ASSESSABLE` behaviour, pacing interpretation.
- Combined campaign judgements (trend + performance + confidence + tracking + pacing).
- Protected/test campaign constraints, eligibility, scoring, final `RecommendationAction`
  assignment, `ReasonCode` assignment, allocation, conservation.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Next Stage

Stage 7 (not started, scope not yet frozen): candidates include conversion-volume
confidence and tracking-status interpretation — each has unresolved formula/boundary
questions of its own (see `DECISIONS.md`) and requires its own dependency and
decision-readiness inspection before being frozen, not file-list order.
