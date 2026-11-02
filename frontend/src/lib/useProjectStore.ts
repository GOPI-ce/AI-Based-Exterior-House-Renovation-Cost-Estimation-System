"use client";

import { produce, type Draft } from "immer";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "./api";
import type { Project, ProjectData } from "./types";

export type SaveStatus = "saved" | "dirty" | "saving" | "error" | "readonly";

const HISTORY_LIMIT = 60;
const AUTOSAVE_MS = 1200;

interface History {
  past: ProjectData[];
  present: ProjectData;
  future: ProjectData[];
}

const pushPast = (h: History) => [...h.past.slice(-HISTORY_LIMIT + 1), h.present];

/**
 * Editing state for one project: immutable updates (immer), undo/redo and debounced autosave.
 *
 * `update(fn)` records an undo step. During a drag, call `checkpoint()` once on pointer-down
 * and then `update(fn, { record: false })` on every move, so one drag = one undo step.
 */
export function useProjectStore(initial: Project) {
  const [project, setProject] = useState(initial);
  const [history, setHistory] = useState<History>({ past: [], present: initial.data, future: [] });
  const [name, setName] = useState(initial.name);
  const [status, setStatus] = useState<SaveStatus>(initial.can_edit ? "saved" : "readonly");
  const [saveError, setSaveError] = useState<string | null>(null);
  const data = history.present;

  const markDirty = useCallback(() => setStatus((s) => (s === "readonly" ? s : "dirty")), []);

  const checkpoint = useCallback(() => {
    setHistory((h) => ({ past: pushPast(h), present: h.present, future: [] }));
  }, []);

  const update = useCallback(
    (recipe: (draft: Draft<ProjectData>) => void, options: { record?: boolean } = {}) => {
      const record = options.record !== false;
      setHistory((h) => {
        const present = produce(h.present, recipe);
        if (present === h.present) return h; // nothing changed
        return record ? { past: pushPast(h), present, future: [] } : { ...h, present };
      });
      markDirty();
    },
    [markDirty],
  );

  const undo = useCallback(() => {
    setHistory((h) =>
      h.past.length ? { past: h.past.slice(0, -1), present: h.past[h.past.length - 1], future: [...h.future, h.present] } : h,
    );
    markDirty();
  }, [markDirty]);

  const redo = useCallback(() => {
    setHistory((h) =>
      h.future.length ? { past: [...h.past, h.present], present: h.future[h.future.length - 1], future: h.future.slice(0, -1) } : h,
    );
    markDirty();
  }, [markDirty]);

  const rename = useCallback(
    (value: string) => {
      setName(value);
      markDirty();
    },
    [markDirty],
  );

  // Latest values for saving; refs are only written in effects, never during render.
  const latest = useRef({ data, name });
  const statusRef = useRef(status);
  useEffect(() => {
    latest.current = { data, name };
    statusRef.current = status;
  }, [data, name, status]);
  const inFlight = useRef<Promise<void> | null>(null);

  /** Save the latest state. Saves are serialised, so an older save can never land after a newer one. */
  const persist = useCallback(async () => {
    if (!project.can_edit) return;
    while (inFlight.current) await inFlight.current;
    const snapshot = latest.current;
    setStatus("saving");
    const run = (async () => {
      try {
        const saved = await api.saveProject(project.id, snapshot.name.trim() || "My house", snapshot.data);
        setProject((p) => ({ ...p, updated_at: saved.updated_at }));
        setStatus((s) => (s === "saving" ? "saved" : s)); // edits made meanwhile stay "dirty"
        setSaveError(null);
      } catch (error) {
        setStatus("error");
        setSaveError(error instanceof ApiError ? error.message : "Could not save.");
      }
    })();
    inFlight.current = run;
    await run;
    inFlight.current = null;
  }, [project.can_edit, project.id]);

  // Debounced autosave whenever there are unsaved edits.
  useEffect(() => {
    if (status !== "dirty") return;
    const timer = setTimeout(() => void persist(), AUTOSAVE_MS);
    return () => clearTimeout(timer);
  }, [status, data, name, persist]);

  // Leaving the workspace inside the app (e.g. the logo link) must not drop the last edits.
  useEffect(
    () => () => {
      if (statusRef.current === "dirty") void persist();
    },
    [persist],
  );

  // Warn before leaving the page with unsaved edits.
  useEffect(() => {
    if (status !== "dirty" && status !== "saving") return;
    const handler = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [status]);

  return {
    project,
    data,
    name,
    status,
    saveError,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
    update,
    checkpoint,
    undo,
    redo,
    rename,
    save: persist,
  };
}

export type ProjectStore = ReturnType<typeof useProjectStore>;
