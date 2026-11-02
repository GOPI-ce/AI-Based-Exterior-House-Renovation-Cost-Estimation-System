"""Distance-aware measurement: depth sampling, depth-normalised scales and the depth API."""

import io

import numpy as np
import pytest
from PIL import Image

from app.catalog import get_catalog
from app.schemas import Assignment, Plane, Region, ScaleReference, View
from app.services.depth import DepthGrid, depth_on_line, focal_norm_from_35mm, region_depths
from app.services.estimator import estimate_project
from app.services.images import prepare_upload
from app.services.scale import ViewDepth, plane_scale, region_ft_per_px

from .conftest import rect, textured_image


def grid(left_m: float, right_m: float, cols: int = 40, rows: int = 20) -> DepthGrid:
    """Left half of the photo at `left_m` metres, right half at `right_m`."""
    cm = np.full((rows, cols), round(left_m * 100), np.uint16)
    cm[:, cols // 2:] = round(right_m * 100)
    return DepthGrid(cm, focal_norm=0.75, model="test")


def ref(rid, x, y0, y1, real_ft, source="manual", weight=1.0):
    return ScaleReference(id=rid, name=rid, axis="vertical", p1=(x, y0), p2=(x, y1), real_length_ft=real_ft, source=source, weight=weight)


def view(planes, regions):
    return View(id="v", name="V", image_id="img", width=1000, height=1000, planes=planes, regions=regions)


def test_grid_round_trips_and_samples_lines():
    g = grid(10, 20)
    assert DepthGrid.from_json_text(g.to_json_text()).cm.tolist() == g.cm.tolist()
    assert depth_on_line(g, (0.2, 0.1), (0.2, 0.9)) == 10
    assert depth_on_line(g, (0.7, 0.1), (0.7, 0.9)) == 20


def test_region_distance_uses_only_its_visible_part():
    # A wall spanning both halves, with a pillar covering most of its far (right) half.
    regions = [
        Region(id="wall", type="wall", label="w", polygons=[rect(0.0, 0.0, 0.7, 1.0)]),
        Region(id="pillar", type="pillar", label="p", polygons=[rect(0.5, 0.0, 1.0, 1.0)]),
    ]
    d = region_depths(grid(10, 20), regions)
    assert d == {"wall": 10, "pillar": 20}


def test_cues_at_different_distances_agree_once_normalised():
    # The same 7 ft door seen at 10 m (100 px) and at 20 m (50 px): one consistent scale, no outlier.
    plane = Plane(id="p", name="Front", references=[
        ref("near", 0.2, 0.1, 0.2, 7), ref("far", 0.7, 0.1, 0.15, 7), ref("other", 0.25, 0.3, 0.4, 7)])
    v = view([plane], [])
    scale = plane_scale(plane, v, ViewDepth.build(grid(10, 20), v))
    assert scale.spread == pytest.approx(0)
    assert scale.cues_rejected == []
    assert scale.ref_depth_m == 10
    assert scale.at_depth(20) == pytest.approx((0.14, 0.14))  # twice as far: twice the feet per pixel


def test_far_surface_is_measured_at_its_own_distance():
    plane = Plane(id="p", name="Front", confirmed=True, references=[ref("door", 0.2, 0.1, 0.2, 7)])  # 0.07 ft/px at 10 m
    regions = [Region(id="far-wall", type="wall", label="Far wall", polygons=[rect(0.6, 0.0, 0.9, 0.5)])]  # 300 x 500 px at 20 m
    v = view([plane], regions)
    data_flat = estimate(v, None)
    data_depth = estimate(v, grid(10, 20))
    assert data_flat.lines[0].net == pytest.approx(300 * 500 * 0.07**2, rel=1e-3)
    assert data_depth.lines[0].net == pytest.approx(300 * 500 * 0.14**2, rel=1e-3)  # 4x the area
    assert data_depth.lines[0].distance_m == 20
    assert data_depth.planes[0].ref_depth_m == 10


def estimate(v, depth):
    from app.schemas import Design, ProjectData, ProjectSettings

    data = ProjectData(views=[v], designs=[Design(id="d", name="D", assignments={"far-wall": Assignment(material_id="ap_apex")})],
                       active_design_id="d", settings=ProjectSettings(site_items=[]))
    return estimate_project(data, get_catalog(), depths={"img": depth} if depth else None)


def test_borrowed_scale_is_distance_corrected_and_trusted_more():
    front = Plane(id="front", name="Front", references=[ref("door", 0.2, 0.1, 0.2, 7)])
    side = Plane(id="side", name="Side", fallback_plane_id="front")
    regions = [Region(id="side-wall", type="wall", label="s", polygons=[rect(0.6, 0.0, 0.9, 0.5)], plane_id="side")]
    v = view([front, side], regions)
    depth = ViewDepth.build(grid(10, 20), v)
    scales = {p.id: plane_scale(p, v, depth) for p in v.planes}
    _, scale, fpp = region_ft_per_px(regions[0], v, scales, depth)
    assert fpp == pytest.approx((0.14, 0.14))
    assert scale.confidence == pytest.approx(plane_scale(front, v, depth).confidence * 0.8)
    assert plane_scale(side, v).confidence == pytest.approx(plane_scale(front, v).confidence * 0.5)


def test_camera_only_scale_when_there_is_no_reference():
    plane = Plane(id="p", name="Front")
    regions = [Region(id="w", type="wall", label="w", polygons=[rect(0.0, 0.0, 0.4, 1.0)])]
    v = view([plane], regions)
    assert plane_scale(plane, v) is None
    scale = plane_scale(plane, v, ViewDepth.build(grid(10, 20), v))
    # Pinhole camera: 10 m * 3.28 ft/m / (0.75 * 1000 px) = 0.0437 ft per px.
    assert scale.ft_per_px_y == pytest.approx(10 * 3.28084 / 750)
    assert scale.confidence == 0.3


def test_disagreeing_planes_are_flagged():
    # Both planes see a "7 ft" object at the same distance, but one covers twice the pixels.
    a = Plane(id="a", name="Front", references=[ref("door", 0.2, 0.1, 0.2, 7)])
    b = Plane(id="b", name="Compound", references=[ref("gate", 0.3, 0.1, 0.3, 7)])
    regions = [Region(id="far-wall", type="wall", label="w", polygons=[rect(0.0, 0.0, 0.1, 0.1)])]
    v = view([a, b], regions)
    assert any("disagree by 100%" in w for w in estimate(v, grid(10, 10)).warnings)
    assert not any("disagree" in w for w in estimate(v, None).warnings)  # without depth, planes may legitimately differ


def test_focal_length_from_exif_and_default():
    assert focal_norm_from_35mm(26, 4000, 3000) == pytest.approx(26 / 36)
    assert focal_norm_from_35mm(26, 3000, 4000) == pytest.approx(26 / 36 * 4 / 3)  # portrait: 36 mm is the height
    assert focal_norm_from_35mm(None, 4000, 3000) == focal_norm_from_35mm(26, 4000, 3000)


def test_upload_keeps_only_the_focal_length_metadata():
    exif = Image.Exif()
    exif.get_ifd(0x8769)[0xA405] = 28
    exif[0x0110] = "Phone model"
    buf = io.BytesIO()
    Image.fromarray(textured_image()).save(buf, format="JPEG", exif=exif)
    kept = Image.open(io.BytesIO(prepare_upload(buf.getvalue(), 1600).jpeg)).getexif()
    assert kept.get_ifd(0x8769).get(0xA405) == 28
    assert 0x0110 not in kept


def test_camera_only_scale_is_not_borrowed_or_blamed():
    # No references anywhere: each plane gets its own camera-only scale, never a "borrowed" one,
    # and the consistency check does not accuse a reference that doesn't exist.
    front = Plane(id="front", name="Front")
    side = Plane(id="side", name="Side", fallback_plane_id="front")
    regions = [Region(id="w", type="wall", label="w", polygons=[rect(0.0, 0.0, 0.4, 1.0)]),
               Region(id="s", type="wall", label="s", polygons=[rect(0.6, 0.0, 0.9, 1.0)], plane_id="side")]
    v = view([front, side], regions)
    scale = plane_scale(side, v, ViewDepth.build(grid(10, 20), v))
    assert scale.camera_only and scale.borrowed_from is None and scale.ref_depth_m == 20

    referenced = Plane(id="ref", name="Gate", references=[ref("gate", 0.2, 0.1, 0.3, 7)])  # disagrees with the camera
    v2 = view([referenced, side], regions)
    side.fallback_plane_id = None
    assert not any("disagree" in w for w in estimate(v2, grid(10, 20)).warnings)
