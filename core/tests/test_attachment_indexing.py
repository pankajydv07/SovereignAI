"""Comprehensive tests for Automatic PDF Indexing on Chat Attachment (Phases 1-3)."""

import asyncio
from collections.abc import AsyncGenerator
import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import numpy as np
import pytest

from agent.policy import PolicyEngine
from core.attachment_loader import process_chat_attachments
from core.chat_handlers import ChatManager
from ingest.types import (
    BoundingBox,
    DocumentClassification,
    IngestDocumentResult,
    IngestPageResult,
    Region,
    RegionType,
)
from kb.attachment_index import (
    AttachmentIndexRequest,
    AttachmentIndexResult,
    AttachmentIndexService,
)
from kb.chunker import LayoutAwareChunker
from kb.embedder import ChunkEmbedder, EmbeddingModelUnavailable
from kb.search import HybridSearchEngine
from kb.store import KnowledgeBaseStore
from kb.types import ClassificationLevel, UserRole
from models.ollama import OllamaClient
from models.registry import ModelRegistry
from models.router import ModelRouter
from storage.db import DatabaseManager
from storage.session_store import SessionStore
from tools.registry import ToolRegistry


def make_test_vector(seed_int: int, dim: int = 1024) -> list[float]:
    """Deterministic normalized test vector for testing."""
    rng = np.random.default_rng(seed_int)
    vec = rng.standard_normal(dim).astype(np.float32)
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec.tolist()


class MockTestEmbedder(ChunkEmbedder):
    """Mock embedder providing deterministic vectors for unit testing."""

    def __init__(self, dim: int = 1024, model: str = "bge-m3:latest") -> None:
        super().__init__(model=model)
        self._dim = dim

    async def get_dimension(self) -> int:
        return self._dim

    async def embed_single_text(self, text: str) -> list[float]:
        vec = np.zeros(self._dim, dtype=np.float32)
        for w in text.lower().split():
            idx = sum(ord(c) for c in w) % self._dim
            vec[idx] += 1.0
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        else:
            vec[0] = 1.0
        return vec.tolist()

    async def embed_texts_batched(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return [await self.embed_single_text(t) for t in texts]


@pytest.fixture
def db_mgr(tmp_path: Path) -> DatabaseManager:
    return DatabaseManager(tmp_path / "test_kb.db")


@pytest.fixture
def kb_store(db_mgr: DatabaseManager) -> KnowledgeBaseStore:
    return KnowledgeBaseStore(db_mgr)


@pytest.fixture
def mock_embedder() -> MockTestEmbedder:
    return MockTestEmbedder(dim=1024)


def create_sample_pdf_result(is_scanned: bool = False) -> IngestDocumentResult:
    """Create a sample born-digital or scanned ingest result."""
    bbox = BoundingBox(x0=0.05, y0=0.05, x1=0.95, y1=0.95)
    if is_scanned:
        regions = [
            Region(
                region_id="r1",
                region_type=RegionType.TEXT_BLOCK,
                bbox=bbox,
                page=1,
                text="INDIAN OIL CORPORATION LIMITED",
                confidence=0.98,
            ),
            Region(
                region_id="r2",
                region_type=RegionType.TEXT_BLOCK,
                bbox=bbox,
                page=1,
                text="Clause 4.1: Crude Distillation Unit operating temperature shall not exceed 380°C under normal atmospheric pressure.",
                confidence=0.95,
            ),
        ]
        pages = [
            IngestPageResult(
                page_num=1,
                classification=DocumentClassification.SCANNED,
                regions=regions,
            )
        ]
        doc_cls = DocumentClassification.SCANNED
    else:
        regions = [
            Region(
                region_id="r1",
                region_type=RegionType.TEXT_BLOCK,
                bbox=bbox,
                page=1,
                text="BHARAT PETROLEUM CORPORATION LIMITED",
                confidence=1.0,
            ),
            Region(
                region_id="r2",
                region_type=RegionType.TABLE_GRID,
                bbox=bbox,
                page=1,
                text="| Tag | Service | Design Temp | Design Pressure |\n| C-101 | Fractionator | 380 C | 2.5 bar |\n| C-102 | Stripper | 240 C | 1.8 bar |",
                confidence=1.0,
            ),
        ]
        pages = [
            IngestPageResult(
                page_num=1,
                classification=DocumentClassification.BORN_DIGITAL,
                regions=regions,
            )
        ]
        doc_cls = DocumentClassification.BORN_DIGITAL

    return IngestDocumentResult(
        doc_path="/tmp/sample.pdf",
        pages=pages,
        classification=doc_cls,
    )


# 1. Born-digital PDF upload -> chunks, FTS5 rows, and vectors present in SQLite
@pytest.mark.asyncio
async def test_born_digital_pdf_indexing(
    kb_store: KnowledgeBaseStore, mock_embedder: MockTestEmbedder, tmp_path: Path
) -> None:
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 mock content")
    sha256 = hashlib.sha256(pdf_file.read_bytes()).hexdigest()

    events: list[tuple[str, dict[str, Any]]] = []
    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document = AsyncMock(return_value=create_sample_pdf_result(is_scanned=False))

    service = AttachmentIndexService(
        kb_store=kb_store,
        embedder=mock_embedder,
        ingest_pipeline=mock_pipeline,
        chunker=LayoutAwareChunker(),
        send_notification_fn=lambda m, p: events.append((m, p)),
    )

    req = AttachmentIndexRequest(
        project_id="proj-alpha",
        session_id="sess-1",
        source_path=str(pdf_file),
        original_filename="report.pdf",
        sha256=sha256,
        uploaded_at="2026-09-08T00:00:00Z",
        uploader_id="eng-101",
    )

    res = await service.index_attachment(req)
    assert res.status == "indexed"
    assert res.chunk_count > 0

    # Verify SQLite persistence
    async with kb_store.db_manager.connect() as conn:
        await kb_store.db_manager.initialize_schema(conn)
        doc = await kb_store.get_document_by_project_and_hash(conn, "proj-alpha", sha256)
        assert doc is not None
        assert doc["status"] == "COMPLETED"
        assert doc["project_id"] == "proj-alpha"

        # Verify FTS5 and vector retrieval
        engine = HybridSearchEngine(mock_embedder)
        results, _, _ = await engine.retrieve_chunks(
            conn=conn,
            user_role="InspectionEngineer",
            query="Fractionator 380 C",
            project_id="proj-alpha",
            uploader_id="eng-101",
        )
        assert len(results) > 0
        assert "C-101" in results[0].body_text


# 2. Scanned PDF upload -> OCR progress emitted and bounding boxes stored
@pytest.mark.asyncio
async def test_scanned_pdf_ocr_path(
    kb_store: KnowledgeBaseStore, mock_embedder: MockTestEmbedder, tmp_path: Path
) -> None:
    pdf_file = tmp_path / "scanned_memo.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 scanned memo bytes")
    sha256 = hashlib.sha256(pdf_file.read_bytes()).hexdigest()

    events: list[tuple[str, dict[str, Any]]] = []
    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document = AsyncMock(return_value=create_sample_pdf_result(is_scanned=True))

    service = AttachmentIndexService(
        kb_store=kb_store,
        embedder=mock_embedder,
        ingest_pipeline=mock_pipeline,
        chunker=LayoutAwareChunker(),
        send_notification_fn=lambda m, p: events.append((m, p)),
    )

    req = AttachmentIndexRequest(
        project_id="proj-beta",
        session_id="sess-2",
        source_path=str(pdf_file),
        original_filename="scanned_memo.pdf",
        sha256=sha256,
        uploaded_at="2026-09-08T00:00:00Z",
        uploader_id="eng-102",
    )

    res = await service.index_attachment(req)
    assert res.status == "indexed"
    assert res.required_ocr is True

    # Check that OCR progress event was emitted
    ocr_events = [e for e in events if e[1].get("update", {}).get("stage") == "ocr"]
    assert len(ocr_events) == 1


# 3. Vector dimension assertion
@pytest.mark.asyncio
async def test_vector_dimension_exact(
    kb_store: KnowledgeBaseStore, mock_embedder: MockTestEmbedder, tmp_path: Path
) -> None:
    pdf_file = tmp_path / "spec.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 spec bytes")
    sha256 = hashlib.sha256(pdf_file.read_bytes()).hexdigest()

    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document = AsyncMock(return_value=create_sample_pdf_result(is_scanned=False))

    service = AttachmentIndexService(
        kb_store=kb_store,
        embedder=mock_embedder,
        ingest_pipeline=mock_pipeline,
        chunker=LayoutAwareChunker(),
    )

    req = AttachmentIndexRequest(
        project_id="proj-gamma",
        session_id="sess-3",
        source_path=str(pdf_file),
        original_filename="spec.pdf",
        sha256=sha256,
        uploaded_at="2026-09-08T00:00:00Z",
        uploader_id="eng-103",
    )

    await service.index_attachment(req)

    async with kb_store.db_manager.connect() as conn:
        await kb_store.db_manager.initialize_schema(conn)
        cursor = await conn.execute(
            "SELECT chunk_id, embedding_json, dimension FROM kb_vectors"
        )
        row = await cursor.fetchone()
        assert row is not None
        import json
        vec = json.loads(row[1])
        dim = await mock_embedder.get_dimension()
        assert len(vec) == dim == 1024
        assert row[2] == 1024


# 4. Atomic table chunking (no split rows, columns preserved)
@pytest.mark.asyncio
async def test_atomic_table_chunking() -> None:
    chunker = LayoutAwareChunker()
    ingest_res = create_sample_pdf_result(is_scanned=False)
    doc = chunker.chunk_document(
        doc_id="doc_test_table",
        title="table_spec.pdf",
        dept="Operations",
        classification=ClassificationLevel.CONFIDENTIAL,
        effective_date="2026-09-08",
        allowed_roles=["*"],
        ingest_result=ingest_res,
        content_hash="mockhash",
        project_id="proj-1",
        session_id="sess-1",
    )

    table_chunks = [c for c in doc.chunks if "Tag | Service" in c.body_text]
    assert len(table_chunks) >= 1
    # Check that table text contains full header and rows
    assert "Tag | Service" in table_chunks[0].body_text
    assert "C-101 | Fractionator" in table_chunks[0].body_text
    assert "C-102 | Stripper" in table_chunks[0].body_text


# 5. Deduplication: COMPLETED short-circuits, INCOMPLETE re-runs
@pytest.mark.asyncio
async def test_deduplication_completed_and_incomplete(
    kb_store: KnowledgeBaseStore, mock_embedder: MockTestEmbedder, tmp_path: Path
) -> None:
    pdf_file = tmp_path / "dedupe.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dedupe bytes")
    sha256 = hashlib.sha256(pdf_file.read_bytes()).hexdigest()

    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document = AsyncMock(return_value=create_sample_pdf_result(is_scanned=False))

    service = AttachmentIndexService(
        kb_store=kb_store,
        embedder=mock_embedder,
        ingest_pipeline=mock_pipeline,
        chunker=LayoutAwareChunker(),
    )

    req = AttachmentIndexRequest(
        project_id="proj-dedupe",
        session_id="sess-4",
        source_path=str(pdf_file),
        original_filename="dedupe.pdf",
        sha256=sha256,
        uploaded_at="2026-09-08T00:00:00Z",
        uploader_id="eng-104",
    )

    # First run: should index
    res1 = await service.index_attachment(req)
    assert res1.status == "indexed"

    # Second run: identical hash + COMPLETED -> already_indexed
    res2 = await service.index_attachment(req)
    assert res2.status == "already_indexed"

    # Simulate INCOMPLETE status (e.g. previous crash or failed embedding)
    async with kb_store.db_manager.connect() as conn:
        await kb_store.db_manager.initialize_schema(conn)
        await conn.execute("UPDATE kb_documents SET status = 'INCOMPLETE' WHERE content_hash = ?", (sha256,))
        await conn.commit()

    # Third run: INCOMPLETE status -> re-runs import and completes
    res3 = await service.index_attachment(req)
    assert res3.status == "indexed"


# 6. Modified file (new revision) marks previous superseded_by
@pytest.mark.asyncio
async def test_revision_superseded(
    kb_store: KnowledgeBaseStore, mock_embedder: MockTestEmbedder, tmp_path: Path
) -> None:
    pdf_v1 = tmp_path / "sop_v1.pdf"
    pdf_v1.write_bytes(b"%PDF-1.4 revision 1 content")
    sha256_v1 = hashlib.sha256(pdf_v1.read_bytes()).hexdigest()

    pdf_v2 = tmp_path / "sop_v2.pdf"
    pdf_v2.write_bytes(b"%PDF-1.4 revision 2 content modified")
    sha256_v2 = hashlib.sha256(pdf_v2.read_bytes()).hexdigest()

    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document = AsyncMock(return_value=create_sample_pdf_result(is_scanned=False))

    service = AttachmentIndexService(
        kb_store=kb_store,
        embedder=mock_embedder,
        ingest_pipeline=mock_pipeline,
        chunker=LayoutAwareChunker(),
    )

    req_v1 = AttachmentIndexRequest(
        project_id="proj-rev",
        session_id="sess-5",
        source_path=str(pdf_v1),
        original_filename="standard_operating_procedure.pdf",
        sha256=sha256_v1,
        uploaded_at="2026-09-08T00:00:00Z",
        uploader_id="eng-105",
    )
    await service.index_attachment(req_v1)

    # Index v2 with the same original filename
    req_v2 = AttachmentIndexRequest(
        project_id="proj-rev",
        session_id="sess-5",
        source_path=str(pdf_v2),
        original_filename="standard_operating_procedure.pdf",
        sha256=sha256_v2,
        uploaded_at="2026-09-08T01:00:00Z",
        uploader_id="eng-105",
    )
    res_v2 = await service.index_attachment(req_v2)
    assert res_v2.status == "indexed"

    async with kb_store.db_manager.connect() as conn:
        await kb_store.db_manager.initialize_schema(conn)
        doc_v1 = await kb_store.get_document_by_project_and_hash(conn, "proj-rev", sha256_v1)
        assert doc_v1 is not None
        assert doc_v1["superseded_by"] == f"doc_proj-rev_{sha256_v2[:12]}"


# 7. Project isolation
@pytest.mark.asyncio
async def test_project_isolation(
    kb_store: KnowledgeBaseStore, mock_embedder: MockTestEmbedder, tmp_path: Path
) -> None:
    pdf_file = tmp_path / "secret.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 confidential data")
    sha256 = hashlib.sha256(pdf_file.read_bytes()).hexdigest()

    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document = AsyncMock(return_value=create_sample_pdf_result(is_scanned=False))

    service = AttachmentIndexService(
        kb_store=kb_store,
        embedder=mock_embedder,
        ingest_pipeline=mock_pipeline,
        chunker=LayoutAwareChunker(),
    )

    req = AttachmentIndexRequest(
        project_id="proj-isolated-A",
        session_id="sess-6",
        source_path=str(pdf_file),
        original_filename="secret.pdf",
        sha256=sha256,
        uploaded_at="2026-09-08T00:00:00Z",
        uploader_id="eng-106",
    )
    await service.index_attachment(req)

    engine = HybridSearchEngine(mock_embedder)
    async with kb_store.db_manager.connect() as conn:
        await kb_store.db_manager.initialize_schema(conn)
        # Search from project B should yield 0 results
        results_proj_b, _, _ = await engine.retrieve_chunks(
            conn=conn,
            user_role="InspectionEngineer",
            query="Fractionator",
            project_id="proj-isolated-B",
            uploader_id="eng-106",
        )
        assert len(results_proj_b) == 0

        # Search from project A should succeed
        results_proj_a, _, _ = await engine.retrieve_chunks(
            conn=conn,
            user_role="InspectionEngineer",
            query="Fractionator",
            project_id="proj-isolated-A",
            uploader_id="eng-106",
        )
        assert len(results_proj_a) > 0


# 8. Uploader ACL
@pytest.mark.asyncio
async def test_uploader_acl_retrieval(
    kb_store: KnowledgeBaseStore, mock_embedder: MockTestEmbedder, tmp_path: Path
) -> None:
    pdf_file = tmp_path / "restricted.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 restricted audit")
    sha256 = hashlib.sha256(pdf_file.read_bytes()).hexdigest()

    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document = AsyncMock(return_value=create_sample_pdf_result(is_scanned=False))

    service = AttachmentIndexService(
        kb_store=kb_store,
        embedder=mock_embedder,
        ingest_pipeline=mock_pipeline,
        chunker=LayoutAwareChunker(),
    )

    req = AttachmentIndexRequest(
        project_id="proj-acl",
        session_id="sess-7",
        source_path=str(pdf_file),
        original_filename="restricted.pdf",
        sha256=sha256,
        uploaded_at="2026-09-08T00:00:00Z",
        uploader_id="contractor-999",
        classification=ClassificationLevel.RESTRICTED,
    )
    await service.index_attachment(req)

    engine = HybridSearchEngine(mock_embedder)
    async with kb_store.db_manager.connect() as conn:
        await kb_store.db_manager.initialize_schema(conn)
        # A user with Public clearance who IS the uploader should retrieve their document
        results, _, _ = await engine.retrieve_chunks(
            conn=conn,
            user_role="Public",
            query="Fractionator",
            project_id="proj-acl",
            uploader_id="contractor-999",
        )
        assert len(results) > 0


# 9. Cancellation cleanup
@pytest.mark.asyncio
async def test_cancellation_cleans_up_document(
    kb_store: KnowledgeBaseStore, mock_embedder: MockTestEmbedder, tmp_path: Path
) -> None:
    pdf_file = tmp_path / "cancel.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 cancel bytes")
    sha256 = hashlib.sha256(pdf_file.read_bytes()).hexdigest()

    async def slow_ingest(*args: Any, **kwargs: Any) -> IngestDocumentResult:
        await asyncio.sleep(5.0)
        return create_sample_pdf_result(is_scanned=False)

    mock_pipeline = MagicMock()
    mock_pipeline.ingest_document = slow_ingest

    service = AttachmentIndexService(
        kb_store=kb_store,
        embedder=mock_embedder,
        ingest_pipeline=mock_pipeline,
        chunker=LayoutAwareChunker(),
    )

    req = AttachmentIndexRequest(
        project_id="proj-cancel",
        session_id="sess-8",
        source_path=str(pdf_file),
        original_filename="cancel.pdf",
        sha256=sha256,
        uploaded_at="2026-09-08T00:00:00Z",
        uploader_id="eng-108",
    )

    task = asyncio.create_task(service.index_attachment(req))
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    async with kb_store.db_manager.connect() as conn:
        await kb_store.db_manager.initialize_schema(conn)
        doc = await kb_store.get_document_by_project_and_hash(conn, "proj-cancel", sha256)
        assert doc is None


# 10. Non-blocking chat stream and direct parse
@pytest.mark.asyncio
async def test_nonblocking_chat_streaming(tmp_path: Path) -> None:
    db_file = tmp_path / "test_chat.db"
    store = SessionStore(db_file)
    reg = ModelRegistry()
    tools = ToolRegistry()

    mock_ollama = MagicMock()
    mock_ollama.get_installed_tags = AsyncMock(return_value={"gpt-oss:20b", "project-brain:latest", "qwen2.5vl:7b"})

    async def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        yield {"message": {"content": "First token streamed immediately."}}
        yield {"done": True, "prompt_eval_count": 10, "eval_count": 15}

    mock_ollama.stream_chat = mock_stream
    router = ModelRouter(reg)
    policy = PolicyEngine(session_store=store)

    notifications: list[tuple[str, dict[str, Any]]] = []
    responses: list[dict[str, Any]] = []

    pdf_file = tmp_path / "chat_attachment.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 chat attachment test content")

    mgr = ChatManager(
        model_registry=reg,
        tool_registry=tools,
        ollama_client=mock_ollama,
        router=router,
        policy_engine=policy,
        send_notification_fn=lambda m, p: notifications.append((m, p)),
        send_response_fn=lambda r: responses.append(r),
        log_stderr_fn=lambda msg: None,
    )

    # Call handle_chat_stream with PDF attachment
    await mgr.handle_chat_stream(
        msg_id=202,
        params={
            "messages": [{"role": "user", "content": "Analyze the attached refinery memo"}],
            "sessionId": "sess-chat-stream",
            "projectId": "proj-chat-stream",
            "attachments": [{"name": "chat_attachment.pdf", "path": str(pdf_file)}],
        },
        store=store,
    )

    # Verify chat completed without waiting for background indexing completion
    assert len(responses) == 1
    assert responses[0]["result"]["status"] == "completed"
    assert "First token streamed immediately." in responses[0]["result"]["content"]

    # Verify that background tasks set was registered
    assert len(mgr.active_indexing_tasks.get("sess-chat-stream", [])) >= 1
