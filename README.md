# Woodful Creations

Business management system for woodcraft and furniture businesses — clients, estimates, orders, materials/inventory (with a real category/subcategory/dynamic-attribute hierarchy, multi-supplier pricing, and a location tree), purchasing (with a smart cart that computes real shortage math), HR (attendance, leave, candidates/interviews, salary slips), a rule-based AI chat assistant that can resolve and propose real actions (create a material, add to cart, record a payment), event-driven notifications, and installable-app support for iPhone and Android.

## Stack

- **Backend:** FastAPI (Python), SQLAlchemy + Alembic migrations, SQLite locally / PostgreSQL in production
- **Frontend:** React

## Setup

See [`SETUP.md`](SETUP.md) for local dev and Docker instructions.

Quick version: `./setup.sh && ./start_all.sh` (or the `.bat` equivalents on Windows) — backend at `http://localhost:8000`, frontend at `http://localhost:3000`.

## Full project docs

See [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md) for the business context, how the core workflow is modeled, where the project currently stands, and a full code tree with notes on where to fix what. Start there if you're new to the team.

## Database

Schema lives in code, not as a hand-maintained SQL file — see [`database/README.md`](database/README.md).
