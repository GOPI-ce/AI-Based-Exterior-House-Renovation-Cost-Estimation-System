"use client";

import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";

type Kind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  kind: Kind;
  message: string;
}

// A tiny global event channel, so any component can call toast() without a provider.
const listeners = new Set<(t: ToastItem) => void>();
let nextId = 1;

export function toast(message: string, kind: Kind = "info") {
  const item = { id: nextId++, kind, message };
  listeners.forEach((l) => l(item));
}

const ICONS = { success: CheckCircle2, error: TriangleAlert, info: Info };
const TONE = {
  success: "text-accent",
  error: "text-danger",
  info: "text-info",
};

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    const add = (t: ToastItem) => {
      setItems((list) => [...list.slice(-3), t]);
      setTimeout(() => setItems((list) => list.filter((x) => x.id !== t.id)), t.kind === "error" ? 7000 : 4000);
    };
    listeners.add(add);
    return () => {
      listeners.delete(add);
    };
  }, []);

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4" aria-live="polite">
      {items.map((t) => {
        const Icon = ICONS[t.kind];
        return (
          <div
            key={t.id}
            className="animate-rise pointer-events-auto flex max-w-md items-start gap-2.5 rounded-xl border border-line bg-surface px-4 py-3 text-sm shadow-lg shadow-black/5"
          >
            <Icon className={`mt-0.5 size-4 shrink-0 ${TONE[t.kind]}`} />
            <span className="text-ink-soft">{t.message}</span>
            <button
              className="ml-1 text-faint hover:text-ink"
              onClick={() => setItems((list) => list.filter((x) => x.id !== t.id))}
              aria-label="Dismiss"
            >
              <X className="size-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
