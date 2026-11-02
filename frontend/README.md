# FacadeAI web app

Next.js 16 (App Router) frontend for FacadeAI. See the [main README](../README.md) for the architecture and methodology.

```bash
npm install
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local   # URL of the FastAPI backend
npm run dev        # http://localhost:3000
npx tsc --noEmit   # type-check
npm run lint
```

`NEXT_PUBLIC_API_URL` is read at build time; set it in the Vercel project settings before deploying.
