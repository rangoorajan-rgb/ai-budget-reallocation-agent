"""Gemini API integration for explanation-only narration of locked results.

Implements Sprint 3 — Development Stage 31: the transport/service layer
that sends a Stage 30 `ExplanationPrompt` to Gemini and returns a typed,
explanation-only `ExplanationResult`. This module never accepts a locked
pipeline result, a payload model, an approval model, or an audit model —
it only ever sees `ExplanationPrompt` (already-built system/user content)
and `GeminiConfig` (a redacted API-key holder). `ExplanationResult` has no
field capable of representing an action, budget, allocation, score, rank,
reason, or conservation value, so there is no path by which anything this
module returns could be written back into a locked deterministic result.

**SDK.** Uses `google.genai` (the current, actively-maintained, GA Google
Gen AI SDK) exclusively. The legacy `google.generativeai` package is never
imported — it is deprecated and not installed in this environment.

**Model and settings, all frozen.** Default model `gemini-2.5-flash-lite`,
overridable via the `model` keyword-only parameter; `temperature=0.2`;
`max_output_tokens=512`; exactly one candidate; a `30_000`-millisecond
timeout via `HttpOptions`; no structured output; no response-content
scanning for "unsupported" text — the only guarantee this module makes is
structural, not textual.

**No automatic retries and no fabricated fallback text.** A failure is
reported as a typed `FAILED` result with a sanitized message; a human
reviewer (via a future UI stage) decides whether to try again. This
module never invents replacement explanation text.

**Client lifecycle.** An injected `client` (satisfying the narrow
`GeminiClient` structural protocol) is used as-is and never closed. When
no client is injected, exactly one production call site retrieves
`config.api_key.get_secret_value()`, builds one fresh `google.genai.Client`
for this call only, and closes it in a `finally` block regardless of
outcome. No client or configuration is cached at module level, and
importing this module performs no environment read, no client
construction, and no network call.

**Secret redaction.** The raw key is used only to construct the internal
client; it is never logged, never printed, and is defensively redacted
(replaced with a fixed marker) out of any caught exception's message
before that message is placed into `error_message` — no other error text
is ever built from raw provider request/response/header/credential data.
"""

from enum import Enum
from typing import Protocol

import httpx
from google.genai import Client, types
from google.genai.errors import APIError, ClientError, ServerError
from pydantic import BaseModel, ConfigDict, model_validator

from config import GeminiConfig, is_gemini_available
from src.explanations import ExplanationPrompt

_DEFAULT_MODEL_NAME = "gemini-2.5-flash-lite"
_TEMPERATURE = 0.2
_MAX_OUTPUT_TOKENS = 512
_TIMEOUT_MILLISECONDS = 30_000
_CANDIDATE_COUNT = 1
_REDACTION_MARKER = "[REDACTED]"
_GENERIC_FAILURE_MESSAGE = "An unexpected error occurred while requesting the explanation."

_AUTHENTICATION_CODES = frozenset({401, 403})
_RATE_LIMIT_CODES = frozenset({429})

_SAFETY_FINISH_REASONS = frozenset(
    {
        types.FinishReason.SAFETY,
        types.FinishReason.PROHIBITED_CONTENT,
        types.FinishReason.BLOCKLIST,
        types.FinishReason.SPII,
        types.FinishReason.IMAGE_SAFETY,
        types.FinishReason.IMAGE_PROHIBITED_CONTENT,
    }
)


class ExplanationStatus(str, Enum):
    GENERATED = "GENERATED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class ErrorCategory(str, Enum):
    CONFIGURATION = "CONFIGURATION"
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER_ERROR = "SERVER_ERROR"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    SAFETY_BLOCK = "SAFETY_BLOCK"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


class ExplanationResult(BaseModel):
    """The only shape a Gemini explanation attempt may take. No field here
    can represent, replace, or reinterpret any locked deterministic value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ExplanationStatus
    explanation_text: str | None = None
    model_name: str | None = None
    error_category: ErrorCategory | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def _check_state_consistency(self) -> "ExplanationResult":
        if self.status is ExplanationStatus.GENERATED:
            if self.explanation_text is None or not self.explanation_text.strip():
                raise ValueError("GENERATED requires a nonblank explanation_text")
            if self.model_name is None or not self.model_name.strip():
                raise ValueError("GENERATED requires a nonblank model_name")
            if self.error_category is not None:
                raise ValueError("GENERATED must not have an error_category")
            if self.error_message is not None:
                raise ValueError("GENERATED must not have an error_message")
        elif self.status is ExplanationStatus.UNAVAILABLE:
            if self.explanation_text is not None:
                raise ValueError("UNAVAILABLE must not have explanation_text")
            if self.model_name is not None:
                raise ValueError("UNAVAILABLE must not have model_name")
            if self.error_category is not ErrorCategory.CONFIGURATION:
                raise ValueError("UNAVAILABLE requires error_category=CONFIGURATION")
            if self.error_message is None or not self.error_message.strip():
                raise ValueError("UNAVAILABLE requires a nonblank error_message")
        elif self.status is ExplanationStatus.FAILED:
            if self.explanation_text is not None:
                raise ValueError("FAILED must not have explanation_text")
            if self.model_name is None or not self.model_name.strip():
                raise ValueError("FAILED requires a nonblank model_name")
            if self.error_category is None or self.error_category is ErrorCategory.CONFIGURATION:
                raise ValueError("FAILED requires a non-CONFIGURATION error_category")
            if self.error_message is None or not self.error_message.strip():
                raise ValueError("FAILED requires a nonblank error_message")
        return self


class _GeminiModels(Protocol):
    def generate_content(
        self, *, model: str, contents: str, config: "types.GenerateContentConfig"
    ) -> "types.GenerateContentResponse": ...


class GeminiClient(Protocol):
    """The narrow structural shape this module actually calls. A real
    `google.genai.Client` satisfies this automatically; a test double needs
    only implement this much, never the full SDK client."""

    models: _GeminiModels


def _create_client(api_key: str) -> Client:
    return Client(api_key=api_key)


def _build_generation_config(system_instruction: str) -> "types.GenerateContentConfig":
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=_TEMPERATURE,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        candidate_count=_CANDIDATE_COUNT,
        http_options=types.HttpOptions(timeout=_TIMEOUT_MILLISECONDS),
    )


def _sanitize_error_message(message: str, secret_value: str | None) -> str:
    sanitized = message
    if secret_value:
        sanitized = sanitized.replace(secret_value, _REDACTION_MARKER)
    sanitized = sanitized.strip()
    return sanitized or _GENERIC_FAILURE_MESSAGE


def _failed_result(model_name: str, category: ErrorCategory, message: str) -> ExplanationResult:
    return ExplanationResult(
        status=ExplanationStatus.FAILED,
        model_name=model_name,
        error_category=category,
        error_message=message,
    )


def _classify_client_error(exc: ClientError) -> ErrorCategory:
    code = getattr(exc, "code", None)
    if code in _AUTHENTICATION_CODES:
        return ErrorCategory.AUTHENTICATION
    if code in _RATE_LIMIT_CODES:
        return ErrorCategory.RATE_LIMIT
    return ErrorCategory.UNEXPECTED_ERROR


def _is_safety_blocked(response: "types.GenerateContentResponse") -> bool:
    prompt_feedback = getattr(response, "prompt_feedback", None)
    if prompt_feedback is not None and getattr(prompt_feedback, "block_reason", None) is not None:
        return True
    candidates = getattr(response, "candidates", None)
    if candidates:
        finish_reason = getattr(candidates[0], "finish_reason", None)
        if finish_reason in _SAFETY_FINISH_REASONS:
            return True
    return False


def generate_explanation(
    prompt: ExplanationPrompt,
    config: GeminiConfig,
    *,
    client: GeminiClient | None = None,
    model: str = _DEFAULT_MODEL_NAME,
) -> ExplanationResult:
    """Send one Stage 30 prompt to Gemini and return a typed result.

    Never retries, never fabricates fallback text, never scans response
    content for "unsupported" claims, and never returns the raw provider
    response. `get_secret_value()` is called at most once, only when no
    `client` is injected, solely to construct one internally-owned client
    for this call, which is always closed in `finally`.
    """
    if not is_gemini_available(config):
        return ExplanationResult(
            status=ExplanationStatus.UNAVAILABLE,
            error_category=ErrorCategory.CONFIGURATION,
            error_message="Gemini is not configured: no API key is available.",
        )

    secret_value: str | None = None
    owned_client: Client | None = None
    if client is None:
        secret_value = config.api_key.get_secret_value()
        owned_client = _create_client(secret_value)
        active_client: GeminiClient = owned_client
    else:
        active_client = client

    try:
        response = active_client.models.generate_content(
            model=model,
            contents=prompt.user_content,
            config=_build_generation_config(prompt.system_instruction),
        )
    except httpx.TimeoutException as exc:
        return _failed_result(
            model, ErrorCategory.TIMEOUT, _sanitize_error_message(str(exc), secret_value)
        )
    except httpx.NetworkError as exc:
        return _failed_result(
            model, ErrorCategory.NETWORK_ERROR, _sanitize_error_message(str(exc), secret_value)
        )
    except ServerError as exc:
        return _failed_result(
            model, ErrorCategory.SERVER_ERROR, _sanitize_error_message(str(exc), secret_value)
        )
    except ClientError as exc:
        return _failed_result(
            model, _classify_client_error(exc), _sanitize_error_message(str(exc), secret_value)
        )
    except APIError as exc:
        return _failed_result(
            model, ErrorCategory.UNEXPECTED_ERROR, _sanitize_error_message(str(exc), secret_value)
        )
    except Exception as exc:  # noqa: BLE001 -- deliberate transport-boundary catch; see module docstring
        return _failed_result(
            model, ErrorCategory.UNEXPECTED_ERROR, _sanitize_error_message(str(exc), secret_value)
        )
    finally:
        if owned_client is not None:
            owned_client.close()

    try:
        if _is_safety_blocked(response):
            return _failed_result(
                model, ErrorCategory.SAFETY_BLOCK, "The response was blocked by provider safety filtering."
            )
        text = response.text
    except Exception as exc:  # noqa: BLE001 -- deliberate extraction-boundary catch; see module docstring
        return _failed_result(
            model, ErrorCategory.MALFORMED_RESPONSE, _sanitize_error_message(str(exc), secret_value)
        )

    if text is None or not text.strip():
        return _failed_result(model, ErrorCategory.EMPTY_RESPONSE, "The provider returned no explanation text.")

    return ExplanationResult(
        status=ExplanationStatus.GENERATED,
        explanation_text=text.strip(),
        model_name=model,
    )
