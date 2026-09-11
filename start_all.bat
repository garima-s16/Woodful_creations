@echo off
REM Woodful Creations - Complete Development Environment Setup for Windows

setlocal enabledelayedexpansion

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
    exit /b 1
)

:setup_done

echo.
echo Starting Woodful Creations in development mode...
echo.

echo Starting backend server on http://localhost:8000
start "Woodful Backend" cmd /k call start_backend.bat

REM Give backend time to start
timeout /t 3

echo Starting frontend server on http://localhost:3000
start "Woodful Frontend" cmd /k call start_frontend.bat

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
