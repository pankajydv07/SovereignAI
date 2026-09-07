"""OCR extraction engine using Tesseract and pdfplumber with real per-word confidence.

Provides calibrated confidence scores (0.0 to 1.0) and normalized bounding boxes.
Executed in process pool per 20-python.md.
"""

from pathlib import Path

import pdfplumber
import pytesseract  # type: ignore[import-untyped]
import structlog
from PIL import Image
from pytesseract import Output

from ingest.types import BoundingBox, ExtractedWord

log = structlog.get_logger()


class OcrEngineUnavailable(RuntimeError):
    """Raised when Tesseract OCR binary is not installed or missing from system PATH."""

    def __init__(
        self,
        message: str = (
            "Tesseract OCR executable ('tesseract') was not found on system PATH. "
            "OCR extraction for scanned documents requires Tesseract. "
            "Installation: on Windows run 'winget install UB-Mannheim.TesseractOCR' and ensure it is in PATH; "
            "on Linux run 'sudo apt install tesseract-ocr'."
        ),
    ) -> None:
        super().__init__(message)


# Backward-compatible alias
OCREngineNotFoundError = OcrEngineUnavailable


def extract_words_pdfplumber(pdf_path: str | Path, page_num: int) -> list[ExtractedWord]:
    """Extract words with exact bounding box coordinates from a born-digital PDF page.

    Sets confidence = 1.00 for born-digital text layer words.
    """
    path = Path(pdf_path)
    words: list[ExtractedWord] = []

    with pdfplumber.open(path) as pdf:
        if page_num < 1 or page_num > len(pdf.pages):
            return []

        page = pdf.pages[page_num - 1]
        width = float(page.width)
        height = float(page.height)

        if width <= 0 or height <= 0:
            return []

        extracted = page.extract_words()
        for w in extracted:
            text = str(w.get("text", "")).strip()
            if not text:
                continue

            x0 = float(w["x0"]) / width
            top = float(w["top"]) / height
            x1 = float(w["x1"]) / width
            bottom = float(w["bottom"]) / height

            bbox = BoundingBox(
                x0=max(0.0, min(1.0, x0)),
                y0=max(0.0, min(1.0, top)),
                x1=max(0.0, min(1.0, x1)),
                y1=max(0.0, min(1.0, bottom)),
            )

            words.append(
                ExtractedWord(
                    text=text,
                    bbox=bbox,
                    confidence=1.00,  # Exact font text layer
                    page=page_num,
                )
            )

    return words


def extract_words_tesseract(pil_img: Image.Image, page_num: int) -> list[ExtractedWord]:
    """Extract words from an image using Tesseract OCR with calibrated confidence scores."""
    img_width, img_height = pil_img.size
    if img_width <= 0 or img_height <= 0:
        return []

    try:
        data = pytesseract.image_to_data(pil_img, output_type=Output.DICT)
    except (pytesseract.TesseractNotFoundError, FileNotFoundError) as exc:
        raise OcrEngineUnavailable() from exc
    except Exception as exc:
        if "tesseract is not installed" in str(exc).lower() or "not found" in str(exc).lower():
            raise OcrEngineUnavailable() from exc
        log.warning("tesseract_ocr_error", error=str(exc), page_num=page_num)
        return []

    words: list[ExtractedWord] = []
    num_items = len(data.get("text", []))

    for i in range(num_items):
        text = str(data["text"][i]).strip()
        raw_conf = data["conf"][i]

        if not text or raw_conf == -1 or raw_conf is None:
            continue

        conf_float = max(0.0, min(1.0, float(raw_conf) / 100.0))
        if "\ufffd" in text:
            conf_float = 0.0

        left = float(data["left"][i])
        top = float(data["top"][i])
        w = float(data["width"][i])
        h = float(data["height"][i])

        bbox = BoundingBox(
            x0=max(0.0, min(1.0, left / img_width)),
            y0=max(0.0, min(1.0, top / img_height)),
            x1=max(0.0, min(1.0, (left + w) / img_width)),
            y1=max(0.0, min(1.0, (top + h) / img_height)),
        )

        words.append(
            ExtractedWord(
                text=text,
                bbox=bbox,
                confidence=conf_float,
                page=page_num,
            )
        )

    return words
