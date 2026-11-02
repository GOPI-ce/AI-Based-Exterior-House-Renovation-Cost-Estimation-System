"""Computing, caching and loading depth maps (by image hash, like AI analyses)."""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import DepthCacheRow, ImageRow
from app.services.depth import DepthEstimator, DepthGrid
from app.services.images import decode_jpeg

log = logging.getLogger(__name__)
_compute_lock = threading.Lock()  # one depth computation at a time; others then find it cached


def cached_depth(db: Session, sha256: str) -> DepthGrid | None:
    row = db.get(DepthCacheRow, sha256)
    return DepthGrid.from_json_text(row.grid) if row else None


def ensure_depth(db: Session, image: ImageRow, estimator: DepthEstimator, wait_s: float = 0) -> tuple[DepthGrid | None, float | None]:
    """The image's depth map, computing and caching it if needed. Returns (grid, seconds spent computing)."""
    grid = cached_depth(db, image.sha256)
    if grid is not None:
        return grid, None
    if wait_s:
        estimator.wait_until_loaded(wait_s)
    if not estimator.ready:
        return None, None
    with _compute_lock:
        db.expire_all()
        grid = cached_depth(db, image.sha256)  # another request may have just computed it
        if grid is not None:
            return grid, None
        started = time.perf_counter()
        try:
            grid = estimator.estimate(image.jpeg, decode_jpeg(image.jpeg))
        except Exception:  # measurement still works without depth
            log.exception("Depth estimation failed for %s", image.sha256[:12])
            return None, None
        if grid is None:
            return None, None
        try:
            db.add(DepthCacheRow(sha256=image.sha256, grid=grid.to_json_text()))
            db.commit()
        except IntegrityError:  # stored meanwhile by another server process: same photo, same result
            db.rollback()
        return grid, round(time.perf_counter() - started, 2)


def depths_for(db: Session, image_ids: list[str]) -> dict[str, DepthGrid]:
    """Cached depth maps of the given images (missing ones are simply left out)."""
    ids = list(dict.fromkeys(image_ids))
    if not ids:
        return {}
    shas = dict(db.execute(select(ImageRow.id, ImageRow.sha256).where(ImageRow.id.in_(ids))).all())
    rows = {r.sha256: r for r in db.scalars(select(DepthCacheRow).where(DepthCacheRow.sha256.in_(set(shas.values()))))}
    return {image_id: DepthGrid.from_json_text(rows[sha].grid) for image_id, sha in shas.items() if sha in rows}
