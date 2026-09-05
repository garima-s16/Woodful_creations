# Architecture

backend/app/modules/<domain> - business logic, one folder per domain
backend/app/platform/<concern> - infra (db, security, config, audit, storage, middleware, monitoring)
backend/app/shared/ - genuinely cross-domain, business-neutral helpers (Excel building, import normalization, PDF/document styling, validators)
backend/app/api/routes/ - a few routes with no single domain owner (settings, audit_logs); everything else lives under modules/<domain>/api/
frontend/src/modules/<domain>/pages/ - one file per screen, matching the backend domain; a handful of pages with no single domain owner (auth, users, settings, audit logs, mobile-app QR, 404) stay at frontend/src/pages/ instead

## Modules

Clients -> modules/clients
Products/Rate cards -> modules/catalog
Materials/Stock/Locations -> modules/inventory
Suppliers/Purchases/Personal cart -> modules/procurement
Estimates/Orders/Payments -> modules/sales
Tasks/Production/Issues/Milestones/Project expenses -> modules/operations
Employees/Attendance/Leave/Salary/Working calendar -> modules/hr
Candidates/Interviews -> modules/recruitment
Documents -> modules/documents
Email/Notifications/Automation/Mentions -> modules/communications
Chatbot/AI agents -> modules/ai
Dashboard/Analytics/Search -> modules/reporting
Auth/Users -> modules/auth

## Platform

DB engine, Base, BaseModel, ID sequence/generator, migrations -> platform/database
JWT, password hashing, roles, rate limiting -> platform/security
Settings/env vars -> platform/configuration
Audit log + log_action -> platform/audit
Local/Drive storage abstraction -> platform/storage
Security headers, global rate-limit middleware -> platform/middleware
Production error/monitoring boundary -> platform/monitoring

## Module layout (typical)

modules/<domain>/models.py
modules/<domain>/schemas.py
modules/<domain>/services.py (or a named service file, e.g. order_service.py)
modules/<domain>/api/*.py (routes)
modules/<domain>/imports/*.py (Excel import parsing, where the domain has imports)
modules/<domain>/pdf_generator.py (where the domain generates its own PDFs - order/estimate/invoice, client profile, product, salary slip - business-specific, so not in shared/)

Not every module has every file. Only what the domain actually needs.

## Lookup tables (Unit, PaymentMode, ProjectStatus, etc)

No single domain owner - used across inventory/sales/HR. Stays at
models/setting.py and schemas/setting.py. Route: api/routes/settings.py.

## Tests

backend/tests/modules/<domain>/ - matches the modules/<domain>/ layout
backend/tests/security/, tests/platform/, tests/integration/ - cross-cutting
backend/tests/conftest.py, helpers.py - shared fixtures, apply to all subdirs

## Rules

New business logic goes in modules/<domain>, never in a top-level
models/schemas/services/utils folder.

New infra goes in platform/<concern>, not core/ (core/ no longer exists).

---

## Where is this? A feature-to-file map

When a client reports a problem, look up the feature area below to get
the exact files involved, instead of searching the codebase from
scratch. Organized by business area, not file type.

How to read each entry: Route -> Service/Logic -> Schema -> Model ->
Frontend Page. Not every feature has all five - only real files are
listed, so this needs updating when a domain gains or loses a file.
All paths are relative to backend/app/ or frontend/src/ as marked.

### Auth & Users
| Layer | File |
|---|---|
| Route | modules/auth/api/auth.py, modules/auth/api/users.py |
| Core logic | platform/security/security.py (tokens, password hashing, role checks), platform/security/rate_limit.py |
| Schema | modules/auth/schemas.py |
| Model | modules/auth/models.py (User, PasswordResetToken) |
| Frontend | pages/LoginPage.jsx, pages/ForgotPasswordPage.jsx, pages/ResetPasswordPage.jsx, pages/UsersPage.jsx |

### Clients
Backend: modules/clients/ (models.py, schemas.py, api/routes.py, api/import_routes.py, api/activity_routes.py, api/product_rate_routes.py, api/reports.py, import_utils.py, matching.py)
Frontend: modules/clients/pages/ClientsPage.jsx, ClientDetailPage.jsx, ClientImportPage.jsx

### Estimates
| Layer | File |
|---|---|
| Route | modules/sales/api/estimates.py, modules/sales/api/estimate_imports.py |
| Schema | modules/sales/schemas.py, modules/sales/imports/estimate_schemas.py |
| Model | modules/sales/models.py (includes EstimateLineItem) |
| Excel import | modules/sales/imports/estimate_import.py |
| Frontend | modules/sales/pages/EstimatesPage.jsx, EstimateDetailPage.jsx, EstimateImportPage.jsx |

### Orders & Projects
| Layer | File |
|---|---|
| Route | modules/sales/api/orders.py, modules/sales/api/order_imports.py, modules/operations/api/milestones.py, modules/operations/api/project_expenses.py |
| Service | modules/sales/order_service.py (advance validation, profitability/overall_gross_margin calc, cash payment reference generation) |
| Schema | modules/sales/schemas.py (OrderItem/OrderComment), modules/sales/imports/order_schemas.py, modules/operations/schemas.py (Milestone, ProjectExpense) |
| Model | modules/sales/models.py (OrderItem/OrderComment), modules/operations/models.py (Milestone, ProjectExpense) |
| Excel import | modules/sales/imports/order_import.py |
| Frontend | modules/sales/pages/OrdersPage.jsx, OrderDetailPage.jsx, OrderImportPage.jsx; modules/operations/pages/ProjectExpensesPage.jsx |

### Payments
| Layer | File |
|---|---|
| Route | modules/sales/api/payments.py |
| Schema/Model | modules/sales/schemas.py, modules/sales/models.py (PaymentDocument) |
| Frontend | modules/sales/pages/PaymentsPage.jsx |
| Related | Cash payment reference generation is in modules/sales/order_service.py |

### Products
| Layer | File |
|---|---|
| Route | modules/catalog/api/products.py, modules/catalog/api/product_imports.py |
| Schema | modules/catalog/schemas.py, modules/catalog/imports/product_schemas.py |
| Model | modules/catalog/models.py |
| Excel import | modules/catalog/imports/product_import.py |
| Frontend | modules/catalog/pages/ProductsPage.jsx, ProductDetailPage.jsx, ProductImportPage.jsx |

### Materials & Inventory
| Layer | File |
|---|---|
| Route | modules/inventory/api/materials.py, material_imports.py, material_categories.py, locations.py; modules/procurement/api/supplier_materials.py |
| Service | modules/inventory/stock_service.py (all stock math: issue, purchase receipt, transfer, adjustment, concurrency locking) |
| Schema | modules/inventory/schemas.py, modules/inventory/imports/material_schemas.py |
| Model | modules/inventory/models.py (Material, MaterialCategory, MaterialSubcategory, MaterialAttributeDefinition/Value, Location, Supplier, SupplierMaterial, Purchase, StockLedgerEntry, StockTransfer, StockAdjustment - inventory and procurement share one data model, split only at API layer) |
| Excel import | modules/inventory/imports/material_import.py |
| Frontend | modules/inventory/pages/MaterialsPage.jsx, MaterialDetailPage.jsx, MaterialImportPage.jsx, LocationsPage.jsx, InventoryPage.jsx |

### Stock Movements (Issue / Purchase / Transfer)
| Layer | File |
|---|---|
| Route | modules/operations/api/issues.py, modules/procurement/api/purchases.py, purchase_imports.py; modules/inventory/api/stock_transactions.py |
| Service | modules/inventory/stock_service.py - single source of truth for record_issue, record_purchase, mark_purchase_received, record_transfer, record_adjustment |
| Schema | modules/operations/schemas.py (Issue), modules/inventory/schemas.py (purchases/transfers/adjustments), modules/procurement/imports/purchase_schemas.py |
| Model | modules/operations/models.py (Issue - has rate_at_issue, frozen cost), modules/inventory/models.py (Purchase) |
| Excel import | modules/procurement/imports/purchase_import.py |
| Frontend | modules/operations/pages/IssuesPage.jsx; modules/procurement/pages/PurchasesPage.jsx, PurchaseDetailPage.jsx, PurchaseImportPage.jsx |

### Suppliers
| Layer | File |
|---|---|
| Route | modules/procurement/api/suppliers.py |
| Schema/Model | modules/inventory/schemas.py / models.py (Supplier) |
| Frontend | modules/procurement/pages/SuppliersPage.jsx, SupplierDetailPage.jsx |

### Rate Cards
| Layer | File |
|---|---|
| Route | modules/catalog/api/rate_cards.py, rate_card_imports.py |
| Schema | modules/catalog/schemas.py, modules/catalog/imports/rate_card_schemas.py |
| Model | modules/catalog/models.py |
| Excel import | modules/catalog/imports/rate_card_import.py (two parse functions: market-range layout, standard layout) |
| Frontend | modules/catalog/pages/RateCardsPage.jsx, RateCardImportPage.jsx |

### Employees & HR
| Layer | File |
|---|---|
| Route | modules/hr/api/employees.py, attendance.py, leaves.py, salary_slips.py; modules/recruitment/api/candidates.py, interviews.py |
| Schema | modules/hr/schemas.py (employees/attendance/leave/salary/working calendar), modules/recruitment/schemas.py |
| Model | modules/hr/models.py (Employee, Attendance - unique per employee/day, Leave, SalarySlip), modules/recruitment/models.py (Candidate, Interview) |
| Frontend | modules/hr/pages/EmployeesPage.jsx, EmployeeDetailPage.jsx, AttendancePage.jsx, LeavesPage.jsx, SalarySlipsPage.jsx; modules/recruitment/pages/CandidatesPage.jsx, CandidateDetailPage.jsx, InterviewsPage.jsx |

### Daily Tasks (assignment, completion, handoff)
| Layer | File |
|---|---|
| Route | modules/operations/api/daily_tasks.py - assignment, completion (apply_task_completion), handoff (complete_and_assign_next), status notifications |
| Schema/Model | modules/operations/schemas.py / models.py (DailyTask, TaskComment) |
| Frontend | modules/operations/pages/DailyTasksPage.jsx, TaskDetailPage.jsx |
| Also touches | modules/communications/services/notification_service.py (task notifications), modules/ai/orchestration.py (chatbot task completion - routes through the same apply_task_completion) |

### Production Jobs
| Layer | File |
|---|---|
| Route | modules/operations/api/production_jobs.py |
| Schema/Model | modules/operations/schemas.py / models.py (ProductionJob) |
| Frontend | modules/operations/pages/ProductionJobsPage.jsx, ProductionJobDetailPage.jsx |

### Company Holidays / Working Calendar
| Layer | File |
|---|---|
| Route | modules/hr/api/working_calendar.py, holiday_imports.py |
| Service | modules/hr/working_calendar_service.py |
| Schema | modules/hr/imports/holiday_schemas.py |
| Model | modules/hr/models.py (WorkingCalendarSettings, CompanyHoliday) |
| Excel import | modules/hr/imports/holiday_import.py |
| Frontend | modules/hr/pages/CompanyHolidaysPage.jsx, HolidayImportPage.jsx |

### Chatbot / AI
| Layer | File |
|---|---|
| Route | modules/ai/api/chat.py, agents.py |
| Service | modules/ai/orchestration.py (deterministic parsing), modules/ai/gateway.py (Gemini tool dispatch, kill switch, learning candidates), modules/ai/security.py (text sanitization), modules/ai/tools.py, agents.py |
| Schema/Model | modules/ai/schemas.py / models.py (ChatLearningCandidate) |
| Frontend | modules/ai/pages/LearningCandidatesPage.jsx; components/ChatWidget.jsx, AssistantMascot.jsx (the single, persistent AI entry point - bottom-right on every page) |

### Notifications & Communication
| Layer | File |
|---|---|
| Route | modules/communications/api/notifications.py, communication.py |
| Service | modules/communications/services/notification_service.py (in-app + email, low-stock alerts, visible_to rule), email_service.py (real SMTP), mention_service.py, communication_ai_service.py |
| Schema/Model | modules/communications/schemas.py / models.py |

### Reports & Analytics
| Layer | File |
|---|---|
| Route | domain-specific modules/*/api/reports.py files (Excel exports, daily status report + email), modules/reporting/api/analytics.py, dashboard.py |
| Service | modules/reporting/analytics_service.py |
| Model | modules/reporting/models.py (ReportHistory - 15-day retention metadata; AIWorkspaceReport) |
| Frontend | modules/reporting/pages/AnalyticsPage.jsx, DashboardPage.jsx |

### Automation & Audit
| Layer | File |
|---|---|
| Route | modules/communications/api/automation.py, api/routes/audit_logs.py, modules/reporting/api/search.py |
| Service | modules/communications/services/automation_service.py |
| Schema/Model | modules/communications/schemas.py / models.py (AutomationLog); platform/audit/audit.py (AuditLog, AuditLogResponse, log_action - the shared audit-logging call every route uses) |
| Frontend | pages/AuditLogsPage.jsx |

### Settings & Personal Cart
| Layer | File |
|---|---|
| Route | api/routes/settings.py, modules/procurement/api/personal_cart.py |
| Schema/Model | schemas/setting.py / models/setting.py (lookup/dropdown tables, no single domain owner - shared across modules); modules/procurement/schemas.py / models.py (PersonalCartItem) |
| Frontend | pages/SettingsPage.jsx |

### Documents & Storage
| Layer | File |
|---|---|
| Route | modules/documents/api/routes.py |
| Core logic | platform/storage/storage.py (LocalStorageBackend, DriveStorageBackend, StorageReference - the storage abstraction every upload uses) |
| Schema/Model | modules/documents/schemas.py / models.py |

### Cross-Cutting (shared/)
| Concern | Where |
|---|---|
| Excel building (shared by every report/export) | shared/exporters.py |
| Import normalization (dates, numbers, match keys, row-count guard) | shared/import_normalize.py, import_common.py |
| Document styling (PDF header/logo, plus fmt_date/mask_value/mask_phone) | shared/document_style.py |
| Cross-entity validators | shared/validators.py |

### Quick lookup: "the client says X is broken"
| Client's words | Start here |
|---|---|
| "Can't create/assign a task" | Daily Tasks section above |
| "Stock count looks wrong" | Materials & Inventory + Stock Movements sections |
| "Wrong profit/cost showing for an order" | modules/sales/order_service.py profitability()/overall_gross_margin() |
| "Duplicate attendance / wrong payroll" | modules/hr/models.py (Attendance) |
| "Email didn't arrive" | modules/communications/services/email_service.py, then the feature's route file for when it calls it |
| "Chatbot picked the wrong person" | modules/ai/orchestration.py _resolve_employee_by_name |
| "Excel import rejected my file" | matching modules/<domain>/imports/<entity>_import.py file |
| "Can't see a client's PDF / wrong data on it" | modules/documents/api/routes.py, platform/storage/storage.py |
| "Report/notification not reaching everyone" | modules/communications/services/notification_service.py, feature's route file |

---

## Key behaviors to know

**Clients -> Estimates -> Orders**, not locked to each other. A client
can be quoted before an order exists; several competing estimates can
exist for one client. Revising an estimate creates a new versioned
row (parent_estimate_id), never overwrites.

**Orders track three independent statuses** - design_status,
execution_status, delivery_status - plus an overall project_status
and progress_percent. These genuinely move independently in a real
project; check which one actually matters before assuming "order
status" means a single field.

**Order.total_received/balance are stored columns, kept in sync by
Order.recompute_totals()** whenever a Payment is added/edited - not
computed on the fly (the dashboard reads them often). advance is
stored directly on the order, not as its own Payment row - anything
that recomputes total_received from scratch must add advance back in,
or it silently vanishes the moment a payment is logged after order
creation.

**Two ID schemes per entity**: a sequential human-scannable code
(EMP-011, WC-2026-001, generated by platform/database/id_generator.py)
and an unrelated opaque business_id (10-char random, e.g. A7K92P4XQ1)
for URLs/exports where record count/order shouldn't be inferable.

**Roles are MASTER and USER only, gated per-field, not per-record.**
There is no per-user resource-ownership model anywhere - every
authenticated user can see every client/order/task/project; role only
ever gates which fields are visible (financial redaction) or which
routes are callable, never which specific records. Route-level gating
is require_role(*roles) (platform/security/security.py); field-level
redaction is an inline is_privileged check plus manual null-out (see
_serialize_orders() in modules/sales/api/orders.py). Before building
anything that looks like per-record authorization, stop - that model
doesn't exist here and would be new architecture, not a bug fix.

**Every write should call platform/audit/audit.py's log_action()** -
it's opt-in per route, not automatic. Check a neighboring route in the
same file to see the pattern before adding a new mutating route.

**The chatbot is deterministic keyword matching first, Gemini
fallback second** (modules/ai/orchestration.py, then
modules/ai/gateway.py when the matcher finds nothing). Neither writes
to the database directly - a write is always a ProposedAction the user
must confirm, then the same authenticated API/RBAC/audit path a human
form submission would use. Two exceptions execute immediately
(create_task, complete_task), but still run the real role/ownership
check against the logged-in session. Financial values (payment
amounts, prices, costs, salary) never reach the external AI provider -
extracted and held locally, restored after the provider's response
returns.

**Materials have a Category -> Subcategory -> dynamic-attribute
hierarchy layered on top of (not replacing) older flat fields.**
Material.category/location stay in sync with subcategory_id/
location_id server-side (_resolve_category_name/_resolve_location_path
in modules/inventory/api/materials.py) - check both when either looks
wrong.

**Notifications and automation are on-demand, not scheduled.** No
background job scheduler exists - notification checks run when
GET /api/notifications/ is called (bell panel opened);
POST /api/automation/run is the hook an external scheduler should call
periodically. Both use dedup_key to avoid spamming the same alert.

**There is one storage implementation** (platform/storage/storage.py) -
local disk or Google Drive behind one interface, keyed by Drive's own
file ID. Email is plain SMTP (smtplib, username/password) - not the
Gmail API, no OAuth.

**Migrations run automatically on backend startup and a failure
refuses to start the server** (platform/database/auto_migrate.py,
called from app/main.py's startup hook) - deliberately, so the app
never serves requests against a schema it knows is wrong. If the
server won't start, check the startup log for a migration failure
before assuming the code is broken.
