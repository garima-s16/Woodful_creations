# Production Readiness - Woodful Creations

Last reviewed: this session, against the codebase as it currently stands.
Every item below is either directly verified against real files/config in
this repo, or explicitly marked NOT RUNTIME VERIFIED / INFRASTRUCTURE
REQUIRED / BLOCKED. Nothing here is assumed.

This sandbox has no network access and no installed backend/frontend
dependencies. It cannot run pip-audit, npm audit, npm install, npm run
build, pytest, docker build, or connect to any live service (Neon,
Redis, Google Drive, SMTP, Gemini). Everything marked CODE VERIFIED
below was checked by reading the actual source and, for Python, static
compilation plus an import-resolution check across the whole backend.
Nothing marked CODE VERIFIED should be read as RUNTIME VERIFIED.

Target deployment: Domain via GoDaddy, frontend on production hosting,
backend/API on Azure/GCP, a managed database, files in object storage,
a production email service.

## Dependencies

Network access re-tested directly this session: requests to
registry.npmjs.org and pypi.org both return HTTP 403 with
x-deny-reason: host_not_allowed. This is a firm, proxy-level block for
this sandbox, not a transient failure - pip-audit, npm audit, pip
install, npm install, npm ci, and npm run build genuinely cannot be
executed here regardless of how many times they are retried.

- Backend requirements.txt reviewed against known CVE history for the
  exact pinned versions (no pip-audit available - manual, evidence-based
  review). Fixed:
  - python-jose removed entirely, replaced with PyJWT==2.9.0.
    python-jose has had no release since 2021 and carries unpatched
    CVE-2024-33664 (JWE decompression-bomb DoS). Confirmed the only
    consumer (app/platform/security/security.py), migrated, verified
    the algorithm was already pinned server-side (HS256 only, never
    read from the token), so this was a safe drop-in swap.
  - fastapi 0.104.1 to 0.109.2 (Starlette multipart-form DoS fix,
    GHSA-2c2j-9gv5-cj23), uvicorn paired-upgraded for compatibility.
  - python-multipart 0.0.6 to 0.0.18 (CVE-2024-24762, CVE-2024-53981 -
    every file upload endpoint uses this).
  - pillow 10.1.0 to 10.3.0 (CVE-2023-50447, CVE-2024-28219).
  - cryptography 41.0.7 to 42.0.5 (CVE-2023-50782, CVE-2024-26130).
  - reportlab 4.0.7 to 4.1.0 (arbitrary code execution via crafted
    color specs, GHSA-6qhm-w4x5-h396 - this app generates PDFs from
    user-influenced data).
  - sentry-sdk added as an optional, commented-out line - only
    installed if MONITORING_PROVIDER=sentry is actually set.
  - passlib removed entirely, migrated to direct bcrypt calls in
    app/platform/security/security.py. Reported by the user as a real
    ModuleNotFoundError in their own environment - the dependency was
    correctly declared in requirements.txt, but passlib is effectively
    unmaintained (no release since 2020, same risk class as
    python-jose above) and its only actual usage here was a thin
    wrapper around bcrypt.hash/verify with a single scheme configured
    (no other passlib feature was in use). This also removes the
    reason bcrypt itself was pinned to the old 4.0.1 - passlib 1.7.4
    is known to break against bcrypt>=4.1.0 due to a removed internal
    attribute it relied on for version detection. bcrypt upgraded to
    4.2.0 now that constraint no longer applies. The new code
    preserves passlib's exact default behavior of truncating a
    password to bcrypt's 72-byte hard limit rather than raising, so
    existing password hashes continue to verify correctly - this is
    not a new policy, just the same one under a different library.
- NOT RUNTIME VERIFIED: none of the above has been installed and
  exercised - the sandbox has no network access. Run pip install -r
  requirements.txt and the full test suite in a real environment
  before trusting these versions in production.
- Frontend package-lock.json is corrupted - BLOCKED. axios is locked
  to 1.19.0, a version that does not exist in real axios release
  history, and motion (declared in package.json, actively imported by
  8 components) has no entry in the lock file at all. This means
  npm ci - what frontend/Dockerfile actually runs - will fail. This
  cannot be fixed from this sandbox: a truthful lock file requires a
  real npm install against the real npm registry, which needs network
  access this environment does not have. Action required before any
  build: run npm install in frontend/ from a network-enabled machine
  and commit the regenerated package-lock.json.
- .env.example (backend and frontend) reviewed - only placeholder
  values, no real secrets.

## Backend tests

- Full backend compile sweep (python -m py_compile) across every file
  in app/, tests/, scripts/ - clean.
- Custom AST-based import-resolution check (since py_compile only
  validates syntax, not whether an imported module actually exists) run
  across all 262+ backend files - zero broken import targets. Caught
  and fixed 2 stale app.core references in
  tests/security/test_security_and_config.py left over from an
  earlier module rename to app.platform.
- BLOCKED: the actual test suite (pytest, 1120 test functions
  across 47 files, re-counted directly against the current repo) has not been executed - FastAPI/SQLAlchemy/pytest
  are not installed in this sandbox and cannot be installed without
  network access. Static verification above is not a substitute for
  running the suite. Action required: run pytest in a real environment
  before trusting this codebase in production.

## Database and migrations

- Alembic migrations are the only mechanism used for schema changes (66
  migrations, verified well-formed via scripts/verify_migrations.py
  chain), applied automatically on backend startup
  (app/platform/database/auto_migrate.py).
- DATABASE_URL is environment-variable driven - pointing at a managed
  production database requires no code change. Confirmed never exposed
  to frontend source (searched frontend/src for DATABASE_URL,
  SECRET_KEY, and other backend secret names - zero matches).
- Production config validator (config.py) rejects DATABASE_URL
  starting with sqlite when ENVIRONMENT=production - confirmed
  present, re-read whole file this session.
- NEON RUNTIME: NOT RUNTIME VERIFIED. No Neon credentials are available
  in this sandbox. Cannot confirm connection, current migration head
  against the real database, or data persistence across a restart.
  Action required: run migrations and the health endpoint against
  real Neon credentials before production use.

## Security - authentication, RBAC, IDOR

- Reviewed app/modules/auth/ whole-file this session (auth.py,
  users.py, models.py, schemas.py). Timing-safe dummy password
  check against account enumeration, generic error messages, per-IP and
  per-account rate limiting with exponential backoff, reset tokens
  stored only as a hash, single-use enforcement, all other outstanding
  reset tokens for an account invalidated on a successful reset,
  password_changed_at invalidates existing sessions.
- Real defect found and fixed: PasswordResetToken.attempt_count
  could previously only ever be 0 or 1 - it was incremented on the
  success path only, immediately before the token became permanently
  unusable, contradicting its own docstring's claim to guard against
  repeated probing. Fixed to increment and commit on every lookup
  against an already-issued token, including the used/expired failure
  paths. New test coverage added for this
  (tests/modules/auth/test_password_recovery.py).
- UserUpdateAdmin confirmed to have no password field - the generic
  field-update loop in the admin user-update route cannot accidentally
  bypass password hashing.
- Reviewed app/modules/documents/api/routes.py whole-file - explicit
  object-level authorization (parent_type + parent_id + document_id
  must all match) on both download and delete, magic-byte file
  signature validation (not just trusting extension/MIME), streamed
  size limits (not trusting Content-Length), random server-side
  filenames, Cache-Control: no-store on downloads.
- Reviewed app/modules/hr/api/salary_slips.py whole-file - correct
  fetch-then-check IDOR protection on read, mutation restricted to
  master only (no per-ID ambiguity), safe empty-list fallback for a
  non-master user with no linked employee record.
- Real defect found and fixed - reverse proxy / rate limiting: both
  app/platform/security/rate_limit.py and
  app/platform/middleware/middleware.py key their per-IP buckets on
  request.client.host, and nothing in the codebase configured trusted
  proxy headers. Behind any real reverse proxy or load balancer for
  HTTPS termination (the only realistic production topology), every
  request would have appeared to come from the proxy's own IP,
  collapsing every real user into one shared rate-limit bucket. Added
  FORWARDED_ALLOW_IPS config, wired into docker-entrypoint.sh via
  uvicorn's --proxy-headers --forwarded-allow-ips. Defaults to
  127.0.0.1 (uvicorn's own default - correct for no-proxy local dev).
  Action required in production: set FORWARDED_ALLOW_IPS to the
  real proxy/load balancer's address.
- IDOR identifier-substitution testing (authorized resource A vs
  resource B) was reviewed at the code level (query filters, ownership
  checks) for the modules above - not executed as live HTTP
  requests, since the test suite itself could not be run this session.

## Redis / rate limiting

- Shared abstraction exists (app/platform/security/rate_limit.py)
  with in-memory (default) and Redis-backed implementations, switched
  via RATE_LIMIT_BACKEND=memory|redis.
- Per-account limiting and exponential backoff confirmed wired into
  every auth route (login, mobile login, password-reset-request,
  password-reset-verify).
- REDIS RUNTIME: NOT RUNTIME VERIFIED. No Redis instance is reachable
  from this sandbox. Action required: any multi-instance production
  deployment must set RATE_LIMIT_BACKEND=redis and provision a real
  Redis instance, then verify login/password-reset/AI-chat/export rate
  limiting and Redis-failure behavior against it.

## File storage / Google Drive

- All four upload routes (documents, clients, payments, candidates) go
  through the storage abstraction (app/platform/storage/storage.py) -
  no route calls the filesystem or Drive API directly.
- LocalStorageBackend and DriveStorageBackend are both complete
  implementations, not stubs. Drive backend keyed by the real Drive
  file ID (never filename search), persisted onto the record via
  storage_backend/drive_file_id columns.
- Failure-consistency handled: an upload that succeeds but whose DB
  commit then fails triggers cleanup of the orphaned file; deletion
  commits the DB change first and only removes the physical file after
  that succeeds.
- DRIVE RUNTIME: NOT RUNTIME VERIFIED. No Google Drive credentials are
  available in this sandbox. Action required before production: a
  real end-to-end test (upload to real Drive file, persisted file ID,
  download, verify content, delete, verify gone) against real
  GOOGLE_DRIVE_CREDENTIALS_PATH/GOOGLE_DRIVE_ROOT_FOLDER_ID.

## Email / SMTP

- app/modules/communications/services/email_service.py reads SMTP
  host/port/sender/password from settings (environment-driven) -
  confirmed never hardcoded, never exposed to frontend source.
- EMAIL RUNTIME: NOT RUNTIME VERIFIED. No SMTP credentials are available
  in this sandbox. Action required: send a real test email (correct
  sender, recipient, links) and verify authentication-failure/provider-
  failure handling against real credentials before production use.

## AI / Gemini

- Verified the architectural boundary this session: app/modules/ai/
  gateway.py's write-tool dispatch contains explicit user_role not in
  ("master",) checks for every financial/HR-sensitive tool, including
  record_payment specifically - confirmed by direct code inspection,
  not assumed. A code comment at the issue-creation tool explicitly
  notes this replicates the REST route's own require_role("master").
- Financial-amount redaction is applied to outbound messages before
  they reach Gemini (_extract_and_redact_amount,
  _redact_outbound_message, _strip_all_currency_amounts in
  gateway.py) - Gemini is not given raw financial values to process.
- Read tools are dispatched through an explicit table
  (READ_TOOL_DISPATCH), not free-form execution - confirmed Gemini
  cannot call arbitrary application code.
- AI RUNTIME: NOT RUNTIME VERIFIED. No Gemini API key is available in
  this sandbox. Action required: a real test request against actual
  GEMINI_API_KEY, confirming authorization, redaction, and rate
  limiting behave the same way in practice as the code implies.

## Notifications / Automation

- FIXED this session - a real defect, found by actually running the
  master verification script and then inspecting the notification
  read endpoints: GET /api/notifications/ and GET
  /api/notifications/unread-count unconditionally re-ran the entire
  AutomationService.run_all (all ~12 rules) plus
  NotificationService.run_all_checks on every single call, regardless
  of the background automation scheduler (app/main.py,
  AUTOMATION_SCHEDULER_ENABLED=true by default) already running the
  identical logic on its own interval. The docstring's own claim
  ("there's no background scheduler in this app") was stale - the
  scheduler was added after that comment was written and never
  updated. In practice this meant every notification-panel open and
  every unread-count badge poll (typically on a short client-side
  timer), across every logged-in user, independently re-executed the
  full automation engine on top of what the scheduler was already
  doing - a real, unbounded database-load multiplier at any
  meaningful concurrent-user count.
- Fix: both endpoints now only run the on-demand fallback when
  AUTOMATION_SCHEDULER_ENABLED is False; with the scheduler enabled
  (the production default), they are pure reads, exactly as their
  name says. tests/conftest.py now explicitly sets
  AUTOMATION_SCHEDULER_ENABLED=False for the test environment, since
  the test client never runs the real background thread - without
  this, tests would have silently had neither mechanism fire.
- 2 new tests added, proving both branches explicitly (scheduler
  enabled -> automation engine not triggered by the read endpoint;
  scheduler disabled -> it is). NOT RUNTIME VERIFIED - no pytest
  execution possible in this sandbox (network-blocked, no backend
  venv). CODE VERIFIED: full backend compile + import-resolution
  sweep clean after the change.
- Deduplication (dedup_key), idempotency, and financial-visibility
  filtering (_visible_to/FINANCIAL_NOTIFICATION_TYPES) were inspected
  and are unaffected by this fix - unchanged from before.

## Observability / monitoring

- Built this session - previously did not exist at all. No
  monitoring/error-reporting boundary existed anywhere in the backend
  before this session. Added app/platform/monitoring/monitoring.py: a
  provider-neutral boundary (capture_exception/capture_message)
  selected via MONITORING_PROVIDER=none|sentry (config-driven opt-in,
  matching the existing GEMINI_ENABLED/GOOGLE_DRIVE_ENABLED
  pattern). Business/platform code never imports a provider SDK
  directly.
- Context passed to the monitoring boundary is redacted by key name
  (password/token/secret/api_key/authorization/cookie/database_url/
  credential/otp/private_key, case-insensitive, recursive into nested
  dicts) before it reaches a provider or a log line.
- A provider failure (bad DSN, network error, provider outage) is
  caught and logged locally - it can never itself become a second,
  unrelated application failure.
- A global handler for genuinely unhandled exceptions is registered in
  app/main.py - it does not intercept normal HTTPException flows
  (401/403/404 etc still work exactly as before), only exceptions no
  route/dependency caught itself. Returns a safe, generic response,
  never the real exception detail.
- Test coverage added (tests/platform/test_monitoring.py): context
  redaction, provider-failure isolation, and the global handler's
  HTTP-level behavior, exercised through a throwaway test-only FastAPI
  app - never the real production app, so no crash-inducing route
  exists in production.
- MONITORING: INFRASTRUCTURE REQUIRED. The boundary is real and wired
  in, but MONITORING_PROVIDER=none by default - no external provider
  is currently configured, and none is available in this sandbox to
  verify against. Action required if external monitoring is wanted:
  set MONITORING_PROVIDER=sentry and MONITORING_DSN, install
  sentry-sdk (see requirements.txt), and verify a real test error
  reaches the provider with safe context before relying on it.

## Dashboard / database performance

- Reviewed app/modules/reporting/api/dashboard.py whole-file.
  orders_dashboard/staff_dashboard already showed clear evidence of
  prior N+1 fixes (explicit comments describing what was fixed).
- Real defect found and fixed: stock_dashboard was not fixed the
  same way - it loaded every Material row unconditionally
  (db.query(Material).all()), filtered/aggregated in Python, and
  accessed .primary_supplier.name in a loop without eager loading (a
  genuine N+1). Also included inactive materials in stock value,
  category totals, and reorder suggestions, contradicting the
  Material model's own docstring, which says inactive materials
  should be excluded from reorder suggestions. Rewrote to push
  aggregation into SQL (GROUP BY, SUM), eager-load
  Material.primary_supplier/Purchase.material/Purchase.supplier/
  Issue.material/Issue.order via selectinload, and filter
  is_active=True. Verified against the existing financial-RBAC test
  that exercises the exact redaction paths touched
  (tests/security/test_financial_rbac.py) - confirmed logically
  equivalent, not executed live (test suite could not run this
  session).
- app/modules/inventory/api/reports.py's Excel export (a genuinely
  different case - a full data export, not a dashboard widget) was
  already correctly eager-loading its relationships - no change needed.
- Follow-up regression pass found the fix above had duplicated
  Material's stock-value formula (current_stock * average_rate) as a
  second, independent copy inside the SQL query. Converted
  Material.stock_value from a plain @property to a @hybrid_property
  (app/modules/inventory/models.py) - one definition now serves both
  Python-instance access (unchanged output, verified nullable=False on
  both source columns so no behavior change is possible) and SQL-level
  aggregation. dashboard.py updated to use it directly.
- That same search surfaced three more genuine unbounded-query
  defects, all the same db.query(Material/Order/Employee).all() then
  Python-side aggregate pattern, one of them on a live, real
  production path:
  - app/modules/reporting/analytics_service.py's inventory_analytics -
    loaded every material unconditionally on every /api/analytics/inventory
    call. Rewrote to SQL aggregation using the new hybrid expression,
    added the same is_active filter as the dashboard fix. Traced every
    assertion in the existing test_financial_rbac.py coverage against
    the rewrite line by line, including verifying the seeded test
    material (opening_stock 2, minimum_stock 10, default is_active)
    would still appear in the low-stock drill-down, before considering
    this safe.
  - app/modules/inventory/services.py's _stock_summary - called
    directly from the AI chatbot's live dispatch path
    (app/modules/ai/orchestration.py) on every "what's my stock worth"
    style message. Fixed the same way. Two sibling functions in the
    same file, _low_stock and _out_of_stock, had the identical defect -
    fixed both to match their own already-correct sibling function
    _replenishment_requirements, which was already filtering in SQL.
  - app/modules/sales/services.py's _orders_summary and
    _payments_summary - both loaded every Order row just to compute a
    count or a sum. Fixed with direct SQL aggregates. The same file's
    _profitability_summary was inspected and deliberately left
    unchanged - it calls OrderService.profitability_bulk, whose own
    docstring confirms it already runs a fixed 2 queries regardless of
    order count; the Order rows it receives are genuinely necessary
    input to a per-order calculation, not an avoidable N+1.
- Verified two genuinely justified, unchanged .all() patterns while
  reviewing these files, so as not to blindly replace every
  occurrence: bulk Excel-import lookup dictionaries (order_imports.py,
  estimate_imports.py, clients/import_routes.py - loading a full
  lookup table once to match against many uploaded rows via O(1) dict
  lookup is the correct alternative to a query-per-row N+1, not a
  defect) and chatbot fuzzy-name-matching against small, headcount-
  bounded tables (Employee, Supplier) where the match direction
  (is this name a substring of the user's free-text message) cannot
  be expressed as a SQL query at all.
- A focused, non-exhaustive .all() search was performed - not a full
  repository audit - matching the instruction to fix only genuine
  production-impacting issues rather than replace every occurrence
  found.

## Route authorization

- Built and ran an AST-based scanner across every route function in
  the backend checking for a get_current_user/require_role dependency.
  Found and fixed a real, consistent gap: 6 download_template
  endpoints (catalog, sales estimates, sales orders, hr, procurement,
  inventory) had no authorization at all, while every other route in
  the same 6 import modules (preview/commit/error-report) correctly
  required master. Confirmed this was an oversight, not a design
  choice, since the sibling clients import module's download_template
  was already correctly protected.
- Verified the fix would not break the actual download before applying
  it: traced the frontend's usage (plain <a href> top-level navigation
  in all 11 call sites) against the app's cookie-based auth
  (SameSite=lax, which is sent on top-level navigation, unlike a
  fetch/XHR subresource request) - confirmed compatible.
- Added test coverage to all 5 previously-untested modules
  (unauthenticated-rejected and non-master-rejected cases), matching
  the exact pattern already used for each file's sibling commit-
  endpoint test. Re-ran the scanner after the fix - only the 4
  genuinely public auth routes (login, login_mobile, forgot_password,
  reset_password) remain unauthenticated across the entire backend.

## Business end-to-end (code-level, not executed live)

BLOCKED for live execution - no running application exists in this
sandbox to send real HTTP requests against. What follows is a code-
level route-existence and authorization-pattern check, not an
executed journey - it confirms every step of the business flow has a
real, wired backend endpoint with the expected access control, not
that a live request actually succeeded end to end.

- Listed every registered route prefix across the backend (48 total).
  Every step of the MASTER journey (login, client, product, material,
  estimate, order, payment, purchase, inventory/stock, production/
  task, document, report, AI) has a corresponding, registered prefix -
  none are missing.
- Spot-checked the EMPLOYEE restriction boundary at both ends: every
  route in app/modules/sales/api/payments.py requires master with no
  exception (confirms "restricted financial areas" is enforced, not
  just assumed); app/modules/operations/api/daily_tasks.py correctly
  mixes get_current_user (view/update/complete tasks and comments -
  genuine operational work) with require_role("master") reserved for
  creating new task assignments and sending management emails
  (confirms "allowed operational areas" are not accidentally over-
  restricted to master-only either).
- This, combined with the whole-file reviews of auth, documents, and
  salary_slips already recorded above, is the strongest evidence
  available in this sandbox that the business journey's access control
  is correctly wired. It is not a substitute for actually running the
  journey once the runtime blockers above are resolved.

## Web - desktop, tablet, mobile (responsive)

Sandbox limitation stated plainly: this environment has no browser and
no rendering capability of any kind. Everything below is CODE VERIFIED
(read the actual CSS/JSX source for structural correctness) - it is
not RESPONSIVE EMULATION VERIFIED and not REAL DEVICE VERIFIED.
Neither of those can be produced without a real browser.

- Read Table.css, Modal.css, Pages.css, Navbar.css,
  GlobalSearch.css, NotificationBell.css, ChatWidget.css whole-
  file. Found substantial, deliberate prior mobile work already in
  place: dedicated mobile search toggle (search bar hidden, replaced by
  a full-width row below the navbar on narrow screens), 44px touch
  targets on icon buttons, env(safe-area-inset-*) handling for iPhone
  notch/home-indicator areas on the chat widget, horizontal-scroll-
  within-a-bounded-container pattern on data tables (not full-page
  overflow), repeat(auto-fit, minmax(...)) grids that collapse
  columns without needing a media query.
- Ran an automated sweep for fixed pixel widths >= 300px without a
  max-width guard across every CSS file - found 2 candidates
  (NotificationBell.css, ChatWidget.css), both confirmed false
  positives on manual whole-file review: both already have a
  @media (max-width: 480px) override capping the panel at
  calc(100vw - Npx). Zero genuine unguarded fixed-width issues found.
- Real defect found and fixed - duplicate submission on mobile
  touch: CompanyHolidaysPage.jsx's save handler had no in-flight
  guard, and the shared ConfirmDialog component (used for every
  destructive action in the app, confirmed via its own docstring) had
  no submit-guard on either button at all. A rapid double-tap - a more
  common accidental interaction on mobile touch than a desktop click -
  could fire a duplicate holiday creation or a duplicate delete
  request. Fixed ConfirmDialog itself with an optional loading prop
  (backward compatible), then wired it into all 14 usages across 12
  pages, each with its own correctly-scoped in-flight state (verified
  zero naming collisions across 165 total state variables in the
  touched files).
- Verification performed on every JSX file touched this session:
  brace/paren/bracket balance (all 12 files balanced), full-frontend
  relative-import resolution sweep (zero broken imports across the
  entire src/ tree), duplicate-useState-name check (zero
  collisions).

## Mobile web release status

- Responsive desktop: CODE VERIFIED (see above) - not built/rendered.
- Responsive tablet: CODE VERIFIED (see above) - not built/rendered.
- Responsive mobile: CODE VERIFIED (see above) - not built/rendered.
- Mobile browser authentication (iOS Safari / Android Chrome): NOT
  RUNTIME VERIFIED. No browser is available in this sandbox.
- Real iPhone validation: NOT RUNTIME VERIFIED. No real device is
  available in this sandbox.
- Real Android validation: NOT RUNTIME VERIFIED. No real device is
  available in this sandbox.
- Real tablet validation: NOT RUNTIME VERIFIED. No real device is
  available in this sandbox.
- Action required before claiming mobile-web readiness: an actual
  frontend build (blocked today by the corrupted package-lock.json
  above) followed by real browser/device testing of the core business
  flows (login, client, product, material, inventory, supplier,
  purchase, estimate, order, payment, task/production, document,
  report, AI, logout) for both MASTER and EMPLOYEE roles.

## Error handling and logging

- Verified zero broad except Exception handlers in any route file
  that re-serializes internal error details back to the client.
- All detail=str(e)) occurrences trace back to a deliberately-raised,
  app-controlled ValueError/RuntimeError with a safe, user-facing
  message - never a raw system/database exception.
- DEBUG=False by default, with a startup validator refusing
  DEBUG=True when ENVIRONMENT=production.
- Audit logging (app/platform/audit/audit.py) applied across create/
  update/delete for every sensitive module checked this session.
- Global unhandled-exception handler (see Observability above) now
  ensures an unexpected error is both logged and, if a provider is
  configured, reported - not just silently 500'd.

## Backups

- NOT VERIFIED / NOT CONFIGURED: no backup strategy exists in
  application code - this is a function of the managed database
  provider chosen at deploy time (automated snapshots, point-in-time
  recovery). BACKUP: INFRASTRUCTURE REQUIRED.

## Deployment / Docker

- Reviewed docker-compose.yml, docker-compose.prod.yml,
  backend/Dockerfile, frontend/Dockerfile whole-file this session.
  No hardcoded secrets, required environment variables enforced via
  ${VAR:?error message} syntax, database/Redis bound to localhost
  only in the dev compose file, health checks present, no local-DB
  fallback in the prod compose file.
- Real defect found and fixed: frontend/Dockerfile and
  docker-compose.yml both had Windows-style CRLF line endings -
  fixed.
- Real defect found and fixed: see the reverse-proxy /
  FORWARDED_ALLOW_IPS fix under Security above - wired into both
  compose files and .env.example.
- Confirmed docker is not installed in this sandbox at all (command
  not found) - this is a tooling absence, not only the network
  restriction. Both compose files parse as valid YAML (verified with
  PyYAML) with the expected services (docker-compose.yml: database,
  redis, backend, frontend; docker-compose.prod.yml: backend,
  frontend). Every file referenced by COPY instructions in both
  Dockerfiles (requirements.txt, docker-entrypoint.sh, package.json,
  package-lock.json) confirmed to exist on disk.
- BLOCKED: cannot build or run the actual Docker images in this
  sandbox (no Docker daemon, no network to pull base images, and the
  frontend build is separately blocked by the corrupted lock file).
- HTTPS: INFRASTRUCTURE REQUIRED - depends on the hosting/ingress setup
  chosen at deploy time, not application code.

## Frontend/backend separation

- Clean separation confirmed: REACT_APP_API_URL is the only coupling
  point, and the backend has no assumption about how or where the
  frontend is served.

## Secrets and Git safety

- Searched the full codebase (backend, frontend, tests, seed data,
  scripts, config, docs) for hardcoded API keys, tokens, passwords, and
  credentials - none found in source.
- .gitignore exists at the project root covering .env/credential
  files/databases/uploads/node_modules/build artifacts.
- NOT VERIFIED - no Git history exists in this working copy, so history
  scanning for a secret that was committed and later removed could not
  be performed. If this codebase has real Git history elsewhere, that
  history has not been scanned this session.

---

## Summary - must be done before production

1. Frontend lock file (blocker) - package-lock.json is corrupted
   (fabricated axios version, missing motion entry). This session
   re-tested network access directly (registry.npmjs.org and
   pypi.org both return 403 host_not_allowed) and confirmed this
   sandbox cannot reach any package registry. Run npm install from
   an environment with real network access and commit the
   regenerated lock file before any frontend build.
2. Dependency install and test suite (blocker) - confirmed blocked by
   the same network restriction as above (pip cannot reach pypi.org
   either). Install requirements.txt and run the full pytest suite
   in a real environment; nothing has actually executed this session.
3. Real infrastructure verification - Neon/PostgreSQL, Redis,
   Google Drive, SMTP, Gemini all have real, complete code but none has
   been exercised against live credentials. Each needs a real
   end-to-end test before production use.
4. Frontend production build and real device/browser testing - the
   codebase has substantial, genuine mobile-responsive work already in
   place (verified at the code level), but no build has run and no
   real device or browser has rendered any of it.
5. CORS_ORIGINS - set to the real production frontend origin(s).
6. FORWARDED_ALLOW_IPS - set to the real reverse proxy/load
   balancer's address in production.
7. Configure infrastructure-level backups (provider-dependent).
8. If a monitoring provider is wanted, set MONITORING_PROVIDER=sentry
   and MONITORING_DSN, install sentry-sdk, verify a real test error
   reaches it.
9. If this codebase is on a real Git repository, check whether .env
   was ever committed to its history - rotate all secrets if so.

Everything else reviewed above is genuinely ready as code, pending the
runtime verification listed here.
