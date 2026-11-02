"use client";

import { useEffect, useRef, useState } from "react";

import { api, ApiError, imageUrl } from "./api";
import type { Catalog, Estimate, ProjectData } from "./types";

let catalogPromise: Promise<Catalog> | null = null;

/** The material catalogue (fetched once per page load). */
export function useCatalog() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    catalogPromise ??= api.catalog();
    catalogPromise.then(setCatalog).catch((e) => {
      catalogPromise = null;
      setError(e instanceof ApiError ? e.message : "Could not load materials.");
    });
  }, []);
  return { catalog, error };
}

/** Live estimate from the backend, debounced and cancelling stale requests. */
export function useEstimate(data: ProjectData, designId: string | null, delayMs = 350) {
  // The last response, remembering which inputs it was calculated for.
  const [result, setResult] = useState<{ estimate: Estimate | null; error: string | null; for: [ProjectData, string | null] | null }>({
    estimate: null,
    error: null,
    for: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api
        .estimate(data, designId, controller.signal)
        .then((estimate) => setResult({ estimate, error: null, for: [data, designId] }))
        .catch((e) => {
          if (controller.signal.aborted) return;
          setResult((r) => ({ ...r, error: e instanceof ApiError ? e.message : "Estimate failed.", for: [data, designId] }));
        });
    }, delayMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [data, designId, delayMs]);

  const loading = result.for?.[0] !== data || result.for?.[1] !== designId;
  return { estimate: result.estimate, loading, error: result.error };
}

/** A decoded, CORS-clean photo element for canvas rendering. */
export function usePhoto(imageId: string | undefined) {
  const [photo, setPhoto] = useState<HTMLImageElement | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!imageId) return;
    let cancelled = false;
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => !cancelled && setPhoto(image);
    image.onerror = () => !cancelled && setError(true);
    image.src = imageUrl(imageId);
    return () => {
      cancelled = true;
    };
  }, [imageId]);
  return { photo: photo && photo.src === imageUrl(imageId ?? "") ? photo : null, error };
}

/** Reports whether the (free, sleep-on-idle) backend is responding, for a friendly wake-up notice. */
export function useServerWake() {
  const [state, setState] = useState<"checking" | "slow" | "ok" | "down">("checking");
  const done = useRef(false);
  useEffect(() => {
    const slowTimer = setTimeout(() => !done.current && setState("slow"), 2500);
    api
      .health()
      .then(() => setState("ok"))
      .catch(() => setState("down"))
      .finally(() => {
        done.current = true;
        clearTimeout(slowTimer);
      });
    return () => clearTimeout(slowTimer);
  }, []);
  return state;
}

/** Estimates for every design in the project, for side-by-side comparison. */
export function useDesignComparison(data: ProjectData, delayMs = 600) {
  const [estimates, setEstimates] = useState<Estimate[] | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      Promise.all(data.designs.map((d) => api.estimate(data, d.id, controller.signal)))
        .then(setEstimates)
        .catch(() => undefined);
    }, delayMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [data, delayMs]);
  return estimates;
}
