"use client";

import { ArrowRight, Building2, ImagePlus, Lightbulb, RefreshCw, ScanSearch, Trash2, TriangleAlert } from "lucide-react";
import { useRef } from "react";

import { usePhotoUpload } from "@/components/photos/usePhotoUpload";
import { Stage, toSvgPoints } from "@/components/stage/Stage";
import { Badge, Button, cx, Notice, Spinner } from "@/components/ui";
import { useWorkspace } from "@/components/workspace/context";
import { PanelHeading, StepLayout } from "@/components/workspace/StepLayout";
import { imageUrl } from "@/lib/api";
import { COMPONENT_META, layerOrder } from "@/lib/geometry";
import { newView } from "@/lib/project";
import type { View } from "@/lib/types";

const VIEW_TYPES: Record<string, string> = {
  front: "Front view",
  angled: "Angled view (two sides)",
  side: "Side view",
  close_up: "Close-up",
  aerial: "Aerial view",
  not_a_building: "Not a building",
};

export function PhotosStep() {
  const { store, view, setViewId, goTo, analyzing, analyzeView } = useWorkspace();
  const fileInput = useRef<HTMLInputElement>(null);
  const { upload, busy, dialog } = usePhotoUpload();
  const readOnly = store.status === "readonly";

  async function addPhoto(file: File | undefined) {
    if (!file) return;
    const info = await upload(file);
    if (!info) return;
    const created = newView(info, `Photo ${store.data.views.length + 1}`);
    store.update((d) => {
      d.views.push(created);
    });
    setViewId(created.id);
  }

  function removeView(target: View) {
    if (!confirm(`Remove "${target.name}" and its regions from this project?`)) return;
    store.update((d) => {
      d.views = d.views.filter((v) => v.id !== target.id);
      for (const design of d.designs) for (const r of target.regions) delete design.assignments[r.id];
    });
    const next = store.data.views.find((v) => v.id !== target.id);
    if (next) setViewId(next.id);
  }

  return (
    <StepLayout
      stage={
        view && (
          <Stage
            width={view.width}
            height={view.height}
            // eslint-disable-next-line @next/next/no-img-element -- photo served by the API
            background={<img src={imageUrl(view.image_id)} alt={view.name} className="absolute inset-0 size-full" />}
            overlay={({ unit }) =>
              layerOrder(view.regions).map((r) =>
                r.polygons.map((poly, i) => (
                  <polygon
                    key={`${r.id}-${i}`}
                    points={toSvgPoints(poly, view.width, view.height)}
                    fill={COMPONENT_META[r.type].color}
                    fillOpacity={0.14}
                    stroke={COMPONENT_META[r.type].color}
                    strokeWidth={1.5 * unit}
                  />
                )),
              )
            }
          />
        )
      }
      panel={
        <>
          <PanelHeading
            title="Photos"
            subtitle="Add clear daylight photos of the outside: the front, plus sides if you want them estimated too. Each photo is analysed separately."
          />

          <div className="space-y-2">
            {store.data.views.map((v) => (
              <ViewCard
                key={v.id}
                view={v}
                active={v.id === view?.id}
                analyzing={!!analyzing[v.id]}
                readOnly={readOnly}
                canRemove={store.data.views.length > 1}
                onSelect={() => setViewId(v.id)}
                onRename={(name) =>
                  store.update((d) => {
                    const target = d.views.find((x) => x.id === v.id);
                    if (target) target.name = name;
                  })
                }
                onAnalyze={() => analyzeView(v.id)}
                onRemove={() => removeView(v)}
              />
            ))}
          </div>

          {!readOnly && (
            <>
              <Button className="w-full" loading={busy} icon={<ImagePlus className="size-4" />} onClick={() => fileInput.current?.click()}>
                Add another photo
              </Button>
              <input
                ref={fileInput}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                hidden
                onChange={(e) => {
                  void addPhoto(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </>
          )}

          <Button variant="primary" className="w-full" onClick={() => goTo("surfaces")}>
            Review detected surfaces <ArrowRight className="size-4" />
          </Button>
          {dialog}
        </>
      }
    />
  );
}

function ViewCard({
  view,
  active,
  analyzing,
  readOnly,
  canRemove,
  onSelect,
  onRename,
  onAnalyze,
  onRemove,
}: {
  view: View;
  active: boolean;
  analyzing: boolean;
  readOnly: boolean;
  canRemove: boolean;
  onSelect: () => void;
  onRename: (name: string) => void;
  onAnalyze: () => void;
  onRemove: () => void;
}) {
  const warnings = view.quality?.issues.filter((i) => i.severity === "warning") ?? [];
  const scene = view.scene;

  return (
    <div
      className={cx("rounded-xl border p-3 transition-colors", active ? "border-accent/50 bg-tint" : "border-line hover:border-line-strong")}
      onClick={onSelect}
    >
      <div className="flex gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- photo served by the API */}
        <img src={imageUrl(view.image_id)} alt="" className="h-16 w-20 shrink-0 rounded-lg object-cover" />
        <div className="min-w-0 flex-1">
          <input
            value={view.name}
            disabled={readOnly}
            onChange={(e) => onRename(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            className="w-full rounded bg-transparent text-sm font-semibold outline-none focus:bg-surface disabled:text-ink"
            aria-label="Photo name"
          />
          <p className="text-xs text-muted">
            {view.width} × {view.height}px
          </p>
          <div className="mt-1 flex flex-wrap gap-1">
            {analyzing ? (
              <Badge tone="info">
                <Spinner className="size-3" /> Analysing…
              </Badge>
            ) : view.regions.length ? (
              <Badge tone="accent">
                <ScanSearch className="size-3" /> {view.regions.length} parts
              </Badge>
            ) : (
              <Badge>Not analysed</Badge>
            )}
            {scene && <Badge>{VIEW_TYPES[scene.view_type] ?? scene.view_type}</Badge>}
            {scene?.storeys ? <Badge>{scene.storeys} storey{scene.storeys > 1 ? "s" : ""}</Badge> : null}
          </div>
        </div>
      </div>

      {analyzing && (
        <p className="mt-2 text-xs text-muted">
          Gemini is identifying the building parts, then SAM traces their outlines. This takes about 15–30 seconds.
        </p>
      )}

      {(warnings.length > 0 || (scene && (!scene.usable || scene.issues.length > 0))) && (
        <div className="mt-3 space-y-2">
          {scene && !scene.is_residential_exterior && (
            <Notice tone="danger" icon={<Building2 className="size-4" />} title="This doesn't look like a house exterior">
              Estimates need a photo of the outside of a residential building.
            </Notice>
          )}
          {warnings.map((w) => (
            <Notice key={w.code} tone="warn" icon={<TriangleAlert className="size-4" />}>
              {w.message}
            </Notice>
          ))}
          {scene && scene.issues.length > 0 && (
            <Notice tone={scene.usable ? "info" : "warn"} icon={<Lightbulb className="size-4" />} title={scene.usable ? "AI notes" : "The AI found problems with this photo"}>
              <ul className="list-disc space-y-0.5 pl-4">
                {[...scene.issues, ...scene.guidance].map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </Notice>
          )}
        </div>
      )}

      {!readOnly && (
        <div className="mt-3 flex gap-2" onClick={(e) => e.stopPropagation()}>
          <Button
            size="sm"
            loading={analyzing}
            icon={<RefreshCw className="size-3.5" />}
            onClick={() => {
              if (!view.regions.length || confirm("Re-running replaces the current regions (you can undo this). Continue?")) onAnalyze();
            }}
          >
            {view.regions.length ? "Re-run AI" : "Detect parts with AI"}
          </Button>
          {canRemove && (
            <Button size="sm" variant="ghost" icon={<Trash2 className="size-3.5" />} onClick={onRemove}>
              Remove
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
