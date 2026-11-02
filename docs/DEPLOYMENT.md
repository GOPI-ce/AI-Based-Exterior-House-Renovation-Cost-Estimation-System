# Deployment (free tier)

| Part | Where | Cost |
| --- | --- | --- |
| Web app (Next.js) | **Vercel** Hobby | free |
| API + AI models (FastAPI, SAM 2.1, Depth Anything V2) | **Modal**: serverless container from `backend/Dockerfile` | free monthly compute allowance |
| Projects and photos | **Neon** Postgres | free |

The API needs about 4 GB of memory for its models, more than typical free web hosts give (512 MB). Modal runs the
container only while it is used and stops it after 10 idle minutes, so normal use stays within the free allowance.
The first request after a pause waits for a cold start (about a minute); the web app shows a "waking up" notice.

Deploy the API first, so you have its URL for the web app.

## 0. Before you start

* Accounts (all free; sign in with GitHub): Vercel, Modal, Neon.
* A Gemini API key from <https://aistudio.google.com/apikey>. Never commit it; it only goes into Modal's secret.
* The project builds and tests locally (see README §10–11), and CI is green on `main`.

## 1. Database on Neon

1. <https://console.neon.tech> → **Create project** (any name, region close to your users, e.g. Singapore).
2. Copy the **connection string** (Dashboard → *Connect*). It looks like
   `postgresql://user:password@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
   Tables and the demo project are created automatically on first start.

## 2. API on Modal

1. Modal → **Secrets → Create new secret → Custom**, name it **`facade-api`**, with:
   * `GEMINI_API_KEY` = your key
   * `DATABASE_URL` = the Neon connection string
   * `CORS_ORIGINS` = `http://localhost:3000` (the Vercel URL is added in step 4)
   * `CORS_ORIGIN_REGEX` = `https://.*\.vercel\.app`
2. Modal → **Settings → API Tokens → New token**. In GitHub → repository **Settings → Secrets and variables →
   Actions → Secrets**, add `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`.
3. GitHub → **Actions → Deploy API → Run workflow** (it also runs by itself after every green CI on `main`).
   The first build takes about 10–15 minutes (PyTorch and both models are baked into the image).
4. The workflow log ends with the URL: `https://<modal-workspace>--facade-ai-api.modal.run`.
   Open `<url>/api/health`: after the cold start you should see `"gemini":"configured"`, then
   `"sam":"ready"` and `"depth":"ready"` within about 30 s.

To deploy from your own machine instead: `pip install modal && modal setup && cd backend && modal deploy modal_app.py`.

## 3. Web app on Vercel

1. <https://vercel.com/new> → import the GitHub repository.
2. **Root Directory: `frontend`** (Next.js is detected automatically).
3. Environment variable `NEXT_PUBLIC_API_URL` = the Modal URL from step 2 (no trailing slash).
4. Deploy, then open the `*.vercel.app` URL. Vercel redeploys on every push to `main`.

## 4. Connect them

* In Modal's `facade-api` secret, set `CORS_ORIGINS` to your Vercel URL, e.g.
  `https://facade-ai.vercel.app,http://localhost:3000`, then re-run **Deploy API** so the container picks it up.
* Put both live URLs at the top of `README.md` and commit.

## Alternative: Hugging Face Space

`backend/README.md` carries the Space metadata, and the same Dockerfile runs there unchanged (port 7860).
Since July 2026, new Docker Spaces need a paid Hugging Face plan. The **Keep API awake** workflow (repository
variable `API_HEALTH_URL`) is for hosts like that, which sleep after days without traffic; Modal does not need it.

## Final check (in a private browser window)

- [ ] Home page loads; **Try the demo** opens the demo house
- [ ] Switching designs re-renders the house; Before | After slider works
- [ ] Estimate shows totals and the 15-year cost; editing a rate changes the total
- [ ] **Download PDF report** works
- [ ] Upload your own house photo → parts detected in about 20–40 s (plus a cold start) → starter design → estimate
- [ ] **Design it for my budget** creates a design within the budget
- [ ] Share link opens read-only in another browser
