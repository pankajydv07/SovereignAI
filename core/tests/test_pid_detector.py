"""Unit tests for P&ID symbol detection, tiling, tag normalization, and reconciliation.

Placed in core/tests/ for consistency with the rest of the project.
"""

import pytest

from ingest.types import BoundingBox
from storage.equipment_store import EquipmentRegisterEntry
from vision.pid_detector import (
    ROBOFLOW_PID_CLASSES,
    TEXT_BEARING_CLASSES,
    PIDDetector,
    PIDSymbolDetection,
    normalize_tag,
    reconcile_pid_tags,
)


def test_roboflow_class_list_and_text_filtering():
    assert len(ROBOFLOW_PID_CLASSES) == 11
    assert "instrument_tag" in ROBOFLOW_PID_CLASSES
    assert "instrument_dcs" in ROBOFLOW_PID_CLASSES
    assert "gate_valve" in ROBOFLOW_PID_CLASSES
    assert "pump" in ROBOFLOW_PID_CLASSES

    assert "instrument_tag" in TEXT_BEARING_CLASSES
    assert "instrument_dcs" in TEXT_BEARING_CLASSES
    assert "gate_valve" not in TEXT_BEARING_CLASSES


def test_tag_normalization():
    assert normalize_tag("FT 1702") == "FT-1702"
    assert normalize_tag("10-pt-101") == "10-PT-101"
    assert normalize_tag("pic-3301a/b") == "PIC-3301A/B"
    assert normalize_tag("LG-T  1707") == "LG-T-1707"


def test_padded_crop_from_original_image():
    det = PIDSymbolDetection(
        symbol_id="sym-01",
        class_name="instrument_tag",
        confidence=0.95,
        bbox=BoundingBox(x0=0.20, y0=0.30, x1=0.40, y1=0.50),
    )

    padded = det.pad_crop_bbox(padding_pct=0.10)
    # Original width = 0.20, height = 0.20. 10% padding = 0.02
    assert padded.x0 == pytest.approx(0.18)
    assert padded.y0 == pytest.approx(0.28)
    assert padded.x1 == pytest.approx(0.42)
    assert padded.y1 == pytest.approx(0.52)


def test_unreadable_region_confidence_is_none():
    det = PIDSymbolDetection(
        symbol_id="sym-unreadable",
        class_name="instrument_tag",
        confidence=0.35,
        bbox=BoundingBox(x0=0.10, y0=0.10, x1=0.20, y1=0.20),
        extracted_tag="unreadable",
        tag_confidence=None,  # Requirement 6: confidence is None when unreadable
        requires_verification=True,
        is_unreadable=True,
    )

    assert det.is_unreadable is True
    assert det.tag_confidence is None
    assert det.requires_verification is True


def test_tiled_detection_and_nms_merging():
    detector = PIDDetector()
    detections = detector.detect_symbols_tiled()

    # Verify duplicate boundary detection was merged via NMS
    tag_ids = [d.symbol_id for d in detections]
    assert "sym-01" in tag_ids
    assert "sym-01-dup" not in tag_ids  # NMS merged!


def test_reconciliation_against_known_register():
    detector = PIDDetector()
    detections = detector.detect_symbols_tiled()

    register_entries = [
        EquipmentRegisterEntry(
            tag_id="PT-101",
            unit_id="UNIT-01",
            equipment_name="Pressure Transmitter",
            service_description="Top Pressure",
            design_pressure_mpa=2.4,
            design_temp_c=120.0,
        ),
        EquipmentRegisterEntry(
            tag_id="TI-202",
            unit_id="UNIT-01",
            equipment_name="Temperature Indicator",
            service_description="Reflux Temp",
            design_pressure_mpa=1.6,
            design_temp_c=180.0,
        ),
        EquipmentRegisterEntry(
            tag_id="FIC-204A",
            unit_id="UNIT-01",
            equipment_name="Flow Controller",
            service_description="Feed Flow",
            design_pressure_mpa=4.0,
            design_temp_c=210.0,
        ),
        # PI-108 is missing from register -> discrepancy!
    ]

    result = reconcile_pid_tags(detections, register_entries)

    assert result.discrepancy_count >= 1
    assert result.unreadable_count == 1

    # Verify matched items
    matched_tags = [r.tag_id for r in result.reconciliation_table if r.status == "MATCHED"]
    assert "PT-101" in matched_tags
    assert "TI-202" in matched_tags
    assert "FIC-204A" in matched_tags

    # Verify discrepancy item PI-108
    discrepancies = [r for r in result.reconciliation_table if r.status == "DISCREPANCY"]
    assert any(d.tag_id == "PI-108" for d in discrepancies)

    # Verify unreadable item has confidence = None
    unreadable_items = [r for r in result.reconciliation_table if r.status == "UNREADABLE"]
    assert len(unreadable_items) == 1
    assert unreadable_items[0].confidence is None
