"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DesignStep } from "@/components/steps/DesignStep";
import { EstimateStep } from "@/components/steps/EstimateStep";
import { PhotosStep } from "@/components/steps/PhotosStep";
import { ReportStep } from "@/components/steps/ReportStep";
import { ScaleStep } from "@/components/steps/ScaleStep";
import { SurfacesStep } from "@/components/steps/SurfacesStep";
import { toast } from "@/components/Toaster";
import { api, ApiError } from "@/lib/api";
import { useCatalog } from "@/lib/hooks";
import { withUniqueIds } from "@/lib/project";
import type { Project } from "@/lib/types";
import { useProjectStore } from "@/lib/useProjectStore";

import { WorkspaceContext, type Step, type WorkspaceContextValue } from "./context";
import { StepNav } from "./StepNav";
import { TopBar } from "./TopBar";

export function Workspace({ initial }: { initial: Project }) {
  const store = useProjectStore(initial);
  const { data } = store;
  const { catalog } = useCatalog();

  const hasRegions = initial.data.views.some((v) => v.regions.length > 0);
  const [step, setStep] = useState<Step>(hasRegions ? "design" : "photos");
  const [viewId, setViewId] = useState(initial.data.views[0]?.id ?? "");
  const [selectedRegionId, selectRegion] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState<Record<string, boolean>>({});

  const view = data.views.find((v) => v.id === viewId) ?? data.views[0];
  const { update } = store;

  const analyzeView = useCallback(
    async (targetId: string) => {
      const target = data.views.find((v) => v.id === targetId);
      if (!target) return;
      setAnalyzing((a) => ({ ...a, [targetId]: true }));
      try {
        const result = await api.analyzeImage(target.image_id);
        update((draft) => {
          const v = draft.views.find((x) => x.id === targetId);
          if (!v) return;
          // Old regions of this photo are replaced: drop their materials from every design.
          for (const design of draft.designs) for (const r of v.regions) delete design.assignments[r.id];
          v.regions = withUniqueIds(result.regions, draft as typeof data, targetId);
          v.scene = result.scene;
          // Keep planes the user measured or confirmed; otherwise take the AI's planes and cues.
          const userPlanes = v.planes.some((p) => p.confirmed || p.references.some((r) => r.source === "manual"));
          if (!userPlanes) v.planes = result.planes;
          else
            for (const r of v.regions) {
              // AI plane ids are kinds ("boundary", ...); point each region at the user's plane of that kind.
              const kept = v.planes.find((p) => p.id === r.plane_id) ?? v.planes.find((p) => p.kind === r.plane_id);
              r.plane_id = kept?.id ?? null;
            }
        });
        selectRegion(null);
        result.warnings.forEach((w) => toast(w, "info"));
        if (!result.scene.usable) toast("The AI thinks this photo is hard to work with; see the tips on the Photos step.", "info");
        else toast(`Found ${result.regions.length} building parts. Review them, then check the scale.`, "success");
      } catch (error) {
        toast(error instanceof ApiError ? error.message : "AI analysis failed.", "error");
      } finally {
        setAnalyzing((a) => ({ ...a, [targetId]: false }));
      }
    },
    [data.views, update],
  );

  // New photos are analysed automatically once.
  const autoAnalyzed = useRef(new Set<string>());
  useEffect(() => {
    if (!initial.can_edit) return;
    for (const v of data.views) {
      if (v.regions.length === 0 && v.scene === null && !autoAnalyzed.current.has(v.id)) {
        autoAnalyzed.current.add(v.id);
        void analyzeView(v.id).then(() => setStep((s) => (s === "photos" ? "surfaces" : s)));
      }
    }
  }, [data.views, analyzeView, initial.can_edit]);

  // Global undo / redo shortcuts (ignored while typing in a field).
  const { undo, redo } = store;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest("input, textarea, select, [contenteditable]")) return;
      if (!(e.ctrlKey || e.metaKey)) return;
      const key = e.key.toLowerCase();
      if (key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (key === "y" || (key === "z" && e.shiftKey)) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo]);

  const goTo = useCallback((s: Step) => setStep(s), []);
  const context: WorkspaceContextValue = useMemo(
    () => ({ store, catalog, view, setViewId, selectedRegionId, selectRegion, goTo, analyzing, analyzeView }),
    [store, catalog, view, selectedRegionId, goTo, analyzing, analyzeView],
  );

  return (
    <WorkspaceContext.Provider value={context}>
      <div className="flex min-h-screen flex-col lg:h-screen">
        <TopBar />
        <StepNav step={step} onChange={setStep} />
        <main className="min-h-0 flex-1">
          {step === "photos" && <PhotosStep />}
          {step === "surfaces" && <SurfacesStep />}
          {step === "scale" && <ScaleStep />}
          {step === "design" && <DesignStep />}
          {step === "estimate" && <EstimateStep />}
          {step === "report" && <ReportStep />}
        </main>
      </div>
    </WorkspaceContext.Provider>
  );
}
