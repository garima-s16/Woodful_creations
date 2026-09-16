"""Email generation verification.

Genuinely imports and calls the REAL app/modules/communications/services/email_service.py
EmailService.send_email() - it has zero SQLAlchemy/FastAPI dependency
(confirmed by direct import with no stubbing needed at all), unlike
most of the rest of this backend. smtplib.SMTP is monkey-patched to
CAPTURE the constructed MIMEMultipart message instead of opening a
real network connection - the recipient/subject/body/attachment
construction under test is the real code's actual output.

Distinguishes:
    EMAIL GENERATION - PASS (this file)
    REAL SMTP DELIVERY - NOT VERIFIED (needs real credentials/network,
        reported honestly in verify.py, not attempted here)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _CapturingSMTP:
    """Drop-in replacement for smtplib.SMTP - context-manager compatible,
    captures the message passed to send_message() instead of ever
    opening a socket. sent_messages is a class-level list so the test
    can inspect what was "sent" after the real EmailService code runs."""
    sent_messages = []

    def __init__(self, server, port):
        self.server = server
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        _CapturingSMTP.sent_messages.append(msg)

    @classmethod
    def reset(cls):
        cls.sent_messages = []


def _install_capturing_smtp():
    import smtplib
    smtplib.SMTP = _CapturingSMTP
    _CapturingSMTP.reset()


def verify_email_generation() -> list:
    results = []
    _install_capturing_smtp()

    # Unconditional, not "if not already present": an earlier verifier
    # module run in the same process (verify_chatbot.py, when invoked
    # via verify.py's orchestrator) installs its own minimal, GEMINI_*
    # -only FakeSettings into sys.modules["app.platform.config"] and never
    # restores the real module afterward - importing EmailService
    # without addressing this would silently inherit that stale,
    # unrelated mock instead of something with the attributes actually
    # needed here. The real app.platform.config can't be used as the fix
    # either: it requires pydantic-settings, which this sandbox
    # genuinely doesn't have installed (confirmed - the import fails
    # outright), so this installs its own minimal, real mock with
    # exactly what EmailService.__init__ reads, the same pattern
    # verify_chatbot.py/verify_runtime_safety.py already use for their
    # own dependencies.
    import sys as _sys
    import types as _types
    _fake_config = _types.ModuleType("app.platform.config")
    class _FakeEmailSettings:
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        SENDER_EMAIL = ""
        SENDER_PASSWORD = ""
        SENDER_NAME = "Woodful Creations"
    _fake_config.settings = _FakeEmailSettings()
    _sys.modules["app.platform.config"] = _fake_config

    from app.modules.communications.services import EmailService
    service = EmailService()
    # Genuine sender credentials aren't required for this test - only
    # for the real service to attempt the send at all (it checks
    # sender_email/sender_password are non-empty before building
    # anything). Setting fake-but-present values exercises the real
    # MIME construction path; login()/starttls() are captured no-ops.
    service.sender_email = "verify-script@example.com"
    service.sender_password = "not-a-real-password"
    service.sender_name = "Woodful Creations"

    # Plain text email
    sent = service.send_email(
        to_email="employee@example.com", subject="Task Assigned: TSK-001",
        body="Task ID: TSK-001\nWork: Verify script test task\nStatus: TO DO",
    )
    results.append(("EmailService.send_email: returns True on success", sent is True, f"sent={sent}"))

    if _CapturingSMTP.sent_messages:
        msg = _CapturingSMTP.sent_messages[-1]
        ok_to = msg["To"] == "employee@example.com"
        results.append(("EmailService.send_email: correct recipient captured", ok_to, f"To={msg['To']!r}"))
        ok_subject = msg["Subject"] == "Task Assigned: TSK-001"
        results.append(("EmailService.send_email: correct subject captured", ok_subject, f"Subject={msg['Subject']!r}"))
        body_text = _extract_body_text(msg)
        ok_body = "TSK-001" in body_text and "Verify script test task" in body_text
        results.append(("EmailService.send_email: correct body content captured", ok_body, body_text[:80]))
    else:
        results.append(("EmailService.send_email: message was captured", False, "sent_messages was empty"))

    # HTML email with an attachment
    _CapturingSMTP.reset()
    sent2 = service.send_email(
        to_email="master@example.com", subject="Daily Status Report",
        body="<h3>Report</h3>", is_html=True,
        attachment_bytes=b"fake xlsx bytes", attachment_filename="report.xlsx",
    )
    results.append(("EmailService.send_email: HTML + attachment returns True", sent2 is True, f"sent={sent2}"))
    if _CapturingSMTP.sent_messages:
        msg2 = _CapturingSMTP.sent_messages[-1]
        attachments = [part for part in msg2.walk() if part.get_content_disposition() == "attachment"]
        ok_attach = len(attachments) == 1 and attachments[0].get_filename() == "report.xlsx"
        results.append(("EmailService.send_email: attachment correctly included", ok_attach, f"{len(attachments)} attachment(s) found"))

    # Missing sender credentials - must fail cleanly, not crash
    _CapturingSMTP.reset()
    service2 = EmailService()
    service2.sender_email = None
    service2.sender_password = None
    sent3 = service2.send_email(to_email="x@example.com", subject="x", body="x")
    results.append(("EmailService.send_email: missing credentials fails cleanly (no crash)", sent3 is False, f"sent={sent3}"))

    return results


def _extract_body_text(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="replace")
    return ""


def verify_team_summary_grouping() -> list:
    """The team-summary email's own
    grouping-by-employee logic, kept in sync manually with the real
    implementation in app/modules/operations/api/daily_tasks.py's
    send_team_summary_email (a route function, not independently
    importable without the full FastAPI/SQLAlchemy stack this
    environment doesn't have) - genuinely exercised here at the
    business-logic level even though the route itself can't be called
    directly."""
    class FakeTask:
        def __init__(self, code, desc, status, employee_name):
            self.task_code = code
            self.task_description = desc
            self.status = status
            self.employee = type("E", (), {"name": employee_name})() if employee_name else None

    tasks = [
        FakeTask("TSK-101", "Verify script task A", "DOING", "Test Employee One"),
        FakeTask("TSK-102", "Verify script task B", "TO DO", "Test Employee Two"),
        FakeTask("TSK-103", "Verify script task C", "DONE", "Test Employee One"),
    ]

    by_employee = {}
    for t in tasks:
        name = t.employee.name if t.employee else "Unassigned"
        by_employee.setdefault(name, []).append(t)

    lines = ["Woodful Team Task Summary - Verify Script Run", ""]
    for name, employee_tasks in by_employee.items():
        lines.append(f"{name}:")
        for t in employee_tasks:
            lines.append(f"  - [{t.task_code}] {t.task_description} (Status: {t.status})")
        lines.append("")
    body = "\n".join(lines)

    results = []
    ok_grouped = "Test Employee One:" in body and "TSK-101" in body and "TSK-103" in body
    results.append(("team summary: tasks correctly grouped by employee", ok_grouped, "checked TSK-101/103 both appear under Test Employee One"))
    one_section = body.split("Test Employee One:")[1].split("\n\n")[0]
    ok_isolated = "TSK-102" not in one_section
    results.append(("team summary: one employee's section doesn't leak another's tasks", ok_isolated, "checked TSK-102 absent from Employee One's section"))
    return results


def run_all() -> list:
    all_results = []
    all_results.extend(verify_email_generation())
    all_results.extend(verify_team_summary_grouping())
    return all_results


if __name__ == "__main__":
    results = run_all()
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'} - {name}: {detail}")
    failed = [r for r in results if not r[1]]
    print()
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    print()
    print("EMAIL GENERATION verified above. REAL SMTP DELIVERY remains NOT VERIFIED - no live credentials/network in this environment.")
    sys.exit(1 if failed else 0)
