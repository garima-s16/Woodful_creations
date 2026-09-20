@echo off
REM Woodful Creations - Complete Development Environment Setup for Windows

setlocal enabledelayedexpansion

REM Same fix as setup.bat: pin the working directory to this script's own
REM folder before any relative path (backend\venv, frontend\node_modules,
REM call setup.bat) is checked or run. Without this, "Run as administrator"
REM (which starts a batch file in C:\Windows\System32), a shortcut with a
REM different "Start in" folder, or running this from a terminal already
REM sitting elsewhere would each make every relative-path check below
REM silently wrong - "backend\venv" not found where it's actually looking,
REM `call setup.bat` failing with "not recognized" because it isn't on
REM PATH and isn't in the wrong cwd either.
cd /d "%~dp0"

echo ======================================
echo Woodful Creations - Quick Start
echo ======================================
echo.

REM Run setup if not already done
if not exist "backend\venv" goto :run_setup
if not exist "frontend\node_modules" goto :run_setup
goto :setup_done

:run_setup
echo Running initial setup...
call setup.bat
if errorlevel 1 (
    echo Setup failed!
    pause
    exit /b 1
)

:setup_done

echo.
echo Starting Woodful Creations in development mode...
echo.

REM Backend/frontend launch commands are inlined here rather than in
REM separate start_backend.bat/start_frontend.bat files, so this one
REM script is the sole source of truth for how the dev servers start.
REM Host is "::" (IPv6 wildcard), not "0.0.0.0" (IPv4-only): modern
REM Windows resolves "localhost" to ::1 (IPv6) first, and a server bound
REM only to 0.0.0.0 never accepts that connection - the browser/axios
REM request to http://localhost:8000 then hangs or fails outright,
REM which is exactly the "Unable to connect to Woodful server" screen.
REM Binding to "::" listens on the IPv6 wildcard while still accepting
REM IPv4 connections (dual-stack, the default on Windows/Linux unless
REM IPV6_V6ONLY is forced), so both ::1 and 127.0.0.1 resolutions of
REM localhost reach it. The frontend's API_URL stays http://localhost:8000
REM unchanged - only the bind address changes, not what the frontend calls.
echo Starting backend server on http://localhost:8000
start "Woodful Backend" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && uvicorn app.main:app --host :: --port 8000 --reload"

REM Give backend time to start
timeout /t 3

echo Starting frontend server on http://localhost:3000
start "Woodful Frontend" cmd /k "cd /d %~dp0frontend && npm start"

echo.
echo ======================================
echo Both servers are running!
echo ======================================
echo.
echo Access points:
echo   Backend API: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo   Frontend: http://localhost:3000
echo.
echo Close the command windows to stop services
echo.
pause
