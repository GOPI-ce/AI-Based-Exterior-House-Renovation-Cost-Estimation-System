"use client";

import { Segmented } from "@/components/ui";

import { useWorkspace } from "./context";

/** Tabs to switch between photos; renders nothing for single-photo projects. */
export function ViewSwitcher() {
  const { store, view, setViewId } = useWorkspace();
  if (store.data.views.length < 2 || !view) return null;
  return (
    <Segmented
      size="sm"
      value={view.id}
      onChange={setViewId}
      options={store.data.views.map((v) => ({ value: v.id, label: v.name }))}
    />
  );
}
