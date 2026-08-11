# Current Sprint

**Active sprint:** Sprint 1 — Development
**Status:** Active (Development Stages 1, 2, 3, 4, 5, 6, 7, and 8 complete)
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

## Development Stage 7 — Neutral Deterministic Conversion-Volume Confidence Classification (complete)

- [x] `src/classification.py` (additions only — Stages 5/6's `PerformanceBand`/
      `CampaignPerformanceClass`/`classify_campaign_performance` and `TrendDirection`/
      `CampaignTrendClass`/`classify_campaign_trend` unmodified) —
      `CampaignConfidenceClass` (frozen, `extra="forbid"`: `campaign_id`, `confidence`,
      reusing the existing `Confidence` enum) and `classify_campaign_confidence(campaign:
      CampaignInput) -> CampaignConfidenceClass`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py` unchanged.
- [x] Classifies `conversions_28d` only (Policy B — the fuller, more stable window,
      avoiding double-counting the nested `conversions_7d` period), using the existing
      frozen `MINIMUM_CONVERSIONS`/`HIGH_CONFIDENCE_CONVERSIONS`: `>=
      HIGH_CONFIDENCE_CONVERSIONS` → `HIGH`; `>= MINIMUM_CONVERSIONS` → `MEDIUM`;
      otherwise (including zero) → `LOW`. Reaching either threshold enters the higher
      band, consistent with Stages 5–6.
- [x] `Confidence.NOT_ASSESSABLE` is never assigned by Stage 7 — a deliberate,
      documented scope boundary, not an inferred rule from zero/low conversions,
      tracking status, pacing, or protected/test status.
- [x] Direct integer comparison only — no arithmetic, weighting, quantisation, or
      `Decimal`/`float` conversion; `conversions_7d` is never read, summed, averaged, or
      combined with `conversions_28d`.
- [x] Depends only on `CampaignInput.campaign_id`/`conversions_28d` — no
      `CampaignMetrics`, `CampaignPacing`, `ReviewSetup`, `CampaignPerformanceClass`,
      `CampaignTrendClass`, `TrackingStatus`, `RecommendationAction`, or `ReasonCode`; no
      platform/KPI branching.
- [x] `tests/test_confidence_classification.py` — 32 tests, all passing.
      `tests/test_classification.py` (Stage 5, 23 tests) and
      `tests/test_trend_classification.py` (Stage 6, 29 tests) re-run and confirmed
      passing. **One approved exception:** both files' pre-existing
      `test_classification_module_does_not_import_out_of_scope_modules_or_enums` AST
      checks were narrowed (removing `CampaignInput`/`Confidence`/`src.models` from
      their forbidden-import sets only) because those checks were written when
      `src/classification.py` legitimately had no reason to import either — Stage 7
      requires both, per your explicit approval; every other forbidden import in both
      tests (`CampaignPacing`, `ReviewSetup`, `RecommendationAction`, `ReasonCode`, and
      the remaining out-of-scope modules) is unchanged and still enforced.
      `tests/test_models.py`, `tests/test_validation.py`, `tests/test_metrics.py`, and
      `tests/test_pacing.py` unchanged and still passing.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 8 — Deterministic Tracking-Based Assessability (complete)

- [x] `src/classification.py` (additions only — Stages 5/6/7's `PerformanceBand`/
      `CampaignPerformanceClass`/`classify_campaign_performance`, `TrendDirection`/
      `CampaignTrendClass`/`classify_campaign_trend`, and `CampaignConfidenceClass`/
      `classify_campaign_confidence` unmodified) — `CampaignTrackingAssessment` (frozen,
      `extra="forbid"`: `campaign_id`, `tracking_status`, `is_assessable`, reusing the
      existing `TrackingStatus` enum) and `assess_campaign_tracking(campaign:
      CampaignInput) -> CampaignTrackingAssessment`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py` unchanged.
- [x] Exact mapping: `is_assessable = campaign.tracking_status is not
      TrackingStatus.UNRELIABLE` — `HEALTHY` and `WARNING` both `True`, `UNRELIABLE` the
      sole `False` condition. `WARNING` represents a concern requiring later caution,
      not unusable evidence; the original `tracking_status` is preserved in the result
      (never collapsed into `HEALTHY`) for later `ReasonCode`/recommendation logic.
- [x] `Confidence.NOT_ASSESSABLE` is never assigned or read by Stage 8; Stage 7 continues
      returning only `HIGH`/`MEDIUM`/`LOW` regardless of `tracking_status`.
      `CampaignConfidenceClass`, `CampaignPerformanceClass`, and `CampaignTrendClass` are
      unmodified.
- [x] Direct enum comparison only — no arithmetic, weighting, quantisation, or
      `Decimal`/`float` conversion; `conversions_7d`/`conversions_28d`, `CampaignMetrics`,
      `CampaignPacing`, `platform`, `kpi_type`, and protected/test status are never read.
- [x] `tests/test_tracking_assessment.py` — 30 tests, all passing.
      `tests/test_classification.py` (Stage 5, 23 tests), `tests/test_trend_classification.py`
      (Stage 6, 29 tests), and `tests/test_confidence_classification.py` (Stage 7, 32
      tests) re-run and confirmed passing. **One approved exception:**
      `tests/test_confidence_classification.py`'s pre-existing
      `test_classification_module_does_not_import_out_of_scope_modules_or_enums` AST
      check was narrowed (removing only `TrackingStatus` from its forbidden-import set)
      because it was written when `src/classification.py` legitimately had no reason to
      import it — Stage 8 requires it, per your explicit approval; every other forbidden
      import (`CampaignPacing`, `ReviewSetup`, `RecommendationAction`, `ReasonCode`, and
      the out-of-scope `src.*` modules) is unchanged and still enforced.
      `tests/test_models.py`, `tests/test_validation.py`, `tests/test_metrics.py`, and
      `tests/test_pacing.py` unchanged and still passing.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 8 (and not yet started)

- Combined confidence/tracking assessment, `Confidence.NOT_ASSESSABLE` ownership and
  trigger, pacing interpretation.
- Protected/test campaign constraints, eligibility, scoring, final `RecommendationAction`
  assignment, `ReasonCode` assignment, allocation, conservation.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Next Stage

Stage 9 (not started, scope not yet frozen): requires its own dependency and
decision-readiness inspection before being frozen, not file-list order. Candidates
include a combined confidence/tracking assessment stage (which would need to decide
`Confidence.NOT_ASSESSABLE` ownership while preserving Stage 7's and Stage 8's
independent results) and pacing interpretation (currently the least-evidenced candidate,
with zero frozen pacing-specific numerical constants).
