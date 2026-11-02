"use client";

import { Calculator, Camera, Check, FileText, Palette, Ruler, ScanSearch } from "lucide-react";

import { cx } from "@/components/ui";
import { activeDesign } from "@/lib/project";

import { useWorkspace, type Step } from "./context";

const STEPS: { id: Step; label: string; icon: typeof Camera }[] = [
  { id: "photos", label: "Photos", icon: Camera },
  { id: "surfaces", label: "Surfaces", icon: ScanSearch },
  { id: "scale", label: "Scale", icon: Ruler },
  { id: "design", label: "Design", icon: Palette },
  { id: "estimate", label: "Estimate", icon: Calculator },
  { id: "report", label: "Report", icon: FileText },
];

export function StepNav({ step, onChange }: { step: Step; onChange: (s: Step) => void }) {
  const { store } = useWorkspace();
  const { data } = store;
  const done: Record<Step, boolean> = {
    photos: data.views.length > 0,
    surfaces: data.views.some((v) => v.regions.length > 0),
    scale: data.views.length > 0 && data.views.every((v) => v.planes.length > 0 && v.planes.every((p) => p.confirmed)),
    design: Object.keys(activeDesign(data).assignments).length > 0,
    estimate: false,
    report: false,
  };

  return (
    <nav className="scroll-thin flex shrink-0 gap-1 overflow-x-auto border-b border-line bg-surface px-2 sm:px-4" aria-label="Steps">
      {STEPS.map(({ id, label, icon: Icon }, i) => {
        const active = id === step;
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            aria-current={active ? "step" : undefined}
            className={cx(
              "relative flex shrink-0 items-center gap-2 px-3 py-3 text-sm font-semibold transition-colors",
              active ? "text-accent" : "text-muted hover:text-ink",
            )}
          >
            <span
              className={cx(
                "grid size-5 place-items-center rounded-full text-[10px] font-bold",
                done[id] ? "bg-accent text-white" : active ? "bg-accent-soft text-accent" : "bg-canvas text-faint",
              )}
            >
              {done[id] ? <Check className="size-3" strokeWidth={3} /> : i + 1}
            </span>
            <Icon className="hidden size-4 sm:block" />
            {label}
            {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent" />}
          </button>
        );
      })}
    </nav>
  );
}
