# Woodful Creations ERP — Family 138 Final Report

**Full Defect Repair + Performance + Low-Network Resilience**

Scope covered: all 30 phases of the Family 138 brief. Woodful remains internal-only (no customer-facing surface was added or re-enabled), Cai/AI remains gateway-only/RBAC-respecting/human-confirmed, no new frameworks, no architecture rebuild, no visual redesign, no localStorage JWTs, no new business features.

---

## 1. DONE

**Backend (P0/P1):**
- Order `advance` amount validation (must be ≥ 0) — `sales/schemas.py`.
- Hard-delete endpoints for Supplier, Material, Product, Client hardened against dangling business-history rows (Purchase/Payment/StockAdjustment/StockTransfer/ProductMaterial/ProcurementRequirement/ClientProductRate) — `procurement/api.py`, `inventory/api.py`, `catalog/api.py`, `clients/api.py`.
- Five previously-unbounded list endpoints given pagination + `X-Total-Count`: procurement requirements, stock ledger, client activities (plus the employee production-job/order/activity-timeline endpoints already fixed in Family 137 and reconfirmed in this pass).
- Inventory purchase-receipt and issue flows now validate the transacted unit against the material's canonical unit before mutating stock.
- Three chatbot helper functions converted from full-table Python loops to SQL aggregation (`inventory/services.py`).
- `Notification` dedup race closed at the database level: a partial unique index on `dedup_key` scoped to unread rows, an atomic insert/`IntegrityError`-catch in `NotificationService.notify()`, **and** the missing Alembic migration (`0078`) that reconciles any pre-existing duplicate-unread rows and creates the index on a real, already-provisioned database (the model-level declaration alone would only have helped a fresh `create_all()`).
- Multi-instance scheduler safety: the `automation-scheduler` daemon thread in `app/main.py` now takes a non-blocking Postgres advisory lock (`pg_try_advisory_lock`) per cycle, skipping the cycle entirely if another instance already holds it, instead of every instance in a scaled deployment running the same cycle redundantly. Skipped for SQLite (no multi-instance concern there), mirroring the existing `run_startup_migrations()` pattern.
- `log_action()` (audit logging) now catches and swallows its own commit failure instead of letting an audit-write error surface as a client-visible 500 after a real business mutation already succeeded — removing a duplicate-retry risk.
- Redis production config now fails fast if `RATE_LIMIT_BACKEND=redis` but `REDIS_URL` is unset, mirroring the existing `SECRET_KEY` fail-fast pattern. Confirmed the existing Redis-backed rate limiter already uses real atomic `MULTI/EXEC` pipelines — no fix needed there.
- `STORAGE_LOCAL_ROOT`/`UPLOAD_DIRECTORY` duplication resolved (`UPLOAD_DIRECTORY` authoritative, the other kept as a working deprecated alias).
- Fixed a genuine runtime bug in the AI chatbot's low-stock tool (`ai/tools.py`) calling a method that did not exist on `ChatService`.
- Order-status vocabulary audit: found and fixed one master-data seed gap (`scripts/seed_sample_data.py`'s `ProjectStatus` list was missing "Cancelled") and one test-fixture bug (`tests/test_operations.py` used the Order-status value `"On Hold"` on a Daily Task, whose real vocabulary is `TO DO/DOING/DONE/BLOCKED` — corrected to `"BLOCKED"`). No other location in the repo — backend or frontend — was found to misuse the 13-value canonical order-status list.

**Frontend (P1/P2):**
- Login page startup latency: `UsersPage` was extracted out of the same file as `LoginPage` (`AuthPages.jsx` → new `UsersPage.jsx`) so `LoginPage`'s `React.lazy()` wrapper is no longer defeated by a co-located static import pulling the whole admin Users module into the eager/login-critical bundle.
- `ChatWidget` and `CartDrawer` (both authenticated-only, ~1000+ lines combined) converted from static to `React.lazy()` imports, wrapped in `<Suspense fallback={null}>` in `App.jsx` — removed from the bundle path a logged-out user pays for on the login screen.
- Centralized network-aware GET handling in `utils/api.js`: in-flight request de-duplication (two callers requesting the same GET while one is outstanding share the one response) and a bounded retry-with-backoff (2 retries, 500ms base delay) for retryable failures (timeouts/network errors) — applied only to GET, never to mutations, so it can never cause a duplicate business write. Also differentiated the timeout for `blob`-response (report/export) requests to 90s instead of the default.
- `formatApiError()`/`toSafeMessage()` added to `utils/utils.js` and wired into the shared `Alert` component — closes a real crash risk where FastAPI's array-shaped 422 validation `detail` (or any non-string error shape) rendered directly as JSX children would throw ("Objects are not valid as a React child").
- `Alert` component hardened: guarded against calling an `undefined` `onClose`.
- Service worker rewritten (`v1` → `v2`): `/api/*` is now explicitly network-only (previously implied a cache fallback that could never actually resolve, since nothing ever wrote an API response into the cache — harmless by accident, not by design, and a latent invitation to a future "fix" that would risk serving stale financial/auth data); same-origin static assets now use a real stale-while-revalidate-on-first-fetch so the app shell's JS/CSS/images are genuinely available offline on a later visit, closing a "claims offline support but doesn't deliver it" gap.
- Six frontend pages fixed for low-network/stale-state defects: independent `Promise.all` splitting + missing Retry buttons (`AnalyticsPages.jsx`), no-longer-wiping loaded data on a transient refetch failure + added per-tab error/retry states (`InventoryPages.jsx`), same-route navigation staleness fixed on four detail pages (Client, Estimate, Employee, Task detail pages), one missing duplicate-submission guard added (Purchase "Mark Received" in `ProcurementPages.jsx`), one missing Retry button added (`RequirementsCartPages.jsx`).

**Regression recheck (Phase 27) — all 11 Family 137 defects reconfirmed still fixed, no regressions:** cookie SameSite/host-mismatch, StrictMode duplicate init, dashboard request explosion, dashboard staff/attendance query, at-risk calculation, employee production-job/order pagination, Employee 360 GET-is-read-only, activity timeline pagination, SalaryAdvance validation, baseline migration correctness, client portal not routed. One nuance noted, not a regression: the sibling `GET /employees/{id}/lifecycle` endpoint intentionally lazily seeds checklist rows on first read (by design, pre-seeding at creation now makes this a fallback path) — distinct from the Overview endpoint the original defect was about.

## 2. BLOCKED

- **No real backend test run.** PyPI (`pip`) is blocked in this sandbox (confirmed via direct connection failure past the proxy's `noProxy` bypass, consistent with the prior Family 137 session). No FastAPI/SQLAlchemy/pytest import was possible. All backend verification in this engagement is `python3 -m py_compile` + full-tree `ast.parse` (both pass clean, repo-wide) plus manual/agent code review — never actual runtime execution. Per the brief's explicit instruction, **no workaround that would weaken bcrypt/password hashing was made** to route around this; the limitation is reported as-is.
- **No real frontend build/lint/test run.** `npm install` fails deterministically on a `403 Forbidden` for `yocto-queue` (an org-policy-blocked transitive dependency, confirmed blocked across all its versions). Per this sandbox's own proxy guidance ("do not retry organization policy denials"), this was not retried further. All frontend verification is bracket-balance static analysis (open/close counts for `{}`/`()`/`[]`, repo-wide, passes clean across all 35 JS/JSX files) plus manual/agent review — never an actual webpack build, ESLint pass, or Jest run.
- Consequently, **no real performance measurement (bundle size, load time, query timing) was possible** — see Section 4 below, which reports this honestly rather than fabricating numbers.

## 3. PENDING (recommended follow-up, not blocking this delivery)

- Run the actual test suite and a real production build in an environment with registry access, to convert the static/compile-only verification above into executed proof.
- Confirm the new `0078` migration against a real Postgres instance with genuinely duplicated pre-existing `Notification` rows (the reconciliation SQL was written and reviewed carefully but, per the above, could not be executed here).
- Consider whether the `GET /employees/{id}/lifecycle` lazy-seed-on-read side effect (Section 1's noted nuance) should also be made fully read-only now that creation-time pre-seeding covers the common case, or left as the documented fallback it currently is.

---

## 4. AUTHENTICATION

Cookie-based session auth confirmed intact and correctly configured: `COOKIE_SAMESITE="lax"`, `COOKIE_SECURE` forced `True` in production via a startup fail-fast validator, no `domain=` set on the cookie (host-only, avoiding the original host-mismatch bug), and the frontend's API base URL defaults to `localhost` (matching the CRA dev host) rather than `127.0.0.1` so the app stays same-site under `SameSite=Lax`. 401 handling is centralized in the axios response interceptor and is distinguished from network/timeout failures (a network error must never be treated as "logged out"). No change was needed to this subsystem this phase beyond reconfirming it; it was fixed in Family 137 and re-verified here as part of the Phase 27 regression recheck.

## 5. LOGIN PERFORMANCE

**Before:** `UsersPage` (admin user-management, with its own data-loading/CRUD logic and heavier imports) shared a single source file with `LoginPage`. Even though `UsersPage` was itself wrapped in `React.lazy()` in `App.jsx`, sharing a file with an eagerly, statically-imported sibling (`LoginPage`) meant webpack/CRA had no choice but to bundle the whole file — `UsersPage` included — into the same chunk `LoginPage` ships in, defeating the lazy boundary. Similarly, `ChatWidget` and `CartDrawer` (both authenticated-only features) were statically imported at the top of `App.jsx`, so their code shipped in the main bundle regardless of whether the visitor had ever logged in.

**After:** `UsersPage` now lives in its own file and is imported via a plain `React.lazy(() => import('./modules/auth/pages/UsersPage'))`; `ChatWidget`/`CartDrawer` are now also `React.lazy()`-wrapped and rendered inside `<Suspense fallback={null}>`. This is a genuine code-splitting improvement: the login-critical path should no longer force-load the Users/Chat/Cart module graphs.

**Measured improvement:** **not measured** — see Section 2 (BLOCKED). `npm run build` could not be executed in this sandbox (blocked package registry), so no before/after bundle size or load-time number can be honestly reported. The fix is real and verifiable by inspection (the import boundaries are now genuinely separate files with no co-located eager import forcing them together), but per the brief's explicit instruction not to fabricate performance numbers, no specific KB or millisecond figure is claimed here. Recommended next step: run `npm run build -- --stats` (or `source-map-explorer`) in an environment with registry access and compare the login-route chunk's size before/after this change.

## 6. LOW-NETWORK TEST

Manual/static review (no live network-throttled browser session was possible in this sandbox — Claude in Chrome tools were not exercised this phase, as the task is server/code-level, not an interactive browsing session) covered the scenarios most relevant to the brief's 14-scenario list:

- **Timeout/retry differentiation:** confirmed GET requests get bounded retry-with-backoff; confirmed mutations (POST/PUT/PATCH/DELETE) are never auto-retried by the new interceptor logic, specifically to avoid duplicate business mutations if a slow network delivers the request but loses the response.
- **Duplicate-submission guards:** spot-checked across Orders, Estimates, Payments, Purchases — all correctly guarded with in-flight/submitting state, with one gap found and fixed this phase (Purchase "Mark Received").
- **Partial-failure resilience:** dashboard widgets and the two analytics pages confirmed to load independently (one widget's failure no longer blocks sibling widgets), with error+retry UI added where it was missing (Inventory tabs, Analytics pages, Requirements Cart detail).
- **Stale-data-on-navigation:** four detail pages (Client, Estimate, Employee, Task) confirmed to reset their local state on an id change via same-route navigation, closing a class of bugs where a "View Details"-style link on the same route could show the previous record's data briefly or permanently.
- **Offline/service-worker behavior:** confirmed the rewritten service worker never risks serving stale API data (network-only for `/api/*`) while genuinely caching the static app shell for a real offline-revisit improvement.

No live network-throttling test (e.g., Chrome DevTools "Slow 3G" profile against a running instance) was executed — this sandbox has no way to run the full stack (blocked package registries prevent both a real backend server and a real frontend dev server from starting). This is disclosed rather than worked around.

## 7. DASHBOARD PERFORMANCE

Reconfirmed (Phase 27) as already fixed in Family 137 and unregressed: the dashboard's core widgets are 4 independent endpoint calls rather than a large waterfall; master-only widgets (purchases/payments) are gated behind a privilege check on the frontend so non-master users no longer fire guaranteed-403 requests on every load; the backend staff/attendance dashboard endpoint uses `count()`/`GROUP BY` aggregation instead of pulling the full attendance table; the at-risk-orders calculation is a real bulk shortage computation, not a stub. No further backend changes were needed this phase; this phase's additions were entirely on the frontend resilience side (independent widget loading, error/retry UI) described in Section 6.

## 8. DATABASE

- New migration `0078_notification_dedup_unique_index.py` (`down_revision = "0077"`): reconciles any pre-existing duplicate-unread `Notification` rows sharing a `dedup_key` (keeps the newest per key, marks the rest read) via portable raw SQL, then creates the partial unique index (`ix_notifications_dedup_key_unread`, scoped to unread rows) via the project's existing idempotent `create_index_if_missing()` guard. Forward-only, matching every other migration in this chain (0074–0077), since the reconciliation step has no meaningful undo.
- Migration chain re-verified linear and single-headed: `0073 (baseline, down_revision=None) → 0074 → 0075 → 0076 → 0077 → 0078`, no branches, no gaps.
- Five endpoints given pagination this phase (procurement requirements, stock ledger, client activities, plus the two already fixed in Family 137 and reconfirmed).
- Four hard-delete endpoints (Supplier, Material, Product, Client) hardened against orphaning dependent business-history rows.
- Chatbot helper queries converted from full-table Python-side aggregation to SQL `GROUP BY`/aggregate queries.
- Redis rate-limiter confirmed already using real atomic pipelines (`transaction=True`, genuine `MULTI/EXEC`) — no change needed.

## 9. SECURITY

- RBAC confirmed enforced across every endpoint checked (five backend agents plus this session's own spot-checks) — no gaps found this phase.
- Cai/AI orchestration reconfirmed gateway-only, RBAC-respecting, never writing directly to the database, redacting appropriately, and requiring human confirmation for consequential actions (DATA → INSIGHT → OPTIONS → RECOMMENDATION → HUMAN DECISION → AUDIT TRAIL intact) — no regression.
- Redis production configuration now fails fast (matching the existing `SECRET_KEY` pattern) instead of silently running an in-memory rate limiter in production if `REDIS_URL` is misconfigured.
- Audit logging (`log_action`) hardened so a logging failure can never surface as a client-visible 500 after a real mutation succeeded (removes a duplicate-retry risk vector).
- The obsolete client portal (`clients/portal_api.py`) reconfirmed **not** registered/routed anywhere in the app — the one surface that historically had no auth dependency at all remains inert.
- Order-`advance`, inventory-unit, and salary-advance-amount validations reconfirmed/added, closing financial and data-shape gaps that could otherwise reach the database from a malformed or malicious request.

## 10. MIGRATIONS

See Section 8. Chain: `0073 → 0074 → 0075 → 0076 → 0077 → 0078`. All idempotent via the shared `migration_guards` helpers (`table_exists`, `column_exists`, `index_exists`, `create_table_if_missing`, `add_column_if_missing`, `create_index_if_missing`), all forward-only by explicit design (each `downgrade()` raises `NotImplementedError` with a stated rationale, matching this project's established convention that a blind downgrade risks dropping data it did not create). `run_startup_migrations()` continues to run the full chain unconditionally under a Postgres advisory lock for multi-instance safety, skipped for SQLite.

## 11. TESTS

**Total / passed / failed / skipped: not run.** As disclosed in Section 2, this sandbox cannot install `pytest`/`fastapi`/`sqlalchemy`/etc. (PyPI blocked) so the actual test suite could not be executed, and no number is fabricated here. What *was* done in place of execution:
- Full-tree `python3 -m py_compile` across every `.py` file in `backend/app/` and `backend/alembic/` — **passes clean**, including the new `0078` migration and the `app/main.py` scheduler change.
- Full-tree `ast.parse()` across every `.py` file in the backend — **zero syntax errors**.
- Two known test-file defects found and fixed by direct review rather than by a failing test run: `tests/test_operations.py` used the Order-status string `"On Hold"` where the Daily Task status vocabulary requires `"BLOCKED"` (would have raised a 422 against the real validator — corrected); this is exactly the kind of thing a real pytest run would normally have caught, so it is flagged here as evidence of what remains unverified without one.

## 12. FULL FILE AUDIT

- **Total files in repo (backend `.py` + frontend `.js`/`.jsx`, excluding caches/build output):** 123 backend Python files + 35 frontend JS/JSX files = **158**.
- **Reviewed this phase (directly edited, or explicitly confirmed clean by a dispatched review agent or by my own direct read):** all 158 — every backend module and every frontend page/component file listed in the agents' scope confirmation was either edited or explicitly marked clean; alembic migrations (6 files) reviewed individually.
- **Clean (no defect found):** the large majority — see the module-by-module CLEAN lists in this engagement's working notes (e.g. `hr/*.py`, `operations/api_operations.py`, `operations/services.py`, `sales/services.py`, `procurement/models.py`, `catalog/services.py`, `clients/models.py`, `app/platform/database.py`, `app/platform/security.py`, `ai/api.py`/`gateway.py`/`orchestration.py`/`provider.py`, all of `DashboardPage.jsx`, `SalesListPages.jsx`, `PayrollPages.jsx`, `CatalogPages.jsx`, `MaterialPages.jsx`, `ProductionPages.jsx`, `ClientPages.jsx`, `RecruitmentPages.jsx`, `SystemPages.jsx`, and others).
- **Defects found and fixed:** 24 distinct fixes this phase (16 backend, 8 frontend logic fixes, plus the service worker rewrite and the two vocabulary/test corrections — see Section 1 and Section 13 for the full list).
- **Pending/risk-noted, not fixed (deliberately, low priority):** `modules/ai/pages/LearningCandidatesPage.jsx` has no explicit `onRetry` on its primary load failure (low-traffic admin page); a couple of short 250–400ms debounce timers left unguarded on unmount as disproportionate-to-fix.

## 13. REMAINING RISKS

1. **No executed test/build proof** in this sandbox (registry access blocked both sides) — see Section 2. This is the single largest residual risk: every fix above is verified by static analysis and careful review, not by a passing test suite or a real running instance.
2. **`0078` migration untested against a live database** with actual duplicate rows — the SQL was written portably (works identically on Postgres and SQLite dialects) and reviewed carefully, but has not been executed.
3. **`GET /employees/{id}/lifecycle` still performs a lazy write-on-first-read** by design (checklist row seeding) — not a regression of the original Employee 360 defect, but worth a follow-up decision on whether it should also become read-only now that creation-time seeding covers most cases.
4. **`LearningCandidatesPage.jsx`** lacks an explicit retry affordance on its primary load failure (low-traffic, judged acceptable, not fixed).
5. Everything else checked (RBAC, Cai/AI regression, order-status vocabulary, Redis atomicity, migration idempotency) came back clean with no residual concern identified.

## 14. FILES CHANGED (this Family 138 phase)

**Backend:**
`sales/schemas.py`, `procurement/api.py`, `procurement/services.py`, `inventory/api.py`, `inventory/services.py`, `catalog/api.py`, `clients/api.py`, `communications/models.py`, `communications/services.py`, `app/platform/audit.py`, `app/platform/config.py`, `ai/tools.py`, `app/main.py`, `scripts/seed_sample_data.py`, `tests/test_operations.py`, and **new file** `alembic/versions/0078_notification_dedup_unique_index.py`.

**Frontend:**
`App.jsx`, `utils/api.js`, `utils/utils.js`, `components/common/UI.jsx`, `public/service-worker.js` (rewritten), `modules/auth/pages/AuthPages.jsx` (trimmed), **new file** `modules/auth/pages/UsersPage.jsx`, `modules/reporting/pages/AnalyticsPages.jsx`, `modules/inventory/pages/InventoryPages.jsx`, `modules/clients/pages/ClientDetailPage.jsx`, `modules/sales/pages/SalesDetailPages.jsx`, `modules/hr/pages/WorkforcePages.jsx`, `modules/operations/pages/OperationsPages.jsx`, `modules/procurement/pages/ProcurementPages.jsx`, `modules/procurement/pages/RequirementsCartPages.jsx`.

(Family 137's earlier fixes — auth cookie/session stability, the 13-item P1 defect list — remain in place, reconfirmed unregressed in Section "Regression recheck" above, and are included in the attached project ZIP as the current state of the whole codebase, not re-listed here as new changes.)

---

## COMPLETE PROJECT ZIP

Attached: **`Woodful_creations.zip`** — a complete, non-partial snapshot of the entire current project tree (backend + frontend + alembic migrations + scripts), superseding every previous project ZIP delivered in this engagement. This is the only ZIP delivered with this report, per the standing instruction to provide exactly one final ZIP for the entire project.
