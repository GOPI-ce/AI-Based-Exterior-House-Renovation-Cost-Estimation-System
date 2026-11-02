"""Photo upload, retrieval and AI analysis."""

from __future__ import annotations

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DEMO_OWNER, get_analyzer, get_ip_limiter, get_limiter, get_segmenter, require_workspace
from app.config import get_settings
from app.db import AnalysisCacheRow, ImageRow, get_db
from app.schemas import AnalysisResult, ImageInfo
from app.services.analysis import analyze_photo
from app.services.gemini import GeminiUnavailable, SceneAnalyzer
from app.services.images import ImageRejected, decode_jpeg, prepare_upload
from app.services.quality import assess_quality
from app.services.ratelimit import RateLimiter
from app.services.segmenter import Segmenter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("", status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    workspace: str = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> ImageInfo:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    raw = await file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise HTTPException(413, detail={"message": f"The photo is larger than {settings.max_upload_mb} MB."})

    try:
        prepared = prepare_upload(raw, settings.max_image_side)
    except ImageRejected as exc:
        raise HTTPException(415, detail={"message": str(exc)}) from exc

    quality = assess_quality(prepared.rgb)
    if not quality.ok:
        raise HTTPException(422, detail={"message": "This photo cannot be used.", "quality": quality.model_dump()})

    sha = hashlib.sha256(prepared.jpeg).hexdigest()
    existing = db.scalar(select(ImageRow).where(ImageRow.sha256 == sha, ImageRow.owner_id == workspace))
    if existing:
        return ImageInfo(image_id=existing.id, width=existing.width, height=existing.height, quality=quality)

    row = ImageRow(
        id=uuid.uuid4().hex,
        owner_id=workspace,
        sha256=sha,
        width=prepared.width,
        height=prepared.height,
        jpeg=prepared.jpeg,
        quality=quality.model_dump_json(),
    )
    db.add(row)
    db.commit()
    return ImageInfo(image_id=row.id, width=row.width, height=row.height, quality=quality)


@router.get("/{image_id}")
def get_image(image_id: str, db: Session = Depends(get_db)) -> Response:
    row = db.get(ImageRow, image_id)
    if row is None:
        raise HTTPException(404, detail={"message": "Image not found."})
    return Response(
        content=row.jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.post("/{image_id}/analyze")
def analyze_image(
    image_id: str,
    request: Request,
    workspace: str = Depends(require_workspace),
    db: Session = Depends(get_db),
    analyzer: SceneAnalyzer = Depends(get_analyzer),
    segmenter: Segmenter = Depends(get_segmenter),
    limiter: RateLimiter = Depends(get_limiter),
    ip_limiter: RateLimiter = Depends(get_ip_limiter),
) -> AnalysisResult:
    """Detect building components. A plain `def`, so FastAPI runs it in a worker thread."""
    row = db.get(ImageRow, image_id)
    if row is None:
        raise HTTPException(404, detail={"message": "Image not found."})

    cached = db.get(AnalysisCacheRow, row.sha256)
    if cached:
        try:
            return AnalysisResult.model_validate_json(cached.result)
        except ValidationError:
            log.info("Cached analysis for %s is from an older pipeline; re-analysing", row.sha256[:12])

    if row.owner_id not in (workspace, DEMO_OWNER):
        raise HTTPException(403, detail={"message": "Only the person who uploaded this photo can run AI analysis on it."})

    # The server runs behind a proxy with --proxy-headers, so this is the real client IP.
    client_ip = request.client.host if request.client else "unknown"
    if not ip_limiter.allow(client_ip) or not limiter.allow(workspace):
        raise HTTPException(429, detail={"message": "AI analysis limit reached for this hour. You can still draw regions manually."})

    try:
        result = analyze_photo(row.jpeg, decode_jpeg(row.jpeg), analyzer, segmenter)
    except GeminiUnavailable as exc:
        log.warning("Analysis unavailable: %s", exc)
        raise HTTPException(503, detail={"message": "AI detection is busy right now. Try again in a minute, or draw the regions manually."}) from exc

    # Cache only complete results: box-only output (SAM still loading) should be retried later.
    if result.regions and (result.pipeline.get("sam_model") != "not used" or not segmenter.enabled):
        db.merge(AnalysisCacheRow(sha256=row.sha256, result=result.model_dump_json()))
        db.commit()
    return result
