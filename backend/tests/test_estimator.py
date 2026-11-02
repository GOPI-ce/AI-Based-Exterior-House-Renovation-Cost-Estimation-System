import math

import pytest

from app.catalog import get_catalog
from app.schemas import Assignment, Plane, RateOverride, Region, ScaleReference
from app.services.estimator import choose_packs, estimate_project, format_packs
from app.services.report import format_inr

from .conftest import rect

catalog = get_catalog()


def assign(project, region_id, material_id, color=None):
    project.designs[0].assignments[region_id] = Assignment(material_id=material_id, color=color)


def m(material_id):
    return catalog.get(material_id)


def test_catalogue_is_consistent():
    ids = [x.id for x in catalog.materials]
    assert len(ids) == len(set(ids))
    for x in catalog.materials:
        assert x.rate_range[0] <= x.rate <= x.rate_range[1], x.id
        assert x.labour_range[0] <= x.labour_rate <= x.labour_range[1], x.id
        assert not x.palette or x.palette in catalog.palettes, x.id
    assert len(catalog.palettes["exterior"]) >= 100


def test_window_is_deducted_from_wall(project):
    assign(project, "wall-1", "ap_apex")
    line = estimate_project(project, catalog).lines[0]
    assert (line.gross, line.deductions, line.net) == pytest.approx((2500, 100, 2400))
    assert line.measured_from == "photo"


def test_paint_system_quantities_and_costs(project):
    assign(project, "wall-1", "ap_apex", "#EDE4D3")
    line = estimate_project(project, catalog).lines[0]
    top, primer = line.quantities
    assert top.quantity == pytest.approx(2400 * 2 / 90 * 1.05, abs=0.05)  # 56 L
    assert primer.quantity == pytest.approx(2400 / 100 * 1.05, abs=0.05)  # 25.2 L
    # Costed on the packs actually bought: 56 L top coat, 26 L primer.
    assert line.material_cost == pytest.approx(56 * 340 + 26 * 190)
    assert line.labour_cost == pytest.approx(2400 * 14)
    assert line.color_name == "Ivory White"


def test_elastomeric_system_adds_a_base_coat(project):
    assign(project, "wall-1", "ap_ultima_protek")
    names = [q.name for q in estimate_project(project, catalog).lines[0].quantities]
    assert names == ["Top coat", "Base coat", "Primer"]


def test_tiles_rounded_to_boxes_and_adhesive_bags(project):
    assign(project, "wall-1", "gvt_600x1200")
    line = estimate_project(project, catalog).lines[0]
    tiles, adhesive = line.quantities
    tile_sqft = 3.94 * 1.97
    assert tiles.quantity == math.ceil(2400 * 1.08 / tile_sqft)
    boxes = math.ceil(tiles.quantity / 2)
    assert f"{boxes} box" in tiles.note
    assert adhesive.quantity == math.ceil(2400 / 35)
    assert line.material_cost == pytest.approx(boxes * 2 * tile_sqft * 90 + adhesive.quantity * 480)


def test_acp_rounded_to_whole_sheets(project):
    assign(project, "wall-1", "acp_pvdf")
    assert estimate_project(project, catalog).lines[0].quantities[0].quantity == 84  # 2400 x 1.12 / 32


def test_pillar_in_front_of_wall_is_not_counted_twice(project):
    project.views[0].regions.append(Region(id="pillar-1", type="pillar", label="Pillar", polygons=[rect(0.4, 0, 0.5, 1)]))
    assign(project, "wall-1", "ap_apex")
    assign(project, "pillar-1", "stone_slate")
    lines = {l.region_id: l for l in estimate_project(project, catalog).lines}
    assert lines["pillar-1"].net == pytest.approx(500)
    assert lines["wall-1"].net == pytest.approx(2400 - 500)


def test_face_factor_multiplies_visible_area(project):
    project.views[0].regions.append(Region(id="gate-1", type="gate", label="Gate", polygons=[rect(0.6, 0.5, 0.8, 1)], face_factor=2))
    assign(project, "gate-1", "metal_enamel")
    assert estimate_project(project, catalog).lines[0].net == pytest.approx(200 * 250 * 0.01 * 2)


def test_railing_priced_per_running_foot(project):
    project.views[0].regions.append(Region(id="railing-1", type="railing", label="Rail", polygons=[rect(0.6, 0.1, 0.9, 0.2)]))
    assign(project, "railing-1", "rail_glass_frameless")
    line = estimate_project(project, catalog).lines[0]
    assert line.measure_unit == "rft" and line.net == pytest.approx(30)  # 300 px long
    assert line.material_cost == pytest.approx(30 * 1.03 * 1950)
    assert line.labour_cost == pytest.approx(30 * 350)


def test_overrides_win_and_zero_is_respected(project):
    project.views[0].regions[0].area_override_sqft = 1000
    assign(project, "wall-1", "brick_tiles")
    line = estimate_project(project, catalog).lines[0]
    assert line.net == 1000 and line.measured_from == "override"
    project.views[0].regions[0].area_override_sqft = 0
    assert estimate_project(project, catalog).lines[0].net == 0


def test_rate_overrides_are_applied(project):
    assign(project, "wall-1", "wpc_louvers")
    project.rate_overrides["wpc_louvers"] = RateOverride(material_rate=300, labour_rate=100)
    line = estimate_project(project, catalog).lines[0]
    assert line.material_cost == pytest.approx(2400 * 1.10 * 300)
    assert line.labour_cost == pytest.approx(2400 * 100)


def test_city_index_scales_rates(project):
    assign(project, "wall-1", "wpc_louvers")
    base = estimate_project(project, catalog).lines[0]
    project.settings.city_id = "mumbai"
    mumbai = estimate_project(project, catalog).lines[0]
    assert mumbai.labour_cost == pytest.approx(base.labour_cost * 1.3)
    assert mumbai.material_cost == pytest.approx(base.material_cost * 1.05)


def test_totals_contingency_then_gst_and_range(project):
    assign(project, "wall-1", "wpc_louvers")
    e = estimate_project(project, catalog)
    assert e.subtotal == pytest.approx(e.material_total + e.labour_total + e.site_total)
    assert e.contingency == pytest.approx(e.subtotal * 0.10)
    assert e.gst == pytest.approx((e.subtotal + e.contingency) * 0.18)
    assert e.grand_total == pytest.approx(e.subtotal + e.contingency + e.gst)
    assert e.low_total < e.grand_total < e.high_total
    line = e.lines[0]
    assert line.low < line.total < line.high


def test_site_items(project):
    project.settings.site_items = None  # catalogue defaults
    assign(project, "wall-1", "ap_apex")
    e = estimate_project(project, catalog)
    site = {s.id: s for s in e.site_lines}
    assert site["scaffolding"].amount == pytest.approx(2400 * 18)
    assert site["surface_prep"].amount == pytest.approx(2400 * 5)
    assert site["debris"].amount == pytest.approx(e.lines[0].total * 0.015)
    assert "removal" not in site  # nothing marked for removal
    project.views[0].regions[0].remove_existing = True
    site = {s.id: s for s in estimate_project(project, catalog).site_lines}
    assert site["removal"].amount == pytest.approx(2400 * 22)


def test_unscaled_view_warns_and_measures_zero(project):
    project.views[0].planes = []
    assign(project, "wall-1", "ap_apex")
    e = estimate_project(project, catalog)
    assert e.lines[0].net == 0 and e.lines[0].measured_from == "unscaled"
    assert any("no scale" in w for w in e.warnings)


def test_each_region_uses_its_own_plane(project):
    view = project.views[0]
    # A second plane where 100 px = 20 ft (twice as far from the camera).
    view.planes.append(Plane(id="far", name="House", references=[
        ScaleReference(id="r", name="Door", axis="free", p1=(0.0, 0.0), p2=(0.1, 0.0), real_length_ft=20)]))
    view.regions.append(Region(id="wall-2", type="wall", label="House wall", polygons=[rect(0.6, 0, 0.7, 0.2)], plane_id="far"))
    assign(project, "wall-2", "ap_apex")
    assert estimate_project(project, catalog).lines[0].net == pytest.approx(100 * 100 * 0.2**2)


def test_horizontal_and_vertical_scales_correct_foreshortening(project):
    view = project.views[0]
    view.planes = [Plane(id="side", name="Side", references=[
        ScaleReference(id="v", name="Door", axis="vertical", p1=(0.0, 0.0), p2=(0.0, 0.2), real_length_ft=10),  # 100 px = 10 ft
        ScaleReference(id="h", name="Wall width", axis="horizontal", p1=(0.0, 0.0), p2=(0.1, 0.0), real_length_ft=20),  # 100 px = 20 ft
    ])]
    view.regions = [Region(id="wall-1", type="wall", label="Side wall", polygons=[rect(0, 0, 0.1, 0.2)])]  # 100 x 100 px
    assign(project, "wall-1", "ap_apex")
    assert estimate_project(project, catalog).lines[0].net == pytest.approx(0.2 * 0.1 * 100 * 100)


def test_low_confidence_scale_is_flagged(project):
    plane = project.views[0].planes[0]
    plane.confirmed = False
    plane.references[0].source = "auto"
    plane.references[0].weight = 0.4
    assign(project, "wall-1", "ap_apex")
    e = estimate_project(project, catalog)
    assert e.planes[0].confidence < 0.5
    assert any("confidence is low" in w for w in e.warnings)


def test_unassigned_surfaces_are_reported_but_openings_are_not(project):
    e = estimate_project(project, catalog)
    assert e.unassigned_regions == ["Front: Front wall"]
    assert e.grand_total == 0


def test_unsuitable_material_gets_a_note(project):
    assign(project, "wall-1", "rail_ms")
    assert any("not usually used" in n for n in estimate_project(project, catalog).lines[0].notes)


@pytest.mark.parametrize(
    "litres,expected_total,expected_packs",
    [(0, 0, {}), (0.4, 1, {1: 1}), (5.2, 6, {4: 1, 1: 2}), (19.1, 20, {20: 1}), (46.5, 48, {20: 2, 4: 2}), (25.2, 26, {20: 1, 4: 1, 1: 2})],
)
def test_choose_packs(litres, expected_total, expected_packs):
    packs, total = choose_packs(litres, [20, 10, 4, 1])
    assert total == expected_total and packs == expected_packs


def test_format_helpers():
    assert format_packs({20: 2, 4: 1}) == "2 x 20 L + 1 x 4 L"
    assert format_inr(1234567.4) == "₹12,34,567"
    assert format_inr(999) == "₹999"


def test_region_ids_must_be_unique_across_photos(project):
    from pydantic import ValidationError

    from app.schemas import ProjectData

    second = project.views[0].model_copy(update={"id": "v2"})
    with pytest.raises(ValidationError, match="unique across photos"):
        ProjectData(views=[project.views[0], second])


def test_old_projects_with_flat_scales_are_migrated():
    from app.schemas import View

    view = View.model_validate({
        "id": "v", "name": "Front", "image_id": "i", "width": 100, "height": 100,
        "scales": [{"id": "s", "name": "Door", "method": "auto_door", "p1": [0, 0], "p2": [0, 0.5], "real_length_ft": 7, "confirmed": True}],
        "regions": [{"id": "w", "type": "wall", "label": "W", "polygons": [[[0, 0], [1, 0], [1, 1]]], "scale_id": "s"}],
    })
    assert view.planes[0].id == "s" and view.planes[0].confirmed
    assert view.planes[0].references[0].source == "auto"
    assert view.regions[0].plane_id == "s"


def test_waterproof_base_coat_not_charged_twice_on_elastomeric_systems(project):
    project.settings.site_items = ["waterproof_basecoat"]
    assign(project, "wall-1", "ap_ultima_protek")  # already includes a base coat
    assert not estimate_project(project, catalog).site_lines
    assign(project, "wall-1", "ap_apex")
    assert estimate_project(project, catalog).site_lines[0].amount == pytest.approx(2400 * 14)


def test_city_index_also_applies_to_primer_and_adhesive(project):
    assign(project, "wall-1", "stone_slate")
    base = estimate_project(project, catalog).lines[0].material_cost
    project.settings.city_id = "mumbai"
    assert estimate_project(project, catalog).lines[0].material_cost == pytest.approx(base * 1.05)


def test_plane_without_any_usable_reference_warns_even_if_confirmed(project):
    plane = project.views[0].planes[0]
    plane.references[0].enabled = False
    assign(project, "wall-1", "ap_apex")
    e = estimate_project(project, catalog)
    assert e.lines[0].net == 0
    assert any("no usable reference length" in w for w in e.warnings)


def test_lifetime_cost_counts_renewals_and_upkeep(project):
    project.settings.inflation_pct = 0
    assign(project, "wall-1", "ap_apex")  # repaint every 6 years: at years 6 and 12 within 15
    line = estimate_project(project, catalog).lines[0]
    assert line.future_cost == pytest.approx(line.total * (2 * 1.0 + 15 * 0.005), rel=1e-3)

    assign(project, "wall-1", "stone_kota")  # outlasts the horizon: upkeep only
    e = estimate_project(project, catalog)
    assert e.lines[0].future_cost == pytest.approx(e.lines[0].total * 15 * 0.003, rel=1e-3)
    assert e.lifetime_total == pytest.approx(e.grand_total + e.lifetime_future)
    assert e.lifetime_future == pytest.approx(e.lines[0].future_cost * 1.18, rel=1e-3)


def test_inflation_raises_future_costs(project):
    assign(project, "wall-1", "ap_apex")
    project.settings.inflation_pct = 0
    flat = estimate_project(project, catalog).lifetime_future
    project.settings.inflation_pct = 6
    assert estimate_project(project, catalog).lifetime_future > flat * 1.3
