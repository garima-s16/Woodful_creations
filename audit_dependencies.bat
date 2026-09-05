@echo off
REM Woodful Creations - Dependency vulnerability audit
REM
REM This sandbox/CI environment used to develop this project has no
REM network access, so pip-audit/npm audit could not actually be run
REM here - dependency security was explicitly NOT verified as part of
REM that work. Run this script from a real, network-enabled machine
REM before deploying, and whenever dependencies change.
REM
REM Does NOT run "npm audit fix --force" or any other command that
REM rewrites lockfiles automatically - review findings and fix
REM commands manually.

echo === Backend (pip) ===
cd /d "%~dp0backend"
if exist "venv" call venv\Scripts\activate.bat
where pip-audit >nul 2>nul
if errorlevel 1 (
    echo pip-audit not installed. Install it with: pip install pip-audit
) else (
    pip-audit -r requirements.txt
)

echo.
echo === Frontend (npm) ===
cd /d "%~dp0frontend"
if exist "package-lock.json" (
    npm audit
) else (
    echo No frontend\package-lock.json found - run "npm install" first.
)
