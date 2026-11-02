"use client";

import { createContext, useContext } from "react";

import type { ProjectStore } from "@/lib/useProjectStore";
import type { Catalog, View } from "@/lib/types";

export type Step = "photos" | "surfaces" | "scale" | "design" | "estimate" | "report";

export interface WorkspaceContextValue {
  store: ProjectStore;
  catalog: Catalog | null;
  view: View | undefined;
  setViewId: (id: string) => void;
  selectedRegionId: string | null;
  selectRegion: (id: string | null) => void;
  goTo: (step: Step) => void;
  analyzing: Record<string, boolean>;
  analyzeView: (viewId: string) => Promise<void>;
}

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspace(): WorkspaceContextValue {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace must be used inside <Workspace>");
  return value;
}
