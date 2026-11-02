"""Pixel-precise masks with SAM 2.1 (Segment Anything), prompted by Gemini's boxes.

Runs on CPU. The model (~150 MB) is loaded once in a background thread at
startup so the first analysis request does not pay the loading cost.
"""

from __future__ import annotations

import logging
import threading
import time

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)
# Models are loaded one at a time: transformers' lazy imports are not thread-safe, and a concurrent
# `from transformers import ...` in another loader thread can fail with ImportError.
MODEL_LOAD_LOCK = threading.Lock()


class Segmenter:
    def __init__(self, model_id: str, threads: int, enabled: bool = True) -> None:
        self.model_id = model_id
        self.threads = threads
        self.status = "loading" if enabled else "disabled"
        self.error: str | None = None
        self._model = None
        self._processor = None
        self._ready = threading.Event()
        self._infer_lock = threading.Lock()  # one CPU inference at a time

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    @property
    def enabled(self) -> bool:
        return self.status != "disabled"

    def load_in_background(self) -> None:
        if self.status == "disabled":
            return
        threading.Thread(target=self._load, name="sam-loader", daemon=True).start()

    def _load(self) -> None:
        try:
            with MODEL_LOAD_LOCK:
                started = time.perf_counter()
                import torch  # imported lazily: heavy, and not needed for tests
                from transformers import Sam2Model, Sam2Processor

                torch.set_num_threads(self.threads)
                self._processor = Sam2Processor.from_pretrained(self.model_id)
                self._model = Sam2Model.from_pretrained(self.model_id).eval()
            self.status = "ready"
            log.info("SAM loaded in %.1fs", time.perf_counter() - started)
        except Exception as exc:  # the app must keep working without SAM
            self.status = "failed"
            self.error = str(exc)
            log.exception("SAM failed to load; falling back to box regions")
        finally:
            self._ready.set()

    def wait_until_loaded(self, timeout_s: float) -> bool:
        if self.status == "disabled":
            return False
        self._ready.wait(timeout_s)
        return self.ready

    def segment(self, image: Image.Image, boxes_px: list[list[float]]) -> tuple[list[np.ndarray], list[float]]:
        """One boolean mask (H x W) and one quality score per [x0, y0, x1, y1] box."""
        if not self.ready or not boxes_px:
            return [], []
        import torch

        with self._infer_lock, torch.inference_mode():
            inputs = self._processor(images=image, input_boxes=[boxes_px], return_tensors="pt")
            outputs = self._model(**inputs, multimask_output=False)
            masks = self._processor.post_process_masks(outputs.pred_masks, inputs["original_sizes"])[0]
        scores = outputs.iou_scores[0, :, 0].tolist()
        return [masks[i, 0].numpy().astype(bool) for i in range(len(boxes_px))], scores
