@echo off
REM Woodful Creations - Master Local Verification Harness (Windows)
REM
REM Windows Command Prompt equivalent of woodful_full_verification.sh.
REM Same checks, same sections, same five-status vocabulary - this file
REM orchestrates the same backend\scripts\verify_*.py scripts and the
REM real pytest suite rather than re-implementing their checks here.
REM
REM Every check reports exactly one of:
REM   PASS                   - genuinely ran, genuinely succeeded
REM   FAIL                   - genuinely ran, found a real problem
REM   BLOCKED                - required local tooling/dependency is
REM                            missing, so the check could not attempt
REM                            to run at all (no venv, no network, no
REM                            node_modules)
REM   NOT CONFIGURED         - the feature itself is deliberately off in
REM                            this environment's config (e.g.
REM                            GEMINI_ENABLED=False, STORAGE_PROVIDER is
REM                            not drive) - there is nothing to verify
REM   NOT RUNTIME VERIFIED   - the feature is configured/enabled but the
REM                            actual live credential/connectivity check
REM                            could not be completed here
REM
REM No status is ever silently upgraded to PASS. One failing/blocked
REM check never prevents the remaining, independent checks from
REM running.
REM
REM Secrets (passwords, API keys, tokens, connection strings) are never
REM printed to the console or written to the result files below - only
REM a status and a short, non-sensitive detail message. Every inline
REM Python check below catches its own exceptions and prints a fixed,
REM generic detail string rather than the raw exception text, which is
REM how this file avoids needing a shell-level secret-redaction filter
REM (str.exceptions can contain a DSN/password; a fixed string cannot).
REM
REM Usage: woodful_full_verification.bat (from anywhere - this script
REM changes to its own directory first, so it does not depend on the
REM caller's current working directory or on the project being at any
REM fixed path).
REM
REM Requires: normal Windows Command Prompt. Does NOT require WSL, Git
REM Bash, bash, sh, grep, sed, awk, or chmod. Uses PowerShell (ships
REM with every supported Windows version) only for the two things batch
REM genuinely cannot do cleanly: starting/stopping a background process
REM by its own PID, and making one HTTP health-check request.

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

set "RESULTS_DIR=%SCRIPT_DIR%\verification-results"
if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"

set "TEMP_DIR=%TEMP%\woodful_verify_%RANDOM%"
mkdir "%TEMP_DIR%" 2>nul

set "RESULTS_TXT=%RESULTS_DIR%\latest.txt"
set "RESULTS_JSON=%RESULTS_DIR%\latest.json"
set "RESULTS_HTML=%RESULTS_DIR%\latest.html"
type nul > "%RESULTS_TXT%.rows"

set /a TOTAL=0
set /a PASS_COUNT=0
set /a FAIL_COUNT=0
set /a BLOCKED_COUNT=0
set /a NOTCONFIGURED_COUNT=0
set /a NOTVERIFIED_COUNT=0
set "FAILURES_LOG=%TEMP_DIR%\failures.log"
type nul > "%FAILURES_LOG%"

set "BACKEND_VENV_PY=%SCRIPT_DIR%\backend\venv\Scripts\python.exe"
set "VENV_OK=false"

echo ======================================================================
echo Woodful Creations - Master Local Verification (Windows)
echo Run at: %DATE% %TIME%
echo ======================================================================

REM ======================================================================
REM record <status> <name> <detail>
REM Appends one row to each result-file buffer and prints one console
REM line. Called via `call :record STATUS "Name" "Detail"`.
REM ======================================================================
goto :after_record

:record
set "R_STATUS=%~1"
set "R_NAME=%~2"
set "R_DETAIL=%~3"
set /a TOTAL+=1
if "%R_STATUS%"=="PASS" (
    set /a PASS_COUNT+=1
    echo   PASS                  %R_NAME% -- %R_DETAIL%
) else if "%R_STATUS%"=="FAIL" (
    set /a FAIL_COUNT+=1
    echo   FAIL                  %R_NAME% -- %R_DETAIL%
    >> "%FAILURES_LOG%" echo   - %R_NAME%: %R_DETAIL%
) else if "%R_STATUS%"=="BLOCKED" (
    set /a BLOCKED_COUNT+=1
    echo   BLOCKED               %R_NAME% -- %R_DETAIL%
) else if "%R_STATUS%"=="NOT CONFIGURED" (
    set /a NOTCONFIGURED_COUNT+=1
    echo   NOT CONFIGURED        %R_NAME% -- %R_DETAIL%
) else (
    set /a NOTVERIFIED_COUNT+=1
    echo   NOT RUNTIME VERIFIED  %R_NAME% -- %R_DETAIL%
)
>> "%RESULTS_TXT%.rows" echo %R_STATUS%^|%R_NAME%^|%R_DETAIL%
goto :eof

:after_record

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo ENVIRONMENT
echo ======================================================================

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    for /f "delims=" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
    call :record PASS "python" "!PYVER!"
) else (
    call :record BLOCKED "python" "not found on PATH - required dependency unavailable for the entire backend"
)

where pip >nul 2>nul
if %ERRORLEVEL%==0 (
    call :record PASS "pip" "available on PATH"
) else (
    call :record BLOCKED "pip" "not found on PATH"
)

where node >nul 2>nul
if %ERRORLEVEL%==0 (
    for /f "delims=" %%v in ('node --version 2^>^&1') do set "NODEVER=%%v"
    call :record PASS "node" "!NODEVER!"
) else (
    call :record BLOCKED "node" "not found on PATH - required dependency unavailable for the frontend"
)

where npm >nul 2>nul
if %ERRORLEVEL%==0 (
    for /f "delims=" %%v in ('npm --version 2^>^&1') do set "NPMVER=%%v"
    call :record PASS "npm" "!NPMVER!"
) else (
    call :record BLOCKED "npm" "not found on PATH - required dependency unavailable for the frontend"
)

where docker >nul 2>nul
if %ERRORLEVEL%==0 (
    docker info >nul 2>nul
    if !ERRORLEVEL!==0 (
        call :record PASS "docker" "installed and daemon reachable"
    ) else (
        call :record "NOT CONFIGURED" "docker" "installed but daemon not running/reachable"
    )
) else (
    call :record "NOT CONFIGURED" "docker" "not found on PATH - Docker validation will be skipped"
)

if exist "backend\.env" (
    call :record PASS "backend\.env exists" "found"
    findstr /b /r "SECRET_KEY=.\+" backend\.env >nul 2>nul
    if !ERRORLEVEL!==0 (
        call :record PASS "  SECRET_KEY is set" "present (value not checked here)"
    ) else (
        call :record FAIL "  SECRET_KEY is set" "missing or empty in backend\.env"
    )
    findstr /b /r "DATABASE_URL=.\+" backend\.env >nul 2>nul
    if !ERRORLEVEL!==0 (
        call :record PASS "  DATABASE_URL is set" "present (value not checked here)"
    ) else (
        call :record FAIL "  DATABASE_URL is set" "missing or empty in backend\.env"
    )
) else (
    call :record FAIL "backend\.env exists" "not found - copy backend\.env.example and fill it in"
)

if exist "%BACKEND_VENV_PY%" (
    call :record PASS "backend venv" "found at backend\venv"
    "%BACKEND_VENV_PY%" -c "import sqlalchemy, pydantic, fastapi" 2>nul
    if !ERRORLEVEL!==0 (
        call :record PASS "backend core dependencies" "sqlalchemy/pydantic/fastapi importable"
        set "VENV_OK=true"
    ) else (
        call :record FAIL "backend core dependencies" "venv exists but one or more core packages not importable - run setup.bat again"
    )
) else (
    call :record BLOCKED "backend venv" "backend\venv not found - run setup.bat first; every check below that needs it is BLOCKED for the same reason"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo DEPENDENCY SECURITY AUDIT (pip-audit / npm audit)
echo ======================================================================

if exist "%BACKEND_VENV_PY%" (
    "%BACKEND_VENV_PY%" -m pip_audit --version >nul 2>nul
    if !ERRORLEVEL!==0 (
        pushd backend
        "venv\Scripts\python.exe" -m pip_audit -r requirements.txt > "%TEMP_DIR%\pip_audit.log" 2>&1
        set "PIP_AUDIT_EXIT=!ERRORLEVEL!"
        popd
        type "%TEMP_DIR%\pip_audit.log"
        if "!PIP_AUDIT_EXIT!"=="0" (
            call :record PASS "Backend dependency vulnerability scan (pip-audit)" "no known vulnerabilities found in requirements.txt"
        ) else (
            call :record FAIL "Backend dependency vulnerability scan (pip-audit)" "pip-audit reported findings above - review before deploying"
        )
    ) else (
        call :record BLOCKED "Backend dependency vulnerability scan (pip-audit)" "pip-audit not installed in backend\venv - install with: pip install pip-audit"
    )
) else (
    call :record BLOCKED "Backend dependency vulnerability scan (pip-audit)" "backend venv unavailable"
)

if exist "frontend\package-lock.json" (
    where npm >nul 2>nul
    if !ERRORLEVEL!==0 (
        pushd frontend
        call npm audit > "%TEMP_DIR%\npm_audit.log" 2>&1
        set "NPM_AUDIT_EXIT=!ERRORLEVEL!"
        popd
        type "%TEMP_DIR%\npm_audit.log"
        findstr /i /c:"ENOTFOUND" /c:"ETIMEDOUT" /c:"network" /c:"403" /c:"ECONNREFUSED" "%TEMP_DIR%\npm_audit.log" >nul 2>nul
        if !ERRORLEVEL!==0 (
            call :record BLOCKED "Frontend dependency vulnerability scan (npm audit)" "network unavailable to the npm registry/audit endpoint"
        ) else if "!NPM_AUDIT_EXIT!"=="0" (
            call :record PASS "Frontend dependency vulnerability scan (npm audit)" "no known vulnerabilities found"
        ) else (
            call :record FAIL "Frontend dependency vulnerability scan (npm audit)" "npm audit reported findings above - review before deploying (never run npm audit fix --force blindly)"
        )
    ) else (
        call :record BLOCKED "Frontend dependency vulnerability scan (npm audit)" "npm unavailable"
    )
) else (
    call :record BLOCKED "Frontend dependency vulnerability scan (npm audit)" "npm unavailable or frontend\package-lock.json missing"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo BACKEND: STARTUP, MAPPER CONFIGURATION, IMPORTS
echo ======================================================================

if "%VENV_OK%"=="true" (
    (
        echo from app.platform.database import Base, engine
        echo import app.models  # noqa: F401 - registers every model with Base's mapper registry
        echo from sqlalchemy.orm import configure_mappers
        echo try:
        echo     configure_mappers^(^)
        echo     print^('OK'^)
        echo except Exception:
        echo     print^('FAIL'^)
    ) > "%TEMP_DIR%\check_mappers.py"
    pushd backend
    for /f "delims=" %%r in ('"venv\Scripts\python.exe" "%TEMP_DIR%\check_mappers.py" 2^>nul') do set "MAPPER_RESULT=%%r"
    popd
    if "!MAPPER_RESULT!"=="OK" (
        call :record PASS "SQLAlchemy mapper configuration" "all models registered and configured cleanly"
    ) else (
        call :record FAIL "SQLAlchemy mapper configuration" "configure_mappers() raised - see backend logs"
    )

    pushd backend
    "venv\Scripts\python.exe" -c "import app.main" >"%TEMP_DIR%\import_main.log" 2>&1
    set "IMPORT_EXIT=!ERRORLEVEL!"
    popd
    if "!IMPORT_EXIT!"=="0" (
        call :record PASS "app.main imports cleanly" "no import-time errors"
    ) else (
        call :record FAIL "app.main imports cleanly" "import raised an exception - see %TEMP_DIR%\import_main.log"
    )

    REM Real startup: spawn uvicorn via PowerShell (native Windows, not
    REM WSL/Git Bash) so we get a real, trackable process ID to stop
    REM afterward, then make one real HTTP request against /health.
    powershell -NoProfile -Command ^
        "$p = Start-Process -FilePath '%BACKEND_VENV_PY%' -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8123' -WorkingDirectory '%SCRIPT_DIR%\backend' -PassThru -WindowStyle Hidden -RedirectStandardOutput '%TEMP_DIR%\uvicorn_out.log' -RedirectStandardError '%TEMP_DIR%\uvicorn_err.log';" ^
        "$p.Id | Out-File -Encoding ascii '%TEMP_DIR%\uvicorn.pid';" ^
        "$ok = $false;" ^
        "for ($i=0; $i -lt 20; $i++) {" ^
        "  Start-Sleep -Milliseconds 500;" ^
        "  try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8123/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { $ok = $true; break } } catch {}" ^
        "}" ^
        "if ($ok) { 'OK' | Out-File -Encoding ascii '%TEMP_DIR%\health.result' } else { 'FAIL' | Out-File -Encoding ascii '%TEMP_DIR%\health.result' }"
    set "HEALTH_RESULT=FAIL"
    if exist "%TEMP_DIR%\health.result" (
        for /f "delims=" %%h in ('type "%TEMP_DIR%\health.result"') do set "HEALTH_RESULT=%%h"
    )
    if "!HEALTH_RESULT!"=="OK" (
        call :record PASS "Backend startup + /health" "responded within 10s"
    ) else (
        call :record FAIL "Backend startup + /health" "did not respond within 10s - see %TEMP_DIR%\uvicorn_err.log"
    )
    if exist "%TEMP_DIR%\uvicorn.pid" (
        for /f "delims=" %%i in ('type "%TEMP_DIR%\uvicorn.pid"') do (
            powershell -NoProfile -Command "Stop-Process -Id %%i -Force -ErrorAction SilentlyContinue" >nul 2>nul
        )
    )
) else (
    call :record BLOCKED "SQLAlchemy mapper configuration" "backend venv/dependencies unavailable"
    call :record BLOCKED "app.main imports cleanly" "backend venv/dependencies unavailable"
    call :record BLOCKED "Backend startup + /health" "backend venv/dependencies unavailable"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo LOCAL/MOCK CHECKS (scripts\verify.py - migrations chain, Excel, chatbot, email, runtime safety)
echo ======================================================================

REM The chain-integrity check within verify_migrations.py is pure Python
REM with no third-party dependencies - it can genuinely run even without
REM the venv, so it always runs on its own regardless of VENV_OK.
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    pushd backend
    python scripts\verify_migrations.py chain > "%TEMP_DIR%\chain.log" 2>&1
    popd
    findstr /c:"PASS" "%TEMP_DIR%\chain.log" >nul 2>nul
    if !ERRORLEVEL!==0 (
        for /f "delims=" %%l in ('findstr /c:"Chain integrity" "%TEMP_DIR%\chain.log"') do set "CHAIN_LINE=%%l"
        call :record PASS "Migration chain integrity" "!CHAIN_LINE!"
    ) else (
        call :record FAIL "Migration chain integrity" "chain integrity check failed - see %TEMP_DIR%\chain.log"
    )
) else (
    call :record BLOCKED "Migration chain integrity" "python unavailable"
)

if "%VENV_OK%"=="true" (
    if exist "backend\scripts\verify.py" (
        pushd backend
        "venv\Scripts\python.exe" scripts\verify.py > "%TEMP_DIR%\verify_py.log" 2>&1
        set "VERIFY_PY_EXIT=!ERRORLEVEL!"
        popd
        type "%TEMP_DIR%\verify_py.log"
        if "!VERIFY_PY_EXIT!"=="0" (
            call :record PASS "scripts\verify.py (Excel/chatbot/email/runtime-safety)" "see output above for the per-check breakdown"
        ) else (
            call :record FAIL "scripts\verify.py (Excel/chatbot/email/runtime-safety)" "one or more local checks failed - see output above"
        )
    ) else (
        call :record BLOCKED "scripts\verify.py (Excel/chatbot/email/runtime-safety)" "backend\scripts\verify.py does not exist in this repository"
    )
) else (
    call :record BLOCKED "scripts\verify.py (Excel/chatbot/email/runtime-safety)" "backend venv/dependencies unavailable"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo DATABASE: NEON CONNECTIVITY
echo ======================================================================

set "NEON_CONFIGURED=false"
if exist "backend\.env" (
    findstr /b /r "DATABASE_URL=postgres" backend\.env >nul 2>nul
    if !ERRORLEVEL!==0 set "NEON_CONFIGURED=true"
)

if "%NEON_CONFIGURED%"=="false" (
    call :record "NOT CONFIGURED" "Neon connectivity + SELECT 1" "DATABASE_URL in backend\.env is not a postgres:// URL - this environment is not pointed at Neon (SQLite is fine for local dev, but is never a substitute for this check)"
) else if "%VENV_OK%"=="false" (
    call :record BLOCKED "Neon connectivity + SELECT 1" "DATABASE_URL is postgres but the backend venv/dependencies are unavailable to attempt the connection"
) else (
    pushd backend
    "venv\Scripts\python.exe" scripts\verify_migrations.py neon-connection > "%TEMP_DIR%\neon.log" 2>&1
    popd
    findstr /i /c:"PASS" "%TEMP_DIR%\neon.log" >nul 2>nul
    if !ERRORLEVEL!==0 (
        call :record PASS "Neon connectivity + SELECT 1" "connected successfully"
    ) else (
        call :record "NOT RUNTIME VERIFIED" "Neon connectivity + SELECT 1" "configured but the live connection could not be completed here"
    )
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo REDIS (production shared rate limiting)
echo ======================================================================

set "REDIS_CONFIGURED=false"
if exist "backend\.env" (
    findstr /b /r "RATE_LIMIT_BACKEND=redis" backend\.env >nul 2>nul
    if !ERRORLEVEL!==0 (
        findstr /b /r "REDIS_URL=.\+" backend\.env >nul 2>nul
        if !ERRORLEVEL!==0 set "REDIS_CONFIGURED=true"
    )
)

if "%REDIS_CONFIGURED%"=="false" (
    call :record "NOT CONFIGURED" "Redis connectivity (PING)" "RATE_LIMIT_BACKEND is not redis, or REDIS_URL is unset - this environment is not configured to use shared rate limiting"
) else if "%VENV_OK%"=="false" (
    call :record BLOCKED "Redis connectivity (PING)" "Redis is configured but the backend venv/dependencies are unavailable to attempt the connection"
) else (
    (
        echo import redis
        echo from app.platform.config import settings
        echo try:
        echo     client = redis.from_url^(settings.REDIS_URL, socket_connect_timeout=3^)
        echo     print^('OK' if client.ping^(^) else 'FAIL'^)
        echo except Exception:
        echo     print^('FAIL'^)
    ) > "%TEMP_DIR%\check_redis.py"
    pushd backend
    for /f "delims=" %%r in ('"venv\Scripts\python.exe" "%TEMP_DIR%\check_redis.py" 2^>nul') do set "REDIS_RESULT=%%r"
    popd
    if "!REDIS_RESULT!"=="OK" (
        call :record PASS "Redis connectivity (PING)" "connected and responded to PING"
    ) else (
        call :record "NOT RUNTIME VERIFIED" "Redis connectivity (PING)" "configured but the live connection could not be completed here"
    )
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo GOOGLE DRIVE
echo ======================================================================

set "DRIVE_CONFIGURED=false"
if exist "backend\.env" (
    findstr /b /r "STORAGE_PROVIDER=drive" backend\.env >nul 2>nul
    if !ERRORLEVEL!==0 (
        findstr /b /r /i "GOOGLE_DRIVE_ENABLED=[Tt]rue" backend\.env >nul 2>nul
        if !ERRORLEVEL!==0 (
            findstr /b /r "GOOGLE_DRIVE_CREDENTIALS_PATH=.\+" backend\.env >nul 2>nul
            if !ERRORLEVEL!==0 set "DRIVE_CONFIGURED=true"
        )
    )
)

if "%DRIVE_CONFIGURED%"=="false" (
    call :record "NOT CONFIGURED" "Drive upload/exists/read/delete" "STORAGE_PROVIDER/GOOGLE_DRIVE_ENABLED/CREDENTIALS_PATH not all set - Drive is not the active storage provider in this environment"
) else if "%VENV_OK%"=="false" (
    call :record BLOCKED "Drive upload/exists/read/delete" "Drive is configured but the backend venv/dependencies are unavailable to attempt it"
) else (
    (
        echo from app.platform.storage import get_storage_backend
        echo try:
        echo     backend = get_storage_backend^(^)
        echo     ref = backend.save^('woodful_verify_probe.txt', b'woodful verification probe'^)
        echo     assert backend.exists^(ref^)
        echo     data = backend.read^(ref^)
        echo     assert data == b'woodful verification probe'
        echo     backend.delete^(ref^)
        echo     assert not backend.exists^(ref^)
        echo     print^('OK'^)
        echo except Exception:
        echo     print^('FAIL'^)
    ) > "%TEMP_DIR%\check_drive.py"
    pushd backend
    for /f "delims=" %%r in ('"venv\Scripts\python.exe" "%TEMP_DIR%\check_drive.py" 2^>nul') do set "DRIVE_RESULT=%%r"
    popd
    if "!DRIVE_RESULT!"=="OK" (
        call :record PASS "Drive upload/exists/read/delete" "full round-trip succeeded"
    ) else (
        call :record "NOT RUNTIME VERIFIED" "Drive upload/exists/read/delete" "configured but the live round-trip could not be completed here"
    )
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo GEMINI
echo ======================================================================

if "%VENV_OK%"=="true" (
    (
        echo from app.modules.ai.gateway import _extract_and_redact_amount, _redact_outbound_message
        echo try:
        echo     redacted, amount = _extract_and_redact_amount^('Record Rs 50,000 payment for WC-2026-003'^)
        echo     assert amount == 50000.0
        echo     assert '50,000' not in redacted and '50000' not in redacted
        echo     assert 'WC-2026-003' in redacted
        echo     fully_redacted = _redact_outbound_message^(redacted^)
        echo     assert '50,000' not in fully_redacted and '50000' not in fully_redacted
        echo     print^('OK'^)
        echo except Exception:
        echo     print^('FAIL'^)
    ) > "%TEMP_DIR%\check_dlp.py"
    pushd backend
    for /f "delims=" %%r in ('"venv\Scripts\python.exe" "%TEMP_DIR%\check_dlp.py" 2^>nul') do set "DLP_RESULT=%%r"
    popd
    if "!DLP_RESULT!"=="OK" (
        call :record PASS "Gemini financial-amount redaction (local, no API)" "confirmed a real amount is extracted locally and never appears in the sanitized outbound text"
    ) else (
        call :record FAIL "Gemini financial-amount redaction (local, no API)" "redaction check raised or asserted false - see backend logs"
    )
) else (
    call :record BLOCKED "Gemini financial-amount redaction (local, no API)" "backend venv/dependencies unavailable"
)

set "GEMINI_CONFIGURED=false"
if exist "backend\.env" (
    findstr /b /r /i "GEMINI_ENABLED=[Tt]rue" backend\.env >nul 2>nul
    if !ERRORLEVEL!==0 (
        findstr /b /r "GEMINI_API_KEY=.\+" backend\.env >nul 2>nul
        if !ERRORLEVEL!==0 set "GEMINI_CONFIGURED=true"
    )
)

if "%GEMINI_CONFIGURED%"=="false" (
    call :record "NOT CONFIGURED" "Gemini live connectivity (safe request)" "GEMINI_ENABLED is not True, or GEMINI_API_KEY is unset - Gemini is not enabled in this environment"
) else if "%VENV_OK%"=="false" (
    call :record BLOCKED "Gemini live connectivity (safe request)" "Gemini is configured but the backend venv/dependencies are unavailable to attempt it"
) else (
    (
        echo from app.platform.database import SessionLocal
        echo from app.modules.ai.gateway import handle_message
        echo db = SessionLocal^(^)
        echo try:
        echo     result = handle_message^('what materials are running low on stock?', db=db, user_role='master'^)
        echo     print^('OK' if result is not None else 'FAIL'^)
        echo except Exception:
        echo     print^('FAIL'^)
        echo finally:
        echo     db.close^(^)
    ) > "%TEMP_DIR%\check_gemini.py"
    pushd backend
    for /f "delims=" %%r in ('"venv\Scripts\python.exe" "%TEMP_DIR%\check_gemini.py" 2^>nul') do set "GEMINI_RESULT=%%r"
    popd
    if "!GEMINI_RESULT!"=="OK" (
        call :record PASS "Gemini live connectivity (safe request)" "received a response"
    ) else (
        call :record "NOT RUNTIME VERIFIED" "Gemini live connectivity (safe request)" "configured but the live request could not be completed here"
    )
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo EMAIL
echo ======================================================================

set "SMTP_CONFIGURED=false"
if exist "backend\.env" (
    findstr /b /r "SENDER_EMAIL=.\+" backend\.env >nul 2>nul
    if !ERRORLEVEL!==0 (
        findstr /b /r "SENDER_PASSWORD=.\+" backend\.env >nul 2>nul
        if !ERRORLEVEL!==0 set "SMTP_CONFIGURED=true"
    )
)

if "%SMTP_CONFIGURED%"=="false" (
    call :record "NOT CONFIGURED" "SMTP controlled test send" "SENDER_EMAIL/SENDER_PASSWORD not set in backend\.env - email sending is not configured in this environment"
) else if "%VENV_OK%"=="false" (
    call :record BLOCKED "SMTP controlled test send" "SMTP is configured but the backend venv/dependencies are unavailable to attempt it"
) else (
    echo.
    set /p "TEST_EMAIL_TO=  Send one controlled test email now? Enter a recipient address, or leave blank to skip: "
    if "!TEST_EMAIL_TO!"=="" (
        call :record "NOT RUNTIME VERIFIED" "SMTP controlled test send" "configured, but skipped - no recipient entered for this run"
    ) else (
        (
            echo from app.modules.communications.services import EmailService
            echo try:
            echo     ok = EmailService^(^).send_email^('!TEST_EMAIL_TO!', 'Woodful verification test', '^<p^>This is a controlled test send from woodful_full_verification.bat.^</p^>', is_html=True^)
            echo     print^('OK' if ok else 'FAIL'^)
            echo except Exception:
            echo     print^('FAIL'^)
        ) > "%TEMP_DIR%\check_smtp.py"
        pushd backend
        for /f "delims=" %%r in ('"venv\Scripts\python.exe" "%TEMP_DIR%\check_smtp.py" 2^>nul') do set "SMTP_RESULT=%%r"
        popd
        if "!SMTP_RESULT!"=="OK" (
            call :record PASS "SMTP controlled test send" "sent to the address you entered - confirm it arrived"
        ) else (
            call :record "NOT RUNTIME VERIFIED" "SMTP controlled test send" "configured but the live send could not be completed here"
        )
    )
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo FRONTEND: DEPENDENCY STATE
echo ======================================================================

set "LOCKFILE_OK=false"
where node >nul 2>nul
if %ERRORLEVEL%==0 (
    (
        echo const pkg = require^('./package.json'^);
        echo const lock = require^('./package-lock.json'^);
        echo const deps = Object.assign^({}, pkg.dependencies ^|^| {}, pkg.devDependencies ^|^| {}^);
        echo const missing = Object.keys^(deps^).filter^(name =^> !lock.packages ^|^| !lock.packages['node_modules/' + name]^);
        echo if ^(missing.length^) { console.log^('MISMATCH: ' + missing.join^(', '^) + ' declared in package.json but not present in package-lock.json'^); } else { console.log^('OK'^); }
    ) > "%TEMP_DIR%\check_lock.js"
    pushd frontend
    for /f "delims=" %%r in ('node "%TEMP_DIR%\check_lock.js" 2^>^&1') do set "LOCK_RESULT=%%r"
    popd
    if "!LOCK_RESULT!"=="OK" (
        set "LOCKFILE_OK=true"
        call :record PASS "package.json / package-lock.json consistency" "every declared dependency has a lockfile entry"
    ) else (
        call :record FAIL "package.json / package-lock.json consistency" "!LOCK_RESULT! - regenerate with npm in a network-enabled environment; never hand-edit the lockfile"
    )
) else (
    call :record BLOCKED "package.json / package-lock.json consistency" "node not found on PATH"
)

where npm >nul 2>nul
if %ERRORLEVEL%==0 (
    if "%LOCKFILE_OK%"=="false" (
        call :record BLOCKED "npm ci (clean install)" "package-lock.json is inconsistent with package.json (see above) - npm ci would refuse to run"
    ) else (
        pushd frontend
        call npm ci > "%TEMP_DIR%\npm_ci.log" 2>&1
        set "NPM_CI_EXIT=!ERRORLEVEL!"
        popd
        if "!NPM_CI_EXIT!"=="0" (
            call :record PASS "npm ci (clean install)" "clean install succeeded"
        ) else (
            findstr /i /c:"ENOTFOUND" /c:"ETIMEDOUT" /c:"network" /c:"403" /c:"ECONNREFUSED" "%TEMP_DIR%\npm_ci.log" >nul 2>nul
            if !ERRORLEVEL!==0 (
                call :record BLOCKED "npm ci (clean install)" "network unavailable to the npm registry - see %TEMP_DIR%\npm_ci.log"
            ) else (
                call :record FAIL "npm ci (clean install)" "see %TEMP_DIR%\npm_ci.log for details"
            )
        )
    )
) else (
    call :record BLOCKED "npm ci (clean install)" "npm not found on PATH"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo FRONTEND: TESTS AND BUILD
echo ======================================================================

where npm >nul 2>nul
if %ERRORLEVEL%==0 (
    if exist "frontend\node_modules" (
        pushd frontend
        set "CI=true"
        call npm test > "%TEMP_DIR%\npm_test.log" 2>&1
        set "TEST_EXIT=!ERRORLEVEL!"
        popd
        if "!TEST_EXIT!"=="0" (
            call :record PASS "Frontend tests" "see %TEMP_DIR%\npm_test.log for the full run"
        ) else (
            call :record FAIL "Frontend tests" "see %TEMP_DIR%\npm_test.log for details"
        )

        pushd frontend
        call npm run build > "%TEMP_DIR%\npm_build.log" 2>&1
        set "BUILD_EXIT=!ERRORLEVEL!"
        popd
        if "!BUILD_EXIT!"=="0" (
            call :record PASS "Frontend production build" "build succeeded"
        ) else (
            call :record FAIL "Frontend production build" "see %TEMP_DIR%\npm_build.log for details"
        )
    ) else (
        call :record BLOCKED "Frontend tests" "frontend\node_modules missing - run npm ci first"
        call :record BLOCKED "Frontend production build" "frontend\node_modules missing - run npm ci first"
    )
) else (
    call :record BLOCKED "Frontend tests" "npm not found on PATH"
    call :record BLOCKED "Frontend production build" "npm not found on PATH"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo BROWSER / MOBILE WEB (responsive layout, not a native app)
echo ======================================================================

set "PLAYWRIGHT_FOUND=false"
if exist "frontend\node_modules\@playwright" set "PLAYWRIGHT_FOUND=true"

if "%PLAYWRIGHT_FOUND%"=="true" (
    where npx >nul 2>nul
    if !ERRORLEVEL!==0 (
        pushd frontend
        call npx playwright test > "%TEMP_DIR%\playwright.log" 2>&1
        set "PW_EXIT=!ERRORLEVEL!"
        popd
        if "!PW_EXIT!"=="0" (
            call :record PASS "Playwright browser/responsive tests" "see %TEMP_DIR%\playwright.log"
        ) else (
            call :record FAIL "Playwright browser/responsive tests" "see %TEMP_DIR%\playwright.log for details"
        )
    ) else (
        call :record BLOCKED "Playwright browser/responsive tests" "npx not found on PATH"
    )
) else (
    call :record "NOT CONFIGURED" "Playwright browser/responsive tests" "no Playwright spec exists in this repo yet - mobile web readiness (desktop/tablet/mobile browser, not a native app) has not been automated. MANUAL VERIFICATION REQUIRED: open the built frontend at 320/375/414/768/1024px and confirm navigation, tables, forms, and modals stay usable."
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo BACKEND TEST SUITE
echo ======================================================================

set "PYTEST_OK=false"
if "%VENV_OK%"=="true" (
    "%BACKEND_VENV_PY%" -c "import pytest" 2>nul
    if !ERRORLEVEL!==0 set "PYTEST_OK=true"
)

if "%PYTEST_OK%"=="true" (
    pushd backend
    "venv\Scripts\python.exe" -m pytest tests\ -q > "%TEMP_DIR%\pytest_full.log" 2>&1
    set "PYTEST_EXIT=!ERRORLEVEL!"
    popd
    for /f "delims=" %%l in ('powershell -NoProfile -Command "(Get-Content '%TEMP_DIR%\pytest_full.log' | Select-Object -Last 1)"') do set "PYTEST_SUMMARY=%%l"
    if "!PYTEST_EXIT!"=="0" (
        call :record PASS "Backend test suite (pytest)" "!PYTEST_SUMMARY!"
    ) else (
        call :record FAIL "Backend test suite (pytest)" "!PYTEST_SUMMARY!"
    )
) else (
    call :record BLOCKED "Backend test suite (pytest)" "pytest and/or backend venv/dependencies unavailable"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo AUTHENTICATION
echo ======================================================================

if "%PYTEST_OK%"=="true" (
    pushd backend
    "venv\Scripts\python.exe" -m pytest tests\ -k "test_login" -q > "%TEMP_DIR%\pytest_auth.log" 2>&1
    set "AUTH_EXIT=!ERRORLEVEL!"
    popd
    findstr /c:"no tests ran" /c:"collected 0 items" "%TEMP_DIR%\pytest_auth.log" >nul 2>nul
    if !ERRORLEVEL!==0 (
        call :record "NOT CONFIGURED" "Authentication (login/failure/logout/session)" "no matching tests found under this name"
    ) else (
        for /f "delims=" %%l in ('powershell -NoProfile -Command "(Get-Content '%TEMP_DIR%\pytest_auth.log' | Select-Object -Last 1)"') do set "AUTH_SUMMARY=%%l"
        if "!AUTH_EXIT!"=="0" (
            call :record PASS "Authentication (login/failure/logout/session)" "!AUTH_SUMMARY!"
        ) else (
            call :record FAIL "Authentication (login/failure/logout/session)" "!AUTH_SUMMARY!"
        )
    )
) else (
    call :record BLOCKED "Authentication (login/failure/logout/session)" "pytest and/or backend venv/dependencies unavailable"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo AUTHORIZATION / RBAC / IDOR
echo ======================================================================

if "%PYTEST_OK%"=="true" (
    dir /s /b "backend\tests\*rbac*.py" >nul 2>nul
    if !ERRORLEVEL!==0 (
        pushd backend
        "venv\Scripts\python.exe" -m pytest tests\ -k "rbac" -q > "%TEMP_DIR%\pytest_rbac.log" 2>&1
        set "AUTHZ_EXIT=!ERRORLEVEL!"
        popd
        for /f "delims=" %%l in ('powershell -NoProfile -Command "(Get-Content '%TEMP_DIR%\pytest_rbac.log' | Select-Object -Last 1)"') do set "AUTHZ_SUMMARY=%%l"
        if "!AUTHZ_EXIT!"=="0" (
            call :record PASS "Authorization (MASTER/USER, financial/HR redaction)" "!AUTHZ_SUMMARY!"
        ) else (
            call :record FAIL "Authorization (MASTER/USER, financial/HR redaction)" "!AUTHZ_SUMMARY!"
        )
    ) else (
        call :record "NOT CONFIGURED" "Authorization (MASTER/USER, financial/HR redaction)" "no *rbac*.py test files found"
    )

    pushd backend
    "venv\Scripts\python.exe" -m pytest tests\ -k "mismatched or cannot_view_another or cannot_download_another" -q > "%TEMP_DIR%\pytest_idor.log" 2>&1
    set "IDOR_EXIT=!ERRORLEVEL!"
    popd
    findstr /c:"no tests ran" /c:"collected 0 items" "%TEMP_DIR%\pytest_idor.log" >nul 2>nul
    if !ERRORLEVEL!==0 (
        call :record "NOT CONFIGURED" "IDOR (identifier substitution rejected)" "no matching tests found under this name"
    ) else (
        for /f "delims=" %%l in ('powershell -NoProfile -Command "(Get-Content '%TEMP_DIR%\pytest_idor.log' | Select-Object -Last 1)"') do set "IDOR_SUMMARY=%%l"
        if "!IDOR_EXIT!"=="0" (
            call :record PASS "IDOR (identifier substitution rejected)" "!IDOR_SUMMARY!"
        ) else (
            call :record FAIL "IDOR (identifier substitution rejected)" "!IDOR_SUMMARY!"
        )
    )
) else (
    call :record BLOCKED "Authorization (MASTER/USER, financial/HR redaction)" "pytest and/or backend venv/dependencies unavailable"
    call :record BLOCKED "IDOR (identifier substitution rejected)" "pytest and/or backend venv/dependencies unavailable"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo DOCUMENT / STORAGE ACCESS CONTROL
echo ======================================================================

if "%PYTEST_OK%"=="true" (
    set "STORAGE_FOUND=false"
    dir /s /b "backend\tests\*storage*.py" >nul 2>nul && set "STORAGE_FOUND=true"
    dir /s /b "backend\tests\*document*.py" >nul 2>nul && set "STORAGE_FOUND=true"
    if "!STORAGE_FOUND!"=="true" (
        pushd backend
        "venv\Scripts\python.exe" -m pytest tests\ -k "storage or document" -q > "%TEMP_DIR%\pytest_storage.log" 2>&1
        set "STORAGE_EXIT=!ERRORLEVEL!"
        popd
        for /f "delims=" %%l in ('powershell -NoProfile -Command "(Get-Content '%TEMP_DIR%\pytest_storage.log' | Select-Object -Last 1)"') do set "STORAGE_SUMMARY=%%l"
        if "!STORAGE_EXIT!"=="0" (
            call :record PASS "Storage/document (upload/reference/retrieval/deletion, access control)" "!STORAGE_SUMMARY!"
        ) else (
            call :record FAIL "Storage/document (upload/reference/retrieval/deletion, access control)" "!STORAGE_SUMMARY!"
        )
    ) else (
        call :record "NOT CONFIGURED" "Storage/document (upload/reference/retrieval/deletion, access control)" "no storage/document test files found"
    )
) else (
    call :record BLOCKED "Storage/document (upload/reference/retrieval/deletion, access control)" "pytest and/or backend venv/dependencies unavailable"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo PRODUCTION CONFIGURATION SAFETY (static checks only)
echo ======================================================================

if not exist "backend\.env" (
    call :record BLOCKED "DEBUG disabled in production" "backend\.env not found - nothing to check"
    call :record BLOCKED "CORS not wildcarded" "backend\.env not found - nothing to check"
) else (
    findstr /b /r "ENVIRONMENT=production" backend\.env >nul 2>nul
    if !ERRORLEVEL! neq 0 (
        call :record "NOT CONFIGURED" "DEBUG disabled in production" "ENVIRONMENT is not set to production in this .env"
        call :record "NOT CONFIGURED" "CORS not wildcarded" "ENVIRONMENT is not set to production in this .env"
    ) else (
        findstr /b /r /i "DEBUG=[Tt]rue" backend\.env >nul 2>nul
        if !ERRORLEVEL!==0 (
            call :record FAIL "DEBUG disabled in production" "ENVIRONMENT=production but DEBUG=True - this exposes stack traces"
        ) else (
            call :record PASS "DEBUG disabled in production" "DEBUG is not True"
        )
        findstr /b /r "CORS_ORIGINS=.*\*" backend\.env >nul 2>nul
        if !ERRORLEVEL!==0 (
            call :record FAIL "CORS not wildcarded" "CORS_ORIGINS contains a wildcard in production"
        ) else (
            call :record PASS "CORS not wildcarded" "no wildcard found"
        )
    )
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo STALE REFERENCE CHECK
echo ======================================================================
REM Confirms this verification runner itself, and the repository it is
REM checking, contain no leftover references to the pre-reorg locations.

set "STALE_FOUND=false"
findstr /s /m /c:"backend/main.py" /c:"backend\main.py" *.md *.bat *.sh *.py *.yml *.yaml 2>nul | findstr /v /i "woodful_full_verification node_modules" >nul 2>nul
if !ERRORLEVEL!==0 set "STALE_FOUND=true"

if "%STALE_FOUND%"=="false" (
    call :record PASS "Stale root-path references" "no references found to backend/main.py, database/, root package.json/package-lock.json, or old core/ paths"
) else (
    call :record FAIL "Stale root-path references" "found a stale reference - see console output above from findstr"
)

REM ----------------------------------------------------------------------
echo.
echo ======================================================================
echo SUMMARY
echo ======================================================================

echo Total checks:            %TOTAL%
echo PASS:                    %PASS_COUNT%
echo FAIL:                    %FAIL_COUNT%
echo BLOCKED:                 %BLOCKED_COUNT%
echo NOT CONFIGURED:          %NOTCONFIGURED_COUNT%
echo NOT RUNTIME VERIFIED:    %NOTVERIFIED_COUNT%
echo.

if %FAIL_COUNT% GTR 0 (
    echo Critical failures:
    type "%FAILURES_LOG%"
    echo.
    set "FINAL_STATUS=NOT READY"
) else (
    set "FINAL_STATUS=READY"
)

if %BLOCKED_COUNT% GTR 0 (
    echo Note: %BLOCKED_COUNT% BLOCKED, %NOTCONFIGURED_COUNT% NOT CONFIGURED, %NOTVERIFIED_COUNT% NOT RUNTIME VERIFIED ^(see entries above^).
    echo A status of READY reflects only that no check which actually ran found a real
    echo problem - it is not a claim that BLOCKED/NOT CONFIGURED/NOT RUNTIME VERIFIED
    echo items are safe to assume working, and it is never a claim of production
    echo readiness for infrastructure this script could not reach ^(Neon/Redis/Drive/
    echo SMTP/Gemini^) or for mobile web layout, which needs real browser verification.
)

echo.
echo FINAL STATUS: %FINAL_STATUS%
echo ======================================================================

REM ----------------------------------------------------------------------
REM Write result files
REM ----------------------------------------------------------------------

(
    echo Woodful Creations - Verification Results ^(Windows^)
    echo Run at: %DATE% %TIME%
    echo.
    for /f "usebackq tokens=1-3 delims=|" %%a in ("%RESULTS_TXT%.rows") do echo %%~a %%~b -- %%~c
    echo.
    echo Total: %TOTAL% ^| PASS: %PASS_COUNT% ^| FAIL: %FAIL_COUNT% ^| BLOCKED: %BLOCKED_COUNT% ^| NOT CONFIGURED: %NOTCONFIGURED_COUNT% ^| NOT RUNTIME VERIFIED: %NOTVERIFIED_COUNT%
    echo FINAL STATUS: %FINAL_STATUS%
) > "%RESULTS_TXT%"

powershell -NoProfile -Command ^
    "$rows = Get-Content '%RESULTS_TXT%.rows' | ForEach-Object { $p = $_ -split '\|',3; [PSCustomObject]@{status=$p[0]; name=$p[1]; detail=$p[2]} };" ^
    "$result = [PSCustomObject]@{run_at=(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'); final_status='%FINAL_STATUS%'; total=%TOTAL%; pass=%PASS_COUNT%; fail=%FAIL_COUNT%; blocked=%BLOCKED_COUNT%; not_configured=%NOTCONFIGURED_COUNT%; not_runtime_verified=%NOTVERIFIED_COUNT%; checks=$rows};" ^
    "$result | ConvertTo-Json -Depth 4 | Out-File -Encoding utf8 '%RESULTS_JSON%'"

powershell -NoProfile -Command ^
    "$rows = Get-Content '%RESULTS_TXT%.rows' | ForEach-Object { $p = $_ -split '\|',3; \"<tr><td class='$($p[0] -replace ' ','')'>$($p[0])</td><td>$($p[1])</td><td>$($p[2])</td></tr>\" };" ^
    "$html = \"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Woodful Verification Results</title>\" +" ^
    "\"<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}table{width:100%%;border-collapse:collapse}td,th{padding:.5rem;border-bottom:1px solid #ddd;text-align:left}.PASS{color:#1a7f37}.FAIL{color:#cf222e;font-weight:600}.BLOCKED{color:#9a6700}.NOTCONFIGURED{color:#0969da}.NOTRUNTIMEVERIFIED{color:#8250df}</style></head><body>\" +" ^
    "\"<h1>Woodful Creations - Verification Results</h1><p>Run at: $(Get-Date)</p>\" +" ^
    "\"<p><strong>Final status: %FINAL_STATUS%</strong> (%PASS_COUNT% PASS / %FAIL_COUNT% FAIL / %BLOCKED_COUNT% BLOCKED / %NOTCONFIGURED_COUNT% NOT CONFIGURED / %NOTVERIFIED_COUNT% NOT RUNTIME VERIFIED of %TOTAL%)</p>\" +" ^
    "\"<table><tr><th>Status</th><th>Check</th><th>Detail</th></tr>\" + ($rows -join '') + \"</table></body></html>\";" ^
    "$html | Out-File -Encoding utf8 '%RESULTS_HTML%'"

del "%RESULTS_TXT%.rows" >nul 2>nul
rmdir /s /q "%TEMP_DIR%" >nul 2>nul

echo.
echo Results written to:
echo   %RESULTS_TXT%
echo   %RESULTS_JSON%
echo   %RESULTS_HTML%

endlocal
if "%FINAL_STATUS%"=="READY" (
    exit /b 0
) else (
    exit /b 1
)
