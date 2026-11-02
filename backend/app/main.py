"""FastAPI application: wires settings, database, AI services and routes together."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api import designs, estimate, images, projects, system
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.services.demo import seed_demo
from app.services.depth import DepthEstimator
from app.services.gemini import SceneAnalyzer
from app.services.ratelimit import RateLimiter
from app.services.segmenter import Segmenter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    with SessionLocal() as db:
        seed_demo(db)

    app.state.analyzer = SceneAnalyzer(settings.gemini_api_key, settings.gemini_model_list, settings.gemini_timeout_s)
    app.state.segmenter = Segmenter(settings.sam_model_id, settings.sam_threads, enabled=settings.enable_sam)
    app.state.segmenter.load_in_background()
    app.state.depth = DepthEstimator(settings.depth_model_id, settings.sam_threads, enabled=settings.enable_depth)
    app.state.depth.load_in_background()
    app.state.analyze_limiter = RateLimiter(settings.analyze_limit_per_hour, window_s=3600)
    app.state.analyze_ip_limiter = RateLimiter(settings.analyze_ip_limit_per_hour, window_s=3600)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FacadeAI API",
        description="AI exterior renovation planning: structure detection, area & quantity estimation, costing and reports.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    for module in (system, images, projects, estimate, designs):
        app.include_router(module.router)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"name": "FacadeAI API", "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
