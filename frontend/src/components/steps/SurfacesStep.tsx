"use client";

import { ArrowRight, Check, Eye, EyeOff, MousePointer2, PenLine, Plus, Tag, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState, type MouseEvent, type PointerEvent } from "react";

import { RegionOverlay } from "@/components/stage/RegionOverlay";
import { pointerToPoint, Stage, toSvgPoints } from "@/components/stage/Stage";
import { toast } from "@/components/Toaster";
import { Badge, Button, cx, Field, IconButton, inputClass, NumberInput, Segmented } from "@/components/ui";
import { useWorkspace } from "@/components/workspace/context";
import { PanelHeading, StepLayout } from "@/components/workspace/StepLayout";
import { ViewSwitcher } from "@/components/workspace/ViewSwitcher";
import { imageUrl } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { COMPONENT_META, COMPONENT_TYPES, distance, planeForRegion, planeScale, polygonAreaPx } from "@/lib/geometry";
import { activeDesign, materialById, nextRegionId } from "@/lib/project";
import type { Catalog, ComponentType, Point, ProjectData, Region, View } from "@/lib/types";

type Tool = "select" | "draw";
interface DragTarget {
  regionId: string;
  poly: number;
  index: number;
  recorded: boolean; // undo step taken (on the first move, so a plain click adds none)
}

export function SurfacesStep() {
  const { store, catalog, view, selectedRegionId, selectRegion, goTo } = useWorkspace();
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<DragTarget | null>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [drawType, setDrawType] = useState<ComponentType>("wall");
  const [partOf, setPartOf] = useState<string | null>(null); // drawing an extra part of an existing region
  const [draft, setDraft] = useState<Point[]>([]);
  const [cursor, setCursor] = useState<Point | null>(null);
  const [hidden, setHidden] = useState<Set<ComponentType>>(new Set());
  const [showLabels, setShowLabels] = useState(false);

  const selected = view?.regions.find((r) => r.id === selectedRegionId) ?? null;
  const { update, checkpoint } = store;

  const updateRegion = (id: string, recipe: (r: Region) => void, record = true) =>
    update(
      (d) => {
        const region = d.views.find((v) => v.id === view?.id)?.regions.find((r) => r.id === id);
        if (region) recipe(region as Region);
      },
      { record },
    );

  function deleteRegion(id: string) {
    update((d) => {
      const v = d.views.find((x) => x.id === view?.id);
      if (v) v.regions = v.regions.filter((r) => r.id !== id);
      for (const design of d.designs) delete design.assignments[id];
    });
    selectRegion(null);
  }

  function cancelDraw() {
    setDraft([]);
    setPartOf(null);
    setTool("select");
  }

  function finishDraw(points = draft) {
    const clean = points.filter((p, i) => i === 0 || distance(p, points[i - 1], view!.width, view!.height) > 2);
    if (clean.length < 3) {
      toast("Click at least 3 corners to outline a surface.", "info");
      return;
    }
    if (partOf) {
      updateRegion(partOf, (r) => r.polygons.push(clean));
      selectRegion(partOf);
    } else if (view) {
      const id = nextRegionId(store.data, drawType);
      const region: Region = {
        id,
        type: drawType,
        label: `${COMPONENT_META[drawType].label} (drawn)`,
        polygons: [clean],
        source: "user",
        confidence: null,
        area_override_sqft: null,
        length_override_ft: null,
        face_factor: drawType === "gate" ? 2 : 1,
        plane_id: null,
        remove_existing: false,
      };
      update((d) => {
        d.views.find((v) => v.id === view.id)?.regions.push(region);
      });
      selectRegion(id);
    }
    cancelDraw();
  }

  // Keyboard: Enter finishes, Esc cancels, Backspace removes the last corner, Delete removes the surface.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, textarea, select")) return;
      if (tool === "draw") {
        if (e.key === "Enter") finishDraw();
        else if (e.key === "Escape") cancelDraw();
        else if (e.key === "Backspace") setDraft((d) => d.slice(0, -1));
        return;
      }
      if (e.key === "Escape") selectRegion(null);
      if ((e.key === "Delete" || e.key === "Backspace") && selectedRegionId) deleteRegion(selectedRegionId);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!view) return null;

  function targetData(e: { target: EventTarget }) {
    const el = (e.target as Element).closest("[data-kind]") as SVGElement | null;
    return {
      kind: el?.dataset.kind,
      region: el?.closest("[data-region]")?.getAttribute("data-region") ?? el?.dataset.region,
      poly: Number(el?.dataset.poly),
      index: Number(el?.dataset.index),
    };
  }

  function onPointerDown(e: PointerEvent<SVGSVGElement>) {
    const p = pointerToPoint(e, svgRef.current);
    if (tool === "draw") {
      const closeEnough = draft.length >= 3 && distance(p, draft[0], view!.width, view!.height) < 12 * (view!.width / (svgRef.current?.clientWidth || view!.width));
      if (closeEnough) finishDraw();
      else setDraft((d) => [...d, p]);
      return;
    }
    const t = targetData(e);
    if ((t.kind === "vertex" || t.kind === "mid") && selected) {
      let index = t.index;
      if (t.kind === "mid") {
        checkpoint(); // inserting a corner is an edit in itself
        index = t.index + 1;
        updateRegion(selected.id, (r) => r.polygons[t.poly].splice(index, 0, p), false);
      }
      drag.current = { regionId: selected.id, poly: t.poly, index, recorded: t.kind === "mid" };
      svgRef.current?.setPointerCapture(e.pointerId);
      return;
    }
    selectRegion(t.kind === "region" && t.region ? t.region : null);
  }

  function onPointerMove(e: PointerEvent<SVGSVGElement>) {
    const p = pointerToPoint(e, svgRef.current);
    if (tool === "draw") setCursor(p);
    const d = drag.current;
    if (!d) return;
    if (!d.recorded) {
      checkpoint();
      d.recorded = true;
    }
    updateRegion(d.regionId, (r) => (r.polygons[d.poly][d.index] = p), false);
  }

  function onPointerUp(e: PointerEvent<SVGSVGElement>) {
    if (drag.current) svgRef.current?.releasePointerCapture(e.pointerId);
    drag.current = null;
  }

  function onDoubleClick(e: MouseEvent<SVGSVGElement>) {
    if (tool === "draw") return finishDraw();
    const t = targetData(e);
    if (t.kind === "vertex" && selected) {
      if (selected.polygons[t.poly].length <= 3) return toast("A surface needs at least 3 corners.", "info");
      updateRegion(selected.id, (r) => void r.polygons[t.poly].splice(t.index, 1));
    }
  }

  return (
    <StepLayout
      toolbar={
        <>
          <ViewSwitcher />
          <Segmented<Tool>
            size="sm"
            value={tool}
            onChange={(t) => (t === "select" ? cancelDraw() : setTool("draw"))}
            options={[
              { value: "select", label: <span className="flex items-center gap-1"><MousePointer2 className="size-3.5" /> Select & edit</span> },
              { value: "draw", label: <span className="flex items-center gap-1"><PenLine className="size-3.5" /> Draw new</span> },
            ]}
          />
          {tool === "draw" && (
            <>
              {!partOf && (
                <select className={cx(inputClass, "h-8 w-auto text-xs")} value={drawType} onChange={(e) => setDrawType(e.target.value as ComponentType)} aria-label="Type of new surface">
                  {COMPONENT_TYPES.map((t) => (
                    <option key={t} value={t}>{COMPONENT_META[t].label}</option>
                  ))}
                </select>
              )}
              <Button size="sm" variant="primary" icon={<Check className="size-3.5" />} disabled={draft.length < 3} onClick={() => finishDraw()}>
                Finish
              </Button>
              <Button size="sm" variant="ghost" icon={<X className="size-3.5" />} onClick={cancelDraw}>
                Cancel
              </Button>
              <span className="text-xs text-muted">
                {partOf ? "Adding a part. " : ""}Click corners, then Finish (Enter) or click the first corner.
              </span>
            </>
          )}
          {tool === "select" && (
            <>
              <IconButton label={showLabels ? "Hide labels" : "Show labels"} active={showLabels} onClick={() => setShowLabels((s) => !s)}>
                <Tag className="size-4" />
              </IconButton>
              <span className="hidden text-xs text-muted md:inline">Drag white corners to adjust · drag small dots to add corners · double-click a corner to remove it</span>
            </>
          )}
        </>
      }
      stage={
        <Stage
          width={view.width}
          height={view.height}
          svgRef={svgRef}
          cursor={tool === "draw" ? "crosshair" : "default"}
          // eslint-disable-next-line @next/next/no-img-element -- photo served by the API
          background={<img src={imageUrl(view.image_id)} alt={view.name} className="absolute inset-0 size-full" />}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onDoubleClick={onDoubleClick}
          overlay={({ unit }) => (
            <>
              <RegionOverlay view={view} unit={unit} selectedId={selectedRegionId} hiddenTypes={hidden} showLabels={showLabels} editable={tool === "select"} />
              {tool === "draw" && draft.length > 0 && (
                <g pointerEvents="none">
                  <polyline
                    points={toSvgPoints(cursor ? [...draft, cursor] : draft, view.width, view.height)}
                    fill={COMPONENT_META[drawType].color}
                    fillOpacity={0.15}
                    stroke="#fff"
                    strokeWidth={2 * unit}
                    strokeDasharray={`${6 * unit} ${4 * unit}`}
                  />
                  {draft.map(([x, y], i) => (
                    <circle key={i} cx={x * view.width} cy={y * view.height} r={(i === 0 ? 7 : 4.5) * unit} fill={i === 0 ? COMPONENT_META[drawType].color : "#fff"} stroke="#111" strokeWidth={unit} />
                  ))}
                </g>
              )}
            </>
          )}
        />
      }
      panel={
        <>
          <PanelHeading
            title="Surfaces"
            subtitle="AI-detected building parts. Click one to check its outline and type; fix anything that is wrong or draw what was missed."
          />
          {selected ? (
            <RegionInspector
              key={selected.id}
              region={selected}
              view={view}
              measuredByLength={isMeasuredByLength(selected, store.data, catalog)}
              readOnly={false}
              onChange={(recipe) => updateRegion(selected.id, recipe)}
              onDelete={() => deleteRegion(selected.id)}
              onAddPart={() => {
                setPartOf(selected.id);
                setDraft([]);
                setTool("draw");
              }}
              onClose={() => selectRegion(null)}
            />
          ) : (
            <RegionList view={view} hidden={hidden} setHidden={setHidden} onSelect={selectRegion} />
          )}
          <Button variant="primary" className="w-full" onClick={() => goTo("scale")}>
            Next: check the scale <ArrowRight className="size-4" />
          </Button>
        </>
      }
    />
  );
}

/** Approximate gross area of a region from the photo (for orientation only; the estimate is server-side). */
function approxSize(region: Region, view: View): string | null {
  const plane = planeForRegion(region, view);
  const scale = plane ? planeScale(plane, view) : null;
  if (!scale) return null;
  const px = region.polygons.reduce((s, p) => s + polygonAreaPx(p, view.width, view.height), 0);
  return `≈ ${formatNumber(px * scale.ftPerPxX * scale.ftPerPxY * region.face_factor)} sqft`;
}

function RegionList({
  view,
  hidden,
  setHidden,
  onSelect,
}: {
  view: View;
  hidden: Set<ComponentType>;
  setHidden: (s: Set<ComponentType>) => void;
  onSelect: (id: string) => void;
}) {
  if (!view.regions.length)
    return (
      <div className="rounded-xl border border-dashed border-line-strong p-5 text-center text-sm text-muted">
        No surfaces yet. Run AI detection on the Photos step, or choose <b>Draw new</b> and outline a wall.
      </div>
    );

  return (
    <div className="space-y-3">
      {COMPONENT_TYPES.map((type) => {
        const regions = view.regions.filter((r) => r.type === type);
        if (!regions.length) return null;
        const isHidden = hidden.has(type);
        return (
          <div key={type}>
            <div className="mb-1 flex items-center gap-2">
              <span className="size-2.5 rounded-full" style={{ background: COMPONENT_META[type].color }} />
              <span className="text-xs font-bold uppercase tracking-wide text-muted">
                {COMPONENT_META[type].label} · {regions.length}
              </span>
              {COMPONENT_META[type].opening && <span className="text-[11px] text-faint">deducted from walls</span>}
              <IconButton
                label={isHidden ? "Show on photo" : "Hide on photo"}
                className="ml-auto size-7"
                onClick={() => {
                  const next = new Set(hidden);
                  if (isHidden) next.delete(type);
                  else next.add(type);
                  setHidden(next);
                }}
              >
                {isHidden ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
              </IconButton>
            </div>
            <div className="space-y-1">
              {regions.map((r) => (
                <button
                  key={r.id}
                  onClick={() => onSelect(r.id)}
                  className="flex w-full items-center gap-2 rounded-lg border border-line px-2.5 py-2 text-left text-sm hover:border-accent/40 hover:bg-tint"
                >
                  <span className="min-w-0 flex-1 truncate font-medium">{r.label}</span>
                  <span className="shrink-0 text-xs text-muted">{approxSize(r, view)}</span>
                  <SourceBadge region={r} />
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SourceBadge({ region }: { region: Region }) {
  if (region.source === "user") return <Badge>drawn</Badge>;
  if (region.source === "ai_box") return <Badge tone="warn">AI box</Badge>;
  return <Badge tone="accent">AI</Badge>;
}

/** Same rule as the estimator: railing materials are measured by length, everything else by area. */
function isMeasuredByLength(region: Region, data: ProjectData, catalog: Catalog | null): boolean {
  const material = materialById(catalog, activeDesign(data).assignments[region.id]?.material_id);
  if (material) return material.calc === "railing";
  return region.type === "railing";
}

function RegionInspector({
  region,
  view,
  measuredByLength,
  readOnly,
  onChange,
  onDelete,
  onAddPart,
  onClose,
}: {
  region: Region;
  view: View;
  measuredByLength: boolean;
  readOnly: boolean;
  onChange: (recipe: (r: Region) => void) => void;
  onDelete: () => void;
  onAddPart: () => void;
  onClose: () => void;
}) {
  const isRailing = measuredByLength;
  const isOpening = COMPONENT_META[region.type].opening;
  return (
    <div className="animate-rise space-y-3 rounded-xl border border-line p-3">
      <div className="flex items-center gap-2">
        <span className="size-3 rounded-full" style={{ background: COMPONENT_META[region.type].color }} />
        <span className="text-xs font-bold uppercase tracking-wide text-muted">Selected surface</span>
        <SourceBadge region={region} />
        <IconButton label="Back to list" className="ml-auto" onClick={onClose}>
          <X className="size-4" />
        </IconButton>
      </div>

      <Field label="Name">
        <input className={inputClass} value={region.label} maxLength={80} disabled={readOnly} onChange={(e) => onChange((r) => void (r.label = e.target.value))} />
      </Field>

      <div className="grid grid-cols-2 gap-2">
        <Field label="Type">
          <select className={inputClass} value={region.type} disabled={readOnly} onChange={(e) => onChange((r) => void (r.type = e.target.value as ComponentType))}>
            {COMPONENT_TYPES.map((t) => (
              <option key={t} value={t}>{COMPONENT_META[t].label}</option>
            ))}
          </select>
        </Field>
        <Field label="Faces to include">
          <select className={inputClass} value={region.face_factor} disabled={readOnly} onChange={(e) => onChange((r) => void (r.face_factor = Number(e.target.value)))}>
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>{n === 1 ? "Visible face" : `${n} faces`}</option>
            ))}
          </select>
        </Field>
      </div>
      {(region.type === "pillar" || region.type === "gate") && (
        <p className="-mt-1 text-[11px] text-muted">A photo shows only the front of a pillar or gate; include the faces you will also finish.</p>
      )}

      {view.planes.length > 1 && (
        <Field label="Depth plane" hint="Surfaces nearer or farther from the camera are measured with their own plane's scale.">
          <select className={inputClass} value={region.plane_id ?? view.planes[0].id} disabled={readOnly} onChange={(e) => onChange((r) => void (r.plane_id = e.target.value))}>
            {view.planes.map((pl) => (
              <option key={pl.id} value={pl.id}>{pl.name}</option>
            ))}
          </select>
        </Field>
      )}

      {!isOpening && (
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-[var(--color-accent)]"
            checked={region.remove_existing}
            disabled={readOnly}
            onChange={(e) => onChange((r) => void (r.remove_existing = e.target.checked))}
          />
          <span>
            Remove the existing finish first
            <span className="block text-[11px] text-muted">E.g. old tiles or cladding. Adds removal cost to the estimate.</span>
          </span>
        </label>
      )}

      {!isOpening && (
        <Field
          label={isRailing ? "Measured length on site (optional)" : "Measured area on site (optional)"}
          hint={`Overrides the photo measurement (${approxSize(region, view) ?? "no scale yet"}).`}
        >
          <NumberInput
            value={isRailing ? region.length_override_ft : region.area_override_sqft}
            onChange={(v) => onChange((r) => void (isRailing ? (r.length_override_ft = v) : (r.area_override_sqft = v)))}
            min={0}
            step={1}
            placeholder="Use photo measurement"
            suffix={isRailing ? "rft" : "sqft"}
            disabled={readOnly}
          />
        </Field>
      )}

      {region.source !== "user" && (
        <p className="text-xs text-muted">
          {region.source === "ai"
            ? `Outlined by SAM 2.1 from a Gemini detection (outline confidence ${Math.round((region.confidence ?? 0) * 100)}%).`
            : "Rough box from Gemini; precise outlining was unavailable. Adjust the corners."}
        </p>
      )}

      <div className="flex gap-2">
        <Button size="sm" icon={<Plus className="size-3.5" />} onClick={onAddPart} disabled={readOnly}>
          Add another part
        </Button>
        <Button size="sm" variant="danger" icon={<Trash2 className="size-3.5" />} onClick={onDelete} disabled={readOnly}>
          Delete
        </Button>
      </div>
    </div>
  );
}
