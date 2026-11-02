// Mirrors backend/app/schemas.py and backend/app/catalog.py.
// Points are normalised to the image: [x, y] with 0 <= x, y <= 1.

export type Point = [number, number];

export type ComponentType =
  | "wall"
  | "window"
  | "door"
  | "balcony"
  | "railing"
  | "pillar"
  | "parapet"
  | "gate"
  | "roof_edge";

export interface QualityIssue {
  code: string;
  severity: "error" | "warning";
  message: string;
}

export interface QualityReport {
  ok: boolean;
  issues: QualityIssue[];
  metrics: Record<string, number>;
}

export interface SceneSummary {
  is_residential_exterior: boolean;
  view_type: string;
  storeys: number | null;
  usable: boolean;
  issues: string[];
  guidance: string[];
}

export interface Region {
  id: string;
  type: ComponentType;
  label: string;
  polygons: Point[][];
  source: "ai" | "ai_box" | "user";
  confidence: number | null;
  area_override_sqft: number | null;
  length_override_ft: number | null;
  face_factor: number;
  plane_id: string | null;
  remove_existing: boolean;
}

export type PlaneKind = "house_front" | "house_side" | "boundary" | "other";
export type CueKind = "door" | "gate" | "railing" | "parapet" | "storey" | "window" | "car" | "person" | "motorbike" | "custom";

/** A line on the photo whose real length is known or estimated. */
export interface ScaleReference {
  id: string;
  name: string;
  cue: CueKind;
  axis: "vertical" | "horizontal" | "free";
  p1: Point;
  p2: Point;
  real_length_ft: number;
  source: "auto" | "manual";
  weight: number;
  enabled: boolean;
}

/** Surfaces at a similar distance from the camera, measured with one consensus scale. */
export interface Plane {
  id: string;
  name: string;
  kind: PlaneKind;
  references: ScaleReference[];
  fallback_plane_id: string | null;
  confirmed: boolean;
}

export interface View {
  id: string;
  name: string;
  image_id: string;
  width: number;
  height: number;
  regions: Region[];
  planes: Plane[];
  quality: QualityReport | null;
  scene: SceneSummary | null;
}

export interface Assignment {
  material_id: string;
  color: string | null;
}

export interface Design {
  id: string;
  name: string;
  assignments: Record<string, Assignment>;
}

export interface RateOverride {
  material_rate: number | null;
  labour_rate: number | null;
}

export interface ProjectSettings {
  contingency_pct: number;
  gst_pct: number;
  paint_coats: number;
  city_id: string;
  site_items: string[] | null; // null = catalogue defaults
}

export interface ProjectData {
  views: View[];
  designs: Design[];
  active_design_id: string;
  rate_overrides: Record<string, RateOverride>;
  settings: ProjectSettings;
}

export interface Project {
  id: string;
  name: string;
  is_demo: boolean;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
  data: ProjectData;
}

export interface ProjectSummary {
  id: string;
  name: string;
  is_demo: boolean;
  updated_at: string;
  view_count: number;
  cover_image_id: string | null;
}

export interface ImageInfo {
  image_id: string;
  width: number;
  height: number;
  quality: QualityReport;
}

export interface AnalysisResult {
  regions: Region[];
  planes: Plane[];
  scene: SceneSummary;
  pipeline: Record<string, string | number | boolean>;
  warnings: string[];
}

// --- Catalogue -------------------------------------------------------------
export type CalcType = "paint" | "texture" | "cladding" | "tiles" | "sheet" | "area" | "railing";
export type Tier = "economy" | "standard" | "premium" | "luxury";

export interface RenderSpec {
  mode: "tint" | "texture" | "tiles" | "panel" | "glass" | "rail";
  texture: string | null;
  tile_ft: number | null;
  strength: number | null;
  tint: string | null;
  joint_w_ft: number | null;
  joint_h_ft: number | null;
  color: string | null;
  posts: boolean;
}

export interface Shade {
  name: string;
  hex: string;
  family: string;
}

export interface Material {
  id: string;
  name: string;
  brand: string | null;
  product: string | null;
  tier: Tier;
  category: string;
  calc: CalcType;
  rate: number;
  rate_range: [number, number];
  rate_unit: string;
  labour_rate: number;
  labour_range: [number, number];
  labour_unit: string;
  waste_pct: number;
  warranty_years: number | null;
  durability: string;
  maintenance: string;
  pros: string[];
  cons: string[];
  specs: string[];
  suitable_for: ComponentType[];
  render: RenderSpec;
  palette: string | null;
  default_color: string | null;
}

export interface SiteItem {
  id: string;
  name: string;
  basis: "house_sqft" | "coated_sqft" | "basecoat_sqft" | "removal_sqft" | "percent";
  rate: number;
  rate_range: [number, number];
  unit: string;
  default: boolean;
  note: string;
}

export interface City {
  id: string;
  name: string;
  labour_index: number;
  material_index: number;
}

export interface Catalog {
  currency: string;
  region: string;
  rates_updated: string;
  rates_note: string;
  cities: City[];
  site_items: SiteItem[];
  palettes: Record<string, Shade[]>;
  materials: Material[];
}

// --- Estimate --------------------------------------------------------------
export interface QuantityItem {
  name: string;
  quantity: number;
  unit: string;
  note: string;
}

export interface EstimateLine {
  region_id: string;
  region_label: string;
  region_type: ComponentType;
  view_name: string;
  plane_name: string;
  material_id: string;
  material_name: string;
  color_name: string;
  category: string;
  measure_unit: "sqft" | "rft";
  gross: number;
  deductions: number;
  net: number;
  measured_from: "photo" | "override" | "unscaled";
  quantities: QuantityItem[];
  material_rate: number;
  material_rate_unit: string;
  labour_rate: number;
  labour_rate_unit: string;
  material_cost: number;
  labour_cost: number;
  total: number;
  low: number;
  high: number;
  notes: string[];
}

export interface SiteLine {
  id: string;
  name: string;
  quantity: number;
  unit: string;
  rate: number;
  amount: number;
  low: number;
  high: number;
  note: string;
}

export interface CategoryTotal {
  category: string;
  material_cost: number;
  labour_cost: number;
  total: number;
}

export interface PlaneSummary {
  view_name: string;
  plane_id: string;
  plane_name: string;
  ft_per_px_x: number | null;
  ft_per_px_y: number | null;
  confidence: number;
  measurement_error_pct: number;
  cues_used: string[];
  cues_rejected: string[];
  borrowed_from: string | null;
  confirmed: boolean;
}

export interface Estimate {
  design_id: string;
  design_name: string;
  city: string;
  lines: EstimateLine[];
  site_lines: SiteLine[];
  categories: CategoryTotal[];
  planes: PlaneSummary[];
  material_total: number;
  labour_total: number;
  site_total: number;
  subtotal: number;
  contingency_pct: number;
  contingency: number;
  gst_pct: number;
  gst: number;
  grand_total: number;
  low_total: number;
  high_total: number;
  total_area_sqft: number;
  total_railing_rft: number;
  unassigned_regions: string[];
  warnings: string[];
}
