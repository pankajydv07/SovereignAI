"""Document classification module (Born-digital vs Scanned heuristic)."""

from pathlib import Path

import pdfplumber
import structlog

from ingest.types import DocumentClassification

log = structlog.get_logger()


def classify_document(file_path: str | Path) -> DocumentClassification:
    """Classify document as BORN_DIGITAL, SCANNED, or HYBRID using pdfplumber."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document file not found: {file_path}")

    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        log.debug(
            "classified_image_file",
            file_path=str(path),
            classification=DocumentClassification.SCANNED,
        )
        return DocumentClassification.SCANNED

    if suffix != ".pdf":
        log.debug("unsupported_extension_default_scanned", file_path=str(path))
        return DocumentClassification.SCANNED

    born_digital_pages = 0
    scanned_pages = 0

    try:
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return DocumentClassification.SCANNED

            for page in pdf.pages:
                text = page.extract_text() or ""
                text_char_count = len(text.strip())
                images = page.images

                # Heuristic: Page is born-digital if it contains > 80 text characters and font info
                if text_char_count > 80:
                    born_digital_pages += 1
                elif images and text_char_count <= 80:
                    scanned_pages += 1
                else:
                    # Low text count, no images
                    scanned_pages += 1

    except Exception as exc:
        log.warning(
            "pdfplumber_classification_error_default_scanned",
            file_path=str(path),
            error=str(exc),
        )
        return DocumentClassification.SCANNED

    total_pages = born_digital_pages + scanned_pages
    if total_pages == 0:
        return DocumentClassification.SCANNED

    if born_digital_pages == total_pages:
        classification = DocumentClassification.BORN_DIGITAL
    elif scanned_pages == total_pages:
        classification = DocumentClassification.SCANNED
    else:
        classification = DocumentClassification.HYBRID

    log.debug(
        "classified_pdf_document",
        file_path=str(path),
        born_digital_pages=born_digital_pages,
        scanned_pages=scanned_pages,
        classification=classification,
    )
    return classification
