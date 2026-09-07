"""Unit and integration tests for Knowledge Base hybrid retrieval, role security, and import lifecycle."""

from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
import numpy as np

from ingest.types import (
    BoundingBox,
    DocumentClassification,
    IngestDocumentResult,
    IngestPageResult,
    Region,
    RegionType,
)
from kb.chunker import LayoutAwareChunker
from kb.embedder import ChunkEmbedder, EmbeddingModelUnavailable
from kb.importer import KBImportService
from kb.search import HybridSearchEngine
from kb.store import KnowledgeBaseStore
from kb.types import (
    ClassificationLevel,
    EmbeddingDimensionMismatchError,
    KBChunk,
    KBDocument,
    UserRole,
)
from storage.db import DatabaseManager


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
        seed = sum(ord(c) for c in text)
        return make_test_vector(seed, self._dim)

    async def embed_texts_batched(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return [await self.embed_single_text(t) for t in texts]


@pytest.fixture
def db_mgr(tmp_path: Path) -> DatabaseManager:
    """Fixture providing a temporary SQLite database manager."""
    db_file = tmp_path / "test_kb.db"
    return DatabaseManager(db_file)


def test_layout_aware_chunker_token_limit() -> None:
    """Test chunker splits oversized layout regions to target token size using calibrated counter."""
    # Construct a very large text region
    long_text = "Detailed ultrasonic wall thickness survey on shell course 3 CML-07. " * 30  # ~360 words

    ingest_res = IngestDocumentResult(
        doc_path="doc_long.pdf",
        classification="BORN_DIGITAL",
        pages=[
            IngestPageResult(
                page_num=1,
                classification="BORN_DIGITAL",
                words=[],
                regions=[
                    Region(
                        region_id="r1",
                        region_type=RegionType.TEXT_BLOCK,
                        bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.2),
                        page=1,
                        text="SOP-114 REFINERY THICKNESS SURVEY PROCEDURE",
                    ),
                    Region(
                        region_id="r2",
                        region_type=RegionType.TEXT_BLOCK,
                        bbox=BoundingBox(x0=0.1, y0=0.21, x1=0.9, y1=0.8),
                        page=1,
                        text=long_text,
                    ),
                ],
            )
        ],
    )

    chunker = LayoutAwareChunker(target_tokens=150)
    doc = chunker.chunk_document(
        doc_id="sop_114_long",
        title="SOP-114 Long",
        dept="Inspection",
        classification=ClassificationLevel.INTERNAL,
        effective_date="2026-01-01",
        allowed_roles=[UserRole.INSPECTION_ENGINEER],
        ingest_result=ingest_res,
    )

    # Must have split the oversized region into multiple sub-chunks
    assert len(doc.chunks) >= 2
    for chunk in doc.chunks:
        assert chunk.token_count <= 180  # Bounded near target tokens


@pytest.mark.asyncio
async def test_embedder_unavailable_raises_loudly() -> None:
    """Test embedder raises EmbeddingModelUnavailable on connection or HTTP error."""
    embedder = ChunkEmbedder(ollama_url="http://127.0.0.1:99999")  # Non-existent port
    with pytest.raises(EmbeddingModelUnavailable) as exc_info:
        await embedder.embed_single_text("test query")
    assert "unavailable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dimension_mismatch_detected(db_mgr: DatabaseManager) -> None:
    """Test that embedding dimension mismatch between query and store raises EmbeddingDimensionMismatchError."""
    store = KnowledgeBaseStore(db_mgr)
    mock_embedder_1024 = MockTestEmbedder(dim=1024)
    search_engine_768 = HybridSearchEngine(embedder=MockTestEmbedder(dim=768))

    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)

        doc = KBDocument(
            id="doc_1024",
            title="Doc 1024",
            dept="Inspection",
            classification=ClassificationLevel.INTERNAL,
            effectiveDate="2026-01-01",
            chunks=[
                KBChunk(
                    id="chunk_1",
                    docId="doc_1024",
                    chunkIndex=1,
                    headingPath="Doc 1024 › Section 1",
                    bodyText="Sample inspection text",
                    tokenCount=50,
                    page=1,
                    bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                    allowedRoles=["*"],
                    effectiveDate="2026-01-01",
                )
            ],
        )
        await store.insert_document(conn, doc)
        # Store 1024-d vector
        await store.save_chunk_embeddings(
            conn, ["chunk_1"], [make_test_vector(42, 1024)], embedding_model="bge-m3:latest", dimension=1024
        )

        # Querying with 768-d embedder MUST raise dimension mismatch
        with pytest.raises(EmbeddingDimensionMismatchError) as exc_info:
            await search_engine_768.retrieve_chunks(
                conn, user_role="InspectionEngineer", query="sample query"
            )
        assert "dimension mismatch" in str(exc_info.value)


@pytest.mark.asyncio
async def test_import_service_incomplete_recovery(tmp_path: Path, db_mgr: DatabaseManager) -> None:
    """Test that importing a previously INCOMPLETE document purges partial chunks and re-runs."""
    store = KnowledgeBaseStore(db_mgr)
    sample_file = tmp_path / "sample_sop.txt"
    sample_file.write_text("MRPL SOP 101 Ultrasonic inspection procedure on crude column C-101", encoding="utf-8")

    mock_ingest = AsyncMock()
    mock_ingest.ingest_document.return_value = IngestDocumentResult(
        doc_path=str(sample_file),
        classification=DocumentClassification.BORN_DIGITAL,
        pages=[
            IngestPageResult(
                page_num=1,
                classification=DocumentClassification.BORN_DIGITAL,
                regions=[
                    Region(
                        region_id="r1",
                        region_type=RegionType.TEXT_BLOCK,
                        bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
                        page=1,
                        text="MRPL SOP 101 Ultrasonic inspection procedure on crude column C-101",
                        confidence=0.98,
                    )
                ],
            )
        ],
    )

    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)

        # Simulate failed first import leaving document as INCOMPLETE
        doc_failed = KBDocument(
            id="sop_failed",
            title="SOP Failed",
            dept="Inspection",
            contentHash=KBImportService.calculate_file_hash(sample_file),
            status="INCOMPLETE",
            classification=ClassificationLevel.INTERNAL,
            effectiveDate="2026-01-01",
            chunks=[
                KBChunk(
                    id="chunk_failed_1",
                    docId="sop_failed",
                    chunkIndex=1,
                    headingPath="SOP Failed",
                    bodyText="Orphan chunk",
                    tokenCount=20,
                    page=1,
                    bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                    allowedRoles=["*"],
                    effectiveDate="2026-01-01",
                )
            ],
        )
        await store.insert_document(conn, doc_failed)

        # Run KBImportService on the same file -> must purge INCOMPLETE and complete indexing
        importer = KBImportService(
            kb_store=store,
            embedder=MockTestEmbedder(dim=1024),
            ingest_pipeline=mock_ingest,
        )

        res = await importer.import_document(
            conn=conn,
            file_path=sample_file,
            doc_id="sop_recovered",
            title="SOP Recovered",
            dept="Inspection",
            classification=ClassificationLevel.INTERNAL,
            effective_date="2026-01-01",
        )
        assert res.status == "COMPLETED"


@pytest.mark.asyncio
async def test_import_service_revision_supersession(tmp_path: Path, db_mgr: DatabaseManager) -> None:
    """Test revision supersession updates superseded_by pointer on old document."""
    store = KnowledgeBaseStore(db_mgr)

    mock_ingest = AsyncMock()
    mock_ingest.ingest_document.return_value = IngestDocumentResult(
        doc_path="sop_path",
        classification=DocumentClassification.BORN_DIGITAL,
        pages=[
            IngestPageResult(
                page_num=1,
                classification=DocumentClassification.BORN_DIGITAL,
                regions=[
                    Region(
                        region_id="r1",
                        region_type=RegionType.TEXT_BLOCK,
                        bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
                        page=1,
                        text="SOP 114 inspection guidelines and procedure",
                        confidence=0.98,
                    )
                ],
            )
        ],
    )

    importer = KBImportService(
        kb_store=store,
        embedder=MockTestEmbedder(dim=1024),
        ingest_pipeline=mock_ingest,
    )

    f1 = tmp_path / "sop_rev18.txt"
    f1.write_text("SOP 114 revision 18 inspection guidelines", encoding="utf-8")
    f2 = tmp_path / "sop_rev19.txt"
    f2.write_text("SOP 114 revision 19 inspection guidelines with updated UT threshold", encoding="utf-8")

    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)

        # Import rev 18
        doc1 = await importer.import_document(
            conn=conn, file_path=f1, doc_id="SOP-114-rev18", title="SOP-114", revision="rev.18"
        )
        assert doc1.status == "COMPLETED"

        # Import rev 19 superseding rev 18
        doc2 = await importer.import_document(
            conn=conn,
            file_path=f2,
            doc_id="SOP-114-rev19",
            title="SOP-114",
            revision="rev.19",
            supersedes_doc_id="SOP-114-rev18",
        )
        assert doc2.status == "COMPLETED"

        # Check that rev 18 is now superseded
        cursor = await conn.execute("SELECT superseded_by FROM kb_documents WHERE id = 'SOP-114-rev18'")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "SOP-114-rev19"
