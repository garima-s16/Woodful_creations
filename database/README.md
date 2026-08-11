# Database

This directory intentionally does not contain a raw SQL schema file.

## Where the schema actually lives

- **`backend/app/models/`** - the SQLAlchemy models. This is the schema
  definition itself: every table, column, type, constraint, and
  relationship in the application.
- **`backend/alembic/versions/`** - the migration history. Running
  `alembic upgrade head` from `backend/` builds the actual database
  (SQLite locally, PostgreSQL in production) from these models.

## Why there's no `schema.sql` here

An earlier version of this project had a `database/schema.sql` file
that was hand-maintained alongside the SQLAlchemy models. It drifted
out of sync with the real schema - different table names, different
columns for the same data - and was actively misleading. It was
removed rather than kept as a second, contradictory source of truth.

If you need to see the schema as raw SQL (for review, documentation,
or a database tool), generate it from the real source instead of
hand-maintaining a copy:

```bash
cd backend
alembic upgrade head
# SQLite:
sqlite3 woodful.db .schema > /tmp/current_schema.sql
```

## Setting up the database

See the root `README.md` or `SETUP_GUIDE.md` for the full setup
sequence: migrations, then bootstrapping the first administrator via
`backend/scripts/setup_local.py`.
