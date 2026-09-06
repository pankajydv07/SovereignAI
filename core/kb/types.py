"""Data models and type definitions for Knowledge Base hybrid retrieval."""

from enum import StrEnum

from pydantic import BaseModel, Field

from ingest.types import BoundingBox


class ClassificationLevel(StrEnum):
    """Document classification level."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class UserRole(StrEnum):
    """User access role for permission filtering."""

    ALL = "*"
    INSPECTION_ENGINEER = "InspectionEngineer"
    DEPUTY_MANAGER = "DeputyManager"
    PROJECTS_ENGINEER = "ProjectsEngineer"
    IT_SECURITY_OFFICER = "ITSecurityOfficer"
    PUBLIC_USER = "PublicUser"


class Citation(BaseModel):
    """Source citation reference for grounded retrieval."""

    doc_id: str = Field(alias="docId")
    heading_path: str = Field(alias="headingPath")
    page: int
    bbox: BoundingBox
    text_snippet: str = Field(alias="textSnippet")


class KBChunk(BaseModel):
    """Knowledge Base chunk model with layout context and metadata."""

    id: str
    doc_id: str = Field(alias="docId")
    chunk_index: int = Field(alias="chunkIndex")
    heading_path: str = Field(alias="headingPath")
    body_text: str = Field(alias="bodyText")
    token_count: int = Field(alias="tokenCount")
    page: int
    bbox: BoundingBox
    allowed_roles: list[str] = Field(default_factory=lambda: ["*"], alias="allowedRoles")
    dept: str = "General"
    classification: ClassificationLevel = ClassificationLevel.INTERNAL
    effective_date: str = Field(alias="effectiveDate", description="YYYY-MM-DD effective date")
    superseded_by: str | None = Field(default=None, alias="supersededBy")


class KBDocument(BaseModel):
    """Knowledge Base document container."""

    id: str
    title: str
    dept: str
    classification: ClassificationLevel
    effective_date: str = Field(alias="effectiveDate")
    superseded_by: str | None = Field(default=None, alias="supersededBy")
    chunks: list[KBChunk] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Individual search result item from hybrid retrieval."""

    chunk_id: str = Field(alias="chunkId")
    doc_id: str = Field(alias="docId")
    heading_path: str = Field(alias="headingPath")
    body_text: str = Field(alias="bodyText")
    page: int
    bbox: BoundingBox
    rrf_score: float = Field(alias="rrfScore")
    cosine_similarity: float = Field(alias="cosineSimilarity")
    citation: Citation
