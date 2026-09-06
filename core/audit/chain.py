"""Tamper-evident audit chain implementation for SWARAJ.

Provides cryptographic hash-chaining across run tasks, retrieved documents,
models used, generated deliverables, and approval events.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from aiosqlite import Connection

GENESIS_PREV_HASH = "0" * 64


@dataclass
class AuditRecord:
    """Immutable audit record within the tamper-evident hash chain."""

    record_index: int
    record_id: str
    run_id: str
    user_id: str
    action_type: str  # e.g., "TASK_EXECUTION", "APPROVAL_EVENT", "AUDIT_EXPORTED"
    prompt: str
    plan: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    documents_retrieved: list[dict[str, Any]]  # List of {doc_id, title, classification}
    models_used: list[str]  # e.g., ["qwen3-coder:30b", "glm-ocr:9b"]
    deliverables: list[dict[str, Any]]  # List of {path, type, sha256}
    approval_event: dict[str, Any] | None
    prev_hash: str
    record_hash: str
    created_at_ms: int

    def to_canonical_dict(self) -> dict[str, Any]:
        """Return canonical dictionary representation excluding record_hash for hashing."""
        return {
            "record_index": self.record_index,
            "record_id": self.record_id,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "prompt": self.prompt,
            "plan": self.plan,
            "steps": self.steps,
            "documents_retrieved": self.documents_retrieved,
            "models_used": self.models_used,
            "deliverables": self.deliverables,
            "approval_event": self.approval_event,
            "prev_hash": self.prev_hash,
            "created_at_ms": self.created_at_ms,
        }


@dataclass
class AuditVerificationResult:
    """Result of audit chain integrity verification."""

    is_valid: bool
    total_records: int
    failed_index: int | None = None
    failed_record_id: str | None = None
    reason: str | None = None


def compute_record_hash(canonical_payload: dict[str, Any]) -> str:
    """Compute SHA-256 digest of a canonical JSON payload with sorted keys."""
    raw_bytes = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


class AuditChainStore:
    """Manages append-only insertion and verification of audit chain records in SQLite."""

    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    async def get_latest_record(self) -> AuditRecord | None:
        """Fetch the most recent audit record in the chain."""
        cursor = await self.conn.execute(
            """
            SELECT record_index, record_id, run_id, user_id, action_type, prompt,
                   plan_json, steps_json, documents_retrieved_json, models_used_json,
                   deliverables_json, approval_event_json, prev_hash, record_hash, created_at_ms
            FROM audit_records
            ORDER BY record_index DESC
            LIMIT 1
            """
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    async def get_all_records(self) -> list[AuditRecord]:
        """Fetch all audit records in ascending order of index."""
        cursor = await self.conn.execute(
            """
            SELECT record_index, record_id, run_id, user_id, action_type, prompt,
                   plan_json, steps_json, documents_retrieved_json, models_used_json,
                   deliverables_json, approval_event_json, prev_hash, record_hash, created_at_ms
            FROM audit_records
            ORDER BY record_index ASC
            """
        )
        rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def append_record(
        self,
        run_id: str,
        user_id: str,
        action_type: str,
        prompt: str,
        plan: list[dict[str, Any]],
        steps: list[dict[str, Any]],
        documents_retrieved: list[dict[str, Any]],
        models_used: list[str],
        deliverables: list[dict[str, Any]],
        approval_event: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Append a new record to the audit chain with cryptographic hash linking."""
        latest = await self.get_latest_record()
        next_index = (latest.record_index + 1) if latest else 0
        prev_hash = latest.record_hash if latest else GENESIS_PREV_HASH

        now_ms = int(time.time() * 1000)
        record_id = f"audit-rec-{now_ms}-{next_index}"

        canonical_payload = {
            "record_index": next_index,
            "record_id": record_id,
            "run_id": run_id,
            "user_id": user_id,
            "action_type": action_type,
            "prompt": prompt,
            "plan": plan,
            "steps": steps,
            "documents_retrieved": documents_retrieved,
            "models_used": models_used,
            "deliverables": deliverables,
            "approval_event": approval_event,
            "prev_hash": prev_hash,
            "created_at_ms": now_ms,
        }

        record_hash = compute_record_hash(canonical_payload)

        record = AuditRecord(
            record_index=next_index,
            record_id=record_id,
            run_id=run_id,
            user_id=user_id,
            action_type=action_type,
            prompt=prompt,
            plan=plan,
            steps=steps,
            documents_retrieved=documents_retrieved,
            models_used=models_used,
            deliverables=deliverables,
            approval_event=approval_event,
            prev_hash=prev_hash,
            record_hash=record_hash,
            created_at_ms=now_ms,
        )

        await self.conn.execute(
            """
            INSERT INTO audit_records (
                record_index, record_id, run_id, user_id, action_type, prompt,
                plan_json, steps_json, documents_retrieved_json, models_used_json,
                deliverables_json, approval_event_json, prev_hash, record_hash, created_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                next_index,
                record_id,
                run_id,
                user_id,
                action_type,
                prompt,
                json.dumps(plan),
                json.dumps(steps),
                json.dumps(documents_retrieved),
                json.dumps(models_used),
                json.dumps(deliverables),
                json.dumps(approval_event) if approval_event else None,
                prev_hash,
                record_hash,
                now_ms,
            ),
        )
        await self.conn.commit()
        return record

    @staticmethod
    def verify_chain(records: list[AuditRecord]) -> AuditVerificationResult:
        """Verify hash chain integrity across all records in sequence."""
        if not records:
            return AuditVerificationResult(is_valid=True, total_records=0)

        for i, rec in enumerate(records):
            if rec.record_index != i:
                return AuditVerificationResult(
                    is_valid=False,
                    total_records=len(records),
                    failed_index=i,
                    failed_record_id=rec.record_id,
                    reason=f"Index mismatch: expected {i}, found {rec.record_index}",
                )

            if i == 0:
                if rec.prev_hash != GENESIS_PREV_HASH:
                    return AuditVerificationResult(
                        is_valid=False,
                        total_records=len(records),
                        failed_index=0,
                        failed_record_id=rec.record_id,
                        reason="Genesis record prev_hash is corrupted",
                    )
            else:
                prev_rec = records[i - 1]
                if rec.prev_hash != prev_rec.record_hash:
                    return AuditVerificationResult(
                        is_valid=False,
                        total_records=len(records),
                        failed_index=i,
                        failed_record_id=rec.record_id,
                        reason=f"Hash chain break: prev_hash does not match record #{i-1}",
                    )

            recomputed = compute_record_hash(rec.to_canonical_dict())
            if recomputed != rec.record_hash:
                return AuditVerificationResult(
                    is_valid=False,
                    total_records=len(records),
                    failed_index=i,
                    failed_record_id=rec.record_id,
                    reason=f"Payload tampering detected at record #{i}: hash mismatch",
                )

        return AuditVerificationResult(is_valid=True, total_records=len(records))

    @staticmethod
    def _row_to_record(row: Any) -> AuditRecord:
        return AuditRecord(
            record_index=row["record_index"],
            record_id=row["record_id"],
            run_id=row["run_id"],
            user_id=row["user_id"],
            action_type=row["action_type"],
            prompt=row["prompt"],
            plan=json.loads(row["plan_json"]),
            steps=json.loads(row["steps_json"]),
            documents_retrieved=json.loads(row["documents_retrieved_json"]),
            models_used=json.loads(row["models_used_json"]),
            deliverables=json.loads(row["deliverables_json"]),
            approval_event=json.loads(row["approval_event_json"]) if row["approval_event_json"] else None,
            prev_hash=row["prev_hash"],
            record_hash=row["record_hash"],
            created_at_ms=row["created_at_ms"],
        )

