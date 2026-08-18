"""Application configuration for the AI Budget Reallocation Agent.

Implements Sprint 3 — Development Stage 29: a narrow, explicit,
side-effect-controlled configuration boundary for Gemini API-key
availability. This module sources `GEMINI_API_KEY`, normalizes blank
values, and holds any key using `pydantic.SecretStr` so it cannot
accidentally appear in `repr`, `str`, model serialization, logs, or
exception messages.

**No import-time side effects.** Importing this module performs no
filesystem read, loads no `.env`, reads no environment variable, imports
no Streamlit, imports no Gemini SDK, makes no network call, and creates
no module-level configuration singleton. Configuration is loaded only
through an explicit call to `load_gemini_config()`.

**Source precedence**: process environment variable `GEMINI_API_KEY` is
authoritative when present — including when explicitly blank, in which
case it does not fall back to `.env`. Only when the environment variable
is entirely absent does a local `.env` file (read via `dotenv_values`,
which never mutates `os.environ`, unlike `load_dotenv`) get consulted, at
a deterministic repository-root path derived from this file's own
location — never the process's current working directory, and never a
parent-directory search.

Missing, blank, and whitespace-only keys are all valid, normal
"Gemini unavailable" states — `GeminiConfig(api_key=None)` — and never
raise. This module implements no Gemini API integration, no prompt
construction, and no UI wiring; those remain reserved for later Sprint 3
stages, none of which are implemented here.

**SDK note**: `requirements.txt` currently declares `google-generativeai`,
which is not installed in this environment; `google-genai` is installed
instead. This module intentionally imports no Gemini SDK at all, so this
mismatch does not affect it. Resolving the mismatch is deferred to the
future Gemini API-integration stage — see `project_management/DECISIONS.md`.
"""

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, SecretStr

_GEMINI_API_KEY_VAR = "GEMINI_API_KEY"


class GeminiConfig(BaseModel):
    """Holds, in redacted form, whether a Gemini API key is configured.

    Availability is derived via `is_gemini_available`, never stored as a
    separate field, so the two can never disagree.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: SecretStr | None = None


def _default_dotenv_path() -> Path:
    return Path(__file__).resolve().parent / ".env"


def load_gemini_config(dotenv_path: str | Path | None = None) -> GeminiConfig:
    """Load Gemini configuration from the process environment or `.env`.

    Precedence: process environment variable `GEMINI_API_KEY` > local
    `.env` file > unavailable. Only whitespace-trimming normalization is
    applied; missing, blank, and whitespace-only keys all resolve to
    `GeminiConfig(api_key=None)` and never raise. Never mutates
    `os.environ`.
    """
    if _GEMINI_API_KEY_VAR in os.environ:
        trimmed = os.environ[_GEMINI_API_KEY_VAR].strip()
        return GeminiConfig(api_key=trimmed or None)

    resolved_path = Path(dotenv_path) if dotenv_path is not None else _default_dotenv_path()
    values = dotenv_values(resolved_path)
    raw_value = values.get(_GEMINI_API_KEY_VAR)
    trimmed = raw_value.strip() if raw_value is not None else ""
    return GeminiConfig(api_key=trimmed or None)


def is_gemini_available(config: GeminiConfig) -> bool:
    """Report Gemini availability without ever retrieving the raw secret."""
    return config.api_key is not None
