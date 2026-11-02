"use client";

import { ChevronsLeftRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Spinner } from "@/components/ui";
import { imageUrl } from "@/lib/api";
import { useViewDepth } from "@/lib/depth";
import { usePhoto } from "@/lib/hooks";
import { loadDesignTextures, renderView } from "@/lib/render";
import type { Catalog, Design, View } from "@/lib/types";

export type CompareMode = "after" | "split" | "before";

/** The redesigned photo (rendered in the browser) with an optional before/after slider. */
export function RenderedPreview({
  view,
  design,
  catalog,
  mode,
  maxSide = 1400,
}: {
  view: View;
  design: Design;
  catalog: Catalog | null;
  mode: CompareMode;
  maxSide?: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const { photo } = usePhoto(view.image_id);
  const depth = useViewDepth(view);
  const [rendering, setRendering] = useState(true);
  const [split, setSplit] = useState(50);
  const frame = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!photo || !catalog || !canvas.current) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setRendering(true);
      const textures = await loadDesignTextures(design, catalog).catch(() => new Map());
      if (cancelled || !canvas.current) return;
      renderView(photo, view, design, catalog, textures, canvas.current, { maxSide, depth });
      setRendering(false);
    }, 60);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [photo, view, design, catalog, maxSide, depth]);

  function dragSplit(clientX: number) {
    const rect = frame.current?.getBoundingClientRect();
    if (rect) setSplit(Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100)));
  }

  return (
    <div ref={frame} className="absolute inset-0">
      <canvas ref={canvas} className="absolute inset-0 size-full" />
      {(mode === "before" || mode === "split") && (
        // eslint-disable-next-line @next/next/no-img-element -- photo served by the API
        <img
          src={imageUrl(view.image_id)}
          alt="Original photo"
          className="absolute inset-0 size-full"
          style={mode === "split" ? { clipPath: `inset(0 ${100 - split}% 0 0)` } : undefined}
        />
      )}
      {mode === "split" && (
        <div
          className="absolute inset-y-0 z-10 w-0.5 cursor-ew-resize bg-white shadow-[0_0_0_1px_rgba(0,0,0,.2)]"
          style={{ left: `${split}%` }}
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            dragSplit(e.clientX);
          }}
          onPointerMove={(e) => e.buttons === 1 && dragSplit(e.clientX)}
        >
          <span className="absolute top-1/2 left-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-ink shadow-lg">
            <ChevronsLeftRight className="size-4" />
          </span>
          <span className="absolute top-2 right-2 rounded bg-black/55 px-1.5 py-0.5 text-[10px] font-bold text-white">BEFORE</span>
          <span className="absolute top-2 left-2 rounded bg-accent/90 px-1.5 py-0.5 text-[10px] font-bold text-white">AFTER</span>
        </div>
      )}
      {(rendering || !photo) && (
        <div className="absolute top-2 right-2 z-10 flex items-center gap-1.5 rounded-lg bg-white/90 px-2 py-1 text-xs font-semibold text-muted shadow">
          <Spinner className="size-3.5" /> Rendering
        </div>
      )}
    </div>
  );
}
