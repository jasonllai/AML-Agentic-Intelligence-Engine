"""Environment-driven application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AML Agentic Intelligence Workbench"
    app_version: str = "0.1.0"
    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+psycopg://aml:aml@localhost:5432/aml_workbench",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    tracing_provider: str = Field(default="none", validation_alias="TRACING_PROVIDER")
    langsmith_api_key: str | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    phoenix_endpoint: str | None = Field(default=None, validation_alias="PHOENIX_ENDPOINT")

    secret_key: str = Field(default="local-development-only-change-me", validation_alias="SECRET_KEY")

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    mock_llm_model: str = Field(default="mock-aml-llm", validation_alias="MOCK_LLM_MODEL")
    llm_temperature: float = Field(default=0.0, validation_alias="LLM_TEMPERATURE")
    llm_timeout_seconds: float = Field(default=20.0, validation_alias="LLM_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
