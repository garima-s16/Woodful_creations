"""
Provider-neutral production error/monitoring boundary.

Every other module - business or platform - reports a problem by calling
capture_exception() or capture_message() from this file. Nothing outside
this file ever imports a monitoring provider's SDK directly. That keeps
the provider genuinely swappable (today "none" or "sentry", selected via
MONITORING_PROVIDER - see app/platform/config.py) and keeps
provider-specific code from leaking into business modules.

Safety rules, both enforced here rather than trusted to every call site:
  - Context is redacted before it leaves this file - see _redact_context.
  - A failure inside the monitoring provider itself (network error,
    misconfigured DSN, provider outage) is caught and logged locally,
    never allowed to become a second, unrelated failure on top of
    whatever was already being reported.
"""
import logging
import traceback
from typing import Any

from app.platform.config import settings

logger = logging.getLogger(__name__)

# Key names that must never leave this process, regardless of which call
# site supplied them - matched case-insensitively against every key in
# the context dict a caller passes in, at any nesting depth. This is a
# defensive floor, not a replacement for call sites keeping secrets out
# of context in the first place.
_REDACTED_KEY_MARKERS = (
    "password", "token", "secret", "api_key", "apikey", "authorization",
    "cookie", "database_url", "credential", "otp", "private_key",
)


def _redact_context(value: Any) -> Any:
    """Recursively strips anything whose key looks like a secret. Applied
    to every context dict before it reaches a provider or a log line."""
    if isinstance(value, dict):
        redacted = {}
        for key, val in value.items():
            key_str = str(key).lower()
            if any(marker in key_str for marker in _REDACTED_KEY_MARKERS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_context(val)
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redact_context(item) for item in value]
    return value


class _NoopProvider:
    """Default provider - errors are still logged locally (same as
    always), nothing is sent anywhere external. Requires zero extra
    infrastructure or dependency, so this is always a fully-functional
    choice, not a degraded placeholder."""

    def capture_exception(self, exc: BaseException, context: dict) -> None:
        logger.error(
            "Unhandled exception: %s\n%s\ncontext=%r",
            exc, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), context,
        )

    def capture_message(self, message: str, level: str, context: dict) -> None:
        log_fn = {"error": logger.error, "warning": logger.warning}.get(level, logger.info)
        log_fn("%s (level=%s) context=%r", message, level, context)


class _SentryProvider:
    """Wraps the sentry-sdk package - imported lazily, not at module
    level, so a deployment with MONITORING_PROVIDER=none (the default)
    never needs sentry-sdk installed at all, the same pattern already
    used for the optional redis dependency in
    app/platform/security.py."""

    def __init__(self):
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.MONITORING_DSN,
            environment=settings.ENVIRONMENT,
            release=settings.APP_VERSION,
            # Request bodies/headers can carry exactly the data
            # _redact_context exists to keep out - never hand raw
            # request data to the SDK's own capture.
            send_default_pii=False,
        )
        self._sdk = sentry_sdk

    def capture_exception(self, exc: BaseException, context: dict) -> None:
        with self._sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            self._sdk.capture_exception(exc)

    def capture_message(self, message: str, level: str, context: dict) -> None:
        with self._sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            self._sdk.capture_message(message, level=level)


_provider = None


def _get_provider():
    global _provider
    if _provider is None:
        provider_name = settings.MONITORING_PROVIDER.lower()
        if provider_name == "sentry":
            try:
                _provider = _SentryProvider()
            except Exception:
                # A provider that fails to even initialize must not take
                # the whole application down with it - fall back to the
                # always-safe local-log behavior and say why, once.
                logger.exception(
                    "Failed to initialize the 'sentry' monitoring provider - "
                    "falling back to local-log-only monitoring. Check that "
                    "sentry-sdk is installed and MONITORING_DSN is a valid DSN."
                )
                _provider = _NoopProvider()
        else:
            _provider = _NoopProvider()
    return _provider


def reset_monitoring_provider() -> None:
    """Test isolation - mirrors reset_rate_limits() in
    app/platform/security.py. The provider is a lazily-created,
    module-level singleton that would otherwise persist across every test
    in a session."""
    global _provider
    _provider = None


def capture_exception(exc: BaseException, **context: Any) -> None:
    """Report an exception that was caught and handled (or is about to
    produce a safe generic error response) but is still worth knowing
    about in production - a database failure, a storage failure, an AI
    provider failure, or any other unexpected condition.

    context is free-form (environment/module/operation/endpoint/
    correlation-id/user-role-where-safe are all reasonable), and is
    redacted before it reaches the provider or a log line - but callers
    should still never pass raw request bodies, tokens, or file contents
    in the first place; redaction here is a safety net, not permission
    to be careless upstream.

    Never raises - a monitoring failure must never become a second,
    unrelated failure on top of whatever was already being reported."""
    try:
        _get_provider().capture_exception(exc, _redact_context(context))
    except Exception:
        logger.exception("Monitoring provider failed while capturing an exception.")


def capture_message(message: str, level: str = "error", **context: Any) -> None:
    """Report a significant non-exception event worth surfacing in
    production monitoring - e.g. a background task that silently gave up
    after exhausting its retries. Not for routine/expected validation
    errors - see the module docstring in the caller's own file for what
    counts as "significant" in that context.

    Never raises, for the same reason as capture_exception."""
    try:
        _get_provider().capture_message(message, level, _redact_context(context))
    except Exception:
        logger.exception("Monitoring provider failed while capturing a message.")
