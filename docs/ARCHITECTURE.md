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
Settings/env vars -> platform/config
Audit log + log_action -> platform/audit
Local/Drive storage abstraction -> platform/storage
Security headers, global rate-limit middleware -> platform/middleware
Production error/monitoring boundary -> platform/monitoring

## Module layout (typical)

modules/<domain>/models.py
modules/<domain>/schemas.py
modules/<domain>/services.py (or a named service file, e.g. order_service.py)
modules/<domain>/api.py (routes; operations has two: api_operations.py and api_production.py)
modules/<domain>/imports.py (Excel import parsing, where the domain has imports)
PDF generation lives directly in each domain's own services.py/api.py/exports.py (order/estimate/invoice, client profile, product, salary slip - business-specific, so not in shared/) - there is no separate pdf_generator.py per domain; that was consolidated into the domain's own service/export file.

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
| Route | modules/auth/auth.py (single consolidated file - models, schemas, and routes for both auth and users) |
| Core logic | platform/security.py (tokens, password hashing, role checks, rate limiting) |
| Schema | modules/auth/schemas.py |
| Model | modules/auth/models.py (User, PasswordResetToken) |
| Frontend | pages/LoginPage.jsx, pages/ForgotPasswordPage.jsx, pages/ResetPasswordPage.jsx, pages/UsersPage.jsx |

### Clients
Backend: modules/clients/ (models.py, schemas.py, api.py, portal_api.py, services.py)
Frontend: modules/clients/pages/ClientsPage.jsx, ClientDetailPage.jsx, ClientImportPage.jsx

### Unified Client Relationship Timeline (Family 137 feature 5)
| Layer | File |
|---|---|
| Route | GET /api/clients/{id}/relationship-timeline (clients/api.py) |
| Service | clients/services.py's client_relationship_timeline - a presentation/aggregation layer only, over existing ClientActivity, Estimate, Order, Payment, ClientDocument, GenericDocument (parent_type="order"), and Notification rows for this client's own orders/estimates - never a second, duplicated timeline table. Payment amounts and financial notification types are gated to MASTER, matching every other financial-confidentiality rule in this codebase. |
| Frontend | modules/clients/pages/ClientDetailPage.jsx's "Timeline" tab (fetched on demand, not on every page load) |

### Estimates
| Layer | File |
|---|---|
| Route | modules/sales/api.py (estimates and estimate imports) |
| Schema | modules/sales/schemas.py, modules/sales/imports.py |
| Model | modules/sales/models.py (includes EstimateLineItem) |
| Excel import | modules/sales/imports.py |
| Frontend | modules/sales/pages/EstimatesPage.jsx, EstimateDetailPage.jsx, EstimateImportPage.jsx |

### Orders & Projects
| Layer | File |
|---|---|
| Route | modules/sales/api.py, modules/operations/api_operations.py |
| Service | modules/sales/services.py (advance validation, profitability/overall_gross_margin calc, cash payment reference generation); OrderService.compute_order_health - the single authoritative Order Health/Delivery Risk calculation (Family 130 P0.1, extended by P0.50): 4-level risk_level (ON_TRACK/WATCH/AT_RISK/CRITICAL), delivery_timing, evidence (each material shortage now carries procurement_status - no_purchase_placed/purchase_placed_insufficient/purchase_covers_gap - and blocks_production, P0.50 s.13), business_impact, next_action, readiness, production_summary (total/completed/pending/blocked job counts, P0.50 s.14) - consumed identically by GET /orders/{id}/health, the chatbot's _order_risk_workspace (services.py), and bulk_attention_flags' lighter per-list-row classification (Orders List). GET /orders/{id}/what-if (P0.50 s.11, What-If Scheduling) reuses this same function via its optional override_delivery_date parameter (default None - zero behavior change for every other caller) to simulate a hypothetical delivery date without writing anything to the database, returning current vs simulated risk side by side; modules/inventory/services.py's calculate_order_material_requirements (per-order material shortage against BOM/current stock/pending purchases/reservations - GET /{order_id}/material-requirements) and calculate_reserved_stock (unfulfilled BOM demand across other open orders, computed fresh, not a stored field - no Reserved Qty column exists on Material); calculate_at_risk_orders (Family 130 - business-wide version of the same shortage formula across every open order in a bounded number of queries, not a loop over the per-order function, which would be its own N+1 at dashboard scale - GET /api/dashboard/at-risk-orders, surfaced on DashboardPage's "Attention Required" and top summary card); _supplier_options_for_materials (Family 130 - which supplier can actually resolve a shortage, price/lead-time/preferred first, reused by both the per-order and business-wide functions and by api_production.py's material-status endpoint, so a shortage never appears without the supplier options that could fix it) |
| Schema | modules/sales/schemas.py (OrderItem/OrderComment), modules/sales/imports.py, modules/operations/schemas.py (Milestone, ProjectExpense) |
| Model | modules/sales/models.py (OrderItem/OrderComment), modules/operations/models.py (Milestone, ProjectExpense) |
| Excel import | modules/sales/imports.py |
| Frontend | modules/sales/pages/OrdersPage.jsx, OrderDetailPage.jsx, OrderImportPage.jsx; modules/operations/pages/ProjectExpensesPage.jsx |

### Visual Build Timeline (Family 137 feature 2)
| Layer | File |
|---|---|
| Route | GET /api/orders/{id}/build-timeline (sales/api.py) |
| Service | OrderService.build_timeline (sales/services.py) - a read-only presentation layer over existing Milestone and ProductionJob data, reusing compute_order_health for the order's own risk_level rather than a second status engine. Each milestone's status (planned/current/completed/delayed/at_risk) is derived only from its own target_date/completed_date plus, for the single next open milestone, the order's real delivery risk. |
| Frontend | modules/sales/pages/SalesDetailPages.jsx's OrderDetailPage "Build Timeline" card (Overview tab) |

### Capacity-Aware Delivery Promise (Family 137 feature 12)
| Layer | File |
|---|---|
| Route | GET /api/orders/{id}/delivery-promise (evaluation - read-only PREDICTION+RECOMMENDATION), POST /api/orders/{id}/delivery-promise (the one place a human's final promised date is written, master-only) - both in sales/api.py |
| Service | OrderService.evaluate_delivery_promise (sales/services.py) - working-day count via hr/services.get_working_dates, material shortage via StockService.calculate_order_material_requirements plus real Purchase.expected_delivery_date, and production backlog via ProductionOperation.estimated_duration_minutes against each WorkCentre.capacity_hours_per_day. Recording writes to the existing Order.delivery_date column (never a second "promised date" field) with its own distinct audit action (delivery_date_promised). |
| Frontend | modules/sales/pages/SalesDetailPages.jsx's OrderDetailPage "Delivery Promise" card (Overview tab, master-only) |

### Payments
| Layer | File |
|---|---|
| Route | modules/sales/api.py |
| Schema/Model | modules/sales/schemas.py, modules/sales/models.py (PaymentDocument) |
| Frontend | modules/sales/pages/PaymentsPage.jsx |
| Related | Cash payment reference generation is in modules/sales/services.py |

### Products
| Layer | File |
|---|---|
| Route | modules/catalog/api.py, modules/catalog/api.py |
| Schema | modules/catalog/schemas.py, modules/catalog/imports.py |
| Model | modules/catalog/models.py |
| Excel import | modules/catalog/imports.py |
| Frontend | modules/catalog/pages/ProductsPage.jsx, ProductDetailPage.jsx, ProductImportPage.jsx |
| Hardware requirements | No separate hardware-BOM concept - a hinge/handle/channel is just a Material (category="Hardware") linked via the same ProductMaterial BOM used for raw materials, so it reuses modules/inventory/services.py's shortage/reservation calculation unchanged (confirmed with a real test, not assumed - see tests/modules/inventory/test_shortage_intelligence.py). Product.hardware_cost is a separate, unconnected flat manual cost input, not a quantity/stock-tracked figure.

### Materials & Inventory
| Layer | File |
|---|---|
| Route | modules/inventory/api.py, material_imports.py, material_categories.py, locations.py; modules/procurement/api.py |
| Service | modules/inventory/services.py (all stock math: issue, purchase receipt, transfer, adjustment, concurrency locking) |
| Schema | modules/inventory/schemas.py, modules/inventory/imports.py |
| Model | modules/inventory/models.py (Material, MaterialCategory, MaterialSubcategory, MaterialAttributeDefinition/Value, Location, StockLedgerEntry, StockTransfer, StockAdjustment). Supplier/SupplierMaterial/Purchase moved to modules/procurement/models.py (Family 130 P0.2 ownership correction) - inventory owns physical stock only, procurement owns suppliers and the purchase business record. |
| Excel import | modules/inventory/imports.py |
| Frontend | modules/inventory/pages/MaterialsPage.jsx, MaterialDetailPage.jsx, MaterialImportPage.jsx, LocationsPage.jsx, InventoryPage.jsx |

### Stock Movements (Issue / Purchase / Transfer)
| Layer | File |
|---|---|
| Route | modules/operations/api_operations.py, modules/procurement/api.py, purchase_imports.py; modules/inventory/api.py |
| Service | modules/inventory/services.py - single source of truth for record_issue, record_purchase, mark_purchase_received, record_transfer, record_adjustment |
| Schema | modules/operations/schemas.py (Issue), modules/inventory/schemas.py (purchases/transfers/adjustments), modules/procurement/schemas.py |
| Model | modules/operations/models.py (Issue - has rate_at_issue, frozen cost), modules/procurement/models.py (Purchase) |
| Excel import | modules/procurement/services.py |
| Frontend | modules/operations/pages/IssuesPage.jsx; modules/procurement/pages/PurchasesPage.jsx, PurchaseDetailPage.jsx, PurchaseImportPage.jsx |

### Suppliers
| Layer | File |
|---|---|
| Route | modules/procurement/api.py |
| Schema/Model | modules/inventory/schemas.py (SupplierResponse etc, not yet moved) / modules/procurement/models.py (Supplier, SupplierMaterial) |
| Frontend | modules/procurement/pages/SuppliersPage.jsx, SupplierDetailPage.jsx |

### Procurement Requirements & Supplier Decisions (P0.2)
| Layer | File |
|---|---|
| Route | modules/procurement/api.py - includes POST /{id}/decision (validates the selected supplier actually has a SupplierMaterial link for the material - backend-enforced, never trusts a frontend dropdown) and POST /{id}/purchase (creates the Purchase from the requirement's own recorded decision, links requirement.purchase_id, marks the requirement Fulfilled only when receipt_status is actually "Received") |
| Schema/Model | modules/procurement/schemas.py, models.py (ProcurementRequirement, SupplierDecision) |
| Note | required_quantity/available/shortage on a requirement are a snapshot of modules/inventory/services.py's calculate_order_material_requirements at creation time - never a second shortage engine |

### Purchases & Suppliers - service ownership (P0.2 correction)
modules/procurement/services.py's ProcurementService owns record_purchase,
mark_purchase_received, and supplier-option recommendation
(_supplier_options_for_materials) - moved out of
modules/inventory/services.py's StockService, which keeps only the
physical stock mutation (_apply_stock_receipt) and inventory-owned
calculations (reserved stock, order material requirements, at-risk
orders). The two services call into each other with a local,
function-level import each way (ProcurementService needs
StockService._apply_stock_receipt; StockService needs
ProcurementService._supplier_options_for_materials to enrich its own
shortage output) - this is deliberate, not an oversight: a top-level
import either direction would be circular.

### Rate Cards
| Layer | File |
|---|---|
| Route | modules/catalog/api.py, rate_card_imports.py |
| Schema | modules/catalog/schemas.py, modules/catalog/imports.py |
| Model | modules/catalog/models.py |
| Excel import | modules/catalog/imports.py (two parse functions: market-range layout, standard layout) |
| Frontend | modules/catalog/pages/RateCardsPage.jsx, RateCardImportPage.jsx |

### Employees & HR
| Layer | File |
|---|---|
| Route | modules/hr/api.py, attendance.py, leaves.py, salary_slips.py, salary_advances.py; modules/recruitment/module.py, interviews.py |
| Schema | modules/hr/schemas.py (employees/attendance/leave/salary/salary advance/working calendar), modules/recruitment/schemas.py |
| Model | modules/hr/models.py (Employee, Attendance - unique per employee/day, Leave, SalarySlip, SalaryAdvance), modules/recruitment/models.py (Candidate, Interview) |
| Frontend | modules/hr/pages/EmployeesPage.jsx, EmployeeDetailPage.jsx, AttendancePage.jsx, LeavesPage.jsx, SalarySlipsPage.jsx; modules/recruitment/pages/CandidatesPage.jsx, CandidateDetailPage.jsx, InterviewsPage.jsx |
| Salary Advance (P0.44) | Full workflow: request (employee or Master-on-behalf) -> Master approve (optionally at a different amount than requested, which stays historical)/reject -> recovery against a real, existing SalarySlip only (never a bare number - 404 if no slip exists for that employee/month). Recovery sets SalarySlip.advance_deduction and recomputes net_salary via salary_slips.py's own _compute_net (imported, not reimplemented). Approve/reject notify the employee's own linked User account (in-app + email in one call, via the same NotificationService.notify() every other module uses - never a second notification path) - a missing linked account or email never blocks the decision itself. Migration 0072. Frontend: modules/hr/pages/SalaryAdvancesPage.jsx (adapts to role, same pattern as SalarySlipsPage.jsx). |
| Overtime (P0.43) | Attendance.overtime_hours is a real, directly Master-settable column (migration 0073) - deliberately NOT derived from in_time/out_time (a long clock span alone implies nothing; only an explicit value counts), zero by default. Employees can mark their own attendance but cannot set a non-zero overtime_hours on it (403) - only Master can. working_hours remains a separate, purely informational clock-span property that never feeds overtime_hours. POST /api/attendance/overtime is the "Manage Overtime" action - one or more dates for one employee, mode="add" (genuinely additive per-date, never replaces) or mode="set" (explicit replacement); creates a bare Attendance record if none exists for a targeted date. |
| Salary Days (P0.43) | working_calendar_service.py's compute_salary_days (Monday-Saturday/configured working days minus APPROVED leave overlapping the month, never double-subtracting a leave day that already falls on a non-working date) - surfaced as additive fields (calendar_days/leave_days/salary_days) on the existing GET /api/salary-slips/attendance-summary suggestion, alongside (not replacing) the actual-attendance-based suggested_paid_days. |
| Payroll summary (P0.43) | modules/hr/payroll_service.py - get_payroll_summary (per month/year: status counts, employees with no slip yet, pending/paid net totals, advance recovery this month) and get_salary_advance_summary (business-wide outstanding advances) - pure aggregation over SalarySlip.status/SalaryAdvance, no new calculation. Not yet wired to an API route. |
| Employee 360 / HR Command Center (Family 137, section 13) | modules/hr/services.py's employee_overview/employee_attendance_intelligence/employee_calendar/employee_leave_summary/employee_work_intelligence/employee_workload/employee_relationships/employee_cost_contribution/employee_needs_attention/employee_lifecycle/employee_activity_timeline - pure read-only aggregation over existing Employee/Attendance/Leave/SalarySlip/SalaryAdvance/DailyTask/ProductionJob/GenericDocument/AuditLog records, never a second HR/task/leave/attendance system. Routes: GET /api/employees/{id}/360-overview, /workload, /relationships, /calendar, /activity-timeline, /lifecycle, PUT /api/employees/{id}/lifecycle/{item_id} - all master-or-self (see hr/api.py's _require_own_or_master), with document-derived facts (counts, expiring-document exceptions, document timeline entries) additionally gated master-only to match the Documents API's own stricter rule for the "employee" parent type. Onboarding/offboarding checklist: EmployeeLifecycleItem model (migration 0076), seeded from the fixed ONBOARDING_ITEMS/OFFBOARDING_ITEMS catalogs in hr/models.py; four onboarding items (record/documents/role/manager) are recomputed from live data on every read rather than stored as a trusted checkbox. Employee.exit_date/exit_reason (migration 0076) are offboarding facts set explicitly via EmployeeUpdate, never auto-inferred from a status change. create_employee/update_employee now call log_action (previously only delete_employee did), feeding the Activity Timeline's designation/salary/status/manager change entries. GenericDocument gained document_type/issue_date/expiry_date (migration 0076, shared by every parent type, not employee-only) - surfaced in DocumentsPanel (components/Assistant.jsx) via an opt-in enableCategorization prop. Workload is Low/Medium/High from an explicit documented formula (active tasks + overdue tasks x 2), never a hidden score; cost/contribution is explicitly labeled FACT with a disclaimer that it is not a profitability score. Cai integration (13.13) needed no new backend code - ChatWidget (components/Assistant.jsx) already scopes context to record_type="employee" from the employeeId route param, so Employee 360's "Ask Cai" quick actions just dispatch openWithMessage() with the four example prompts from the spec. Frontend: modules/hr/pages/WorkforcePages.jsx's EmployeeDetailPage - tabs Overview/Attendance/Leave/Tasks/Production/Salary/Documents/Onboarding/Activity. |

### Daily Tasks (assignment, completion, handoff)
| Layer | File |
|---|---|
| Route | modules/operations/api_operations.py - assignment, completion (apply_task_completion), handoff (complete_and_assign_next), status notifications; list endpoint's include_material_risk=true opt-in flag (Family 130 section 12) annotates each task with material_at_risk, using StockService.calculate_at_risk_orders computed once for the whole page - opt-in because most callers of this list (e.g. the dashboard's small "my tasks" widget) have no use for it |
| Schema/Model | modules/operations/schemas.py / models.py (DailyTask, TaskComment) |
| Frontend | modules/operations/pages/DailyTasksPage.jsx, TaskDetailPage.jsx |
| Also touches | modules/communications/services/notification_service.py (task notifications), modules/ai/orchestration.py (chatbot task completion - routes through the same apply_task_completion) |

### Production Jobs
| Layer | File |
|---|---|
| Route | modules/operations/api_production.py |
| Schema/Model | modules/operations/schemas.py / models.py (ProductionJob) |
| Frontend | modules/operations/pages/ProductionJobsPage.jsx, ProductionJobDetailPage.jsx |
| Dependency/shortage check | GET /{job_id}/material-status - reuses modules/inventory/services.py's calculate_order_material_requirements for the job's own order_id, no separate calculation. There is no "Blocked" status value (confirmed against the real frontend dropdown; blocker_reason is freestanding and can accompany any status) - do not add one without also updating the frontend dropdown deliberately. |
| Readiness (P0.3) | GET /{job_id}/readiness - READY/PARTIALLY_READY/BLOCKED, distinguishes "shortage covered by a pending purchase" (not READY - goods aren't physically in hand) from genuinely in-stock; employee-reported blocker_reason always overrides the material check. |
| Variance (P0.3, planned vs actual) | GET /{job_id}/variance - quantity variance from ProductionJob.planned_qty/completed_qty; duration variance from ProductionOperation.estimated_duration_minutes/actual_duration_minutes, computed only across operations that actually have an actual duration recorded (duration_complete tells the caller whether that's all of them or only some - never a fabricated full-job variance from partial data). |
| Risk (P0.3 section 29) | GET /{job_id}/risks - a list of individually-explained findings (type/what/why/impact/when), never a single opaque score. Covers material shortage (reuses readiness), dependency blockage (reuses is_blocked_by_dependency), work-centre capacity overload, and order delivery-date risk (already passed, or within 3 days). Deliberately does NOT check procurement-delay or "overdue operation" - no data link/field exists for either yet; an empty list means "nothing found from checkable data", not a safety guarantee. |

### Cutting (P0.3 section 25)
| Layer | File |
|---|---|
| Route | modules/operations/api_production.py |
| Schema/Model | modules/operations/schemas.py / models.py (CuttingRequirement) |
| Migration | alembic/versions/0071_cutting_requirements.py |
| Note | One row per part - real length_mm/width_mm/thickness_mm/grain_direction/rotation_allowed/kerf_mm, never collapsed into a free-text description. Creating a row is planning only; it has no write path into Material.current_stock at all (confirmed by a real test) - actual consumption still goes only through Issue/StockService.record_issue. Exposed on ProductionJobDetailPage.jsx (add/list/delete). Nesting (arranging these parts onto sheets) is not built - would consume this table's data, not duplicate it. |

### Company Holidays / Working Calendar
| Layer | File |
|---|---|
| Route | modules/hr/api.py, holiday_imports.py |
| Service | modules/hr/working_calendar_service.py |
| Schema | modules/hr/schemas.py |
| Model | modules/hr/models.py (WorkingCalendarSettings, CompanyHoliday) |
| Excel import | modules/hr/api.py |
| Frontend | modules/hr/pages/CompanyHolidaysPage.jsx, HolidayImportPage.jsx |

### Chatbot / AI
| Layer | File |
|---|---|
| Route | modules/ai/api.py, agents.py |
| Service | modules/ai/orchestration.py (deterministic parsing - includes _at_risk_orders, Family 130 section 15, matched by a combined "mentions an order" + "mentions risk/blocked/delayed" check rather than a fixed phrase list, since a fixed list missed natural phrasing like "which orders ARE at risk"; reuses StockService.calculate_at_risk_orders directly, the same calculation already surfacing on the dashboard and daily-tasks list), modules/ai/gateway.py (Gemini tool dispatch, kill switch, learning candidates), modules/ai/security.py (text sanitization), modules/ai/tools.py, agents.py |
| Schema/Model | modules/ai/schemas.py / models.py (ChatLearningCandidate) |
| Frontend | modules/ai/pages/LearningCandidatesPage.jsx; components/ChatWidget.jsx, AssistantMascot.jsx (the single, persistent AI entry point - bottom-right on every page) |
| Family 131 tools | get_business_attention (reuses business_risk_service.get_business_risks - "what needs my attention"), get_salary_advance_status/get_overtime_status (master-only, reuse hr/payroll_service.get_salary_advance_summary/get_overtime_summary) - all registered in both READ_TOOL_DISPATCH (tools.py) and gateway.py's Gemini function-declaration list; reachable via Gemini's natural-language fallback today, not yet added to orchestration.py's deterministic keyword routing. |

### Notifications & Communication
| Layer | File |
|---|---|
| Route | modules/communications/api.py, communication.py |
| Service | modules/communications/services/notification_service.py (in-app + email, low-stock alerts, visible_to rule), email_service.py (real SMTP), mention_service.py, communication_ai_service.py |
| Schema/Model | modules/communications/schemas.py / models.py |

### Reports & Analytics
| Layer | File |
|---|---|
| Route | domain-specific modules/*/api/reports.py files (Excel exports, daily status report + email), modules/reporting/api.py, dashboard.py |
| Service | modules/reporting/analytics_service.py |
| Model | modules/reporting/models.py (ReportHistory - 15-day retention metadata; AIWorkspaceReport) |
| Frontend | modules/reporting/pages/AnalyticsPage.jsx, DashboardPage.jsx |

### Forward Cash-Flow Forecast (Family 137 feature 12) + Owner Daily/Weekly Business Briefing (feature 11)
| Layer | File |
|---|---|
| Route | GET /api/dashboard/cash-flow-forecast, GET /api/dashboard/owner-briefing?period=daily\|weekly (reporting/api.py, both master-only) |
| Service | reporting/services.py's cash_flow_forecast (buckets real, current Order.balance by delivery_date into weekly EXPECTED buckets, real Payment rows into ACTUAL, a past delivery_date with balance still outstanding into OVERDUE, no delivery_date into FORECAST; a past-week EXPECTED balance still outstanding becomes an exception) and owner_briefing (a synthesis over get_business_risks, cash_flow_forecast, inventory/_low_stock, operations/_production_bottlenecks + _delayed_deliveries + _delayed_projects, and hr/get_payroll_summary + get_salary_advance_summary + pending Leave rows - never a second, parallel computation of any of these; a section only appears when it actually found something, and facts/predictions/recommendations are kept in separate lists, never blended) |
| Frontend | modules/reporting/pages/AnalyticsPages.jsx's OwnerBriefingPage (route /owner-briefing, master-only nav item) |

### Cross-Module Business Risk + Business Decision Centre (P0.49/P0.51)
| Layer | File |
|---|---|
| Route | modules/reporting/api.py - GET / (prioritized list + severity counts), GET /{entity_type}/{entity_id} (single item, for AI/chatbot "why is X at risk") |
| Service | modules/reporting/business_risk_service.py - orchestrates OrderService.compute_order_health (DELIVERY risk, one item per open order not ON_TRACK - never a second risk calculation) and real SalarySlip/SalaryAdvance data (PAYROLL risk: finalized-unpaid slips, Pending advance requests only - not every outstanding-balance advance, since recovery can legitimately span months) |
| Note | Master-only payroll/advance risk items (financial/HR confidentiality) - an employee gets a genuinely shorter list, not a redacted copy. A non-privileged entity lookup returns 404, identical to "doesn't exist" - never a distinguishable "exists but you can't see it". Frontend: modules/reporting/pages/BusinessDecisionCentrePage.jsx (severity KPI filters, decision cards, "Review" links to the entity's real list page - no per-entity detail routes exist for salary slips/advances, so this deliberately does not link to a nonexistent one). |

### Automation & Audit
| Layer | File |
|---|---|
| Route | modules/communications/automation.py, api/routes/audit_logs.py, modules/reporting/api.py |
| Service | modules/communications/services/automation_service.py - 11 rules total; order_at_risk_material_shortage (Family 130) reuses StockService.calculate_at_risk_orders directly, complementing the older, material-only low_stock_purchase_recommendation rule with order-level context (which specific order is threatened, not just which material is low) |
| Schema/Model | modules/communications/schemas.py / models.py (AutomationLog); platform/audit.py (AuditLog, AuditLogResponse, log_action - the shared audit-logging call every route uses) |
| Frontend | pages/AuditLogsPage.jsx |

### Settings & Personal Cart
| Layer | File |
|---|---|
| Route | api/routes/settings.py, modules/procurement/api.py |
| Schema/Model | schemas/setting.py / models/setting.py (lookup/dropdown tables, no single domain owner - shared across modules); modules/procurement/schemas.py / models.py (PersonalCartItem) |
| Frontend | pages/SettingsPage.jsx |

### Documents & Storage
| Layer | File |
|---|---|
| Route | modules/documents/api.py |
| Core logic | platform/storage.py (LocalStorageBackend, DriveStorageBackend, StorageReference - the storage abstraction every upload uses) |
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
| "Wrong profit/cost showing for an order" | modules/sales/services.py profitability()/overall_gross_margin() |
| "Duplicate attendance / wrong payroll" | modules/hr/models.py (Attendance) |
| "Email didn't arrive" | modules/communications/services/email_service.py, then the feature's route file for when it calls it |
| "Chatbot picked the wrong person" | modules/ai/orchestration.py _resolve_employee_by_name |
| "Excel import rejected my file" | matching modules/<domain>/imports/<entity>_import.py file |
| "Can't see a client's PDF / wrong data on it" | modules/documents/api.py, platform/storage.py |
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
(EMP-011, WC-2026-001, generated by platform/ids.py)
and an unrelated opaque business_id (10-char random, e.g. A7K92P4XQ1)
for URLs/exports where record count/order shouldn't be inferable.

**Roles are MASTER and USER only, gated per-field, not per-record.**
There is no per-user resource-ownership model anywhere - every
authenticated user can see every client/order/task/project; role only
ever gates which fields are visible (financial redaction) or which
routes are callable, never which specific records. Route-level gating
is require_role(*roles) (platform/security.py); field-level
redaction is an inline is_privileged check plus manual null-out (see
_serialize_orders() in modules/sales/api.py). Before building
anything that looks like per-record authorization, stop - that model
doesn't exist here and would be new architecture, not a bug fix.

**Every write should call platform/audit.py's log_action()** -
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
in modules/inventory/api.py) - check both when either looks
wrong.

**Notifications and automation are on-demand, not scheduled.** No
background job scheduler exists - notification checks run when
GET /api/notifications/ is called (bell panel opened);
POST /api/automation/run is the hook an external scheduler should call
periodically. Both use dedup_key to avoid spamming the same alert.

**There is one storage implementation** (platform/storage.py) -
local disk or Google Drive behind one interface, keyed by Drive's own
file ID. Email is plain SMTP (smtplib, username/password) - not the
Gmail API, no OAuth.

**Migrations run automatically on backend startup and a failure
refuses to start the server** (platform/database.py,
called from app/main.py's startup hook) - deliberately, so the app
never serves requests against a schema it knows is wrong. If the
server won't start, check the startup log for a migration failure
before assuming the code is broken.
