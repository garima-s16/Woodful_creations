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

REM Defect repair: "::" (the IPv6 wildcard), not "0.0.0.0" (IPv4-only) -
REM a dual-stack bind. Windows has defaulted to dual-stack sockets
REM (IPV6_V6ONLY=0) since Vista, so this one socket accepts BOTH ::1
REM and 127.0.0.1/any-IPv4 connections - it no longer matters which
REM address family "localhost" resolves to first on this machine, the
REM backend answers immediately either way. This is what makes it safe
REM for the frontend to default to http://localhost:8000 instead of
REM 127.0.0.1 (see frontend\.env.example and
REM frontend\src\utils\api.js): same host on both ends keeps every
REM request "same-site" for the SameSite=Lax auth cookie, which
REM 127.0.0.1-vs-localhost was silently breaking (see those files for
REM the full explanation). If IPv6 is ever genuinely disabled at the OS
REM level on this machine, uvicorn will fail to bind here - revert this
REM one flag to --host 0.0.0.0 and set
REM REACT_APP_API_URL=http://127.0.0.1:8000 in frontend\.env (a
REM supported override, not a default meant for everyone else).
if /i "%ENVIRONMENT_VALUE%"=="development" (
    uvicorn app.main:app --reload --host :: --port 8000
) else (
    echo ENVIRONMENT=%ENVIRONMENT_VALUE% - starting without --reload ^(reload is development-only^).
    uvicorn app.main:app --host :: --port 8000
)
