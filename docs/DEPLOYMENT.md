# Deployment (free tier)

The frontend goes to **Vercel**. The API (FastAPI + SAM) goes to a **Hugging Face Space** (Docker, free CPU).
The order matters: deploy the API first, so you have its URL for the frontend.

## 0. Before you start

* Accounts: GitHub, Hugging Face, Vercel (all free).
* A Gemini API key from <https://aistudio.google.com/apikey>. Never commit it; it only goes into Space secrets.
* The project builds and tests locally (see README §8–9).

## 1. Push the code to GitHub

```bash
cd facade-ai
git add .
git commit -m "FacadeAI: exterior renovation planner"
git branch -M main
git remote add origin https://github.com/<you>/facade-ai.git
git push -u origin main
```

Check on GitHub that **no `.env` file** was pushed (`.gitignore` excludes it).

## 2. API on a Hugging Face Space

1. <https://huggingface.co/new-space> → name `facade-ai-api` → **SDK: Docker** → template **Blank** →
   hardware **CPU basic (free)** → Public → *Create Space*.
2. Upload the `backend` folder as the Space's root. The CLI handles binary files (fonts, demo photo) for you:

   ```bash
   pip install -U huggingface_hub
   hf auth login                      # paste a token with "write" access (Settings → Access Tokens)
   hf upload <your-hf-username>/facade-ai-api backend . --repo-type space
   ```

3. Space → **Settings → Variables and secrets**:
   * Secret `GEMINI_API_KEY` = your key
   * Variable `CORS_ORIGINS` = `http://localhost:3000` for now (you'll add the Vercel URL in step 4)
   * Variable `CORS_ORIGIN_REGEX` = `https://.*\.vercel\.app`
4. Wait for the build (about 8–12 min the first time: PyTorch and SAM are baked into the image).
   When it shows *Running*, open `https://<your-hf-username>-facade-ai-api.hf.space/api/health`.
   You should see `"gemini":"configured"` and, after about 20 s, `"sam":"ready"`.

> Free Spaces sleep after a period without traffic; the first request then takes about a minute (the app
> shows a "waking up" notice). Open the health URL a few minutes before a demo or an expected busy period.

## 3. Frontend on Vercel

1. <https://vercel.com/new> → import the GitHub repo.
2. **Root Directory: `frontend`** (Framework preset: Next.js is detected automatically).
3. Environment variable `NEXT_PUBLIC_API_URL` = `https://<your-hf-username>-facade-ai-api.hf.space`
   (no trailing slash).
4. Deploy, then open the `*.vercel.app` URL.

## 4. Connect them

* In the Space settings, set `CORS_ORIGINS` to your Vercel URL, e.g.
  `https://facade-ai.vercel.app,http://localhost:3000`, then **Restart** the Space.
* Put both live URLs at the top of `README.md` and commit.

## 5. Optional: persistent projects

The Space stores projects in SQLite inside the container, which resets when the Space rebuilds or restarts.
For permanent storage, create a free Postgres database (e.g. [Neon](https://neon.tech)) and add its
connection string as the secret `DATABASE_URL`. The demo project is re-created automatically either way.

## 6. Final check (in a private browser window)

- [ ] Home page loads; **Try the demo** opens the demo house on the Design step
- [ ] Switching designs re-renders the house; Before | After slider works
- [ ] Estimate shows totals; editing a rate changes the total
- [ ] **Download PDF report** works
- [ ] Upload your own house photo → parts detected in about 20–40 s → starter design → estimate
- [ ] Share link opens read-only in another browser
