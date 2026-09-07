"""Unit tests for DeliverableStore and Maker-Checker storage lifecycle."""

from pathlib import Path
import pytest
from storage.db import DatabaseManager
from storage.deliverable_store import DeliverableStore
from approval.service import ApprovalService, SeparationOfDutiesError


@pytest.mark.asyncio
async def test_deliverable_lifecycle_and_verification(tmp_path: Path):
    db_path = tmp_path / "test_sessions.db"
    db_manager = DatabaseManager(db_path)
    async with db_manager.connect() as conn:
        await db_manager.initialize_schema(conn)

    approval_service = ApprovalService()
    store = DeliverableStore(str(db_path), approval_service=approval_service)

    # 1. Empty list initially
    initial_list = await store.list_deliverables("proj-1")
    assert len(initial_list) == 0

    # 2. Create deliverable
    deliv_payload = {
        "id": "DELIV-101",
        "projectId": "proj-1",
        "sessionId": "sess-1",
        "title": "C-101 Column Inspection Note",
        "subject": "Remaining Life Evaluation",
        "maker": {"id": "user_sharma", "name": "A. Sharma", "designation": "Sr. Engineer"},
        "checker": {"id": "user_kulkarni", "name": "P. V. Kulkarni", "designation": "Chief Manager"},
        "fields": [
            {
                "id": "f1",
                "field_name": "corrosion_rate",
                "value": "0.25",
                "unit": "mm/yr",
                "confidence": 0.75,
                "is_verified": False,
                "requires_verification": True,
                "page": 1,
                "imagePath": "scan.pdf",
            }
        ],
        "citations": [
            {
                "id": "c1",
                "doc_id": "KB-API-570",
                "title": "API 570",
                "clause_or_section": "7.1.2",
                "claim_text": "Governing formula verified",
                "is_cited": True,
            }
        ],
    }

    created = await store.create_deliverable(deliv_payload)
    assert created["id"] == "DELIV-101"
    assert created["status"] == "PENDING_CHECK"

    # 3. Retrieve
    fetched = await store.get_deliverable("DELIV-101")
    assert fetched is not None
    assert fetched["title"] == "C-101 Column Inspection Note"
    assert len(fetched["fields"]) == 1
    assert fetched["fields"][0]["is_verified"] is False

    # 4. Verify field
    verified = await store.verify_field("DELIV-101", "f1", verified_by="user_kulkarni")
    assert verified["fields"][0]["is_verified"] is True
    assert verified["fields"][0]["requires_verification"] is False

    # 5. Separation of duties: maker cannot approve their own deliverable
    with pytest.raises(SeparationOfDutiesError):
        await store.approve(
            "DELIV-101",
            checker={"id": "user_sharma", "name": "A. Sharma", "designation": "Sr. Engineer"},
        )

    # 6. Checker approves
    approved = await store.approve(
        "DELIV-101",
        checker={"id": "user_kulkarni", "name": "P. V. Kulkarni", "designation": "Chief Manager"},
        stamp_text="APPROVED BY: P. V. Kulkarni\nPREPARED BY: A. Sharma",
    )
    assert approved["status"] == "APPROVED"
    assert "APPROVED BY: P. V. Kulkarni" in approved["stamp_text"]

    # 7. Deliverable list shows approved status
    final_list = await store.list_deliverables("proj-1")
    assert len(final_list) == 1
    assert final_list[0]["status"] == "APPROVED"
