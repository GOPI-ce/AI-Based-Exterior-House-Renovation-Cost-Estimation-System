"""Cost estimation and PDF report generation (stateless: they work on unsaved edits too)."""

from __future__ import annotations

import base64
import binascii
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.catalog import get_catalog
from app.db import ImageRow, get_db
from app.schemas import Estimate, EstimateRequest, ProjectData
from app.services.depth_store import depths_for
from app.services.estimator import estimate_project
from app.services.report import build_report

router = APIRouter(prefix="/api", tags=["estimate"])

DATA_URL = re.compile(r"^data:image/(png|jpeg|webp);base64,(.+)$", re.S)
MAX_RENDER_BYTES = 8 * 1024 * 1024
MAX_RENDER_PIXELS = 4096 * 4096


class ReportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    data: ProjectData
    design_id: str | None = None
    renders: dict[str, str] = {}  # view id -> data URL of the redesigned image


@router.post("/estimate")
def estimate(body: EstimateRequest, db: Session = Depends(get_db)) -> Estimate:
    return estimate_project(body.data, get_catalog(), body.design_id, _depths(db, body.data))


@router.post("/report")
def report(body: ReportRequest, db: Session = Depends(get_db)) -> Response:
    catalog = get_catalog()
    result = estimate_project(body.data, catalog, body.design_id, _depths(db, body.data))

    originals: dict[str, bytes] = {}
    for view in body.data.views:
        row = db.get(ImageRow, view.image_id)
        if row is not None:
            originals[view.id] = row.jpeg

    view_ids = {v.id for v in body.data.views}
    renders = {view_id: _decode_render(url) for view_id, url in body.renders.items() if view_id in view_ids}
    pdf = build_report(body.name, body.data, result, catalog, originals, renders)
    filename = re.sub(r"[^A-Za-z0-9_-]+", "-", body.name).strip("-")[:60] or "renovation-plan"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}-estimate.pdf"'},
    )


def _depths(db: Session, data: ProjectData):
    return depths_for(db, [v.image_id for v in data.views])


def _decode_render(data_url: str) -> bytes:
    """Validate an image data URL from the browser and return it as JPEG bytes."""
    match = DATA_URL.match(data_url)
    if not match:
        raise HTTPException(422, detail={"message": "Rendered images must be PNG/JPEG/WebP data URLs."})
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except binascii.Error as exc:
        raise HTTPException(422, detail={"message": "Rendered image is not valid base64."}) from exc
    if len(raw) > MAX_RENDER_BYTES:
        raise HTTPException(413, detail={"message": "Rendered image is too large."})
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > MAX_RENDER_PIXELS:  # checked before decoding any pixels
                raise HTTPException(413, detail={"message": "Rendered image has too many pixels."})
            out = io.BytesIO()
            image.convert("RGB").save(out, format="JPEG", quality=88)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, detail={"message": "Rendered image could not be decoded."}) from exc
