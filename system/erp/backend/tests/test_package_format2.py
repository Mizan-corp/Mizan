"""Step 9c: format 2 signs the package kind; format 1 packages are still read."""
import hashlib
import io
import json
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import main  # noqa: F401  (settings)
from app.framework import package as mzm


MANIFEST = {
    "id": "acme.visits", "name": "الزيارات", "name_en": "Visits", "version": "1.0.0", "kind": "community",
    "icon": "CalendarCheck", "entities": ["visit"],
    "permissions": [{"id": "acme.visits.view", "name": "عرض الزيارات", "name_en": "View visits"}],
    "menu": [{"entity": "visit", "label": "الزيارات", "permission": "acme.visits.view"}],
    "scopes": ["customers:read"],
}
VISIT = {
    "id": "visit", "name": "زيارة", "name_en": "Visit", "title": "customer",
    "fields": [{"key": "customer", "type": "reference", "to": "customers", "label": "العميل", "required": True},
               {"key": "on", "type": "date", "label": "التاريخ"}],
    "list": ["on", "customer"],
    "form": {"sections": [{"id": "main", "label": "الزيارة", "fields": ["customer", "on"]}]},
}


def files() -> dict[str, bytes]:
    return {"manifest.json": json.dumps(MANIFEST).encode(), "entities/visit.json": json.dumps(VISIT).encode()}


def _developer():
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, raw, mzm.certify("acme", "k1", pub)


def _zip(content: dict[str, bytes], signature: dict) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, body in content.items():
            z.writestr(name, body)
        z.writestr("SIGNATURE", json.dumps(signature))
    return out.getvalue()


def _signed(key, certificate, content, fmt, kind="community", signed_kind=None):
    hashes = {n: hashlib.sha256(b).hexdigest() for n, b in content.items()}
    body = {"format": fmt, "module": "acme.visits", "version": "1.0.0", "files": hashes}
    if fmt >= 2:
        body["kind"] = signed_kind if signed_kind is not None else kind
    sig = key.sign(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    out = {"format": fmt, "module": "acme.visits", "version": "1.0.0", "files": hashes,
           "certificate": certificate, "signature": mzm._b64e(sig)}
    if fmt >= 2:
        out["kind"] = kind
    return _zip(content, out)


def test_build_writes_format_2_with_the_kind():
    _, raw, cert = _developer()
    data = mzm.build(files(), raw, cert)
    _, sig = mzm.read_unverified(data)
    assert sig["format"] == 2 and sig["kind"] == "community"
    assert mzm.verify(data).manifest["id"] == "acme.visits"


def test_a_format_1_package_is_still_accepted():
    key, _, cert = _developer()
    assert mzm.verify(_signed(key, cert, files(), 1)).manifest["id"] == "acme.visits"


def test_the_kind_is_covered_by_the_signature():
    key, _, cert = _developer()
    data = _signed(key, cert, files(), 2)
    content, sig = mzm.read_unverified(data)
    forged = _zip(content, {**sig, "kind": "theme"})
    with pytest.raises(mzm.PackageError):
        mzm.verify(forged)


def test_a_signed_kind_that_disagrees_with_the_manifest_is_refused():
    key, _, cert = _developer()
    data = _signed(key, cert, files(), 2, kind="theme")
    with pytest.raises(mzm.PackageError, match="kind"):
        mzm.verify(data)


def test_an_unknown_format_is_refused():
    key, _, cert = _developer()
    data = _signed(key, cert, files(), 3)
    with pytest.raises(mzm.PackageError):
        mzm.verify(data)
