"""Provider-neutral LLM client interface."""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import get_settings

StructuredResponseT = TypeVar("StructuredResponseT", bound=BaseModel)


class LLMClient(ABC):
    """Abstract LLM client used by all agents."""

    model_name: str
    temperature: float
    timeout: float

    @abstractmethod
    def generate_structured(self, prompt: str, response_schema: type[StructuredResponseT]) -> StructuredResponseT:
        """Generate a response validated against a Pydantic schema."""

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """Generate plain text."""


def get_llm_client() -> LLMClient:
    """Return the configured LLM client, defaulting safely to mock mode."""
    settings = get_settings()
    if settings.openai_api_key:
        from app.llm.openai_client import OpenAICompatibleClient

        return OpenAICompatibleClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model_name=settings.openai_model,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
        )

    from app.llm.mock_client import MockLLMClient

    return MockLLMClient(
        model_name=settings.mock_llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
    )

