"""AI budget designer: a complete design for the user's own house, within their budget.

    priced options --> Gemini proposes (sees the photo, the style brief, every option's real cost)
                   --> the estimator verifies the full total (site items, contingency, GST)
                   --> over budget? Gemini revises with the numbers  (up to MAX_AI_ROUNDS)
                   --> still over? deterministic repair: cheapest-per-rupee downgrades until it fits

The language model is only trusted for taste (what suits this house and brief). Every number comes
from the estimator, every id and shade it returns is validated against the catalogue, and the
budget is enforced by code, so the result is never an invented price or an impossible material.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.genai import types
from pydantic import BaseModel, Field

from app.catalog import Catalog, Material
from app.schemas import OPENING_TYPES, Assignment, Design, DesignStepLog, DesignSuggestion, ProjectData
from app.services.depth import DepthGrid
from app.services.estimator import estimate_project
from app.services.gemini import GeminiUnavailable, SceneAnalyzer

MAX_AI_ROUNDS = 3
TARGET_USE = 0.75  # below this share of the budget, the model is asked once to upgrade visible surfaces


class AiPick(BaseModel):
    region_id: str
    material_id: str
    shade: str = Field(default="", description="Exact shade name from the material's palette, or empty")
    reason: str = Field(default="", description="Why this suits the surface, at most 15 words")


class AiDesign(BaseModel):
    name: str = Field(description="Short design name, 2-4 words")
    concept: str = Field(description="The idea of the design in one or two sentences, for a homeowner")
    picks: list[AiPick]


PROMPT = """You are an experienced exterior designer for Indian homes. Design a renovation of the house
in the photo for its owner.

Brief from the owner: {style}
Budget: Rs {budget:,.0f} all-inclusive. The total is computed by an estimator as
  (sum of surface costs + site costs) x (1 + {contingency:g}% contingency) x (1 + {gst:g}% GST),
so the surface costs must add up to well below the budget. Current site costs at this size: about Rs {site:,.0f}.

Surfaces to finish (sizes measured from the photo) and, for each, the materials that suit it with their
installed cost for that surface (material + labour, before contingency and GST):
{surfaces}

Shades available per palette (use exact names):
{palettes}

Rules:
- Choose exactly one material for every surface, only from that surface's options, by id.
- Respect the house: keep a coherent palette of at most 3 main colours, contrast trims (balcony, roof edge)
  against walls, and keep similar surfaces (e.g. all pillars) consistent unless there is a reason.
- Use between 75% and 100% of the budget (never more), unless the brief asks to save.
- Spend where it is seen most (large front walls, the gate, feature walls) and save elsewhere.
- For materials with a palette pick a shade that suits the photo's surroundings; otherwise leave shade empty.
{feedback}"""


@dataclass
class Option:
    material: Material
    cost: float  # material + labour for this surface, before site items, contingency and GST


def suggest_design(
    data: ProjectData,
    catalog: Catalog,
    budget: float,
    style: str,
    analyzer: SceneAnalyzer,
    photo_jpeg: bytes | None,
    depths: dict[str, DepthGrid] | None = None,
) -> DesignSuggestion:
    options = _price_options(data, catalog, depths)
    if not options:
        raise ValueError("No surfaces to design yet: detect or draw the walls first.")
    steps: list[DesignStepLog] = []
    warnings: list[str] = []

    cheapest = {rid: min(opts, key=lambda o: o.cost) for rid, opts in options.items()}
    floor = _verify(data, catalog, {rid: _assign(o.material) for rid, o in cheapest.items()}, depths)
    if floor.grand_total > budget:
        steps.append(DesignStepLog(label="Cheapest possible finish for every surface", total=floor.grand_total, within_budget=False))
        warnings.append(f"The budget is below the minimum for these surfaces (about Rs {floor.grand_total:,.0f} with the most "
                        "economical finishes), so this is the most economical design. Consider fewer surfaces.")
        design = Design(id="ai", name="Most economical", assignments={rid: _assign(o.material) for rid, o in cheapest.items()})
        return _result(design, "The most economical finish for every surface.", floor, budget, steps, warnings, "estimator only")

    feedback = ""
    best = None  # (estimate, picks, name, concept) of the fullest proposal within budget
    last = None
    model = "not used"
    upgrade_asked = False
    for round_no in range(1, MAX_AI_ROUNDS + 1):
        prompt = PROMPT.format(
            style=style.strip() or "Modern, elegant and low-maintenance.",
            budget=budget,
            contingency=data.settings.contingency_pct,
            gst=data.settings.gst_pct,
            site=floor.site_total,
            surfaces=_surfaces_text(data, options),
            palettes=_palettes_text(catalog, options),
            feedback=feedback,
        )
        contents: list = [prompt]
        if photo_jpeg:
            contents.insert(0, types.Part.from_bytes(data=photo_jpeg, mime_type="image/jpeg"))
        try:
            proposal, model = analyzer.generate(AiDesign, contents, temperature=0.6)
        except GeminiUnavailable:
            if last is None:
                raise
            steps.append(DesignStepLog(label="AI revision unavailable; kept the earlier proposal", total=last[0].grand_total,
                                       within_budget=last[0].grand_total <= budget))
            break
        picks, dropped = _validate(proposal, options, catalog)
        for rid, opt in cheapest.items():  # surfaces the model skipped get the economical option
            picks.setdefault(rid, _assign(opt.material))
        estimate = _verify(data, catalog, picks, depths)
        last = (estimate, picks, proposal.name.strip()[:60] or "AI design", proposal.concept.strip()[:400])
        ok = estimate.grand_total <= budget
        steps.append(DesignStepLog(label=f"AI proposal {round_no}" + (f" ({dropped} invalid picks replaced)" if dropped else ""),
                                   total=estimate.grand_total, within_budget=ok))
        if ok:
            if best is None or estimate.grand_total > best[0].grand_total:
                best = last
            if estimate.grand_total >= TARGET_USE * budget or upgrade_asked or round_no == MAX_AI_ROUNDS:
                break
            upgrade_asked = True
            feedback = _upgrade_feedback(estimate.grand_total, budget)
        else:
            feedback = _feedback(estimate.grand_total, budget, picks, options)

    if best is not None:
        estimate, picks, name, concept = best
    else:
        _, picks, name, concept = last
        picks, estimate = _repair(data, catalog, picks, options, budget, depths, steps)
        concept += " Some finishes were adjusted to fit the budget."
    design = Design(id="ai", name=name, assignments=picks)
    return _result(design, concept, estimate, budget, steps, warnings, model)


# --------------------------------------------------------------------------- #
def _assign(material: Material, color: str | None = None) -> Assignment:
    return Assignment(material_id=material.id, color=color or material.default_color)


def _price_options(data: ProjectData, catalog: Catalog, depths) -> dict[str, list[Option]]:
    """Installed cost of every suitable material on every surface, from the real estimator."""
    surfaces = [r for v in data.views for r in v.regions if r.type not in OPENING_TYPES]
    costs: dict[str, list[Option]] = {r.id: [] for r in surfaces}
    probe = data.model_copy(deep=True)
    probe.settings.site_items = []
    for material in catalog.materials:
        targets = [r for r in surfaces if r.type in material.suitable_for]
        if not targets:
            continue
        probe.designs = [Design(id="probe", name="probe", assignments={r.id: _assign(material) for r in targets})]
        probe.active_design_id = "probe"
        for line in estimate_project(probe, catalog, depths=depths).lines:
            if line.net > 0:
                costs[line.region_id].append(Option(material, line.total))
    return {rid: sorted(opts, key=lambda o: o.cost) for rid, opts in costs.items() if opts}


def _verify(data: ProjectData, catalog: Catalog, assignments: dict[str, Assignment], depths):
    trial = data.model_copy(deep=True)
    trial.designs = [Design(id="ai", name="AI design", assignments=assignments)]
    trial.active_design_id = "ai"
    return estimate_project(trial, catalog, depths=depths)


def _surfaces_text(data: ProjectData, options: dict[str, list[Option]]) -> str:
    lines = []
    for view in data.views:
        for r in view.regions:
            if r.id not in options:
                continue
            opts = "; ".join(f"{o.material.id} ({o.material.name}, {o.material.tier}) Rs {o.cost:,.0f}" for o in options[r.id])
            lines.append(f"- {r.id}: {r.label} [{r.type}]. Options: {opts}")
    return "\n".join(lines)


def _palettes_text(catalog: Catalog, options: dict[str, list[Option]]) -> str:
    used = sorted({o.material.palette for opts in options.values() for o in opts if o.material.palette})
    return "\n".join(f"- {p}: " + ", ".join(s.name for s in catalog.palettes[p]) for p in used)


def _validate(proposal: AiDesign, options: dict[str, list[Option]], catalog: Catalog):
    """Keep only picks that name a real surface, a material allowed on it and a real shade."""
    picks: dict[str, Assignment] = {}
    dropped = 0
    for pick in proposal.picks:
        allowed = {o.material.id: o.material for o in options.get(pick.region_id, [])}
        material = allowed.get(pick.material_id)
        if material is None or pick.region_id in picks:
            dropped += 1
            continue
        shade = next((s for s in catalog.palettes.get(material.palette or "", []) if s.name.lower() == pick.shade.strip().lower()), None)
        picks[pick.region_id] = Assignment(material_id=material.id, color=shade.hex if shade else material.default_color,
                                           note=pick.reason.strip()[:200] or None)
    return picks, dropped


def _feedback(total: float, budget: float, picks: dict[str, Assignment], options: dict[str, list[Option]]) -> str:
    cost = {rid: next(o.cost for o in options[rid] if o.material.id == a.material_id) for rid, a in picks.items() if rid in options}
    top = sorted(cost.items(), key=lambda kv: -kv[1])[:5]
    listing = ", ".join(f"{rid} {picks[rid].material_id} Rs {c:,.0f}" for rid, c in top)
    return (f"\nYOUR PREVIOUS PROPOSAL came to Rs {total:,.0f}, which is Rs {total - budget:,.0f} OVER the budget. "
            f"Its most expensive surfaces were: {listing}. Revise it to fit the budget while keeping the design idea.")


def _upgrade_feedback(total: float, budget: float) -> str:
    return (f"\nYOUR PREVIOUS PROPOSAL came to only Rs {total:,.0f}, {total / budget:.0%} of the budget. The owner can spend more: "
            "upgrade the most visible surfaces (front walls, feature walls, gate, pillars) to better materials, staying within the budget.")


def _repair(data, catalog, picks, options, budget, depths, steps):
    """Downgrade, one surface at a time, the step that saves the most money, until the design fits."""
    picks = dict(picks)
    estimate = _verify(data, catalog, picks, depths)
    changes = 0
    while estimate.grand_total > budget:
        best = None
        for rid, a in picks.items():
            opts = options.get(rid, [])
            current = next((o for o in opts if o.material.id == a.material_id), None)
            cheaper = [o for o in opts if current and o.cost < current.cost]
            if current and cheaper:
                step = max(cheaper, key=lambda o: o.cost)  # the next cheaper option: the smallest change in look
                saving = current.cost - step.cost
                if best is None or saving > best[2]:
                    best = (rid, step, saving)
        if best is None:
            break
        rid, step, _ = best
        same_palette = picks[rid].color if step.material.palette == catalog.get(picks[rid].material_id).palette else None
        picks[rid] = _assign(step.material, same_palette)
        changes += 1
        estimate = _verify(data, catalog, picks, depths)
    steps.append(DesignStepLog(label=f"Budget repair: {changes} surface{'s' if changes != 1 else ''} switched to a cheaper finish",
                               total=estimate.grand_total, within_budget=estimate.grand_total <= budget))
    return picks, estimate


def _result(design, concept, estimate, budget, steps, warnings, model) -> DesignSuggestion:
    return DesignSuggestion(
        design=design,
        concept=concept,
        budget=budget,
        total=estimate.grand_total,
        low=estimate.low_total,
        high=estimate.high_total,
        within_budget=estimate.grand_total <= budget,
        steps=steps,
        warnings=warnings,
        model=model,
    )

