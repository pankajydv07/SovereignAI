"""Unit tests for SWARAJ Core Tools, Tool Registry, Workspace Security, and Schema Derivation."""

from pathlib import Path

import pytest

from tools.base import ToolContext
from tools.fs_list import FsListTool
from tools.fs_read import MAX_LINE_THRESHOLD, FsReadTool
from tools.fs_write import FsWriteTool
from tools.glob import GlobTool
from tools.registry import ToolRegistry
from tools.workspace import WorkspaceAccessError, verify_workspace_path


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Fixture creating a isolated temporary workspace directory."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def tool_context(temp_workspace: Path) -> ToolContext:
    """Fixture providing ToolContext pointing to the temporary workspace."""
    return ToolContext(workspace_root=temp_workspace)


# 1. Schema Derivation Tests
def test_to_ollama_tool_schema_derivation() -> None:
    read_tool = FsReadTool()
    schema = read_tool.to_ollama_tool()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "fs_read"
    assert "description" in schema["function"]
    assert "parameters" in schema["function"]
    assert "properties" in schema["function"]["parameters"]
    assert "path" in schema["function"]["parameters"]["properties"]
    assert "start_line" in schema["function"]["parameters"]["properties"]

    write_tool = FsWriteTool()
    write_schema = write_tool.to_ollama_tool()
    assert write_schema["function"]["name"] == "fs_write"
    assert "content" in write_schema["function"]["parameters"]["properties"]


# 2. Workspace Path Security Tests
def test_verify_workspace_path_valid(temp_workspace: Path) -> None:
    valid_file = temp_workspace / "sub" / "file.txt"
    valid_file.parent.mkdir(parents=True, exist_ok=True)
    valid_file.write_text("hello")

    res = verify_workspace_path("sub/file.txt", temp_workspace)
    assert res == valid_file.resolve()


def test_verify_workspace_path_traversal_rejection(temp_workspace: Path) -> None:
    with pytest.raises(WorkspaceAccessError):
        verify_workspace_path("../outside.txt", temp_workspace)

    with pytest.raises(WorkspaceAccessError):
        verify_workspace_path("../../etc/passwd", temp_workspace)


def test_verify_workspace_path_symlink_escape(temp_workspace: Path, tmp_path: Path) -> None:
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret")

    symlink_path = temp_workspace / "sym_outside.txt"
    try:
        symlink_path.symlink_to(outside_file)
    except OSError:
        pytest.skip("Symlink creation not supported on this platform/permissions")

    with pytest.raises(WorkspaceAccessError):
        verify_workspace_path("sym_outside.txt", temp_workspace)


# 3. fs_read Tests
@pytest.mark.asyncio
async def test_fs_read_line_slicing(temp_workspace: Path, tool_context: ToolContext) -> None:
    test_file = temp_workspace / "sample.txt"
    content_lines = [f"Line {i}\n" for i in range(1, 101)]
    test_file.write_text("".join(content_lines))

    read_tool = FsReadTool()
    res = await read_tool.run(
        FsReadTool.input_model(path="sample.txt", start_line=10, end_line=15),
        tool_context,
    )

    assert res.success is True
    assert res.output["start_line"] == 10
    assert res.output["end_line"] == 15
    assert res.output["total_lines"] == 100
    assert res.output["content"].splitlines() == [f"Line {i}" for i in range(10, 16)]


@pytest.mark.asyncio
async def test_fs_read_refusal_threshold_hint(
    temp_workspace: Path, tool_context: ToolContext
) -> None:
    large_file = temp_workspace / "large.txt"
    lines_count = MAX_LINE_THRESHOLD + 100
    large_file.write_text("x\n" * lines_count)

    read_tool = FsReadTool()
    res = await read_tool.run(FsReadTool.input_model(path="large.txt"), tool_context)

    assert res.success is False
    assert res.error is not None
    assert f"total_lines: {lines_count}" in res.error
    assert "Specify line ranges" in res.error


# 4. fs_write Tests (Diff Generation & Atomic Replace)
@pytest.mark.asyncio
async def test_fs_write_atomic_create_and_diff(
    temp_workspace: Path, tool_context: ToolContext
) -> None:
    write_tool = FsWriteTool()

    # Create new file
    res1 = await write_tool.run(
        FsWriteTool.input_model(path="hello.txt", content="Hello\nWorld\n"), tool_context
    )
    assert res1.success is True
    assert res1.output["created"] is True
    assert "Hello" in res1.output["diff"]
    assert (temp_workspace / "hello.txt").read_text() == "Hello\nWorld\n"

    # Modify existing file
    res2 = await write_tool.run(
        FsWriteTool.input_model(path="hello.txt", content="Hello\nSWARAJ\n"), tool_context
    )
    assert res2.success is True
    assert res2.output["created"] is False
    assert "-World" in res2.output["diff"]
    assert "+SWARAJ" in res2.output["diff"]
    assert (temp_workspace / "hello.txt").read_text() == "Hello\nSWARAJ\n"


# 5. fs_list & glob Tests
@pytest.mark.asyncio
async def test_fs_list_and_glob(temp_workspace: Path, tool_context: ToolContext) -> None:
    (temp_workspace / "dirA").mkdir()
    (temp_workspace / "dirA" / "file1.py").write_text("# py")
    (temp_workspace / "dirA" / "file2.txt").write_text("txt")

    list_tool = FsListTool()
    list_res = await list_tool.run(FsListTool.input_model(path="dirA"), tool_context)
    assert list_res.success is True
    assert list_res.output["total_entries"] == 2

    glob_tool = GlobTool()
    glob_res = await glob_tool.run(
        GlobTool.input_model(pattern="**/*.py"), tool_context
    )
    assert glob_res.success is True
    assert "dirA/file1.py" in glob_res.output["matches"]


# 6. Tool Registry & Task Ceiling Tests
def test_tool_registry_task_ceiling() -> None:
    registry = ToolRegistry()
    registry.register(FsReadTool())
    registry.register(FsWriteTool())
    registry.register(FsListTool())
    registry.register(GlobTool())

    assert len(registry.list_all()) == 4
    task_tools = registry.get_tools_for_task("code")
    assert len(task_tools) <= 6

    ollama_tools = registry.to_ollama_tools("code")
    assert isinstance(ollama_tools, list)
    assert len(ollama_tools) == 4
    assert ollama_tools[0]["type"] == "function"
