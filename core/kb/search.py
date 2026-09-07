"""Hybrid Retrieval Engine (FTS5 + Dense Vectors + RRF Fusion + Calibrated Dual-Gating)."""

import json
from datetime import datetime
from typing import Any

import aiosqlite
import numpy as np
import structlog

from context.tokens import count_tokens
from ingest.types import BoundingBox
from kb.embedder import ChunkEmbedder
from kb.types import Citation, EmbeddingDimensionMismatchError, SearchResult

log = structlog.get_logger()

# Empirically derived threshold on bge-m3 cosine similarity:
# Known relevant queries score in 0.62-0.92; out-of-domain/unrelated noise scores <= 0.52.
COSINE_RELEVANCE_FLOOR = 0.58
BM25_HIGH_CONFIDENCE_RANK = 3


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

    Enforces mandatory user_role parameterization, dimension verification,
    and calibrated dual-gating (dense cosine + BM25 keyword match).
    """

    def __init__(self, embedder: ChunkEmbedder | None = None) -> None:
        self.embedder = embedder or ChunkEmbedder()

    async def retrieve_chunks(
        self,
        conn: aiosqlite.Connection,
        user_role: str,
        query: str,
        top_k: int = 5,
        num_ctx: int = 8192,
        include_superseded: bool = False,
        today_date: str | None = None,
        query_vector: list[float] | None = None,
    ) -> tuple[list[SearchResult], bool, int]:
        """Mandatory retrieval chokepoint with role filtering, dual-gating, and context token ceiling.

        Returns: (results, is_truncated, total_matching_count)
        """
        if not user_role or not user_role.strip():
            raise ValueError("user_role is mandatory and cannot be empty")

        if not query or not query.strip():
            return [], False, 0

        current_date = today_date or datetime.now().strftime("%Y-%m-%d")
        expected_dim = await self.embedder.get_dimension()

        # Step 1: Execute FTS5 BM25 Keyword Search filtered by indexed role table
        fts_query = """
        SELECT c.id, c.doc_id, c.heading_path, c.body_text, c.token_count, c.page, c.bbox_json, d.title
        FROM kb_chunks_fts fts
        JOIN kb_chunks c ON fts.chunk_id = c.id
        JOIN kb_documents d ON c.doc_id = d.id
        WHERE fts.kb_chunks_fts MATCH ?
          AND d.status = 'COMPLETED'
          AND EXISTS (SELECT 1 FROM kb_chunk_roles r WHERE r.chunk_id = c.id AND r.role IN (?, '*'))
          AND d.effective_date <= ?
        """
        if not include_superseded:
            fts_query += " AND d.superseded_by IS NULL"
        fts_query += " LIMIT 50"

        fts_results: list[dict[str, Any]] = []
        try:
            terms = [f'"{t.replace('"', "")}"' for t in query.split() if t.strip()]
            clean_query = " ".join(terms)
            async with conn.execute(fts_query, (clean_query, user_role, current_date)) as cursor:
                async for row in cursor:
                    fts_results.append(dict(row))
        except Exception as exc:
            log.warning("fts5_search_warning", error=str(exc), query=query)

        # Step 2: Compute Dense Vector Cosine Similarity Search filtered by role
        if query_vector is not None and len(query_vector) > 0:
            query_vec = query_vector
        else:
            query_vec = await self.embedder.embed_single_text(query)
        if len(query_vec) != expected_dim:
            raise EmbeddingDimensionMismatchError(expected_dim, len(query_vec), self.embedder.model)

        vec_query = """
        SELECT v.chunk_id, v.embedding_json
        FROM kb_vectors v
        JOIN kb_chunks c ON v.chunk_id = c.id
        JOIN kb_documents d ON c.doc_id = d.id
        WHERE d.status = 'COMPLETED'
          AND EXISTS (SELECT 1 FROM kb_chunk_roles r WHERE r.chunk_id = c.id AND r.role IN (?, '*'))
          AND d.effective_date <= ?
        """
        if not include_superseded:
            vec_query += " AND d.superseded_by IS NULL"

        q_arr = np.array(query_vec, dtype=np.float32)
        q_norm = float(np.linalg.norm(q_arr))
        if q_norm > 0:
            q_arr /= q_norm

        dense_scored: list[tuple[str, float]] = []
        cursor = await conn.execute(vec_query, (user_role, current_date))
        rows = await cursor.fetchall()
        for row in rows:
            cid = str(row[0])
            chunk_vec = json.loads(row[1])
            stored_dim = len(chunk_vec)
            if stored_dim != expected_dim:
                raise EmbeddingDimensionMismatchError(expected_dim, stored_dim, self.embedder.model)

            c_arr = np.array(chunk_vec, dtype=np.float32)
            c_norm = float(np.linalg.norm(c_arr))
            sim = float(np.dot(q_arr, c_arr) / c_norm) if c_norm > 0 else 0.0
            dense_scored.append((cid, sim))

        dense_scored.sort(key=lambda x: x[1], reverse=True)
        dense_results = dense_scored[:50]

        # Step 3: Reciprocal Rank Fusion (RRF)
        fts_ranks = {r["id"]: idx + 1 for idx, r in enumerate(fts_results)}
        dense_ranks = {cid: idx + 1 for idx, (cid, _) in enumerate(dense_results)}

        all_candidate_ids = list(set(fts_ranks.keys()).union(dense_ranks.keys()))
        if not all_candidate_ids:
            return [], False, 0

        # Hydrate chunk details for candidate IDs only
        placeholders = ",".join("?" for _ in all_candidate_ids)
        hydrate_query = f"""
        SELECT c.id, c.doc_id, c.heading_path, c.body_text, c.token_count, c.page, c.bbox_json
        FROM kb_chunks c
        WHERE c.id IN ({placeholders})
        """
        chunks_map: dict[str, dict[str, Any]] = {}
        async with conn.execute(hydrate_query, all_candidate_ids) as h_cursor:
            async for h_row in h_cursor:
                chunks_map[h_row["id"]] = dict(h_row)

        cosine_sim_map = {cid: sim for cid, sim in dense_results}

        rrf_scores: list[tuple[str, float, float, int | None]] = []
        for cid in all_candidate_ids:
            r_fts = fts_ranks.get(cid, 999)
            r_dense = dense_ranks.get(cid, 999)
            score = (1.0 / (60.0 + r_fts)) + (1.0 / (60.0 + r_dense))
            cos_sim = cosine_sim_map.get(cid, 0.0)
            bm25_rank = fts_ranks.get(cid, None)
            rrf_scores.append((cid, score, cos_sim, bm25_rank))

        rrf_scores.sort(key=lambda x: x[1], reverse=True)

        # Step 4: Dual-Condition Rejection Gate
        # Reject only if max cosine similarity is below floor AND there is no strong BM25 rank <= 3
        max_cosine = max((s[2] for s in rrf_scores), default=0.0)
        best_bm25_rank = min((s[3] for s in rrf_scores if s[3] is not None), default=999)

        if max_cosine < COSINE_RELEVANCE_FLOOR and best_bm25_rank > BM25_HIGH_CONFIDENCE_RANK:
            log.info(
                "kb_relevance_threshold_rejected",
                query=query,
                max_cosine=max_cosine,
                best_bm25_rank=best_bm25_rank,
            )
            return [], False, 0

        # Step 5: Dynamic Context-Scaled Token Ceiling
        max_retrieval_tokens = min(1500, max(400, int(0.15 * num_ctx)))
        accumulated_tokens = 0
        search_results: list[SearchResult] = []
        is_truncated = False
        total_matching = len(rrf_scores)

        for cid, rrf_score, cos_sim, bm25_rank in rrf_scores:
            if len(search_results) >= top_k:
                is_truncated = True
                break

            # Discard weak tail candidates
            if cos_sim < (COSINE_RELEVANCE_FLOOR - 0.10) and (bm25_rank is None or bm25_rank > 5):
                continue

            cdata = chunks_map[cid]
            chunk_tokens = int(cdata.get("token_count", 0))
            if chunk_tokens <= 0:
                chunk_tokens = count_tokens(cdata["body_text"])

            if accumulated_tokens + chunk_tokens > max_retrieval_tokens and search_results:
                is_truncated = True
                break

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
                    bm25Rank=bm25_rank,
                    citation=citation,
                )
            )
            accumulated_tokens += chunk_tokens

        return search_results, is_truncated, total_matching
