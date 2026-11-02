"""Scale: turning photo pixels into feet, robustly.

Every plane (house front, house side, compound...) collects reference *cues*: lines on the photo
whose real length is known or confidently estimated (a door is ~7 ft, a car ~5 ft, a railing ~3.5 ft,
or a length the user measured). The plane's scale is the weighted median of what the cues imply,
after dropping outliers, computed separately for the vertical and horizontal directions when both
kinds of cue exist (that is what corrects the horizontal foreshortening of an angled wall).

The same algorithm runs in the browser (frontend/src/lib/geometry.ts) for the editor's live sizes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.schemas import PLANE_NAMES, CueKind, Plane, Region, ScaleReference, View
from app.services.geometry import region_bounds

# Typical real heights (ft) of objects Gemini may report, used when it gives no estimate,
# and how much each kind of cue is trusted (heights of cars and people vary more than doors).
CUE_DEFAULTS: dict[str, tuple[float, float]] = {
    "door": (7.0, 1.0),  # 2100 mm, standard Indian door height
    "storey": (10.0, 0.6),  # floor-to-floor, typically 9.5-10.5 ft
    "railing": (3.5, 0.7),  # balcony guard, 1.0-1.2 m
    "parapet": (3.3, 0.5),  # roof parapet, ~1 m
    "gate": (6.0, 0.4),  # varies a lot
    "window": (4.0, 0.3),
    "car": (5.0, 0.7),  # hatchback/sedan 4.7-5.2 ft, SUV ~5.8 ft
    "person": (5.4, 0.6),
    "motorbike": (3.6, 0.5),
    "custom": (1.0, 1.0),
}
OUTLIER_TOLERANCE = 0.35  # cues more than 35% away from the median are ignored
STOREY_HEIGHT_FT = 10.0  # typical Indian floor-to-floor height
MIN_LINE_PX = 8


@dataclass
class PlaneScale:
    ft_per_px_x: float
    ft_per_px_y: float
    confidence: float  # 0..1
    spread: float  # relative disagreement between cues (0 = perfect agreement)
    cues_used: list[str] = field(default_factory=list)
    cues_rejected: list[str] = field(default_factory=list)
    borrowed_from: str | None = None


def _ft_per_px(ref: ScaleReference, width: int, height: int) -> float | None:
    px = math.dist((ref.p1[0] * width, ref.p1[1] * height), (ref.p2[0] * width, ref.p2[1] * height))
    return ref.real_length_ft / px if px >= MIN_LINE_PX else None


def _weighted_median(values: list[tuple[float, float]]) -> float:
    ordered = sorted(values)
    half = sum(w for _, w in ordered) / 2
    acc = 0.0
    for value, weight in ordered:
        acc += weight
        if acc >= half:
            return value
    return ordered[-1][0]


def _consensus(samples: list[tuple[float, float, ScaleReference]]):
    """(value, spread, used refs, rejected refs) from (ft_per_px, weight, reference) samples."""
    samples = [s for s in samples if s[1] > 0]
    if not samples:
        return None
    median = _weighted_median([(v, w) for v, w, _ in samples])
    kept = [s for s in samples if abs(s[0] / median - 1) <= OUTLIER_TOLERANCE] if len(samples) >= 3 else samples
    rejected = [r for _, _, r in samples if all(r.id != k.id for _, _, k in kept)]
    value = _weighted_median([(v, w) for v, w, _ in kept])
    total = sum(w for _, w, _ in kept)
    spread = sum(w * abs(v / value - 1) for v, w, _ in kept) / total if total else 0.0
    return value, spread, [r for _, _, r in kept], rejected


def plane_scale(plane: Plane, view: View, _seen: frozenset[str] = frozenset()) -> PlaneScale | None:
    refs = [r for r in plane.references if r.enabled]
    vertical, horizontal = [], []
    for r in refs:
        fpp = _ft_per_px(r, view.width, view.height)
        if fpp is None:
            continue
        sample = (fpp, r.weight if r.source == "auto" else 1.0, r)
        if r.axis in ("vertical", "free"):
            vertical.append(sample)
        if r.axis in ("horizontal", "free"):
            horizontal.append(sample)

    v = _consensus(vertical)
    h = _consensus(horizontal)
    if v is None and h is None:
        fallback = next((p for p in view.planes if p.id == plane.fallback_plane_id), None)
        if fallback is None or fallback.id in _seen:
            return None
        borrowed = plane_scale(fallback, view, _seen | {plane.id})
        if borrowed is None:
            return None
        borrowed.confidence *= 0.5
        borrowed.borrowed_from = fallback.name
        return borrowed

    fy, sy, used_v, rej_v = v or h  # type: ignore[misc]
    fx, sx, used_h, rej_h = h or v  # type: ignore[misc]
    used = list({r.id: r for r in used_v + used_h}.values())
    used_ids = {r.id for r in used}
    rejected = [r for r in {r.id: r for r in rej_v + rej_h}.values() if r.id not in used_ids]
    spread = max(sy, sx)

    manual = any(r.source == "manual" for r in refs)
    n = len(used)
    confidence = (0.75 if manual else 0.35) + 0.12 * min(n - 1, 3)
    confidence *= max(0.3, 1 - 2 * spread)
    if plane.confirmed:
        confidence = max(confidence, 0.9)
    return PlaneScale(fx, fy, round(min(confidence, 0.97), 2), round(spread, 3), [r.name for r in used], [r.name for r in rejected])


def plane_for_region(region: Region, view: View) -> Plane | None:
    if not view.planes:
        return None
    return next((p for p in view.planes if p.id == region.plane_id), view.planes[0])


def _front_building_span(regions: list[Region], width: int, height: int) -> tuple[float, float] | None:
    """Normalised (top, bottom) of the house front's walls, parapets and roof edges."""
    tops, bottoms = [], []
    for r in regions:
        if (r.plane_id or "house_front") == "house_front" and r.type in ("wall", "parapet", "roof_edge"):
            b = region_bounds(r, width, height)
            if b:
                tops.append(b[1] / height)
                bottoms.append(b[3] / height)
    if not tops or max(bottoms) - min(tops) <= 0.1:
        return None
    return min(tops), max(bottoms)


def scale_error(scale: PlaneScale | None) -> float:
    """Expected relative error of a length measured with this scale (for estimate ranges)."""
    if scale is None:
        return 0.5
    return round(0.04 + 0.3 * (1 - scale.confidence) + scale.spread, 3)


# --------------------------------------------------------------------------- #
# Automatic planes from the AI analysis
# --------------------------------------------------------------------------- #
@dataclass
class DetectedCue:
    kind: CueKind
    box: tuple[float, float, float, float]  # normalised x0, y0, x1, y1
    plane: str
    real_height_ft: float | None
    confidence: float
    label: str
    line: tuple[tuple[float, float], tuple[float, float]] | None = None  # measured on the SAM mask


def auto_planes(regions: list[Region], cues: list[DetectedCue], storeys: int | None, width: int, height: int) -> list[Plane]:
    """One plane per depth group seen in the photo, each with the cues found on it."""
    kinds = list(dict.fromkeys([r.plane_id or "house_front" for r in regions] + [c.plane for c in cues]))
    if not kinds:
        return []
    planes: dict[str, Plane] = {k: Plane(id=k, name=PLANE_NAMES.get(k, k), kind=k if k in PLANE_NAMES else "other") for k in kinds}

    counts: dict[str, int] = {}
    for cue in cues:
        default_ft, trust = CUE_DEFAULTS.get(cue.kind, (None, 0.3))
        real = cue.real_height_ft or default_ft
        if not real or real <= 0:
            continue
        x0, y0, x1, y1 = cue.box
        cx = (x0 + x1) / 2
        p1, p2 = cue.line or ((cx, y0), (cx, y1))
        counts[cue.kind] = counts.get(cue.kind, 0) + 1
        planes[cue.plane].references.append(ScaleReference(
            id=f"auto-{cue.kind}-{counts[cue.kind]}",
            name=cue.label[:60] or cue.kind.title(),
            cue=cue.kind,
            axis="vertical",
            p1=p1,
            p2=p2,
            real_length_ft=round(real, 2),
            source="auto",
            weight=round(trust * max(0.2, min(1.0, cue.confidence)), 2),
        ))

    # The building as a whole: visible storeys at ~10 ft each plus ~3 ft for plinth and parapet.
    front = planes.get("house_front")
    building = _front_building_span(regions, width, height)
    if front is not None and storeys and building:
        top, bottom = building
        # 1) An independent, low-trust cue that breaks ties when object cues disagree.
        front.references.append(ScaleReference(
            id="auto-building-1", name=f"Building height ({storeys} storeys)", cue="storey", axis="vertical",
            p1=(0.5, top), p2=(0.5, bottom), real_length_ft=storeys * STOREY_HEIGHT_FT + 3.0, source="auto", weight=0.35,
        ))
        # 2) A plausibility check: a cue implying an impossible building height (a 2-storey house must be
        #    roughly 17-32 ft) is switched off, but kept visible so the user can re-enable it.
        building_px = (bottom - top) * height
        low_ft, high_ft = storeys * 8 + 1, storeys * 13 + 6
        for ref in front.references:
            fpp = _ft_per_px(ref, width, height)
            if fpp and ref.id != "auto-building-1" and not low_ft <= building_px * fpp <= high_ft:
                ref.enabled = False
                ref.name = f"{ref.name} (implausible: implies a {building_px * fpp:.0f} ft building)"

    # Planes without cues borrow from the house front (or any plane that has cues).
    donor = next((p for p in [planes.get("house_front"), *planes.values()] if p and p.references), None)
    for p in planes.values():
        if not p.references and donor and donor is not p:
            p.fallback_plane_id = donor.id

    order = ["house_front", "house_side", "boundary", "other"]
    return sorted(planes.values(), key=lambda p: order.index(p.kind) if p.kind in order else 9)
