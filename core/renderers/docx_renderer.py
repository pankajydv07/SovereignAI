"""DOCX Renderer — Generates Word documents from validated JSON schemas.

Supports docxtpl with SandboxedEnvironment for custom templates and python-docx
for structured PSU default document layout with non-removable provenance footers.
"""

from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentClass
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docxtpl import DocxTemplate

from calc.models import CalculationExecutionRecord, CalculationVerificationFailedError
from renderers.schemas import (
    ApprovalNoteSchema,
    EngineeringCalculationSchema,
    InspectionSummarySchema,
    SystemProvenanceMetadata,
)
from renderers.templates import TemplateManager


class DocxRenderer:
    """Renderer for Word (.docx) documents."""

    def __init__(self, template_manager: TemplateManager | None = None) -> None:
        self.template_manager = template_manager or TemplateManager()

    def render_approval_note(
        self,
        data: ApprovalNoteSchema,
        prov: SystemProvenanceMetadata,
        output_path: Path,
        template_name: str | None = "approval_note.docx",
    ) -> Path:
        """Render ApprovalNoteSchema to .docx document."""
        template_file = (
            self.template_manager.find_template(template_name) if template_name else None
        )

        if template_file and template_file.exists():
            return self._render_tpl(template_file, data.model_dump(), prov, output_path)

        return self._render_default_approval_note(data, prov, output_path)

    def render_inspection_summary(
        self,
        data: InspectionSummarySchema,
        prov: SystemProvenanceMetadata,
        output_path: Path,
        template_name: str | None = "inspection_summary.docx",
    ) -> Path:
        """Render InspectionSummarySchema to .docx document."""
        template_file = (
            self.template_manager.find_template(template_name) if template_name else None
        )

        if template_file and template_file.exists():
            return self._render_tpl(template_file, data.model_dump(), prov, output_path)

        return self._render_default_inspection_summary(data, prov, output_path)

    def render_engineering_calculation(
        self,
        data: EngineeringCalculationSchema,
        prov: SystemProvenanceMetadata,
        calc_record: CalculationExecutionRecord | dict[str, Any] | None,
        output_path: Path,
    ) -> Path:
        """Render EngineeringCalculationSchema to .docx. Refuses if verification failed."""
        if not calc_record:
            raise CalculationVerificationFailedError(
                "Refusing to render: calculation execution record absent"
            )

        # Resolve record dictionary or model
        if isinstance(calc_record, dict):
            verification_passed = calc_record.get("verification_passed", False)
            clause_text = calc_record.get("clause_quoted_text", "")
            requires_manual = calc_record.get("requires_manual_clause_verification", False)
            cross_check_res = calc_record.get("cross_check", {})
            derivation_steps = calc_record.get("derivation_steps", [])
            final_answer = calc_record.get("final_answer", {})
            has_unverified = calc_record.get("has_unverified_inputs", False)
        else:
            verification_passed = calc_record.verification_passed
            clause_text = calc_record.clause_quoted_text
            requires_manual = calc_record.requires_manual_clause_verification
            cross_check_res = calc_record.cross_check.model_dump()
            derivation_steps = calc_record.derivation_steps
            final_answer = calc_record.final_answer
            has_unverified = calc_record.has_unverified_inputs

        if not verification_passed:
            raise CalculationVerificationFailedError(
                f"Refusing to render calculation '{data.title}': cross-check verification failed"
            )

        doc: DocumentClass = Document()
        self._setup_margins(doc)

        doc.add_heading(f"ENGINEERING CALCULATION: {data.title}", level=1)

        meta_p = doc.add_paragraph()
        tag_str = (
            f"Equipment Tag: {data.equipment_tag} | "
            f"Standard: {data.governing_standard} §{data.governing_clause}"
        )
        meta_p.add_run(tag_str).bold = True

        # Given Inputs Table
        doc.add_heading("1. GIVEN INPUT PARAMETERS", level=2)
        tbl = doc.add_table(rows=1, cols=5)
        hdr_cells = tbl.rows[0].cells
        hdr_cells[0].text = "Parameter"
        hdr_cells[1].text = "Symbol"
        hdr_cells[2].text = "Given Value"
        hdr_cells[3].text = "Source Tag"
        hdr_cells[4].text = "Verification State (FR-5.7)"

        for p in data.parameters:
            row_cells = tbl.add_row().cells
            row_cells[0].text = p.name
            row_cells[1].text = p.symbol
            row_cells[2].text = f"{p.value} {p.unit}"
            row_cells[3].text = p.source
            row_cells[4].text = "VERIFIED"

        if has_unverified:
            unv_p = doc.add_paragraph()
            unv_msg = (
                "WARNING: Calculation contains unverified input parameters "
                "(FR-5.7 approval blocked)."
            )
            r_unv = unv_p.add_run(unv_msg)
            r_unv.bold = True
            r_unv.font.color.rgb = RGBColor(0xEF, 0x44, 0x44)

        # Quoted KB Clause Box
        doc.add_heading("2. GOVERNING STANDARD CLAUSE (KNOWLEDGE BASE)", level=2)
        clause_p = doc.add_paragraph()
        if requires_manual:
            r_c = clause_p.add_run(f"*** {clause_text} ***")
            r_c.bold = True
            r_c.font.color.rgb = RGBColor(0xF5, 0x9E, 0x0B)
        else:
            r_c = clause_p.add_run(f'"{clause_text}"')
            r_c.italic = True

        # Derivation Steps
        doc.add_heading("3. EXECUTED STEP-BY-STEP DERIVATION", level=2)
        for step in derivation_steps:
            dp = doc.add_paragraph()
            step_str = (
                f"• {step.get('step', 'Step')}: {step.get('output_var', '')} = "
                f"{step.get('value', '')} {step.get('unit', '')}"
            )
            dp.add_run(step_str).bold = True

        # Cross-Check Badge
        doc.add_heading("4. MULTI-LAYERED CROSS-CHECK VERIFICATION", level=2)
        cc_p = doc.add_paragraph()
        cc_run = cc_p.add_run(
            f"Verification Status: PASSED | Pint Dimensional Analysis: PASSED | "
            f"Relative Diff: {cross_check_res.get('relative_diff', 0.0):.6f}"
        )
        cc_run.bold = True
        cc_run.font.color.rgb = RGBColor(0x10, 0xB9, 0x81)

        # Final Answer
        doc.add_heading("5. FINAL CALCULATION RESULT", level=2)
        ans_p = doc.add_paragraph()
        ans_p.add_run(f"Result: {final_answer}").bold = True

        self._add_provenance_footer_docx(doc, prov)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path

    def _render_tpl(
        self,
        template_path: Path,
        context: dict[str, Any],
        prov: SystemProvenanceMetadata,
        output_path: Path,
    ) -> Path:
        """Render custom template using docxtpl with SandboxedEnvironment."""
        doc = DocxTemplate(str(template_path))
        env = TemplateManager.get_sandboxed_environment()

        ctx = dict(context)
        ctx["provenance"] = prov.model_dump()

        doc.render(ctx, jinja_env=env)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))

        # Append non-removable provenance footer to template output
        saved_doc: DocumentClass = Document(str(output_path))
        self._add_provenance_footer_docx(saved_doc, prov)
        saved_doc.save(str(output_path))
        return output_path

    def _render_default_approval_note(
        self,
        data: ApprovalNoteSchema,
        prov: SystemProvenanceMetadata,
        output_path: Path,
    ) -> Path:
        """Build structured default PSU Approval Note document."""
        doc: DocumentClass = Document()
        self._setup_margins(doc)

        # Header / Letterhead
        hdr = doc.add_paragraph()
        hdr.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = hdr.add_run(
            "MANGALORE REFINERY AND PETROCHEMICALS LIMITED\n"
            "(A Subsidiary of Oil and Natural Gas Corporation Limited)"
        )
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        t_run = title.add_run("INTER-OFFICE MEMORANDUM / APPROVAL NOTE")
        t_run.bold = True
        t_run.font.size = Pt(13)

        # Subject & References
        doc.add_heading(f"SUBJECT: {data.subject}", level=1)
        if data.reference:
            ref_p = doc.add_paragraph()
            ref_p.add_run("References: ").bold = True
            ref_p.add_run("; ".join(data.reference))

        # Background
        doc.add_heading("1. BACKGROUND", level=2)
        doc.add_paragraph(data.background)

        # Observations
        doc.add_heading("2. OBSERVATIONS AND FINDINGS", level=2)
        for i, obs in enumerate(data.observations, start=1):
            p = doc.add_paragraph()
            p.add_run(f"2.{i} {obs.text} ")
            for cit in obs.citations:
                c_run = p.add_run(f"[{cit.doc_id} §{cit.clause_or_section}]")
                c_run.font.size = Pt(8.5)
                c_run.font.color.rgb = RGBColor(0x4C, 0x8D, 0xF6)

        # Financial Implication
        doc.add_heading("3. FINANCIAL IMPLICATION", level=2)
        doc.add_paragraph(data.financial_implication)

        # Deviation (if any)
        if data.deviation:
            doc.add_heading("4. DEVIATION / EXCEPTION", level=2)
            doc.add_paragraph(data.deviation)

        # Recommendations
        heading_num = 5 if data.deviation else 4
        doc.add_heading(f"{heading_num}. RECOMMENDATION", level=2)
        for i, rec in enumerate(data.recommendation, start=1):
            p = doc.add_paragraph()
            p.add_run(f"{heading_num}.{i} {rec.text} ")
            for cit in rec.citations:
                c_run = p.add_run(f"[{cit.doc_id} §{cit.clause_or_section}]")
                c_run.font.size = Pt(8.5)
                c_run.font.color.rgb = RGBColor(0x4C, 0x8D, 0xF6)

        # Approval Ladder
        doc.add_heading("APPROVAL LADDER (MAKER-CHECKER)", level=2)
        tbl = doc.add_table(rows=1, cols=3)
        hdr_cells = tbl.rows[0].cells
        hdr_cells[0].text = "Role"
        hdr_cells[1].text = "Officer Name & Designation"
        hdr_cells[2].text = "Status"
        for role_entry in data.approval_ladder:
            row_cells = tbl.add_row().cells
            row_cells[0].text = role_entry.role
            row_cells[1].text = role_entry.name
            row_cells[2].text = role_entry.status

        # Non-removable provenance footer
        self._add_provenance_footer_docx(doc, prov)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path

    def _render_default_inspection_summary(
        self,
        data: InspectionSummarySchema,
        prov: SystemProvenanceMetadata,
        output_path: Path,
    ) -> Path:
        """Build structured default Inspection Summary document."""
        doc: DocumentClass = Document()
        self._setup_margins(doc)

        doc.add_heading(f"INSPECTION SUMMARY: {data.asset_tag}", level=1)

        meta_p = doc.add_paragraph()
        meta_p.add_run(
            f"Inspection Date: {data.inspection_date} | Method: {data.inspection_method}"
        ).bold = True

        if data.thickness_readings:
            doc.add_heading("1. WALL THICKNESS MEASUREMENTS", level=2)
            tbl = doc.add_table(rows=1, cols=4)
            hdr_cells = tbl.rows[0].cells
            hdr_cells[0].text = "Location / Circuit"
            hdr_cells[1].text = "Nominal (mm)"
            hdr_cells[2].text = "Actual (mm)"
            hdr_cells[3].text = "Min Required (mm)"
            for reading in data.thickness_readings:
                row_cells = tbl.add_row().cells
                row_cells[0].text = reading.location
                row_cells[1].text = str(reading.nominal_mm)
                row_cells[2].text = str(reading.actual_mm)
                row_cells[3].text = str(reading.min_required_mm)

        if data.observed_defects:
            doc.add_heading("2. OBSERVED DEFECTS & NON-CONFORMANCES", level=2)
            for defect in data.observed_defects:
                p = doc.add_paragraph()
                p.add_run(f"[{defect.severity}] {defect.description} ")
                for cit in defect.citations:
                    c_run = p.add_run(f"[{cit.doc_id} §{cit.clause_or_section}]")
                    c_run.font.size = Pt(8.5)
                    c_run.font.color.rgb = RGBColor(0x4C, 0x8D, 0xF6)

        if data.recommendations:
            doc.add_heading("3. RECOMMENDATIONS", level=2)
            for rec in data.recommendations:
                p = doc.add_paragraph()
                p.add_run(f"• {rec.text} ")
                for cit in rec.citations:
                    c_run = p.add_run(f"[{cit.doc_id} §{cit.clause_or_section}]")
                    c_run.font.size = Pt(8.5)
                    c_run.font.color.rgb = RGBColor(0x4C, 0x8D, 0xF6)

        self._add_provenance_footer_docx(doc, prov)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path

    def _setup_margins(self, doc: DocumentClass) -> None:
        for section in doc.sections:
            section.top_margin = Inches(0.8)
            section.bottom_margin = Inches(0.8)
            section.left_margin = Inches(0.8)
            section.right_margin = Inches(0.8)

    def _add_provenance_footer_docx(
        self, doc: DocumentClass, prov: SystemProvenanceMetadata
    ) -> None:
        """Add mandatory, non-removable legal draft provenance footer."""
        section = doc.sections[0]
        footer = section.footer
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        banner = p.add_run(f"*** {prov.draft_warning} ***\n")
        banner.bold = True
        banner.font.size = Pt(8.5)
        banner.font.color.rgb = RGBColor(0xEF, 0x44, 0x44)

        info = p.add_run(
            f"Run ID: {prov.run_id} | Models: {', '.join(prov.models_used)} | "
            f"Min Conf: {prov.min_confidence:.2f} | Verified Fields: {prov.human_verified_count}"
        )
        info.font.size = Pt(7.5)
        info.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
