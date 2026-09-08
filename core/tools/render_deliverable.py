"""Render Deliverable Tool — Agent tool for rendering real files from validated JSON."""

from typing import Any

from pydantic import Field, ValidationError

from protocol.models import ProtocolBaseModel
from renderers.schemas import UncitedClaimError
from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.workspace import WorkspaceAccessError, verify_workspace_path


class RenderDeliverableInput(ProtocolBaseModel):
    """Input model for deliverable rendering tool."""

    deliverable_type: str = Field(
        alias="deliverableType",
        description="Target deliverable type name",
    )
    data: dict[str, Any] = Field(description="Deliverable JSON payload matching the target schema")
    output_filename: str = Field(
        alias="outputFilename",
        description="Output file name (e.g. approval_note_101.docx, cost_sheet.xlsx, review.pptx)",
    )
    template_name: str | None = Field(
        default=None,
        alias="templateName",
        description="Optional custom template file name",
    )


class RenderDeliverableOutput(ProtocolBaseModel):
    """Output model for deliverable rendering tool."""

    file_path: str = Field(alias="filePath")
    deliverable_type: str = Field(alias="deliverableType")
    run_id: str = Field(alias="runId")
    success: bool = Field(default=True)


class RenderDeliverableTool(BaseTool[RenderDeliverableInput, RenderDeliverableOutput]):
    """Tool for rendering real DOCX, PPTX, and XLSX files from schema-validated JSON."""

    name = "render_deliverable"
    description = (
        "Render deterministic deliverable files (.docx, .pptx, .xlsx) from validated JSON schemas"
    )
    kind = ToolKind.OTHER
    side_effect = SideEffect.WRITE
    scopes = ["workspace:write"]
    timeout_s = 30.0
    is_idempotent = True
    input_model = RenderDeliverableInput
    output_model = RenderDeliverableOutput

    def __init__(self, engine: Any | None = None) -> None:
        if engine is None:
            from renderers.engine import DeliverableRenderEngine

            self.engine = DeliverableRenderEngine()
        else:
            self.engine = engine

    async def run(self, args: RenderDeliverableInput, ctx: ToolContext) -> ToolResult:
        run_id = f"render_{ctx.session_id}"
        if args.deliverable_type == "review_deck":
            return ToolResult.failed(
                "Governed review decks are not yet available and cannot enter the approval workflow"
            )

        try:
            out_path = verify_workspace_path(args.output_filename, ctx.workspace_root)
        except WorkspaceAccessError as exc:
            return ToolResult.failed(str(exc))

        try:
            rendered_file = self.engine.render(
                deliverable_type=args.deliverable_type,
                data=args.data,
                run_id=run_id,
                output_path=out_path,
                template_name=args.template_name,
            )
            output = RenderDeliverableOutput(
                filePath=str(rendered_file.resolve()),
                deliverableType=args.deliverable_type,
                runId=run_id,
                success=True,
            )
            return ToolResult.ok(output)

        except (ValidationError, UncitedClaimError, ValueError) as exc:
            # Return detailed validation error for turn loop repair path (max 2 repair rounds)
            return ToolResult.failed(f"ValidationError: {exc}")
        except Exception as exc:
            return ToolResult.failed(f"Render failed: {exc}")



