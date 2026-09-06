"""Calculation Engine Models and Exceptions for SWARAJ.

Defines Pydantic models for calculation parameters, provenance tracking (FR-5.7),
dimensional cross-checks, and execution records.
"""

from typing import Any

from pydantic import BaseModel, Field


class NoAssertionError(ValueError):
    """Raised when a Python calculation script lacks explicit unit declarations or assertions."""

    pass


class CalculationVerificationError(ValueError):
    """Raised when cross-check verification, dimensional analysis, or bounds assertions fail."""

    pass


class CalculationVerificationFailedError(ValueError):
    """Raised by renderers when attempting to render a deliverable for a failed calculation."""

    pass


class ParameterProvenance(BaseModel):
    """Provenance tracking metadata for input calculation parameters (FR-5.7)."""

    extracted_field_id: str | None = Field(default=None, description="Extracted field ID")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    human_verified: bool = Field(default=True, description="Human verification status")
    source_doc_id: str = Field(default="Drawing/Spec", description="Source document ID")


class CalculationParameter(BaseModel):
    """Input parameter for engineering calculation."""

    name: str = Field(description="Parameter description")
    symbol: str = Field(description="Mathematical symbol (e.g. P, D, S, E)")
    value: float | int | str = Field(description="Given input value")
    unit: str = Field(description="Unit of measurement (e.g. MPa, mm, °C)")
    source: str = Field(default="Drawing/Spec", description="Source clause or drawing tag")
    provenance: ParameterProvenance = Field(
        default_factory=ParameterProvenance, description="Parameter provenance"
    )


class CrossCheckResult(BaseModel):
    """Multi-layered cross-check verification result."""

    passed: bool = Field(description="Overall cross-check status")
    dimensional_check_passed: bool = Field(
        description="Physical unit dimensional consistency check status"
    )
    bounds_check_passed: bool = Field(description="Physical bounds assertions check status")
    primary_value: float = Field(description="Primary calculation script output value")
    cross_check_value: float = Field(description="Secondary cross-check script output value")
    relative_diff: float = Field(description="Computed relative difference")


class CalculationExecutionRecord(BaseModel):
    """Complete execution record for a sandboxed calculation run."""

    calc_run_id: str = Field(description="Unique calculation run ID")
    session_id: str = Field(default="default", description="Associated session ID")
    equipment_tag: str = Field(description="Plant equipment tag (e.g., 10-C-101)")
    title: str = Field(description="Calculation title")
    governing_standard: str = Field(
        description="Governing code or standard (e.g., API 570, ASME Sec VIII)"
    )
    governing_clause: str = Field(description="Governing clause reference (e.g., §7.1.1, UG-27)")
    clause_quoted_text: str = Field(description="Clause text quoted directly from Knowledge Base")
    requires_manual_clause_verification: bool = Field(
        default=False, description="Flagged True if clause was missing from KB"
    )
    parameters: list[CalculationParameter] = Field(description="Given input parameters")
    has_unverified_inputs: bool = Field(
        default=False, description="Flagged True if any parameter is unverified (FR-5.7)"
    )
    unverified_fields_count: int = Field(
        default=0, description="Number of unverified input parameters"
    )
    derivation_steps: list[dict[str, Any]] = Field(
        description="Step-by-step mathematical derivation log"
    )
    cross_check: CrossCheckResult = Field(description="Cross-check verification result")
    verification_passed: bool = Field(description="Whether all assertions and cross-checks passed")
    assertions_log: list[str] = Field(description="Log of inline assertions executed and passed")
    final_answer: dict[str, Any] = Field(description="Final output variables with units")
