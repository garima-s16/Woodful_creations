# Setup

Two ways to run this: local dev scripts (fastest for day-to-day work) or Docker Compose (closer to production).

## Option A - Local dev scripts

```bash
# 1. One-time setup: creates backend venv + installs all dependencies
./setup.sh        # macOS/Linux
setup.bat         # Windows

# 2. Configure environment
cp backend/.env.example backend/.env
# edit backend/.env - set SECRET_KEY at minimum:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"

# 3. Start everything
./start_all.sh    # macOS/Linux
start_all.bat     # Windows
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

To run either side alone: `start_backend.sh` / `start_frontend.sh` (and `.bat` equivalents). Migrations run automatically on backend startup.

### First admin user

No admin account ships with the repo. Two ways to get one:

1. **Interactive, one account:** after the backend has started at least once (so the database exists):

   ```bash
   cd backend
   python scripts/setup_local.py
   ```

   Follow the prompts to set a username and password.

2. **Seeded, with realistic demo data:** `scripts/seed_sample_data.py` populates suppliers, materials, clients, orders, employees, and two named master accounts (`nikhil@woodful.local` / Nikhil Soni, `garima@woodful.local` / Garima Sharma) in one pass. It also seeds Woodful's permanent business roster - the real Clients (`CLW-xxx`), Suppliers (`SUPW-xxx`), and Employees (`EMP-xxx`, matched by name) - alongside the illustrative test/demo Estimate/Order data (`CL-xxx`, `WC-2026-xxx`), including the Shrangi (CL-008) multi-month Estimate -> Order scenario. The master accounts need `SEED_MASTER_PASSWORD` set first, or they're skipped (never created with an insecure default):

   ```bash
   cd backend
   export SEED_MASTER_PASSWORD="choose a password"   # Windows: set SEED_MASTER_PASSWORD=...
   python scripts/seed_sample_data.py
   ```

   Safe to re-run - every seed function checks for existing rows first (or reconciles them to the exact roster values), so running it twice never creates duplicates or changes fixed phone numbers/addresses.

## Option B - Docker Compose (local, closer-to-production settings)

```bash
export POSTGRES_PASSWORD=<choose a password>
export REDIS_PASSWORD=<choose a password>
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export CORS_ORIGINS=http://localhost:3000
docker-compose up --build
```

This brings up Postgres, Redis, the backend, and the frontend together, all as local containers, with `ENVIRONMENT=production`-style settings (DEBUG off, secure cookies, Redis-backed rate limiting). It's useful for testing production-like behavior locally, but it is **not** the real production deployment - `DATABASE_URL`/`REDIS_URL` still point at the Postgres/Redis containers this same file starts, not at any managed service.

## Option C - Real production deployment

Real production must point at the managed database (Neon) and a managed/shared Redis, never at a container-local instance. Use `docker-compose.prod.yml`, which has no local `database`/`redis` services at all:

```bash
export DATABASE_URL=<real Neon connection string>
export REDIS_URL=<real managed Redis URL>
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export CORS_ORIGINS=<real frontend origin, e.g. https://app.yourdomain.com>
export FRONTEND_URL=<same real frontend origin>
export REACT_APP_API_URL=<real backend origin the browser should call>
docker-compose -f docker-compose.prod.yml up --build -d
```

Every required value above uses `:?` in the compose file, so a missing one fails startup immediately with a clear message rather than silently falling back to something local. `app/platform/configuration/config.py` additionally refuses to start at all if `ENVIRONMENT=production` and any of the following hold: `DATABASE_URL` is SQLite, `CORS_ORIGINS` is empty or contains a `localhost`/`127.0.0.1` origin, or `RATE_LIMIT_BACKEND` isn't `redis`.

## Troubleshooting

- **"backend/venv not found" on start_all:** run `setup.sh`/`setup.bat` first, or delete `backend/venv` and `frontend/node_modules` to force a clean reinstall.
- **Docker Compose exits immediately:** it fails fast if `POSTGRES_PASSWORD` or `SECRET_KEY` aren't set - export them or put them in a `.env` file next to `docker-compose.yml` (never commit that file).
- **Database schema questions:** the schema lives in `backend/app/platform/database/` (platform-level entities like `Base`/`BaseModel`) and `backend/app/modules/*/models.py` (business domains), plus `backend/alembic/versions/` (migration history) - there is no hand-written `schema.sql`. An earlier version of this project had one, hand-maintained alongside the SQLAlchemy models; it drifted out of sync (different table/column names for the same data) and was actively misleading, so it was removed rather than kept as a second, contradictory source of truth. To see the schema as raw SQL for review or a database tool, generate it from the real source instead of hand-maintaining a copy: `cd backend && alembic upgrade head && sqlite3 woodful.db .schema > /tmp/current_schema.sql` (SQLite locally; use your Postgres client's own schema-dump command for a Postgres database).
