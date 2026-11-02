"""Material catalogue: typed access to data/catalog.json (generated, see docs/ESTIMATION.md)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

CalcType = Literal["paint", "texture", "cladding", "tiles", "sheet", "area", "railing"]
Tier = Literal["economy", "standard", "premium", "luxury"]


class Shade(BaseModel):
    name: str
    hex: str
    family: str


class RenderSpec(BaseModel):
    """How the browser draws the material onto the photo."""

    mode: Literal["tint", "texture", "tiles", "panel", "glass", "rail"]
    texture: str | None = None
    tile_ft: float | None = None  # real-world width one texture image covers
    strength: float | None = None  # "tint": how much texture grain shows through the colour
    tint: str | None = None  # "texture"/"tiles": colour multiplied over the photo texture
    joint_w_ft: float | None = None  # "tiles"/"panel": joint grid spacing
    joint_h_ft: float | None = None
    color: str | None = None
    posts: bool = False  # "glass": show SS posts


class Material(BaseModel):
    id: str
    name: str
    brand: str | None = None
    product: str | None = None
    tier: Tier = "standard"
    category: str
    calc: CalcType
    rate: float
    rate_range: tuple[float, float]
    rate_unit: str
    labour_rate: float
    labour_range: tuple[float, float]
    labour_unit: str
    waste_pct: float
    warranty_years: int | None = None
    durability: str
    maintenance: str
    pros: list[str] = []
    cons: list[str] = []
    specs: list[str] = []
    suitable_for: list[str]
    render: RenderSpec
    palette: str | None = None  # key into Catalog.palettes
    default_color: str | None = None

    # Life cycle (for the long-term cost): renewal every `renew_years` costing `renew_share` of the installed cost
    # (repaint, reseal...), plus yearly upkeep (washing, cleaning) as a % of the installed cost.
    renew_years: float | None = None
    renew_share: float = 0.0
    upkeep_pct: float = 0.0

    # Calculation parameters (only those relevant to `calc` are set).
    coverage_sqft_per_l_per_coat: float | None = None
    primer_coverage_sqft_per_l: float | None = None
    primer_rate: float | None = None
    basecoat_rate: float | None = None
    basecoat_coverage_sqft_per_l: float | None = None
    pack_sizes_l: list[float] | None = None
    kg_per_sqft: float | None = None
    bag_kg: float | None = None
    adhesive_sqft_per_bag: float | None = None
    adhesive_rate: float | None = None
    tile_w_ft: float | None = None
    tile_h_ft: float | None = None
    tiles_per_box: int | None = None
    sheet_sqft: float | None = None


class SiteItem(BaseModel):
    id: str
    name: str
    # What the rate applies to: house surfaces (scaffolding), painted/textured area,
    # surfaces marked for removal, or a percentage of the works.
    basis: Literal["house_sqft", "coated_sqft", "basecoat_sqft", "removal_sqft", "percent"]
    rate: float
    rate_range: tuple[float, float]
    unit: str
    default: bool
    note: str


class City(BaseModel):
    id: str
    name: str
    labour_index: float
    material_index: float


class Catalog(BaseModel):
    currency: str
    region: str
    rates_updated: str
    rates_note: str
    cities: list[City]
    site_items: list[SiteItem]
    palettes: dict[str, list[Shade]]
    materials: list[Material]

    def get(self, material_id: str) -> Material | None:
        return next((m for m in self.materials if m.id == material_id), None)

    def city(self, city_id: str) -> City:
        return next((c for c in self.cities if c.id == city_id), self.cities[0])

    def shade_name(self, palette: str | None, hex_value: str | None) -> str:
        if not hex_value:
            return ""
        for shade in self.palettes.get(palette or "", []):
            if shade.hex.lower() == hex_value.lower():
                return shade.name
        return hex_value.upper()


CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"


@lru_cache
def get_catalog() -> Catalog:
    return Catalog.model_validate(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
