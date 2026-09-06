"""Tool for searching files by glob pattern within the workspace."""


from pydantic import BaseModel, Field

from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.workspace import WorkspaceAccessError, verify_workspace_path


class GlobInput(BaseModel):
    pattern: str = Field(description="Glob pattern (e.g. '**/*.py', 'docs/*.md')")
    path: str | None = Field(
        default=None, description="Relative sub-directory path to search within"
    )


class GlobOutput(BaseModel):
    matches: list[str]
    total_matches: int


class GlobTool(BaseTool[GlobInput, GlobOutput]):
    name = "glob"
    description = "Find workspace files matching a glob pattern."
    kind = ToolKind.SEARCH
    side_effect = SideEffect.READ
    scopes = ["fs:read"]
    timeout_s = 10.0
    is_idempotent = True
    input_model = GlobInput
    output_model = GlobOutput

    async def run(self, args: GlobInput, ctx: ToolContext) -> ToolResult:
        search_dir_str = args.path or "."
        try:
            search_dir = verify_workspace_path(search_dir_str, ctx.workspace_root)
        except WorkspaceAccessError as exc:
            return ToolResult.failed(str(exc))

        if not search_dir.exists() or not search_dir.is_dir():
            return ToolResult.failed(
                f"Search directory not found or not a directory: {search_dir_str}"
            )

        try:
            raw_matches = search_dir.glob(args.pattern)
            ws_root = ctx.workspace_root.resolve()
            matched_paths: list[str] = []

            for match in raw_matches:
                try:
                    resolved_match = verify_workspace_path(match, ws_root)
                    if resolved_match.is_file():
                        rel = resolved_match.relative_to(ws_root).as_posix()
                        matched_paths.append(rel)
                except WorkspaceAccessError:
                    continue  # Ignore files escaping workspace via symlinks

            matched_paths.sort()
            output = GlobOutput(matches=matched_paths, total_matches=len(matched_paths))
            return ToolResult.ok(output.model_dump())
        except Exception as exc:
            return ToolResult.failed(f"Glob search failed for pattern '{args.pattern}': {exc}")
