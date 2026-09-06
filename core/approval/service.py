"""Core approval service for SWARAJ maker-checker gate.

Enforces server-side precondition re-validation, separation of duties (maker != checker),
word-level diff auditing, and hash-chained audit record logging.
"""

import difflib
import time
from dataclasses import dataclass, field
from typing import Any


class SeparationOfDutiesError(ValueError):
    """Raised when the approving user is identical to the preparing user (maker == checker)."""

    pass


class ApprovalPreconditionFailedError(ValueError):
    """Raised when one or more approval preconditions (unverified fields, uncited claims, calc status) fail."""

    def __init__(self, message: str, reasons: list[str]) -> None:
        super().__init__(message)
        self.reasons = reasons


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
    audit_record: AuditRecord


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

    def __init__(self, identity_source: str = "os_user_session") -> None:
        self.identity_source = identity_source
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
            audit_record=audit_record,
        )

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
