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
    """Inject legal draft attestation into DOCX footer with IBM Plex Mono font."""
    doc: DocumentClass = Document(str(file_path))
    sources_str = ", ".join(prov.sources_cited) if prov.sources_cited else "None"
    for section in doc.sections:
        footer = section.footer
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.text = ""

        info = p.add_run(
            f"Run ID: {prov.run_id} | Models: {', '.join(prov.models_used)} | "
            f"Min Conf: {prov.min_confidence:.2f} | Sources: {sources_str}"
        )
        info.font.name = "IBM Plex Mono"
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
    ws["A1"].font = Font(name="Calibri", size=11, bold=True, color="1F2328")
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
            name="Calibri", size=9, bold=True, color="57606A"
        )
        ws.cell(row=idx, column=2, value=val).font = Font(
            name="IBM Plex Mono" if label in ("Run ID", "Generated At") else "Calibri",
            size=9,
            color="1F2328",
        )

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 60

    wb.save(str(file_path))


def inject_pptx_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    """Inject legal draft attestation into closing PPTX slide."""
    prs = Presentation(str(file_path))
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    slide = prs.slides.add_slide(blank_layout)

    # Background card in surface fill #F6F8FA with border #D0D7DE
    bg = slide.shapes.add_shape(1, Inches(0.8), Inches(1.2), Inches(11.733), Inches(5.2))
    bg.fill.solid()
    bg.fill.fore_color.rgb = PptxRGBColor(0xF6, 0xF8, 0xFA)
    bg.line.color.rgb = PptxRGBColor(0xD0, 0xD7, 0xDE)
    bg.line.width = Pt(0.75)

    tx_box = slide.shapes.add_textbox(Inches(1.1), Inches(1.5), Inches(11.133), Inches(4.6))
    tf = tx_box.text_frame
    tf.word_wrap = True

    p_hdr = tf.paragraphs[0]
    p_hdr.text = "DRAFT — REQUIRES APPROVAL BY COMPETENT AUTHORITY"
    p_hdr.font.name = "IBM Plex Mono"
    p_hdr.font.size = PptxPt(13)
    p_hdr.font.bold = True
    p_hdr.font.color.rgb = PptxRGBColor(0xF5, 0x9E, 0x0B)

    p_title = tf.add_paragraph()
    p_title.text = "System Provenance & Attestation Record"
    p_title.font.name = "Calibri"
    p_title.font.size = PptxPt(16)
    p_title.font.bold = True
    p_title.font.color.rgb = PptxRGBColor(0x1F, 0x23, 0x28)
    p_title.space_before = PptxPt(8)

    records = [
        f"Execution Run ID: {prov.run_id}",
        f"Models Utilized: {', '.join(prov.models_used)}",
        f"Sources Cited: {', '.join(prov.sources_cited) if prov.sources_cited else 'None'}",
        f"Minimum Confidence: {prov.min_confidence:.2f}",
        f"Human Verified Count: {prov.human_verified_count}",
        f"Timestamp (UTC): {prov.timestamp_utc}",
    ]
    for rec in records:
        p = tf.add_paragraph()
        p.text = f"• {rec}"
        p.font.name = "IBM Plex Mono"
        p.font.size = PptxPt(10)
        p.font.color.rgb = PptxRGBColor(0x57, 0x60, 0x6A)
        p.space_before = PptxPt(4)

    prs.save(str(file_path))


def inject_pdf_provenance(file_path: Path, prov: SystemProvenanceMetadata) -> None:
    """Inject legal draft attestation into PDF via transparent ReportLab overlay."""
    reader = PdfReader(str(file_path))
    writer = PdfWriter()
    sources_str = ", ".join(prov.sources_cited) if prov.sources_cited else "None"
    meta_line = (
        f"{prov.draft_warning} | Run ID: {prov.run_id} | Models: {', '.join(prov.models_used)} | "
        f"Min Conf: {prov.min_confidence:.2f} | Sources: {sources_str}"
    )

    for _idx, page in enumerate(reader.pages):
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        overlay_buffer = BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

        c.setFont("Helvetica", 6.5)
        c.setFillColor(HexColor("#57606A"))
        c.drawString(30, 14, meta_line)
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
