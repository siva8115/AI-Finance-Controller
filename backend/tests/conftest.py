"""
Shared pytest configuration and fixtures.

All test modules share this conftest so that:
1. There is only ONE in-memory SQLite engine (preventing app.dependency_overrides conflicts).
2. Each test gets a clean database via the setup_db fixture autouse.
3. No module-level override_get_db collisions between test files.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.financial  # Register models first
from app.main import app
from app.core.database import Base, get_db

# Single shared in-memory SQLite engine for all tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """DB dependency override for FastAPI TestClient to use the shared in-memory engine."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Apply override globally once (prevents multiple test modules from fighting)
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after — ensuring full isolation."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
