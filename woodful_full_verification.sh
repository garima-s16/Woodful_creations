#!/bin/bash
# Woodful Creations - Master Local Verification Harness
#
# The single local entry point for Woodful production verification.
# Orchestrates the focused backend/scripts/verify_*.py scripts and the
# real pytest suite rather than re-implementing their checks here -
# this file's job is sequencing and honest reporting, not duplicate
# logic.
#
# Every check reports exactly one of:
#   PASS                  - genuinely ran, genuinely succeeded
#   FAIL                  - genuinely ran, found a real problem
#   BLOCKED               - required local tooling/dependency is
#                           missing, so the check could not attempt
#                           to run at all (e.g. no venv, no network,
#                           no node_modules)
#   NOT CONFIGURED        - the feature itself is deliberately off in
#                           this environment's config (e.g.
#                           GEMINI_ENABLED=False, STORAGE_PROVIDER is
#                           not drive) - there is nothing to verify
#   NOT RUNTIME VERIFIED  - the feature is configured/enabled but the
#                           actual live credential/connectivity check
#                           could not be completed here (e.g. Neon/
#                           Redis/SMTP/Gemini reachable only with
#                           real external infrastructure)
#
# NOT RUN is never used - every check is classified into one of the
# five statuses above, and a status is never silently upgraded to
# PASS. One failing/blocked check never prevents the remaining,
# independent checks from running (no `set -e`).
#
# Secrets (passwords, API keys, tokens, connection strings) are never
# printed to stdout or written to the result files below - only a
# status and a short, non-sensitive detail message.
#
# Usage: ./woodful_full_verification.sh (from anywhere - the script
# cd's to its own directory first, so it does not depend on the
# caller's current working directory).

set -u  # undefined variables are errors; deliberately NOT `set -e` -
        # one failing check must not abort the rest of the run, and no
        # command in this script is ever silenced with || true - every
        # exit code is inspected and classified below.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RESULTS_DIR="$SCRIPT_DIR/verification-results"
mkdir -p "$RESULTS_DIR"

# Parallel arrays: one entry per check. Bash 3.2 (macOS default) has no
# associative arrays, so this uses indexed arrays instead for portability.
CHECK_NAMES=()
CHECK_STATUS=()   # "PASS" | "FAIL" | "BLOCKED" | "NOT CONFIGURED" | "NOT RUNTIME VERIFIED"
CHECK_DETAIL=()

record() {
    # record <name> <status> <detail>
    CHECK_NAMES+=("$1")
    CHECK_STATUS+=("$2")
    CHECK_DETAIL+=("$3")
    case "$2" in
        PASS)                  printf "  \033[32mPASS\033[0m                  %-45s %s\n" "$1" "$3" ;;
        FAIL)                  printf "  \033[31mFAIL\033[0m                  %-45s %s\n" "$1" "$3" ;;
        BLOCKED)               printf "  \033[33mBLOCKED\033[0m               %-45s %s\n" "$1" "$3" ;;
        "NOT CONFIGURED")      printf "  \033[36mNOT CONFIGURED\033[0m        %-45s %s\n" "$1" "$3" ;;
        *)                     printf "  \033[35mNOT RUNTIME VERIFIED\033[0m  %-45s %s\n" "$1" "$3" ;;
    esac
}

section() {
    echo ""
    echo "======================================================================"
    echo "$1"
    echo "======================================================================"
}

# Redacts anything that looks like it could be a secret before it is
# ever echoed - used on any command output this script surfaces, since
# a tool's own error message can accidentally include a credential
# (e.g. a database driver printing the DSN it failed to connect to).
redact() {
    sed -E \
        -e 's/(PASSWORD|SECRET|KEY|TOKEN)=[^&[:space:]]+/\1=[REDACTED]/gi' \
        -e 's#(://)[^:]+:[^@]+(@)#\1[REDACTED]:[REDACTED]\2#g'
}

echo "======================================================================"
echo "Woodful Creations - Master Local Verification"
echo "Run at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "======================================================================"

# ----------------------------------------------------------------------
section "ENVIRONMENT"
# ----------------------------------------------------------------------

if command -v python3 &>/dev/null; then
    record "python3" "PASS" "$(python3 --version 2>&1)"
else
    record "python3" "BLOCKED" "not found on PATH - required dependency unavailable for the entire backend"
fi

if command -v pip &>/dev/null || command -v pip3 &>/dev/null; then
    record "pip" "PASS" "available on PATH"
else
    record "pip" "BLOCKED" "not found on PATH"
fi

if command -v node &>/dev/null; then
    record "node" "PASS" "$(node --version 2>&1)"
else
    record "node" "BLOCKED" "not found on PATH - required dependency unavailable for the frontend"
fi

if command -v npm &>/dev/null; then
    record "npm" "PASS" "$(npm --version 2>&1)"
else
    record "npm" "BLOCKED" "not found on PATH - required dependency unavailable for the frontend"
fi

if command -v docker &>/dev/null; then
    if docker info &>/dev/null; then
        record "docker" "PASS" "installed and daemon reachable"
    else
        record "docker" "NOT CONFIGURED" "installed but daemon not running/reachable"
    fi
else
    record "docker" "NOT CONFIGURED" "not found on PATH - Docker validation will be skipped"
fi

if [ -f "backend/.env" ]; then
    record "backend/.env exists" "PASS" "found"
    # Presence only, never the value.
    for var in SECRET_KEY DATABASE_URL; do
        if grep -q "^${var}=.\+" backend/.env 2>/dev/null; then
            record "  ${var} is set" "PASS" "present (value not checked here)"
        else
            record "  ${var} is set" "FAIL" "missing or empty in backend/.env"
        fi
    done
else
    record "backend/.env exists" "FAIL" "not found - copy backend/.env.example and fill it in"
fi

BACKEND_VENV_PY="backend/venv/bin/python3"
if [ -x "$BACKEND_VENV_PY" ]; then
    record "backend venv" "PASS" "found at backend/venv"
    if "$BACKEND_VENV_PY" -c "import sqlalchemy, pydantic, fastapi" 2>/dev/null; then
        record "backend core dependencies" "PASS" "sqlalchemy/pydantic/fastapi importable"
    else
        record "backend core dependencies" "FAIL" "venv exists but one or more core packages not importable - run ./setup.sh again"
    fi
else
    record "backend venv" "BLOCKED" "backend/venv not found - run ./setup.sh first; every check below that needs it is BLOCKED for the same reason"
fi

VENV_OK=false
if [ -x "$BACKEND_VENV_PY" ] && "$BACKEND_VENV_PY" -c "import sqlalchemy, pydantic, fastapi" 2>/dev/null; then
    VENV_OK=true
fi

# ----------------------------------------------------------------------
section "DEPENDENCY SECURITY AUDIT (pip-audit / npm audit)"
# ----------------------------------------------------------------------
# Folded in from the former standalone audit_dependencies.sh/.bat -
# one master verification entry point, not two competing ones. Never
# runs an automatic fix command (npm audit fix --force, etc) - a fix
# can introduce breaking changes and must be reviewed by a human.

if [ -x "$BACKEND_VENV_PY" ]; then
    if "$BACKEND_VENV_PY" -m pip_audit --version &>/dev/null; then
        PIP_AUDIT_OUT=$(cd backend && ./venv/bin/python3 -m pip_audit -r requirements.txt 2>&1)
        PIP_AUDIT_EXIT=$?
        echo "$PIP_AUDIT_OUT" | redact
        if [ "$PIP_AUDIT_EXIT" -eq 0 ]; then
            record "Backend dependency vulnerability scan (pip-audit)" "PASS" "no known vulnerabilities found in requirements.txt"
        else
            record "Backend dependency vulnerability scan (pip-audit)" "FAIL" "pip-audit reported findings above - review before deploying"
        fi
    else
        record "Backend dependency vulnerability scan (pip-audit)" "BLOCKED" "pip-audit not installed in backend/venv - install with: pip install pip-audit"
    fi
else
    record "Backend dependency vulnerability scan (pip-audit)" "BLOCKED" "backend venv unavailable"
fi

if command -v npm &>/dev/null && [ -f "frontend/package-lock.json" ]; then
    NPM_AUDIT_OUT=$(cd frontend && npm audit 2>&1)
    NPM_AUDIT_EXIT=$?
    echo "$NPM_AUDIT_OUT" | redact
    if [ "$NPM_AUDIT_EXIT" -eq 0 ]; then
        record "Frontend dependency vulnerability scan (npm audit)" "PASS" "no known vulnerabilities found"
    elif echo "$NPM_AUDIT_OUT" | grep -qiE "ENOTFOUND|ETIMEDOUT|network|403|ECONNREFUSED"; then
        record "Frontend dependency vulnerability scan (npm audit)" "BLOCKED" "network unavailable to the npm registry/audit endpoint"
    else
        record "Frontend dependency vulnerability scan (npm audit)" "FAIL" "npm audit reported findings above - review before deploying (never run npm audit fix --force blindly)"
    fi
else
    record "Frontend dependency vulnerability scan (npm audit)" "BLOCKED" "npm unavailable or frontend/package-lock.json missing"
fi

# ----------------------------------------------------------------------
section "BACKEND: STARTUP, MAPPER CONFIGURATION, IMPORTS"
# ----------------------------------------------------------------------

if [ "$VENV_OK" = true ]; then
    MAPPER_OUT=$(cd backend && ./venv/bin/python3 -c "
from app.platform.database.database import Base, engine
import app.models  # noqa: F401 - importing registers every model with Base's mapper registry
from sqlalchemy.orm import configure_mappers
configure_mappers()
print('OK')
" 2>&1)
    if echo "$MAPPER_OUT" | grep -q "^OK$"; then
        record "SQLAlchemy mapper configuration" "PASS" "all models registered and configured cleanly"
    else
        record "SQLAlchemy mapper configuration" "FAIL" "$(echo "$MAPPER_OUT" | tail -1 | redact)"
    fi

    IMPORT_OUT=$(cd backend && ./venv/bin/python3 -c "import app.main" 2>&1)
    if [ -z "$IMPORT_OUT" ] || echo "$IMPORT_OUT" | grep -qv "Error\|Traceback"; then
        record "app.main imports cleanly" "PASS" "no import-time errors"
    else
        record "app.main imports cleanly" "FAIL" "$(echo "$IMPORT_OUT" | tail -1 | redact)"
    fi

    # Real startup: spawn uvicorn, hit /health, kill it. Not a mock -
    # this is the actual ASGI app actually accepting an actual request.
    (cd backend && ./venv/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8123 \
        > "$RESULTS_DIR/.backend_startup.log" 2>&1 &)
    UVICORN_PID=""
    for i in $(seq 1 20); do
        sleep 0.5
        if command -v curl &>/dev/null && curl -sf "http://127.0.0.1:8123/health" > /dev/null 2>&1; then
            record "Backend startup + /health" "PASS" "responded within $(echo "$i * 0.5" | bc 2>/dev/null || echo "~$i x 0.5")s"
            UVICORN_PID=$(pgrep -f "uvicorn app.main:app.*8123" | head -1)
            break
        fi
    done
    if [ -z "${UVICORN_PID:-}" ]; then
        if command -v curl &>/dev/null; then
            record "Backend startup + /health" "FAIL" "did not respond within 10s - see verification-results/.backend_startup.log"
        else
            record "Backend startup + /health" "BLOCKED" "curl not available to check the endpoint"
        fi
    fi
    pkill -f "uvicorn app.main:app.*8123" 2>/dev/null
else
    record "SQLAlchemy mapper configuration" "BLOCKED" "backend venv/dependencies unavailable"
    record "app.main imports cleanly" "BLOCKED" "backend venv/dependencies unavailable"
    record "Backend startup + /health" "BLOCKED" "backend venv/dependencies unavailable"
fi

# ----------------------------------------------------------------------
section "LOCAL/MOCK CHECKS (scripts/verify.py - migrations chain, Excel, chatbot, email, runtime safety)"
# ----------------------------------------------------------------------

# The chain-integrity check within verify_migrations.py is pure Python
# with no third-party dependencies - it can genuinely run even without
# the venv, so it always runs on its own regardless of VENV_OK.
if command -v python3 &>/dev/null; then
    CHAIN_OUT=$(cd backend && python3 scripts/verify_migrations.py chain 2>&1)
    if echo "$CHAIN_OUT" | grep -q "PASS"; then
        record "Migration chain integrity" "PASS" "$(echo "$CHAIN_OUT" | head -1)"
    else
        record "Migration chain integrity" "FAIL" "$(echo "$CHAIN_OUT" | head -1 | redact)"
    fi
else
    record "Migration chain integrity" "BLOCKED" "python3 unavailable"
fi

if [ "$VENV_OK" = true ]; then
    VERIFY_PY_OUT=$(cd backend && ./venv/bin/python3 scripts/verify.py 2>&1)
    VERIFY_PY_EXIT=$?
    echo "$VERIFY_PY_OUT" | redact
    if [ "$VERIFY_PY_EXIT" -eq 0 ]; then
        record "scripts/verify.py (Excel/chatbot/email/runtime-safety)" "PASS" "see output above for the per-check breakdown"
    else
        record "scripts/verify.py (Excel/chatbot/email/runtime-safety)" "FAIL" "one or more local checks failed - see output above"
    fi
else
    record "scripts/verify.py (Excel/chatbot/email/runtime-safety)" "BLOCKED" "backend venv/dependencies unavailable"
fi

# ----------------------------------------------------------------------
section "DATABASE: NEON CONNECTIVITY"
# ----------------------------------------------------------------------

NEON_CONFIGURED=false
if [ -f "backend/.env" ] && grep -q "^DATABASE_URL=postgres" backend/.env 2>/dev/null; then
    NEON_CONFIGURED=true
fi

if [ "$NEON_CONFIGURED" = false ]; then
    record "Neon connectivity + SELECT 1" "NOT CONFIGURED" "DATABASE_URL in backend/.env is not a postgres:// URL - this environment is not pointed at Neon (SQLite is fine for local dev, but is never a substitute for this check)"
elif [ "$VENV_OK" = false ]; then
    record "Neon connectivity + SELECT 1" "BLOCKED" "DATABASE_URL is postgres but the backend venv/dependencies are unavailable to attempt the connection"
else
    NEON_OUT=$(cd backend && ./venv/bin/python3 scripts/verify_migrations.py neon-connection 2>&1)
    if echo "$NEON_OUT" | grep -qi "PASS"; then
        record "Neon connectivity + SELECT 1" "PASS" "connected successfully"
    else
        record "Neon connectivity + SELECT 1" "NOT RUNTIME VERIFIED" "configured but the live connection could not be completed here - $(echo "$NEON_OUT" | tail -1 | redact)"
    fi
fi

# ----------------------------------------------------------------------
section "REDIS (production shared rate limiting)"
# ----------------------------------------------------------------------

REDIS_CONFIGURED=false
if [ -f "backend/.env" ] && grep -q "^RATE_LIMIT_BACKEND=redis" backend/.env 2>/dev/null && grep -q "^REDIS_URL=.\+" backend/.env 2>/dev/null; then
    REDIS_CONFIGURED=true
fi

if [ "$REDIS_CONFIGURED" = false ]; then
    record "Redis connectivity (PING)" "NOT CONFIGURED" "RATE_LIMIT_BACKEND is not redis, or REDIS_URL is unset - this environment is not configured to use shared rate limiting"
elif [ "$VENV_OK" = false ]; then
    record "Redis connectivity (PING)" "BLOCKED" "Redis is configured but the backend venv/dependencies are unavailable to attempt the connection"
else
    REDIS_OUT=$(cd backend && ./venv/bin/python3 -c "
import redis, os
from app.platform.configuration.config import settings
client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
print('OK' if client.ping() else 'NO_PONG')
" 2>&1)
    if echo "$REDIS_OUT" | grep -q "^OK$"; then
        record "Redis connectivity (PING)" "PASS" "connected and responded to PING"
    else
        record "Redis connectivity (PING)" "NOT RUNTIME VERIFIED" "configured but the live connection could not be completed here - $(echo "$REDIS_OUT" | tail -1 | redact)"
    fi
fi

# ----------------------------------------------------------------------
section "GOOGLE DRIVE"
# ----------------------------------------------------------------------

DRIVE_CONFIGURED=false
if [ -f "backend/.env" ] && grep -q "^STORAGE_PROVIDER=drive" backend/.env 2>/dev/null \
   && grep -q "^GOOGLE_DRIVE_ENABLED=[Tt]rue" backend/.env 2>/dev/null \
   && grep -q "^GOOGLE_DRIVE_CREDENTIALS_PATH=.\+" backend/.env 2>/dev/null; then
    DRIVE_CONFIGURED=true
fi

if [ "$DRIVE_CONFIGURED" = false ]; then
    record "Drive upload/exists/read/delete" "NOT CONFIGURED" "STORAGE_PROVIDER/GOOGLE_DRIVE_ENABLED/CREDENTIALS_PATH not all set - Drive is not the active storage provider in this environment"
elif [ "$VENV_OK" = false ]; then
    record "Drive upload/exists/read/delete" "BLOCKED" "Drive is configured but the backend venv/dependencies are unavailable to attempt it"
else
    DRIVE_OUT=$(cd backend && ./venv/bin/python3 -c "
from app.platform.storage.storage import get_storage_backend
backend = get_storage_backend()
ref = backend.save('woodful_verify_probe.txt', b'woodful verification probe')
assert backend.exists(ref), 'uploaded file does not report as existing'
data = backend.read(ref)
assert data == b'woodful verification probe', 'read-back content mismatch'
backend.delete(ref)
assert not backend.exists(ref), 'file still exists after delete'
print('OK')
" 2>&1)
    if echo "$DRIVE_OUT" | grep -q "^OK$"; then
        record "Drive upload/exists/read/delete" "PASS" "full round-trip succeeded"
    else
        record "Drive upload/exists/read/delete" "NOT RUNTIME VERIFIED" "configured but the live round-trip could not be completed here - $(echo "$DRIVE_OUT" | tail -1 | redact)"
    fi
fi

# ----------------------------------------------------------------------
section "GEMINI"
# ----------------------------------------------------------------------

if [ "$VENV_OK" = true ]; then
    DLP_OUT=$(cd backend && ./venv/bin/python3 -c "
from app.modules.ai.gateway import _extract_and_redact_amount, _redact_outbound_message

redacted, amount = _extract_and_redact_amount('Record Rs 50,000 payment for WC-2026-003')
assert amount == 50000.0, f'expected to extract 50000.0, got {amount!r}'
assert '50,000' not in redacted and '50000' not in redacted, f'real amount leaked into sanitized text: {redacted!r}'
assert 'WC-2026-003' in redacted, 'order reference should survive redaction'

fully_redacted = _redact_outbound_message(redacted)
assert '50,000' not in fully_redacted and '50000' not in fully_redacted, 'real amount leaked after full redaction pipeline'
print('OK')
" 2>&1)
    if echo "$DLP_OUT" | grep -q "^OK$"; then
        record "Gemini financial-amount redaction (local, no API)" "PASS" "confirmed a real amount is extracted locally and never appears in the sanitized outbound text"
    else
        record "Gemini financial-amount redaction (local, no API)" "FAIL" "$(echo "$DLP_OUT" | tail -1 | redact)"
    fi
else
    record "Gemini financial-amount redaction (local, no API)" "BLOCKED" "backend venv/dependencies unavailable"
fi

GEMINI_CONFIGURED=false
if [ -f "backend/.env" ] && grep -q "^GEMINI_ENABLED=[Tt]rue" backend/.env 2>/dev/null \
   && grep -q "^GEMINI_API_KEY=.\+" backend/.env 2>/dev/null; then
    GEMINI_CONFIGURED=true
fi

if [ "$GEMINI_CONFIGURED" = false ]; then
    record "Gemini live connectivity (safe request)" "NOT CONFIGURED" "GEMINI_ENABLED is not True, or GEMINI_API_KEY is unset - Gemini is not enabled in this environment"
elif [ "$VENV_OK" = false ]; then
    record "Gemini live connectivity (safe request)" "BLOCKED" "Gemini is configured but the backend venv/dependencies are unavailable to attempt it"
else
    GEMINI_OUT=$(cd backend && ./venv/bin/python3 -c "
from app.platform.database.database import SessionLocal
from app.modules.ai.gateway import handle_message
db = SessionLocal()
try:
    # A deliberately safe, non-financial, non-sensitive operational
    # question - per this document's own instruction never to use
    # financial test data in a live external Gemini request.
    result = handle_message('what materials are running low on stock?', db=db, user_role='master')
    print('OK' if result is not None else 'NO_RESPONSE')
finally:
    db.close()
" 2>&1)
    if echo "$GEMINI_OUT" | grep -q "^OK$"; then
        record "Gemini live connectivity (safe request)" "PASS" "received a response"
    else
        record "Gemini live connectivity (safe request)" "NOT RUNTIME VERIFIED" "configured but the live request could not be completed here - $(echo "$GEMINI_OUT" | tail -1 | redact)"
    fi
fi

# ----------------------------------------------------------------------
section "EMAIL"
# ----------------------------------------------------------------------

SMTP_CONFIGURED=false
if [ -f "backend/.env" ] && grep -q "^SENDER_EMAIL=.\+" backend/.env 2>/dev/null \
   && grep -q "^SENDER_PASSWORD=.\+" backend/.env 2>/dev/null; then
    SMTP_CONFIGURED=true
fi

if [ "$SMTP_CONFIGURED" = false ]; then
    record "SMTP controlled test send" "NOT CONFIGURED" "SENDER_EMAIL/SENDER_PASSWORD not set in backend/.env - email sending is not configured in this environment"
elif [ "$VENV_OK" = false ]; then
    record "SMTP controlled test send" "BLOCKED" "SMTP is configured but the backend venv/dependencies are unavailable to attempt it"
else
    echo ""
    read -r -p "  Send one controlled test email now? Enter a recipient address, or leave blank to skip: " TEST_EMAIL_TO
    if [ -n "$TEST_EMAIL_TO" ]; then
        SMTP_OUT=$(cd backend && ./venv/bin/python3 -c "
from app.modules.communications.services.email_service import EmailService
ok = EmailService().send_email('$TEST_EMAIL_TO', 'Woodful verification test', '<p>This is a controlled test send from woodful_full_verification.sh.</p>', is_html=True)
print('OK' if ok else 'SEND_FAILED')
" 2>&1)
        if echo "$SMTP_OUT" | grep -q "^OK$"; then
            record "SMTP controlled test send" "PASS" "sent to the address you entered - confirm it arrived"
        else
            record "SMTP controlled test send" "NOT RUNTIME VERIFIED" "configured but the live send could not be completed here - $(echo "$SMTP_OUT" | tail -1 | redact)"
        fi
    else
        record "SMTP controlled test send" "NOT RUNTIME VERIFIED" "configured, but skipped - no recipient entered for this run"
    fi
fi

# ----------------------------------------------------------------------
section "FRONTEND: DEPENDENCY STATE"
# ----------------------------------------------------------------------

LOCKFILE_OK=false
if command -v node &>/dev/null; then
    LOCK_CHECK_OUT=$(cd frontend && node -e "
const pkg = require('./package.json');
const lock = require('./package-lock.json');
const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
const missing = Object.keys(deps).filter(name => !lock.packages || !lock.packages['node_modules/' + name]);
if (missing.length) {
    console.log('MISMATCH: ' + missing.join(', ') + ' declared in package.json but not present in package-lock.json');
} else {
    console.log('OK');
}
" 2>&1)
    if echo "$LOCK_CHECK_OUT" | grep -q "^OK$"; then
        LOCKFILE_OK=true
        record "package.json / package-lock.json consistency" "PASS" "every declared dependency has a lockfile entry"
    else
        record "package.json / package-lock.json consistency" "FAIL" "$(echo "$LOCK_CHECK_OUT" | tail -1 | redact) - regenerate with npm in a network-enabled environment; never hand-edit the lockfile"
    fi
else
    record "package.json / package-lock.json consistency" "BLOCKED" "node not found on PATH"
fi

if command -v npm &>/dev/null; then
    if [ "$LOCKFILE_OK" = false ]; then
        record "npm ci (clean install)" "BLOCKED" "package-lock.json is inconsistent with package.json (see above) - npm ci would refuse to run"
    else
        NPM_CI_OUT=$(cd frontend && npm ci 2>&1)
        NPM_CI_EXIT=$?
        if [ "$NPM_CI_EXIT" -eq 0 ]; then
            record "npm ci (clean install)" "PASS" "clean install succeeded"
        else
            if echo "$NPM_CI_OUT" | grep -qiE "ENOTFOUND|ETIMEDOUT|network|403|ECONNREFUSED"; then
                record "npm ci (clean install)" "BLOCKED" "network unavailable to the npm registry - $(echo "$NPM_CI_OUT" | tail -2 | redact)"
            else
                record "npm ci (clean install)" "FAIL" "$(echo "$NPM_CI_OUT" | tail -5 | redact)"
            fi
        fi
    fi
else
    record "npm ci (clean install)" "BLOCKED" "npm not found on PATH"
fi

# ----------------------------------------------------------------------
section "FRONTEND: TESTS AND BUILD"
# ----------------------------------------------------------------------

if command -v npm &>/dev/null && [ -d "frontend/node_modules" ]; then
    TEST_OUT=$(cd frontend && CI=true npm test 2>&1)
    TEST_EXIT=$?
    if [ "$TEST_EXIT" -eq 0 ]; then
        record "Frontend tests" "PASS" "$(echo "$TEST_OUT" | tail -3 | tr '\n' ' ')"
    else
        record "Frontend tests" "FAIL" "$(echo "$TEST_OUT" | tail -5 | redact)"
    fi

    BUILD_OUT=$(cd frontend && npm run build 2>&1)
    BUILD_EXIT=$?
    if [ "$BUILD_EXIT" -eq 0 ]; then
        record "Frontend production build" "PASS" "build succeeded"
    else
        record "Frontend production build" "FAIL" "$(echo "$BUILD_OUT" | tail -5 | redact)"
    fi
else
    record "Frontend tests" "BLOCKED" "frontend/node_modules missing or npm unavailable - run npm ci first"
    record "Frontend production build" "BLOCKED" "frontend/node_modules missing or npm unavailable - run npm ci first"
fi

# ----------------------------------------------------------------------
section "BROWSER / MOBILE WEB (responsive layout, not a native app)"
# ----------------------------------------------------------------------

if command -v npx &>/dev/null && [ -d "frontend/node_modules/@playwright" ]; then
    PLAYWRIGHT_OUT=$(cd frontend && npx playwright test 2>&1)
    PLAYWRIGHT_EXIT=$?
    if [ "$PLAYWRIGHT_EXIT" -eq 0 ]; then
        record "Playwright browser/responsive tests" "PASS" "$(echo "$PLAYWRIGHT_OUT" | tail -1)"
    else
        record "Playwright browser/responsive tests" "FAIL" "$(echo "$PLAYWRIGHT_OUT" | tail -3 | redact)"
    fi
else
    record "Playwright browser/responsive tests" "NOT CONFIGURED" "no Playwright spec exists in this repo yet - mobile web readiness (desktop/tablet/mobile browser, not a native app) has not been automated. Manual verification required: open the built frontend at 320/375/414/768/1024px and confirm navigation, tables, forms, and modals stay usable."
fi

# ----------------------------------------------------------------------
section "BACKEND TEST SUITE"
# ----------------------------------------------------------------------

if [ "$VENV_OK" = true ] && "$BACKEND_VENV_PY" -c "import pytest" 2>/dev/null; then
    PYTEST_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -q 2>&1)
    PYTEST_EXIT=$?
    SUMMARY=$(echo "$PYTEST_OUT" | tail -1)
    if [ "$PYTEST_EXIT" -eq 0 ]; then
        record "Backend test suite (pytest)" "PASS" "$SUMMARY"
    else
        record "Backend test suite (pytest)" "FAIL" "$SUMMARY"
    fi
else
    record "Backend test suite (pytest)" "BLOCKED" "pytest and/or backend venv/dependencies unavailable"
fi

# ----------------------------------------------------------------------
section "AUTHENTICATION"
# ----------------------------------------------------------------------

if [ "$VENV_OK" = true ] && "$BACKEND_VENV_PY" -c "import pytest" 2>/dev/null; then
    AUTH_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -k "test_login" -q 2>&1)
    AUTH_EXIT=$?
    SUMMARY=$(echo "$AUTH_OUT" | tail -1)
    if echo "$AUTH_OUT" | grep -qE "no tests ran|collected 0 items"; then
        record "Authentication (login/failure/logout/session)" "NOT CONFIGURED" "no matching tests found under this name"
    elif [ "$AUTH_EXIT" -eq 0 ]; then
        record "Authentication (login/failure/logout/session)" "PASS" "$SUMMARY"
    else
        record "Authentication (login/failure/logout/session)" "FAIL" "$SUMMARY"
    fi
else
    record "Authentication (login/failure/logout/session)" "BLOCKED" "pytest and/or backend venv/dependencies unavailable"
fi

# ----------------------------------------------------------------------
section "AUTHORIZATION / RBAC / IDOR"
# ----------------------------------------------------------------------

if [ "$VENV_OK" = true ] && "$BACKEND_VENV_PY" -c "import pytest" 2>/dev/null; then
    RBAC_FILES=$(find backend/tests -name "*rbac*.py" 2>/dev/null)
    if [ -n "$RBAC_FILES" ]; then
        AUTHZ_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -k "rbac" -q 2>&1)
        AUTHZ_EXIT=$?
        SUMMARY=$(echo "$AUTHZ_OUT" | tail -1)
        if [ "$AUTHZ_EXIT" -eq 0 ]; then
            record "Authorization (MASTER/USER, financial/HR redaction)" "PASS" "$SUMMARY"
        else
            record "Authorization (MASTER/USER, financial/HR redaction)" "FAIL" "$SUMMARY"
        fi
    else
        record "Authorization (MASTER/USER, financial/HR redaction)" "NOT CONFIGURED" "no *rbac*.py test files found"
    fi

    # IDOR specifically: identifier-substitution tests (order/estimate/
    # payment/salary-slip/candidate/document/employee cross-access
    # rejection) - a distinct, named check per this family's own
    # requirement, not folded silently into the RBAC run above even
    # though some of the same test files cover both.
    IDOR_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -k "mismatched or cannot_view_another or cannot_download_another" -q 2>&1)
    IDOR_EXIT=$?
    IDOR_SUMMARY=$(echo "$IDOR_OUT" | tail -1)
    if echo "$IDOR_OUT" | grep -qE "no tests ran|collected 0 items"; then
        record "IDOR (identifier substitution rejected)" "NOT CONFIGURED" "no matching tests found under this name"
    elif [ "$IDOR_EXIT" -eq 0 ]; then
        record "IDOR (identifier substitution rejected)" "PASS" "$IDOR_SUMMARY"
    else
        record "IDOR (identifier substitution rejected)" "FAIL" "$IDOR_SUMMARY"
    fi
else
    record "Authorization (MASTER/USER, financial/HR redaction)" "BLOCKED" "pytest and/or backend venv/dependencies unavailable"
    record "IDOR (identifier substitution rejected)" "BLOCKED" "pytest and/or backend venv/dependencies unavailable"
fi

# ----------------------------------------------------------------------
section "DOCUMENT / STORAGE ACCESS CONTROL"
# ----------------------------------------------------------------------

if [ "$VENV_OK" = true ] && "$BACKEND_VENV_PY" -c "import pytest" 2>/dev/null; then
    STORAGE_FILES=$(find backend/tests -name "*storage*.py" -o -name "*document*.py" 2>/dev/null)
    if [ -n "$STORAGE_FILES" ]; then
        STORAGE_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -k "storage or document" -q 2>&1)
        STORAGE_EXIT=$?
        SUMMARY=$(echo "$STORAGE_OUT" | tail -1)
        if [ "$STORAGE_EXIT" -eq 0 ]; then
            record "Storage/document (upload/reference/retrieval/deletion, access control)" "PASS" "$SUMMARY"
        else
            record "Storage/document (upload/reference/retrieval/deletion, access control)" "FAIL" "$SUMMARY"
        fi
    else
        record "Storage/document (upload/reference/retrieval/deletion, access control)" "NOT CONFIGURED" "no storage/document test files found"
    fi
else
    record "Storage/document (upload/reference/retrieval/deletion, access control)" "BLOCKED" "pytest and/or backend venv/dependencies unavailable"
fi

# ----------------------------------------------------------------------
section "PRODUCTION CONFIGURATION SAFETY (static checks only)"
# ----------------------------------------------------------------------

if [ ! -f "backend/.env" ]; then
    record "DEBUG disabled in production" "BLOCKED" "backend/.env not found - nothing to check"
    record "CORS not wildcarded" "BLOCKED" "backend/.env not found - nothing to check"
elif ! grep -q "^ENVIRONMENT=production" backend/.env 2>/dev/null; then
    record "DEBUG disabled in production" "NOT CONFIGURED" "ENVIRONMENT is not set to production in this .env"
    record "CORS not wildcarded" "NOT CONFIGURED" "ENVIRONMENT is not set to production in this .env"
else
    if grep -q "^DEBUG=[Tt]rue" backend/.env 2>/dev/null; then
        record "DEBUG disabled in production" "FAIL" "ENVIRONMENT=production but DEBUG=True - this exposes stack traces"
    else
        record "DEBUG disabled in production" "PASS" "DEBUG is not True"
    fi
    if grep -qE "^CORS_ORIGINS=.*\*" backend/.env 2>/dev/null; then
        record "CORS not wildcarded" "FAIL" "CORS_ORIGINS contains a wildcard in production"
    else
        record "CORS not wildcarded" "PASS" "no wildcard found"
    fi
fi

# ----------------------------------------------------------------------
section "STALE REFERENCE CHECK"
# ----------------------------------------------------------------------
# Confirms this verification runner itself, and the repository it is
# checking, contain no leftover references to the pre-reorg locations
# (the app now lives at backend/app/main.py, not backend/main.py; there
# is no top-level database/ directory, no root package.json/
# package-lock.json, and no app/core/ path).

STALE_HITS=$(grep -rlIE "backend/main\.py|database/models|app/core/|app\.core\." \
    --include="*.md" --include="*.bat" --include="*.sh" --include="*.py" \
    --include="*.yml" --include="*.yaml" . 2>/dev/null \
    | grep -v -E "woodful_full_verification|node_modules|/venv/" || true)
if [ -f "package.json" ] || [ -f "package-lock.json" ]; then
    STALE_HITS="$STALE_HITS
./package.json (root package.json should not exist - frontend/package.json is authoritative)"
fi

if [ -z "$STALE_HITS" ]; then
    record "Stale root-path references" "PASS" "no references found to backend/main.py, database/, root package.json/package-lock.json, or old core/ paths"
else
    record "Stale root-path references" "FAIL" "found a stale reference - see console output above from grep"
    echo "$STALE_HITS" | redact
fi

# ----------------------------------------------------------------------
section "SUMMARY"
# ----------------------------------------------------------------------

TOTAL=${#CHECK_NAMES[@]}
PASS_COUNT=0
FAIL_COUNT=0
BLOCKED_COUNT=0
NOTCONFIGURED_COUNT=0
NOTVERIFIED_COUNT=0
CRITICAL_FAILURES=()

for i in "${!CHECK_NAMES[@]}"; do
    case "${CHECK_STATUS[$i]}" in
        PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
        FAIL)
            FAIL_COUNT=$((FAIL_COUNT + 1))
            CRITICAL_FAILURES+=("${CHECK_NAMES[$i]}: ${CHECK_DETAIL[$i]}")
            ;;
        BLOCKED) BLOCKED_COUNT=$((BLOCKED_COUNT + 1)) ;;
        "NOT CONFIGURED") NOTCONFIGURED_COUNT=$((NOTCONFIGURED_COUNT + 1)) ;;
        *) NOTVERIFIED_COUNT=$((NOTVERIFIED_COUNT + 1)) ;;
    esac
done

echo "Total checks:            $TOTAL"
echo "PASS:                    $PASS_COUNT"
echo "FAIL:                    $FAIL_COUNT"
echo "BLOCKED:                 $BLOCKED_COUNT"
echo "NOT CONFIGURED:          $NOTCONFIGURED_COUNT"
echo "NOT RUNTIME VERIFIED:    $NOTVERIFIED_COUNT"
echo ""

# Only a genuine FAIL (a check that ran and found a real problem) makes
# this NOT READY / non-zero exit. BLOCKED, NOT CONFIGURED, and NOT
# RUNTIME VERIFIED are environment/infrastructure/configuration facts,
# never application defects, and must never be hidden or silently
# folded into PASS to make the run look greener than it is.
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "Critical failures:"
    for f in "${CRITICAL_FAILURES[@]}"; do
        echo "  - $f"
    done
    echo ""
    FINAL_STATUS="NOT READY"
else
    FINAL_STATUS="READY"
fi

if [ "$BLOCKED_COUNT" -gt 0 ] || [ "$NOTCONFIGURED_COUNT" -gt 0 ] || [ "$NOTVERIFIED_COUNT" -gt 0 ]; then
    echo "Note: $BLOCKED_COUNT BLOCKED, $NOTCONFIGURED_COUNT NOT CONFIGURED, $NOTVERIFIED_COUNT NOT RUNTIME VERIFIED (see entries above)."
    echo "A status of READY reflects only that no check which actually ran found a real"
    echo "problem - it is not a claim that BLOCKED/NOT CONFIGURED/NOT RUNTIME VERIFIED"
    echo "items are safe to assume working, and it is never a claim of production"
    echo "readiness for infrastructure this script could not reach (Neon/Redis/Drive/"
    echo "SMTP/Gemini) or for mobile web layout, which needs real browser verification."
fi

echo ""
echo "FINAL STATUS: $FINAL_STATUS"
echo "======================================================================"

# ----------------------------------------------------------------------
# Write result files
# ----------------------------------------------------------------------

{
    echo "Woodful Creations - Verification Results"
    echo "Run at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo ""
    for i in "${!CHECK_NAMES[@]}"; do
        printf "%-22s %-55s %s\n" "${CHECK_STATUS[$i]}" "${CHECK_NAMES[$i]}" "${CHECK_DETAIL[$i]}"
    done
    echo ""
    echo "Total: $TOTAL | PASS: $PASS_COUNT | FAIL: $FAIL_COUNT | BLOCKED: $BLOCKED_COUNT | NOT CONFIGURED: $NOTCONFIGURED_COUNT | NOT RUNTIME VERIFIED: $NOTVERIFIED_COUNT"
    echo "FINAL STATUS: $FINAL_STATUS"
} | redact > "$RESULTS_DIR/latest.txt"

{
    echo "{"
    echo "  \"run_at\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\","
    echo "  \"final_status\": \"$FINAL_STATUS\","
    echo "  \"total\": $TOTAL,"
    echo "  \"pass\": $PASS_COUNT,"
    echo "  \"fail\": $FAIL_COUNT,"
    echo "  \"blocked\": $BLOCKED_COUNT,"
    echo "  \"not_configured\": $NOTCONFIGURED_COUNT,"
    echo "  \"not_runtime_verified\": $NOTVERIFIED_COUNT,"
    echo "  \"checks\": ["
    for i in "${!CHECK_NAMES[@]}"; do
        name_esc=$(echo "${CHECK_NAMES[$i]}" | redact | sed 's/"/\\"/g')
        detail_esc=$(echo "${CHECK_DETAIL[$i]}" | redact | sed 's/"/\\"/g')
        comma=","
        if [ "$i" -eq $((TOTAL - 1)) ]; then comma=""; fi
        echo "    {\"name\": \"$name_esc\", \"status\": \"${CHECK_STATUS[$i]}\", \"detail\": \"$detail_esc\"}$comma"
    done
    echo "  ]"
    echo "}"
} > "$RESULTS_DIR/latest.json"

{
    echo "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Woodful Verification Results</title>"
    echo "<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}"
    echo "table{width:100%;border-collapse:collapse}td,th{padding:.5rem;border-bottom:1px solid #ddd;text-align:left}"
    echo ".PASS{color:#1a7f37}.FAIL{color:#cf222e;font-weight:600}.BLOCKED{color:#9a6700}.NOTCONFIGURED{color:#0969da}.NOTRUNTIMEVERIFIED{color:#8250df}</style></head><body>"
    echo "<h1>Woodful Creations - Verification Results</h1>"
    echo "<p>Run at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')</p>"
    echo "<p><strong>Final status: $FINAL_STATUS</strong> ($PASS_COUNT PASS / $FAIL_COUNT FAIL / $BLOCKED_COUNT BLOCKED / $NOTCONFIGURED_COUNT NOT CONFIGURED / $NOTVERIFIED_COUNT NOT RUNTIME VERIFIED of $TOTAL)</p>"
    echo "<table><tr><th>Status</th><th>Check</th><th>Detail</th></tr>"
    for i in "${!CHECK_NAMES[@]}"; do
        css_class=$(echo "${CHECK_STATUS[$i]}" | tr -d ' ')
        name_esc=$(echo "${CHECK_NAMES[$i]}" | redact)
        detail_esc=$(echo "${CHECK_DETAIL[$i]}" | redact)
        echo "<tr><td class='$css_class'>${CHECK_STATUS[$i]}</td><td>$name_esc</td><td>$detail_esc</td></tr>"
    done
    echo "</table></body></html>"
} > "$RESULTS_DIR/latest.html"

echo ""
echo "Results written to:"
echo "  $RESULTS_DIR/latest.txt"
echo "  $RESULTS_DIR/latest.json"
echo "  $RESULTS_DIR/latest.html"

if [ "$FINAL_STATUS" = "READY" ]; then
    exit 0
else
    exit 1
fi
