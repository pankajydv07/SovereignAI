"""Attachment Indexing Service for SWARAJ.

Executes asynchronous background ingestion for chat attachments:
validate -> dedupe -> ingest/OCR -> chunk -> embed -> store -> notify
"""

import asyncio
from collections.abc import Callable
import hashlib
from pathlib import Path
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field
import structlog

from ingest.pipeline import DocumentIngestPipeline
from ingest.types import DocumentClassification
from kb.chunker import LayoutAwareChunker
from kb.embedder import ChunkEmbedder
from kb.store import KnowledgeBaseStore
from kb.types import ClassificationLevel, KBDocument

log = structlog.get_logger()


class AttachmentIndexRequest(BaseModel):
    """Input request specification for indexing a chat attachment."""

    model_config = ConfigDict(populate_by_name=True)

    project_id: str = Field(alias="projectId")
    session_id: str = Field(alias="sessionId")
    source_path: str = Field(alias="sourcePath")
    original_filename: str = Field(alias="originalFilename")
    sha256: str
    mime_type: str = Field(default="application/pdf", alias="mimeType")
    size_bytes: int = Field(default=0, alias="sizeBytes")
    uploaded_at: str = Field(alias="uploadedAt")
    uploader_id: str = Field(alias="uploaderId")
    classification: ClassificationLevel = ClassificationLevel.CONFIDENTIAL
    source_kind: Literal["chat_attachment"] = Field(default="chat_attachment", alias="sourceKind")
    scope: Literal["session", "project"] = "project"


class AttachmentIndexResult(BaseModel):
    """Execution output summary for an attachment indexing task."""

    model_config = ConfigDict(populate_by_name=True)

    status: Literal["indexed", "already_indexed", "in_progress", "failed", "cancelled"]
    document_id: str | None = Field(default=None, alias="documentId")
    chunk_count: int = Field(default=0, alias="chunkCount")
    page_count: int = Field(default=0, alias="pageCount")
    required_ocr: bool = Field(default=False, alias="requiredOcr")
    low_confidence_field_count: int = Field(default=0, alias="lowConfidenceFieldCount")
    failure_reason: str | None = Field(default=None, alias="failureReason")


class AttachmentIndexService:
    """Asynchronous service for indexing chat attachments into project Knowledge Base."""

    def __init__(
        self,
        kb_store: KnowledgeBaseStore,
        embedder: ChunkEmbedder | None = None,
        ingest_pipeline: DocumentIngestPipeline | None = None,
        chunker: LayoutAwareChunker | None = None,
        send_notification_fn: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.kb_store = kb_store
        self.embedder = embedder or ChunkEmbedder()
        self.ingest_pipeline = ingest_pipeline or DocumentIngestPipeline()
        self.chunker = chunker or LayoutAwareChunker()
        self.send_notification = send_notification_fn

    def _emit(self, event_type: str, session_id: str, payload: dict[str, Any]) -> None:
        """Dispatch protocol notification if callback is registered."""
        if self.send_notification:
            self.send_notification("session/update", {
                "sessionId": session_id,
                "update": {"type": event_type, **payload},
            })

    async def index_attachment(
        self, req: AttachmentIndexRequest
    ) -> AttachmentIndexResult:
        """Process and index a PDF attachment with progress notifications and uploader ACL grant."""
        path = Path(req.source_path)
        if not path.exists():
            res = AttachmentIndexResult(
                status="failed",
                failure_reason=f"Attachment file not found: {req.source_path}",
            )
            self._emit("attachment_index_failed", req.session_id, {
                "documentId": req.sha256[:12],
                "reason": res.failure_reason or "File not found",
                "directReadSucceeded": True,
            })
            return res

        doc_id = f"doc_{req.project_id}_{req.sha256[:12]}"

        # Always grant the uploader explicit retrieval access to their own upload
        allowed_roles = ["*", req.uploader_id] if req.uploader_id else ["*"]

        # Step 0: Scoped Deduplication by (project_id, sha256)
        async with self.kb_store.db_manager.connect() as conn:
            await self.kb_store.db_manager.initialize_schema(conn)
            try:
                existing = await self.kb_store.get_document_by_project_and_hash(
                    conn, req.project_id, req.sha256
                )
                if existing:
                    if existing["status"] == "COMPLETED":
                        log.info("attachment_already_indexed", project_id=req.project_id, sha256=req.sha256[:8])
                        res = AttachmentIndexResult(
                            status="already_indexed",
                            document_id=str(existing["id"]),
                            page_count=int(existing.get("page_count", 1)),
                            chunk_count=int(existing.get("chunk_count", 0)),
                        )
                        self._emit("attachment_index_completed", req.session_id, {
                            "status": "already_indexed",
                            "documentId": str(existing["id"]),
                            "chunkCount": res.chunk_count,
                            "pageCount": res.page_count,
                            "requiredOcr": False,
                            "lowConfidenceFieldCount": 0,
                        })
                        return res
                    else:
                        # Previous attempt was INCOMPLETE -> purge partial data and re-index
                        log.info("reindexing_incomplete_attachment", doc_id=existing["id"])
                        await self.kb_store.delete_document(conn, str(existing["id"]))

                # Step 1: Start Ingestion
                self._emit("attachment_index_started", req.session_id, {
                    "documentId": doc_id,
                    "filename": req.original_filename,
                    "pageCount": 1,
                })

                # Stage: Parsing / OCR
                self._emit("attachment_index_progress", req.session_id, {
                    "documentId": doc_id, "stage": "parsing", "current": 1, "total": 4,
                })
                ingest_result = await self.ingest_pipeline.ingest_document(path)
                num_pages = len(ingest_result.pages) or 1
                has_ocr = any(
                    getattr(p, "classification", None) == DocumentClassification.SCANNED
                    or getattr(p, "page_type", None) == "scanned"
                    for p in ingest_result.pages
                )
                if has_ocr:
                    self._emit("attachment_index_progress", req.session_id, {
                        "documentId": doc_id, "stage": "ocr", "current": 2, "total": 4,
                    })

                # Stage: Chunking
                self._emit("attachment_index_progress", req.session_id, {
                    "documentId": doc_id, "stage": "chunking", "current": 3, "total": 4,
                })
                kb_doc = self.chunker.chunk_document(
                    doc_id=doc_id,
                    title=req.original_filename,
                    dept=req.project_id,
                    classification=req.classification,
                    effective_date=req.uploaded_at.split("T")[0] if "T" in req.uploaded_at else "2026-01-01",
                    allowed_roles=allowed_roles,
                    ingest_result=ingest_result,
                    content_hash=req.sha256,
                    project_id=req.project_id,
                    session_id=req.session_id,
                    scope=req.scope,
                )
                kb_doc.status = "INCOMPLETE"
                await self.kb_store.insert_document(conn, kb_doc)

                # Check if there is a previous revision of this document in the project to mark superseded
                prev_rev = await self.kb_store.get_document_by_project_and_title(
                    conn, req.project_id, req.original_filename, exclude_doc_id=doc_id
                )
                if prev_rev and prev_rev.get("id"):
                    await self.kb_store.mark_document_superseded(conn, str(prev_rev["id"]), doc_id)

                # Stage: Embedding
                self._emit("attachment_index_progress", req.session_id, {
                    "documentId": doc_id, "stage": "embedding", "current": 4, "total": 4,
                })
                dim = await self.embedder.get_dimension()
                chunk_texts = [f"{c.heading_path} › {c.body_text}" for c in kb_doc.chunks]
                chunk_ids = [c.id for c in kb_doc.chunks]

                embeddings = await self.embedder.embed_texts_batched(chunk_texts)

                # Stage: Indexing / Finalize
                await self.kb_store.save_chunk_embeddings(
                    conn,
                    chunk_ids=chunk_ids,
                    embeddings=embeddings,
                    embedding_model=self.embedder.model,
                    dimension=dim,
                )
                await conn.execute("UPDATE kb_documents SET status = 'COMPLETED' WHERE id = ?", (doc_id,))
                await conn.commit()

                res = AttachmentIndexResult(
                    status="indexed",
                    document_id=doc_id,
                    chunk_count=len(kb_doc.chunks),
                    page_count=num_pages,
                    required_ocr=has_ocr,
                    low_confidence_field_count=0,
                )
                self._emit("attachment_index_completed", req.session_id, {
                    "status": "indexed",
                    "documentId": doc_id,
                    "chunkCount": res.chunk_count,
                    "pageCount": res.page_count,
                    "requiredOcr": has_ocr,
                    "lowConfidenceFieldCount": 0,
                })
                return res

            except asyncio.CancelledError:
                log.warning("attachment_indexing_cancelled", doc_id=doc_id)
                try:
                    await self.kb_store.delete_document(conn, doc_id)
                except Exception as e:
                    log.error("failed_to_cleanup_cancelled_document", error=str(e))
                self._emit("attachment_index_failed", req.session_id, {
                    "documentId": doc_id,
                    "reason": "Attachment indexing cancelled",
                    "directReadSucceeded": True,
                })
                raise
            except Exception as exc:
                log.error("attachment_indexing_failed", doc_id=doc_id, error=str(exc))
                try:
                    await self.kb_store.mark_document_incomplete(conn, doc_id)
                except Exception as mark_err:
                    log.warning("failed_to_mark_document_incomplete", doc_id=doc_id, error=str(mark_err))
                self._emit("attachment_index_failed", req.session_id, {
                    "documentId": doc_id,
                    "reason": str(exc),
                    "directReadSucceeded": True,
                })
                return AttachmentIndexResult(
                    status="failed",
                    document_id=doc_id,
                    failure_reason=str(exc),
                )
