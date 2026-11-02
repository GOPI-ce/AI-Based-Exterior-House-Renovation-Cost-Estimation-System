"use client";

import { useLayoutEffect, useRef, useState, type MouseEvent, type PointerEvent, type ReactNode, type RefObject } from "react";

import type { Point } from "@/lib/types";

/**
 * Shows a photo (or rendered canvas) fitted inside its container, with an SVG overlay that uses the
 * photo's own pixel coordinates (viewBox = 0 0 width height). Children draw into that overlay.
 */
export function Stage({
  width,
  height,
  background,
  overlay,
  className = "",
  cursor,
  svgRef,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onDoubleClick,
}: {
  width: number;
  height: number;
  background: ReactNode;
  overlay?: (ctx: { unit: number }) => ReactNode;
  className?: string;
  cursor?: string;
  svgRef?: RefObject<SVGSVGElement | null>;
  onPointerDown?: (e: PointerEvent<SVGSVGElement>) => void;
  onPointerMove?: (e: PointerEvent<SVGSVGElement>) => void;
  onPointerUp?: (e: PointerEvent<SVGSVGElement>) => void;
  onDoubleClick?: (e: MouseEvent<SVGSVGElement>) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const fit = () => {
      const s = Math.min(el.clientWidth / width, el.clientHeight / height);
      setSize({ w: Math.floor(width * s), h: Math.floor(height * s) });
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
  }, [width, height]);

  // One screen pixel expressed in image pixels: keeps handles and strokes a constant on-screen size.
  const unit = size.w ? width / size.w : 1;

  return (
    <div ref={box} className={`relative grid h-full w-full place-items-center overflow-hidden ${className}`}>
      {size.w > 0 && (
        <div className="relative overflow-hidden rounded-xl bg-ink/5 shadow-sm" style={{ width: size.w, height: size.h }}>
          {background}
          {overlay && (
            <svg
              ref={svgRef}
              viewBox={`0 0 ${width} ${height}`}
              className="absolute inset-0 size-full touch-none select-none"
              style={{ cursor }}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={onPointerUp}
              onDoubleClick={onDoubleClick}
            >
              {overlay({ unit })}
            </svg>
          )}
        </div>
      )}
    </div>
  );
}

/** Pointer position as a normalised image point (0..1), clamped to the photo. */
export function pointerToPoint(e: { clientX: number; clientY: number }, svg: SVGSVGElement | null): Point {
  if (!svg) return [0, 0];
  const rect = svg.getBoundingClientRect();
  const x = (e.clientX - rect.left) / rect.width;
  const y = (e.clientY - rect.top) / rect.height;
  return [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))];
}

/** SVG points attribute for a normalised polygon. */
export const toSvgPoints = (points: Point[], width: number, height: number) =>
  points.map(([x, y]) => `${(x * width).toFixed(1)},${(y * height).toFixed(1)}`).join(" ");
