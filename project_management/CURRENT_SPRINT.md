# Current Sprint

**Active sprint:** Sprint 4 — Hardening and Documentation (not yet started)
**Status:** Sprint 2 — Deterministic Core Engine is complete (Development Stages 1–27).
**Sprint 3 — Explanation, Approval, and Interface is complete** (Development Stages
28 through 36). Stage 36 delivered the final end-to-end integration test, exercising the
complete upload → validate → assess → recommend → lock → explain → approve/reject →
audit → export flow together through real Streamlit `AppTest` widget interaction for the
first time, with zero real Gemini/network calls and zero real audit/export artifacts left
in the repository. Verified baseline: `1715 passed` (1703 Stage 1–35 regression, after
retiring four now-obsolete "test_integration.py stays empty" guard assertions per explicit
approval — see Stage 36 below — + 12 Stage 36 integration tests in
`tests/test_integration.py`). All frozen Sprint 3 exit criteria (`MASTER_PROJECT_PLAN.md`)
are satisfied. Sprint 4 — Hardening and Documentation is next and has not yet started.
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

## Development Stage 21 — Deterministic Ordered Campaign Recommendation-Action Selection (complete)

- [x] `src/recommendation.py` (new dedicated module — not added to
      `src/suitability.py`, `src/availability.py`, `src/scoring.py`,
      `src/classification.py`, or `src/constraints.py`, since Stage 21
      selects a recommendation outcome, a responsibility separate from
      classification, constraints, availability, suitability, scoring, and
      allocation) — `CampaignRecommendation` (frozen, `extra="forbid"`:
      `campaign_id`, `recommendation_action: RecommendationAction`) and
      `resolve_campaign_recommendation_action(campaign: CampaignInput,
      suitability: CampaignActionSuitability, tracking:
      CampaignTrackingAssessment) -> CampaignRecommendation`. Reuses the
      existing `RecommendationAction` enum unchanged — no second action
      enum, no numeric ordering or weights. `RecommendationAction` selection
      is a **provisional direction only** — no monetary amount is produced.
      `src/suitability.py`, `src/availability.py`, `src/scoring.py`,
      `src/classification.py`, `src/constraints.py`, `src/constants.py`,
      `src/models.py`, `src/validation.py`, `src/metrics.py`,
      `src/pacing.py` unchanged.
- [x] **Approved HOLD-versus-MAINTAIN meaning:** `MAINTAIN` means the
      campaign was eligible for automated assessment, no available action
      had a uniquely stronger directional suitability, and keeping the
      budget unchanged is the selected recommendation — an assessed
      no-change decision. `HOLD` means the engine must not make an
      automated directional budget recommendation for this review — because
      the campaign is paused, its tracking is unassessable, its suitability
      input is ambiguous, or no valid fallback action is available. `HOLD`
      is a review/deferral outcome; `MAINTAIN` is an assessed no-change
      recommendation.
- [x] **Approved exact ordered policy**, applied after campaign-ID
      validation: (1) Paused override — `campaign.status is
      CampaignStatus.PAUSED` → `HOLD`, overriding all suitability, read
      explicitly from `CampaignInput.status`, never inferred from
      suitability shape; (2) tracking-assessability override — `not
      tracking.is_assessable` → `HOLD`, overriding all suitability,
      `WARNING` remains assessable per Stage 8's frozen rule; (3)
      unique-`SUITABLE` selection — exactly one field `SUITABLE` → that
      action; (4) multiple-`SUITABLE` ambiguity — more than one field
      `SUITABLE` → `HOLD`, with no fixed precedence, no first-field
      selection, no `MAINTAIN` default, and no error; (5) conservative
      `MAINTAIN` fallback — no `SUITABLE`, `maintain_suitability is
      Suitability.NEUTRAL` → `MAINTAIN`, regardless of
      `increase_suitability`/`reduce_suitability`'s own values; (6) final
      `HOLD` fallback — no `SUITABLE`, `maintain_suitability` is
      `UNSUITABLE` or `NOT_APPLICABLE` → `HOLD`. A `Suitability.NOT_APPLICABLE`
      value is never selected as an action.
- [x] Consumes Stage 20's and Stage 8's already-approved result objects
      directly (never calls `resolve_campaign_action_suitability`,
      `assess_campaign_tracking`, `resolve_campaign_action_availability`, or
      any other Stage 1–20 production function) plus `CampaignInput`
      directly for explicit status — `CampaignActionAvailability` is not
      accepted separately, since Stage 20 has already applied availability
      through `NOT_APPLICABLE`. Requires all three `campaign_id` values to
      match, raising exactly `ValueError("Campaign IDs must match when
      resolving recommendation action.")` otherwise, checked before any
      status/assessability/suitability evaluation. Never reads
      `is_protected`, `decrease_blocked`, `is_test_campaign`,
      `test_budget_floor`, or `tracking_status`. Excludes `Confidence`,
      `PacingStatus`, and `BusinessPriority` entirely. Outputs no
      `ReasonCode`.
- [x] `tests/test_recommendation.py` (new dedicated test file —
      `tests/test_suitability.py` unchanged at 67 tests,
      `tests/test_availability.py` unchanged at 61 tests,
      `tests/test_constraints.py` unchanged at 322 tests) — 84 new Stage 21
      tests, all passing. `tests/test_models.py` (Stage 1),
      `tests/test_validation.py` (Stage 2), `tests/test_metrics.py` (Stage
      3), `tests/test_pacing.py` (Stage 4), `tests/test_classification.py`
      (Stage 5), `tests/test_trend_classification.py` (Stage 6),
      `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed
      passing — no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 21 (and not yet started)

- `ReasonCode` assignment (deferred to Stage 22).
- `Confidence`/`Confidence.NOT_ASSESSABLE`, `PacingStatus`, `BusinessPriority`
  effects on action selection, scoring, or allocation.
- Effective increase limit (`CampaignRawIncreaseLimit` remains the authoritative
  increase-side constraint; no approved rule exists to transform it).
- Combined campaign assessment (performance + trend + confidence + tracking + pacing
  status), `Confidence.NOT_ASSESSABLE` ownership and trigger.
- Numeric prioritisation scoring, ranking/prioritisation, allocation, conservation.
- Any monetary amount associated with `RecommendationAction` (Stage 21 selects
  only a provisional direction).
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Development Stage 22 — Deterministic Campaign Recommendation Reasons (complete)

- [x] `src/reasons.py` (new dedicated module — not added to
      `src/recommendation.py`, `src/suitability.py`, `src/availability.py`,
      `src/classification.py`, `src/constraints.py`, or `src/scoring.py`,
      since Stage 22 explains an already-selected action, a responsibility
      separate from selecting it) — `CampaignRecommendationReason` (frozen,
      `extra="forbid"`: `campaign_id`, `reason_codes:
      tuple[ReasonCode, ...]`) and `resolve_campaign_recommendation_reason(
      recommendation: CampaignRecommendation, campaign: CampaignInput,
      suitability: CampaignActionSuitability, tracking:
      CampaignTrackingAssessment, performance: CampaignPerformanceClass,
      trend: CampaignTrendClass) -> CampaignRecommendationReason`. Does not
      duplicate `recommendation_action` on the result. `src/recommendation.py`,
      `src/suitability.py`, `src/availability.py`, `src/scoring.py`,
      `src/classification.py`, `src/constraints.py`, `src/constants.py`
      (including the existing `ReasonCode` enum, unmodified), `src/models.py`,
      `src/validation.py`, `src/metrics.py`, `src/pacing.py` unchanged.
- [x] **Approved HOLD precedence**, mirroring Stage 21's exact rule order:
      Paused alone → `(PAUSED_CAMPAIGN,)`, remaining the sole reason even
      when tracking is also unassessable (Stage 21's own short-circuit logic
      never reaches the assessability check once Paused has already
      resolved `HOLD`); otherwise unassessable → `(TRACKING_UNRELIABLE,)`;
      otherwise (multiple-`SUITABLE` ambiguity or no valid `MAINTAIN`
      fallback) → `(HELD_FOR_MANUAL_REVIEW,)`. Never used for a non-HOLD
      action, since `MAINTAIN` is itself an assessed, confident decision,
      not a deferral.
- [x] **Approved INCREASE/MAINTAIN/REDUCE mapping**: two fixed, immutable
      lookup tables applied to `performance.performance_band`/
      `trend.trend_direction` — `ABOVE_TARGET`→`ABOVE_TARGET_STRONG`,
      `ON_TARGET`→`NEAR_TARGET`, `BELOW_TARGET`→no performance reason (no
      approved severity classification exists to choose between
      `BELOW_TARGET_MODERATE` and `BELOW_TARGET_SEVERE`);
      `IMPROVING`/`STABLE`/`DECLINING`→`RECENT_TREND_IMPROVING`/`STABLE`/
      `DECLINING` unconditionally; performance reason (when available)
      precedes trend reason. Reproduces exactly the seven approved
      `MAINTAIN` cells plus the two cells reachable only via a Stage 19
      availability block on an otherwise diagonal-`SUITABLE` direction,
      using the identical already-approved mapping — not a new invented
      rule.
- [x] Consumes Stage 21's, Stage 20's, Stage 8's, Stage 5's, and Stage 6's
      already-approved result objects directly (never calls
      `resolve_campaign_recommendation_action` or any other Stage 1–21
      production function). Requires all six `campaign_id` values to match,
      raising exactly `ValueError("Campaign IDs must match when resolving
      recommendation reasons.")` otherwise, checked before any reason is
      resolved. Reads exactly the fourteen authorised fields. Never reads
      raw metrics, monetary constraint results, `Confidence`,
      `PacingStatus`, `tracking_status`, `is_protected`,
      `is_test_campaign`, `test_budget_floor`, or `BusinessPriority`.
- [x] **Approved reason-code scope**: exactly eight existing `ReasonCode`
      members (`PAUSED_CAMPAIGN`, `TRACKING_UNRELIABLE`,
      `HELD_FOR_MANUAL_REVIEW`, `ABOVE_TARGET_STRONG`, `NEAR_TARGET`,
      `RECENT_TREND_IMPROVING`, `RECENT_TREND_STABLE`,
      `RECENT_TREND_DECLINING`) — no new enum member added, no severity
      threshold invented. `TRACKING_WARNING`,
      `INSUFFICIENT_CONVERSION_VOLUME`, `PROTECTED_FROM_REDUCTION`,
      `BELOW_TARGET_MODERATE`, `BELOW_TARGET_SEVERE`,
      `STRONG_LONG_TERM_RECENT_DECLINE`, `CAMPAIGN_CAP_REACHED`,
      `CAMPAIGN_FLOOR_REACHED`, `TEST_BUDGET_FLOOR_APPLIED`,
      `MAX_CHANGE_LIMIT_APPLIED`, `NO_ELIGIBLE_RECIPIENT`, and
      `ACCOUNT_RESERVE_REQUIRED` are never emitted.
- [x] `tests/test_reasons.py` (new dedicated test file —
      `tests/test_recommendation.py` unchanged at 84 tests,
      `tests/test_suitability.py` unchanged at 67 tests,
      `tests/test_availability.py` unchanged at 61 tests,
      `tests/test_constraints.py` unchanged at 322 tests) — 69 new Stage 22
      tests, all passing. `tests/test_models.py` (Stage 1),
      `tests/test_validation.py` (Stage 2), `tests/test_metrics.py` (Stage
      3), `tests/test_pacing.py` (Stage 4), `tests/test_classification.py`
      (Stage 5), `tests/test_trend_classification.py` (Stage 6),
      `tests/test_confidence_classification.py` (Stage 7),
      `tests/test_tracking_assessment.py` (Stage 8), and
      `tests/test_pacing_interpretation.py` (Stage 9) re-run and confirmed
      passing — no regression, no existing test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 22 (and not yet started)

- The remaining twelve `ReasonCode` members' trigger conditions:
  `BELOW_TARGET_MODERATE`/`BELOW_TARGET_SEVERE`/`STRONG_LONG_TERM_RECENT_DECLINE`
  (pending an approved performance-severity classification),
  `CAMPAIGN_CAP_REACHED`/`CAMPAIGN_FLOOR_REACHED`/`TEST_BUDGET_FLOOR_APPLIED`/
  `MAX_CHANGE_LIMIT_APPLIED` (pending preserved constraint binding-source
  identity), `NO_ELIGIBLE_RECIPIENT`/`ACCOUNT_RESERVE_REQUIRED` (pending a
  later allocation/conservation stage), and
  `INSUFFICIENT_CONVERSION_VOLUME`/`TRACKING_WARNING`/`PROTECTED_FROM_REDUCTION`
  (intentionally and permanently excluded from action-reason scope).
- `Confidence`/`Confidence.NOT_ASSESSABLE`, `PacingStatus`, `BusinessPriority`
  effects on action selection, scoring, or allocation.
- Numeric prioritisation scoring, ranking/prioritisation, allocation, conservation.
- Any monetary amount associated with `RecommendationAction`.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Development Stage 23 — Deterministic Campaign Reallocation Priority Scoring (complete)

- [x] `src/scoring.py` (Sprint 1 placeholder pair filled in for the first
      time — not a newly created module, unlike Stages 19–22) —
      `CampaignReallocationPriorityScore` (frozen, `extra="forbid"`:
      `campaign_id`, `confidence_component: int`,
      `business_priority_component: int`,
      `reallocation_priority_score: int`, each numeric field constrained to
      `0..100`, total model-validated to equal the sum of the two
      components) and
      `calculate_campaign_reallocation_priority_score(recommendation:
      CampaignRecommendation, campaign: CampaignInput, confidence:
      CampaignConfidenceClass) -> CampaignReallocationPriorityScore`. Does
      not duplicate `recommendation_action` on the result.
      `src/recommendation.py`, `src/reasons.py`, `src/suitability.py`,
      `src/availability.py`, `src/constraints.py`, `src/classification.py`,
      `src/constants.py` (no enum added or changed), `src/models.py`
      unchanged.
- [x] **Approved business meaning**: the score represents the relative
      priority with which an already-selected *directional* recommendation
      should be considered during later cross-campaign ranking. A higher
      score means a stronger candidate only within the same direction —
      `INCREASE` scores compared only with other `INCREASE` scores,
      `REDUCE` scores only with other `REDUCE` scores; direction remains
      solely and authoritatively carried by
      `CampaignRecommendation.recommendation_action`, never re-encoded
      through sign or magnitude.
- [x] **Approved non-directional rule**: `HOLD`/`MAINTAIN` unconditionally
      produce `(0, 0, 0)`, without inspecting or applying the confidence or
      business-priority mappings.
- [x] **Approved `Confidence.NOT_ASSESSABLE` override**: an `INCREASE`/
      `REDUCE` recommendation paired with `NOT_ASSESSABLE` also produces
      `(0, 0, 0)` — a scoring-only override, no exception, no change to the
      existing recommendation.
- [x] **Approved exact mappings** (fixed, immutable `MappingProxyType`,
      independent of enum declaration order): confidence — `HIGH`→60,
      `MEDIUM`→40, `LOW`→20; business priority for `INCREASE` — `HIGH`→40,
      `MEDIUM`→20, `STANDARD`→0; business priority for `REDUCE` —
      `STANDARD`→40, `MEDIUM`→20, `HIGH`→0.
      `reallocation_priority_score = confidence_component +
      business_priority_component`, always a member of `{0, 20, 40, 60, 80,
      100}`.
- [x] Consumes Stage 21's already-approved `CampaignRecommendation` and
      Stage 7's already-approved `CampaignConfidenceClass` directly (never
      calls `resolve_campaign_recommendation_action`,
      `classify_campaign_confidence`, or any other Stage 1–22 production
      function). Requires all three `campaign_id` values to match, raising
      exactly `ValueError("Campaign IDs must match when calculating
      reallocation priority score.")` otherwise, checked before any action,
      confidence, or priority value is read. Reads exactly the six
      authorised fields. Never reads `PerformanceBand`, `TrendDirection`,
      `PacingStatus`, `ReasonCode`, raw metrics, monetary constraint
      results, protection, test-campaign status, or tracking status.
- [x] Plain Python `int` throughout — never `float`/`Decimal`; no rounding,
      quantisation, or ambient `Decimal` context; no multiplication or
      division; no negative value or value above `100`; tie-breaking
      deferred entirely to the later ranking stage. Completely
      single-campaign — no other campaign's data is read, compared, or
      required.
- [x] `tests/test_scoring.py` (Sprint 1 placeholder filled in for the first
      time) — 81 new Stage 23 tests, all passing.
      `tests/test_reasons.py` unchanged at 69 tests,
      `tests/test_recommendation.py` unchanged at 84 tests,
      `tests/test_suitability.py` unchanged at 67 tests,
      `tests/test_availability.py` unchanged at 61 tests,
      `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
      (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
      re-run and confirmed passing — no regression, no existing test file
      required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 23 (and not yet started)

- Cross-campaign ranking/prioritisation — sorting, normalising, or
  comparing `CampaignReallocationPriorityScore` results across campaigns
  (the first genuinely cross-campaign stage).
- Tie-breaking among equal scores.
- Any monetary recommendation amount, allocation, or conservation.
- `PacingStatus` effects on scoring or ranking (no approved
  direction-specific policy exists).
- The remaining twelve `ReasonCode` members' trigger conditions (see Stage
  22's Explicitly-Out-of-Scope list above).
- `Confidence.NOT_ASSESSABLE` ownership/trigger and the combined
  confidence/tracking/pacing assessment question.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Development Stage 24 — Deterministic Cross-Campaign Reallocation Ranking (complete)

- [x] `src/ranking.py` (new dedicated module, the first genuinely
      cross-campaign responsibility in this repository — not added to
      `src/scoring.py`, `src/recommendation.py`, `src/reasons.py`, or
      `src/allocation.py`, since ranking already-scored campaigns across a
      portfolio is a responsibility separate from single-campaign scoring
      and from the later monetary allocation decision) —
      `RankedCampaignPriority` (frozen, `extra="forbid"`: `campaign_id`,
      `rank: int` `>= 1`, `reallocation_priority_score: int` `1..100` —
      does not carry `RecommendationAction`; direction is represented
      structurally by tuple membership), `CampaignReallocationRanking`
      (frozen, `extra="forbid"`: `increase_rankings:
      tuple[RankedCampaignPriority, ...]`, `reduce_rankings:
      tuple[RankedCampaignPriority, ...]`, either or both legitimately
      empty), and `rank_campaign_reallocation_priorities(recommendations:
      tuple[CampaignRecommendation, ...], scores:
      tuple[CampaignReallocationPriorityScore, ...]) ->
      CampaignReallocationRanking`. `src/scoring.py`, `src/recommendation.py`,
      `src/reasons.py`, `src/allocation.py`, `src/conservation.py`,
      `src/constants.py` (no enum added or changed) unchanged.
- [x] **Approved direction separation**: `INCREASE` and `REDUCE`
      candidates are never compared against each other; the first-ranked
      campaign in each direction may both hold rank `1` with no
      relationship between them; no global combined rank exists; no
      campaign ever crosses direction.
- [x] **Approved eligible population**: only `INCREASE`/`REDUCE` paired
      with a strictly positive score is ranked; `MAINTAIN`/`HOLD` are
      always excluded regardless of score; a zero-scored directional
      recommendation (reachable via Stage 23's `NOT_ASSESSABLE` override)
      is also excluded — no output record, no reason code, no error, no
      mutation of the excluded campaign's recommendation or score, and no
      excluded-campaign collection is created.
- [x] **Approved matching policy**: `recommendations` and `scores` are
      matched exclusively by `campaign_id` value equality, never by tuple
      position (`zip` never used, AST-verified). Validation completes
      fully before any filtering, sorting, or rank assignment (AST-verified
      order): a repeated ID within `recommendations` raises exactly
      `ValueError("Recommendation campaign IDs must be unique when
      ranking reallocation priorities.")`; a repeated ID within `scores`
      raises exactly `ValueError("Score campaign IDs must be unique when
      ranking reallocation priorities.")`; a mismatched ID set raises
      exactly `ValueError("Recommendation and score campaign IDs must
      match when ranking reallocation priorities.")`. Both tuples empty
      returns a valid empty result, not an error.
- [x] **Approved sorting and dense-ranking policy**: within each
      direction, sort by `reallocation_priority_score` descending, then
      `campaign_id` ascending solely for deterministic tied-record
      serialization — `campaign_id` never affects the assigned rank and
      is never a business-priority key. Ranks are dense, start at `1`,
      plain `int`; equal scores share the same rank with no gap
      (`100, 80, 80, 60` → `1, 2, 2, 3`; all equal → `1, 1, 1`). No
      component already reflected in the Stage 23 total, and no other
      field (input position, platform, budget, performance, trend,
      pacing, monetary capacity), is ever used as a sort key.
- [x] **Approved no-normalisation rule**: Stage 23's score is used
      completely unchanged — no percentage, percentile, portfolio-relative
      transform, min-max normalisation, z-score, or direction-relative
      transformation is ever computed.
- [x] Consumes Stage 21's and Stage 23's already-approved result objects
      directly (never calls `resolve_campaign_recommendation_action`,
      `calculate_campaign_reallocation_priority_score`, or any other Stage
      1–23 production function). Reads exactly the four authorised fields.
      Never reads `confidence_component`, `business_priority_component`,
      any campaign-input field, or any
      performance/trend/pacing/confidence/suitability/availability/
      tracking/reason/monetary field. Never imports, reads, or infers any
      raw/effective monetary constraint result, binding-constraint
      identity, monetary recommendation amount, donor/recipient matching,
      partial allocation, or conservation.
- [x] Neither input tuple nor any contained model is ever mutated or
      sorted in place; every output object is newly constructed; identical
      serialized output regardless of input order (confirmed by test).
- [x] `tests/test_ranking.py` (new dedicated test file) — 69 new Stage 24
      tests, all passing. `tests/test_scoring.py` unchanged at 81 tests,
      `tests/test_reasons.py` unchanged at 69 tests,
      `tests/test_recommendation.py` unchanged at 84 tests,
      `tests/test_suitability.py` unchanged at 67 tests,
      `tests/test_availability.py` unchanged at 61 tests,
      `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
      (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
      re-run and confirmed passing — no regression, no existing test file
      required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 24 (and not yet started)

- Any monetary recommendation amount, allocation, or conservation.
- Donor/recipient matching or partial allocation of available funds.
- `PacingStatus` effects on scoring or ranking (no approved
  direction-specific policy exists).
- The remaining twelve `ReasonCode` members' trigger conditions (see Stage
  22's Explicitly-Out-of-Scope list above).
- `Confidence.NOT_ASSESSABLE` ownership/trigger and the combined
  confidence/tracking/pacing assessment question.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Development Stage 25 — Deterministic Cross-Campaign Budget Allocation (complete)

- [x] `src/allocation.py` (Sprint 1 placeholder pair filled in for the
      first time — not a newly created module, mirroring Stage 23's
      pattern; no separate monetary recommendation-amount stage was
      created, per the accepted post-Stage-24 boundary decision) —
      `CampaignAllocatedAmount` (frozen, `extra="forbid"`: `campaign_id`,
      `allocated_amount: Currency` constrained `>= 0` — never carries
      direction, rank, score, or capacity; direction is structural tuple
      membership, never a sign), `CampaignReallocationAllocation` (frozen,
      `extra="forbid"`: `increase_allocations:
      tuple[CampaignAllocatedAmount, ...]`, `decrease_allocations:
      tuple[CampaignAllocatedAmount, ...]`, either legitimately empty),
      and `allocate_campaign_reallocation(ranking:
      CampaignReallocationRanking, increase_limits:
      tuple[CampaignRawIncreaseLimit, ...], decrease_limits:
      tuple[CampaignEffectiveDecreaseLimit, ...]) ->
      CampaignReallocationAllocation`. `src/ranking.py`, `src/scoring.py`,
      `src/recommendation.py`, `src/reasons.py`, `src/constraints.py`,
      `src/conservation.py`, `src/constants.py` (no enum added or
      changed), `src/models.py` unchanged.
- [x] **Approved reserve exclusion**: `ReviewSetup.initial_account_reserve`
      is never accepted, read, consumed, reduced, or returned —
      authoritative meaning *"Budget held back from reallocation"* treats
      it as protected. `ReasonCode.ACCOUNT_RESERVE_REQUIRED` remains
      unassigned. The only funding source is the sum of
      `effective_decrease_limit` across Stage 24's `reduce_rankings`.
- [x] **Approved two-phase strict dense-rank waterfall**: Phase 1 funds
      `increase_rankings` by ascending dense rank against total available
      supply (full-tier funding while supply covers it, largest-remainder
      proportional split on the first tier it cannot fully cover, then
      zero for every lower rank); Phase 2 draws the exact Phase 1 total
      from `reduce_rankings` by the identical waterfall, always exhausting
      exactly since Phase 1's total can never exceed total supply. A
      partially funded tier, on either side, is a valid, non-error
      outcome, as are both insufficient and excess supply.
- [x] **Approved largest-remainder currency method**: exact proportional
      shares at operand-derived local precision, floored to
      `CURRENCY_QUANTUM` via `ROUND_DOWN`; the whole-penny shortfall
      distributed by fractional-remainder descending, `campaign_id`
      ascending breaking only an *exact* remainder tie — a narrow,
      explicitly scoped exception to "campaign ID is a serialization aid
      only," never used to order recipients against donors or to
      influence which tier is funded. Never adds a penny above a
      campaign's own capacity. An all-zero-capacity tier allocates zero to
      every campaign without division.
- [x] Consumes Stage 24's, Stage 16's, and Stage 18's already-approved
      result objects directly (never calls
      `rank_campaign_reallocation_priorities`,
      `calculate_campaign_reallocation_priority_score`,
      `resolve_campaign_recommendation_action`, or any other Stage 1–24
      production function). Matches `increase_limits`/`decrease_limits`
      to the rankings exclusively by `campaign_id` value — never `zip`.
      Requires uniqueness within each limit collection and a matching
      direction-appropriate limit for every ranked campaign, raising
      exactly `ValueError("Increase-limit campaign IDs must be unique
      when allocating reallocation.")`, `ValueError("Decrease-limit
      campaign IDs must be unique when allocating reallocation.")`,
      `ValueError("Every ranked increase campaign must have a matching
      increase limit.")`, or `ValueError("Every ranked decrease campaign
      must have a matching decrease limit.")` otherwise, checked before
      any allocation arithmetic. Extra, unranked limit records are
      accepted and ignored. Stage 24's own guarantees (uniqueness,
      direction separation, rank correctness, ordering) are trusted, never
      recalculated. Reads exactly the authorised fields; never reads
      `reallocation_priority_score`, `ReviewSetup`, `CampaignInput`,
      `CampaignRecommendation`, `CampaignRecommendationReason`, or
      `ReasonCode`.
- [x] Plain `Decimal` throughout — never `float`; every arithmetic
      operation, including simple sums and penny apportionment, runs
      inside an explicitly-scoped `localcontext`, immune to ambient global
      context mutation. `sum(increase_allocations) ==
      sum(decrease_allocations)` always holds by construction. No
      `ReasonCode` is ever emitted; no final campaign budget is
      calculated; conservation verification remains entirely separate.
      Output order exactly preserves Stage 24's own ranking order.
- [x] `tests/test_allocation.py` (Sprint 1 placeholder filled in for the
      first time) — 79 new Stage 25 tests, all passing.
      `tests/test_ranking.py` unchanged at 69 tests,
      `tests/test_scoring.py` unchanged at 81 tests,
      `tests/test_reasons.py` unchanged at 69 tests,
      `tests/test_recommendation.py` unchanged at 84 tests,
      `tests/test_suitability.py` unchanged at 67 tests,
      `tests/test_availability.py` unchanged at 61 tests,
      `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
      (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
      re-run and confirmed passing — no regression, no existing
      non-placeholder test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 25 (and not yet started)

- Conservation verification of the balance invariant Stage 25's
  allocation already constructs (`src/conservation.py`).
- Final campaign budgets (`current_budget ± allocated amount`) — deferred
  to a later deterministic integration/reporting stage if required.
- `ACCOUNT_RESERVE_REQUIRED`, `NO_ELIGIBLE_RECIPIENT`, and the remaining
  ten `ReasonCode` members' trigger conditions (see Stage 22's
  Explicitly-Out-of-Scope list above).
- `Confidence.NOT_ASSESSABLE` ownership/trigger and the combined
  confidence/tracking/pacing assessment question.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Development Stage 26 — Deterministic, Independent Budget Conservation Verification (complete)

- [x] `src/conservation.py` (Sprint 1 placeholder pair filled in for the
      first time — not a newly created module, mirroring Stages 23 and 25's
      pattern) — `CampaignReallocationConservation` (frozen,
      `extra="forbid"`: `total_increase_allocated: Currency` `>= 0`,
      `total_decrease_allocated: Currency` `>= 0`, `net_change: Decimal`
      (plain, may be negative), `is_conserved: bool` — a model validator
      rejects any instance where `net_change != total_increase_allocated
      - total_decrease_allocated` or `is_conserved` is inconsistent with
      `net_change == Decimal("0.00")`) and
      `verify_campaign_reallocation_conservation(allocation:
      CampaignReallocationAllocation) -> CampaignReallocationConservation`.
      `src/allocation.py`, `src/ranking.py`, `src/scoring.py`,
      `src/recommendation.py`, `src/reasons.py`, `src/constraints.py`,
      `src/constants.py` (no enum added or changed), `src/models.py`
      unchanged.
- [x] **Approved conservation equation**: independently recomputes
      `total_increase_allocated`/`total_decrease_allocated` by summing
      `allocated_amount` across `allocation.increase_allocations`/
      `.decrease_allocations` — never trusting a portfolio total from
      Stage 25, which returns none. `net_change =
      total_increase_allocated - total_decrease_allocated`;
      `is_conserved = (net_change == Decimal("0.00"))`.
- [x] **Approved sign convention**: positive `net_change` means increases
      exceed decreases, negative means decreases exceed increases — never
      left ambiguous, never returned as an absolute difference.
- [x] **Approved exact-equality policy**: no tolerance, epsilon,
      absolute-difference threshold, or rounded comparison — an imbalance
      of exactly `Decimal("0.01")` is reported as not conserved.
- [x] **Approved always-return-a-result policy**: the production function
      never raises merely because an allocation is imbalanced;
      `is_conserved=False` with the exact signed `net_change` is a valid,
      auditable result. Only a directly-constructed, internally
      inconsistent result model is rejected, via ordinary Pydantic
      validation.
- [x] **Approved duplicate/overlap indifference**: `campaign_id` is never
      read from any allocation record; Stage 26 sums every
      `allocated_amount` present regardless of duplicate IDs within one
      direction, the same ID in both directions, or repeated zero
      records — trusting Stage 24/25's own structural identity
      guarantees rather than re-validating them.
- [x] Consumes only Stage 25's `CampaignReallocationAllocation` — never
      `ReviewSetup`, `CampaignInput`, Stage 16/18 capacity results, Stage
      24's ranking, `CampaignRecommendation`, or
      `CampaignRecommendationReason`. Never calls
      `allocate_campaign_reallocation` or any other Stage 1–25 production
      function. Reads exactly the authorised fields.
- [x] Plain `Decimal` throughout — never `float`. Every sum and the final
      subtraction run inside an explicitly-scoped `localcontext`, with
      precision derived from the actual operands' digit counts and record
      count (never a blindly assumed fixed value), directly responding to
      the ambient-context arithmetic defect discovered and corrected
      during Stage 25. No `ReasonCode` is ever emitted; no final campaign
      budget is calculated; no repair, rebalancing, or mutation of the
      allocation ever occurs.
- [x] `tests/test_conservation.py` (Sprint 1 placeholder filled in for the
      first time) — 50 new Stage 26 tests, all passing.
      `tests/test_allocation.py` unchanged at 79 tests,
      `tests/test_ranking.py` unchanged at 69 tests,
      `tests/test_scoring.py` unchanged at 81 tests,
      `tests/test_reasons.py` unchanged at 69 tests,
      `tests/test_recommendation.py` unchanged at 84 tests,
      `tests/test_suitability.py` unchanged at 67 tests,
      `tests/test_availability.py` unchanged at 61 tests,
      `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
      (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
      re-run and confirmed passing — no regression, no existing
      non-placeholder test file required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 26 (and not yet started)

- Final deterministic integration/reporting — including any publication
  gating on `CampaignReallocationConservation.is_conserved` and final
  campaign-budget computation (`current_budget ± allocated amount`).
- `ACCOUNT_RESERVE_REQUIRED`, `NO_ELIGIBLE_RECIPIENT`, and the remaining
  ten `ReasonCode` members' trigger conditions (see Stage 22's
  Explicitly-Out-of-Scope list above).
- `Confidence.NOT_ASSESSABLE` ownership/trigger and the combined
  confidence/tracking/pacing assessment question.
- Streamlit interface, Gemini integration, approval workflow, audit, exports.
- Tests for any of the above.

## Development Stage 27 — Final Deterministic Pipeline Integration and Reporting (complete)

- [x] `src/pipeline.py` (new production module — no existing placeholder
      was scoped for deterministic orchestration; `app.py`, `config.py`,
      `src/explanations.py`, `src/gemini_analyzer.py`, `src/approval.py`,
      `src/audit.py`, `src/exports.py` all remain reserved for their own
      Sprint 3 responsibilities, untouched) —
      `CampaignBudgetRecommendationResult` (frozen, `extra="forbid"`:
      `campaign_id`, `campaign_name`, `platform`, `current_budget:
      Currency`, `recommendation_action`, `allocated_amount: Currency`
      `>= 0`, `recommended_budget: Currency` `>= 0`, `reason_codes:
      tuple[ReasonCode, ...]`, `performance_band`, `trend_direction`,
      `confidence`, `pacing_status`, `reallocation_priority_score: int`
      `0..100`, `rank: int | None` `>= 1` when present),
      `BudgetReallocationReviewResult` (frozen, `extra="forbid"`:
      `review_id`, `campaign_results:
      tuple[CampaignBudgetRecommendationResult, ...]`,
      `total_current_budget: Currency` `>= 0`, `total_recommended_budget:
      Currency` `>= 0`, `conservation: CampaignReallocationConservation`),
      and `run_budget_reallocation_review(review: ReviewSetup, campaigns:
      tuple[CampaignInput, ...]) -> BudgetReallocationReviewResult`. This
      completes the master plan's Sprint 2 "Deterministic Core Engine"
      goal. No Stage 1–26 production or test module was modified; no enum
      was added or changed.
- [x] **Approved orchestration**: calls every already-approved Stage 3–26
      production function, in their exact frozen dependency order, per
      campaign then once per portfolio (ranking → allocation →
      conservation), then assembles final results in the original input
      order — no formula duplicated, approximated, reopened, or
      recalculated from an upstream result object.
- [x] **Approved validation boundary**: `ReviewSetup` and every
      `CampaignInput` are accepted only already-validated; this stage
      never reads a CSV, never calls `validate_campaign_csv`, never
      returns validation issues, and never re-checks campaign-ID
      uniqueness (already Stage 2's responsibility). An empty campaign
      tuple is valid and returns an empty portfolio result.
- [x] **Approved final-movement and final-budget policy**: exactly one
      unsigned `allocated_amount` per campaign (direction carried only by
      `recommendation_action`); `Decimal("0.00")` for `HOLD`/`MAINTAIN`
      and for any directional recommendation with no matching Stage 25
      allocation record; a zero-funded `INCREASE`/`REDUCE` is never
      rewritten to `MAINTAIN`/`HOLD` (verified for the real G002 sample
      result). Final budget: `INCREASE → current_budget +
      allocated_amount`; `REDUCE → current_budget - allocated_amount`;
      `MAINTAIN`/`HOLD → current_budget` unchanged — computed only from
      Stage 25's actual allocated amount, never from raw/effective
      constraint limits.
- [x] **Approved conservation policy**: the embedded Stage 26
      `CampaignReallocationConservation` result is always present,
      regardless of `is_conserved` — never hidden, gated, or omitted; this
      stage never raises merely because an allocation is unconserved. A
      defence-in-depth check — distinct from, and never a replacement
      for, Stage 26's own invariant — raises exactly
      `RuntimeError("Conserved allocation must preserve the total
      campaign budget.")` only if a *conserved* allocation's recomputed
      portfolio totals fail to match exactly.
- [x] **Approved matching/ordering**: all cross-collection matching
      (rank, allocation) is by `campaign_id` value, never tuple position;
      `campaign_results` preserves the original `campaigns` input order;
      Stage 24's increase/reduce rankings remain independent, with no
      global cross-direction rank ever constructed.
- [x] Plain `Decimal` throughout — never `float`; every addition,
      subtraction, and portfolio-level sum runs inside an
      explicitly-scoped `localcontext`, with precision derived from the
      actual operands' digit counts and collection size, immune to
      ambient global context mutation — directly extending the corrected
      discipline established at Stages 25 and 26. Stage 22's ordered
      `reason_codes` are passed through unchanged; no allocation-specific
      reason code is ever invented. Fails fast on any unexpected exception
      or upstream `ValueError` — no `try`/`except`, no retry, no partial
      result, no campaign ever silently dropped, no input or upstream
      result object ever mutated.
- [x] `tests/test_pipeline.py` (new dedicated test file — deliberately
      distinct from `tests/test_integration.py`, which remains reserved
      for the later, materially larger AI/UI-inclusive end-to-end flow)
      — 35 new Stage 27 tests, all passing. `tests/test_conservation.py`
      unchanged at 50 tests, `tests/test_allocation.py` unchanged at 79
      tests, `tests/test_ranking.py` unchanged at 69 tests,
      `tests/test_scoring.py` unchanged at 81 tests,
      `tests/test_reasons.py` unchanged at 69 tests,
      `tests/test_recommendation.py` unchanged at 84 tests,
      `tests/test_suitability.py` unchanged at 67 tests,
      `tests/test_availability.py` unchanged at 61 tests,
      `tests/test_constraints.py` unchanged at 322 tests. `tests/test_models.py`
      (Stage 1) through `tests/test_pacing_interpretation.py` (Stage 9)
      re-run and confirmed passing — no regression, no existing test
      module required modification.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`, `docs/TEST_SCENARIOS.md`
      updated.

## Explicitly Out of Scope for Stage 27 (and not yet started)

- Streamlit interface (`app.py`), configuration wiring (`config.py`).
- Gemini explanation (`src/gemini_analyzer.py`, `src/explanations.py`).
- Human approval/rejection workflow (`src/approval.py`).
- Immutable JSON audit recording (`src/audit.py`).
- CSV export generation (`src/exports.py`).
- The full AI/UI-inclusive end-to-end integration test
  (`tests/test_integration.py`, reserved, untouched).
- `ACCOUNT_RESERVE_REQUIRED`, `NO_ELIGIBLE_RECIPIENT`, and the remaining
  ten `ReasonCode` members' trigger conditions (see Stage 22's
  Explicitly-Out-of-Scope list above).
- `Confidence.NOT_ASSESSABLE` ownership/trigger and the combined
  confidence/tracking/pacing assessment question.
- Sprint 4 hardening and documentation finalization.
- Tests for any of the above.

## Development Stage 28 — Deterministic Streamlit Review Shell (complete)

- [x] `app.py` (placeholder filled in for the first time — the Sprint 1
      placeholder Streamlit entry point) — a deterministic-only Streamlit
      review shell. Collects raw `ReviewSetup` input and an uploaded
      campaign CSV, calls the existing Stage 2 `validate_review_setup`/
      `validate_campaign_csv` functions, displays every validation issue,
      and — only when the frozen execution-gating policy permits — calls
      the existing Stage 27 `run_budget_reallocation_review` and displays
      the locked, read-only `BudgetReallocationReviewResult`. No
      validation rule, business formula, or Stage 1–27 calculation is
      reimplemented; `app.py` only calls the three existing functions and
      renders their already-computed output. `config.py`,
      `src/gemini_analyzer.py`, `src/explanations.py`, `src/approval.py`,
      `src/audit.py`, `src/exports.py` remain untouched Sprint 3
      placeholders.
- [x] **Frozen execution-gating policy** (all seven required
      simultaneously; warnings never block): the form was explicitly
      submitted; `validate_review_setup` returned a non-`None` review with
      no errors; a CSV file was supplied and decoded as UTF-8; the
      campaign validation report contains no errors (a CSV with any
      error — even alongside otherwise-valid rows — never runs a partial
      portfolio); and `valid_campaigns` is non-empty. Implemented as a
      pure predicate, `_may_run_pipeline`, decoupled from all Streamlit
      rendering so it is directly unit-testable. Does not change the
      lower-level pipeline's own valid empty-tuple behavior — this is a
      UI-level policy only.
- [x] **Submission and session-state policy**: an explicit
      `st.form_submit_button` ("Run deterministic review") gates every
      pipeline invocation — `_handle_submission` is only ever called
      inside `if submitted:`, confirmed by an AST test, so an ordinary
      Streamlit rerun never recomputes the pipeline. The locked result is
      held under the session-state key `locked_review_result`, explicitly
      cleared to `None` at the start of every new submission before
      validation begins, so a failed resubmission never leaves a stale
      result visible as though it belonged to the new submission. No
      `st.cache_data`/`st.cache_resource` is used.
- [x] **Pipeline-exception policy**: the deterministic pipeline itself
      remains unchanged and fail-fast (no `try`/`except` inside
      `run_budget_reallocation_review`). `app.py` adds exactly one
      deliberate `except Exception` at the Streamlit UI boundary around
      the pipeline call — on an unexpected exception it keeps
      `locked_review_result` empty, shows a clear `st.error` including the
      exception's own message, and does not retry, reclassify, wrap in a
      new exception type, or fabricate a result.
- [x] **Locked-result rendering**: read-only. Displays portfolio-level
      `review_id`, `total_current_budget`, `total_recommended_budget`, and
      every `conservation` field; every campaign result in original
      pipeline order (never sorted) with all fourteen
      `CampaignBudgetRecommendationResult` fields, ordered `reason_codes`
      preserved, and a missing `rank` shown as "Not ranked" rather than a
      fabricated number. No control edits any locked value. Decimal
      values are formatted via `format(value, "f")` — no `float`
      conversion anywhere in the module (AST-verified).
- [x] **Conservation rendering**: always visible for a successful result.
      A conserved result shows a clear success state; an unconserved
      result shows a prominent error state, states plainly that the
      allocation is not conserved, and continues to display the full
      locked result for inspection — never concealed, repaired,
      rebalanced, or rerun, and with no approval control regardless of
      conservation status (Stage 28 has none at all).
- [x] **Explicitly excluded**: Gemini/`google-generativeai`, `config`,
      `src.explanations`, `src.approval`, `src.audit`, `src.exports` are
      neither imported nor referenced (AST-verified); no explanation,
      approval, audit, or export control exists anywhere on the page.
- [x] `tests/test_app.py` (new dedicated test file) — 31 new Stage 28
      tests, all passing, using Streamlit `AppTest` (confirmed available
      and sufficient in the installed `streamlit==1.59.2`, including
      programmatic `file_uploader` population via `set_value`/`upload` —
      no widget-boundary mocking was needed). The real deterministic
      chain is exercised for every successful-path test; the only
      deliberate mock is a single exception-path test that replaces
      `run_budget_reallocation_review` to verify UI failure handling,
      which cannot otherwise be triggered by any legitimately valid input.
      `tests/test_integration.py` remains the untouched Sprint 3 full-flow
      placeholder (AST-confirmed: no function or class definitions).
      Stage 1–27 regression re-run and confirmed passing unchanged at
      1258 tests. Full suite: 1289 tests passing (1258 + 31).
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Explicitly Out of Scope for Stage 28 (and not yet started)

- `config.py` — configuration/secret wiring (env vars, Gemini
  availability). No secret is needed by a deterministic-only shell.
- Gemini explanation (`src/gemini_analyzer.py`, `src/explanations.py`).
- Human approval/rejection workflow (`src/approval.py`).
- Immutable JSON audit recording (`src/audit.py`).
- CSV export generation (`src/exports.py`).
- The full AI/UI-inclusive end-to-end integration test
  (`tests/test_integration.py`, reserved, untouched).
- Any visual/styling design beyond a clear, functional page structure.
- Approval granularity, rejection-comment requirement, and audit-record
  content — open questions reserved for their own later stages.

## Development Stage 29 — Gemini Configuration Foundation (complete)

- [x] `config.py` (placeholder filled in for the first time — the Sprint 1
      placeholder configuration module) — a narrow, explicit,
      side-effect-controlled configuration boundary for Gemini API-key
      availability only: `GeminiConfig` (frozen, `extra="forbid"`, exactly
      one field, `api_key: SecretStr | None`),
      `load_gemini_config(dotenv_path: str | Path | None = None) ->
      GeminiConfig`, and `is_gemini_available(config: GeminiConfig) ->
      bool`. No Gemini SDK is imported; no prompt construction, API call,
      or UI wiring is implemented. `app.py` is untouched and does not
      import `config` (AST-verified).
- [x] **Source precedence**: the process environment variable
      `GEMINI_API_KEY` (checked for presence in `os.environ`, not
      truthiness) is authoritative whenever it exists — including when
      explicitly blank, in which case it does not fall back to `.env`.
      Only when the variable is entirely absent is a local `.env` file
      consulted. Neither source yielding a non-blank value resolves to
      `GeminiConfig(api_key=None)`, a normal, valid, non-raising state.
- [x] **`.env` behavior**: read via `dotenv_values(...)`, never
      `load_dotenv(...)`, so `os.environ` is never mutated. Default path
      (used only when `dotenv_path` is not supplied):
      `Path(__file__).resolve().parent / ".env"` — deterministic,
      independent of the current working directory, never searched in
      parent directories. A missing `.env`, a `.env` without
      `GEMINI_API_KEY`, and a blank/whitespace-only `.env` value all
      resolve the same as the equivalent environment-variable cases.
- [x] **Normalization**: whitespace-trimming only — no case
      transformation, no format/prefix validation, no live API check, no
      logging, never included in an exception message.
- [x] **Secret protection**: `SecretStr` redacts the value in `repr`,
      `str`, `model_dump()`, and `model_dump_json()`; retrievable only via
      the existing `config.api_key.get_secret_value()` — no alternative
      accessor added. `is_gemini_available` never calls
      `get_secret_value()`; availability is derived
      (`api_key is not None`), never a stored field.
- [x] **Import and side-effect policy**: importing `config` performs no
      filesystem read, loads no `.env`, reads no environment variable,
      imports no Streamlit, imports no Gemini SDK, and creates no
      module-level configuration singleton. Configuration is loaded only
      through an explicit call to `load_gemini_config()`.
- [x] **Deterministic independence**: every Stage 28 capability — CSV
      validation, deterministic pipeline execution, locked-result
      rendering — remains fully functional with no Gemini key present. No
      missing-key warning is added to the Stage 28 UI yet.
- [x] **SDK mismatch recorded, not resolved**: `requirements.txt` declares
      `google-generativeai`, not installed in this environment;
      `google-genai` is installed instead. Stage 29 imports no Gemini SDK
      at all; resolving the mismatch is deferred to the future Gemini
      API-integration stage.
- [x] `tests/test_config.py` (new dedicated test file) — 45 new Stage 29
      tests, all passing, using only synthetic fake keys — no real secret
      is ever read, printed, or asserted against. `tests/test_app.py`
      (Stage 28, 31 tests) and `tests/test_integration.py` (untouched
      placeholder) confirmed unmodified. Stage 1–27 regression re-run and
      confirmed passing unchanged at 1258 tests; full Stage 1–28 suite
      confirmed unchanged at 1289 tests. Full suite: 1334 tests passing
      (1289 + 45).
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Explicitly Out of Scope for Stage 29 (and not yet started)

- Gemini SDK import or any live API call.
- Explanation payload/prompt construction (`src/explanations.py`).
- Gemini API integration (`src/gemini_analyzer.py`), including resolving
  the `google-generativeai`/`google-genai` dependency mismatch.
- Any missing-key warning or other UI wiring in `app.py`.
- Human approval/rejection workflow (`src/approval.py`).
- Immutable JSON audit recording (`src/audit.py`).
- CSV export generation (`src/exports.py`).
- The full AI/UI-inclusive end-to-end integration test
  (`tests/test_integration.py`, reserved, untouched).

## Development Stage 30 — Explanation Payload and Prompt Construction (complete)

- [x] `src/explanations.py` (placeholder filled in for the first time — the
      Sprint 1 placeholder explanation module) — a pure, deterministic
      boundary between an already-locked pipeline result and whatever
      future stage actually calls Gemini: `CampaignExplanationPayload`,
      `PortfolioExplanationPayload`, `ExplanationPrompt` (all frozen,
      `extra="forbid"`), `build_campaign_explanation_payload`,
      `build_portfolio_explanation_payload`, `serialize_explanation_payload`,
      `build_campaign_explanation_prompt`, `build_portfolio_explanation_prompt`
      — exactly these five public functions, no orchestration wrapper. Never
      calls Gemini, never imports `config`/`GeminiConfig`/
      `is_gemini_available`/`GEMINI_API_KEY`, never imports Streamlit or any
      Gemini SDK, never mutates a locked result. `app.py` is untouched.
- [x] **Frozen Gemini boundary**: Gemini is explanation-only — it may
      explain only the locked facts supplied in a payload, and must never
      select/change an action, allocation, budget, score, or rank;
      add/remove/reorder reason codes; change a classification; hide,
      repair, or reinterpret conservation; rewrite a zero-funded
      directional action to `MAINTAIN`/`HOLD`; approve/reject; create
      audit facts; infer from data outside the payload; or introduce
      unsupported claims. Stage 30 creates prompts only — it never
      generates or fabricates an explanation.
- [x] **Authorized fields only**: `CampaignExplanationPayload` copies
      exactly the fourteen authorized campaign fields from one locked
      `CampaignBudgetRecommendationResult`; `PortfolioExplanationPayload`
      copies `review_id`, both totals, and all four conservation fields
      directly from `result.conservation` — never recalculated. Raw CSV
      data, `review_notes`, raw metrics, validation issues, intermediate
      constraints, availability/suitability, the API key, and audit data
      are all excluded and unreachable.
- [x] **Granularity**: campaign and portfolio payloads are structurally
      separate — one campaign payload contains exactly one campaign with
      no sibling-campaign data; the portfolio payload contains only
      totals/conservation, never a campaign list. No function loops over
      the full campaign collection to build a combined prompt.
- [x] **Canonical serialization**: compact JSON, key order matches model
      field declaration order (never sorted), `ensure_ascii=False`,
      separators exactly `(",", ":")`, no indentation. `Decimal`/
      `Currency` serialize as fixed-point strings via `format(value,
      "f")` — never a JSON number, never `float`, never scientific
      notation. Enums serialize to `.value`; tuples to JSON arrays,
      order preserved; `None` to `null`. Identical input produces
      byte-for-byte identical output.
- [x] **Prompt architecture**: one fixed system instruction, byte-for-byte
      identical regardless of payload contents, containing no campaign/
      portfolio data, API key, SDK detail, model name, or generation
      parameter — it states every frozen boundary rule above plus the
      "not ranked, never rank zero" and "disclose, never conceal" rules.
      User content contains one fixed sentence plus the canonical JSON
      between fixed `BEGIN_LOCKED_DATA`/`END_LOCKED_DATA` markers; no
      field is interpolated individually into prose.
- [x] **Injection containment, honestly scoped**: `campaign_name` is
      treated as untrusted data — JSON escaping plus system/user
      separation verified against embedded quotes, backslashes, braces,
      newlines, Markdown, Unicode, literal marker text, and
      instruction-like phrasing. This does not eliminate prompt
      injection; the decisive protection is structural — no Gemini
      output ever writes back into a locked deterministic model.
- [x] **Output contract deferred**: concise, grounded, plain-language text
      only is requested; response parsing, a response model, structured
      output, retries, timeouts, fallback explanations, API-error
      handling, and persistence all remain reserved for the future Gemini
      API-integration stage, along with the still-unresolved
      `google-generativeai`/`google-genai` mismatch.
- [x] `tests/test_explanations.py` (new dedicated test file) — 93 new
      Stage 30 tests, all passing. Real Stage 27 sample-data results used
      for primary success-path coverage (including the G002 zero-funded-
      `INCREASE` and G001 unranked cases); hand-built frozen fixtures used
      only for states unreachable through the real pipeline (an
      unconserved portfolio, extreme 28-significant-digit Decimal
      magnitudes, an empty portfolio). No Gemini output fabricated; no SDK
      mocked. `tests/test_app.py`, `tests/test_config.py`, and
      `tests/test_integration.py` confirmed unmodified. Stage 1–29
      regression re-run and confirmed passing unchanged at 1334 tests.
      Full suite: 1427 tests passing (1334 + 93).
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Explicitly Out of Scope for Stage 30 (and not yet started)

- Any Gemini SDK import or live API call.
- Resolving the `google-generativeai`/`google-genai` dependency mismatch.
- A Gemini response model, response parsing, or structured output.
- Retries, timeouts, fallback explanations, or API-error handling.
- Explanation persistence.
- Any UI wiring in `app.py`.
- Human approval/rejection workflow (`src/approval.py`).
- Immutable JSON audit recording (`src/audit.py`).
- CSV export generation (`src/exports.py`).
- The full AI/UI-inclusive end-to-end integration test
  (`tests/test_integration.py`, reserved, untouched).

## Development Stage 31 — Gemini Explanation Transport (complete)

- [x] `src/gemini_analyzer.py` (placeholder filled in for the first time —
      the Sprint 1 placeholder Gemini-integration module) — the
      transport/service layer sending one Stage 30 `ExplanationPrompt` to
      Gemini and returning a typed `ExplanationResult`. Consumes only
      `ExplanationPrompt` and `GeminiConfig` (plus an optional injected
      client and a model-name override) — never a locked pipeline result,
      a payload model, an approval model, an audit model, or Streamlit.
      One generic `generate_explanation` function only — no separate
      campaign/portfolio transport functions, no batch function. `app.py`
      is untouched.
- [x] **SDK dependency mismatch resolved**: `requirements.txt` now
      declares `google-genai>=2,<3` (removed `google-generativeai`,
      which was never actually installed and is officially documented as
      not actively maintained, with legacy libraries deprecated as of
      2025-11-30). No code anywhere imports `google.generativeai`.
      `pyproject.toml` unchanged (it has no dependency section). No
      package was installed or upgraded — the already-installed
      `google-genai==2.12.1` satisfies the new pin.
- [x] **Frozen model and settings**: default model `gemini-2.5-flash-lite`
      in one private module constant, overridable via the keyword-only
      `model` parameter; `temperature=0.2`; `max_output_tokens=512`;
      exactly one candidate; a `30_000`-millisecond timeout via
      `GenerateContentConfig.http_options=HttpOptions(timeout=...)`. No
      structured output, no safety-setting overrides, no seed, no stop
      sequences.
- [x] **Availability guard and client lifecycle**: `is_gemini_available`
      checked first — unavailable means zero client construction and
      zero API attempt. An injected client is used as-is and never
      closed; when none is injected, `get_secret_value()` is called at
      exactly one production call site to build one fresh
      `google.genai.Client` for that call only, always closed in
      `finally` on both success and failure. No module-level client or
      config singleton; no import-time side effect.
- [x] **Failure mapping, no retries, no fabricated fallback**: every
      failure returns `FAILED` with one of ten frozen `ErrorCategory`
      values (`CONFIGURATION`, `AUTHENTICATION`, `RATE_LIMIT`,
      `SERVER_ERROR`, `TIMEOUT`, `NETWORK_ERROR`, `SAFETY_BLOCK`,
      `EMPTY_RESPONSE`, `MALFORMED_RESPONSE`, `UNEXPECTED_ERROR`).
      Exactly one provider invocation per call; no fabricated
      deterministic fallback explanation text is ever returned.
- [x] **Secret redaction**: any exception message from the owned-client
      path has the known key value replaced with `[REDACTED]` before
      entering `error_message`; the raw provider response, request,
      headers, and credentials are never stored; the injected-client path
      never reads `config.api_key` at all.
- [x] **Result-state invariants**: `ExplanationResult` (frozen,
      `extra="forbid"`) enforces by model validator that `GENERATED`
      requires nonblank `explanation_text`/`model_name` and no error
      fields; `UNAVAILABLE` requires no text/model, `CONFIGURATION`, and
      a nonblank message; `FAILED` requires no text, a nonblank model, a
      non-`CONFIGURATION` category, and a nonblank message. Inconsistent
      direct construction is rejected, never silently repaired.
- [x] `tests/test_gemini_analyzer.py` (new dedicated test file) — 61 new
      Stage 31 tests, all passing, using explicit fake clients/responses
      (never loose `MagicMock`) and zero real network/API calls. A real
      Stage 27 sample-data campaign (G002) is used for the primary
      success-path test, built through the real Stage 30 payload/prompt
      chain. `tests/test_config.py`, `tests/test_explanations.py`, and
      `tests/test_integration.py` confirmed unmodified. Stage 1–30
      regression re-run and confirmed passing unchanged at 1427 tests.
      Full suite: 1488 tests passing (1427 + 61).
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Explicitly Out of Scope for Stage 31 (and not yet started)

- Any UI wiring in `app.py` — including a missing-key or failure display.
- Response parsing beyond plain `.text` extraction; any structured
  response schema.
- Human approval/rejection workflow (`src/approval.py`).
- Immutable JSON audit recording (`src/audit.py`).
- CSV export generation (`src/exports.py`).
- The full AI/UI-inclusive end-to-end integration test
  (`tests/test_integration.py`, reserved, untouched).

## Development Stage 32 — Explanation UI Wiring (complete)

- [x] `app.py` (extended, not replaced) — one optional, click-only Gemini
      explanation section, rendered strictly after the complete locked
      deterministic result: one portfolio-level explanation and one
      explanation for a user-selected campaign. Nothing generates
      automatically; no campaign call is ever batched.
- [x] **Required section and trust labeling**: `st.subheader("Optional
      AI-generated explanations")` followed by the fixed caption "Gemini
      explanations are supplementary and may be inaccurate. The
      deterministic recommendations above remain authoritative." An
      explanation is never labeled verified, validated, checked,
      authoritative, approved, or deterministic.
- [x] **Exact widgets**: `generate_portfolio_explanation` button;
      `explanation_campaign_id` selectbox formatted `{campaign_id} —
      {campaign_name}`; `generate_campaign_explanation` button. Both
      buttons appear only with a locked result, remain enabled regardless
      of Gemini configuration, and are never inside the deterministic
      form.
- [x] **Session-state lifecycle**: `portfolio_explanation_result`,
      `campaign_explanation_result`, and `campaign_explanation_campaign_id`
      (alongside the existing `locked_review_result`) are all cleared at
      the very start of every new deterministic submission, before
      validation. Ordinary reruns preserve stored explanations and make
      no Gemini call. Each click clears-then-replaces its own result. The
      stored campaign explanation renders only when its recorded campaign
      ID matches the current selection — changing the selector hides a
      mismatched explanation without a new call; reselecting the original
      campaign redisplays it without regenerating.
- [x] **Exact call chains**: portfolio —
      `build_portfolio_explanation_payload` →
      `build_portfolio_explanation_prompt` → `load_gemini_config()` →
      `generate_explanation(prompt, config)`; campaign — the selected
      existing locked campaign result →
      `build_campaign_explanation_payload` →
      `build_campaign_explanation_prompt` → `load_gemini_config()` →
      `generate_explanation(prompt, config)`. No Stage 29/30/31 formula
      is reimplemented in `app.py`.
- [x] **Rendering policy**: a shared private helper renders every
      `ExplanationResult`. `GENERATED` shows a local heading, the text via
      `st.markdown(..., unsafe_allow_html=False)` (never `True`), and an
      "AI-generated using {model_name}" caption. `UNAVAILABLE`/`FAILED`
      show only the sanitized `error_message` via `st.info`/`st.error`.
      `error_category` is never displayed. The locked deterministic
      totals, conservation, and campaign table remain fully visible and
      authoritative in every state.
- [x] **Configuration/secret boundary**: `load_gemini_config()` is called
      fresh inside each click handler, never cached or stored in session
      state. `app.py` never accesses `config.api_key`, references
      `SecretStr`, calls `get_secret_value()`, inspects an environment
      variable, or reads `.env` directly.
- [x] **Single explanation-action exception boundary**: an unexpected
      failure while building a payload/prompt or calling the transport is
      caught only at the one click-handler boundary per action, showing a
      concise generic error, storing no fabricated result, preserving the
      locked result, exposing no raw secret/traceback/configuration, and
      never retrying automatically.
- [x] **One approved test exception**: `tests/test_app.py`'s
      `test_module_does_not_import_forbidden_modules` and
      `test_module_does_not_reference_forbidden_names`, and
      `tests/test_config.py`'s former `test_app_module_does_not_import_config`
      (renamed `test_app_module_imports_config_but_never_touches_the_raw_key`),
      were narrowed to remove only `config`/`src.explanations`/
      `src.gemini_analyzer` from their forbidden sets, per explicit
      approval, because `app.py` now legitimately imports exactly those
      three. Every other forbidden entry in all three tests is unchanged
      and still enforced.
- [x] `tests/test_app_explanation.py` (new dedicated test file) — 35 new
      Stage 32 tests, all passing, using explicit fake/monkeypatched
      generation behavior and zero real Gemini/network calls. Covers
      section/widget presence and absence, the exact trust caption, real
      Stage 30 payload/prompt construction reaching the real Stage 31
      transport boundary, campaign-selector formatting and exact-campaign
      resolution, rendering of every `ExplanationStatus`, one-click/one-call
      and zero-call-on-rerun discipline, re-click replacement, stale
      campaign-explanation hiding and redisplay, explanation-state
      clearing on both successful and failed new submissions, full
      deterministic-result visibility and non-mutation, the real
      network-free `UNAVAILABLE` path, API-key absence from rendered
      output and session state, no unsafe HTML, the single
      exception-action boundary, and AST-based isolation. `tests/test_config.py`,
      `tests/test_explanations.py`, `tests/test_gemini_analyzer.py`, and
      `tests/test_integration.py` confirmed unmodified beyond the one
      approved narrow exception above. Stage 1–31 regression re-run and
      confirmed passing unchanged at 1488 tests. Full suite: 1523 tests
      passing (1488 + 35).
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Development Stage 33 — Human Approval Workflow (complete)

- [x] `src/approval.py` (populated for the first time — placeholder
      replaced) — one accountable human decision, approve or reject,
      applied to the complete locked `BudgetReallocationReviewResult` only
      — never a per-campaign or partial-portfolio decision, since
      conservation is a whole-portfolio invariant. **Reuses the existing
      Stage 1 `ReviewStatus` enum** rather than inventing a new one, per
      explicit approval — no `ApprovalDecision` or other new enum was
      created.
- [x] **Exact model**: `CampaignReallocationApproval` (frozen,
      `extra="forbid"`: `review_id: str`, `decision: ReviewStatus`,
      `reviewer_name: str`, `note: str | None = None`). A `@field_validator`
      restricts `decision` to `ReviewStatus.APPROVED`/`REJECTED` only —
      direct construction with `DRAFT` or `PENDING_APPROVAL` fails Pydantic
      validation. Blank `review_id`/`reviewer_name` are rejected by
      `Field(min_length=1)`; a blank `note` normalizes to `None`.
- [x] **Exact functions**:
      `approve_campaign_reallocation_review(result, reviewer_name, *,
      note=None)` and `reject_campaign_reallocation_review(result,
      reviewer_name, *, note=None)`. `review_id` is always derived from
      `result.review_id` — never a separate caller-supplied parameter.
- [x] **Conservation policy**: `approve_campaign_reallocation_review`
      raises exactly `ValueError("An unconserved allocation cannot be
      approved.")` when `result.conservation.is_conserved` is `False` —
      fail-fast domain validation, checked after the blank-reviewer-name
      check. `reject_campaign_reallocation_review` places no such
      restriction — a conserved or unconserved result may both be
      rejected. Neither function repairs, rebalances, or reruns anything.
- [x] Both functions raise exactly `ValueError("Reviewer name must not be
      blank.")` for a blank/whitespace-only `reviewer_name`, checked before
      the conservation check. Neither the locked `result` nor any of its
      nested fields is ever mutated (frozen throughout the deterministic
      pipeline).
- [x] **No timestamp**: Stage 33 records no wall-clock value; that
      responsibility belongs to the later audit stage. **No Gemini,
      configuration, audit, or export coupling**: `src/approval.py` never
      imports `config`, `src.explanations`, `src.gemini_analyzer`,
      `src.audit`, `src.exports`, `datetime`, `time`, `random`, `uuid`, or
      any filesystem/network module — structurally guaranteed via
      AST-based isolation tests, not just behavioral convention.
- [x] `app.py` (extended, not replaced) — a new "Human approval" section
      rendered immediately after the optional explanation section, inside
      the same `if result is not None:` block. Exact caption: "Approval
      applies to the complete locked deterministic review. AI-generated
      explanations are supplementary and are not part of the approval
      decision."
- [x] **Exact widgets and keys**: `st.text_input("Approver name",
      key="approval_reviewer_name")` (starts blank — deliberately **not**
      pre-filled from `ReviewSetup.reviewer_name`, per explicit approval,
      since the locked result does not carry that field and a hidden
      linkage was judged unnecessary); `st.text_area("Decision note
      (optional)", key="approval_note")`; `st.button("Approve
      deterministic review", key="approve_review")`; `st.button("Reject
      deterministic review", key="reject_review")`. No confirmation
      checkbox, radio selector, separate confirmation button, reconsider
      button, or change-decision control exists anywhere in the section.
- [x] **Session-state lifecycle**: `APPROVAL_DECISION_STATE_KEY =
      "approval_decision_result"`, plus `approval_reviewer_name` and
      `approval_note`, are all cleared at the very start of every new
      deterministic submission (successful or failed), immediately after
      the existing explanation-state clears and before validation begins —
      safe because it runs before the approval section's widgets are ever
      instantiated later in the same script run. Ordinary reruns and
      explanation-generation clicks never create, alter, or clear a
      decision. A successful decision triggers one immediate `st.rerun()`
      so the finalized view fully replaces the editable controls within a
      single clean run, rather than rendering both simultaneously — an
      empirically necessary fix, since Streamlit cannot retroactively
      remove elements already emitted earlier in the same run. A failed
      attempt (blank name, unconserved approval, or an unexpected error)
      stores nothing, triggers no rerun, and leaves the visible error
      beside the still-editable widgets.
- [x] **Finalized-decision rendering** (exact text): `st.success("Decision:
      APPROVED")` or `st.warning("Decision: REJECTED")`, then `st.write(f"Approver:
      {approval.reviewer_name}")`, then — only when `approval.note is not
      None` — `st.write(f"Decision note: {approval.note}")`. Once stored,
      a decision cannot be overwritten or reconsidered; further reruns
      always re-render the same finalized state.
- [x] **Defense-in-depth `review_id` check** (explicitly not a result
      fingerprint, per explicit approval): if a stored decision's
      `review_id` does not match the current locked result's `review_id`,
      it is cleared and a generic mismatch error is shown, falling through
      to fresh, editable controls. Normal operation never reaches this
      path — the submission-time clearing above already prevents it.
- [x] **Single unexpected-error boundary**: exactly one domain-function
      call per click, wrapped in `try/except ValueError as exc: st.error(str(exc))`
      then `except Exception: st.error("The approval decision could not be
      recorded due to an unexpected error.")` — no raw exception,
      traceback, or provider detail is ever shown; no fabricated decision
      is ever stored.
- [x] **One approved test exception** (pre-approved, narrower than Stage
      32 — no confirmation question needed this stage): `tests/test_app.py`'s
      `test_module_does_not_import_forbidden_modules` and
      `test_module_does_not_reference_forbidden_names`, and
      `tests/test_app_explanation.py`'s renamed
      `test_no_audit_or_export_imports` (formerly
      `test_no_approval_audit_or_export_imports`), were narrowed to remove
      only `src.approval`/`approval` from their forbidden sets, because
      `app.py` now legitimately imports `src.approval`. Every other
      forbidden entry in all three tests is unchanged and still enforced.
- [x] `tests/test_approval.py` (populated for the first time — placeholder
      replaced) — 31 new Stage 33 domain tests, all passing. Covers exact
      model fields, `extra="forbid"`, frozen, `APPROVED`/`REJECTED` valid
      and `DRAFT`/`PENDING_APPROVAL` rejected, blank-field rejection and
      whitespace-stripping, note normalization, exact function signatures,
      conserved/unconserved approve/reject behavior, exact error messages,
      check-ordering (blank name before conservation), `review_id`
      derivation from the locked result only, non-mutation of the locked
      result, and AST-based isolation (no Gemini/config/audit/export/
      filesystem/network/wall-clock/random/uuid reference anywhere in the
      module).
- [x] `tests/test_app_approval.py` (new dedicated test file) — 34 new
      Stage 33 UI tests, all passing, using `AppTest` with explicit
      fixtures/monkeypatches and zero live network calls/real API key.
      Covers control presence/absence, the exact heading/caption, the
      approver field starting blank, successful approve/reject with and
      without a note, blank-name and unconserved-approval validation,
      unconserved-rejection success, one-click/one-call discipline,
      zero-call-on-ordinary-rerun, finalized-decision rendering that
      replaces all editable controls and cannot be overwritten,
      approval-state clearing on new successful and new invalid
      submissions, explanation-generation and campaign-selector
      independence, Gemini/API-key independence, deterministic-result
      visibility and non-mutation across every outcome, the stale-
      review-ID defense-in-depth path, the single unexpected-exception
      boundary with no raw exception/provider detail exposed, no
      audit/export/platform-execution behavior, and the session-state
      clearing lifecycle at the source level. A file-scoped autouse
      fixture restores `app.approve_campaign_reallocation_review`,
      `app.reject_campaign_reallocation_review`, `app.generate_explanation`,
      and `app.run_budget_reallocation_review` to their real
      implementations before every test, mirroring the established
      Stage 32 defensive pattern against `AppTest`'s shared
      `sys.modules["app"]` singleton.
- [x] Stage 1–32 regression re-run and confirmed passing unchanged at
      `1523 passed`. Full suite: `1588 passed` (1523 + 31 + 34).
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Explicitly Out of Scope for Stage 33 (and not yet started)

- Immutable JSON audit recording (`src/audit.py`), including any
  timestamp for the approval decision.
- CSV export generation (`src/exports.py`).
- The full AI/UI-inclusive end-to-end integration test
  (`tests/test_integration.py`, reserved, untouched).
- Persisting, overwriting, or reconsidering a finalized decision.

## Development Stage 34 — Audit Persistence (complete)

- [x] `src/audit.py` (populated for the first time — placeholder
      replaced) — the durable, structured record of exactly one complete
      locked `BudgetReallocationReviewResult` and its finalized
      `CampaignReallocationApproval`. The only component in the project
      that persists anything to disk.
- [x] **Exact model**: `CampaignReallocationAudit` (frozen,
      `extra="forbid"`: `audit_id: str`, `review_id: str`, `result:
      BudgetReallocationReviewResult`, `approval:
      CampaignReallocationApproval`, `recorded_at: datetime`). Embeds the
      existing frozen Stage 27/33 models directly — no parallel result,
      campaign, conservation, or approval schema is created. A
      `@field_validator` rejects a naive `recorded_at` and normalizes any
      timezone-aware value to UTC.
- [x] **Exact functions**: `build_campaign_reallocation_audit(result,
      approval, recorded_at)` — pure, no file/environment/clock/network/SDK
      access — and `record_campaign_reallocation_audit(audit, *,
      directory=None)`. No public read, list, delete, repair, overwrite,
      or retry function exists; enumeration/export is reserved for Stage
      35.
- [x] **Consistency checks**, checked in order before construction:
      `approval.review_id == result.review_id`, else exactly
      `ValueError("Approval review_id does not match the locked result's
      review_id.")`; if `decision is ReviewStatus.APPROVED`,
      `result.conservation.is_conserved` must be `True`, else exactly
      `ValueError("An unconserved allocation cannot be recorded as
      approved.")`. A rejected unconserved result is always recordable.
      Neither input is ever repaired, rebalanced, rerun, reinterpreted, or
      mutated.
- [x] **No wall-clock call in `src/audit.py`**: `recorded_at` is always
      supplied by the caller. The one production call to
      `datetime.now(timezone.utc)` lives in `app.py`'s
      `_attempt_audit_recording`, the single Stage 34 audit-action
      boundary, and is passed straight into
      `build_campaign_reallocation_audit`.
- [x] **Deterministic, content-derived audit ID**: `audit_id =
      f"audit_{sha256(canonical_bytes).hexdigest()}"`, where
      `canonical_bytes` is the canonical JSON of exactly `{"result":
      result, "approval": approval}` — excluding `recorded_at` entirely.
      No UUID, no `hash()`, no raw `review_id` path component, no
      timestamp contributes to the ID. Canonical serialization matches
      `src/explanations.py`'s existing policy: model declaration field
      order, `ensure_ascii=False`, compact separators, `Decimal` as
      fixed-point strings via `format(value, "f")`, enums via `.value`,
      tuples as arrays, `recorded_at` as ISO-8601 with an explicit UTC
      offset.
- [x] **Persistence**: one UTF-8 JSON file per record at
      `audit_records/{audit_id}.json` (default directory resolved from
      `src/audit.py`'s own location, never the current working
      directory; overridable via `directory=`), written to a temporary
      file in the same directory, flushed and closed, then finalized via
      atomic `os.replace`; a failure during serialization or finalization
      leaves no temporary or final file behind.
- [x] **Idempotency**: a pre-existing file with the same `audit_id` and
      the same substantive content (`review_id`, `result`, `approval` —
      `recorded_at` excluded, since the first successful write's
      timestamp is authoritative) is a no-op success returning the
      original path unchanged. A pre-existing file with different
      content raises exactly `ValueError("An audit record with this
      audit_id already exists with different content.")`. A pre-existing
      file that cannot be parsed and validated raises without being
      overwritten. This makes a Streamlit rerun or a manual retry safe.
- [x] **No Gemini, configuration, export, network, or database coupling**:
      `src/audit.py` never imports `config`, `src.explanations`,
      `src.gemini_analyzer`, `src.exports`, `streamlit`, a Gemini SDK, or
      any network/database client — structurally guaranteed via
      AST-based isolation tests. An audit record contains only the
      locked deterministic result, the human decision, an audit
      identifier, and a timestamp.
- [x] `app.py` (extended, not replaced) — audit persistence happens
      automatically from the same approve/reject click, not a separate
      confirmation action: create the decision → store it in
      `APPROVAL_DECISION_STATE_KEY` (finalized regardless of what happens
      next) → build the audit with the current UTC timestamp → persist it
      → store the outcome → rerun. A disk failure never reopens, erases,
      or allows replacement of the already-finalized decision.
- [x] **Exact session-state keys**: `AUDIT_RECORD_PATH_STATE_KEY =
      "audit_record_path"`, `AUDIT_RECORD_ERROR_STATE_KEY =
      "audit_record_error"`, both cleared at the start of every new
      deterministic-review submission alongside the existing
      locked-result, explanation, and approval state.
- [x] **Exact success rendering**: `st.success("Audit record written.")`
      plus a caption `Audit ID: {audit_id}` (the filename stem) — the
      full local filesystem path is never displayed anywhere.
- [x] **Exact failure rendering**: the finalized approval/rejection
      remains fully visible; `st.error("The decision was finalized, but
      its audit record could not be written.")` — no raw exception, stack
      trace, temporary filename, directory, or other filesystem detail is
      ever shown; exactly one `st.button("Retry audit recording",
      key="retry_audit_recording")`. Retry performs no new
      approval/rejection, reuses the already-finalized approval and
      locked result, builds with a new current UTC timestamp, relies on
      domain idempotency if the first write actually succeeded before the
      UI observed failure, and only runs when clicked — no automatic
      retry loop, and ordinary reruns never write again.
- [x] **One approved exception, narrower than Stage 32/33 — plus one
      additional authorized test-harness change**: `tests/test_app.py`'s
      `test_module_does_not_import_forbidden_modules` and
      `test_module_does_not_reference_forbidden_names`,
      `tests/test_app_explanation.py`'s `test_no_audit_or_export_imports`,
      and `tests/test_app_approval.py`'s
      `test_no_audit_export_or_platform_imports_in_app` were narrowed to
      permit `src.audit` only (`src.exports` remains forbidden and
      enforced everywhere). Separately, `tests/test_app_approval.py`'s
      `_fresh_app()` and `_unconserved_app()` helpers were converted from
      `AppTest.from_file` to `AppTest.from_string` with
      `app.record_campaign_reallocation_audit` redirected to an isolated
      OS temp directory embedded directly in the executed script — the
      only mechanism that reliably intercepts a real approve/reject
      click's now-automatic audit write, since `AppTest.from_file`
      executes in a namespace that does not honor an external
      monkeypatch of this function (confirmed empirically). All 34
      pre-existing Stage 33 UI tests and assertions are unchanged; only
      the harness plumbing changed, and no test in that file writes a
      real file under the repository's `audit_records/`.
- [x] `tests/test_audit.py` (populated for the first time — placeholder
      replaced) — 38 new Stage 34 domain tests, all passing. Covers exact
      model fields, `extra="forbid"`, frozen, aware-UTC timestamp
      acceptance, naive-timestamp rejection, non-UTC-aware normalization,
      the exact ID-mismatch and unconserved-approval error messages,
      rejected-unconserved acceptance, deterministic audit-ID
      construction (excluding `recorded_at`; changing with reviewer/note/
      result content), fixed-point `Decimal` preservation including
      trailing zeros and extreme values, enum/tuple/datetime
      preservation, byte-for-byte canonical-JSON determinism,
      missing-directory creation, successful `tmp_path` writes, identical
      and different-timestamp idempotent retries, conflicting- and
      malformed-existing-record rejection without overwrite,
      serialization/finalization-failure cleanup leaving no partial file,
      non-mutation of `result`/`approval`, isolation from Gemini/config/
      exports/network/database, and the absence of any public read/list/
      delete/export function.
- [x] `tests/test_app_audit.py` (new dedicated test file) — 21 new Stage
      34 UI tests, all passing, using `AppTest.from_string` with the
      audit-directory redirect embedded directly in each script and zero
      real network/filesystem/Gemini calls. Covers: an approved or
      rejected decision automatically creating exactly one record; the
      correct locked result and finalized approval reaching the builder;
      one click causing one persistence call; zero additional writes on
      ordinary and repeated reruns; the exact success message and audit
      ID (never the full path); a failed write leaving the decision fully
      finalized with the exact sanitized message, no raw exception, and
      exactly one retry control; retry performing no second approval
      call and clearing the error on success; no automatic retry on
      ordinary reruns; audit-state clearing on both a new valid and a
      new invalid submission; independence from Gemini explanation
      actions; and full deterministic-result visibility and non-mutation
      throughout. A file-scoped autouse fixture restores
      `app.build_campaign_reallocation_audit`,
      `app.record_campaign_reallocation_audit`, and the Stage 27/31/33
      functions to their real implementations before every test,
      mirroring the established defensive pattern against `AppTest`'s
      shared `sys.modules["app"]` singleton.
- [x] Stage 1–33 regression re-run and confirmed passing unchanged at
      `1588 passed`. Full suite: `1647 passed` (1588 + 38 + 21).
      Confirmed zero test-created files under the repository's real
      `audit_records/` directory (only the pre-existing `.gitkeep`
      remains) across every verification pass.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Explicitly Out of Scope for Stage 34 (and not yet started)

- CSV export generation (`src/exports.py`).
- Any public function to read, list, or enumerate audit records — Stage
  35's own responsibility, built on this stage's frozen schema and
  filename convention.
- The full AI/UI-inclusive end-to-end integration test
  (`tests/test_integration.py`, reserved, untouched).
- A database, cloud storage, user authentication, or electronic
  signature of any kind — audit storage remains local JSON on disk, per
  the frozen `DECISIONS.md` entry.
- Any guarantee of durability under ephemeral or multi-instance hosting
  — local-file persistence is correct for the project's current
  single-user, desktop-oriented scope, but does not survive a
  stateless/ephemeral cloud filesystem being wiped on redeploy, and
  remains a named Sprint 4 limitation, not a Stage 34 defect.

## Development Stage 35 — CSV Exports (complete)

- [x] `src/exports.py` (populated for the first time — placeholder
      replaced) — the CSV export of a successfully persisted
      `CampaignReallocationAudit`. Never rebuilds, rereads from disk, or
      recomputes anything; never accepts separate `result`/`approval`
      arguments; never calls any Stage 1–34 production function.
- [x] **Exact model**: `CampaignReallocationExportRow` (frozen,
      `extra="forbid"`, 26 fields — audit/approval/portfolio/conservation
      context plus one campaign's locked recommendation, all as `str`
      except `is_conserved: bool` and `reallocation_priority_score: int`).
- [x] **Exact functions**: `build_campaign_reallocation_export_rows(audit)
      -> tuple[CampaignReallocationExportRow, ...]` and
      `serialize_campaign_reallocation_export_csv(rows) -> str`. No
      other public model or function exists — no read/list/export-to-disk
      surface.
- [x] **One flat CSV, one row per campaign**, in `campaign_results`' own
      original order — never re-sorted by score, rank, ID, or name.
      Shared audit/approval/portfolio-total/conservation values are
      deliberately repeated on every row so each row is self-contained.
      No summary row, no multiple files, no `record_type` column. An
      audit with no campaigns produces a valid header-only CSV with the
      frozen 26-column header and zero data rows.
- [x] **Both `APPROVED` and `REJECTED` audits are exportable, identically.**
      For a rejected review, the CSV remains a factual record of the
      deterministic recommendations that were reviewed, together with the
      final rejection decision — rejection never deletes, relabels, or
      reinterprets them. A rejected, *unconserved* audit is also
      exportable (rejection has no conservation restriction, per Stage
      33's own frozen policy, unchanged here).
- [x] **Exact column order** (independent of Pydantic field-declaration
      order or dict ordering — the serializer uses one frozen
      `_EXPORT_COLUMNS` tuple): `audit_id, review_id, recorded_at,
      decision, reviewer_name, decision_note, total_current_budget,
      total_recommended_budget, total_increase_allocated,
      total_decrease_allocated, net_change, is_conserved, campaign_id,
      campaign_name, platform, current_budget, recommendation_action,
      allocated_amount, recommended_budget, reason_codes,
      performance_band, trend_direction, confidence, pacing_status,
      reallocation_priority_score, rank`.
- [x] **Exact serialization policy**: every `Decimal` via `format(value,
      "f")` — exact, fixed-point, never scientific notation, never routed
      through `float`; enums via `.value`; `recorded_at` (already
      UTC-normalized by the Stage 34 model) via `.isoformat()`;
      `rank=None` → `"Not ranked"`; `note=None` → `""`; `is_conserved`
      written as the raw Python `bool`, which `csv.writer` renders as the
      literal text `True`/`False`. Quoting/escaping of commas, quotes,
      embedded newlines, and Unicode is delegated entirely to Python's
      standard `csv` module.
- [x] **CSV formula-injection mitigation**: one private helper
      (`_neutralize_formula`) applied to `review_id`, `reviewer_name`,
      `decision_note`, `campaign_id`, and `campaign_name` — if a value's
      first non-whitespace character is `=`, `+`, `-`, or `@`, the
      complete original value is prefixed with a single apostrophe,
      preserving all original text and whitespace; idempotent, since an
      apostrophe is never itself a trigger character. Never applied to
      trusted enum/boolean/integer/hash/timestamp/Decimal-string values.
- [x] **No JSON export, no PDF, no Excel, no Google Sheets, no database
      export, no advertising-platform upload, no API submission, no ZIP/
      multi-file bundle.** The existing immutable JSON audit record
      (Stage 34) remains the sole JSON artifact — never duplicated as a
      second JSON "export."
- [x] **No local export persistence.** The CSV is generated entirely in
      memory and delivered via `st.download_button` — no `exports/`
      directory was created, `.gitignore` is unchanged, and no atomic
      export-file write exists, since there is no file to atomically
      write.
- [x] `app.py` (extended, not replaced) — a new "CSV export" section,
      rendered only once an audit record has actually been *persisted*
      (never merely built or merely approved), immediately after the
      human-approval section. One new session-state key,
      `AUDIT_RECORD_STATE_KEY = "audit_record"`, holds the exact,
      successfully-persisted `CampaignReallocationAudit` object itself —
      populated only after `record_campaign_reallocation_audit` actually
      succeeds inside `_attempt_audit_recording`, cleared to `None` at
      the start of every audit-recording attempt and at the start of
      every new deterministic submission. The export section consumes
      exactly this stored object; it is never rebuilt from a separate
      result/approval pair and never re-read from disk.
- [x] **Exact download button**: label `"Download audited recommendations
      CSV"`, `file_name=f"{audit.audit_id}.csv"`, `mime="text/csv"`. No
      separate "Generate export" button and no retry control — generation
      is fully in-memory and deterministic, so there is nothing to retry.
- [x] **Exact failure message**: `"The CSV export could not be prepared.
      The finalized review and audit record remain unchanged."` — no raw
      exception, traceback, or absolute path is ever shown; a failure
      never mutates the locked result, the approval, or the audit object,
      never rewrites the audit record, never calls Gemini, and never
      reruns the deterministic pipeline.
- [x] **One approved exception, narrower than every prior stage — one of
      the three narrowed assertions is now vacuous.**
      `tests/test_app.py`'s `test_module_does_not_import_forbidden_modules`
      was narrowed to remove only `src.exports`. `tests/test_app_explanation.py`'s
      `test_no_audit_or_export_imports` and `tests/test_app_approval.py`'s
      `test_no_audit_export_or_platform_imports_in_app` were also narrowed
      to remove `src.exports` — the sole remaining member of each of
      their forbidden sets — so both assertions are now `isdisjoint(set())`,
      a faithful record that every module they originally guarded against
      (`src.approval`, `src.audit`, `src.exports`) is now a legitimate,
      separately-covered import of `app.py`. The bare-name
      `test_module_does_not_reference_forbidden_names` narrowing was
      **not** needed — no bare `exports` identifier exists anywhere in
      `app.py`'s AST. Every Gemini, network, database, secret, and
      deterministic-engine isolation assertion in all three files is
      unchanged and still enforced.
- [x] `tests/test_exports.py` (new — no placeholder existed) — 40 new
      Stage 35 domain tests, all passing. Covers exact model fields,
      `extra="forbid"`, frozen, exact function signatures, exact column
      order, header-only CSV for an empty campaign tuple, approved and
      rejected audits (including a rejected, unconserved audit), exact
      audit/approval/portfolio field copying, exact campaign field
      copying, preserved campaign and reason-code order, `rank=None` →
      `"Not ranked"`, `note=None` → `""`, exact `Decimal` fixed-point
      formatting (trailing zeros, extreme precision, no scientific
      notation), exact UTC ISO timestamp, deterministic repeated builds/
      serialization, special characters (commas, quotes, embedded
      newlines, backslashes, Markdown-like content, Unicode) round-tripped
      through `csv.DictReader`, CSV formula-injection neutralization for
      all four trigger characters (including after leading whitespace,
      safe text unchanged, empty text unchanged, and no double-
      neutralization), exact `is_conserved` Boolean text, non-mutation of
      the input audit, and isolation from `float`, the filesystem, the
      network, Gemini/config/secrets, and every Stage 1–34 production
      function.
- [x] `tests/test_app_exports.py` (new dedicated test file) — 20 new
      Stage 35 UI tests, all passing, using `AppTest.from_string` with the
      established Stage 34 audit-directory redirect embedded directly in
      each script and zero real network/filesystem/Gemini calls. Covers:
      the export section absent without a locked result, before a
      decision, and while audit recording has failed; present only once
      persistence actually succeeds, identically for approved and
      rejected audits; the exact download-button label; the exact literal
      `file_name`/`mime` arguments (verified via AST source inspection,
      since `AppTest` exposes no stable public accessor for a download
      button's underlying bytes/filename/MIME in this Streamlit version);
      the exact CSV content built from the exact stored audit object
      (verified via a capturing wrapper around the real Stage 35
      functions); deterministic, non-duplicated generation across
      reruns; a successful audit retry making the export appear;
      session-state clearing on both a new valid and a new invalid
      submission; sanitized failure rendering with no raw exception; no
      Gemini invocation and no pipeline rerun triggered by the export
      section; and no real audit/export file left behind.
- [x] Stage 1–34 regression re-run and confirmed passing unchanged at
      `1647 passed`. Full suite: `1707 passed` (1647 + 40 + 20). Confirmed
      zero test-created files under the repository's real `audit_records/`
      directory (only the pre-existing `.gitkeep` remains), and no
      `exports/` directory was ever created, across every verification
      pass.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Explicitly Out of Scope for Stage 35 (and not yet started)

- The full AI/UI-inclusive end-to-end integration test
  (`tests/test_integration.py`, reserved, untouched) — the final
  remaining Sprint 3 stage.
- A JSON export, PDF, Excel/XLSX, Google Sheets, database export,
  advertising-platform upload, or API submission of any kind.
- Reading, listing, or enumerating persisted audit records from
  `audit_records/` — no evidenced need in the current session-based UI
  flow; would be a future Stage 35-adjacent convenience, not implemented
  here.
- Any local export-file persistence, `exports/` directory, or
  `.gitignore` change — the CSV is generated entirely in memory and
  delivered via `st.download_button`.

## Development Stage 36 — Final End-to-End Integration and Sprint 3 Completion (complete)

- [x] `tests/test_integration.py` (populated for the first time — placeholder
      replaced) — 12 focused integration tests, all passing, proving the
      complete frozen Sprint 3 flow works together through real Streamlit
      `AppTest` widget interaction: CSV upload → review-setup validation →
      campaign validation → deterministic pipeline → locked result →
      optional Gemini explanation → human approval or rejection →
      immutable audit construction → successful audit persistence →
      audited CSV export availability. No production file and no existing
      Stage 1–35 test's *behavior* was changed — Stage 36 tests wiring and
      state flow only, never re-deriving any formula, validation rule, or
      serialization policy already owned by an earlier stage's own
      focused test file.
- [x] **`AppTest.from_string` exclusively** for every scenario that
      approves or rejects a review — never `AppTest.from_file`, which
      does not honor an external monkeypatch of a real approve/reject
      click's automatic Stage 34 audit write (confirmed empirically at
      Stage 34, reconfirmed here). Every embedded script redirects
      `app.record_campaign_reallocation_audit` to the test's own
      `tmp_path`, mirroring the established Stage 34/35 pattern verbatim.
- [x] **Zero real Gemini/network calls.** Two paths only: the genuine,
      network-free `UNAVAILABLE` path (real `generate_explanation`,
      `GEMINI_API_KEY` absent) and a deterministic fake `GENERATED` result
      patched onto `app.generate_explanation` from within the embedded
      script. No real Gemini SDK client is ever constructed; no real key
      is used, required, or created via a real `.env`.
- [x] **Approved flow** (Scenario A): the real sample data
      (`data/sample_campaigns.csv`) through the real deterministic
      pipeline, approved, audited, and exported — asserting the exact,
      independently-established stable sample contract (`total_current_budget`/
      `total_recommended_budget = 11700.00`, `is_conserved = True`,
      G001/M001/G003 `MAINTAIN`, G002 `INCREASE`/rank 1/zero-funded, exact
      reason codes) already proven by `tests/test_app.py` and
      `tests/test_app_explanation.py` against the same untouched data —
      never re-derived here. The captured real CSV (via the established
      Stage 35 capture-wrapper pattern, never mocked) is parsed with
      Python's standard `csv` module and checked field-by-field against
      the exact stored audit.
- [x] **Rejected flow** (Scenario B): rejection finalizes, the locked
      recommendations are provably unchanged (`model_dump()` snapshot
      equality), one audit JSON persists recording `REJECTED`, and every
      exported CSV row records `REJECTED` — with no reconsider/overwrite
      control anywhere and no advertising-platform action path existing
      in the codebase.
- [x] **Generated-explanation independence** (Scenario C): a fake
      `GENERATED` explanation renders, is labeled AI-generated/
      supplementary per the existing UI, costs exactly one fake call per
      click and zero on a bare rerun, never touches the locked result's
      `model_dump()`, and is structurally absent from both the persisted
      audit JSON and the exported CSV — approval, audit, and export all
      continue to work normally afterward.
- [x] **Gemini-unavailable independence** (Scenario D): the real,
      network-free `UNAVAILABLE` result does not block approval, audit
      persistence, or CSV export.
- [x] **Unconserved-result gating** (Scenario E), injected via the
      established test-fixture pipeline-wrapping pattern with no
      production code touched: approval is blocked with the exact
      existing conservation error, rejection remains allowed and
      finalizes, the rejected audit persists, and the exported CSV
      records both `REJECTED` and `is_conserved=False` — nothing repaired,
      rebalanced, recalculated, or rerun.
- [x] **Audit failure then retry** (Scenario F): a first failed
      audit-persistence attempt leaves the decision finalized with the
      exact sanitized error (no raw path/traceback) and no export
      control; retry succeeds through the real redirected recorder,
      leaving exactly one audit JSON and the export control appearing
      only after success; the locked result and approval are unchanged
      across the failure and the retry.
- [x] **Validation-blocking flows** (Scenarios G, H): an invalid
      `ReviewSetup` and a mixed valid/invalid CSV both block the pipeline
      entirely — no locked result, no explanation/approval/audit/export
      state, and no audit JSON written — without duplicating every
      individual validation rule already owned by `tests/test_validation.py`.
- [x] **State-reset and rerun stability** (Scenarios I, J): a new valid
      submission clears every downstream state key while establishing a
      fresh locked result; a new invalid submission clears them with no
      replacement result; a bare rerun after a completed cycle leaves the
      locked result, explanation, approval, audit path, stored audit
      object, and captured CSV all byte-identical, with zero additional
      pipeline, Gemini, or audit-persistence calls.
- [x] **Cross-cutting security/artifact sweep**: a synthetic fake API key
      never appears in any rendered element, session-state value, the
      persisted audit JSON, or the exported CSV; fake explanation text is
      absent from both the audit JSON and the CSV; the real repository
      `audit_records/` directory is confirmed unchanged before and after
      the full scenario set; no `exports/` directory or other unexpected
      repository entry is ever created.
- [x] **One additional defensive isolation fixture, scoped entirely to
      `tests/test_integration.py` itself — no other file touched for this
      purpose.** `tests/test_gemini_analyzer.py`'s own
      `test_import_performs_no_client_construction_environment_or_network`
      pops `src.gemini_analyzer` from `sys.modules` and reimports it fresh
      to prove import-time side-effect freedom, leaving a *different*
      `ExplanationStatus` class installed under that name for the rest of
      the process — silently breaking `app.py`'s own already-cached `is
      ExplanationStatus.GENERATED` identity check for any fake explanation
      built after that test runs, with the failure surfacing deep inside
      rendering rather than at the click boundary's own exception
      handling. An autouse fixture restores `sys.modules["src.gemini_analyzer"]`
      to the original module object (captured at this file's own
      import/collection time) before and after every test in this file,
      regardless of order — a defensive addition entirely within the one
      authorized new test file, not a change to
      `tests/test_gemini_analyzer.py` or any other existing test.
- [x] **One approved exception, retiring four now-obsolete guard
      assertions.** `tests/test_app.py`'s `test_test_integration_remains_untouched`,
      and `tests/test_app_explanation.py`'s, `tests/test_config.py`'s, and
      `tests/test_explanations.py`'s respective
      `test_test_integration_remains_unchanged` each asserted that
      `tests/test_integration.py` contained zero function/class
      definitions — a sentinel guarding against premature implementation
      before Stage 36. Stage 36 has now legitimately populated that file
      with the final integration suite, making the guard's condition
      permanently false by design; per explicit approval, all four were
      retired (removed, with an explanatory comment pointing to
      `tests/test_integration.py` for that stage's own coverage) rather
      than replaced with a different check. This is the only respect in
      which the regression count below differs from a simple stage-over-
      stage sum: `1707` (Stage 1–35 baseline) minus these 4 retired tests
      equals the `1703` reported below. No other assertion in any of the
      four files was touched.
- [x] Stage 1–35 regression (`tests/ --ignore=tests/test_integration.py`,
      which also reflects the four retired guard tests) re-run and
      confirmed passing at `1703 passed`. Full suite: `1715 passed`
      (1703 + 12). Confirmed zero test-created files under the
      repository's real `audit_records/` directory (only the pre-existing
      `.gitkeep` remains), no `exports/` directory ever created, and no
      real `.env` ever created, across every verification pass.
- [x] `docs/DATA_DICTIONARY.md`, `docs/DECISION_RULES.md`,
      `docs/TEST_SCENARIOS.md` updated.

## Sprint 3 — Explanation, Approval, and Interface: Complete

Every frozen exit criterion in `MASTER_PROJECT_PLAN.md`'s Sprint 3 section is now
satisfied and demonstrated together by Stage 36's own integration suite, not merely by the
sum of each stage's separate focused tests:

- *"End-to-end flow works: upload → validate → assess → recommend → lock → explain
  (Gemini) → approve/reject → audit record written → CSV export available."* — proven by
  Scenarios A and B end-to-end, using the real sample data and the real deterministic
  pipeline.
- *"Gemini is verifiably confined to explanation of locked numbers; no path exists by which
  it can alter recommendations or touch live advertising-platform budgets."* — proven by
  Scenario C's immutability snapshot and the structural absence of any Gemini-writable path
  anywhere in the codebase.
- *"Every approval or rejection produces a traceable JSON audit record."* — proven by every
  approving/rejecting scenario (A, B, E, F), including the unconserved-rejection and
  failure/retry cases.

## Next Sprint

**Sprint 3 is complete. Sprint 4 — Hardening and Documentation is next and has not yet
started.** Per `MASTER_PROJECT_PLAN.md`'s Sprint 4 scope: full test coverage review
including adversarial/edge-case CSV inputs; finalizing `docs/ARCHITECTURE.md` and
`docs/LIMITATIONS.md` (both remain untouched placeholders, deliberately deferred through
every Sprint 3 stage); a review of the human-in-the-loop boundary and audit-trail
completeness; and general cleanup and packaging. The remaining `ReasonCode` members'
trigger conditions (see Stage 27's Explicitly-Out-of-Scope list above) remain open and
belong to this sprint.
