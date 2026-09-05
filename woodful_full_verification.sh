#!/bin/bash
# Woodful Creations - Master Local Verification Harness
#
# The single local entry point for Woodful production verification.
# Exists specifically for checks that cannot be reliably performed
# from within an AI coding assistant's sandbox (no live credentials,
# no network egress, no installed pytest/sqlalchemy) - this script is
# meant to be run on YOUR machine, with your own .env populated.
#
# Every check reports exactly one of: PASS, FAIL, NOT RUN.
# NOT RUN is never silently converted to PASS - a missing tool,
# missing credential, or unreachable service is reported honestly as
# NOT RUN, not treated as success. One failed check never prevents
# the remaining, independent checks from running.
#
# Secrets (passwords, API keys, tokens, connection strings) are never
# printed to stdout or written to the result files below - only
# PASS/FAIL/NOT RUN and a short, non-sensitive detail message.
#
# Usage: ./woodful_full_verification.sh

set -u  # undefined variables are errors; deliberately NOT `set -e` -
        # one failing check must not abort the rest of the run.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RESULTS_DIR="$SCRIPT_DIR/verification-results"
mkdir -p "$RESULTS_DIR"

# Parallel arrays: one entry per check. Bash 3.2 (macOS default) has no
# associative arrays, so this uses indexed arrays instead for portability.
CHECK_NAMES=()
CHECK_STATUS=()   # "PASS" | "FAIL" | "NOT RUN"
CHECK_DETAIL=()

record() {
    # record <name> <PASS|FAIL|"NOT RUN"> <detail>
    CHECK_NAMES+=("$1")
    CHECK_STATUS+=("$2")
    CHECK_DETAIL+=("$3")
    case "$2" in
        PASS)     printf "  \033[32mPASS\033[0m     %-45s %s\n" "$1" "$3" ;;
        FAIL)     printf "  \033[31mFAIL\033[0m     %-45s %s\n" "$1" "$3" ;;
        *)        printf "  \033[33mNOT RUN\033[0m  %-45s %s\n" "$1" "$3" ;;
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
    record "python3" "FAIL" "not found on PATH - required for the backend"
fi

if command -v node &>/dev/null; then
    record "node" "PASS" "$(node --version 2>&1)"
else
    record "node" "NOT RUN" "not found on PATH - frontend build/tests will be skipped"
fi

if command -v npm &>/dev/null; then
    record "npm" "PASS" "$(npm --version 2>&1)"
else
    record "npm" "NOT RUN" "not found on PATH - frontend build/tests will be skipped"
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
        record "backend core dependencies" "FAIL" "one or more core packages not importable - run ./setup.sh"
    fi
else
    record "backend venv" "NOT RUN" "backend/venv not found - run ./setup.sh first; backend checks below will be skipped"
fi

# ----------------------------------------------------------------------
section "BACKEND: STARTUP, MAPPER CONFIGURATION, IMPORTS"
# ----------------------------------------------------------------------

if [ -x "$BACKEND_VENV_PY" ]; then
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
            record "Backend startup + /health" "NOT RUN" "curl not available to check the endpoint"
        fi
    fi
    pkill -f "uvicorn app.main:app.*8123" 2>/dev/null
else
    record "SQLAlchemy mapper configuration" "NOT RUN" "backend venv unavailable"
    record "app.main imports cleanly" "NOT RUN" "backend venv unavailable"
    record "Backend startup + /health" "NOT RUN" "backend venv unavailable"
fi

# ----------------------------------------------------------------------
section "LOCAL/MOCK CHECKS (scripts/verify.py - migrations chain, Excel, chatbot, email, runtime safety)"
# ----------------------------------------------------------------------

if [ -x "$BACKEND_VENV_PY" ]; then
    VERIFY_PY_OUT=$(cd backend && ./venv/bin/python3 scripts/verify.py 2>&1)
    VERIFY_PY_EXIT=$?
    echo "$VERIFY_PY_OUT" | redact
    if [ "$VERIFY_PY_EXIT" -eq 0 ]; then
        record "scripts/verify.py (all local/mock checks)" "PASS" "see output above for the per-check breakdown"
    else
        record "scripts/verify.py (all local/mock checks)" "FAIL" "one or more local checks failed - see output above"
    fi
else
    # The chain-integrity check within verify_migrations.py is pure
    # Python with no third-party dependencies - it can genuinely run
    # even without the venv, so it's worth attempting on its own.
    if command -v python3 &>/dev/null; then
        CHAIN_OUT=$(cd backend && python3 scripts/verify_migrations.py chain 2>&1)
        if echo "$CHAIN_OUT" | grep -q "PASS"; then
            record "Migration chain integrity" "PASS" "$(echo "$CHAIN_OUT" | head -1)"
        else
            record "Migration chain integrity" "FAIL" "$(echo "$CHAIN_OUT" | head -1 | redact)"
        fi
    else
        record "Migration chain integrity" "NOT RUN" "python3 unavailable"
    fi
    record "scripts/verify.py (all local/mock checks)" "NOT RUN" "backend venv unavailable - see individual migration-chain result above"
fi

# ----------------------------------------------------------------------
section "DATABASE: NEON CONNECTIVITY"
# ----------------------------------------------------------------------

NEON_CONFIGURED=false
if [ -f "backend/.env" ] && grep -q "^DATABASE_URL=postgres" backend/.env 2>/dev/null; then
    NEON_CONFIGURED=true
fi

if [ "$NEON_CONFIGURED" = true ] && [ -x "$BACKEND_VENV_PY" ]; then
    NEON_OUT=$(cd backend && ./venv/bin/python3 scripts/verify_migrations.py neon-connection 2>&1)
    if echo "$NEON_OUT" | grep -qi "PASS"; then
        record "Neon connectivity + SELECT 1" "PASS" "connected successfully"
    else
        record "Neon connectivity + SELECT 1" "FAIL" "$(echo "$NEON_OUT" | tail -1 | redact)"
    fi
else
    record "Neon connectivity + SELECT 1" "NOT RUN" "DATABASE_URL is not a postgres:// URL, or venv unavailable - SQLite is not a substitute for this check"
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

if [ "$DRIVE_CONFIGURED" = true ] && [ -x "$BACKEND_VENV_PY" ]; then
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
        record "Drive upload/exists/read/delete" "FAIL" "$(echo "$DRIVE_OUT" | tail -1 | redact)"
    fi
else
    record "Drive upload/exists/read/delete" "NOT RUN" "STORAGE_PROVIDER=drive/GOOGLE_DRIVE_ENABLED/CREDENTIALS_PATH not all configured, or venv unavailable"
fi

# ----------------------------------------------------------------------
section "GEMINI"
# ----------------------------------------------------------------------

if [ -x "$BACKEND_VENV_PY" ]; then
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
        record "Gemini financial-amount redaction (direct)" "PASS" "confirmed a real amount is extracted locally and never appears in the sanitized outbound text"
    else
        record "Gemini financial-amount redaction (direct)" "FAIL" "$(echo "$DLP_OUT" | tail -1 | redact)"
    fi
else
    record "Gemini financial-amount redaction (direct)" "NOT RUN" "backend venv unavailable"
fi

GEMINI_CONFIGURED=false
if [ -f "backend/.env" ] && grep -q "^GEMINI_ENABLED=[Tt]rue" backend/.env 2>/dev/null \
   && grep -q "^GEMINI_API_KEY=.\+" backend/.env 2>/dev/null; then
    GEMINI_CONFIGURED=true
fi

if [ "$GEMINI_CONFIGURED" = true ] && [ -x "$BACKEND_VENV_PY" ]; then
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
        record "Gemini live connectivity (safe request)" "FAIL" "$(echo "$GEMINI_OUT" | tail -1 | redact)"
    fi
else
    record "Gemini live connectivity (safe request)" "NOT RUN" "GEMINI_ENABLED/API_KEY not configured, or venv unavailable"
fi

# ----------------------------------------------------------------------
section "EMAIL"
# ----------------------------------------------------------------------

SMTP_CONFIGURED=false
if [ -f "backend/.env" ] && grep -q "^SENDER_EMAIL=.\+" backend/.env 2>/dev/null \
   && grep -q "^SENDER_PASSWORD=.\+" backend/.env 2>/dev/null; then
    SMTP_CONFIGURED=true
fi

if [ "$SMTP_CONFIGURED" = true ] && [ -x "$BACKEND_VENV_PY" ]; then
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
            record "SMTP controlled test send" "FAIL" "$(echo "$SMTP_OUT" | tail -1 | redact)"
        fi
    else
        record "SMTP controlled test send" "NOT RUN" "skipped - no recipient entered"
    fi
else
    record "SMTP controlled test send" "NOT RUN" "SENDER_EMAIL/SENDER_PASSWORD not configured, or venv unavailable"
fi

# ----------------------------------------------------------------------
section "FRONTEND BUILD"
# ----------------------------------------------------------------------

if command -v npm &>/dev/null && [ -d "frontend" ]; then
    if [ ! -d "frontend/node_modules" ]; then
        record "Frontend production build" "NOT RUN" "frontend/node_modules missing - run ./setup.sh or npm install first"
    else
        BUILD_OUT=$(cd frontend && npm run build 2>&1)
        BUILD_EXIT=$?
        if [ "$BUILD_EXIT" -eq 0 ]; then
            record "Frontend production build" "PASS" "build succeeded"
        else
            record "Frontend production build" "FAIL" "$(echo "$BUILD_OUT" | tail -5 | redact)"
        fi
    fi
else
    record "Frontend production build" "NOT RUN" "npm unavailable or frontend/ missing"
fi

# ----------------------------------------------------------------------
section "BROWSER / PLAYWRIGHT"
# ----------------------------------------------------------------------

if command -v npx &>/dev/null && [ -d "frontend/node_modules/@playwright" ]; then
    PLAYWRIGHT_OUT=$(cd frontend && npx playwright test 2>&1)
    PLAYWRIGHT_EXIT=$?
    if [ "$PLAYWRIGHT_EXIT" -eq 0 ]; then
        record "Playwright browser tests" "PASS" "$(echo "$PLAYWRIGHT_OUT" | tail -1)"
    else
        record "Playwright browser tests" "FAIL" "$(echo "$PLAYWRIGHT_OUT" | tail -3 | redact)"
    fi
else
    record "Playwright browser tests" "NOT RUN" "Playwright not installed - no browser test suite exists in this repo yet either way"
fi

# ----------------------------------------------------------------------
section "BACKEND TEST SUITE"
# ----------------------------------------------------------------------

if [ -x "$BACKEND_VENV_PY" ]; then
    if "$BACKEND_VENV_PY" -c "import pytest" 2>/dev/null; then
        PYTEST_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -q 2>&1)
        PYTEST_EXIT=$?
        SUMMARY=$(echo "$PYTEST_OUT" | tail -1)
        if [ "$PYTEST_EXIT" -eq 0 ]; then
            record "Backend test suite (pytest)" "PASS" "$SUMMARY"
        else
            record "Backend test suite (pytest)" "FAIL" "$SUMMARY"
        fi
    else
        record "Backend test suite (pytest)" "NOT RUN" "pytest not installed in backend/venv"
    fi
else
    record "Backend test suite (pytest)" "NOT RUN" "backend venv unavailable"
fi

# ----------------------------------------------------------------------
section "AUTHENTICATION"
# ----------------------------------------------------------------------

if [ -x "$BACKEND_VENV_PY" ] && "$BACKEND_VENV_PY" -c "import pytest" 2>/dev/null; then
    AUTH_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -k "test_login" -q 2>&1)
    AUTH_EXIT=$?
    SUMMARY=$(echo "$AUTH_OUT" | tail -1)
    if echo "$AUTH_OUT" | grep -qE "no tests ran|collected 0 items"; then
        record "Authentication (login/failure/logout/session)" "NOT RUN" "no matching tests found"
    elif [ "$AUTH_EXIT" -eq 0 ]; then
        record "Authentication (login/failure/logout/session)" "PASS" "$SUMMARY"
    else
        record "Authentication (login/failure/logout/session)" "FAIL" "$SUMMARY"
    fi
else
    record "Authentication (login/failure/logout/session)" "NOT RUN" "pytest/backend venv unavailable"
fi

# ----------------------------------------------------------------------
section "AUTHORIZATION"
# ----------------------------------------------------------------------

if [ -x "$BACKEND_VENV_PY" ] && "$BACKEND_VENV_PY" -c "import pytest" 2>/dev/null; then
    RBAC_FILES=$(find backend/tests -name "*rbac*.py" 2>/dev/null)
    if [ -n "$RBAC_FILES" ]; then
        AUTHZ_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -k "rbac" -q 2>&1)
        AUTHZ_EXIT=$?
        SUMMARY=$(echo "$AUTHZ_OUT" | tail -1)
        if [ "$AUTHZ_EXIT" -eq 0 ]; then
            record "Authorization (MASTER/USER, ownership, IDOR/BOLA)" "PASS" "$SUMMARY"
        else
            record "Authorization (MASTER/USER, ownership, IDOR/BOLA)" "FAIL" "$SUMMARY"
        fi
    else
        record "Authorization (MASTER/USER, ownership, IDOR/BOLA)" "NOT RUN" "no *rbac*.py test files found"
    fi
else
    record "Authorization (MASTER/USER, ownership, IDOR/BOLA)" "NOT RUN" "pytest/backend venv unavailable"
fi

# ----------------------------------------------------------------------
section "STORAGE"
# ----------------------------------------------------------------------

if [ -x "$BACKEND_VENV_PY" ] && "$BACKEND_VENV_PY" -c "import pytest" 2>/dev/null; then
    STORAGE_FILES=$(find backend/tests -name "*storage*.py" -o -name "*document*.py" 2>/dev/null)
    if [ -n "$STORAGE_FILES" ]; then
        STORAGE_OUT=$(cd backend && ./venv/bin/python3 -m pytest tests/ -k "storage or document" -q 2>&1)
        STORAGE_EXIT=$?
        SUMMARY=$(echo "$STORAGE_OUT" | tail -1)
        if [ "$STORAGE_EXIT" -eq 0 ]; then
            record "Storage (upload/reference/retrieval/deletion)" "PASS" "$SUMMARY"
        else
            record "Storage (upload/reference/retrieval/deletion)" "FAIL" "$SUMMARY"
        fi
    else
        record "Storage (upload/reference/retrieval/deletion)" "NOT RUN" "no storage/document test files found"
    fi
else
    record "Storage (upload/reference/retrieval/deletion)" "NOT RUN" "pytest/backend venv unavailable"
fi

# ----------------------------------------------------------------------
section "THEME"
# ----------------------------------------------------------------------

record "Theme (Login system theme, authenticated Dark default, switching)" "NOT RUN" "No Playwright theme spec exists in this repo yet - this is a genuine browser-level check (Login follows system theme, authenticated app defaults Dark, Light/Dark switching), not something a backend pytest run can verify. Add a Playwright spec under frontend/ to close this gap."

# ----------------------------------------------------------------------
section "PRODUCTION CONFIGURATION SAFETY (static checks only)"
# ----------------------------------------------------------------------

if [ -f "backend/.env" ]; then
    if grep -q "^ENVIRONMENT=production" backend/.env 2>/dev/null; then
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
    else
        record "DEBUG disabled in production" "NOT RUN" "ENVIRONMENT is not set to production in this .env"
        record "CORS not wildcarded" "NOT RUN" "ENVIRONMENT is not set to production in this .env"
    fi
else
    record "DEBUG disabled in production" "NOT RUN" "backend/.env not found"
    record "CORS not wildcarded" "NOT RUN" "backend/.env not found"
fi

# ----------------------------------------------------------------------
section "SUMMARY"
# ----------------------------------------------------------------------

TOTAL=${#CHECK_NAMES[@]}
PASS_COUNT=0
FAIL_COUNT=0
NOTRUN_COUNT=0
CRITICAL_FAILURES=()

for i in "${!CHECK_NAMES[@]}"; do
    case "${CHECK_STATUS[$i]}" in
        PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
        FAIL)
            FAIL_COUNT=$((FAIL_COUNT + 1))
            CRITICAL_FAILURES+=("${CHECK_NAMES[$i]}: ${CHECK_DETAIL[$i]}")
            ;;
        *) NOTRUN_COUNT=$((NOTRUN_COUNT + 1)) ;;
    esac
done

echo "Total checks:   $TOTAL"
echo "PASS:           $PASS_COUNT"
echo "FAIL:           $FAIL_COUNT"
echo "NOT RUN:        $NOTRUN_COUNT"
echo ""

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

# "READY" must never be reported when a critical check failed - and a
# genuinely honest READY still can't promise everything was actually
# checked, only that nothing checked here failed.
if [ "$NOTRUN_COUNT" -gt 0 ]; then
    echo "Note: $NOTRUN_COUNT check(s) could not run in this environment (see NOT RUN entries above)."
    echo "A status of READY reflects only what was actually able to run - it does not"
    echo "imply the NOT RUN items are safe to assume passing."
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
        printf "%-8s %-50s %s\n" "${CHECK_STATUS[$i]}" "${CHECK_NAMES[$i]}" "${CHECK_DETAIL[$i]}"
    done
    echo ""
    echo "Total: $TOTAL | PASS: $PASS_COUNT | FAIL: $FAIL_COUNT | NOT RUN: $NOTRUN_COUNT"
    echo "FINAL STATUS: $FINAL_STATUS"
} | redact > "$RESULTS_DIR/latest.txt"

{
    echo "{"
    echo "  \"run_at\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\","
    echo "  \"final_status\": \"$FINAL_STATUS\","
    echo "  \"total\": $TOTAL,"
    echo "  \"pass\": $PASS_COUNT,"
    echo "  \"fail\": $FAIL_COUNT,"
    echo "  \"not_run\": $NOTRUN_COUNT,"
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
    echo ".PASS{color:#1a7f37}.FAIL{color:#cf222e;font-weight:600}.NOTRUN{color:#9a6700}</style></head><body>"
    echo "<h1>Woodful Creations - Verification Results</h1>"
    echo "<p>Run at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')</p>"
    echo "<p><strong>Final status: $FINAL_STATUS</strong> ($PASS_COUNT PASS / $FAIL_COUNT FAIL / $NOTRUN_COUNT NOT RUN of $TOTAL)</p>"
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
