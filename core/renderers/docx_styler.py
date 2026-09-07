"""DOCX Styler — PSU Engineering typography, table geometry, and page furniture for python-docx.

Enforces:
- 0.5pt horizontal rules with no vertical rules (#D0D7DE)
- #1F2328 dark table headers with white text
- w:tblHeader on header rows and w:cantSplit on all rows
- Monospace right-aligned numeric data
- A4 geometry with Mm(25) margins, 30mm binding gutter
- Centered draft classification header and non-removable provenance footer
"""

from pathlib import Path
import re
from typing import Any

from docx.document import Document as DocumentClass
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from renderers.schemas import SystemProvenanceMetadata


def set_cell_shading(cell: Any, color_hex: str) -> None:
    """Set cell background fill color in OpenXML."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcPr.append(shd)
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)


def set_table_borders_and_padding(tbl: Any) -> None:
    """Apply 0.5pt horizontal rules only (no vertical rules) and dense technical padding."""
    tblPr = tbl._tbl.tblPr
    borders = tblPr.find(qn("w:tblBorders"))
    if borders is not None:
        tblPr.remove(borders)

    borders = OxmlElement("w:tblBorders")
    for b_name in ("top", "bottom", "insideH"):
        b = OxmlElement(f"w:{b_name}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")  # 0.5 pt
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), "D0D7DE")
        borders.append(b)

    for b_name in ("left", "right", "insideV"):
        b = OxmlElement(f"w:{b_name}")
        b.set(qn("w:val"), "none")
        borders.append(b)

    tblPr.append(borders)

    # Padding: 0.08" left/right (115 dxa), 0.04" top/bottom (58 dxa)
    tblCellMar = tblPr.find(qn("w:tblCellMar"))
    if tblCellMar is None:
        tblCellMar = OxmlElement("w:tblCellMar")
        tblPr.append(tblCellMar)
    for m_name, val in [("top", "58"), ("bottom", "58"), ("left", "115"), ("right", "115")]:
        m = tblCellMar.find(qn(f"w:{m_name}"))
        if m is None:
            m = OxmlElement(f"w:{m_name}")
            tblCellMar.append(m)
        m.set(qn("w:w"), val)
        m.set(qn("w:type"), "dxa")


def is_numeric_value(val: str) -> bool:
    """Check if string is numeric for column right-alignment."""
    clean = re.sub(r"[,%\s]", "", str(val).strip())
    return bool(re.match(r"^-?\d+(\.\d+)?$", clean))


def format_technical_table(
    tbl: Any,
    caption: str | None = None,
    source_note: str | None = None,
) -> None:
    """Format table conforming to PSU technical documentation standards."""
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders_and_padding(tbl)

    # Header Row: #1F2328 dark fill, white bold text, w:tblHeader
    if tbl.rows:
        hdr_tr = tbl.rows[0]._tr.get_or_add_trPr()
        if hdr_tr.find(qn("w:tblHeader")) is None:
            hdr_tr.append(OxmlElement("w:tblHeader"))

        for cell in tbl.rows[0].cells:
            set_cell_shading(cell, "1F2328")
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    r.bold = True
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    # Detect numeric columns from data rows
    num_cols = set()
    if len(tbl.rows) > 1:
        for c_idx in range(len(tbl.columns)):
            data_vals = [tbl.rows[r_idx].cells[c_idx].text.strip() for r_idx in range(1, len(tbl.rows))]
            if data_vals and all(is_numeric_value(v) for v in data_vals if v):
                num_cols.add(c_idx)

    # Body rows: cantSplit, formatting, optional banding if > 8 rows
    is_banded = len(tbl.rows) > 9
    for r_idx, row in enumerate(tbl.rows[1:], start=1):
        trPr = row._tr.get_or_add_trPr()
        if trPr.find(qn("w:cantSplit")) is None:
            trPr.append(OxmlElement("w:cantSplit"))

        row_fill = "F6F8FA" if (is_banded and r_idx % 2 == 0) else None
        for c_idx, cell in enumerate(row.cells):
            if row_fill:
                set_cell_shading(cell, row_fill)
            for p in cell.paragraphs:
                if c_idx in num_cols:
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                else:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    r.font.name = "IBM Plex Mono" if c_idx in num_cols or re.search(r"[A-Z0-9-]{4,}", r.text) else "Calibri"
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)


def setup_doc_margins(doc: DocumentClass) -> None:
    """Configure A4 portrait geometry with 25mm top/bottom, 30mm left, 20mm right."""
    for section in doc.sections:
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.top_margin = Mm(25)
        section.bottom_margin = Mm(25)
        section.left_margin = Mm(30)
        section.right_margin = Mm(20)
        section.header_distance = Mm(12)
        section.footer_distance = Mm(12)
    apply_doc_styles(doc)


def apply_doc_styles(doc: DocumentClass) -> None:
    """Apply typography tokens: 11pt Calibri, 1.15 line spacing, ragged-right, widow control."""
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)
    style.paragraph_format.line_spacing = 1.15
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    pPr = style.element.get_or_add_pPr()
    widow = pPr.find(qn("w:widowControl"))
    if widow is None:
        widow = OxmlElement("w:widowControl")
        pPr.append(widow)
    widow.set(qn("w:val"), "1")

    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), "Calibri")
    rFonts.set(qn("w:hAnsi"), "Calibri")
    rFonts.set(qn("w:cs"), "Noto Sans Devanagari")


def format_doc_heading(heading: Any, level: int) -> None:
    """Format heading styles with keep_with_next and restrained typography."""
    heading.paragraph_format.keep_with_next = True
    heading.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if level == 1:
        heading.paragraph_format.space_before = Pt(18)
        heading.paragraph_format.space_after = Pt(6)
        for r in heading.runs:
            r.bold = True
            r.font.name = "Calibri"
            r.font.size = Pt(14)
            r.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)
    elif level == 2:
        heading.paragraph_format.space_before = Pt(12)
        heading.paragraph_format.space_after = Pt(4)
        for r in heading.runs:
            r.bold = True
            r.font.name = "Calibri"
            r.font.size = Pt(12)
            r.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)


def add_provenance_furniture(doc: DocumentClass, prov: SystemProvenanceMetadata) -> None:
    """Add formal page furniture: classification & draft header, provenance footer."""
    section = doc.sections[0]

    # Header: Centered classification and draft line in --verify (#F59E0B)
    header = section.header
    p_hdr = header.paragraphs[0]
    p_hdr.text = ""
    p_hdr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_c = p_hdr.add_run("CONFIDENTIAL — FOR INTERNAL USE ONLY\n")
    r_c.font.name = "IBM Plex Mono"
    r_c.font.size = Pt(8.5)
    r_c.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)

    r_draft = p_hdr.add_run("DRAFT — REQUIRES APPROVAL BY COMPETENT AUTHORITY")
    r_draft.bold = True
    r_draft.font.name = "IBM Plex Mono"
    r_draft.font.size = Pt(9.0)
    r_draft.font.color.rgb = RGBColor(0xF5, 0x9E, 0x0B)

    # Footer: Reference left, Run ID and provenance
    footer = section.footer
    p_ftr = footer.paragraphs[0]
    p_ftr.text = ""
    p_ftr.alignment = WD_ALIGN_PARAGRAPH.LEFT
    sources_str = ", ".join(prov.sources_cited) if prov.sources_cited else "None"
    r_info = p_ftr.add_run(
        f"Run ID: {prov.run_id} | Models: {', '.join(prov.models_used)} | "
        f"Min Conf: {prov.min_confidence:.2f} | Sources: {sources_str}"
    )
    r_info.font.name = "IBM Plex Mono"
    r_info.font.size = Pt(7.5)
    r_info.font.color.rgb = RGBColor(0x57, 0x60, 0x6A)
