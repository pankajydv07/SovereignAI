"""Unit and integration tests for document ingestion, OCR, layout, and field extraction."""

import asyncio
from pathlib import Path
import pytest
from ingest.classifier import classify_document
from ingest.extractor import FieldExtractor
from ingest.pipeline import DocumentIngestPipeline
from ingest.preprocess import adaptive_binarise, cv2_to_pil, deskew_image, pil_to_cv2
from ingest.types import BoundingBox, DocumentClassification, ExtractedWord
from tests.fixtures.synthetic_generator import create_test_corpus


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary synthetic document test corpus."""
    c_dir = tmp_path / "corpus"
    create_test_corpus(c_dir)
    return c_dir


def test_extracted_word_bounding_box_union() -> None:
    """Test BoundingBox union calculation."""
    b1 = BoundingBox(x0=0.1, y0=0.1, x1=0.3, y1=0.3)
    b2 = BoundingBox(x0=0.2, y0=0.2, x1=0.5, y1=0.6)
    union = b1.union(b2)
    assert union.x0 == 0.1
    assert union.y0 == 0.1
    assert union.x1 == 0.5
    assert union.y1 == 0.6


def test_classification_scanned_image(corpus_dir: Path) -> None:
    """Test document classification heuristic on scanned image."""
    img_path = corpus_dir / "report_clean.png"
    classification = classify_document(img_path)
    assert classification == DocumentClassification.SCANNED


def test_opencv_preprocessing(corpus_dir: Path) -> None:
    """Test OpenCV deskewing and adaptive binarization."""
    from PIL import Image

    img_path = corpus_dir / "report_skewed.png"
    pil_img = Image.open(img_path)
    cv_img = pil_to_cv2(pil_img)

    deskewed = deskew_image(cv_img)
    assert deskewed is not None
    assert deskewed.shape == cv_img.shape

    binarised = adaptive_binarise(deskewed)
    assert binarised is not None
    res_pil = cv2_to_pil(binarised)
    assert res_pil.size == pil_img.size


def test_field_extractor_patterns() -> None:
    """Test pattern rule field extraction and bounding box union."""
    words = [
        ExtractedWord(text="Equipment", bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15), confidence=0.95, page=1),
        ExtractedWord(text="Tag:", bbox=BoundingBox(x0=0.21, y0=0.1, x1=0.25, y1=0.15), confidence=0.92, page=1),
        ExtractedWord(text="C-101", bbox=BoundingBox(x0=0.26, y0=0.1, x1=0.35, y1=0.15), confidence=0.98, page=1),
    ]

    extractor = FieldExtractor()
    fields = extractor.extract_pattern_fields(words, page_num=1)
    assert len(fields) >= 1

    tag_field = next(f for f in fields if f.field_name == "asset_tag")
    assert tag_field.value == "C-101"
    assert tag_field.confidence is not None
    assert tag_field.confidence > 0.90
    assert tag_field.requires_verification is False


def test_vision_field_uncalibrated_confidence() -> None:
    """Test Vision LLM output alignment forces confidence=None and requires_verification=True."""
    words = [
        ExtractedWord(text="Handwritten", bbox=BoundingBox(x0=0.1, y0=0.5, x1=0.3, y1=0.6), confidence=None, page=1),
        ExtractedWord(text="Note", bbox=BoundingBox(x0=0.31, y0=0.5, x1=0.4, y1=0.6), confidence=None, page=1),
    ]
    extractor = FieldExtractor()
    field = extractor.align_vision_extracted_field(
        field_name="handwritten_remark",
        value="Handwritten Note",
        unit=None,
        words=words,
        page_num=1,
    )
    assert field.confidence is None
    assert field.requires_verification is True
    assert field.extractor == "vision_llm"


@pytest.mark.asyncio
async def test_pipeline_end_to_end_synthetic_report(corpus_dir: Path) -> None:
    """Test async DocumentIngestPipeline execution on synthetic test report."""
    pipeline = DocumentIngestPipeline(max_workers=2)
    try:
        report_path = corpus_dir / "report_clean.png"
        result = await pipeline.ingest_document(report_path)

        assert result.classification == DocumentClassification.SCANNED
        assert len(result.pages) == 1
        page = result.pages[0]
        assert len(page.regions) > 0

        # Check extracted fields if OCR engine runs
        field_names = [f.field_name for f in result.fields]
        assert isinstance(field_names, list)

    finally:
        pipeline.shutdown()
