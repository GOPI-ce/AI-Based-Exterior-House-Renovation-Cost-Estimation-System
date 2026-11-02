import type {
  AnalysisResult,
  Catalog,
  DesignSuggestion,
  Estimate,
  ImageInfo,
  Project,
  ProjectData,
  ProjectSummary,
  QualityReport,
} from "./types";
import { decodeDepth, type DepthGrid } from "./depth";
import { getWorkspaceId } from "./workspace";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** An API error with a user-facing message (and the quality report for rejected photos). */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public quality?: QualityReport,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Workspace-Id", getWorkspaceId());
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection; the free server may also be waking up.", 0);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message =
      typeof detail === "string" ? detail : detail?.message ?? `Request failed (${response.status}).`;
    throw new ApiError(message, response.status, detail?.quality);
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? response.json() : response.blob()) as Promise<T>;
}

export const imageUrl = (imageId: string) => `${API_URL}/api/images/${imageId}`;

export const api = {
  health: () => request<{ status: string; gemini: string; sam: string; depth: string }>("/api/health"),
  catalog: () => request<Catalog>("/api/catalog"),

  uploadImage(file: File) {
    const form = new FormData();
    form.append("file", file);
    return request<ImageInfo>("/api/images", { method: "POST", body: form });
  },
  /** The photo's depth grid, or null while it is not available. */
  async depth(imageId: string): Promise<DepthGrid | null> {
    try {
      return decodeDepth(await request(`/api/images/${imageId}/depth`));
    } catch {
      return null;
    }
  },
  analyzeImage: (imageId: string) => request<AnalysisResult>(`/api/images/${imageId}/analyze`, { method: "POST" }),

  listProjects: () => request<ProjectSummary[]>("/api/projects"),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (name: string, data: ProjectData) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify({ name, data }) }),
  saveProject: (id: string, name: string, data: ProjectData) =>
    request<Project>(`/api/projects/${id}`, { method: "PUT", body: JSON.stringify({ name, data }) }),
  copyProject: (id: string) => request<Project>(`/api/projects/${id}/copy`, { method: "POST" }),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),

  estimate: (data: ProjectData, designId: string | null, signal?: AbortSignal) =>
    request<Estimate>("/api/estimate", { method: "POST", body: JSON.stringify({ data, design_id: designId }), signal }),
  suggestDesign: (data: ProjectData, budget: number, style: string) =>
    request<DesignSuggestion>("/api/designs/suggest", { method: "POST", body: JSON.stringify({ data, budget, style }) }),
  report: (name: string, data: ProjectData, designId: string, renders: Record<string, string>) =>
    request<Blob>("/api/report", {
      method: "POST",
      body: JSON.stringify({ name, data, design_id: designId, renders }),
    }),
};
