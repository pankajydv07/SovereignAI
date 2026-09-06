"""Unit tests for tamper-evident audit chain and SQLite triggers."""

import pytest
import pytest_asyncio
import aiosqlite

from audit.chain import AuditChainStore, GENESIS_PREV_HASH
from storage.db import DatabaseManager


@pytest_asyncio.fixture
async def db_conn(tmp_path):
    """Provide an in-memory or temp file SQLite database with schema initialized."""
    db_file = tmp_path / "test_audit.db"
    mgr = DatabaseManager(db_file)
    async with mgr.connect() as conn:
        await mgr.initialize_schema(conn)
        yield conn


@pytest.mark.asyncio
async def test_audit_chain_append_and_verify(db_conn):
    """Test appending records to the audit chain and verifying hash integrity."""
    store = AuditChainStore(db_conn)

    rec0 = await store.append_record(
        run_id="run-001",
        user_id="user_sharma",
        action_type="TASK_EXECUTION",
        prompt="Calculate remaining life for Crude Distillation Column C-101",
        plan=[{"step": 1, "description": "Fetch thickness measurements"}],
        steps=[{"step": 1, "status": "completed"}],
        documents_retrieved=[{"doc_id": "DOC-101", "title": "Inspection SOP", "classification": "CONFIDENTIAL"}],
        models_used=["qwen3-coder:30b"],
        deliverables=[{"path": "reports/c101.docx", "type": "approval_note", "sha256": "abc123hash"}],
    )

    assert rec0.record_index == 0
    assert rec0.prev_hash == GENESIS_PREV_HASH
    assert len(rec0.record_hash) == 64

    rec1 = await store.append_record(
        run_id="run-002",
        user_id="user_kulkarni",
        action_type="APPROVAL_EVENT",
        prompt="Approve deliverable DELIV-2026-09-C101",
        plan=[],
        steps=[],
        documents_retrieved=[],
        models_used=[],
        deliverables=[],
        approval_event={"checker": "P. V. Kulkarni", "action": "APPROVED"},
    )

    assert rec1.record_index == 1
    assert rec1.prev_hash == rec0.record_hash

    records = await store.get_all_records()
    assert len(records) == 2

    verification = AuditChainStore.verify_chain(records)
    assert verification.is_valid is True
    assert verification.total_records == 2
    assert verification.failed_index is None


@pytest.mark.asyncio
async def test_audit_chain_tamper_detection(db_conn):
    """Test that modifying a record payload breaks verification and names the exact index."""
    store = AuditChainStore(db_conn)

    await store.append_record(
        run_id="run-001",
        user_id="user_a",
        action_type="TASK_EXECUTION",
        prompt="Initial prompt",
        plan=[],
        steps=[],
        documents_retrieved=[],
        models_used=["qwen3-coder:30b"],
        deliverables=[],
    )

    await store.append_record(
        run_id="run-002",
        user_id="user_b",
        action_type="APPROVAL_EVENT",
        prompt="Second prompt",
        plan=[],
        steps=[],
        documents_retrieved=[],
        models_used=[],
        deliverables=[],
    )

    records = await store.get_all_records()
    assert len(records) == 2

    # Verify clean state
    assert AuditChainStore.verify_chain(records).is_valid is True

    # Mutate record 1 payload without recomputing hash
    records[1].prompt = "TAMPERED PROMPT IN AUDIT TRAIL"

    res = AuditChainStore.verify_chain(records)
    assert res.is_valid is False
    assert res.failed_index == 1
    assert res.failed_record_id == records[1].record_id
    assert "Payload tampering detected" in res.reason


@pytest.mark.asyncio
async def test_sqlite_audit_append_only_trigger(db_conn):
    """Test that SQLite triggers abort UPDATE or DELETE on audit_records table."""
    store = AuditChainStore(db_conn)
    rec = await store.append_record(
        run_id="run-001",
        user_id="user_a",
        action_type="TASK_EXECUTION",
        prompt="Test prompt",
        plan=[],
        steps=[],
        documents_retrieved=[],
        models_used=[],
        deliverables=[],
    )

    with pytest.raises(aiosqlite.Error, match="append-only"):
        await db_conn.execute(
            "UPDATE audit_records SET prompt = 'hacked' WHERE record_id = ?",
            (rec.record_id,),
        )

    with pytest.raises(aiosqlite.Error, match="append-only"):
        await db_conn.execute(
            "DELETE FROM audit_records WHERE record_id = ?",
            (rec.record_id,),
        )
