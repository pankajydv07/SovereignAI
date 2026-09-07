"""Knowledge Base Document Import Service.

Executes production pipeline:
file -> ingest_document -> chunk_document -> embed_texts_batched -> insert_document -> save_chunk_embeddings -> index_fts5
"""

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

from ingest.pipeline import DocumentIngestPipeline
from kb.chunker import LayoutAwareChunker
from kb.embedder import ChunkEmbedder
from kb.store import KnowledgeBaseStore
from kb.types import ClassificationLevel, KBDocument

log = structlog.get_logger()

ProgressCallback = Callable[[str, float, str], None]


class KBImportService:
    """Async import service for registering and indexing documents into the Knowledge Base."""

    def __init__(
        self,
        kb_store: KnowledgeBaseStore,
        embedder: ChunkEmbedder | None = None,
        ingest_pipeline: DocumentIngestPipeline | None = None,
        chunker: LayoutAwareChunker | None = None,
    ) -> None:
        self.kb_store = kb_store
        self.embedder = embedder or ChunkEmbedder()
        self.ingest_pipeline = ingest_pipeline or DocumentIngestPipeline()
        self.chunker = chunker or LayoutAwareChunker()

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """Compute SHA-256 content hash of the input file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def import_document(
        self,
        conn: aiosqlite.Connection,
        file_path: str | Path,
        doc_id: str,
        title: str,
        dept: str = "Engineering",
        classification: ClassificationLevel = ClassificationLevel.INTERNAL,
        effective_date: str = "2026-01-01",
        revision: str = "rev.01",
        allowed_roles: list[str] | None = None,
        supersedes_doc_id: str | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> KBDocument:
        """Import, chunk, embed, and index a document into SQLite KB with fail-loud error handling."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        roles = allowed_roles or ["*"]
        content_hash = self.calculate_file_hash(path)

        def report(stage: str, progress: float, message: str) -> None:
            if progress_cb:
                progress_cb(stage, progress, message)
            log.info("kb_import_progress", doc_id=doc_id, stage=stage, progress=progress)

        # Step 0: Check Deduplication against COMPLETED documents
        existing = await self.kb_store.get_document_by_hash(conn, content_hash)
        if existing:
            if existing["status"] == "COMPLETED":
                report("COMPLETED", 1.0, f"Document already indexed (matched hash {content_hash[:8]})")
                return KBDocument(
                    id=str(existing["id"]),
                    title=str(existing["title"]),
                    dept=str(existing["dept"]),
                    revision=str(existing["revision"]),
                    contentHash=str(existing["content_hash"]),
                    status=str(existing["status"]),
                    classification=ClassificationLevel(str(existing["classification"])),
                    effectiveDate=str(existing["effective_date"]),
                    supersededBy=existing["superseded_by"] if existing["superseded_by"] else None,
                )
            else:
                # INCOMPLETE document -> purge previous partial data and re-index
                log.info("reindexing_incomplete_document", doc_id=existing["id"])
                await self.kb_store.delete_document(conn, str(existing["id"]))

        # Step 1: Ingest Document
        report("INGESTING", 0.15, "Running layout analysis and OCR extraction")
        try:
            ingest_result = await self.ingest_pipeline.ingest_document(path)
        except Exception as exc:
            report("FAILED", 0.0, f"Ingest failed: {exc}")
            raise

        # Step 2: Chunk Document
        report("CHUNKING", 0.35, "Generating layout-aware chunks with calibrated token boundaries")
        try:
            kb_doc = self.chunker.chunk_document(
                doc_id=doc_id,
                title=title,
                dept=dept,
                classification=classification,
                effective_date=effective_date,
                allowed_roles=roles,
                ingest_result=ingest_result,
                revision=revision,
                content_hash=content_hash,
                superseded_by=None,
            )
            # Mark initial status as INCOMPLETE in case embedding fails
            kb_doc.status = "INCOMPLETE"
            await self.kb_store.insert_document(conn, kb_doc)
        except Exception as exc:
            report("FAILED", 0.0, f"Chunking failed: {exc}")
            raise

        # Step 3: Embed Chunks
        report("EMBEDDING", 0.60, f"Embedding {len(kb_doc.chunks)} chunks via Role.EMBEDDER")
        chunk_texts = [f"{c.heading_path} › {c.body_text}" for c in kb_doc.chunks]
        chunk_ids = [c.id for c in kb_doc.chunks]

        try:
            dim = await self.embedder.get_dimension()
            embeddings = await self.embedder.embed_texts_batched(chunk_texts)
        except Exception as exc:
            report("FAILED", 0.0, f"Embedding failed: {exc}")
            await self.kb_store.mark_document_incomplete(conn, doc_id)
            raise

        # Step 4: Save Embeddings and Finalize
        report("INDEXING", 0.85, "Saving vector embeddings and FTS5 indices")
        try:
            await self.kb_store.save_chunk_embeddings(
                conn,
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                embedding_model=self.embedder.model,
                dimension=dim,
            )
            # Mark document as COMPLETED
            await conn.execute(
                "UPDATE kb_documents SET status = 'COMPLETED' WHERE id = ?",
                (doc_id,),
            )
            if supersedes_doc_id:
                await self.kb_store.mark_document_superseded(conn, supersedes_doc_id, doc_id)

            await conn.commit()
        except Exception as exc:
            report("FAILED", 0.0, f"Indexing failed: {exc}")
            await self.kb_store.mark_document_incomplete(conn, doc_id)
            raise

        report("COMPLETED", 1.0, f"Successfully indexed {len(kb_doc.chunks)} chunks")
        kb_doc.status = "COMPLETED"
        return kb_doc
