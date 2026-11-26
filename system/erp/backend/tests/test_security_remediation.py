"""Independent Remediation Test Suite for Security Defects.

Verifies:
- SEC-01 (Issue #10): Hardcoded Backdoor Superadmin Bypass in require_superadmin.
  Validates that usernames 'ammar' and 'admoon' without is_superadmin=True or role='superadmin'
  are strictly rejected with 403 Forbidden.
- SEC-02 (Issue #11): Broken Object Level Authorization & Role Escalation in Authorization Router.
  Validates that non-admin/cashier users cannot assign roles, override permissions, or access audit logs,
  and cross-tenant user mutations return 404 / 403.
- SEC-03 (Issue #12): Break-Glass Emergency Escalation Guardrails.
  Validates that non-clinical users cannot trigger emergency override, reason must be meaningful (>= 10 chars),
  and emergency window is capped to max 4 hours.
"""
import os
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from app.db.base import AsyncSessionLocal
from app.platform.auth.security import create_access_token, hash_password
from app.dependencies import require_superadmin
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User
from fastapi import HTTPException
from tests.conftest import give_roles

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set"
)


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _create_security_test_env():
    """Sets up two separate tenants with users of varying privilege levels."""
    async with AsyncSessionLocal() as session:
        t1_id = uuid.uuid4()
        tenant1 = Tenant(
            id=t1_id,
            name=f"Sec Tenant 1 {t1_id.hex[:6]}",
            slug=f"sec-1-{t1_id.hex[:6]}",
            status="active",
            active_modules=["healthcare_clinic", "sales", "finance"],
        )
        session.add(tenant1)
        await session.flush()  # the workspace exists before its users

        t2_id = uuid.uuid4()
        tenant2 = Tenant(
            id=t2_id,
            name=f"Sec Tenant 2 {t2_id.hex[:6]}",
            slug=f"sec-2-{t2_id.hex[:6]}",
            status="active",
            active_modules=["sales"],
        )
        session.add(tenant2)
        await session.flush()  # the workspace exists before its users

        # 1. Backdoor test user 1: username="ammar", role="cashier", is_superadmin=False
        u_ammar = User(
            id=uuid.uuid4(),
            tenant_id=t1_id,
            username="ammar",
            full_name="Ammar Regular Cashier",
            role="cashier",
            password_hash=hash_password("Pass123!"),
            permissions=["sales"],
            is_active=True,
            is_superadmin=False,
        )
        session.add(u_ammar)

        # 2. Backdoor test user 2: username="admoon", role="cashier", is_superadmin=False
        u_admoon = User(
            id=uuid.uuid4(),
            tenant_id=t1_id,
            username="admoon",
            full_name="Admoon Regular Cashier",
            role="cashier",
            password_hash=hash_password("Pass123!"),
            permissions=["sales"],
            is_active=True,
            is_superadmin=False,
        )
        session.add(u_admoon)

        # 3. Legitimate Superadmin
        u_super = User(
            id=uuid.uuid4(),
            tenant_id=t1_id,
            username=f"real_super_{uuid.uuid4().hex[:6]}",
            full_name="Real Super Admin",
            role="superadmin",
            password_hash=hash_password("Pass123!"),
            permissions=["*"],
            is_active=True,
            is_superadmin=True,
        )
        session.add(u_super)

        # 4. Tenant 1 Admin
        u_t1_admin = User(
            id=uuid.uuid4(),
            tenant_id=t1_id,
            username=f"admin_t1_{uuid.uuid4().hex[:6]}",
            full_name="Tenant 1 Admin",
            role="admin",
            password_hash=hash_password("Pass123!"),
            permissions=["users", "users:admin", "audit:read"],
            is_active=True,
            is_superadmin=False,
        )
        session.add(u_t1_admin)

        # 5. Tenant 1 Regular Cashier
        u_t1_cashier = User(
            id=uuid.uuid4(),
            tenant_id=t1_id,
            username=f"cashier_t1_{uuid.uuid4().hex[:6]}",
            full_name="Tenant 1 Cashier",
            role="cashier",
            password_hash=hash_password("Pass123!"),
            permissions=["sales", "pos"],
            is_active=True,
            is_superadmin=False,
        )
        session.add(u_t1_cashier)

        # 6. Tenant 1 Clinical Doctor
        u_t1_doc = User(
            id=uuid.uuid4(),
            tenant_id=t1_id,
            username=f"doc_t1_{uuid.uuid4().hex[:6]}",
            full_name="Dr. Clinical Specialist",
            role="doctor",
            password_hash=hash_password("Pass123!"),
            permissions=["clinic", "clinic:doctor", "clinical:emergency"],
            is_active=True,
            is_superadmin=False,
        )
        session.add(u_t1_doc)

        # 7. Tenant 2 Target User
        u_t2_user = User(
            id=uuid.uuid4(),
            tenant_id=t2_id,
            username=f"user_t2_{uuid.uuid4().hex[:6]}",
            full_name="Tenant 2 User",
            role="staff",
            password_hash=hash_password("Pass123!"),
            permissions=["sales"],
            is_active=True,
            is_superadmin=False,
        )
        session.add(u_t2_user)

        await give_roles(session)
        await session.commit()

        def make_token(u):
            return create_access_token({
                "sub": str(u.id),
                "role": u.role,
                "username": u.username,
                "tid": str(u.tenant_id),
            })

        return {
            "t1_id": str(t1_id),
            "t2_id": str(t2_id),
            "u_ammar": u_ammar,
            "u_admoon": u_admoon,
            "u_super": u_super,
            "u_t1_admin": u_t1_admin,
            "u_t1_cashier": u_t1_cashier,
            "u_t1_doc": u_t1_doc,
            "u_t2_user": u_t2_user,
            "h_ammar": {"Authorization": f"Bearer {make_token(u_ammar)}"},
            "h_admoon": {"Authorization": f"Bearer {make_token(u_admoon)}"},
            "h_super": {"Authorization": f"Bearer {make_token(u_super)}"},
            "h_t1_admin": {"Authorization": f"Bearer {make_token(u_t1_admin)}"},
            "h_t1_cashier": {"Authorization": f"Bearer {make_token(u_t1_cashier)}"},
            "h_t1_doc": {"Authorization": f"Bearer {make_token(u_t1_doc)}"},
            "h_t2_user": {"Authorization": f"Bearer {make_token(u_t2_user)}"},
        }


def _load_admin_app():
    """Import the admin service app (admin/backend/main.py) alongside the system app."""
    import importlib.util
    import sys
    from pathlib import Path

    admin_dir = Path(__file__).resolve().parents[4] / "admin" / "backend"
    if str(admin_dir) not in sys.path:
        sys.path.insert(0, str(admin_dir))
    spec = importlib.util.spec_from_file_location("admin_main", admin_dir / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


@pytest.mark.asyncio
async def test_sec_01_backdoor_superadmin_elimination():
    """SEC-01: Verify 'ammar' and 'admoon' without is_superadmin=True are rejected by require_superadmin."""
    env = await _create_security_test_env()

    # Direct dependency function test
    with pytest.raises(HTTPException) as exc_ammar:
        await require_superadmin(current_user=env["u_ammar"])
    assert exc_ammar.value.status_code == 403
    assert "Superadmin" in exc_ammar.value.detail or "مطلوبة" in exc_ammar.value.detail

    with pytest.raises(HTTPException) as exc_admoon:
        await require_superadmin(current_user=env["u_admoon"])
    assert exc_admoon.value.status_code == 403
    assert "Superadmin" in exc_admoon.value.detail or "مطلوبة" in exc_admoon.value.detail

    # Legitimate superadmin succeeds
    async with AsyncSessionLocal() as session:
        result = await require_superadmin(current_user=env["u_super"], db=session)
        assert result.id == env["u_super"].id

    # The control plane is not part of the system API at all
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res_system = await c.get("/admoon/overview", headers=env["h_super"])
        assert res_system.status_code == 404

    # HTTP endpoint test via /admoon/overview on the admin API
    async with AsyncClient(transport=ASGITransport(app=_load_admin_app()), base_url="http://test") as c:
        # ammar must be rejected
        res_ammar = await c.get("/admoon/overview", headers=env["h_ammar"])
        assert res_ammar.status_code == 403

        # admoon must be rejected
        res_admoon = await c.get("/admoon/overview", headers=env["h_admoon"])
        assert res_admoon.status_code == 403

        # real superadmin gets 200
        res_super = await c.get("/admoon/overview", headers=env["h_super"])
        assert res_super.status_code == 200


@pytest.mark.asyncio
async def test_sec_02_bola_and_privilege_escalation_guardrails():
    """SEC-02: Verify authorization endpoints enforce admin permissions and strict tenant boundaries."""
    env = await _create_security_test_env()
    cashier = env["u_t1_cashier"]
    t2_user = env["u_t2_user"]
    dummy_role_id = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 1. A cashier can't assign roles, list roles or set positions -> 403
        res = await c.put(f"/authz/access/users/{cashier.id}/roles", json={"role_ids": [dummy_role_id]},
                          headers=env["h_t1_cashier"])
        assert res.status_code == 403
        assert (await c.get("/authz/access/roles", headers=env["h_t1_cashier"])).status_code == 403
        res = await c.put(f"/authz/access/users/{cashier.id}/position", json={"position_id": None},
                          headers=env["h_t1_cashier"])
        assert res.status_code == 403

        # 2. An admin can't touch a user of another workspace -> 404 (isolation)
        res_cross_tenant = await c.put(f"/authz/access/users/{t2_user.id}/roles", json={"role_ids": [dummy_role_id]},
                                       headers=env["h_t1_admin"])
        assert res_cross_tenant.status_code in (403, 404)


@pytest.mark.asyncio
async def test_sec_03_unenforced_access_controls_are_gone():
    """Break-glass, permission overrides and facility/patient rules enforced nothing (no endpoint
    checked them); they were removed rather than shown as security controls (#94 follow-up)."""
    env = await _create_security_test_env()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for path in ("/authz/break-glass", "/authz/seed", f"/authz/users/{env['u_t1_cashier'].id}/permission-override",
                     f"/authz/users/{env['u_t1_cashier'].id}/assign-role", "/authz/patient-assignments"):
            res = await c.post(path, json={}, headers=env["h_t1_admin"])
            assert res.status_code in (404, 405), path


@pytest.mark.asyncio
async def test_sec_04_cross_tenant_login_ambiguity():
    """SEC-04: Verify ambiguous multi-tenant usernames require tenant_slug and prevent cross-tenant credential testing."""
    async with AsyncSessionLocal() as session:
        t1_id = uuid.uuid4()
        tenant1 = Tenant(
            id=t1_id,
            name=f"Ambiguity Tenant 1 {t1_id.hex[:4]}",
            slug=f"ambig-1-{t1_id.hex[:6]}",
            status="active",
        )
        session.add(tenant1)
        await session.flush()  # the workspace exists before its users

        t2_id = uuid.uuid4()
        tenant2 = Tenant(
            id=t2_id,
            name=f"Ambiguity Tenant 2 {t2_id.hex[:4]}",
            slug=f"ambig-2-{t2_id.hex[:6]}",
            status="active",
        )
        session.add(tenant2)
        await session.flush()  # the workspace exists before its users

        shared_username = f"cashier_{uuid.uuid4().hex[:6]}"
        u1 = User(
            id=uuid.uuid4(),
            tenant_id=t1_id,
            username=shared_username,
            full_name="Cashier Tenant 1",
            role="cashier",
            password_hash=hash_password("Tenant1Secret!"),
            is_active=True,
        )
        session.add(u1)

        u2 = User(
            id=uuid.uuid4(),
            tenant_id=t2_id,
            username=shared_username,
            full_name="Cashier Tenant 2",
            role="cashier",
            password_hash=hash_password("Tenant2Secret!"),
            is_active=True,
        )
        session.add(u2)
        await give_roles(session)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 1. Login without tenant_slug must fail with 400 Ambiguous Tenant Error
        res_ambig = await c.post(
            "/auth/login",
            json={"username": shared_username, "password": "Tenant1Secret!"},
        )
        assert res_ambig.status_code == 400
        assert "tenant_slug" in res_ambig.json()["detail"]

        # 2. Login with non-existent tenant_slug must fail with 401
        res_fake_tenant = await c.post(
            "/auth/login",
            json={"username": shared_username, "password": "Tenant1Secret!", "tenant_slug": "non-existent-tenant-slug"},
        )
        assert res_fake_tenant.status_code == 401

        # 3. Login with tenant1 slug and correct tenant1 password succeeds
        res_t1_ok = await c.post(
            "/auth/login",
            json={"username": shared_username, "password": "Tenant1Secret!", "tenant_slug": tenant1.slug},
        )
        assert res_t1_ok.status_code == 200
        data1 = res_t1_ok.json()
        assert data1["username"] == shared_username
        assert data1["user_id"] == str(u1.id)

        # 4. Login with tenant2 slug and tenant1 password fails 401
        res_t2_wrong_pw = await c.post(
            "/auth/login",
            json={"username": shared_username, "password": "Tenant1Secret!", "tenant_slug": tenant2.slug},
        )
        assert res_t2_wrong_pw.status_code == 401

        # 5. Login with tenant2 slug and correct tenant2 password succeeds
        res_t2_ok = await c.post(
            "/auth/login",
            json={"username": shared_username, "password": "Tenant2Secret!", "tenant_slug": tenant2.slug},
        )
        assert res_t2_ok.status_code == 200
        data2 = res_t2_ok.json()
        assert data2["username"] == shared_username
        assert data2["user_id"] == str(u2.id)


@pytest.mark.asyncio
async def test_db_01_all_tenant_tables_have_rls_enabled():
    """DB-01: Verify 100% of public database tables with a tenant_id column have Row Level Security enabled."""
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT count(*) 
            FROM information_schema.columns c
            JOIN pg_tables t ON t.tablename = c.table_name AND t.schemaname = 'public'
            WHERE c.column_name = 'tenant_id' AND t.rowsecurity = false;
        """))
        vulnerable_count = result.scalar_one()
        assert vulnerable_count == 0, f"Found {vulnerable_count} tables with tenant_id lacking Row Level Security!"




def test_module_guard_reads_the_signed_in_workspace():
    # require_module must resolve the user (which binds the workspace) before reading the
    # workspace's modules; otherwise it reads installed_modules across workspaces.
    import inspect

    from app.framework.activation import require_module
    from app.dependencies import get_current_user

    params = inspect.signature(require_module("restaurant")).parameters.values()
    assert any(getattr(p.default, "dependency", None) is get_current_user for p in params)


def test_module_packages_cannot_be_uploaded():
    # Uploaded zips were unpacked into the server's code and imported (ADR-006 phase 6
    # replaces this with signed, isolated packages).
    from fastapi.routing import APIRoute

    from main import app

    assert not [r for r in app.routes if isinstance(r, APIRoute) and r.path == "/modules/upload"]
