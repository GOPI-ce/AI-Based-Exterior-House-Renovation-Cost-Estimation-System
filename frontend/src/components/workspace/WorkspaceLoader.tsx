"use client";

import { ArrowLeft, CloudOff } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useServerWake } from "@/lib/hooks";
import type { Project } from "@/lib/types";

import { Workspace } from "./Workspace";
import { WorkspaceSkeleton } from "./WorkspaceSkeleton";

export function WorkspaceLoader({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const server = useServerWake();

  useEffect(() => {
    let cancelled = false;
    api
      .getProject(projectId)
      .then((p) => !cancelled && setProject(p))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Could not load the project."));
    return () => {
      cancelled = true;
    };
  }, [projectId, attempt]);

  if (project) return <Workspace initial={project} />;

  if (error)
    return (
      <div className="grid min-h-screen place-items-center p-6">
        <div className="max-w-sm text-center">
          <CloudOff className="mx-auto mb-3 size-10 text-faint" />
          <h1 className="text-lg font-bold">Project unavailable</h1>
          <p className="mt-1 text-sm text-muted">{error}</p>
          <div className="mt-5 flex justify-center gap-2">
            <Link href="/">
              <Button icon={<ArrowLeft className="size-4" />}>Home</Button>
            </Link>
            <Button
              variant="primary"
              onClick={() => {
                setError(null);
                setAttempt((n) => n + 1);
              }}
            >
              Retry
            </Button>
          </div>
        </div>
      </div>
    );

  return (
    <WorkspaceSkeleton
      message={server === "slow" ? "Waking up the server (free hosting sleeps when idle)… this can take up to a minute." : "Loading project…"}
    />
  );
}
