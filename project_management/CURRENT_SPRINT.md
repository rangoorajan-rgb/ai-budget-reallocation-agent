# Current Sprint

**Active sprint:** Sprint 1 — Development
**Status:** Active (Development Stages 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, and 20 complete)
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

## Development Stage 9 — Neutral Deterministic Pacing Interpretation (complete)

- [x] `src/constants.py` — added `PACING_LOWER_THRESHOLD = Decimal("0.90")` and
      `PACING_UPPER_THRESHOLD = Decimal("1.10")` (a symmetric ±10% on-pace tolerance
      around `1.00`). No other constant changed.
- [x] `src/pacing.py` (additions only — Stage 4's `CampaignPacing`/
      `calculate_campaign_pacing` unmodified) — `PacingStatus` enum (`UNDERSPENDING =
      "Under spending"`, `ON_PACE = "On pace"`, `OVERSPENDING = "Over spending"`,
      `NOT_AVAILABLE = "Not available"`) and `CampaignPacingClass` (frozen,
      `extra="forbid"`: `campaign_id`, `pacing_status`) and
      `classify_campaign_pacing(pacing: CampaignPacing) -> CampaignPacingClass`.
      `src/constants.py` (beyond the two new constants), `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/classification.py` unchanged.
- [x] `pacing_ratio` is the sole classification input (plus `campaign_id` for result
      identity) — `spend_variance`, `expected_spend`, `elapsed_fraction`,
      `elapsed_days`, `total_period_days`, `remaining_budget`, and
      `projected_end_of_period_spend` are never read; `CampaignInput`, `ReviewSetup`,
      `CampaignMetrics`, and every Stage 5–8 result are never read.
- [x] Exact precedence: `pacing_ratio is None` → `NOT_AVAILABLE`; `pacing_ratio <
      PACING_LOWER_THRESHOLD` → `UNDERSPENDING`; `PACING_LOWER_THRESHOLD <= pacing_ratio
      <= PACING_UPPER_THRESHOLD` → `ON_PACE` (closed, inclusive interval on both ends);
      otherwise → `OVERSPENDING`. `NOT_AVAILABLE` is a pacing-data state only — never
      `Confidence.NOT_ASSESSABLE`, `is_assessable=False`, `TrackingStatus.UNRELIABLE`,
      `RecommendationAction.HOLD`, a reason code, or an eligibility outcome. The upstream
      `None` cause (zero elapsed time vs. zero current budget) is never distinguished,
      and `pacing_ratio` is never recalculated.
- [x] Direct `Decimal` comparison only — no arithmetic, weighting, quantisation, or
      `float` conversion; `PACING_LOWER_THRESHOLD`/`PACING_UPPER_THRESHOLD` are both
      `Decimal`. `classify_campaign_pacing` never calls `classify_campaign_performance`,
      `classify_campaign_trend`, `classify_campaign_confidence`, or
      `assess_campaign_tracking` (or vice versa). Descriptive only — does not state
      whether overspending or underspending is desirable.
- [x] `tests/test_pacing_interpretation.py` — 33 tests, all passing. `tests/test_pacing.py`
      (Stage 4, 30 tests), `tests/test_classification.py` (Stage 5, 23 tests),
      `tests/test_trend_classification.py` (Stage 6, 29 tests),
      `tests/test_confidence_classification.py` (Stage 7, 32 tests), and
      `tests/test_tracking_assessment.py` (Stage 8, 30 tests) re-run and confirmed
      passing — no regression, no existing test file required modification, no
      approved exception needed this stage.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 10 — Deterministic Static Budget-Bound Calculation (complete)

- [x] `src/constraints.py` (populated for the first time — placeholder replaced) —
      `CampaignStaticBudgetRoom` (frozen, `extra="forbid"`: `campaign_id`,
      `room_to_static_maximum`, `room_to_static_minimum`) and
      `calculate_campaign_static_budget_room(campaign: CampaignInput) ->
      CampaignStaticBudgetRoom`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py`, `src/classification.py`
      unchanged.
- [x] Exact formulas: `room_to_static_maximum = maximum_budget - current_budget`;
      `room_to_static_minimum = current_budget - minimum_budget`. Both structurally
      guaranteed non-negative by `CampaignInput`'s already-validated `minimum_budget <=
      current_budget <= maximum_budget` invariant. No new validation, clamping, or
      default substitution. `Decimal("0.00")` is a valid outcome exactly at either
      bound, never replaced with `None` or a categorical status.
- [x] Static-bound terminology (`CampaignStaticBudgetRoom`,
      `calculate_campaign_static_budget_room`, `room_to_static_maximum`,
      `room_to_static_minimum`) deliberately distinguishes these facts from a future
      *effective* constraint. `campaign_max_change_percentage`,
      `ReviewSetup.default_max_change_percentage`, `DEFAULT_MAX_CHANGE_PERCENTAGE`,
      `is_protected`, `is_test_campaign`, and `test_budget_floor` are all never read —
      the percentage-limit mechanism, protection rules, and test-budget-floor
      enforcement all remain pending a later effective-constraint stage. Reporting
      `room_to_static_minimum` against `minimum_budget` for a test campaign (e.g. G003:
      `room_to_static_minimum = 1100.00` against `minimum_budget=100.00`, while
      `test_budget_floor=300.00`) is a static-bound fact only and does not authorise a
      reduction below the test floor.
- [x] Calculation runs inside an explicit `decimal.localcontext()` (`prec=28`,
      `ROUND_HALF_UP`), isolated from any mutated global `Decimal` context; no `float`,
      no re-quantisation, no rounding of the output (both results are already exact to
      two decimal places).
- [x] Independent of Stages 3–9 — no `ReviewSetup`, `CampaignMetrics`, `CampaignPacing`,
      `PerformanceBand`, `TrendDirection`, `Confidence`, `TrackingStatus`,
      `CampaignTrackingAssessment`, or `PacingStatus` import; no Stage 3–9 function
      called.
- [x] `tests/test_constraints.py` (populated for the first time — placeholder replaced)
      — 25 tests, all passing. `tests/test_models.py` (Stage 1), `tests/test_validation.py`
      (Stage 2), `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing — no
      regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 11 — Deterministic Applicable Change-Percentage Resolution (complete)

- [x] `src/constraints.py` (additions only — Stage 10's `CampaignStaticBudgetRoom`/
      `calculate_campaign_static_budget_room` unmodified) — `CampaignApplicableChangePercentage`
      (frozen, `extra="forbid"`: `campaign_id`, `applicable_max_change_percentage`) and
      `resolve_campaign_applicable_change_percentage(review: ReviewSetup, campaign:
      CampaignInput) -> CampaignApplicableChangePercentage`. `src/constants.py`,
      `src/models.py`, `src/validation.py`, `src/metrics.py`, `src/pacing.py`,
      `src/classification.py` unchanged.
- [x] Exact rule and precedence: `applicable_max_change_percentage =
      campaign.campaign_max_change_percentage if campaign.campaign_max_change_percentage
      is not None else review.default_max_change_percentage` — a non-`None` campaign
      override always wins; otherwise the review default applies. Explicit `is not None`
      check, never a truthiness-based fallback. The result is never `None`; no special
      zero handling exists or is needed (both source fields are `gt=0`).
      `DEFAULT_MAX_CHANGE_PERCENTAGE` is never imported or read — only the
      already-validated `review.default_max_change_percentage` is used.
- [x] Reads only `campaign.campaign_id`, `campaign.campaign_max_change_percentage`, and
      `review.default_max_change_percentage` — never `current_budget`,
      `minimum_budget`, `maximum_budget`, `room_to_static_maximum`,
      `room_to_static_minimum`, `is_protected`, `is_test_campaign`,
      `test_budget_floor`, `platform`, `kpi_type`, or any Stage 3–9 result. No
      arithmetic, quantisation, or rounding; no local `Decimal` context (none is
      required for conditional selection); unaffected by a mutated global `Decimal`
      context. Never calls `calculate_campaign_static_budget_room` or any Stage 3–9
      function.
- [x] `tests/test_constraints.py` extended (all 25 existing Stage 10 tests preserved
      unchanged) with 24 new Stage 11 tests — 49 tests total, all passing.
      `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
      `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing —
      no regression. **One approved exception:** `tests/test_constraints.py`'s
      pre-existing `test_module_does_not_import_out_of_scope_modules` AST check was
      narrowed (removing only `"ReviewSetup"` from its forbidden-import set) because it
      was written when `src/constraints.py` legitimately had no reason to import it —
      Stage 11 requires it, per your explicit approval; every other forbidden import
      (`src.classification`, `src.metrics`, `src.pacing`, `src.scoring`,
      `src.allocation`, `src.conservation`, `CampaignMetrics`, `CampaignPacing`,
      `PerformanceBand`, `TrendDirection`, `Confidence`, `TrackingStatus`,
      `CampaignTrackingAssessment`, `PacingStatus`, `RecommendationAction`,
      `ReasonCode`, and `DEFAULT_MAX_CHANGE_PERCENTAGE`) is unchanged and still
      enforced.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 12 — Deterministic Raw Percentage-Based Monetary Movement-Cap Calculation (complete)

- [x] `src/constraints.py` (additions only — Stage 10's `CampaignStaticBudgetRoom`/
      `calculate_campaign_static_budget_room` and Stage 11's
      `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`
      unmodified) — `CampaignRawPercentageMovementCap` (frozen, `extra="forbid"`:
      `campaign_id`, `raw_percentage_movement_cap`) and
      `calculate_campaign_raw_percentage_movement_cap(campaign: CampaignInput,
      applicable_percentage: CampaignApplicableChangePercentage) ->
      CampaignRawPercentageMovementCap`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py`, `src/classification.py`
      unchanged.
- [x] Exact formula: `raw_percentage_movement_cap = quantize(current_budget *
      applicable_max_change_percentage, CURRENCY_QUANTUM, ROUND_HALF_UP)` — a raw,
      informational fact only, not permission to move a budget. Requires
      `campaign.campaign_id == applicable_percentage.campaign_id`, raising
      `ValueError("campaign_id mismatch between campaign and applicable percentage")`
      otherwise, with no result returned. Consumes Stage 11's result directly — never
      accepts `ReviewSetup`, never reads `campaign.campaign_max_change_percentage` or
      `review.default_max_change_percentage`, never imports
      `DEFAULT_MAX_CHANGE_PERCENTAGE`, never re-resolves override/default precedence.
- [x] **Operand-derived Decimal precision policy** (found necessary during inspection,
      approved before implementation): `safe_precision = max(28,
      len(current_budget.as_tuple().digits) +
      len(applicable_max_change_percentage.as_tuple().digits) + 4)`, used only inside a
      local `decimal` context for the multiplication and final quantisation. A fixed
      `prec=28` context was empirically shown to incorrectly return
      `Decimal("...52910.71")` for an already-valid extreme `CampaignInput`
      (`current_budget=Decimal("99999999999999999999999999.99")`, 28 significant
      digits — the largest `Currency` can hold under the default global context) paired
      with a many-decimal-digit percentage
      (`Decimal("0.036020245307579938554529107051")`), via double rounding; the correct
      exact result is `Decimal("...52910.70")`. The operand-derived precision computes
      the multiplication exactly, leaving the explicit final `.quantize(...)` call as
      the sole rounding operation. No new maximum budget or percentage digit
      restriction was introduced; `CampaignInput`/`Currency` validation is unmodified.
      The global `Decimal` context is never mutated and is unaffected by the function
      call.
- [x] Independent of Stage 10 — never reads `minimum_budget`, `maximum_budget`,
      `room_to_static_maximum`, or `room_to_static_minimum`, never calls
      `calculate_campaign_static_budget_room`. Ignores `is_protected`,
      `is_test_campaign`, and `test_budget_floor`. No arithmetic, weighting, or
      `float` conversion beyond the single approved multiplication and quantisation.
- [x] `tests/test_constraints.py` extended (all 49 existing Stage 10/11 tests preserved
      unchanged) with 35 new Stage 12 tests — 84 tests total, all passing, including a
      dedicated extreme-value regression test asserting the exact correct result and
      explicitly asserting the incorrect fixed-precision-28 result is *not* returned.
      `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
      `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing —
      no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 13 — Deterministic Test-Floor Distance Calculation (complete)

- [x] `src/constraints.py` (additions only — Stage 10's `CampaignStaticBudgetRoom`/
      `calculate_campaign_static_budget_room`, Stage 11's
      `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
      and Stage 12's `CampaignRawPercentageMovementCap`/
      `calculate_campaign_raw_percentage_movement_cap` unmodified) —
      `CampaignTestFloorRoom` (frozen, `extra="forbid"`: `campaign_id`,
      `room_to_test_floor: Decimal | None`) and
      `calculate_campaign_test_floor_room(campaign: CampaignInput) ->
      CampaignTestFloorRoom`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py`, `src/classification.py`
      unchanged.
- [x] Exact formula: `room_to_test_floor = current_budget - test_budget_floor` for
      test campaigns (`is_test_campaign=True`); `None` for non-test campaigns — an
      explicit "not applicable" statement, never a fallback, never `Decimal("0.00")`,
      never an error. A valid non-test `CampaignInput` never raises. Reads only
      `campaign_id`, `is_test_campaign`, `current_budget`, `test_budget_floor` —
      never `minimum_budget`, `maximum_budget`, `is_protected`,
      `campaign_max_change_percentage`, `platform`, `kpi_type`, `ReviewSetup`, or any
      Stage 3–9/Stage 10–12 result.
- [x] Raw, informational fact only — explicitly not the effective floor, not an
      alternative or additional minimum, not permissible decrease, not an effective
      directional constraint, never combined with `minimum_budget`, Stage 10's static
      room, or Stage 12's raw percentage movement cap. This approval does not decide
      the eventual effective-floor precedence.
- [x] Calculated inside a fixed local `decimal` context (`prec=28`,
      `ROUND_HALF_UP`, matching Stage 10's established policy, not Stage 12's
      operand-derived policy — subtraction of two already-quantised `Currency`
      values never needs more significant digits than the larger operand already
      has). Neither operand nor the result is re-quantised; the exact two-decimal
      exponent is preserved. Confirmed safe for the largest value `Currency` can hold
      under the default global context (28 significant digits), with all
      significant whole-number digits preserved.
- [x] `tests/test_constraints.py` extended (all 84 existing Stage 10/11/12 tests
      preserved unchanged) with 35 new Stage 13 tests — 119 tests total, all passing.
      `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
      `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing —
      no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 14 — Deterministic Protection Constraint (complete)

- [x] `src/constraints.py` (additions only — Stage 10's `CampaignStaticBudgetRoom`/
      `calculate_campaign_static_budget_room`, Stage 11's
      `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
      Stage 12's `CampaignRawPercentageMovementCap`/
      `calculate_campaign_raw_percentage_movement_cap`, and Stage 13's
      `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room` unmodified) —
      `CampaignProtectionConstraint` (frozen, `extra="forbid"`: `campaign_id`,
      `decrease_blocked: bool`) and `resolve_campaign_protection_constraint(campaign:
      CampaignInput) -> CampaignProtectionConstraint`. `src/constants.py`,
      `src/models.py`, `src/validation.py`, `src/metrics.py`, `src/pacing.py`,
      `src/classification.py` unchanged.
- [x] Exact mapping: `decrease_blocked = campaign.is_protected` — `True` means only
      that protection prohibits a decrease (not eligibility, a recommendation, or an
      allocation decision); `False` means only that protection itself does not
      prohibit a decrease (not permission to reduce the campaign's budget). `False`
      is a meaningful result, never converted to `None`. Boolean representation
      approved specifically to avoid prematurely translating the frozen "must never
      be reduced" rule into a monetary room amount.
- [x] Reads only `campaign_id`, `is_protected` — never `current_budget`,
      `minimum_budget`, `maximum_budget`, `is_test_campaign`, `test_budget_floor`,
      `campaign_max_change_percentage`, `platform`, `kpi_type`, `ReviewSetup`, or any
      Stage 3–9/Stage 10–13 result. No `Decimal` import, no local context, no
      rounding, no quantisation, no float conversion — a plain boolean selection.
      Decrease-specific only; increase-side protection behaviour remains entirely
      unaddressed.
- [x] `tests/test_constraints.py` extended (all 119 existing Stage 10/11/12/13 tests
      preserved unchanged) with 28 new Stage 14 tests — 147 tests total, all passing.
      `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
      `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing —
      no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 15 — Deterministic Test-Aware Static Decrease Room (complete)

- [x] `src/constraints.py` (additions only — Stage 10's `CampaignStaticBudgetRoom`/
      `calculate_campaign_static_budget_room`, Stage 11's
      `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
      Stage 12's `CampaignRawPercentageMovementCap`/
      `calculate_campaign_raw_percentage_movement_cap`, Stage 13's
      `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, and Stage 14's
      `CampaignProtectionConstraint`/`resolve_campaign_protection_constraint`
      unmodified) — `CampaignTestAwareStaticDecreaseRoom` (frozen, `extra="forbid"`:
      `campaign_id`, `test_aware_static_decrease_room: Decimal`) and
      `resolve_campaign_test_aware_static_decrease_room(static_room:
      CampaignStaticBudgetRoom, test_floor_room: CampaignTestFloorRoom) ->
      CampaignTestAwareStaticDecreaseRoom`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py`, `src/classification.py`
      unchanged.
- [x] **First approved constraints-domain business precedence rule:**
      `test_budget_floor` is an additional retained-spend floor for test campaigns —
      the higher of `minimum_budget`/`test_budget_floor` controls, equivalently the
      smaller of the two already-calculated rooms:
      `test_aware_static_decrease_room = room_to_static_minimum` when
      `room_to_test_floor is None`; otherwise
      `min(room_to_static_minimum, room_to_test_floor)`. Mathematically equivalent to
      `max(minimum_budget, test_budget_floor)` via `c - max(a, b) = min(c-a, c-b)`.
      Raw constraint only — not permissible decrease, not an effective decrease
      limit, does not account for Stage 12's percentage cap or Stage 14's protection
      constraint.
- [x] Consumes Stage 10's and Stage 13's already-approved result objects directly —
      never accepts or reads `CampaignInput`, never calls
      `calculate_campaign_static_budget_room` or `calculate_campaign_test_floor_room`,
      never recalculates either room. Requires
      `static_room.campaign_id == test_floor_room.campaign_id`, raising exactly
      `ValueError("Campaign IDs must match when resolving test-aware static decrease
      room.")` otherwise, checked before any monetary result is resolved. No
      arithmetic — the selected `Decimal` operand is returned unchanged; no local
      context, quantisation, or rounding; ambient global `Decimal` precision cannot
      affect the result. Fully independent of Stages 11, 12, and 14 — never reads
      `applicable_max_change_percentage`, `raw_percentage_movement_cap`,
      `decrease_blocked`, or `is_protected`.
- [x] `tests/test_constraints.py` extended (all 147 existing Stage 10/11/12/13/14
      tests preserved unchanged) with 39 new Stage 15 tests — 186 tests total, all
      passing. `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage
      2), `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing —
      no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 16 — Deterministic Raw Increase Limit (complete)

- [x] `src/constraints.py` (additions only — Stage 10's `CampaignStaticBudgetRoom`/
      `calculate_campaign_static_budget_room`, Stage 11's
      `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
      Stage 12's `CampaignRawPercentageMovementCap`/
      `calculate_campaign_raw_percentage_movement_cap`, Stage 13's
      `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, Stage 14's
      `CampaignProtectionConstraint`/`resolve_campaign_protection_constraint`, and
      Stage 15's `CampaignTestAwareStaticDecreaseRoom`/
      `resolve_campaign_test_aware_static_decrease_room` unmodified) —
      `CampaignRawIncreaseLimit` (frozen, `extra="forbid"`: `campaign_id`,
      `raw_increase_limit: Decimal`) and `resolve_campaign_raw_increase_limit(static_room:
      CampaignStaticBudgetRoom, raw_cap: CampaignRawPercentageMovementCap) ->
      CampaignRawIncreaseLimit`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py`, `src/classification.py`
      unchanged.
- [x] **Approved business rule:** both upward constraints apply simultaneously —
      `room_to_static_maximum` prevents exceeding `maximum_budget`;
      `raw_percentage_movement_cap` limits the size of a change under the applicable
      percentage rule — so the smaller value is the binding limit:
      `raw_increase_limit = min(room_to_static_maximum, raw_percentage_movement_cap)`.
      Raw, increase-specific constraint only — not permission to increase a budget,
      not an effective increase, not eligibility, not a recommendation, and not a
      final movement amount.
- [x] Consumes Stage 10's and Stage 12's already-approved result objects directly —
      never accepts or reads `CampaignInput`/`ReviewSetup`, never calls
      `calculate_campaign_static_budget_room` or
      `calculate_campaign_raw_percentage_movement_cap`, never recalculates either
      fact. Requires `static_room.campaign_id == raw_cap.campaign_id`, raising
      exactly `ValueError("Campaign IDs must match when resolving raw increase
      limit.")` otherwise, checked before any Decimal selection. No arithmetic — the
      selected `Decimal` operand is returned unchanged; no local context,
      quantisation, or rounding; ambient global `Decimal` precision cannot affect the
      result. Fully independent of Stages 11, 13, 14, and 15 — never reads
      `applicable_max_change_percentage`, `room_to_test_floor`, `decrease_blocked`,
      or `test_aware_static_decrease_room`. Protected status has no approved
      increase-side effect; test-floor rules have no bearing on this result.
- [x] `tests/test_constraints.py` extended (all 186 existing Stage 10/11/12/13/14/15
      tests preserved unchanged) with 40 new Stage 16 tests — 226 tests total, all
      passing. `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage
      2), `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing —
      no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 17 — Deterministic Raw Decrease Limit (complete)

- [x] `src/constraints.py` (additions only — Stage 10's `CampaignStaticBudgetRoom`/
      `calculate_campaign_static_budget_room`, Stage 11's
      `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
      Stage 12's `CampaignRawPercentageMovementCap`/
      `calculate_campaign_raw_percentage_movement_cap`, Stage 13's
      `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, Stage 14's
      `CampaignProtectionConstraint`/`resolve_campaign_protection_constraint`, Stage
      15's `CampaignTestAwareStaticDecreaseRoom`/
      `resolve_campaign_test_aware_static_decrease_room`, and Stage 16's
      `CampaignRawIncreaseLimit`/`resolve_campaign_raw_increase_limit` unmodified) —
      `CampaignRawDecreaseLimit` (frozen, `extra="forbid"`: `campaign_id`,
      `raw_decrease_limit: Decimal`) and `resolve_campaign_raw_decrease_limit(decrease_room:
      CampaignTestAwareStaticDecreaseRoom, raw_cap: CampaignRawPercentageMovementCap) ->
      CampaignRawDecreaseLimit`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py`, `src/classification.py`
      unchanged.
- [x] **Approved business rule:** both decrease-side constraints apply
      simultaneously — `test_aware_static_decrease_room` preserves the approved
      minimum-budget/test-floor constraint (Stage 15); `raw_percentage_movement_cap`
      limits the size of a change under the applicable percentage rule (Stage 12) —
      so the smaller value is the binding limit:
      `raw_decrease_limit = min(test_aware_static_decrease_room,
      raw_percentage_movement_cap)`. Raw, decrease-specific constraint only — not
      permission to decrease a budget, not an effective decrease, not eligibility,
      not a recommendation, and not a final movement amount. A protected campaign
      still receives its neutral Stage 17 raw result; Stage 14's protection
      constraint is not applied here.
- [x] Consumes Stage 15's and Stage 12's already-approved result objects directly —
      never accepts or reads `CampaignInput`/`ReviewSetup`, never calls
      `resolve_campaign_test_aware_static_decrease_room` or
      `calculate_campaign_raw_percentage_movement_cap`, never recalculates either
      fact. Requires `decrease_room.campaign_id == raw_cap.campaign_id`, raising
      exactly `ValueError("Campaign IDs must match when resolving raw decrease
      limit.")` otherwise, checked before any Decimal selection. No arithmetic — the
      selected `Decimal` operand is returned unchanged; no local context,
      quantisation, or rounding; ambient global `Decimal` precision cannot affect the
      result. Fully independent of Stages 10, 11, 13, 14, and 16 — never reads
      `room_to_static_maximum`, `room_to_static_minimum`,
      `applicable_max_change_percentage`, `room_to_test_floor`, `decrease_blocked`,
      `is_protected`, or `raw_increase_limit`; never reopens `minimum_budget`,
      `test_budget_floor`, `is_test_campaign`, or Stage 15's stricter-floor
      precedence. Test-campaign status affects Stage 17 only through Stage 15's
      already-resolved value; protected campaigns receive the same neutral result as
      otherwise identical unprotected campaigns.
- [x] `tests/test_constraints.py` extended (all 226 existing Stage 10/11/12/13/14/15/16
      tests preserved unchanged) with 46 new Stage 17 tests — 272 tests total, all
      passing. `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage
      2), `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing —
      no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 18 — Protection-Adjusted Effective Decrease Limit (complete)

- [x] `src/constraints.py` (additions only — Stage 10's `CampaignStaticBudgetRoom`/
      `calculate_campaign_static_budget_room`, Stage 11's
      `CampaignApplicableChangePercentage`/`resolve_campaign_applicable_change_percentage`,
      Stage 12's `CampaignRawPercentageMovementCap`/
      `calculate_campaign_raw_percentage_movement_cap`, Stage 13's
      `CampaignTestFloorRoom`/`calculate_campaign_test_floor_room`, Stage 14's
      `CampaignProtectionConstraint`/`resolve_campaign_protection_constraint`, Stage
      15's `CampaignTestAwareStaticDecreaseRoom`/
      `resolve_campaign_test_aware_static_decrease_room`, Stage 16's
      `CampaignRawIncreaseLimit`/`resolve_campaign_raw_increase_limit`, and Stage
      17's `CampaignRawDecreaseLimit`/`resolve_campaign_raw_decrease_limit`
      unmodified) — `CampaignEffectiveDecreaseLimit` (frozen, `extra="forbid"`:
      `campaign_id`, `effective_decrease_limit: Decimal`) and
      `resolve_campaign_effective_decrease_limit(raw_decrease:
      CampaignRawDecreaseLimit, protection: CampaignProtectionConstraint) ->
      CampaignEffectiveDecreaseLimit`. `src/constants.py`, `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py`, `src/classification.py`
      unchanged.
- [x] **Approved business rule:** `decrease_blocked=True` means protection
      prohibits reducing the campaign, so `effective_decrease_limit =
      Decimal("0.00")` — a deliberate, computed effective constraint, never missing
      data, regardless of whether the raw value was positive, zero, or extreme.
      `decrease_blocked=False` means protection adds no further restriction, so
      `raw_decrease_limit` passes through unchanged. Still not eligibility, a
      recommendation, a final movement amount, an allocation, or a decision to
      decrease the campaign — a campaign with `effective_decrease_limit ==
      Decimal("0.00")` may still later be eligible for `MAINTAIN` or `INCREASE`.
      `Decimal("0.00")` is used instead of `None` because protection-triggered zero
      is a computed, deliberate fact, not a non-applicability signal.
- [x] Consumes Stage 17's and Stage 14's already-approved result objects directly —
      never accepts or reads `CampaignInput`/`ReviewSetup`, never calls
      `resolve_campaign_raw_decrease_limit` or
      `resolve_campaign_protection_constraint`, never recalculates either fact.
      Requires `raw_decrease.campaign_id == protection.campaign_id`, raising
      exactly `ValueError("Campaign IDs must match when resolving effective
      decrease limit.")` otherwise, checked before reading `decrease_blocked` for
      selection or resolving any Decimal result. No arithmetic — the unprotected
      branch returns the selected `Decimal` operand unchanged, the protected branch
      constructs the literal `Decimal("0.00")`; no local context, quantisation, or
      rounding; ambient global `Decimal` precision cannot affect either branch.
      Fully independent of Stages 10, 11, 12, 13, 15, and 16 — never reads
      `is_protected`, `current_budget`, `minimum_budget`, `maximum_budget`,
      `test_budget_floor`, `is_test_campaign`, `applicable_max_change_percentage`,
      `room_to_static_minimum`, `room_to_test_floor`,
      `test_aware_static_decrease_room`, or `raw_percentage_movement_cap`. Does
      **not** create `CampaignEffectiveIncreaseLimit`, `effective_increase_limit`,
      or a combined effective-directional result — no approved constraint remains
      to transform Stage 16's raw increase limit, and protection has no approved
      increase-side effect, so `CampaignRawIncreaseLimit` remains the authoritative
      increase-side constraint.
- [x] `tests/test_constraints.py` extended (all 272 existing Stage 10/11/12/13/14/15/16/17
      tests preserved unchanged) with 50 new Stage 18 tests — 322 tests total, all
      passing. `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage
      2), `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing —
      no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 19 — Deterministic Campaign Action Availability (complete)

- [x] `src/availability.py` (new dedicated module — not added to
      `src/constraints.py`, `src/classification.py`, or `src/scoring.py`, since
      action availability spans campaign status, tracking assessability, and both
      directional monetary constraints simultaneously, and is not purely a
      monetary constraint, a descriptive classification, or a score) —
      `CampaignActionAvailability` (frozen, `extra="forbid"`: `campaign_id`,
      `increase_available: bool`, `maintain_available: bool`,
      `reduce_available: bool`) and `resolve_campaign_action_availability(campaign:
      CampaignInput, tracking: CampaignTrackingAssessment, raw_increase:
      CampaignRawIncreaseLimit, effective_decrease: CampaignEffectiveDecreaseLimit)
      -> CampaignActionAvailability`. Uses the term **"action availability,"**
      never "eligibility." `src/constraints.py`, `src/classification.py`,
      `src/constants.py`, `src/models.py`, `src/validation.py`, `src/metrics.py`,
      `src/pacing.py` unchanged.
- [x] **Approved concept boundary:** availability means an action is not prevented
      by campaign status, tracking-based assessability, or the relevant approved
      monetary capacity — it does not mean the action is advisable. Positive
      capacity means only that a direction is mechanically possible, never a
      recommendation. Does not decide which available action is suitable, which
      action should be recommended, `HOLD`, scoring, priority, ranking,
      `ReasonCode`, or allocation.
- [x] **Exact mapping:** `is_active = campaign.status is CampaignStatus.ACTIVE`;
      `increase_available = is_active and tracking.is_assessable and
      raw_increase.raw_increase_limit > Decimal("0.00")`; `maintain_available =
      is_active`; `reduce_available = is_active and tracking.is_assessable and
      effective_decrease.effective_decrease_limit > Decimal("0.00")`. Paused →
      all three `False`, always one result object, never an error, never `HOLD`,
      never a reason code. Unassessable Active → `increase_available=False`,
      `maintain_available=True`, `reduce_available=False`. `hold_available` is
      excluded entirely — `HOLD`'s exact trigger remains undecided, reserved for
      a later review/deferral or recommendation stage.
- [x] Consumes Stage 8's, Stage 16's, and Stage 18's already-approved result
      objects directly, plus `CampaignInput` for identity/status (no
      status-wrapper model created — mirrors the Stage 14 precedent of consuming
      `CampaignInput` directly) — never calls `assess_campaign_tracking`,
      `resolve_campaign_raw_increase_limit`,
      `resolve_campaign_effective_decrease_limit`, or any other Stage 1–18
      production function. Requires all four `campaign_id` values to match,
      raising exactly `ValueError("Campaign IDs must match when resolving action
      availability.")` otherwise, checked before any status/assessability/Decimal
      evaluation. No arithmetic — enum-identity comparison, Boolean conjunction,
      and `Decimal` comparison against `Decimal("0.00")` only; no local context,
      quantisation, or rounding; ambient global `Decimal` precision cannot affect
      the result. Never reads `tracking_status`, `is_protected`,
      `decrease_blocked`, `is_test_campaign`, `test_budget_floor`,
      `minimum_budget`, `maximum_budget`, `PerformanceBand`, `TrendDirection`,
      `Confidence`, `PacingStatus`, or `BusinessPriority`. Outputs no
      `ReasonCode` and selects no `RecommendationAction.HOLD`.
- [x] `tests/test_availability.py` (new dedicated test file — `tests/test_constraints.py`
      unchanged at 322 tests) — 61 new Stage 19 tests, all passing.
      `tests/test_models.py` (Stage 1), `tests/test_validation.py` (Stage 2),
      `tests/test_metrics.py` (Stage 3), `tests/test_pacing.py` (Stage 4),
      `tests/test_classification.py` (Stage 5), `tests/test_trend_classification.py`
      (Stage 6), `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed passing
      — no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Development Stage 20 — Deterministic Conservative Diagonal-Only Campaign Action Suitability (complete)

- [x] `src/suitability.py` (new dedicated module — not added to
      `src/classification.py`, `src/constraints.py`, `src/availability.py`, or
      `src/scoring.py`, since suitability combines classification-domain
      performance, classification-domain trend, and availability-domain action
      gates, and is not a raw classification, a monetary constraint,
      availability, or numeric scoring; `src/scoring.py` remains unchanged,
      reserved for later numeric prioritisation-scoring work) — `Suitability`
      (`str, Enum`: `SUITABLE = "Suitable"`, `NEUTRAL = "Neutral"`,
      `UNSUITABLE = "Unsuitable"`, `NOT_APPLICABLE = "Not Applicable"`, purely
      categorical, no ordering), `CampaignActionSuitability` (frozen,
      `extra="forbid"`: `campaign_id`, `increase_suitability: Suitability`,
      `maintain_suitability: Suitability`, `reduce_suitability: Suitability`),
      and `resolve_campaign_action_suitability(performance:
      CampaignPerformanceClass, trend: CampaignTrendClass, availability:
      CampaignActionAvailability) -> CampaignActionSuitability`. Uses ordinal
      **"suitability,"** never a numeric score. `src/classification.py`,
      `src/constraints.py`, `src/availability.py`, `src/scoring.py`,
      `src/constants.py`, `src/models.py`, `src/validation.py`,
      `src/metrics.py`, `src/pacing.py` unchanged.
- [x] **Approved concept boundary:** availability answers "can this action be
      taken mechanically and operationally?"; suitability answers "do the
      approved performance and trend classifications provide a clear
      directional signal supporting this available action?" Suitability does
      not mean recommendation — `SUITABLE` is not automatically selected,
      `NEUTRAL` is not automatically rejected, `UNSUITABLE` is not a final
      prohibition. Does not select `RecommendationAction`, select `HOLD`,
      produce `ReasonCode`, produce a numeric score, rank campaigns, or apply
      `Confidence`, `PacingStatus`, or `BusinessPriority`.
- [x] **Approved conservative diagonal-only rule:** only the three cells where
      `PerformanceBand` and `TrendDirection` clearly agree
      (`ABOVE_TARGET`+`IMPROVING`, `ON_TARGET`+`STABLE`,
      `BELOW_TARGET`+`DECLINING`) produce a directional `SUITABLE`/`UNSUITABLE`
      result; all six conflicting/mixed combinations resolve to `NEUTRAL` for
      every direction — deliberately avoiding a performance-vs-trend
      precedence decision. Implemented as a module-level immutable
      `MappingProxyType` containing exactly all nine
      `PerformanceBand`×`TrendDirection` keys, never mutated at runtime, no
      enum-declaration-order dependency.
- [x] **Availability-first override:** applied independently per direction
      after the base-table lookup — an unavailable direction is always
      `Suitability.NOT_APPLICABLE`, overriding the base table; never `None`,
      numeric zero, or `UNSUITABLE`. For an Active but unassessable campaign,
      Stage 19 already makes `INCREASE`/`REDUCE` unavailable, so Stage 20
      returns `NOT_APPLICABLE` for both while `MAINTAIN` still receives its
      base-table result — Stage 20 never decides `MAINTAIN` versus `HOLD`.
- [x] Consumes Stage 5's, Stage 6's, and Stage 19's already-approved result
      objects directly (never calls `classify_campaign_performance`,
      `classify_campaign_trend`, or `resolve_campaign_action_availability`, and
      never accepts `CampaignInput`/`ReviewSetup`/`CampaignTrackingAssessment`)
      — no combined-assessment data-carrier model was created. Requires all
      three `campaign_id` values to match, raising exactly
      `ValueError("Campaign IDs must match when resolving action
      suitability.")` otherwise, checked before any rule-table lookup or
      availability evaluation. No `Decimal`, arithmetic, or numeric weight is
      used anywhere — only enum-identity comparison, a fixed mapping lookup,
      and Boolean gating. Excludes `Confidence` (including any
      `Confidence.NOT_ASSESSABLE` relationship), `PacingStatus`, and
      `BusinessPriority` entirely — none is read. Outputs no `ReasonCode` and
      selects no `RecommendationAction`/`HOLD`.
- [x] `tests/test_suitability.py` (new dedicated test file — `tests/test_availability.py`
      unchanged at 61 tests, `tests/test_constraints.py` unchanged at 322
      tests) — 67 new Stage 20 tests, all passing. `tests/test_models.py`
      (Stage 1), `tests/test_validation.py` (Stage 2), `tests/test_metrics.py`
      (Stage 3), `tests/test_pacing.py` (Stage 4), `tests/test_classification.py`
      (Stage 5), `tests/test_trend_classification.py` (Stage 6),
      `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed
      passing — no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 20 (and not yet started)

- Resolution of the six conflicting/mixed performance-trend cells (deliberately
  left `NEUTRAL` rather than assigning a performance-vs-trend precedence).
- `RecommendationAction` selection, `HOLD` (exact trigger still undecided).
- `ReasonCode` assignment.
- `Confidence`/`Confidence.NOT_ASSESSABLE`, `PacingStatus`, `BusinessPriority`
  effects on suitability, scoring, or allocation.
- Effective increase limit (`CampaignRawIncreaseLimit` remains the authoritative
  increase-side constraint; no approved rule exists to transform it).
- Combined campaign assessment (performance + trend + confidence + tracking + pacing
  status), `Confidence.NOT_ASSESSABLE` ownership and trigger.
- Numeric prioritisation scoring, ranking/prioritisation, allocation, conservation.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Next Stage

Stage 21 (not started, scope not yet frozen): requires its own dependency and
decision-readiness inspection before being frozen, not file-list order.
`RecommendationAction` selection is the leading candidate, consuming
`CampaignActionSuitability` (Stage 20) to move toward a final action per campaign
— but selecting among `SUITABLE`/`NEUTRAL`/`UNSUITABLE` results, and deciding
`HOLD`'s exact trigger, both remain open business decisions requiring their own
approval. Whether `Confidence`, `PacingStatus`, or `BusinessPriority` first need
a dedicated readiness/scoring stage before `RecommendationAction` can be
finalised is not yet resolved. Per-campaign scoring may remain single-campaign;
only normalisation, ranking/prioritisation, and allocation genuinely require
comparing multiple campaigns simultaneously (corrected at Stage 19 completion).
The still-deferred combined campaign-assessment question (performance + trend +
confidence + tracking + pacing) remains a live but not clearly necessary
candidate on its own, as noted since the Stage 11 inspection.
