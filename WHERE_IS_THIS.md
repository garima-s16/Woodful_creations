# Where Is This? - Feature-to-File Map

Purpose: when a client reports a problem, look up the feature area
below to get the exact files involved, instead of searching the
codebase from scratch. Organized by business area, not file type.

How to read each entry: Route -> Service/Logic -> Schema -> Model ->
Frontend Page. Not every feature has all five - only real files are
listed, so this needs updating when a domain gains or loses a file.

All paths are relative to backend/app/ or frontend/src/ as marked.

---

## Auth & Users
| Layer | File |
|---|---|
| Route | modules/auth/api/auth.py, modules/auth/api/users.py |
| Core logic | platform/security/security.py (tokens, password hashing, role checks), platform/security/rate_limit.py |
| Schema | modules/auth/schemas.py |
| Model | modules/auth/models.py (User, PasswordResetToken) |
| Frontend | pages/LoginPage.jsx, pages/ForgotPasswordPage.jsx, pages/ResetPasswordPage.jsx, pages/UsersPage.jsx |

## Clients
Backend: modules/clients/ (models.py, schemas.py, api/routes.py, api/import_routes.py, api/activity_routes.py, api/product_rate_routes.py, api/reports.py, import_utils.py, matching.py)
| Layer | File |
|---|---|
| Frontend | pages/ClientsPage.jsx, pages/ClientDetailPage.jsx, pages/ClientImportPage.jsx |

## Estimates
| Layer | File |
|---|---|
| Route | modules/sales/api/estimates.py, modules/sales/api/estimate_imports.py |
| Schema | modules/sales/schemas.py, modules/sales/imports/estimate_schemas.py |
| Model | modules/sales/models.py (includes EstimateLineItem) |
| Excel import | modules/sales/imports/estimate_import.py |
| Frontend | pages/EstimatesPage.jsx, pages/EstimateDetailPage.jsx, pages/EstimateImportPage.jsx |

## Orders & Projects
| Layer | File |
|---|---|
| Route | modules/sales/api/orders.py, modules/sales/api/order_imports.py, modules/operations/api/milestones.py, modules/operations/api/project_expenses.py |
| Service | modules/sales/order_service.py (advance validation, profitability calc, cash payment reference generation) |
| Schema | modules/sales/schemas.py (OrderItem/OrderComment), modules/sales/imports/order_schemas.py, modules/operations/schemas.py (Milestone, ProjectExpense) |
| Model | modules/sales/models.py (OrderItem/OrderComment), modules/operations/models.py (Milestone, ProjectExpense) |
| Excel import | modules/sales/imports/order_import.py |
| Frontend | pages/OrdersPage.jsx, pages/OrderDetailPage.jsx, pages/OrderImportPage.jsx, pages/ProjectExpensesPage.jsx |

## Payments
| Layer | File |
|---|---|
| Route | modules/sales/api/payments.py |
| Schema/Model | modules/sales/schemas.py, modules/sales/models.py (PaymentDocument) |
| Frontend | pages/PaymentsPage.jsx |
| Related | Cash payment reference generation is in modules/sales/order_service.py |

## Products
| Layer | File |
|---|---|
| Route | modules/catalog/api/products.py, modules/catalog/api/product_imports.py |
| Schema | modules/catalog/schemas.py, modules/catalog/imports/product_schemas.py |
| Model | modules/catalog/models.py |
| Excel import | modules/catalog/imports/product_import.py |
| Frontend | pages/ProductsPage.jsx, pages/ProductDetailPage.jsx, pages/ProductImportPage.jsx |

## Materials & Inventory
| Layer | File |
|---|---|
| Route | modules/inventory/api/materials.py, material_imports.py, material_categories.py, locations.py; modules/procurement/api/supplier_materials.py |
| Service | modules/inventory/stock_service.py (all stock math: issue, purchase receipt, transfer, adjustment, concurrency locking) |
| Schema | modules/inventory/schemas.py, modules/inventory/imports/material_schemas.py |
| Model | modules/inventory/models.py (Material, MaterialCategory, MaterialSubcategory, MaterialAttributeDefinition/Value, Location, Supplier, SupplierMaterial, Purchase, StockLedgerEntry, StockTransfer, StockAdjustment - inventory and procurement share one data model, split only at API layer) |
| Excel import | modules/inventory/imports/material_import.py |
| Frontend | pages/MaterialsPage.jsx, pages/MaterialDetailPage.jsx, pages/MaterialImportPage.jsx, pages/LocationsPage.jsx, pages/InventoryPage.jsx |

## Stock Movements (Issue / Purchase / Transfer)
| Layer | File |
|---|---|
| Route | modules/operations/api/issues.py, modules/procurement/api/purchases.py, purchase_imports.py; modules/inventory/api/stock_transactions.py |
| Service | modules/inventory/stock_service.py - single source of truth for record_issue, record_purchase, mark_purchase_received, record_transfer, record_adjustment |
| Schema | modules/operations/schemas.py (Issue), modules/inventory/schemas.py (purchases/transfers/adjustments), modules/procurement/imports/purchase_schemas.py |
| Model | modules/operations/models.py (Issue - has rate_at_issue, frozen cost), modules/inventory/models.py (Purchase) |
| Excel import | modules/procurement/imports/purchase_import.py |
| Frontend | pages/IssuesPage.jsx, pages/PurchasesPage.jsx, pages/PurchaseDetailPage.jsx, pages/PurchaseImportPage.jsx |

## Suppliers
| Layer | File |
|---|---|
| Route | modules/procurement/api/suppliers.py |
| Schema/Model | modules/inventory/schemas.py / models.py (Supplier) |
| Frontend | pages/SuppliersPage.jsx, pages/SupplierDetailPage.jsx |

## Rate Cards
| Layer | File |
|---|---|
| Route | modules/catalog/api/rate_cards.py, rate_card_imports.py |
| Schema | modules/catalog/schemas.py, modules/catalog/imports/rate_card_schemas.py |
| Model | modules/catalog/models.py |
| Excel import | modules/catalog/imports/rate_card_import.py (two parse functions: market-range layout, standard layout) |
| Frontend | pages/RateCardsPage.jsx, pages/RateCardImportPage.jsx |

## Employees & HR
| Layer | File |
|---|---|
| Route | modules/hr/api/employees.py, attendance.py, leaves.py, salary_slips.py; modules/recruitment/api/candidates.py, interviews.py |
| Schema | modules/hr/schemas.py (employees/attendance/leave/salary/working calendar), modules/recruitment/schemas.py |
| Model | modules/hr/models.py (Employee, Attendance - unique per employee/day, Leave, SalarySlip), modules/recruitment/models.py (Candidate, Interview) |
| Frontend | pages/EmployeesPage.jsx, pages/EmployeeDetailPage.jsx, pages/AttendancePage.jsx, pages/LeavesPage.jsx, pages/CandidatesPage.jsx, pages/CandidateDetailPage.jsx, pages/InterviewsPage.jsx, pages/SalarySlipsPage.jsx |

## Daily Tasks (assignment, completion, handoff)
| Layer | File |
|---|---|
| Route | modules/operations/api/daily_tasks.py - assignment, completion (apply_task_completion), handoff (complete_and_assign_next), status notifications |
| Schema/Model | modules/operations/schemas.py / models.py (DailyTask, TaskComment) |
| Frontend | pages/DailyTasksPage.jsx, pages/TaskDetailPage.jsx |
| Also touches | modules/communications/services/notification_service.py (task notifications), modules/ai/orchestration.py (chatbot task completion - routes through the same apply_task_completion) |

## Production Jobs
| Layer | File |
|---|---|
| Route | modules/operations/api/production_jobs.py |
| Schema/Model | modules/operations/schemas.py / models.py (ProductionJob) |
| Frontend | pages/ProductionJobsPage.jsx, pages/ProductionJobDetailPage.jsx |

## Company Holidays / Working Calendar
| Layer | File |
|---|---|
| Route | modules/hr/api/working_calendar.py, holiday_imports.py |
| Service | modules/hr/working_calendar_service.py |
| Schema | modules/hr/imports/holiday_schemas.py |
| Model | modules/hr/models.py (WorkingCalendarSettings, CompanyHoliday) |
| Excel import | modules/hr/imports/holiday_import.py |
| Frontend | pages/CompanyHolidaysPage.jsx, pages/HolidayImportPage.jsx |

## Chatbot / AI
| Layer | File |
|---|---|
| Route | modules/ai/api/chat.py, agents.py |
| Service | modules/ai/orchestration.py (deterministic parsing), modules/ai/gateway.py (Gemini tool dispatch, kill switch, learning candidates), modules/ai/security.py (text sanitization), modules/ai/agents.py, modules/communications/services/communication_ai_service.py |
| Schema/Model | modules/ai/schemas.py / models.py |
| Frontend | pages/LearningCandidatesPage.jsx, components/ChatWidget.jsx |

## Notifications & Communication
| Layer | File |
|---|---|
| Route | modules/communications/api/notifications.py, communication.py |
| Service | modules/communications/services/notification_service.py (in-app + email, low-stock alerts, visible_to rule), email_service.py (real SMTP), mention_service.py |
| Schema/Model | modules/communications/schemas.py / models.py |

## Reports & Analytics
| Layer | File |
|---|---|
| Route | domain-specific modules/*/api/reports.py files (Excel exports, daily status report + email), modules/reporting/api/analytics.py, dashboard.py |
| Service | modules/reporting/analytics_service.py |
| Model | modules/reporting/models.py (ReportHistory - 15-day retention metadata; AIWorkspaceReport) |
| Frontend | pages/AnalyticsPage.jsx, pages/DashboardPage.jsx |

## Automation & Audit
| Layer | File |
|---|---|
| Route | modules/communications/api/automation.py, api/routes/audit_logs.py, modules/reporting/api/search.py |
| Service | modules/communications/services/automation_service.py |
| Schema/Model | modules/communications/schemas.py / models.py (AutomationLog); platform/audit/audit.py (AuditLog, AuditLogResponse, log_action - the shared audit-logging call every route uses) |
| Frontend | pages/AuditLogsPage.jsx |

## Settings & Personal Cart
| Layer | File |
|---|---|
| Route | api/routes/settings.py, modules/procurement/api/personal_cart.py |
| Schema/Model | schemas/setting.py / models/setting.py (lookup/dropdown tables, no single domain owner - shared across modules); modules/procurement/schemas.py / models.py (PersonalCartItem) |
| Frontend | pages/SettingsPage.jsx |

## Documents & Storage
| Layer | File |
|---|---|
| Route | modules/documents/api/routes.py |
| Core logic | platform/storage/storage.py (LocalStorageBackend, DriveStorageBackend, StorageReference - the storage abstraction every upload uses) |
| Schema/Model | modules/documents/schemas.py / models.py |

## Cross-Cutting (platform/)
| Concern | Where |
|---|---|
| DB engine/session, Base, BaseModel | platform/database/database.py, base.py |
| ID sequence + business-ID generation | platform/database/id_sequence.py, id_generator.py |
| Migration guards + startup migrations | platform/database/migration_guards.py, auto_migrate.py |
| JWT/password/roles | platform/security/security.py |
| Rate limiting | platform/security/rate_limit.py |
| Config/env vars | platform/configuration/config.py |
| Audit log model + log_action | platform/audit/audit.py |
| Storage abstraction | platform/storage/storage.py |
| Security headers + global rate-limit middleware | platform/middleware/middleware.py |

## Cross-Cutting (shared/)
| Concern | Where |
|---|---|
| Excel building (shared by every report/export) | shared/exporters.py |
| Import normalization (dates, numbers, match keys, row-count guard) | shared/import_normalize.py, import_common.py |
| Document styling (PDF header/logo) | shared/document_style.py |
| PDF generation | shared/pdf_generator.py |
| Cross-entity validators | shared/validators.py |

---

## Quick lookup: "the client says X is broken"

| Client's words | Start here |
|---|---|
| "Can't create/assign a task" | Daily Tasks section above |
| "Stock count looks wrong" | Materials & Inventory + Stock Movements sections |
| "Wrong profit/cost showing for an order" | modules/sales/order_service.py profitability() |
| "Duplicate attendance / wrong payroll" | modules/hr/models.py (Attendance) |
| "Email didn't arrive" | modules/communications/services/email_service.py, then the feature's route file for when it calls it |
| "Chatbot picked the wrong person" | modules/ai/orchestration.py _resolve_employee_by_name |
| "Excel import rejected my file" | matching modules/<domain>/imports/<entity>_import.py file |
| "Can't see a client's PDF / wrong data on it" | modules/documents/api/routes.py, platform/storage/storage.py |
| "Report/notification not reaching everyone" | modules/communications/services/notification_service.py, feature's route file |

---

Built by listing the actual files in the repo, not from memory. Update
the relevant section when a file moves, rather than treating this as
permanently accurate.
