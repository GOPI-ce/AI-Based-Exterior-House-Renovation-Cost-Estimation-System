"""Regenerate the demo project from a photo using the real AI pipeline.

    python -m scripts.build_demo path/to/photo.jpg

Writes app/demo/house.jpg and app/demo/analysis.json. The curated designs in
app/demo/project.json are then built from that analysis by scripts/demo_designs.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.config import get_settings
from app.services.analysis import analyze_photo
from app.services.demo import DEMO_DIR
from app.services.gemini import SceneAnalyzer
from app.services.images import prepare_upload
from app.services.segmenter import Segmenter


def main(photo: Path) -> None:
    settings = get_settings()
    prepared = prepare_upload(photo.read_bytes(), settings.max_image_side)
    segmenter = Segmenter(settings.sam_model_id, settings.sam_threads)
    segmenter.load_in_background()
    analyzer = SceneAnalyzer(settings.gemini_api_key, settings.gemini_model_list, settings.gemini_timeout_s)

    result = analyze_photo(prepared.jpeg, prepared.rgb, analyzer, segmenter)

    DEMO_DIR.mkdir(exist_ok=True)
    (DEMO_DIR / "house.jpg").write_bytes(prepared.jpeg)
    (DEMO_DIR / "analysis.json").write_text(result.model_dump_json(indent=1), encoding="utf-8")
    print(f"{len(result.regions)} regions, pipeline: {result.pipeline}")
    for r in result.regions:
        print(f"  {r.id:12s} {r.source:6s} {r.label}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
