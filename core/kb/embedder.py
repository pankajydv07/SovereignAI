"""Batched chunk embedding engine using Ollama local embedder role (bge-m3).

Pins embedder model resident with keep_alive: -1 to eliminate query-time cold load latency.
"""

import httpx
import numpy as np
import structlog

log = structlog.get_logger()

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_EMBED_MODEL = "bge-m3"
VECTOR_DIM = 1024


def generate_synthetic_embedding(text: str, dim: int = VECTOR_DIM) -> list[float]:
    """Deterministic normalized vector embedding for offline testing."""
    vec = np.zeros(dim, dtype=np.float32)
    for i, word in enumerate(text.lower().split()):
        val = sum(ord(c) for c in word)
        idx = (val + i * 31) % dim
        vec[idx] += 1.0 + (val % 10) * 0.1

    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec.tolist()


class ChunkEmbedder:
    """Async batched chunk embedder for local Ollama bge-m3 model."""

    def __init__(self, ollama_url: str = OLLAMA_URL, model: str = DEFAULT_EMBED_MODEL) -> None:
        self.ollama_url = ollama_url
        self.model = model

    async def embed_texts_batched(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[float]]:
        """Embed text strings in batches using Ollama POST /api/embed with keep_alive: -1."""
        if not texts:
            return []

        embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                try:
                    res = await client.post(
                        f"{self.ollama_url}/api/embed",
                        json={
                            "model": self.model,
                            "input": batch,
                            "keep_alive": -1,  # Pin embedder resident in VRAM/RAM
                        },
                    )
                    if res.status_code == 200:
                        data = res.json()
                        batch_embeds = data.get("embeddings", [])
                        embeddings.extend(batch_embeds)
                    else:
                        log.warning(
                            "ollama_embed_non_200_fallback",
                            status_code=res.status_code,
                            batch_size=len(batch),
                        )
                        for t in batch:
                            embeddings.append(generate_synthetic_embedding(t))

                except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                    log.debug("ollama_embed_offline_synthetic_fallback", error=str(exc))
                    for t in batch:
                        embeddings.append(generate_synthetic_embedding(t))

        return embeddings

    async def embed_single_text(self, text: str) -> list[float]:
        """Embed a single query text."""
        res = await self.embed_texts_batched([text], batch_size=1)
        return res[0] if res else generate_synthetic_embedding(text)
