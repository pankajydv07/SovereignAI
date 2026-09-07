"""Negative security tests for RenderDeliverableTool workspace boundary guards."""

import os
from pathlib import Path
import pytest
from tools.base import ToolContext
from tools.render_deliverable import RenderDeliverableInput, RenderDeliverableTool
from tools.workspace import WorkspaceAccessError, verify_workspace_path


@pytest.fixture
def workspace_ctx(tmp_path: Path) -> ToolContext:
    ws = tmp_path / "sandbox_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ToolContext(workspace_root=ws, session_id="sess_sec_test")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "forbidden_filename",
    [
        "../outside.docx",
        "../../escaped.xlsx",
        "nested/../../outside.pptx",
        "sub/dir/../../../root.docx",
        r"C:\Windows\System32\malicious.docx",
        r"D:\confidential\payload.xlsx",
        "/etc/shadow",
        "/tmp/escaped.pptx",
    ],
)
async def test_render_deliverable_rejects_path_traversal(
    workspace_ctx: ToolContext, forbidden_filename: str
):
    """Test that render_deliverable strictly rejects absolute and directory traversal paths."""
    tool = RenderDeliverableTool()
    inp = RenderDeliverableInput(
        deliverableType="approval_note",
        data={},
        outputFilename=forbidden_filename,
    )

    res = await tool.run(inp, workspace_ctx)
    assert not res.success
    assert "Access denied" in res.error or "outside workspace boundary" in res.error


def test_verify_workspace_path_rejects_symlink_escape(tmp_path: Path):
    """Test that symlinks pointing outside the workspace boundary are rejected."""
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("classified", encoding="utf-8")

    ws = tmp_path / "ws"
    ws.mkdir()

    symlink_path = ws / "symlink_escape"
    try:
        os.symlink(outside_dir, symlink_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation requires elevated privileges on Windows")

    # Access through symlink pointing outside workspace must be blocked
    with pytest.raises(WorkspaceAccessError):
        verify_workspace_path("symlink_escape/secret.txt", ws)
