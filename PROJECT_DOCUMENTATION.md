# Woodful Creations — Project Documentation

Business management system for a woodcraft/furniture business: stock & materials, purchases from suppliers, client orders, estimates/quotes, production jobs, HR (employees, attendance, leaves, hiring), payments/expenses, and an AI chat assistant over the whole dataset.

This is the one file to read to understand what the app does, what it's built with, and — when something breaks — which folder/file owns that piece.

---

## 1. Features (by module)

| Module | What it does | Backend route | Frontend page(s) |
|---|---|---|---|
| Auth | Login, session/cookie auth, role-based access | `api/routes/auth.py` | `LoginPage.jsx`, `ProtectedRoute.jsx` |
| Users & roles | Manage internal user accounts | `api/routes/users.py` | `UsersPage.jsx` |
| Clients | Client directory, activity history | `api/routes/clients.py`, `client_activities.py` | `ClientsPage.jsx`, `ClientDetailPage.jsx` |
| Estimates | Quotes/estimates with versioning | `api/routes/estimates.py` | `EstimatesPage.jsx`, `EstimateDetailPage.jsx` |
| Orders | Client orders, status tracking | `api/routes/orders.py` | `OrdersPage.jsx`, `OrderDetailPage.jsx` |
| Materials & stock | Inventory, stock transactions | `api/routes/materials.py`, `services/stock_service.py` | `MaterialsPage.jsx`, `MaterialDetailPage.jsx` |
| Suppliers & purchases | Supplier directory, purchase orders | `api/routes/suppliers.py`, `purchases.py` | `SuppliersPage.jsx`, `SupplierDetailPage.jsx`, `PurchasesPage.jsx` |
| Production jobs | Job tracking through production | `api/routes/production_jobs.py` | `ProductionJobsPage.jsx` |
| Daily tasks / issues | Task assignment, issue tracking | `api/routes/daily_tasks.py`, `issues.py` | `DailyTasksPage.jsx`, `TaskDetailPage.jsx`, `IssuesPage.jsx` |
| Employees | Employee directory | `api/routes/employees.py` | `EmployeesPage.jsx`, `EmployeeDetailPage.jsx` |
| Attendance | Daily attendance tracking | `api/routes/attendance.py` | `AttendancePage.jsx` |
| Leaves | Leave requests/approval | `api/routes/leaves.py` | `LeavesPage.jsx` |
| Hiring | Candidates and interviews | `api/routes/candidates.py`, `interviews.py` | `CandidatesPage.jsx`, `CandidateDetailPage.jsx`, `InterviewsPage.jsx` |
| Salary slips | Payroll slip generation | `api/routes/salary_slips.py` | `SalarySlipsPage.jsx` |
| Payments & expenses | Client payments, project expenses | `api/routes/payments.py`, `project_expenses.py` | `PaymentsPage.jsx`, `ProjectExpensesPage.jsx` |
| Dashboard | KPIs, attention-required summary | `api/routes/dashboard.py` | `DashboardPage.jsx` |
| Global search | Cross-entity search | `api/routes/search.py` | `GlobalSearch.jsx` |
| Chat assistant | AI chatbot over business data | `api/routes/chat.py`, `services/chat_service.py` | `ChatWidget.jsx`, `AssistantMascot.jsx` |
| Reports / exports | PDF & Excel document generation | `api/routes/reports.py`, `utils/pdf_generator.py`, `utils/exporters.py` | (triggered from detail pages) |
| Audit logs | Who-changed-what history | `api/routes/audit_logs.py`, `core/audit.py` | `AuditLogsPage.jsx` |
| Settings | App-wide settings | `api/routes/settings.py` | `SettingsPage.jsx` |

Every entity above uses a short human-readable **business ID** (see `utils/id_generator.py` and Alembic migrations `0005`–`0007`) instead of raw database IDs in the UI/exports.

---

## 2. Tech stack

**Backend** — Python, FastAPI, SQLAlchemy ORM, Alembic migrations (run automatically on startup via `core/auto_migrate.py`), SQLite (local) / PostgreSQL (production), Redis (caching), JWT/cookie auth (`python-jose`, `passlib`+`bcrypt`), PDF generation (`reportlab`), Excel export (`openpyxl`), Word export (`python-docx`), image handling (`pillow`), tests via `pytest`+`httpx`. Full dependency list: `backend/requirements.txt`.

**Frontend** — React 18, React Router, Redux Toolkit (`react-redux`) for auth state, Axios for API calls, `react-scripts` (Create React App) build tooling. Full dependency list: `frontend/package.json`.

**Infra** — Docker (`backend/Dockerfile`, `frontend/Dockerfile`), Docker Compose (`docker-compose.yml`) orchestrating Postgres + Redis + backend + frontend for a production-like run.

---

## 3. Where to fix what (code tree)

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
│   ├── alembic/versions/       Migration files, one per schema change — READ HERE to
│   │                           understand schema history / to add a new migration
│   │
│   ├── app/
│   │   ├── main.py             FastAPI app setup: middleware, CORS, router registration,
│   │   │                       startup migration hook — fix app-wide behavior here
│   │   ├── core/
│   │   │   ├── config.py       Settings/env var loading — fix config/env issues here
│   │   │   ├── database.py     DB session/engine setup — fix DB connection issues here
│   │   │   ├── security.py     Password hashing, token logic — fix auth/security bugs here
│   │   │   ├── middleware.py   Security headers middleware
│   │   │   ├── rate_limit.py   Rate limiting
│   │   │   ├── audit.py        Audit log writing logic
│   │   │   ├── auto_migrate.py Runs Alembic migrations automatically on startup
│   │   │   ├── constants.py    App-wide constants/enums
│   │   │   └── exceptions.py   Custom exception classes / error handling
│   │   │
│   │   ├── models/             SQLAlchemy models — ONE FILE PER ENTITY (client.py, order.py,
│   │   │                       employee.py, etc.) — fix "wrong data in DB" / schema issues here
│   │   │
│   │   ├── schemas/            Pydantic request/response schemas, mirrors models/ —
│   │   │                       fix "API accepts/returns wrong shape" issues here
│   │   │
│   │   ├── api/routes/         One file per feature (see feature table above) — fix
│   │   │                       "wrong behavior on a specific endpoint" here first
│   │   │
│   │   ├── services/           Business logic shared across routes:
│   │   │                       order_service.py, stock_service.py, chat_service.py,
│   │   │                       email_service.py — fix cross-cutting business logic here
│   │   │
│   │   ├── utils/              Helpers: pdf_generator.py, exporters.py (Excel/Word),
│   │   │                       id_generator.py (business IDs), validators.py, helpers.py,
│   │   │                       document_style.py (PDF/Excel branding) — fix export/formatting
│   │   │                       bugs here
│   │   │
│   │   └── assets/logo.png     Logo used in generated PDFs/exports
│   │
│   ├── scripts/                One-off/manual scripts: setup_local.py (bootstrap first
│   │                           admin), create_master_user.py, init_db.py, seed_sample_data.py
│   │
│   ├── tests/                  Pytest suite, roughly one file per feature — run these first
│   │                           after any backend change
│   │
│   ├── logs/                   Runtime log output (empty in repo, gitignored)
│   └── woodful.db              Local SQLite database file (dev only)
│
└── frontend/
    ├── index.html / public/    Static HTML shell, favicon, manifest
    ├── Dockerfile              Frontend container build
    ├── package.json            Node dependencies + npm scripts
    ├── .env.example            Template for frontend/.env
    │
    └── src/
        ├── index.jsx           React entrypoint
        ├── App.jsx             Route definitions — fix "wrong page loads" / routing here
        │
        ├── pages/               One file per screen (see feature table above) — most
        │                        feature bugs are fixed here
        │
        ├── components/          Reusable/shared UI:
        │   ├── Navbar.jsx, Sidebar.jsx, Footer.jsx    App shell/layout
        │   ├── ProtectedRoute.jsx                      Route auth guard
        │   ├── GlobalSearch.jsx                        Search bar
        │   ├── ChatWidget.jsx, AssistantMascot.jsx     Chat assistant UI
        │   ├── QuickActions.jsx, BrandBackdrop.jsx     Dashboard/branding widgets
        │   ├── icons/index.jsx                          Icon set
        │   └── common/          Generic building blocks: Table, Form, Modal, Card,
        │                        Pagination, Alert, KpiCard (+ matching .css files) —
        │                        fix shared UI/styling bugs here, affects many pages
        │
        ├── redux/
        │   ├── store.js                Redux store setup
        │   └── slices/authSlice.js     Auth state — fix "user gets logged out" /
        │                               session state bugs here
        │
        ├── utils/
        │   ├── api.js           Axios instance + API call wrappers — fix "wrong endpoint
        │   │                    called" / request format issues here
        │   ├── currency.js      Currency formatting
        │   ├── dates.js         Date formatting
        │   └── statusColors.js  Status badge color mapping
        │
        └── styles/               Global CSS (index.css, Pages.css, Navbar.css,
                                   LoginPage.css) + styles/components/ (per-component CSS)
```

---

## 4. Quick "where do I look" guide

- **A specific page shows wrong data or behaves wrong** → `frontend/src/pages/<Page>.jsx` first, then the matching `backend/app/api/routes/<feature>.py`.
- **API returns wrong data or errors** → route file in `api/routes/` → then `services/` if it's business logic → then `models/`/`schemas/` if it's a data-shape issue.
- **Login/session/permissions broken** → `core/security.py`, `api/routes/auth.py` (backend); `redux/slices/authSlice.js`, `ProtectedRoute.jsx` (frontend).
- **Database schema needs to change** → add a new file in `backend/alembic/versions/`, update the matching model in `app/models/`.
- **PDF/Excel export looks wrong** → `backend/app/utils/pdf_generator.py`, `exporters.py`, `document_style.py`.
- **A shared UI element (table, form, modal) looks/behaves wrong everywhere** → `frontend/src/components/common/`.
- **Setup/install fails** → `SETUP.md`, `setup.sh`/`setup.bat`, `backend/requirements.txt`, `frontend/package.json`.
- **App won't start / migration errors** → `backend/app/core/auto_migrate.py`, `backend/alembic/versions/` (check latest migration matches latest model changes).
