"""OpenCV document image preprocessing pipeline (deskew, denoise, binarise, DPI normalization).

Executed in a process pool per 20-python.md to prevent blocking the asyncio event loop.
"""

import cv2
import numpy as np
import structlog
from PIL import Image

log = structlog.get_logger()


def pil_to_cv2(image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR numpy array."""
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def cv2_to_pil(cv_img: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR or Grayscale numpy array to PIL Image."""
    if len(cv_img.shape) == 2:
        return Image.fromarray(cv_img, mode="L")
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb, mode="RGB")


def deskew_image(cv_img: np.ndarray) -> np.ndarray:
    """Detect skew angle via minAreaRect on text contours and rotate image."""
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img.copy()
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Dilate text blocks to create connected components
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return cv_img

    angles: list[float] = []
    for c in contours:
        if cv2.contourArea(c) < 500:
            continue
        rect = cv2.minAreaRect(c)
        angle = rect[-1]
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90
        angles.append(angle)

    if not angles:
        return cv_img

    median_angle = float(np.median(angles))
    # Ignore negligible angles (< 0.5 degrees) or extreme angles (> 30 degrees)
    if abs(median_angle) < 0.5 or abs(median_angle) > 30.0:
        return cv_img

    (h, w) = cv_img.shape[:2]
    center = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        cv_img, rot_mat, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )

    log.debug("image_deskewed", angle=median_angle, width=w, height=h)
    return rotated


def denoise_image(cv_img: np.ndarray) -> np.ndarray:
    """Apply median filter to remove speckle and scan noise."""
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img
    return cv2.medianBlur(gray, 3)


def adaptive_binarise(cv_img: np.ndarray) -> np.ndarray:
    """Apply adaptive thresholding for high contrast B/W document text."""
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 11
    )


def normalize_dpi(cv_img: np.ndarray, target_dpi: int = 300, current_dpi: int = 72) -> np.ndarray:
    """Resample image to target DPI (default 300 DPI) density."""
    if current_dpi >= target_dpi or current_dpi <= 0:
        return cv_img
    scale = target_dpi / current_dpi
    (h, w) = cv_img.shape[:2]
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def preprocess_scanned_page(pil_img: Image.Image) -> Image.Image:
    """Run full OpenCV preprocessing pipeline on a PIL Image page.

    Steps: Convert to CV2 -> Deskew -> Denoise -> Adaptive Binarise -> PIL Image.
    """
    cv_img = pil_to_cv2(pil_img)
    deskewed = deskew_image(cv_img)
    denoised = denoise_image(deskewed)
    binarised = adaptive_binarise(denoised)
    return cv2_to_pil(binarised)
