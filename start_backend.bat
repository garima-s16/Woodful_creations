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

REM --reload is development-only (see start_backend.sh for the full
REM rationale) - never use it when ENVIRONMENT is not "development".
set "ENVIRONMENT_VALUE=development"
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /r "^ENVIRONMENT=" .env`) do set "ENVIRONMENT_VALUE=%%B"

if /i "%ENVIRONMENT_VALUE%"=="development" (
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) else (
    echo ENVIRONMENT=%ENVIRONMENT_VALUE% - starting without --reload ^(reload is development-only^).
    uvicorn app.main:app --host 0.0.0.0 --port 8000
)
