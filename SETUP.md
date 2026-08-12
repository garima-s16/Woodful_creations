# Setup

Two ways to run this: local dev scripts (fastest for day-to-day work) or Docker Compose (closer to production). See `REQUIREMENTS.md` for versions.

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

No admin account ships with the repo. After the backend has started at least once (so the database exists), bootstrap one:

```bash
cd backend
python scripts/setup_local.py
```

Follow the prompts to set a username and password.

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
