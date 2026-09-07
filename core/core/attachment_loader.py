import base64
from pathlib import Path
from typing import Any

from context.tokens import count_tokens
from tools.document_reader import convert_document_to_markdown

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def extract_attachment_features(attachments: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Determine if attachments contain images and extract MIME types."""
    has_image = any(
        isinstance(a, dict) and (
            a.get("mime_type", "").startswith("image/")
            or Path(a.get("path") or a.get("name") or a.get("filename") or "").suffix.lower() in IMAGE_EXTENSIONS
        )
        for a in attachments
    )
    mimes = [
        a.get("mime_type") or f"image/{Path(a.get('path', '')).suffix.lower().lstrip('.')}"
        for a in attachments
        if isinstance(a, dict) and (
            a.get("mime_type", "").startswith("image/")
            or Path(a.get("path") or a.get("name") or a.get("filename") or "").suffix.lower() in IMAGE_EXTENSIONS
        )
    ]
    return has_image, mimes


def _read_pdf_with_budget(path: Path, max_tokens: int) -> tuple[str, int, int]:
    """Read PDF page-by-page within token budget and return (markdown, included_pages, total_pages)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        total_pages = len(reader.pages)
        if total_pages == 0:
            return "*(Empty PDF)*", 0, 0

        pages_md: list[str] = []
        accumulated_tokens = 0
        included_pages = 0

        for idx, page in enumerate(reader.pages, 1):
            raw = page.extract_text() or ""
            clean = raw.encode("utf-8", errors="replace").decode("utf-8", errors="replace").strip()
            page_text = f"## Page {idx}\n{clean}\n"
            p_tokens = count_tokens(page_text)
            if idx > 1 and accumulated_tokens + p_tokens > max_tokens:
                break
            pages_md.append(page_text)
            accumulated_tokens += p_tokens
            included_pages = idx

        full_md = "\n".join(pages_md)
        return full_md, included_pages, total_pages
    except Exception as exc:
        return f"*(Failed to parse PDF: {exc})*", 0, 0


def process_chat_attachments(
    attachments: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    user_prompt: str,
    max_context_tokens: int = 4000,
) -> None:
    """Process incoming attachments into message context within the dynamic token budget."""
    if not attachments:
        return

    attachment_contexts: list[str] = []
    attached_images: list[str] = []
    budget_per_doc = max(1000, max_context_tokens // max(1, len(attachments)))

    for att in attachments:
        if not isinstance(att, dict):
            continue
        att_name = att.get("name") or att.get("filename") or "Attachment"
        att_path = att.get("path")
        att_content = att.get("content")
        if att_path:
            p = Path(att_path)
            if p.exists() and p.is_file():
                suf = p.suffix.lower()
                if suf in IMAGE_EXTENSIONS:
                    try:
                        b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
                        attached_images.append(b64)
                        attachment_contexts.append(f"### Attached Image: {att_name} ({p.name})")
                    except Exception as e:
                        attachment_contexts.append(f"### Attached Image: {att_name} (Failed to load: {e})")
                elif suf == ".pdf":
                    doc_md, inc_pages, tot_pages = _read_pdf_with_budget(p, budget_per_doc)
                    if tot_pages > inc_pages and inc_pages > 0:
                        doc_md += f"\n\n*(pages 1–{inc_pages} of {tot_pages} included; remaining pages searchable via the knowledge base)*"
                    attachment_contexts.append(f"### Document: {att_name} ({p.name})\n\n{doc_md}")
                else:
                    try:
                        doc_md = convert_document_to_markdown(p)
                        clean_md = doc_md.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                        if count_tokens(clean_md) > budget_per_doc:
                            # Truncate to budget
                            lines = clean_md.splitlines(keepends=True)
                            buf: list[str] = []
                            cur_t = 0
                            for line in lines:
                                lt = count_tokens(line)
                                if cur_t + lt > budget_per_doc and buf:
                                    break
                                buf.append(line)
                                cur_t += lt
                            clean_md = "".join(buf) + "\n\n*(content truncated to token budget; full document searchable via knowledge base)*"
                        attachment_contexts.append(f"### Document: {att_name} ({p.name})\n\n{clean_md}")
                    except Exception as e:
                        attachment_contexts.append(f"### Document: {att_name} (Failed to read: {e})")
        elif att_content:
            clean_att = str(att_content).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            attachment_contexts.append(f"### Document: {att_name}\n```\n{clean_att[:16000]}\n```")

    if attachment_contexts or attached_images:
        combined_context = (
            "The user has provided the following attached context:\n\n" + "\n\n".join(attachment_contexts)
        ) if attachment_contexts else ""
        if messages and messages[-1].get("role") == "user":
            if combined_context:
                messages[-1]["content"] = f"{combined_context}\n\n---\nUser Query: {messages[-1].get('content', '')}"
            if attached_images:
                messages[-1]["images"] = attached_images
        else:
            msg_obj: dict[str, Any] = {"role": "user", "content": combined_context or user_prompt}
            if attached_images:
                msg_obj["images"] = attached_images
            messages.append(msg_obj)
