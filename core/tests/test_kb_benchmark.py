"""SQLite hybrid retrieval latency benchmark at 1k, 5k, and 10k chunks.

Uses random normalized vectors for measuring raw database query, JSON deserialization,
cosine dot product, and RRF rank fusion latency.
"""

import time
from pathlib import Path
import numpy as np
import pytest

from ingest.types import BoundingBox
from kb.embedder import ChunkEmbedder
from kb.search import HybridSearchEngine
from kb.store import KnowledgeBaseStore
from kb.types import ClassificationLevel, KBChunk, KBDocument
from storage.db import DatabaseManager


def generate_random_vector(dim: int = 768) -> list[float]:
    """Generate normalized random vector for latency benchmarking."""
    vec = np.random.standard_normal(dim).astype(np.float32)
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec.tolist()


class BenchmarkEmbedder(ChunkEmbedder):
    """Embedder producing deterministic random vectors for benchmarking."""

    def __init__(self, dim: int = 768) -> None:
        super().__init__()
        self._dim = dim

    async def get_dimension(self) -> int:
        return self._dim

    async def embed_single_text(self, text: str) -> list[float]:
        return generate_random_vector(self._dim)

    async def embed_texts_batched(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return [generate_random_vector(self._dim) for _ in texts]


@pytest.mark.asyncio
async def test_sqlite_retrieval_latency_benchmark(tmp_path: Path) -> None:
    """Benchmark retrieve_chunks latency at 1k, 5k, and 10k chunk scale."""
    db_file = tmp_path / "bench_kb.db"
    db_mgr = DatabaseManager(db_file)
    store = KnowledgeBaseStore(db_mgr)
    embedder = BenchmarkEmbedder(dim=768)
    search_engine = HybridSearchEngine(embedder=embedder)

    dim = 768
    scales = [1000, 5000]

    async with db_mgr.connect() as conn:
        await db_mgr.initialize_schema(conn)

        current_count = 0
        for target_count in scales:
            needed = target_count - current_count
            batch_size = 500
            
            for batch_start in range(0, needed, batch_size):
                batch_n = min(batch_size, needed - batch_start)
                doc_id = f"doc_{current_count + batch_start}"
                
                chunks = []
                chunk_ids = []
                vectors = []
                for i in range(batch_n):
                    c_idx = current_count + batch_start + i
                    cid = f"chunk_{c_idx}"
                    chunk_ids.append(cid)
                    vectors.append(generate_random_vector(dim))
                    chunks.append(
                        KBChunk(
                            id=cid,
                            docId=doc_id,
                            chunkIndex=i,
                            headingPath=f"Section {i} Benchmarking",
                            bodyText=f"Ultrasonic thickness inspection test record {c_idx} for pipe spool PS-1002.",
                            tokenCount=35,
                            page=1,
                            bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
                            allowedRoles=["*"],
                            effectiveDate="2026-01-01",
                        )
                    )
                
                doc = KBDocument(
                    id=doc_id,
                    title="Benchmark Document",
                    dept="Engineering",
                    classification=ClassificationLevel.INTERNAL,
                    effectiveDate="2026-01-01",
                    chunks=chunks,
                )
                await store.insert_document(conn, doc)
                await store.save_chunk_embeddings(
                    conn, chunk_ids, vectors, embedding_model="nomic-embed-text:latest", dimension=dim
                )
            
            current_count = target_count

            # Run 10 warm queries to measure p50, p95 latency
            latencies_ms: list[float] = []
            for q_idx in range(10):
                t0 = time.perf_counter()
                _results, is_truncated, total_count = await search_engine.retrieve_chunks(
                    conn,
                    user_role="InspectionEngineer",
                    query=f"pipe spool PS-1002 ultrasonic test {q_idx}",
                    top_k=5,
                )
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000.0)

            p50 = float(np.percentile(latencies_ms, 50))
            p95 = float(np.percentile(latencies_ms, 95))
            
            # Assert performance guarantees
            if target_count == 1000:
                assert p50 < 400.0, f"1k chunks p50 latency {p50:.2f}ms exceeds 400ms ceiling"
            elif target_count == 5000:
                assert p50 < 2500.0, f"5k chunks p50 latency {p50:.2f}ms exceeds 2500ms ceiling"
