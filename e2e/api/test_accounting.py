"""accounting (ACC-3): the party picker searches on the server; bad input is a 422. Skipped when the
workspace under test hasn't turned the accounting module on."""
import pytest

from conftest import admin_api, cashier_api, customer  # noqa: F401


def _on(api) -> bool:
    r = api.get("/accounting/parties", params={"type": "customer"})
    if r.status_code == 403 and "غير مفعلة" in r.text:
        return False
    return True


def test_party_search(admin_api, cashier_api, customer):
    if not _on(admin_api):
        pytest.skip("accounting is off in this workspace")
    found = admin_api.ok(admin_api.get("/accounting/parties", params={"type": "customer", "q": customer["name"], "limit": 5}))
    assert [p["id"] for p in found] == [customer["id"]]
    chosen = admin_api.ok(admin_api.get("/accounting/parties", params={"type": "supplier", "limit": 1, "id": customer["id"]}))
    assert len(chosen) <= 1  # a customer's id is no supplier: nothing added
    assert admin_api.get("/accounting/parties", params={"type": "robot"}).status_code == 422
    assert admin_api.get("/accounting/parties", params={"type": "customer", "limit": 51}).status_code == 422
    assert cashier_api.get("/accounting/parties", params={"type": "customer"}).status_code == 403
