# Cloud storage (free tier)

Vioci can run entirely on your machine (default) or use **[Supabase](https://supabase.com)** on the free tier:

| Piece | Supabase product | Free tier (typical) |
|-------|------------------|---------------------|
| Users, orgs, projects, images, diagrams | **PostgreSQL** | 500 MB database |
| Source PNGs, diagram JSON, telemetry sheets | **Storage** | 1 GB files |

No credit card is required for the Supabase free plan. If you only set `VIOCI_DATABASE_URL`, metadata and blobs live in Postgres; set Storage vars too so sheet files and parse caches sync to the cloud.

## 1. Create a Supabase project

1. Sign up at [supabase.com](https://supabase.com) and create a new project.
2. Wait until the database is ready.

## 2. Database connection string

1. Open **Project Settings → Database**.
2. Under **Connection string**, choose **URI** and **Transaction** pooler (port **6543**).
3. Copy the URL and replace `[YOUR-PASSWORD]` with your database password.
4. Add to `.env`:

```bash
VIOCI_DATABASE_URL=postgresql://postgres.xxxx:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

The app rewrites this to `postgresql+psycopg://` automatically and disables server-side prepared statements (required for the transaction pooler on port 6543).

## 3. Storage bucket (project files)

1. Open **Storage** in the Supabase dashboard.
2. **New bucket** → name: `vioci` → **Private** (recommended).
3. Open **Project Settings → API** and copy:
   - **Project URL** → `VIOCI_SUPABASE_URL`
   - **service_role** key (secret) → `VIOCI_SUPABASE_SERVICE_ROLE_KEY`

```bash
VIOCI_SUPABASE_URL=https://xxxx.supabase.co
VIOCI_SUPABASE_SERVICE_ROLE_KEY=eyJ...
VIOCI_SUPABASE_BUCKET=vioci
```

The server uses the service role key only on the backend (never ship it to the browser).

## 4. Install Python extras

```bash
pip install -e ".[web,cloud,google,dev]"
```

## 5. Initialize tables and verify

```bash
PYTHONPATH=. python scripts/check_cloud.py
```

This connects to Postgres, creates tables if needed, and checks Storage when configured.

## 6. Run the app

```bash
make dev
```

On startup, with `VIOCI_DATABASE_URL` set, data is stored in Supabase Postgres. With Storage vars set, project files are uploaded after writes and cached under `VIOCI_FILE_CACHE_DIR` (default: `~/.cache/vioci/projects`) for parsing and CSV sheets.

## Migrating existing local data

If you already have projects under `workspace/`:

```bash
PYTHONPATH=. python scripts/migrate_local_to_cloud.py
```

This copies rows from `workspace/.index.sqlite` into Postgres and uploads files to Storage. Run once while `.env` has cloud variables set.

## Security notes

- Rotate the database password and service role key if they are ever committed.
- Use a strong `VIOCI_JWT_SECRET` in production.
- Do not expose `VIOCI_SUPABASE_SERVICE_ROLE_KEY` to the frontend.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Signup stuck on “Creating account…”, no API logs | Zombie server on port 8000. Run `make kill-dev-ports` then `make dev`. Confirm `curl http://127.0.0.1:8000/api/health` returns `{"ok":true}` before using the UI. |
| `Address already in use` when running `make dev` | Same as above — `make kill-dev-ports` |
| `No module named 'psycopg'` | `pip install -e ".[cloud]"` |
| `No module named 'supabase'` | same |
| Connection refused on port 5432 | Use the **pooler** URI on port **6543** from the dashboard |
| Storage upload 403 | Create the `vioci` bucket; confirm service role key |
| Tables missing | Run `scripts/check_cloud.py` or start the API once (`init_db` creates tables) |
| `DuplicatePreparedStatement` / `f405` on startup | Use the **transaction pooler** URI (6543); the app sets `prepare_threshold=None` automatically — redeploy after updating |
