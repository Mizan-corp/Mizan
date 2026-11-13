"""The developer portal API (ADR-007 D5): accounts, teams, keys → certificates that sign
packages the platform accepts, revocation, CLI tokens."""
import base64
import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def no_rate_limits():
    from website_api.routers import developers

    app.dependency_overrides[developers.signup_limiter] = lambda: None
    app.dependency_overrides[developers.login_limiter] = lambda: None
    yield
    app.dependency_overrides.clear()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def keypair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return raw, _b64(pub)


def module_files(module_id: str) -> dict[str, bytes]:
    manifest = {"id": module_id, "name": "تجربة", "name_en": "Test", "version": "1.0.0", "kind": "community",
                "entities": ["item"], "menu": [{"entity": "item", "label": "سجلات"}], "scopes": []}
    entity = {"id": "item", "name": "سجل", "name_en": "Item", "title": "title",
              "fields": [{"key": "title", "type": "text", "label": "العنوان", "required": True}]}
    return {"manifest.json": json.dumps(manifest, ensure_ascii=False).encode(), "entities/item.json": json.dumps(entity).encode()}


async def test_portal_flow():
    from app.db.base import AsyncSessionLocal
    from app.framework import package as mzm
    from app.platform.developers.service import key_revoked

    tag = uuid.uuid4().hex[:8]
    handle, a_mail, b_mail = f"t{tag}", f"a-{tag}@example.com", f"b-{tag}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/developers/signup", json={"email": a_mail.upper(), "full_name": "مطور أ", "password": "longpass1"})
            assert r.status_code == 201, r.text
            a = {"Authorization": f"Bearer {r.json()['access_token']}"}
            assert (await c.post("/developers/signup", json={"email": a_mail, "full_name": "x y", "password": "longpass1"})).status_code == 409
            assert (await c.post("/developers/login", json={"email": a_mail, "password": "wrong"})).status_code == 401
            b_tok = (await c.post("/developers/signup", json={"email": b_mail, "full_name": "مطور ب", "password": "longpass2"})).json()["access_token"]
            b = {"Authorization": f"Bearer {b_tok}"}
            assert (await c.get("/developers/me")).status_code == 401

            # Teams: handles follow module ids; reserved and taken ones are refused.
            assert (await c.post("/developers/teams", headers=a, json={"handle": "Mizan", "name": "x y"})).status_code == 422
            assert (await c.post("/developers/teams", headers=a, json={"handle": "1abc", "name": "x y"})).status_code == 422
            assert (await c.post("/developers/teams", headers=a, json={"handle": handle, "name": "فريق"})).status_code == 201
            assert (await c.post("/developers/teams", headers=b, json={"handle": handle, "name": "x y"})).status_code == 409
            assert [t["handle"] for t in (await c.get("/developers/me", headers=a)).json()["teams"]] == [handle]
            assert (await c.get(f"/developers/teams/{handle}", headers=b)).status_code == 404  # not a member

            # Members: owners add existing developers; a member can't manage the team.
            assert (await c.post(f"/developers/teams/{handle}/members", headers=a, json={"email": "nobody@example.com"})).status_code == 404
            assert (await c.post(f"/developers/teams/{handle}/members", headers=a, json={"email": b_mail})).status_code == 201
            team = (await c.get(f"/developers/teams/{handle}", headers=b)).json()
            assert team["role"] == "member" and {m["email"] for m in team["members"]} == {a_mail, b_mail}
            me_a = next(m for m in team["members"] if m["email"] == a_mail)
            assert (await c.delete(f"/developers/teams/{handle}/members/{me_a['id']}", headers=b)).status_code == 403
            assert (await c.delete(f"/developers/teams/{handle}/members/{me_a['id']}", headers=a)).status_code == 409  # last owner

            # Keys: a member registers one, its certificate signs packages the platform accepts.
            assert (await c.post(f"/developers/teams/{handle}/keys", headers=b, json={"public_key": "!" * 43})).status_code == 422
            private, public = keypair()
            r = await c.post(f"/developers/teams/{handle}/keys", headers=b, json={"public_key": public, "name": "laptop"})
            assert r.status_code == 201, r.text
            key = r.json()
            assert key["certificate"].startswith("MZD1.") and key["key_id"].startswith(f"{handle}-")
            assert (await c.post(f"/developers/teams/{handle}/keys", headers=a, json={"public_key": public})).status_code == 409
            pkg = mzm.verify(mzm.build(module_files(f"{handle}.notes"), private, key["certificate"]))
            assert pkg.developer == handle and pkg.key_id == key["key_id"]
            with pytest.raises(mzm.PackageError):  # the team can only sign its own namespace
                mzm.verify(mzm.build(module_files("other.notes"), private, key["certificate"]))

            # CLI tokens reach the same API; revoking ends them.
            r = await c.post("/developers/cli-tokens", headers=a, json={"name": "laptop"})
            cli = {"Authorization": f"Bearer {r.json()['token']}"}
            assert r.json()["token"].startswith("mzd_")
            assert (await c.get("/developers/me", headers=cli)).json()["email"] == a_mail
            assert [t["name"] for t in (await c.get("/developers/cli-tokens", headers=cli)).json()["items"]] == ["laptop"]
            assert (await c.delete(f"/developers/cli-tokens/{r.json()['id']}", headers=a)).status_code == 204
            assert (await c.get("/developers/me", headers=cli)).status_code == 401

            # Revoking a key: owners only; installs then refuse its packages.
            assert (await c.post(f"/developers/teams/{handle}/keys/{key['key_id']}/revoke", headers=b)).status_code == 403
            assert (await c.post(f"/developers/teams/{handle}/keys/{key['key_id']}/revoke", headers=a)).status_code == 204
            async with AsyncSessionLocal() as db:
                assert await key_revoked(db, key["key_id"])

            # Signing out and password changes end portal sessions.
            assert (await c.post("/developers/logout", headers=b)).status_code == 204
            assert (await c.get("/developers/me", headers=b)).status_code == 401
            assert (await c.post("/developers/me/password", headers=a,
                                 json={"current_password": "longpass1", "new_password": "newpass99"})).status_code == 204
            assert (await c.get("/developers/me", headers=a)).status_code == 401
            assert (await c.post("/developers/login", json={"email": a_mail, "password": "newpass99"})).status_code == 200
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM developer_teams WHERE handle = :h"), {"h": handle})
            await db.execute(text("DELETE FROM developer_users WHERE email = ANY(:e)"), {"e": [a_mail, b_mail]})
            await db.commit()


async def test_messages_are_english_unless_arabic_is_asked():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        body = {"email": f"nobody-{uuid.uuid4().hex[:6]}@example.com", "password": "wrong-pass"}
        assert (await c.post("/developers/login", json=body)).json()["detail"] == "Wrong email or password"
        ar = await c.post("/developers/login", json=body, headers={"Accept-Language": "ar-EG,ar;q=0.9"})
        assert ar.json()["detail"] == "البريد أو كلمة المرور غير صحيحة"


async def test_marketplace_submission_review_and_store():
    """#105: submit → review (countersign, list) → the store serves a verified package."""
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.db.base import AsyncSessionLocal
    from app.framework import package as mzm
    from app.platform.marketplace import listings
    from app.platform.marketplace.listings import MarketplaceVersion

    tag = uuid.uuid4().hex[:8]
    handle, mail = f"m{tag}", f"m-{tag}@example.com"

    def files(version: str) -> dict[str, bytes]:
        f = module_files(f"{handle}.notes")
        m = json.loads(f["manifest.json"])
        m["version"], m["description"] = version, "دفتر ملاحظات للفريق"
        f["manifest.json"] = json.dumps(m, ensure_ascii=False).encode()
        return f

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = (await c.post("/developers/signup", json={"email": mail, "full_name": "مطور", "password": "longpass1"})).json()["access_token"]
            h = {"Authorization": f"Bearer {tok}"}
            assert (await c.post("/developers/teams", headers=h, json={"handle": handle, "name": "فريق"})).status_code == 201
            private, public = keypair()
            key = (await c.post(f"/developers/teams/{handle}/keys", headers=h, json={"public_key": public})).json()
            v1 = mzm.build(files("1.0.0"), private, key["certificate"])

            # Submit (raw body, as `mizan publish` sends it); the same version again is refused.
            r = await c.post(f"/developers/teams/{handle}/packages", headers=h, content=v1)
            assert r.status_code == 201, r.text
            assert r.json()["status"] == "in_review" and r.json()["item_id"] == f"{handle}.notes"
            assert (await c.post(f"/developers/teams/{handle}/packages", headers=h, content=v1)).status_code == 409
            assert (await c.post(f"/developers/teams/{handle}/packages", headers=h, content=b"not a zip")).status_code == 422
            listed = (await c.get(f"/developers/teams/{handle}/packages", headers=h)).json()
            assert listed["items"] == [] and listed["versions"][0]["status"] == "in_review"

            # A second version can be withdrawn while in review.
            v2 = mzm.build(files("1.1.0"), private, key["certificate"])
            files_form = {"file": ("notes.mzm", v2, "application/octet-stream")}
            assert (await c.post(f"/developers/teams/{handle}/packages", headers=h, files=files_form)).status_code == 201
            assert (await c.delete(f"/developers/teams/{handle}/packages/{handle}.notes/1.1.0", headers=h)).status_code == 204
            assert (await c.delete(f"/developers/teams/{handle}/packages/{handle}.notes/1.1.0", headers=h)).status_code == 409

        # The Mizan team approves 1.0.0: countersigned and listed; the store serves it, verified.
        async with AsyncSessionLocal() as db:
            v = await db.scalar(select(MarketplaceVersion).where(MarketplaceVersion.item_id == f"{handle}.notes",
                                                                MarketplaceVersion.version == "1.0.0"))
            item = await listings.approve(db, v, uuid.uuid4())
            await db.commit()
            assert v.countersignature.startswith("MZP1.") and item.status == "listed" and item.current_version == "1.0.0"
            assert any(i["id"] == f"{handle}.notes" for i in await listings.store(db, "community", "ملاحظات"))
            got, pkg = await listings.listed_package(db, f"{handle}.notes")
            assert pkg.manifest["version"] == "1.0.0" and pkg.developer == handle

            # Tampered bytes are refused, and an older version can't be submitted after a listing.
            good = v.package
            v.package = good[:-1] + bytes([good[-1] ^ 1])
            await db.flush()
            with pytest.raises(HTTPException):
                await listings.listed_package(db, f"{handle}.notes")
            await db.rollback()

            await listings.set_listed(db, f"{handle}.notes", False, "test")
            await db.commit()
            assert not any(i["id"] == f"{handle}.notes" for i in await listings.store(db))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            v0 = mzm.build(files("0.9.0"), private, key["certificate"])
            assert (await c.post(f"/developers/teams/{handle}/packages", headers=h, content=v0)).status_code == 409
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM marketplace_items WHERE id = :i"), {"i": f"{handle}.notes"})
            await db.execute(text("DELETE FROM marketplace_versions WHERE item_id = :i"), {"i": f"{handle}.notes"})
            await db.execute(text("DELETE FROM developer_teams WHERE handle = :h"), {"h": handle})
            await db.execute(text("DELETE FROM developer_users WHERE email = :e"), {"e": mail})
            await db.commit()
