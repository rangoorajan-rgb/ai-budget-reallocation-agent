"""Tests for config.py (Sprint 3 — Development Stage 29).

Covers the `GeminiConfig` schema (single `api_key` field, `extra="forbid"`,
frozen); the two-source, exact-precedence loader (`GEMINI_API_KEY` process
environment variable authoritative over a local `.env`, read via
`dotenv_values` — never `load_dotenv` — so `os.environ` is never mutated);
whitespace-only normalization with no format/API validation; the
deterministic, cwd-independent, non-parent-searching `.env` default path;
`SecretStr` redaction across `repr`/`str`/`model_dump`/`model_dump_json`;
import-time side-effect freedom; `app.py` independence; and isolation from
Streamlit and any Gemini SDK. Every key used below is synthetic and fake;
no real secret is ever read, printed, or asserted against.
"""

import ast
import inspect
import os
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

import config
from config import GeminiConfig, is_gemini_available, load_gemini_config

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.py"

FAKE_ENV_KEY = "fake-env-key-abc123"
FAKE_DOTENV_KEY = "fake-dotenv-key-xyz789"


@pytest.fixture(autouse=True)
def _clean_gemini_env(monkeypatch):
    # Every test starts with GEMINI_API_KEY entirely absent from the real
    # environment; monkeypatch restores the original state afterward.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _write_dotenv(tmp_path: Path, content: str) -> Path:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(content, encoding="utf-8")
    return dotenv_path


# ---------------------------------------------------------------------------
# 1-4. GeminiConfig schema, extra="forbid", frozen, api_key=None valid
# ---------------------------------------------------------------------------


def test_gemini_config_schema_is_exactly_one_field():
    assert set(GeminiConfig.model_fields.keys()) == {"api_key"}


def test_gemini_config_rejects_unknown_field():
    with pytest.raises(ValidationError):
        GeminiConfig(api_key=None, extra_field="not allowed")


def test_gemini_config_is_frozen():
    config_instance = GeminiConfig(api_key=None)
    with pytest.raises(ValidationError):
        config_instance.api_key = SecretStr(FAKE_ENV_KEY)


def test_gemini_config_api_key_none_is_valid():
    config_instance = GeminiConfig(api_key=None)
    assert config_instance.api_key is None


def test_gemini_config_default_api_key_is_none():
    assert GeminiConfig().api_key is None


# ---------------------------------------------------------------------------
# 5-6. Direct construction: valid SecretStr, invalid type
# ---------------------------------------------------------------------------


def test_direct_valid_secretstr_construction():
    config_instance = GeminiConfig(api_key=SecretStr(FAKE_ENV_KEY))
    assert config_instance.api_key.get_secret_value() == FAKE_ENV_KEY


def test_direct_invalid_type_uses_normal_pydantic_validation():
    with pytest.raises(ValidationError):
        GeminiConfig(api_key=12345)


# ---------------------------------------------------------------------------
# 7-8. Missing environment + missing .env; environment present
# ---------------------------------------------------------------------------


def test_missing_environment_and_missing_dotenv_returns_unavailable(tmp_path):
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert result.api_key is None
    assert is_gemini_available(result) is False


def test_environment_key_present_returns_available(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_ENV_KEY)
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert is_gemini_available(result) is True
    assert result.api_key.get_secret_value() == FAKE_ENV_KEY


# ---------------------------------------------------------------------------
# 9-11. Trimming, blank, whitespace-only environment values
# ---------------------------------------------------------------------------


def test_environment_key_is_trimmed(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", f"  {FAKE_ENV_KEY}  ")
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert result.api_key.get_secret_value() == FAKE_ENV_KEY


def test_blank_environment_key_returns_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert result.api_key is None


def test_whitespace_only_environment_key_returns_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "   \t  ")
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert result.api_key is None


# ---------------------------------------------------------------------------
# 12-14. Precedence: env authoritative even when blank; env overrides .env;
# absent env falls back to populated .env
# ---------------------------------------------------------------------------


def test_present_blank_environment_key_does_not_fall_back_to_dotenv(monkeypatch, tmp_path):
    dotenv_path = _write_dotenv(tmp_path, f"GEMINI_API_KEY={FAKE_DOTENV_KEY}\n")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    result = load_gemini_config(dotenv_path=dotenv_path)
    assert result.api_key is None


def test_environment_key_overrides_different_dotenv_key(monkeypatch, tmp_path):
    dotenv_path = _write_dotenv(tmp_path, f"GEMINI_API_KEY={FAKE_DOTENV_KEY}\n")
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_ENV_KEY)
    result = load_gemini_config(dotenv_path=dotenv_path)
    assert result.api_key.get_secret_value() == FAKE_ENV_KEY


def test_absent_environment_uses_populated_dotenv(tmp_path):
    dotenv_path = _write_dotenv(tmp_path, f"GEMINI_API_KEY={FAKE_DOTENV_KEY}\n")
    result = load_gemini_config(dotenv_path=dotenv_path)
    assert result.api_key.get_secret_value() == FAKE_DOTENV_KEY


# ---------------------------------------------------------------------------
# 15-17. .env missing key / blank / whitespace-only
# ---------------------------------------------------------------------------


def test_missing_key_inside_existing_dotenv_returns_unavailable(tmp_path):
    dotenv_path = _write_dotenv(tmp_path, "OTHER_VAR=something\n")
    result = load_gemini_config(dotenv_path=dotenv_path)
    assert result.api_key is None


def test_blank_dotenv_key_returns_unavailable(tmp_path):
    dotenv_path = _write_dotenv(tmp_path, "GEMINI_API_KEY=\n")
    result = load_gemini_config(dotenv_path=dotenv_path)
    assert result.api_key is None


def test_whitespace_only_dotenv_key_returns_unavailable(tmp_path):
    dotenv_path = _write_dotenv(tmp_path, "GEMINI_API_KEY=   \n")
    result = load_gemini_config(dotenv_path=dotenv_path)
    assert result.api_key is None


# ---------------------------------------------------------------------------
# 18-20. Explicit dotenv_path honored; deterministic default path; no
# parent/cwd search
# ---------------------------------------------------------------------------


def test_explicit_dotenv_path_is_honored(tmp_path):
    dotenv_path = _write_dotenv(tmp_path, f"GEMINI_API_KEY={FAKE_DOTENV_KEY}\n")
    result = load_gemini_config(dotenv_path=dotenv_path)
    assert result.api_key.get_secret_value() == FAKE_DOTENV_KEY


def test_explicit_dotenv_path_accepts_str_and_path(tmp_path):
    dotenv_path = _write_dotenv(tmp_path, f"GEMINI_API_KEY={FAKE_DOTENV_KEY}\n")
    result_from_str = load_gemini_config(dotenv_path=str(dotenv_path))
    assert result_from_str.api_key.get_secret_value() == FAKE_DOTENV_KEY


def test_default_dotenv_path_is_adjacent_to_config_py():
    expected = Path(config.__file__).resolve().parent / ".env"
    assert config._default_dotenv_path() == expected


def test_default_path_used_when_dotenv_path_is_none_and_no_real_env_exists():
    # The repository has no real .env (verified: it is gitignored and not
    # present), so the default-path branch resolves to "unavailable" here
    # without ever creating or reading a real secret.
    assert not (Path(config.__file__).resolve().parent / ".env").exists()
    result = load_gemini_config(dotenv_path=None)
    assert result.api_key is None


def test_loader_does_not_search_parent_or_cwd_directories(tmp_path, monkeypatch):
    # A .env in the current working directory must be ignored when an
    # explicit path (or the real default path) does not point to it.
    cwd_dotenv = tmp_path / "cwd_dir"
    cwd_dotenv.mkdir()
    _write_dotenv(cwd_dotenv, f"GEMINI_API_KEY={FAKE_DOTENV_KEY}\n")
    monkeypatch.chdir(cwd_dotenv)

    unrelated_path = tmp_path / "elsewhere" / ".env"
    result = load_gemini_config(dotenv_path=unrelated_path)
    assert result.api_key is None


# ---------------------------------------------------------------------------
# 21. Loader does not mutate os.environ
# ---------------------------------------------------------------------------


def test_loader_does_not_mutate_environment(tmp_path):
    dotenv_path = _write_dotenv(tmp_path, f"GEMINI_API_KEY={FAKE_DOTENV_KEY}\n")
    before = dict(os.environ)
    load_gemini_config(dotenv_path=dotenv_path)
    assert dict(os.environ) == before
    assert "GEMINI_API_KEY" not in os.environ


def test_loader_does_not_mutate_environment_with_real_env_var_present(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_ENV_KEY)
    before = dict(os.environ)
    load_gemini_config(dotenv_path=tmp_path / ".env")
    assert dict(os.environ) == before


def test_module_does_not_use_load_dotenv():
    source = inspect.getsource(config)
    tree = ast.parse(source)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "load_dotenv" not in referenced


# ---------------------------------------------------------------------------
# 22-25. Import side effects; no Streamlit; no Gemini SDK
# ---------------------------------------------------------------------------


def test_import_performs_no_environment_or_file_loading(monkeypatch):
    import importlib
    import sys

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sys.modules.pop("config", None)
    reimported = importlib.import_module("config")
    assert not hasattr(reimported, "CONFIG")
    assert "GEMINI_API_KEY" not in os.environ


def test_import_works_without_any_key():
    import importlib
    import sys

    sys.modules.pop("config", None)
    reimported = importlib.import_module("config")
    assert reimported.GeminiConfig(api_key=None).api_key is None


def test_module_creates_no_module_level_config_singleton():
    assert not hasattr(config, "CONFIG")
    assert not hasattr(config, "config")


def test_module_does_not_import_streamlit():
    tree = ast.parse(inspect.getsource(config))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    assert "streamlit" not in imported_modules


def test_module_does_not_import_gemini_sdk():
    tree = ast.parse(inspect.getsource(config))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    forbidden = {"google.generativeai", "google.genai", "genai", "generativeai"}
    assert imported_modules.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# 26. is_gemini_available never retrieves the raw secret
# ---------------------------------------------------------------------------


def test_is_gemini_available_does_not_retrieve_raw_secret():
    source = inspect.getsource(is_gemini_available)
    assert "get_secret_value" not in source


def test_is_gemini_available_true_and_false_cases():
    assert is_gemini_available(GeminiConfig(api_key=SecretStr(FAKE_ENV_KEY))) is True
    assert is_gemini_available(GeminiConfig(api_key=None)) is False


# ---------------------------------------------------------------------------
# 27-30. Secret non-disclosure in repr/str/model_dump/model_dump_json
# ---------------------------------------------------------------------------


def test_fake_key_absent_from_repr(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_ENV_KEY)
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert FAKE_ENV_KEY not in repr(result)


def test_fake_key_absent_from_str(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_ENV_KEY)
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert FAKE_ENV_KEY not in str(result)


def test_fake_key_absent_from_model_dump_repr(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_ENV_KEY)
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert FAKE_ENV_KEY not in repr(result.model_dump())


def test_fake_key_absent_from_model_dump_json(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_ENV_KEY)
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert FAKE_ENV_KEY not in result.model_dump_json()


# ---------------------------------------------------------------------------
# 31. Raw value retrievable only through SecretStr.get_secret_value()
# ---------------------------------------------------------------------------


def test_raw_value_retrievable_only_via_get_secret_value(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_ENV_KEY)
    result = load_gemini_config(dotenv_path=tmp_path / ".env")
    assert isinstance(result.api_key, SecretStr)
    assert result.api_key.get_secret_value() == FAKE_ENV_KEY


def test_no_alternative_raw_key_accessor_exists():
    public_names = {name for name in dir(config) if not name.startswith("_")}
    assert public_names == {
        "GeminiConfig",
        "load_gemini_config",
        "is_gemini_available",
        "os",
        "Path",
        "dotenv_values",
        "SecretStr",
        "BaseModel",
        "ConfigDict",
    }


# ---------------------------------------------------------------------------
# 32. Absent/blank loading raises no exception containing secret material
# ---------------------------------------------------------------------------


def test_absent_and_blank_loading_raise_nothing(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    load_gemini_config(dotenv_path=tmp_path / ".env")

    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    load_gemini_config(dotenv_path=tmp_path / ".env")


def test_no_broad_exception_handling_in_loader_source():
    tree = ast.parse(inspect.getsource(load_gemini_config))
    assert not any(isinstance(node, ast.Try) for node in ast.walk(tree))


# ---------------------------------------------------------------------------
# 33-34. app.py independence; tests/test_integration.py unchanged
# ---------------------------------------------------------------------------


def test_app_module_does_not_import_config():
    app_path = Path(__file__).resolve().parent.parent / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    assert "config" not in imported_modules


def test_app_functions_without_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parent.parent / "app.py"
    at = AppTest.from_file(str(app_path))
    at.run(timeout=10)
    assert not at.exception
    assert [t.value for t in at.title] == ["AI Budget Reallocation Agent"]


def test_test_integration_remains_unchanged():
    integration_path = Path(__file__).resolve().parent / "test_integration.py"
    tree = ast.parse(integration_path.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in ast.walk(tree)
    )


# ---------------------------------------------------------------------------
# 35. No real .env is created or modified by any test
# ---------------------------------------------------------------------------


def test_no_real_dotenv_file_created_or_modified():
    real_dotenv_path = Path(config.__file__).resolve().parent / ".env"
    assert not real_dotenv_path.exists()
