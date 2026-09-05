"""Shared pytest fixtures: an isolated in-memory SQLite DB per test session,
wired into the FastAPI app via dependency override so tests never touch a
real database."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A valid-looking SECRET_KEY must exist before app.platform.configuration.config is imported.
# Must not contain any of the validator's placeholder markers (change,
# secret-key, your-, woodful-secret) - a prior version of this line
# literally contained "secret-key" and would fail its own check.
os.environ.setdefault("SECRET_KEY", "pytest-fixture-a8f3k29dl0qm4x7bnv6t1rwzcy5hj-not-a-real-value")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("COOKIE_SECURE", "False")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.platform.database.database import Base, get_db
from app.platform.security.security import hash_password
from app.main import app
from app.modules.auth.models import User

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function", autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function", autouse=True)
def reset_rate_limiter():
    """Test isolation. Without this, the
    rate limiter's module-level singleton (app/platform/security/rate_limit.py)
    persists across every test in a session, so a test late in the
    suite that hits an already-exercised bucket (e.g. login, chat)
    could be unexpectedly rejected with 429 purely from requests
    earlier, unrelated tests already made - not a real bug in the
    test itself. Sibling to reset_db above, same autouse/function-
    scope pattern."""
    from app.platform.security.rate_limit import reset_rate_limits
    reset_rate_limits()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_user(db_session):
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        password_hash=hash_password("TestPass123!"),
        role="master",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
