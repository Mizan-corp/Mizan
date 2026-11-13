"""Marketplace review in the admin panel (#105): Needs you, details, approve (listed), delist."""
import base64
import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from main import app
from tests.test_owners import admin_headers

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


async def submitted(handle: str) -> uuid.UUID:
    """A team, a certified key and a submitted module package, made directly."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from app.framework import package as mzm
    from app.platform.developers.models import DeveloperTeam
    from app.platform.marketplace import listings

    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    cert = mzm.certify(handle, f"{handle}-test", pub)
    manifest = {"id": f"{handle}.visits", "name": "الزيارات", "name_en": "Visits", "version": "1.0.0", "kind": "community",
                "entities": ["visit"], "menu": [{"entity": "visit", "label": "الزيارات"}], "scopes": ["customers:read"]}
    entity = {"id": "visit", "name": "زيارة", "name_en": "Visit", "title": "title",
              "fields": [{"key": "title", "type": "text", "label": "العنوان", "required": True}]}
    data = mzm.build({"manifest.json": json.dumps(manifest, ensure_ascii=False).encode(),
                      "entities/visit.json": json.dumps(entity).encode()}, raw, cert)
    async with AsyncSessionLocal() as db:
        team = DeveloperTeam(handle=handle, name="فريق")
        db.add(team)
        await db.flush()
        v = await listings.submit(db, team, None, data)
        await db.commit()
        return v.id


async def test_review_approve_and_delist():
    handle = f"r{uuid.uuid4().hex[:8]}"
    version_id = await submitted(handle)
    h = await admin_headers()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            attention = (await c.get("/admoon/overview", headers=h)).json()["attention"]
            assert any(a["kind"] == "marketplace_review" and a["version_id"] == str(version_id) for a in attention)
            detail = (await c.get(f"/admoon/marketplace/submissions/{version_id}", headers=h)).json()
            assert detail["developer"] == handle and detail["manifest"]["scopes"] == ["customers:read"]
            assert {f["name"] for f in detail["files"]} == {"manifest.json", "entities/visit.json"}
            assert "summary" in detail and detail["listed_version"] is None

            assert (await c.post(f"/admoon/marketplace/submissions/{version_id}/reject", headers=h, json={})).status_code == 422
            r = await c.post(f"/admoon/marketplace/submissions/{version_id}/approve", headers=h, json={"note": "ok"})
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "approved" and r.json()["listing"]["status"] == "listed"
            assert (await c.post(f"/admoon/marketplace/submissions/{version_id}/approve", headers=h, json={})).status_code == 409

            item_id = f"{handle}.visits"
            assert item_id in {i["id"] for i in (await c.get("/admoon/marketplace/items", headers=h)).json()["items"]}
            assert (await c.post(f"/admoon/marketplace/items/{item_id}/delist", headers=h, json={})).status_code == 422
            r = await c.post(f"/admoon/marketplace/items/{item_id}/delist", headers=h, json={"note": "unsafe"})
            assert r.json()["status"] == "delisted"
            assert (await c.post(f"/admoon/marketplace/items/{item_id}/relist", headers=h, json={})).json()["status"] == "listed"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM marketplace_items WHERE id = :i"), {"i": f"{handle}.visits"})
            await db.execute(text("DELETE FROM marketplace_versions WHERE item_id = :i"), {"i": f"{handle}.visits"})
            await db.execute(text("DELETE FROM developer_teams WHERE handle = :h"), {"h": handle})
            await db.commit()
