"use client";

import { ChevronDown, Cpu } from "lucide-react";
import { useState } from "react";

import { cx } from "@/components/ui";

type Pipeline = Record<string, string | number | boolean>;

/** What the AI pipeline did for a photo: each stage, the model that ran it, its time and any fallback. */
export function PipelineTrace({ pipeline }: { pipeline: Pipeline }) {
  const [open, setOpen] = useState(false);
  const str = (k: string) => (typeof pipeline[k] === "string" ? (pipeline[k] as string) : null);
  const num = (k: string) => (typeof pipeline[k] === "number" ? (pipeline[k] as number) : null);

  const gemini = str("gemini_model");
  const primary = str("gemini_primary");
  const sam = str("sam_model");
  const depth = str("depth_model");
  const cues = num("scale_cues");
  const rejected = num("scale_cues_rejected");
  const stages = [
    {
      name: "Scene & parts",
      model: gemini,
      seconds: num("gemini_s"),
      detail: `${num("components_detected") ?? 0} building parts with depth planes${cues != null ? `, ${cues} scale cues` : ""}${rejected ? ` (${rejected} implausible rejected)` : ""}`,
      note: gemini && primary && gemini !== primary ? `${primary} was busy, so the fallback model answered` : null,
    },
    {
      name: "Precise outlines",
      model: sam && sam !== "not used" ? sam : null,
      seconds: num("sam_s"),
      detail: sam && sam !== "not used" ? "pixel masks from the boxes, simplified to editable polygons" : "unavailable: rough boxes used instead",
      note: null,
    },
    {
      name: "Distances",
      model: depth && depth !== "not used" ? depth : null,
      seconds: num("depth_s"),
      detail: depth && depth !== "not used" ? "how far every surface is, for distance-aware measurement" : "unavailable: one scale per plane",
      note: null,
    },
  ];
  const total = stages.reduce((s, x) => s + (x.seconds ?? 0), 0);

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface" onClick={(e) => e.stopPropagation()}>
      <button className="flex w-full items-center gap-2 px-2.5 py-2 text-left text-xs" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Cpu className="size-3.5 text-accent" />
        <span className="flex-1 font-semibold">How the AI analysed this photo</span>
        {total > 0 && <span className="text-muted">{total.toFixed(1)} s</span>}
        <ChevronDown className={cx("size-3.5 text-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ol className="space-y-2 border-t border-line px-2.5 py-2 text-xs">
          {stages.map((s, i) => (
            <li key={s.name} className="flex gap-2">
              <span className={cx("mt-px flex size-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white", s.model ? "bg-accent" : "bg-warn")}>
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex justify-between gap-2">
                  <b>{s.name}</b>
                  {s.seconds != null && <span className="text-muted">{s.seconds.toFixed(1)} s</span>}
                </span>
                {s.model && <span className="block truncate font-mono text-[10.5px] text-faint">{s.model}</span>}
                <span className="block text-muted">{s.detail}</span>
                {s.note && <span className="block text-warn">{s.note}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
