"""Community module packages (ADR-007): manifests, entities, signing and verification."""
import io
import json
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import main  # noqa: F401  (settings)
from app.framework import package as mzm
from app.framework.manifest import community_manifest_problems, entity_problems

MANIFEST = {
    "id": "acme.visits", "name": "الزيارات", "name_en": "Visits", "version": "1.0.0", "kind": "community",
    "icon": "CalendarCheck", "entities": ["visit"],
    "permissions": [{"id": "acme.visits.view", "name": "عرض الزيارات", "name_en": "View visits"}],
    "menu": [{"entity": "visit", "label": "الزيارات", "permission": "acme.visits.view"}],
    "scopes": ["customers:read", "events:sale.confirmed"],
    "webhooks": {"url": "https://acme.example/mizan", "events": ["sale.confirmed", "record.created"]},
}
VISIT = {
    "id": "visit", "name": "زيارة", "name_en": "Visit", "title": "customer",
    "fields": [{"key": "customer", "type": "reference", "to": "customers", "label": "العميل", "required": True},
               {"key": "on", "type": "date", "label": "التاريخ"},
               {"key": "fee", "type": "money", "label": "الرسوم"},
               {"key": "state", "type": "select", "options": ["مجدولة", "تمت"], "label": "الحالة"}],
    "list": ["on", "customer", "state"],
    "form": {"sections": [{"id": "main", "label": "الزيارة", "fields": ["customer", "on", "fee", "state"]}]},
}


def files(manifest=MANIFEST, entity=VISIT) -> dict[str, bytes]:
    return {"manifest.json": json.dumps(manifest).encode(), "entities/visit.json": json.dumps(entity).encode()}


def developer(name: str = "acme"):
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return raw, mzm.certify(name, "k1", pub)


def test_a_good_module_has_no_problems():
    assert community_manifest_problems(MANIFEST, {"visit"}) == []
    assert entity_problems(VISIT, {"visit"}, set(MANIFEST["scopes"])) == []


@pytest.mark.parametrize("change, expected", [
    ({"id": "visits"}, "id must be"),
    ({"kind": "business"}, "kind must be 'community'"),
    ({"version": "1.0"}, "version must be"),
    ({"scopes": ["customers:read", "money:steal"]}, "unknown scope: money:steal"),
    ({"webhooks": {"url": "http://insecure", "events": []}}, "https://"),
    ({"scopes": ["customers:read"]}, "needs the scope events:sale.confirmed"),
    ({"router": "x.py"}, "'router' isn't allowed"),
    ({"permissions": [{"id": "other.view", "name": "x", "name_en": "x"}]}, "must start with the module id"),
])
def test_manifest_problems(change, expected):
    problems = community_manifest_problems({**MANIFEST, **change}, {"visit"})
    assert any(expected in p for p in problems), problems


def test_entity_problems():
    no_scope = entity_problems(VISIT, {"visit"}, set())
    assert any("needs the scope customers:read" in p for p in no_scope)
    bad = {**VISIT, "fields": [*VISIT["fields"], {"key": "x", "type": "select", "label": "x"}], "list": ["nope"]}
    problems = entity_problems(bad, {"visit"}, {"customers:read"})
    assert any("a select needs options" in p for p in problems) and any("list column nope" in p for p in problems)


def test_signed_packages_verify_and_tampering_is_caught():
    key, cert = developer()
    data = mzm.build(files(), key, cert)
    pkg = mzm.verify(data)
    assert pkg.manifest["id"] == "acme.visits" and set(pkg.entities) == {"visit"} and pkg.developer == "acme"

    # A changed file breaks the signature.
    z = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as w:
        for i in z.infolist():
            body = z.read(i)
            if i.filename == "entities/visit.json":
                body = json.dumps({**VISIT, "name": "مختلف"}).encode()
            w.writestr(i, body)
    with pytest.raises(mzm.PackageError, match="don't match its signature"):
        mzm.verify(out.getvalue())


def test_a_developer_signs_only_their_own_modules():
    key, cert = developer("other")
    with pytest.raises(mzm.PackageError, match="can only sign modules named other"):
        mzm.verify(mzm.build(files(), key, cert))


def test_uncertified_keys_and_unsafe_files_are_refused():
    key, _ = developer()
    stranger = Ed25519PrivateKey.generate()
    fake_cert = "MZD1.eyJ4IjoxfQ." + mzm._b64e(stranger.sign(b"MZD1.eyJ4IjoxfQ"))
    with pytest.raises(mzm.PackageError, match="certificate isn't from Mizan"):
        mzm.verify(mzm.build(files(), key, fake_cert))
    key, cert = developer()
    for bad in ("../evil.json", "server/app.py", "entities/run.sh"):
        with pytest.raises(mzm.PackageError):
            mzm.build({**files(), bad: b"x"}, key, cert)
    with pytest.raises(mzm.PackageError, match="isn't a Mizan module package"):
        mzm.verify(b"not a zip")


def test_the_sdk_ships_the_platforms_validator_and_its_packages_verify(tmp_path):
    """mizan-sdk (sdk/python) must check modules exactly as the platform does, and the packages
    `mizan package` builds must pass the platform's verification."""
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    platform_copy = (repo / "shared/backend/app/framework/manifest.py").read_text()
    assert (repo / "sdk/python/mizan_sdk/manifest.py").read_text() == platform_copy, \
        "sdk/python/mizan_sdk/manifest.py is out of date: copy shared/backend/app/framework/manifest.py over it"

    sys.path.insert(0, str(repo / "sdk/python"))
    try:
        from mizan_sdk.cli import starter
        from mizan_sdk.package import build as sdk_build
    finally:
        sys.path.pop(0)
    files_ = {rel: json.dumps(body, ensure_ascii=False).encode() for rel, body in starter("acme.notes").items()}
    key, cert = developer()
    pkg = mzm.verify(sdk_build(files_, key, cert))
    assert pkg.manifest["id"] == "acme.notes" and set(pkg.entities) == {"item"}
