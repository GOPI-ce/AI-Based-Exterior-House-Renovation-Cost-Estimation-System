"""Fast, explainable photo-quality checks (OpenCV), run before any AI call.

Errors block the upload with a clear instruction; warnings let the user continue.
Thresholds were tuned on sample house photos at a 1024 px working size.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.schemas import QualityIssue, QualityReport

MIN_SIDE_PX = 480
WORK_SIDE_PX = 1024


def assess_quality(rgb: np.ndarray) -> QualityReport:
    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    scale = WORK_SIDE_PX / max(width, height)
    if scale < 1:
        gray = cv2.resize(gray, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)

    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())  # low = blurry
    brightness = float(gray.mean())
    contrast = float(gray.std())
    highlights = float((gray >= 250).mean())

    issues: list[QualityIssue] = []

    def add(code: str, severity: str, message: str) -> None:
        issues.append(QualityIssue(code=code, severity=severity, message=message))

    if min(width, height) < MIN_SIDE_PX:
        add("too_small", "error", f"The photo is only {width}x{height}px. Use a photo at least {MIN_SIDE_PX}px on its shorter side.")
    if brightness < 40:
        add("too_dark", "error", "The photo is too dark to see the walls. Retake it in daylight.")
    elif brightness < 70:
        add("dark", "warning", "The photo is quite dark; colours in the preview may look muddy.")
    if brightness > 225:
        add("overexposed", "error", "The photo is washed out. Avoid shooting towards the sun.")
    elif highlights > 0.25:
        add("highlights", "warning", "Parts of the photo are blown out (pure white); avoid direct sunlight on the lens.")
    if contrast < 18:
        add("low_contrast", "error", "The photo has almost no detail (fog, glare or a blank surface). Retake it.")
    if sharpness < 15:
        add("too_blurry", "error", "The photo is too blurry. Hold the phone steady and tap to focus on the house.")
    elif sharpness < 100:
        add("soft", "warning", "The photo is slightly soft; edges may be detected less accurately.")

    return QualityReport(
        ok=not any(i.severity == "error" for i in issues),
        issues=issues,
        metrics={
            "width": width,
            "height": height,
            "sharpness": round(sharpness, 1),
            "brightness": round(brightness, 1),
            "contrast": round(contrast, 1),
            "highlights_pct": round(highlights * 100, 1),
        },
    )
