"""Scene understanding with Gemini: is this a usable house photo, and where are its parts?

Gemini returns *boxes* (which it localises reliably) plus semantic labels. Precise
outlines come afterwards from SAM (see segmenter.py). Gemini's own polygon and
mask outputs were evaluated and found too coarse for facade outlines.
"""

from __future__ import annotations

import logging
import time
from typing import Literal, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError

from app.schemas import ComponentType, CueKind, PlaneKind

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 503, 504}
T = TypeVar("T", bound=BaseModel)


class GeminiComponent(BaseModel):
    type: ComponentType
    label: str = Field(description="Short human-readable name, e.g. 'First-floor front wall'")
    box_2d: list[int] = Field(description="[ymin, xmin, ymax, xmax] normalised to 0-1000")
    plane: PlaneKind = "house_front"


class GeminiCue(BaseModel):
    """An object of known or estimable real height, used to set the photo's scale."""

    kind: CueKind
    label: str
    box_2d: list[int]
    plane: PlaneKind = "house_front"
    real_height_ft: float | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)


class GeminiScene(BaseModel):
    is_residential_exterior: bool
    view_type: Literal["front", "angled", "side", "close_up", "aerial", "not_a_building"]
    storeys: int
    usable_for_renovation: bool
    issues: list[str]
    guidance: list[str]
    components: list[GeminiComponent]
    scale_cues: list[GeminiCue] = []


PROMPT = """You assist an exterior-renovation planner for Indian residential buildings.
Analyse this photo and answer in the requested JSON format.

1. is_residential_exterior: does it show the OUTSIDE of a residential building (house, bungalow,
   villa, row house, low-rise apartment)?
2. view_type: "front" (one facade faces the camera), "angled" (two facades visible), "side",
   "close_up" (only part of the building), "aerial", or "not_a_building".
3. storeys: number of floors above ground that are visible (0 if not a building).
4. usable_for_renovation: false if the facade is mostly hidden (trees, vehicles, scaffolding),
   cut off, at night, or not a residential exterior.
5. issues: short list of problems with the photo for renovation planning (empty if none).
6. guidance: 1-3 short, friendly tips for a better photo (empty if the photo is good).
7. components: every visible exterior component of the MAIN building and its compound:
   - wall: each distinct wall plane separately (ground-floor wall, first-floor wall, side wall,
     compound/boundary wall, feature wall). Do not merge walls that face different directions.
   - window, door: each one separately (these are deducted from wall areas).
   - balcony: balcony slab edge and its solid front/side faces.
   - railing: glass or metal railings, including those on balconies and terraces.
   - pillar: columns and gate pillars.
   - parapet: low wall along the roof or terrace edge.
   - gate: main and side gates.
   - roof_edge: roof slab edges, sunshades (chajja), fascia bands and projections.
   Give each a short descriptive label and a tight box_2d as [ymin, xmin, ymax, xmax] on a 0-1000
   scale. Ignore neighbouring buildings, sky, ground, vehicles and plants. At most 40 components.
   For each component also give its plane (how far it is from the camera):
   "house_front" (the facade facing the camera), "house_side" (a facade at an angle / the side),
   "boundary" (compound wall, gate and gate pillars, usually nearer the camera) or "other".
8. scale_cues: up to 12 objects whose real HEIGHT can be judged, used to measure the photo:
   fully visible doors (standard Indian door 7 ft), cars, people, motorbikes, balcony railings
   (usually 3-3.5 ft), roof parapets (~3.3 ft), one full storey (floor to floor, ~10 ft) or a gate.
   For each give kind, a label, a TIGHT box_2d around its full visible height, its plane, your best
   estimate of its real height in feet (e.g. a hatchback ~5 ft, an SUV ~5.8 ft), and confidence 0-1.
   Lower the confidence if the object is partly hidden (e.g. a door behind a gate or railing).
"""


class GeminiUnavailable(RuntimeError):
    """No configured Gemini model could analyse the image."""


class SceneAnalyzer:
    def __init__(self, api_key: str, models: list[str], timeout_s: float) -> None:
        self.models = models
        self._client = (
            genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
            if api_key
            else None
        )

    @property
    def available(self) -> bool:
        return self._client is not None

    def analyze(self, jpeg: bytes) -> tuple[GeminiScene, str]:
        """Return the parsed scene and the name of the model that produced it."""
        return self.generate(GeminiScene, [types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"), PROMPT], temperature=0.2)

    def generate(self, schema: type[T], contents: list, temperature: float = 0.2) -> tuple[T, str]:
        """Structured output from the first model that answers, with one retry on overload."""
        if self._client is None:
            raise GeminiUnavailable("GEMINI_API_KEY is not configured.")

        last_error: Exception | None = None
        for model in self.models:
            for attempt in range(2):
                try:
                    return self._call(model, schema, contents, temperature), model
                except errors.APIError as exc:
                    last_error = exc
                    log.warning("Gemini %s failed (attempt %d): %s %s", model, attempt + 1, exc.code, exc.message)
                    if exc.code in RETRYABLE_STATUS and attempt == 0:
                        time.sleep(2)
                        continue
                    break  # non-retryable, or retried once already: try the next model
                except (ValidationError, ValueError) as exc:
                    last_error = exc
                    log.warning("Gemini %s returned unparseable output: %s", model, exc)
                    break
        raise GeminiUnavailable(str(last_error) if last_error else "No Gemini models configured.")

    def _call(self, model: str, schema: type[T], contents: list, temperature: float) -> T:
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )
        if "2.5" in model:
            # Google recommends disabling thinking for 2.5 models on detection tasks.
            config.thinking_config = types.ThinkingConfig(thinking_budget=0)

        response = self._client.models.generate_content(model=model, contents=contents, config=config)  # type: ignore[union-attr]
        if isinstance(response.parsed, schema):
            return response.parsed
        return schema.model_validate_json(response.text or "")


def box_to_normalised(box_2d: list[int]) -> tuple[float, float, float, float] | None:
    """Gemini [ymin, xmin, ymax, xmax] (0-1000) -> normalised (x0, y0, x1, y1), or None if degenerate."""
    if len(box_2d) != 4:
        return None
    y0, x0, y1, x1 = (min(max(v, 0), 1000) / 1000 for v in box_2d)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if x1 - x0 < 0.004 or y1 - y0 < 0.004:
        return None
    return x0, y0, x1, y1
