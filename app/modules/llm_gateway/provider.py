import os
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol

import httpx


@dataclass
class ProviderResult:
    model: str
    content: str
    usage: dict[str, int]
    finish_reason: str = "stop"
    tool_calls: list[dict] | None = None


class Provider(Protocol):
    async def generate(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int | None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> ProviderResult:
        pass


@dataclass
class ImageResult:
    url: str


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key_env: str) -> None:
        self.base_url = base_url.rstrip("/")
        api_key = os.getenv(api_key_env)
        if not api_key:
            from app.shared.config import get_settings
            settings = get_settings()
            api_key = getattr(settings, api_key_env.lower(), None)
        self._api_key = api_key

    async def generate(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int | None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> ProviderResult:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage") or {}
        return ProviderResult(
            model=data.get("model", model),
            content=(choice.get("message") or {}).get("content", ""),
            tool_calls=(choice.get("message") or {}).get("tool_calls"),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            finish_reason=choice.get("finish_reason") or "stop",
        )

    async def image_generate(
        self,
        *,
        model: str,
        prompt: str,
        size: str = "2K",
    ) -> ImageResult:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "response_format": "url",
            "watermark": True,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/images/generations",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        data = response.json()
        return ImageResult(url=data["data"][0]["url"])

    async def stream_generate(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int | None,
    ) -> AsyncIterator[str]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = (chunk.get("choices", [{}])[0].get("delta") or {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

_provider: Provider | None = None


def set_provider(provider: Provider | None) -> None:
    global _provider
    _provider = provider


def get_provider(base_url: str, api_key_env: str) -> Provider:
    if _provider is not None:
        return _provider
    return OpenAICompatibleProvider(base_url, api_key_env)
