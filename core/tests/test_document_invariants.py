"""Unit tests for Document Generation Invariants, Complex Script Fonts, and Markdown Scrubbing."""

from pathlib import Path
import pytest
from docx import Document
from docx.oxml.ns import qn

from ingest.ocr import extract_words_tesseract
from renderers.docx_renderer import DocxRenderer
from renderers.post_processor import DocumentValidationError, assert_zero_raw_markdown
from renderers.schemas import InspectionSummarySchema, SystemProvenanceMetadata
from tools.doc_script_builder import build_docx_script, build_pdf_script
from tools.fs_read import FsReadInput, FsReadTool
from tools.base import ToolContext


def test_docx_complex_script_font_configuration(tmp_path: Path) -> None:
    """Test that generated DOCX styles configure w:cs for Noto Sans Devanagari and w:ascii for Calibri."""
    renderer = DocxRenderer()
    sample_data = InspectionSummarySchema(
        asset_tag="E-101 (हीट एक्सचेंजर)",
        inspection_date="2026-09-07",
        inspection_method="UT Thickness Gauging",
        thickness_readings=[],
        observed_defects=[],
        recommendations=[],
    )
    prov = SystemProvenanceMetadata(
        run_id="run-font-test",
        models_used=["active-model"],
        sources_cited=[],
        min_confidence=1.0,
    )
    out_file = tmp_path / "inspection_devanagari.docx"
    renderer.render_inspection_summary(sample_data, prov, out_file, template_name=None)

    assert out_file.exists()
    doc = Document(str(out_file))
    style = doc.styles["Normal"]
    rPr = style.element.rPr
    assert rPr is not None
    rFonts = rPr.find(qn("w:rFonts"))
    assert rFonts is not None
    assert rFonts.get(qn("w:ascii")) == "Calibri"
    assert rFonts.get(qn("w:hAnsi")) == "Calibri"
    assert rFonts.get(qn("w:cs")) == "Noto Sans Devanagari"


def test_assert_zero_raw_markdown_blocks_structural_markdown() -> None:
    """Test that raw markdown headings, table rows, and paired asterisks raise DocumentValidationError."""
    with pytest.raises(DocumentValidationError) as exc_1:
        assert_zero_raw_markdown("This has a heading:\n# Main Heading\nText", "DOCX")
    assert "Markdown heading marker" in str(exc_1.value)

    with pytest.raises(DocumentValidationError) as exc_2:
        assert_zero_raw_markdown("Here is a table:\n|---|---|\nData", "DOCX")
    assert "Markdown table delimiter row" in str(exc_2.value)

    with pytest.raises(DocumentValidationError) as exc_3:
        assert_zero_raw_markdown("Here is **bold text** not rendered natively.", "DOCX")
    assert "Markdown bold markers" in str(exc_3.value)


def test_assert_zero_raw_markdown_permits_arithmetic_and_pipes() -> None:
    """Test that valid arithmetic asterisks (3 * 4) and engineering pipes are permitted."""
    valid_text = (
        "Calculated load: 3 * 4.5 = 13.5 kN.\n"
        "Tag ID: MRPL-CL-101 | Unit 02 | API 570.\n"
        "Single footnote indicator * Note 1."
    )
    # Should not raise
    assert_zero_raw_markdown(valid_text, "DOCX")


@pytest.mark.asyncio
async def test_fs_read_robust_multilingual_decode(tmp_path: Path) -> None:
    """Test that reading UTF-8 files with Hindi/Devanagari text decodes cleanly without replacement chars."""
    test_file = tmp_path / "test_hindi.txt"
    hindi_content = "उपकरण निरीक्षण रिपोर्ट: MRPL/C-101\nदबाव: 14.8 MPa"
    test_file.write_text(hindi_content, encoding="utf-8")

    tool = FsReadTool()
    ctx = ToolContext(session_id="s1", workspace_root=tmp_path)
    res = await tool.run(FsReadInput(path="test_hindi.txt"), ctx)

    assert res.success is True
    assert "उपकरण निरीक्षण रिपोर्ट" in res.output["content"]
    assert "\ufffd" not in res.output["content"]


def test_doc_script_builders_generate_valid_python() -> None:
    """Test that build_docx_script and build_pdf_script emit syntax-valid Python scripts."""
    docx_code = build_docx_script("test.docx", "# Title\n\n- Bullet item\n\n| Col1 | Col2 |\n|---|---|\n| Val1 | Val2 |")
    pdf_code = build_pdf_script("test.pdf", "# Title\n\n- Bullet item\n\n| Col1 | Col2 |\n|---|---|\n| Val1 | Val2 |")

    assert "import os" in docx_code
    assert "Noto Sans Devanagari" in docx_code
    assert "reportlab" in pdf_code
    # Compile to assert valid python syntax
    compile(docx_code, "<test_docx>", "exec")
    compile(pdf_code, "<test_pdf>", "exec")


def test_normalize_typographic_punctuation_replaces_nonbreaking_hyphens() -> None:
    """Test that non-breaking hyphens (U+2011) and missing glyphs are converted to ASCII '-'."""
    from tools.doc_script_builder import normalize_typographic_punctuation

    input_text = (
        "A hackathon is a time\u2011boxed event with cross\u2011functional teams.\n"
        "1. Kick\u2011off — Rules and schedule. |\n"
        "2. Multi\u2011day Tech\u2011specific track.\n"
        "उपकरण निरीक्षण: E-101 (हीट एक्सचेंजर)"
    )
    cleaned = normalize_typographic_punctuation(input_text)

    assert "time-boxed" in cleaned
    assert "cross-functional" in cleaned
    assert "Kick-off" in cleaned
    assert "Multi-day" in cleaned
    assert "Tech-specific" in cleaned
    assert "\u2011" not in cleaned
    # Devanagari text must be completely preserved
    assert "उपकरण निरीक्षण: E-101 (हीट एक्सचेंजर)" in cleaned

