"""Integration tests for ChatManager routing, Plan execution, and TurnLoop invocation."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.chat_handlers import ChatManager
from agent.policy import PolicyEngine
from models.ollama import OllamaClient
from models.registry import ModelRegistry
from models.router import ModelRouter
from storage import SessionStore
from tools.registry import ToolRegistry
from tools.fs_read import FsReadTool


@pytest.fixture
def mock_store(tmp_path: Path) -> SessionStore:
    db_file = tmp_path / "test_sessions.db"
    return SessionStore(db_file)


@pytest.fixture
def chat_manager(mock_store: SessionStore) -> tuple[ChatManager, MagicMock, MagicMock]:
    reg = ModelRegistry()
    tools = ToolRegistry()
    tools.register(FsReadTool())

    mock_ollama = MagicMock()
    mock_ollama.get_installed_tags = AsyncMock(return_value={"gpt-oss:20b", "project-brain:latest", "qwen2.5vl:7b"})

    router = ModelRouter(reg)
    policy = PolicyEngine(session_store=mock_store)

    notifications: list[tuple[str, dict[str, Any]]] = []
    responses: list[dict[str, Any]] = []

    def mock_send_notif(method: str, params: dict[str, Any]) -> None:
        notifications.append((method, params))

    def mock_send_resp(resp: dict[str, Any]) -> None:
        responses.append(resp)

    mgr = ChatManager(
        model_registry=reg,
        tool_registry=tools,
        ollama_client=mock_ollama,
        router=router,
        policy_engine=policy,
        send_notification_fn=mock_send_notif,
        send_response_fn=mock_send_resp,
        log_stderr_fn=lambda msg: None,
    )
    return mgr, notifications, responses


# 1. Test handle_chat_stream routes prompt and emits chat/routing
@pytest.mark.asyncio
async def test_chat_stream_routing_and_execution(
    chat_manager: tuple[ChatManager, list[Any], list[Any]],
    mock_store: SessionStore,
) -> None:
    mgr, notifs, resps = chat_manager

    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        yield {"message": {"content": "Here is the response."}}
        yield {"done": True, "prompt_eval_count": 10, "eval_count": 15}

    mgr.ollama.stream_chat = mock_stream

    await mgr.handle_chat_stream(
        msg_id=101,
        params={
            "messages": [{"role": "user", "content": "Explain refinery safety compliance"}],
            "sessionId": "test-sess-1",
            "projectId": "proj-1",
        },
        store=mock_store,
    )

    # Verify chat/routing notification was emitted
    routing_notifs = [n for n in notifs if n[0] == "chat/routing"]
    assert len(routing_notifs) == 1
    assert routing_notifs[0][1]["sessionId"] == "test-sess-1"
    assert "modelTag" in routing_notifs[0][1]

    # Verify final response was completed
    assert len(resps) == 1
    assert resps[0]["result"]["status"] == "completed"
    assert resps[0]["result"]["content"] == "Here is the response."


# 2. Test Plan path triggers Planner and emits session/update
@pytest.mark.asyncio
async def test_chat_stream_plan_path(
    chat_manager: tuple[ChatManager, list[Any], list[Any]],
    mock_store: SessionStore,
) -> None:
    mgr, notifs, resps = chat_manager

    # When planFirst is True, enters plan path
    plan_json = '{"steps": [{"stepIndex": 1, "description": "Read specs", "tool": "fs_read", "sideEffect": "read", "requiresApproval": false, "idempotent": true, "dependencies": []}]}'

    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        yield {"message": {"content": plan_json}}

    mgr.ollama.stream_chat = mock_stream

    await mgr.handle_chat_stream(
        msg_id=102,
        params={
            "messages": [{"role": "user", "content": "Draft an approval note for pump repair"}],
            "sessionId": "test-sess-2",
            "projectId": "proj-1",
            "planFirst": True,
        },
        store=mock_store,
    )

    plan_notifs = [n for n in notifs if n[0] == "session/update"]
    assert len(plan_notifs) == 1
    assert plan_notifs[0][1]["update"]["type"] == "plan"
    assert len(plan_notifs[0][1]["update"]["steps"]) == 1

    assert len(resps) == 1
    assert resps[0]["result"]["status"] == "plan_created"


# 3. Test handle_plan_run executes plan steps sequentially
@pytest.mark.asyncio
async def test_plan_run_execution(
    chat_manager: tuple[ChatManager, list[Any], list[Any]],
    mock_store: SessionStore,
    tmp_path: Path,
) -> None:
    mgr, notifs, resps = chat_manager
    sample_file = tmp_path / "test.txt"
    sample_file.write_text("sample content")

    steps = [
        {
            "stepIndex": 1,
            "description": "Read test file",
            "tool": "fs_read",
            "sideEffect": "read",
            "requiresApproval": False,
            "dependencies": [],
        }
    ]

    await mgr.handle_plan_run(
        msg_id=103,
        params={
            "sessionId": "test-sess-3",
            "projectId": "proj-1",
            "projectPath": str(tmp_path),
            "steps": steps,
        },
        store=mock_store,
    )

    assert len(resps) == 1
    assert resps[0]["result"]["status"] == "plan_executed"
    assert resps[0]["result"]["results"][0]["status"] == "completed"
