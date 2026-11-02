"use client";

import { CheckCircle2, Download, FileDown, ImageDown, Link2 } from "lucide-react";
import { useEffect, useState } from "react";

import { toast } from "@/components/Toaster";
import { Button, Field, inputClass, Panel, Spinner } from "@/components/ui";
import { useWorkspace } from "@/components/workspace/context";
import { api, ApiError, imageUrl } from "@/lib/api";
import { formatINRShort } from "@/lib/format";
import { useEstimate } from "@/lib/hooks";
import { activeDesign } from "@/lib/project";
import { renderToDataUrl } from "@/lib/render";

const CONTENTS = [
  "Original and redesigned photo for every view",
  "Material and colour chosen for each surface",
  "Net areas with deductions, and quantities to buy (packs, bags, boxes, sheets)",
  "Material, labour, contingency and GST breakdown",
  "How the estimate was made, assumptions and exclusions",
];

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

const safeName = (name: string) => name.replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-|-$/g, "") || "renovation";

export function ReportStep() {
  const { store, catalog } = useWorkspace();
  const { data, name } = store;
  const [designId, setDesignId] = useState(activeDesign(data).id);
  const design = data.designs.find((d) => d.id === designId) ?? activeDesign(data);
  const { estimate } = useEstimate(data, design.id);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"pdf" | "image" | null>(null);

  // Small rendered previews of every photo for the chosen design.
  useEffect(() => {
    if (!catalog) return;
    let cancelled = false;
    Promise.all(
      data.views.map(async (v) => [v.id, await renderToDataUrl(v, design, catalog, imageUrl(v.image_id), 700)] as const),
    )
      .then((entries) => !cancelled && setPreviews(Object.fromEntries(entries)))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [data.views, design, catalog]);

  async function downloadPdf() {
    if (!catalog) return;
    setBusy("pdf");
    try {
      const renders: Record<string, string> = {};
      for (const v of data.views) renders[v.id] = await renderToDataUrl(v, design, catalog, imageUrl(v.image_id));
      const pdf = await api.report(name, data, design.id, renders);
      download(pdf, `${safeName(name)}-estimate.pdf`);
      toast("Report downloaded.", "success");
    } catch (error) {
      toast(error instanceof ApiError ? error.message : "Could not create the report.", "error");
    } finally {
      setBusy(null);
    }
  }

  async function downloadImages() {
    if (!catalog) return;
    setBusy("image");
    try {
      for (const v of data.views) {
        const url = await renderToDataUrl(v, design, catalog, imageUrl(v.image_id));
        download(await (await fetch(url)).blob(), `${safeName(name)}-${safeName(v.name)}-${safeName(design.name)}.jpg`);
      }
    } catch {
      toast("Could not create the image. Check your connection and try again.", "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="scroll-thin h-full overflow-y-auto">
      <div className="mx-auto grid max-w-6xl gap-4 p-3 sm:p-5 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-extrabold tracking-tight">Report for contractors</h2>
            <p className="text-sm text-muted">A PDF you can share or print to discuss the work, compare quotes and agree on materials.</p>
          </div>
          {data.views.map((v) => (
            <Panel key={v.id} title={v.name}>
              <div className="grid gap-3 sm:grid-cols-2">
                <figure>
                  {/* eslint-disable-next-line @next/next/no-img-element -- photo served by the API */}
                  <img src={imageUrl(v.image_id)} alt="Existing" className="aspect-[4/3] w-full rounded-lg object-cover" />
                  <figcaption className="mt-1 text-xs text-muted">Existing</figcaption>
                </figure>
                <figure>
                  {previews[v.id] ? (
                    // eslint-disable-next-line @next/next/no-img-element -- generated data URL
                    <img src={previews[v.id]} alt="Proposed" className="aspect-[4/3] w-full rounded-lg object-cover" />
                  ) : (
                    <div className="grid aspect-[4/3] place-items-center rounded-lg bg-canvas">
                      <Spinner />
                    </div>
                  )}
                  <figcaption className="mt-1 text-xs text-muted">Proposed: {design.name}</figcaption>
                </figure>
              </div>
            </Panel>
          ))}
        </div>

        <div className="space-y-4">
          <Panel title="Download">
            <div className="space-y-3">
              <Field label="Design to include">
                <select className={inputClass} value={design.id} onChange={(e) => setDesignId(e.target.value)}>
                  {data.designs.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </Field>
              {estimate && (
                <div className="rounded-xl bg-tint p-3">
                  <p className="text-xs font-semibold text-muted">Estimated total</p>
                  <p className="text-2xl font-extrabold text-accent">{formatINRShort(estimate.grand_total)}</p>
                  <p className="text-xs text-muted">
                    Likely range {formatINRShort(estimate.low_total)} – {formatINRShort(estimate.high_total)} · {estimate.lines.length} surfaces ·{" "}
                    {estimate.city}
                  </p>
                </div>
              )}
              <Button variant="primary" className="w-full" loading={busy === "pdf"} icon={<FileDown className="size-4" />} onClick={downloadPdf} disabled={!catalog}>
                Download PDF report
              </Button>
              <Button className="w-full" loading={busy === "image"} icon={<ImageDown className="size-4" />} onClick={downloadImages} disabled={!catalog}>
                Download redesigned photo{data.views.length > 1 ? "s" : ""}
              </Button>
              <Button
                variant="ghost"
                className="w-full"
                icon={<Link2 className="size-4" />}
                onClick={() => navigator.clipboard.writeText(window.location.href).then(() => toast("Link copied (read-only for others).", "success"))}
              >
                Copy share link
              </Button>
            </div>
          </Panel>
          <Panel title="What's in the report">
            <ul className="space-y-2 text-sm">
              {CONTENTS.map((c) => (
                <li key={c} className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-accent" />
                  {c}
                </li>
              ))}
            </ul>
            <p className="mt-3 flex items-start gap-1.5 text-xs text-muted">
              <Download className="mt-px size-3.5 shrink-0" /> The PDF is generated by the server from the same estimate engine you see here.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
