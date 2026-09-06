"""Unit tests for SWARAJ Model Registry and Ollama client."""

from typing import Any

import pytest

from models.ollama import OllamaApiError, OllamaClient
from models.registry import (
    ModelNotInstalledError,
    ModelRegistry,
    NoModelForRoleError,
    Role,
)


def test_registry_resolves_role_and_overrides() -> None:
    """Test resolving Role.WRITER and fetching model overrides."""
    registry = ModelRegistry()
    writer_tag = registry.resolve(Role.WRITER)
    assert isinstance(writer_tag, str)
    assert len(writer_tag) > 0

    overrides = registry.get_overrides(writer_tag)
    assert isinstance(overrides, dict)


def test_registry_raises_on_unknown_role() -> None:
    """Test resolving an unconfigured role raises NoModelForRoleError."""
    registry = ModelRegistry()
    with pytest.raises(NoModelForRoleError) as exc_info:
        registry.resolve("invalid_role_name")
    assert "invalid_role_name" in str(exc_info.value)


def test_preflight_validation_raises_on_missing_model() -> None:
    """Test pre-flight validation raises ModelNotInstalledError with ollama pull instructions."""
    registry = ModelRegistry()
    fake_installed = {"some-other-unrelated-model:7b"}

    with pytest.raises(ModelNotInstalledError) as exc_info:
        registry.validate_models(fake_installed)

    err_str = str(exc_info.value)
    assert "is not installed in Ollama" in err_str
    assert "Run: ollama pull" in err_str


@pytest.mark.asyncio
async def test_ollama_request_body_formatting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test stream_chat formats options inside 'options' object and keep_alive top-level."""
    captured_payload: dict[str, Any] = {}

    class MockStreamResponse:
        status_code = 200

        async def __aenter__(self) -> "MockStreamResponse":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def aiter_lines(self) -> Any:
            yield '{"message": {"content": "hello"}, "done": false}'
            yield (
                '{"message": {"content": " world"}, "done": true, '
                '"total_duration": 1234567, "eval_count": 5}'
            )

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "MockAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        def stream(
            self, method: str, url: str, json: dict[str, Any] | None = None
        ) -> MockStreamResponse:
            nonlocal captured_payload
            if json:
                captured_payload = json
            return MockStreamResponse()

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)

    client = OllamaClient()
    chunks: list[dict[str, Any]] = []
    async for chunk in client.stream_chat(
        model="dummy-model",
        messages=[{"role": "user", "content": "hi"}],
        options={"num_ctx": 16384, "temperature": 0.2},
        keep_alive="30m",
    ):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert captured_payload.get("model") == "dummy-model"
    assert captured_payload.get("keep_alive") == "30m"
    assert captured_payload.get("options") == {"num_ctx": 16384, "temperature": 0.2}


@pytest.mark.asyncio
async def test_ollama_api_error_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test stream_chat raises OllamaApiError when HTTP status is not 200."""

    class MockStreamResponse:
        status_code = 404

        async def __aenter__(self) -> "MockStreamResponse":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def aread(self) -> bytes:
            return b"model 'missing-model' not found"

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "MockAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        def stream(
            self, method: str, url: str, json: dict[str, Any] | None = None
        ) -> MockStreamResponse:
            return MockStreamResponse()

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)

    client = OllamaClient()
    with pytest.raises(OllamaApiError) as exc_info:
        async for _ in client.stream_chat(model="missing-model", messages=[]):
            pass

    assert exc_info.value.status_code == 404
    assert "missing-model" in exc_info.value.message
