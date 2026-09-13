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

REM Defect repair: an existing frontend\.env from before this fix (this
REM exact line was .env.example's own old default) silently breaks
REM login - see frontend\src\utils\api.js's comment on API_URL for the
REM full SameSite/cross-site explanation. Migrated automatically, in
REM place. Only ever touches this one exact known-stale value - never a
REM REACT_APP_API_URL a person deliberately set to something else.
findstr /x /c:"REACT_APP_API_URL=http://127.0.0.1:8000" .env >nul 2>&1
if not errorlevel 1 (
    echo Migrating frontend\.env: REACT_APP_API_URL 127.0.0.1 -^> localhost ^(see api.js for why^).
    powershell -NoProfile -Command "(Get-Content .env) -replace '^REACT_APP_API_URL=http://127\.0\.0\.1:8000$', 'REACT_APP_API_URL=http://localhost:8000' | Set-Content .env"
)

call npm start
