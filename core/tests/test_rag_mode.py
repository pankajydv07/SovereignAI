"""Unit and integration tests for RAG Mode toggle and empty prompt attachment processing."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest

from agent.policy import PolicyEngine
from core.chat_handlers import ChatManager
from core.pre_retrieval import maybe_execute_preretrieval
from kb.store import KnowledgeBaseStore
from models.ollama import OllamaClient
from models.registry import ModelRegistry
from models.router import ModelRouter
from storage.db import DatabaseManager
from storage.session_store import SessionStore
from tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_maybe_execute_preretrieval_force_flag(tmp_path: Path) -> None:
    """Test that force_retrieval=True triggers pre-retrieval even for non-retrieval task_class."""
    store = SessionStore(tmp_path / "test.db")
    async with store._get_connection() as conn:
        pass
    await store.ensure_project("proj-1", "Project 1", str(tmp_path))
    session_id = await store.create_session("sess-1", "proj-1", "Test")

    messages: list[dict[str, Any]] = [{"role": "user", "content": "What is the operating pressure?"}]
    notifications: list[tuple[str, dict[str, Any]]] = []

    mock_registry = MagicMock()
    mock_registry.get_num_ctx.return_value = 8192
    mock_registry.installed_tags.return_value = ["bge-m3:latest", "qwen3-coder:30b"]
    mock_registry.resolve.return_value = "bge-m3:latest"

    # 1. When force_retrieval=False and task_class is "other", pre-retrieval is skipped
    await maybe_execute_preretrieval(
        task_class="other",
        user_prompt="What is the operating pressure?",
        user_role="InspectionEngineer",
        num_ctx=8192,
        model_registry=mock_registry,
        session_store=store,
        session_id=session_id,
        messages=messages,
        send_notification_fn=lambda t, p: notifications.append((t, p)),
        force_retrieval=False,
    )
    assert len(notifications) == 0
    assert "Retrieved Knowledge Base Context" not in messages[0]["content"]

    # 2. When force_retrieval=True (RAG mode ON), pre-retrieval runs
    async with store.db_manager.connect() as conn:
        await conn.execute(
            """
            INSERT INTO kb_documents (id, title, dept, classification, effective_date, revision, content_hash, status, project_id, created_at_ms)
            VALUES ('doc-test', 'cdu_spec.pdf', 'Operations', 'CONFIDENTIAL', '2026-01-01', 'rev.01', 'hash1', 'COMPLETED', 'proj-1', 1000)
            """
        )
        await conn.execute(
            """
            INSERT INTO kb_chunks (id, doc_id, chunk_index, heading_path, body_text, token_count, page, bbox_json, created_at_ms)
            VALUES ('chunk-1', 'doc-test', 0, 'CDU Specification > Pressure', 'Design operating pressure is 14.5 bar.', 20, 1, '{"x0":0.0,"y0":0.0,"x1":1.0,"y1":1.0}', 1000)
            """
        )
        await conn.execute(
            """
            INSERT INTO kb_chunk_roles (chunk_id, role)
            VALUES ('chunk-1', 'InspectionEngineer')
            """
        )
        await conn.execute(
            """
            INSERT INTO kb_chunks_fts (chunk_id, heading_path, body_text)
            VALUES ('chunk-1', 'CDU Specification > Pressure', 'Design operating pressure is 14.5 bar.')
            """
        )
        await conn.commit()

    await maybe_execute_preretrieval(
        task_class="other",
        user_prompt="operating pressure",
        user_role="InspectionEngineer",
        num_ctx=8192,
        model_registry=mock_registry,
        session_store=store,
        session_id="sess-1",
        messages=messages,
        send_notification_fn=lambda t, p: notifications.append((t, p)),
        force_retrieval=True,
    )

    assert len(notifications) == 1
    assert notifications[0][0] == "session/update"
    assert notifications[0][1]["update"]["type"] == "sources"
    assert "Retrieved Knowledge Base Context" in messages[0]["content"]
    assert "14.5 bar" in messages[0]["content"]


@pytest.mark.asyncio
async def test_chat_manager_rag_mode_routing(tmp_path: Path) -> None:
    """Test ChatManager sets task_class to kb_qa and executes pre-retrieval when ragMode=True."""
    store = SessionStore(tmp_path / "test.db")
    async with store._get_connection() as conn:
        pass
    await store.ensure_project("proj-1", "Project 1", str(tmp_path))
    await store.create_session("sess-rag", "proj-1", "RAG Test")

    notifications: list[tuple[str, dict[str, Any]]] = []
    responses: list[dict[str, Any]] = []

    mock_ollama = AsyncMock(spec=OllamaClient)
    mock_ollama.get_installed_tags.return_value = {"bge-m3:latest", "qwen3-coder:30b"}
    mock_ollama.get_running_models.return_value = []
    mock_ollama.check_supports_tools.return_value = True

    async def mock_stream(*args: Any, **kwargs: Any):
        yield {"message": {"content": "Operating pressure is 14.5 bar based on spec."}, "done": True}

    mock_ollama.stream_chat = mock_stream

    registry = ModelRegistry()
    router = ModelRouter(registry=registry)
    policy_engine = PolicyEngine()
    tool_registry = ToolRegistry()

    mgr = ChatManager(
        model_registry=registry,
        tool_registry=tool_registry,
        ollama_client=mock_ollama,
        router=router,
        policy_engine=policy_engine,
        send_notification_fn=lambda t, p: notifications.append((t, p)),
        send_response_fn=lambda r: responses.append(r),
        log_stderr_fn=lambda m: None,
    )

    # Call handle_chat_stream with ragMode=True
    await mgr.handle_chat_stream(
        msg_id=101,
        params={
            "sessionId": "sess-rag",
            "projectId": "proj-1",
            "messages": [{"role": "user", "content": "What is the pressure limit?"}],
            "ragMode": True,
            "planFirst": False,
        },
        store=store,
    )

    # Verify routing notification recorded kb_qa or ragMode
    routing_events = [p for (t, p) in notifications if t == "chat/routing"]
    assert len(routing_events) == 1
    assert responses[0]["result"]["taskClass"] in ("kb_qa", "engineering_calc")


@pytest.mark.asyncio
async def test_attachment_with_default_prompt(tmp_path: Path) -> None:
    """Test ChatManager processes file attachment when prompt is auto-generated for attached file."""
    store = SessionStore(tmp_path / "test.db")
    async with store._get_connection() as conn:
        pass
    await store.ensure_project("proj-1", "Project 1", str(tmp_path))
    await store.create_session("sess-att", "proj-1", "Attachment Test")

    # Create dummy text attachment file in tmp_path
    att_path = tmp_path / "sample_data.csv"
    att_path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")

    notifications: list[tuple[str, dict[str, Any]]] = []
    responses: list[dict[str, Any]] = []

    mock_ollama = AsyncMock(spec=OllamaClient)
    mock_ollama.get_installed_tags.return_value = {"bge-m3:latest", "qwen3-coder:30b"}
    mock_ollama.get_running_models.return_value = []
    mock_ollama.check_supports_tools.return_value = True

    async def mock_stream(*args: Any, **kwargs: Any):
        yield {"message": {"content": "Parsed CSV with 1 data row."}, "done": True}

    mock_ollama.stream_chat = mock_stream

    registry = ModelRegistry()
    router = ModelRouter(registry=registry)
    policy_engine = PolicyEngine()
    tool_registry = ToolRegistry()

    mgr = ChatManager(
        model_registry=registry,
        tool_registry=tool_registry,
        ollama_client=mock_ollama,
        router=router,
        policy_engine=policy_engine,
        send_notification_fn=lambda t, p: notifications.append((t, p)),
        send_response_fn=lambda r: responses.append(r),
        log_stderr_fn=lambda m: None,
    )

    await mgr.handle_chat_stream(
        msg_id=102,
        params={
            "sessionId": "sess-att",
            "projectId": "proj-1",
            "messages": [{"role": "user", "content": "Analyze and process attached file: sample_data.csv"}],
            "attachments": [{"name": "sample_data.csv", "filename": "sample_data.csv", "path": str(att_path)}],
            "ragMode": False,
            "planFirst": False,
        },
        store=store,
    )

    assert len(responses) == 1
    assert responses[0]["result"]["status"] == "completed"
    assert "Parsed CSV" in responses[0]["result"]["content"]


