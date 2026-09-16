# Woodful Creations — P0/P1 Defect Repair Report

**Scope:** the 13 defects below, as given.
**Status:** all 13 addressed. P0-1 and P0-2 were already fixed and delivered in the prior session (auth/session-stability engagement); this report covers that work plus all of P1 (items 3–13), fixed in this session.

Verification method throughout: this sandbox has no PyPI/npm registry access (confirmed by 403s from both registries), so nothing could be run end-to-end. Every backend change was verified with `python3 -m py_compile` (a full sweep of `app/` and `alembic/` passes cleanly); every frontend change was verified with bracket-balance scripts across all `.js`/`.jsx` files (34 files, all balanced) and, where a Phase A static-checker script already existed (`scripts/verify_auth_session_contract.js`), by actually running it with `node` — all 10 checks still pass. Nothing here was exercised against a live database or a running React build. Anything that would benefit from a real test run against a live backend/DB is flagged below.

---

## P0 — already fixed (prior session)

**1. Authentication cookie/session stability** and **2. 401 handling** — root cause was a `SameSite` cookie/site-mismatch between frontend and backend default hosts, plus a hard-redirect-on-401 that raced React's own auth state. Fixed via host consistency (`localhost:8000` everywhere), a `woodful:session-invalid` event replacing the hard redirect, and a StrictMode-safe bootstrap guard. 10 new regression tests added in `backend/tests/test_auth.py`. Full detail in the previous session's delivery.

---

## P1 — fixed this session

### 3. React StrictMode duplicate initialization
Investigated beyond the auth-bootstrap fix already in place. Swept every `useEffect` in the frontend for the two ways StrictMode's dev-only double-invoke can cause real harm: an effect that performs a write (POST/PUT/DELETE/create) directly, or an effect that opens something (interval, listener, socket) without a matching cleanup.

Findings: no effect anywhere in the codebase performs a write. Every effect using `setInterval` or `addEventListener` (`Navigation.jsx`'s unread-count poll, `Assistant.jsx`'s loading-step ticker, `App.jsx`'s session-invalid listener) already returns a proper cleanup function, so StrictMode's mount→cleanup→mount double-invoke is harmless by construction. There is no `WebSocket`/`EventSource`/`Worker` usage anywhere. The auth-bootstrap effect (fixed previously) was the only genuine defect in this class — confirmed, not reintroduced.

**Outcome: verified clean, no further code change needed.**

### 4. Dashboard request explosion
`DashboardPage.jsx` fires 10–11 concurrent requests on every load. The clearest, highest-confidence defect within that: a `Promise.all([purchasesAPI.list(...), paymentsAPI.list(...), purchasesAPI.list(...)])` block fired unconditionally for every user, but the two backend endpoints it calls (`list_purchases`, `list_payments`) are both `Depends(require_role("master"))` — every non-master employee's dashboard load was guaranteed 3 wasted round-trips that always 403. Gated that block behind `isPrivileged`, matching every other master-only widget on the page.

*File: `frontend/src/modules/reporting/pages/DashboardPage.jsx`.*

### 5. Dashboard staff attendance query
`GET /api/dashboard/staff` — called on every dashboard load, for every user — was loading the **entire** `attendance` table (every clock-in/out row, for every employee, since the business opened; no date bound, no limit) into Python on every single request, plus a per-employee task GROUP BY and a Python loop building a full performance breakdown. None of that computed data (`employee_performance`, `total_overtime`, `task_status_summary`) is actually rendered by the Dashboard widget — confirmed by checking every field the frontend reads from this response. It's a duplicate of what the Analytics "Workforce" tab already computes independently via its own route. Stripped the dashboard route down to only the four fields it actually uses (`active_employees`, `pending_tasks`, `completed_tasks`, `production_status_summary`) — the full attendance-table load is gone from the hot dashboard path entirely.

*File: `backend/app/modules/reporting/api.py` (`staff_dashboard`).*

### 6. Dashboard at-risk calculation
`GET /api/dashboard/at-risk-orders` computed the full business-wide at-risk order list — every open order with a material shortage, each enriched with a full materials breakdown and per-material supplier options — on every dashboard load, for every user. The underlying calculation itself was already N+1-free (confirmed by re-reading `StockService.calculate_at_risk_orders` in full: bulk queries throughout, no per-order loop), so this wasn't an algorithmic bug — it was over-fetching: the dashboard widget only ever renders the top 4 results (`.slice(0, 4)`), but the backend built and returned the complete set every time, including a real supplier-options query for materials belonging to orders that would never be shown.

Added an optional `limit` parameter to `calculate_at_risk_orders` (defaults to `None`, so the three other real callers — the alerts/automation job, an operations at-risk flag lookup — are unaffected and continue to get the true, complete set). The dashboard route now passes `limit=10` (matching the `TOP_ORDERS_LIMIT` pattern already used elsewhere on this page), and the function sorts orders by shortage before the limit is applied, so the same top-N-by-severity ordering is preserved — the supplier-options enrichment and per-order result assembly just don't run for orders beyond the cutoff anymore.

*Files: `backend/app/modules/inventory/services.py` (`calculate_at_risk_orders`), `backend/app/modules/reporting/api.py` (`at_risk_orders_dashboard`).*

### 7. Employee Detail unbounded production-job query
The Employee Detail page fetched the entire `production_jobs` table and filtered it down to one employee's jobs in React — confirmed by the frontend's own prior code. Added a server-side `employee_id` filter to `GET /api/production-jobs/` and switched the frontend to use it.

*Files: `backend/app/modules/operations/api_production.py`, `frontend/src/modules/hr/pages/WorkforcePages.jsx`.*

### 8. Employee Detail unbounded order query
The same page's "assign to project" order dropdown called `ordersAPI.list()` with no filter, relying on an incidental default `limit=100` server-side rather than a deliberate scope. Added an `active_only` filter (excludes completed orders) plus an explicit `limit=200`, matching what the dropdown is actually for.

*Files: `backend/app/modules/sales/api.py` (`list_orders`), `frontend/src/modules/hr/pages/WorkforcePages.jsx`.*

### 9. Employee 360 GET causing DB writes
`employee_lifecycle()` performs `db.add()` + `db.commit()` (seeding missing checklist items, syncing others) and was reachable from a plain `GET /360-overview` via `employee_overview`/`employee_needs_attention` — a GET request with side effects. Split the function: `employee_lifecycle()` remains the write-performing version for the dedicated checklist route (`GET /lifecycle`, which genuinely needs real row IDs to let a user check items off), now hardened with an `IntegrityError` catch-rollback-retry against the pre-existing unique index (`ux_employee_lifecycle_items_employee_phase_key`, from migration `0076`) in case of a concurrent seed race. A new `employee_onboarding_progress_readonly()` — pure read, no writes — now backs the summary/overview GET paths. Proactive seeding was also added at the real write points (`create_employee`, `update_employee`) so the checklist is populated when an employee's record actually changes, not lazily on every GET.

*Files: `backend/app/modules/hr/services.py`, `backend/app/modules/hr/api.py`.*

### 10. Employee activity timeline loading entire history
`employee_activity_timeline()` ran 6 unbounded `.all()` queries (leaves, salary slips, salary advances, documents, audit log, lifecycle items) and only sorted/limited the merged result in Python — meaning every source was fully loaded regardless of how much history existed. Added `.order_by(<date>.desc()).limit(limit)` to the 5 genuinely unbounded sources (the 6th, lifecycle items, is a small fixed catalog and left as-is). This is a standard top-K-per-source merge: since each source is already sorted and limited to the same `limit`, and the final result only ever takes the top `limit` of the merged set, no row that could appear in the final output is excluded by limiting each source individually.

*File: `backend/app/modules/hr/services.py`.*

### 11. SalaryAdvanceResponse validation defect
`SalaryAdvanceResponse` was the only `*Response` schema in `hr/schemas.py` missing `class Config: from_attributes = True` — confirmed by checking every sibling response class in the file. Since `_serialize()` calls `.model_validate()` directly on a SQLAlchemy ORM object, this would raise a `pydantic.ValidationError` on every salary-advance endpoint (list/create/get/approve/reject/recover) at runtime. Added the missing Config block.

*File: `backend/app/modules/hr/schemas.py`.*

### 12. Baseline migration correctness
Independently re-verified `0073_baseline_current_schema.py` (the 1368-line consolidated baseline covering the historical 0001–0072 chain) against the current models, rather than trusting its own extensive self-documentation at face value:

- **Migration chain integrity:** all 5 migration files (`0073`→`0077`) form a single unbroken chain, no branches, no duplicate revision IDs.
- **Table/column coverage:** wrote an AST-based extractor that reads every `models.py`-equivalent file across the whole backend (76 tables found, including ones defined outside the `modules/*/models.py` convention — auth, audit, documents, recruitment, id-sequencing) and compared it against every `create_table_if_missing`/`add_column_if_missing` call across all 5 migration files. **Zero drift**: every table and every column the models declare is created by the migration chain, and nothing is created by the migrations that the models don't declare.
- **Type/nullable correctness:** extended the same comparison to column types and `nullable` flags. **Zero mismatches** across all shared columns.
- **The two documented special cases:** the baseline's own docstring calls out `estimates.order_id` (a unique index the model itself doesn't declare, added by old migration 0067) and `payments.reference_number` (a Postgres/SQLite partial unique index for `CASH-%` references, from old migration 0062) as schema elements not expressible as plain model columns. Both verified present and correctly declared.
- **Index name collisions:** no duplicate index names across any migration file.
- **Foreign key targets:** every `ForeignKey("table.column")` reference in the baseline resolves to a table the migration chain actually creates — no typos.
- **Downgrade behavior:** deliberately raises `NotImplementedError` rather than attempting a destructive downgrade from the schema floor — reasonable and intentional, not a bug.
- **Idempotent-migration mechanics:** `run_startup_migrations()` (in `app/platform/database.py`) already runs the full chain unconditionally against any starting DB state rather than guessing/stamping a revision, with a Postgres advisory lock for multi-instance safety — this was itself a documented prior fix and is sound.

**Outcome: verified correct on every axis checkable without a live database. No defect found; no code change made.** (The one thing this cannot rule out, and the migration's own docstring already says so: a schema element applied by hand directly against a database outside of any migration would be invisible to a static read of migration history. That's a monitoring/discipline concern, not a bug in this file.)

### 13. Remove/restrict obsolete client portal (Woodful is internal-only)
`clients/portal_api.py` implemented a fully public, token-only, no-auth-at-all API surface (`/api/client-portal/*`) for external clients to review/approve estimates and check order status — the one part of this application with no `Depends(get_current_user)`/`require_role` of any kind. Since Woodful is internal-only, **restricted** rather than deleted, for a reversible, low-risk change:

- The router is no longer registered in `app/api/routes.py` — every `/api/client-portal/*` route now 404s for anyone, from anywhere.
- The two staff-triggered "generate client link" endpoints (`POST /orders/{id}/client-link`, `POST /estimates/{id}/client-link`) now return `410 Gone` with a clear message, instead of minting a token for a link that would only 404.
- The two client-facing emails (`send_order_email`, `send_estimate_email`) no longer generate a token or append a client-portal link to the outgoing message — the emails still send normally (PDF attachment, subject/body) for whatever purpose staff use them for, just without a dead link.
- Frontend: removed the two public routes (`/review-estimate/:token`, `/my-order/:token`) and their pages, the "Get Client Approval Link" / "Get My Order Link" buttons and their supporting state on the Estimate/Order detail pages, `clientPortalAPI` and both `generateClientLink` API methods from `utils/api.js`, and deleted the now-orphaned `ClientPortalPages.jsx`.
- **Nothing was deleted at the data layer** — `portal_api.py` itself, the `ClientAccessToken`/`ClientActivity` models, and their migrations are untouched, so re-enabling this (if that product decision is ever reversed) is a one-line change (re-adding the router import/registration), not a rebuild.

*Files: `backend/app/api/routes.py`, `backend/app/modules/clients/portal_api.py` (docstring only), `backend/app/modules/sales/api.py`, `frontend/src/App.jsx`, `frontend/src/utils/api.js`, `frontend/src/modules/sales/pages/SalesDetailPages.jsx`; removed `frontend/src/modules/clients/pages/ClientPortalPages.jsx`.*

---

## Recommended follow-up (not done here, out of this defect list's scope)
- Run the full backend test suite (`pytest`) and a real frontend build against a live environment with registry access — everything above was verified statically only.
- Items 5/6/12 turned out to already be well-optimized or already-correct on the axes checked; if there's a specific slow-query symptom still being observed in production for the dashboard or at-risk workflow, a live EXPLAIN/profiling pass would catch anything outside what a static read can verify (e.g., missing DB indexes, connection-pool exhaustion under real concurrent load).
- Item 13: if any external integration or scheduled job elsewhere in the codebase (outside `sales/api.py`) still calls `generate_client_access_token`/`build_client_link_email_footer`, a repo-wide grep after this delivery is a good idea before considering the portal fully inert — none was found in this sweep, but this was a manual/AST-based search, not an exhaustive dynamic trace.
