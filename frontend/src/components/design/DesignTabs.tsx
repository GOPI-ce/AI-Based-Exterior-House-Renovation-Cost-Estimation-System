"use client";

import { Copy, Pencil, Plus, Trash2 } from "lucide-react";

import { cx, IconButton } from "@/components/ui";
import { useWorkspace } from "@/components/workspace/context";
import { uid } from "@/lib/format";
import { activeDesign } from "@/lib/project";

/** Switch, add, duplicate, rename and delete design options. */
export function DesignTabs() {
  const { store } = useWorkspace();
  const { data, update } = store;
  const active = activeDesign(data);

  const add = (copyFrom?: typeof active) => {
    const id = uid("design");
    update((d) => {
      const letter = String.fromCharCode(65 + d.designs.length);
      d.designs.push({
        id,
        name: copyFrom ? `${copyFrom.name} (copy)` : `Design ${letter}`,
        assignments: copyFrom ? structuredClone(copyFrom.assignments) : {},
      });
      d.active_design_id = id;
    });
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {data.designs.map((d) => (
          <button
            key={d.id}
            onClick={() => update((x) => void (x.active_design_id = d.id), { record: false })}
            className={cx(
              "rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition-colors",
              d.id === active.id ? "border-accent bg-accent text-white" : "border-line bg-surface text-ink-soft hover:border-accent/40",
            )}
          >
            {d.name}
          </button>
        ))}
        <button
          onClick={() => add()}
          className="flex items-center gap-1 rounded-lg border border-dashed border-line-strong px-2.5 py-1.5 text-xs font-semibold text-muted hover:text-accent"
        >
          <Plus className="size-3.5" /> New
        </button>
      </div>
      <div className="flex items-center gap-1">
        <span className="mr-auto text-xs text-muted">Compare options side by side on the Estimate step.</span>
        <IconButton
          label="Rename design"
          onClick={() => {
            const name = prompt("Design name", active.name)?.trim();
            if (name) update((d) => void (d.designs.find((x) => x.id === active.id)!.name = name.slice(0, 60)));
          }}
        >
          <Pencil className="size-3.5" />
        </IconButton>
        <IconButton label="Duplicate design" onClick={() => add(active)}>
          <Copy className="size-3.5" />
        </IconButton>
        <IconButton
          label="Delete design"
          disabled={data.designs.length < 2}
          onClick={() => {
            if (!confirm(`Delete "${active.name}"?`)) return;
            update((d) => {
              d.designs = d.designs.filter((x) => x.id !== active.id);
              d.active_design_id = d.designs[0].id;
            });
          }}
        >
          <Trash2 className="size-3.5" />
        </IconButton>
      </div>
    </div>
  );
}
