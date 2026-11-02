"""Pre-computes the demo photo's depth map (app/demo/depth.json), so the demo is measured
distance-aware even on a server where the depth model is disabled.

    python -m scripts.build_demo_depth
"""

from __future__ import annotations

from app.config import get_settings
from app.services.demo import DEMO_DIR
from app.services.depth import DepthEstimator
from app.services.images import decode_jpeg


def main() -> None:
    estimator = DepthEstimator(get_settings().depth_model_id, threads=4)
    estimator._load()
    jpeg = (DEMO_DIR / "house.jpg").read_bytes()
    grid = estimator.estimate(jpeg, decode_jpeg(jpeg))
    if grid is None:
        raise SystemExit("The depth model is not available.")
    (DEMO_DIR / "depth.json").write_text(grid.to_json_text(), encoding="utf-8")
    print(f"depth.json: {grid.cols}x{grid.rows}, {grid.cm.min() / 100:.1f}-{grid.cm.max() / 100:.1f} m")


if __name__ == "__main__":
    main()
