#!/usr/bin/env node
/**
 * Static regression checks for the WOODFUL AUTH + STARTUP LATENCY
 * DEFECT REPAIR (Requirement 10, frontend A-D). Zero dependencies
 * (plain Node `fs`/regex, no jest/testing-library) - this repo's
 * frontend has no test runner configured at all (see package.json),
 * and standing one up is out of scope for an auth/session-stability
 * repair. These are deliberately "static checks", exactly as the
 * defect-repair brief allows for the frontend side, mirroring the
 * black-box style of the existing woodful_full_verification.sh/.bat
 * scripts rather than introducing a new framework dependency.
 *
 * Exit code 0 = every check passed. Non-zero = at least one failed
 * (see the printed [FAIL] lines for which, and why).
 *
 * Run directly: node frontend/scripts/verify_auth_session_contract.js
 * Also wired into woodful_full_verification.sh/.bat.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'src');

let failures = 0;

function check(label, condition, detail) {
  if (condition) {
    console.log(`[PASS] ${label}`);
  } else {
    failures += 1;
    console.log(`[FAIL] ${label}${detail ? ` - ${detail}` : ''}`);
  }
}

function read(relPath) {
  return fs.readFileSync(path.join(ROOT, relPath), 'utf8');
}

// Recursively collect every .js/.jsx file under src/, skipping
// node_modules (not expected under src/, but defensive anyway).
function collectSourceFiles(dir) {
  let out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules') continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out = out.concat(collectSourceFiles(full));
    } else if (/\.(js|jsx)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

// --- A: API default host is consistent with backend dev config ---
const apiJs = read('src/utils/api.js');
const apiUrlMatch = apiJs.match(/const API_URL = process\.env\.REACT_APP_API_URL \|\| '([^']+)'/);
check(
  'A: api.js REACT_APP_API_URL fallback default uses "localhost", not 127.0.0.1',
  !!apiUrlMatch && apiUrlMatch[1] === 'http://localhost:8000',
  `found ${apiUrlMatch ? apiUrlMatch[1] : '(no match - regex out of sync with api.js?)'}`
);

const envExample = fs.existsSync(path.join(ROOT, '.env.example')) ? fs.readFileSync(path.join(ROOT, '.env.example'), 'utf8') : '';
const envUrlMatch = envExample.match(/^REACT_APP_API_URL=(.+)$/m);
check(
  'A: frontend/.env.example REACT_APP_API_URL matches the same "localhost" default',
  !!envUrlMatch && envUrlMatch[1].trim() === 'http://localhost:8000',
  `found ${envUrlMatch ? envUrlMatch[1] : '(missing REACT_APP_API_URL line)'}`
);

let backendEnvExample = '';
try {
  backendEnvExample = fs.readFileSync(path.join(ROOT, '..', 'backend', '.env.example'), 'utf8');
} catch (e) {
  // handled by the check below
}
const corsMatch = backendEnvExample.match(/^CORS_ORIGINS=(.+)$/m);
check(
  'A: backend/.env.example CORS_ORIGINS includes the matching "localhost" frontend origin',
  !!corsMatch && corsMatch[1].includes('http://localhost:3000'),
  `found ${corsMatch ? corsMatch[1] : '(backend/.env.example not found or missing CORS_ORIGINS)'}`
);

// --- B: no localStorage/sessionStorage JWT storage exists anywhere ---
const TOKEN_LIKE = /token|jwt|access_token|auth_token|bearer/i;
const storageCallPattern = /(localStorage|sessionStorage)\.(setItem|getItem)\(\s*([^,)]+)/g;
const suspiciousStorageUses = [];
for (const file of collectSourceFiles(SRC)) {
  const content = fs.readFileSync(file, 'utf8');
  let m;
  while ((m = storageCallPattern.exec(content)) !== null) {
    const keyExpr = m[3];
    if (TOKEN_LIKE.test(keyExpr)) {
      suspiciousStorageUses.push(`${path.relative(ROOT, file)}: ${m[0]}`);
    }
  }
}
check(
  'B: no localStorage/sessionStorage call references a token/JWT-like key anywhere in src/',
  suspiciousStorageUses.length === 0,
  suspiciousStorageUses.join('; ')
);

// --- C: a single optional/background 401 must not force a global logout ---
// The old defect was a direct, unconditional `window.location.href =
// '/login'` inside the shared axios interceptor - any 401, from any of
// the ~50 API domain objects, triggered an immediate hard redirect.
// The fix removed that hard redirect entirely in favor of a
// deduplicated event (see D below) - so api.js must no longer contain
// any `window.location.href` assignment at all.
check(
  'C: utils/api.js no longer hard-redirects (window.location.href) on an ordinary 401',
  !/window\.location\.href\s*=/.test(apiJs),
  'a window.location.href assignment is still present in api.js'
);
check(
  'C: utils/api.js single-flight-guards the session-invalidated event (only the first 401 in a burst acts)',
  /sessionInvalidationHandled/.test(apiJs) && /woodful:session-invalid/.test(apiJs),
  'expected a sessionInvalidationHandled guard dispatching a woodful:session-invalid event'
);
check(
  'C: utils/api.js exempts the auth bootstrap call (/api/auth/me) from the ordinary-401 path',
  /isBootstrapCheck/.test(apiJs) && /AUTH_BOOTSTRAP_PATH/.test(apiJs),
  'expected the interceptor to special-case the bootstrap /api/auth/me call'
);

// --- D: genuine session invalidation still redirects to /login ---
const appJsx = read('src/App.jsx');
check(
  'D: App.jsx listens for the session-invalidated event and dispatches logout',
  /addEventListener\('woodful:session-invalid'/.test(appJsx) && /dispatch\(logoutAction\(\)\)/.test(appJsx),
  'expected an event listener that dispatches the logout action'
);

const infrastructureJsx = read('src/components/Infrastructure.jsx');
check(
  'D: ProtectedRoute still redirects to /login once isAuthenticated is false',
  /<Navigate to="\/login" replace \/>/.test(infrastructureJsx),
  'expected ProtectedRoute\'s unauthenticated branch to still redirect to /login'
);

// --- Bonus: Requirement 8 - bootstrap call must be idempotent under StrictMode double-invoke ---
check(
  'Bonus: App.jsx guards the auth bootstrap call against a StrictMode double-invoke',
  /hasStartedBootstrap/.test(appJsx),
  'expected a ref-based guard around the authAPI.me() bootstrap call'
);

console.log('');
if (failures === 0) {
  console.log('All auth/session-contract static checks passed.');
  process.exit(0);
} else {
  console.log(`${failures} auth/session-contract static check(s) FAILED.`);
  process.exit(1);
}
