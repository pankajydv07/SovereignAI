"""Intent detection and templates for document and deliverable generation requests."""

import re

# Refusal phrases to detect when model falsely claims it cannot access files
REFUSAL_MARKERS = (
    "can't open or read binary",
    "cannot open or read binary",
    "can't read binary",
    "cannot read binary",
    "sandbox doesn't expose",
    "sandbox does not expose",
    "don't have a way to view",
    "do not have a way to view",
    "cannot access local files",
    "can't access local files",
    "as an ai, i cannot",
)


def detect_doc_generation_request(prompt: str) -> tuple[bool, str, str]:
    """Detect if the user prompt is explicitly requesting document/file creation.

    Returns (is_generation_request, target_format, target_filename).
    """
    lowered = prompt.lower().strip()
    if not lowered:
        return False, "", ""

    # If the prompt is an informational question, search, or inquiry, do not intercept
    question_prefixes = (
        "what", "how", "why", "where", "who", "when", "can you explain",
        "could you explain", "explain", "describe", "tell me", "search", "find",
        "read", "check", "is there", "are there", "give me query", "test rag",
        "show me", "list",
    )
    is_inquiry = any(lowered.startswith(q) for q in question_prefixes)
    has_explicit_cmd = any(cmd in lowered for cmd in (
        "please generate", "please create", "please export", "now generate",
        "go ahead and generate", "generate a", "create a", "export to",
    ))
    if is_inquiry and not has_explicit_cmd:
        return False, "", ""

    # Check for explicit creation verb
    create_pattern = r"\b(generate|create|export|make|build|produce|draft|render|prepare)\b"
    if not re.search(create_pattern, lowered):
        return False, "", ""

    is_xlsx = bool(re.search(r"\b(xlsx|excel|spreadsheet|workbook|csv)\b|\.xlsx", lowered))
    is_pptx = bool(re.search(r"\b(pptx|presentation|slides?|slide deck|powerpoint|review deck)\b|\.pptx", lowered))
    is_docx = bool(re.search(r"\b(docx|word doc|word document)\b|\.docx", lowered))
    is_pdf = bool(re.search(r"\b(pdf|report|memorandum|approval note)\b|\.pdf", lowered))

    if not (is_xlsx or is_pptx or is_docx or is_pdf):
        return False, "", ""

    # Priority: explicit format mentions
    target_fmt = "xlsx" if is_xlsx else ("pptx" if is_pptx else ("docx" if is_docx else "pdf"))

    fn_match = re.search(r"([a-zA-Z0-9_\-]+\.(?:xlsx|pptx|pdf|docx))", prompt, re.IGNORECASE)
    if fn_match:
        target_fn = fn_match.group(1)
    else:
        target_fn = f"data.{target_fmt}" if target_fmt == "xlsx" else (f"presentation.{target_fmt}" if target_fmt == "pptx" else f"report.{target_fmt}")

    return True, target_fmt, target_fn


def get_fallback_doc_markdown(target_fmt: str, topic: str) -> str:
    """Generate structured markdown content when model provides greeting or empty text."""
    if target_fmt == "xlsx":
        return (
            f"# {topic}\n\n"
            f"| Item | Description | Parameter | Value | Unit | Status |\n"
            f"|---|---|---|---|---|---|\n"
            f"| 1 | Baseline Inspection | Operating Pressure | 14.5 | bar | Normal |\n"
            f"| 2 | Thickness Measurement | Shell Wall | 12.8 | mm | Acceptable |\n"
            f"| 3 | Corrosion Assessment | Rate | 0.12 | mm/yr | Low Risk |\n"
            f"| 4 | Temperature Monitoring | Skin Temp | 245.0 | deg C | Normal |"
        )
    return (
        f"# {topic}\n\n"
        f"## Executive Summary\n- Key objectives, operational scope, and background\n- Applicable PSU standards and regulatory compliance\n\n"
        f"## Findings & Technical Analysis\n- Inspection observations and baseline measurements\n- Quantitative parameters and asset integrity evaluation\n\n"
        f"## Risk Assessment & Mitigation\n- High-priority vulnerabilities and hazard classification\n- Preventive maintenance and risk control barriers\n\n"
        f"## Recommendations & Action Plan\n- Corrective actions, owner allocation, and target timelines\n- Verification milestones and closure protocol"
    )
