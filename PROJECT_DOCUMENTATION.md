# Woodful Creations — Project Documentation

## What this is and who it's for

Woodful Creations is a woodcraft/furniture business, and this application is their internal operations system — the tool the office staff, site supervisors, and management actually use to run the business day to day. It is not a public-facing product; there's no customer-facing storefront or portal anywhere in this codebase. Everyone who logs in is either staff or an owner/manager.

The business itself works roughly like this, and the app is shaped around that flow: a client enquires about a piece of furniture or an interior project, the team prepares a cost estimate (material + labor + tax), the client approves it, the enquiry becomes an order, the order gets tracked through design, production, and delivery, materials get pulled from stock or purchased from suppliers as needed, payments come in against the order over time, and at some point the job is complete and delivered. Alongside that, there's a full HR side — hiring (candidates and interviews), employee records, daily attendance, leave requests, and salary slip generation — because this is also the system the office uses to run payroll-adjacent work, not just the workshop.

Because this is an Indian business, that shows up directly in the code rather than being an abstraction: currency is INR and formatted the Indian way (lakhs/crores grouping — see `frontend/src/utils/currency.js`), tax defaults to 18% GST (`Estimate.tax_percent`), and order codes follow a `WC-2026-001` style scheme.

If you're new to the team, the single most useful thing to internalize before touching code is this: **Order** is the center of gravity. Almost everything else — payments, expenses, production jobs, daily tasks, issues, estimates — hangs off an order via a foreign key. When in doubt about how two features relate to each other, start by asking how they both relate to an order.

## How the core workflow is actually modeled

**Clients → Estimates → Orders.** A `Client` can have any number of `Estimate` rows and any number of `Order` rows. Estimates are deliberately *not* locked to a single order — the code comment in `models/estimate.py` is explicit that a client can be quoted before an order is confirmed, because in practice a client might get quoted, go quiet for two months, and only convert later, or might get several competing estimates before picking one. Estimates also support versioning: revising an estimate doesn't overwrite it, it creates a new row with `version` incremented and `parent_estimate_id` pointing back to the original, so the full negotiation history survives. That was added deliberately (see the "estimate version and client activity log" commit) — before that, revising a quote silently lost the old numbers.

**Orders carry their own status across three independent tracks**, not one combined status: `design_status`, `execution_status`, and `delivery_status`, plus an overall `project_status` (Enquiry → ... ) and a `progress_percent`. This exists because in a real furniture/interior project these three things genuinely move independently — design can be finished while execution hasn't started, or execution can be done while delivery is still pending logistics. If you're building anything that shows "order status" in the UI, check which of these four fields is actually the one that matters for what you're building; conflating them is an easy mistake.

**Money on an order is intentionally denormalized for speed, and that has a sharp edge.** `Order.total_received` and `Order.balance` are stored columns, not computed on the fly, because the dashboard reads them a lot and recomputing from all payments on every dashboard load would be wasteful. They're kept in sync by `Order.recompute_totals()` in `models/order.py`, which must be called any time a `Payment` is added or edited. Read the docstring on that method — it explains a real bug that existed here: the `advance` amount is stored directly on the order (not as its own `Payment` row), so if `recompute_totals()` ever summed only the `Payment` rows without adding `advance` back in, the advance would silently vanish from the running total the moment any payment was logged after order creation. If you ever touch payment logic, this is the exact kind of bug to watch for again — anything that recomputes `total_received` from scratch needs to remember the advance isn't a payment row.

**Stock and purchasing.** `Material` rows track `current_stock` against `minimum_stock`; the dashboard's low-stock and out-of-stock lists (`api/routes/dashboard.py`) are just materials filtered by that comparison, not a separate alerting system. Stock is adjusted by `services/stock_service.py`, and materials are replenished via `Purchase` records against `Supplier`s. There isn't, as of this codebase, a formal purchase-approval workflow — a purchase is just recorded, not routed for sign-off.

**Human-readable IDs are server-generated, not typed by users, and there are two different kinds.** Every major entity has a sequential, human-scannable code like `EMP-011` or `WC-2026-001` (see `utils/id_generator.py` — `next_sequence_number()` scans existing codes for the highest suffix rather than keeping a separate counter table, which is simpler and self-healing if a row gets deleted, at the cost of a table scan per generation). On top of that, most entities also carry a second, unrelated `business_id`: a random 10-character opaque code like `A7K92P4XQ1`. These solve different problems — the sequential code is what a person reads off a list ("show me EMP-011"), the opaque one is for contexts (URLs, exports, external references) where you don't want to reveal how many records exist or in what order they were created. Rolling this `business_id` field out across eleven entities was a significant recent chunk of work — if you're adding a new entity type, check whether it needs one too, and follow the pattern in an existing migration rather than inventing a new ID scheme.

**Roles are simple and enforced per-endpoint, not per-page.** There are three roles in practice: `master`, `manager`, and the default `user`. Authorization is done with `require_role(*allowed_roles)` (`core/security.py`) as a FastAPI dependency directly on each route — for example most write operations require `master` or `manager`, while a handful of sensitive ones (deleting a material, viewing audit logs) are restricted to `master` only. There is no central permissions table or role-hierarchy object; if you need to know what a role can do, the honest answer is to grep `require_role` across `api/routes/`. The frontend's `ProtectedRoute.jsx` only gates whether a route renders at all (logged in or not) — it does not re-implement role checks, so a user without permission for a given action will find out from the API call failing, not from the button being hidden. That's worth knowing if a bug report says "the manager can see a button that doesn't work for them" — that's expected as the code stands, not necessarily a bug.

**Every write is meant to leave an audit trail.** `core/audit.py`'s `log_action()` writes to `audit_logs` with the user, action, module, and before/after values, and is called from routes on top of whatever they're already doing. Audit log records are only visible to `master` role users (`api/routes/audit_logs.py`). If you add a new route that mutates data, check a neighboring route in the same file to see whether it calls `log_action`, and follow suit — it's opt-in per route, not automatic.

**The chat assistant is not actually a language model.** This is probably the single most surprising thing to a new dev, so it's worth saying plainly: despite living next to an `OPENAI_API_KEY` setting and being called a "chatbot" in commit messages, `services/chat_service.py` is a rule-based, keyword-matching system — it pattern-matches phrases like "record a payment" or "this order" against the message, pulls real numbers by querying the database directly, and returns either a plain-text answer or a `records` list the frontend renders as clickable cards. The docstring at the top of that file says outright that this is a working placeholder for a future real NLU upgrade, not a finished AI integration. Two design decisions in there are worth preserving if you extend it: it's context-aware (the frontend passes what record the user is currently viewing, so "summarize this order" resolves against that specific order rather than a generic aggregate), and it never writes data on its own — when it recognizes something like a payment-logging request, it returns a proposed action for the user to explicitly confirm, and only then does the frontend call the real `POST /api/payments/` endpoint, which goes through the same RBAC and audit logging as if a human had filled in the form. Don't let the assistant bypass either of those on a future change.

**Migrations run automatically, and failures are intentionally non-fatal at startup.** `core/auto_migrate.py` runs Alembic on every backend boot so nobody has to remember a manual migration step in dev. Look at the try/except around it in `app/main.py`: if a migration fails, the server logs the exception and starts anyway, rather than refusing to boot. That's a deliberate tradeoff so one bad migration doesn't take the whole API down, but it means a migration failure shows up later as confusing "table/column doesn't exist" errors on whatever endpoint touches the new schema, not as a startup crash. If something is broken in a way that smells like a stale schema, check the startup log for a migration failure before debugging the endpoint itself.

## Where the project currently stands

Looking at the commit history, the most recent sustained work (the last handful of commits before this documentation was written) was: rolling the `business_id` opaque-ID scheme out across eleven entities and wiring it into search, PDF, and Excel output; reworking the dashboard's "Quick Actions" and what the code calls an "honest Attention Required" section (surfacing things that actually need attention rather than a vague summary); restructuring the chat assistant to return structured, clickable record results instead of plain text; and a brand redesign of the generated PDF/Excel documents with real formula-driven totals instead of hardcoded numbers. Before that, there was a run of bug-fixing and cleanup (dead code removal, currency formatting fixes, runtime error fixes) following an earlier stretch that built out most of the HR side — leave management, candidate/interview tracking, RBAC, attendance — and before that, the core order/client/estimate/payment workflow.

Practically, that means: the estimate → order → payment → HR skeleton is mature and has had several rounds of real bug fixes against it — read `Order.recompute_totals()`'s docstring for a flavor of the kind of subtle bug this codebase has already hit once. The `business_id` rollout and the document/export redesign are the newest and least battle-tested layers — if you're hunting for where a fresh bug is likely to be hiding, those are a reasonable first guess. The chat assistant, despite the "AI" framing in commit messages, is functionally a keyword matcher and should be treated as an early-stage feature, not a finished one, when someone asks why it "didn't understand" something.

There is a `backend/tests/` suite with roughly one file per feature area (leaves, stock, payments, salary slips, estimate versioning, business_id, a full integration "business journey" test, and more) — run it after any backend change before assuming something works. It's the closest thing this project has to a specification of intended behavior in ambiguous cases.

## Code tree

```
Woodful_creations/
├── README.md                  Project intro, points here + SETUP.md
├── SETUP.md                   How to install and run (local + Docker)
├── PROJECT_DOCUMENTATION.md   This file
├── docker-compose.yml         Orchestrates postgres + redis + backend + frontend
├── package.json               Root convenience scripts (npm run dev, etc.)
├── setup.sh / setup.bat       One-time install (backend venv + frontend deps)
├── start_all.sh / .bat        Start backend + frontend together
├── start_backend.sh / .bat    Start backend only
├── start_frontend.sh / .bat   Start frontend only
│
├── database/
│   └── README.md              Explains schema lives in code (models + migrations), not raw SQL
│
├── backend/
│   ├── main.py                 Dev entrypoint — runs uvicorn
│   ├── requirements.txt        Python dependencies
│   ├── alembic.ini             Migration tool config
│   ├── Dockerfile               Backend container build
│   ├── docker-entrypoint.sh    Container startup script
│   ├── .env.example            Template for backend/.env (copy, fill in, never commit)
│   │
│   ├── alembic/versions/       Migration files, one per schema change — read these to
│   │                           understand schema history, or add a new one for a schema change
│   │
│   ├── app/
│   │   ├── main.py             FastAPI app setup: middleware, CORS, router registration,
│   │   │                       startup migration hook — fix app-wide behavior here
│   │   ├── core/
│   │   │   ├── config.py       Settings/env var loading — fix config/env issues here
│   │   │   ├── database.py     DB session/engine setup — fix DB connection issues here
│   │   │   ├── security.py     Password hashing, tokens, require_role() — fix auth/RBAC bugs here
│   │   │   ├── middleware.py   Security headers middleware
│   │   │   ├── rate_limit.py   Rate limiting (login attempts especially)
│   │   │   ├── audit.py        log_action() — writes to the audit_logs table
│   │   │   ├── auto_migrate.py Runs Alembic migrations automatically on startup
│   │   │   ├── constants.py    App-wide constants/enums
│   │   │   └── exceptions.py   Custom exception classes / error handling
│   │   │
│   │   ├── models/             SQLAlchemy models, one file per entity (client.py, order.py,
│   │   │                       employee.py, etc.) — the schema itself lives here, not in SQL
│   │   │
│   │   ├── schemas/             Pydantic request/response schemas, mirrors models/ —
│   │   │                        fix "API accepts/returns the wrong shape" issues here
│   │   │
│   │   ├── api/routes/          One file per feature area — fix "wrong behavior on a
│   │   │                        specific endpoint" here first, check for require_role()
│   │   │                        and log_action() calls before changing what a route allows
│   │   │
│   │   ├── services/            Business logic shared across routes: order_service.py
│   │   │                        (recompute_totals and friends), stock_service.py,
│   │   │                        chat_service.py (the rule-based assistant),
│   │   │                        email_service.py — fix cross-cutting business logic here
│   │   │
│   │   ├── utils/               Helpers: pdf_generator.py, exporters.py (Excel/Word),
│   │   │                        id_generator.py (sequential codes + business_id),
│   │   │                        validators.py, helpers.py, document_style.py (PDF/Excel
│   │   │                        branding) — fix export/formatting bugs here
│   │   │
│   │   └── assets/logo.png      Logo used in generated PDFs/exports
│   │
│   ├── scripts/                 One-off/manual scripts: setup_local.py (bootstrap the first
│   │                            admin), create_master_user.py, init_db.py, seed_sample_data.py
│   │
│   ├── tests/                   Pytest suite, roughly one file per feature — the closest
│   │                            thing to a spec of intended behavior; run before assuming
│   │                            a backend change works
│   │
│   ├── logs/                    Runtime log output (empty in repo, gitignored)
│   └── woodful.db               Local SQLite database file (dev only)
│
└── frontend/
    ├── index.html / public/     Static HTML shell, favicon, manifest
    ├── Dockerfile               Frontend container build
    ├── package.json             Node dependencies + npm scripts
    ├── .env.example             Template for frontend/.env
    │
    └── src/
        ├── index.jsx            React entrypoint
        ├── App.jsx              Route definitions — fix "wrong page loads" / routing here
        │
        ├── pages/                One file per screen, named after the feature it shows
        │                         (OrdersPage.jsx, ClientDetailPage.jsx, etc.) — most
        │                         feature bugs are fixed here
        │
        ├── components/           Reusable/shared UI:
        │   ├── Navbar.jsx, Sidebar.jsx, Footer.jsx     App shell/layout
        │   ├── ProtectedRoute.jsx                       Gates whether a route renders at all
        │   │                                            (logged in/out only — not role-aware)
        │   ├── GlobalSearch.jsx                         Search bar
        │   ├── ChatWidget.jsx, AssistantMascot.jsx      Chat assistant UI
        │   ├── QuickActions.jsx, BrandBackdrop.jsx      Dashboard/branding widgets
        │   ├── icons/index.jsx                           Icon set
        │   └── common/           Generic building blocks: Table, Form, Modal, Card,
        │                         Pagination, Alert, KpiCard (+ matching .css files) —
        │                         fix shared UI/styling bugs here, affects many pages at once
        │
        ├── redux/
        │   ├── store.js                 Redux store setup
        │   └── slices/authSlice.js      Auth state — fix "user gets logged out" /
        │                                session state bugs here
        │
        ├── utils/
        │   ├── api.js            Axios instance + API call wrappers — fix "wrong endpoint
        │   │                     called" / request format issues here
        │   ├── currency.js       Indian-style currency formatting (lakhs/crores)
        │   ├── dates.js          Date formatting
        │   └── statusColors.js   Status badge color mapping
        │
        └── styles/                Global CSS (index.css, Pages.css, Navbar.css,
                                    LoginPage.css) + styles/components/ (per-component CSS)
```

## Quick "where do I look" guide

- **A specific page shows wrong data or behaves wrong** — start at `frontend/src/pages/<Page>.jsx`, then the matching `backend/app/api/routes/<feature>.py`.
- **Order totals or balance look wrong** — `Order.recompute_totals()` in `models/order.py` and its callers in `services/order_service.py`; re-read the docstring there before changing anything, it documents a real bug this exact area had before.
- **A user can/can't do something they shouldn't** — search for `require_role(` in `api/routes/` for that endpoint; remember the frontend does not independently enforce roles beyond logged-in/out.
- **Something isn't showing up in the audit log** — check whether that route actually calls `log_action()`; it's opt-in per route, not automatic.
- **Login/session broken** — `core/security.py`, `api/routes/auth.py` on the backend; `redux/slices/authSlice.js`, `ProtectedRoute.jsx` on the frontend.
- **Database schema needs to change** — add a new file in `backend/alembic/versions/`, update the matching model in `app/models/`; run it locally and confirm the app starts cleanly (see the auto-migrate note above about silent startup failures).
- **PDF/Excel export looks wrong** — `backend/app/utils/pdf_generator.py`, `exporters.py`, `document_style.py`.
- **Chat assistant "doesn't understand" a question** — it's keyword matching, not an LLM; check `services/chat_service.py`'s keyword lists rather than assuming it should generalize.
- **A shared UI element (table, form, modal) looks/behaves wrong everywhere** — `frontend/src/components/common/`.
- **Setup/install fails** — `SETUP.md`, `setup.sh`/`setup.bat`, `backend/requirements.txt`, `frontend/package.json`.
- **App won't start, or things error with "table/column doesn't exist"** — check the startup log for a migration failure first (`core/auto_migrate.py` lets the server start even if migrations failed), then look at `backend/alembic/versions/` for a migration that hasn't been applied or conflicts with the current models.
