"""Tool for listing workspace directory contents."""


from pydantic import BaseModel, Field

from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.workspace import WorkspaceAccessError, verify_workspace_path


class DirectoryEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size_bytes: int


class FsListInput(BaseModel):
    path: str = Field(default=".", description="Relative directory path to list")


class FsListOutput(BaseModel):
    entries: list[DirectoryEntry]
    total_entries: int


class FsListTool(BaseTool[FsListInput, FsListOutput]):
    name = "fs_list"
    description = "List entries (files and directories) inside a workspace directory."
    kind = ToolKind.READ
    side_effect = SideEffect.READ
    scopes = ["fs:read"]
    timeout_s = 5.0
    is_idempotent = True
    input_model = FsListInput
    output_model = FsListOutput

    async def run(self, args: FsListInput, ctx: ToolContext) -> ToolResult:
        try:
            target_path = verify_workspace_path(args.path, ctx.workspace_root)
        except WorkspaceAccessError as exc:
            return ToolResult.failed(str(exc))

        if not target_path.exists():
            return ToolResult.failed(f"Directory not found: {args.path}")
        if not target_path.is_dir():
            return ToolResult.failed(f"Path is not a directory: {args.path}")

        try:
            entries: list[DirectoryEntry] = []
            for child in sorted(target_path.iterdir()):
                try:
                    rel_path = child.relative_to(ctx.workspace_root.resolve()).as_posix()
                except ValueError:
                    rel_path = child.name

                is_directory = child.is_dir()
                size_bytes = 0 if is_directory else child.stat().st_size
                entries.append(
                    DirectoryEntry(
                        name=child.name,
                        path=rel_path,
                        is_dir=is_directory,
                        size_bytes=size_bytes,
                    )
                )

            output = FsListOutput(entries=entries, total_entries=len(entries))
            return ToolResult.ok(output.model_dump())
        except Exception as exc:
            return ToolResult.failed(f"Failed to list directory '{args.path}': {exc}")
