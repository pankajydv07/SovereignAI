"""Tool for ingesting scanned or born-digital documents with provenance tracking."""

from typing import Any

from pydantic import Field

from ingest.pipeline import DocumentIngestPipeline
from protocol.models import ProtocolBaseModel
from tools.base import BaseTool, SideEffect, ToolContext, ToolKind, ToolResult
from tools.workspace import WorkspaceAccessError, verify_workspace_path


class DocIngestInput(ProtocolBaseModel):
    """Input model for document ingestion tool."""

    path: str = Field(description="Relative or absolute workspace path to document (PDF or image)")


class DocIngestOutput(ProtocolBaseModel):
    """Output model for document ingestion tool."""

    doc_path: str = Field(alias="docPath", description="Path to ingested document")
    classification: str = Field(
        description="Document classification (BORN_DIGITAL, SCANNED, HYBRID)"
    )
    total_pages: int = Field(alias="totalPages", description="Total processed pages")
    total_fields: int = Field(alias="totalFields", description="Total extracted fields")
    fields: list[dict[str, Any]] = Field(
        description="List of extracted fields with bounding box provenance"
    )


class DocIngestTool(BaseTool[DocIngestInput, DocIngestOutput]):
    """Tool for scanned and born-digital document ingestion."""

    name = "doc_ingest"
    description = (
        "Ingest a document (PDF or scanned image) to classify text layer structure, "
        "segment layout regions, and extract structured fields with bounding-box provenance."
    )
    kind = ToolKind.READ
    side_effect = SideEffect.READ
    scopes = ["doc:ingest"]
    timeout_s = 60.0
    is_idempotent = True
    input_model = DocIngestInput
    output_model = DocIngestOutput

    async def run(self, args: DocIngestInput, ctx: ToolContext) -> ToolResult:
        try:
            target_path = verify_workspace_path(args.path, ctx.workspace_root)
        except WorkspaceAccessError as exc:
            return ToolResult.failed(str(exc))

        if not target_path.exists():
            return ToolResult.failed(f"Document not found: {args.path}")

        pipeline = DocumentIngestPipeline()
        try:
            res = await pipeline.ingest_document(target_path)
        except Exception as exc:
            return ToolResult.failed(f"Ingestion pipeline failed: {exc}")
        finally:
            pipeline.shutdown()

        raw_fields = [f.model_dump(by_alias=True) for f in res.fields]

        output = DocIngestOutput(
            docPath=res.doc_path,
            classification=res.classification.value,
            totalPages=len(res.pages),
            totalFields=len(res.fields),
            fields=raw_fields,
        )
        return ToolResult.ok(output.model_dump(by_alias=True))
