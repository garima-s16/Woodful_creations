# Woodful Creations

Business management system for woodcraft and furniture businesses — stock/inventory, estimates, attendance, interviews, and client management.

## Stack

- **Backend:** FastAPI (Python), SQLAlchemy + Alembic migrations, SQLite locally / PostgreSQL in production
- **Frontend:** React

## Setup

See [`SETUP.md`](SETUP.md) for local dev and Docker instructions, and [`REQUIREMENTS.md`](REQUIREMENTS.md) for versions and dependencies.

Quick version: `./setup.sh && ./start_all.sh` (or the `.bat` equivalents on Windows) — backend at `http://localhost:8000`, frontend at `http://localhost:3000`.

## Database

Schema lives in code, not as a hand-maintained SQL file — see [`database/README.md`](database/README.md).
