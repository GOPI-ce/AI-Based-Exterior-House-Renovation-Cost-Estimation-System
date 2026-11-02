"""Geometry: masks -> editable polygons, and photo regions -> real-world measurements.

Layering rule (used identically by the frontend renderer):
regions are stacked by (LAYER_PRIORITY, position in list). A region on a higher
layer covers the ones below it. So when measuring, each region's net area is
its own shape minus everything stacked above it. This is what deducts windows
and doors from walls, and stops a pillar standing in front of a wall from being
counted twice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid

from app.schemas import Point, Region

LAYER_PRIORITY: dict[str, int] = {
    "wall": 10,
    "roof_edge": 40,
    "parapet": 50,
    "balcony": 60,
    "pillar": 70,
    "railing": 80,
    "gate": 90,
    "window": 100,
    "door": 100,
}


# --------------------------------------------------------------------------- #
# Masks -> polygons
# --------------------------------------------------------------------------- #
def mask_to_polygons(
    mask: np.ndarray,
    *,
    max_parts: int = 4,
    min_part_ratio: float = 0.08,
    min_area_frac: float = 0.0003,
    tolerance_frac: float = 0.003,
) -> list[list[Point]]:
    """Convert a boolean mask (H x W) into a few simplified, normalised polygons.

    Small speckles are removed, then each remaining blob's outline is simplified
    (Douglas-Peucker) so the user gets a handful of draggable corners rather than
    hundreds of pixel steps.
    """
    height, width = mask.shape
    m = mask.astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    if not contours:
        return []

    largest = cv2.contourArea(contours[0])
    min_area = max(min_area_frac * width * height, min_part_ratio * largest)
    epsilon = tolerance_frac * max(width, height)

    polygons: list[list[Point]] = []
    for contour in contours[:max_parts]:
        if cv2.contourArea(contour) < min_area:
            break
        approx = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(approx) >= 3:
            polygons.append([(round(x / width, 5), round(y / height, 5)) for x, y in approx])
    return polygons


def box_to_polygon(box: tuple[float, float, float, float]) -> list[Point]:
    """Normalised (x0, y0, x1, y1) box -> rectangle polygon."""
    x0, y0, x1, y1 = box
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# --------------------------------------------------------------------------- #
# Regions -> shapes
# --------------------------------------------------------------------------- #
def _polygonal_part(geom: BaseGeometry) -> BaseGeometry:
    """Keep only area-bearing parts (make_valid can return lines/points too)."""
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if isinstance(geom, GeometryCollection):
        parts = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
        return unary_union(parts) if parts else Polygon()
    return Polygon()


def region_shape(region: Region, width: int, height: int) -> BaseGeometry:
    """Region polygons in pixel coordinates, merged into one valid shape."""
    shapes = []
    for points in region.polygons:
        if len(points) < 3:
            continue
        poly = Polygon([(x * width, y * height) for x, y in points])
        if not poly.is_valid:
            poly = _polygonal_part(make_valid(poly))
        if not poly.is_empty:
            shapes.append(poly)
    return unary_union(shapes) if shapes else Polygon()


def layer_order(regions: list[Region]) -> list[int]:
    """Indices of regions from the bottom layer to the top layer."""
    return sorted(range(len(regions)), key=lambda i: (LAYER_PRIORITY.get(regions[i].type, 0), i))


@dataclass
class RegionMeasure:
    gross_px2: float
    net_px2: float
    # Long and short sides of the region's minimum bounding rectangle, as (dx, dy) pixel vectors,
    # so they can be converted with different horizontal and vertical scales.
    long_side: tuple[float, float]
    short_side: tuple[float, float]


def measure_regions(regions: list[Region], width: int, height: int) -> dict[str, RegionMeasure]:
    """Pixel measurements for every region, with overlaps deducted by layer."""
    shapes = [region_shape(r, width, height) for r in regions]
    measures: dict[str, RegionMeasure] = {}

    covered_above: BaseGeometry = Polygon()
    for i in reversed(layer_order(regions)):  # walk from the top layer down
        shape = shapes[i]
        net = shape.difference(covered_above) if not covered_above.is_empty else shape
        long_side, short_side = _rect_sides(shape)
        measures[regions[i].id] = RegionMeasure(shape.area, net.area, long_side, short_side)
        if not shape.is_empty:
            covered_above = unary_union([covered_above, shape])
    return measures


def _rect_sides(shape: BaseGeometry) -> tuple[tuple[float, float], tuple[float, float]]:
    if shape.is_empty:
        return (0.0, 0.0), (0.0, 0.0)
    rect = shape.minimum_rotated_rectangle
    coords = list(rect.exterior.coords) if isinstance(rect, Polygon) else []
    if len(coords) < 4:
        return (0.0, 0.0), (0.0, 0.0)
    a = (coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
    b = (coords[2][0] - coords[1][0], coords[2][1] - coords[1][1])
    return (a, b) if math.hypot(*a) >= math.hypot(*b) else (b, a)


def region_bounds(region: Region, width: int, height: int) -> tuple[float, float, float, float] | None:
    """Pixel bounding box (x0, y0, x1, y1) of all of a region's polygons."""
    points = [p for poly in region.polygons for p in poly]
    if not points:
        return None
    xs = [p[0] * width for p in points]
    ys = [p[1] * height for p in points]
    return min(xs), min(ys), max(xs), max(ys)
