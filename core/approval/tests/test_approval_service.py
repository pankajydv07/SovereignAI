"""Unit tests for ApprovalService in core/approval."""

import pytest

from approval.service import (
    ApprovalPreconditionFailedError,
    ApprovalService,
    SeparationOfDutiesError,
)


def test_approval_service_separation_of_duties_fails():
    service = ApprovalService(identity_source="local_keystore")

    with pytest.raises(SeparationOfDutiesError) as exc_info:
        service.approve_deliverable(
            deliverable_id="deliv-01",
            maker_id="user_sharma",
            checker_id="user_sharma",  # Same user!
            checker_name="A. Sharma",
            checker_designation="Senior Inspection Engineer",
            unverified_fields_count=0,
            uncited_claims_count=0,
            calc_verification_status="VERIFIED",
        )

    assert "Approver cannot be the preparing user" in str(exc_info.value)


def test_approval_service_unverified_fields_fails():
    service = ApprovalService()

    with pytest.raises(ApprovalPreconditionFailedError) as exc_info:
        service.approve_deliverable(
            deliverable_id="deliv-01",
            maker_id="user_sharma",
            checker_id="user_kulkarni",
            checker_name="P. V. Kulkarni",
            checker_designation="Chief Manager",
            unverified_fields_count=2,  # 2 unverified fields!
            uncited_claims_count=0,
            calc_verification_status="VERIFIED",
        )

    assert "2 field(s) unverified" in str(exc_info.value)


def test_approval_service_uncited_claims_fails():
    service = ApprovalService()

    with pytest.raises(ApprovalPreconditionFailedError) as exc_info:
        service.approve_deliverable(
            deliverable_id="deliv-01",
            maker_id="user_sharma",
            checker_id="user_kulkarni",
            checker_name="P. V. Kulkarni",
            checker_designation="Chief Manager",
            unverified_fields_count=0,
            uncited_claims_count=1,  # 1 uncited claim!
            calc_verification_status="VERIFIED",
        )

    assert "1 claim(s) without citation" in str(exc_info.value)


def test_approval_service_calc_status_fails():
    service = ApprovalService()

    with pytest.raises(ApprovalPreconditionFailedError) as exc_info:
        service.approve_deliverable(
            deliverable_id="deliv-01",
            maker_id="user_sharma",
            checker_id="user_kulkarni",
            checker_name="P. V. Kulkarni",
            checker_designation="Chief Manager",
            unverified_fields_count=0,
            uncited_claims_count=0,
            calc_verification_status="FAILED",  # Calc status failed!
        )

    assert "Calculation status is 'FAILED'" in str(exc_info.value)


def test_approval_service_success_and_diff():
    service = ApprovalService(identity_source="os_user_session")

    orig_text = "The remaining life is calculated to be 14.2 years based on corrosion rate."
    edited_text = "The remaining life is calculated to be 14.2 years based on actual corrosion rate."

    result = service.approve_deliverable(
        deliverable_id="deliv-01",
        maker_id="user_sharma",
        checker_id="user_kulkarni",
        checker_name="P. V. Kulkarni",
        checker_designation="Chief Manager - Mechanical",
        unverified_fields_count=0,
        uncited_claims_count=0,
        calc_verification_status="VERIFIED",
        original_text=orig_text,
        edited_text=edited_text,
        org_terminology="APPROVED",
    )

    assert result.status == "APPROVED"
    assert result.approved_by == "P. V. Kulkarni"
    assert "APPROVED BY: P. V. Kulkarni (Chief Manager - Mechanical)" in result.stamp_text
    assert result.audit_record.identity_source == "os_user_session"
    assert result.audit_record.action == "EDITED_AND_APPROVED"
    assert len(result.audit_record.word_diffs) > 0


def test_rejection_requires_reason():
    service = ApprovalService()

    with pytest.raises(ValueError) as exc_info:
        service.reject_deliverable(
            deliverable_id="deliv-01",
            maker_id="user_sharma",
            checker_id="user_kulkarni",
            checker_name="P. V. Kulkarni",
            checker_designation="Chief Manager",
            reason="   ",  # Blank reason!
        )

    assert "non-empty written reason" in str(exc_info.value)

    res = service.reject_deliverable(
        deliverable_id="deliv-01",
        maker_id="user_sharma",
        checker_id="user_kulkarni",
        checker_name="P. V. Kulkarni",
        checker_designation="Chief Manager",
        reason="Missing corrosion rate calculation derivation.",
    )

    assert res.status == "REJECTED"
    assert res.reason == "Missing corrosion rate calculation derivation."
    assert res.audit_record.action == "REJECTED"
