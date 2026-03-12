from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, ConfigDict


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    system_prompt: str | None = None


class LLMGateway(ABC):
    @abstractmethod
    def generate_text(self, request: GenerateRequest) -> str:
        raise NotImplementedError


class MockLLMGateway(LLMGateway):
    def generate_text(self, request: GenerateRequest) -> str:
        return f"mock:{request.prompt[:80]}"


class OpenAICompatibleGateway(LLMGateway):
    def __init__(self, base_url: str, api_key: str, model_name: str = "gpt-4o-mini") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name

    def generate_text(self, request: GenerateRequest) -> str:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": request.system_prompt or "You are a helpful assistant."},
                    {"role": "user", "content": request.prompt},
                ],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]
