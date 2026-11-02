"use client";

import { ArrowRight, CircleHelp, Layers3, MousePointerClick, Plus, Ruler, Trash2, TriangleAlert } from "lucide-react";
import { useRef, useState, type PointerEvent } from "react";

import { RegionOverlay } from "@/components/stage/RegionOverlay";
import { pointerToPoint, Stage } from "@/components/stage/Stage";
import { Badge, Button, cx, inputClass, Notice, NumberInput } from "@/components/ui";
import { useWorkspace } from "@/components/workspace/context";
import { PanelHeading, StepLayout } from "@/components/workspace/StepLayout";
import { ViewSwitcher } from "@/components/workspace/ViewSwitcher";
import { imageUrl } from "@/lib/api";
import { formatNumber, uid } from "@/lib/format";
import { useViewDepth, type ViewDepth } from "@/lib/depth";
import { distance, planeScale, type PlaneScale } from "@/lib/geometry";
import type { CueKind, Plane, PlaneKind, Point, ScaleReference, View } from "@/lib/types";

const PLANE_COLORS = ["#2563eb", "#db2777", "#059669", "#d97706", "#7c3aed"];
const MIN_LINE_PX = 10; // shorter reference lines are too imprecise to measure with
const PRESETS: { label: string; ft: number; cue: CueKind; axis: ScaleReference["axis"] }[] = [
  { label: "Door", ft: 7, cue: "door", axis: "vertical" },
  { label: "Gate", ft: 6, cue: "gate", axis: "vertical" },
  { label: "Railing", ft: 3.5, cue: "railing", axis: "vertical" },
  { label: "Storey", ft: 10, cue: "storey", axis: "vertical" },
  { label: "Car", ft: 5, cue: "car", axis: "vertical" },
  { label: "Person", ft: 5.4, cue: "person", axis: "vertical" },
];
const PLANE_KINDS: { value: PlaneKind; label: string }[] = [
  { value: "house_front", label: "House front" },
  { value: "house_side", label: "House side" },
  { value: "boundary", label: "Compound wall & gate" },
  { value: "other", label: "Other" },
];

type Drawing = { planeId: string; refId: string | null; points: Point[] };
type Drag = { planeId: string; refId: string; end: "p1" | "p2"; moved: boolean };

export function ScaleStep() {
  const { store, view, goTo } = useWorkspace();
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<Drag | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawing, setDrawing] = useState<Drawing | null>(null);
  const [assigning, setAssigning] = useState(false);
  const { update, checkpoint } = store;
  const depth = useViewDepth(view);

  if (!view) return null;
  const selected = view.planes.find((p) => p.id === selectedId) ?? view.planes[0] ?? null;
  const colorOf = (id: string | null) => PLANE_COLORS[Math.max(0, view.planes.findIndex((p) => p.id === id)) % PLANE_COLORS.length];

  const updateView = (recipe: (v: View) => void, record = true) =>
    update((d) => {
      const v = d.views.find((x) => x.id === view.id);
      if (v) recipe(v as View);
    }, { record });
  const updatePlane = (planeId: string, recipe: (p: Plane) => void, record = true) =>
    updateView((v) => {
      const p = v.planes.find((x) => x.id === planeId);
      if (p) recipe(p);
    }, record);
  const updateRef = (planeId: string, refId: string, recipe: (r: ScaleReference, p: Plane) => void, record = true) =>
    updatePlane(planeId, (p) => {
      const r = p.references.find((x) => x.id === refId);
      if (r) recipe(r, p);
    }, record);

  function addPlane() {
    const id = uid("plane");
    updateView((v) => {
      v.planes.push({ id, name: `Plane ${v.planes.length + 1}`, kind: "other", references: [], fallback_plane_id: v.planes[0]?.id ?? null, confirmed: false });
    });
    setSelectedId(id);
  }

  function commitLine({ planeId, refId, points: [p1, p2] }: Drawing) {
    if (distance(p1, p2, view!.width, view!.height) < MIN_LINE_PX) return;
    if (refId) {
      updateRef(planeId, refId, (r, p) => {
        r.p1 = p1;
        r.p2 = p2;
        r.source = "manual";
        p.confirmed = false;
      });
      return;
    }
    // A new line's direction decides which scale it sets.
    const dx = Math.abs(p2[0] - p1[0]) * view!.width;
    const dy = Math.abs(p2[1] - p1[1]) * view!.height;
    const axis = dy > 2 * dx ? "vertical" : dx > 2 * dy ? "horizontal" : "free";
    updatePlane(planeId, (p) => {
      p.references.push({
        id: uid("ref"), name: `Measured length ${p.references.length + 1}`, cue: "custom", axis, p1, p2,
        real_length_ft: 7, source: "manual", weight: 1, enabled: true,
      });
      p.confirmed = false;
    });
  }

  function onPointerDown(e: PointerEvent<SVGSVGElement>) {
    const p = pointerToPoint(e, svgRef.current);
    if (drawing) {
      const next = { ...drawing, points: [...drawing.points, p] };
      if (next.points.length === 2) {
        commitLine(next);
        setDrawing(null);
      } else setDrawing(next);
      return;
    }
    const el = (e.target as Element).closest("[data-kind]") as SVGElement | null;
    if (el?.dataset.kind === "scale-end") {
      drag.current = { planeId: el.dataset.plane!, refId: el.dataset.ref!, end: el.dataset.end as "p1" | "p2", moved: false };
      setSelectedId(el.dataset.plane!);
      svgRef.current?.setPointerCapture(e.pointerId);
      return;
    }
    if (el?.dataset.kind === "scale-line") return setSelectedId(el.dataset.plane!);
    const regionId = (e.target as Element).closest("[data-region]")?.getAttribute("data-region");
    if (assigning && selected && regionId) {
      updateView((v) => {
        const r = v.regions.find((x) => x.id === regionId);
        if (r) r.plane_id = selected.id;
      });
    }
  }

  function onPointerMove(e: PointerEvent<SVGSVGElement>) {
    const d = drag.current;
    if (!d) return;
    const p = pointerToPoint(e, svgRef.current);
    const ref = view!.planes.find((x) => x.id === d.planeId)?.references.find((r) => r.id === d.refId);
    const other = ref && (d.end === "p1" ? ref.p2 : ref.p1);
    if (!other || distance(p, other, view!.width, view!.height) < MIN_LINE_PX) return; // keep a usable line
    if (!d.moved) {
      checkpoint();
      d.moved = true;
    }
    updateRef(d.planeId, d.refId, (r, plane) => {
      r[d.end] = p;
      r.source = "manual";
      plane.confirmed = false; // a moved line must be re-confirmed
    }, false);
  }

  function onPointerUp(e: PointerEvent<SVGSVGElement>) {
    if (drag.current) svgRef.current?.releasePointerCapture(e.pointerId);
    drag.current = null;
  }

  const surfaceCount = (planeId: string) => view.regions.filter((r) => (r.plane_id ?? view.planes[0]?.id) === planeId).length;

  return (
    <StepLayout
      toolbar={
        <>
          <ViewSwitcher />
          {drawing ? (
            <span className="rounded-lg bg-info-soft px-3 py-1.5 text-xs font-semibold text-info">
              Click the {drawing.points.length ? "second" : "first"} end of a length you know (e.g. top and bottom of a door)
              <button className="ml-2 underline" onClick={() => setDrawing(null)}>Cancel</button>
            </span>
          ) : assigning ? (
            <span className="rounded-lg bg-info-soft px-3 py-1.5 text-xs font-semibold text-info">
              Click surfaces that belong to “{selected?.name}”
              <button className="ml-2 underline" onClick={() => setAssigning(false)}>Done</button>
            </span>
          ) : (
            <span className="text-xs text-muted">Surfaces are coloured by depth plane. Drag a line&apos;s ends to adjust it.</span>
          )}
        </>
      }
      stage={
        <Stage
          width={view.width}
          height={view.height}
          svgRef={svgRef}
          cursor={drawing ? "crosshair" : assigning ? "pointer" : "default"}
          // eslint-disable-next-line @next/next/no-img-element -- photo served by the API
          background={<img src={imageUrl(view.image_id)} alt={view.name} className="absolute inset-0 size-full" />}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          overlay={({ unit }) => (
            <>
              <RegionOverlay view={view} unit={unit} selectedId={null} colorFor={(r) => colorOf(r.plane_id ?? view.planes[0]?.id ?? null)} />
              {view.planes.flatMap((plane) =>
                plane.references.map((ref) => (
                  <ScaleLine key={ref.id} plane={plane} reference={ref} view={view} unit={unit} color={colorOf(plane.id)} active={plane.id === selected?.id} />
                )),
              )}
              {drawing?.points.map(([x, y], i) => (
                <circle key={i} cx={x * view.width} cy={y * view.height} r={6 * unit} fill="#fff" stroke="#111" strokeWidth={2 * unit} />
              ))}
            </>
          )}
        />
      }
      panel={
        <>
          <PanelHeading
            title="Scale"
            subtitle="Each depth plane is measured from the objects of known size on it. More cues that agree = a more reliable estimate."
          />

          {depth && view.planes.length > 0 && (
            <p className="flex gap-1.5 text-xs text-muted">
              <Layers3 className="mt-px size-3.5 shrink-0 text-accent" />
              <span>
                <b className="text-ink">Distance-aware.</b> A depth model estimated how far each surface is from the camera, so references
                near and far agree and every surface is measured at its own distance.
              </span>
            </p>
          )}
          {view.planes.length === 0 && (
            <Notice tone="warn" icon={<Ruler className="size-4" />} title="No scale yet">
              Add a depth plane, then draw a line over something whose real length you know: a door (usually 7 ft), the gate, a
              railing, or a wall you have measured.
            </Notice>
          )}

          {view.planes.map((plane) => (
            <PlaneCard
              key={plane.id}
              plane={plane}
              view={view}
              depth={depth}
              color={colorOf(plane.id)}
              active={plane.id === selected?.id}
              surfaces={surfaceCount(plane.id)}
              onSelect={() => setSelectedId(plane.id)}
              onPlane={(recipe) => updatePlane(plane.id, recipe)}
              onRef={(refId, recipe) => updateRef(plane.id, refId, recipe)}
              onDraw={(refId) => setDrawing({ planeId: plane.id, refId, points: [] })}
              onAssign={() => {
                setSelectedId(plane.id);
                setAssigning(true);
              }}
              onRemove={() =>
                updateView((v) => {
                  v.planes = v.planes.filter((x) => x.id !== plane.id);
                  v.planes.forEach((x) => x.fallback_plane_id === plane.id && (x.fallback_plane_id = null));
                  v.regions.forEach((r) => r.plane_id === plane.id && (r.plane_id = null));
                })
              }
            />
          ))}

          <Button className="w-full" icon={<Plus className="size-4" />} onClick={addPlane}>
            Add a depth plane
          </Button>

          <div className="flex gap-2 rounded-xl bg-canvas p-3 text-xs leading-relaxed text-muted">
            <CircleHelp className="size-4 shrink-0" />
            <span>
              Each cue implies feet-per-pixel = real length ÷ line length. A plane uses the weighted median of its cues and ignores
              outliers; vertical and horizontal lines are kept separate, which corrects walls seen at an angle. Things nearer the
              camera look bigger, so the compound wall and the house need separate planes.
            </span>
          </div>

          <Button variant="primary" className="w-full" onClick={() => goTo("design")}>
            Next: design <ArrowRight className="size-4" />
          </Button>
        </>
      }
    />
  );
}

function ConfidenceBadge({ scale }: { scale: PlaneScale | null }) {
  if (!scale) return <Badge tone="danger">No scale</Badge>;
  const pct = Math.round(scale.confidence * 100);
  if (scale.confidence >= 0.8) return <Badge tone="accent">High · {pct}%</Badge>;
  if (scale.confidence >= 0.5) return <Badge tone="info">Medium · {pct}%</Badge>;
  return <Badge tone="warn">Low · {pct}%</Badge>;
}

function PlaneCard({
  plane,
  view,
  depth,
  color,
  active,
  surfaces,
  onSelect,
  onPlane,
  onRef,
  onDraw,
  onAssign,
  onRemove,
}: {
  plane: Plane;
  view: View;
  depth: ViewDepth | null;
  color: string;
  active: boolean;
  surfaces: number;
  onSelect: () => void;
  onPlane: (recipe: (p: Plane) => void) => void;
  onRef: (refId: string, recipe: (r: ScaleReference, p: Plane) => void) => void;
  onDraw: (refId: string | null) => void;
  onAssign: () => void;
  onRemove: () => void;
}) {
  const scale = planeScale(plane, view, depth);
  const cameraOnly = Boolean(scale?.cameraOnly);
  // A value the user typed is a measurement, not a guess: it becomes "manual" and needs re-confirming.
  const editRef = (refId: string, recipe: (r: ScaleReference) => void) =>
    onRef(refId, (r, p) => {
      recipe(r);
      r.source = "manual";
      p.confirmed = false;
    });

  return (
    <div onClick={onSelect} className={cx("space-y-3 rounded-xl border p-3 transition-colors", active ? "border-accent/50 bg-tint" : "border-line")}>
      <div className="flex items-center gap-2">
        <span className="size-3 shrink-0 rounded-full" style={{ background: color }} />
        <input
          className="min-w-0 flex-1 rounded bg-transparent text-sm font-bold outline-none focus:bg-surface"
          value={plane.name}
          onChange={(e) => onPlane((p) => void (p.name = e.target.value))}
          aria-label="Plane name"
        />
        <ConfidenceBadge scale={scale} />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <select
          className={cx(inputClass, "h-7 w-auto py-0 text-xs")}
          value={plane.kind}
          onChange={(e) => onPlane((p) => void (p.kind = e.target.value as PlaneKind))}
          aria-label="Plane type"
        >
          {PLANE_KINDS.map((k) => (
            <option key={k.value} value={k.value}>{k.label}</option>
          ))}
        </select>
        <span>{surfaces} surfaces</span>
        {scale && (
          <span>
            · {formatNumber(1 / scale.ftPerPxY)} px/ft
            {Math.abs(scale.ftPerPxX / scale.ftPerPxY - 1) > 0.03 && ` (horizontal ${formatNumber(1 / scale.ftPerPxX)})`}
            {scale.refDepthM != null && ` at ${scale.refDepthM.toFixed(1)} m`}
          </span>
        )}
      </div>

      {scale?.borrowedFrom && (
        <p className="text-xs text-warn">
          No references here yet, so this plane borrows the scale of “{scale.borrowedFrom}”
          {depth ? ", corrected for distance by the depth map" : " (lower confidence)"}. Add a length you know.
        </p>
      )}
      {cameraOnly && (
        <p className="text-xs text-warn">
          No references at all: sizes come from the depth model and a typical phone lens alone (rough, ±20% or more). Draw a length you know.
        </p>
      )}
      {scale && scale.cuesRejected.length > 0 && (
        <p className="flex gap-1 text-xs text-warn">
          <TriangleAlert className="mt-px size-3.5 shrink-0" /> Ignored as outliers: {scale.cuesRejected.join(", ")}
        </p>
      )}

      <div className="space-y-2">
        {plane.references.map((r) => (
          <div key={r.id} className={cx("space-y-2 rounded-lg border border-line bg-surface p-2", !r.enabled && "opacity-55")}>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                className="size-4 accent-[var(--color-accent)]"
                checked={r.enabled}
                onChange={(e) => onRef(r.id, (x, p) => {
                  x.enabled = e.target.checked;
                  p.confirmed = false;
                })}
                aria-label="Use this reference"
              />
              <input
                className="min-w-0 flex-1 rounded bg-transparent text-xs font-semibold outline-none focus:bg-canvas"
                value={r.name}
                onChange={(e) => onRef(r.id, (x) => void (x.name = e.target.value))}
                aria-label="Reference name"
              />
              {r.source === "auto" ? <Badge tone="info">AI · trust {Math.round(r.weight * 100)}%</Badge> : <Badge>measured</Badge>}
            </div>
            <div className="grid grid-cols-[1fr_auto] gap-2">
              <NumberInput value={r.real_length_ft} min={0.1} max={200} step={0.5} suffix="ft" ariaLabel="Real length"
                onChange={(v) => v && v > 0 && editRef(r.id, (x) => void (x.real_length_ft = v))} />
              <select className={cx(inputClass, "w-auto text-xs")} value={r.axis} aria-label="Direction"
                onChange={(e) => editRef(r.id, (x) => void (x.axis = e.target.value as ScaleReference["axis"]))}>
                <option value="vertical">Vertical</option>
                <option value="horizontal">Horizontal</option>
                <option value="free">Both</option>
              </select>
            </div>
            <div className="flex flex-wrap items-center gap-1">
              {PRESETS.map((preset) => (
                <button key={preset.label} onClick={() => editRef(r.id, (x) => {
                  x.real_length_ft = preset.ft;
                  x.cue = preset.cue;
                  x.axis = preset.axis;
                })} className="rounded-md border border-line px-1.5 py-0.5 text-[11px] font-semibold text-ink-soft hover:border-accent/40 hover:bg-canvas">
                  {preset.label} {formatNumber(preset.ft)}
                </button>
              ))}
              <button className="ml-auto text-[11px] font-semibold text-accent hover:underline" onClick={() => onDraw(r.id)}>Redraw</button>
              <button className="text-faint hover:text-danger" aria-label="Delete reference" onClick={() => onPlane((p) => {
                p.references = p.references.filter((x) => x.id !== r.id);
                p.confirmed = false;
              })}>
                <Trash2 className="size-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <label className="flex items-start gap-2 rounded-lg bg-surface p-2 text-sm">
        <input type="checkbox" className="mt-0.5 size-4 accent-[var(--color-accent)]" checked={plane.confirmed}
          onChange={(e) => onPlane((p) => void (p.confirmed = e.target.checked))} />
        <span>
          <b>Confirmed:</b> I&apos;ve checked these lengths on this plane.
        </span>
      </label>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" icon={<Ruler className="size-3.5" />} onClick={() => onDraw(null)}>Add reference</Button>
        {view.planes.length > 1 && (
          <Button size="sm" icon={<MousePointerClick className="size-3.5" />} onClick={onAssign}>Assign surfaces</Button>
        )}
        <Button size="sm" variant="ghost" icon={<Trash2 className="size-3.5" />} onClick={onRemove}>Remove plane</Button>
      </div>
    </div>
  );
}

function ScaleLine({ plane, reference, view, unit, color, active }: { plane: Plane; reference: ScaleReference; view: View; unit: number; color: string; active: boolean }) {
  const [x1, y1] = [reference.p1[0] * view.width, reference.p1[1] * view.height];
  const [x2, y2] = [reference.p2[0] * view.width, reference.p2[1] * view.height];
  const label = `${formatNumber(reference.real_length_ft)} ft`;
  const dash = reference.enabled ? undefined : `${4 * unit} ${4 * unit}`;
  return (
    <g opacity={reference.enabled ? 1 : 0.5}>
      <line data-kind="scale-line" data-plane={plane.id} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#fff" strokeWidth={(active ? 6 : 4.5) * unit} strokeLinecap="round" style={{ cursor: "pointer" }} />
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={(active ? 3 : 2) * unit} strokeLinecap="round" strokeDasharray={dash} pointerEvents="none" />
      {(["p1", "p2"] as const).map((end) => (
        <circle key={end} data-kind="scale-end" data-plane={plane.id} data-ref={reference.id} data-end={end}
          cx={end === "p1" ? x1 : x2} cy={end === "p1" ? y1 : y2} r={(active ? 6.5 : 5) * unit}
          fill="#fff" stroke={color} strokeWidth={2.5 * unit} style={{ cursor: "move" }} />
      ))}
      <g transform={`translate(${(x1 + x2) / 2 + 10 * unit}, ${(y1 + y2) / 2})`} pointerEvents="none">
        <rect x={0} y={-10 * unit} width={(label.length * 7 + 14) * unit} height={20 * unit} rx={6 * unit} fill={color} />
        <text x={7 * unit} y={4.5 * unit} fontSize={12 * unit} fontWeight={700} fill="#fff">{label}</text>
      </g>
    </g>
  );
}
