"""Synthetic inspection report document and ground-truth generator for testing."""

import json
from pathlib import Path
from typing import Any
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def generate_synthetic_report_image(output_path: Path, skew_angle: float = 0.0) -> dict[str, str | None]:
    """Generate a synthetic scanned inspection report image with optional skew.

    Returns the expected ground-truth field mapping.
    """
    width, height = 1200, 1600
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Use default bitmap font
    font = ImageFont.load_default()

    ground_truth = {
        "asset_tag": "C-101",
        "inspection_date": "2026-09-05",
        "cml_number": "CML-01",
        "thickness_mm": "12.5",
        "corrosion_rate_mm_yr": "0.15",
        "ncr_status": "ACCEPTED",
    }

    # Draw header and text lines
    draw.text((100, 100), "MRPL REFINERY INSPECTION REPORT", fill=(0, 0, 0), font=font)
    draw.text((100, 200), f"Equipment Tag: {ground_truth['asset_tag']}", fill=(0, 0, 0), font=font)
    draw.text((100, 260), f"Inspection Date: {ground_truth['inspection_date']}", fill=(0, 0, 0), font=font)
    draw.text((100, 320), f"Location CML: {ground_truth['cml_number']}", fill=(0, 0, 0), font=font)
    draw.text((100, 380), f"Measured Thickness: {ground_truth['thickness_mm']} mm", fill=(0, 0, 0), font=font)
    draw.text((100, 440), f"Corrosion Rate: {ground_truth['corrosion_rate_mm_yr']} mm/yr", fill=(0, 0, 0), font=font)
    draw.text((100, 500), f"Final Status: {ground_truth['ncr_status']}", fill=(0, 0, 0), font=font)

    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    if skew_angle != 0.0:
        center = (width // 2, height // 2)
        M = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
        cv_img = cv2.warpAffine(cv_img, M, (width, height), borderValue=(255, 255, 255))

    cv2.imwrite(str(output_path), cv_img)
    return ground_truth


def create_test_corpus(output_dir: Path) -> dict:
    """Create synthetic test corpus directory with images and ground_truth.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_1 = output_dir / "report_clean.png"
    gt_1 = generate_synthetic_report_image(report_1, skew_angle=0.0)

    report_2 = output_dir / "report_skewed.png"
    gt_2 = generate_synthetic_report_image(report_2, skew_angle=-2.5)

    corpus_gt = {
        "report_clean.png": gt_1,
        "report_skewed.png": gt_2,
    }

    gt_file = output_dir / "ground_truth.json"
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(corpus_gt, f, indent=2)

    return corpus_gt


def generate_realistic_scanned_fixture(output_path: Path) -> dict[str, Any]:
    """Generate a realistic PSU bilingual scanned inspection report fixture.

    Contains printed bilingual text, tabular thickness gauging survey,
    observed defects, and a handwritten inspector remark region for vision escalation.
    """
    width, height = 1400, 1800
    img = Image.new("RGB", (width, height), color=(250, 250, 248))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    ground_truth = {
        "org_name_hi": "मंगलोर रिफाइनरी एवं पेट्रोकेमिकल्स लिमिटेड",
        "org_name_en": "MANGALORE REFINERY AND PETROCHEMICALS LIMITED",
        "division": "Inspection & Maintenance Engineering Division",
        "report_ref": "MRPL/INSP/2026/09",
        "inspection_date": "2026-09-07",
        "asset_tag": "C-101",
        "equipment_name": "Crude Distillation Column C-101",
        "inspection_method": "Ultrasonic Testing (UT) + Visual",
        "cml_number": "CML-07",
        "thickness_mm": "8.2",
        "nominal_thickness_mm": "12.0",
        "min_required_thickness_mm": "4.5",
        "corrosion_rate_mm_yr": "0.25",
        "ncr_status": "NON-CONFORMANCE",
        "ncr_ref": "NCR-MRPL-2026-088",
        "defect_description": "Localised external wall thinning and pitting corrosion detected at shell course 3 CML-07.",
        "handwritten_inspector_remark": "Immediate weld overlay required during next turnaround.",
    }

    # Draw Bilingual Header
    draw.text((120, 80), ground_truth["org_name_hi"], fill=(20, 30, 50), font=font)
    draw.text((120, 110), ground_truth["org_name_en"], fill=(20, 30, 50), font=font)
    draw.text((120, 140), ground_truth["division"], fill=(70, 80, 90), font=font)
    draw.line([(100, 170), (1300, 170)], fill=(30, 40, 60), width=3)

    # Document Title & Ref
    draw.text((120, 200), "TECHNICAL INSPECTION REPORT & THICKNESS SURVEY", fill=(10, 10, 10), font=font)
    draw.text((120, 240), f"Report Reference: {ground_truth['report_ref']}", fill=(40, 40, 40), font=font)
    draw.text((800, 240), f"Inspection Date: {ground_truth['inspection_date']}", fill=(40, 40, 40), font=font)

    # Equipment Specifications
    draw.text((120, 300), f"Equipment Tag: {ground_truth['asset_tag']}", fill=(0, 0, 0), font=font)
    draw.text((500, 300), f"Description: {ground_truth['equipment_name']}", fill=(0, 0, 0), font=font)
    draw.text((120, 340), f"NDT Inspection Method: {ground_truth['inspection_method']}", fill=(0, 0, 0), font=font)

    # Thickness Survey Table
    draw.rectangle([(110, 400), (1290, 600)], outline=(100, 100, 100), width=2)
    draw.line([(110, 450), (1290, 450)], fill=(100, 100, 100), width=1)
    draw.text((130, 420), "Location / Circuit", fill=(0, 0, 0), font=font)
    draw.text((450, 420), "Nominal (mm)", fill=(0, 0, 0), font=font)
    draw.text((650, 420), "Measured Actual (mm)", fill=(0, 0, 0), font=font)
    draw.text((900, 420), "Min Required (mm)", fill=(0, 0, 0), font=font)
    draw.text((1100, 420), "Corrosion Rate", fill=(0, 0, 0), font=font)

    draw.text((130, 480), f"{ground_truth['cml_number']} (Shell 3)", fill=(0, 0, 0), font=font)
    draw.text((450, 480), f"{ground_truth['nominal_thickness_mm']} mm", fill=(0, 0, 0), font=font)
    draw.text((650, 480), f"{ground_truth['thickness_mm']} mm", fill=(0, 0, 0), font=font)
    draw.text((900, 480), f"{ground_truth['min_required_thickness_mm']} mm", fill=(0, 0, 0), font=font)
    draw.text((1100, 480), f"{ground_truth['corrosion_rate_mm_yr']} mm/yr", fill=(0, 0, 0), font=font)

    # Findings & Defect Section
    draw.text((120, 640), "OBSERVED DEFECTS & NON-CONFORMANCES:", fill=(0, 0, 0), font=font)
    draw.text((140, 680), f"1. {ground_truth['defect_description']}", fill=(30, 30, 30), font=font)
    draw.text((140, 720), f"2. Non-Conformance Tagged: {ground_truth['ncr_ref']} [{ground_truth['ncr_status']}]", fill=(180, 20, 20), font=font)

    # Handwritten Inspector Remark Box (Simulated handwriting region)
    draw.rectangle([(110, 800), (1290, 980)], outline=(180, 100, 100), width=1)
    draw.text((130, 815), "[FIELD INSPECTOR HANDWRITTEN REMARK & STAMP]", fill=(120, 50, 50), font=font)
    draw.text((140, 860), f"Note: {ground_truth['handwritten_inspector_remark']}", fill=(40, 40, 160), font=font)
    draw.rectangle([(1000, 850), (1250, 950)], outline=(160, 40, 40), width=2)
    draw.text((1020, 890), "MRPL INSPECTION STAMP", fill=(160, 40, 40), font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))
    return ground_truth
