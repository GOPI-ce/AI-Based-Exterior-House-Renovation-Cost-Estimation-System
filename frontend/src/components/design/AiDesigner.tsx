"use client";

import { Check, ChevronDown, Sparkles, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { Badge, Button, cx, inputClass, Notice, NumberInput } from "@/components/ui";
import { useWorkspace } from "@/components/workspace/context";
import { api, ApiError } from "@/lib/api";
import { formatINRShort, uid } from "@/lib/format";
import type { DesignSuggestion } from "@/lib/types";

const STYLES = ["Modern & minimal", "Warm with natural stone", "Traditional Indian", "Low maintenance", "Premium statement"];

/**
 * Budget designer: Gemini proposes a full design for this house from the catalogue, the estimator
 * checks the all-in total and, if needed, the design is revised until it fits the budget.
 */
export function AiDesigner() {
  const { store } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [budget, setBudget] = useState<number | null>(400000);
  const [style, setStyle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DesignSuggestion | null>(null);
  const readOnly = store.status === "readonly";
  const hasSurfaces = store.data.views.some((v) => v.regions.length > 0);

  async function run() {
    if (!budget) return;
    setBusy(true);
    setError(null);
    try {
      const suggestion = await api.suggestDesign(store.data, budget, style);
      const id = uid("design");
      store.update((d) => {
        d.designs.push({ ...suggestion.design, id, name: uniqueName(suggestion.design.name, d.designs.map((x) => x.name)) });
        d.active_design_id = id;
      });
      setResult(suggestion);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The AI designer failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-accent/30 bg-tint">
      <button className="flex w-full items-center gap-2 px-3 py-2.5 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Sparkles className="size-4 text-accent" />
        <span className="flex-1">
          <span className="block text-sm font-bold">Design it for my budget</span>
          <span className="block text-xs text-muted">AI picks every finish for this house; the estimator keeps it within budget.</span>
        </span>
        <ChevronDown className={cx("size-4 text-muted transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="space-y-3 border-t border-accent/20 px-3 pb-3 pt-3">
          {readOnly ? (
            <p className="text-xs text-muted">Make your own copy of this project (top bar) to use the AI designer.</p>
          ) : !hasSurfaces ? (
            <p className="text-xs text-muted">Detect or draw the surfaces first.</p>
          ) : (
            <>
              <label className="block space-y-1">
                <span className="text-xs font-semibold">All-inclusive budget (with GST)</span>
                <NumberInput value={budget} onChange={setBudget} min={10000} step={10000} suffix="₹" ariaLabel="Budget" />
              </label>
              <label className="block space-y-1">
                <span className="text-xs font-semibold">Style (optional)</span>
                <input
                  className={inputClass}
                  value={style}
                  maxLength={300}
                  placeholder="e.g. warm, natural stone, easy to maintain"
                  onChange={(e) => setStyle(e.target.value)}
                />
              </label>
              <div className="flex flex-wrap gap-1.5">
                {STYLES.map((s) => (
                  <button
                    key={s}
                    onClick={() => setStyle(s)}
                    className={cx("rounded-full border px-2 py-0.5 text-[11px] font-semibold", style === s ? "border-accent bg-accent text-white" : "border-line bg-surface text-ink-soft hover:border-accent/40")}
                  >
                    {s}
                  </button>
                ))}
              </div>
              <Button variant="primary" className="w-full" loading={busy} disabled={!budget} onClick={run} icon={<Sparkles className="size-4" />}>
                {busy ? "Designing… (about 20 s)" : "Create AI design"}
              </Button>
            </>
          )}

          {error && <Notice tone="danger">{error}</Notice>}

          {result && !busy && (
            <div className="space-y-2 rounded-lg border border-line bg-surface p-2.5 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-bold">{formatINRShort(result.total)}</span>
                <span className="text-muted">of {formatINRShort(result.budget)}</span>
                {result.within_budget ? (
                  <Badge tone="accent"><Check className="size-3" /> within budget</Badge>
                ) : (
                  <Badge tone="warn"><TriangleAlert className="size-3" /> over budget</Badge>
                )}
              </div>
              {result.concept && <p className="leading-relaxed text-ink-soft">{result.concept}</p>}
              <ol className="space-y-0.5 text-muted">
                {result.steps.map((s, i) => (
                  <li key={i} className="flex justify-between gap-2">
                    <span>{i + 1}. {s.label}</span>
                    <span className={s.within_budget ? "text-accent" : "text-warn"}>{formatINRShort(s.total)}</span>
                  </li>
                ))}
              </ol>
              {result.warnings.map((w) => (
                <p key={w} className="text-warn">{w}</p>
              ))}
              <p className="text-faint">Added as a new design tab · {result.model}. Click any surface to see why it was chosen or to change it.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function uniqueName(name: string, taken: string[]): string {
  let candidate = name || "AI design";
  for (let i = 2; taken.includes(candidate); i++) candidate = `${name} ${i}`;
  return candidate.slice(0, 60);
}
