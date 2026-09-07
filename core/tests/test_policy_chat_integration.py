"""Unit and integration tests for SWARAJ PolicyEngine, TurnLoop Permission handling, and Fail-Closed guarantees."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.budget import RunBudget, RunBudgetTracker
from agent.policy import PolicyDecision, PolicyEngine
from agent.resources import compute_default_resource_pattern, extract_resource_string
from agent.turn_loop import StopReason, TurnLoop
from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.fs_read import FsReadTool
from tools.fs_write import FsWriteTool
from tools.registry import ToolRegistry
from pydantic import BaseModel, Field


class DummyWriteInput(BaseModel):
    path: str = Field(description="Path to write")
    content: str = Field(description="Content")


class DummyWriteTool(BaseTool[DummyWriteInput, dict[str, Any]]):
    name = "dummy_write"
    description = "Test write tool"
    kind = ToolKind.EDIT
    side_effect = SideEffect.WRITE
    input_model = DummyWriteInput
    output_model = dict

    async def run(self, input_data: DummyWriteInput, context: ToolContext) -> ToolResult:
        return ToolResult(output={"written": input_data.path}, success=True)


@pytest.fixture
def policy_engine() -> PolicyEngine:
    return PolicyEngine()


@pytest.fixture
def budget_tracker() -> RunBudgetTracker:
    budget = RunBudget(max_steps=5, max_run_tokens=1000, wall_clock_timeout_s=10.0)
    return RunBudgetTracker(budget=budget)


# 1. Resource extraction test
def test_resource_extraction_and_pattern_computation() -> None:
    # File write
    res1 = extract_resource_string("fs_write", {"path": "docs/reports/audit.pdf", "content": "test"})
    assert res1 == "docs/reports/audit.pdf"
    assert compute_default_resource_pattern(res1) == "docs/reports/**"

    # Generate document
    res2 = extract_resource_string("generate_document", {"filename": "output.xlsx"})
    assert res2 == "output.xlsx"
    assert compute_default_resource_pattern(res2) == "**"

    # Code exec
    res3 = extract_resource_string("code_exec", {"command": ["python", "script.py"]})
    assert res3 == "python script.py"

    # Kb search (conservative unscoped)
    res4 = extract_resource_string("kb_search", {"query": "refinery standards"})
    assert res4 == "<unscoped>"

    # Unknown tool fallback (conservative unscoped)
    res5 = extract_resource_string("unknown_tool", {})
    assert res5 == "<unscoped>"


# 2. PolicyEngine decisions: AUTO for READ, ASK for WRITE, pattern matching
@pytest.mark.asyncio
async def test_policy_engine_decisions(policy_engine: PolicyEngine) -> None:
    # Read tool is AUTO
    dec, pat = await policy_engine.decide(
        subject=None,
        tool="fs_read",
        resource="config.yaml",
        side_effect=SideEffect.READ,
        project_id="proj1",
    )
    assert dec == PolicyDecision.AUTO

    # Unconfigured write tool is ASK
    dec, pat = await policy_engine.decide(
        subject=None,
        tool="fs_write",
        resource="docs/report.md",
        side_effect=SideEffect.WRITE,
        project_id="proj1",
    )
    assert dec == PolicyDecision.ASK

    # Add session allow rule for docs/**
    policy_engine.add_session_rule("proj1", "fs_write", "docs/**")
    dec, pat = await policy_engine.decide(
        subject=None,
        tool="fs_write",
        resource="docs/report.md",
        side_effect=SideEffect.WRITE,
        project_id="proj1",
    )
    assert dec == PolicyDecision.AUTO
    assert pat == "docs/**"

    # File outside docs/** remains ASK
    dec, pat = await policy_engine.decide(
        subject=None,
        tool="fs_write",
        resource="src/main.py",
        side_effect=SideEffect.WRITE,
        project_id="proj1",
    )
    assert dec == PolicyDecision.ASK


# 3. Fail-Closed Security Test: No permission requester provided
@pytest.mark.asyncio
async def test_fail_closed_when_requester_is_none(
    budget_tracker: RunBudgetTracker, policy_engine: PolicyEngine
) -> None:
    reg = ToolRegistry()
    reg.register(DummyWriteTool())

    mock_ollama = MagicMock()

    call_count = 0
    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "dummy_write",
                                "arguments": {"path": "test.txt", "content": "hello"},
                            }
                        }
                    ]
                },
                "done": True,
            }
        else:
            yield {
                "message": {"content": "Understood."},
                "done": True,
            }

    mock_ollama.stream_chat = mock_stream

    # permission_requester is None (e.g. headless or wiring error)
    loop = TurnLoop(
        ollama_client=mock_ollama,
        tool_registry=reg,
        budget_tracker=budget_tracker,
        policy_engine=policy_engine,
        permission_requester=None,
    )

    stop_reason, messages = await loop.run_step(
        session_id="test-session",
        model_tag="test-model",
        messages=[{"role": "user", "content": "write to test.txt"}],
        project_id="proj1",
    )

    # Tool call must fail closed with refusal observation
    tool_obs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_obs) == 1
    assert "fail-closed" in tool_obs[0]["content"]
    assert tool_obs[0]["success"] is False


# 4. Permission approval round-trip with scope persistence
@pytest.mark.asyncio
async def test_permission_approval_roundtrip(
    budget_tracker: RunBudgetTracker, policy_engine: PolicyEngine
) -> None:
    reg = ToolRegistry()
    reg.register(DummyWriteTool())

    mock_ollama = MagicMock()
    call_count = 0

    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "dummy_write",
                                "arguments": {"path": "docs/audit.txt", "content": "hello"},
                            }
                        }
                    ]
                },
                "done": True,
            }
        else:
            yield {
                "message": {"content": "Wrote file."},
                "done": True,
            }

    mock_ollama.stream_chat = mock_stream

    async def mock_permission_requester(
        tool: str, side_effect: str, desc: str, res: str, project_id: str
    ) -> tuple[str, str | None]:
        # User approves for session with parent directory pattern
        return "allow_session", "docs/**"

    loop = TurnLoop(
        ollama_client=mock_ollama,
        tool_registry=reg,
        budget_tracker=budget_tracker,
        policy_engine=policy_engine,
        permission_requester=mock_permission_requester,
    )

    stop_reason, messages = await loop.run_step(
        session_id="test-session",
        model_tag="test-model",
        messages=[{"role": "user", "content": "write to docs/audit.txt"}],
        project_id="proj1",
    )

    tool_obs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_obs) == 1
    assert tool_obs[0]["success"] is True

    # Next call under docs/** should now be AUTO
    dec, pat = await policy_engine.decide(
        subject=None,
        tool="dummy_write",
        resource="docs/another_file.txt",
        side_effect=SideEffect.WRITE,
        project_id="proj1",
    )
    assert dec == PolicyDecision.AUTO
    assert pat == "docs/**"


@pytest.mark.asyncio
async def test_permission_denial_immediate_halt() -> None:
    """Test that when permission is denied, turn loop stops immediately and doesn't execute further tools."""
    policy_engine = PolicyEngine()
    budget_tracker = RunBudgetTracker(RunBudget(max_steps=5, max_run_tokens=4000))
    reg = ToolRegistry()
    reg.register(DummyWriteTool())

    mock_ollama = AsyncMock()

    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        yield {
            "message": {
                "tool_calls": [
                    {
                        "function": {
                            "name": "dummy_write",
                            "arguments": {"path": "confidential.txt", "content": "secret"},
                        }
                    },
                    {
                        "function": {
                            "name": "dummy_write",
                            "arguments": {"path": "second.txt", "content": "secret2"},
                        }
                    },
                ]
            },
            "done": True,
        }

    mock_ollama.stream_chat = mock_stream
    permission_request_count = 0

    async def mock_deny_requester(
        tool: str, side_effect: str, desc: str, res: str, project_id: str
    ) -> tuple[str, str | None]:
        nonlocal permission_request_count
        permission_request_count += 1
        return "deny", None

    loop = TurnLoop(
        ollama_client=mock_ollama,
        tool_registry=reg,
        budget_tracker=budget_tracker,
        policy_engine=policy_engine,
        permission_requester=mock_deny_requester,
    )

    stop_reason, messages = await loop.run_step(
        session_id="test-session-deny",
        model_tag="test-model",
        messages=[{"role": "user", "content": "write to confidential.txt"}],
        project_id="proj1",
    )

    # Permission must be requested exactly ONCE (not looped for second tool call)
    assert permission_request_count == 1
    assert stop_reason == StopReason.END_TURN
    assert any("Permission was denied by the user for 'dummy_write'" in m.get("content", "") for m in messages)

