"""Build app/demo/project.json from the AI analysis plus curated scale references and designs.

    python -m scripts.demo_designs

The regions are what the pipeline detected (scripts/build_demo.py), with the review a user
would do in the Surfaces step (two outlines corrected, one porch column added). The house front's
reference length was placed by hand and confirmed, as a user would in the Scale step; the compound
wall is closer to the camera and borrows that scale, corrected for its distance by the depth map.
"""

from __future__ import annotations

import json

from app.schemas import AnalysisResult, Assignment, Design, Plane, ProjectData, Region, ScaleReference, View
from app.config import get_settings
from app.services.demo import DEMO_DIR, DEMO_IMAGE_ID

W, H = 1280, 960

PLANES = [
    Plane(id="house_front", name="House front", kind="house_front", confirmed=True, references=[
        ScaleReference(id="ref-railing", name="Balcony glass railing (3.5 ft)", cue="railing", axis="vertical",
                       p1=(740 / W, 412 / H), p2=(740 / W, 471 / H), real_length_ft=3.5, source="manual"),
    ]),
    Plane(id="boundary", name="Compound wall & gate", kind="boundary", fallback_plane_id="house_front"),
]
COMPOUND = {"wall-1", "wall-2", "wall-3", "wall-4", "gate-1", "gate-2", "pillar-1", "pillar-2", "pillar-3"}


def px(*points: tuple[int, int]) -> list[tuple[float, float]]:
    return [(round(x / W, 5), round(y / H, 5)) for x, y in points]


# Review step, as a user would do it in the Surfaces editor: SAM's outline of the back wall was
# jagged (swing and ceiling lights), and one 'pillar' merged a cladding strip, the porch column and
# the gate pillar. Everything else is exactly as detected.
CORRECTED_POLYGONS = {
    "wall-5": [px((530, 280), (875, 318), (877, 444), (530, 507))],
    "pillar-3": [px((733, 705), (800, 700), (802, 955), (735, 958))],
}
ADDED_REGIONS = [
    Region(id="pillar-5", type="pillar", label="Porch column", source="user",
           polygons=[px((777, 505), (829, 508), (831, 700), (779, 702))], plane_id="house_front"),
]


def a(material: str, color: str | None = None) -> Assignment:
    return Assignment(material_id=material, color=color)


DESIGNS = [
    Design(id="warm", name="Warm contemporary", assignments={
        "wall-1": a("ap_apex_ultima", "#EDE4D3"), "wall-2": a("ap_apex_ultima", "#EDE4D3"),
        "wall-3": a("ap_apex_ultima", "#EDE4D3"), "wall-4": a("texture_roller", "#D8CBB4"),
        "wall-5": a("wpc_louvers", "#9A6236"), "wall-6": a("stone_jaisalmer"), "wall-7": a("wpc_louvers", "#9A6236"),
        "wall-8": a("ap_apex_ultima", "#D9C4A2"),
        "gate-1": a("metal_enamel", "#2F3A3F"), "gate-2": a("metal_enamel", "#2F3A3F"),
        "pillar-1": a("stone_slate"), "pillar-2": a("stone_slate"), "pillar-3": a("stone_slate"),
        "pillar-4": a("wpc_louvers", "#9A6236"), "pillar-5": a("wpc_louvers", "#9A6236"),
        "balcony-1": a("ap_apex_ultima", "#3C4044"), "railing-1": a("rail_glass_frameless"),
        "roof_edge-1": a("ap_apex_ultima", "#F4F2EC"),
    }),
    Design(id="stone", name="Stone & charcoal", assignments={
        "wall-1": a("texture_roller", "#9A9890"), "wall-2": a("texture_roller", "#9A9890"),
        "wall-3": a("texture_roller", "#9A9890"), "wall-4": a("stone_kota"),
        "wall-5": a("microcement"), "wall-6": a("gvt_600x1200"), "wall-7": a("brick_tiles"),
        "wall-8": a("dulux_weathershield_max", "#F4F2EC"),
        "gate-1": a("metal_enamel", "#1F2022"), "gate-2": a("metal_enamel", "#1F2022"),
        "pillar-1": a("stone_dholpur"), "pillar-2": a("stone_dholpur"), "pillar-3": a("stone_dholpur"),
        "pillar-4": a("acp_pvdf", "#3A3D40"), "pillar-5": a("acp_pvdf", "#3A3D40"),
        "balcony-1": a("acp_pvdf", "#3A3D40"), "railing-1": a("rail_ss_pipe"),
        "roof_edge-1": a("acp_pvdf", "#3A3D40"),
    }),
    Design(id="luxury", name="Luxury granite & HPL", assignments={
        "wall-1": a("ap_ultima_protek", "#E9E7E1"), "wall-2": a("ap_ultima_protek", "#E9E7E1"),
        "wall-3": a("ap_ultima_protek", "#E9E7E1"), "wall-4": a("granite_cladding"),
        "wall-5": a("hpl_exterior", "#6B4429"), "wall-6": a("stone_ledge"), "wall-7": a("hpl_exterior", "#6B4429"),
        "wall-8": a("ap_ultima_protek", "#E9E7E1"),
        "gate-1": a("metal_enamel", "#1F2022"), "gate-2": a("metal_enamel", "#1F2022"),
        "pillar-1": a("granite_cladding"), "pillar-2": a("granite_cladding"), "pillar-3": a("granite_cladding"),
        "pillar-4": a("hpl_exterior", "#6B4429"), "pillar-5": a("hpl_exterior", "#6B4429"),
        "balcony-1": a("acp_fr", "#B8975A"), "railing-1": a("rail_glass_frameless"),
        "roof_edge-1": a("acp_fr", "#B8975A"),
    }),
    Design(id="budget", name="Budget repaint", assignments={
        "wall-1": a("ap_apex", "#F4F2EC"), "wall-2": a("ap_apex", "#F4F2EC"),
        "wall-3": a("ap_apex", "#F4F2EC"), "wall-4": a("ap_apex", "#F4F2EC"),
        "wall-5": a("ap_apex", "#B4643F"), "wall-6": a("ap_apex", "#9DAE8F"),
        "wall-7": a("ap_apex", "#B4643F"), "wall-8": a("ap_apex", "#F4F2EC"),
        "gate-1": a("metal_enamel", "#7A7F84"), "gate-2": a("metal_enamel", "#7A7F84"),
        "pillar-1": a("ap_apex", "#6C7176"), "pillar-2": a("ap_apex", "#6C7176"),
        "pillar-3": a("ap_apex", "#6C7176"), "pillar-4": a("ap_apex", "#B4643F"),
        "pillar-5": a("ap_apex", "#B4643F"),
        "balcony-1": a("ap_apex", "#6C7176"), "roof_edge-1": a("ap_apex", "#F4F2EC"),
    }),
]


def main() -> None:
    raw = json.loads((DEMO_DIR / "analysis.json").read_text(encoding="utf-8"))
    raw.pop("calibration", None)  # older analysis files
    raw.pop("scales", None)
    raw.setdefault("planes", [])
    analysis = AnalysisResult.model_validate(raw)

    regions = []
    for region in analysis.regions:
        region.plane_id = "boundary" if region.id in COMPOUND else "house_front"
        if region.id in CORRECTED_POLYGONS:
            region.polygons = CORRECTED_POLYGONS[region.id]
            region.source = "user"
        regions.append(region)
    regions += ADDED_REGIONS

    view = View(
        id="front", name="Front view", image_id=DEMO_IMAGE_ID, width=W, height=H,
        regions=regions, planes=PLANES, scene=analysis.scene,
        # Timings measured when the demo was built (scripts/build_demo.py, build_demo_depth.py).
        pipeline={**analysis.pipeline, "gemini_primary": "gemini-3.5-flash",
                  "depth_model": get_settings().depth_model_id, "depth_s": 1.8},
    )
    data = ProjectData(views=[view], designs=DESIGNS, active_design_id="warm")
    spec = {
        "name": "Demo: two-storey house, Kanyakumari",
        "photo_credit": (
            "Photo: Timothy A. Gonsalves, 'Modern House Eraviputhenthurai', Wikimedia Commons, CC BY-SA 4.0 "
            "(https://commons.wikimedia.org/wiki/File:Modern_House_Eraviputhenthurai_Mar24_A7C_10232.jpg). "
            "Redesigned previews are modified versions of this photo."
        ),
        "data": json.loads(data.model_dump_json()),
    }
    (DEMO_DIR / "project.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    print(f"Wrote project.json: {len(regions)} regions, {len(DESIGNS)} designs")


if __name__ == "__main__":
    main()
