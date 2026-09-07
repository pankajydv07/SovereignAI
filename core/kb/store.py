"""Knowledge Base storage layer enforcing indexed kb_chunk_roles join table and dimension provenance."""

import json
import aiosqlite
import structlog

from kb.types import KBDocument
from storage.db import DatabaseManager, current_time_ms

log = structlog.get_logger()


class KnowledgeBaseStore:
    """Storage repository for Knowledge Base documents, chunks, roles, and vector embeddings."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    async def get_document_by_hash(
        self, conn: aiosqlite.Connection, content_hash: str
    ) -> dict[str, str | int | None] | None:
        """Fetch existing document by content hash to support deduplication."""
        if not content_hash:
            return None
        cursor = await conn.execute(
            """
            SELECT id, title, dept, revision, content_hash, status, classification, effective_date, superseded_by, project_id, session_id, scope
            FROM kb_documents WHERE content_hash = ?
            """,
            (content_hash,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_document_by_project_and_hash(
        self, conn: aiosqlite.Connection, project_id: str, content_hash: str
    ) -> dict[str, str | int | None] | None:
        """Fetch existing document by project_id and content_hash for scoped deduplication."""
        if not content_hash:
            return None
        cursor = await conn.execute(
            """
            SELECT id, title, dept, revision, content_hash, status, classification, effective_date, superseded_by, project_id, session_id, scope
            FROM kb_documents WHERE project_id = ? AND content_hash = ?
            """,
            (project_id, content_hash),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_document_by_project_and_title(
        self, conn: aiosqlite.Connection, project_id: str, title: str, exclude_doc_id: str | None = None
    ) -> dict[str, str | int | None] | None:
        """Fetch active document by project_id and title to mark previous revisions as superseded."""
        query = """
            SELECT id, title, dept, revision, content_hash, status, classification, effective_date, superseded_by
            FROM kb_documents
            WHERE project_id = ? AND title = ? AND status = 'COMPLETED' AND superseded_by IS NULL
        """
        params: list[Any] = [project_id, title]
        if exclude_doc_id:
            query += " AND id != ?"
            params.append(exclude_doc_id)
        cursor = await conn.execute(query, tuple(params))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete_document(self, conn: aiosqlite.Connection, doc_id: str) -> None:
        """Purge document and all associated chunks, vectors, roles, and FTS5 entries."""
        # Find all chunk IDs
        cursor = await conn.execute("SELECT id FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        rows = await cursor.fetchall()
        chunk_ids = [r[0] for r in rows]

        for cid in chunk_ids:
            await conn.execute("DELETE FROM kb_vectors WHERE chunk_id = ?", (cid,))
            await conn.execute("DELETE FROM kb_chunk_roles WHERE chunk_id = ?", (cid,))
            await conn.execute("DELETE FROM kb_chunks_fts WHERE chunk_id = ?", (cid,))
            await conn.execute("DELETE FROM kb_chunks WHERE id = ?", (cid,))

        await conn.execute("DELETE FROM kb_documents WHERE id = ?", (doc_id,))
        await conn.commit()
        log.info("kb_document_purged", doc_id=doc_id, chunks_deleted=len(chunk_ids))

    async def mark_document_incomplete(self, conn: aiosqlite.Connection, doc_id: str) -> None:
        """Mark document status as INCOMPLETE when embedding or processing fails."""
        await conn.execute(
            "UPDATE kb_documents SET status = 'INCOMPLETE' WHERE id = ?",
            (doc_id,),
        )
        await conn.commit()
        log.warning("kb_document_marked_incomplete", doc_id=doc_id)

    async def mark_document_superseded(
        self, conn: aiosqlite.Connection, old_doc_id: str, new_doc_id: str
    ) -> None:
        """Update superseded_by pointer on an existing document."""
        await conn.execute(
            "UPDATE kb_documents SET superseded_by = ? WHERE id = ?",
            (new_doc_id, old_doc_id),
        )
        await conn.commit()
        log.info("kb_document_superseded", old_doc_id=old_doc_id, new_doc_id=new_doc_id)

    async def insert_document(self, conn: aiosqlite.Connection, doc: KBDocument) -> None:
        """Insert document, chunks, indexed roles, and FTS5 keywords into SQLite."""
        now = current_time_ms()
        await conn.execute(
            """
            INSERT OR REPLACE INTO kb_documents
            (id, title, dept, classification, effective_date, revision, content_hash, status, superseded_by, project_id, session_id, scope, created_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc.id,
                doc.title,
                doc.dept,
                doc.classification.value,
                doc.effective_date,
                doc.revision,
                doc.content_hash,
                doc.status,
                doc.superseded_by,
                doc.project_id,
                doc.session_id,
                doc.scope,
                now,
            ),
        )

        for chunk in doc.chunks:
            bbox_json = chunk.bbox.model_dump_json()
            await conn.execute(
                """
                INSERT OR REPLACE INTO kb_chunks
                (
                    id, doc_id, chunk_index, heading_path, body_text,
                    token_count, page, bbox_json, created_at_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    chunk.doc_id,
                    chunk.chunk_index,
                    chunk.heading_path,
                    chunk.body_text,
                    chunk.token_count,
                    chunk.page,
                    bbox_json,
                    now,
                ),
            )

            # Insert indexed roles into kb_chunk_roles join table
            roles_to_insert = set(chunk.allowed_roles)
            if not roles_to_insert:
                roles_to_insert.add("*")

            for r in roles_to_insert:
                await conn.execute(
                    "INSERT OR REPLACE INTO kb_chunk_roles (chunk_id, role) VALUES (?, ?)",
                    (chunk.id, r),
                )

            # Insert FTS5 keyword index
            await conn.execute(
                """
                INSERT OR REPLACE INTO kb_chunks_fts (chunk_id, heading_path, body_text)
                VALUES (?, ?, ?)
                """,
                (chunk.id, chunk.heading_path, chunk.body_text),
            )

        await conn.commit()

    async def save_chunk_embeddings(
        self,
        conn: aiosqlite.Connection,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        embedding_model: str = "bge-m3:latest",
        dimension: int = 1024,
    ) -> None:
        """Save vector embeddings with model and dimension provenance into kb_vectors table."""
        for cid, emb in zip(chunk_ids, embeddings, strict=True):
            await conn.execute(
                """
                INSERT OR REPLACE INTO kb_vectors (chunk_id, embedding_json, embedding_model, dimension)
                VALUES (?, ?, ?, ?)
                """,
                (cid, json.dumps(emb), embedding_model, dimension),
            )
        await conn.commit()
