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
    cors_allow_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="CORS_ALLOW_ORIGINS",
    )
    cors_allow_origin_regex: str | None = Field(
        default=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        validation_alias="CORS_ALLOW_ORIGIN_REGEX",
    )
    cors_allow_credentials: bool = Field(default=False, validation_alias="CORS_ALLOW_CREDENTIALS")

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

    real_data_dir: str = Field(default="real_data", validation_alias="REAL_DATA_DIR")
    model_artifact_dir: str = Field(default="artifacts/models", validation_alias="MODEL_ARTIFACT_DIR")
    rag_artifact_dir: str = Field(default="artifacts/rag", validation_alias="RAG_ARTIFACT_DIR")
    ml_model_backend: str = Field(default="isolation_forest", validation_alias="ML_MODEL_BACKEND")
    rag_embedding_backend: str = Field(default="local", validation_alias="RAG_EMBEDDING_BACKEND")

    @property
    def cors_origins(self) -> list[str]:
        """Return configured CORS origins as a normalized list."""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
