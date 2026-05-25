"""OpenAI-compatible LLM client using environment-provided configuration."""

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.llm.client import LLMClient

StructuredResponseT = TypeVar("StructuredResponseT", bound=BaseModel)


class OpenAICompatibleClient(LLMClient):
    """Minimal OpenAI-compatible chat-completions client.

    This class avoids logging or exposing the API key. It supports OpenAI and
    compatible gateways that implement `/chat/completions`.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float,
        timeout: float,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.temperature = temperature
        self.timeout = timeout

    def generate_structured(self, prompt: str, response_schema: type[StructuredResponseT]) -> StructuredResponseT:
        """Generate JSON and validate it against the requested Pydantic schema."""
        schema_prompt = (
            f"{prompt}\n\nReturn only valid JSON matching this JSON Schema:\n"
            f"{json.dumps(response_schema.model_json_schema(), separators=(',', ':'))}"
        )
        text = self.generate_text(schema_prompt)
        return response_schema.model_validate_json(text)

    def generate_text(self, prompt: str) -> str:
        """Generate text through an OpenAI-compatible endpoint."""
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model_name,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": "You are a careful AML intelligence assistant."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"])

