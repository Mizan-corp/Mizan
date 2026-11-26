"""Activity packages (ADR-010 D2): a whole business activity, declarative, signed like modules,
checked against Mizan's own modules, screens, widgets, records and themes."""
import copy
import json
import sys
from pathlib import Path

import pytest

import main  # noqa: F401
from app.framework import package as mzm
from tests.test_community_packages import developer, files

REPO = Path(__file__).resolve().parents[4]


def starter() -> dict[str, dict]:
    sys.path.insert(0, str(REPO / "sdk/python"))
    try:
        from mizan_sdk.cli import activity_starter
    finally:
        sys.path.pop(0)
    return activity_starter("acme.laundry")


def build(body: dict[str, dict]) -> bytes:
    key, cert = developer()
    return mzm.build({k: json.dumps(v, ensure_ascii=False).encode() for k, v in body.items()}, key, cert)


def test_the_sdks_starter_activity_is_a_valid_signed_package():
    pkg = mzm.verify(build(starter()))
    assert pkg.kind == "activity" and pkg.developer == "acme" and pkg.manifest["id"] == "acme.laundry"
    assert "modules/acme.laundry_orders/entities/order.json" in pkg.files


@pytest.mark.parametrize("change, problem", [
    (lambda b: b["manifest.json"]["modules"].append("teleport"), "unknown module 'teleport'"),
    (lambda b: b["manifest.json"]["menu"][0]["items"].append({"screen": "pos.nope", "label": "x"}), "unknown screen 'pos.nope'"),
    (lambda b: b["manifest.json"]["menu"][0]["items"].append({"screen": "acme.laundry_orders/visit", "label": "x"}), "unknown screen"),
    (lambda b: b["manifest.json"]["dashboard"].append("pos.nothing"), "unknown widget 'pos.nothing'"),
    (lambda b: b["manifest.json"].update(theme="acme.missing"), "neither one of its themes nor Mizan's"),
    (lambda b: b["manifest.json"].update(family="space"), "family must be one of"),
    (lambda b: b["variants/pos/variant.json"]["fields"].update(invoice_banner=[{"key": "x", "label": "x"}]), "pos has no record 'invoice_banner'"),
    (lambda b: b.update({"variants/acme.laundry_orders/variant.json": {"module": "acme.laundry_orders"}}), "can't contain variants/acme.laundry_orders"),
    (lambda b: b["seed/orders.json"]["records"].append({"colour": "red"}), "records may only use order's fields"),
    (lambda b: b["themes/fresh/theme.json"].update(id="other.fresh"), "an activity's themes are named acme."),
    (lambda b: b.update({"modules/other.things/manifest.json": {**b["modules/acme.laundry_orders/manifest.json"], "id": "other.things"}}),
     "an activity's modules are named acme."),
])
def test_activity_packages_refuse_wrong_references(change, problem):
    body = copy.deepcopy(starter())
    change(body)
    with pytest.raises(mzm.PackageError, match=problem.replace("(", r"\(").replace(".", r"\.").replace("'", "'")):
        mzm.verify(build(body))


def test_activity_folders_belong_to_activity_packages_only():
    key, cert = developer()
    body = {**files(), "themes/x/theme.json": b"{}"}
    with pytest.raises(mzm.PackageError, match="Only an activity package holds themes/"):
        mzm.verify(mzm.build(body, key, cert))
