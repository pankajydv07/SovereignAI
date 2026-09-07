"""Pydantic JSON Schemas and Citation Validation for Deliverable Rendering.

Defines typed deliverable schemas for Approval Notes, Inspection Summaries,
Review Decks, Cost Sheets, and Engineering Calculations, enforcing render-time
citation verification.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field

from calc.models import CalculationParameter, ParameterProvenance


class UncitedClaimError(ValueError):
    """Raised when a substantive claim or recommendation lacks required citations."""

    pass


class LowConfidenceFieldUnverifiedError(ValueError):
    """Raised when an official deliverable references an unverified extraction field with low confidence."""

    pass


class CitationRef(BaseModel):
    """Citation link referencing source material in the knowledge base or extracted field."""

    doc_id: str = Field(description="Document ID or reference tag")
    title: str = Field(default="", description="Document or report title")
    clause_or_section: str = Field(
        default="", description="Specific clause, section, or page reference"
    )
    extracted_field_id: str | None = Field(
        default=None, description="Extracted field ID if provenance is from OCR/Extraction"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    is_verified: bool = Field(
        default=True, description="Whether field has been verified by human checker"
    )
    source_page: int | None = Field(default=None, description="Source document page number")
    source_region_bbox: list[float] | None = Field(
        default=None, description="Bounding box [ymin, xmin, ymax, xmax]"
    )


class SystemProvenanceMetadata(BaseModel):
    """System-constructed provenance metadata derived from execution context.

    This is constructed deterministically by the system/renderer from run context,
    NOT supplied or faked by model JSON.
    """

    run_id: str = Field(description="System execution run ID")
    models_used: list[str] = Field(description="List of model tags used in generating findings")
    sources_cited: list[str] = Field(description="Aggregated list of document sources cited")
    min_confidence: float = Field(description="Minimum extraction confidence across all fields")
    human_verified_count: int = Field(default=0, description="Count of human-verified fields")
    draft_warning: str = Field(
        default="DRAFT — requires approval by competent authority",
        description="Non-removable legal draft attestation banner",
    )
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC generation timestamp",
    )



class SubstantiveClaim(BaseModel):
    """Base item requiring at least one explicit citation."""

    text: str = Field(description="Substantive claim text")
    citations: list[CitationRef] = Field(
        default_factory=list,
        description="List of source citations supporting this claim",
    )


class ApprovalLadderRole(BaseModel):
    """Role entry in the PSU maker-checker approval ladder."""

    role: str = Field(description="Role designation (e.g., Prepared By, Checked By, Sanctioned By)")
    name: str = Field(description="Name and designation of officer")
    status: str = Field(default="PENDING", description="Status (PENDING, VERIFIED, APPROVED)")


class ApprovalNoteSchema(BaseModel):
    """PSU Approval Note deliverable schema matching swaraj-domain conventions."""

    subject: str = Field(description="One-line subject statement")
    reference: list[str] = Field(
        default_factory=list, description="Prior file numbers/correspondence"
    )
    background: str = Field(description="Background and necessity narrative")
    observations: list[SubstantiveClaim] = Field(description="Key observations with citations")
    financial_implication: str = Field(description="Cost and budget head breakdown text")
    deviation: str | None = Field(
        default=None, description="Explicit departure from standard practice"
    )
    recommendation: list[SubstantiveClaim] = Field(
        description="Specific sanction sought with citations"
    )
    approval_ladder: list[ApprovalLadderRole] = Field(
        description="Maker-checker approval workflow roles"
    )


class ThicknessReading(BaseModel):
    """Equipment wall thickness reading item."""

    location: str = Field(description="Measurement location / nozzle / circuit tag")
    nominal_mm: float = Field(gt=0, description="Nominal wall thickness in mm")
    actual_mm: float = Field(gt=0, description="Actual measured wall thickness in mm")
    min_required_mm: float = Field(gt=0, description="Minimum allowable thickness in mm")


class DefectItem(BaseModel):
    """Observed defect or non-conformance item."""

    description: str = Field(description="Defect description")
    severity: str = Field(description="Severity (LOW, MEDIUM, HIGH, CRITICAL)")
    citations: list[CitationRef] = Field(description="Citations referencing inspection logs/photos")


class InspectionFinding(BaseModel):
    """Structured inspection finding with defect categorization and provenance link."""

    finding_id: str = Field(description="Unique finding identifier (e.g., FIND-C101-01)")
    category: str = Field(
        description="Category (CORROSION, EROSION, CRACK, LEAK, MECHANICAL_DAMAGE, COATING_FAILURE, WALL_THINNING, OTHER)"
    )
    severity: str = Field(description="Severity (LOW, MEDIUM, HIGH, CRITICAL)")
    equipment_tag: str = Field(description="Plant equipment tag (e.g., C-101, CML-07)")
    description: str = Field(description="Detailed finding narrative")
    source_page: int = Field(default=1, description="Page in inspection report")
    source_region_bbox: list[float] | None = Field(
        default=None, description="Bounding box [ymin, xmin, ymax, xmax]"
    )
    extracted_field_ids: list[str] = Field(
        default_factory=list, description="Associated extracted field IDs"
    )
    citations: list[CitationRef] = Field(default_factory=list, description="Source citations")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    verification_status: str = Field(
        default="UNVERIFIED", description="Status (UNVERIFIED, VERIFIED, REJECTED)"
    )
    recommended_action: str = Field(
        default="", description="Recommended engineering action or repair"
    )
    photograph_path: str | None = Field(default=None, description="Path to inspection photo")
    inspection_method: str = Field(
        default="UT", description="NDT method (UT, MPI, Radiography, Visual, Dye-Penetrant)"
    )


class InspectionSummarySchema(BaseModel):
    """Inspection report summary deliverable schema."""

    asset_tag: str = Field(description="Plant equipment tag number (e.g., 11-V-102)")
    equipment_tag: str | None = Field(
        default=None, description="Optional explicit equipment tag"
    )
    inspection_date: str = Field(description="Date of inspection (YYYY-MM-DD)")
    inspection_method: str = Field(description="NDT method (UT, MPI, Radiography, Visual)")
    findings: list[InspectionFinding] = Field(
        default_factory=list, description="Structured inspection findings"
    )
    thickness_readings: list[ThicknessReading] = Field(default_factory=list)
    observed_defects: list[DefectItem] = Field(default_factory=list)
    ncrs: list[str] = Field(default_factory=list, description="Non-conformance report IDs")
    photographs: list[str] = Field(
        default_factory=list, description="Inspection photograph paths"
    )
    recommendations: list[SubstantiveClaim] = Field(
        default_factory=list, description="Action recommendations with citations"
    )


InspectionReportSummary = InspectionSummarySchema


class DeckSlide(BaseModel):
    """Individual slide model for review decks."""

    slide_type: str = Field(
        default="content", description="Slide type (title, content, metrics, table)"
    )
    title: str = Field(description="Slide heading title")
    bullets: list[str] = Field(default_factory=list, description="Bullet points")
    key_metrics: list[dict[str, str]] = Field(
        default_factory=list, description="Metric label-value pairs"
    )
    table_headers: list[str] = Field(default_factory=list, description="Table column headers")
    table_rows: list[list[str]] = Field(default_factory=list, description="Table row cells")
    citations: list[CitationRef] = Field(default_factory=list, description="Slide citations")


class ReviewDeckSchema(BaseModel):
    """Review presentation deck deliverable schema."""

    title: str = Field(description="Presentation title")
    subtitle: str | None = Field(default=None, description="Subtitle or unit name")
    slides: list[DeckSlide] = Field(description="List of slide content items")


class CostLineItem(BaseModel):
    """Individual financial line item for cost sheets."""

    description: str = Field(description="Item name or description")
    quantity: float = Field(gt=0, description="Quantity")
    unit_rate: float = Field(ge=0, description="Unit rate in currency")
    formula: str = Field(description="Live Excel formula string, e.g. '=B4*C4'")
    computed_amount: float | None = Field(default=None, description="Pre-computed initial amount")
    citations: list[CitationRef] = Field(
        default_factory=list, description="Item cost basis citations"
    )


class CostSheetSchema(BaseModel):
    """Financial implication / cost sheet deliverable schema."""

    currency: str = Field(default="INR", description="Currency symbol/code")
    budget_head: str = Field(description="PSU accounting budget head")
    provisioned: bool = Field(description="Whether provisioned in current financial year")
    items: list[CostLineItem] = Field(description="Cost line items")
    total_formula: str = Field(default="=SUM(D4:D{end})", description="Total formula string")


class EngineeringCalculationSchema(BaseModel):
    """Engineering calculation deliverable schema.

    Numerical calculation results are NOT accepted from LLM JSON. Instead,
    calc_run_id points to the P6.2 sandboxed code execution record.
    """

    title: str = Field(description="Calculation title (e.g., Shell Thickness Verification)")
    equipment_tag: str = Field(description="Equipment tag number (e.g., 10-C-101)")
    governing_standard: str = Field(description="Governing code (e.g., ASME Sec VIII Div 1)")
    governing_clause: str = Field(description="Specific code clause reference (e.g., UG-27)")
    calc_run_id: str = Field(description="Execution record ID from P6.2 sandbox code execution")
    parameters: list[CalculationParameter] = Field(description="Input given parameters")
    citations: list[CitationRef] = Field(description="Code and standards citations")


def validate_citations(data: BaseModel) -> None:
    """Enforce render-time citation verification and checker verification gates on substantive claims.

    Raises:
    - UncitedClaimError if any substantive observation, defect, or recommendation lacks at least one citation.
    - LowConfidenceFieldUnverifiedError if any cited field has confidence < 0.85 and is not verified by a checker.
    """

    if isinstance(data, ApprovalNoteSchema):
        for obs in data.observations:
            if not obs.citations:
                raise UncitedClaimError(
                    f"Observation claim '{obs.text[:40]}...' lacks required citations"
                )
            for cit in obs.citations:
                if cit.confidence < 0.85 and not cit.is_verified:
                    field_id = cit.extracted_field_id or cit.doc_id
                    page_info = f" on page {cit.source_page}" if cit.source_page else ""
                    raise LowConfidenceFieldUnverifiedError(
                        f"Observation '{obs.text[:40]}...' references unverified field '{field_id}' "
                        f"with low confidence {cit.confidence:.2f}{page_info}. "
                        "Checker verification is required before deliverable can be rendered."
                    )
        for rec in data.recommendation:
            if not rec.citations:
                raise UncitedClaimError(
                    f"Recommendation claim '{rec.text[:40]}...' lacks required citations"
                )
            for cit in rec.citations:
                if cit.confidence < 0.85 and not cit.is_verified:
                    field_id = cit.extracted_field_id or cit.doc_id
                    raise LowConfidenceFieldUnverifiedError(
                        f"Recommendation '{rec.text[:40]}...' references unverified field '{field_id}' "
                        f"with low confidence {cit.confidence:.2f}. "
                        "Checker verification is required before deliverable can be rendered."
                    )

    elif isinstance(data, InspectionSummarySchema):
        for defect in data.observed_defects:
            if not defect.citations:
                raise UncitedClaimError(
                    f"Defect item '{defect.description[:40]}...' lacks required citations"
                )
            for cit in defect.citations:
                if cit.confidence < 0.85 and not cit.is_verified:
                    field_id = cit.extracted_field_id or cit.doc_id
                    raise LowConfidenceFieldUnverifiedError(
                        f"Defect item '{defect.description[:40]}...' references unverified field '{field_id}' "
                        f"with low confidence {cit.confidence:.2f}."
                    )
        for finding in data.findings:
            if finding.confidence < 0.85 and finding.verification_status != "VERIFIED":
                raise LowConfidenceFieldUnverifiedError(
                    f"Inspection finding '{finding.finding_id}' ({finding.description[:40]}...) "
                    f"has low confidence {finding.confidence:.2f} and status '{finding.verification_status}'. "
                    "Checker verification is required before deliverable can be rendered."
                )
        for rec in data.recommendations:
            if not rec.citations:
                raise UncitedClaimError(
                    f"Recommendation item '{rec.text[:40]}...' lacks required citations"
                )

    elif isinstance(data, EngineeringCalculationSchema):
        if not data.citations:
            raise UncitedClaimError(
                f"Engineering calculation '{data.title}' lacks required standard/code citations"
            )


__all__ = [
    "UncitedClaimError",
    "LowConfidenceFieldUnverifiedError",
    "CitationRef",
    "SystemProvenanceMetadata",
    "SubstantiveClaim",
    "ApprovalLadderRole",
    "ApprovalNoteSchema",
    "ThicknessReading",
    "DefectItem",
    "InspectionFinding",
    "InspectionSummarySchema",
    "InspectionReportSummary",
    "DeckSlide",
    "ReviewDeckSchema",
    "CostLineItem",
    "CostSheetSchema",
    "ParameterProvenance",
    "CalculationParameter",
    "EngineeringCalculationSchema",
    "validate_citations",
]
