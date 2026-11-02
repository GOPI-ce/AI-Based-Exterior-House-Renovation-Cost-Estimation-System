/**
 * Structure-preserving renovation renderer (runs in the browser, no AI cost).
 *
 * Each region is painted in layer order (walls first, openings last). For a region:
 *  1. its polygons are rasterised into an anti-aliased mask;
 *  2. the material is generated at real-world scale (feet per pixel from the photo's scale reference);
 *  3. the photo's lighting is re-applied. Lighting is estimated as the local *brightest envelope*
 *     of the photo (white-patch Retinex): a dark old panel takes the brightness of its surroundings,
 *     so the old surface's colour pattern does not bleed through, while real shadows (larger than
 *     the window) stay dark. Gates and railings use a fine, detail-preserving variant (slats stay visible);
 *  4. the result is alpha-blended into the output.
 * Openings and surfaces without a new material restore the original photo pixels.
 */
import { COMPONENT_META, layerOrder, planeForRegion, planeScale, polygonBounds, type PlaneScale } from "./geometry";
import type { Catalog, Design, Material, Region, View } from "./types";

export interface Texture {
  image: HTMLImageElement;
  width: number;
  height: number;
}

interface Sampled {
  w: number;
  h: number;
  data: Uint8ClampedArray;
  meanLum: number;
}

const FALLBACK_FACADE_WIDTH_FT = 40; // used only when a photo has no scale yet
const textureLoads = new Map<string, Promise<Texture>>();
const sampledCache = new Map<string, Sampled>();

export function loadTexture(file: string): Promise<Texture> {
  let promise = textureLoads.get(file);
  if (!promise) {
    promise = new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve({ image, width: image.naturalWidth, height: image.naturalHeight });
      image.onerror = () => {
        textureLoads.delete(file); // allow a retry on the next render
        reject(new Error(`Texture ${file} failed to load`));
      };
      image.src = `/textures/${file}`;
    });
    textureLoads.set(file, promise);
  }
  return promise;
}

/** Load every texture a design needs (resolves to a lookup by file name). */
export async function loadDesignTextures(design: Design, catalog: Catalog): Promise<Map<string, Texture>> {
  const files = new Set<string>();
  for (const a of Object.values(design.assignments)) {
    const file = catalog.materials.find((m) => m.id === a.material_id)?.render.texture;
    if (file) files.add(file);
  }
  // A texture that fails to load falls back to the material's colour instead of breaking the render.
  const results = await Promise.allSettled([...files].map(async (f) => [f, await loadTexture(f)] as const));
  return new Map(results.flatMap((r) => (r.status === "fulfilled" ? [r.value] : [])));
}

/** The texture resampled so one tile is `width` pixels wide (a manual mip-map: avoids aliasing). */
function sampleTexture(file: string, tex: Texture, width: number): Sampled {
  const w = Math.max(8, Math.min(2048, Math.round(width)));
  const key = `${file}@${w}`;
  const hit = sampledCache.get(key);
  if (hit) return hit;
  const h = Math.max(8, Math.round((w * tex.height) / tex.width));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(tex.image, 0, 0, w, h);
  const data = ctx.getImageData(0, 0, w, h).data;
  let sum = 0;
  for (let i = 0; i < data.length; i += 4) sum += lum(data[i], data[i + 1], data[i + 2]);
  const sampled = { w, h, data, meanLum: sum / (w * h) || 1 };
  sampledCache.set(key, sampled);
  return sampled;
}

const lum = (r: number, g: number, b: number) => 0.2126 * r + 0.7152 * g + 0.0722 * b;

function hexToRgb(hex: string | null | undefined, fallback: [number, number, number] = [220, 214, 200]) {
  if (!hex || !/^#[0-9a-f]{6}$/i.test(hex)) return fallback;
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [number, number, number];
}

interface RegionMask {
  region: Region;
  x0: number;
  y0: number;
  w: number;
  h: number;
  alpha: Float32Array; // 0..1 per bbox pixel
  light: Lighting;
}

/** Low-resolution lighting estimate for one region (grid cells of `cell` x `cell` pixels). */
interface Lighting {
  cell: number;
  gw: number;
  gh: number;
  grid: Float32Array;
  mean: number;
  detail: boolean;
}

/** Thin metal surfaces keep fine shading; walls get the albedo-free envelope. */
const DETAIL_TYPES = new Set(["gate", "railing"]);

export interface RenderOptions {
  maxSide?: number; // downscale for fast previews
}

export function renderView(
  photo: CanvasImageSource,
  view: View,
  design: Design,
  catalog: Catalog,
  textures: Map<string, Texture>,
  target: HTMLCanvasElement,
  options: RenderOptions = {},
): void {
  const scale = Math.min(1, (options.maxSide ?? Infinity) / Math.max(view.width, view.height));
  const W = Math.round(view.width * scale);
  const H = Math.round(view.height * scale);
  target.width = W;
  target.height = H;
  const ctx = target.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(photo, 0, 0, W, H);
  const src = ctx.getImageData(0, 0, W, H).data;
  const out = new Uint8ClampedArray(src);

  const L = new Float32Array(W * H);
  for (let i = 0, p = 0; i < L.length; i++, p += 4) L[i] = lum(src[p], src[p + 1], src[p + 2]);

  // Pass 1: masks and lighting of every region.
  const cell = Math.max(2, Math.round(Math.max(W, H) / 320));
  const maskCanvas = document.createElement("canvas");
  maskCanvas.width = W;
  maskCanvas.height = H;
  const mctx = maskCanvas.getContext("2d", { willReadFrequently: true })!;
  const masks: RegionMask[] = [];
  let lumSum = 0;
  let lumWeight = 0;
  for (const region of layerOrder(view.regions)) {
    const mask = rasterise(region, W, H, mctx, L, cell);
    if (!mask) continue;
    masks.push(mask);
    if (!mask.light.detail) {
      lumSum += mask.light.mean * mask.alpha.length;
      lumWeight += mask.alpha.length;
    }
  }
  const sceneLight = lumWeight ? lumSum / lumWeight : 160;

  // Pass 2: paint bottom-to-top.
  const scales = new Map<string, PlaneScale | null>(view.planes.map((p) => [p.id, planeScale(p, view)]));
  for (const mask of masks) {
    const { region } = mask;
    const assignment = design.assignments[region.id];
    const material = assignment && !COMPONENT_META[region.type].opening
      ? catalog.materials.find((m) => m.id === assignment.material_id)
      : undefined;
    if (!material) {
      restore(mask, src, out, W);
      continue;
    }
    const plane = planeForRegion(region, view);
    const ps = plane ? scales.get(plane.id) : null;
    const fallback = FALLBACK_FACADE_WIDTH_FT / view.width;
    // Feet per *rendered* pixel, horizontally and vertically (angled planes differ).
    const fpx = (ps?.ftPerPxX ?? fallback) / scale;
    const fpy = (ps?.ftPerPxY ?? fallback) / scale;
    paintMaterial(mask, material, assignment.color, fpx, fpy, sceneLight, out, W, textures);
  }

  ctx.putImageData(new ImageData(out, W, H), 0, 0);
}

function rasterise(region: Region, W: number, H: number, mctx: CanvasRenderingContext2D, L: Float32Array, cell: number): RegionMask | null {
  const polygons = region.polygons.filter((p) => p.length >= 3);
  if (!polygons.length) return null;
  const [bx0, by0, bx1, by1] = polygonBounds(polygons);
  const x0 = Math.max(0, Math.floor(bx0 * W) - 1);
  const y0 = Math.max(0, Math.floor(by0 * H) - 1);
  const x1 = Math.min(W, Math.ceil(bx1 * W) + 1);
  const y1 = Math.min(H, Math.ceil(by1 * H) + 1);
  const w = x1 - x0;
  const h = y1 - y0;
  if (w <= 0 || h <= 0) return null;

  mctx.clearRect(x0, y0, w, h);
  mctx.fillStyle = "#fff";
  // Fill each part separately: overlapping parts form a union (as the backend measures them),
  // whatever direction their corners were drawn in.
  for (const poly of polygons) {
    mctx.beginPath();
    poly.forEach(([x, y], i) => (i ? mctx.lineTo(x * W, y * H) : mctx.moveTo(x * W, y * H)));
    mctx.closePath();
    mctx.fill();
  }
  const raw = mctx.getImageData(x0, y0, w, h).data;

  const alpha = new Float32Array(w * h);
  let weight = 0;
  for (let i = 0; i < alpha.length; i++) {
    alpha[i] = raw[i * 4 + 3] / 255;
    weight += alpha[i];
  }
  if (weight < 1) return null;
  const detail = DETAIL_TYPES.has(region.type);
  const envelopeCells = Math.round((Math.max(W, H) * 0.04) / cell);
  const light = detail
    ? estimateLighting(alpha, x0, y0, w, h, L, W, 1, 0, 1)
    : estimateLighting(alpha, x0, y0, w, h, L, W, cell, envelopeCells, envelopeCells);
  return { region, x0, y0, w, h, alpha, light: { ...light, detail } };
}

function restore(mask: RegionMask, src: Uint8ClampedArray, out: Uint8ClampedArray, W: number) {
  const { x0, y0, w, h, alpha } = mask;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const a = alpha[y * w + x];
      if (a <= 0) continue;
      const p = ((y0 + y) * W + x0 + x) * 4;
      for (let c = 0; c < 3; c++) out[p + c] = out[p + c] * (1 - a) + src[p + c] * a;
    }
}

/**
 * Lighting on a coarse grid: masked average luminance per cell, then a masked max filter
 * (brightest envelope: removes darker *materials* smaller than the window), then a masked blur.
 */
function estimateLighting(
  alpha: Float32Array,
  x0: number,
  y0: number,
  w: number,
  h: number,
  L: Float32Array,
  W: number,
  cell: number,
  maxRadius: number,
  blurRadius: number,
): Omit<Lighting, "detail"> {
  const gw = Math.ceil(w / cell);
  const gh = Math.ceil(h / cell);
  const sum = new Float32Array(gw * gh);
  const weight = new Float32Array(gw * gh);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const a = alpha[y * w + x];
      if (a <= 0) continue;
      const g = Math.floor(y / cell) * gw + Math.floor(x / cell);
      sum[g] += a * L[(y0 + y) * W + x0 + x];
      weight[g] += a;
    }
  const grid = new Float32Array(gw * gh);
  for (let g = 0; g < grid.length; g++) grid[g] = weight[g] > 0 ? sum[g] / weight[g] : -1;
  if (maxRadius > 0) maxFilter(grid, gw, gh, maxRadius);

  const num = new Float32Array(gw * gh);
  const den = new Float32Array(gw * gh);
  for (let g = 0; g < grid.length; g++) {
    if (weight[g] > 0 && grid[g] >= 0) {
      num[g] = grid[g];
      den[g] = 1;
    }
  }
  boxBlur(num, gw, gh, blurRadius);
  boxBlur(den, gw, gh, blurRadius);
  let total = 0;
  let totalWeight = 0;
  for (let g = 0; g < grid.length; g++) {
    grid[g] = den[g] > 1e-4 ? num[g] / den[g] : -1;
    if (grid[g] >= 0 && weight[g] > 0) {
      total += grid[g] * weight[g];
      totalWeight += weight[g];
    }
  }
  const mean = totalWeight ? total / totalWeight : 128;
  for (let g = 0; g < grid.length; g++) if (grid[g] < 0) grid[g] = mean;
  return { cell, gw, gh, grid, mean };
}

/** Bilinear lookup of the lighting grid at a bbox pixel. */
function lightAt(l: Lighting, x: number, y: number): number {
  const gx = Math.min(l.gw - 1, Math.max(0, (x + 0.5) / l.cell - 0.5));
  const gy = Math.min(l.gh - 1, Math.max(0, (y + 0.5) / l.cell - 0.5));
  const ix = Math.floor(gx);
  const iy = Math.floor(gy);
  const fx = gx - ix;
  const fy = gy - iy;
  const jx = Math.min(l.gw - 1, ix + 1);
  const jy = Math.min(l.gh - 1, iy + 1);
  const top = l.grid[iy * l.gw + ix] * (1 - fx) + l.grid[iy * l.gw + jx] * fx;
  const bottom = l.grid[jy * l.gw + ix] * (1 - fx) + l.grid[jy * l.gw + jx] * fx;
  return top * (1 - fy) + bottom * fy;
}

/** Separable running max over a radius (cells marked -1 never win). */
function maxFilter(data: Float32Array, w: number, h: number, r: number) {
  const tmp = new Float32Array(Math.max(w, h));
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let m = -1;
      for (let k = Math.max(0, x - r); k <= Math.min(w - 1, x + r); k++) m = Math.max(m, data[y * w + k]);
      tmp[x] = m;
    }
    for (let x = 0; x < w; x++) data[y * w + x] = tmp[x];
  }
  for (let x = 0; x < w; x++) {
    for (let y = 0; y < h; y++) {
      let m = -1;
      for (let k = Math.max(0, y - r); k <= Math.min(h - 1, y + r); k++) m = Math.max(m, data[k * w + x]);
      tmp[y] = m;
    }
    for (let y = 0; y < h; y++) data[y * w + x] = tmp[y];
  }
}

function boxBlur(data: Float32Array, w: number, h: number, r: number) {
  const tmp = new Float32Array(Math.max(w, h));
  const pass = (count: number, length: number, index: (line: number, k: number) => number) => {
    for (let line = 0; line < count; line++) {
      let acc = 0;
      for (let k = -r; k <= r; k++) acc += data[index(line, Math.min(length - 1, Math.max(0, k)))];
      for (let k = 0; k < length; k++) {
        tmp[k] = acc / (2 * r + 1);
        acc += data[index(line, Math.min(length - 1, k + r + 1))] - data[index(line, Math.max(0, k - r))];
      }
      for (let k = 0; k < length; k++) data[index(line, k)] = tmp[k];
    }
  };
  pass(h, w, (y, x) => y * w + x);
  pass(w, h, (x, y) => y * w + x);
}

function paintMaterial(
  mask: RegionMask,
  material: Material,
  colorHex: string | null,
  ftPerPxX: number,
  ftPerPxY: number,
  sceneLight: number,
  out: Uint8ClampedArray,
  W: number,
  textures: Map<string, Texture>,
) {
  const { x0, y0, w, h, alpha, light } = mask;
  const spec = material.render;
  // How strongly the photo's lighting modulates the new material, and its allowed range.
  // Lighting is applied as a gamma curve: shadows stay visible, but leftover old-colour patches
  // (which the envelope cannot fully separate from shadow) only shift brightness gently.
  const gamma = light.detail ? 0.95 : spec.mode === "texture" || spec.mode === "tiles" ? 0.5 : 0.6;
  const [minShade, maxShade] = light.detail ? [0.25, 1.6] : [0.4, 1.3];
  // Keep the relative exposure of this surface (a soffit in shade stays darker than a sunlit wall).
  const exposure = light.detail ? 1 : Math.min(1.1, Math.max(0.65, Math.pow(light.mean / sceneLight, 0.6)));
  const base = hexToRgb(colorHex ?? material.default_color ?? spec.color);

  const tex = spec.texture ? textures.get(spec.texture) : undefined;
  const tileFt = spec.tile_ft ?? 4;
  const sampled = tex && spec.texture ? sampleTexture(spec.texture, tex, tileFt / ftPerPxX) : null;
  const tileH = sampled ? (tileFt * sampled.h) / sampled.w : 1;
  const tint = spec.tint ? hexToRgb(spec.tint) : null;

  // Column extents for railings (top / bottom edge of the mask in each column).
  let top: Int32Array | null = null;
  let bottom: Int32Array | null = null;
  if (spec.mode === "glass" || spec.mode === "rail") {
    top = new Int32Array(w).fill(-1);
    bottom = new Int32Array(w).fill(-1);
    for (let x = 0; x < w; x++)
      for (let y = 0; y < h; y++)
        if (alpha[y * w + x] > 0.5) {
          if (top[x] < 0) top[x] = y;
          bottom[x] = y;
        }
  }
  // Size of a real-world distance in pixels (at least one pixel), and a joint's width in feet.
  const pxY = (ft: number) => Math.max(1, ft / ftPerPxY);
  const jointX = (ft: number) => Math.max(ft, ftPerPxX);
  const jointY = (ft: number) => Math.max(ft, ftPerPxY);
  const railColor = hexToRgb(spec.mode === "glass" ? "#C9CDD0" : colorHex ?? spec.color);

  const rgb: [number, number, number] = [0, 0, 0];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      const a = alpha[i];
      if (a <= 0) continue;
      const gx = x0 + x;
      const gy = y0 + y;
      const p = (gy * W + gx) * 4;
      const fx = gx * ftPerPxX; // position in feet
      const fy = gy * ftPerPxY;
      let lit = true;

      switch (spec.mode) {
        case "glass": {
          // Glass shows the (already repainted) surface behind it, slightly tinted and brightened.
          const onRail = top && y - top[x] < pxY(0.18);
          const onPost = spec.posts && fx % 4 < jointX(0.15);
          if (onRail || onPost) {
            rgb[0] = railColor[0]; rgb[1] = railColor[1]; rgb[2] = railColor[2];
          } else {
            for (let c = 0; c < 3; c++) rgb[c] = out[p + c] * 0.72 + [208, 230, 234][c] * 0.28;
            lit = false;
          }
          break;
        }
        case "rail": {
          const onRail = top && bottom && (y - top[x] < pxY(0.16) || bottom[x] - y < pxY(0.12));
          const onBaluster = fx % 0.36 < jointX(0.05);
          if (onRail || onBaluster) {
            rgb[0] = railColor[0]; rgb[1] = railColor[1]; rgb[2] = railColor[2];
          } else {
            rgb[0] = out[p]; rgb[1] = out[p + 1]; rgb[2] = out[p + 2];
            lit = false;
          }
          break;
        }
        case "panel": {
          const jw = spec.joint_w_ft ?? 4;
          const jh = spec.joint_h_ft ?? 8;
          const joint = fx % jw < jointX(0.04) || fy % jh < jointY(0.04);
          const k = joint ? 0.55 : 1;
          rgb[0] = base[0] * k; rgb[1] = base[1] * k; rgb[2] = base[2] * k;
          break;
        }
        default: {
          // tint, texture, tiles
          if (sampled) {
            const u = Math.floor((((fx / tileFt) % 1) + 1) % 1 * sampled.w);
            const v = Math.floor((((fy / tileH) % 1) + 1) % 1 * sampled.h);
            const t = (v * sampled.w + u) * 4;
            const tr = sampled.data[t], tg = sampled.data[t + 1], tb = sampled.data[t + 2];
            if (spec.mode === "tint") {
              const grain = 1 + (spec.strength ?? 0.2) * (lum(tr, tg, tb) / sampled.meanLum - 1);
              rgb[0] = base[0] * grain; rgb[1] = base[1] * grain; rgb[2] = base[2] * grain;
            } else if (tint) {
              // Tinted stone/tile: the texture's detail in the chosen stone's colour.
              const grain = lum(tr, tg, tb) / sampled.meanLum;
              for (let c = 0; c < 3; c++) rgb[c] = tint[c] * grain * 0.75 + [tr, tg, tb][c] * 0.25;
            } else {
              rgb[0] = tr; rgb[1] = tg; rgb[2] = tb;
            }
          } else {
            rgb[0] = base[0]; rgb[1] = base[1]; rgb[2] = base[2];
          }
          if (spec.mode === "tiles") {
            const jw = spec.joint_w_ft ?? 4;
            const jh = spec.joint_h_ft ?? 2;
            if (fx % jw < jointX(0.03) || fy % jh < jointY(0.03)) {
              rgb[0] = 128; rgb[1] = 122; rgb[2] = 112;
            }
          }
        }
      }

      const s = Math.min(maxShade, Math.max(minShade, lightAt(light, x, y) / light.mean));
      const k = lit ? Math.pow(s, gamma) * exposure : 1;
      for (let c = 0; c < 3; c++) out[p + c] = out[p + c] * (1 - a) + Math.min(255, rgb[c] * k) * a;
    }
  }
}

/** Load a photo from the API as a CORS-clean image (needed to read and export canvas pixels). */
export function loadPhoto(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Photo failed to load"));
    image.src = url;
  });
}

/** Render a design for one photo into a JPEG data URL (for the report and downloads). */
export async function renderToDataUrl(view: View, design: Design, catalog: Catalog, photoUrl: string, maxSide = 1600): Promise<string> {
  const [photo, textures] = await Promise.all([loadPhoto(photoUrl), loadDesignTextures(design, catalog)]);
  const canvas = document.createElement("canvas");
  renderView(photo, view, design, catalog, textures, canvas, { maxSide });
  return canvas.toDataURL("image/jpeg", 0.88);
}
