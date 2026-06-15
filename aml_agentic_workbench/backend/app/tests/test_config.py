"""Configuration loading tests."""

from pathlib import Path

from app.core.config import env_file_candidates, get_settings
from app.llm.client import get_llm_client
from app.llm.openai_client import OpenAICompatibleClient


def test_env_file_candidates_include_repo_root_env() -> None:
    """Backend startup from the backend directory should still discover the repo-root .env."""
    repo_root_env = Path(__file__).resolve().parents[4] / ".env"

    assert str(repo_root_env) in env_file_candidates()


def test_openai_env_selects_openai_compatible_client(monkeypatch) -> None:
    """Configured OpenAI-compatible variables should select the real LLM client instead of mock mode."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("OPENAI_MODEL", "deepseek-v4-flash")
    get_settings.cache_clear()

    settings = get_settings()
    client = get_llm_client()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_base_url == "https://api.deepseek.com"
    assert settings.openai_model == "deepseek-v4-flash"
    assert isinstance(client, OpenAICompatibleClient)
