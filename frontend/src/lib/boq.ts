import type { Estimate } from "./types";

/** CSV cell: quote when needed, and neutralise leading = + - @ so spreadsheets don't run formulas. */
function cell(value: string | number): string {
  if (typeof value === "number") return String(value);
  const text = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Bill of quantities as CSV (opens in Excel / Google Sheets), for contractors to price against. */
export function boqCsv(projectName: string, e: Estimate): string {
  const rows: (string | number)[][] = [
    [`Bill of quantities: ${projectName}`],
    [`Design: ${e.design_name}`, `Rates: ${e.city}`, "Amounts in INR, excluding GST unless stated"],
    [],
    ["#", "Photo", "Surface", "Material", "Colour", "Net qty", "Unit", "Purchase quantities", "Material rate", "Material cost", "Labour rate", "Labour cost", "Total", "Low", "High"],
  ];
  e.lines.forEach((l, i) =>
    rows.push([
      i + 1, l.view_name, l.region_label, l.material_name, l.color_name, l.net, l.measure_unit,
      l.quantities.map((q) => `${q.name}: ${q.quantity} ${q.unit}${q.note ? ` (${q.note})` : ""}`).join("; "),
      `${l.material_rate}/${l.material_rate_unit}`, Math.round(l.material_cost), `${l.labour_rate}/${l.labour_rate_unit}`,
      Math.round(l.labour_cost), Math.round(l.total), Math.round(l.low), Math.round(l.high),
    ]),
  );
  rows.push([]);
  rows.push(["", "", "Site & preparation"]);
  e.site_lines.forEach((x) => rows.push(["", "", x.name, "", "", x.quantity, x.unit, x.note, "", "", x.unit === "%" ? "" : `${x.rate}/${x.unit}`, Math.round(x.amount), Math.round(x.amount)]));
  rows.push([]);
  const totals: [string, number][] = [
    ["Materials", e.material_total],
    ["Labour", e.labour_total],
    ["Site & preparation", e.site_total],
    ["Subtotal", e.subtotal],
    [`Contingency ${e.contingency_pct}%`, e.contingency],
    [`GST ${e.gst_pct}%`, e.gst],
    ["Most likely total (incl. GST)", e.grand_total],
    ["Likely range low", e.low_total],
    ["Likely range high", e.high_total],
  ];
  totals.forEach(([label, value]) => rows.push(["", "", label, "", "", "", "", "", "", "", "", "", Math.round(value)]));
  return rows.map((r) => r.map(cell).join(",")).join("\r\n");
}

export function downloadBoq(projectName: string, e: Estimate) {
  const blob = new Blob(["﻿" + boqCsv(projectName, e)], { type: "text/csv;charset=utf-8" }); // BOM: Excel reads ₹ correctly
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${projectName.replace(/[^A-Za-z0-9_-]+/g, "-") || "project"}-${e.design_name.replace(/[^A-Za-z0-9_-]+/g, "-")}-BOQ.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
