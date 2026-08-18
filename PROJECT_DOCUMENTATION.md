# Woodful Creations — Project Documentation

## Client Requirements

Woodful Creations is a woodcraft/furniture business, and this application is their internal operations system — the tool the office staff, site supervisors, and management actually use to run the business day to day. It is not a public-facing product; there's no customer-facing storefront or portal anywhere in this codebase. Everyone who logs in is either staff or an owner/manager.

The business itself works roughly like this, and the app is shaped around that flow: a client enquires about a piece of furniture or an interior project, the team prepares a cost estimate (material + labor + tax), the client approves it, the enquiry becomes an order, the order gets tracked through design, production, and delivery, materials get pulled from stock or purchased from suppliers as needed, payments come in against the order over time, and at some point the job is complete and delivered. Alongside that, there's a full HR side — hiring (candidates and interviews), employee records, daily attendance, leave requests, and salary slip generation — because this is also the system the office uses to run payroll-adjacent work, not just the workshop.

Because this is an Indian business, that shows up directly in the code rather than being an abstraction: currency is INR and formatted the Indian way (lakhs/crores grouping — see `frontend/src/utils/currency.js`), tax defaults to 18% GST (`Estimate.tax_percent`), and order codes follow a `WC-2026-001` style scheme.

**Order** is the center of gravity. Almost everything else — payments, expenses, production jobs, daily tasks, issues, estimates — hangs off an order via a foreign key.

## How the core workflow is actually modeled

**Clients → Estimates → Orders.** A `Client` can have any number of `Estimate` rows and any number of `Order` rows. Estimates are deliberately *not* locked to a single order — the code comment in `models/estimate.py` is explicit that a client can be quoted before an order is confirmed, because in practice a client might get quoted, go quiet for two months, and only convert later, or might get several competing estimates before picking one. Estimates also support versioning: revising an estimate doesn't overwrite it, it creates a new row with `version` incremented and `parent_estimate_id` pointing back to the original, so the full negotiation history survives. 

**Orders carry their own status across three independent tracks**, not one combined status: `design_status`, `execution_status`, and `delivery_status`, plus an overall `project_status` (Enquiry → ... ) and a `progress_percent`. This exists because in a real furniture/interior project these three things genuinely move independently — design can be finished while execution hasn't started, or execution can be done while delivery is still pending logistics. If you're building anything that shows "order status" in the UI, check which of these four fields is actually the one that matters for what you're building; conflating them is an easy mistake.

**Money on an order is intentionally denormalized for speed, and that has a sharp edge.** `Order.total_received` and `Order.balance` are stored columns, not computed on the fly, because the dashboard reads them a lot and recomputing from all payments on every dashboard load would be wasteful. They're kept in sync by `Order.recompute_totals()` in `models/order.py`, which must be called any time a `Payment` is added or edited. Read the docstring on that method — it explains a real bug that existed here: the `advance` amount is stored directly on the order (not as its own `Payment` row), so if `recompute_totals()` ever summed only the `Payment` rows without adding `advance` back in, the advance would silently vanish from the running total the moment any payment was logged after order creation. If you ever touch payment logic, this is the exact kind of bug to watch for again — anything that recomputes `total_received` from scratch needs to remember the advance isn't a payment row.

**Stock and purchasing.** `Material` rows track `current_stock` against `minimum_stock`; the dashboard's low-stock and out-of-stock lists (`api/routes/dashboard.py`) are just materials filtered by that comparison, not a separate alerting system. Stock is adjusted by `services/stock_service.py`, and materials are replenished via `Purchase` records against `Supplier`s. There isn't, as of this codebase, a formal purchase-approval workflow — a purchase is just recorded, not routed for sign-off.

**Human-readable IDs are server-generated, not typed by users, and there are two different kinds.** Every major entity has a sequential, human-scannable code like `EMP-011` or `WC-2026-001` (see `utils/id_generator.py` — `next_sequence_number()` scans existing codes for the highest suffix rather than keeping a separate counter table, which is simpler and self-healing if a row gets deleted, at the cost of a table scan per generation). On top of that, most entities also carry a second, unrelated `business_id`: a random 10-character opaque code like `A7K92P4XQ1`. These solve different problems — the sequential code is what a person reads off a list ("show me EMP-011"), the opaque one is for contexts (URLs, exports, external references) where you don't want to reveal how many records exist or in what order they were created. Rolling this `business_id` field out across eleven entities was a significant recent chunk of work — if you're adding a new entity type, check whether it needs one too, and follow the pattern in an existing migration rather than inventing a new ID scheme.

**Roles are simple and enforced per-endpoint, not per-page.** There are three roles in practice: `master`, `manager`, and the default `user`. Authorization is done with `require_role(*allowed_roles)` (`core/security.py`) as a FastAPI dependency directly on each route — for example most write operations require `master` or `manager`, while a handful of sensitive ones (deleting a material, viewing audit logs) are restricted to `master` only. There is no central permissions table or role-hierarchy object; if you need to know what a role can do, the honest answer is to grep `require_role` across `api/routes/`. The frontend's `ProtectedRoute.jsx` only gates whether a route renders at all (logged in or not) — it does not re-implement role checks, so a user without permission for a given action will find out from the API call failing, not from the button being hidden. That's worth knowing if a bug report says "the manager can see a button that doesn't work for them" — that's expected as the code stands, not necessarily a bug.

**Every write is meant to leave an audit trail.** `core/audit.py`'s `log_action()` writes to `audit_logs` with the user, action, module, and before/after values, and is called from routes on top of whatever they're already doing. Audit log records are only visible to `master` role users (`api/routes/audit_logs.py`). If you add a new route that mutates data, check a neighboring route in the same file to see whether it calls `log_action`, and follow suit — it's opt-in per route, not automatic.

**The chat assistant is not actually a language model.** This is probably the single most surprising thing to a new dev, so it's worth saying plainly: despite living next to an `OPENAI_API_KEY` setting and being called a "chatbot," `services/chat_service.py` is a rule-based, keyword-matching system — it pattern-matches phrases against the message, resolves entities against the real database (never invented), and returns either a plain-text answer, a `records` list the frontend renders as clickable cards, or a `proposed_action` the user must explicitly confirm before anything is written. It genuinely understands more than a first glance suggests, though: it resolves natural-language material commands ("add one HDHMR sheet of 6mm to my material list", "add 5 HDHMR 18mm sheets to my purchase cart") into `create_material`/`add_to_cart` proposed actions via `parse_add_material_command()`, it resolves "my tasks"/"my leaves" through the real `User.employee_id` link (never by matching names), and it resolves a named person's tasks/leaves via a live `Employee.name` search. Context is generic — `ChatContext.record_type`/`record_id` is a single pair resolved by `context.resolved()`, not one field added per page type (the five older `order_id`/`material_id`/etc. fields still exist for backward compatibility and are checked as a fallback). It never writes data on its own: when it recognizes something like "add this material" or "record a payment," it returns a proposed action for the user to explicitly confirm, and only then does the frontend's `ACTION_EXECUTORS` registry in `ChatWidget.jsx` call the real endpoint (or, for `add_to_cart`, dispatch to Redux directly, since the cart has no backend of its own) — going through the same RBAC and audit logging as if a human had filled in the form. Don't let the assistant bypass any of that on a future change. The panel itself is a persistent floating widget, bottom-right, on every page — this was deliberately kept as the single AI entry point after an earlier attempt at a second persistent top-of-app command bar was explicitly reverted; see `docs/UI_UX_BACKLOG.md`'s Resolved section for why.

**Materials have a real Category → Subcategory → dynamic-attribute hierarchy, layered on top of (not replacing) the older flat fields.** `MaterialCategory` → `MaterialSubcategory` → `MaterialAttributeDefinition` (per-subcategory spec fields like Thickness/Brand, typed as text/number/select) → `MaterialAttributeValue` (the actual value on one material). `Material.category`/`brand_grade`/`thickness_size` are the original flat string columns; they're kept for backward compatibility and are still what most of the app reads directly, but when `subcategory_id` is set on a material, `category` is server-synced from the subcategory's parent category name — check `_resolve_category_name()` in `api/routes/materials.py` before assuming these two representations could drift apart. The same pattern applies to `Location`: a real self-referential tree (`Location.parent_id`, arbitrary depth — Warehouse → Area → Rack, or however deep a business actually needs) alongside the legacy flat `Material.location` string, synced the same way via `_resolve_location_path()`. The Material Catalog's filters (`MaterialsPage.jsx`) are genuinely dynamic — picking a category/subcategory loads that subcategory's real attribute definitions and renders filter controls from them, backed by a real `attribute_filters` JSON query param on `GET /api/materials/` that ANDs across multiple selected attributes. A material can have many suppliers (not just the one `Material.supplier_id` primary) via `SupplierMaterial`, carrying its own price/MOQ/lead-time/preferred-status per pairing — `SupplierMaterial.last_purchase_price` auto-updates whenever a `Purchase` is recorded against that exact supplier+material pair (see `StockService.record_purchase`), but a purchase from an *unlinked* supplier does not silently create a new link.

**There is a real notification system, event-driven, not a demo table.** `Notification` rows are only ever created by `NotificationService` from an actual condition in the database at the moment it's checked (low/out-of-stock materials via the same `Material.stock_status` every other part of the app already uses, a payment overdue via the same 30-day rule the Orders page's `overdue_only` filter already uses, a purchase received fired directly from `StockService.record_purchase`). There is no background job scheduler in this app — checks run on-demand, triggered by `GET /api/notifications/` itself (i.e., whenever the bell's panel is opened), made safe to call repeatedly by `dedup_key`: before creating a notification, the service checks for an existing *unread* one with the same key and skips if found, so opening the panel five times doesn't spam five low-stock notifications for the same material. Marking one read clears that suppression, so a genuinely recurring situation gets a fresh notification later rather than being permanently silenced.

**Migrations run automatically, and failures are intentionally non-fatal at startup.** `core/auto_migrate.py` runs Alembic on every backend boot so nobody has to remember a manual migration step in dev. Look at the try/except around it in `app/main.py`: if a migration fails, the server logs the exception and starts anyway, rather than refusing to boot. That's a deliberate tradeoff so one bad migration doesn't take the whole API down, but it means a migration failure shows up later as confusing "table/column doesn't exist" errors on whatever endpoint touches the new schema, not as a startup crash. If something is broken in a way that smells like a stale schema, check the startup log for a migration failure before debugging the endpoint itself.

## Where the project currently stands

The core order/client/estimate/payment/HR skeleton described above is mature and has had several rounds of real bug fixes against it. On top of that foundation, the most recent sustained work built out an inventory/procurement layer that didn't exist before: the Category/Subcategory/dynamic-attribute material hierarchy, the Location tree, `SupplierMaterial` multi-supplier pricing, a real Purchase Cart with server-computed shortage math (required vs. in-stock vs. to-purchase — never blindly converts a requested quantity into a purchase quantity), the notification system, the chatbot's material-action capability (`create_material`/`add_to_cart` via natural language), and PWA/mobile installability (manifest, icons, service worker, safe-area handling for iPhone/Android). `Order` also gained real `OrderItem`/`EstimateLineItem` line items (server-computed amounts, never trusted from client input) and a computed `payment_status` (derived from the existing `balance`/`total_received`, not a separately-maintained column).

A recurring theme worth knowing about if you're extending any of this: several of these systems were built as genuine backward-compatible additions on top of older flat fields, not replacements — `Material.category`/`location` (flat strings) coexist with the new `subcategory_id`/`location_id`, synced server-side rather than left to drift. If you add a new structured field to something that already has a flat equivalent, follow that same pattern (sync on write, keep both readable) rather than a one-time migration that could silently break whatever still reads the old field.

The newest and least battle-tested layers are, in rough order: the notification system (built and tested against real events, but never run against production traffic), the Excel purchase import (real round-trip tested against its own generated template, but only ever exercised with clean test data - never a messy real-world spreadsheet), and the chatbot's material-action parsing (`parse_add_material_command()` in `chat_service.py` — tested against every example phrasing in the product brief that introduced it, but natural-language parsing by definition has edges nobody's tried yet; "add 4 sheets to Ishu's project" is explicitly recognized and given an honest "not yet supported, use the Issues page" response rather than silently mishandled). The material hierarchy's frontend (`MaterialAttributesEditor.jsx`) now supports both create and edit - worth knowing if you touch it: the edit path pre-populates from the material's existing subcategory/attribute values, and it must call `onChange()` immediately after doing so, not just update its own display state - an earlier version of this component didn't, which meant saving an edited material without touching the Category/Specifications fields would have silently wiped its existing category and specs. The chat assistant overall, despite understanding more than a first glance suggests, is still functionally a keyword/pattern matcher, not an LLM, and should be treated accordingly when someone asks why it "didn't understand" a phrasing that wasn't anticipated.

`docs/UI_UX_BACKLOG.md` tracks known UI/UX gaps found during this work that were deliberately deferred rather than fixed on the spot — each entry has severity, why it was deferred, and a planned resolution. Check it before assuming something is simply broken; it may already be a tracked, intentional gap with reasoning attached (e.g. why "why is this project over budget?" isn't offered as a chatbot suggestion on every order, or why the Material edit form doesn't yet support attribute values).

There is a `backend/tests/` suite with roughly one file per feature area (leaves, stock, payments, salary slips, estimate versioning, business_id, material hierarchy, supplier-material relationships, location hierarchy, notifications, chat material actions, chat generic context, a full integration "business journey" test, and more) — run it after any backend change before assuming something works. It's the closest thing this project has to a specification of intended behavior in ambiguous cases.

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
├── docs/
│   └── UI_UX_BACKLOG.md         Known UI/UX gaps found during development, deliberately
│                                deferred rather than fixed on the spot - severity, why
│                                deferred, planned resolution for each
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
│   │   │                       employee.py, etc.) — the schema itself lives here, not in SQL.
│   │   │                       Newer additions: material_category.py (Category/Subcategory),
│   │   │                       material_attribute.py (dynamic attribute defs/values),
│   │   │                       supplier_material.py (multi-supplier pricing M2M),
│   │   │                       location.py (self-referential location tree),
│   │   │                       notification.py
│   │   │
│   │   ├── schemas/             Pydantic request/response schemas, mirrors models/ —
│   │   │                        fix "API accepts/returns the wrong shape" issues here
│   │   │
│   │   ├── api/routes/          One file per feature area — fix "wrong behavior on a
│   │   │                        specific endpoint" here first, check for require_role()
│   │   │                        and log_action() calls before changing what a route allows.
│   │   │                        Newer additions: material_categories.py, supplier_materials.py,
│   │   │                        locations.py, notifications.py
│   │   │
│   │   ├── services/            Business logic shared across routes: order_service.py
│   │   │                        (recompute_totals and friends), stock_service.py
│   │   │                        (also where PURCHASE_RECEIVED notifications and
│   │   │                        SupplierMaterial.last_purchase_price sync happen),
│   │   │                        chat_service.py (the rule-based assistant — material-action
│   │   │                        parsing, generic context resolution, task/leave queries),
│   │   │                        notification_service.py (event-driven notification
│   │   │                        generation with dedup), email_service.py
│   │   │
│   │   ├── utils/               Helpers: pdf_generator.py, exporters.py (Excel/Word),
│   │   │                        id_generator.py (sequential codes + business_id),
│   │   │                        validators.py, helpers.py, document_style.py (PDF/Excel
│   │   │                        branding) — fix export/formatting bugs here
│   │   │
│   │   └── assets/logo.png      Logo used in generated PDFs/exports
│   │
│   ├── scripts/                 One-off/manual scripts: setup_local.py (bootstrap the first
│   │                            admin), create_master_user.py, init_db.py,
│   │                            seed_sample_data.py (idempotent - safe to re-run; also
│   │                            seeds two named master accounts via SEED_MASTER_PASSWORD,
│   │                            see SETUP.md)
│   │
│   ├── tests/                   Pytest suite, roughly one file per feature — the closest
│   │                            thing to a spec of intended behavior; run before assuming
│   │                            a backend change works
│   │
│   ├── logs/                    Runtime log output (empty in repo, gitignored)
│   └── woodful.db               Local SQLite database file (dev only)
│
└── frontend/
    ├── index.html / public/     Static HTML shell, favicon, manifest.json, service-worker.js,
    │                            apple-touch-icon.png / icon-*.png (PWA install icons,
    │                            including a maskable icon with proper safe-zone padding
    │                            for Android's adaptive icon masking)
    ├── Dockerfile               Frontend container build
    ├── package.json             Node dependencies + npm scripts
    ├── .env.example             Template for frontend/.env
    │
    └── src/
        ├── index.jsx            React entrypoint — also registers the service worker
        │                        (serviceWorkerRegistration.js), production-only
        ├── App.jsx              Route definitions — fix "wrong page loads" / routing here
        │
        ├── pages/                One file per screen, named after the feature it shows
        │                         (OrdersPage.jsx, ClientDetailPage.jsx, etc.) — most
        │                         feature bugs are fixed here. Newer additions:
        │                         LocationsPage.jsx (location tree browser/manager),
        │                         MobileAppPage.jsx (master-only QR code to install the PWA)
        │
        ├── components/           Reusable/shared UI:
        │   ├── Navbar.jsx, Sidebar.jsx, Footer.jsx     App shell/layout
        │   ├── ProtectedRoute.jsx                       Gates whether a route renders at all
        │   │                                            (logged in/out only — not role-aware)
        │   ├── GlobalSearch.jsx                         Search bar
        │   ├── ChatWidget.jsx, AssistantMascot.jsx      Chat assistant UI — bottom-right,
        │   │                                            persistent, the single AI entry point
        │   ├── NotificationBell.jsx                     Notification bell + panel (Navbar)
        │   ├── CartDrawer.jsx, MaterialCard.jsx          Purchase Cart UI (real shortage math)
        │   ├── MaterialAttributesEditor.jsx              Category/Subcategory/dynamic-attribute
        │   │                                             picker for material creation
        │   ├── QuickActions.jsx, BrandBackdrop.jsx      Dashboard/branding widgets
        │   ├── icons/index.jsx                           Icon set
        │   └── common/           Generic building blocks: Table, Form, Modal, Card,
        │                         Pagination, Alert, KpiCard (+ matching .css files) —
        │                         fix shared UI/styling bugs here, affects many pages at once.
        │                         Form.js supports multi-step wizards (a `section` property
        │                         on any field switches a flat form into a wizard) and
        │                         `visibleIf` for conditional fields.
        │
        ├── redux/
        │   ├── store.js                 Redux store setup
        │   └── slices/
        │       ├── authSlice.js         Auth state — fix "user gets logged out" /
        │       │                        session state bugs here
        │       ├── cartSlice.js         Purchase Cart state (client-side only, no backend -
        │       │                        localStorage-persisted)
        │       └── chatUiSlice.js       Coordination plumbing for scoped "Ask AI" triggers
        │                                to open the one floating chat widget with a
        │                                prefilled message - not a second AI surface
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
- **Chat assistant "doesn't understand" a question** — it's keyword/pattern matching, not an LLM; check `services/chat_service.py`'s keyword lists and `parse_add_material_command()` rather than assuming it should generalize.
- **A material's category/specs/location look wrong or a filter isn't showing what it should** — check both the legacy flat field (`Material.category`/`location`) and the structured one (`subcategory_id`/`location_id`); `_resolve_category_name()`/`_resolve_location_path()` in `api/routes/materials.py` are what keep them in sync, so a mismatch there is the first thing to check.
- **A notification isn't appearing, or the same one keeps reappearing** — `services/notification_service.py`; check `dedup_key` logic first for duplicates, and remember checks only run on-demand (when `GET /api/notifications/` is called), not on a timer.
- **Something about "Add to Home Screen" / the app not installing on a phone** — `frontend/public/manifest.json`, `index.html`'s `apple-touch-icon`/`mobile-web-app-capable` tags, `serviceWorkerRegistration.js`. Only registers in production builds.
- **A shared UI element (table, form, modal) looks/behaves wrong everywhere** — `frontend/src/components/common/`.
- **Setup/install fails** — `SETUP.md`, `setup.sh`/`setup.bat`, `backend/requirements.txt`, `frontend/package.json`.
- **App won't start, or things error with "table/column doesn't exist"** — check the startup log for a migration failure first (`core/auto_migrate.py` lets the server start even if migrations failed), then look at `backend/alembic/versions/` for a migration that hasn't been applied or conflicts with the current models.
