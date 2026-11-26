"""Role screens (ADR-006 phase 5). The designer and custom-field editing endpoints were removed in steps 8d and 8f."""

def _screen_ids(api) -> set[str]:
    return {s["id"] for s in api.ok(api.get("/settings/screens"))["screens"]}


def test_screens_follow_the_acting_role(admin_api, cashier_api):
    admin = admin_api.ok(admin_api.get("/settings/screens"))
    cashier = cashier_api.ok(cashier_api.get("/settings/screens"))
    assert admin["menu"] and cashier["menu"]
    admin_ids, cashier_ids = _screen_ids(admin_api), _screen_ids(cashier_api)
    assert {"core.users", "core.settings"} <= admin_ids
    assert not {"core.users", "core.settings"} & cashier_ids
    assert cashier_ids < admin_ids
    # The menu only lists screens the role may open.
    in_menu = {i["id"] for g in cashier["menu"] for i in g["items"]}
    assert in_menu <= cashier_ids
    assert {w["id"] for w in admin["dashboard"]} >= {"reporting.sales_today", "pos.shift_status"}


def test_the_designer_and_field_editing_apis_are_gone(admin_api):
    # Removed in steps 8d and 8f: layouts and fields are authored by developers and in Studio.
    for path in ("/settings/designer", "/settings/designer/shell", "/settings/fields/product"):
        assert admin_api.get(path).status_code in (404, 405), path
    assert admin_api.put("/settings/fields/product/x", json={"definition": {"label": "x"}}).status_code in (404, 405)
