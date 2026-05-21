# Deploy Vioci webapp to Vercel (existing project)

The **webapp** is a static Vite/React build. The **FastAPI API** (`server/`) does not run on Vercel by default — host it elsewhere (Railway, Render, Fly.io, a VM, etc.) and either proxy `/api` from Vercel or set `VITE_API_BASE_URL`.

## 1. Vercel project settings

In your **existing** Vercel project → **Settings → General**:

| Setting | Value |
|---------|--------|
| **Root Directory** | `webapp` |
| **Framework Preset** | Vite |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |
| **Install Command** | `npm install` |

`webapp/vercel.json` already configures SPA routing (all paths → `index.html` for React Router).

## 2. Connect the API

Choose one:

### A. Same origin (recommended) — Vercel rewrites

In the Vercel project, add a rewrite **above** the SPA rule (Dashboard → **Redirects** or edit `webapp/vercel.json`):

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-BACKEND-HOST/api/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

Replace `YOUR-BACKEND-HOST` with your live API (no trailing slash). The UI keeps `baseURL: ''` and WebSockets use `wss://your-vercel-domain/...`.

### B. Separate API URL — environment variable

If the API is on another domain and you are **not** proxying:

1. Vercel → **Settings → Environment Variables** (Production):
   - `VITE_API_BASE_URL` = `https://api.example.com` (no trailing slash)
2. Redeploy.

Backend must allow CORS from your Vercel domain.

## 3. Backend env (on your API host)

At minimum for production:

- `VIOCI_JWT_SECRET` — long random secret
- `VIOCI_DATABASE_URL` — e.g. Supabase pooler URI ([cloud-setup.md](./cloud-setup.md))
- VLM keys as needed (`GOOGLE_API_KEY`, etc.)

## 4. Deploy from Git

1. Connect the GitHub repo to the existing Vercel project (if not already).
2. Push to the branch Vercel watches (usually `main`).
3. **Deployments** → trigger **Redeploy** after changing root directory or env.

## 5. Deploy from CLI (link existing project)

```bash
cd webapp
npx vercel login
npx vercel link
```

Select your **existing** team and project when prompted.

```bash
npx vercel --prod
```

Preview deploy (no production):

```bash
npx vercel
```

## 6. Verify

- `https://YOUR-VERCEL-DOMAIN/` — landing page
- `https://YOUR-VERCEL-DOMAIN/login` — auth UI
- `https://YOUR-VERCEL-DOMAIN/api/health` — should return `{"ok":true}` if rewrites/proxy are set
- Sign up / login → should reach `/workspace` with a valid API

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 404 on `/login`, `/workspace` | Root Directory must be `webapp`; redeploy after `vercel.json` is present |
| API calls fail / network error | Add `/api` rewrite or `VITE_API_BASE_URL`; confirm backend is up |
| WebSocket parse stuck | Rewrites must include WS path to backend, or API on same host as UI |
| Blank page after deploy | Check build logs; run `cd webapp && npm run build` locally |
