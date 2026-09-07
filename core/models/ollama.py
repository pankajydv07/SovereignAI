"""SWARAJ Ollama Async API Client.

Sole permitted egress destination: http://127.0.0.1:11434
Handles streaming chat, model tag listing, option overrides, and timing metrics.
"""

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

OLLAMA_BASE_URL = "http://127.0.0.1:11434"


class OllamaUnreachableError(Exception):
    """Raised when Ollama server on 127.0.0.1:11434 cannot be reached."""

    def __init__(self, message: str = "Ollama service is unreachable at 127.0.0.1:11434") -> None:
        super().__init__(message)


class OllamaApiError(Exception):
    """Raised when Ollama API returns a non-200 HTTP status code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Ollama API Error ({status_code}): {message}")
        self.status_code = status_code
        self.message = message


def _clean_surrogates(obj: Any) -> Any:
    """Recursively sanitize strings to replace lone UTF-16 surrogates with replacement chars."""
    if isinstance(obj, str):
        return obj.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    if isinstance(obj, dict):
        return {_clean_surrogates(k): _clean_surrogates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_surrogates(x) for x in obj]
    return obj


class OllamaClient:
    """Async client for local Ollama server."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_installed_tags(self) -> set[str]:
        """Fetch list of installed model tags via GET /api/tags."""
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    raise OllamaApiError(resp.status_code, resp.text)

                data = resp.json()
                models = data.get("models", [])
                tags: set[str] = set()
                for m in models:
                    name = m.get("name")
                    model_id = m.get("model")
                    if name:
                        tags.add(name)
                    if model_id:
                        tags.add(model_id)
                return tags
        except httpx.RequestError as exc:
            raise OllamaUnreachableError(
                f"Failed to connect to Ollama at {self.base_url}: {exc}"
            ) from exc

    async def get_installed_models_full(self) -> list[dict[str, Any]]:
        """Fetch list of installed models with metadata dict items via GET /api/tags."""
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    raise OllamaApiError(resp.status_code, resp.text)
                data = resp.json()
                return data.get("models", [])
        except httpx.RequestError as exc:
            raise OllamaUnreachableError(
                f"Failed to connect to Ollama at {self.base_url}: {exc}"
            ) from exc

    async def show_model(self, model_tag: str) -> dict[str, Any]:
        """Fetch model details and GGUF metadata via POST /api/show."""
        url = f"{self.base_url}/api/show"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json={"name": model_tag})
                if resp.status_code != 200:
                    raise OllamaApiError(resp.status_code, resp.text)
                return resp.json()
        except httpx.RequestError as exc:
            raise OllamaUnreachableError(
                f"Failed to connect to Ollama at {self.base_url}: {exc}"
            ) from exc

    async def check_supports_tools(self, model_tag: str) -> bool:
        """Check if model template or parameters declare native tool calling capability via discovery."""
        try:
            info = await self.show_model(model_tag)
            template = info.get("template", "")
            modelfile = info.get("modelfile", "")
            capabilities = info.get("capabilities", [])
            if "tools" in capabilities:
                return True
            if ".Tools" in template or "[AVAILABLE_TOOLS]" in template or "<tools>" in template:
                return True
            if ".Tools" in modelfile or "[AVAILABLE_TOOLS]" in modelfile:
                return True
            return False
        except Exception:
            return False

    async def get_running_models(self) -> list[dict[str, Any]]:
        """Fetch currently loaded models and VRAM/RAM utilization via GET /api/ps."""
        url = f"{self.base_url}/api/ps"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    raise OllamaApiError(resp.status_code, resp.text)
                data = resp.json()
                return data.get("models", [])
        except httpx.RequestError as exc:
            raise OllamaUnreachableError(
                f"Failed to connect to Ollama at {self.base_url}: {exc}"
            ) from exc

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format: dict[str, Any] | str | None = None,
        options: dict[str, Any] | None = None,
        keep_alive: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream chat completions from POST /api/chat.

        `tools` list contains function schemas for native tool calls.
        `format` passes JSON Schema object or format type.
        `options` dictionary is placed inside the top-level 'options' JSON key.
        `keep_alive` is placed top-level.
        """
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        if tools:
            payload["tools"] = tools

        if format:
            payload["format"] = format

        if options:
            payload["options"] = options

        if keep_alive:
            payload["keep_alive"] = keep_alive

        payload = _clean_surrogates(payload)

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        error_text = error_body.decode("utf-8", errors="replace")
                        raise OllamaApiError(response.status_code, error_text)

                    async for line in response.aiter_lines():
                        trimmed = line.strip()
                        if not trimmed:
                            continue

                        chunk_data: dict[str, Any] = json.loads(trimmed)
                        yield chunk_data

        except httpx.RequestError as exc:
            raise OllamaUnreachableError(
                f"Ollama stream connection failed at {url}: {exc}"
            ) from exc
