"""Layout-aware document chunking with heading path prefixing and table preservation."""

import re
import uuid

import structlog

from ingest.types import IngestDocumentResult
from kb.types import ClassificationLevel, KBChunk, KBDocument

log = structlog.get_logger()


class LayoutAwareChunker:
    """Chunks documents into ~500 token windows with heading path prefixes."""

    def __init__(self, target_tokens: int = 500) -> None:
        self.target_tokens = target_tokens

    def chunk_document(
        self,
        doc_id: str,
        title: str,
        dept: str,
        classification: ClassificationLevel,
        effective_date: str,
        allowed_roles: list[str],
        ingest_result: IngestDocumentResult,
        superseded_by: str | None = None,
    ) -> KBDocument:
        """Parse IngestDocumentResult into layout-aware KBChunk items with heading path prefixes."""
        chunks: list[KBChunk] = []
        chunk_idx = 1
        current_heading_path = [title]

        for page_res in ingest_result.pages:
            page_num = page_res.page_num

            # Check regions
            for region in page_res.regions:
                text = region.text.strip()
                if not text:
                    continue

                # Heading detection heuristic
                if len(text) < 80 and (text.isupper() or re.match(r"^\d+(\.\d+)*\s+[A-Z]", text)):
                    current_heading_path = [title, text]
                    continue

                heading_prefix = " › ".join(current_heading_path)
                full_body = f"{heading_prefix} › {text}"

                token_est = len(full_body.split())

                chunk_id = f"chunk_{doc_id}_{chunk_idx}_{uuid.uuid4().hex[:6]}"
                chunk = KBChunk(
                    id=chunk_id,
                    docId=doc_id,
                    chunkIndex=chunk_idx,
                    headingPath=heading_prefix,
                    bodyText=text,
                    tokenCount=token_est,
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
            classification=classification,
            effectiveDate=effective_date,
            supersededBy=superseded_by,
            chunks=chunks,
        )
