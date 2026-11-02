import cv2
import numpy as np
import pytest

from app.schemas import Plane, Region, ScaleReference, View
from app.services.analysis import _cue_line, _dedupe, _plausible_cue
from app.services.gemini import GeminiComponent, box_to_normalised
from app.services.geometry import mask_to_polygons, measure_regions
from app.services.quality import assess_quality
from app.services.scale import DetectedCue, auto_planes, plane_scale

from .conftest import rect, textured_image


def test_mask_to_polygons_simplifies_a_rectangle():
    mask = np.zeros((200, 400), bool)
    mask[50:150, 100:300] = True
    polygons = mask_to_polygons(mask)
    assert len(polygons) == 1
    assert 4 <= len(polygons[0]) <= 6
    xs = [p[0] for p in polygons[0]]
    assert min(xs) == pytest.approx(0.25, abs=0.01) and max(xs) == pytest.approx(0.75, abs=0.01)


def test_mask_to_polygons_drops_speckles_and_keeps_parts():
    mask = np.zeros((200, 400), bool)
    mask[20:180, 20:150] = True  # big part
    mask[20:180, 250:380] = True  # second part (wall split by a pillar)
    mask[5:7, 200:202] = True  # speckle
    assert len(mask_to_polygons(mask)) == 2


def test_layering_deducts_higher_layers_only():
    regions = [
        Region(id="w", type="wall", label="w", polygons=[rect(0, 0, 1, 1)]),
        Region(id="d", type="door", label="d", polygons=[rect(0, 0, 0.5, 0.5)]),
    ]
    m = measure_regions(regions, 100, 100)
    assert m["w"].gross_px2 == pytest.approx(10000)
    assert m["w"].net_px2 == pytest.approx(7500)
    assert m["d"].net_px2 == pytest.approx(2500)


def _view(planes, regions=()):
    return View(id="v", name="V", image_id="i", width=1000, height=1000, planes=planes, regions=list(regions))


def _ref(name, length_px, real_ft, axis="vertical", source="manual", weight=1.0):
    return ScaleReference(id=name, name=name, axis=axis, p1=(0.5, 0.0), p2=(0.5, length_px / 1000), real_length_ft=real_ft,
                          source=source, weight=weight)


def test_consensus_rejects_an_outlier_cue():
    # Door and car agree on 0.07 ft/px; a misread 'person' says 0.14 and is dropped.
    plane = Plane(id="p", name="Front", references=[
        _ref("Door", 100, 7, source="auto"), _ref("Car", 71.4, 5, source="auto"), _ref("Person", 40, 5.6, source="auto")])
    scale = plane_scale(plane, _view([plane]))
    assert scale.ft_per_px_y == pytest.approx(0.07, rel=0.01)
    assert scale.cues_rejected == ["Person"]
    assert scale.confidence < 0.9  # automatic, unconfirmed


def test_manual_and_confirmed_scales_are_trusted_more():
    auto = Plane(id="a", name="A", references=[_ref("Door", 100, 7, source="auto", weight=0.9)])
    manual = Plane(id="m", name="M", references=[_ref("Tape", 100, 7)])
    confirmed = Plane(id="c", name="C", confirmed=True, references=[_ref("Door", 100, 7, source="auto", weight=0.9)])
    view = _view([auto, manual, confirmed])
    assert plane_scale(auto, view).confidence < plane_scale(manual, view).confidence <= plane_scale(confirmed, view).confidence


def test_plane_without_cues_borrows_with_lower_confidence():
    front = Plane(id="front", name="Front", references=[_ref("Door", 100, 7)])
    side = Plane(id="side", name="Side", fallback_plane_id="front")
    view = _view([front, side])
    borrowed = plane_scale(side, view)
    assert borrowed.ft_per_px_y == pytest.approx(0.07)
    assert borrowed.borrowed_from == "Front"
    assert borrowed.confidence == pytest.approx(plane_scale(front, view).confidence * 0.5)


def test_auto_planes_from_cues_and_region_planes():
    regions = [
        Region(id="w1", type="wall", label="w", polygons=[rect(0.1, 0.1, 0.5, 0.6)], plane_id="house_front"),
        Region(id="w2", type="wall", label="c", polygons=[rect(0.0, 0.7, 1.0, 1.0)], plane_id="boundary"),
    ]
    cues = [DetectedCue(kind="door", box=(0.3, 0.4, 0.35, 0.55), plane="house_front", real_height_ft=None, confidence=0.9, label="Main door")]
    planes = auto_planes(regions, cues, storeys=2, width=1000, height=1000)
    by_id = {p.id: p for p in planes}
    assert by_id["house_front"].references[0].real_length_ft == 7  # door default
    assert by_id["boundary"].references == [] and by_id["boundary"].fallback_plane_id == "house_front"


def test_cue_line_uses_typical_column_height_of_a_slanted_mask():
    # A railing seen in perspective: a band 40 px tall that slopes down 200 px across the box.
    mask = np.zeros((1000, 1000), bool)
    for x in range(200, 800):
        top = 300 + (x - 200) // 3
        mask[top:top + 40, x] = True
    box = (0.2, 0.3, 0.8, 0.54)  # its bounding box is 240 px tall
    (x1, y1), (x2, y2) = _cue_line(mask, box)
    assert (y2 - y1) * 1000 == pytest.approx(40, abs=1)


def test_implausible_cues_are_rejected():
    assert _plausible_cue("door", (0.4, 0.4, 0.45, 0.52), 1000, 1000)  # 50 x 120 px: door-shaped
    assert not _plausible_cue("door", (0.4, 0.4, 0.6, 0.45), 1000, 1000)  # wider than tall
    assert not _plausible_cue("storey", (0.17, 0.48, 0.18, 0.57), 1000, 1000)  # a sliver
    assert not _plausible_cue("person", (0.5, 0.5, 0.51, 0.51), 1000, 1000)  # too small


def test_gemini_box_normalisation_and_dedupe():
    assert box_to_normalised([100, 200, 300, 400]) == (0.2, 0.1, 0.4, 0.3)
    assert box_to_normalised([300, 400, 100, 200]) == (0.2, 0.1, 0.4, 0.3)  # swapped corners
    assert box_to_normalised([100, 100, 101, 101]) is None  # degenerate
    comps = [
        GeminiComponent(type="window", label="a", box_2d=[100, 100, 300, 300]),
        GeminiComponent(type="window", label="b", box_2d=[101, 101, 300, 300]),  # duplicate
        GeminiComponent(type="railing", label="c", box_2d=[100, 100, 300, 300]),  # same box, other type: kept
    ]
    assert [c.label for c in _dedupe(comps)] == ["a", "c"]


def test_quality_accepts_a_sharp_photo():
    assert assess_quality(textured_image()).ok


@pytest.mark.parametrize(
    "transform,code",
    [
        (lambda im: cv2.GaussianBlur(im, (41, 41), 0), "too_blurry"),
        (lambda im: (im * 0.15).astype(np.uint8), "too_dark"),
        (lambda im: np.full_like(im, 128), "low_contrast"),
        (lambda im: cv2.resize(im, (400, 300)), "too_small"),
    ],
)
def test_quality_rejects_bad_photos(transform, code):
    report = assess_quality(transform(textured_image()))
    assert not report.ok
    assert code in [i.code for i in report.issues]


def test_cues_implying_an_impossible_building_are_switched_off():
    # Front walls span 500 px of a 1000 px photo; a 2-storey house is ~23 ft, i.e. ~21.7 px/ft.
    regions = [Region(id="w", type="wall", label="w", polygons=[rect(0.2, 0.2, 0.8, 0.7)], plane_id="house_front")]
    cues = [
        DetectedCue(kind="railing", box=(0.4, 0.5, 0.5, 0.53), plane="house_front", real_height_ft=3.5, confidence=0.9, label="Railing"),  # 30 px -> 58 ft building
        DetectedCue(kind="door", box=(0.45, 0.55, 0.5, 0.70), plane="house_front", real_height_ft=7, confidence=0.9, label="Door"),  # 150 px -> 23 ft
    ]
    planes = auto_planes(regions, cues, storeys=2, width=1000, height=1000)
    front = next(p for p in planes if p.id == "house_front")
    refs = {r.name.split(" (")[0]: r for r in front.references}
    assert not refs["Railing"].enabled and "implausible" in refs["Railing"].name
    assert refs["Door"].enabled and refs["Building height"].enabled
    view = View(id="v", name="V", image_id="i", width=1000, height=1000, planes=planes, regions=regions)
    assert 1 / plane_scale(front, view).ft_per_px_y == pytest.approx(21.4, abs=0.6)


def test_cues_with_the_same_name_each_count():
    one = Plane(id="a", name="A", references=[_ref("Door", 100, 7, source="auto", weight=0.9)])
    two = Plane(id="b", name="B", references=[
        _ref("Door", 100, 7, source="auto", weight=0.9),
        ScaleReference(id="d2", name="Door", axis="vertical", p1=(0.2, 0.0), p2=(0.2, 0.1), real_length_ft=7, source="auto", weight=0.9)])
    view = _view([one, two])
    assert plane_scale(two, view).confidence > plane_scale(one, view).confidence
