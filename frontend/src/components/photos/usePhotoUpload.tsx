"use client";

import { Camera, Lightbulb, TriangleAlert } from "lucide-react";
import { useCallback, useState } from "react";

import { toast } from "@/components/Toaster";
import { Button, Modal } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { ImageInfo, QualityReport } from "@/lib/types";

const MAX_MB = 12;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

/** Upload a photo with client-side checks; a photo the server rejects opens a guidance dialog. */
export function usePhotoUpload() {
  const [busy, setBusy] = useState(false);
  const [rejected, setRejected] = useState<QualityReport | null>(null);

  const upload = useCallback(async (file: File): Promise<ImageInfo | null> => {
    if (!ACCEPTED.includes(file.type)) {
      toast("Please choose a JPG, PNG or WebP photo. (iPhone HEIC photos: export or share them as JPG.)", "error");
      return null;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      toast(`The photo is larger than ${MAX_MB} MB. Please choose a smaller one.`, "error");
      return null;
    }
    setBusy(true);
    try {
      return await api.uploadImage(file);
    } catch (error) {
      if (error instanceof ApiError && error.quality) setRejected(error.quality);
      else toast(error instanceof ApiError ? error.message : "Upload failed.", "error");
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  const dialog = <RejectedPhotoDialog report={rejected} onClose={() => setRejected(null)} />;
  return { upload, busy, dialog };
}

function RejectedPhotoDialog({ report, onClose }: { report: QualityReport | null; onClose: () => void }) {
  return (
    <Modal open={report !== null} onClose={onClose} title="This photo can't be used">
      <div className="space-y-4">
        <ul className="space-y-2">
          {report?.issues.map((issue) => (
            <li key={issue.code} className="flex gap-2 text-sm">
              <TriangleAlert className={`mt-0.5 size-4 shrink-0 ${issue.severity === "error" ? "text-danger" : "text-warn"}`} />
              <span>{issue.message}</span>
            </li>
          ))}
        </ul>
        <div className="rounded-xl bg-tint p-4 text-sm">
          <p className="mb-2 flex items-center gap-1.5 font-semibold text-accent">
            <Lightbulb className="size-4" /> Tips for a good renovation photo
          </p>
          <ul className="list-disc space-y-1 pl-5 text-ink-soft">
            <li>Stand across the road and face the house, so the whole front fits in the frame.</li>
            <li>Shoot in daylight with the sun behind you, not behind the house.</li>
            <li>Hold the phone level (not tilted up) and tap the house to focus.</li>
            <li>Avoid parked cars or trees in front of the walls where possible.</li>
          </ul>
        </div>
        <div className="flex justify-end">
          <Button variant="primary" icon={<Camera className="size-4" />} onClick={onClose}>
            Choose another photo
          </Button>
        </div>
      </div>
    </Modal>
  );
}
