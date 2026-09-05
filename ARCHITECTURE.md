# Architecture

backend/app/modules/<domain> - business logic, one folder per domain
backend/app/platform/<concern> - infra (db, security, config, audit, storage, middleware, monitoring)
backend/app/shared/ - genuinely cross-domain, business-neutral helpers (Excel building, import normalization, PDF/document styling, validators)
backend/app/api/routes/ - a few routes with no single domain owner (settings, audit_logs); everything else lives under modules/<domain>/api/

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

Not every module has every file. Only what the domain actually needs.

## Lookup tables (Unit, PaymentMode, ProjectStatus, etc)

No single domain owner - used across inventory/sales/HR. Stays at
models/setting.py and schemas/setting.py. Route: api/routes/settings.py.

## Finding things

See WHERE_IS_THIS.md for a feature -> file map.

## Tests

backend/tests/modules/<domain>/ - matches the modules/<domain>/ layout
backend/tests/security/, tests/platform/, tests/integration/ - cross-cutting
backend/tests/conftest.py, helpers.py - shared fixtures, apply to all subdirs

## Rules

New business logic goes in modules/<domain>, never in a top-level
models/schemas/services/utils folder.

New infra goes in platform/<concern>, not core/ (core/ no longer exists).
