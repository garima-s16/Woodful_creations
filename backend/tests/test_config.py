"""Regression test for the CORS_ORIGINS crash: pydantic-settings tries to
JSON-decode env values for List[str] fields before any validator runs,
which crashes on a plain comma-separated string. This test instantiates
Settings directly (not through conftest's pre-set env vars) to catch that
class of bug specifically."""
import os


def test_settings_accepts_comma_separated_cors_origins(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key-not-for-real-use-1234567890")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # Re-import fresh so it picks up the monkeypatched env vars rather than
    # any cached settings instance from a prior test.
    import importlib
    from app.core import config as config_module
    importlib.reload(config_module)

    fresh_settings = config_module.Settings()
    assert fresh_settings.cors_origins_list == [
        "http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000",
    ]


def test_settings_allowed_extensions_split_correctly(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key-not-for-real-use-1234567890")
    monkeypatch.setenv("ALLOWED_EXTENSIONS", "pdf,xlsx,docx")

    import importlib
    from app.core import config as config_module
    importlib.reload(config_module)

    fresh_settings = config_module.Settings()
    assert fresh_settings.allowed_extensions_list == ["pdf", "xlsx", "docx"]
