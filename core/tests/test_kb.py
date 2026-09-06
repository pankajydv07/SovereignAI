"""Unit and integration tests for Knowledge Base hybrid retrieval and role security."""

from pathlib import Path
import pytest
from ingest.types import BoundingBox, IngestDocumentResult, IngestPageResult, Region, RegionType
from kb.chunker import LayoutAwareChunker
from kb.embedder import generate_synthetic_embedding
from kb.search import HybridSearchEngine
from kb.store import KnowledgeBaseStore
from kb.types import ClassificationLevel, KBChunk, KBDocument, UserRole
from storage.db import DatabaseManager


@pytest.fixture
def db_mgr(tmp_path: Path) -> DatabaseManager:
    """Fixture providing a temporary SQLite database manager."""
    db_file = tmp_path / "test_kb.db"
    return DatabaseManager(db_file)


def test_layout_aware_chunker() -> None:
    """Test chunking with heading path prefixing."""
    ingest_res = IngestDocumentResult(
        doc_path="doc1.pdf",
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
                        text="SOP-114 REFINERY INSPECTION",
                    ),
                    Region(
                        region_id="r2",
                        region_type=RegionType.TEXT_BLOCK,
                        bbox=BoundingBox(x0=0.1, y0=0.21, x1=0.9, y1=0.5),
                        page=1,
                        text="Thickness readings on FT-1702 flow transmitter must comply with IS-2825 Cl 4.2.",
                    ),
                ],
            )
        ],
    )

    chunker = LayoutAwareChunker()
    doc = chunker.chunk_document(
        doc_id="sop_114",
        title="SOP-114",
        dept="Inspection",
        classification=ClassificationLevel.INTERNAL,
        effective_date="2026-01-01",
        allowed_roles=[UserRole.INSPECTION_ENGINEER],
        ingest_result=ingest_res,
    )

    assert len(doc.chunks) >= 1
    chunk = doc.chunks[0]
    assert "SOP-114" in chunk.heading_path
    assert "FT-1702" in chunk.body_text


@pytest.mark.asyncio
async def test_indexed_role_security_filtering(db_mgr: DatabaseManager) -> None:
    """Test role security filtering on indexed kb_chunk_roles join table."""
    store = KnowledgeBaseStore(db_mgr)
    engine = HybridSearchEngine()

    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)

        # Confidential SOP for InspectionEngineer
        doc1 = KBDocument(
            id="sop_confidential",
            title="Confidential Refractory Inspection",
            dept="Inspection",
            classification=ClassificationLevel.CONFIDENTIAL,
            effectiveDate="2026-01-01",
            chunks=[
                KBChunk(
                    id="chunk_conf_1",
                    docId="sop_confidential",
                    chunkIndex=1,
                    headingPath="SOP-101 › Refractory",
                    bodyText="Equipment C-101 refractory lining inspection procedure for high temperature unit.",
                    tokenCount=100,
                    page=1,
                    bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                    allowedRoles=[UserRole.INSPECTION_ENGINEER],
                    effectiveDate="2026-01-01",
                )
            ],
        )

        # Public SOP for all roles
        doc2 = KBDocument(
            id="sop_public",
            title="Public Safety Guidelines",
            dept="Safety",
            classification=ClassificationLevel.PUBLIC,
            effectiveDate="2026-01-01",
            chunks=[
                KBChunk(
                    id="chunk_pub_1",
                    docId="sop_public",
                    chunkIndex=1,
                    headingPath="SOP-201 › Safety",
                    bodyText="General helmet and protective gear safety procedure for all refinery staff.",
                    tokenCount=80,
                    page=1,
                    bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                    allowedRoles=["*"],
                    effectiveDate="2026-01-01",
                )
            ],
        )

        await store.insert_document(conn, doc1)
        await store.insert_document(conn, doc2)

        # Save synthetic embeddings
        await store.save_chunk_embeddings(
            conn,
            ["chunk_conf_1", "chunk_pub_1"],
            [
                generate_synthetic_embedding(doc1.chunks[0].body_text),
                generate_synthetic_embedding(doc2.chunks[0].body_text),
            ],
        )

        # Query as InspectionEngineer -> Should return confidential chunk
        eng_results = await engine.retrieve_chunks(
            conn, user_role=UserRole.INSPECTION_ENGINEER, query="C-101 inspection"
        )
        returned_ids_eng = [r.chunk_id for r in eng_results]
        assert "chunk_conf_1" in returned_ids_eng

        # Query as PublicUser -> Confidential chunk MUST be filtered out in SQL
        pub_results = await engine.retrieve_chunks(
            conn, user_role=UserRole.PUBLIC_USER, query="C-101 inspection"
        )
        returned_ids_pub = [r.chunk_id for r in pub_results]
        assert "chunk_conf_1" not in returned_ids_pub


@pytest.mark.asyncio
async def test_chokepoint_enforcement(db_mgr: DatabaseManager) -> None:
    """Test that retrieve_chunks raises ValueError if user_role is missing/empty."""
    engine = HybridSearchEngine()
    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)
        with pytest.raises(ValueError, match="user_role is mandatory"):
            await engine.retrieve_chunks(conn, user_role="", query="equipment tag")


@pytest.mark.asyncio
async def test_superseded_and_effective_date_filters(db_mgr: DatabaseManager) -> None:
    """Test superseded_by IS NULL and effective_date <= CURRENT_DATE filters."""
    store = KnowledgeBaseStore(db_mgr)
    engine = HybridSearchEngine()

    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)

        doc_superseded = KBDocument(
            id="sop_old",
            title="Old SOP",
            dept="Process",
            classification=ClassificationLevel.INTERNAL,
            effectiveDate="2020-01-01",
            supersededBy="sop_new",
            chunks=[
                KBChunk(
                    id="chunk_old_1",
                    docId="sop_old",
                    chunkIndex=1,
                    headingPath="SOP-001 › Old",
                    bodyText="Superseded pressure valve calibration instructions.",
                    tokenCount=50,
                    page=1,
                    bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                    allowedRoles=["*"],
                    effectiveDate="2020-01-01",
                    supersededBy="sop_new",
                )
            ],
        )

        doc_future = KBDocument(
            id="sop_future",
            title="Future SOP",
            dept="Process",
            classification=ClassificationLevel.INTERNAL,
            effectiveDate="2099-01-01",  # Future date
            chunks=[
                KBChunk(
                    id="chunk_fut_1",
                    docId="sop_future",
                    chunkIndex=1,
                    headingPath="SOP-999 › Future",
                    bodyText="Future pressure valve calibration instructions.",
                    tokenCount=50,
                    page=1,
                    bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                    allowedRoles=["*"],
                    effectiveDate="2099-01-01",
                )
            ],
        )

        await store.insert_document(conn, doc_superseded)
        await store.insert_document(conn, doc_future)

        await store.save_chunk_embeddings(
            conn,
            ["chunk_old_1", "chunk_fut_1"],
            [
                generate_synthetic_embedding(doc_superseded.chunks[0].body_text),
                generate_synthetic_embedding(doc_future.chunks[0].body_text),
            ],
        )

        results = await engine.retrieve_chunks(
            conn,
            user_role=UserRole.INSPECTION_ENGINEER,
            query="pressure valve calibration",
            today_date="2026-09-06",
        )
        returned_ids = [r.chunk_id for r in results]
        assert "chunk_old_1" not in returned_ids
        assert "chunk_fut_1" not in returned_ids


@pytest.mark.asyncio
async def test_ungroundable_question_fallback(db_mgr: DatabaseManager) -> None:
    """Test ungroundable query returns empty results triggering fallback message."""
    engine = HybridSearchEngine()
    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)
        results = await engine.retrieve_chunks(
            conn, user_role=UserRole.INSPECTION_ENGINEER, query="completely ungrounded quantum mechanics"
        )
        assert len(results) == 0
