"""Structured field extraction engine with bounding box provenance alignment."""

import re

import structlog

from ingest.types import BoundingBox, ExtractedField, ExtractedWord

log = structlog.get_logger()

# Regex patterns for industrial refinery domain inspection fields
PATTERNS: dict[str, tuple[str, str | None]] = {
    # (Regex pattern, default unit)
    "asset_tag": (r"\b([A-Z]{1,3}-\d{3,4}[A-Z]?)\b", None),
    "inspection_date": (r"\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})\b", None),
    "cml_number": (r"\b(CML-\d{1,3}[A-Z]?)\b", None),
    "thickness_mm": (r"\b(\d{1,2}\.\d{1,2})\s*(?:mm)?\b", "mm"),
    "corrosion_rate_mm_yr": (r"\b(\d{1,2}\.\d{1,3})\s*(?:mm/yr)\b", "mm/yr"),
    "ncr_status": (r"\b(ACCEPTED|REJECTED|NON-CONFORMANCE|SATISFACTORY|UNSATISFACTORY)\b", None),
}


class FieldExtractor:
    """Extracts named domain fields from extracted words with exact bounding-box provenance."""

    def extract_pattern_fields(
        self, words: list[ExtractedWord], page_num: int
    ) -> list[ExtractedField]:
        """Extract structured fields using domain regex rules mapped to word coordinate unions."""
        if not words:
            return []

        full_text = " ".join([w.text for w in words])
        fields: list[ExtractedField] = []

        for field_name, (pattern, unit) in PATTERNS.items():
            for match in re.finditer(pattern, full_text, re.IGNORECASE):
                matched_val = match.group(1)
                start_char = match.start()
                end_char = match.end()

                # Find words that span this character match
                matched_words: list[ExtractedWord] = []
                current_len = 0
                for w in words:
                    w_start = current_len
                    w_end = current_len + len(w.text)
                    if w_end >= start_char and w_start <= end_char:
                        matched_words.append(w)
                    current_len = w_end + 1  # include space

                if not matched_words:
                    continue

                boxes = [w.bbox for w in matched_words]
                bbox = BoundingBox.from_union(boxes)

                confidences = [w.confidence for w in matched_words if w.confidence is not None]
                conf = float(sum(confidences) / len(confidences)) if confidences else None

                requires_verification = conf is None or conf < 0.85

                fields.append(
                    ExtractedField(
                        field_name=field_name,
                        value=matched_val,
                        unit=unit,
                        confidence=conf,
                        requires_verification=requires_verification,
                        page=page_num,
                        bbox=bbox,
                        extractor="pattern_rule",
                    )
                )

        return fields

    def align_vision_extracted_field(
        self,
        field_name: str,
        value: str,
        unit: str | None,
        words: list[ExtractedWord],
        page_num: int,
    ) -> ExtractedField:
        """Create an ExtractedField from Vision LLM output.

        Vision LLM self-reported numbers are uncalibrated:
        Sets confidence = None and requires_verification = True.
        Maps returned value substring back to page word bounding box.
        """
        matched_words = [w for w in words if value.lower() in w.text.lower()]
        if matched_words:
            bbox = BoundingBox.from_union([w.bbox for w in matched_words])
        elif words:
            bbox = BoundingBox.from_union([w.bbox for w in words[:3]])
        else:
            bbox = BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0)

        return ExtractedField(
            field_name=field_name,
            value=value,
            unit=unit,
            confidence=None,  # Uncalibrated for Vision LLM
            requires_verification=True,  # Mandatory human verification
            page=page_num,
            bbox=bbox,
            extractor="vision_llm",
        )
