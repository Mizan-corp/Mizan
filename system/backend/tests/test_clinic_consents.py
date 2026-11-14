"""Consent forms (#43): signed by a clinician who reaches the record, signature in the private
store behind a short-lived signed link, PDF export; signed links (#43, #44) refuse tampering and expiry."""
import base64
import os
import time

import pytest

from app.framework import files, signed
from tests.test_clinic_patient_access import _book, _client, _env, _patient, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
SIGNATURE = "data:image/png;base64," + base64.b64encode(PNG).decode()


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


def test_signed_tokens_refuse_tampering_other_purposes_and_expiry():
    token = signed.sign("clinic-media", {"k": "image", "id": "x"}, 60)
    assert signed.verify("clinic-media", token)["id"] == "x"
    payload, mac = token.split(".")
    forged = base64.urlsafe_b64encode(b'{"k":"image","id":"y","exp":9999999999}').rstrip(b"=").decode()
    for bad in (f"{forged}.{mac}", f"{payload}.{mac[:-2]}xx", "nonsense", f"{payload}.{mac}.x"):
        with pytest.raises(signed.InvalidToken):
            signed.verify("clinic-media", bad)
    with pytest.raises(signed.InvalidToken):
        signed.verify("other-purpose", token)
    old = signed.sign("clinic-media", {"id": "x"}, 60, now=time.time() - 120)
    with pytest.raises(signed.ExpiredToken):
        signed.verify("clinic-media", old)


async def test_consent_signed_viewed_and_exported_by_the_care_team_only(private_dir):
    env = await _env()
    h = env["h"]
    async with _client() as c:
        pid = await _patient(c, env, "مريض الموافقة")
        assert (await _book(c, env, pid, "doc_a")).status_code == 200
        body = {"kind": "surgery", "title": "استئصال الزائدة الدودية", "signer_name": "منى حسن", "signer_relation": "guardian",
                "body": "أوافق على إجراء العملية بعد شرح المخاطر والبدائل.\nأقر بأنني فهمت ما سبق.", "signature_png": SIGNATURE}

        # Not on the care team, or not a clinician: refused.
        for who in ("doc_b", "reception", "lab"):
            assert (await c.post(f"/clinic/patients/{pid}/consents", json=body, headers=h[who])).status_code == 403, who
            assert (await c.get(f"/clinic/patients/{pid}/consents", headers=h[who])).status_code == 403, who
        # The signature must be a PNG from the pad.
        bad = await c.post(f"/clinic/patients/{pid}/consents", json={**body, "signature_png": "data:image/svg+xml;base64,PHN2Zz4="},
                           headers=h["doc_a"])
        assert bad.status_code == 400
        bad = await c.post(f"/clinic/patients/{pid}/consents", json={**body, "signature_png": "data:image/png;base64,"
                                                                     + base64.b64encode(b"not a png").decode()}, headers=h["doc_a"])
        assert bad.status_code == 400

        r = await c.post(f"/clinic/patients/{pid}/consents", json=body, headers=h["doc_a"])
        assert r.status_code == 200, r.text
        consent = r.json()
        assert consent["status"] == "active" and consent["witness_name"] == "د. أحمد الفريق"
        assert "signature_path" not in consent
        key = (await _sql("SELECT signature_path FROM clinic_consent_forms WHERE id = :i", i=consent["id"]))[0][0]
        assert key.startswith("private:") and "/uploads/" not in key
        stored = private_dir / key.removeprefix("private:")
        assert stored.read_bytes() == PNG  # on disk, not base64 in the row

        listed = (await c.get(f"/clinic/patients/{pid}/consents", headers=h["doc_a"])).json()
        assert [x["id"] for x in listed] == [consent["id"]]

        # The signature: a short-lived link, served after the access check, logged.
        assert (await c.get(f"/clinic/consents/{consent['id']}/signature-link", headers=h["doc_b"])).status_code == 403
        link = (await c.get(f"/clinic/consents/{consent['id']}/signature-link", headers=h["doc_a"])).json()
        img = await c.get(link["url"])  # no session: the token stands in for it
        assert img.status_code == 200 and img.content == PNG and img.headers["content-type"] == "image/png"
        assert (await c.get(link["url"][:-3] + "abc")).status_code == 403
        logged = await _sql("SELECT count(*) FROM clinic_access_log WHERE patient_id = :p AND resource = 'signature'", p=pid)
        assert logged[0][0] == 1

        # The PDF: Arabic, with the signature.
        pdf = await c.get(f"/clinic/consents/{consent['id']}/pdf", headers=h["doc_a"])
        assert pdf.status_code == 200
        if pdf.headers["content-type"] == "application/pdf":
            assert pdf.content.startswith(b"%PDF") and len(pdf.content) > 2000
        else:  # no WeasyPrint system libraries: the printable page
            assert "منى حسن" in pdf.text and "data:image/png;base64," in pdf.text
        assert (await c.get(f"/clinic/consents/{consent['id']}/pdf", headers=h["doc_b"])).status_code == 403

        # Revoked, never deleted; the link stops working once the doctor leaves the care team.
        assert (await c.post(f"/clinic/consents/{consent['id']}/revoke", json={"reason": "تراجع ولي الأمر"},
                             headers=h["doc_a"])).json()["status"] == "revoked"
        assert (await c.post(f"/clinic/consents/{consent['id']}/revoke", json={"reason": "مرة أخرى"},
                             headers=h["doc_a"])).status_code == 409
        await _sql("UPDATE clinic_care_team SET ended_at = now() WHERE patient_id = :p", p=pid)
        assert (await c.get(link["url"])).status_code == 403


def test_page_renders_arabic_with_the_signature():
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.activities.healthcare.modules.healthcare_clinic.routes.consents import consent_html

    c = SimpleNamespace(consent_ref="CNS-1", title="عملية <b>", body="سطر أول\nسطر ثان", kind="surgery", signer_relation="self",
                        signer_name="منى", witness_name="د. أحمد", signed_at=datetime.now(UTC), revoked_at=None, revoke_reason="")
    p = SimpleNamespace(full_name="مريض", patient_mrn="MRN-1", national_id="1")
    page = consent_html(c, p, PNG, "عيادة")
    assert 'dir="rtl"' in page and "&lt;b&gt;" in page and base64.b64encode(PNG).decode() in page
    assert "NotoSansArabic-Regular.ttf" in page
