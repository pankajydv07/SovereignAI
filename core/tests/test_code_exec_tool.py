"""Tests for CodeExecTool execution, output formatting, and pytest exit code mapping."""

from pathlib import Path
from unittest.mock import AsyncMock
import pytest

from tools.base import ToolContext
from tools.code_exec import CodeExecInput, CodeExecOutput, CodeExecTool


@pytest.mark.asyncio
async def test_code_exec_mock_rpc_success(tmp_path: Path):
    """Test CodeExecTool with mocked RPC runner returning exit code 0."""
    mock_rpc = AsyncMock(
        return_value={
            "runId": "exec_test123",
            "exitCode": 0,
            "stdoutTail": ["PASSED test_calc.py::test_add"],
            "stderrTail": [],
            "durationMs": 150,
            "timedOut": False,
            "outputArtifacts": [],
        }
    )

    tool = CodeExecTool(rpc_runner=mock_rpc)
    ctx = ToolContext(workspace_root=tmp_path)

    inp = CodeExecInput(
        code="def add(a, b):\n    return a + b\n",
        test_code="def test_add():\n    assert add(1, 2) == 3\n",
    )

    res = await tool.run(inp, ctx)

    assert res.success is True
    output = res.output
    assert output["runId"].startswith("exec_")
    assert output["exitCode"] == 0
    assert output["testPassed"] is True
    assert mock_rpc.call_count == 1
    assert mock_rpc.call_args[0][0] == "sandbox/exec"


@pytest.mark.asyncio
async def test_code_exec_no_tests_executed_label(tmp_path: Path):
    """Test CodeExecTool when test_code is None maps testPassed to None ('Executed')."""
    mock_rpc = AsyncMock(
        return_value={
            "runId": "exec_test456",
            "exitCode": 0,
            "stdoutTail": ["Hello world"],
            "stderrTail": [],
            "durationMs": 80,
            "timedOut": False,
            "outputArtifacts": [],
        }
    )

    tool = CodeExecTool(rpc_runner=mock_rpc)
    ctx = ToolContext(workspace_root=tmp_path)

    inp = CodeExecInput(code="print('Hello world')", test_code=None)

    res = await tool.run(inp, ctx)

    assert res.success is True
    assert res.output["testPassed"] is None


@pytest.mark.asyncio
async def test_code_exec_test_failure_exit_code_truth(tmp_path: Path):
    """Test CodeExecTool maps exit code != 0 to testPassed = False."""
    mock_rpc = AsyncMock(
        return_value={
            "runId": "exec_test789",
            "exitCode": 1,
            "stdoutTail": ["FAILED test_sub.py::test_sub"],
            "stderrTail": ["AssertionError: assert 1 - 2 == 5"],
            "durationMs": 200,
            "timedOut": False,
            "outputArtifacts": [],
        }
    )

    tool = CodeExecTool(rpc_runner=mock_rpc)
    ctx = ToolContext(workspace_root=tmp_path)

    inp = CodeExecInput(
        code="def sub(a, b):\n    return a - b\n",
        test_code="def test_sub():\n    assert sub(1, 2) == 5\n",
    )

    res = await tool.run(inp, ctx)

    assert res.success is False
    assert res.output["testPassed"] is False
    assert "Execution failed with exit code 1" in res.error
