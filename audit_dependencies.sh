#!/bin/bash
# Woodful Creations - Dependency vulnerability audit
#
# This sandbox/CI environment used to develop this project has no
# network access, so pip-audit/npm audit could not actually be run
# here - dependency security was explicitly NOT verified as part of
# that work. Run this script from a real, network-enabled development
# machine before deploying, and whenever dependencies change.
#
# Does NOT run `npm audit fix --force` or any other command that
# rewrites lockfiles/dependency versions automatically - a fix command
# can introduce breaking changes and should be reviewed by a human,
# not run blindly.

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=== Backend (pip) ==="
cd "$SCRIPT_DIR/backend"
if [ -d "venv" ]; then
    source venv/bin/activate
fi
if ! command -v pip-audit &> /dev/null; then
    echo "pip-audit not installed. Install it with: pip install pip-audit"
else
    pip-audit -r requirements.txt || echo "pip-audit reported findings above - review before deploying."
fi

echo ""
echo "=== Frontend (npm) ==="
cd "$SCRIPT_DIR/frontend"
if [ -f "package-lock.json" ]; then
    npm audit || echo "npm audit reported findings above - review before deploying. Do NOT run 'npm audit fix --force' without understanding what it changes."
else
    echo "No frontend/package-lock.json found - run 'npm install' first."
fi
