"""Knowledge Base storage layer enforcing indexed kb_chunk_roles join table."""

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

    async def insert_document(self, conn: aiosqlite.Connection, doc: KBDocument) -> None:
        """Insert document, chunks, indexed roles, FTS5 keywords, and embeddings into SQLite."""
        now = current_time_ms()
        await conn.execute(
            """
            INSERT OR REPLACE INTO kb_documents
            (id, title, dept, classification, effective_date, superseded_by, created_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc.id,
                doc.title,
                doc.dept,
                doc.classification.value,
                doc.effective_date,
                doc.superseded_by,
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
        self, conn: aiosqlite.Connection, chunk_ids: list[str], embeddings: list[list[float]]
    ) -> None:
        """Save vector embeddings into kb_vectors table."""
        for cid, emb in zip(chunk_ids, embeddings, strict=True):
            await conn.execute(
                "INSERT OR REPLACE INTO kb_vectors (chunk_id, embedding_json) VALUES (?, ?)",
                (cid, json.dumps(emb)),
            )
        await conn.commit()
