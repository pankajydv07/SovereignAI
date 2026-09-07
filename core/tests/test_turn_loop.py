"""Unit tests for SWARAJ Agent Turn Loop, Repair, Run Budgets, and Cancellation."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.budget import RunBudget, RunBudgetTracker, StopReason
from agent.turn_loop import RunBudgetExhausted, TurnLoop
from tools.base import ToolContext
from tools.fs_read import FsReadTool
from tools.registry import ToolRegistry


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(FsReadTool())
    return reg


@pytest.fixture
def budget_tracker() -> RunBudgetTracker:
    budget = RunBudget(max_steps=5, max_run_tokens=1000, wall_clock_timeout_s=10.0)
    return RunBudgetTracker(budget=budget)


# 1. Streaming Accumulation Test
@pytest.mark.asyncio
async def test_turn_loop_streaming_accumulation(
    registry: ToolRegistry, budget_tracker: RunBudgetTracker
) -> None:
    mock_ollama = MagicMock()

    call_count = 0
    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {"message": {"thinking": "Analyzing file... "}}
            yield {"message": {"thinking": "done."}}
            yield {"message": {"content": "I will read sample.txt"}}
            yield {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "fs_read",
                                "arguments": {"path": "sample.txt", "start_line": 1, "end_line": 5},
                            }
                        }
                    ]
                },
                "done": True,
                "prompt_eval_count": 50,
                "eval_count": 20,
            }
        else:
            yield {
                "message": {"content": "Sample file read."},
                "done": True,
            }

    mock_ollama.stream_chat = mock_stream
    loop = TurnLoop(
        ollama_client=mock_ollama, tool_registry=registry, budget_tracker=budget_tracker
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": "read sample"}]
    reason, res_msgs = await loop.run_step(
        session_id="s1",
        model_tag="qwen3-coder",
        messages=messages,
        tool_context=ToolContext(workspace_root=Path(".")),
    )

    assert reason == StopReason.END_TURN
    assert len(res_msgs) >= 2
    assistant_msg = res_msgs[1]
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["thinking"] == "Analyzing file... done."
    assert assistant_msg["content"] == "I will read sample.txt"
    assert len(assistant_msg["tool_calls"]) == 1
    assert budget_tracker.total_tokens == 70


# 2. Shared Repair Budget & Pruning Test
@pytest.mark.asyncio
async def test_turn_loop_shared_repair_and_pruning(
    registry: ToolRegistry, budget_tracker: RunBudgetTracker
) -> None:
    mock_ollama = MagicMock()
    call_count = 0

    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt: invalid arguments (start_line is string "invalid")
            yield {
                "message": {
                    "content": "Attempting read",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "fs_read",
                                "arguments": {"path": "sample.txt", "start_line": "invalid"},
                            }
                        }
                    ],
                },
                "done": True,
            }
        elif call_count == 2:
            # Second attempt: repaired valid arguments
            yield {
                "message": {
                    "content": "Repaired read",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "fs_read",
                                "arguments": {"path": "sample.txt", "start_line": 1, "end_line": 2},
                            }
                        }
                    ],
                },
                "done": True,
            }
        else:
            # Third attempt: final completion after tool output
            yield {
                "message": {"content": "Read finished."},
                "done": True,
            }

    mock_ollama.stream_chat = mock_stream

    ws_path = Path("sample.txt")
    ws_path.write_text("line1\nline2\n")

    try:
        loop = TurnLoop(
            ollama_client=mock_ollama, tool_registry=registry, budget_tracker=budget_tracker
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": "read"}]

        reason, res_msgs = await loop.run_step(
            session_id="s1",
            model_tag="qwen3-coder",
            messages=messages,
            tool_context=ToolContext(workspace_root=Path(".")),
        )

        assert reason == StopReason.END_TURN
        assert call_count == 3
        # Verify intermediate failed repair attempts were pruned from history
        assert len(res_msgs) >= 3
        assert res_msgs[1]["content"] == "Repaired read"
        assert res_msgs[2]["role"] == "tool"
    finally:
        if ws_path.exists():
            ws_path.unlink()


# 3. Structured Output Fallback Test
@pytest.mark.asyncio
async def test_turn_loop_structured_output_fallback(
    registry: ToolRegistry, budget_tracker: RunBudgetTracker
) -> None:
    mock_ollama = MagicMock()
    captured_kwargs: dict[str, Any] = {}

    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        captured_kwargs.update(kwargs)
        yield {"message": {"content": '{"path": "foo.txt"}'}, "done": True}

    mock_ollama.stream_chat = mock_stream
    loop = TurnLoop(
        ollama_client=mock_ollama, tool_registry=registry, budget_tracker=budget_tracker
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": "read foo"}]
    reason, res_msgs = await loop.run_step(
        session_id="s1",
        model_tag="small-model",
        messages=messages,
        required_tool="fs_read",
        supports_native_tools=False,
    )

    assert reason == StopReason.END_TURN
    assert captured_kwargs["format"] is not None
    assert captured_kwargs["format"]["type"] == "object"
    assert captured_kwargs["options"] == {"temperature": 0.0}


# 4. Run Budget Exhaustion Test
@pytest.mark.asyncio
async def test_turn_loop_run_budget_exhausted(registry: ToolRegistry) -> None:
    mock_ollama = MagicMock()
    mock_session_store = AsyncMock()

    tracker = RunBudgetTracker(budget=RunBudget(max_steps=1))
    tracker.step_count = 1

    loop = TurnLoop(
        ollama_client=mock_ollama,
        tool_registry=registry,
        budget_tracker=tracker,
        session_store=mock_session_store,
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": "hello"}]

    with pytest.raises(RunBudgetExhausted) as exc_info:
        await loop.run_step(session_id="s1", model_tag="m1", messages=messages)

    assert exc_info.value.stop_reason == StopReason.MAX_TURN_REQUESTS
    mock_session_store.append_event.assert_called_once()


# 5. Wall-Clock Timeout Stream Test
@pytest.mark.asyncio
async def test_turn_loop_wall_clock_timeout(registry: ToolRegistry) -> None:
    mock_ollama = MagicMock()

    async def mock_slow_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        await asyncio.sleep(0.5)
        yield {"message": {"content": "slow"}}

    mock_ollama.stream_chat = mock_slow_stream
    tracker = RunBudgetTracker(budget=RunBudget(wall_clock_timeout_s=0.05))

    loop = TurnLoop(ollama_client=mock_ollama, tool_registry=registry, budget_tracker=tracker)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "slow query"}]

    with pytest.raises(RunBudgetExhausted) as exc_info:
        await loop.run_step(session_id="s1", model_tag="m1", messages=messages)

    assert exc_info.value.stop_reason == StopReason.MAX_TOKENS


# 6. HTTP Stream Abort Cancellation Test
@pytest.mark.asyncio
async def test_turn_loop_http_abort_cancellation(
    registry: ToolRegistry, budget_tracker: RunBudgetTracker
) -> None:
    mock_ollama = MagicMock()

    async def mock_hanging_stream(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"message": {"content": "part 1"}}
        await asyncio.sleep(5.0)
        yield {"message": {"content": "part 2"}}

    mock_ollama.stream_chat = mock_hanging_stream
    loop = TurnLoop(
        ollama_client=mock_ollama, tool_registry=registry, budget_tracker=budget_tracker
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": "hang"}]

    async def run_task() -> tuple[StopReason, list[dict[str, Any]]]:
        return await loop.run_step(session_id="s1", model_tag="m1", messages=messages)

    task = asyncio.create_task(run_task())
    loop.active_task = task

    await asyncio.sleep(0.05)
    loop.cancel()

    reason, res = await task
    assert reason == StopReason.CANCELLED
    assert loop._cancelled is True
