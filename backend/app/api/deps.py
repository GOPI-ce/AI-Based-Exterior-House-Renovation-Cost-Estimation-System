"""Shared request dependencies.

Users are identified by an anonymous *workspace id*: a random UUID the browser
creates once and sends in the X-Workspace-Id header. It scopes projects per
browser without forcing a sign-up for a planning tool. (A production system would
put real authentication here; see docs/ARCHITECTURE.md.)
"""

from __future__ import annotations

import re

from fastapi import Header, HTTPException, Request

from app.config import get_settings

from app.services.depth import DepthEstimator
from app.services.gemini import SceneAnalyzer
from app.services.ratelimit import RateLimiter
from app.services.segmenter import Segmenter

WORKSPACE_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")
DEMO_OWNER = "demo"


def optional_workspace(x_workspace_id: str | None = Header(default=None)) -> str | None:
    if x_workspace_id and WORKSPACE_PATTERN.match(x_workspace_id) and x_workspace_id != DEMO_OWNER:
        return x_workspace_id
    return None


def require_workspace(x_workspace_id: str | None = Header(default=None)) -> str:
    workspace = optional_workspace(x_workspace_id)
    if workspace is None:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Workspace-Id header.")
    return workspace


def client_ip(request: Request) -> str:
    """The caller's IP for rate limiting. Behind N trusted proxies it is the N-th address from the right of
    X-Forwarded-For: those entries were added by our proxies, anything further left could be spoofed."""
    hops = get_settings().trusted_proxy_hops
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if hops and len(forwarded) >= hops:
        return forwarded[-hops]
    return request.client.host if request.client else "unknown"


def get_analyzer(request: Request) -> SceneAnalyzer:
    return request.app.state.analyzer


def get_segmenter(request: Request) -> Segmenter:
    return request.app.state.segmenter


def get_depth(request: Request) -> DepthEstimator:
    return request.app.state.depth


def get_limiter(request: Request) -> RateLimiter:
    return request.app.state.analyze_limiter


def get_ip_limiter(request: Request) -> RateLimiter:
    return request.app.state.analyze_ip_limiter
