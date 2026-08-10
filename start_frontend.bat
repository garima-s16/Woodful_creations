@echo off
REM Woodful Creations - Start the React frontend dev server

cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)

if not exist ".env" (
    echo WARNING: frontend\.env not found. Copying from .env.example.
    copy .env.example .env
)

call npm start
