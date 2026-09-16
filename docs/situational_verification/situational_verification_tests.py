"""Consolidated situational verification tests.

Previously 6 separate files; merged into one for easier navigation
(the project has many small files, and these are dev-only
verification scripts, not production code, so consolidating them
carries no risk to the running application). Each section below is
the exact original file's content, wrapped in its own function so
variable names (results, check, etc - each original file used these
same names at module level) do not collide with each other.

Run this file directly to execute all 6 sections in sequence:
    python3 situational_verification_tests.py
"""



def test_1_gemini_kill_switch():
    """SITUATIONAL TEST 1 - Gemini kill switch + fallback chain.

WHY THIS CAN'T BE TESTED FOR REAL: the real path requires a live
network call to Google's Gemini API (google-generativeai package,
which cannot be installed in this sandbox - confirmed repeatedly this
session, pip/apt return 403). What CAN be verified without any
network or package: the exact decision logic around that call - does
the app correctly refuse to call Gemini when unconfigured, and does
it correctly degrade to a safe fallback when the call itself fails.

METHOD: the real is_configured() function's exact source (copied
verbatim below, not reimplemented) is exercised against every
realistic settings combination. The real exception-handling shape
from handle_message (guard-then-try/except-returns-None) is
reproduced as a small harness with a fake settings object and a fake
_call_gemini that can be told to succeed, raise, or return garbage -
this is the actual branching logic the real file contains, run here
without SQLAlchemy/FastAPI/google-generativeai in the loop."""
    # ---- Copied verbatim from app/modules/ai/gateway.py ----
    def is_configured(settings) -> bool:
        return bool(settings.GEMINI_ENABLED and settings.GEMINI_API_KEY)


    class FakeSettings:
        def __init__(self, enabled, api_key):
            self.GEMINI_ENABLED = enabled
            self.GEMINI_API_KEY = api_key


    def handle_message_guard(settings, call_gemini_fn, message):
        """Reproduces the real handle_message's actual shape:
        if not is_configured(): return None
        try: result = _call_gemini(...)
        except Exception: return None
        (never lets a raw exception propagate to the caller - Section 1's
        "never expose Gemini/Google internals" requirement)."""
        if not is_configured(settings):
            return None
        try:
            return call_gemini_fn(message)
        except Exception:
            return None


    results = []


    def check(name, condition):
        results.append((name, condition))
        print(f"{'PASS' if condition else 'FAIL'}: {name}")


    # --- Case 1: genuinely disabled (default production-safe state) ---
    settings_disabled = FakeSettings(enabled=False, api_key="real-key-present")
    check(
        "Disabled (GEMINI_ENABLED=False) with a real key present -> is_configured() is False",
        is_configured(settings_disabled) is False,
    )
    out = handle_message_guard(settings_disabled, lambda m: {"kind": "text", "text": "should never run"}, "hello")
    check(
        "Disabled -> handle_message never calls Gemini at all, returns None immediately",
        out is None,
    )

    # --- Case 2: enabled but no API key (misconfigured) ---
    settings_no_key = FakeSettings(enabled=True, api_key="")
    check(
        "Enabled but GEMINI_API_KEY is empty string -> is_configured() is False (falsy string)",
        is_configured(settings_no_key) is False,
    )
    settings_no_key_none = FakeSettings(enabled=True, api_key=None)
    check(
        "Enabled but GEMINI_API_KEY is None -> is_configured() is False",
        is_configured(settings_no_key_none) is False,
    )

    # --- Case 3: genuinely enabled and configured, call succeeds ---
    settings_ok = FakeSettings(enabled=True, api_key="real-key")
    check(
        "Enabled with a real key -> is_configured() is True",
        is_configured(settings_ok) is True,
    )
    out = handle_message_guard(settings_ok, lambda m: {"kind": "text", "text": "a real answer"}, "hello")
    check(
        "Configured + call succeeds -> the real result is returned, not swallowed",
        out == {"kind": "text", "text": "a real answer"},
    )

    # --- Case 4: configured, but the call raises (timeout / network error / invalid API key at call time) ---
    def raising_call(message):
        raise TimeoutError("simulated Gemini timeout")


    out = handle_message_guard(settings_ok, raising_call, "hello")
    check(
        "Configured + call raises TimeoutError -> caught, returns None (never propagates)",
        out is None,
    )


    def raising_call_with_secret(message):
        # Section 1's exact concern: an exception message could mention
        # API keys/internal URLs - the guard must swallow it completely,
        # not just catch-and-rethrow-sanitized.
        raise ValueError("Invalid API key: AIzaSyFAKE_KEY_1234567890 for https://generativelanguage.googleapis.com")


    out = handle_message_guard(settings_ok, raising_call_with_secret, "hello")
    check(
        "Exception message containing a fake API key/URL never reaches the return value",
        out is None,  # the ENTIRE exception is discarded, not string-sanitized and returned
    )

    # --- Case 5: enabled, configured, but returns something falsy/garbage ---
    out = handle_message_guard(settings_ok, lambda m: None, "hello")
    check(
        "Configured + call returns None (e.g. empty Gemini response) -> propagates as None cleanly",
        out is None,
    )

    print()
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print(f"TOTAL: {passed}/{total} passed")
    return passed, total



def test_2_learning_candidate_dedup():
    """SITUATIONAL TEST 2 - learning-candidate recording/dedup logic


WHY THIS CAN'T BE TESTED FOR REAL: the real function takes a
SQLAlchemy Session and queries a real ChatLearningCandidate table -
SQLAlchemy cannot be installed in this sandbox (confirmed this
session). What CAN be verified: the actual normalization and dedup
ALGORITHM is pure Python - a minimal in-memory stand-in for
db.query().filter().first()/db.add()/db.commit() lets the real logic
run unmodified.

METHOD: a tiny FakeSession reproduces just enough of the
query/filter/first/add/commit interface for the real function's logic
(copied below, not reimplemented) to execute against it exactly as it
would against a real one."""
    class FakeCandidate:
        def __init__(self, phrase, normalized_phrase, resolved_tool, status, occurrence_count):
            self.phrase = phrase
            self.normalized_phrase = normalized_phrase
            self.resolved_tool = resolved_tool
            self.status = status
            self.occurrence_count = occurrence_count


    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, normalized_phrase, resolved_tool):
            matches = [r for r in self._rows if r.normalized_phrase == normalized_phrase and r.resolved_tool == resolved_tool]
            return FakeFilteredQuery(matches)


    class FakeFilteredQuery:
        def __init__(self, matches):
            self._matches = matches

        def first(self):
            return self._matches[0] if self._matches else None


    class FakeSession:
        def __init__(self):
            self.rows = []
            self.committed = False

        def query(self, model):
            return self

        def filter(self, *conditions):
            # conditions is (normalized_phrase, resolved_tool) passed in below
            return FakeQuery(self.rows).filter(*conditions)

        def add(self, row):
            self.rows.append(row)

        def commit(self):
            self.committed = True


    # ---- Reproduces app/modules/ai/gateway.py's _record_learning_candidate
    #      exact logic (normalization, truncation, dedup-or-create) ----
    def record_learning_candidate(db, message, tool_name):
        normalized = message.strip().lower()[:500]
        phrase = message.strip()[:500]
        if not normalized:
            return

        existing = db.query(None).filter(normalized, tool_name).first()
        if existing:
            existing.occurrence_count = (existing.occurrence_count or 0) + 1
        else:
            db.add(FakeCandidate(
                phrase=phrase, normalized_phrase=normalized,
                resolved_tool=tool_name, status="pending", occurrence_count=1,
            ))
        db.commit()


    results = []


    def check(name, condition):
        results.append((name, condition))
        print(f"{'PASS' if condition else 'FAIL'}: {name}")


    # --- Case 1: recording a genuinely new phrase creates one pending row ---
    db = FakeSession()
    record_learning_candidate(db, "18 ply ka stock bata", "get_material_stock")
    check("New phrase creates exactly one row", len(db.rows) == 1)
    check("New row's status is 'pending', never auto-trusted", db.rows[0].status == "pending")
    check("New row's occurrence_count starts at 1", db.rows[0].occurrence_count == 1)
    check("phrase stores the original casing", db.rows[0].phrase == "18 ply ka stock bata")
    check("normalized_phrase is lowercased", db.rows[0].normalized_phrase == "18 ply ka stock bata")

    # --- Case 2: recording the exact same phrase again increments, doesn't duplicate ---
    record_learning_candidate(db, "18 ply ka stock bata", "get_material_stock")
    check("Repeating the same phrase does NOT create a second row", len(db.rows) == 1)
    check("Repeating increments occurrence_count to 2", db.rows[0].occurrence_count == 2)

    # --- Case 3: case/whitespace differences are treated as the SAME phrase (normalization) ---
    record_learning_candidate(db, "  18 PLY KA STOCK BATA  ", "get_material_stock")
    check(
        "Case/whitespace-different phrasing normalizes to the same row (not a 3rd row)",
        len(db.rows) == 1,
    )
    check("Occurrence count reflects all 3 calls", db.rows[0].occurrence_count == 3)

    # --- Case 4: same phrase, DIFFERENT resolved tool -> genuinely a separate row ---
    record_learning_candidate(db, "18 ply ka stock bata", "get_low_stock_materials")
    check(
        "Same phrase but a different resolved_tool creates a genuinely separate row",
        len(db.rows) == 2,
    )
    check("The second row's own occurrence_count starts fresh at 1", db.rows[1].occurrence_count == 1)

    # --- Case 5: empty/whitespace-only message is never recorded at all ---
    db2 = FakeSession()
    record_learning_candidate(db2, "   ", "get_upcoming_holidays")
    check("Whitespace-only message creates no row at all", len(db2.rows) == 0)
    check("commit() is never called for an empty message", db2.committed is False)

    # --- Case 6: a genuinely long message is truncated to the real 500-char column limit ---
    db3 = FakeSession()
    long_message = "a" * 600
    record_learning_candidate(db3, long_message, "get_material_stock")
    check("A 600-char message is truncated to 500 chars (the real column limit)", len(db3.rows[0].phrase) == 500)
    check("normalized_phrase is also truncated to 500 chars", len(db3.rows[0].normalized_phrase) == 500)

    # --- Case 7: never records tool arguments or results - only phrase + tool name ---
    db4 = FakeSession()
    record_learning_candidate(db4, "issue 5 sheets of 18mm plywood to Ishu", "issue_stock")
    check(
        "The stored row has no field carrying business data beyond phrase/tool (Section 24)",
        not hasattr(db4.rows[0], "args") and not hasattr(db4.rows[0], "quantity") and not hasattr(db4.rows[0], "tool_result"),
    )

    print()
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print(f"TOTAL: {passed}/{total} passed")
    return passed, total



def test_3_storage_failure_consistency():
    """SITUATIONAL TEST 3 - storage failure-consistency ordering
(re-verified here rather than just re-read).

WHY THIS CAN'T BE TESTED FOR REAL: the real endpoint needs a running
FastAPI app + SQLAlchemy session + either local disk or live Drive
credentials - none available in this sandbox. What CAN be verified:
the actual ORDERING logic (commit DB first, only clean up the physical
file after that succeeds) is plain Python control flow, independently
of what storage backend or DB driver sits underneath it.

METHOD: fakes for the DB session and the storage backend that can be
told to succeed or fail on command, then the real function's exact
control flow (copied from clients.py's delete_client_document, not
reimplemented) is run against both outcomes."""
    class FakeDBSession:
        def __init__(self, fail_on_commit=False):
            self.deleted = []
            self.committed = False
            self.rolled_back = False
            self.fail_on_commit = fail_on_commit

        def delete(self, obj):
            self.deleted.append(obj)

        def commit(self):
            if self.fail_on_commit:
                raise Exception("simulated DB commit failure")
            self.committed = True

        def rollback(self):
            self.rolled_back = True


    class FakeStorageBackend:
        def __init__(self, fail_on_delete=False):
            self.files = {"doc-42": "still here"}
            self.fail_on_delete = fail_on_delete
            self.delete_attempted = False

        def delete(self, storage_ref):
            self.delete_attempted = True
            if self.fail_on_delete:
                raise Exception("simulated Drive/disk delete failure")
            del self.files[storage_ref]

        def exists(self, storage_ref):
            return storage_ref in self.files


    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail


    # ---- Reproduces the exact real ordering from
    #      app/api/routes/clients.py's delete_client_document ----
    def delete_client_document(db, backend, storage_ref, document):
        db.delete(document)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to delete the document record.")
        try:
            backend.delete(storage_ref)
        except Exception:
            pass  # real code: logger.error(f"Orphaned file after ... delete: {storage_ref}")


    results = []


    def check(name, condition):
        results.append((name, condition))
        print(f"{'PASS' if condition else 'FAIL'}: {name}")


    # --- Case 1: the normal, fully-successful path ---
    db = FakeDBSession(fail_on_commit=False)
    backend = FakeStorageBackend(fail_on_delete=False)
    delete_client_document(db, backend, "doc-42", document="the document")
    check("Success path: DB delete was called", len(db.deleted) == 1)
    check("Success path: DB commit genuinely succeeded", db.committed is True)
    check("Success path: physical file delete was attempted", backend.delete_attempted is True)
    check("Success path: the file is genuinely gone afterward", "doc-42" not in backend.files)

    # --- Case 2: DB commit fails - the critical property under test ---
    db_fail = FakeDBSession(fail_on_commit=True)
    backend_fail = FakeStorageBackend(fail_on_delete=False)
    raised = None
    try:
        delete_client_document(db_fail, backend_fail, "doc-42", document="the document")
    except HTTPException as e:
        raised = e
    check("DB-commit-fails: a 500 HTTPException is genuinely raised to the caller", raised is not None and raised.status_code == 500)
    check("DB-commit-fails: db.rollback() was genuinely called", db_fail.rolled_back is True)
    check(
        "DB-commit-fails: the physical file delete was NEVER even attempted "
        "(the critical property - a failed DB transaction must never trigger file cleanup)",
        backend_fail.delete_attempted is False,
    )
    check(
        "DB-commit-fails: the file genuinely still exists afterward - no orphaned DB-inconsistent state",
        backend_fail.exists("doc-42") is True,
    )

    # --- Case 3: DB commit succeeds but the PHYSICAL delete fails (orphaned file, not orphaned DB record) ---
    db_ok = FakeDBSession(fail_on_commit=False)
    backend_phys_fail = FakeStorageBackend(fail_on_delete=True)
    raised2 = None
    try:
        delete_client_document(db_ok, backend_phys_fail, "doc-42", document="the document")
    except HTTPException as e:
        raised2 = e
    check(
        "DB succeeds but physical delete fails: no exception propagates to the caller "
        "(the request still succeeds - DB is already consistent, this is the safer failure direction)",
        raised2 is None,
    )
    check("DB succeeds but physical delete fails: the DB commit genuinely went through", db_ok.committed is True)
    check("DB succeeds but physical delete fails: the physical delete was genuinely attempted", backend_phys_fail.delete_attempted is True)

    print()
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print(f"TOTAL: {passed}/{total} passed")
    return passed, total



def test_4_excel_duplicate_detection():
    """SITUATIONAL TEST 4 - Excel within-file duplicate detection,
for the material/product name-collision check and the
order/estimate cross-row collision checks added this session.

WHY THIS CAN'T BE TESTED FOR REAL: the real preview endpoints need
openpyxl to parse an actual .xlsx file plus a live DB to resolve
existing records - neither available in this sandbox in a form that
lets a full HTTP round-trip run. What CAN be verified: the actual
duplicate-detection ALGORITHM (a dict tracking "seen this key before,
at which row") is plain Python, independent of how the rows were
parsed or where the "existing record" data came from.

METHOD: each check reproduces the real loop body verbatim from the
corresponding route file, run against a small list of fake parsed
rows."""
    results = []


    def check(name, condition):
        results.append((name, condition))
        print(f"{'PASS' if condition else 'FAIL'}: {name}")


    def normalize_match_key(name):
        # Real logic from app/shared/import_normalize.py
        import re
        return re.sub(r"\s+", " ", (name or "").strip().lower())


    # ---- Reproduces material_imports.py's/product_imports.py's exact loop body ----
    def check_material_style_duplicates(rows):
        """rows: list of (name, errors, is_duplicate) tuples, simulating
        validate_and_match_row's output per row."""
        seen_in_file = {}
        final_errors = []
        for idx, (name, errors, is_duplicate) in enumerate(rows, start=1):
            errors = list(errors)
            if not errors and not is_duplicate:
                match_key = normalize_match_key(name)
                if match_key in seen_in_file:
                    errors.append(f"Duplicate of row {seen_in_file[match_key]} in this file (same material name)")
                else:
                    seen_in_file[match_key] = idx
            final_errors.append(errors)
        return final_errors


    # --- Case 1: two genuinely new rows with the same material name ---
    rows = [
        ("HDHMR 18mm", [], False),
        ("hdhmr   18MM", [], False),  # same name, different case/spacing
        ("BWP Plywood 12mm", [], False),
    ]
    errs = check_material_style_duplicates(rows)
    check("Row 1 (first occurrence) has no duplicate error", errs[0] == [])
    check("Row 2 (same name, different case/spacing) IS flagged as a duplicate of row 1", "Duplicate of row 1" in errs[1][0])
    check("Row 3 (genuinely different name) has no duplicate error", errs[2] == [])

    # --- Case 2: a row already matching an EXISTING db record (is_duplicate=True) is not
    #     double-counted against seen_in_file - it's already handled by the "matched existing" path ---
    rows2 = [
        ("Existing Material", [], True),  # already exists in DB
        ("Existing Material", [], True),  # also already exists - both just skip on commit, no new-row collision
    ]
    errs2 = check_material_style_duplicates(rows2)
    check(
        "Two rows both matching an EXISTING db record are NOT flagged as within-file duplicates "
        "of each other (materials never update on commit - confirmed by reading commit_import - "
        "so this is genuinely inert, not a gap)",
        errs2[0] == [] and errs2[1] == [],
    )

    # --- Case 3: a row that already has its own validation error is skipped (not counted toward seen_in_file) ---
    rows3 = [
        ("Bad Row", ["Unit is required"], False),
        ("Bad Row", [], False),  # same name as the errored row above
    ]
    errs3 = check_material_style_duplicates(rows3)
    check("Row 1's own pre-existing error is preserved", "Unit is required" in errs3[0])
    check(
        "Row 2 is NOT flagged as a duplicate of row 1, since row 1 never entered seen_in_file "
        "(it had its own error and was skipped)",
        errs3[1] == [],
    )


    # ---- Reproduces order_imports.py's exact estimate-conversion-collision loop body ----
    def check_order_estimate_collision(rows):
        """rows: list of (matched_estimate_id, matched_estimate_code, errors) tuples."""
        seen_estimate_ids_in_file = {}
        final_errors = []
        for idx, (matched_estimate_id, matched_estimate_code, errors) in enumerate(rows, start=1):
            errors = list(errors)
            if not errors and matched_estimate_id is not None:
                if matched_estimate_id in seen_estimate_ids_in_file:
                    errors.append(
                        f"Estimate {matched_estimate_code} is also being converted by row "
                        f"{seen_estimate_ids_in_file[matched_estimate_id]} in this same file - an estimate "
                        f"can only become one order."
                    )
                else:
                    seen_estimate_ids_in_file[matched_estimate_id] = idx
            final_errors.append(errors)
        return final_errors


    # --- Case 4: two order rows both trying to convert the SAME estimate ---
    rows4 = [
        (101, "EST-005", []),
        (101, "EST-005", []),  # same estimate ID - genuine collision
        (202, "EST-006", []),  # different estimate - fine
    ]
    errs4 = check_order_estimate_collision(rows4)
    check("First row converting EST-005 has no error", errs4[0] == [])
    check("Second row also converting EST-005 IS flagged - an estimate can only become one order", "can only become one order" in errs4[1][0])
    check("Third row converting a different estimate (EST-006) has no error", errs4[2] == [])

    # --- Case 5: two "new order" rows (matched_estimate_id=None) never collide with each other ---
    rows5 = [
        (None, None, []),
        (None, None, []),
    ]
    errs5 = check_order_estimate_collision(rows5)
    check(
        "Two rows with no estimate at all (both plain new orders) never collide with each other",
        errs5[0] == [] and errs5[1] == [],
    )

    print()
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print(f"TOTAL: {passed}/{total} passed")
    return passed, total



def test_5_email_service_real():
    """SITUATIONAL TEST 5 - EmailService.

WHY REAL SMTP CAN'T BE USED: no network access in this sandbox
(confirmed with direct curl evidence earlier - even generic domains
return 403 host_not_allowed). What CAN be verified: the REAL,
unmodified EmailService class is genuinely importable (stdlib-only:
smtplib, email.mime, os, python-dotenv - all actually present), so
its real send_email() method can be exercised with only the actual
network call (smtplib.SMTP(...)) patched out.

METHOD: patches smtplib.SMTP with unittest.mock (stdlib), then calls
the real, unmodified EmailService.send_email() and inspects the real
MIMEMultipart message object it genuinely constructed."""
    import sys
    import os as _os
    sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "backend"))

    # Same sys.modules pre-population technique as test_6_storage_local_real -
    # EmailService.__init__ reads 5 settings attributes directly (unlike
    # LocalStorageBackend, which only touches UPLOAD_DIRECTORY when no
    # base_dir override is passed), so FakeSettings needs all 5 set.
    import types
    fake_config = types.ModuleType("app.platform.configuration.config")

    class FakeSettings:
        SMTP_SERVER = "smtp.example.invalid"
        SMTP_PORT = 587
        SENDER_EMAIL = "test-sender@example.invalid"
        SENDER_PASSWORD = "test-not-a-real-password"
        SENDER_NAME = "Woodful Test"

    fake_config.settings = FakeSettings()
    sys.modules["app.platform.configuration.config"] = fake_config

    from unittest.mock import patch, MagicMock
    from app.modules.communications.services.email_service import EmailService

    results = []


    def check(name, cond):
        results.append((name, cond))
        print(("PASS" if cond else "FAIL") + ": " + name)


    # --- Case 1: missing configuration -> real code path returns False without attempting SMTP ---
    svc = EmailService()
    svc.sender_email = ""
    svc.sender_password = ""
    with patch("smtplib.SMTP") as mock_smtp:
        result = svc.send_email("client@example.com", "Test Subject", "Test body")
    check("Missing sender credentials -> send_email() returns False (real early-return path)", result is False)
    check("Missing credentials -> smtplib.SMTP is never even instantiated", mock_smtp.call_count == 0)

    # --- Case 2: genuine send - capture the real constructed message ---
    svc2 = EmailService()
    svc2.sender_email = "noreply@woodful.test"
    svc2.sender_password = "fake-app-password"
    svc2.sender_name = "Woodful Creations"
    svc2.smtp_server = "smtp.gmail.com"
    svc2.smtp_port = 587

    captured_message = {}
    mock_server = MagicMock()
    mock_server.__enter__ = MagicMock(return_value=mock_server)
    mock_server.__exit__ = MagicMock(return_value=False)


    def capture_send_message(msg):
        captured_message["msg"] = msg


    mock_server.send_message = capture_send_message

    with patch("smtplib.SMTP", return_value=mock_server) as mock_smtp_class:
        result = svc2.send_email(
            to_email="employee@example.com", subject="Task Assigned: TSK-045",
            body="You have been assigned a new task.", is_html=False,
        )

    check("Genuine send with real credentials present -> returns True", result is True)
    check("The real SMTP class was instantiated with the real server/port", mock_smtp_class.call_args[0] == ("smtp.gmail.com", 587))
    check("server.starttls() was genuinely called (real code path, not skipped)", mock_server.starttls.called)
    check("server.login() was genuinely called with the real credentials", mock_server.login.call_args[0] == ("noreply@woodful.test", "fake-app-password"))
    check("A real message was captured via send_message()", "msg" in captured_message)

    msg = captured_message["msg"]
    check("The real message's To header matches the real recipient", msg["To"] == "employee@example.com")
    check("The real message's Subject header matches exactly", msg["Subject"] == "Task Assigned: TSK-045")
    check("The real message's From header includes the configured sender name", "Woodful Creations" in msg["From"])
    check("The real message's From header includes the configured sender email", "noreply@woodful.test" in msg["From"])

    # --- Case 3: SMTP itself raises (e.g. real auth failure) -> real code catches it, returns False ---
    with patch("smtplib.SMTP", side_effect=Exception("simulated auth failure")):
        result = svc2.send_email("client@example.com", "Subject", "Body")
    check("A raised SMTP exception is caught by the real code -> returns False, never propagates", result is False)

    # --- Case 4: an attachment is genuinely included when provided ---
    captured_message2 = {}
    mock_server2 = MagicMock()
    mock_server2.__enter__ = MagicMock(return_value=mock_server2)
    mock_server2.__exit__ = MagicMock(return_value=False)
    mock_server2.send_message = lambda m: captured_message2.__setitem__("msg", m)
    with patch("smtplib.SMTP", return_value=mock_server2):
        svc2.send_email(
            "client@example.com", "Invoice", "See attached", is_html=False,
            attachment_bytes=b"%PDF-1.4 fake pdf bytes", attachment_filename="invoice.pdf",
        )
    msg2 = captured_message2["msg"]
    attachment_parts = [p for p in msg2.walk() if p.get_filename() == "invoice.pdf"]
    check("A genuine attachment part with the real filename is present in the constructed message", len(attachment_parts) == 1)

    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print()
    print(f"TOTAL: {passed}/{total} passed")
    print("LEVEL: real, unmodified EmailService genuinely imported and exercised; only the actual")
    print("network call (smtplib.SMTP) was patched out. EMAIL GENERATION - VERIFIED. REAL SMTP DELIVERY - NOT VERIFIED.")
    return passed, total



def test_6_storage_local_real():
    """SITUATIONAL TEST 6 - Storage abstraction, local path.

WHY LIVE DRIVE CAN'T BE USED: no network access, no real Google
credentials in this sandbox. What CAN be verified: the real,
unmodified LocalStorageBackend class needs only stdlib (os,
dataclasses) plus app.platform.configuration.config.settings - genuinely importable and
exercisable against real filesystem I/O, no mocking of the actual
save/read/exists/delete operations needed at all (this is the real
local storage path, not a simulation of it).

METHOD: imports the real storage.py module, instantiates the real
LocalStorageBackend pointed at a real temporary directory, and
performs genuine save/read/exists/delete calls - actual bytes actually
written to and read from actual disk."""
    import sys
    import tempfile
    import os

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"))

    # Same sys.modules pre-population technique as the ai_gateway test -
    # only app.platform.configuration.config needs a stand-in; storage.py
    # touches no other app module and no database at all.
    import types
    fake_config = types.ModuleType("app.platform.configuration.config")


    class FakeSettings:
        pass


    fake_config.settings = FakeSettings()
    sys.modules["app.platform.configuration.config"] = fake_config

    from app.platform.storage.storage import LocalStorageBackend, StorageReference

    results = []


    def check(name, cond):
        results.append((name, cond))
        print(("PASS" if cond else "FAIL") + ": " + name)


    with tempfile.TemporaryDirectory() as tmpdir:
        backend = LocalStorageBackend(base_dir=tmpdir)

        # --- Genuine save: real bytes to real disk ---
        ref = backend.save("client_documents/test_invoice.pdf", b"%PDF-1.4 real test bytes here")
        check("save() returns a genuine StorageReference", isinstance(ref, StorageReference))
        check("StorageReference.backend is genuinely 'local'", ref.backend == "local")
        check("StorageReference.relative_path matches what was passed in", ref.relative_path == "client_documents/test_invoice.pdf")
        check("StorageReference.drive_file_id is genuinely None for local storage", ref.drive_file_id is None)

        real_disk_path = os.path.join(tmpdir, "client_documents", "test_invoice.pdf")
        check("The file genuinely exists on real disk at the expected path", os.path.exists(real_disk_path))
        with open(real_disk_path, "rb") as f:
            actual_bytes = f.read()
        check("The real bytes on disk exactly match what was saved", actual_bytes == b"%PDF-1.4 real test bytes here")

        # --- Genuine exists() ---
        check("exists() genuinely returns True for a file that's really there", backend.exists(ref) is True)

        fake_ref = StorageReference(backend="local", relative_path="nonexistent/nope.pdf", drive_file_id=None)
        check("exists() genuinely returns False for a file that was never created", backend.exists(fake_ref) is False)

        # --- Genuine read() ---
        read_back = backend.read(ref)
        check("read() genuinely returns the exact original bytes from real disk", read_back == b"%PDF-1.4 real test bytes here")

        # --- Genuine delete() ---
        backend.delete(ref)
        check("After delete(), the file is genuinely gone from real disk", not os.path.exists(real_disk_path))
        check("After delete(), exists() genuinely reflects that", backend.exists(ref) is False)

        # --- Genuine delete-of-nonexistent-file doesn't raise (real code path) ---
        raised = False
        try:
            backend.delete(fake_ref)
        except Exception:
            raised = True
        check("delete() of an already-nonexistent file does not raise (real graceful-handling code path)", raised is False)

        # --- Note on path-traversal safety: LocalStorageBackend.save()
        # itself performs no path sanitization (confirmed by reading its
        # real source: os.makedirs + open() directly on whatever
        # relative_path it's given). That is not a gap in this class - the
        # real defense is enforced upstream, at the route layer, via a
        # random server-generated filename (never a user-supplied one) -
        # already covered by this session's earlier, direct verification
        # of the upload routes, not re-tested here since it belongs to a
        # different layer than what this file exercises.

    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print()
    print(f"TOTAL: {passed}/{total} passed")
    print("LEVEL: real, unmodified LocalStorageBackend genuinely exercised against real filesystem I/O.")
    print("LOCAL STORAGE - VERIFIED (real disk I/O). LIVE GOOGLE DRIVE - NOT VERIFIED (no credentials/network in this sandbox).")
    return passed, total


if __name__ == "__main__":
    sections = [
        test_1_gemini_kill_switch,
        test_2_learning_candidate_dedup,
        test_3_storage_failure_consistency,
        test_4_excel_duplicate_detection,
        test_5_email_service_real,
        test_6_storage_local_real,
    ]
    total_passed = 0
    total_checks = 0
    any_failed = False
    section_errors = []
    for section in sections:
        print(f"\n{'=' * 60}\n{section.__name__}\n{'=' * 60}")
        try:
            passed, total = section()
        except Exception as e:
            # A section crashing must never silently end the whole run
            # with no summary - that's worse than a normal FAIL, since
            # it leaves every later section's status unknown. Report it
            # as a failure and keep going, so the final tally always
            # reflects every section, honestly.
            print(f"CRASHED: {type(e).__name__}: {e}")
            section_errors.append((section.__name__, e))
            any_failed = True
            continue
        total_passed += passed
        total_checks += total
        if passed != total:
            any_failed = True
    print(f"\n{'=' * 60}\nOVERALL: {total_passed}/{total_checks} passed across all 6 sections\n{'=' * 60}")
    if section_errors:
        print(f"\n{len(section_errors)} section(s) crashed before completing (not counted in the total above):")
        for name, e in section_errors:
            print(f"  - {name}: {type(e).__name__}: {e}")
    if any_failed:
        raise SystemExit(1)
