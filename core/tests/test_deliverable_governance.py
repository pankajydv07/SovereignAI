"""Tests for Official Deliverable Governance and Boundary Enforcement."""

from pathlib import Path
import pytest
from docxtpl import DocxTemplate
from docx import Document

from renderers.docx_renderer import DocxRenderer
from renderers.engine import DeliverableRenderEngine
from renderers.governance import OfficialDeliverableViolationError
from renderers.schemas import (
    ApprovalLadderRole,
    ApprovalNoteSchema,
    CitationRef,
    InspectionFinding,
    InspectionReportSummary,
    LowConfidenceFieldUnverifiedError,
    SubstantiveClaim,
    SystemProvenanceMetadata,
    ThicknessReading,
    UncitedClaimError,
)
from renderers.templates import MissingOrgTemplateError, TemplateManager
from tools.base import ToolContext
from tools.generate_document import GenerateDocumentInput, GenerateDocumentTool


@pytest.fixture
def sample_approval_note() -> ApprovalNoteSchema:
    return ApprovalNoteSchema(
        subject="Column C-101 Remaining Life Sanction",
        reference=["MRPL/INSP/2026/09"],
        background="UT scan indicates localised wall thinning in shell course 3.",
        observations=[
            SubstantiveClaim(
                text="UT scan revealed minimum wall thickness of 8.2 mm at CML-07.",
                citations=[
                    CitationRef(
                        doc_id="MRPL-INSP-2026-09",
                        clause_or_section="p. 3",
                        confidence=0.98,
                        is_verified=True,
                    )
                ],
            )
        ],
        financial_implication="INR 12,50,000 under Mechanical Maintenance budget head.",
        deviation=None,
        recommendation=[
            SubstantiveClaim(
                text="Sanction extended run for 14.8 months subject to quarterly UT monitoring.",
                citations=[
                    CitationRef(
                        doc_id="API-570",
                        clause_or_section="Section 7.1.2",
                        confidence=1.0,
                        is_verified=True,
                    )
                ],
            )
        ],
        approval_ladder=[
            ApprovalLadderRole(
                role="Prepared By",
                name="A. Sharma (Senior Inspection Engineer)",
                status="VERIFIED",
            ),
            ApprovalLadderRole(
                role="Checked By",
                name="P. V. Kulkarni (Chief Manager - Mechanical)",
                status="PENDING",
            ),
        ],
    )


@pytest.fixture
def minimal_org_template(tmp_path: Path) -> Path:
    """Create a minimal approved organisation DOCX template."""
    tpl_dir = tmp_path / ".swaraj" / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    tpl_file = tpl_dir / "approval_note.docx"

    doc = Document()
    doc.add_heading("{{ subject }}", level=1)
    doc.add_paragraph("Background: {{ background }}")
    doc.add_paragraph("Financial Implication: {{ financial_implication }}")
    doc.save(str(tpl_file))
    return tpl_file


def test_approval_note_without_org_template_raises_error(
    tmp_path: Path, sample_approval_note: ApprovalNoteSchema
) -> None:
    """Requirement 1: Refuse to render approval note when org template is missing."""
    tm = TemplateManager(workspace_root=tmp_path)
    renderer = DocxRenderer(template_manager=tm)
    prov = SystemProvenanceMetadata(
        run_id="run-1",
        models_used=["qwen3-coder:30b"],
        sources_cited=["MRPL-INSP-2026-09"],
        min_confidence=0.98,
    )
    out_file = tmp_path / "approval_note.docx"

    with pytest.raises(MissingOrgTemplateError) as exc_info:
        renderer.render_approval_note(
            sample_approval_note, prov, out_file, template_name="mrpl_approval_note.docx"
        )

    assert "mrpl_approval_note.docx" in str(exc_info.value)
    assert "Approved organisation DOCX template" in str(exc_info.value)


def test_approval_note_with_registered_org_template_renders_successfully(
    tmp_path: Path, minimal_org_template: Path, sample_approval_note: ApprovalNoteSchema
) -> None:
    """Requirement 1: Render approval note when org template is registered."""
    tm = TemplateManager(workspace_root=tmp_path)
    engine = DeliverableRenderEngine(template_manager=tm)
    out_file = tmp_path / "official_approval_note.docx"

    res = engine.render(
        deliverable_type="approval_note",
        data=sample_approval_note.model_dump(),
        run_id="run-approval-01",
        output_path=out_file,
    )

    assert res.exists()
    assert res.stat().st_size > 0


@pytest.mark.asyncio
async def test_generate_document_rejects_official_deliverable_filename(tmp_path: Path) -> None:
    """Requirement 2: generate_document must be structurally unable to produce official deliverables."""
    tool = GenerateDocumentTool()
    ctx = ToolContext(session_id="s1", workspace_root=tmp_path)

    for forbidden_filename in [
        "approval_note.docx",
        "approval-note-final.docx",
        "inspection_summary.docx",
        "inspection_report.docx",
        "cost_sheet.xlsx",
        "engineering_calc.xlsx",
        "review_deck.pptx",
    ]:
        args = GenerateDocumentInput(
            taskDescription="Generate report document",
            outputFormat="docx" if forbidden_filename.endswith(".docx") else "xlsx",
            outputFilename=forbidden_filename,
        )
        with pytest.raises(OfficialDeliverableViolationError) as exc_info:
            await tool.run(args, ctx)

        assert "render_deliverable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_document_rejects_official_approval_note_task(tmp_path: Path) -> None:
    """Requirement 2: generate_document must reject official approval note generation requests."""
    tool = GenerateDocumentTool()
    ctx = ToolContext(session_id="s1", workspace_root=tmp_path)

    args = GenerateDocumentInput(
        taskDescription="Render official PSU approval note for management sanction",
        outputFormat="docx",
        outputFilename="sanction_memo.docx",
    )
    with pytest.raises(OfficialDeliverableViolationError) as exc_info:
        await tool.run(args, ctx)

    assert "render_deliverable" in str(exc_info.value)


def test_approval_note_uncited_observation_raises_error() -> None:
    """Requirement 4: Uncited observation blocks deliverable rendering."""
    uncited_note = ApprovalNoteSchema(
        subject="Sanction Note",
        background="Test background",
        observations=[
            SubstantiveClaim(
                text="Thickness thinning observed at nozzle N-1.",
                citations=[],  # Empty citations!
            )
        ],
        financial_implication="Nil",
        recommendation=[
            SubstantiveClaim(
                text="Approve replacement.",
                citations=[CitationRef(doc_id="API-570", confidence=1.0)],
            )
        ],
        approval_ladder=[],
    )

    engine = DeliverableRenderEngine()
    with pytest.raises(UncitedClaimError) as exc_info:
        engine.render(
            deliverable_type="approval_note",
            data=uncited_note.model_dump(),
            run_id="run-test",
            output_path="out.docx",
        )

    assert "lacks required citations" in str(exc_info.value)


def test_approval_note_low_confidence_unverified_field_blocks_rendering() -> None:
    """Requirement 4: Low-confidence (<0.85) unverified field blocks rendering."""
    low_conf_note = ApprovalNoteSchema(
        subject="Sanction Note",
        background="Test background",
        observations=[
            SubstantiveClaim(
                text="Wall thickness measured at 6.1 mm.",
                citations=[
                    CitationRef(
                        doc_id="MRPL-INSP-2026-09",
                        extracted_field_id="t_actual_cml07",
                        confidence=0.74,  # Low confidence!
                        is_verified=False,  # Not verified by checker!
                        source_page=2,
                    )
                ],
            )
        ],
        financial_implication="Nil",
        recommendation=[
            SubstantiveClaim(
                text="Approve replacement.",
                citations=[CitationRef(doc_id="API-570", confidence=1.0, is_verified=True)],
            )
        ],
        approval_ladder=[],
    )

    engine = DeliverableRenderEngine()
    with pytest.raises(LowConfidenceFieldUnverifiedError) as exc_info:
        engine.render(
            deliverable_type="approval_note",
            data=low_conf_note.model_dump(),
            run_id="run-test",
            output_path="out.docx",
        )

    assert "t_actual_cml07" in str(exc_info.value)
    assert "0.74" in str(exc_info.value)
    assert "Checker verification is required" in str(exc_info.value)


def test_typed_inspection_finding_and_summary_validation(tmp_path: Path) -> None:
    """Requirement 3: Typed inspection findings with defect categories, confidence, and actions."""
    finding = InspectionFinding(
        finding_id="FIND-C101-01",
        category="CORROSION",
        severity="HIGH",
        equipment_tag="C-101",
        description="Localised external corrosion at CML-07, thickness below threshold, action required.",
        source_page=3,
        source_region_bbox=[140.0, 320.0, 180.0, 460.0],
        extracted_field_ids=["t_actual_cml07", "corrosion_rate_cml07"],
        citations=[
            CitationRef(
                doc_id="INSP-REPORT-2026",
                clause_or_section="Section 3.2",
                confidence=0.96,
                is_verified=True,
            )
        ],
        confidence=0.96,
        verification_status="VERIFIED",
        recommended_action="Execute weld overlay cladding during upcoming turnaround.",
        inspection_method="UT",
    )

    summary = InspectionReportSummary(
        asset_tag="11-C-101",
        equipment_tag="C-101",
        inspection_date="2026-09-07",
        inspection_method="UT + Visual",
        findings=[finding],
        thickness_readings=[
            ThicknessReading(
                location="CML-07",
                nominal_mm=12.0,
                actual_mm=8.2,
                min_required_mm=4.5,
            )
        ],
        ncrs=["NCR-MRPL-2026-088"],
        recommendations=[
            SubstantiveClaim(
                text="Apply metallic coating and re-inspect in 6 months.",
                citations=[
                    CitationRef(
                        doc_id="OISD-129",
                        clause_or_section="Clause 4.1",
                        confidence=1.0,
                        is_verified=True,
                    )
                ],
            )
        ],
    )

    engine = DeliverableRenderEngine()
    out_file = tmp_path / "inspection_summary.docx"

    res = engine.render(
        deliverable_type="inspection_summary",
        data=summary.model_dump(),
        run_id="run-insp-01",
        output_path=out_file,
    )

    assert res.exists()
    assert res.stat().st_size > 0
