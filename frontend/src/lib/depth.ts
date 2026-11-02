"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "./api";
import { layerOrder, pointInPolygon } from "./geometry";
import type { Point, Region, View } from "./types";

/**
 * Distance-aware measurement: the photo's depth grid (from Depth Anything V2 on the server) and the
 * same sampling as backend/app/services/depth.py, on the same integer-centimetre values, so live
 * sizes in the editor match the estimate.
 */
export interface DepthGrid {
  cols: number;
  rows: number;
  focalNorm: number;
  model: string;
  cm: Uint16Array; // row-major
}

/** A photo's depth grid plus the distance (m) of each of its regions. */
export interface ViewDepth {
  grid: DepthGrid;
  regions: Map<string, number>;
}

const LINE_SAMPLES = [0.1, 0.3, 0.5, 0.7, 0.9];
const RETRY_DELAYS_S = [10, 20, 40, 60, 120];
export const FT_PER_M = 3.28084;

// Successful fetches only: a photo whose depth is not ready yet is asked again later.
const cache = new Map<string, Promise<DepthGrid | null>>();

export function fetchDepth(imageId: string): Promise<DepthGrid | null> {
  let promise = cache.get(imageId);
  if (!promise) {
    promise = api.depth(imageId).then((grid) => {
      if (!grid) cache.delete(imageId);
      return grid;
    });
    cache.set(imageId, promise);
  }
  return promise;
}

function cell(grid: DepthGrid, x: number, y: number): number {
  const r = Math.min(grid.rows - 1, Math.max(0, Math.floor(y * grid.rows)));
  const c = Math.min(grid.cols - 1, Math.max(0, Math.floor(x * grid.cols)));
  return grid.cm[r * grid.cols + c];
}

function medianM(values: number[]): number {
  const s = [...values].sort((a, b) => a - b);
  const mid = s.length >> 1;
  return (s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2) / 100;
}

/** Distance (m) of a reference line: median of five samples along it. */
export function depthOnLine(grid: DepthGrid, p1: Point, p2: Point): number {
  return medianM(LINE_SAMPLES.map((t) => cell(grid, p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))));
}

/** Distance (m) of each region: median depth of the cells where it is the visible (top) layer. */
export function regionDepths(grid: DepthGrid, regions: Region[]): Map<string, number> {
  const { cols, rows } = grid;
  const top = new Int32Array(cols * rows).fill(-1);
  const index = new Map(regions.map((r, i) => [r, i]));
  const cells = new Map<number, number[]>();
  for (const region of layerOrder(regions)) {
    const i = index.get(region)!;
    const polys = region.polygons.filter((p) => p.length >= 3);
    const mine: number[] = [];
    for (const poly of polys) {
      let x0 = 1, y0 = 1, x1 = 0, y1 = 0;
      for (const [x, y] of poly) {
        x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
      }
      const c0 = Math.max(0, Math.floor(x0 * cols - 0.5)), c1 = Math.min(cols - 1, Math.ceil(x1 * cols));
      const r0 = Math.max(0, Math.floor(y0 * rows - 0.5)), r1 = Math.min(rows - 1, Math.ceil(y1 * rows));
      for (let r = r0; r <= r1; r++) {
        for (let c = c0; c <= c1; c++) {
          if (pointInPolygon([(c + 0.5) / cols, (r + 0.5) / rows], poly)) mine.push(r * cols + c);
        }
      }
    }
    for (const k of mine) top[k] = i;
    cells.set(i, mine);
  }

  const out = new Map<string, number>();
  regions.forEach((region, i) => {
    const all = [...new Set(cells.get(i) ?? [])];
    const visible = all.filter((k) => top[k] === i);
    if (visible.length) out.set(region.id, medianM(visible.map((k) => grid.cm[k])));
    else if (all.length) out.set(region.id, medianM(all.map((k) => grid.cm[k])));
    else {
      const pts = region.polygons.flat();
      if (!pts.length) return;
      const xs = pts.map((p) => p[0]);
      const ys = pts.map((p) => p[1]);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      out.set(region.id, cell(grid, cx, cy) / 100);
    }
  });
  return out;
}

export function viewDepth(grid: DepthGrid | null, view: View): ViewDepth | null {
  return grid ? { grid, regions: regionDepths(grid, view.regions) } : null;
}

/** The view's depth (fetched once per photo) with its regions' distances, recomputed as regions change. */
export function useViewDepth(view: View | undefined): ViewDepth | null {
  const imageId = view?.image_id;
  const hasRegions = Boolean(view?.regions.length);
  const [grid, setGrid] = useState<{ id: string; grid: DepthGrid } | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!imageId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    // Not ready yet (model still loading on a cold server, or analysis running): ask again with backoff.
    fetchDepth(imageId).then((g) => {
      if (cancelled) return;
      if (g) setGrid({ id: imageId, grid: g });
      else if (hasRegions && attempt < RETRY_DELAYS_S.length) timer = setTimeout(() => setAttempt((a) => a + 1), RETRY_DELAYS_S[attempt] * 1000);
    });
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [imageId, hasRegions, attempt]);
  const current = grid && grid.id === imageId ? grid.grid : null;
  const regions = view?.regions;
  return useMemo(() => (current && regions ? { grid: current, regions: regionDepths(current, regions) } : null), [current, regions]);
}

export function decodeDepth(json: { cols: number; rows: number; focal_norm: number; model: string; cm: string }): DepthGrid {
  const bytes = Uint8Array.from(atob(json.cm), (ch) => ch.charCodeAt(0));
  const view = new DataView(bytes.buffer);
  const cm = new Uint16Array(json.cols * json.rows);
  for (let i = 0; i < cm.length; i++) cm[i] = view.getUint16(i * 2, true);
  return { cols: json.cols, rows: json.rows, focalNorm: json.focal_norm, model: json.model, cm };
}
