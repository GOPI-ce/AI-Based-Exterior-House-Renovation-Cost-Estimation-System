"""The structure-identification pipeline.

    photo --Gemini--> labelled boxes --SAM 2.1--> pixel masks --OpenCV--> editable polygons
                                                                         + automatic scale suggestion

Every stage degrades gracefully: without SAM the boxes become rectangles; without
Gemini the user draws regions by hand. The user reviews and corrects the result
in the editor either way.
"""

from __future__ import annotations

import time
from collections import Counter

import numpy as np
from PIL import Image

from app.schemas import AnalysisResult, Region, SceneSummary
from app.services.gemini import GeminiComponent, GeminiScene, SceneAnalyzer, box_to_normalised
from app.services.geometry import box_to_polygon, mask_to_polygons
from app.services.scale import DetectedCue, auto_planes
from app.services.segmenter import Segmenter

DUPLICATE_IOU = 0.85
MIN_MASK_FILL = 0.12  # a mask covering less of its box than this is treated as a failure
MIN_SAM_SCORE = 0.3
BOX_MARGIN = 0.02  # masks are clipped to the prompt box plus this margin

# Plausible height/width ratios of scale cues; a box outside these is a misdetection.
CUE_ASPECT = {"door": (1.5, 3.6), "person": (1.8, 5.0), "car": (0.2, 1.0), "motorbike": (0.4, 1.3), "gate": (0.2, 2.5)}
MIN_CUE_HEIGHT_FRAC = 0.03  # cues shorter than 3% of the photo give too coarse a scale


def analyze_photo(jpeg: bytes, rgb: np.ndarray, analyzer: SceneAnalyzer, segmenter: Segmenter) -> AnalysisResult:
    height, width = rgb.shape[:2]
    timings: dict[str, float] = {}

    started = time.perf_counter()
    scene, model = analyzer.analyze(jpeg)
    timings["gemini_s"] = round(time.perf_counter() - started, 2)

    components = _dedupe(scene.components)
    boxes = [box_to_normalised(c.box_2d) for c in components]
    kept = [(c, b) for c, b in zip(components, boxes) if b is not None]
    cue_boxes = [(c, b) for c in scene.scale_cues if (b := box_to_normalised(c.box_2d)) is not None]
    plausible_cues = [(c, b) for c, b in cue_boxes if _plausible_cue(c.kind, b, width, height)]

    # One SAM batch for building parts and scale cues alike.
    all_masks: list[np.ndarray] = []
    all_scores: list[float] = []
    prompts = [b for _, b in kept] + [b for _, b in plausible_cues]
    if prompts and segmenter.wait_until_loaded(timeout_s=60):
        started = time.perf_counter()
        boxes_px = [[b[0] * width, b[1] * height, b[2] * width, b[3] * height] for b in prompts]
        all_masks, all_scores = segmenter.segment(Image.fromarray(rgb), boxes_px)
        timings["sam_s"] = round(time.perf_counter() - started, 2)
    masks, scores = all_masks[: len(kept)], all_scores[: len(kept)]
    cue_masks = all_masks[len(kept):]

    regions: list[Region] = []
    counts: Counter[str] = Counter()
    for i, (component, box) in enumerate(kept):
        polygons, source, confidence = None, "ai_box", None
        if i < len(masks):
            polygons = _mask_polygons(masks[i], box, scores[i])
            if polygons:
                source, confidence = "ai", round(scores[i], 3)
        if not polygons:
            polygons = [box_to_polygon(box)]
        counts[component.type] += 1
        regions.append(
            Region(
                id=f"{component.type}-{counts[component.type]}",
                type=component.type,
                label=component.label.strip()[:80] or component.type,
                polygons=polygons,
                source=source,
                confidence=confidence,
                face_factor=2.0 if component.type == "gate" else 1.0,
                plane_id=component.plane,
            )
        )

    warnings = []
    if kept and not masks:
        warnings.append("Precise outlining (SAM) was unavailable, so regions are rough boxes. Please adjust their corners.")
    if not regions:
        warnings.append("No building parts were detected. Draw the walls you want to renovate manually.")

    cues = [
        DetectedCue(kind=c.kind, box=b, plane=c.plane, real_height_ft=c.real_height_ft, confidence=c.confidence, label=c.label,
                    line=_cue_line(cue_masks[i], b) if i < len(cue_masks) else None)
        for i, (c, b) in enumerate(plausible_cues)
    ]
    planes = auto_planes(regions, cues, scene.storeys, width, height)
    if regions and not any(p.references for p in planes):
        warnings.append("No object of known size was found to set the scale. Draw a line over a length you know.")

    return AnalysisResult(
        regions=regions,
        planes=planes,
        scene=_summary(scene),
        pipeline={
            "gemini_model": model,
            "sam_model": segmenter.model_id if masks else "not used",
            "components_detected": len(regions),
            "scale_cues": len(cues),
            "scale_cues_rejected": len(cue_boxes) - len(plausible_cues),
            **timings,
        },
        warnings=warnings,
    )


def _plausible_cue(kind: str, box: tuple[float, float, float, float], width: int, height: int) -> bool:
    """Reject cue boxes whose shape cannot be the object claimed (a 'door' wider than tall, a sliver...)."""
    w_px = (box[2] - box[0]) * width
    h_px = (box[3] - box[1]) * height
    min_frac = 0.02 if kind in ("railing", "parapet") else MIN_CUE_HEIGHT_FRAC
    if h_px < min_frac * height or w_px <= 0:
        return False
    if kind == "storey":
        return h_px >= 0.08 * height and w_px >= 0.5 * h_px
    lo, hi = CUE_ASPECT.get(kind, (0.0, float("inf")))
    return lo <= h_px / w_px <= hi


def _cue_line(mask: np.ndarray, box: tuple[float, float, float, float]) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """A vertical line through the cue's *typical* height, measured on its SAM mask.

    For each column inside the box we count mask pixels; the line is drawn at the column whose
    height is the median of the well-covered columns. This is robust to perspective (a slanted
    railing has a tall bounding box but a short real height) and to ragged mask edges.
    """
    height, width = mask.shape
    x0, x1 = int(box[0] * width), max(int(box[0] * width) + 1, int(box[2] * width))
    y0, y1 = int(box[1] * height), max(int(box[1] * height) + 1, int(box[3] * height))
    window = mask[y0:y1, x0:x1]
    if window.size == 0:
        return None
    col_heights = window.sum(axis=0)
    if col_heights.max() <= 2:
        return None
    good = np.flatnonzero(col_heights >= 0.5 * col_heights.max())
    target = float(np.median(col_heights[good]))
    col = int(good[np.argmin(np.abs(col_heights[good] - target))])
    rows = np.flatnonzero(window[:, col])
    x = (x0 + col + 0.5) / width
    return (x, (y0 + rows[0]) / height), (x, (y0 + rows[-1] + 1) / height)


def _summary(scene: GeminiScene) -> SceneSummary:
    return SceneSummary(
        is_residential_exterior=scene.is_residential_exterior,
        view_type=scene.view_type,
        storeys=scene.storeys or None,
        usable=scene.usable_for_renovation and scene.is_residential_exterior,
        issues=scene.issues[:5],
        guidance=scene.guidance[:3],
    )


def _mask_polygons(mask: np.ndarray, box: tuple[float, float, float, float], score: float):
    if score < MIN_SAM_SCORE:
        return None
    height, width = mask.shape
    x0 = max(0, int((box[0] - BOX_MARGIN) * width))
    y0 = max(0, int((box[1] - BOX_MARGIN) * height))
    x1 = min(width, int((box[2] + BOX_MARGIN) * width) + 1)
    y1 = min(height, int((box[3] + BOX_MARGIN) * height) + 1)
    clipped = np.zeros_like(mask)
    clipped[y0:y1, x0:x1] = mask[y0:y1, x0:x1]

    box_area = max(1.0, (box[2] - box[0]) * width * (box[3] - box[1]) * height)
    if clipped.sum() / box_area < MIN_MASK_FILL:
        return None
    return mask_to_polygons(clipped) or None


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _dedupe(components: list[GeminiComponent]) -> list[GeminiComponent]:
    """Drop near-identical boxes of the same type (Gemini occasionally repeats an item)."""
    kept: list[GeminiComponent] = []
    for c in components:
        box = box_to_normalised(c.box_2d)
        if box is None:
            continue
        if any(k.type == c.type and _iou(box, box_to_normalised(k.box_2d) or (0, 0, 0, 0)) > DUPLICATE_IOU for k in kept):
            continue
        kept.append(c)
    return kept[:40]
