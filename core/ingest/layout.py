"""Layout analysis and region segmentation using OpenCV morphological contours."""

import cv2
import numpy as np
import structlog
from PIL import Image

from ingest.preprocess import pil_to_cv2
from ingest.types import BoundingBox, ExtractedWord, Region, RegionType

log = structlog.get_logger()


def detect_layout_regions(
    pil_img: Image.Image,
    words: list[ExtractedWord],
    page_num: int,
) -> list[Region]:
    """Detect structural layout regions on a page using OpenCV morphological operations."""
    img_width, img_height = pil_img.size
    if img_width <= 0 or img_height <= 0:
        return []

    cv_img = pil_to_cv2(pil_img)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img

    # Morphological dilation to group words into text blocks and tables
    kernel_text = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 9))
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    dilated_text = cv2.dilate(thresh, kernel_text, iterations=2)

    contours, _ = cv2.findContours(dilated_text, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions: list[Region] = []

    # Map words to regions for calculating average OCR confidence
    region_idx = 1
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        # Filter small noise contours
        if w < 20 or h < 10 or (w * h) < 300:
            continue

        bbox = BoundingBox(
            x0=max(0.0, min(1.0, float(x) / img_width)),
            y0=max(0.0, min(1.0, float(y) / img_height)),
            x1=max(0.0, min(1.0, float(x + w) / img_width)),
            y1=max(0.0, min(1.0, float(y + h) / img_height)),
        )

        # Collect words inside this region
        region_words = [
            w for w in words
            if w.bbox.x0 >= bbox.x0 - 0.02 and w.bbox.x1 <= bbox.x1 + 0.02
            and w.bbox.y0 >= bbox.y0 - 0.02 and w.bbox.y1 <= bbox.y1 + 0.02
        ]

        region_text = " ".join([w.text for w in region_words])
        confidences = [w.confidence for w in region_words if w.confidence is not None]
        avg_conf = float(np.mean(confidences)) if confidences else None

        aspect_ratio = float(w) / float(h)
        area_ratio = float(w * h) / float(img_width * img_height)

        # Region typing rules
        has_table_char = "|" in region_text or "\t" in region_text
        if aspect_ratio > 3.0 and len(region_words) > 5 and has_table_char:
            region_type = RegionType.TABLE_GRID
        elif area_ratio > 0.05 and len(region_words) < 3:
            region_type = RegionType.GRAPHIC_REGION
        elif avg_conf is not None and avg_conf < 0.40 and len(region_words) > 0:
            # Low confidence text block indicates potential handwriting
            region_type = RegionType.HANDWRITING
        elif aspect_ratio < 1.5 and 0.01 < area_ratio < 0.08 and len(region_words) <= 4:
            # Compact graphic block often indicates a stamp
            region_type = RegionType.STAMP
        else:
            region_type = RegionType.TEXT_BLOCK

        requires_verification = (
            region_type in {RegionType.HANDWRITING, RegionType.STAMP}
            or (avg_conf is None or avg_conf < 0.70)
        )

        is_uncalibrated = region_type in {RegionType.HANDWRITING, RegionType.STAMP}
        regions.append(
            Region(
                region_id=f"p{page_num}_r{region_idx}",
                region_type=region_type,
                bbox=bbox,
                page=page_num,
                text=region_text,
                confidence=avg_conf if not is_uncalibrated else None,
                requires_verification=requires_verification,
            )
        )
        region_idx += 1

    return regions
