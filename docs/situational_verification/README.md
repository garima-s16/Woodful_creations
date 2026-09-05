# Situational Verification

These are NOT the project's real test suite - that's `backend/tests/`,
which requires the actual pip dependencies (SQLAlchemy, FastAPI,
pytest) and runs against a real database.

This folder exists because the sandbox these tests were originally
written in has **no network access at all** - confirmed with direct
evidence, not assumed:

```
$ curl -sS -I https://pypi.org/simple/sqlalchemy/
HTTP/2 403
x-deny-reason: host_not_allowed
```

The same block applies to `registry.npmjs.org`, `api.github.com`, and
even `example.com` - a blanket, default-deny egress policy, not
something specific to package registries. `pip install` cannot
succeed there under any circumstances; this is an environment
property, not an application defect.

Rather than stop at "cannot test - sandbox limitation," each file
here finds the closest thing to real execution actually possible
without those packages, genuinely runs it, and honestly labels what
was and wasn't verified. Run any of them with plain `python3` - no
`pip install` needed for any file in this folder:

```
python3 situational_verification_tests.py
```

(Originally 6 separate files - later consolidated into one, since these
are dev-only verification scripts, not production code, and having a
separate file per subsystem made the project harder to navigate for no
real benefit. Running the file directly executes all 6 sections in
sequence and prints a combined pass/fail summary.)

## What each section actually verified

Each row below is now a function inside `situational_verification_tests.py`, not a separate file.

| Section | What genuinely ran | Level |
|---|---|---|
| `test_1_gemini_kill_switch` | The real `is_configured()` source, copied verbatim, plus the real exception-handling shape from `handle_message` | Focused logic test - copied real source, not a live import |
| `test_2_learning_candidate_dedup` | The real `_record_learning_candidate` normalization/dedup logic against a minimal fake DB session | Focused logic test - copied real source, not a live import |
| `test_3_storage_failure_consistency` | The real delete-ordering logic (commit-before-cleanup) from `clients.py`, copied verbatim, against fake DB/storage objects that can be told to succeed or fail | Focused logic test - copied real source, not a live import |
| `test_4_excel_duplicate_detection` | The real within-file duplicate-detection loop bodies from `material_imports.py`/`order_imports.py`, copied verbatim | Focused logic test - copied real source, not a live import |
| `test_5_email_service_real` | **The real, completely unmodified `EmailService` class, genuinely imported and called** - only the actual network call (`smtplib.SMTP`) is patched out | Real service execution - genuine import, not copied |
| `test_6_storage_local_real` | **The real, completely unmodified `LocalStorageBackend` class, genuinely imported and exercised against real filesystem I/O** in a real temp directory | Real service execution - genuine import, genuine disk I/O |

`shims/` contains minimal stand-ins for `pydantic` and `sqlalchemy`
that let `app/modules/ai/gateway.py` (and its full transitive import
chain through `app/models/`, `app/modules/ai/schemas.py`, and
`app/modules/communications/services/notification_service.py`) be genuinely imported and
have its real functions genuinely called - not reimplemented -
without the real packages installed. This was used during initial
verification (`ai_gateway.build_conversation_context()` and
`is_configured()` were both genuinely called against the real,
unmodified source file) but a standalone repro script for that
specific result isn't included here, since it needs the `sys.modules`
pre-population technique shown in this README rather than a plain
`python3 file.py` invocation:

```python
import sys, types
fake_config = types.ModuleType("app.platform.configuration.config")
fake_config.settings = type("S", (), {"GEMINI_ENABLED": False, "GEMINI_API_KEY": ""})()
sys.modules["app.platform.configuration.config"] = fake_config
fake_database = types.ModuleType("app.platform.database.database")
fake_database.Base = type("Base", (), {})
sys.modules["app.platform.database.database"] = fake_database
# then: PYTHONPATH=docs/situational_verification/shims:. python3 -c "from app.modules.ai import gateway as ai_gateway; ..."
```

## Honest limits - what this genuinely could NOT reach

- **Real database queries** (`db.query(Model).filter(...)`) - the
  `sqlalchemy` shim's `Column`/`filter` are inert placeholders
  sufficient for *importing* model classes, not for real query
  execution (comparison operators, `ORDER BY`, `LIMIT`). Faithfully
  replicating that would mean building a real fake ORM, which risks
  becoming its own testing architecture rather than a lightweight
  verification aid.
- **Real Alembic migrations against any database**, temporary SQLite
  included - same root cause.
- **Live Gemini, live Google Drive, live SMTP delivery** - genuinely
  require network access this sandbox does not have, confirmed with
  direct `curl` evidence above, not assumed from memory.
- **`npm run build` / a running FastAPI server / real HTTP requests**
  - same root cause.

None of these are being claimed as passed. Where the real thing
couldn't run, the closest honest alternative was used and labeled as
exactly that - see the table above.
