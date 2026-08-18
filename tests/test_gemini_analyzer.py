"""Tests for src.gemini_analyzer (Sprint 3 — Development Stage 31).

Covers `ExplanationStatus`/`ErrorCategory`/`ExplanationResult` (exact
schema, `extra="forbid"`, frozen, and every state-consistency invariant);
the single public `generate_explanation` function (exact signature,
prompt/config-only input boundary); the availability pre-flight guard
(zero client construction and zero invocation when unavailable); a real
Stage 27 -> Stage 30 sample-data success path through an injected fake
client with exact request-forwarding verification; injected-vs-owned
client lifecycle (never closing an injected client, always closing an
internally-created one, via a patched internal factory); every frozen
failure-category mapping with exactly-one-invocation (no retry)
verification; synthetic-key redaction through the owned-client path; no
raw provider response retention; no mutation of locked inputs; import-time
side-effect freedom; and AST-based isolation (single `get_secret_value()`
call site, no logging/print, no locked-result/approval/audit/Streamlit/
legacy-SDK references, no module-level singleton, no retry loop). No real
network call or live SDK client is ever used.
"""

import ast
import importlib
import inspect
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from google.genai import types
from google.genai.errors import ClientError, ServerError
from pydantic import SecretStr, ValidationError

import src.gemini_analyzer as gemini_analyzer
from config import GeminiConfig
from src.classification import PerformanceBand, TrendDirection
from src.constants import Confidence, Platform, ReasonCode, RecommendationAction
from src.explanations import build_campaign_explanation_payload, build_campaign_explanation_prompt
from src.gemini_analyzer import ErrorCategory, ExplanationResult, ExplanationStatus, generate_explanation
from src.models import ReviewSetup
from src.pacing import PacingStatus
from src.pipeline import CampaignBudgetRecommendationResult, run_budget_reallocation_review
from src.validation import validate_campaign_csv

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FAKE_KEY = "fake-gemini-key-do-not-use-abc123"


@pytest.fixture(autouse=True)
def _clean_gemini_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _campaign_result(**overrides) -> CampaignBudgetRecommendationResult:
    kwargs = dict(
        campaign_id="C001",
        campaign_name="Test Campaign",
        platform=Platform.GOOGLE_ADS,
        current_budget=Decimal("1000.00"),
        recommendation_action=RecommendationAction.MAINTAIN,
        allocated_amount=Decimal("0.00"),
        recommended_budget=Decimal("1000.00"),
        reason_codes=(ReasonCode.NEAR_TARGET, ReasonCode.RECENT_TREND_STABLE),
        performance_band=PerformanceBand.ON_TARGET,
        trend_direction=TrendDirection.STABLE,
        confidence=Confidence.HIGH,
        pacing_status=PacingStatus.ON_PACE,
        reallocation_priority_score=0,
        rank=None,
    )
    kwargs.update(overrides)
    return CampaignBudgetRecommendationResult(**kwargs)


def _real_sample_campaign() -> CampaignBudgetRecommendationResult:
    review = ReviewSetup(
        review_id="REV-1",
        review_date=date(2026, 8, 5),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 10),
        reviewer_name="Reviewer",
        approved_monthly_budget=Decimal("10000.00"),
        initial_account_reserve=Decimal("0.00"),
    )
    with open(DATA_DIR / "sample_campaigns.csv", newline="", encoding="utf-8") as f:
        report = validate_campaign_csv(f)
    assert report.is_valid is True
    result = run_budget_reallocation_review(review, tuple(report.valid_campaigns))
    return next(r for r in result.campaign_results if r.campaign_id == "G002")


def _prompt_for(campaign: CampaignBudgetRecommendationResult):
    return build_campaign_explanation_prompt(build_campaign_explanation_payload(campaign))


class _FakeModels:
    def __init__(self, response=None, exc: Exception | None = None):
        self._response = response
        self._exc = exc
        self.calls: list[dict] = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._exc is not None:
            raise self._exc
        return self._response


class _FakeClient:
    def __init__(self, response=None, exc: Exception | None = None):
        self.models = _FakeModels(response=response, exc=exc)
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


class _FakeResponse:
    def __init__(self, text=None, candidates=None, prompt_feedback=None):
        self.text = text
        self.candidates = candidates if candidates is not None else []
        self.prompt_feedback = prompt_feedback


class _FakeCandidate:
    def __init__(self, finish_reason):
        self.finish_reason = finish_reason


class _RaisingTextResponse:
    candidates: list = []
    prompt_feedback = None

    @property
    def text(self):
        raise TypeError("simulated malformed response")


def _available_config(key: str = FAKE_KEY) -> GeminiConfig:
    return GeminiConfig(api_key=SecretStr(key))


# ---------------------------------------------------------------------------
# 1. Exact public model fields, frozen, extra="forbid"
# ---------------------------------------------------------------------------


def test_explanation_status_members():
    assert {member.value for member in ExplanationStatus} == {"GENERATED", "UNAVAILABLE", "FAILED"}


def test_error_category_members():
    assert {member.value for member in ErrorCategory} == {
        "CONFIGURATION",
        "AUTHENTICATION",
        "RATE_LIMIT",
        "SERVER_ERROR",
        "TIMEOUT",
        "NETWORK_ERROR",
        "SAFETY_BLOCK",
        "EMPTY_RESPONSE",
        "MALFORMED_RESPONSE",
        "UNEXPECTED_ERROR",
    }


def test_explanation_result_schema():
    assert set(ExplanationResult.model_fields.keys()) == {
        "status",
        "explanation_text",
        "model_name",
        "error_category",
        "error_message",
    }


def test_explanation_result_rejects_unknown_field():
    with pytest.raises(ValidationError):
        ExplanationResult(status=ExplanationStatus.UNAVAILABLE, extra_field="nope")


def test_explanation_result_is_frozen():
    result = ExplanationResult(
        status=ExplanationStatus.GENERATED, explanation_text="x", model_name="m"
    )
    with pytest.raises(ValidationError):
        result.explanation_text = "changed"


# ---------------------------------------------------------------------------
# 2. Every valid model state
# ---------------------------------------------------------------------------


def test_valid_generated_state():
    result = ExplanationResult(
        status=ExplanationStatus.GENERATED,
        explanation_text="This campaign is on target.",
        model_name="gemini-2.5-flash-lite",
    )
    assert result.status is ExplanationStatus.GENERATED


def test_valid_unavailable_state():
    result = ExplanationResult(
        status=ExplanationStatus.UNAVAILABLE,
        error_category=ErrorCategory.CONFIGURATION,
        error_message="No API key is available.",
    )
    assert result.status is ExplanationStatus.UNAVAILABLE


def test_valid_failed_state():
    result = ExplanationResult(
        status=ExplanationStatus.FAILED,
        model_name="gemini-2.5-flash-lite",
        error_category=ErrorCategory.TIMEOUT,
        error_message="The request timed out.",
    )
    assert result.status is ExplanationStatus.FAILED


# ---------------------------------------------------------------------------
# 3. Rejection of every inconsistent model state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(status=ExplanationStatus.GENERATED, model_name="m"),  # blank explanation_text
        dict(status=ExplanationStatus.GENERATED, explanation_text="x"),  # blank model_name
        dict(status=ExplanationStatus.GENERATED, explanation_text="x", model_name="m", error_category=ErrorCategory.TIMEOUT),
        dict(status=ExplanationStatus.GENERATED, explanation_text="x", model_name="m", error_message="oops"),
        dict(status=ExplanationStatus.GENERATED, explanation_text="   ", model_name="m"),
    ],
)
def test_generated_state_rejects_inconsistency(kwargs):
    with pytest.raises(ValidationError):
        ExplanationResult(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(status=ExplanationStatus.UNAVAILABLE, explanation_text="x", error_category=ErrorCategory.CONFIGURATION, error_message="m"),
        dict(status=ExplanationStatus.UNAVAILABLE, model_name="m", error_category=ErrorCategory.CONFIGURATION, error_message="m"),
        dict(status=ExplanationStatus.UNAVAILABLE, error_category=ErrorCategory.TIMEOUT, error_message="m"),
        dict(status=ExplanationStatus.UNAVAILABLE, error_category=ErrorCategory.CONFIGURATION),
        dict(status=ExplanationStatus.UNAVAILABLE, error_category=ErrorCategory.CONFIGURATION, error_message="   "),
    ],
)
def test_unavailable_state_rejects_inconsistency(kwargs):
    with pytest.raises(ValidationError):
        ExplanationResult(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(status=ExplanationStatus.FAILED, explanation_text="x", model_name="m", error_category=ErrorCategory.TIMEOUT, error_message="m"),
        dict(status=ExplanationStatus.FAILED, error_category=ErrorCategory.TIMEOUT, error_message="m"),
        dict(status=ExplanationStatus.FAILED, model_name="m", error_message="m"),
        dict(status=ExplanationStatus.FAILED, model_name="m", error_category=ErrorCategory.CONFIGURATION, error_message="m"),
        dict(status=ExplanationStatus.FAILED, model_name="m", error_category=ErrorCategory.TIMEOUT),
        dict(status=ExplanationStatus.FAILED, model_name="m", error_category=ErrorCategory.TIMEOUT, error_message="   "),
    ],
)
def test_failed_state_rejects_inconsistency(kwargs):
    with pytest.raises(ValidationError):
        ExplanationResult(**kwargs)


# ---------------------------------------------------------------------------
# 4. Exact function signature
# ---------------------------------------------------------------------------


def test_exact_function_signature():
    sig = inspect.signature(generate_explanation)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["prompt", "config", "client", "model"]
    assert params[0].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params[1].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params[2].kind == inspect.Parameter.KEYWORD_ONLY
    assert params[3].kind == inspect.Parameter.KEYWORD_ONLY
    assert params[2].default is None
    assert params[3].default == "gemini-2.5-flash-lite"


# ---------------------------------------------------------------------------
# 5-6. Missing/blank config -> UNAVAILABLE; zero client construction/invocation
# ---------------------------------------------------------------------------


def test_missing_key_returns_unavailable():
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, GeminiConfig(api_key=None))
    assert result.status is ExplanationStatus.UNAVAILABLE
    assert result.error_category is ErrorCategory.CONFIGURATION


def test_blank_env_key_via_real_loader_returns_unavailable(monkeypatch, tmp_path):
    import config as config_module

    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    loaded = config_module.load_gemini_config(dotenv_path=tmp_path / ".env")
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, loaded)
    assert result.status is ExplanationStatus.UNAVAILABLE


def test_unavailable_config_never_constructs_or_invokes_client(monkeypatch):
    def _fail_if_called(api_key):
        raise AssertionError("_create_client must not be called when unavailable")

    monkeypatch.setattr(gemini_analyzer, "_create_client", _fail_if_called)
    prompt = _prompt_for(_campaign_result())
    generate_explanation(prompt, GeminiConfig(api_key=None))  # must not raise


# ---------------------------------------------------------------------------
# 7-8. Real Stage 27 -> Stage 30 chain, exact request forwarding
# ---------------------------------------------------------------------------


def test_successful_generation_through_real_sample_chain():
    campaign = _real_sample_campaign()
    prompt = _prompt_for(campaign)
    fake_client = _FakeClient(response=_FakeResponse(text="  G002 is above target and improving.  "))

    result = generate_explanation(prompt, _available_config(), client=fake_client)

    assert result.status is ExplanationStatus.GENERATED
    assert result.explanation_text == "G002 is above target and improving."
    assert result.model_name == "gemini-2.5-flash-lite"
    assert result.error_category is None
    assert result.error_message is None


def test_request_forwarding_exact():
    campaign = _real_sample_campaign()
    prompt = _prompt_for(campaign)
    fake_client = _FakeClient(response=_FakeResponse(text="ok"))

    generate_explanation(prompt, _available_config(), client=fake_client, model="gemini-custom-model")

    assert len(fake_client.models.calls) == 1
    call = fake_client.models.calls[0]
    assert call["model"] == "gemini-custom-model"
    assert call["contents"] == prompt.user_content
    config_arg = call["config"]
    assert isinstance(config_arg, types.GenerateContentConfig)
    assert config_arg.system_instruction == prompt.system_instruction
    assert config_arg.temperature == 0.2
    assert config_arg.max_output_tokens == 512
    assert config_arg.candidate_count == 1
    assert config_arg.http_options.timeout == 30_000


def test_default_model_constant_used_when_not_overridden():
    prompt = _prompt_for(_campaign_result())
    fake_client = _FakeClient(response=_FakeResponse(text="ok"))
    generate_explanation(prompt, _available_config(), client=fake_client)
    assert fake_client.models.calls[0]["model"] == "gemini-2.5-flash-lite"


# ---------------------------------------------------------------------------
# 9-10. Client lifecycle: injected never closed; owned always closed
# ---------------------------------------------------------------------------


def test_injected_client_is_never_closed():
    prompt = _prompt_for(_campaign_result())
    fake_client = _FakeClient(response=_FakeResponse(text="ok"))
    generate_explanation(prompt, _available_config(), client=fake_client)
    assert fake_client.close_calls == 0


def test_injected_client_not_closed_even_on_failure():
    prompt = _prompt_for(_campaign_result())
    fake_client = _FakeClient(exc=RuntimeError("boom"))
    generate_explanation(prompt, _available_config(), client=fake_client)
    assert fake_client.close_calls == 0


def test_owned_client_closed_on_success(monkeypatch):
    created: list[_FakeClient] = []

    def _factory(api_key):
        c = _FakeClient(response=_FakeResponse(text="ok"))
        created.append(c)
        return c

    monkeypatch.setattr(gemini_analyzer, "_create_client", _factory)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config())
    assert result.status is ExplanationStatus.GENERATED
    assert created[0].close_calls == 1


def test_owned_client_closed_on_failure(monkeypatch):
    created: list[_FakeClient] = []

    def _factory(api_key):
        c = _FakeClient(exc=RuntimeError("boom"))
        created.append(c)
        return c

    monkeypatch.setattr(gemini_analyzer, "_create_client", _factory)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config())
    assert result.status is ExplanationStatus.FAILED
    assert created[0].close_calls == 1


def test_create_client_receives_the_correct_key(monkeypatch):
    received = []

    def _factory(api_key):
        received.append(api_key)
        return _FakeClient(response=_FakeResponse(text="ok"))

    monkeypatch.setattr(gemini_analyzer, "_create_client", _factory)
    prompt = _prompt_for(_campaign_result())
    generate_explanation(prompt, _available_config("distinct-key-value"))
    assert received == ["distinct-key-value"]


# ---------------------------------------------------------------------------
# 11-19 & 20. Failure category mappings, each exactly one invocation
# ---------------------------------------------------------------------------


def test_authentication_failure():
    exc = ClientError(401, {"message": "invalid api key", "status": "UNAUTHENTICATED"})
    fake_client = _FakeClient(exc=exc)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.AUTHENTICATION
    assert fake_client.models.calls.__len__() == 1


def test_permission_denied_failure_is_authentication():
    exc = ClientError(403, {"message": "permission denied", "status": "PERMISSION_DENIED"})
    fake_client = _FakeClient(exc=exc)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.error_category is ErrorCategory.AUTHENTICATION


def test_rate_limit_failure():
    exc = ClientError(429, {"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"})
    fake_client = _FakeClient(exc=exc)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.RATE_LIMIT
    assert len(fake_client.models.calls) == 1


def test_server_error_failure():
    exc = ServerError(503, {"message": "unavailable", "status": "UNAVAILABLE"})
    fake_client = _FakeClient(exc=exc)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.SERVER_ERROR
    assert len(fake_client.models.calls) == 1


def test_timeout_failure():
    fake_client = _FakeClient(exc=httpx.ReadTimeout("timed out"))
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.TIMEOUT
    assert len(fake_client.models.calls) == 1


def test_network_failure():
    fake_client = _FakeClient(exc=httpx.ConnectError("connection refused"))
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.NETWORK_ERROR
    assert len(fake_client.models.calls) == 1


def test_safety_block_via_finish_reason():
    response = _FakeResponse(text=None, candidates=[_FakeCandidate(types.FinishReason.SAFETY)])
    fake_client = _FakeClient(response=response)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.SAFETY_BLOCK
    assert len(fake_client.models.calls) == 1


def test_safety_block_via_prompt_feedback():
    class _FeedbackWithBlock:
        block_reason = "SAFETY"

    response = _FakeResponse(text=None, prompt_feedback=_FeedbackWithBlock())
    fake_client = _FakeClient(response=response)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.error_category is ErrorCategory.SAFETY_BLOCK


@pytest.mark.parametrize("text_value", [None, "", "   ", "\t\n"])
def test_empty_or_whitespace_response(text_value):
    response = _FakeResponse(text=text_value)
    fake_client = _FakeClient(response=response)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.EMPTY_RESPONSE
    assert len(fake_client.models.calls) == 1


def test_malformed_response_during_extraction():
    fake_client = _FakeClient(response=_RaisingTextResponse())
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.MALFORMED_RESPONSE
    assert len(fake_client.models.calls) == 1


def test_unexpected_sdk_exception():
    fake_client = _FakeClient(exc=ValueError("something nobody anticipated"))
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.status is ExplanationStatus.FAILED
    assert result.error_category is ErrorCategory.UNEXPECTED_ERROR
    assert len(fake_client.models.calls) == 1


# ---------------------------------------------------------------------------
# 21. Synthetic-key redaction through the owned-client path
# ---------------------------------------------------------------------------


def test_synthetic_key_redacted_from_error_message(monkeypatch):
    secret = "super-secret-owned-path-key-999"

    class _ExplodingModels:
        def generate_content(self, **kwargs):
            raise RuntimeError(f"request rejected for key={secret}")

    class _ExplodingClient:
        def __init__(self):
            self.models = _ExplodingModels()
            self.close_calls = 0

        def close(self):
            self.close_calls += 1

    def _factory(api_key):
        assert api_key == secret
        return _ExplodingClient()

    monkeypatch.setattr(gemini_analyzer, "_create_client", _factory)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(secret))

    assert result.status is ExplanationStatus.FAILED
    assert secret not in result.error_message
    assert "[REDACTED]" in result.error_message


def test_no_redaction_attempted_without_owned_secret():
    # Through the injected-client path, generate_explanation never reads
    # config.api_key at all -- confirming the secret truly is retrieved
    # only at the one owned-client call site, not read defensively "just
    # in case" elsewhere.
    fake_client = _FakeClient(exc=RuntimeError("plain failure, no secret involved"))
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)
    assert result.error_message == "plain failure, no secret involved"


# ---------------------------------------------------------------------------
# 22. Raw provider response never retained
# ---------------------------------------------------------------------------


def test_raw_provider_response_never_retained():
    response = _FakeResponse(text="the explanation")
    fake_client = _FakeClient(response=response)
    prompt = _prompt_for(_campaign_result())
    result = generate_explanation(prompt, _available_config(), client=fake_client)

    dumped = result.model_dump()
    assert response not in dumped.values()
    assert set(dumped.keys()) == {
        "status",
        "explanation_text",
        "model_name",
        "error_category",
        "error_message",
    }


# ---------------------------------------------------------------------------
# 23. No mutation of inputs
# ---------------------------------------------------------------------------


def test_no_mutation_of_prompt_or_locked_campaign():
    campaign = _real_sample_campaign()
    campaign_snapshot = campaign.model_dump()
    prompt = _prompt_for(campaign)
    prompt_snapshot = prompt.model_dump()
    config = _available_config()

    fake_client = _FakeClient(response=_FakeResponse(text="ok"))
    generate_explanation(prompt, config, client=fake_client)

    assert campaign.model_dump() == campaign_snapshot
    assert prompt.model_dump() == prompt_snapshot


# ---------------------------------------------------------------------------
# 24. Import-time side-effect freedom
# ---------------------------------------------------------------------------


def test_import_performs_no_client_construction_environment_or_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sys.modules.pop("src.gemini_analyzer", None)
    reimported = importlib.import_module("src.gemini_analyzer")
    assert "GEMINI_API_KEY" not in __import__("os").environ
    assert not hasattr(reimported, "CLIENT")
    assert not hasattr(reimported, "_client")


# ---------------------------------------------------------------------------
# 25. AST/source isolation checks
# ---------------------------------------------------------------------------


def test_exactly_one_production_get_secret_value_call_site():
    tree = ast.parse(inspect.getsource(gemini_analyzer))
    call_sites = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_secret_value"
    ]
    assert len(call_sites) == 1


def test_no_logging_or_print_calls():
    tree = ast.parse(inspect.getsource(gemini_analyzer))
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert referenced.isdisjoint({"logging", "print", "logger"})


def test_no_locked_result_approval_audit_streamlit_or_legacy_sdk_imports():
    tree = ast.parse(inspect.getsource(gemini_analyzer))
    imported_modules = set()
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
            for alias in node.names:
                imported_names.add(alias.name)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)

    assert "streamlit" not in imported_modules
    assert "google.generativeai" not in imported_modules
    assert "src.pipeline" not in imported_modules
    assert "src.approval" not in imported_modules
    assert "src.audit" not in imported_modules
    assert "BudgetReallocationReviewResult" not in imported_names
    assert "CampaignBudgetRecommendationResult" not in imported_names
    assert "CampaignExplanationPayload" not in imported_names
    assert "PortfolioExplanationPayload" not in imported_names


def test_no_module_level_client_or_config_singleton():
    module_level_assigns = set()
    tree = ast.parse(inspect.getsource(gemini_analyzer))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    module_level_assigns.add(target.id)
    forbidden = {"CLIENT", "client", "CONFIG", "config", "_client", "_config"}
    assert module_level_assigns.isdisjoint(forbidden)


def test_no_retry_loop_around_generation_call():
    tree = ast.parse(inspect.getsource(gemini_analyzer.generate_explanation))
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))


def test_function_accepts_only_prompt_config_client_model():
    source = inspect.getsource(gemini_analyzer.generate_explanation)
    tree = ast.parse(source)
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)
    arg_names = [a.arg for a in func_def.args.args] + [a.arg for a in func_def.args.kwonlyargs]
    assert set(arg_names) == {"prompt", "config", "client", "model"}
