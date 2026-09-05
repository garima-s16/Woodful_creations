# Woodful Creations — Project Documentation

## Client Requirements

Woodful Creations makes furniture and does interior/woodwork projects. This app is their internal ops system — what the office staff, site supervisors, and management use to actually run the business. There's no customer-facing side at all; everyone who logs in is staff or a manager/owner.

The core flow: a client enquires about a piece of furniture or an interior job, the team puts together a cost estimate (material + labor + tax), the client signs off, the enquiry turns into an order, and the order moves through design → production → delivery. Materials get pulled from stock or bought from suppliers along the way, payments come in against the order over time, and eventually the job ships. There's also a full HR side bolted onto this — hiring, employee records, attendance, leave, salary slips — since the same office runs payroll too.

It's an Indian business, and that's not just cosmetic: currency is INR with lakhs/crores formatting, GST defaults to 18%, order codes look like `WC-2026-001`.

`Order` is the center of everything. Payments, expenses, production jobs, daily tasks, issues, estimates — all of it hangs off an order.

That's the original shape of the requirement. It's grown a lot since:

- **Bulk Excel import/export** for most masters and a few transactions (clients, materials, products, suppliers, purchases, orders, estimates, rate cards, holidays) — each with its own template, validation, and preview-before-commit step, not a generic import framework.
- **PDF documents** — quotes, invoices, payslips — generated server-side off the same data the screens show, not a separately maintained set of numbers.
- **A chat assistant**, which is really two things stacked: a deterministic keyword matcher that handles most day-to-day questions and a small set of actions, and a Gemini-backed fallback behind it for things the keyword matcher doesn't recognize. Neither one writes data directly — anything consequential goes through a proposed-action confirmation and then the normal authenticated API, same as if a person filled in the form.
- **File storage for documents** — client documents, payment receipts, resumes — backed by either local disk or Google Drive depending on how the server's configured, behind one storage interface so the rest of the app doesn't care which.

None of this changes the core order/estimate/payment shape described above — it's all built on top of it.

## How the core workflow is actually modeled

**Clients → Estimates → Orders.** A `Client` can have any number of `Estimate` rows and any number of `Order` rows. Estimates are deliberately *not* locked to a single order — the code comment in `modules/sales/models.py` is explicit that a client can be quoted before an order is confirmed, because in practice a client might get quoted, go quiet for two months, and only convert later, or might get several competing estimates before picking one. Estimates also support versioning: revising an estimate doesn't overwrite it, it creates a new row with `version` incremented and `parent_estimate_id` pointing back to the original, so the full negotiation history survives. 

**Orders carry their own status across three independent tracks**, not one combined status: `design_status`, `execution_status`, and `delivery_status`, plus an overall `project_status` (Enquiry → ... ) and a `progress_percent`. This exists because in a real furniture/interior project these three things genuinely move independently — design can be finished while execution hasn't started, or execution can be done while delivery is still pending logistics. If you're building anything that shows "order status" in the UI, check which of these four fields is actually the one that matters for what you're building; conflating them is an easy mistake.

**Money on an order is intentionally denormalized for speed, and that has a sharp edge.** `Order.total_received` and `Order.balance` are stored columns, not computed on the fly, because the dashboard reads them a lot and recomputing from all payments on every dashboard load would be wasteful. They're kept in sync by `Order.recompute_totals()` in `modules/sales/models.py`, which must be called any time a `Payment` is added or edited. Read the docstring on that method — it explains a real bug that existed here: the `advance` amount is stored directly on the order (not as its own `Payment` row), so if `recompute_totals()` ever summed only the `Payment` rows without adding `advance` back in, the advance would silently vanish from the running total the moment any payment was logged after order creation. If you ever touch payment logic, this is the exact kind of bug to watch for again — anything that recomputes `total_received` from scratch needs to remember the advance isn't a payment row.

**Stock and purchasing.** `Material` rows track `current_stock` against `minimum_stock`; the dashboard's low-stock and out-of-stock lists (`modules/reporting/api/dashboard.py`) are just materials filtered by that comparison, not a separate alerting system. Stock is adjusted by `modules/inventory/stock_service.py`, and materials are replenished via `Purchase` records against `Supplier`s. There isn't, as of this codebase, a formal purchase-approval workflow — a purchase is just recorded, not routed for sign-off.

**Human-readable IDs are server-generated, not typed by users, and there are two different kinds.** Every major entity has a sequential, human-scannable code like `EMP-011` or `WC-2026-001` (see `platform/database/id_generator.py` — `next_sequence_number()` scans existing codes for the highest suffix rather than keeping a separate counter table, which is simpler and self-healing if a row gets deleted, at the cost of a table scan per generation). On top of that, most entities also carry a second, unrelated `business_id`: a random 10-character opaque code like `A7K92P4XQ1`. These solve different problems — the sequential code is what a person reads off a list ("show me EMP-011"), the opaque one is for contexts (URLs, exports, external references) where you don't want to reveal how many records exist or in what order they were created. Rolling this `business_id` field out across eleven entities was a significant recent chunk of work — if you're adding a new entity type, check whether it needs one too, and follow the pattern in an existing migration rather than inventing a new ID scheme.

**Roles are simple and enforced per-endpoint, not per-page — and there are exactly two of them.** `master` and the default `user`; there is no `manager` role and no per-user resource-ownership model (no client/project/order assignment, no team membership) anywhere in this codebase — every authenticated user, regardless of role, can see every client/order/task/project, and role only ever gates *which fields* are visible or *which routes* are callable, never *which records*. Authorization is done with `require_role(*allowed_roles)` (`platform/security/security.py`) as a FastAPI dependency directly on each route for route-level gating (most financial mutations — payments, purchases, salary — are `master`-only), and with an inline `is_privileged = auth.get("role", "user") in ("master",)` check plus manual field-nulling for routes that stay open to everyone but must redact specific fields (see `_serialize_orders()` in `modules/sales/api/orders.py`, and the same pattern across `analytics.py`/`reports.py`). There is no central permissions table or role-hierarchy object; if you need to know what a role can do, the honest answer is to grep `require_role` and `is_privileged` across `api/routes/`. The frontend's `ProtectedRoute.jsx` only gates whether a route renders at all (logged in or not) — it does not re-implement role checks, so a `user` without permission for a given action will find out from the API call failing (or from a field silently coming back `null`), not from the button being hidden. Before adding anything that looks like per-record authorization ("can this user access *this specific* client/order/project"), stop — that model doesn't exist here and building it would be new architecture, not a bug fix; the actual, real security boundary in this app is field-level financial redaction by role, and that's almost always what a "leak" report is really about.

**Every write is meant to leave an audit trail.** `platform/audit/audit.py`'s `log_action()` writes to `audit_logs` with the user, action, module, and before/after values, and is called from routes on top of whatever they're already doing. Audit log records are only visible to `master` role users (`api/routes/audit_logs.py`). If you add a new route that mutates data, check a neighboring route in the same file to see whether it calls `log_action`, and follow suit — it's opt-in per route, not automatic.

**The chat assistant is not actually a language model.** This is probably the single most surprising thing to a new dev, so it's worth saying plainly: despite living next to an `OPENAI_API_KEY` setting and being called a "chatbot," `modules/ai/orchestration.py` is a rule-based, keyword-matching system — it pattern-matches phrases against the message, resolves entities against the real database (never invented), and returns either a plain-text answer, a `records` list the frontend renders as clickable cards, or a `proposed_action` the user must explicitly confirm before anything is written. It genuinely understands more than a first glance suggests, though: it resolves natural-language material commands ("add one HDHMR sheet of 6mm to my material list", "add 5 HDHMR 18mm sheets to my purchase cart") into `create_material`/`add_to_cart` proposed actions via `parse_add_material_command()`, it resolves "my tasks"/"my leaves" through the real `User.employee_id` link (never by matching names), and it resolves a named person's tasks/leaves via a live `Employee.name` search. Context is generic — `ChatContext.record_type`/`record_id` is a single pair resolved by `context.resolved()`, not one field added per page type (the five older `order_id`/`material_id`/etc. fields still exist for backward compatibility and are checked as a fallback). It never writes data on its own: when it recognizes something like "add this material" or "record a payment," it returns a proposed action for the user to explicitly confirm, and only then does the frontend's `ACTION_EXECUTORS` registry in `ChatWidget.jsx` call the real endpoint (or, for `add_to_cart`, dispatch to Redux directly, since the cart has no backend of its own) — going through the same RBAC and audit logging as if a human had filled in the form. Don't let the assistant bypass any of that on a future change. The panel itself is a persistent floating widget, bottom-right, on every page — this was deliberately kept as the single AI entry point after an earlier attempt at a second persistent top-of-app command bar was explicitly reverted; see `docs/UI_UX_BACKLOG.md`'s Resolved section for why.

**Materials have a real Category → Subcategory → dynamic-attribute hierarchy, layered on top of (not replacing) the older flat fields.** `MaterialCategory` → `MaterialSubcategory` → `MaterialAttributeDefinition` (per-subcategory spec fields like Thickness/Brand, typed as text/number/select) → `MaterialAttributeValue` (the actual value on one material). `Material.category`/`brand_grade`/`thickness_size` are the original flat string columns; they're kept for backward compatibility and are still what most of the app reads directly, but when `subcategory_id` is set on a material, `category` is server-synced from the subcategory's parent category name — check `_resolve_category_name()` in `modules/inventory/api/materials.py` before assuming these two representations could drift apart. The same pattern applies to `Location`: a real self-referential tree (`Location.parent_id`, arbitrary depth — Warehouse → Area → Rack, or however deep a business actually needs) alongside the legacy flat `Material.location` string, synced the same way via `_resolve_location_path()`. The Material Catalog's filters (`MaterialsPage.jsx`) are genuinely dynamic — picking a category/subcategory loads that subcategory's real attribute definitions and renders filter controls from them, backed by a real `attribute_filters` JSON query param on `GET /api/materials/` that ANDs across multiple selected attributes. A material can have many suppliers (not just the one `Material.supplier_id` primary) via `SupplierMaterial`, carrying its own price/MOQ/lead-time/preferred-status per pairing — `SupplierMaterial.last_purchase_price` auto-updates whenever a `Purchase` is recorded against that exact supplier+material pair (see `StockService.record_purchase`), but a purchase from an *unlinked* supplier does not silently create a new link.

**There is a real notification system, event-driven, not a demo table.** `Notification` rows are only ever created by `NotificationService` from an actual condition in the database at the moment it's checked (low/out-of-stock materials via the same `Material.stock_status` every other part of the app already uses, a payment overdue via the same 30-day rule the Orders page's `overdue_only` filter already uses, a purchase received fired directly from `StockService.record_purchase`). There is no background job scheduler in this app — checks run on-demand, triggered by `GET /api/notifications/` itself (i.e., whenever the bell's panel is opened), made safe to call repeatedly by `dedup_key`: before creating a notification, the service checks for an existing *unread* one with the same key and skips if found, so opening the panel five times doesn't spam five low-stock notifications for the same material. Marking one read clears that suppression, so a genuinely recurring situation gets a fresh notification later rather than being permanently silenced. `NotificationService.FINANCIAL_NOTIFICATION_TYPES` is the single, shared definition of "which notification types are money-sensitive" (`PAYMENT_OVERDUE`, `PAYMENT_DUE`, `PURCHASE_RECOMMENDED`, `ESTIMATE_PENDING_RESPONSE`) — a broadcast notification of one of these types is visible to `master` only, everything else broadcasts to everyone; `NotificationService.visible_to()` is the one place this is enforced, and it's reused unchanged everywhere else that needs the same rule (communication search over notification content included), so a new financial notification type should be added to that set rather than hand-rolled elsewhere.

**Automation runs the same on-demand pattern as notifications, one rule per real business condition.** `modules/communications/services/automation_service.py`'s `AutomationService` follows EVENT → CONDITION → ACTION → AUDIT for ten rules: task overdue, low-stock purchase recommendation, purchase delivery approaching, payment overdue, project delayed (milestone target date already passed), production blocked, follow-up due (a `ClientActivity.follow_up_date` that's due/overdue and not yet done — reuses the exact condition `ChatService._follow_up_suggestions` already uses), pending estimate response (an `Estimate` left in `"sent"` status with no update for 5+ days — financial-tier, master-only per `FINANCIAL_NOTIFICATION_TYPES`), project deadline approaching (a milestone target date within 5 days but *not yet passed* — the mirror-image companion to project delayed, so a milestone gets exactly one of the two notifications, never both on the same day), and operational summary (a once-per-calendar-day consolidated broadcast of counts only — no financial amounts — across overdue tasks, approaching deadlines, blocked production, low stock, pending purchases, and pending follow-ups). Every rule writes an `AutomationLog` row (status `SUCCESS`/`PROPOSED`/`FAILED`) and reuses `NotificationService.notify()`'s `dedup_key` mechanism for idempotency — no rule here creates a `Notification` directly. Actions never go further than "notify" or "recommend" (e.g. low stock proposes a purchase quantity, logged `PROPOSED`, never auto-creates a `Purchase`); there is no auto-purchase/auto-payment authority anywhere in this app for automation to grant itself. Like notifications, there's no background scheduler — `POST /api/automation/run` (master-only) is the hook an external scheduler (cron, a hosting platform's scheduled task) should call periodically; `GET /api/automation/rules` and `/logs` (both master-only) expose the registry and audit trail.

**Communication and analytics both inherit the app's one real access-control axis: `master` vs. everyone else, gated per-field, not per-record.** There is no per-user resource-ownership model anywhere in Woodful — no client/project/order assignment, no team membership — every authenticated user can see every client, order, task, and project; what's gated is *which fields* on those records are financial. `modules/reporting/analytics_service.py` and `modules/reporting/api/analytics.py` follow this consistently: sales/purchases/payments/expenses routes are `require_role("master")` outright, while inventory/production/projects/tasks/workforce/operations routes are open to everyone but compute an `is_privileged` flag from the caller's role and null out financial sub-fields (order profitability, stock value, salary) for non-master — the same pattern `_serialize_orders()` in `modules/sales/api/orders.py` already uses for the orders list. `modules/communications/api/communication.py` (search, insights, draft) deliberately does *not* add per-record authorization on top of that — task/order comments and client activities are visible to every role already (matching every other place that reads them), and the module docstring/comments explain why that's intentional, not an oversight; what communication search/insights/AI must never do is surface a financial value that's otherwise role-gated (e.g. a `PAYMENT_OVERDUE`/`ESTIMATE_PENDING_RESPONSE` notification's content), which is why it reuses `NotificationService.visible_to()` rather than re-deriving its own rule. **Watch this specifically with exports:** every Excel/PDF export in the domain-specific `modules/*/api/reports.py` files is supposed to inherit exactly the same field-level authorization as its on-screen equivalent — this held everywhere except two PDF routes (`orders/{id}/estimate.pdf`, `estimates/{id}/quote.pdf`), which used `get_current_user` instead of `require_role("master")` and so let any authenticated role download `order_value`/`total_received`/line-item `rate`/`amount`, fields the JSON API already nulls for non-master. Fixed to `require_role("master")` to match `invoice.pdf`'s existing pattern (see `tests/security/test_financial_rbac.py`'s `test_user_cannot_download_order_estimate_pdf`/`test_user_cannot_download_estimate_quote_pdf`) — if you add a new export, check what the on-screen version redacts and gate the export the same way *before* assuming `get_current_user` is enough.

**Migrations run automatically, and startup refuses to proceed if they fail.** `platform/database/auto_migrate.py` runs Alembic on every backend boot so nobody has to remember a manual migration step in dev. The startup hook in `app/main.py` deliberately does not swallow a migration failure - it logs the exception and re-raises, so the server does not start at all rather than serve requests against a schema it knows is wrong (serving against a known-stale schema would fail unpredictably later and mask the real problem). If the server won't start, check the startup log for a migration failure before assuming the code itself is broken.

## Where the project currently stands

The core order/client/estimate/payment/HR skeleton described above is mature and has had several rounds of real bug fixes against it. On top of that foundation, the most recent sustained work built out an inventory/procurement layer that didn't exist before: the Category/Subcategory/dynamic-attribute material hierarchy, the Location tree, `SupplierMaterial` multi-supplier pricing, a real Purchase Cart with server-computed shortage math (required vs. in-stock vs. to-purchase — never blindly converts a requested quantity into a purchase quantity), the notification system, the chatbot's material-action capability (`create_material`/`add_to_cart` via natural language), and PWA/mobile installability (manifest, icons, service worker, safe-area handling for iPhone/Android). `Order` also gained real `OrderItem`/`EstimateLineItem` line items (server-computed amounts, never trusted from client input) and a computed `payment_status` (derived from the existing `balance`/`total_received`, not a separately-maintained column).

A recurring theme worth knowing about if you're extending any of this: several of these systems were built as genuine backward-compatible additions on top of older flat fields, not replacements — `Material.category`/`location` (flat strings) coexist with the new `subcategory_id`/`location_id`, synced server-side rather than left to drift. If you add a new structured field to something that already has a flat equivalent, follow that same pattern (sync on write, keep both readable) rather than a one-time migration that could silently break whatever still reads the old field.

The newest and least battle-tested layers are, in rough order: the notification system (built and tested against real events, but never run against production traffic), the Excel purchase import (real round-trip tested against its own generated template, but only ever exercised with clean test data - never a messy real-world spreadsheet), and the chatbot's material-action parsing (`parse_add_material_command()` in `chat_service.py` — tested against every example phrasing in the product brief that introduced it, but natural-language parsing by definition has edges nobody's tried yet; "add 4 sheets to Ishu's project" is explicitly recognized and given an honest "not yet supported, use the Issues page" response rather than silently mishandled). The material hierarchy's frontend (`MaterialAttributesEditor.jsx`) now supports both create and edit - worth knowing if you touch it: the edit path pre-populates from the material's existing subcategory/attribute values, and it must call `onChange()` immediately after doing so, not just update its own display state - an earlier version of this component didn't, which meant saving an edited material without touching the Category/Specifications fields would have silently wiped its existing category and specs. The chat assistant overall, despite understanding more than a first glance suggests, is still functionally a keyword/pattern matcher, not an LLM, and should be treated accordingly when someone asks why it "didn't understand" a phrasing that wasn't anticipated.

**If you're adding a new Excel import module** (there are 8 already - client/material/product/purchase/order/estimate/rate_card/holiday), use `app/shared/import_normalize.py` for `normalize_match_key`/`normalize_number`/`normalize_date` rather than defining your own copy - these were genuinely, byte-for-byte duplicated across most of the existing import modules until a recent consolidation pass. `client_import.py`'s own `normalize_match_key` is a deliberate exception (it takes name AND phone, since Client Recognition requires both) and correctly still lives there, not in the shared module. `parse_uploaded_workbook`/`build_import_template` are still separately implemented per module - they look similar at a glance but each delegates to a genuinely entity-specific header/column resolver underneath, so consolidating those would mean parameterizing real behavioral differences, not just moving identical code; that hasn't been attempted.

`docs/UI_UX_BACKLOG.md` tracks known UI/UX gaps found during this work that were deliberately deferred rather than fixed on the spot — each entry has severity, why it was deferred, and a planned resolution. Check it before assuming something is simply broken; it may already be a tracked, intentional gap with reasoning attached (e.g. why "why is this project over budget?" isn't offered as a chatbot suggestion on every order, or why the Material edit form doesn't yet support attribute values).

The most recent work closed out communication, analytics, and business automation and their gap-fix pass: `automation_service.py` gained four rules that didn't exist before (follow-up due, pending estimate response, project deadline approaching, operational summary), and two PDF export routes (`orders/{id}/estimate.pdf`, `estimates/{id}/quote.pdf`) were found and fixed to require `master`, having previously let any authenticated role download financial fields the JSON API already redacts. Communication (search/insights/draft) and most of analytics (export role gating) were audited and found already correct against the app's real access model — nothing there needed changing; see the automation/communication/analytics paragraphs above for the detail.

There is a `backend/tests/` suite with roughly one file per feature area (leaves, stock, payments, salary slips, estimate versioning, business_id, material hierarchy, supplier-material relationships, location hierarchy, notifications, automation, communication, analytics RBAC, export RBAC, chat material actions, chat generic context, a full integration "business journey" test, and more) — run it after any backend change before assuming something works. It's the closest thing this project has to a specification of intended behavior in ambiguous cases.

A later pass went back over the newest, least-visible layers — the Gemini AI gateway, document storage, email — and checked what's actually there instead of trusting the source. `modules/ai/gateway.py` gives the chatbot a real Gemini fallback for when the keyword matcher comes up empty, so the "not an LLM" line above is only true of the first-pass matcher now, not the whole chat feature. It doesn't write anything on its own: 13 of its write tools just produce a proposed action, which `ChatWidget.jsx` sends to the same authenticated endpoints the regular forms use once the user confirms. Two exceptions — `create_task` and `complete_task` — execute right away, matching how `chat_service.py` already handled those two before Gemini existed, but the role/ownership check still runs against the real logged-in session, not anything Gemini said. What actually gets sent to Gemini is the user's message plus a one-line hint about what page they're on — no prices, no contact info, no secrets. None of this has run against a live Gemini key here (no network access in this environment), so treat it as correctly built, not proven. No standalone Gemini-suggestion-learning mechanism — interpret, propose, approve, turn into a rule — exists in this repo at all.

There is one storage implementation, `app/platform/storage/storage.py` — `documents.py`, `clients.py`, `payments.py`, and `candidates.py` all import it, and it can write to local disk or Google Drive behind the same interface, keyed by Drive's own file ID rather than a filename. An older, separate `app/storage/` package once existed alongside it with no callers anywhere else in the codebase; it has since been removed entirely. Email is plain SMTP (`smtplib`, a username and password, defaulting to `smtp.gmail.com`) — not the Gmail API, no OAuth. Worth saying plainly so nobody assumes otherwise from the name.

## Code tree

```
Woodful_creations/
├── README.md                  Project intro, points here + SETUP.md
├── SETUP.md                   How to install and run (local + Docker)
├── PROJECT_DOCUMENTATION.md   This file
├── docker-compose.yml         Orchestrates postgres + redis + backend + frontend
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
├── backend/
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
│   │   │                       startup migration hook, global exception handler — fix
│   │   │                       app-wide behavior here. The app object is app.main:app;
│   │   │                       there is no separate top-level backend/main.py.
│   │   ├── platform/            Infrastructure, not business logic:
│   │   │                        configuration/ (settings/env), database/ (DB session/
│   │   │                        engine, Base/BaseModel, id_sequence, id_generator,
│   │   │                        auto_migrate), security/ (password hashing, JWT,
│   │   │                        require_role(), rate_limit.py), middleware/ (security
│   │   │                        headers, global rate limiting), storage/ (Drive/local
│   │   │                        storage abstraction), audit/ (log_action() + AuditLog),
│   │   │                        monitoring/ (capture_exception()/capture_message() -
│   │   │                        the one place any module reports an error, provider
│   │   │                        swappable via MONITORING_PROVIDER)
│   │   │
│   │   ├── modules/             Business domains — each owns its own models.py, schemas.py,
│   │   │   │                    and api/ (plus services.py, imports/, or a services/
│   │   │   │                    subfolder where genuinely needed). Find a feature by
│   │   │   │                    business concept, not by layer:
│   │   │   ├── auth/             User accounts, password reset, login/session routes
│   │   │   ├── clients/          Client master, activities, product-rate overrides,
│   │   │   │                     matching.py (duplicate-detection/recognition rules)
│   │   │   ├── catalog/          Products, rate cards, pricing_engine.py/pricing_priority.py
│   │   │   │                     (the one place the selling-rate formula lives),
│   │   │   │                     pdf_generator.py (product PDF)
│   │   │   ├── inventory/        Materials, stock ledger/transfers/adjustments, locations,
│   │   │   │                     stock_service.py (all stock mutation)
│   │   │   ├── procurement/      Suppliers, supplier-material pricing, purchases,
│   │   │   │                     personal cart (material request list, pre-Mastercart)
│   │   │   ├── sales/            Estimates, orders, payments, order_service.py
│   │   │   │                     (recompute_totals/profitability/overall_gross_margin),
│   │   │   │                     calculations.py, status_rules.py, quantity_rules.py,
│   │   │   │                     pdf_generator.py (estimate/order/invoice PDFs)
│   │   │   ├── operations/       Daily tasks, production jobs, issues, milestones,
│   │   │   │                     project expenses
│   │   │   ├── hr/                Employees, attendance, leave, salary slips, working
│   │   │   │                      calendar, company holidays, pdf_generator.py (salary slip)
│   │   │   ├── recruitment/      Candidates, interviews
│   │   │   ├── documents/        The generic, polymorphic document system (GenericDocument)
│   │   │   │                     that order/purchase/employee/product documents attach to
│   │   │   ├── communications/   Notifications, automation (EVENT->CONDITION->ACTION
│   │   │   │                     rules), mentions, cross-record search/insights/draft,
│   │   │   │                     email sending — all under services/
│   │   │   ├── ai/                gateway.py (Gemini dispatch, financial DLP, kill switch),
│   │   │   │                     orchestration.py (the rule-based assistant), security.py
│   │   │   │                     (text sanitization), tools.py, agents.py, models.py
│   │   │   │                     (ChatLearningCandidate)
│   │   │   └── reporting/        analytics_service.py (per-domain aggregates,
│   │   │                         is_privileged nulls financial fields), dashboard.py,
│   │   │                         search.py, models.py (AIWorkspaceReport, ReportHistory)
│   │   │
│   │   ├── shared/               Genuinely domain-neutral helpers used across many
│   │   │                        modules: document_style.py (PDF/Excel branding, plus
│   │   │                        fmt_date/mask_value/mask_phone), exporters.py (Excel/Word),
│   │   │                        validators.py, import_common.py, import_normalize.py.
│   │   │                        Domain-specific PDF generation (order/estimate/invoice/
│   │   │                        client/product/salary-slip) lives with its owning module
│   │   │                        instead, not here - shared/ stays business-neutral.
│   │   │
│   │   ├── models/, schemas/, api/routes/
│   │   │                        What's left after the module split: genuinely cross-
│   │   │                        cutting lookup/dropdown tables with no single domain
│   │   │                        owner (setting.py - Unit, PaymentMode, ProjectStatus,
│   │   │                        etc, referenced across many modules), plus the settings
│   │   │                        and audit-log routes. Everything else that used to live
│   │   │                        at this top level (users, auth, id_generator, and a
│   │   │                        services/ and utils/ folder) has since moved into its
│   │   │                        owning module or platform/ - this location is deliberately
│   │   │                        small now, not a second dumping ground.
│   │   │
│   │   └── assets/logo.png      Logo used in generated PDFs/exports
│   │
│   ├── scripts/                 One-off/manual scripts: setup_local.py (bootstrap the first
│   │                            admin), create_master_user.py, set_user_password.py,
│   │                            init_db.py, seed_sample_data.py (idempotent - safe to
│   │                            re-run; also seeds two named master accounts via
│   │                            SEED_MASTER_PASSWORD, see SETUP.md), seed_sample_login_data.py,
│   │                            migrate_local_to_neon.py, inspect_neon_database.py, and
│   │                            verify.py - the single dependency-free verification entry
│   │                            point (orchestrates verify_migrations/verify_excel/
│   │                            verify_chatbot/verify_email/verify_runtime_safety.py),
│   │                            honestly reporting LOCAL EXECUTION vs MOCK INTEGRATIONS
│   │                            vs LIVE INTEGRATIONS (not attempted) vs BLOCKED, for
│   │                            environments where pytest itself can't run (no network to
│   │                            install fastapi/sqlalchemy)
│   │
│   ├── tests/                   Pytest suite, organized by product domain — the closest
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
- **Order totals or balance look wrong** — `Order.recompute_totals()` in `modules/sales/models.py` and its callers in `modules/sales/order_service.py`; re-read the docstring there before changing anything, it documents a real bug this exact area had before.
- **A user can/can't do something they shouldn't** — search for `require_role(` in `api/routes/` for that endpoint; remember the frontend does not independently enforce roles beyond logged-in/out.
- **Something isn't showing up in the audit log** — check whether that route actually calls `log_action()`; it's opt-in per route, not automatic.
- **Login/session broken** — `platform/security/security.py`, `modules/auth/api/auth.py` on the backend; `redux/slices/authSlice.js`, `ProtectedRoute.jsx` on the frontend.
- **Database schema needs to change** — add a new file in `backend/alembic/versions/`, update the matching model in `app/models/`; run it locally and confirm the app starts cleanly (see the auto-migrate note above about silent startup failures).
- **PDF/Excel export looks wrong** — `backend/app/shared/pdf_generator.py`, `exporters.py`, `document_style.py`.
- **Chat assistant "doesn't understand" a question** — it's keyword/pattern matching, not an LLM; check `modules/ai/orchestration.py`'s keyword lists and `parse_add_material_command()` rather than assuming it should generalize.
- **A material's category/specs/location look wrong or a filter isn't showing what it should** — check both the legacy flat field (`Material.category`/`location`) and the structured one (`subcategory_id`/`location_id`); `_resolve_category_name()`/`_resolve_location_path()` in `modules/inventory/api/materials.py` are what keep them in sync, so a mismatch there is the first thing to check.
- **A notification isn't appearing, or the same one keeps reappearing** — `modules/communications/services/notification_service.py`; check `dedup_key` logic first for duplicates, and remember checks only run on-demand (when `GET /api/notifications/` is called), not on a timer.
- **An automation rule isn't firing, fires twice, or an existing rule needs a sibling** — `modules/communications/services/automation_service.py`; each rule is one `check_*` static method with its own try/except and `dedup_key`, registered in both `RULES` (the static registry `GET /api/automation/rules` returns) and the `run_all()` tuple — a new rule needs to be added to both, not just written.
- **Analytics/export shows (or hides) financial data it shouldn't for a given role** — check the `is_privileged` flag in `modules/reporting/analytics_service.py` / `modules/reporting/api/analytics.py` first; for exports specifically, compare the domain-specific `modules/*/api/reports.py` files against the on-screen route it mirrors — an export must never expose more than its screen equivalent (see `tests/security/test_financial_rbac.py`'s `test_user_cannot_download_order_estimate_pdf` for the pattern to follow when adding a new export).
- **Communication search/insights/draft looks like it's leaking something** — `modules/communications/api/communication.py`; remember comments/activities are intentionally visible to every role (not a bug), the thing to check is whether a *financial* value (notification content, a redacted field) is leaking through, not whether the record itself is visible.
- **Something about "Add to Home Screen" / the app not installing on a phone** — `frontend/public/manifest.json`, `index.html`'s `apple-touch-icon`/`mobile-web-app-capable` tags, `serviceWorkerRegistration.js`. Only registers in production builds.
- **A shared UI element (table, form, modal) looks/behaves wrong everywhere** — `frontend/src/components/common/`.
- **Setup/install fails** — `SETUP.md`, `setup.sh`/`setup.bat`, `backend/requirements.txt`, `frontend/package.json`.
- **App won't start, or things error with "table/column doesn't exist"** — check the startup log for a migration failure first (a failed migration means the server refuses to start at all - `platform/database/auto_migrate.py`), then look at `backend/alembic/versions/` for a migration that hasn't been applied or conflicts with the current models.
- **The chatbot answered something the deterministic keyword list clearly doesn't cover** — that's the Gemini fallback (`modules/ai/gateway.py`), not the pattern matcher; it only runs when `chat_service.py`'s own parsing finds nothing. A write it proposes should always show up as a confirmation card handled by `ChatWidget.jsx`'s `ACTION_EXECUTORS` — if something looks like it wrote data without that confirmation step, check whether it's one of the two deliberate immediate-execution exceptions (`create_task`/`complete_task`) before assuming a bypass.
- **A document/file (client document, payment document, resume, generic document) won't upload, download, or delete correctly** — `app/platform/storage/storage.py` is the one, sole storage path in this codebase - there is no separate legacy storage package to rule out. `get_storage_backend_for_record()` is what decides local vs. Drive for an *existing* file — it reads the record's own `storage_backend` column, not the server's current `STORAGE_PROVIDER` setting.
- **An email didn't send, or someone assumes it's Gmail API/OAuth** — `modules/communications/services/email_service.py` is SMTP only (`smtplib`, username/password); there is no Gmail API or OAuth integration in this codebase.
