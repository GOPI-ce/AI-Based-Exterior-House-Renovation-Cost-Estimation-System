"use client";

import { Check, CloudAlert, Copy, Link2, Loader2, Lock, Redo2, Undo2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Logo } from "@/components/Logo";
import { toast } from "@/components/Toaster";
import { Button, IconButton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

import { useWorkspace } from "./context";

export function TopBar() {
  const { store } = useWorkspace();
  const router = useRouter();
  const [copying, setCopying] = useState(false);
  const [navigating, startNavigation] = useTransition(); // true only while the page change is in progress
  const readOnly = store.status === "readonly";

  async function makeCopy() {
    setCopying(true);
    try {
      const copy = await api.copyProject(store.project.id);
      await api.saveProject(copy.id, store.project.is_demo ? "My copy of the demo" : store.name, store.data);
      toast("Your own editable copy is ready.", "success");
      startNavigation(() => router.push(`/p/${copy.id}`));
    } catch (error) {
      toast(error instanceof ApiError ? error.message : "Could not copy the project.", "error");
    } finally {
      setCopying(false);
    }
  }

  function share() {
    void navigator.clipboard
      .writeText(window.location.href)
      .then(() => toast("Link copied. Anyone with it can view this project (read-only).", "success"))
      .catch(() => toast(window.location.href, "info"));
  }

  return (
    <>
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-3 sm:px-4">
        <Logo compact />
        <input
          value={store.name}
          onChange={(e) => store.rename(e.target.value)}
          disabled={readOnly}
          maxLength={120}
          aria-label="Project name"
          className="min-w-0 flex-1 truncate rounded-md bg-transparent px-1.5 py-1 text-[15px] font-bold outline-none hover:bg-tint focus:bg-tint disabled:hover:bg-transparent sm:max-w-sm"
        />
        <SaveStatus />
        <div className="ml-auto flex items-center gap-1">
          <IconButton label="Undo (Ctrl+Z)" onClick={store.undo} disabled={!store.canUndo}>
            <Undo2 className="size-4" />
          </IconButton>
          <IconButton label="Redo (Ctrl+Y)" onClick={store.redo} disabled={!store.canRedo}>
            <Redo2 className="size-4" />
          </IconButton>
          <span className="hidden sm:block">
            <Button size="sm" variant="ghost" icon={<Link2 className="size-4" />} onClick={share}>
              Share
            </Button>
          </span>
          {readOnly && (
            <Button size="sm" variant="primary" icon={<Copy className="size-4" />} loading={copying || navigating} onClick={makeCopy}>
              Make my copy
            </Button>
          )}
        </div>
      </header>
      {readOnly && (
        <div className="flex items-center gap-2 border-b border-info/15 bg-info-soft px-4 py-2 text-xs text-info">
          <Lock className="size-3.5 shrink-0" />
          {store.project.is_demo
            ? "This is the demo project: explore freely, but changes are not saved. Use “Make my copy” to keep your edits."
            : "You are viewing someone else's project. Changes are not saved unless you make your own copy."}
        </div>
      )}
    </>
  );
}

function SaveStatus() {
  const { store } = useWorkspace();
  const map = {
    saved: { icon: <Check className="size-3.5" />, text: "Saved", cls: "text-accent" },
    dirty: { icon: <Loader2 className="size-3.5" />, text: "Unsaved", cls: "text-muted" },
    saving: { icon: <Loader2 className="size-3.5 animate-spin" />, text: "Saving…", cls: "text-muted" },
    error: { icon: <CloudAlert className="size-3.5" />, text: "Save failed: retry", cls: "text-danger" },
    readonly: { icon: <Lock className="size-3.5" />, text: "Read-only", cls: "text-info" },
  } as const;
  const s = map[store.status];
  return (
    <button
      onClick={() => store.status === "error" && store.save()}
      title={store.saveError ?? undefined}
      className={`hidden items-center gap-1 text-xs font-semibold sm:flex ${s.cls}`}
    >
      {s.icon}
      {s.text}
    </button>
  );
}
