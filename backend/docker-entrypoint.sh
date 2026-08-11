#!/bin/sh
set -e

echo "Starting application (database migrations run automatically on startup)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
