"""Tool for reading workspace files with line range limits and VRAM context protection."""


from pydantic import BaseModel, Field

from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.document_reader import SUPPORTED_RICH_EXTENSIONS, convert_document_to_markdown
from tools.workspace import WorkspaceAccessError, verify_workspace_path

MAX_LINE_THRESHOLD = 800
MAX_BYTE_THRESHOLD = 46080


class FsReadInput(BaseModel):
    path: str = Field(description="Relative or absolute workspace path to read")
    start_line: int | None = Field(
        default=None, description="1-indexed starting line number (inclusive)"
    )
    end_line: int | None = Field(
        default=None, description="1-indexed ending line number (inclusive)"
    )


class FsReadOutput(BaseModel):
    content: str
    start_line: int
    end_line: int
    total_lines: int
    total_bytes: int


class FsReadTool(BaseTool[FsReadInput, FsReadOutput]):
    name = "fs_read"
    description = (
        "Read file content from the workspace. Automatically converts spreadsheets (.xlsx, .xls, .csv), "
        "Word documents (.docx), presentations (.pptx), and PDFs into structured Markdown tables and text. "
        "Always use this tool when asked to read, inspect, or explain any file in the workspace."
    )
    kind = ToolKind.READ
    side_effect = SideEffect.READ
    scopes = ["fs:read"]
    timeout_s = 10.0
    is_idempotent = True
    input_model = FsReadInput
    output_model = FsReadOutput

    async def run(self, args: FsReadInput, ctx: ToolContext) -> ToolResult:
        try:
            target_path = verify_workspace_path(args.path, ctx.workspace_root)
        except WorkspaceAccessError as exc:
            return ToolResult.failed(str(exc))

        if not target_path.exists():
            clean_search = args.path.strip("\"' .").lower()
            candidates = [
                f for f in ctx.workspace_root.rglob("*")
                if f.is_file() and (
                    clean_search == f.name.lower()
                    or (len(clean_search) >= 3 and clean_search in f.name.lower())
                    or (len(clean_search) >= 3 and f.stem.lower() in clean_search)
                )
            ]
            if len(candidates) >= 1:
                target_path = verify_workspace_path(candidates[0], ctx.workspace_root)
            else:
                return ToolResult.failed(f"File not found: {args.path}")

        if not target_path.is_file():
            return ToolResult.failed(f"Path is not a regular file: {args.path}")

        try:
            if target_path.suffix.lower() in SUPPORTED_RICH_EXTENSIONS:
                text = convert_document_to_markdown(target_path)
            else:
                raw_bytes = target_path.read_bytes()
                text = raw_bytes.decode("utf-8", errors="replace")

            clean_text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            raw_bytes = clean_text.encode("utf-8", errors="replace")
            total_bytes = len(raw_bytes)
            lines = clean_text.splitlines(keepends=True)
            total_lines = len(lines)
        except Exception as exc:
            return ToolResult.failed(f"Failed to read file '{args.path}': {exc}")

        # Refusal check for whole-file reads over threshold
        if args.start_line is None and args.end_line is None:
            if total_lines > MAX_LINE_THRESHOLD or total_bytes > MAX_BYTE_THRESHOLD:
                return ToolResult.failed(
                    f"File '{args.path}' exceeds size threshold (total_lines: {total_lines}, "
                    f"total_bytes: {total_bytes}). Specify line ranges "
                    "(e.g. start_line=1, end_line=200) to inspect within VRAM budget."
                )

        start = 1 if args.start_line is None else max(1, args.start_line)
        end = total_lines if args.end_line is None else min(total_lines, args.end_line)

        if start > total_lines and total_lines > 0:
            return ToolResult.failed(
                f"start_line ({start}) exceeds total line count ({total_lines}) for '{args.path}'"
            )

        selected_lines = lines[start - 1 : end]
        content = "".join(selected_lines)

        output = FsReadOutput(
            content=content,
            start_line=start,
            end_line=end,
            total_lines=total_lines,
            total_bytes=total_bytes,
        )
        return ToolResult.ok(output.model_dump())
