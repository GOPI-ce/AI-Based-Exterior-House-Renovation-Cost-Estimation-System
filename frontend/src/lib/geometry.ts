import type { ComponentType, Plane, Point, Region, ScaleReference, View } from "./types";

/** Must match LAYER_PRIORITY in backend/app/services/geometry.py: higher layers cover lower ones. */
export const LAYER_PRIORITY: Record<ComponentType, number> = {
  wall: 10,
  roof_edge: 40,
  parapet: 50,
  balcony: 60,
  pillar: 70,
  railing: 80,
  gate: 90,
  window: 100,
  door: 100,
};

export const COMPONENT_META: Record<ComponentType, { label: string; color: string; opening?: boolean }> = {
  wall: { label: "Wall", color: "#e4573d" },
  roof_edge: { label: "Roof edge / sunshade", color: "#46b37b" },
  parapet: { label: "Parapet", color: "#2f9e44" },
  balcony: { label: "Balcony", color: "#8b5cf6" },
  pillar: { label: "Pillar / column", color: "#e0a400" },
  railing: { label: "Railing", color: "#0ea5b7" },
  gate: { label: "Gate", color: "#d6336c" },
  window: { label: "Window", color: "#3b82f6", opening: true },
  door: { label: "Door", color: "#f08c00", opening: true },
};

export const COMPONENT_TYPES = Object.keys(COMPONENT_META) as ComponentType[];

/** Regions sorted bottom layer first (ties keep list order), exactly like the backend. */
export function layerOrder(regions: Region[]): Region[] {
  return regions
    .map((r, i) => ({ r, i }))
    .sort((a, b) => LAYER_PRIORITY[a.r.type] - LAYER_PRIORITY[b.r.type] || a.i - b.i)
    .map(({ r }) => r);
}

export function distance(a: Point, b: Point, width = 1, height = 1): number {
  return Math.hypot((a[0] - b[0]) * width, (a[1] - b[1]) * height);
}

// --- Scale: same algorithm as backend/app/services/scale.py ----------------------------------
const OUTLIER_TOLERANCE = 0.35;
const MIN_LINE_PX = 8;

export interface PlaneScale {
  ftPerPxX: number;
  ftPerPxY: number;
  confidence: number;
  spread: number;
  cuesUsed: string[];
  cuesRejected: string[];
  borrowedFrom: string | null;
}

export function planeForRegion(region: Region, view: View): Plane | null {
  if (!view.planes.length) return null;
  return view.planes.find((p) => p.id === region.plane_id) ?? view.planes[0];
}

function weightedMedian(values: [number, number][]): number {
  const ordered = [...values].sort((a, b) => a[0] - b[0]);
  const half = ordered.reduce((s, [, w]) => s + w, 0) / 2;
  let acc = 0;
  for (const [v, w] of ordered) {
    acc += w;
    if (acc >= half) return v;
  }
  return ordered[ordered.length - 1][0];
}

type Sample = [value: number, weight: number, ref: ScaleReference];

function consensus(samples: Sample[]) {
  const usable = samples.filter((s) => s[1] > 0);
  if (!usable.length) return null;
  const median = weightedMedian(usable.map(([v, w]) => [v, w]));
  const kept = usable.length >= 3 ? usable.filter(([v]) => Math.abs(v / median - 1) <= OUTLIER_TOLERANCE) : usable;
  const value = weightedMedian(kept.map(([v, w]) => [v, w]));
  const total = kept.reduce((s, [, w]) => s + w, 0);
  const spread = total ? kept.reduce((s, [v, w]) => s + w * Math.abs(v / value - 1), 0) / total : 0;
  return { value, spread, used: kept.map((k) => k[2]), rejected: usable.filter((u) => !kept.includes(u)).map((u) => u[2]) };
}

/** Feet per pixel (horizontal and vertical) of a plane: robust consensus of its reference cues. */
export function planeScale(plane: Plane, view: View, seen: Set<string> = new Set()): PlaneScale | null {
  const vertical: Sample[] = [];
  const horizontal: Sample[] = [];
  const refs = plane.references.filter((r) => r.enabled);
  for (const r of refs) {
    const px = distance(r.p1, r.p2, view.width, view.height);
    if (px < MIN_LINE_PX) continue;
    const sample: Sample = [r.real_length_ft / px, r.source === "auto" ? r.weight : 1, r];
    if (r.axis !== "horizontal") vertical.push(sample);
    if (r.axis !== "vertical") horizontal.push(sample);
  }
  const v = consensus(vertical);
  const h = consensus(horizontal);
  if (!v && !h) {
    const fallback = view.planes.find((p) => p.id === plane.fallback_plane_id);
    if (!fallback || seen.has(fallback.id)) return null;
    const borrowed = planeScale(fallback, view, new Set([...seen, plane.id]));
    return borrowed && { ...borrowed, confidence: borrowed.confidence * 0.5, borrowedFrom: fallback.name };
  }
  const y = (v ?? h)!;
  const x = (h ?? v)!;
  const used = [...new Map([...y.used, ...x.used].map((r) => [r.id, r])).values()];
  const rejected = [...new Map([...y.rejected, ...x.rejected].map((r) => [r.id, r])).values()].filter((r) => !used.includes(r));
  const spread = Math.max(x.spread, y.spread);
  const manual = refs.some((r) => r.source === "manual");
  let confidence = (manual ? 0.75 : 0.35) + 0.12 * Math.min(used.length - 1, 3);
  confidence *= Math.max(0.3, 1 - 2 * spread);
  if (plane.confirmed) confidence = Math.max(confidence, 0.9);
  return {
    ftPerPxX: x.value,
    ftPerPxY: y.value,
    confidence: Math.round(Math.min(confidence, 0.97) * 100) / 100,
    spread,
    cuesUsed: used.map((r) => r.name),
    cuesRejected: rejected.map((r) => r.name),
    borrowedFrom: null,
  };
}

/** Real length of a reference line according to a plane's scale (to show what a line implies). */
export function lineLengthFt(ref: Pick<ScaleReference, "p1" | "p2">, scale: PlaneScale, view: View): number {
  const dx = (ref.p2[0] - ref.p1[0]) * view.width * scale.ftPerPxX;
  const dy = (ref.p2[1] - ref.p1[1]) * view.height * scale.ftPerPxY;
  return Math.hypot(dx, dy);
}

export function polygonBounds(polygons: Point[][]): [number, number, number, number] {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const poly of polygons)
    for (const [x, y] of poly) {
      x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    }
  return [x0, y0, x1, y1];
}

/** Shoelace area of a normalised polygon in image pixels. */
export function polygonAreaPx(points: Point[], width: number, height: number): number {
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    sum += x1 * width * (y2 * height) - x2 * width * (y1 * height);
  }
  return Math.abs(sum) / 2;
}

export function clamp01(p: Point): Point {
  return [Math.min(1, Math.max(0, p[0])), Math.min(1, Math.max(0, p[1]))];
}

/** Ray-casting point-in-polygon test on normalised coordinates. */
export function pointInPolygon([px, py]: Point, poly: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** The top-most region under a point (what the user sees when clicking the photo). */
export function regionAt(point: Point, regions: Region[]): Region | null {
  const ordered = layerOrder(regions);
  for (let i = ordered.length - 1; i >= 0; i--) {
    if (ordered[i].polygons.some((poly) => poly.length >= 3 && pointInPolygon(point, poly))) return ordered[i];
  }
  return null;
}
