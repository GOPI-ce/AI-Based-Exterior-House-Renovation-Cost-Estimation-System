# FacadeAI: AI exterior renovation planner & cost estimator

Upload a photo of a house. FacadeAI identifies its walls, windows, balconies, pillars, parapets, gates and roof
edges; lets the owner try real materials and brand paint systems on **their own house**; measures every surface
at its own distance with a confidence-rated scale; can **design the whole house for a budget** with AI; and produces a bill of quantities, a cost range and a PDF report for contractors.

| | |
| --- | --- |
| **Live app** | **https://ai-based-exterior-house-renovation.vercel.app** |
| **API** | https://gopichand111333--facade-ai-api.us-east.modal.run/docs (serverless: the first request after a pause takes about a minute to wake) |
| **Technical docs** | [docs/TECHNICAL.md](docs/TECHNICAL.md): architecture, data model, API, AI pipeline, measurement & cost maths, reliability, security, testing |
| **Access** | No login. Open the demo house, or upload your own photo. Projects are saved per browser; share links are read-only. |
| **Stack** | Next.js 16 · React 19 · TypeScript · Tailwind · FastAPI · Gemini 3.5 Flash · SAM 2.1 · Depth Anything V2 · OpenCV · Shapely · ReportLab · Playwright · GitHub Actions |

---

## 1. Features

| Area | What FacadeAI does |
| --- | --- |
| **Photo upload & checks** | JPG/PNG/WebP up to 12 MB, EXIF-rotated and normalised. **OpenCV** rejects too-small, dark, washed-out, low-contrast and blurry photos with specific instructions; **Gemini** flags photos that aren't a house, are obstructed or too far away, with tips to retake. Several photos per project. |
| **Structure detection** | **Gemini** labels each component (wall, window, door, balcony, railing, pillar, parapet, gate, roof edge/sunshade) and its **depth plane** (house front, house side, compound); **SAM 2.1** turns each box into a pixel-precise mask; OpenCV simplifies masks into **editable polygons**. Users drag/add/remove corners, retype, reassign planes, draw missing parts, with undo/redo. |
| **Materials & design** | **30 products in 7 categories**: brand paint systems (Asian Paints Ace / Apex / Apex Ultima / Ultima Protek, Berger WeatherCoat Long Life, Nerolac Excel Total, Dulux Weathershield Max), textures, **named stones** (Jaisalmer, Dholpur, Kota, slate, ledge-stone, granite), GVT elevation tiles by size, brick slips, ACP (PVDF / fire-retardant), HPL, WPC louvers, fibre-cement, four railing systems, metal enamel. Each has a tier, rate range, warranty claim, life, upkeep, pros/cons, specs and **the surfaces it suits**. A **120-shade exterior palette** (plus metal, ACP, HPL, WPC palettes) with families and search. Several named designs per project. |
| **Visualisation** | The user's actual photo is re-rendered with the chosen materials, **preserving the structure exactly**: textures at real-world scale (per plane, horizontally and vertically), the photo's own lighting re-applied, glass showing the new wall behind it, SS posts, tile joints, panel joints. After / Before \| After slider / Before. |
| **Measurement** | **Multi-cue, plane-aware scale**: each depth plane's scale is the robust consensus of reference cues (doors, cars, people, railings, the building's storey height, user-measured lengths), outliers rejected, impossible cues switched off, separate vertical/horizontal scales for angled walls, and a **confidence score** shown to the user. **Distance-aware**: a monocular depth model gives every surface its own distance, so a wall set back behind the balcony or a compound wall near the camera is measured at its true scale. Openings and overlapping parts are deducted; hidden faces of pillars/gates can be included; site measurements override. |
| **Quantities** | Paint systems (primer, elastomeric base coat, top coats) rounded to **practical pack combinations**; texture compound in bags; cladding sqft + adhesive bags; **tiles and boxes**; ACP **sheets**; railings in running feet, all with wastage. |
| **AI budget designer** | Give a budget and a style brief: **Gemini** looks at the photo and every option's real installed cost and proposes a complete, colour-coordinated design with a reason per surface; the **estimator verifies** the all-in total (site items, contingency, GST); if it is over, Gemini revises with the numbers; if still over, a deterministic repair downgrades the finishes that save the most until it fits. The model only chooses; code checks every id, shade and rupee. |
| **Costing** | Material + labour per surface and category, **site & preparation items** (scaffolding, surface prep, waterproof base coat, removal of old finish, debris), contingency, GST, **city rate index**, all rates editable. A **most-likely total with a likely range**, design comparison with a **long-term cost** (repaints, resealing and upkeep over 15 years with inflation: cheap paint vs durable cladding), and a **BOQ export (CSV)** for contractors to price against. |
| **Reports** | Server-generated **PDF**: original vs redesigned photos, material schedule with shade names and planes, net areas and deductions, purchase quantities, site items, cost range, per-plane scale confidence, method, assumptions and exclusions. |
| **Platform** | Guided 6-step flow; responsive to phones; photos ≤1600 px; autosave (serialised, flushed on navigation) + undo; per-browser workspaces and read-only share links; stateless API with rate limiting and AI result caching; graceful degradation when an AI stage is unavailable; a per-photo **AI pipeline trace** (models, timings, fallbacks). |

## 2. Architecture

```mermaid
flowchart TB
  subgraph WEB["Browser · Next.js on Vercel"]
    direction LR
    UI["Guided workflow<br/>Photos → Surfaces → Scale → Design → Estimate → Report"]
    ED["Editors<br/>outlines, depth planes, scale lines, undo/redo"]
    RE["Renderer (Canvas)<br/>materials at real scale + photo lighting"]
  end

  subgraph API["FastAPI on Modal (Docker)"]
    direction LR
    subgraph PIPE["AI pipeline"]
      direction TB
      Q["Quality gate<br/>OpenCV"] --> AN["Analysis<br/>parts, planes, scale cues"]
      AN --> S["SAM 2.1<br/>pixel-precise outlines"]
      AN --> D["Depth Anything V2<br/>distance of every surface"]
    end
    subgraph COST["Measurement & cost"]
      direction TB
      SC["Scale engine<br/>depth-normalised consensus"] --> EST["Estimator<br/>quantities, costs, range, 15-year cost"]
      AID["AI budget designer<br/>propose → verify → revise / repair"] --> EST
      EST --> PDF["PDF report<br/>ReportLab"]
    end
  end

  subgraph EXT["Cloud services"]
    direction LR
    G["Gemini 3.5 Flash (2.5 fallback)<br/>parts, planes, cues · design proposals"]
    DB[("Neon Postgres<br/>projects, photos, AI + depth cache")]
  end

  UI -->|photo| Q
  AN -->|polygons, planes, depth grid| ED
  ED -->|edits| SC
  UI -->|budget + style| AID
  RE -->|redesigned images| PDF
  AN --> G
  AID --> G
  ED -->|autosave| DB
  AN -->|cache| DB
```

* **AI and money logic live on the server.** One estimator (unit-tested) serves the live UI, the BOQ and the PDF, so the numbers always match. The scale algorithm is mirrored in the browser only for live editor feedback.
* **Rendering runs in the browser**: instant, free per render, and it never distorts the building.
* **Every AI stage degrades gracefully**: model fallback on overload; boxes if SAM is unavailable; one scale per plane if the depth model is unavailable; manual drawing if Gemini is down; implausible scale cues are switched off rather than trusted.

## 3. User workflow

1. **Photos**: upload. Bad photos are rejected with reasons and tips; the AI's notes are shown.
2. **Surfaces**: AI-detected parts as coloured outlines. Fix type, outline, plane or name; draw anything missed; mark finishes to be removed.
3. **Scale**: one card per depth plane with its consensus scale, confidence badge, used/rejected cues and editable references (presets for door, gate, railing, storey, car, person; vertical / horizontal / both). Confirm when checked.
4. **Design**: click a surface, browse materials by category, tier, brand or search, pick a shade; the photo re-renders instantly. Keep several designs, or let the **AI budget designer** create one.
5. **Estimate**: likely total and range, warnings, per-surface lines with ranges, site items, measurement confidence, city, settings, editable rates, design comparison, **BOQ (CSV)**.
6. **Report**: PDF, redesigned photos, share link.

## 4. The AI pipeline

```
photo ─► OpenCV quality gate ─► Gemini ──────────────────────► SAM 2.1 (one batch) ─────────► editable polygons
         size, exposure,        usable house? parts + boxes,    parts → masks                   + depth planes
         contrast, blur         depth planes, scale cues        cues  → median column heights   + scale consensus
                                        └─────────────────────► Depth Anything V2 ──────────► distance of every
                                                                metric, outdoor, Small          surface and cue
```

Choices were made by testing on real Indian house photos:

| Tried | Result | Decision |
| --- | --- | --- |
| Gemini 2.5 Flash boxes | Rough, overlapping boxes; mislabelled cues | fallback only |
| Gemini 3.5 Flash polygons | Too coarse | rejected |
| Gemini native masks | Internal mask tokens / time-outs | rejected |
| **Gemini 3.5 Flash boxes + SAM 2.1** | Tight boxes, pixel-accurate outlines | **chosen** |
| A single "door = 7 ft" scale | Wrong whenever the door is partly hidden | replaced by multi-cue consensus |
| Cue height = bounding-box height | Inflated by perspective (slanted railings) | replaced by SAM-mask median column height |
| One scale per plane | A wall 22 m away measured with a railing's scale at 16 m loses half its area | **depth-normalised scale** (Depth Anything V2) |
| Wall angle from the depth map (RANSAC plane fit) | Angles off by up to ±20° on real photos: would distort more than it corrects | not used; angled walls use horizontal references |
| Depth Anything V2 Base/Large | Better, but CC-BY-NC | Small (Apache-2.0) |

## 5. Scale & measurement (how areas are derived)

1. **Cues.** Every line of known or estimated real length is a cue: AI-detected doors (7 ft), cars (~5 ft), people (~5.4 ft), railings (3–3.5 ft), parapets, gates; the building's storeys (~10 ft each + plinth/parapet); and any length the user draws and types. Each cue's pixel length is measured on its SAM mask (median column height), not its bounding box.
2. **Sanity filters.** Cue boxes with impossible shapes (a "door" wider than tall, a sliver "storey") are discarded. On the house front, a cue that implies an impossible building height (a 2-storey house must be ~17–32 ft) is switched off and labelled, and the user can re-enable it.
3. **Consensus per plane.** `feet per pixel` = weighted median of the cues on that plane (auto cues weighted by type × AI confidence; user-measured cues weight 1); with ≥3 cues, any >35% from the median is rejected. Vertical and horizontal cues give separate `ftPerPx_y` and `ftPerPx_x`, which corrects foreshortening on angled walls. A plane without cues borrows another plane's scale at half confidence.
4. **Distance (depth model).** Feet-per-pixel grows linearly with distance from the camera. Depth Anything V2 (metric, outdoor) estimates every pixel's distance; each cue is divided by its own distance before the consensus, so a door at 12 m and a railing at 16 m agree, and every surface is then measured at its own distance (median depth of its *visible* cells, so a pillar in front doesn't pull a wall forward). The model's absolute error is common to the whole photo and is calibrated away by the cues; only relative distances matter. A plane without cues borrows a distance-corrected scale (80% confidence instead of 50%); with no cue at all, the camera's focal length (EXIF, else a typical phone lens) gives a rough last-resort scale. Because all planes share one camera, their distance-corrected scales must agree: a disagreement over 30% is flagged as a probably wrong reference length. The browser runs the same sampling on the same integer-centimetre grid, so live sizes match the estimate exactly.
5. **Confidence & error.** Confidence grows with the number of agreeing cues and with user-measured or confirmed references, and falls with disagreement. It maps to an expected length error (shown per plane), which drives the cost range.
6. **Area.** `polygon pixel area × ftPerPx_x × ftPerPx_y` (at the surface's distance). Surfaces are stacked in layers (wall < roof edge < parapet < balcony < pillar < railing < gate < window/door); **net area = polygon minus everything layered above it**, so openings and things in front are never counted twice. The renderer uses the same layering. Railing length uses the long side of the minimum bounding rectangle, converted with both scales. Site measurements entered by the user override all of this.

## 6. Quantities, cost and range

| Material type | Purchase quantity | Labour on |
| --- | --- | --- |
| Paint system | top coat `net × coats ÷ coverage × (1+waste)` L, primer `net ÷ coverage × (1+waste)` L, optional elastomeric base coat; each rounded to a practical pack mix (minimises litres + packs) | net sqft |
| Texture | `net × kg/sqft × (1+waste)` → whole 25 kg bags | net sqft |
| Stone / brick cladding | `net × (1+waste)` sqft + `⌈net ÷ sqft per bag⌉` adhesive bags | net sqft |
| GVT tiles | `⌈net × (1+waste) ÷ tile area⌉` tiles → whole boxes + adhesive bags | net sqft |
| ACP | `⌈net × (1+waste) ÷ 32⌉` 4×8 ft sheets | net sqft |
| HPL / WPC / fibre cement / microcement | `net × (1+waste)` sqft | net sqft |
| Railings (installed systems) | `length × (1+waste)` running ft | running ft |

* **Site & preparation:** scaffolding on all house-plane surfaces in scope, surface prep on painted/textured area, optional waterproof base coat, removal on surfaces marked for it, debris as % of works.
* **City index:** labour and material rates are scaled for 12 cities (Ahmedabad = 1.00); user rate overrides are used as entered.
* **Totals:** `subtotal = material + labour + site`; `total = (subtotal + contingency%) × (1 + GST%)`.
* **Range:** each line's spread combines its material/labour **market rate range** and its plane's **measurement error** as root-sum-square (independent sources). The result is a concept-stage range comparable to an **AACE International Class 4–5 estimate**: around −25 % / +35 % for the demo, narrower as references are measured and confirmed.

**Worked example (demo, first-floor feature wall, Jaisalmer sandstone):** the wall is set back 18.5 m from the camera
(the railing that sets the scale is at 15.5 m), so it gets (18.5 ÷ 15.5)² ≈ 1.42× the area a flat scale would give.
Gross 462.1 sqft − 45.7 sqft window = **416.4 sqft net** → ×1.10 waste = **458.1 sqft** at ₹140 + ⌈416.4 ÷ 30⌉ = **14 bags**
adhesive at ₹480 = **₹70,852** material; 416.4 × ₹75 = **₹31,233** labour; likely range ₹77.5k–130.5k for the line.

**Rates** ([`catalog.json`](backend/app/data/catalog.json), generated by `backend/scripts/build_catalog.py`) are indicative 2026 figures excluding GST: dealer prices derived from published MRPs and market listings, and Ahmedabad labour rates, each with a low–high range. Brand names identify product classes for planning; confirm prices, coverage and warranty terms with dealers and data sheets.

## 7. How the redesign is rendered

Per surface, in layer order: anti-aliased polygon mask → material generated at real-world scale using the plane's
horizontal and vertical feet-per-pixel at the surface's own distance → the photo's lighting re-applied → alpha blend. Lighting is the local
**brightest envelope** of the photo (white-patch Retinex on a coarse grid, mask-aware), applied through a gamma curve.
The old surface's colours don't bleed through, while real shadows stay. Gates and railings keep fine shading. Glass
shows the newly finished wall behind it. Windows, doors and untouched surfaces keep their original pixels.

## 8. Limitations (honest)

* **Single-photo measurement is approximate.** The scale is cross-checked, distance-corrected and confidence-rated, but it can still be off if all cues are wrong or the depth model misjudges relative distances (glass, reflections, very distant buildings). Wall angles are not recovered from depth (tested, too noisy), so angled walls need a horizontal reference. The UI shows the confidence, and a measured length on each plane (door, gate, wall width) brings the error to a few percent.
* **AI outlines need review.** SAM can merge neighbouring parts or produce ragged edges around clutter. The demo shows the AI result with two outlines corrected and one porch column added by hand.
* **The render is a planning visual**, not a photoreal render. No new geometry, no reflections, and textures are not perspective-warped within a plane.
* **Rates are indicative** and differ by dealer, quantity and season. Structural repairs, major damp treatment, electrical/plumbing work and permits are not included. Estimates are advisory, not quotations.
* **No accounts.** Projects are scoped to an anonymous per-browser workspace; share links are read-only. Data is stored in Postgres (Neon) in production, SQLite locally.
* **Free-tier hosting.** The API sleeps when idle (about a minute to wake), and Gemini's free tier is sometimes overloaded (the app retries and falls back to 2.5 Flash).

## 9. Related work

How this compares with published approaches to estimating facade work from images:

* **Facade parsing for cost estimation** (e.g. the *Vitruvio* line of research, 2024) segments facade elements and
  derives quantities, but assumes a rectified, front-parallel facade. FacadeAI keeps the user's own perspective
  photo, measures each surface at its own distance with a depth model, and lets the user correct outlines and scale.
* **Patented exterior-estimate systems** (e.g. US 12,602,711) describe photo-to-estimate pipelines for exterior work.
  FacadeAI's specific contributions are the multi-cue, depth-normalised scale with outlier rejection and confidence,
  the layer model that deducts what is in front, and estimator-verified AI design.
* **Material selection by multi-criteria decision models** (e.g. ANN + TOPSIS studies, *Algorithms* 2025) rank
  materials from criteria weights. FacadeAI instead lets a vision-language model choose for the actual house and brief,
  with an estimator in the loop that enforces the budget, and reports the long-term cost so the trade-off is visible.
* **Commercial measurement apps** reconstruct a 3D model from several guided photos or use aerial imagery: more
  accurate, but they need special capture or paid imagery. FacadeAI works from one ordinary photo and is explicit about
  its uncertainty (confidence per plane, a likely range, and site measurements that override the photo).

## 10. Run locally

Requirements: Node 20.9+, Python 3.12+, a free Gemini API key (Google AI Studio).

```bash
# API (http://localhost:8000)
cd backend
python -m venv .venv && .venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
cp .env.example .env                                     # add GEMINI_API_KEY
uvicorn app.main:app --port 8000

# Web app (http://localhost:3000)
cd frontend
npm install
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
npm run dev
```

## 11. Tests & CI

```bash
cd backend && pytest -q                               # 78 tests: scale consensus, depth-normalised scale, AI designer loop, lifetime cost, plausibility, estimator, geometry, quality, API, migration
cd frontend && npm run typecheck && npm run lint
cd frontend && npx playwright install chromium && npm run test:e2e   # 13 browser tests (app must be running)
E2E_AI=1 npm run test:e2e                             # also runs the live AI tests: upload + AI designer (uses Gemini quota)
```

[GitHub Actions](.github/workflows/ci.yml) runs the backend tests, the frontend type check, lint and production
build, then starts the API and app and runs the Playwright suite (AI disabled, no quota used).

## 12. Project structure

```
backend/
  app/main.py, config.py, db.py, schemas.py, catalog.py
  app/api/                images (upload/analyse), projects, estimate + report
  app/services/           quality · gemini · segmenter (SAM) · depth · analysis · designer · scale · geometry · estimator · report
  app/data/catalog.json   products, palettes, site items, cities (from scripts/build_catalog.py)
  app/demo/               demo photo, its depth map + project
  scripts/                build_catalog.py, build_demo.py, build_demo_depth.py, demo_designs.py
  tests/                  pytest suite
  Dockerfile              API image (SAM + depth weights baked in)
  modal_app.py            serverless deployment of that image on Modal
frontend/
  src/app/                routes: / and /p/[id]
  src/components/steps/   the six workflow steps
  src/components/design/  material browser, shade picker, design tabs
  src/lib/                API client, types, geometry + scale, renderer, store, BOQ export
  e2e/                    Playwright tests + fixtures
.github/workflows/ci.yml  CI pipeline
docs/                     technical documentation, deployment guide
```

## 13. Credits

* Demo and test photos: Timothy A. Gonsalves, [*Modern House, Eraviputhenthurai*](https://commons.wikimedia.org/wiki/File:Modern_House_Eraviputhenthurai_Mar24_A7C_10232.jpg), Wikimedia Commons, **CC BY-SA 4.0**. Redesigned previews are modified versions.
* Material textures: [ambientCG](https://ambientcg.com) (CC0). PDF font: Noto Sans (SIL OFL).
* Models: Google Gemini (API), Meta SAM 2.1 (`facebook/sam2.1-hiera-tiny`, Apache 2.0), Depth Anything V2 Metric Outdoor Small (`depth-anything/Depth-Anything-V2-Metric-Outdoor-Small-hf`, Apache 2.0).
* Brand and product names belong to their owners and are used only to identify product classes for planning.
