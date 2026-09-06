"""Tool for writing workspace files with diff generation and atomic safe-replace."""

import difflib
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.workspace import WorkspaceAccessError, verify_workspace_path


class FsWriteInput(BaseModel):
    path: str = Field(description="Relative workspace path to write")
    content: str = Field(description="Full text content to write to the file")


class FsWriteOutput(BaseModel):
    path: str
    bytes_written: int
    diff: str
    created: bool


class FsWriteTool(BaseTool[FsWriteInput, FsWriteOutput]):
    name = "fs_write"
    description = (
        "Write text content to a workspace file. Returns a unified diff. "
        "Uses safe atomic tempfile replace to prevent partial write corruption."
    )
    kind = ToolKind.EDIT
    side_effect = SideEffect.WRITE
    scopes = ["fs:write"]
    timeout_s = 10.0
    is_idempotent = False
    input_model = FsWriteInput
    output_model = FsWriteOutput

    async def run(self, args: FsWriteInput, ctx: ToolContext) -> ToolResult:
        try:
            target_path = verify_workspace_path(args.path, ctx.workspace_root)
        except WorkspaceAccessError as exc:
            return ToolResult.failed(str(exc))

        # Check existing content for diff generation
        existing_content = ""
        is_created = not target_path.exists()

        if not is_created:
            if target_path.is_dir():
                return ToolResult.failed(
                    f"Target path is a directory, cannot overwrite: {args.path}"
                )
            try:
                existing_content = target_path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return ToolResult.failed(
                    f"Failed to read existing file for diff '{args.path}': {exc}"
                )

        # Generate unified diff
        from_file = f"a/{args.path}"
        to_file = f"b/{args.path}"
        old_lines = existing_content.splitlines(keepends=True)
        new_lines = args.content.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(old_lines, new_lines, fromfile=from_file, tofile=to_file)
        )
        diff_text = "".join(diff_lines)

        # Atomic write pattern using tempfile in target directory + os.replace
        target_dir = target_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=target_dir,
                delete=False,
                encoding="utf-8",
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(args.content)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())

            # Atomic replace
            os.replace(tmp_path, target_path)
            bytes_written = len(args.content.encode("utf-8"))

            output = FsWriteOutput(
                path=args.path,
                bytes_written=bytes_written,
                diff=diff_text,
                created=is_created,
            )
            return ToolResult.ok(output.model_dump())

        except Exception as exc:
            # Clean up temp file on failure/cancellation
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            return ToolResult.failed(f"Atomic file write failed for '{args.path}': {exc}")
