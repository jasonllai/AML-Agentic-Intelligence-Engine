"""Shared test configuration."""

import os

import pytest

from app.core.config import get_settings

os.environ["OPENAI_API_KEY"] = ""


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    """Keep tests deterministic even when a developer has real LLM settings in .env."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
