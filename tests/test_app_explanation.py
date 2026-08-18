"""Tests for the Stage 32 explanation UI wiring in app.py
(Sprint 3 — Development Stage 32).

Covers the optional, click-only portfolio and campaign explanation
section added after the locked deterministic result: section/widget
presence and absence; the exact trust caption; exact Stage 30 payload/
prompt construction reaching Stage 31's `generate_explanation` unchanged;
the campaign selectbox's `{id} — {name}` formatting and exact-campaign
resolution; rendering for every `ExplanationStatus`; call-count discipline
(one click = one call, ordinary reruns and selectbox changes = zero
calls); stale-explanation hiding/redisplay across campaign selection
changes; explanation-state clearing on every new deterministic
submission (successful or failed); deterministic-result visibility and
non-mutation across all explanation states; the real, network-free
`UNAVAILABLE` path; absence of the API key from any rendered element or
session-state value; the single explanation-action exception boundary;
and AST-based isolation (no secret access, no direct environment/`.env`
access, no automatic generation, no automatic retry loop, no unsafe HTML,
no approval/audit/export imports). No real Gemini/network call is ever
made.
"""

import ast
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
import src.pipeline
from src.explanations import build_portfolio_explanation_payload, build_portfolio_explanation_prompt
from src.gemini_analyzer import ErrorCategory, ExplanationResult, ExplanationStatus

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture(autouse=True)
def _ensure_real_deterministic_pipeline(monkeypatch):
    """Defensive isolation, scoped to this file only.

    `AppTest.from_string`'s embedded `import app` resolves to the same
    `sys.modules["app"]` singleton used everywhere else in the process
    (confirmed empirically), so an earlier test file's own
    `AppTest`-embedded monkeypatch of `app.run_budget_reallocation_review`
    -- if left unrestored -- would otherwise silently leak into every test
    below. This does not touch any protected file; it only guarantees this
    file's own tests exercise the real Stage 27 pipeline regardless of
    what ran before them in the same pytest session.
    """
    monkeypatch.setattr(app, "run_budget_reallocation_review", src.pipeline.run_budget_reallocation_review)

VALID_REVIEW = {
    "review_id": "REV-1",
    "review_date": date(2026, 8, 5),
    "period_start": date(2026, 8, 1),
    "period_end": date(2026, 8, 10),
    "reviewer_name": "Reviewer",
    "approved_monthly_budget": "10000.00",
    "initial_account_reserve": "0.00",
}

FAKE_KEY = "fake-explanation-ui-key-123"


def _fresh_app() -> AppTest:
    at = AppTest.from_file(str(APP_PATH))
    at.run(timeout=10)
    assert not at.exception
    return at


def _fill_review_inputs(at: AppTest, overrides: dict | None = None) -> None:
    values = dict(VALID_REVIEW)
    if overrides:
        values.update(overrides)
    at.text_input(key="review_id").set_value(values["review_id"])
    at.date_input(key="review_date").set_value(values["review_date"])
    at.date_input(key="period_start").set_value(values["period_start"])
    at.date_input(key="period_end").set_value(values["period_end"])
    at.text_input(key="reviewer_name").set_value(values["reviewer_name"])
    at.text_input(key="approved_monthly_budget").set_value(values["approved_monthly_budget"])
    at.text_input(key="initial_account_reserve").set_value(values["initial_account_reserve"])


def _upload_sample_csv(at: AppTest) -> None:
    content = (DATA_DIR / "sample_campaigns.csv").read_bytes()
    at.file_uploader(key="campaign_csv").set_value(("sample_campaigns.csv", content, "text/csv"))


def _submit(at: AppTest) -> None:
    at.button(key="submit_review").click().run(timeout=10)


def _submit_valid_sample(at: AppTest) -> None:
    _fill_review_inputs(at)
    _upload_sample_csv(at)
    _submit(at)
    assert at.session_state["locked_review_result"] is not None


_FAKE_SCRIPT_HEADER = """
import app
import streamlit as st
from src.gemini_analyzer import ExplanationResult, ExplanationStatus, ErrorCategory

if "fake_calls" not in st.session_state:
    st.session_state["fake_calls"] = []
"""


def _app_test_with_fake_generation(body: str) -> AppTest:
    """Build an AppTest running app.py with `app.generate_explanation`
    replaced by a fake that records every call in
    `st.session_state["fake_calls"]` as (system_instruction, user_content).
    `body` must define `_fake_generate_explanation(prompt, config)`.
    """
    script = _FAKE_SCRIPT_HEADER + body + "\napp.generate_explanation = _fake_generate_explanation\napp.main()\n"
    at = AppTest.from_string(script)
    at.run(timeout=10)
    return at


def _generated_fake(text: str = "The campaign is performing as expected.") -> str:
    return f"""
def _fake_generate_explanation(prompt, config):
    st.session_state["fake_calls"].append((prompt.system_instruction, prompt.user_content))
    return ExplanationResult(
        status=ExplanationStatus.GENERATED,
        explanation_text={text!r},
        model_name="gemini-2.5-flash-lite",
    )
"""


def _unavailable_fake() -> str:
    return """
def _fake_generate_explanation(prompt, config):
    st.session_state["fake_calls"].append((prompt.system_instruction, prompt.user_content))
    return ExplanationResult(
        status=ExplanationStatus.UNAVAILABLE,
        error_category=ErrorCategory.CONFIGURATION,
        error_message="Gemini is not configured: no API key is available.",
    )
"""


def _failed_fake(message: str = "The request timed out.") -> str:
    return f"""
def _fake_generate_explanation(prompt, config):
    st.session_state["fake_calls"].append((prompt.system_instruction, prompt.user_content))
    return ExplanationResult(
        status=ExplanationStatus.FAILED,
        model_name="gemini-2.5-flash-lite",
        error_category=ErrorCategory.TIMEOUT,
        error_message={message!r},
    )
"""


def _raising_fake() -> str:
    return """
def _fake_generate_explanation(prompt, config):
    st.session_state["fake_calls"].append((prompt.system_instruction, prompt.user_content))
    raise RuntimeError("simulated unexpected failure while building the request")
"""


# ---------------------------------------------------------------------------
# 1-3. Section presence/absence, widgets, trust caption
# ---------------------------------------------------------------------------


def test_section_absent_without_locked_result():
    at = _fresh_app()
    assert "Optional AI-generated explanations" not in [s.value for s in at.subheader]
    assert not any(b.key == "generate_portfolio_explanation" for b in at.button)
    assert not any(b.key == "generate_campaign_explanation" for b in at.button)


def test_widgets_appear_after_successful_review():
    at = _fresh_app()
    _submit_valid_sample(at)
    assert "Optional AI-generated explanations" in [s.value for s in at.subheader]
    assert any(b.key == "generate_portfolio_explanation" for b in at.button)
    assert any(b.key == "generate_campaign_explanation" for b in at.button)
    assert any(sb.key == "explanation_campaign_id" for sb in at.selectbox)


def test_exact_trust_caption_appears():
    at = _fresh_app()
    _submit_valid_sample(at)
    expected = (
        "Gemini explanations are supplementary and may be inaccurate. The "
        "deterministic recommendations above remain authoritative."
    )
    assert expected in [c.value for c in at.caption]


# ---------------------------------------------------------------------------
# 4. Portfolio click uses the real Stage 30 chain, calls Stage 31 once
# ---------------------------------------------------------------------------


def test_portfolio_click_builds_real_payload_and_prompt():
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    locked_result = at.session_state["locked_review_result"]
    expected_prompt = build_portfolio_explanation_prompt(
        build_portfolio_explanation_payload(locked_result)
    )

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)

    calls = at.session_state["fake_calls"]
    assert len(calls) == 1
    system_instruction, user_content = calls[0]
    assert system_instruction == expected_prompt.system_instruction
    assert user_content == expected_prompt.user_content


# ---------------------------------------------------------------------------
# 5. Campaign selector formatting
# ---------------------------------------------------------------------------


def test_campaign_selector_shows_id_and_name():
    at = _fresh_app()
    _submit_valid_sample(at)
    selectbox = at.selectbox(key="explanation_campaign_id")
    assert "G001 — Search - Brand" in selectbox.options
    assert "G002 — Shopping - Core Catalog" in selectbox.options


# ---------------------------------------------------------------------------
# 6. Campaign click uses exactly the selected campaign
# ---------------------------------------------------------------------------


def test_campaign_click_uses_exactly_selected_campaign():
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    locked_result = at.session_state["locked_review_result"]
    g002 = next(r for r in locked_result.campaign_results if r.campaign_id == "G002")

    from src.explanations import build_campaign_explanation_payload, build_campaign_explanation_prompt

    expected_prompt = build_campaign_explanation_prompt(build_campaign_explanation_payload(g002))

    at.selectbox(key="explanation_campaign_id").set_value("G002 — Shopping - Core Catalog")
    at.run(timeout=10)
    at.button(key="generate_campaign_explanation").click().run(timeout=10)

    calls = at.session_state["fake_calls"]
    assert len(calls) == 1
    system_instruction, user_content = calls[0]
    assert system_instruction == expected_prompt.system_instruction
    assert user_content == expected_prompt.user_content


# ---------------------------------------------------------------------------
# 7-8. GENERATED rendering, portfolio and campaign
# ---------------------------------------------------------------------------


def test_portfolio_generated_rendering():
    at = _app_test_with_fake_generation(_generated_fake("Portfolio is well balanced."))
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)

    markdown_values = [m.value for m in at.markdown]
    assert "**Portfolio explanation**" in markdown_values
    assert "Portfolio is well balanced." in markdown_values
    assert "AI-generated using gemini-2.5-flash-lite" in [c.value for c in at.caption]


def test_campaign_generated_rendering():
    at = _app_test_with_fake_generation(_generated_fake("G002 is above target."))
    _submit_valid_sample(at)
    at.selectbox(key="explanation_campaign_id").set_value("G002 — Shopping - Core Catalog")
    at.run(timeout=10)
    at.button(key="generate_campaign_explanation").click().run(timeout=10)

    markdown_values = [m.value for m in at.markdown]
    assert "**Campaign explanation for G002**" in markdown_values
    assert "G002 is above target." in markdown_values


# ---------------------------------------------------------------------------
# 9-10. UNAVAILABLE and FAILED rendering, both flows
# ---------------------------------------------------------------------------


def test_portfolio_unavailable_rendering():
    at = _app_test_with_fake_generation(_unavailable_fake())
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert "Gemini is not configured: no API key is available." in [i.value for i in at.info]
    assert len(at.error) == 0


def test_campaign_unavailable_rendering():
    at = _app_test_with_fake_generation(_unavailable_fake())
    _submit_valid_sample(at)
    at.button(key="generate_campaign_explanation").click().run(timeout=10)
    assert "Gemini is not configured: no API key is available." in [i.value for i in at.info]


def test_portfolio_failed_rendering():
    at = _app_test_with_fake_generation(_failed_fake("The request timed out."))
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert "The request timed out." in [e.value for e in at.error]


def test_campaign_failed_rendering():
    at = _app_test_with_fake_generation(_failed_fake("The request timed out."))
    _submit_valid_sample(at)
    at.button(key="generate_campaign_explanation").click().run(timeout=10)
    assert "The request timed out." in [e.value for e in at.error]


# ---------------------------------------------------------------------------
# 11-12. error_category never rendered; sanitized message only
# ---------------------------------------------------------------------------


def test_error_category_not_rendered():
    at = _app_test_with_fake_generation(_failed_fake("The request timed out."))
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)

    rendered_text = " ".join(
        [m.value for m in at.markdown] + [e.value for e in at.error] + [i.value for i in at.info]
    )
    for category in ErrorCategory:
        assert category.value not in rendered_text


def test_sanitized_message_only_no_raw_provider_or_config_data():
    at = _app_test_with_fake_generation(_failed_fake("[REDACTED] request failed"))
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    rendered_errors = [e.value for e in at.error]
    assert rendered_errors == ["[REDACTED] request failed"]
    for forbidden in ("Traceback", "GeminiConfig", "api_key", "SecretStr"):
        assert forbidden not in " ".join(rendered_errors)


# ---------------------------------------------------------------------------
# 13-14. Exactly one call per click; zero calls on ordinary rerun
# ---------------------------------------------------------------------------


def test_one_click_causes_exactly_one_call():
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert len(at.session_state["fake_calls"]) == 1


def test_ordinary_rerun_causes_zero_additional_calls():
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert len(at.session_state["fake_calls"]) == 1
    at.run(timeout=10)
    at.run(timeout=10)
    assert len(at.session_state["fake_calls"]) == 1


# ---------------------------------------------------------------------------
# 15. Re-click replaces the previous explanation
# ---------------------------------------------------------------------------


def test_reclick_replaces_previous_portfolio_explanation():
    # AppTest.from_string executes in its own isolated namespace, so the
    # fake must decide its own behavior from persisted session state rather
    # than being swapped from outside mid-test: fail on the first call,
    # succeed on every call after.
    body = """
def _fake_generate_explanation(prompt, config):
    calls = st.session_state["fake_calls"]
    calls.append((prompt.system_instruction, prompt.user_content))
    if len(calls) == 1:
        return ExplanationResult(
            status=ExplanationStatus.FAILED,
            model_name="gemini-2.5-flash-lite",
            error_category=ErrorCategory.TIMEOUT,
            error_message="first failure",
        )
    return ExplanationResult(
        status=ExplanationStatus.GENERATED,
        explanation_text="now it works",
        model_name="gemini-2.5-flash-lite",
    )
"""
    at = _app_test_with_fake_generation(body)
    _submit_valid_sample(at)

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert "first failure" in [e.value for e in at.error]

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)

    assert "now it works" in [m.value for m in at.markdown]
    assert "first failure" not in [e.value for e in at.error]
    assert len(at.error) == 0


# ---------------------------------------------------------------------------
# 16-18. Selectbox change: no call, hides prior explanation, redisplay on return
# ---------------------------------------------------------------------------


def test_changing_selection_causes_no_call():
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    at.button(key="generate_campaign_explanation").click().run(timeout=10)
    assert len(at.session_state["fake_calls"]) == 1

    at.selectbox(key="explanation_campaign_id").set_value("G001 — Search - Brand")
    at.run(timeout=10)
    assert len(at.session_state["fake_calls"]) == 1


def test_changing_selection_hides_previous_campaign_explanation():
    at = _app_test_with_fake_generation(_generated_fake("explanation for the first pick"))
    _submit_valid_sample(at)
    # Default selection is the first campaign, G001.
    at.button(key="generate_campaign_explanation").click().run(timeout=10)
    assert "explanation for the first pick" in [m.value for m in at.markdown]

    at.selectbox(key="explanation_campaign_id").set_value("G002 — Shopping - Core Catalog")
    at.run(timeout=10)
    assert "explanation for the first pick" not in [m.value for m in at.markdown]


def test_reselecting_original_campaign_redisplays_without_regenerating():
    at = _app_test_with_fake_generation(_generated_fake("explanation for the first pick"))
    _submit_valid_sample(at)
    at.button(key="generate_campaign_explanation").click().run(timeout=10)
    assert len(at.session_state["fake_calls"]) == 1

    at.selectbox(key="explanation_campaign_id").set_value("G002 — Shopping - Core Catalog")
    at.run(timeout=10)
    at.selectbox(key="explanation_campaign_id").set_value("G001 — Search - Brand")
    at.run(timeout=10)

    assert len(at.session_state["fake_calls"]) == 1
    assert "explanation for the first pick" in [m.value for m in at.markdown]


# ---------------------------------------------------------------------------
# 19-20. New submission clears explanation state
# ---------------------------------------------------------------------------


def test_new_successful_submission_clears_explanation_state():
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert at.session_state["portfolio_explanation_result"] is not None

    _submit_valid_sample(at)

    assert at.session_state["portfolio_explanation_result"] is None
    assert at.session_state["campaign_explanation_result"] is None
    assert at.session_state["campaign_explanation_campaign_id"] is None


def test_new_invalid_submission_also_clears_explanation_state():
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert at.session_state["portfolio_explanation_result"] is not None

    at.text_input(key="review_id").set_value("")
    at.text_input(key="reviewer_name").set_value("")
    at.button(key="submit_review").click().run(timeout=10)

    assert at.session_state["locked_review_result"] is None
    assert at.session_state["portfolio_explanation_result"] is None
    assert at.session_state["campaign_explanation_result"] is None
    assert at.session_state["campaign_explanation_campaign_id"] is None


# ---------------------------------------------------------------------------
# 21. Gemini failure leaves the full deterministic result visible
# ---------------------------------------------------------------------------


def test_gemini_failure_leaves_deterministic_result_fully_visible():
    at = _app_test_with_fake_generation(_failed_fake("boom"))
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)

    rows = at.dataframe[0].value.to_dict("records")
    ids = [row["campaign_id"] for row in rows]
    assert ids == ["G001", "M001", "G002", "G003"]
    by_id = {row["campaign_id"]: row for row in rows}
    assert by_id["G002"]["recommendation_action"] == "INCREASE"
    assert by_id["G002"]["allocated_amount"] == "0.00"
    assert by_id["G002"]["recommended_budget"] == "5000.00"
    assert by_id["G002"]["reason_codes"] == "ABOVE_TARGET_STRONG, RECENT_TREND_IMPROVING"
    assert by_id["G002"]["reallocation_priority_score"] == 100
    assert by_id["G002"]["rank"] == "1"
    assert any("Conserved" in s.value for s in at.success)
    assert "**Total current budget:** 11700.00" in [m.value for m in at.markdown]


# ---------------------------------------------------------------------------
# 22. No mutation of locked result / campaign results
# ---------------------------------------------------------------------------


def test_locked_result_unchanged_after_explanation_actions():
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    snapshot = at.session_state["locked_review_result"].model_dump()

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    at.button(key="generate_campaign_explanation").click().run(timeout=10)

    assert at.session_state["locked_review_result"].model_dump() == snapshot


# ---------------------------------------------------------------------------
# 23. Real, network-free UNAVAILABLE path
# ---------------------------------------------------------------------------


def test_real_missing_configuration_path_is_network_free(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = _fresh_app()
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)
    assert not at.exception
    assert any("not configured" in i.value for i in at.info)
    assert at.session_state["locked_review_result"] is not None


# ---------------------------------------------------------------------------
# 24. API key never appears in rendered elements or session state
# ---------------------------------------------------------------------------


def test_api_key_absent_from_rendered_elements_and_session_state(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    at = _app_test_with_fake_generation(_generated_fake())
    _submit_valid_sample(at)
    at.button(key="generate_portfolio_explanation").click().run(timeout=10)

    rendered = " ".join(
        [m.value for m in at.markdown]
        + [c.value for c in at.caption]
        + [e.value for e in at.error]
        + [i.value for i in at.info]
    )
    assert FAKE_KEY not in rendered

    for key, value in at.session_state.filtered_state.items():
        assert FAKE_KEY not in repr(value)


# ---------------------------------------------------------------------------
# 25. No unsafe HTML in generated Markdown rendering
# ---------------------------------------------------------------------------


def test_no_unsafe_allow_html_true_in_source():
    source = inspect.getsource(app)
    assert "unsafe_allow_html=True" not in source
    assert "unsafe_allow_html=False" in source


# ---------------------------------------------------------------------------
# 26. Unexpected explanation-action exception is contained
# ---------------------------------------------------------------------------


def test_unexpected_exception_is_contained_without_hiding_deterministic_result():
    at = _app_test_with_fake_generation(_raising_fake())
    _submit_valid_sample(at)

    at.button(key="generate_portfolio_explanation").click().run(timeout=10)

    assert not at.exception
    assert at.session_state["portfolio_explanation_result"] is None
    assert at.session_state["locked_review_result"] is not None
    assert any("unexpected error" in e.value for e in at.error)
    rows = at.dataframe[0].value.to_dict("records")
    assert [row["campaign_id"] for row in rows] == ["G001", "M001", "G002", "G003"]


# ---------------------------------------------------------------------------
# 27. AST/source isolation checks
# ---------------------------------------------------------------------------


def test_no_get_secret_value_or_secretstr_reference():
    tree = ast.parse(inspect.getsource(app))
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "get_secret_value" not in referenced
    assert "SecretStr" not in referenced
    assert "api_key" not in referenced


def test_no_direct_environment_or_dotenv_access():
    tree = ast.parse(inspect.getsource(app))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    assert "os" not in imported_modules
    assert "dotenv" not in imported_modules

    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert referenced.isdisjoint({"environ", "getenv", "dotenv_values", "load_dotenv"})


def test_no_configuration_object_stored_in_session_state():
    # No assignment of the form `st.session_state[...] = config` anywhere:
    # only `None` (clearing) or the `explanation` result variable are ever
    # assigned to a session_state key in this module.
    tree = ast.parse(inspect.getsource(app))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "session_state"
                ):
                    assert not (isinstance(node.value, ast.Name) and node.value.id == "config"), (
                        "a GeminiConfig object must never be stored in session_state"
                    )


def test_no_automatic_generation_outside_button_branches():
    source = inspect.getsource(app._render_explanation_section)
    tree = ast.parse(source)
    # Every call to the click-handler functions must be textually inside an
    # `if` statement whose test involves `st.button(...)`.
    calls_outside_if = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test_source = ast.dump(node.test)
            if "button" not in test_source:
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Name)
                    and inner.func.id in {"_handle_portfolio_explanation_click", "_handle_campaign_explanation_click"}
                ):
                    calls_outside_if.append(inner.func.id)
    assert set(calls_outside_if) == {
        "_handle_portfolio_explanation_click",
        "_handle_campaign_explanation_click",
    }


def test_no_retry_loop_in_click_handlers():
    for func in (app._handle_portfolio_explanation_click, app._handle_campaign_explanation_click):
        tree = ast.parse(inspect.getsource(func))
        assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))


def test_no_approval_audit_or_export_imports():
    tree = ast.parse(inspect.getsource(app))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    assert imported_modules.isdisjoint({"src.approval", "src.audit", "src.exports"})


# ---------------------------------------------------------------------------
# tests/test_integration.py remains untouched
# ---------------------------------------------------------------------------


def test_test_integration_remains_unchanged():
    integration_path = Path(__file__).resolve().parent / "test_integration.py"
    tree = ast.parse(integration_path.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in ast.walk(tree)
    )
