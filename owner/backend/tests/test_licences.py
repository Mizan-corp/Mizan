"""Single-device and LAN workspaces: licences, check-ins and the on-premise licence gate (ADR-005)."""
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.platform.licensing import keys as licensing
from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.platform.billing.models import BillingInvoice
from app.platform.licensing.models import Licence
from app.platform.tenancy.models import Tenant
from app.platform.billing.services.subscriptions import activate_invoice, new_invoice
from main import app
from tests.test_owner_api import client, login, make_owner  # noqa: F401  (fixtures/helpers)

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


async def new_on_prem(c: AsyncClient, h: dict, mode: str = "lan") -> dict:
    r = await c.post("/account/workspaces", headers=h, json={"name": f"Branch {uuid.uuid4().hex[:6]}", "sector": "retail", "mode": mode})
    assert r.status_code == 201, r.text
    return r.json()


# ─── Keys ──────────────────────────────────────────────────────────────────


def test_keys_sign_verify_and_reject_tampering():
    key = licensing.sign({"lid": "x", "valid_until": (datetime.now(UTC) + timedelta(days=1)).isoformat()})
    assert key.startswith("MZN1.")
    assert licensing.verify(key)["lid"] == "x"
    prefix, body, sig = key.split(".")
    forged = licensing._b64e(b'{"lid":"x","valid_until":"2099-01-01T00:00:00+00:00"}')
    # Flip a real byte of the signature. (Replacing its last characters with "AA" was a no-op
    # about 1 time in 256: the last base64 character carries only 2 bits.)
    raw = bytearray(licensing._b64d(sig))
    raw[0] ^= 0x01
    tampered_sig = licensing._b64e(bytes(raw))
    for bad in (f"{prefix}.{forged}.{sig}", f"{prefix}.{body}.{tampered_sig}", "MZN2." + body + "." + sig, "nonsense"):
        with pytest.raises(licensing.LicenceError):
            licensing.verify(bad)
    assert licensing.is_current({"valid_until": (datetime.now(UTC) + timedelta(hours=1)).isoformat()})
    assert not licensing.is_current({"valid_until": (datetime.now(UTC) - timedelta(hours=1)).isoformat()})


# ─── Cloud side ────────────────────────────────────────────────────────────


async def test_on_premise_workspace_is_registered_with_a_licence():
    owner, _, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        w = await new_on_prem(c, h, "desktop")
        assert w["deployment_mode"] == "desktop" and w["licence"]["status"] == "active" and w["users_count"] == 0
        # Nothing to open in the cloud; a download instead.
        assert (await c.post(f"/account/workspaces/{w['id']}/open", headers=h)).status_code == 409
        d = (await c.get(f"/account/workspaces/{w['id']}/download", headers=h)).json()
        claims = licensing.verify(d["licence_key"])
        assert claims["workspace"]["id"] == w["id"] and claims["mode"] == "desktop"
        assert claims["owner"]["login"] == owner.login
    # Registered only: no users and no data in the cloud.
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        assert await db.scalar(text("SELECT count(*) FROM users WHERE tenant_id = :t"), {"t": w["id"]}) == 0


async def test_paying_extends_the_licence():
    owner, _, _ = await make_owner()
    async with client() as c:
        w = await new_on_prem(c, await login(c, owner))
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        tenant = await db.get(Tenant, uuid.UUID(w["id"]))
        inv: BillingInvoice = await new_invoice(db, tenant, plan="pro", cycle="annual", method="bank")
        await activate_invoice(db, inv, reference="test")
        await db.commit()
        lic = await db.scalar(text("SELECT valid_until FROM licences WHERE tenant_id = :t"), {"t": w["id"]})
        assert lic == inv.period_end


async def test_check_in_records_the_install_and_renews_the_key():
    owner, _, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        w = await new_on_prem(c, h)
        key = (await c.get(f"/account/workspaces/{w['id']}/download", headers=h)).json()["licence_key"]
        install = uuid.uuid4()

        async with AsyncSessionLocal() as db:  # the owner pays: the licence moves on a year
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            lic = await db.scalar(text("SELECT id FROM licences WHERE tenant_id = :t"), {"t": w["id"]})
            row = await db.get(Licence, lic)
            row.valid_until = datetime.now(UTC) + timedelta(days=365)
            await db.commit()

        r = await c.post("/installations/check-in", json={"licence_key": key, "installation_id": str(install),
                                                           "hostname": "till-1", "os": "Windows 11", "app_version": "1.0.0"})
        assert r.status_code == 200 and r.json()["status"] == "active"
        renewed = licensing.verify(r.json()["licence_key"])
        assert datetime.fromisoformat(renewed["valid_until"]) > datetime.now(UTC) + timedelta(days=300)
        detail = (await c.get(f"/account/workspaces/{w['id']}", headers=h)).json()
        assert [i["hostname"] for i in detail["installations"]] == ["till-1"]

        # Revoked → the install is told so and gets no key.
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("UPDATE licences SET revoked_at = now() WHERE tenant_id = :t"), {"t": w["id"]})
            await db.commit()
        r = await c.post("/installations/check-in", json={"licence_key": key, "installation_id": str(install)})
        assert r.json() == {"status": "revoked", "valid_until": r.json()["valid_until"], "licence_key": None, "update": None}

        # Forged keys are refused.
        assert (await c.post("/installations/check-in", json={"licence_key": key[:-4] + "AAAA", "installation_id": str(install)})).status_code == 401


# ─── Install side: the licence gate ────────────────────────────────────────


async def test_server_mode_is_read_only_without_a_current_licence(tmp_path, monkeypatch):
    from app.onprem import server, state

    monkeypatch.setattr(settings, "MIZAN_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MIZAN_LICENCE", "")
    api = FastAPI()

    @api.post("/products")
    async def write():
        return {"ok": True}

    @api.get("/products")
    async def read():
        return {"ok": True}

    @api.post("/auth/login")
    async def sign_in():
        return {"ok": True}

    root = server.build_server_app(api)
    transport = ASGITransport(app=root)
    async with AsyncClient(transport=transport, base_url="http://install") as c:
        # No licence: reading and signing in work, writing doesn't.
        assert (await c.get("/api/products")).status_code == 200
        assert (await c.post("/api/auth/login")).status_code == 200
        r = await c.post("/api/products")
        assert r.status_code == 403 and r.json()["code"] == "licence_read_only"

        def key(days: int) -> str:
            return licensing.sign({"lid": "l", "workspace": {"id": "w"}, "mode": "lan",
                                   "valid_until": (datetime.now(UTC) + timedelta(days=days)).isoformat()})

        state.save_licence_key(key(30))
        assert (await c.post("/api/products")).status_code == 200
        state.save_licence_key(key(-1))
        assert (await c.post("/api/products")).status_code == 403
        state.save_licence_key(key(30))
        state.update_state(revoked=True)
        assert (await c.post("/api/products")).status_code == 403


def test_a_key_for_another_workspace_is_refused(tmp_path, monkeypatch):
    from app.onprem import licence, state

    monkeypatch.setattr(settings, "MIZAN_DATA_DIR", str(tmp_path))
    until = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    state.save_licence_key(licensing.sign({"lid": "a", "workspace": {"id": "one"}, "valid_until": until}))
    with pytest.raises(licensing.LicenceError):
        licence.accept_key(licensing.sign({"lid": "b", "workspace": {"id": "two"}, "valid_until": until}))
    assert licence.accept_key(licensing.sign({"lid": "a", "workspace": {"id": "one"}, "valid_until": until}))


assert app  # the owner API is importable with the installations router


def test_published_installers(monkeypatch):
    from app.platform.updates.releases import published_installers

    monkeypatch.delenv("MIZAN_INSTALLERS", raising=False)
    assert published_installers("desktop") == []
    monkeypatch.setenv("MIZAN_INSTALLERS", "not json")
    assert published_installers("lan") == []
    monkeypatch.setenv("MIZAN_INSTALLERS", '{"windows": {"url": "https://x/MizanSetup.exe", "version": "1.0.0"},'
                                           ' "linux": {"url": "https://x/MizanSetup"}, "mac": {"url": "https://x/m"}}')
    # The same setup installs both modes on both platforms.
    for mode in ("desktop", "lan"):
        assert [i["platform"] for i in published_installers(mode)] == ["windows", "linux"]


# ─── Updates for installed servers (#89) ───────────────────────────────────

RELEASES = ('{"windows": {"url": "https://x/MizanSetup-1.2.0-windows.exe", "version": "1.2.0",'
            ' "payload_url": "https://x/payload-1.2.0-windows.zip", "payload_sha256": "AB" ,"notes": "Faster reports"},'
            ' "linux": {"url": "https://x/MizanSetup-1.2.0-linux", "version": "1.2.0"}}')


def test_release_offers_are_signed_and_never_pass_as_licences(monkeypatch):
    from app.platform.updates.releases import update_offer

    monkeypatch.setenv("MIZAN_INSTALLERS", RELEASES)
    offer = update_offer("Windows 11", "1.0.1")
    assert offer["version"] == "1.2.0"
    release = licensing.verify(offer["release"], prefix=licensing.RELEASE_PREFIX)
    assert release == {"version": "1.2.0", "platform": "windows", "url": "https://x/payload-1.2.0-windows.zip",
                       "sha256": "ab", "notes": "Faster reports"}
    with pytest.raises(licensing.LicenceError):
        licensing.verify(offer["release"])  # not a licence
    tampered = offer["release"].replace(offer["release"].split(".")[1], licensing._b64e(b'{"version":"9.9.9"}'))
    with pytest.raises(licensing.LicenceError):
        licensing.verify(tampered, prefix=licensing.RELEASE_PREFIX)
    # Up to date, no payload published for the platform, or an unknown system: nothing offered.
    assert update_offer("Windows 10", "1.2.0") is None
    assert update_offer("Linux 6.8", "1.0.0") is None
    assert update_offer(None, "1.0.0") is None


async def test_check_in_offers_newer_releases(monkeypatch):
    monkeypatch.setenv("MIZAN_INSTALLERS", RELEASES)
    owner, _, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        w = await new_on_prem(c, h)
        key = (await c.get(f"/account/workspaces/{w['id']}/download", headers=h)).json()["licence_key"]
        body = {"licence_key": key, "installation_id": str(uuid.uuid4()), "os": "Windows 11", "app_version": "1.0.1"}
        offer = (await c.post("/installations/check-in", json=body)).json()["update"]
        assert offer["version"] == "1.2.0"
        # The owner panel says which computer is behind.
        detail = (await c.get(f"/account/workspaces/{w['id']}", headers=h)).json()
        assert [i["update_to"] for i in detail["installations"]] == ["1.2.0"]
        current = (await c.post("/installations/check-in", json={**body, "app_version": "1.2.0"})).json()
        assert current["update"] is None


def test_the_install_keeps_only_genuine_newer_offers(monkeypatch, tmp_path):
    from app.onprem import checkin, state
    from app.platform.updates.releases import update_offer

    monkeypatch.setattr(settings, "MIZAN_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(checkin, "APP_VERSION", "1.0.1")
    monkeypatch.setenv("MIZAN_INSTALLERS", RELEASES)
    offer = update_offer("Windows 11", "1.0.1")
    checkin._remember_update(offer)
    assert state.read_state()["update_available"]["version"] == "1.2.0"
    forged = {"version": "1.3.0", "release": offer["release"][:-6] + "AAAAAA"}
    checkin._remember_update(forged)
    assert state.read_state()["update_available"] is None
    checkin._remember_update(None)  # up to date
    assert state.read_state()["update_available"] is None
