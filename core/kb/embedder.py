"""Batched chunk embedding engine resolving via Role.EMBEDDER.

Fails loudly if Ollama embedding endpoint or model is unavailable.
Never generates synthetic/fake vectors.
"""

from typing import Any
import httpx
import structlog

log = structlog.get_logger()

OLLAMA_URL = "http://127.0.0.1:11434"


class EmbeddingModelUnavailable(RuntimeError):
    """Raised when Ollama embedding model or endpoint is unavailable or returns non-200."""

    def __init__(self, model: str, endpoint: str, details: str = "") -> None:
        msg = f"Embedding model '{model}' unavailable at '{endpoint}'. {details}".strip()
        super().__init__(msg)
        self.model = model
        self.endpoint = endpoint
        self.details = details


class ChunkEmbedder:
    """Async batched chunk embedder resolving through Role.EMBEDDER."""

    def __init__(
        self,
        ollama_url: str = OLLAMA_URL,
        model: str | None = None,
        model_registry: Any | None = None,
    ) -> None:
        self.ollama_url = ollama_url
        if model:
            self._model = model
        else:
            if model_registry is None:
                from models.registry import ModelRegistry

                reg = ModelRegistry()
            else:
                reg = model_registry

            self._model = reg.resolve("embedder")

        self._dimension: int | None = None

    @property
    def model(self) -> str:
        """Return the resolved embedding model tag."""
        return self._model

    async def get_dimension(self) -> int:
        """Dynamically probe and cache vector dimension by embedding a short probe string."""
        if self._dimension is not None:
            return self._dimension

        probe_vec = await self.embed_single_text("probe")
        self._dimension = len(probe_vec)
        log.info("embedding_dimension_probed", model=self._model, dimension=self._dimension)
        return self._dimension

    async def embed_texts_batched(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[float]]:
        """Embed text strings in batches using Ollama POST /api/embed.

        Fails loudly if the endpoint or model is unavailable.
        """
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
                            "model": self._model,
                            "input": batch,
                            "keep_alive": "5m",
                        },
                    )
                except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                    log.error(
                        "ollama_embed_connection_failed",
                        model=self._model,
                        endpoint=self.ollama_url,
                        error=str(exc),
                    )
                    raise EmbeddingModelUnavailable(
                        model=self._model,
                        endpoint=f"{self.ollama_url}/api/embed",
                        details=f"Network error: {exc}",
                    ) from exc

                if res.status_code != 200:
                    err_msg = res.text
                    log.error(
                        "ollama_embed_failed",
                        status_code=res.status_code,
                        model=self._model,
                        response=err_msg,
                    )
                    raise EmbeddingModelUnavailable(
                        model=self._model,
                        endpoint=f"{self.ollama_url}/api/embed",
                        details=f"HTTP {res.status_code}: {err_msg}",
                    )

                data = res.json()
                batch_embeds = data.get("embeddings", [])
                if len(batch_embeds) != len(batch):
                    raise EmbeddingModelUnavailable(
                        model=self._model,
                        endpoint=f"{self.ollama_url}/api/embed",
                        details=f"Expected {len(batch)} embeddings, received {len(batch_embeds)}",
                    )
                embeddings.extend(batch_embeds)

        return embeddings

    async def embed_single_text(self, text: str) -> list[float]:
        """Embed a single query text."""
        res = await self.embed_texts_batched([text], batch_size=1)
        if not res:
            raise EmbeddingModelUnavailable(
                model=self._model,
                endpoint=f"{self.ollama_url}/api/embed",
                details="Empty embedding response returned",
            )
        return res[0]
