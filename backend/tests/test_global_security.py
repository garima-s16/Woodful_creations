"""Tests for the global security fixes: the default rate-limit floor
applied to every request via middleware, and the DEBUG=True +
ENVIRONMENT=production cross-field rejection."""


def test_debug_true_in_production_is_rejected():
    from app.core.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db", ENVIRONMENT="production", DEBUG=True)


def test_debug_true_in_development_is_allowed():
    from app.core.config import Settings
    s = Settings(SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db", ENVIRONMENT="development", DEBUG=True)
    assert s.DEBUG is True


def test_debug_false_in_production_is_allowed():
    from app.core.config import Settings
    s = Settings(SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db", ENVIRONMENT="production", DEBUG=False)
    assert s.DEBUG is False


def test_global_rate_limit_middleware_blocks_after_threshold(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200

    from app.core.config import settings
    responses = [client.get("/api/materials/") for _ in range(settings.RATE_LIMIT_DEFAULT_PER_MINUTE + 5)]
    assert any(r.status_code == 429 for r in responses)


def test_health_endpoint_is_exempt_from_global_rate_limit(client):
    """The health check must never be rate-limited - infrastructure
    monitoring depends on it staying reachable."""
    responses = [client.get("/health") for _ in range(50)]
    assert all(r.status_code == 200 for r in responses)


def test_purchase_import_rejects_non_xlsx_extension(client, test_user):
    import io
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200
    files = {"file": ("data.csv", io.BytesIO(b"not,an,xlsx"), "text/csv")}
    resp = client.post("/api/purchase-imports/preview", files=files)
    assert resp.status_code == 400
