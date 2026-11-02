"""Quantity and cost estimation.

For every region that has a material in the chosen design:

    photo pixels --plane scale (x, y) at the surface's distance--> net sqft or running ft --material rules--> purchase quantities
                                                                 --rates x city index--> material + labour

* Net area = region area minus everything layered above it (windows, doors, pillars in front...).
* Purchase quantities include wastage and are rounded up to what can be bought (packs, bags,
  boxes, sheets). Labour is charged on the net installed area or length.
* Site & preparation items (scaffolding, surface prep, waterproofing, removal, debris) are added
  from the measured areas.
* Contingency is applied to the subtotal, then GST to (subtotal + contingency).
* Lifetime cost: each line's renewals (repaints, resealing...) and yearly upkeep over the comparison
  horizon, priced like today's work plus inflation, so a cheap paint and a durable cladding compare fairly.
* Every line also gets a low-high range: the catalogue's low/high rates combined with the expected
  measurement error of its plane's scale (more cues that agree = narrower range).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.catalog import Catalog, City, Material
from app.schemas import (
    OPENING_TYPES,
    CategoryTotal,
    Design,
    Estimate,
    EstimateLine,
    PlaneSummary,
    ProjectData,
    QuantityItem,
    Region,
    SiteLine,
)
from app.services.geometry import RegionMeasure, measure_regions
from app.services.depth import DepthGrid
from app.services.scale import PlaneScale, ViewDepth, plane_scale, region_ft_per_px, scale_error

LARGE_SURFACE_SQFT = 2500
CONSISTENCY_TOLERANCE = 0.3  # planes' distance-corrected scales may differ this much before we warn  # a single surface bigger than this on a house usually means a wrong scale


@dataclass
class Measured:
    unit: str  # "sqft" or "rft"
    gross: float
    net: float
    source: str  # "photo", "override" or "unscaled"
    error: float  # expected relative error of `net`


@dataclass
class Priced:
    quantities: list[QuantityItem]
    material_cost: float
    labour_basis: float  # quantity labour is charged on (net sqft or rft)
    notes: list[str] = field(default_factory=list)


@dataclass
class Rates:
    material: float
    labour: float
    material_low: float
    material_high: float
    labour_low: float
    labour_high: float


def estimate_project(data: ProjectData, catalog: Catalog, design_id: str | None = None,
                     depths: dict[str, DepthGrid] | None = None) -> Estimate:
    """`depths` maps image ids to their depth maps; photos without one use one scale per plane."""
    design = _pick_design(data, design_id)
    city = catalog.city(data.settings.city_id)
    lines: list[EstimateLine] = []
    unassigned: list[str] = []
    warnings: list[str] = []
    planes: list[PlaneSummary] = []
    bases = {"house_sqft": 0.0, "coated_sqft": 0.0, "basecoat_sqft": 0.0, "removal_sqft": 0.0}

    for view in data.views:
        pixel_measures = measure_regions(view.regions, view.width, view.height)
        depth = ViewDepth.build((depths or {}).get(view.image_id), view)
        scales: dict[str, PlaneScale | None] = {p.id: plane_scale(p, view, depth) for p in view.planes}
        planes += [_plane_summary(view.name, p, scales[p.id]) for p in view.planes]
        warnings += _consistency_warnings(view.name, view.planes, scales)
        if not view.planes:
            warnings.append(f"'{view.name}' has no scale yet, so its areas are 0 unless entered manually.")

        for region in view.regions:
            if region.type in OPENING_TYPES:
                continue
            assignment = design.assignments.get(region.id)
            if assignment is None:
                unassigned.append(f"{view.name}: {region.label}")
                continue
            material = catalog.get(assignment.material_id)
            if material is None:
                warnings.append(f"Unknown material '{assignment.material_id}' on {region.label}; skipped.")
                continue

            plane, scale, fpp = region_ft_per_px(region, view, scales, depth)
            measured = _measure(region, material, pixel_measures[region.id], scale, fpp)
            rates = _rates(material, data, city)
            aux = city.material_index  # primer, base coat and adhesive follow the city's material prices
            priced = _price(material, measured.net, rates.material, data.settings.paint_coats, aux)
            labour_cost = priced.labour_basis * rates.labour

            # Likely range. Rate spread (market low/high) and measurement error are independent, so they
            # combine as root-sum-square rather than adding up into a worst case.
            total = priced.material_cost + labour_cost
            low_p = _price(material, measured.net, rates.material_low, data.settings.paint_coats, aux)
            high_p = _price(material, measured.net, rates.material_high, data.settings.paint_coats, aux)
            rate_down = 1 - (low_p.material_cost + low_p.labour_basis * rates.labour_low) / total if total else 0.0
            rate_up = (high_p.material_cost + high_p.labour_basis * rates.labour_high) / total - 1 if total else 0.0
            low = total * (1 - math.hypot(rate_down, measured.error))
            high = total * (1 + math.hypot(rate_up, measured.error))

            notes = list(priced.notes)
            if region.type not in material.suitable_for:
                notes.append(f"{material.name} is not usually used on a {region.type.replace('_', ' ')}.")
            if region.face_factor > 1 and measured.source == "photo":
                notes.append(f"Visible area x{region.face_factor:g} to include faces not seen in the photo.")
            if measured.unit == "sqft" and measured.net > LARGE_SURFACE_SQFT and measured.source == "photo":
                warnings.append(f"'{region.label}' measures {measured.net:,.0f} sqft, which is unusually large: "
                                f"check the scale of '{plane.name if plane else view.name}'.")

            if measured.unit == "sqft":
                if not plane or plane.kind != "boundary":
                    bases["house_sqft"] += measured.net
                if material.calc in ("paint", "texture") and material.category != "Metal finishes":
                    bases["coated_sqft"] += measured.net
                    if not material.basecoat_rate:  # systems with their own base coat aren't charged twice
                        bases["basecoat_sqft"] += measured.net
                if region.remove_existing:
                    bases["removal_sqft"] += measured.net

            lines.append(EstimateLine(
                region_id=region.id,
                region_label=region.label,
                region_type=region.type,
                view_name=view.name,
                plane_name=plane.name if plane else "-",
                material_id=material.id,
                material_name=material.name,
                color_name=catalog.shade_name(material.palette, assignment.color or material.default_color) if material.palette else "",
                category=material.category,
                measure_unit=measured.unit,  # type: ignore[arg-type]
                gross=round(measured.gross, 1),
                deductions=round(max(0.0, measured.gross - measured.net), 1),
                net=round(measured.net, 1),
                measured_from=measured.source,  # type: ignore[arg-type]
                distance_m=round(depth.region(region), 1) if depth and depth.region(region) else None,
                quantities=priced.quantities,
                material_rate=round(rates.material, 2),
                material_rate_unit=material.rate_unit,
                labour_rate=round(rates.labour, 2),
                labour_rate_unit=material.labour_unit,
                material_cost=round(priced.material_cost, 2),
                labour_cost=round(labour_cost, 2),
                total=round(priced.material_cost + labour_cost, 2),
                future_cost=round(_future_cost(material, total, data.settings.horizon_years, data.settings.inflation_pct), 2),
                low=round(low, 2),
                high=round(high, 2),
                notes=notes,
            ))

    for p in planes:
        if p.ft_per_px_y is None:
            warnings.append(f"'{p.view_name}' / {p.plane_name}: no usable reference length, so its surfaces measure 0. Add one in the Scale step.")
        elif p.confidence < 0.5 and not p.confirmed:
            warnings.append(f"'{p.view_name}' / {p.plane_name}: scale confidence is low ({p.confidence:.0%}). "
                            "Check it or add a reference length.")

    site_lines = _site_lines(data, catalog, city, bases, lines)
    return _totals(design, city, lines, site_lines, planes, unassigned, warnings, data)


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def _measure(region: Region, material: Material, px: RegionMeasure, scale: PlaneScale | None,
             fpp: tuple[float, float] | None) -> Measured:
    """`fpp` is the region's (ft per px x, ft per px y) at its own distance."""
    error = scale_error(scale)
    if material.calc == "railing":
        if region.length_override_ft is not None:
            return Measured("rft", region.length_override_ft, region.length_override_ft, "override", 0.03)
        if fpp is None:
            return Measured("rft", 0.0, 0.0, "unscaled", 0.5)
        dx, dy = px.long_side
        length = math.hypot(dx * fpp[0], dy * fpp[1])
        return Measured("rft", length, length, "photo", error)

    if region.area_override_sqft is not None:
        return Measured("sqft", region.area_override_sqft, region.area_override_sqft, "override", 0.03)
    if fpp is None:
        return Measured("sqft", 0.0, 0.0, "unscaled", 0.5)
    sqft_per_px2 = fpp[0] * fpp[1] * region.face_factor
    # An area error is roughly twice the length error (it scales with length squared).
    return Measured("sqft", px.gross_px2 * sqft_per_px2, px.net_px2 * sqft_per_px2, "photo", min(0.6, 2 * error))


def _rates(material: Material, data: ProjectData, city: City) -> Rates:
    """Catalogue rates adjusted for the city, unless the user entered their own."""
    override = data.rate_overrides.get(material.id)
    m_idx, l_idx = city.material_index, city.labour_index
    if override and override.material_rate is not None:
        m = mlo = mhi = override.material_rate
    else:
        m, mlo, mhi = material.rate * m_idx, material.rate_range[0] * m_idx, material.rate_range[1] * m_idx
    if override and override.labour_rate is not None:
        lab = llo = lhi = override.labour_rate
    else:
        lab, llo, lhi = material.labour_rate * l_idx, material.labour_range[0] * l_idx, material.labour_range[1] * l_idx
    return Rates(m, lab, mlo, mhi, llo, lhi)


# --------------------------------------------------------------------------- #
# Quantities & material cost, per calculation type
# --------------------------------------------------------------------------- #
def _price(m: Material, net: float, rate: float, coats: int, aux_index: float = 1.0) -> Priced:
    net = max(0.0, net)
    waste = 1 + m.waste_pct / 100

    if m.calc == "paint":
        paint_l = net * coats / (m.coverage_sqft_per_l_per_coat or 90) * waste
        primer_l = net / (m.primer_coverage_sqft_per_l or 100) * waste
        packs, bought = choose_packs(paint_l, m.pack_sizes_l or [1])
        primer_packs, primer_bought = choose_packs(primer_l, m.pack_sizes_l or [1])
        quantities = [
            QuantityItem(name="Top coat", quantity=round(paint_l, 1), unit="L", note=f"{coats} coats; buy {format_packs(packs)}"),
            QuantityItem(name="Primer", quantity=round(primer_l, 1), unit="L", note=f"1 coat; buy {format_packs(primer_packs)}"),
        ]
        cost = bought * rate + primer_bought * (m.primer_rate or 0) * aux_index
        if m.basecoat_rate and m.basecoat_coverage_sqft_per_l:
            base_l = net / m.basecoat_coverage_sqft_per_l * waste
            base_packs, base_bought = choose_packs(base_l, m.pack_sizes_l or [1])
            quantities.insert(1, QuantityItem(name="Base coat", quantity=round(base_l, 1), unit="L", note=f"buy {format_packs(base_packs)}"))
            cost += base_bought * m.basecoat_rate * aux_index
        return Priced(quantities, cost, net, [f"Costed on full packs bought ({bought:g} L top coat)."] if net else [])

    if m.calc == "texture":
        kg = net * (m.kg_per_sqft or 0.15) * waste
        bag_kg = m.bag_kg or 25
        bags = ceil_count(kg / bag_kg) if kg else 0
        return Priced([QuantityItem(name="Texture compound", quantity=round(kg, 1), unit="kg", note=f"{bags} bag(s) of {bag_kg:g} kg")],
                      bags * bag_kg * rate, net)

    if m.calc == "cladding":
        buy_sqft = net * waste
        bags = _adhesive_bags(net, m)
        return Priced([
            QuantityItem(name="Cladding", quantity=round(buy_sqft, 1), unit="sqft", note=f"incl. {m.waste_pct:g}% cutting waste"),
            QuantityItem(name="Adhesive", quantity=bags, unit="bags", note="20 kg bags"),
        ], buy_sqft * rate + bags * (m.adhesive_rate or 0) * aux_index, net)

    if m.calc == "tiles":
        tile_sqft = (m.tile_w_ft or 4) * (m.tile_h_ft or 2)
        tiles = ceil_count(net * waste / tile_sqft) if net else 0
        per_box = m.tiles_per_box or 1
        boxes = ceil_count(tiles / per_box)
        bought_sqft = boxes * per_box * tile_sqft
        bags = _adhesive_bags(net, m)
        return Priced([
            QuantityItem(name="Tiles", quantity=tiles, unit="pcs", note=f"{boxes} box(es) of {per_box}; {bought_sqft:,.0f} sqft"),
            QuantityItem(name="Tile adhesive", quantity=bags, unit="bags", note="20 kg bags"),
        ], bought_sqft * rate + bags * (m.adhesive_rate or 0) * aux_index, net)

    if m.calc == "sheet":
        sheet_sqft = m.sheet_sqft or 32
        sheets = ceil_count(net * waste / sheet_sqft) if net else 0
        return Priced([QuantityItem(name="Sheets", quantity=sheets, unit="sheets", note=f"{sheet_sqft:g} sqft each (4 x 8 ft)")],
                      sheets * sheet_sqft * rate, net)

    if m.calc == "area":
        buy_sqft = net * waste
        return Priced([QuantityItem(name="Material", quantity=round(buy_sqft, 1), unit="sqft", note=f"incl. {m.waste_pct:g}% waste")],
                      buy_sqft * rate, net)

    # "railing": installed systems priced per running foot
    buy_rft = net * waste
    return Priced([QuantityItem(name="Railing", quantity=round(buy_rft, 1), unit="rft", note=f"incl. {m.waste_pct:g}% waste")],
                  buy_rft * rate, net)


def ceil_count(value: float) -> int:
    """Round a count up, ignoring floating-point noise (324.0000001 tiles is 324, not 325)."""
    return math.ceil(round(value, 6))


def _adhesive_bags(net_sqft: float, m: Material) -> int:
    per_bag = m.adhesive_sqft_per_bag
    return ceil_count(net_sqft / per_bag) if per_bag and net_sqft else 0


def choose_packs(litres: float, sizes: list[float]) -> tuple[dict[int, int], float]:
    """A practical combination of paint packs covering `litres`.

    Each extra pack is treated as costing about one litre (small tins cost more per litre and are a
    nuisance to buy), so the choice minimises litres_bought + pack_count. E.g. 47 L -> 2 x 20 + 2 x 4
    (48 L in 4 packs) rather than 2 x 20 + 4 + 3 x 1 (47 L in 6 packs). Returns ({size: count}, litres).
    """
    need = ceil_count(litres)
    if need <= 0:
        return {}, 0.0
    pack_sizes = sorted({int(s) for s in sizes if s >= 1}, reverse=True) or [1]
    limit = need + max(pack_sizes)
    # fewest[v] = (pack count, combination) making exactly v litres
    fewest: list[tuple[int, dict[int, int]] | None] = [None] * (limit + 1)
    fewest[0] = (0, {})
    for v in range(1, limit + 1):
        for size in pack_sizes:
            prev = fewest[v - size] if v >= size else None
            if prev is not None and (fewest[v] is None or prev[0] + 1 < fewest[v][0]):
                combo = dict(prev[1])
                combo[size] = combo.get(size, 0) + 1
                fewest[v] = (prev[0] + 1, combo)
    options = [(v + fewest[v][0], v) for v in range(need, limit + 1) if fewest[v] is not None]
    if options:
        _, best = min(options)
        return fewest[best][1], float(best)
    return {1: need}, float(need)


def format_packs(packs: dict[int, int]) -> str:
    if not packs:
        return "nothing"
    return " + ".join(f"{count} x {size} L" for size, count in sorted(packs.items(), reverse=True))


# --------------------------------------------------------------------------- #
# Site items & totals
# --------------------------------------------------------------------------- #
def _site_lines(data: ProjectData, catalog: Catalog, city: City, bases: dict[str, float], lines: list[EstimateLine]) -> list[SiteLine]:
    enabled = set(data.settings.site_items) if data.settings.site_items is not None else {s.id for s in catalog.site_items if s.default}
    works = sum(l.total for l in lines)
    works_low = sum(l.low for l in lines)
    works_high = sum(l.high for l in lines)
    out: list[SiteLine] = []
    for item in catalog.site_items:
        if item.id not in enabled:
            continue
        if item.basis == "percent":
            if works <= 0:
                continue
            out.append(SiteLine(
                id=item.id, name=item.name, quantity=item.rate, unit="%", rate=item.rate, amount=round(works * item.rate / 100, 2),
                low=round(works_low * item.rate_range[0] / 100, 2), high=round(works_high * item.rate_range[1] / 100, 2), note=item.note,
            ))
            continue
        qty = bases[item.basis]
        if qty <= 0:
            continue
        rate = item.rate * city.labour_index
        out.append(SiteLine(
            id=item.id, name=item.name, quantity=round(qty, 1), unit=item.unit, rate=round(rate, 2), amount=round(qty * rate, 2),
            low=round(qty * item.rate_range[0] * city.labour_index, 2), high=round(qty * item.rate_range[1] * city.labour_index, 2),
            note=item.note,
        ))
    return out


def _plane_summary(view_name: str, plane, scale: PlaneScale | None) -> PlaneSummary:
    return PlaneSummary(
        view_name=view_name,
        plane_id=plane.id,
        plane_name=plane.name,
        ft_per_px_x=scale.ft_per_px_x if scale else None,
        ft_per_px_y=scale.ft_per_px_y if scale else None,
        confidence=scale.confidence if scale else 0.0,
        measurement_error_pct=round(scale_error(scale) * 100, 1),
        cues_used=scale.cues_used if scale else [],
        cues_rejected=scale.cues_rejected if scale else [],
        borrowed_from=scale.borrowed_from if scale else None,
        ref_depth_m=round(scale.ref_depth_m, 1) if scale and scale.ref_depth_m else None,
        confirmed=plane.confirmed,
    )


def _consistency_warnings(view_name: str, planes, scales: dict[str, PlaneScale | None]) -> list[str]:
    """With a depth map, every plane's vertical scale per metre of distance should agree (walls are
    vertical and the camera is the same), so a big disagreement means a wrong reference length."""
    per_m = [(p.name, s.ft_per_px_y / s.ref_depth_m) for p in planes
             if (s := scales.get(p.id)) and s.ref_depth_m and not s.borrowed_from and not s.camera_only]
    if len(per_m) < 2:
        return []
    (lo_name, lo), (hi_name, hi) = min(per_m, key=lambda t: t[1]), max(per_m, key=lambda t: t[1])
    if hi / lo <= 1 + CONSISTENCY_TOLERANCE:
        return []
    return [f"'{view_name}': after correcting for distance, the scales of {lo_name} and {hi_name} disagree by "
            f"{hi / lo - 1:.0%}. One of their reference lengths is probably wrong; check them in the Scale step."]


def _pick_design(data: ProjectData, design_id: str | None) -> Design:
    wanted = design_id or data.active_design_id
    for d in data.designs:
        if d.id == wanted:
            return d
    return data.designs[0] if data.designs else Design(id="design-a", name="Design A")


def _future_cost(material: Material, installed: float, years: int, inflation_pct: float) -> float:
    """Renewals and upkeep of one surface over `years`, in future rupees (today's price x inflation)."""
    grow = 1 + inflation_pct / 100
    cost = sum(installed * material.upkeep_pct / 100 * grow**y for y in range(1, years + 1))
    if material.renew_years and material.renew_share:
        k = 1
        while k * material.renew_years <= years - 0.5:  # a renewal due in the final months is left out
            cost += installed * material.renew_share * grow ** (k * material.renew_years)
            k += 1
    return cost


def _totals(design: Design, city: City, lines: list[EstimateLine], site_lines: list[SiteLine], planes: list[PlaneSummary],
            unassigned: list[str], warnings: list[str], data: ProjectData) -> Estimate:
    categories: dict[str, CategoryTotal] = {}
    for line in lines:
        cat = categories.setdefault(line.category, CategoryTotal(category=line.category, material_cost=0, labour_cost=0, total=0))
        cat.material_cost += line.material_cost
        cat.labour_cost += line.labour_cost
        cat.total += line.total
    site_total = sum(x.amount for x in site_lines)
    if site_lines:
        categories["Site & preparation"] = CategoryTotal(category="Site & preparation", material_cost=0, labour_cost=site_total, total=site_total)

    material_total = sum(l.material_cost for l in lines)
    labour_total = sum(l.labour_cost for l in lines)
    subtotal = material_total + labour_total + site_total
    s = data.settings
    uplift = (1 + s.contingency_pct / 100) * (1 + s.gst_pct / 100)
    contingency = subtotal * s.contingency_pct / 100
    gst = (subtotal + contingency) * s.gst_pct / 100
    grand_total = subtotal + contingency + gst
    low_total = (sum(l.low for l in lines) + sum(x.low for x in site_lines)) * uplift
    high_total = (sum(l.high for l in lines) + sum(x.high for x in site_lines)) * uplift

    lifetime_future = sum(l.future_cost for l in lines) * (1 + s.gst_pct / 100)

    if not lines:
        warnings.append("No materials applied yet. Choose a material for at least one surface in the Design step.")

    return Estimate(
        design_id=design.id,
        design_name=design.name,
        city=city.name,
        lines=lines,
        site_lines=site_lines,
        categories=[CategoryTotal(category=c.category, material_cost=round(c.material_cost, 2), labour_cost=round(c.labour_cost, 2),
                                  total=round(c.total, 2)) for c in sorted(categories.values(), key=lambda c: -c.total)],
        planes=planes,
        material_total=round(material_total, 2),
        labour_total=round(labour_total, 2),
        site_total=round(site_total, 2),
        subtotal=round(subtotal, 2),
        contingency_pct=s.contingency_pct,
        contingency=round(contingency, 2),
        gst_pct=s.gst_pct,
        gst=round(gst, 2),
        grand_total=round(grand_total, 2),
        low_total=round(min(low_total, grand_total), 2),
        high_total=round(max(high_total, grand_total), 2),
        lifetime_years=s.horizon_years,
        lifetime_future=round(lifetime_future, 2),
        lifetime_total=round(grand_total + lifetime_future, 2),
        total_area_sqft=round(sum(l.net for l in lines if l.measure_unit == "sqft"), 1),
        total_railing_rft=round(sum(l.net for l in lines if l.measure_unit == "rft"), 1),
        unassigned_regions=unassigned,
        warnings=list(dict.fromkeys(warnings)),
    )
