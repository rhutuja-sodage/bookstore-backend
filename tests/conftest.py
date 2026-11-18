import os
import uuid

# Must be set before the app is imported: tests run against a throwaway database.
TEST_DB = f"bookworm_test_{uuid.uuid4().hex[:8]}"
os.environ["BOOKWORM_MONGODB_DB"] = TEST_DB
os.environ["BOOKWORM_SEED_ON_STARTUP"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(create_app()) as c:
        yield c
    MongoClient(get_settings().mongodb_url).drop_database(TEST_DB)


@pytest.fixture
def demo_headers(client):
    r = client.post("/api/auth/login", json={"email": "demo@bookworm.com", "password": "Demo@123"})
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.fixture
def new_user(client):
    """A fresh account (so tests never depend on each other's gift points / orders)."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/register", json={"name": "Test User", "email": email, "password": "secret1"})
    assert r.status_code == 201
    return {"email": email, "headers": {"Authorization": f"Bearer {r.json()['accessToken']}"}}


ADDRESS = {
    "firstName": "Test", "lastName": "User", "line1": "12 Main Street", "email": "t@example.com", "city": "Pune",
    "pin": "411001", "countryCode": "+91", "phone": "9876543210", "state": "Maharashtra", "country": "India",
}
PAYMENT = {"mode": "UPI", "detail": "test@upi"}


@pytest.fixture
def order_body():
    def make(items=(("art-of-focus", 2),), **extra):
        return {
            "items": [{"bookId": b, "qty": q} for b, q in items],
            "address": ADDRESS, "payment": PAYMENT, **extra,
        }
    return make
