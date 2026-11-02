import os
import tempfile

# Configure the app for tests *before* any app module is imported.
_tmp = tempfile.mkdtemp(prefix="facade-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ENABLE_SAM"] = "false"
os.environ["ENABLE_DEPTH"] = "false"
os.environ["GEMINI_API_KEY"] = ""

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from app.schemas import Design, Plane, ProjectData, ProjectSettings, Region, ScaleReference, View  # noqa: E402


def rect(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


@pytest.fixture
def scaled_view() -> View:
    """1000 x 500 px photo where 100 px = 10 ft, i.e. 0.1 ft per pixel."""
    return View(
        id="v1",
        name="Front",
        image_id="img",
        width=1000,
        height=500,
        planes=[Plane(id="front", name="House front", confirmed=True, references=[
            ScaleReference(id="s1", name="Gate", axis="free", p1=(0.0, 0.5), p2=(0.1, 0.5), real_length_ft=10),
        ])],
        regions=[
            # 500 x 500 px wall = 2500 sqft, with a 100 x 100 px window (100 sqft) inside.
            Region(id="wall-1", type="wall", label="Front wall", polygons=[rect(0, 0, 0.5, 1)]),
            Region(id="window-1", type="window", label="Window", polygons=[rect(0.1, 0.2, 0.2, 0.4)]),
        ],
    )


@pytest.fixture
def project(scaled_view: View) -> ProjectData:
    # Site items off by default here, so line-level tests check one thing at a time.
    return ProjectData(views=[scaled_view], designs=[Design(id="d1", name="D1")], active_design_id="d1",
                       settings=ProjectSettings(site_items=[]))


def textured_image(width: int = 900, height: int = 600, seed: int = 0) -> np.ndarray:
    """A sharp, well-exposed synthetic 'photo' that passes the quality checks."""
    rng = np.random.default_rng(seed)
    base = rng.integers(60, 200, size=(height // 10, width // 10, 3), dtype=np.uint8)
    return np.kron(base, np.ones((10, 10, 1), dtype=np.uint8))
