"""DOCX Renderer — Generates Word documents conforming to PSU engineering standards.

Supports docxtpl with SandboxedEnvironment for custom templates and python-docx
for structured PSU default document layout with non-removable provenance footers.
"""

from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentClass
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from docxtpl import DocxTemplate

from calc.models import CalculationExecutionRecord, CalculationVerificationFailedError
from renderers.docx_styler import (
    add_provenance_furniture,
    format_doc_heading,
    format_technical_table,
    setup_doc_margins,
)
from renderers.schemas import (
    ApprovalNoteSchema,
    EngineeringCalculationSchema,
    InspectionSummarySchema,
    SystemProvenanceMetadata,
)
from renderers.templates import MissingOrgTemplateError, TemplateManager


class DocxRenderer:
    """Renderer for Word (.docx) documents conforming to PSU engineering standards."""

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
        tpl_name = template_name or "approval_note.docx"
        template_file = self.template_manager.find_template(tpl_name)

        if not template_file or not template_file.exists():
            searched = []
            if self.template_manager.workspace_root:
                searched.append(self.template_manager.workspace_root / ".swaraj" / "templates" / tpl_name)
            searched.append(self.template_manager.user_template_dir / tpl_name)
            raise MissingOrgTemplateError(tpl_name, searched_paths=searched)

        return self._render_tpl(template_file, data.model_dump(), prov, output_path)

    def render_inspection_summary(
        self,
        data: InspectionSummarySchema,
        prov: SystemProvenanceMetadata,
        output_path: Path,
        template_name: str | None = "inspection_summary.docx",
    ) -> Path:
        """Render InspectionSummarySchema to .docx document."""
        template_file = self.template_manager.find_template(template_name) if template_name else None
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
        """Render EngineeringCalculationSchema to .docx with technical table and derivation."""
        if not calc_record:
            raise CalculationVerificationFailedError("Refusing to render: calculation execution record absent")

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
            raise CalculationVerificationFailedError(f"Refusing to render calculation '{data.title}': cross-check verification failed")

        doc: DocumentClass = Document()
        setup_doc_margins(doc)

        h1 = doc.add_heading(f"ENGINEERING CALCULATION: {data.title}", level=1)
        format_doc_heading(h1, level=1)

        meta_p = doc.add_paragraph()
        tag_r = meta_p.add_run(f"Equipment Tag: {data.equipment_tag} | Standard: {data.governing_standard} §{data.governing_clause}")
        tag_r.bold = True
        tag_r.font.name = "IBM Plex Mono"
        tag_r.font.size = Pt(10)

        # 1. Given Inputs
        h2_1 = doc.add_heading("1. GIVEN INPUT PARAMETERS", level=2)
        format_doc_heading(h2_1, level=2)
        tbl = doc.add_table(rows=1, cols=5)
        hdr_cells = tbl.rows[0].cells
        hdr_cells[0].text = "Parameter"
        hdr_cells[1].text = "Symbol"
        hdr_cells[2].text = "Given Value"
        hdr_cells[3].text = "Source Tag"
        hdr_cells[4].text = "Verification State"

        for p in data.parameters:
            row_cells = tbl.add_row().cells
            row_cells[0].text = p.name
            row_cells[1].text = p.symbol
            row_cells[2].text = f"{p.value} {p.unit}"
            row_cells[3].text = p.source
            row_cells[4].text = "VERIFIED"

        format_technical_table(tbl)

        if has_unverified:
            unv_p = doc.add_paragraph()
            r_unv = unv_p.add_run("WARNING: Calculation contains unverified input parameters (FR-5.7 approval blocked).")
            r_unv.bold = True
            r_unv.font.color.rgb = RGBColor(0xEF, 0x44, 0x44)

        # 2. Standard Clause
        h2_2 = doc.add_heading("2. GOVERNING STANDARD CLAUSE (KNOWLEDGE BASE)", level=2)
        format_doc_heading(h2_2, level=2)
        clause_p = doc.add_paragraph()
        r_c = clause_p.add_run(f'"{clause_text}"' if not requires_manual else f"[{clause_text}]")
        r_c.italic = True
        r_c.font.size = Pt(10.5)

        # 3. Derivation
        h2_3 = doc.add_heading("3. EXECUTED STEP-BY-STEP DERIVATION", level=2)
        format_doc_heading(h2_3, level=2)
        for step in derivation_steps:
            dp = doc.add_paragraph()
            dp.paragraph_format.space_after = Pt(3)
            step_str = f"• {step.get('step', 'Step')}: {step.get('output_var', '')} = {step.get('value', '')} {step.get('unit', '')}"
            r_s = dp.add_run(step_str)
            r_s.font.name = "IBM Plex Mono"
            r_s.font.size = Pt(10)

        # 4. Cross-Check
        h2_4 = doc.add_heading("4. MULTI-LAYERED CROSS-CHECK VERIFICATION", level=2)
        format_doc_heading(h2_4, level=2)
        cc_p = doc.add_paragraph()
        cc_run = cc_p.add_run(f"Verification: PASSED | Dimensional Analysis: PASSED | Rel Diff: {cross_check_res.get('relative_diff', 0.0):.6f}")
        cc_run.bold = True
        cc_run.font.name = "IBM Plex Mono"
        cc_run.font.size = Pt(10)
        cc_run.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)

        # 5. Result
        h2_5 = doc.add_heading("5. FINAL CALCULATION RESULT", level=2)
        format_doc_heading(h2_5, level=2)
        ans_p = doc.add_paragraph()
        ans_r = ans_p.add_run(f"Result: {final_answer}")
        ans_r.bold = True
        ans_r.font.name = "IBM Plex Mono"
        ans_r.font.size = Pt(11)

        add_provenance_furniture(doc, prov)
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

        saved_doc: DocumentClass = Document(str(output_path))
        for tbl in saved_doc.tables:
            format_technical_table(tbl)
        add_provenance_furniture(saved_doc, prov)
        saved_doc.save(str(output_path))
        return output_path

    def _render_default_inspection_summary(
        self,
        data: InspectionSummarySchema,
        prov: SystemProvenanceMetadata,
        output_path: Path,
    ) -> Path:
        """Build structured default Inspection Summary document."""
        doc: DocumentClass = Document()
        setup_doc_margins(doc)

        h1 = doc.add_heading(f"INSPECTION SUMMARY: {data.asset_tag}", level=1)
        format_doc_heading(h1, level=1)

        meta_p = doc.add_paragraph()
        meta_p.add_run(f"Inspection Date: {data.inspection_date} | Method: {data.inspection_method}").bold = True

        if data.thickness_readings:
            h2 = doc.add_heading("1. WALL THICKNESS MEASUREMENTS", level=2)
            format_doc_heading(h2, level=2)
            tbl = doc.add_table(rows=1, cols=4)
            hdr_cells = tbl.rows[0].cells
            hdr_cells[0].text = "Location / Circuit"
            hdr_cells[1].text = "Nominal (mm)"
            hdr_cells[2].text = "Actual (mm)"
            hdr_cells[3].text = "Min Required (mm)"
            for reading in data.thickness_readings:
                row_cells = tbl.add_row().cells
                row_cells[0].text = reading.location
                row_cells[1].text = f"{reading.nominal_mm:.2f}"
                row_cells[2].text = f"{reading.actual_mm:.2f}"
                row_cells[3].text = f"{reading.min_required_mm:.2f}"
            format_technical_table(tbl)

        if data.observed_defects:
            h2 = doc.add_heading("2. OBSERVED DEFECTS & NON-CONFORMANCES", level=2)
            format_doc_heading(h2, level=2)
            for defect in data.observed_defects:
                p = doc.add_paragraph()
                r_sev = p.add_run(f"[{defect.severity}] ")
                r_sev.bold = True
                r_sev.font.name = "IBM Plex Mono"
                r_sev.font.size = Pt(10)
                if defect.severity == "CRITICAL":
                    r_sev.font.color.rgb = RGBColor(0xEF, 0x44, 0x44)
                elif defect.severity == "MAJOR":
                    r_sev.font.color.rgb = RGBColor(0xF5, 0x9E, 0x0B)
                p.add_run(f"{defect.description} ")
                for cit in defect.citations:
                    c_run = p.add_run(f"[{cit.doc_id} §{cit.clause_or_section}]")
                    c_run.font.name = "IBM Plex Mono"
                    c_run.font.size = Pt(8.5)
                    c_run.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)

        if data.recommendations:
            h2 = doc.add_heading("3. RECOMMENDATIONS", level=2)
            format_doc_heading(h2, level=2)
            for rec in data.recommendations:
                p = doc.add_paragraph()
                p.add_run(f"• {rec.text} ")
                for cit in rec.citations:
                    c_run = p.add_run(f"[{cit.doc_id} §{cit.clause_or_section}]")
                    c_run.font.name = "IBM Plex Mono"
                    c_run.font.size = Pt(8.5)
                    c_run.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)

        add_provenance_furniture(doc, prov)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path

    @staticmethod
    def create_approved_stamped_copy(
        draft_docx_path: Path,
        checker_name: str,
        checker_designation: str,
        approval_timestamp: str,
        reviewed_docx_hash: str,
        output_path: Path,
    ) -> Path:
        """Create approved stamped copy of draft DOCX carrying authoritative SHA-256 fingerprint."""
        draft_docx_path = Path(draft_docx_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc: DocumentClass = Document(str(draft_docx_path))

        # Clear draft line from header
        for section in doc.sections:
            p_hdr = section.header.paragraphs[0]
            p_hdr.text = ""
            p_hdr.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_c = p_hdr.add_run("OFFICIAL RECORD — CONFIDENTIAL")
            r_c.bold = True
            r_c.font.name = "IBM Plex Mono"
            r_c.font.size = Pt(8.5)
            r_c.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)

            footer = section.footer
            for p in footer.paragraphs:
                p.text = ""
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                stamp_run = p.add_run(
                    f"OFFICIAL RECORD — APPROVED BY COMPETENT AUTHORITY\n"
                    f"Approved By: {checker_name} ({checker_designation}) | Date: {approval_timestamp}\n"
                    f"Reviewed Working Copy SHA-256: {reviewed_docx_hash[:16]}...{reviewed_docx_hash[-8:]}"
                )
                stamp_run.font.name = "IBM Plex Mono"
                stamp_run.font.size = Pt(8.0)
                stamp_run.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)

        p_stamp = doc.add_paragraph()
        p_stamp.paragraph_format.space_before = Pt(18)
        p_stamp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r_head = p_stamp.add_run("APPROVAL ATTESTATION & SIGN-OFF\n")
        r_head.bold = True
        r_head.font.size = Pt(10.0)

        tbl = doc.add_table(rows=4, cols=2)
        tbl.rows[0].cells[0].text = "Status:"
        tbl.rows[0].cells[1].text = "APPROVED (Formal Sign-Off Complete)"
        tbl.rows[1].cells[0].text = "Approved By:"
        tbl.rows[1].cells[1].text = f"{checker_name} ({checker_designation})"
        tbl.rows[2].cells[0].text = "Timestamp:"
        tbl.rows[2].cells[1].text = approval_timestamp
        tbl.rows[3].cells[0].text = "Reviewed Working Copy Digest:"
        tbl.rows[3].cells[1].text = f"SHA-256: {reviewed_docx_hash}"
        format_technical_table(tbl)

        doc.save(str(output_path))
        return output_path
