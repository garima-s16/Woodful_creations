# Woodful Creations

Business management system for woodcraft and furniture businesses — stock/inventory, estimates, attendance, interviews, and client management.

## Stack

- **Backend:** FastAPI (Python), SQLAlchemy + Alembic migrations, SQLite locally / PostgreSQL in production
- **Frontend:** React

## Quick start

```bash
# One-time setup (creates backend venv, installs frontend deps)
./setup.sh        # macOS/Linux
setup.bat         # Windows

# Start both backend and frontend
./start_all.sh    # macOS/Linux
start_all.bat     # Windows
```

Or start each side individually with `start_backend.sh` / `start_frontend.sh` (and their `.bat` equivalents).

Backend runs at `http://localhost:8000`, frontend at `http://localhost:3000`.

## Configuration

- Backend: copy `backend/.env.example` to `backend/.env` and fill in real values (never commit `.env`).
- Frontend: `frontend/.env` holds `REACT_APP_API_URL` and related settings.

## Database

Schema lives in code, not as a hand-maintained SQL file — see [`database/README.md`](database/README.md) for details and how to generate a raw schema dump if you need one.

## First admin user

No default admin credentials ship with this repo. Bootstrap the first administrator account locally via `backend/scripts/setup_local.py` after running migrations.

## Docker

`docker-compose.yml` at the repo root brings up backend + frontend together; see the file for service details.
