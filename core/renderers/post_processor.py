"""Document Post-Processor & Provenance Injection.

Implements format-specific validation and provenance injection for:
- DOCX (python-docx header/footer paragraphs)
- XLSX (openpyxl _Attestation_Provenance worksheet + metadata)
- PPTX (python-pptx attestation closing slide)
- PDF (Per-page ReportLab transparent overlay merged via pypdf)
- Markdown (GFM frontmatter / provenance block)
"""

import re
from io import BytesIO
from pathlib import Path
from typing import Any

import openpyxl
import pdfplumber
from docx import Document
from docx.document import Document as DocumentClass
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from openpyxl.styles import Font, PatternFill
from pptx import Presentation
from pptx.dml.color import RGBColor as PptxRGBColor
from pptx.util import Inches
from pptx.util import Pt as PptxPt
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from renderers.schemas import SystemProvenanceMetadata


class DocumentValidationError(Exception):
    """Raised when generated document fails structural or cardinality validation."""


class ProvenanceSpoofError(DocumentValidationError):
    """Raised when script attempted to author its own provenance/attestation block."""


def scan_for_provenance_spoofing(file_path: Path, output_format: str) -> None:
    """Scan pre-injection document content for illicit manual provenance/attestation markers."""
    suspicious_patterns = [
        r"run[\s_-]?id\s*:",
        r"\*\*\*\s*draft[\s_-]?warning\s*\*\*\*",
        r"provenance[\s_-]?attestation",
        r"models[\s_-]?used\s*:",
        r"min[\s_-]?conf(idence)?\s*:",
    ]
    extracted_text = ""

    fmt = output_format.lower().strip()
    if fmt == "docx":
        doc = Document(str(file_path))
        extracted_text = " ".join([p.text for p in doc.paragraphs])
        for section in doc.sections:
            extracted_text += " " + " ".join([p.text for p in section.footer.paragraphs])
            extracted_text += " " + " ".join([p.text for p in section.header.paragraphs])

    elif fmt == "xlsx":
        wb = openpyxl.load_workbook(str(file_path), data_only=True)
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                extracted_text += " " + " ".join([str(v) for v in row if v is not None])

    elif fmt == "pptx":
        prs = Presentation(str(file_path))
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    extracted_text += " " + shape.text_frame.text

    elif fmt == "pdf":
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                extracted_text += " " + txt

    elif fmt == "md":
        extracted_text = file_path.read_text(encoding="utf-8")

    for pat in suspicious_patterns:
        if re.search(pat, extracted_text, re.IGNORECASE):
            raise ProvenanceSpoofError(
                f"Manual provenance marker detected matching '{pat}'. "
                "The system injects official provenance automatically. "
                "Remove any manual footer/attestation blocks from the script."
            )


def validate_generated_document(
    file_path: Path,
    output_format: str,
    input_data: dict[str, Any] | list[Any] | None = None,
    expects_full_tabulation: bool = False,
) -> dict[str, Any]:
    """Validate structure, non-emptiness, and cardinality of the generated document."""
    if not file_path.exists():
        raise DocumentValidationError(f"Generated file does not exist: {file_path}")

    fmt = output_format.lower().strip()
    metrics: dict[str, Any] = {"format": fmt, "fileSizeBytes": file_path.stat().st_size}

    # First: Check for illicit provenance spoofing and official deliverable structures
    scan_for_provenance_spoofing(file_path, fmt)
    from renderers.governance import scan_for_official_deliverable_structures

    scan_for_official_deliverable_structures(file_path, fmt)

    expected_row_count = 0
    if isinstance(input_data, list):
        expected_row_count = len(input_data)
    elif isinstance(input_data, dict):
        for val in input_data.values():
            if isinstance(val, list):
                expected_row_count = max(expected_row_count, len(val))

    if fmt == "docx":
        try:
            doc = Document(str(file_path))
            p_count = len(doc.paragraphs)
            t_count = len(doc.tables)
            total_table_rows = sum(len(t.rows) for t in doc.tables)
            metrics.update(
                {
                    "paragraphs": p_count,
                    "tables": t_count,
                    "tableRows": total_table_rows,
                }
            )
            if p_count == 0 and t_count == 0:
                raise DocumentValidationError("DOCX has zero paragraphs and zero tables")

            if expects_full_tabulation and expected_row_count > 0:
                if total_table_rows < expected_row_count:
                    raise DocumentValidationError(
                        f"DOCX table row count ({total_table_rows}) "
                        f"is less than expected input rows ({expected_row_count})"
                    )
        except Exception as exc:
            if isinstance(exc, DocumentValidationError):
                raise
            raise DocumentValidationError(f"Invalid DOCX document: {exc}") from exc

    elif fmt == "xlsx":
        try:
            wb = openpyxl.load_workbook(str(file_path), data_only=True)
            sheet_names = wb.sheetnames
            metrics["sheets"] = sheet_names
            if not sheet_names:
                raise DocumentValidationError("XLSX contains no sheets")

            first_sheet = wb.active
            row_count = first_sheet.max_row if first_sheet else 0
            metrics["maxRows"] = row_count
            if row_count < 1:
                raise DocumentValidationError("XLSX active worksheet has no rows")

            if expects_full_tabulation and expected_row_count > 0:
                if row_count < expected_row_count:
                    raise DocumentValidationError(
                        f"XLSX row count ({row_count}) "
                        f"is less than expected input rows ({expected_row_count})"
                    )
        except Exception as exc:
            if isinstance(exc, DocumentValidationError):
                raise
            raise DocumentValidationError(f"Invalid XLSX workbook: {exc}") from exc

    elif fmt == "pptx":
        try:
            prs = Presentation(str(file_path))
            slide_count = len(prs.slides)
            metrics["slides"] = slide_count
            if slide_count < 1:
                raise DocumentValidationError("PPTX contains zero slides")
        except Exception as exc:
            if isinstance(exc, DocumentValidationError):
                raise
            raise DocumentValidationError(f"Invalid PPTX presentation: {exc}") from exc

    elif fmt == "pdf":
        try:
            raw_bytes = file_path.read_bytes()
            if not raw_bytes.startswith(b"%PDF-"):
                raise DocumentValidationError("PDF missing standard %PDF- magic header")

            with pdfplumber.open(str(file_path)) as pdf:
                page_count = len(pdf.pages)
                metrics["pages"] = page_count
                if page_count < 1:
                    raise DocumentValidationError("PDF contains zero pages")

                total_chars = sum(len(p.extract_text() or "") for p in pdf.pages)
                metrics["charCount"] = total_chars
                if total_chars < 50:
                    raise DocumentValidationError("PDF has insufficient extracted text content")
        except Exception as exc:
            if isinstance(exc, DocumentValidationError):
                raise
            raise DocumentValidationError(f"Invalid PDF document: {exc}") from exc

    elif fmt == "md":
        content = file_path.read_text(encoding="utf-8")
        metrics["charCount"] = len(content)
        if len(content.strip()) < 10:
            raise DocumentValidationError("Markdown document is empty or too short")

    else:
        raise DocumentValidationError(f"Unsupported document format: {fmt}")

    return metrics


def _inject_docx_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    doc: DocumentClass = Document(str(file_path))
    sources_str = ", ".join(prov.sources_cited) if prov.sources_cited else "None"
    for section in doc.sections:
        footer = section.footer
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.text = ""

        banner = p.add_run(f"*** {prov.draft_warning} ***\n")
        banner.bold = True
        banner.font.size = Pt(8.5)
        banner.font.color.rgb = RGBColor(0xEF, 0x44, 0x44)

        info = p.add_run(
            f"Run ID: {prov.run_id} | Models: {', '.join(prov.models_used)} | "
            f"Min Conf: {prov.min_confidence:.2f} | Sources: {sources_str}"
        )
        info.font.size = Pt(7.5)
        info.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)

    doc.save(str(file_path))


def _inject_xlsx_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    wb = openpyxl.load_workbook(str(file_path))
    ws_name = "_Attestation_Provenance"
    if ws_name in wb.sheetnames:
        del wb[ws_name]

    ws = wb.create_sheet(title=ws_name)
    ws.views.sheetView[0].showGridLines = True

    # Title header
    ws["A1"] = "SWARAJ SYSTEM PROVENANCE ATTESTATION"
    ws["A1"].font = Font(name="Arial", size=11, bold=True, color="1F2328")
    ws["A1"].fill = PatternFill(start_color="D0D7DE", end_color="D0D7DE", fill_type="solid")

    meta_rows = [
        ("Draft Warning", prov.draft_warning),
        ("Run ID", prov.run_id),
        ("Models Used", ", ".join(prov.models_used)),
        ("Sources Cited", ", ".join(prov.sources_cited) if prov.sources_cited else "None"),
        ("Minimum Confidence", f"{prov.min_confidence:.2f}"),
        ("Human Verified Count", str(prov.human_verified_count)),
        ("Generated At", prov.timestamp_utc),
    ]

    for idx, (label, val) in enumerate(meta_rows, start=3):
        ws.cell(row=idx, column=1, value=label).font = Font(
            name="Arial", size=9, bold=True, color="57606A"
        )
        ws.cell(row=idx, column=2, value=val).font = Font(name="Arial", size=9, color="1F2328")

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 60

    wb.save(str(file_path))


def _inject_pptx_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    prs = Presentation(str(file_path))
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    slide = prs.slides.add_slide(blank_layout)

    # Background box
    bg = slide.shapes.add_shape(1, Inches(0.5), Inches(0.5), Inches(9.0), Inches(6.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = PptxRGBColor(0x12, 0x18, 0x21)
    bg.line.color.rgb = PptxRGBColor(0x26, 0x32, 0x41)

    tx_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.0), Inches(8.0), Inches(5.0))
    tf = tx_box.text_frame
    tf.word_wrap = True

    p_hdr = tf.paragraphs[0]
    p_hdr.text = f"*** {prov.draft_warning} ***"
    p_hdr.font.size = PptxPt(13)
    p_hdr.font.bold = True
    p_hdr.font.color.rgb = PptxRGBColor(0xEF, 0x44, 0x44)

    p_title = tf.add_paragraph()
    p_title.text = "System Provenance & Attestation Record"
    p_title.font.size = PptxPt(16)
    p_title.font.bold = True
    p_title.font.color.rgb = PptxRGBColor(0xE6, 0xED, 0xF3)

    records = [
        f"Run ID: {prov.run_id}",
        f"Models Used: {', '.join(prov.models_used)}",
        f"Sources Cited: {', '.join(prov.sources_cited) if prov.sources_cited else 'None'}",
        f"Minimum Confidence: {prov.min_confidence:.2f}",
        f"Human Verified Count: {prov.human_verified_count}",
        f"Timestamp (UTC): {prov.timestamp_utc}",
    ]
    for rec in records:
        p = tf.add_paragraph()
        p.text = f"• {rec}"
        p.font.size = PptxPt(10)
        p.font.color.rgb = PptxRGBColor(0x9A, 0xA7, 0xB4)

    prs.save(str(file_path))


def _inject_pdf_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    reader = PdfReader(str(file_path))
    writer = PdfWriter()
    sources_str = ", ".join(prov.sources_cited) if prov.sources_cited else "None"
    meta_line = (
        f"Run ID: {prov.run_id} | Models: {', '.join(prov.models_used)} | "
        f"Min Conf: {prov.min_confidence:.2f} | Sources: {sources_str}"
    )

    for _idx, page in enumerate(reader.pages):
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        # Generate transparent overlay canvas matching exact page dimensions
        overlay_buffer = BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

        # Bottom footer
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(HexColor("#EF4444"))
        c.drawCentredString(page_width / 2.0, 24, f"*** {prov.draft_warning} ***")

        c.setFont("Helvetica", 6.5)
        c.setFillColor(HexColor("#57606A"))
        c.drawCentredString(page_width / 2.0, 12, meta_line)
        c.save()

        overlay_buffer.seek(0)
        overlay_reader = PdfReader(overlay_buffer)
        overlay_page = overlay_reader.pages[0]

        page.merge_page(overlay_page)
        writer.add_page(page)


    with open(str(file_path), "wb") as f_out:
        writer.write(f_out)


def _inject_md_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    content = file_path.read_text(encoding="utf-8")
    provenance_block = (
        f"\n\n---\n"
        f"**PROVENANCE ATTESTATION**\n"
        f"- Warning: `{prov.draft_warning}`\n"
        f"- Run ID: `{prov.run_id}`\n"
        f"- Models Used: `{', '.join(prov.models_used)}`\n"
        f"- Sources Cited: `{', '.join(prov.sources_cited) if prov.sources_cited else 'None'}`\n"
        f"- Min Confidence: `{prov.min_confidence:.2f}`\n"
        f"- Timestamp: `{prov.timestamp_utc}`\n"
    )
    file_path.write_text(content + provenance_block, encoding="utf-8")


def inject_system_provenance(
    file_path: Path,
    output_format: str,
    prov: SystemProvenanceMetadata,
) -> Path:
    """Inject authoritative system provenance attestation into the validated document."""
    fmt = output_format.lower().strip()
    if fmt == "docx":
        _inject_docx_provenance(file_path, prov)
    elif fmt == "xlsx":
        _inject_xlsx_provenance(file_path, prov)
    elif fmt == "pptx":
        _inject_pptx_provenance(file_path, prov)
    elif fmt == "pdf":
        _inject_pdf_provenance(file_path, prov)
    elif fmt == "md":
        _inject_md_provenance(file_path, prov)
    else:
        raise ValueError(f"Unsupported format for provenance injection: {fmt}")

    return file_path
