"use client";

import { ArrowRight, Calculator, FileText, ImageUp, Layers, Palette, ScanSearch, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { Logo } from "@/components/Logo";
import { usePhotoUpload } from "@/components/photos/usePhotoUpload";
import { toast } from "@/components/Toaster";
import { Button, Spinner } from "@/components/ui";
import { api, ApiError, imageUrl } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { newProjectData, newView } from "@/lib/project";
import type { ProjectSummary } from "@/lib/types";

const STEPS = [
  { icon: ImageUp, title: "Upload a photo", text: "Any clear daylight photo of your house exterior. Bad photos are caught with tips to retake." },
  { icon: ScanSearch, title: "AI maps your house", text: "Walls, windows, balconies, pillars, parapets, gates and roof edges are outlined. Correct anything." },
  { icon: Palette, title: "Try materials", text: "Paint, texture, stone, brick, tiles, ACP, WPC and railings, previewed on your own house." },
  { icon: Calculator, title: "Know the cost", text: "Areas, material quantities with wastage, labour and GST, with rates you can edit." },
];

export function HomeScreen() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const { upload, busy, dialog } = usePhotoUpload();
  const [creating, setCreating] = useState(false);
  // The page change runs in a transition: `navigating` is true only while it is in progress. (Next keeps
  // left pages alive for instant Back navigation, so a plain "loading" flag would still be on on return.)
  const [navigating, startNavigation] = useTransition();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  async function startFromFile(file: File | undefined) {
    if (!file) return;
    const image = await upload(file);
    if (!image) return;
    setCreating(true);
    try {
      const project = await api.createProject("My house", newProjectData(newView(image, "Front view")));
      startNavigation(() => router.push(`/p/${project.id}`));
    } catch (error) {
      toast(error instanceof ApiError ? error.message : "Could not create the project.", "error");
    } finally {
      setCreating(false);
    }
  }

  async function remove(project: ProjectSummary) {
    if (!confirm(`Delete "${project.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteProject(project.id);
      setProjects((list) => list?.filter((p) => p.id !== project.id) ?? null);
    } catch (error) {
      toast(error instanceof ApiError ? error.message : "Delete failed.", "error");
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <Link href="/p/demo" className="text-sm font-semibold text-accent hover:underline">
            Open demo house
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        <section className="grid items-center gap-10 py-12 md:grid-cols-[1.1fr_1fr] md:py-16">
          <div className="animate-rise">
            <p className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-bold text-accent">
              <Layers className="size-3.5" /> Pre-construction planning assistant
            </p>
            <h1 className="text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl">
              See your house renovated <span className="text-accent">before you build.</span>
            </h1>
            <p className="mt-4 max-w-lg text-base leading-relaxed text-ink-soft">
              Upload a photo of your home. FacadeAI maps every wall, pillar and balcony, lets you try real materials on
              your own house, and works out the quantities and cost, so you can talk to contractors with confidence.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Button variant="primary" className="h-12 px-5 text-base" loading={busy || creating || navigating} icon={<ImageUp className="size-5" />} onClick={() => fileInput.current?.click()}>
                {busy ? "Checking photo…" : creating ? "Creating project…" : navigating ? "Opening project…" : "Upload a house photo"}
              </Button>
              <Link href="/p/demo">
                <Button className="h-12 px-5 text-base">
                  Try the demo <ArrowRight className="size-4" />
                </Button>
              </Link>
            </div>
            <p className="mt-3 text-xs text-muted">JPG, PNG or WebP up to 12 MB. No sign-up; projects are saved to this browser&apos;s workspace.</p>
            <input
              ref={fileInput}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              onChange={(e) => {
                void startFromFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </div>

          <Link href="/p/demo" className="group relative block overflow-hidden rounded-3xl border border-line bg-surface shadow-xl shadow-ink/5">
            {/* eslint-disable-next-line @next/next/no-img-element -- photo served by the API */}
            <img src={imageUrl("demo-house")} alt="Demo house" className="aspect-[4/3] w-full object-cover transition duration-500 group-hover:scale-[1.02]" />
            <div className="absolute inset-x-3 bottom-3 flex items-center justify-between rounded-2xl bg-surface/95 px-4 py-3 shadow-lg backdrop-blur">
              <div>
                <p className="text-sm font-bold">Demo: two-storey house</p>
                <p className="text-xs text-muted">20 parts detected · 3 designs · full estimate</p>
              </div>
              <span className="grid size-9 place-items-center rounded-full bg-accent text-white">
                <ArrowRight className="size-4" />
              </span>
            </div>
          </Link>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <div key={title} className="rounded-2xl border border-line bg-surface p-5">
              <div className="mb-3 flex items-center gap-2">
                <span className="grid size-9 place-items-center rounded-xl bg-accent-soft text-accent">
                  <Icon className="size-5" />
                </span>
                <span className="text-xs font-bold text-faint">STEP {i + 1}</span>
              </div>
              <h3 className="font-bold">{title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted">{text}</p>
            </div>
          ))}
        </section>

        <section className="mt-12">
          <h2 className="mb-4 text-lg font-bold">Your projects</h2>
          {projects === null ? (
            <div className="flex items-center gap-2 text-sm text-muted">
              <Spinner /> Loading…
            </div>
          ) : projects.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-line-strong bg-surface p-8 text-center text-sm text-muted">
              No projects yet. Upload a photo of your house, or open the demo and make a copy.
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((p) => (
                <div key={p.id} className="group overflow-hidden rounded-2xl border border-line bg-surface transition hover:shadow-md">
                  <Link href={`/p/${p.id}`} className="block">
                    {p.cover_image_id ? (
                      // eslint-disable-next-line @next/next/no-img-element -- photo served by the API
                      <img src={imageUrl(p.cover_image_id)} alt="" className="aspect-[16/10] w-full object-cover" />
                    ) : (
                      <div className="grid aspect-[16/10] place-items-center bg-tint text-faint">
                        <FileText className="size-8" />
                      </div>
                    )}
                  </Link>
                  <div className="flex items-center justify-between gap-2 px-4 py-3">
                    <Link href={`/p/${p.id}`} className="min-w-0">
                      <p className="truncate font-semibold">{p.name}</p>
                      <p className="text-xs text-muted">
                        {p.view_count} photo{p.view_count === 1 ? "" : "s"} · edited {timeAgo(p.updated_at)}
                      </p>
                    </Link>
                    <button onClick={() => remove(p)} className="rounded-lg p-2 text-faint hover:bg-danger-soft hover:text-danger" aria-label={`Delete ${p.name}`}>
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-line bg-surface py-6 text-center text-xs text-muted">
        Estimates are advisory planning figures, not quotations. Demo photo: Timothy A. Gonsalves, Wikimedia Commons, CC BY-SA 4.0.
      </footer>
      {dialog}
    </div>
  );
}
