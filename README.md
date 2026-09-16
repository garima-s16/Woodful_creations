# Woodful Creations

Business management system for woodcraft and furniture businesses - clients, estimates, orders, materials/inventory (with a real category/subcategory/dynamic-attribute hierarchy, multi-supplier pricing, and a location tree), purchasing (with a smart cart that computes real shortage math), HR (attendance, leave, candidates/interviews, salary slips), a rule-based AI chat assistant that can resolve and propose real actions (create a material, add to cart, record a payment), event-driven notifications, and a responsive web app installable to the home screen on iPhone and Android (PWA - not a native app).

## Stack

- **Backend:** FastAPI (Python), SQLAlchemy + Alembic migrations, SQLite locally / PostgreSQL in production
- **Frontend:** React

## Setup

See [`docs/SETUP.md`](docs/SETUP.md) for local dev and Docker instructions.

Quick version: `./setup.sh && ./start_all.sh` (or the `.bat` equivalents on Windows) - backend at `http://localhost:8000`, frontend at `http://localhost:3000`.

## Full project docs

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the architecture, module ownership, a full feature-to-file map, and key behavioral gotchas. Start there if you're new to the team.

## Database

Schema lives in code, not as a hand-maintained SQL file - see [`docs/SETUP.md`](docs/SETUP.md#troubleshooting).
