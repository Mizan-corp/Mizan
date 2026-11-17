"""Medical images (#44): upload limits and types, private storage, short-lived signed links that
re-check access, expire and refuse tampering."""
import base64
import os
import time

import pytest

from app.activities.healthcare.modules.healthcare_clinic import media
from app.activities.healthcare.modules.healthcare_clinic.routes import imaging
from app.framework import files, signed
from tests.test_clinic_patient_access import _book, _client, _env, _patient, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 200
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 100
DCM = b"\x00" * 128 + b"DICM" + b"\x02\x00\x00\x00UL\x04\x00" + b"\x00" * 64


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def private_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PRIVATE_UPLOAD_DIR", str(tmp_path / "private"))
    monkeypatch.setattr(files, "_private_root", None)
    yield tmp_path / "private"
    files._private_root = None


def test_types_are_read_from_the_bytes():
    assert imaging.sniff(JPEG, "x.png") == "image/jpeg"
    assert imaging.sniff(PNG, "x") == "image/png"
    assert imaging.sniff(WEBP, "x") == "image/webp"
    assert imaging.sniff(DCM[:132], "scan") == "application/dicom"
    assert imaging.sniff(b"\x08\x00\x05\x00CS\x0a\x00", "old.dcm") == "application/dicom"
    assert imaging.sniff(b"<svg xmlns='http://www.w3.org/2000/svg'>", "x.jpg") is None
    assert imaging.sniff(b"%PDF-1.7", "x.png") is None
    assert imaging.sniff(b"MZ\x90\x00", "x.dcm") is None


async def test_upload_view_and_links(private_dir, monkeypatch):
    env = await _env()
    h = env["h"]
    async with _client() as c:
        pid = await _patient(c, env, "مريض الأشعة")
        assert (await _book(c, env, pid, "doc_a")).status_code == 200

        def up(content, name="chest.jpg", ctype="image/jpeg", who="doc_a", **form):
            return c.post(f"/clinic/patients/{pid}/images", headers=h[who],
                          files={"file": (name, content, ctype)}, data={"modality": "XR", **form})

        # Not on the care team, or not a clinician: refused (upload and list).
        for who in ("doc_b", "reception", "lab"):
            assert (await up(JPEG, who=who)).status_code == 403, who
            assert (await c.get(f"/clinic/patients/{pid}/images", headers=h[who])).status_code == 403, who
        # Types: decided by the bytes, not the declared type or the name.
        assert (await up(b"<svg onload='alert(1)'></svg>", "x.jpg")).status_code == 415
        assert (await up(b"%PDF-1.7 ...", "scan.png", "image/png")).status_code == 415
        assert (await up(JPEG, modality="PET")).status_code == 422
        assert (await up(b"")).status_code == 400
        # Size: over the limit is refused.
        monkeypatch.setattr(imaging, "MAX_BYTES", 150)
        assert (await up(JPEG)).status_code == 413
        monkeypatch.setattr(imaging, "MAX_BYTES", 50 * 1024 * 1024)

        r = await up(JPEG, notes="أشعة صدر")
        assert r.status_code == 200, r.text
        img = r.json()
        assert img["content_type"] == "image/jpeg" and img["size"] == len(JPEG) and not img["is_dicom"]
        dcm = await up(DCM, "ct_head.dcm", "application/octet-stream", modality="CT")
        assert dcm.status_code == 200 and dcm.json()["is_dicom"]
        assert (await up(PNG, "us.png", "image/png", modality="US")).status_code == 200

        key = (await _sql("SELECT file_path FROM clinic_images WHERE id = :i", i=img["id"]))[0][0]
        assert key.startswith("private:") and (private_dir / key.removeprefix("private:")).read_bytes() == JPEG
        assert "file_path" not in img

        listed = (await c.get(f"/clinic/patients/{pid}/images", headers=h["doc_a"])).json()
        assert len(listed) == 3 and all(x["url"].startswith("/clinic/media/") for x in listed)

        # The link serves the file without the session, and logs the read.
        got = await c.get(img["url"])
        assert got.status_code == 200 and got.content == JPEG and got.headers["content-type"] == "image/jpeg"
        assert got.headers["cache-control"].startswith("private")
        d = await c.get(dcm.json()["url"])
        assert d.status_code == 200 and d.headers["content-disposition"].startswith("attachment") and d.content == DCM
        logged = await _sql("SELECT count(*) FROM clinic_access_log WHERE patient_id = :p AND resource = 'image'", p=pid)
        assert logged[0][0] == 2

        # Tampered: refused. Pointing another user's token at the file: refused (signature).
        token = img["url"].rsplit("/", 1)[1]
        payload, mac = token.split(".")
        assert (await c.get(f"/clinic/media/{payload}.{('B' if mac[0] == 'A' else 'A') + mac[1:]}")).status_code == 403
        forged = signed.sign("other-purpose", {"k": "image", "id": img["id"], "u": str(env["users"]["doc_a"].id),
                                               "t": env["tenant_id"]}, 300)
        assert (await c.get(f"/clinic/media/{forged}")).status_code == 403
        # Expired: 410.
        old = signed.sign(media.PURPOSE, {"k": "image", "id": img["id"], "u": str(env["users"]["doc_a"].id),
                                          "t": env["tenant_id"]}, media.LINK_SECONDS, now=time.time() - 3600)
        assert (await c.get(f"/clinic/media/{old}")).status_code == 410
        # A valid link for someone without access (doc_b): refused at serving time too.
        theirs = signed.sign(media.PURPOSE, {"k": "image", "id": img["id"], "u": str(env["users"]["doc_b"].id),
                                             "t": env["tenant_id"]}, 300)
        assert (await c.get(f"/clinic/media/{theirs}")).status_code == 403
        assert (await c.get(f"/clinic/images/{img['id']}/link", headers=h["doc_b"])).status_code == 403

        # The public /uploads mount never sees it.
        assert (await c.get("/uploads/" + key.removeprefix("private:"))).status_code == 404

        # Deleting removes the file and the record.
        assert (await c.delete(f"/clinic/images/{img['id']}", headers=h["doc_a"])).status_code == 204
        assert not (private_dir / key.removeprefix("private:")).exists()
        assert (await c.get(img["url"])).status_code == 404
