# Production: Vercel (UI) + Render (API)

| Layer | Host | URL |
|-------|------|-----|
| React UI | Vercel | https://www.vioci.xyz |
| FastAPI API | Render (Docker) | `https://vioci-work-1.onrender.com` |

## 1. Deploy the Python API on Render

1. [render.com](https://render.com) → **New** → **Blueprint**.
2. Connect GitHub repo **`ankit06ch/vioci-work`** (branch `main`).
3. Render reads [`render.yaml`](../render.yaml) and creates **`vioci-api`** (Docker).
4. In the Render service → **Environment**, set secrets:

| Variable | Required | Notes |
|----------|----------|--------|
| `VIOCI_DATABASE_URL` | Yes (prod) | Supabase pooler URI — [cloud-setup.md](./cloud-setup.md) |
| `VIOCI_SUPABASE_URL` | Recommended | File storage |
| `VIOCI_SUPABASE_SERVICE_ROLE_KEY` | Recommended | Backend only |
| `GOOGLE_API_KEY` | For parse/chat | Or Vertex config |
| `VIOCI_JWT_SECRET` | Auto-generated | Or set your own long random string |
| `VIOCI_CORS_ORIGINS` | Pre-set in blueprint | Add preview URLs if needed |

5. Wait until deploy is **Live**. Open:

   `https://vioci-work-1.onrender.com/api/health`

   Expect: `{"ok":true}`

Copy the service URL (no trailing slash), e.g. `https://vioci-work-1.onrender.com`.

> Free Render services spin down after idle; first request may take ~30s.

## 2. Point Vercel at the API

1. [vercel.com](https://vercel.com) → project **vioci** → **Settings** → **Environment Variables**.
2. Add **Production** (and Preview if you want):

   | Name | Value |
   |------|--------|
   | `VIOCI_API_ORIGIN` | `https://vioci-work-1.onrender.com` |

3. **Redeploy** (required — the build script writes `/api` rewrites from this variable):

   ```bash
   cd webapp
   npx vercel --prod --yes
   ```

   Or push to `main` if Git deploy is enabled.

4. Verify:

   - `https://www.vioci.xyz/api/health` → `{"ok":true}`
   - Sign up / login on the site

## How routing works

- Browser calls `https://www.vioci.xyz/api/...`
- Vercel **rewrites** to `https://vioci-work-1.onrender.com/api/...` (also committed in `webapp/vercel.json`)
- WebSockets use the same host (`wss://www.vioci.xyz/api/projects/.../events`)
- CORS on the API allows `vioci.xyz` and Vercel domains

Implementation: [`webapp/scripts/sync-vercel-api-rewrite.mjs`](../webapp/scripts/sync-vercel-api-rewrite.mjs) runs during `npm run build`.

## Alternative: direct API URL (no Vercel proxy)

Set on Vercel instead:

- `VITE_API_BASE_URL` = `https://vioci-work-1.onrender.com`

Leave `VIOCI_API_ORIGIN` unset. CORS must include your UI origin (already in `render.yaml`).

## Local Docker smoke test

```bash
docker build -t vioci-api .
docker run --rm -p 8000:8000 -e VIOCI_AUTH_DISABLED=true vioci-api
curl http://127.0.0.1:8000/api/health
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/api/health` 404 on vioci.xyz | Set `VIOCI_API_ORIGIN` on Vercel and redeploy |
| Login network error | Render API down or wrong `VIOCI_API_ORIGIN` |
| CORS error in browser | Add your UI URL to `VIOCI_CORS_ORIGINS` on Render |
| 401 after login | Same `VIOCI_JWT_SECRET` not required across hosts if using proxy; JWT is issued by API |
| Parse never finishes | Set `GOOGLE_API_KEY` on Render |
