# Production Readiness — Woodful Creations

Last reviewed: this session, against the codebase as it currently stands.
Every item below is either directly verified against real files/config in
this repo, or explicitly marked NOT VERIFIED. Nothing here is assumed.

Target deployment (per Family 17): Domain via GoDaddy, frontend on
production hosting, backend/API on Azure/GCP, a managed database, files
in object storage, a production email service, mobile via App Store +
Google Play.

## Environment configuration — READY, with action required at deploy time

- `ENVIRONMENT`, `DEBUG`, `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`,
  `COOKIE_SECURE`, `COOKIE_SAMESITE` are all environment-variable driven
  (`app/core/config.py`) — no hardcoded production values to change in code.
- `SECRET_KEY` has a startup validator rejecting anything under 32 chars or
  a known placeholder string (`config.py`, `SECRET_KEY` validator).
- **A real safeguard added this session**: a cross-field validator now
  rejects `DEBUG=True` when `ENVIRONMENT=production` at startup — this
  used to be possible (the `.env.example` template itself defaults to
  `DEBUG=True`) and would have leaked full stack tracebacks in HTTP error
  responses if carried into production unchanged.
- Action required: `CORS_ORIGINS` defaults to `http://localhost:3000` and
  must be set to the real production frontend origin(s) before deploy.

## Secrets — VERIFIED, one item explicitly not verifiable here

- Searched the full codebase (backend, frontend, tests, seed data,
  scripts, config, docs) for hardcoded API keys, tokens, passwords, and
  credentials — none found in source.
- Confirmed the only frontend env var (`REACT_APP_API_URL`) is a public
  URL, never a server-side secret.
- **NOT VERIFIED — no Git history exists in this working copy** (no
  `.git` directory), so history scanning for a secret that was committed
  and later removed could not be performed. If this codebase has real
  Git history elsewhere, that history has not been scanned.

## Dependency vulnerabilities — NOT VERIFIED, requires network access

- `pip-audit`/`npm audit` could not run in this environment (no network).
- Manifests were read (`requirements.txt`, `package.json`) — versions are
  reasonably current at a glance, but this is not a substitute for a real
  audit and no CVE claims are made here.
- **Action required before production**: run `audit_dependencies.sh` (or
  `.bat`) from a network-enabled environment, and review/update anything
  it flags. Do not deploy on the strength of the manual read above alone.

## Rate limiting — READY for single-instance, action required for multi-instance

- A shared abstraction exists (`app/core/rate_limit.py`) with both an
  in-memory backend (default, works with zero setup for local dev) and a
  Redis-backed backend, switched via `RATE_LIMIT_BACKEND=memory|redis`.
- A global default floor applies to every request via middleware, on top
  of tighter, purpose-specific limits already in place for login,
  password reset, chat, and exports.
- **Action required**: the in-memory backend does not share state across
  processes/instances. Any multi-instance production deployment (more
  than one backend process/container) must set `RATE_LIMIT_BACKEND=redis`
  and provision a real Redis instance, or rate limits will be enforced
  per-instance rather than globally — under-limiting in aggregate.
- Not yet implemented: per-account limiting (only per-IP exists today)
  and exponential backoff on repeated auth failures.

## File storage — ABSTRACTION IMPLEMENTED IN CODE; cloud backend REQUIRES PRODUCTION INFRASTRUCTURE

- **Corrected from an earlier version of this document**, which stated
  every upload endpoint wrote directly to local disk. That has since
  been fixed: all four upload routes (`documents.py`, `clients.py`,
  `payments.py`, `candidates.py`) now go through a storage abstraction
  (`app/core/storage.py`, `StorageBackend`/`get_storage_backend()`) with
  `save`/`read`/`exists`/`delete` - no route calls `open()`/`os.remove()`
  directly anymore.
- **IMPLEMENTED IN CODE**: `LocalStorageBackend`, selected via
  `STORAGE_PROVIDER=local` (the default). Preserves the exact prior
  on-disk layout and every existing validation/authorization/IDOR
  behavior - confirmed by tests re-run against all four routes after
  the migration.
- **REQUIRES PRODUCTION INFRASTRUCTURE**: no real cloud backend (S3-
  compatible / Azure Blob / GCS) is implemented in this build - only the
  local one. `get_storage_backend()` raises clearly for any
  `STORAGE_PROVIDER` value other than `local`, rather than silently
  falling back to local storage under a different provider's name.
- **Must be done before production**: implement a concrete
  `StorageBackend` subclass for the actual chosen provider (using its
  SDK) and select it via `STORAGE_PROVIDER` in production configuration.
  No route/business logic needs to change - that is the entire point of
  the abstraction now in place.
- **NOT RUNTIME VERIFIED**: the abstraction has not been tested against
  a real cloud backend, since none is implemented - only the local
  backend has actually run.

## Database & migrations — READY

- Alembic migrations are the only mechanism used for schema changes (45
  migrations as of this session), applied automatically on backend
  startup (`app/core/auto_migrate.py`).
- `DATABASE_URL` is environment-driven — pointing it at a managed
  production database (RDS, Cloud SQL, Azure Database) requires no code
  change.
- Action required: verify migrations run cleanly against the actual
  target database engine before first production deploy (this session's
  verification has been against the dev database only).

## Error handling & logging — READY

- Verified zero broad `except Exception` handlers in any route file that
  might re-serialize internal error details back to the client.
- Audit logging (`app/core/audit.py`) exists and is applied across
  create/update/delete for every sensitive module checked this session.
- **NOT VERIFIED**: no dedicated production monitoring/alerting
  (e.g. Sentry, CloudWatch, Azure Monitor) is wired up. Server-side
  `print`/logging exists but has not been evaluated for production log
  aggregation.

## Backups

- **NOT VERIFIED / NOT CONFIGURED**: no backup strategy exists in this
  codebase — this is entirely a function of the managed database
  provider chosen at deploy time (automated snapshots, point-in-time
  recovery), not application code. Must be configured at the
  infrastructure level before production.

## Frontend/backend separation — READY

- Clean separation already exists: `REACT_APP_API_URL` is the only
  coupling point, and the backend has no assumption about how or where
  the frontend is served.

## Mobile (App Store / Play Store) — NOT APPLICABLE YET

- No native mobile app exists in this codebase — the "mobile readiness"
  work done this session (Family 16) is responsive web only. Store
  compliance cannot be claimed because no store submission exists to
  validate against. This is correctly out of scope until a mobile app is
  actually built.

## External access portal (Family 18)

- Not built. No client/supplier-facing portal exists. Per Family 18's
  own instruction ("do not create this portal unless the workflow
  provides genuine value"), and with no established business need
  identified for it, this was deliberately not built rather than
  speculatively added.

---

## Summary — must be done before production

1. **File storage** — the abstraction is implemented; implement a real
   cloud `StorageBackend` (S3-compatible/Azure Blob/GCS) and set
   `STORAGE_PROVIDER` before production. No route changes needed.
2. **Dependency audit** (blocker) — run a real `pip-audit`/`npm audit`
   from a network-enabled environment; nothing has been scanned yet.
3. **Redis rate limiting** — provision Redis and set
   `RATE_LIMIT_BACKEND=redis` if deploying more than one backend
   instance.
4. **CORS_ORIGINS** — set to the real production frontend origin(s).
5. Verify migrations against the actual target database engine.
6. Configure infrastructure-level backups (provider-dependent, not
   application code).
7. Wire up production monitoring/log aggregation (not evaluated here).

Everything else reviewed above is genuinely ready as-is.
