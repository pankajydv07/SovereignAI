"""Unified Deliverable Render Engine for SWARAJ.

Validates raw JSON payloads against Pydantic deliverable schemas, enforces citation rules,
constructs system-attested provenance metadata, and dispatches to DOCX, PPTX, or XLSX renderers.
"""

from pathlib import Path
from typing import Any

from renderers.docx_renderer import DocxRenderer
from renderers.pptx_renderer import PptxRenderer
from renderers.schemas import (
    ApprovalNoteSchema,
    CostSheetSchema,
    EngineeringCalculationSchema,
    InspectionSummarySchema,
    ReviewDeckSchema,
    SystemProvenanceMetadata,
    validate_citations,
)
from renderers.templates import TemplateManager
from renderers.xlsx_renderer import XlsxRenderer


class DeliverableRenderEngine:
    """Unified engine for rendering typed deliverable documents."""

    def __init__(
        self,
        template_manager: TemplateManager | None = None,
        calc_execution_store: dict[str, Any] | None = None,
    ) -> None:
        self.template_manager = template_manager or TemplateManager()
        self.calc_execution_store = calc_execution_store or {}
        self.docx_renderer = DocxRenderer(self.template_manager)
        self.pptx_renderer = PptxRenderer(self.template_manager)
        self.xlsx_renderer = XlsxRenderer(self.template_manager)

    def render(
        self,
        deliverable_type: str,
        data: dict[str, Any],
        run_id: str,
        output_path: Path | str,
        models_used: list[str] | None = None,
        min_confidence: float = 0.95,
        human_verified_count: int = 0,
        template_name: str | None = None,
    ) -> Path:
        """Validate payload and render target deliverable document file."""
        out_path = Path(output_path)
        d_type = deliverable_type.lower().strip()

        # Parse & Validate Schema
        schema_obj = self._parse_schema(d_type, data)
        validate_citations(schema_obj)

        # Collect cited sources
        sources_cited = self._extract_sources(schema_obj)

        # Construct System Provenance Metadata from execution facts
        prov = SystemProvenanceMetadata(
            run_id=run_id,
            models_used=models_used or ["qwen3-coder:30b"],
            sources_cited=sources_cited,
            min_confidence=min_confidence,
            human_verified_count=human_verified_count,
        )

        # Dispatch Rendering
        if d_type == "approval_note":
            assert isinstance(schema_obj, ApprovalNoteSchema)
            return self.docx_renderer.render_approval_note(
                schema_obj, prov, out_path, template_name
            )

        elif d_type in ("inspection_summary", "inspection_report"):
            assert isinstance(schema_obj, InspectionSummarySchema)
            return self.docx_renderer.render_inspection_summary(
                schema_obj, prov, out_path, template_name
            )

        elif d_type == "review_deck":
            assert isinstance(schema_obj, ReviewDeckSchema)
            return self.pptx_renderer.render_review_deck(
                schema_obj,
                prov,
                out_path,
                template_name,
            )

        elif d_type == "cost_sheet":
            assert isinstance(schema_obj, CostSheetSchema)
            return self.xlsx_renderer.render_cost_sheet(schema_obj, prov, out_path)

        elif d_type == "engineering_calculation":
            assert isinstance(schema_obj, EngineeringCalculationSchema)
            calc_record = self.calc_execution_store.get(schema_obj.calc_run_id, {})
            return self.xlsx_renderer.render_engineering_calculation(
                schema_obj, prov, calc_record, out_path
            )

        else:
            raise ValueError(f"Unsupported deliverable type: {deliverable_type}")

    def _parse_schema(self, d_type: str, data: dict[str, Any]) -> Any:
        """Parse raw dictionary into Pydantic deliverable model."""
        if d_type == "approval_note":
            return ApprovalNoteSchema.model_validate(data)
        elif d_type in ("inspection_summary", "inspection_report"):
            return InspectionSummarySchema.model_validate(data)
        elif d_type == "review_deck":
            return ReviewDeckSchema.model_validate(data)
        elif d_type == "cost_sheet":
            return CostSheetSchema.model_validate(data)
        elif d_type == "engineering_calculation":
            return EngineeringCalculationSchema.model_validate(data)
        else:
            raise ValueError(f"Unknown deliverable type: {d_type}")

    def _extract_sources(self, schema_obj: Any) -> list[str]:
        """Collect all doc_ids cited across fields."""
        sources = set()
        if hasattr(schema_obj, "observations"):
            for obs in getattr(schema_obj, "observations", []):
                for c in getattr(obs, "citations", []):
                    sources.add(c.doc_id)
        if hasattr(schema_obj, "recommendation"):
            for rec in getattr(schema_obj, "recommendation", []):
                for c in getattr(rec, "citations", []):
                    sources.add(c.doc_id)
        if hasattr(schema_obj, "recommendations"):
            for rec in getattr(schema_obj, "recommendations", []):
                for c in getattr(rec, "citations", []):
                    sources.add(c.doc_id)
        if hasattr(schema_obj, "findings"):
            for f in getattr(schema_obj, "findings", []):
                for c in getattr(f, "citations", []):
                    sources.add(c.doc_id)
                for fid in getattr(f, "extracted_field_ids", []):
                    sources.add(fid)
        if hasattr(schema_obj, "observed_defects"):
            for d in getattr(schema_obj, "observed_defects", []):
                for c in getattr(d, "citations", []):
                    sources.add(c.doc_id)
        if hasattr(schema_obj, "citations"):
            for c in getattr(schema_obj, "citations", []):
                sources.add(c.doc_id)
        return sorted(list(sources))
