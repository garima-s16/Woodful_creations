# Woodful Creations

Business management system for woodcraft and furniture businesses — stock/inventory, estimates, attendance, interviews, and client management.

## Stack

- **Backend:** FastAPI (Python), SQLAlchemy + Alembic migrations, SQLite locally / PostgreSQL in production
- **Frontend:** React

## Setup

See [`SETUP.md`](SETUP.md) for local dev and Docker instructions.

Quick version: `./setup.sh && ./start_all.sh` (or the `.bat` equivalents on Windows) — backend at `http://localhost:8000`, frontend at `http://localhost:3000`.

## Full project docs

See [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md) for the complete feature list, tech stack, and a full code tree with notes on where to fix what.

## Database

Schema lives in code, not as a hand-maintained SQL file — see [`database/README.md`](database/README.md).
