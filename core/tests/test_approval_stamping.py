"""Tests for Maker-Checker Approval Stamping, 3-Artifact Hashing, and PDF Conversion."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from docx import Document

from approval.service import (
    ApprovalPreconditionFailedError,
    ApprovalService,
    SeparationOfDutiesError,
    compute_file_sha256,
)
from renderers.converter import DocxToPdfConverter, LibreOfficeUnavailableError
from renderers.docx_renderer import DocxRenderer


@pytest.fixture
def sample_draft_docx(tmp_path: Path) -> Path:
    """Create a sample working draft DOCX with DRAFT header warning banner."""
    doc_path = tmp_path / "sample_note_draft.docx"
    doc = Document()
    p = doc.add_paragraph("Subject: Replacement of spool PS-1002 on Crude Column C-101.")
    doc.add_paragraph("Background: Wall thickness measured below threshold.")

    # Add DRAFT footer
    section = doc.sections[0]
    footer = section.footer
    p_f = footer.paragraphs[0]
    p_f.text = "*** DRAFT — requires approval by competent authority ***\nRun ID: run-01"

    doc.save(str(doc_path))
    return doc_path


def test_libreoffice_unavailable_raises_loudly_with_instructions(tmp_path: Path) -> None:
    """Test that missing LibreOffice binary raises explicit error naming paths checked."""
    with patch("renderers.converter.shutil.which", return_value=None):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(LibreOfficeUnavailableError) as exc_info:
                DocxToPdfConverter._resolve_soffice(custom_path=tmp_path / "non_existent_soffice.exe")

            err_str = str(exc_info.value)
            assert "LibreOffice binary (soffice) not found" in err_str
            assert "Checked paths:" in err_str
            assert "SOFFICE_PATH" in err_str


def test_moment_of_approval_hashing_and_stamped_copy(tmp_path: Path, sample_draft_docx: Path) -> None:
    """Test reviewed DOCX is hashed at moment of approval, draft marker replaced by stamp."""
    mock_pdf = tmp_path / "sample_note_draft_approved.pdf"
    mock_pdf.write_bytes(b"%PDF-1.4 Mock PDF Content")

    mock_converter = MagicMock(spec=DocxToPdfConverter)
    mock_converter.convert_docx_to_pdf.return_value = mock_pdf

    service = ApprovalService(pdf_converter=mock_converter)

    # Modify the draft before approving (simulating checker edit during review)
    doc = Document(str(sample_draft_docx))
    doc.add_paragraph("Checker Note: Verified against IS 2825 Cl 4.2.")
    doc.save(str(sample_draft_docx))

    # Compute expected hash of the exact file at approval moment
    expected_reviewed_hash = compute_file_sha256(sample_draft_docx)

    result = service.approve_deliverable(
        deliverable_id="DELIV-101",
        maker_id="inspector_01",
        checker_id="lead_eng_02",
        checker_name="R. K. Verma",
        checker_designation="Chief Inspection Engineer",
        unverified_fields_count=0,
        uncited_claims_count=0,
        calc_verification_status="VERIFIED",
        reviewed_docx_path=sample_draft_docx,
        output_dir=tmp_path,
    )

    assert result.status == "APPROVED"
    assert result.reviewed_docx_hash == expected_reviewed_hash
    assert result.stamped_docx_hash is not None
    assert result.approved_pdf_hash == compute_file_sha256(mock_pdf)
    assert result.pdf_status == "COMPLETED"

    # Verify original draft was NOT mutated in place
    draft_doc_after = Document(str(sample_draft_docx))
    draft_footer_text = draft_doc_after.sections[0].footer.paragraphs[0].text
    assert "DRAFT — requires approval" in draft_footer_text

    # Verify stamped copy exists and has DRAFT marker removed + Approval Stamp added
    stamped_path = tmp_path / "sample_note_draft_approved.docx"
    assert stamped_path.exists()
    stamped_doc = Document(str(stamped_path))
    stamped_footer_text = stamped_doc.sections[0].footer.paragraphs[0].text
    assert "DRAFT" not in stamped_footer_text
    assert "OFFICIAL RECORD — APPROVED BY COMPETENT AUTHORITY" in stamped_footer_text
    assert "R. K. Verma" in stamped_footer_text
    assert expected_reviewed_hash[:16] in stamped_footer_text


def test_approval_persists_when_pdf_conversion_fails(tmp_path: Path, sample_draft_docx: Path) -> None:
    """Test human approval persists even if PDF conversion tool fails."""
    failing_converter = MagicMock(spec=DocxToPdfConverter)
    failing_converter.convert_docx_to_pdf.side_effect = RuntimeError("LibreOffice process timed out")

    service = ApprovalService(pdf_converter=failing_converter)

    result = service.approve_deliverable(
        deliverable_id="DELIV-102",
        maker_id="inspector_01",
        checker_id="lead_eng_02",
        checker_name="R. K. Verma",
        checker_designation="Chief Inspection Engineer",
        unverified_fields_count=0,
        uncited_claims_count=0,
        calc_verification_status="VERIFIED",
        reviewed_docx_path=sample_draft_docx,
        output_dir=tmp_path,
    )

    # Human decision SUCCEEDED
    assert result.status == "APPROVED"
    assert result.pdf_status == "FAILED"
    assert result.approved_pdf_hash is None
    assert "timed out" in (result.pdf_error or "")

    # Stamped DOCX exists and was hashed
    assert result.stamped_docx_hash is not None
    stamped_docx = tmp_path / "sample_note_draft_approved.docx"
    assert stamped_docx.exists()

    # Retry PDF conversion
    mock_fixed_pdf = tmp_path / "sample_note_draft_approved.pdf"
    mock_fixed_pdf.write_bytes(b"%PDF-1.4 Fixed PDF Content")
    failing_converter.convert_docx_to_pdf.side_effect = None
    failing_converter.convert_docx_to_pdf.return_value = mock_fixed_pdf

    retry_pdf = service.retry_pdf_conversion(
        deliverable_id="DELIV-102",
        stamped_docx_path=stamped_docx,
        output_dir=tmp_path,
    )
    assert retry_pdf.exists()
    assert service.audit_log[-1].pdf_status == "COMPLETED"
    assert service.audit_log[-1].approved_pdf_hash == compute_file_sha256(mock_fixed_pdf)


def test_separation_of_duties_self_approval_blocked(sample_draft_docx: Path) -> None:
    """Test self-approval attempt (maker == checker) is rejected loudly."""
    service = ApprovalService()

    with pytest.raises(SeparationOfDutiesError) as exc_info:
        service.approve_deliverable(
            deliverable_id="DELIV-103",
            maker_id="inspector_01",
            checker_id="inspector_01",  # Self-approval!
            checker_name="A. Sharma",
            checker_designation="Inspection Engineer",
            unverified_fields_count=0,
            uncited_claims_count=0,
            calc_verification_status="VERIFIED",
            reviewed_docx_path=sample_draft_docx,
        )

    assert "Approver cannot be the preparing user" in str(exc_info.value)
