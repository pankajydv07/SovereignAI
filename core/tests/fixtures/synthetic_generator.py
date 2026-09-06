"""Synthetic inspection report document and ground-truth generator for testing."""

import json
from pathlib import Path
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
