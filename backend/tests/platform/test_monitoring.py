"""Tests for the provider-neutral monitoring boundary
(app/platform/monitoring/monitoring.py) - context redaction, safe
fallback when no provider (or a broken one) is configured, and the
global unhandled-exception handler registered in app/main.py."""
import pytest


@pytest.fixture(autouse=True)
def _reset_monitoring():
    from app.platform.monitoring.monitoring import reset_monitoring_provider
    reset_monitoring_provider()
    yield
    reset_monitoring_provider()


def test_capture_exception_never_raises_with_default_provider():
    """The default MONITORING_PROVIDER=none must be a fully safe,
    always-working choice - capturing an exception must never itself
    raise, since that would turn error reporting into a second failure
    on top of whatever was already being reported."""
    from app.platform.monitoring.monitoring import capture_exception
    capture_exception(ValueError("something went wrong"), endpoint="/api/test", module="test")


def test_capture_message_never_raises_with_default_provider():
    from app.platform.monitoring.monitoring import capture_message
    capture_message("a significant non-exception event", level="warning", module="test")


def test_capture_exception_survives_a_broken_provider(monkeypatch):
    """If the configured provider itself throws (network error, bad
    DSN, provider outage), capture_exception must still not raise -
    the whole point of this boundary is that a monitoring failure can
    never become a second, unrelated application failure."""
    import app.platform.monitoring.monitoring as monitoring_module

    class _BrokenProvider:
        def capture_exception(self, exc, context):
            raise RuntimeError("simulated monitoring provider outage")

    monkeypatch.setattr(monitoring_module, "_get_provider", lambda: _BrokenProvider())
    monitoring_module.capture_exception(ValueError("original error"), module="test")


def test_redact_context_strips_password_like_keys():
    from app.platform.monitoring.monitoring import _redact_context
    result = _redact_context({
        "password": "hunter2", "user_token": "abc123", "API_KEY": "sk-real-key",
        "safe_field": "this is fine",
    })
    assert result["password"] == "[REDACTED]"
    assert result["user_token"] == "[REDACTED]"
    assert result["API_KEY"] == "[REDACTED]"
    assert result["safe_field"] == "this is fine"


def test_redact_context_is_recursive_into_nested_dicts():
    from app.platform.monitoring.monitoring import _redact_context
    result = _redact_context({"request": {"headers": {"cookie": "session=abc"}, "path": "/api/x"}})
    assert result["request"]["headers"]["cookie"] == "[REDACTED]"
    assert result["request"]["path"] == "/api/x"


def test_redact_context_covers_database_url_and_secret_key():
    """Explicitly required by the production observability rules -
    DATABASE_URL and SECRET_KEY must never reach a monitoring provider
    even if a call site accidentally includes them in context."""
    from app.platform.monitoring.monitoring import _redact_context
    result = _redact_context({"DATABASE_URL": "postgresql://real-connection-string", "SECRET_KEY": "real-secret"})
    assert result["DATABASE_URL"] == "[REDACTED]"
    assert result["SECRET_KEY"] == "[REDACTED]"


def test_unhandled_exception_handler_returns_safe_generic_response(monkeypatch):
    """End-to-end HTTP behavior of the handler registered in app/main.py,
    exercised through a throwaway test-only app - never the real
    production app - so no crash-inducing route ever exists in
    production. Confirms the response is generic (no exception detail,
    no traceback) and that monitoring was actually invoked."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.main as main_module

    captured = []
    monkeypatch.setattr(main_module, "capture_exception", lambda exc, **ctx: captured.append((exc, ctx)))

    test_app = FastAPI()
    test_app.add_exception_handler(Exception, main_module.unhandled_exception_handler)

    @test_app.get("/boom")
    def boom():
        raise RuntimeError("a very specific internal detail that must never reach the client")

    test_client = TestClient(test_app, raise_server_exceptions=False)
    resp = test_client.get("/boom")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "An unexpected error occurred. Please try again."}
    assert "very specific internal detail" not in resp.text

    assert len(captured) == 1
    exc, ctx = captured[0]
    assert isinstance(exc, RuntimeError)
    assert ctx == {"method": "GET", "path": "/boom"}
