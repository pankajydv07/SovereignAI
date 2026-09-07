"""Tests for GenerateDocumentTool and format-specific post-processing."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import openpyxl
import pdfplumber
import pytest
from docx import Document
from pptx import Presentation
from pypdf import PdfReader

from renderers.post_processor import (
    DocumentValidationError,
    validate_generated_document,
)
from tools.base import ToolContext
from tools.generate_document import (
    GenerateDocumentInput,
    GenerateDocumentOutput,
    GenerateDocumentTool,
    SandboxUnavailableError,
)


@pytest.fixture
def test_ctx(tmp_path: Path) -> ToolContext:
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ToolContext(workspace_root=ws, session_id="sess_test_123")


@pytest.fixture
def test_sandbox_rpc():
    """Test-double sandbox RPC runner executing code isolated in temporary process."""
    async def _mock_rpc(method: str, params: dict):
        if method != "sandbox/exec":
            return {"exitCode": -1, "stdoutTail": [], "stderrTail": [f"Unknown method {method}"]}
        cmd = params["command"]
        cwd = params["workDir"]
        env = params.get("env", {})
        timeout = params.get("timeoutS", 60)
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "exitCode": proc.returncode,
                "stdoutTail": proc.stdout.splitlines()[-20:] if proc.stdout else [],
                "stderrTail": proc.stderr.splitlines()[-20:] if proc.stderr else [],
            }
        except subprocess.TimeoutExpired:
            return {"exitCode": -1, "stdoutTail": [], "stderrTail": ["Timeout"]}
        except Exception as exc:
            return {"exitCode": -1, "stdoutTail": [], "stderrTail": [str(exc)]}
    return _mock_rpc


@pytest.mark.asyncio
async def test_generate_document_fails_when_script_errors(test_ctx: ToolContext):
    """Test that failing script execution returns clear diagnostic failure."""
    tool = GenerateDocumentTool(rpc_runner=None)
    inp = GenerateDocumentInput(
        taskDescription="Generate compressor audit docx",
        outputFormat="docx",
        outputFilename="compressor_audit.docx",
        scriptCode="raise RuntimeError('Synthetic script crash')",
        sourceRefs=["SOP-ENG-042"],
    )
    res = await tool.run(inp, test_ctx)
    assert not res.success
    assert "Document generation failed" in res.error


@pytest.mark.asyncio
async def test_generate_document_docx_happy_path(test_ctx: ToolContext, test_sandbox_rpc):
    """Test generating a valid DOCX document from sandboxed Python script."""
    script = """
import os
from docx import Document

os.makedirs("out", exist_ok=True)
doc = Document()
doc.add_heading("Compressor Stage-2 Audit Report", level=1)
doc.add_paragraph("Comprehensive vibration analysis completed.")
doc.save("out/compressor_audit.docx")
"""
    tool = GenerateDocumentTool(rpc_runner=test_sandbox_rpc)
    inp = GenerateDocumentInput(
        taskDescription="Generate compressor audit docx",
        outputFormat="docx",
        outputFilename="compressor_audit.docx",
        scriptCode=script,
        sourceRefs=["SOP-ENG-042"],
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    data: GenerateDocumentOutput = res.output  # type: ignore[assignment]
    assert data.output_format == "docx"
    assert data.script_iterations == 1
    assert Path(data.file_path).exists()

    # Validate document content and system-injected provenance
    doc = Document(data.file_path)
    assert len(doc.paragraphs) >= 2
    footer_text = " ".join([p.text for s in doc.sections for p in s.footer.paragraphs])
    assert data.run_id in footer_text
    assert "SOP-ENG-042" in footer_text


@pytest.mark.asyncio
async def test_generate_document_xlsx_happy_path(test_ctx: ToolContext, test_sandbox_rpc):
    """Test generating a valid XLSX spreadsheet from sandboxed Python script with data.json."""
    input_data = [
        {"tag": "V-101", "reading_mm": 14.2},
        {"tag": "V-102", "reading_mm": 11.8},
        {"tag": "V-103", "reading_mm": 9.5},
    ]

    script = """
import os, json
import openpyxl

os.makedirs("out", exist_ok=True)
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Readings"

data = json.load(open("data.json"))
ws.append(["Tag", "Reading (mm)"])
for item in data:
    ws.append([item["tag"], item["reading_mm"]])

wb.save("out/survey.xlsx")
"""
    tool = GenerateDocumentTool(rpc_runner=test_sandbox_rpc)
    inp = GenerateDocumentInput(
        taskDescription="Generate survey sheet from data.json",
        outputFormat="xlsx",
        outputFilename="survey.xlsx",
        scriptCode=script,
        inputData=input_data,
        expectsFullTabulation=True,
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    data: GenerateDocumentOutput = res.output  # type: ignore[assignment]
    assert data.validation["maxRows"] >= 4  # Header + 3 rows

    wb = openpyxl.load_workbook(data.file_path)
    assert "_Attestation_Provenance" in wb.sheetnames
    prov_sheet = wb["_Attestation_Provenance"]
    assert prov_sheet["A1"].value == "SWARAJ SYSTEM PROVENANCE ATTESTATION"


@pytest.mark.asyncio
async def test_generate_document_pptx_happy_path(test_ctx: ToolContext, test_sandbox_rpc):
    """Test generating a valid PPTX slide deck with closing attestation slide."""
    script = """
import os
from pptx import Presentation

os.makedirs("out", exist_ok=True)
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Refinery Turnaround Q3 Review"
prs.save("out/turnaround.pptx")
"""
    tool = GenerateDocumentTool(rpc_runner=test_sandbox_rpc)
    inp = GenerateDocumentInput(
        taskDescription="Generate turnaround review presentation",
        outputFormat="pptx",
        outputFilename="turnaround.pptx",
        scriptCode=script,
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    assert Path(res.output.file_path).exists()
    prs_out = Presentation(res.output.file_path)
    assert len(prs_out.slides) >= 2  # 1 content slide + 1 provenance slide
    assert "Refinery Turnaround Q3 Review" in prs_out.slides[0].shapes.title.text
    prov_text = " ".join([s.text_frame.text for s in prs_out.slides[-1].shapes if s.has_text_frame])
    assert "System Provenance" in prov_text or "Run ID" in prov_text


@pytest.mark.asyncio
async def test_generate_document_pdf_happy_path(test_ctx: ToolContext, test_sandbox_rpc):
    """Test generating a valid PDF with per-page transparent ReportLab overlay."""
    script = """
import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

os.makedirs("out", exist_ok=True)
doc = SimpleDocTemplate("out/inspection.pdf", pagesize=A4, bottomMargin=70)
styles = getSampleStyleSheet()
story = [
    Paragraph("Page 1: Inspection Overview - Boiler B-201", styles['Heading1']),
    PageBreak(),
    Paragraph("Page 2: Non-destructive Testing Measurements & Results", styles['Heading1'])
]
doc.build(story)
"""
    tool = GenerateDocumentTool(rpc_runner=test_sandbox_rpc)
    inp = GenerateDocumentInput(
        taskDescription="Generate multi-page inspection report pdf",
        outputFormat="pdf",
        outputFilename="inspection.pdf",
        scriptCode=script,
        sourceRefs=["IS-2825-SEC-4"],
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    data: GenerateDocumentOutput = res.output  # type: ignore[assignment]

    reader = PdfReader(data.file_path)
    assert len(reader.pages) == 2

    # Verify ReportLab overlay merged onto pages
    with pdfplumber.open(data.file_path) as pdf:
        txt_p1 = pdf.pages[0].extract_text()
        txt_p2 = pdf.pages[1].extract_text()
        assert data.run_id in txt_p1
        assert "DRAFT" in txt_p1
        assert "requires approval" in txt_p1
        assert data.run_id in txt_p2


@pytest.mark.asyncio
async def test_generate_document_markdown_direct_path(test_ctx: ToolContext):
    """Test markdown generation directly writes without sandbox execution."""
    tool = GenerateDocumentTool(rpc_runner=None)
    inp = GenerateDocumentInput(
        taskDescription="Generate safety memo",
        outputFormat="md",
        outputFilename="safety_memo.md",
        markdownContent="# Safety Deviation Memo\n\nAll hot-work permits must be verified.",
        sourceRefs=["OISD-STD-105"],
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    data: GenerateDocumentOutput = res.output  # type: ignore[assignment]
    assert data.output_format == "md"

    saved_text = Path(data.file_path).read_text(encoding="utf-8")
    assert "PROVENANCE ATTESTATION" in saved_text
    assert "OISD-STD-105" in saved_text
    assert data.run_id in saved_text


@pytest.mark.asyncio
async def test_generate_document_pdf_from_markdown(test_ctx: ToolContext, test_sandbox_rpc):
    """Test generating a PDF from markdown content when script_code is omitted."""
    tool = GenerateDocumentTool(rpc_runner=test_sandbox_rpc)
    inp = GenerateDocumentInput(
        taskDescription="Generate LLM Overview PDF",
        outputFormat="pdf",
        outputFilename="llm_overview.pdf",
        markdownContent="# Large Language Models Overview\n\n- Self-attention architecture\n- Local inference with Ollama",
        sourceRefs=["REF-LLM-01"],
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    data: GenerateDocumentOutput = res.output  # type: ignore[assignment]
    assert data.output_format == "pdf"
    assert Path(data.file_path).exists()

    reader = PdfReader(data.file_path)
    assert len(reader.pages) >= 1


@pytest.mark.asyncio
async def test_script_traceback_repair_loop(test_ctx: ToolContext, test_sandbox_rpc):
    """Test that a script error triggers repair and succeeds on subsequent iteration."""
    broken_script = """
import os
os.makedirs("out", exist_ok=True)
raise ValueError("Intentional syntax or runtime crash on attempt 1")
"""
    fixed_script = """
import os
from docx import Document
os.makedirs("out", exist_ok=True)
doc = Document()
doc.add_paragraph("Fixed content on attempt 2")
doc.save("out/repaired.docx")
"""
    mock_turn_loop = AsyncMock()
    mock_turn_loop.request_code_repair.return_value = fixed_script
    mock_session_store = AsyncMock()

    tool = GenerateDocumentTool(
        rpc_runner=test_sandbox_rpc,
        turn_loop=mock_turn_loop,
        session_store=mock_session_store,
    )
    inp = GenerateDocumentInput(
        taskDescription="Generate repaired docx",
        outputFormat="docx",
        outputFilename="repaired.docx",
        scriptCode=broken_script,
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    data: GenerateDocumentOutput = res.output  # type: ignore[assignment]
    assert data.script_iterations == 2
    assert mock_turn_loop.request_code_repair.called
    assert mock_session_store.append_event.call_count >= 2


@pytest.mark.asyncio
async def test_spoofing_detection_triggers_repair(test_ctx: ToolContext, test_sandbox_rpc):
    """Test that manual provenance spoofing triggers validation failure and repair."""
    spoofed_script = """
import os
from docx import Document
os.makedirs("out", exist_ok=True)
doc = Document()
doc.add_paragraph("Legitimate document content")
doc.add_paragraph("Run ID: fake-spoofed-run-id-999")
doc.save("out/spoofed.docx")
"""
    clean_script = """
import os
from docx import Document
os.makedirs("out", exist_ok=True)
doc = Document()
doc.add_paragraph("Legitimate document content without manual footers")
doc.save("out/spoofed.docx")
"""
    mock_turn_loop = AsyncMock()
    mock_turn_loop.request_code_repair.return_value = clean_script

    tool = GenerateDocumentTool(
        rpc_runner=test_sandbox_rpc,
        turn_loop=mock_turn_loop,
    )
    inp = GenerateDocumentInput(
        taskDescription="Test spoof detection",
        outputFormat="docx",
        outputFilename="spoofed.docx",
        scriptCode=spoofed_script,
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    data: GenerateDocumentOutput = res.output  # type: ignore[assignment]
    assert data.script_iterations == 2


@pytest.mark.asyncio
async def test_cardinality_validation_enforcement(tmp_path: Path):
    """Test expects_full_tabulation asserts expected row cardinality."""
    docx_file = tmp_path / "cardinality_test.docx"
    doc = Document()
    t = doc.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = "Header 1"
    doc.save(str(docx_file))

    # 10 expected input rows, but table has only 1 row
    input_data = [{"id": i} for i in range(10)]

    with pytest.raises(DocumentValidationError, match="less than expected input rows"):
        validate_generated_document(
            file_path=docx_file,
            output_format="docx",
            input_data=input_data,
            expects_full_tabulation=True,
        )

    # When expects_full_tabulation=False, it passes the minimum floor
    metrics = validate_generated_document(
        file_path=docx_file,
        output_format="docx",
        input_data=input_data,
        expects_full_tabulation=False,
    )
    assert metrics["tables"] == 1


@pytest.mark.asyncio
async def test_generate_document_pptx_ast_builder_auto(test_ctx: ToolContext, test_sandbox_rpc):
    """Test generating PPTX automatically via build_pptx_script when scriptCode is None."""
    tool = GenerateDocumentTool(rpc_runner=test_sandbox_rpc)
    inp = GenerateDocumentInput(
        taskDescription="# Refinery Q3 Review\n\n## Key Observations\n- Furnace F-101 tube thinning\n- Column C-102 tray fouling\n\n## Action Items\n| Action | Owner | Deadline |\n| Replacement | Inspection Lead | 15-Oct-2026 |",
        outputFormat="pptx",
        outputFilename="q3_review.pptx",
    )

    res = await tool.run(inp, test_ctx)
    assert res.success
    assert Path(res.output.file_path).exists()
    prs_out = Presentation(res.output.file_path)
    assert len(prs_out.slides) >= 3  # Title slide, 2 content slides, plus closing provenance slide

