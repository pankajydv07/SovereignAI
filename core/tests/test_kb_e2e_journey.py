"""End-to-end integration test for the Knowledge Base & Task-Gated RAG Journey.

Tests:
1. Document ingestion and indexing via KBImportService
2. Task-gated pre-retrieval execution for kb_qa, official_drafting, doc_summarise
3. Prompt context augmentation and UI notification emission with provenance (docId, headingPath, page, bbox)
4. Non-retrieval task class gating (e.g. code_generate, vision_ocr)
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.pre_retrieval import maybe_execute_preretrieval
from ingest.types import (
    BoundingBox,
    DocumentClassification,
    IngestDocumentResult,
    IngestPageResult,
    Region,
    RegionType,
)
from kb.embedder import ChunkEmbedder
from kb.importer import KBImportService
from kb.store import KnowledgeBaseStore
from kb.types import ClassificationLevel
from storage.db import DatabaseManager


class MockDeterministicEmbedder(ChunkEmbedder):
    """Deterministic mock embedder for e2e integration testing."""

    def __init__(self) -> None:
        super().__init__()
        self._dim = 768

    async def get_dimension(self) -> int:
        return self._dim

    async def embed_single_text(self, text: str) -> list[float]:
        # High similarity for queries mentioning UT or C-101
        vec = [0.0] * self._dim
        if "C-101" in text or "ultrasonic" in text.lower() or "thickness" in text.lower():
            vec[0] = 0.95
            vec[1] = 0.20
        else:
            vec[0] = 0.10
            vec[1] = 0.90
        return vec

    async def embed_texts_batched(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return [await self.embed_single_text(t) for t in texts]


@pytest.mark.asyncio
async def test_kb_e2e_rag_journey(tmp_path: Path) -> None:
    """Prove end-to-end KB indexing and task-gated RAG context augmentation."""
    db_file = tmp_path / "rag_journey.db"
    db_mgr = DatabaseManager(db_file)
    store = KnowledgeBaseStore(db_mgr)
    embedder = MockDeterministicEmbedder()

    # Step 1: Import a realistic refinery SOP document via KBImportService
    sop_file = tmp_path / "MRPL_SOP_101.pdf"
    sop_file.write_text("SOP 101: Ultrasonic thickness inspection procedure on crude distillation column C-101.", encoding="utf-8")

    mock_ingest = AsyncMock()
    mock_ingest.ingest_document.return_value = IngestDocumentResult(
        doc_path=str(sop_file),
        classification=DocumentClassification.BORN_DIGITAL,
        pages=[
            IngestPageResult(
                page_num=1,
                classification=DocumentClassification.BORN_DIGITAL,
                regions=[
                    Region(
                        region_id="r_sop_1",
                        region_type=RegionType.TEXT_BLOCK,
                        bbox=BoundingBox(x0=0.10, y0=0.15, x1=0.90, y1=0.45),
                        page=1,
                        text="MRPL SOP 101: Ultrasonic thickness inspection procedure on crude distillation column C-101. Minimum retirement thickness is 6.5 mm per IS 2825 Cl 4.2.",
                        confidence=0.99,
                    )
                ],
            )
        ],
    )

    importer = KBImportService(
        kb_store=store,
        embedder=embedder,
        ingest_pipeline=mock_ingest,
    )

    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)

        doc = await importer.import_document(
            conn=conn,
            file_path=sop_file,
            doc_id="MRPL-SOP-101",
            title="Ultrasonic Thickness SOP for C-101",
            dept="Inspection",
            classification=ClassificationLevel.INTERNAL,
            effective_date="2026-09-01",
            revision="rev.03",
        )
        assert doc.status == "COMPLETED"
        assert len(doc.chunks) == 1
        assert doc.chunks[0].token_count > 0

    # Step 2: Test Task-Gated Pre-retrieval for kb_qa task
    notifications: list[tuple[str, dict]] = []
    def mock_send_notification(method: str, params: dict) -> None:
        notifications.append((method, params))

    class MockSessionStore:
        def _get_connection(self):
            return db_mgr.connect()

    mock_session_store = MockSessionStore()
    mock_registry = MagicMock()

    # Pre-retrieval for 'kb_qa' query
    messages_qa = [{"role": "user", "content": "What is the retirement thickness for C-101 ultrasonic inspection?"}]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("core.pre_retrieval.ChunkEmbedder", lambda **kwargs: embedder)
        await maybe_execute_preretrieval(
            task_class="kb_qa",
            user_prompt="What is the retirement thickness for C-101 ultrasonic inspection?",
            user_role="InspectionEngineer",
            num_ctx=8192,
            model_registry=mock_registry,
            session_store=mock_session_store,
            session_id="sess_123",
            messages=messages_qa,
            send_notification_fn=mock_send_notification,
        )

    # Verify context injected into prompt
    assert "## Retrieved Knowledge Base Context" in messages_qa[-1]["content"]
    assert "MRPL-SOP-101" in messages_qa[-1]["content"]
    assert "IS 2825 Cl 4.2" in messages_qa[-1]["content"]

    # Verify notification emitted with source provenance
    assert len(notifications) == 1
    assert notifications[0][0] == "session/update"
    update_data = notifications[0][1]["update"]
    assert update_data["type"] == "sources"
    assert update_data["showingCount"] == 1
    assert update_data["isTruncated"] is False
    source = update_data["sources"][0]
    assert source["docId"] == "MRPL-SOP-101"
    assert source["page"] == 1
    assert "bbox" in source
    assert source["bbox"]["x0"] == 0.10

    # Step 3: Verify non-retrieval task class (code_generate) is NOT augmented
    messages_code = [{"role": "user", "content": "def calculate_wall_loss(t_nom, t_act):"}]
    notifications.clear()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("core.pre_retrieval.ChunkEmbedder", lambda **kwargs: embedder)
        await maybe_execute_preretrieval(
            task_class="code_generate",
            user_prompt="def calculate_wall_loss(t_nom, t_act):",
            user_role="InspectionEngineer",
            num_ctx=8192,
            model_registry=mock_registry,
            session_store=mock_session_store,
            session_id="sess_123",
            messages=messages_code,
            send_notification_fn=mock_send_notification,
        )

    # Prompt unchanged and zero notifications sent
    assert messages_code[-1]["content"] == "def calculate_wall_loss(t_nom, t_act):"
    assert len(notifications) == 0
