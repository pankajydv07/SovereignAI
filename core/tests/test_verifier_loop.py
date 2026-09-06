"""Tests for CodeVerifierStrategy multi-iteration repair, budget tracking, and test weakening protection."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from agent.budget import RunBudget, RunBudgetTracker, StopReason
from agent.turn_loop import RunBudgetExhausted, TurnCancelledError, TurnLoop
from agent.verifier import CodeVerifierStrategy, extract_failing_test_names
from models.ollama import OllamaClient
from tools.code_exec import CodeExecTool
from tools.registry import ToolRegistry


def test_extract_failing_test_names():
    stderr_lines = [
        "================ FAILURES ================",
        "FAILED test_math.py::test_division - ZeroDivisionError",
        "ERROR test_runner.py::test_init - Exception",
    ]
    failing = extract_failing_test_names(stderr_lines)
    assert "test_math.py::test_division" in failing or "FAILED test_math.py::test_division - ZeroDivisionError" in failing


@pytest.mark.asyncio
async def test_verifier_first_attempt_pass(tmp_path: Path):
    """Test verifier strategy returns success on 1st execution attempt."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    registry = ToolRegistry()

    mock_rpc = AsyncMock(
        return_value={
            "runId": "run_1",
            "exitCode": 0,
            "stdoutTail": ["PASSED test_math.py::test_add"],
            "stderrTail": [],
            "durationMs": 100,
            "timedOut": False,
            "outputArtifacts": [],
        }
    )
    code_exec_tool = CodeExecTool(rpc_runner=mock_rpc)
    registry.register(code_exec_tool)

    budget = RunBudgetTracker(RunBudget(max_steps=10))
    turn_loop = TurnLoop(mock_ollama, registry, budget)

    strategy = CodeVerifierStrategy(turn_loop)
    res = await strategy.run_verifier(
        session_id="s1",
        model_tag="qwen2.5-coder:32b",
        code="def add(a, b): return a + b",
        test_code="def test_add(): assert add(1, 2) == 3",
        step_approval_granted=True,
    )

    assert res.success is True
    assert res.iterations == 1
    assert res.test_passed is True
    assert res.ui_label == "Verified in sandbox"
    assert res.test_modified is False


@pytest.mark.asyncio
async def test_verifier_second_attempt_repair_to_green(tmp_path: Path):
    """Test verifier strategy repairs code on 2nd attempt and passes."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    # Stream response for model repair
    async def mock_stream_chat(*args, **kwargs):
        yield {"message": {"content": "```python\ndef add(a, b):\n    return a + b\n```"}, "done": True}

    mock_ollama.stream_chat = mock_stream_chat

    registry = ToolRegistry()

    # Iteration 1 fails, Iteration 2 succeeds
    mock_rpc = AsyncMock(
        side_effect=[
            {
                "runId": "run_1",
                "exitCode": 1,
                "stdoutTail": ["FAILED test_add"],
                "stderrTail": ["AssertionError"],
                "durationMs": 100,
                "timedOut": False,
                "outputArtifacts": [],
            },
            {
                "runId": "run_2",
                "exitCode": 0,
                "stdoutTail": ["PASSED test_add"],
                "stderrTail": [],
                "durationMs": 110,
                "timedOut": False,
                "outputArtifacts": [],
            },
        ]
    )
    code_exec_tool = CodeExecTool(rpc_runner=mock_rpc)
    registry.register(code_exec_tool)

    budget = RunBudgetTracker(RunBudget(max_steps=10))
    turn_loop = TurnLoop(mock_ollama, registry, budget)

    strategy = CodeVerifierStrategy(turn_loop)
    res = await strategy.run_verifier(
        session_id="s1",
        model_tag="qwen2.5-coder:32b",
        code="def add(a, b): return a - b",  # Buggy initial code
        test_code="def test_add(): assert add(1, 2) == 3",
        step_approval_granted=True,
    )

    assert res.success is True
    assert res.iterations == 2
    assert res.test_passed is True
    assert res.ui_label == "Verified in sandbox"


@pytest.mark.asyncio
async def test_verifier_three_failures_surfaces_diagnostic_report(tmp_path: Path):
    """Test verifier strategy surfaces structured diagnostic report after 3 failed attempts."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    async def mock_stream_chat(*args, **kwargs):
        yield {"message": {"content": "def add(a, b): return 0"}, "done": True}

    mock_ollama.stream_chat = mock_stream_chat

    registry = ToolRegistry()

    # 3 consecutive failures
    fail_res = {
        "runId": "run_fail",
        "exitCode": 1,
        "stdoutTail": ["FAILED test_add"],
        "stderrTail": ["AssertionError: assert 0 == 3"],
        "durationMs": 90,
        "timedOut": False,
        "outputArtifacts": [],
    }
    mock_rpc = AsyncMock(side_effect=[fail_res, fail_res, fail_res])
    code_exec_tool = CodeExecTool(rpc_runner=mock_rpc)
    registry.register(code_exec_tool)

    budget = RunBudgetTracker(RunBudget(max_steps=10))
    turn_loop = TurnLoop(mock_ollama, registry, budget)

    strategy = CodeVerifierStrategy(turn_loop)
    res = await strategy.run_verifier(
        session_id="s1",
        model_tag="qwen2.5-coder:32b",
        code="def add(a, b): return -1",
        test_code="def test_add(): assert add(1, 2) == 3",
        step_approval_granted=True,
    )

    assert res.success is False
    assert res.iterations == 3
    assert res.test_passed is False
    assert res.diagnostic_report is not None
    assert "user_options" in res.diagnostic_report
    assert "Retry with guidance" in res.diagnostic_report["user_options"]


@pytest.mark.asyncio
async def test_verifier_cancellation_during_iteration(tmp_path: Path):
    """Test verifier strategy raises TurnCancelledError when cancellation token is set."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    registry = ToolRegistry()

    mock_rpc = AsyncMock(
        return_value={
            "runId": "run_1",
            "exitCode": 1,
            "stdoutTail": [],
            "stderrTail": ["Error"],
            "durationMs": 50,
            "timedOut": False,
            "outputArtifacts": [],
        }
    )
    code_exec_tool = CodeExecTool(rpc_runner=mock_rpc)
    registry.register(code_exec_tool)

    budget = RunBudgetTracker(RunBudget(max_steps=10))
    turn_loop = TurnLoop(mock_ollama, registry, budget)

    # Trigger cancellation mid-verifier loop
    turn_loop.cancel()

    strategy = CodeVerifierStrategy(turn_loop)
    with pytest.raises(TurnCancelledError):
        await strategy.run_verifier(
            session_id="s1",
            model_tag="qwen2.5-coder:32b",
            code="print('test')",
            test_code="assert True",
        )


@pytest.mark.slow
@pytest.mark.asyncio
async def test_verifier_slow_integration():
    """Slow integration test verifying real execution fallback."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    registry = ToolRegistry()
    registry.register(CodeExecTool(rpc_runner=None))

    budget = RunBudgetTracker(RunBudget(max_steps=10))
    turn_loop = TurnLoop(mock_ollama, registry, budget)

    strategy = CodeVerifierStrategy(turn_loop)
    res = await strategy.run_verifier(
        session_id="s1",
        model_tag="qwen2.5-coder:32b",
        code="def mul(a, b): return a * b",
        test_code="def test_mul(): assert mul(3, 4) == 12",
    )

    assert res.success is True
    assert res.test_passed is True
    assert res.ui_label == "Verified in sandbox"
