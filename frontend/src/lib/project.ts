import type { CSSProperties } from "react";

import type { Catalog, Design, ImageInfo, Material, ProjectData, Region, View } from "./types";

export function newView(info: ImageInfo, name: string, id = `view-${Date.now().toString(36)}`): View {
  return {
    id,
    name,
    image_id: info.image_id,
    width: info.width,
    height: info.height,
    regions: [],
    planes: [],
    quality: info.quality,
    scene: null,
  };
}

export function newProjectData(view: View): ProjectData {
  return {
    views: [view],
    designs: [{ id: "design-a", name: "Design A", assignments: {} }],
    active_design_id: "design-a",
    rate_overrides: {},
    settings: { contingency_pct: 10, gst_pct: 18, paint_coats: 2, city_id: "ahmedabad", site_items: null },
  };
}

export function activeDesign(data: ProjectData): Design {
  return data.designs.find((d) => d.id === data.active_design_id) ?? data.designs[0];
}

export function findRegion(data: ProjectData, viewId: string, regionId: string): Region | undefined {
  return data.views.find((v) => v.id === viewId)?.regions.find((r) => r.id === regionId);
}

export function materialById(catalog: Catalog | null, id: string | undefined): Material | undefined {
  return id ? catalog?.materials.find((m) => m.id === id) : undefined;
}

/**
 * A region id unused anywhere in the project, e.g. "wall-9". Ids must be unique across photos
 * because designs store materials by region id.
 */
export function nextRegionId(data: ProjectData, type: string, reserved: Set<string> = new Set()): string {
  const used = new Set([...reserved, ...data.views.flatMap((v) => v.regions.map((r) => r.id))]);
  let n = 1;
  while (used.has(`${type}-${n}`)) n++;
  return `${type}-${n}`;
}

/** Re-number AI regions for one photo so their ids don't clash with other photos' regions. */
export function withUniqueIds(regions: Region[], data: ProjectData, viewId: string): Region[] {
  const others = { ...data, views: data.views.filter((v) => v.id !== viewId) };
  const reserved = new Set<string>();
  return regions.map((r) => {
    const id = nextRegionId(others, r.type, reserved);
    reserved.add(id);
    return { ...r, id };
  });
}

/** Swatch CSS for a material: its texture image, or its colour. */
export function materialSwatch(material: Material, color?: string | null): CSSProperties {
  const tint = color ?? material.default_color ?? material.render.color ?? "#ddd";
  switch (material.render.mode) {
    case "texture":
    case "tiles":
      return material.render.tint
        ? { backgroundImage: `url(/textures/${material.render.texture})`, backgroundColor: material.render.tint, backgroundBlendMode: "multiply", backgroundSize: "cover" }
        : { backgroundImage: `url(/textures/${material.render.texture})`, backgroundSize: "cover" };
    case "glass":
      return { background: "linear-gradient(135deg, #d9eef2 0%, #9fc6cf 55%, #e8f6f8 100%)" };
    case "rail":
      return { background: `repeating-linear-gradient(90deg, ${tint} 0 3px, #f3f4f2 3px 11px)` };
    case "panel":
      return { background: `linear-gradient(90deg, transparent 49%, rgba(0,0,0,.35) 49% 51%, transparent 51%), ${tint}` };
    default:
      // Strongly grained tints (texture finish, WPC) show their grain in the swatch too.
      if (material.render.texture && (material.render.strength ?? 0) >= 0.5)
        return {
          backgroundImage: `url(/textures/${material.render.texture})`,
          backgroundColor: tint,
          backgroundBlendMode: "multiply",
          backgroundSize: "cover",
        };
      return { background: tint };
  }
}
