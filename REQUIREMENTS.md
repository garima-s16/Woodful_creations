# Requirements

## System

| Tool | Version | Notes |
|---|---|---|
| Python | 3.10+ | backend (FastAPI) |
| Node.js | 18+ | frontend (React) |
| npm | 9+ | ships with Node 18 |
| SQLite | bundled | default local database |
| PostgreSQL | 15 | production database (see `docker-compose.yml`) |
| Redis | 7 | caching/session use in production |

Docker + Docker Compose are only needed if you run via `docker-compose.yml` instead of the local dev scripts.

## Backend (Python)

Installed from `backend/requirements.txt`:

- **Web/API:** fastapi, uvicorn, python-multipart
- **Data/DB:** sqlalchemy, psycopg2-binary, alembic (runs migrations automatically on startup — this is a runtime dependency, not dev-only)
- **Validation/config:** pydantic, pydantic-settings, python-dotenv
- **Auth/security:** python-jose, passlib, bcrypt, cryptography
- **Documents/exports:** reportlab (PDF), openpyxl (Excel), python-docx, pillow
- **Other:** email-validator, requests, aiofiles, redis
- **Dev/test only:** pytest, httpx

## Frontend (Node)

Installed from `frontend/package.json`:

- react, react-dom, react-router-dom
- react-redux, @reduxjs/toolkit
- axios
- react-scripts (build tooling, dev dependency)

## Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in real values (`SECRET_KEY`, database URL, email/SMTP, `OPENAI_API_KEY` if using the chat assistant). Never commit `.env`.

`frontend/.env` holds `REACT_APP_API_URL`, `REACT_APP_APP_NAME`, `REACT_APP_ENVIRONMENT`.

Docker Compose additionally requires `POSTGRES_PASSWORD` and `SECRET_KEY` to be set in your shell or a `.env` next to `docker-compose.yml` — it will refuse to start without them.
