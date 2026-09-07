"""Multi-format Rich Document Reader for SWARAJ.

Converts binary and office formats (.xlsx, .xls, .docx, .pptx, .pdf, .csv, .tsv)
into clean, structured Markdown text for local LLM reasoning.
Zero network egress, 100% air-gapped using openpyxl, python-docx, python-pptx, and pypdf.
"""

import csv
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SUPPORTED_RICH_EXTENSIONS = {
    ".xlsx", ".xls", ".xlsm",
    ".docx", ".doc",
    ".pptx", ".ppt",
    ".pdf",
    ".csv", ".tsv",
}


def _clean_str(val: Any) -> str:
    """Sanitize cell or token value into valid UTF-8 string without line breaks or surrogates."""
    if val is None:
        return ""
    s = str(val).replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("|", "\\|")
    return s.encode("utf-8", errors="replace").decode("utf-8", errors="replace").strip()


def read_excel_to_markdown(path: Path, max_rows_per_sheet: int = 200) -> str:
    """Convert Excel workbook into Markdown tables per sheet."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    except Exception as exc:
        return f"*(Failed to open Excel workbook '{path.name}': {exc})*"

    sections: list[str] = [f"# Workbook: {path.name}\n"]
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        sections.append(f"## Sheet: {sheet_name}")

        rows_data: list[list[str]] = []
        max_cols = 0
        total_rows = 0

        for row in sheet.iter_rows(values_only=True):
            total_rows += 1
            if total_rows > max_rows_per_sheet:
                continue
            cleaned_row = [_clean_str(cell) for cell in row]
            # Strip trailing empty cells
            while cleaned_row and not cleaned_row[-1]:
                cleaned_row.pop()
            if any(cleaned_row):
                rows_data.append(cleaned_row)
                max_cols = max(max_cols, len(cleaned_row))

        if not rows_data or max_cols == 0:
            sections.append("*(Empty sheet)*\n")
            continue

        # Normalize column count across all rows
        normalized_rows = [r + [""] * (max_cols - len(r)) for r in rows_data]
        header = normalized_rows[0]
        # Ensure header names are distinct and non-empty
        header = [h if h else f"Col_{i + 1}" for i, h in enumerate(header)]

        table_lines: list[str] = []
        table_lines.append("| " + " | ".join(header) + " |")
        table_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        for r in normalized_rows[1:]:
            table_lines.append("| " + " | ".join(r) + " |")

        if total_rows > max_rows_per_sheet:
            table_lines.append(f"\n*(Truncated: showing first {max_rows_per_sheet} of {total_rows} rows)*")

        sections.append("\n".join(table_lines) + "\n")

    wb.close()
    return "\n".join(sections)


def read_docx_to_markdown(path: Path) -> str:
    """Convert Word document into structured Markdown."""
    try:
        import docx
        doc = docx.Document(str(path))
    except Exception as exc:
        return f"*(Failed to open Word document '{path.name}': {exc})*"

    lines: list[str] = [f"# Document: {path.name}\n"]

    for element in doc.paragraphs:
        txt = element.text.strip()
        if not txt:
            continue
        clean = _clean_str(txt)
        style = (element.style.name or "").lower() if element.style else ""
        if "heading 1" in style:
            lines.append(f"## {clean}\n")
        elif "heading 2" in style:
            lines.append(f"### {clean}\n")
        elif "heading 3" in style:
            lines.append(f"#### {clean}\n")
        elif "list" in style or "bullet" in style:
            lines.append(f"- {clean}")
        else:
            lines.append(f"{clean}\n")

    for table in doc.tables:
        t_rows: list[list[str]] = []
        max_c = 0
        for row in table.rows:
            r_data = [_clean_str(cell.text) for cell in row.cells]
            t_rows.append(r_data)
            max_c = max(max_c, len(r_data))
        if t_rows and max_c > 0:
            norm = [r + [""] * (max_c - len(r)) for r in t_rows]
            lines.append("\n| " + " | ".join(norm[0]) + " |")
            lines.append("| " + " | ".join(["---"] * max_c) + " |")
            for r in norm[1:]:
                lines.append("| " + " | ".join(r) + " |")
            lines.append("")

    return "\n".join(lines)


def read_pptx_to_markdown(path: Path) -> str:
    """Convert PowerPoint presentation into structured Markdown."""
    try:
        import pptx
        prs = pptx.Presentation(str(path))
    except Exception as exc:
        return f"*(Failed to open PowerPoint presentation '{path.name}': {exc})*"

    lines: list[str] = [f"# Presentation: {path.name}\n"]

    for idx, slide in enumerate(prs.slides, 1):
        lines.append(f"## Slide {idx}")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    txt = _clean_str(p.text)
                    if txt:
                        lines.append(f"- {txt}")
            elif shape.has_table:
                t_rows = [[_clean_str(c.text) for c in r.cells] for r in shape.table.rows]
                if t_rows:
                    cols = len(t_rows[0])
                    lines.append("\n| " + " | ".join(t_rows[0]) + " |")
                    lines.append("| " + " | ".join(["---"] * cols) + " |")
                    for r in t_rows[1:]:
                        lines.append("| " + " | ".join(r) + " |")
                    lines.append("")
        lines.append("")

    return "\n".join(lines)


def read_pdf_to_markdown(path: Path) -> str:
    """Extract page-by-page text from PDF document into Markdown."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
    except Exception as exc:
        return f"*(Failed to open PDF document '{path.name}': {exc})*"

    pages: list[str] = [f"# Document: {path.name}\n"]
    for i, page in enumerate(reader.pages):
        raw = page.extract_text() or ""
        clean = raw.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        pages.append(f"## Page {i + 1}\n{clean}\n")

    return "\n".join(pages)


def read_csv_to_markdown(path: Path, max_rows: int = 200) -> str:
    """Convert CSV or TSV file into Markdown table."""
    try:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        content = path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(content.splitlines(), delimiter=delimiter)
        rows = list(reader)
    except Exception as exc:
        return f"*(Failed to read delimited file '{path.name}': {exc})*"

    if not rows:
        return f"# File: {path.name}\n*(Empty file)*"

    max_cols = max(len(r) for r in rows)
    norm = [[_clean_str(c) for c in r] + [""] * (max_cols - len(r)) for r in rows[:max_rows]]

    table: list[str] = [f"# Table: {path.name}\n"]
    table.append("| " + " | ".join(norm[0]) + " |")
    table.append("| " + " | ".join(["---"] * max_cols) + " |")
    for r in norm[1:]:
        table.append("| " + " | ".join(r) + " |")

    if len(rows) > max_rows:
        table.append(f"\n*(Truncated: showing first {max_rows} of {len(rows)} rows)*")

    return "\n".join(table)


def convert_document_to_markdown(path: Path, max_rows: int = 200) -> str:
    """Dispatch file conversion to Markdown based on extension."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls", ".xlsm"):
        return read_excel_to_markdown(path, max_rows_per_sheet=max_rows)
    if suffix in (".docx", ".doc"):
        return read_docx_to_markdown(path)
    if suffix in (".pptx", ".ppt"):
        return read_pptx_to_markdown(path)
    if suffix == ".pdf":
        return read_pdf_to_markdown(path)
    if suffix in (".csv", ".tsv"):
        return read_csv_to_markdown(path, max_rows=max_rows)

    # Plain text / source code / JSON / YAML / markdown
    raw = path.read_text(encoding="utf-8", errors="replace")
    return raw.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
