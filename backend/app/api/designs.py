"""AI budget designer (see services/designer.py)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import DEMO_OWNER, client_ip, get_analyzer, get_ip_limiter, get_limiter, require_workspace
from app.catalog import get_catalog
from app.db import ImageRow, get_db
from app.schemas import DesignSuggestion, DesignSuggestRequest
from app.services.depth_store import depths_for
from app.services.designer import MAX_AI_ROUNDS, suggest_design
from app.services.gemini import GeminiUnavailable, SceneAnalyzer
from app.services.ratelimit import RateLimiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/designs", tags=["designs"])


@router.post("/suggest")
def suggest(
    body: DesignSuggestRequest,
    request: Request,
    workspace: str = Depends(require_workspace),
    db: Session = Depends(get_db),
    analyzer: SceneAnalyzer = Depends(get_analyzer),
    limiter: RateLimiter = Depends(get_limiter),
    ip_limiter: RateLimiter = Depends(get_ip_limiter),
) -> DesignSuggestion:
    """A full design within the budget. A plain `def`, so FastAPI runs it in a worker thread."""
    # A suggestion can take up to MAX_AI_ROUNDS model calls, so it is charged as that many analyses.
    ip = client_ip(request)
    if not all(ip_limiter.allow(ip) and limiter.allow(workspace) for _ in range(MAX_AI_ROUNDS)):
        raise HTTPException(429, detail={"message": "AI limit reached for this hour. You can still choose materials yourself."})

    photo = db.get(ImageRow, body.data.views[0].image_id) if body.data.views else None
    if photo is not None and photo.owner_id not in (workspace, DEMO_OWNER):
        photo = None  # only your own (or the demo) photo is sent to the AI
    try:
        return suggest_design(body.data, get_catalog(), body.budget, body.style, analyzer,
                              photo.jpeg if photo else None, depths_for(db, [v.image_id for v in body.data.views]))
    except ValueError as exc:
        raise HTTPException(422, detail={"message": str(exc)}) from exc
    except GeminiUnavailable as exc:
        log.warning("AI designer unavailable: %s", exc)
        raise HTTPException(503, detail={"message": "The AI designer is busy right now. Try again in a minute."}) from exc
