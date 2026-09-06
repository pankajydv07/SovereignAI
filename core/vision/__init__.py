"""P&ID Vision module for symbol detection, crop OCR, and equipment reconciliation."""

from .pid_detector import (
    ROBOFLOW_PID_CLASSES,
    TEXT_BEARING_CLASSES,
    PIDDetector,
    PIDReconciliationItem,
    PIDReconciliationResult,
    PIDSymbolDetection,
    normalize_tag,
    reconcile_pid_tags,
)

__all__ = [
    "ROBOFLOW_PID_CLASSES",
    "TEXT_BEARING_CLASSES",
    "PIDDetector",
    "PIDSymbolDetection",
    "PIDReconciliationItem",
    "PIDReconciliationResult",
    "normalize_tag",
    "reconcile_pid_tags",
]
