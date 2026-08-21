@echo off
REM Woodful Creations - Start the FastAPI backend
REM The app object lives at app/main.py (app.main:app), not at top-level main.py.

cd /d "%~dp0backend"

if not exist "venv" (
    echo ERROR: backend\venv not found. Run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

if not exist ".env" (
    echo WARNING: backend\.env not found. Copying from .env.example - edit it before real use.
    copy .env.example .env
)

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
