"""Pydantic models shared by the API, the database layer and the services.

Coordinate convention: every point stored in a project is *normalised* to the
image, i.e. (x, y) with 0 <= x, y <= 1. This keeps regions valid if the image is
displayed or rendered at a different resolution.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ComponentType = Literal[
    "wall", "window", "door", "balcony", "railing", "pillar", "parapet", "gate", "roof_edge"
]

COMPONENT_LABELS: dict[str, str] = {
    "wall": "Wall",
    "window": "Window",
    "door": "Door",
    "balcony": "Balcony",
    "railing": "Railing",
    "pillar": "Pillar / column",
    "parapet": "Parapet",
    "gate": "Gate",
    "roof_edge": "Roof edge / sunshade",
}

# Openings are never finished; they are deducted from the surfaces around them.
OPENING_TYPES: frozenset[str] = frozenset({"window", "door"})

Point = tuple[float, float]

# Surfaces at a similar distance from the camera share one scale ("plane").
PlaneKind = Literal["house_front", "house_side", "boundary", "other"]
PLANE_NAMES: dict[str, str] = {
    "house_front": "House front",
    "house_side": "House side",
    "boundary": "Compound wall & gate",
    "other": "Other surfaces",
}


# --------------------------------------------------------------------------- #
# Image quality & scene understanding
# --------------------------------------------------------------------------- #
class QualityIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str


class QualityReport(BaseModel):
    ok: bool
    issues: list[QualityIssue] = []
    metrics: dict[str, float] = {}


class SceneSummary(BaseModel):
    """What the vision model understood about the photo as a whole."""

    is_residential_exterior: bool = True
    view_type: str = "unknown"
    storeys: int | None = None
    usable: bool = True
    issues: list[str] = []
    guidance: list[str] = []


# --------------------------------------------------------------------------- #
# Project structure
# --------------------------------------------------------------------------- #
class Region(BaseModel):
    """One building component on one photo, e.g. 'First-floor front wall'."""

    id: str
    type: ComponentType
    label: str
    # A component can consist of several disjoint parts (e.g. a wall split by a pillar).
    polygons: list[list[Point]]
    source: Literal["ai", "ai_box", "user"] = "user"
    confidence: float | None = None
    # Manual corrections a user can make after measuring on site.
    area_override_sqft: float | None = Field(default=None, ge=0)
    length_override_ft: float | None = Field(default=None, ge=0)
    # A photo shows one face of a pillar or gate; this multiplies the visible area
    # to cover the faces we cannot see (e.g. 2 = front + back of a gate).
    face_factor: float = Field(default=1.0, ge=1.0, le=4.0)
    # The depth plane whose scale measures this region; None = the photo's first plane.
    plane_id: str | None = None
    # Strip the existing finish (tiles, cladding) before applying the new one.
    remove_existing: bool = False

    @model_validator(mode="before")
    @classmethod
    def _migrate_scale_id(cls, value):
        # Projects saved before planes existed used `scale_id`.
        if isinstance(value, dict) and "scale_id" in value and "plane_id" not in value:
            value = {**value, "plane_id": value["scale_id"]}
        return value


CueKind = Literal["door", "gate", "railing", "parapet", "storey", "window", "car", "person", "motorbike", "custom"]


class ScaleReference(BaseModel):
    """A line on the photo whose real length is known (or confidently estimated)."""

    id: str
    name: str
    cue: CueKind = "custom"
    # vertical/horizontal references set the scale along that direction; free ones count for both.
    axis: Literal["vertical", "horizontal", "free"] = "free"
    p1: Point
    p2: Point
    real_length_ft: float = Field(gt=0)
    source: Literal["auto", "manual"] = "manual"
    weight: float = Field(default=1.0, ge=0, le=1)  # trust in this cue for the consensus
    enabled: bool = True


class Plane(BaseModel):
    """Surfaces at a similar distance from the camera, measured with one consensus scale.

    Things nearer the camera look bigger, so a compound wall in front of a house needs its own
    scale. A plane can hold several reference cues (doors, cars, people, railings...); the scale is
    their robust consensus, separately for vertical and horizontal when both are available.
    """

    id: str
    name: str
    kind: PlaneKind = "house_front"
    references: list[ScaleReference] = []
    # If this plane has no usable references, borrow the scale of another plane (low confidence).
    fallback_plane_id: str | None = None
    confirmed: bool = False


class View(BaseModel):
    """One uploaded photo of the building together with its mapped regions."""

    id: str
    name: str
    image_id: str
    width: int
    height: int
    regions: list[Region] = []
    planes: list[Plane] = []
    quality: QualityReport | None = None
    scene: SceneSummary | None = None
    # What the AI pipeline did for this photo (models, timings, fallbacks), shown to the user.
    pipeline: dict[str, str | float | int | bool] | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_scales(cls, value):
        # Projects saved before planes existed had one flat list of `scales`: each becomes a plane.
        if isinstance(value, dict) and "scales" in value and "planes" not in value:
            planes = []
            for sc in value.get("scales") or []:
                planes.append({
                    "id": sc["id"], "name": sc.get("name", "Reference"), "kind": "house_front",
                    "confirmed": sc.get("confirmed", False),
                    "references": [{
                        "id": f"{sc['id']}-ref", "name": sc.get("name", "Reference"), "axis": "free",
                        "p1": sc["p1"], "p2": sc["p2"], "real_length_ft": sc["real_length_ft"],
                        "source": "auto" if str(sc.get("method", "")).startswith("auto") else "manual",
                    }],
                })
            value = {k: v for k, v in value.items() if k != "scales"} | {"planes": planes}
        return value


class Assignment(BaseModel):
    material_id: str
    color: str | None = None  # hex colour for paintable / tintable materials
    note: str | None = Field(default=None, max_length=200)  # why it was chosen (AI designer)


class Design(BaseModel):
    """A named combination of materials; a project can hold several to compare."""

    id: str
    name: str
    assignments: dict[str, Assignment] = {}  # keyed by region id


class RateOverride(BaseModel):
    material_rate: float | None = Field(default=None, ge=0)
    labour_rate: float | None = Field(default=None, ge=0)


class ProjectSettings(BaseModel):
    contingency_pct: float = Field(default=10, ge=0, le=50)
    gst_pct: float = Field(default=18, ge=0, le=28)
    paint_coats: int = Field(default=2, ge=1, le=4)
    city_id: str = "ahmedabad"
    # Site & preparation items switched on for this project (ids from the catalogue's site_items).
    site_items: list[str] | None = None  # None = the catalogue defaults
    # Long-term cost comparison: years to look ahead and yearly price inflation.
    horizon_years: int = Field(default=15, ge=5, le=30)
    inflation_pct: float = Field(default=6, ge=0, le=15)


class ProjectData(BaseModel):
    views: list[View] = []
    designs: list[Design] = [Design(id="design-a", name="Design A")]
    active_design_id: str = "design-a"
    rate_overrides: dict[str, RateOverride] = {}
    settings: ProjectSettings = ProjectSettings()

    @model_validator(mode="after")
    def _region_ids_unique(self) -> "ProjectData":
        # Designs store materials by region id, so ids must be unique across all photos.
        ids = [r.id for v in self.views for r in v.regions]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"Region ids must be unique across photos: {sorted(duplicates)}")
        return self


class Project(BaseModel):
    id: str
    name: str
    is_demo: bool = False
    can_edit: bool = False
    created_at: datetime
    updated_at: datetime
    data: ProjectData


class ProjectSummary(BaseModel):
    id: str
    name: str
    is_demo: bool
    updated_at: datetime
    view_count: int
    cover_image_id: str | None


class ProjectCreate(BaseModel):
    name: str = Field(default="My house", min_length=1, max_length=120)
    data: ProjectData = ProjectData()


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    data: ProjectData


# --------------------------------------------------------------------------- #
# Upload & analysis responses
# --------------------------------------------------------------------------- #
class ImageInfo(BaseModel):
    image_id: str
    width: int
    height: int
    quality: QualityReport


class AnalysisResult(BaseModel):
    regions: list[Region]
    planes: list[Plane]
    scene: SceneSummary
    pipeline: dict[str, str | float | int | bool]
    warnings: list[str] = []


# --------------------------------------------------------------------------- #
# Estimation
# --------------------------------------------------------------------------- #
class EstimateRequest(BaseModel):
    data: ProjectData
    design_id: str | None = None


class QuantityItem(BaseModel):
    name: str
    quantity: float
    unit: str
    note: str = ""


class EstimateLine(BaseModel):
    region_id: str
    region_label: str
    region_type: str
    view_name: str
    plane_name: str
    material_id: str
    material_name: str
    color_name: str = ""
    category: str
    measure_unit: Literal["sqft", "rft"]
    gross: float
    deductions: float
    net: float
    measured_from: Literal["photo", "override", "unscaled"]
    future_cost: float = 0  # renewals and upkeep over the settings' horizon, before GST
    distance_m: float | None = None  # the surface's distance from the camera, when the photo has a depth map
    quantities: list[QuantityItem]
    material_rate: float
    material_rate_unit: str
    labour_rate: float
    labour_rate_unit: str
    material_cost: float
    labour_cost: float
    total: float
    low: float  # cheapest rates and the low end of the measurement uncertainty
    high: float
    notes: list[str] = []


class SiteLine(BaseModel):
    id: str
    name: str
    quantity: float
    unit: str
    rate: float
    amount: float
    low: float
    high: float
    note: str = ""


class CategoryTotal(BaseModel):
    category: str
    material_cost: float
    labour_cost: float
    total: float


class PlaneSummary(BaseModel):
    view_name: str
    plane_id: str
    plane_name: str
    ft_per_px_x: float | None
    ft_per_px_y: float | None
    confidence: float
    measurement_error_pct: float
    cues_used: list[str]
    cues_rejected: list[str]
    borrowed_from: str | None = None
    # Distance (m) at which ft_per_px_x/y hold; surfaces farther away get proportionally more ft/px.
    ref_depth_m: float | None = None
    confirmed: bool


class Estimate(BaseModel):
    design_id: str
    design_name: str
    city: str
    lines: list[EstimateLine]
    site_lines: list[SiteLine]
    categories: list[CategoryTotal]
    planes: list[PlaneSummary]
    material_total: float
    labour_total: float
    site_total: float
    subtotal: float
    contingency_pct: float
    contingency: float
    gst_pct: float
    gst: float
    grand_total: float
    low_total: float
    high_total: float
    # Lifetime: today's total plus renewals (repaint, reseal...) and upkeep over the horizon, with inflation and GST.
    lifetime_years: int = 15
    lifetime_future: float = 0
    lifetime_total: float = 0
    total_area_sqft: float
    total_railing_rft: float
    unassigned_regions: list[str]
    warnings: list[str]


class DesignSuggestRequest(BaseModel):
    data: ProjectData
    budget: float = Field(gt=0, le=1e9)
    style: str = Field(default="", max_length=300)


class DesignStepLog(BaseModel):
    label: str
    total: float
    within_budget: bool


class DesignSuggestion(BaseModel):
    """An AI-proposed design, verified (and if needed repaired) against the budget by the estimator."""

    design: Design
    concept: str
    budget: float
    total: float
    low: float
    high: float
    within_budget: bool
    steps: list[DesignStepLog]
    warnings: list[str]
    model: str
