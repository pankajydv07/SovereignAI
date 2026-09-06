"""Core approval module for SWARAJ maker-checker gate."""

from .service import (
    ApprovalPreconditionFailedError,
    ApprovalResult,
    ApprovalService,
    RejectionResult,
    SeparationOfDutiesError,
)

__all__ = [
    "ApprovalService",
    "ApprovalResult",
    "RejectionResult",
    "SeparationOfDutiesError",
    "ApprovalPreconditionFailedError",
]
