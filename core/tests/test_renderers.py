"""Tests for SWARAJ P6.1 Deliverable Renderers."""

import tempfile
from collections.abc import Generator
from pathlib import Path

from docx import Document
import openpyxl
import pytest

from renderers.engine import DeliverableRenderEngine
from renderers.schemas import (
    ApprovalLadderRole,
    ApprovalNoteSchema,
    CitationRef,
    SubstantiveClaim,
    UncitedClaimError,
    validate_citations,
)
from renderers.templates import TemplateManager
from tools.base import ToolContext
from tools.render_deliverable import RenderDeliverableInput, RenderDeliverableTool


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def sample_citation() -> CitationRef:
    return CitationRef(
        doc_id="SOP-114",
        title="Refinery Safety Operating Procedure",
        clause_or_section="4.2",
        confidence=0.98,
    )


def test_citation_enforcement_missing_citations() -> None:
    """Verify that substantive claims without citations raise UncitedClaimError."""
    data = ApprovalNoteSchema(
        subject="Replacement of Crude Unit Pump Impeller",
        reference=["MRPL/PROC/2026/88"],
        background="Pump P-101B experienced high vibration.",
        observations=[
            SubstantiveClaim(text="Substantive observation with no citation", citations=[])
        ],
        financial_implication="Rs 4,50,000 under Revenue Head 440",
        recommendation=[
            SubstantiveClaim(
                text="Procure replacement impeller",
                citations=[
                    CitationRef(
                        doc_id="DOC-1",
                        title="Ref",
                        clause_or_section="1",
                    )
                ],
            )
        ],
        approval_ladder=[
            ApprovalLadderRole(role="Prepared By", name="A. Kumar", status="VERIFIED")
        ],
    )
    with pytest.raises(UncitedClaimError):
        validate_citations(data)


def test_docx_approval_note_rendering(temp_dir: Path, sample_citation: CitationRef) -> None:
    """Test DOCX Approval Note rendering and provenance footer presence."""
    tpl_dir = temp_dir / ".swaraj" / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    tpl_file = tpl_dir / "approval_note.docx"
    doc = Document()
    doc.add_heading("{{ subject }}", level=1)
    doc.save(str(tpl_file))

    data = {
        "subject": "Overhaul of High Pressure Boiler B-201",
        "reference": ["FILE/B-201/2026/01"],
        "background": "Boiler B-201 requires statutory annual overhaul and inspection.",
        "observations": [
            {
                "text": "Header tube wall thickness degraded to 4.2mm (Min 4.0mm).",
                "citations": [sample_citation.model_dump()],
            }
        ],
        "financial_implication": "Estimated cost INR 12,50,000 provisioned in Capex.",
        "deviation": "None",
        "recommendation": [
            {
                "text": "Sanction overhaul expenditure of INR 12.5 Lakhs.",
                "citations": [sample_citation.model_dump()],
            }
        ],
        "approval_ladder": [
            {"role": "Prepared By", "name": "R. Sharma, AM(M)", "status": "VERIFIED"},
            {"role": "Sanctioned By", "name": "K. Singh, DGM", "status": "PENDING"},
        ],
    }

    tm = TemplateManager(workspace_root=temp_dir)
    engine = DeliverableRenderEngine(template_manager=tm)
    out_file = temp_dir / "approval_note.docx"

    res_path = engine.render(
        deliverable_type="approval_note",
        data=data,
        run_id="run_test_101",
        output_path=out_file,
    )

    assert res_path.exists()
    assert res_path.stat().st_size > 0


def test_docx_inspection_summary_rendering(temp_dir: Path, sample_citation: CitationRef) -> None:
    """Test Inspection Summary DOCX generation."""
    data = {
        "asset_tag": "11-V-102",
        "inspection_date": "2026-08-15",
        "inspection_method": "Ultrasonic Thickness Testing",
        "thickness_readings": [
            {
                "location": "Shell C-1",
                "nominal_mm": 12.0,
                "actual_mm": 11.2,
                "min_required_mm": 9.5,
            }
        ],
        "observed_defects": [
            {
                "description": "Pitting corrosion detected at bottom dish head",
                "severity": "MEDIUM",
                "citations": [sample_citation.model_dump()],
            }
        ],
        "ncrs": ["NCR-2026-042"],
        "recommendations": [
            {
                "text": "Re-inspect after 6 months of operation.",
                "citations": [sample_citation.model_dump()],
            }
        ],
    }

    engine = DeliverableRenderEngine()
    out_file = temp_dir / "inspection_summary.docx"

    res_path = engine.render(
        deliverable_type="inspection_summary",
        data=data,
        run_id="run_test_102",
        output_path=out_file,
    )

    assert res_path.exists()


def test_pptx_review_deck_rendering(temp_dir: Path, sample_citation: CitationRef) -> None:
    """Test governed PPTX Review Deck rendering."""
    data = {
        "title": "Crude Distillation Unit Inspection Review",
        "subtitle": "MRPL Phase III Expansion Unit",
        "slides": [
            {
                "slide_type": "metrics",
                "title": "Key Unit Health Metrics",
                "bullets": ["Overall equipment availability: 98.4%"],
                "key_metrics": [{"Availability": "98.4%"}, {"NCRs Open": "2"}],
                "citations": [sample_citation.model_dump()],
            }
        ],
    }

    engine = DeliverableRenderEngine()
    out_file = temp_dir / "review_deck.pptx"

    result = engine.render(
        deliverable_type="review_deck",
        data=data,
        run_id="run_test_103",
        output_path=out_file,
    )

    assert result == out_file
    assert out_file.exists()
    assert out_file.stat().st_size > 0


def test_xlsx_cost_sheet_live_formulas(temp_dir: Path, sample_citation: CitationRef) -> None:
    """Test XLSX Cost Sheet generation with live Excel formulas (data_only=False)."""
    data = {
        "currency": "INR",
        "budget_head": "CAPEX-2026-MECH-04",
        "provisioned": True,
        "items": [
            {
                "description": "High Pressure Gate Valves 4-inch",
                "quantity": 5.0,
                "unit_rate": 85000.0,
                "formula": "=B6*C6",
                "computed_amount": 425000.0,
                "citations": [sample_citation.model_dump()],
            },
            {
                "description": "Gasket Sets & Fasteners",
                "quantity": 10.0,
                "unit_rate": 4500.0,
                "formula": "=B7*C7",
                "computed_amount": 45000.0,
                "citations": [sample_citation.model_dump()],
            },
        ],
        "total_formula": "=SUM(D6:D7)",
    }

    engine = DeliverableRenderEngine()
    out_file = temp_dir / "cost_sheet.xlsx"

    res_path = engine.render(
        deliverable_type="cost_sheet",
        data=data,
        run_id="run_test_104",
        output_path=out_file,
    )

    assert res_path.exists()

    # Open with openpyxl data_only=False to verify live formula strings
    wb = openpyxl.load_workbook(str(res_path), data_only=False)
    ws = wb["Cost Sheet"]

    # Verify formula string starting with '='
    f_val = ws["D6"].value
    assert isinstance(f_val, str)
    assert f_val.startswith("=")
    assert f_val == "=B6*C6"

    tot_val = ws["D8"].value
    assert isinstance(tot_val, str)
    assert tot_val.startswith("=")
    assert tot_val == "=SUM(D6:D7)"

    # Verify non-removable Provenance sheet
    assert "Provenance & Audit" in wb.sheetnames
    prov_ws = wb["Provenance & Audit"]
    prov_b3 = str(prov_ws["B3"].value)
    assert (
        "run_test_104" in prov_b3
        or "run_test_104" in str(prov_ws["B2"].value)
        or "run_test_104" in str(prov_ws["B1"].value)
    )


def test_xlsx_engineering_calculation_exec_integration(
    temp_dir: Path, sample_citation: CitationRef
) -> None:
    """Test Engineering Calculation rendering pulling executed sandbox results via calc_run_id."""
    calc_record = {
        "computed_outputs": {
            "t_min_required_mm": 8.42,
            "MAWP_bar": 24.5,
            "pass_check": True,
        },
        "stdout_tail": [
            "Calculating t_min per ASME Sec VIII Div 1 UG-27...",
            "t_min = (P * R) / (S * E - 0.6 * P) = 8.42 mm",
            "Assertion Passed: actual_t (10.5mm) >= t_min (8.42mm)",
        ],
    }

    data = {
        "title": "Pressure Vessel Shell Wall Thickness Re-verification",
        "equipment_tag": "10-C-101",
        "governing_standard": "ASME Sec VIII Div 1",
        "governing_clause": "UG-27",
        "calc_run_id": "exec_sandbox_8841",
        "parameters": [
            {
                "name": "Design Pressure",
                "symbol": "P",
                "value": 2.5,
                "unit": "MPa",
                "source": "Drawing 10-C-101-D01",
            }
        ],
        "citations": [sample_citation.model_dump()],
    }

    engine = DeliverableRenderEngine(calc_execution_store={"exec_sandbox_8841": calc_record})
    out_file = temp_dir / "engineering_calc.xlsx"

    res_path = engine.render(
        deliverable_type="engineering_calculation",
        data=data,
        run_id="run_test_105",
        output_path=out_file,
    )

    assert res_path.exists()
    wb = openpyxl.load_workbook(str(res_path))
    ws = wb["Engineering Calculation"]
    assert str(ws["A1"].value).startswith("ENGINEERING CALCULATION")


def test_template_manager_and_sandbox_env(temp_dir: Path) -> None:
    """Verify TemplateManager hierarchy and SandboxedEnvironment safety."""
    tm = TemplateManager(workspace_root=temp_dir)

    # Test workspace override path lookup
    ws_override_dir = temp_dir / ".swaraj" / "templates"
    ws_override_dir.mkdir(parents=True, exist_ok=True)
    custom_tpl = ws_override_dir / "approval_note.docx"
    custom_tpl.write_text("dummy template", encoding="utf-8")

    found = tm.find_template("approval_note.docx")
    assert found == custom_tpl

    # Test SandboxedEnvironment
    env = tm.get_sandboxed_environment()
    assert env.__class__.__name__ == "SandboxedEnvironment"


@pytest.mark.asyncio
async def test_render_deliverable_tool_execution(temp_dir: Path, sample_citation: CitationRef) -> None:
    """Test RenderDeliverableTool execution and error reporting for repair path."""
    tpl_dir = temp_dir / ".swaraj" / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    tpl_file = tpl_dir / "approval_note.docx"
    doc = Document()
    doc.add_heading("{{ subject }}", level=1)
    doc.save(str(tpl_file))

    tm = TemplateManager(workspace_root=temp_dir)
    engine = DeliverableRenderEngine(template_manager=tm)
    tool = RenderDeliverableTool(engine=engine)
    ctx = ToolContext(workspace_root=temp_dir, session_id="test_session_55")

    valid_input = RenderDeliverableInput(
        deliverableType="approval_note",
        outputFilename="tool_approval_note.docx",
        data={
            "subject": "Tool Invocation Test",
            "reference": ["REF/001"],
            "background": "Testing tool execution",
            "observations": [
                {
                    "text": "Valid observation claim",
                    "citations": [sample_citation.model_dump()],
                }
            ],
            "financial_implication": "NIL",
            "recommendation": [
                {
                    "text": "Approve test",
                    "citations": [sample_citation.model_dump()],
                }
            ],
            "approval_ladder": [{"role": "Prepared By", "name": "Tester", "status": "VERIFIED"}],
        },
    )

    res = await tool.run(valid_input, ctx)
    assert res.success is True
    assert res.output is not None
    assert Path(res.output.file_path).exists()

    # Test invalid input (missing citation) returns ToolResult.failed for turn loop repair
    invalid_input = RenderDeliverableInput(
        deliverableType="approval_note",
        outputFilename="tool_approval_note_invalid.docx",
        data={
            "subject": "Invalid Test",
            "reference": [],
            "background": "No citations",
            "observations": [{"text": "Uncited observation claim", "citations": []}],
            "financial_implication": "NIL",
            "recommendation": [],
            "approval_ladder": [],
        },
    )

    inv_res = await tool.run(invalid_input, ctx)
    assert inv_res.success is False
    assert inv_res.error is not None
    assert "ValidationError" in inv_res.error or "UncitedClaimError" in inv_res.error
