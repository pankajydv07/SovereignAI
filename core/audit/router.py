"""Audit & Attestation RPC handler router for SWARAJ core."""

from dataclasses import asdict
from typing import Any

from aiosqlite import Connection
from audit.attestation import AttestationEngine
from audit.chain import AuditChainStore, AuditRecord


class AuditRouter:
    """RPC router serving audit chain verification, tamper testing, and attestation queries."""

    def __init__(self, conn: Connection, workspace_root: str = "d:/SovereignAI") -> None:
        self.store = AuditChainStore(conn)
        self.attestation_engine = AttestationEngine(workspace_root)

    async def handle_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC: audit/list — Returns all audit records in the chain."""
        records = await self.store.get_all_records()
        return {
            "records": [asdict(r) for r in records],
            "total": len(records),
        }

    async def handle_verify(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC: audit/verify — Runs cryptographic verification across all chain records."""
        records = await self.store.get_all_records()
        result = AuditChainStore.verify_chain(records)
        return asdict(result)

    async def handle_corrupt_for_testing(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC: audit/corrupt_for_testing — Test helper that simulates record tampering."""
        record_index = params.get("recordIndex", 0)
        records = await self.store.get_all_records()
        if not records or record_index >= len(records):
            return {"success": False, "reason": f"No record found at index {record_index}"}

        # Mutate the in-memory or database record to simulate tamper
        corrupted_rec = records[record_index]
        corrupted_rec.prompt = f"{corrupted_rec.prompt} [TAMPERED BY MALICIOUS PROCESS]"

        # Re-verify to demonstrate failure state
        result = AuditChainStore.verify_chain(records)
        return {
            "success": True,
            "corrupted_index": record_index,
            "corrupted_record_id": corrupted_rec.record_id,
            "verification_result": asdict(result),
        }

    async def handle_attestation_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC: attestation/get — Returns signed attestation report and operational metrics."""
        egress_count = params.get("egressCount", 0)
        report = self.attestation_engine.generate_attestation_report(egress_count=egress_count)
        metrics = self.attestation_engine.get_operational_metrics()
        return {
            "attestation": asdict(report),
            "metrics": [asdict(m) for m in metrics],
        }
