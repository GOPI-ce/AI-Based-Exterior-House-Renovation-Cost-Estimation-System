"use client";

import { ArrowRight, ChevronDown, Download, Info, RotateCcw, TriangleAlert } from "lucide-react";
import { Fragment, useState } from "react";

import { Badge, Button, cx, Field, inputClass, Notice, NumberInput, Panel, Spinner } from "@/components/ui";
import { useWorkspace } from "@/components/workspace/context";
import { formatINR, formatINRShort, formatNumber } from "@/lib/format";
import { useDesignComparison, useEstimate } from "@/lib/hooks";
import { activeDesign } from "@/lib/project";
import { downloadBoq } from "@/lib/boq";
import type { Catalog, Estimate, EstimateLine, Material, ProjectData } from "@/lib/types";

export function EstimateStep() {
  const { store, catalog, goTo } = useWorkspace();
  const { data, update } = store;
  const design = activeDesign(data);
  const { estimate, loading, error } = useEstimate(data, design.id);
  const comparison = useDesignComparison(data);

  const setOverride = (line: EstimateLine, value: number | null) =>
    update((d) => {
      for (const v of d.views) {
        const r = v.regions.find((x) => x.id === line.region_id);
        if (!r) continue;
        if (line.measure_unit === "rft") r.length_override_ft = value;
        else r.area_override_sqft = value;
      }
    });

  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl space-y-4 p-3 sm:p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-extrabold tracking-tight">Quantities & cost</h2>
            {estimate && catalog && (
              <p className="text-xs font-semibold text-accent">
                Rates: {estimate.city} · updated {catalog.rates_updated}
              </p>
            )}
            <p className="text-sm text-muted">
              {catalog?.rates_note ?? "Indicative rates."} Edit any rate or measurement and everything recalculates.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.designs.map((d) => (
              <button
                key={d.id}
                onClick={() => update((x) => void (x.active_design_id = d.id), { record: false })}
                className={cx(
                  "rounded-lg border px-3 py-1.5 text-sm font-semibold",
                  d.id === design.id ? "border-accent bg-accent text-white" : "border-line bg-surface hover:border-accent/40",
                )}
              >
                {d.name}
              </button>
            ))}
          </div>
        </div>

        {error && <Notice tone="danger" icon={<TriangleAlert className="size-4" />} title="Could not calculate">{error}</Notice>}

        {estimate ? (
          <>
            <Kpis estimate={estimate} loading={loading} />
            {estimate.warnings.length > 0 && (
              <Notice tone="warn" icon={<TriangleAlert className="size-4" />} title="Check before relying on these numbers">
                <ul className="list-disc space-y-0.5 pl-4">
                  {estimate.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
                {estimate.warnings.some((w) => /scale/i.test(w)) && (
                  <button className="mt-1 font-semibold underline" onClick={() => goTo("scale")}>
                    Review the scale
                  </button>
                )}
              </Notice>
            )}

            <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
              <div className="min-w-0 space-y-4">
                <Panel
                  title="Cost breakdown by surface"
                  action={
                    <Button size="sm" icon={<Download className="size-3.5" />} onClick={() => downloadBoq(store.name, estimate)}>
                      BOQ (CSV)
                    </Button>
                  }
                >
                  <LinesTable estimate={estimate} onOverride={setOverride} />
                  {estimate.unassigned_regions.length > 0 && (
                    <p className="mt-3 text-xs text-muted">
                      <b>Unchanged in this design:</b> {estimate.unassigned_regions.join(", ")}
                    </p>
                  )}
                </Panel>
                {estimate.site_lines.length > 0 && (
                  <Panel title="Site & preparation">
                    <SiteTable estimate={estimate} />
                  </Panel>
                )}
                <Panel title="Measurement confidence">
                  <PlanesPanel estimate={estimate} onFix={() => goTo("scale")} />
                </Panel>
                <div className="grid gap-4 md:grid-cols-2">
                  <Panel title="By category">
                    <Categories estimate={estimate} />
                  </Panel>
                  <Panel title="Compare designs">
                    <Comparison estimates={comparison} activeId={design.id} />
                  </Panel>
                </div>
              </div>

              <div className="space-y-4">
                <Panel title="Totals">
                  <Totals estimate={estimate} />
                </Panel>
                <Panel title="Project settings">
                  <Settings data={data} catalog={catalog} onChange={(recipe) => update(recipe)} />
                </Panel>
                {catalog && (
                  <Panel title="Rates (₹, excl. GST)">
                    <RatesEditor
                      materials={catalog.materials}
                      usedIds={new Set(Object.values(design.assignments).map((a) => a.material_id))}
                      data={data}
                      onChange={(id, field, value) =>
                        update((d) => {
                          const o = (d.rate_overrides[id] ??= { material_rate: null, labour_rate: null });
                          o[field] = value;
                          if (o.material_rate === null && o.labour_rate === null) delete d.rate_overrides[id];
                        })
                      }
                    />
                  </Panel>
                )}
                <Button variant="primary" className="w-full" onClick={() => goTo("report")}>
                  Create the report <ArrowRight className="size-4" />
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex items-center gap-2 p-10 text-sm text-muted">
            <Spinner /> Calculating…
          </div>
        )}
      </div>
    </div>
  );
}

function Kpis({ estimate, loading }: { estimate: Estimate; loading: boolean }) {
  const items = [
    { label: "Materials", value: formatINR(estimate.material_total) },
    { label: "Labour + site works", value: formatINR(estimate.labour_total + estimate.site_total) },
    { label: "Surface to finish", value: `${formatNumber(estimate.total_area_sqft)} sqft` },
    { label: "Railing", value: `${formatNumber(estimate.total_railing_rft)} rft` },
  ];
  return (
    <div className={cx("grid grid-cols-2 gap-2 transition-opacity sm:grid-cols-3 lg:grid-cols-5", loading && "opacity-60")}>
      <div className="col-span-2 rounded-2xl border border-accent bg-accent p-4 text-white sm:col-span-1">
        <p className="text-xs font-semibold text-white/80">Most likely total (incl. GST)</p>
        <p className="mt-1 text-2xl font-extrabold tracking-tight">{formatINRShort(estimate.grand_total)}</p>
        <p className="mt-0.5 text-[11px] text-white/80">
          Likely range {formatINRShort(estimate.low_total)} – {formatINRShort(estimate.high_total)}
        </p>
      </div>
      {items.map((k) => (
        <div key={k.label} className="rounded-2xl border border-line bg-surface p-4">
          <p className="text-xs font-semibold text-muted">{k.label}</p>
          <p className="mt-1 text-xl font-extrabold tracking-tight">{k.value}</p>
        </div>
      ))}
    </div>
  );
}

function SiteTable({ estimate }: { estimate: Estimate }) {
  return (
    <div className="space-y-2">
      {estimate.site_lines.map((x) => (
        <div key={x.id} className="flex items-start justify-between gap-3 border-b border-line/70 pb-2 text-sm last:border-0">
          <div>
            <p className="font-medium">{x.name}</p>
            <p className="text-xs text-muted">
              {x.unit === "%" ? `${x.quantity}% of works` : `${formatNumber(x.quantity)} ${x.unit} @ ${formatINR(x.rate)}/${x.unit}`} · {x.note}
            </p>
          </div>
          <p className="shrink-0 font-semibold">{formatINR(x.amount)}</p>
        </div>
      ))}
      <p className="text-xs text-muted">Switch these on or off in Project settings.</p>
    </div>
  );
}

function PlanesPanel({ estimate, onFix }: { estimate: Estimate; onFix: () => void }) {
  return (
    <div className="space-y-2">
      {estimate.planes.map((p, i) => (
        <div key={`${i}-${p.plane_id}`} className="flex items-start justify-between gap-3 text-sm">
          <div className="min-w-0">
            <p className="font-medium">
              {p.view_name} · {p.plane_name}
            </p>
            <p className="text-xs text-muted">
              {p.ft_per_px_y === null ? "No scale" : p.borrowed_from ? `Borrowed from ${p.borrowed_from}` : `From ${p.cues_used.join(", ")}`}
              {p.ft_per_px_y !== null && ` · lengths ±${p.measurement_error_pct}%`}
            </p>
          </div>
          <Badge tone={p.confidence >= 0.8 ? "accent" : p.confidence >= 0.5 ? "info" : "warn"}>{Math.round(p.confidence * 100)}%</Badge>
        </div>
      ))}
      <button className="text-xs font-semibold text-accent hover:underline" onClick={onFix}>
        Improve the scale (add or confirm reference lengths)
      </button>
    </div>
  );
}

function LinesTable({ estimate, onOverride }: { estimate: Estimate; onOverride: (l: EstimateLine, v: number | null) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!estimate.lines.length) return <p className="text-sm text-muted">No materials applied yet. Choose materials in the Design step.</p>;

  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="w-full min-w-[760px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="px-4 py-2 font-semibold">Surface</th>
            <th className="px-2 py-2 font-semibold">Material</th>
            <th className="px-2 py-2 text-right font-semibold">Net size</th>
            <th className="px-2 py-2 text-right font-semibold">Material</th>
            <th className="px-2 py-2 text-right font-semibold">Labour</th>
            <th className="px-4 py-2 text-right font-semibold">Total</th>
          </tr>
        </thead>
        <tbody>
          {estimate.lines.map((l) => {
            const key = l.region_id;
            const isOpen = open === key;
            return (
              <Fragment key={key}>
                <tr className="cursor-pointer border-b border-line/70 hover:bg-tint/60" onClick={() => setOpen(isOpen ? null : key)}>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1.5 font-medium">
                      <ChevronDown className={cx("size-3.5 shrink-0 text-faint transition-transform", isOpen && "rotate-180")} />
                      {l.region_label}
                    </div>
                    <div className="pl-5 text-xs text-muted">{l.view_name}</div>
                  </td>
                  <td className="px-2 py-2.5 text-ink-soft">
                    {l.material_name}
                    {l.color_name && <span className="block text-xs text-muted">{l.color_name}</span>}
                  </td>
                  <td className="px-2 py-2.5 text-right whitespace-nowrap">
                    {formatNumber(l.net)} {l.measure_unit}
                    {l.measured_from === "override" && <Badge tone="info" className="ml-1">site</Badge>}
                    {l.measured_from === "unscaled" && <Badge tone="warn" className="ml-1">no scale</Badge>}
                  </td>
                  <td className="px-2 py-2.5 text-right">{formatINR(l.material_cost)}</td>
                  <td className="px-2 py-2.5 text-right">{formatINR(l.labour_cost)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="font-bold">{formatINR(l.total)}</span>
                    <span className="block text-[11px] text-muted">
                      {formatINRShort(l.low)}–{formatINRShort(l.high)}
                    </span>
                  </td>
                </tr>
                {isOpen && (
                  <tr className="border-b border-line bg-canvas/60">
                    <td colSpan={6} className="px-4 py-3">
                      <LineDetail line={l} onOverride={(v) => onOverride(l, v)} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function LineDetail({ line, onOverride }: { line: EstimateLine; onOverride: (v: number | null) => void }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="space-y-1 text-xs">
        <p className="font-semibold text-ink-soft">Measurement</p>
        <p>Gross from photo: {formatNumber(line.gross)} {line.measure_unit}</p>
        {line.deductions > 0 && <p>Openings / overlaps deducted: −{formatNumber(line.deductions)} {line.measure_unit}</p>}
        <p className="font-semibold">Net: {formatNumber(line.net)} {line.measure_unit}</p>
        <div className="pt-1">
          <NumberInput
            ariaLabel="Site measurement"
            value={line.measured_from === "override" ? line.net : null}
            onChange={onOverride}
            min={0}
            placeholder="Enter a site measurement"
            suffix={line.measure_unit}
          />
        </div>
      </div>
      <div className="space-y-1 text-xs">
        <p className="font-semibold text-ink-soft">Quantities to buy</p>
        {line.quantities.map((q) => (
          <p key={q.name}>
            <b>{q.name}:</b> {formatNumber(q.quantity)} {q.unit}
            {q.note && <span className="text-muted"> · {q.note}</span>}
          </p>
        ))}
      </div>
      <div className="space-y-1 text-xs">
        <p className="font-semibold text-ink-soft">Rates</p>
        <p>Material: {formatINR(line.material_rate)}/{line.material_rate_unit}</p>
        <p>Labour: {formatINR(line.labour_rate)}/{line.labour_rate_unit}</p>
        {line.notes.map((n) => (
          <p key={n} className="flex gap-1 text-muted">
            <Info className="mt-px size-3 shrink-0" /> {n}
          </p>
        ))}
      </div>
    </div>
  );
}

function Totals({ estimate: e }: { estimate: Estimate }) {
  const rows: [string, number, boolean?][] = [
    ["Materials", e.material_total],
    ["Labour", e.labour_total],
    ["Site & preparation", e.site_total],
    ["Subtotal", e.subtotal, true],
    [`Contingency (${e.contingency_pct}%)`, e.contingency],
    [`GST (${e.gst_pct}%)`, e.gst],
  ];
  return (
    <dl className="space-y-1.5 text-sm">
      {rows.map(([label, value, strong]) => (
        <div key={label} className={cx("flex justify-between", strong && "border-t border-line pt-1.5 font-semibold")}>
          <dt className="text-ink-soft">{label}</dt>
          <dd>{formatINR(value)}</dd>
        </div>
      ))}
      <div className="flex justify-between border-t border-line pt-2 text-base font-extrabold text-accent">
        <dt>Most likely total</dt>
        <dd>{formatINR(e.grand_total)}</dd>
      </div>
      <div className="flex justify-between text-xs text-muted">
        <dt>Likely range</dt>
        <dd>
          {formatINR(e.low_total)} – {formatINR(e.high_total)}
        </dd>
      </div>
      <p className="pt-1 text-[11px] leading-snug text-faint">
        Concept-stage estimate (comparable to an AACE Class 4–5 estimate): the range combines market rate spreads with how precisely
        each plane is measured.
      </p>
    </dl>
  );
}

function Categories({ estimate }: { estimate: Estimate }) {
  const max = Math.max(1, ...estimate.categories.map((c) => c.total));
  return (
    <div className="space-y-2.5">
      {estimate.categories.map((c) => (
        <div key={c.category}>
          <div className="mb-1 flex justify-between text-sm">
            <span className="font-medium">{c.category}</span>
            <span className="font-semibold">{formatINR(c.total)}</span>
          </div>
          <div className="flex h-2 overflow-hidden rounded-full bg-canvas">
            <div className="bg-accent" style={{ width: `${(c.material_cost / max) * 100}%` }} title="Material" />
            <div className="bg-accent/40" style={{ width: `${(c.labour_cost / max) * 100}%` }} title="Labour" />
          </div>
        </div>
      ))}
      <p className="flex gap-3 pt-1 text-[11px] text-muted">
        <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-accent" /> Material</span>
        <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-accent/40" /> Labour</span>
      </p>
    </div>
  );
}

function Comparison({ estimates, activeId }: { estimates: Estimate[] | null; activeId: string }) {
  if (!estimates) return <Spinner />;
  const min = Math.min(...estimates.map((e) => e.grand_total).filter((t) => t > 0));
  return (
    <div className="space-y-2">
      {estimates.map((e) => (
        <div key={e.design_id} className={cx("flex items-center justify-between rounded-lg border px-3 py-2 text-sm", e.design_id === activeId ? "border-accent/50 bg-tint" : "border-line")}>
          <div>
            <p className="font-semibold">{e.design_name}</p>
            <p className="text-xs text-muted">
              {e.lines.length} surfaces · {formatNumber(e.total_area_sqft)} sqft
            </p>
          </div>
          <div className="text-right">
            <p className="font-bold">{formatINRShort(e.grand_total)}</p>
            {e.grand_total === min && estimates.length > 1 && <Badge tone="accent">lowest</Badge>}
          </div>
        </div>
      ))}
    </div>
  );
}

function Settings({ data, catalog, onChange }: { data: ProjectData; catalog: Catalog | null; onChange: (recipe: (d: ProjectData) => void) => void }) {
  const s = data.settings;
  const enabled = new Set(s.site_items ?? catalog?.site_items.filter((i) => i.default).map((i) => i.id) ?? []);
  return (
    <div className="space-y-3">
      {catalog && (
        <Field label="City (adjusts labour and material rates)">
          <select className={inputClass} value={s.city_id} onChange={(e) => onChange((d) => void (d.settings.city_id = e.target.value))}>
            {catalog.cities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · labour ×{c.labour_index}
              </option>
            ))}
          </select>
        </Field>
      )}
      <div className="grid grid-cols-3 gap-2">
        <Field label="Paint coats">
          <NumberInput value={s.paint_coats} min={1} max={4} step={1} onChange={(v) => v && onChange((d) => void (d.settings.paint_coats = Math.round(v)))} />
        </Field>
        <Field label="Contingency">
          <NumberInput value={s.contingency_pct} min={0} max={50} suffix="%" onChange={(v) => onChange((d) => void (d.settings.contingency_pct = v ?? 0))} />
        </Field>
        <Field label="GST">
          <NumberInput value={s.gst_pct} min={0} max={28} suffix="%" onChange={(v) => onChange((d) => void (d.settings.gst_pct = v ?? 0))} />
        </Field>
      </div>
      {catalog && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-ink-soft">Site & preparation items</p>
          {catalog.site_items.map((item) => (
            <label key={item.id} className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5 size-4 accent-[var(--color-accent)]"
                checked={enabled.has(item.id)}
                onChange={(e) =>
                  onChange((d) => {
                    const next = new Set(enabled);
                    if (e.target.checked) next.add(item.id);
                    else next.delete(item.id);
                    d.settings.site_items = [...next];
                  })
                }
              />
              <span>
                {item.name}
                <span className="block text-[11px] text-muted">
                  {item.basis === "percent" ? `${item.rate}% of works` : `${formatINR(item.rate)}/${item.unit}`} · {item.note}
                </span>
              </span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function RatesEditor({
  materials,
  usedIds,
  data,
  onChange,
}: {
  materials: Material[];
  usedIds: Set<string>;
  data: ProjectData;
  onChange: (id: string, field: "material_rate" | "labour_rate", value: number | null) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const list = showAll ? materials : materials.filter((m) => usedIds.has(m.id));
  return (
    <div className="space-y-3">
      {list.map((m) => {
        const o = data.rate_overrides[m.id];
        return (
          <div key={m.id} className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-xs font-semibold">{m.name}</p>
              {o && (
                <button className="flex items-center gap-1 text-[11px] font-semibold text-accent" onClick={() => {
                  onChange(m.id, "material_rate", null);
                  onChange(m.id, "labour_rate", null);
                }}>
                  <RotateCcw className="size-3" /> Reset
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <NumberInput ariaLabel={`${m.name} material rate`} value={o?.material_rate ?? null} placeholder={String(m.rate)} min={0} suffix={`/${m.rate_unit}`} onChange={(v) => onChange(m.id, "material_rate", v)} />
              <NumberInput ariaLabel={`${m.name} labour rate`} value={o?.labour_rate ?? null} placeholder={String(m.labour_rate)} min={0} suffix={`/${m.labour_unit}`} onChange={(v) => onChange(m.id, "labour_rate", v)} />
            </div>
          </div>
        );
      })}
      {!list.length && <p className="text-xs text-muted">Rates appear here for the materials used in this design.</p>}
      <button className="text-xs font-semibold text-accent hover:underline" onClick={() => setShowAll((s) => !s)}>
        {showAll ? "Show only materials in this design" : `Show all ${materials.length} materials`}
      </button>
      <p className="text-[11px] text-muted">Left: material rate · right: labour rate. Empty = catalogue default.</p>
    </div>
  );
}
