---
title: FacadeAI API
emoji: 🏠
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: AI exterior renovation planning and cost estimation API
---

# FacadeAI API

FastAPI backend for FacadeAI, an AI exterior renovation planner. See the
[main README](../README.md) for the full architecture and methodology.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Status of Gemini (key configured) and SAM (model loaded) |
| `GET /api/catalog` | Material catalogue with rates, coverage, wastage and render specs |
| `POST /api/images` | Upload a photo: validate, auto-rotate, downscale, quality-check |
| `GET /api/images/{id}` | The stored (normalised) photo |
| `POST /api/images/{id}/analyze` | Gemini scene check + component boxes → SAM 2.1 masks → editable polygons + auto scale |
| `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/{id}`, `POST /api/projects/{id}/copy` | Saved projects, scoped by the `X-Workspace-Id` header |
| `POST /api/estimate` | Quantities and costs for a design (stateless) |
| `POST /api/report` | Contractor PDF report (stateless) |

Interactive docs: `/docs`.

## Configuration (Space secrets / variables)

| Variable | Required | Example |
| --- | --- | --- |
| `GEMINI_API_KEY` | yes (secret) | key from Google AI Studio |
| `CORS_ORIGINS` | yes | `https://your-app.vercel.app` |
| `CORS_ORIGIN_REGEX` | optional | `https://.*\.vercel\.app` (allow preview deployments) |
| `DATABASE_URL` | optional | Postgres URL for persistent projects (default: SQLite inside the container) |
| `GEMINI_MODELS` | optional | `gemini-3.5-flash,gemini-2.5-flash,gemini-flash-latest` |

## Local run

```bash
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
cp .env.example .env    # add your GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
pytest -q
```
