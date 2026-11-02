"""Distance-aware measurement with Depth Anything V2 (metric, outdoor, Small; Apache-2.0).

A photo has no single scale: a wall 22 m from the camera covers fewer pixels per foot than a
railing 16 m away, so measuring both with the railing's scale under-counts the wall's area by
(16/22)^2, almost half. A monocular depth model tells how far every pixel is, and for a pinhole
camera feet-per-pixel grows linearly with distance. So every reference cue is normalised by its
own distance, the cues agree on one *feet per pixel per metre* value, and every surface is then
measured at its own distance.

The model's absolute distances can be off by 10-20%, but that error is common to the whole photo
and cancels out: the cues calibrate it. Its *relative* distances are what matter, and they are
consistent (on the demo house the railing, balcony slab and balcony pillar all come out at
15.6-16.5 m; the boundary wall, gate and gate pillar at 11.5-12.5 m).

We also tried recovering each surface's angle to the camera from the depth map (plane fitting).
On real photos the angles were off by up to +-20 deg, which would distort areas more than it
corrects, so angled walls still rely on horizontal references in the Scale step.

The browser runs the same sampling (frontend/src/lib/depth.ts) on the same integer-centimetre grid,
so the editor's live sizes match the estimate exactly.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import threading
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.schemas import Point, Region
from app.services.geometry import layer_order
from app.services.segmenter import MODEL_LOAD_LOCK

log = logging.getLogger(__name__)

FT_PER_M = 3.28084
GRID_SIDE = 192  # the depth grid's long side: plenty for per-surface statistics, small to ship to the browser
PHONE_FOCAL_35MM = 26.0  # a typical phone main camera, used when the photo has no EXIF focal length
EXIF_FOCAL_35MM = 0xA405  # FocalLengthIn35mmFilm
LINE_SAMPLES = (0.1, 0.3, 0.5, 0.7, 0.9)


@dataclass
class DepthGrid:
    """Depth in whole centimetres on a coarse grid over the photo (row-major, uint16)."""

    cm: np.ndarray  # (rows, cols) uint16
    focal_norm: float  # focal length / image width
    model: str

    @property
    def cols(self) -> int:
        return int(self.cm.shape[1])

    @property
    def rows(self) -> int:
        return int(self.cm.shape[0])

    def to_json(self) -> dict:
        return {
            "cols": self.cols,
            "rows": self.rows,
            "focal_norm": self.focal_norm,
            "model": self.model,
            "cm": base64.b64encode(self.cm.astype("<u2").tobytes()).decode(),
        }

    @classmethod
    def from_json(cls, data: dict) -> DepthGrid:
        cm = np.frombuffer(base64.b64decode(data["cm"]), dtype="<u2").reshape(data["rows"], data["cols"])
        return cls(cm.astype(np.uint16), float(data["focal_norm"]), data["model"])

    def to_json_text(self) -> str:
        return json.dumps(self.to_json())

    @classmethod
    def from_json_text(cls, text: str) -> DepthGrid:
        return cls.from_json(json.loads(text))

    def ft_per_px_per_m(self, image_width: int) -> float:
        """Pinhole camera: feet per image pixel, per metre of distance, for a surface facing the camera."""
        return FT_PER_M / (self.focal_norm * image_width)


def focal_norm_from_35mm(focal_35mm: float | None, width: int, height: int) -> float:
    """Focal length as a fraction of the image width, from the 35 mm-equivalent focal length."""
    f35 = focal_35mm if focal_35mm and 10 <= focal_35mm <= 300 else PHONE_FOCAL_35MM
    # The 35 mm frame is 36 mm along its long side.
    return f35 / 36.0 * (max(width, height) / width)


def exif_focal_35mm(jpeg: bytes) -> float | None:
    try:
        value = Image.open(io.BytesIO(jpeg)).getexif().get_ifd(0x8769).get(EXIF_FOCAL_35MM)
        return float(value) if value else None
    except Exception:
        return None


class DepthEstimator:
    """Loads the depth model once in a background thread; one CPU inference at a time."""

    def __init__(self, model_id: str, threads: int, enabled: bool = True) -> None:
        self.model_id = model_id
        self.threads = threads
        self.status = "loading" if enabled else "disabled"
        self._pipe = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def load_in_background(self) -> None:
        if self.status == "disabled":
            return
        threading.Thread(target=self._load, name="depth-loader", daemon=True).start()

    def _load(self) -> None:
        try:
            with MODEL_LOAD_LOCK:  # see segmenter.py
                started = time.perf_counter()
                import torch  # imported lazily: heavy, and not needed for tests
                from transformers import pipeline

                torch.set_num_threads(self.threads)
                self._pipe = pipeline("depth-estimation", model=self.model_id, device="cpu")
            self.status = "ready"
            log.info("Depth model loaded in %.1fs", time.perf_counter() - started)
        except Exception:  # measurement falls back to one scale per plane
            self.status = "failed"
            log.exception("Depth model failed to load; measuring with per-plane scales")
        finally:
            self._ready.set()

    def wait_until_loaded(self, timeout_s: float) -> bool:
        if self.status == "disabled":
            return False
        self._ready.wait(timeout_s)
        return self.ready

    def estimate(self, jpeg: bytes, rgb: np.ndarray) -> DepthGrid | None:
        if not self.ready:
            return None
        height, width = rgb.shape[:2]
        with self._lock:
            out = self._pipe(Image.fromarray(rgb))
        pred = out["predicted_depth"]
        depth = (pred[0] if pred.ndim == 3 else pred).float().numpy()
        scale = GRID_SIDE / max(width, height)
        cols, rows = max(8, round(width * scale)), max(8, round(height * scale))
        grid = np.asarray(Image.fromarray(depth).resize((cols, rows), Image.Resampling.BOX))
        cm = np.clip(np.rint(grid * 100), 30, 50_000).astype(np.uint16)
        return DepthGrid(cm, focal_norm_from_35mm(exif_focal_35mm(jpeg), width, height), self.model_id)


# --------------------------------------------------------------------------- #
# Sampling (mirrored exactly in frontend/src/lib/depth.ts)
# --------------------------------------------------------------------------- #
def _cell(grid: DepthGrid, x: float, y: float) -> tuple[int, int]:
    return min(grid.rows - 1, max(0, int(y * grid.rows))), min(grid.cols - 1, max(0, int(x * grid.cols)))


def _median_m(values: np.ndarray) -> float:
    return float(np.median(values)) / 100


def depth_on_line(grid: DepthGrid, p1: Point, p2: Point) -> float:
    """Distance (m) of a reference line: median of five samples along it."""
    samples = [grid.cm[_cell(grid, p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))] for t in LINE_SAMPLES]
    return _median_m(np.array(samples))


def _inside(poly: list[Point], xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Even-odd ray casting, vectorised; the same arithmetic as pointInPolygon in the browser."""
    inside = np.zeros(xs.shape, bool)
    n = len(poly)
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[i - 1]
        if yi == yj:
            continue  # a horizontal edge never satisfies the crossing condition
        crosses = (yi > ys) != (yj > ys)
        inside ^= crosses & (xs < (xj - xi) * (ys - yi) / (yj - yi) + xi)
    return inside


def region_depths(grid: DepthGrid, regions: list[Region]) -> dict[str, float]:
    """Distance (m) of each region: the median depth of the grid cells where it is the visible (top) layer.

    Using only visible cells keeps a wall's distance from being pulled forward by a pillar or
    railing in front of it. A region with no visible cell (tiny or fully covered) uses all its cells,
    then the cell at its bounding-box centre.
    """
    gx = (np.arange(grid.cols) + 0.5) / grid.cols
    gy = (np.arange(grid.rows) + 0.5) / grid.rows
    xs, ys = np.meshgrid(gx, gy)
    top = np.full((grid.rows, grid.cols), -1, np.int32)
    masks: dict[int, np.ndarray] = {}
    for i in layer_order(regions):
        mask = np.zeros_like(top, bool)
        for poly in regions[i].polygons:
            if len(poly) >= 3:
                mask |= _inside(poly, xs, ys)
        masks[i] = mask
        top[mask] = i

    out: dict[str, float] = {}
    for i, region in enumerate(regions):
        visible = grid.cm[top == i]
        if visible.size:
            out[region.id] = _median_m(visible)
        elif masks[i].any():
            out[region.id] = _median_m(grid.cm[masks[i]])
        else:
            pts = [p for poly in region.polygons for p in poly]
            if pts:
                cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
                cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
                out[region.id] = float(grid.cm[_cell(grid, cx, cy)]) / 100
    return out
