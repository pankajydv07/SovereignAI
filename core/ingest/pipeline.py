"""Document Ingest Pipeline Orchestrator.

Manages process pool for OpenCV preprocessing and Tesseract OCR per 20-python.md.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pdfplumber
import structlog
from PIL import Image

from ingest.classifier import classify_document
from ingest.extractor import FieldExtractor
from ingest.layout import detect_layout_regions
from ingest.ocr import (
    OcrEngineUnavailable,
    extract_words_pdfplumber,
    extract_words_tesseract,
)
from ingest.preprocess import preprocess_scanned_page
from ingest.types import (
    DocumentClassification,
    ExtractedField,
    ExtractedWord,
    IngestDocumentResult,
    IngestPageResult,
)

log = structlog.get_logger()


class DocumentIngestPipeline:
    """Async air-gapped document ingestion pipeline."""

    def __init__(
        self,
        max_workers: int | None = None,
        vision_client: Any | None = None,
        executor: Any | None = None,
    ) -> None:
        self._pool = executor or ProcessPoolExecutor(max_workers=max_workers)
        self._extractor = FieldExtractor()
        self._vision_client = vision_client

    def shutdown(self) -> None:
        """Shutdown the process pool executor."""
        self._pool.shutdown(wait=False)

    async def ingest_document(self, file_path: str | Path) -> IngestDocumentResult:
        """Ingest document file (PDF/Image) and return result with provenance."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        loop = asyncio.get_running_loop()
        classification = classify_document(path)
        log.info("ingest_started", file_path=str(path), classification=classification)

        page_results: list[IngestPageResult] = []
        all_fields: list[ExtractedField] = []

        if path.suffix.lower() == ".pdf":
            with pdfplumber.open(path) as pdf:
                num_pages = len(pdf.pages)
                for page_idx in range(1, num_pages + 1):
                    page_res = await self._process_pdf_page(
                        loop, path, pdf, page_idx, classification
                    )
                    page_results.append(page_res)
                    all_fields.extend(page_res.fields)
        else:
            # Single image file
            pil_img = Image.open(path)
            page_res = await self._process_image_page(loop, pil_img, 1)
            page_results.append(page_res)
            all_fields.extend(page_res.fields)

        log.info(
            "ingest_completed",
            file_path=str(path),
            total_pages=len(page_results),
            total_fields=len(all_fields),
        )
        return IngestDocumentResult(
            doc_path=str(path),
            classification=classification,
            pages=page_results,
            fields=all_fields,
        )

    async def _process_pdf_page(
        self,
        loop: asyncio.AbstractEventLoop,
        pdf_path: Path,
        pdf: pdfplumber.pdf.PDF,
        page_num: int,
        classification: DocumentClassification,
    ) -> IngestPageResult:
        """Process a single PDF page."""
        words: list[ExtractedWord] = []

        if classification == DocumentClassification.BORN_DIGITAL:
            words = extract_words_pdfplumber(pdf_path, page_num)
            page_obj = pdf.pages[page_num - 1]
            pil_img = page_obj.to_image(resolution=150).original
        else:
            page_obj = pdf.pages[page_num - 1]
            pil_img = page_obj.to_image(resolution=300).original
            # Preprocess image in process pool
            preprocessed_img = await loop.run_in_executor(
                self._pool, preprocess_scanned_page, pil_img
            )
            # Run Tesseract OCR in process pool - fails loudly if binary absent
            words = await loop.run_in_executor(
                self._pool, extract_words_tesseract, preprocessed_img, page_num
            )
            pil_img = preprocessed_img

        regions = detect_layout_regions(pil_img, words, page_num)
        fields = self._extractor.extract_pattern_fields(words, page_num)

        # Escalate low-confidence, handwriting, or stamp regions to vision role
        for r in regions:
            if (r.requires_verification or r.confidence is None or r.confidence < 0.70) and self._vision_client:
                v_field = await self._escalate_region_to_vision(pil_img, r, page_num)
                if v_field:
                    fields.append(v_field)

        return IngestPageResult(
            page_num=page_num,
            classification=classification,
            words=words,
            regions=regions,
            fields=fields,
        )

    async def _process_image_page(
        self,
        loop: asyncio.AbstractEventLoop,
        pil_img: Image.Image,
        page_num: int,
    ) -> IngestPageResult:
        """Process a single image page."""
        preprocessed_img = await loop.run_in_executor(
            self._pool, preprocess_scanned_page, pil_img
        )
        # Run Tesseract OCR in process pool - fails loudly if binary absent
        words = await loop.run_in_executor(
            self._pool, extract_words_tesseract, preprocessed_img, page_num
        )
        regions = detect_layout_regions(preprocessed_img, words, page_num)
        fields = self._extractor.extract_pattern_fields(words, page_num)

        # Escalate low-confidence, handwriting, or stamp regions to vision role
        for r in regions:
            if (r.requires_verification or r.confidence is None or r.confidence < 0.70) and self._vision_client:
                v_field = await self._escalate_region_to_vision(preprocessed_img, r, page_num)
                if v_field:
                    fields.append(v_field)

        return IngestPageResult(
            page_num=page_num,
            classification=DocumentClassification.SCANNED,
            words=words,
            regions=regions,
            fields=fields,
        )

    async def _escalate_region_to_vision(
        self,
        pil_img: Image.Image,
        region: Any,
        page_num: int,
    ) -> ExtractedField | None:
        """Escalate candidate region crop to vision role with uncalibrated confidence."""
        if not self._vision_client:
            return None

        img_w, img_h = pil_img.size
        crop_box = (
            int(region.bbox.x0 * img_w),
            int(region.bbox.y0 * img_h),
            int(region.bbox.x1 * img_w),
            int(region.bbox.y1 * img_h),
        )
        if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
            return None

        crop_img = pil_img.crop(crop_box)
        try:
            if asyncio.iscoroutinefunction(getattr(self._vision_client, "extract_field", None)):
                res = await self._vision_client.extract_field(crop_img, region)
            elif hasattr(self._vision_client, "extract_field"):
                res = self._vision_client.extract_field(crop_img, region)
            else:
                res = None

            if res and isinstance(res, dict):
                return ExtractedField(
                    field_name=res.get("field_name", "inspector_handwritten_remark"),
                    value=res.get("value", ""),
                    unit=res.get("unit", None),
                    confidence=None,  # Uncalibrated for vision models
                    requires_verification=True,  # Mandatory human verification
                    page=page_num,
                    bbox=region.bbox,
                    extractor="vision_llm",
                )
        except Exception as exc:
            log.warning("vision_escalation_failed", region_id=region.region_id, error=str(exc))

        return None
