"""Data models and type definitions for document ingestion and field extraction."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field


class DocumentClassification(StrEnum):
    """Document text-layer classification."""

    BORN_DIGITAL = "BORN_DIGITAL"
    SCANNED = "SCANNED"
    HYBRID = "HYBRID"


class RegionType(StrEnum):
    """Layout region type."""

    TEXT_BLOCK = "TEXT_BLOCK"
    TABLE_GRID = "TABLE_GRID"
    GRAPHIC_REGION = "GRAPHIC_REGION"
    HANDWRITING = "HANDWRITING"
    STAMP = "STAMP"


class BoundingBox(BaseModel):
    """Normalized bounding box coordinates on a page: [x0, y0, x1, y1] in [0.0, 1.0]."""

    x0: float = Field(ge=0.0, le=1.0, description="Left coordinate normalized")
    y0: float = Field(ge=0.0, le=1.0, description="Top coordinate normalized")
    x1: float = Field(ge=0.0, le=1.0, description="Right coordinate normalized")
    y1: float = Field(ge=0.0, le=1.0, description="Bottom coordinate normalized")

    def union(self, other: Self) -> Self:
        """Compute the enclosing bounding box of self and another box."""
        return self.__class__(
            x0=min(self.x0, other.x0),
            y0=min(self.y0, other.y0),
            x1=max(self.x1, other.x1),
            y1=max(self.y1, other.y1),
        )

    @classmethod
    def from_union(cls, boxes: list["BoundingBox"]) -> "BoundingBox":
        """Compute enclosing bounding box for a list of boxes."""
        if not boxes:
            return cls(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
        res = boxes[0]
        for b in boxes[1:]:
            res = res.union(b)
        return res


class ExtractedWord(BaseModel):
    """Single word extracted from a document page with provenance coordinate and confidence."""

    text: str
    bbox: BoundingBox
    confidence: float | None = Field(
        default=None,
        description="Calibrated extraction confidence (0.0 to 1.0), or None if uncalibrated",
    )
    page: int = Field(ge=1, description="1-indexed page number")


class Region(BaseModel):
    """Segmented layout region on a page."""

    region_id: str
    region_type: RegionType
    bbox: BoundingBox
    page: int = Field(ge=1, description="1-indexed page number")
    text: str = ""
    confidence: float | None = Field(
        default=None,
        description="Region confidence score (0.0 to 1.0), or None for vision model outputs",
    )
    requires_verification: bool = Field(
        default=False,
        description="True if maker-checker human verification is mandatory for this region",
    )


class VerificationMeta(BaseModel):
    """Separate human verification metadata. Preserves immutable machine confidence."""

    verified_by: str = Field(alias="verifiedBy")
    verified_at: str = Field(alias="verifiedAt")
    original_value: str = Field(alias="originalValue")
    corrected_value: str | None = Field(default=None, alias="correctedValue")


class ExtractedField(BaseModel):
    """Structured field extracted from a document with full provenance."""

    field_name: str
    value: str
    unit: str | None = None
    confidence: float | None = Field(
        default=None,
        description="Calibrated field confidence (0.0 to 1.0), or None for vision/LLM outputs",
    )
    requires_verification: bool = Field(
        default=False,
        description="True if maker-checker human verification is required",
    )
    page: int = Field(ge=1, description="1-indexed page number")
    bbox: BoundingBox
    extractor: str = Field(
        description="Extractor identifier, e.g. pdfplumber, pytesseract, pattern_rule, vision_llm",
    )
    verification: VerificationMeta | None = None


class IngestPageResult(BaseModel):
    """Ingestion output for a single document page."""

    page_num: int = Field(ge=1)
    classification: DocumentClassification
    words: list[ExtractedWord] = Field(default_factory=list)
    regions: list[Region] = Field(default_factory=list)
    fields: list[ExtractedField] = Field(default_factory=list)


class IngestDocumentResult(BaseModel):
    """Complete document ingestion result."""

    doc_path: str
    classification: DocumentClassification
    pages: list[IngestPageResult] = Field(default_factory=list)
    fields: list[ExtractedField] = Field(default_factory=list)
