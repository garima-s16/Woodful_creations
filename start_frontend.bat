@echo off
REM Woodful Creations - Start frontend only
cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo node_modules not found. Run setup.bat first (or "npm install" here).
    exit /b 1
)

npm start
