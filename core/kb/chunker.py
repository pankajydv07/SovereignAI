"""Layout-aware document chunking with heading path prefixing and calibrated token limits."""

import re
import uuid
import structlog

from context.tokens import count_tokens
from ingest.types import IngestDocumentResult
from kb.types import ClassificationLevel, KBChunk, KBDocument

log = structlog.get_logger()


class LayoutAwareChunker:
    """Chunks documents into ~500 token windows with heading path prefixes."""

    def __init__(self, target_tokens: int = 500, overlap_tokens: int = 50) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def _split_long_text(self, text: str, heading_prefix: str) -> list[str]:
        """Split oversized text into sub-chunks strictly respecting target token limits."""
        heading_tokens = count_tokens(heading_prefix)
        available_body_tokens = max(100, self.target_tokens - heading_tokens)

        # Split on paragraph boundaries first
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        sub_chunks: list[str] = []
        current_chunk_parts: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)
            if para_tokens > available_body_tokens:
                # If a single paragraph is longer than limit, split by sentences or words
                sentences = re.split(r"(?<=[.!?])\s+", para)
                for sent in sentences:
                    sent_tokens = count_tokens(sent)
                    if current_tokens + sent_tokens > available_body_tokens and current_chunk_parts:
                        sub_chunks.append(" ".join(current_chunk_parts))
                        current_chunk_parts = []
                        current_tokens = 0

                    if sent_tokens > available_body_tokens:
                        # Split by words if sentence is huge
                        words = sent.split()
                        w_buf: list[str] = []
                        w_tokens = 0
                        for w in words:
                            wt = count_tokens(w)
                            if w_tokens + wt > available_body_tokens and w_buf:
                                sub_chunks.append(" ".join(w_buf))
                                w_buf = []
                                w_tokens = 0
                            w_buf.append(w)
                            w_tokens += wt
                        if w_buf:
                            current_chunk_parts.append(" ".join(w_buf))
                            current_tokens += w_tokens
                    else:
                        current_chunk_parts.append(sent)
                        current_tokens += sent_tokens
            else:
                if current_tokens + para_tokens > available_body_tokens and current_chunk_parts:
                    sub_chunks.append("\n\n".join(current_chunk_parts))
                    current_chunk_parts = []
                    current_tokens = 0
                current_chunk_parts.append(para)
                current_tokens += para_tokens

        if current_chunk_parts:
            sub_chunks.append("\n\n".join(current_chunk_parts))

        return sub_chunks if sub_chunks else [text]

    def chunk_document(
        self,
        doc_id: str,
        title: str,
        dept: str,
        classification: ClassificationLevel,
        effective_date: str,
        allowed_roles: list[str],
        ingest_result: IngestDocumentResult,
        revision: str = "rev.01",
        content_hash: str = "",
        superseded_by: str | None = None,
    ) -> KBDocument:
        """Parse IngestDocumentResult into layout-aware KBChunk items with heading path prefixes."""
        chunks: list[KBChunk] = []
        chunk_idx = 1
        current_heading_path = [title]

        for page_res in ingest_result.pages:
            page_num = page_res.page_num

            for region in page_res.regions:
                text = region.text.strip()
                if not text:
                    continue

                # Heading detection heuristic
                if len(text) < 80 and (text.isupper() or re.match(r"^\d+(\.\d+)*\s+[A-Z]", text)):
                    current_heading_path = [title, text]
                    continue

                heading_prefix = " › ".join(current_heading_path)
                total_est = count_tokens(f"{heading_prefix} › {text}")

                if total_est > self.target_tokens:
                    # Split oversized region
                    sub_texts = self._split_long_text(text, heading_prefix)
                else:
                    sub_texts = [text]

                for sub_text in sub_texts:
                    token_count = count_tokens(f"{heading_prefix} › {sub_text}")
                    chunk_id = f"chunk_{doc_id}_{chunk_idx}_{uuid.uuid4().hex[:6]}"
                    chunk = KBChunk(
                        id=chunk_id,
                        docId=doc_id,
                        chunkIndex=chunk_idx,
                        headingPath=heading_prefix,
                        bodyText=sub_text,
                        tokenCount=token_count,
                        page=page_num,
                        bbox=region.bbox,
                        allowedRoles=allowed_roles,
                        dept=dept,
                        classification=classification,
                        effectiveDate=effective_date,
                        supersededBy=superseded_by,
                    )
                    chunks.append(chunk)
                    chunk_idx += 1

        log.debug("document_chunked", doc_id=doc_id, total_chunks=len(chunks))
        return KBDocument(
            id=doc_id,
            title=title,
            dept=dept,
            revision=revision,
            contentHash=content_hash,
            classification=classification,
            effectiveDate=effective_date,
            supersededBy=superseded_by,
            chunks=chunks,
        )
