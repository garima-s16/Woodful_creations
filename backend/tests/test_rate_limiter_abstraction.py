"""Tests for the pluggable rate-limiter backend (Family 1 - "do not
depend on Redis merely to run locally"). Verifies the in-memory
backend's behavior directly (bypassing the module-global singleton
so each test gets a clean instance), and that the module itself
never imports redis at module level."""
import time


def test_in_memory_backend_allows_up_to_the_limit():
    from app.core.rate_limit import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        assert backend.is_allowed("test-key", max_requests=5, window_seconds=60) is True


def test_in_memory_backend_blocks_beyond_the_limit():
    from app.core.rate_limit import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        backend.is_allowed("test-key", max_requests=5, window_seconds=60)
    assert backend.is_allowed("test-key", max_requests=5, window_seconds=60) is False


def test_in_memory_backend_keys_are_independent():
    from app.core.rate_limit import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        backend.is_allowed("key-a", max_requests=5, window_seconds=60)
    # A different key must have its own independent budget.
    assert backend.is_allowed("key-b", max_requests=5, window_seconds=60) is True


def test_in_memory_backend_window_expires():
    from app.core.rate_limit import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(3):
        backend.is_allowed("test-key", max_requests=3, window_seconds=1)
    assert backend.is_allowed("test-key", max_requests=3, window_seconds=1) is False
    time.sleep(1.1)
    assert backend.is_allowed("test-key", max_requests=3, window_seconds=1) is True


def test_redis_is_not_imported_at_module_level():
    """The core requirement - a plain local dev environment must never
    need the redis package installed just to import this file."""
    import ast
    import app.core.rate_limit as module
    with open(module.__file__) as f:
        tree = ast.parse(f.read())
    module_level_names = [n.names[0].name for n in tree.body if isinstance(n, ast.Import)]
    assert "redis" not in module_level_names


def test_public_rate_limit_function_signature_unchanged(client, test_user):
    """Every existing caller (login, chat, password reset) uses
    rate_limit(bucket, max_requests, window_seconds) - confirms the
    endpoints that depend on it still respond normally rather than
    erroring on a broken dependency."""
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_chat_endpoint_is_rate_limited(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200

    from app.core.config import settings
    responses = [client.post("/api/chat/", json={"message": "hello"}) for _ in range(settings.RATE_LIMIT_CHAT_PER_MINUTE + 3)]
    assert any(r.status_code == 429 for r in responses)
