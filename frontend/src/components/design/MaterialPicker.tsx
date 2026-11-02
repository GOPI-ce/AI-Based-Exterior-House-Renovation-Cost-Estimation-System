"use client";

import { BadgeCheck, Check, Clock, Copy, Eraser, Search, ThumbsDown, ThumbsUp, Wrench } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Badge, Button, cx, inputClass } from "@/components/ui";
import { formatINR } from "@/lib/format";
import { COMPONENT_META } from "@/lib/geometry";
import { materialSwatch } from "@/lib/project";
import type { Assignment, Catalog, Material, Region, Shade, Tier } from "@/lib/types";

const TIERS: { value: Tier | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "economy", label: "Economy" },
  { value: "standard", label: "Standard" },
  { value: "premium", label: "Premium" },
  { value: "luxury", label: "Luxury" },
];
const TIER_TONE: Record<Tier, "neutral" | "info" | "accent" | "warn"> = { economy: "neutral", standard: "info", premium: "accent", luxury: "warn" };

/** Choose a material for one surface: browse the catalogue, compare, and pick a shade. */
export function MaterialPicker({
  region,
  catalog,
  assignment,
  sameTypeCount,
  onAssign,
  onApplyToSameType,
  onClear,
}: {
  region: Region;
  catalog: Catalog;
  assignment: Assignment | undefined;
  sameTypeCount: number;
  onAssign: (a: Assignment) => void;
  onApplyToSameType: () => void;
  onClear: () => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const [category, setCategory] = useState<string>("all");
  const [tier, setTier] = useState<Tier | "all">("all");
  const [query, setQuery] = useState("");
  const current = catalog.materials.find((m) => m.id === assignment?.material_id);
  const typeLabel = COMPONENT_META[region.type].label.toLowerCase();

  const pool = useMemo(
    () => (showAll ? catalog.materials : catalog.materials.filter((m) => m.suitable_for.includes(region.type))),
    [catalog.materials, region.type, showAll],
  );
  const categories = [...new Set(pool.map((m) => m.category))];
  const q = query.trim().toLowerCase();
  const list = pool.filter(
    (m) =>
      (category === "all" || m.category === category) &&
      (tier === "all" || m.tier === tier) &&
      (!q || `${m.name} ${m.brand ?? ""} ${m.category}`.toLowerCase().includes(q)),
  );

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-faint" />
        <input className={cx(inputClass, "pl-8")} placeholder="Search materials, brands…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="scroll-thin -mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        {["all", ...categories].map((c) => (
          <button key={c} onClick={() => setCategory(c)}
            className={cx("shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold", category === c ? "border-accent bg-accent text-white" : "border-line text-ink-soft hover:border-accent/40")}>
            {c === "all" ? "All" : c}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1">
        {TIERS.map((t) => (
          <button key={t.value} onClick={() => setTier(t.value)}
            className={cx("rounded-md px-2 py-0.5 text-[11px] font-semibold", tier === t.value ? "bg-ink text-white" : "bg-canvas text-muted hover:text-ink")}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2">
        {list.map((m) => (
          <MaterialCard
            key={m.id}
            material={m}
            selected={m.id === current?.id}
            unsuitable={!m.suitable_for.includes(region.type)}
            onClick={() => onAssign({ material_id: m.id, color: m.id === current?.id ? assignment!.color : m.default_color })}
          />
        ))}
      </div>
      {!list.length && <p className="text-sm text-muted">No materials match these filters.</p>}
      <button className="text-xs font-semibold text-accent hover:underline" onClick={() => setShowAll((s) => !s)}>
        {showAll ? `Show only materials suited to a ${typeLabel}` : `Show all ${catalog.materials.length} materials`}
      </button>

      {current && (
        <div className="animate-rise space-y-3 rounded-xl border border-line p-3">
          <div>
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-bold">{current.name}</p>
              <Badge tone={TIER_TONE[current.tier]}>{current.tier}</Badge>
            </div>
            <p className="mt-0.5 text-xs text-muted">
              {formatINR(current.rate_range[0])}–{formatINR(current.rate_range[1])}/{current.rate_unit} material ·{" "}
              {formatINR(current.labour_range[0])}–{formatINR(current.labour_range[1])}/{current.labour_unit} labour
            </p>
          </div>

          {current.palette && catalog.palettes[current.palette] && (
            <ShadePicker
              key={current.palette}
              shades={catalog.palettes[current.palette]}
              value={assignment?.color ?? current.default_color}
              onChange={(hex) => onAssign({ material_id: current.id, color: hex })}
            />
          )}

          <dl className="space-y-1.5 text-xs">
            {current.warranty_years && <Row icon={<BadgeCheck className="size-3.5" />} label="Warranty">Up to {current.warranty_years} years (manufacturer claim; conditions apply)</Row>}
            <Row icon={<Clock className="size-3.5" />} label="Life">{current.durability}</Row>
            <Row icon={<Wrench className="size-3.5" />} label="Upkeep">{current.maintenance}</Row>
            <Row icon={<ThumbsUp className="size-3.5" />} label="Pros">{current.pros.join("; ")}</Row>
            <Row icon={<ThumbsDown className="size-3.5" />} label="Cons">{current.cons.join("; ")}</Row>
          </dl>
          {current.specs.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-muted">
              {current.specs.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap gap-2">
            {sameTypeCount > 1 && (
              <Button size="sm" icon={<Copy className="size-3.5" />} onClick={onApplyToSameType}>
                Apply to all {sameTypeCount} {typeLabel}s
              </Button>
            )}
            <Button size="sm" variant="ghost" icon={<Eraser className="size-3.5" />} onClick={onClear}>
              Keep as it is
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function ShadePicker({ shades, value, onChange }: { shades: Shade[]; value: string | null; onChange: (hex: string) => void }) {
  const families = [...new Set(shades.map((s) => s.family))];
  const selected = shades.find((s) => s.hex.toLowerCase() === value?.toLowerCase());
  const [family, setFamily] = useState(selected?.family ?? families[0]);
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const visible = q ? shades.filter((s) => s.name.toLowerCase().includes(q)) : shades.filter((s) => s.family === family);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-ink-soft">
          Shade: <span className="text-ink">{selected?.name ?? value?.toUpperCase() ?? "-"}</span>
        </p>
        <label className="relative flex cursor-pointer items-center gap-1 text-[11px] font-semibold text-accent">
          Custom
          <input type="color" className="absolute inset-0 cursor-pointer opacity-0" value={value ?? "#cccccc"} onChange={(e) => onChange(e.target.value)} />
        </label>
      </div>
      {shades.length > 12 && (
        <input className={cx(inputClass, "h-8 text-xs")} placeholder={`Search ${shades.length} shades…`} value={query} onChange={(e) => setQuery(e.target.value)} />
      )}
      {!q && families.length > 1 && (
        <div className="scroll-thin -mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
          {families.map((f) => (
            <button key={f} onClick={() => setFamily(f)}
              className={cx("shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold", family === f ? "bg-ink text-white" : "bg-canvas text-muted hover:text-ink")}>
              {f}
            </button>
          ))}
        </div>
      )}
      <div className="grid grid-cols-6 gap-1.5">
        {visible.map((s) => {
          const active = s.hex.toLowerCase() === value?.toLowerCase();
          return (
            <button key={s.hex + s.name} title={s.name} aria-label={s.name} onClick={() => onChange(s.hex)}
              className={cx("grid aspect-square place-items-center rounded-lg border-2 shadow-sm", active ? "border-accent" : "border-white")}
              style={{ background: s.hex }}>
              {active && <Check className="size-4 text-white mix-blend-difference" />}
            </button>
          );
        })}
      </div>
      <p className="text-[10px] text-faint">On-screen colours are approximate; confirm with the physical shade card.</p>
    </div>
  );
}

function MaterialCard({ material, selected, unsuitable, onClick }: { material: Material; selected: boolean; unsuitable: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={cx("group overflow-hidden rounded-xl border text-left transition", selected ? "border-accent ring-2 ring-accent/25" : "border-line hover:border-accent/40", unsuitable && "opacity-60")}>
      <div className="relative h-14" style={materialSwatch(material)}>
        <span className="absolute bottom-1 left-1 rounded bg-white/85 px-1 text-[9px] font-bold tracking-wide text-ink uppercase">{material.tier}</span>
        {selected && (
          <span className="absolute top-1.5 right-1.5 grid size-5 place-items-center rounded-full bg-accent text-white">
            <Check className="size-3" strokeWidth={3} />
          </span>
        )}
      </div>
      <div className="p-2">
        {material.brand && <p className="text-[10px] font-semibold text-muted">{material.brand}</p>}
        <p className="line-clamp-2 text-xs leading-snug font-semibold">{material.product ?? material.name}</p>
        <p className="mt-0.5 text-[11px] text-muted">
          {formatINR(material.rate)}/{material.rate_unit} + {formatINR(material.labour_rate)}/{material.labour_unit}
        </p>
        {material.warranty_years && <p className="text-[10px] font-semibold text-accent">Warranty up to {material.warranty_years} yrs</p>}
        {unsuitable && <p className="mt-0.5 text-[10px] font-semibold text-warn">Not typical here</p>}
      </div>
    </button>
  );
}

function Row({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="flex w-20 shrink-0 items-center gap-1 font-semibold text-ink-soft">
        {icon}
        {label}
      </dt>
      <dd className="text-muted">{children}</dd>
    </div>
  );
}
