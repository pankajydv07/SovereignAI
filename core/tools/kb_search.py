"""Tool for Knowledge Base hybrid search with grounded citations and role filtering."""

from typing import Any

import structlog
from pydantic import Field

from kb.search import HybridSearchEngine
from protocol.models import ProtocolBaseModel
from storage.db import DatabaseManager
from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult

log = structlog.get_logger()


class KbSearchInput(ProtocolBaseModel):
    """Input model for knowledge base search tool."""

    query: str = Field(
        description="Search query or question to retrieve from knowledge base"
    )
    user_role: str = Field(
        alias="userRole",
        description="Requesting user role for security permission filtering",
    )
    include_superseded: bool = Field(
        default=False,
        alias="includeSuperseded",
        description="True to deliberately include superseded historical revisions",
    )


class KbSearchOutput(ProtocolBaseModel):
    """Output model for knowledge base search tool."""

    query: str
    user_role: str = Field(alias="userRole")
    total_results: int = Field(alias="totalResults")
    results: list[dict[str, Any]] = Field(description="List of cited search results")
    fallback_message: str | None = Field(
        default=None,
        alias="fallbackMessage",
        description="'not found in the knowledge base' if ungrounded",
    )


class KbSearchTool(BaseTool[KbSearchInput, KbSearchOutput]):
    """Tool for hybrid keyword/vector search over knowledge base with citations."""

    name = "kb_search"
    description = (
        "Search the knowledge base for SOPs, inspection procedures, and engineering clauses. "
        "Returns grounded citations with role permission filtering or fallback notification."
    )
    kind = ToolKind.SEARCH
    side_effect = SideEffect.READ
    scopes = ["kb:search"]
    timeout_s = 15.0
    is_idempotent = True
    input_model = KbSearchInput
    output_model = KbSearchOutput

    async def run(self, args: KbSearchInput, ctx: ToolContext) -> ToolResult:
        db_path = ctx.workspace_root / ".swaraj" / "sessions.db"
        db_mgr = DatabaseManager(db_path)
        engine = HybridSearchEngine()

        async with db_mgr.connect() as conn:
            await db_mgr.initialize_schema(conn)
            results, is_truncated, total_matches = await engine.retrieve_chunks(
                conn,
                user_role=args.user_role,
                query=args.query,
                include_superseded=args.include_superseded,
            )

        if not results:
            fallback = "not found in the knowledge base"
            output = KbSearchOutput(
                query=args.query,
                userRole=args.user_role,
                totalResults=0,
                results=[],
                fallbackMessage=fallback,
            )
            return ToolResult.ok(output.model_dump(by_alias=True))

        raw_results = [r.model_dump(by_alias=True) for r in results]
        output = KbSearchOutput(
            query=args.query,
            userRole=args.user_role,
            totalResults=len(results),
            results=raw_results,
            fallbackMessage=None,
        )
        return ToolResult.ok(output.model_dump(by_alias=True))
