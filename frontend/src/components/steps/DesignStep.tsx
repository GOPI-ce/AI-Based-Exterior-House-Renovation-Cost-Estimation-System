"use client";

import { ArrowRight, MousePointerClick, Sparkles, SquareDashed, X } from "lucide-react";
import { useRef, useState } from "react";

import { AiDesigner } from "@/components/design/AiDesigner";
import { DesignTabs } from "@/components/design/DesignTabs";
import { MaterialPicker } from "@/components/design/MaterialPicker";
import { RegionOverlay } from "@/components/stage/RegionOverlay";
import { RenderedPreview, type CompareMode } from "@/components/stage/RenderedPreview";
import { pointerToPoint, Stage } from "@/components/stage/Stage";
import { Button, IconButton, Notice, Segmented, Spinner } from "@/components/ui";
import { useWorkspace } from "@/components/workspace/context";
import { PanelHeading, StepLayout } from "@/components/workspace/StepLayout";
import { ViewSwitcher } from "@/components/workspace/ViewSwitcher";
import { formatINRShort } from "@/lib/format";
import { COMPONENT_META, regionAt } from "@/lib/geometry";
import { useEstimate } from "@/lib/hooks";
import { activeDesign, materialSwatch } from "@/lib/project";
import type { Assignment, Catalog, ComponentType, Region, View } from "@/lib/types";

/** Sensible first choices per component type, so a new project shows a redesign in one click. */
const STARTER: Partial<Record<ComponentType, Assignment>> = {
  wall: { material_id: "ap_apex_ultima", color: "#EDE4D3" },
  parapet: { material_id: "ap_apex_ultima", color: "#EDE4D3" },
  roof_edge: { material_id: "ap_apex_ultima", color: "#F4F2EC" },
  balcony: { material_id: "ap_apex_ultima", color: "#3C4044" },
  pillar: { material_id: "stone_slate", color: null },
  railing: { material_id: "rail_ss_glass", color: null },
  gate: { material_id: "metal_enamel", color: "#2F3A3F" },
};

export function DesignStep() {
  const { store, catalog, view, selectedRegionId, selectRegion, goTo } = useWorkspace();
  const svgRef = useRef<SVGSVGElement>(null);
  const [mode, setMode] = useState<CompareMode>("after");
  const [outlines, setOutlines] = useState(false);
  const design = activeDesign(store.data);
  const { estimate, loading } = useEstimate(store.data, design.id);

  if (!view) return null;
  const selected = view.regions.find((r) => r.id === selectedRegionId) ?? null;
  const assignedCount = view.regions.filter((r) => design.assignments[r.id]).length;

  const setAssignment = (regionIds: string[], assignment: Assignment | null) =>
    store.update((d) => {
      const target = d.designs.find((x) => x.id === design.id);
      if (!target) return;
      for (const id of regionIds) {
        if (assignment) target.assignments[id] = { ...assignment };
        else delete target.assignments[id];
      }
    });

  function applyStarter() {
    store.update((d) => {
      const target = d.designs.find((x) => x.id === design.id);
      if (!target) return;
      for (const v of d.views)
        for (const r of v.regions) {
          const starter = STARTER[r.type];
          if (starter && !target.assignments[r.id]) target.assignments[r.id] = { ...starter };
        }
    });
  }

  return (
    <StepLayout
      toolbar={
        <>
          <ViewSwitcher />
          <Segmented<CompareMode>
            size="sm"
            value={mode}
            onChange={setMode}
            options={[
              { value: "after", label: "After" },
              { value: "split", label: "Before | After" },
              { value: "before", label: "Before" },
            ]}
          />
          <IconButton label={outlines ? "Hide outlines" : "Show outlines"} active={outlines} onClick={() => setOutlines((o) => !o)}>
            <SquareDashed className="size-4" />
          </IconButton>
          <span className="hidden items-center gap-1 text-xs text-muted md:flex">
            <MousePointerClick className="size-3.5" /> Click a surface on the photo to change its material
          </span>
        </>
      }
      stage={
        <Stage
          width={view.width}
          height={view.height}
          svgRef={svgRef}
          cursor="pointer"
          background={<RenderedPreview view={view} design={design} catalog={catalog} mode={mode} />}
          onPointerDown={(e) => selectRegion(regionAt(pointerToPoint(e, svgRef.current), view.regions)?.id ?? null)}
          overlay={({ unit }) =>
            outlines || selected ? (
              <RegionOverlay
                view={outlines ? view : { ...view, regions: selected ? [selected] : [] }}
                unit={unit}
                selectedId={selected?.id ?? null}
                dimUnselected
              />
            ) : null
          }
        />
      }
      panel={
        <>
          <div className="flex items-end justify-between gap-3 rounded-xl bg-accent px-4 py-3 text-white">
            <div>
              <p className="text-xs font-semibold opacity-80">{design.name} · estimated total</p>
              <p className="text-2xl font-extrabold tracking-tight">{estimate ? formatINRShort(estimate.grand_total) : "…"}</p>
              {estimate && estimate.grand_total > 0 && (
                <p className="text-[11px] opacity-80">
                  likely {formatINRShort(estimate.low_total)} – {formatINRShort(estimate.high_total)}
                </p>
              )}
            </div>
            {loading ? <Spinner className="text-white" /> : (
              <button className="text-xs font-semibold underline opacity-90" onClick={() => goTo("estimate")}>
                Details
              </button>
            )}
          </div>

          <DesignTabs />
          {!selected && <AiDesigner />}

          {selected ? (
            <SelectedSurface
              region={selected}
              view={view}
              catalog={catalog}
              onClose={() => selectRegion(null)}
              assignment={design.assignments[selected.id]}
              onAssign={(a) => setAssignment([selected.id], a)}
              onApplyToSameType={() => {
                const a = design.assignments[selected.id];
                if (a) setAssignment(view.regions.filter((r) => r.type === selected.type).map((r) => r.id), a);
              }}
              onClear={() => setAssignment([selected.id], null)}
            />
          ) : (
            <>
              <PanelHeading title="Surfaces in this design" subtitle="Pick a surface here or on the photo." />
              {assignedCount === 0 && view.regions.length > 0 && (
                <Notice tone="info" icon={<Sparkles className="size-4" />} title="Start quickly">
                  <p>Fill this design with sensible defaults (paint, stone pillars, glass railing), then fine-tune each surface.</p>
                  <Button size="sm" variant="primary" className="mt-2" onClick={applyStarter}>
                    Apply a starter design
                  </Button>
                </Notice>
              )}
              <SurfaceList view={view} catalog={catalog} assignments={design.assignments} onSelect={selectRegion} />
            </>
          )}

          <Button variant="primary" className="w-full" onClick={() => goTo("estimate")}>
            See quantities & cost <ArrowRight className="size-4" />
          </Button>
        </>
      }
    />
  );
}

function SelectedSurface({
  region,
  view,
  catalog,
  onClose,
  assignment,
  onAssign,
  onApplyToSameType,
  onClear,
}: {
  region: Region;
  view: View;
  catalog: Catalog | null;
  onClose: () => void;
  assignment: Assignment | undefined;
  onAssign: (a: Assignment) => void;
  onApplyToSameType: () => void;
  onClear: () => void;
}) {
  const isOpening = COMPONENT_META[region.type].opening;
  return (
    <div className="animate-rise space-y-3">
      <div className="flex items-center gap-2">
        <span className="size-3 rounded-full" style={{ background: COMPONENT_META[region.type].color }} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold">{region.label}</p>
          <p className="text-xs text-muted">{COMPONENT_META[region.type].label}</p>
        </div>
        <IconButton label="Back to list" onClick={onClose}>
          <X className="size-4" />
        </IconButton>
      </div>
      {assignment?.note && (
        <p className="flex gap-1.5 rounded-lg bg-tint px-2.5 py-2 text-xs text-ink-soft">
          <Sparkles className="mt-px size-3.5 shrink-0 text-accent" /> {assignment.note}
        </p>
      )}
      {isOpening ? (
        <Notice tone="info">Windows and doors are kept as they are; their area is deducted from the surrounding walls.</Notice>
      ) : catalog ? (
        <MaterialPicker
          region={region}
          catalog={catalog}
          assignment={assignment}
          sameTypeCount={view.regions.filter((r) => r.type === region.type).length}
          onAssign={onAssign}
          onApplyToSameType={onApplyToSameType}
          onClear={onClear}
        />
      ) : (
        <Spinner />
      )}
    </div>
  );
}

function SurfaceList({
  view,
  catalog,
  assignments,
  onSelect,
}: {
  view: View;
  catalog: Catalog | null;
  assignments: Record<string, Assignment>;
  onSelect: (id: string) => void;
}) {
  const surfaces = view.regions.filter((r) => !COMPONENT_META[r.type].opening);
  if (!surfaces.length) return <p className="text-sm text-muted">No surfaces yet: add them in the Surfaces step.</p>;
  return (
    <div className="space-y-1">
      {surfaces.map((r) => {
        const a = assignments[r.id];
        const material = catalog?.materials.find((m) => m.id === a?.material_id);
        return (
          <button key={r.id} onClick={() => onSelect(r.id)} className="flex w-full items-center gap-2.5 rounded-lg border border-line px-2.5 py-2 text-left hover:border-accent/40 hover:bg-tint">
            <span className="size-7 shrink-0 rounded-md border border-line" style={material ? materialSwatch(material, a?.color) : { background: "repeating-linear-gradient(45deg,#eef1ee 0 4px,#fff 4px 8px)" }} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{r.label}</span>
              <span className="block truncate text-xs text-muted">{material?.name ?? "Unchanged"}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
