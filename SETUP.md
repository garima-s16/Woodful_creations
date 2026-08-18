# Setup

Two ways to run this: local dev scripts (fastest for day-to-day work) or Docker Compose (closer to production).

## Option A — Local dev scripts

```bash
# 1. One-time setup: creates backend venv + installs all dependencies
./setup.sh        # macOS/Linux
setup.bat         # Windows

# 2. Configure environment
cp backend/.env.example backend/.env
# edit backend/.env — set SECRET_KEY at minimum:
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

2. **Seeded, with realistic demo data:** `scripts/seed_sample_data.py` populates suppliers, materials, clients, orders, employees, and two named master accounts (`garima@woodful.local`, `nikhil@woodful.local`) in one pass. The master accounts need `SEED_MASTER_PASSWORD` set first, or they're skipped (never created with an insecure default):

   ```bash
   cd backend
   export SEED_MASTER_PASSWORD="choose a password"   # Windows: set SEED_MASTER_PASSWORD=...
   python scripts/seed_sample_data.py
   ```

   Safe to re-run — every seed function checks for existing rows first, so running it twice never creates duplicates.

## Option B — Docker Compose

```bash
export POSTGRES_PASSWORD=<choose a password>
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
docker-compose up --build
```

This brings up Postgres, Redis, the backend, and the frontend together. Same ports as above.

## Troubleshooting

- **"backend/venv not found" on start_all:** run `setup.sh`/`setup.bat` first, or delete `backend/venv` and `frontend/node_modules` to force a clean reinstall.
- **Docker Compose exits immediately:** it fails fast if `POSTGRES_PASSWORD` or `SECRET_KEY` aren't set — export them or put them in a `.env` file next to `docker-compose.yml` (never commit that file).
- **Database schema questions:** see [`database/README.md`](database/README.md) — the schema lives in `backend/app/models/` and `backend/alembic/versions/`, not a hand-written SQL file.
