"""Format-Specific Provenance Injection for SWARAJ Documents.

Injects non-removable legal draft attestation banners and metadata into:
- DOCX (python-docx footer)
- XLSX (openpyxl _Attestation_Provenance worksheet)
- PPTX (python-pptx attestation closing slide)
- PDF (pypdf transparent ReportLab overlay)
- Markdown (GFM provenance attestation block)
"""

from io import BytesIO
from pathlib import Path

import openpyxl
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


def inject_docx_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    """Inject legal draft attestation into DOCX footer."""
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


def inject_xlsx_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    """Inject legal draft attestation into XLSX _Attestation_Provenance worksheet."""
    wb = openpyxl.load_workbook(str(file_path))
    ws_name = "_Attestation_Provenance"
    if ws_name in wb.sheetnames:
        del wb[ws_name]

    ws = wb.create_sheet(title=ws_name)
    ws.views.sheetView[0].showGridLines = True

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


def inject_pptx_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    """Inject legal draft attestation into closing PPTX slide."""
    prs = Presentation(str(file_path))
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    slide = prs.slides.add_slide(blank_layout)

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


def inject_pdf_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    """Inject legal draft attestation into PDF via transparent ReportLab overlay."""
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

        overlay_buffer = BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

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


def inject_md_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    """Inject legal draft attestation into Markdown document."""
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
