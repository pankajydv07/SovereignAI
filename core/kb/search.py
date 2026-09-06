"""Hybrid Retrieval Engine (FTS5 + Dense Vectors + RRF Fusion)."""

import json
from datetime import datetime
from typing import Any

import aiosqlite
import numpy as np
import structlog

from ingest.types import BoundingBox
from kb.embedder import ChunkEmbedder
from kb.types import Citation, SearchResult

log = structlog.get_logger()

COSINE_SIM_THRESHOLD = 0.65


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two normalized vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class HybridSearchEngine:
    """Hybrid Search Engine combining FTS5 BM25 and dense vector embeddings via RRF Fusion.

    Enforces mandatory user_role parameterization on the single retrieval chokepoint.
    """

    def __init__(self, embedder: ChunkEmbedder | None = None) -> None:
        self.embedder = embedder or ChunkEmbedder()

    async def retrieve_chunks(
        self,
        conn: aiosqlite.Connection,
        user_role: str,
        query: str,
        top_k: int = 5,
        include_superseded: bool = False,
        today_date: str | None = None,
    ) -> list[SearchResult]:
        """Single mandatory retrieval chokepoint with role filtering in SQL."""
        if not user_role or not user_role.strip():
            raise ValueError("user_role is mandatory and cannot be empty")

        if not query or not query.strip():
            return []

        current_date = today_date or datetime.now().strftime("%Y-%m-%d")

        # Step 1: Execute FTS5 BM25 Keyword Search filtered by indexed role table
        fts_query = """
        SELECT c.id, c.doc_id, c.heading_path, c.body_text, c.page, c.bbox_json, d.title
        FROM kb_chunks_fts fts
        JOIN kb_chunks c ON fts.chunk_id = c.id
        JOIN kb_documents d ON c.doc_id = d.id
        WHERE fts.kb_chunks_fts MATCH ?
          AND EXISTS (SELECT 1 FROM kb_chunk_roles r WHERE r.chunk_id = c.id AND r.role IN (?, '*'))
          AND d.effective_date <= ?
        """
        if not include_superseded:
            fts_query += " AND d.superseded_by IS NULL"
        fts_query += " LIMIT 50"

        fts_results: list[dict[str, Any]] = []
        try:
            # Wrap FTS5 search terms in quotes to safely handle hyphens (e.g. C-101, FT-1702)
            terms = [f'"{t.replace('"', "")}"' for t in query.split() if t.strip()]
            clean_query = " ".join(terms)
            async with conn.execute(fts_query, (clean_query, user_role, current_date)) as cursor:
                async for row in cursor:
                    fts_results.append(dict(row))
        except Exception as exc:
            log.warning("fts5_search_warning", error=str(exc), query=query)

        # Step 2: Compute Dense Vector Cosine Similarity Search filtered by role
        query_vec = await self.embedder.embed_single_text(query)

        vec_query = """
        SELECT c.id, c.doc_id, c.heading_path, c.body_text, c.page, c.bbox_json, v.embedding_json
        FROM kb_chunks c
        JOIN kb_documents d ON c.doc_id = d.id
        JOIN kb_vectors v ON c.id = v.chunk_id
        WHERE EXISTS (SELECT 1 FROM kb_chunk_roles r WHERE r.chunk_id = c.id AND r.role IN (?, '*'))
          AND d.effective_date <= ?
        """
        if not include_superseded:
            vec_query += " AND d.superseded_by IS NULL"

        dense_scored: list[tuple[dict[str, Any], float]] = []
        async with conn.execute(vec_query, (user_role, current_date)) as cursor:
            async for row in cursor:
                r_dict = dict(row)
                chunk_vec = json.loads(r_dict["embedding_json"])
                sim = compute_cosine_similarity(query_vec, chunk_vec)
                dense_scored.append((r_dict, sim))

        dense_scored.sort(key=lambda x: x[1], reverse=True)
        dense_results = dense_scored[:50]

        # Step 3: Reciprocal Rank Fusion (RRF)
        # RRF(d) = 1/(60 + r_fts) + 1/(60 + r_dense)
        fts_ranks = {r["id"]: idx + 1 for idx, r in enumerate(fts_results)}
        dense_ranks = {r[0]["id"]: idx + 1 for idx, r in enumerate(dense_results)}

        all_candidate_ids = set(fts_ranks.keys()).union(dense_ranks.keys())
        chunks_map: dict[str, dict[str, Any]] = {}
        for r in fts_results:
            chunks_map[r["id"]] = r
        for r, _ in dense_results:
            chunks_map[r["id"]] = r

        cosine_sim_map = {r[0]["id"]: r[1] for r in dense_results}

        rrf_scores: list[tuple[str, float, float]] = []
        for cid in all_candidate_ids:
            r_fts = fts_ranks.get(cid, 999)
            r_dense = dense_ranks.get(cid, 999)
            score = (1.0 / (60.0 + r_fts)) + (1.0 / (60.0 + r_dense))
            cos_sim = cosine_sim_map.get(cid, 0.0)
            rrf_scores.append((cid, score, cos_sim))

        rrf_scores.sort(key=lambda x: x[1], reverse=True)

        # Step 4: Calibrated Cosine Similarity Thresholding (cos_sim >= 0.65)
        search_results: list[SearchResult] = []
        for cid, rrf_score, cos_sim in rrf_scores[:top_k]:
            if cos_sim < COSINE_SIM_THRESHOLD and rrf_score < 0.02:
                # Candidate fails similarity thresholding
                continue

            cdata = chunks_map[cid]
            bbox_dict = json.loads(cdata["bbox_json"])
            bbox = BoundingBox.model_validate(bbox_dict)

            citation = Citation(
                docId=cdata["doc_id"],
                headingPath=cdata["heading_path"],
                page=cdata["page"],
                bbox=bbox,
                textSnippet=cdata["body_text"][:150],
            )

            search_results.append(
                SearchResult(
                    chunkId=cid,
                    docId=cdata["doc_id"],
                    headingPath=cdata["heading_path"],
                    bodyText=cdata["body_text"],
                    page=cdata["page"],
                    bbox=bbox,
                    rrfScore=rrf_score,
                    cosineSimilarity=cos_sim,
                    citation=citation,
                )
            )

        log.debug(
            "hybrid_retrieval_completed",
            user_role=user_role,
            query=query,
            total_returned=len(search_results),
        )
        return search_results
