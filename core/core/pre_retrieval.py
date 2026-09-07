"""Task-gated conditional pre-retrieval for chat execution."""

from typing import Any
import structlog

from kb.embedder import ChunkEmbedder
from kb.search import HybridSearchEngine

log = structlog.get_logger()

RETRIEVAL_TASK_CLASSES = {"kb_qa", "official_drafting", "doc_summarise"}


async def maybe_execute_preretrieval(
    task_class: str,
    user_prompt: str,
    user_role: str,
    num_ctx: int,
    model_registry: Any,
    session_store: Any,
    session_id: str,
    messages: list[dict[str, Any]],
    send_notification_fn: Any,
    query_vector: list[float] | None = None,
    force_retrieval: bool = False,
) -> None:
    """Execute pre-retrieval if task_class is in RETRIEVAL_TASK_CLASSES or force_retrieval is True."""
    if (task_class not in RETRIEVAL_TASK_CLASSES and not force_retrieval) or not user_prompt:
        return

    search_engine = HybridSearchEngine(
        embedder=ChunkEmbedder(model_registry=model_registry)
    )

    try:
        async with session_store._get_connection() as conn:
            results, is_truncated, total_matches = await search_engine.retrieve_chunks(
                conn=conn,
                user_role=user_role,
                query=user_prompt,
                top_k=5,
                num_ctx=num_ctx,
                query_vector=query_vector,
            )
            if not results:
                return

            kb_lines = [f"## Retrieved Knowledge Base Context (Role: {user_role}):"]
            retrieved_sources = []
            for r in results:
                kb_lines.append(f"[{r.doc_id} › {r.heading_path} (p. {r.page})]\n{r.body_text}")
                retrieved_sources.append({
                    "chunkId": r.chunk_id,
                    "docId": r.doc_id,
                    "headingPath": r.heading_path,
                    "page": r.page,
                    "bbox": r.bbox.model_dump(),
                    "textSnippet": r.body_text[:150],
                    "cosineSimilarity": r.cosine_similarity,
                })

            kb_context_str = "\n\n".join(kb_lines)
            if messages and messages[-1].get("role") == "user":
                orig_c = messages[-1].get("content", "")
                messages[-1]["content"] = f"{kb_context_str}\n\n---\nUser Query: {orig_c}"
            else:
                messages.append({"role": "user", "content": f"{kb_context_str}\n\n---\nUser Query: {user_prompt}"})

            send_notification_fn("session/update", {
                "sessionId": session_id,
                "update": {
                    "type": "sources",
                    "sources": retrieved_sources,
                    "isTruncated": is_truncated,
                    "totalMatches": total_matches,
                    "showingCount": len(results),
                },
            })
    except Exception as e:
        log.warning("preretrieval_failed", error=str(e), task_class=task_class)
