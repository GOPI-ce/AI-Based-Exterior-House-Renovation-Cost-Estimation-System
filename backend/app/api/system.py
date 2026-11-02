from fastapi import APIRouter, Depends

from app.api.deps import get_analyzer, get_segmenter
from app.catalog import Catalog, get_catalog
from app.services.gemini import SceneAnalyzer
from app.services.segmenter import Segmenter

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(analyzer: SceneAnalyzer = Depends(get_analyzer), segmenter: Segmenter = Depends(get_segmenter)) -> dict:
    return {
        "status": "ok",
        "gemini": "configured" if analyzer.available else "missing_api_key",
        "gemini_models": analyzer.models,
        "sam": segmenter.status,
    }


@router.get("/catalog")
def catalog() -> Catalog:
    return get_catalog()
