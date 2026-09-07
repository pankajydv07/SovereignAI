"""Core approval service for SWARAJ maker-checker gate.

Enforces server-side precondition re-validation, separation of duties (maker != checker),
three-artifact cryptographic hash provenance, and headless LibreOffice PDF conversion.
"""

import difflib
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import structlog

from renderers.converter import DocxToPdfConverter, LibreOfficeUnavailableError
from renderers.docx_renderer import DocxRenderer

log = structlog.get_logger()


class SeparationOfDutiesError(ValueError):
    """Raised when the approving user is identical to the preparing user (maker == checker)."""

    pass


class ApprovalPreconditionFailedError(ValueError):
    """Raised when one or more approval preconditions (unverified fields, uncited claims, calc status) fail."""

    def __init__(self, message: str, reasons: list[str]) -> None:
        super().__init__(message)
        self.reasons = reasons


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest of a local file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class AuditRecord:
    """Immutable audit entry for maker-checker approval/rejection actions."""

    audit_id: str
    deliverable_id: str
    action: str  # "APPROVED", "REJECTED", "EDITED_AND_APPROVED"
    maker_id: str
    checker_id: str
    checker_name: str
    checker_designation: str
    identity_source: str  # e.g., "os_user_session", "local_keystore"
    timestamp: str
    stamp_text: str
    reviewed_docx_hash: str | None = None
    stamped_docx_hash: str | None = None
    approved_pdf_hash: str | None = None
    pdf_status: str | None = None  # "COMPLETED", "FAILED", "SKIPPED"
    pdf_path: str | None = None
    word_diffs: list[str] = field(default_factory=list)
    rejection_reason: str | None = None


@dataclass
class ApprovalResult:
    """Result of a successful deliverable approval action."""

    deliverable_id: str
    status: str  # "APPROVED"
    approved_by: str
    checker_designation: str
    stamp_text: str
    approved_at: str
    reviewed_docx_hash: str | None
    stamped_docx_hash: str | None
    approved_pdf_hash: str | None
    pdf_status: str  # "COMPLETED" or "FAILED"
    pdf_path: str | None
    audit_record: AuditRecord
    pdf_error: str | None = None


@dataclass
class RejectionResult:
    """Result of a deliverable rejection action."""

    deliverable_id: str
    status: str  # "REJECTED"
    rejected_by: str
    reason: str
    rejected_at: str
    audit_record: AuditRecord


class ApprovalService:
    """Service governing maker-checker gates and deliverable attestation in SWARAJ."""

    def __init__(
        self,
        identity_source: str = "os_user_session",
        pdf_converter: DocxToPdfConverter | None = None,
    ) -> None:
        self.identity_source = identity_source
        self.pdf_converter = pdf_converter or DocxToPdfConverter()
        self.audit_log: list[AuditRecord] = []

    @staticmethod
    def compute_word_diff(original_text: str, edited_text: str) -> list[str]:
        """Compute word-level diff between original model output and checker edits."""
        orig_words = original_text.split()
        edit_words = edited_text.split()

        matcher = difflib.SequenceMatcher(None, orig_words, edit_words)
        diff_chunks: list[str] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                diff_chunks.append(" ".join(orig_words[i1:i2]))
            elif tag == "replace":
                diff_chunks.append(
                    f"[-{' '.join(orig_words[i1:i2])}-] [+{' '.join(edit_words[j1:j2])}+]"
                )
            elif tag == "delete":
                diff_chunks.append(f"[-{' '.join(orig_words[i1:i2])}-]")
            elif tag == "insert":
                diff_chunks.append(f"[+{' '.join(edit_words[j1:j2])}+]")

        return diff_chunks

    def approve_deliverable(
        self,
        deliverable_id: str,
        maker_id: str,
        checker_id: str,
        checker_name: str,
        checker_designation: str,
        unverified_fields_count: int,
        uncited_claims_count: int,
        calc_verification_status: str,
        original_text: str | None = None,
        edited_text: str | None = None,
        org_terminology: str = "APPROVED",
        reviewed_docx_path: Path | str | None = None,
        output_dir: Path | str | None = None,
        workspace_root: Path | str | None = None,
    ) -> ApprovalResult:
        """Approve a deliverable after server-side re-validation of all preconditions.

        Preconditions enforced:
        1. maker_id != checker_id (Separation of duties)
        2. unverified_fields_count == 0
        3. uncited_claims_count == 0
        4. calc_verification_status == "VERIFIED"
        """
        reasons: list[str] = []

        # 1. Separation of duties check
        if maker_id.strip().lower() == checker_id.strip().lower():
            raise SeparationOfDutiesError(
                "Approver cannot be the preparing user. You prepared this deliverable. A different checker must approve it."
            )

        # 2. Field verification check
        if unverified_fields_count > 0:
            reasons.append(f"{unverified_fields_count} field(s) unverified")

        # 3. Citation check
        if uncited_claims_count > 0:
            reasons.append(f"{uncited_claims_count} claim(s) without citation")

        # 4. Calculation verification check
        if calc_verification_status != "VERIFIED":
            reasons.append(f"Calculation status is '{calc_verification_status}' (expected 'VERIFIED')")

        if reasons:
            raise ApprovalPreconditionFailedError(
                f"Cannot approve deliverable '{deliverable_id}': " + " · ".join(reasons),
                reasons=reasons,
            )

        # Compute word diff if edited
        word_diffs: list[str] = []
        action = "APPROVED"
        if original_text and edited_text and original_text != edited_text:
            word_diffs = self.compute_word_diff(original_text, edited_text)
            action = "EDITED_AND_APPROVED"

        timestamp = time.strftime("%H:%M:%S · %d %b %Y", time.localtime())
        stamp_text = (
            f"APPROVED BY: {checker_name} ({checker_designation}) · {org_terminology.upper()} · {timestamp}"
        )

        reviewed_docx_hash: str | None = None
        stamped_docx_hash: str | None = None
        approved_pdf_hash: str | None = None
        pdf_status: str = "SKIPPED"
        pdf_path: str | None = None
        pdf_error: str | None = None

        # Process document stamping and conversion if reviewed DOCX is provided
        if reviewed_docx_path:
            rd_path = Path(reviewed_docx_path)
            if rd_path.exists():
                # Step 1: Compute reviewed_docx_hash AT THE EXACT MOMENT OF APPROVAL
                reviewed_docx_hash = compute_file_sha256(rd_path)

                # Step 2: Create stamped copy with draft marker removed
                out_dir = Path(output_dir) if output_dir else rd_path.parent
                stamped_docx_path = out_dir / f"{rd_path.stem}_approved.docx"

                DocxRenderer.create_approved_stamped_copy(
                    draft_docx_path=rd_path,
                    checker_name=checker_name,
                    checker_designation=checker_designation,
                    approval_timestamp=timestamp,
                    reviewed_docx_hash=reviewed_docx_hash,
                    output_path=stamped_docx_path,
                )
                stamped_docx_hash = compute_file_sha256(stamped_docx_path)

                # Step 3: Convert stamped copy to PDF
                try:
                    pdf_result_path = self.pdf_converter.convert_docx_to_pdf(
                        docx_path=stamped_docx_path,
                        output_dir=out_dir,
                        workspace_root=Path(workspace_root) if workspace_root else None,
                    )
                    approved_pdf_hash = compute_file_sha256(pdf_result_path)
                    pdf_status = "COMPLETED"
                    pdf_path = str(pdf_result_path)
                except Exception as exc:
                    log.warning("pdf_conversion_failed_during_approval", error=str(exc))
                    pdf_status = "FAILED"
                    pdf_error = str(exc)

        audit_record = AuditRecord(
            audit_id=f"audit-{int(time.time() * 1000)}",
            deliverable_id=deliverable_id,
            action=action,
            maker_id=maker_id,
            checker_id=checker_id,
            checker_name=checker_name,
            checker_designation=checker_designation,
            identity_source=self.identity_source,
            timestamp=timestamp,
            stamp_text=stamp_text,
            reviewed_docx_hash=reviewed_docx_hash,
            stamped_docx_hash=stamped_docx_hash,
            approved_pdf_hash=approved_pdf_hash,
            pdf_status=pdf_status,
            pdf_path=pdf_path,
            word_diffs=word_diffs,
        )
        self.audit_log.append(audit_record)

        return ApprovalResult(
            deliverable_id=deliverable_id,
            status="APPROVED",
            approved_by=checker_name,
            checker_designation=checker_designation,
            stamp_text=stamp_text,
            approved_at=timestamp,
            reviewed_docx_hash=reviewed_docx_hash,
            stamped_docx_hash=stamped_docx_hash,
            approved_pdf_hash=approved_pdf_hash,
            pdf_status=pdf_status,
            pdf_path=pdf_path,
            audit_record=audit_record,
            pdf_error=pdf_error,
        )

    def retry_pdf_conversion(
        self,
        deliverable_id: str,
        stamped_docx_path: Path | str,
        output_dir: Path | str,
        workspace_root: Path | str | None = None,
    ) -> Path:
        """Retry PDF conversion for an already approved deliverable without repeating review."""
        stamped_path = Path(stamped_docx_path)
        if not stamped_path.exists():
            raise FileNotFoundError(f"Stamped DOCX copy not found: {stamped_path}")

        pdf_path = self.pdf_converter.convert_docx_to_pdf(
            docx_path=stamped_path,
            output_dir=Path(output_dir),
            workspace_root=Path(workspace_root) if workspace_root else None,
        )
        pdf_hash = compute_file_sha256(pdf_path)

        # Update audit record for deliverable
        for rec in reversed(self.audit_log):
            if rec.deliverable_id == deliverable_id and rec.action in ("APPROVED", "EDITED_AND_APPROVED"):
                rec.approved_pdf_hash = pdf_hash
                rec.pdf_status = "COMPLETED"
                rec.pdf_path = str(pdf_path)
                break

        return pdf_path

    def reject_deliverable(
        self,
        deliverable_id: str,
        maker_id: str,
        checker_id: str,
        checker_name: str,
        checker_designation: str,
        reason: str,
    ) -> RejectionResult:
        """Reject a deliverable with a mandatory reason."""
        if not reason or not reason.strip():
            raise ValueError("Rejection requires a non-empty written reason for the audit trail.")

        timestamp = time.strftime("%H:%M:%S · %d %b %Y", time.localtime())
        stamp_text = f"REJECTED BY: {checker_name} ({checker_designation}) · {timestamp}"

        audit_record = AuditRecord(
            audit_id=f"audit-{int(time.time() * 1000)}",
            deliverable_id=deliverable_id,
            action="REJECTED",
            maker_id=maker_id,
            checker_id=checker_id,
            checker_name=checker_name,
            checker_designation=checker_designation,
            identity_source=self.identity_source,
            timestamp=timestamp,
            stamp_text=stamp_text,
            rejection_reason=reason.strip(),
        )
        self.audit_log.append(audit_record)

        return RejectionResult(
            deliverable_id=deliverable_id,
            status="REJECTED",
            rejected_by=checker_name,
            reason=reason.strip(),
            rejected_at=timestamp,
            audit_record=audit_record,
        )
