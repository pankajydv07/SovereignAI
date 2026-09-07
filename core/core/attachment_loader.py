"""Attachment extraction and formatting helpers for chat messages."""

import base64
from pathlib import Path
from typing import Any

from tools.document_reader import convert_document_to_markdown

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def process_chat_attachments(
    attachments: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    user_prompt: str,
) -> None:
    """Process incoming attachments (images/documents) and format them into message context."""
    if not attachments:
        return

    attachment_contexts: list[str] = []
    attached_images: list[str] = []

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
                else:
                    try:
                        doc_md = convert_document_to_markdown(p)
                        clean_md = doc_md.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                        attachment_contexts.append(f"### Document: {att_name} ({p.name})\n\n{clean_md[:32000]}")
                    except Exception as e:
                        attachment_contexts.append(f"### Document: {att_name} (Failed to read: {e})")
        elif att_content:
            clean_att = str(att_content).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            attachment_contexts.append(f"### Document: {att_name}\n```\n{clean_att[:24000]}\n```")

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
