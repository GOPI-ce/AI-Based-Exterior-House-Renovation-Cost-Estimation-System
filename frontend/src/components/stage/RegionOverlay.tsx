import { COMPONENT_META, layerOrder, polygonBounds } from "@/lib/geometry";
import type { ComponentType, Point, Region, View } from "@/lib/types";

import { toSvgPoints } from "./Stage";

/**
 * Draws a photo's regions in layer order. Interactive parts carry data attributes
 * (data-kind = region | vertex | mid) that the owning step reads in its pointer handlers.
 */
export function RegionOverlay({
  view,
  unit,
  selectedId,
  hiddenTypes,
  showLabels = false,
  editable = false,
  colorFor,
  dimUnselected = false,
}: {
  view: View;
  unit: number;
  selectedId: string | null;
  hiddenTypes?: Set<ComponentType>;
  showLabels?: boolean;
  editable?: boolean;
  colorFor?: (region: Region) => string;
  dimUnselected?: boolean;
}) {
  const { width: W, height: H } = view;
  const visible = layerOrder(view.regions).filter((r) => !hiddenTypes?.has(r.type));
  const selected = view.regions.find((r) => r.id === selectedId);

  return (
    <g>
      {visible.map((r) => {
        const color = colorFor?.(r) ?? COMPONENT_META[r.type].color;
        const isSelected = r.id === selectedId;
        const faded = dimUnselected && selectedId !== null && !isSelected;
        return (
          <g key={r.id} data-kind="region" data-region={r.id} style={{ cursor: "pointer" }} opacity={faded ? 0.45 : 1}>
            {r.polygons.map((poly, i) => (
              <polygon
                key={i}
                points={toSvgPoints(poly, W, H)}
                fill={color}
                fillOpacity={isSelected ? 0.3 : 0.13}
                stroke={color}
                strokeWidth={(isSelected ? 2.5 : 1.4) * unit}
                strokeLinejoin="round"
              />
            ))}
          </g>
        );
      })}

      {showLabels &&
        visible.map((r) => {
          const [x0, y0, x1, y1] = polygonBounds(r.polygons);
          return (
            <text
              key={`label-${r.id}`}
              x={((x0 + x1) / 2) * W}
              y={((y0 + y1) / 2) * H}
              fontSize={11 * unit}
              fontWeight={700}
              textAnchor="middle"
              fill="#fff"
              stroke="rgba(0,0,0,.65)"
              strokeWidth={3 * unit}
              paintOrder="stroke"
              pointerEvents="none"
            >
              {r.label}
            </text>
          );
        })}

      {editable && selected && !hiddenTypes?.has(selected.type) && <Handles region={selected} W={W} H={H} unit={unit} />}
    </g>
  );
}

function Handles({ region, W, H, unit }: { region: Region; W: number; H: number; unit: number }) {
  const color = COMPONENT_META[region.type].color;
  return (
    <g>
      {region.polygons.map((poly, pi) =>
        poly.map((p, i) => {
          const next = poly[(i + 1) % poly.length];
          const mid: Point = [(p[0] + next[0]) / 2, (p[1] + next[1]) / 2];
          return (
            <g key={`${pi}-${i}`}>
              <circle
                data-kind="mid"
                data-poly={pi}
                data-index={i}
                cx={mid[0] * W}
                cy={mid[1] * H}
                r={3.5 * unit}
                fill={color}
                fillOpacity={0.75}
                stroke="#fff"
                strokeWidth={unit}
                style={{ cursor: "copy" }}
              >
                <title>Drag to add a corner</title>
              </circle>
              <circle
                data-kind="vertex"
                data-poly={pi}
                data-index={i}
                cx={p[0] * W}
                cy={p[1] * H}
                r={5.5 * unit}
                fill="#fff"
                stroke={color}
                strokeWidth={2 * unit}
                style={{ cursor: "move" }}
              >
                <title>Drag to move · double-click to delete</title>
              </circle>
            </g>
          );
        }),
      )}
    </g>
  );
}
