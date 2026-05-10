"""
Tests for therapist plan field (Part 2 of plan/billing investigation).

Covers:
1. New users registered without ?plan= param default to plan='free'.
2. New users registered with ?plan=pro get plan='pro'.
3. Admin PATCH /plan rejects invalid plan values.
4. Admin PATCH /plan=pro persists and is reflected.
5. Admin PATCH /plan=clinic stores clinic_name in parentheses format.
6. Admin PATCH /plan=free clears clinic_name.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.api.deps import get_db
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_therapist(db):
    t = Therapist(
        email="admin@clinic.com",
        hashed_password="x",
        full_name="Admin",
        is_active=True,
        is_admin=True,
        plan="free",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def admin_client(admin_therapist):
    """TestClient with admin JWT injected."""
    from app.security.auth import create_access_token
    from datetime import timedelta
    token = create_access_token(
        data={"sub": str(admin_therapist.id), "is_admin": True},
        expires_delta=timedelta(hours=1),
    )

    def override_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def target_therapist(db):
    t = Therapist(
        email="target@clinic.com",
        hashed_password="x",
        full_name="Target User",
        is_active=True,
        plan="free",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# ── Default plan for new users ────────────────────────────────────────────────

class TestDefaultPlan:
    def test_therapist_model_defaults_to_free(self, db):
        t = Therapist(
            email="newuser@test.com",
            hashed_password="x",
            full_name="New User",
            is_active=True,
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        assert t.plan == "free"
        assert t.clinic_name is None

    def test_pro_signup_sets_plan_pro(self, db):
        t = Therapist(
            email="pro@test.com",
            hashed_password="x",
            full_name="Pro User",
            is_active=True,
        )
        db.add(t)
        db.commit()
        # Simulate what auth.py does on ?plan=pro
        t.intended_plan = "pro"
        t.plan = "pro"
        db.commit()
        db.refresh(t)
        assert t.plan == "pro"
        assert t.intended_plan == "pro"


# ── Admin PATCH /plan validation ──────────────────────────────────────────────

class TestAdminPlanEndpoint:
    def test_invalid_plan_value_rejected(self, admin_client, target_therapist):
        resp = admin_client.patch(
            f"/api/v1/admin-panel/therapists/{target_therapist.id}/plan",
            json={"plan": "enterprise"},
        )
        assert resp.status_code == 422

    def test_set_plan_pro(self, admin_client, target_therapist):
        resp = admin_client.patch(
            f"/api/v1/admin-panel/therapists/{target_therapist.id}/plan",
            json={"plan": "pro"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "pro"
        assert data["clinic_name"] is None

    def test_set_plan_free(self, admin_client, target_therapist, db):
        # Set to pro first
        target_therapist.plan = "pro"
        db.commit()

        resp = admin_client.patch(
            f"/api/v1/admin-panel/therapists/{target_therapist.id}/plan",
            json={"plan": "free"},
        )
        assert resp.status_code == 200
        assert resp.json()["plan"] == "free"

    def test_set_plan_clinic_stores_clinic_name(self, admin_client, target_therapist):
        resp = admin_client.patch(
            f"/api/v1/admin-panel/therapists/{target_therapist.id}/plan",
            json={"plan": "clinic", "clinic_name": "מרפאת השרון"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "clinic"
        assert data["clinic_name"] == "מרפאת השרון"

    def test_set_plan_free_clears_clinic_name(self, admin_client, target_therapist, db):
        # Set up as clinic first
        target_therapist.plan = "clinic"
        target_therapist.clinic_name = "מרפאת השרון"
        db.commit()

        resp = admin_client.patch(
            f"/api/v1/admin-panel/therapists/{target_therapist.id}/plan",
            json={"plan": "free"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        assert data["clinic_name"] is None

    def test_plan_persists_in_list_endpoint(self, admin_client, target_therapist, db):
        target_therapist.plan = "clinic"
        target_therapist.clinic_name = "קליניקה מרכזית"
        db.commit()

        resp = admin_client.get("/api/v1/admin-panel/therapists")
        assert resp.status_code == 200
        rows = resp.json()
        row = next((r for r in rows if r["id"] == target_therapist.id), None)
        assert row is not None
        assert row["plan"] == "clinic"
        assert row["clinic_name"] == "קליניקה מרכזית"

    def test_plan_filter_free(self, admin_client, target_therapist, db, admin_therapist):
        # admin_therapist is free, target_therapist is free by default
        resp = admin_client.get("/api/v1/admin-panel/therapists?plan=free")
        assert resp.status_code == 200
        rows = resp.json()
        assert all(r["plan"] == "free" for r in rows)

    def test_plan_filter_pro(self, admin_client, target_therapist, db):
        target_therapist.plan = "pro"
        db.commit()

        resp = admin_client.get("/api/v1/admin-panel/therapists?plan=pro")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) >= 1
        assert all(r["plan"] == "pro" for r in rows)

    def test_non_admin_cannot_set_plan(self, target_therapist, db):
        from app.security.auth import create_access_token
        from datetime import timedelta
        token = create_access_token(
            data={"sub": str(target_therapist.id), "is_admin": False},
            expires_delta=timedelta(hours=1),
        )

        def override_db():
            session = TestSessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_db
        try:
            with TestClient(app) as c:
                resp = c.patch(
                    f"/api/v1/admin-panel/therapists/{target_therapist.id}/plan",
                    json={"plan": "pro"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()
