"""Role screens and the screen builder (ADR-006 phase 5): menus, dashboards, forms, custom fields."""
import io

import pytest

from helpers import uid


def _screen_ids(api) -> set[str]:
    return {s["id"] for s in api.ok(api.get("/settings/screens"))["screens"]}


def _role_id(api, code: str) -> str:
    roles = api.ok(api.get("/settings/designer"))["roles"]
    return next(r["id"] for r in roles if r["code"] == code)


def test_screens_follow_the_acting_role(admin_api, cashier_api):
    admin = admin_api.ok(admin_api.get("/settings/screens"))
    cashier = cashier_api.ok(cashier_api.get("/settings/screens"))
    assert admin["menu"] and cashier["menu"]
    admin_ids, cashier_ids = _screen_ids(admin_api), _screen_ids(cashier_api)
    assert {"core.designer", "core.users", "core.settings"} <= admin_ids
    assert not {"core.designer", "core.users", "core.settings"} & cashier_ids
    assert cashier_ids < admin_ids
    # The menu only lists screens the role may open.
    in_menu = {i["id"] for g in cashier["menu"] for i in g["items"]}
    assert in_menu <= cashier_ids
    assert {w["id"] for w in admin["dashboard"]} >= {"reporting.sales_today", "pos.shift_status"}


def test_the_builder_needs_the_designer_permission(cashier_api):
    assert cashier_api.get("/settings/designer").status_code == 403
    assert cashier_api.get("/settings/fields/product").status_code == 403


def test_a_role_layout_changes_what_the_role_sees(admin_api, cashier_api):
    cashier_role = _role_id(admin_api, "cashier")
    layout = {
        "home": "pos.pos",
        "menu": [{"id": "till", "label": "الكاشير", "items": [
            {"screen": "pos.pos", "label": "البيع"},
            {"screen": "core.users"},  # the cashier can't open it: placed, but never shown
        ]}],
        "dashboard": [{"id": "pos.shift_status", "size": "m"}],
    }
    try:
        saved = admin_api.ok(admin_api.put(f"/settings/designer/roles/{cashier_role}", json=layout))
        assert saved["custom"] is True
        assert [i["screen"] for i in saved["layout"]["menu"][0]["items"]] == ["pos.pos", "core.users"]
        assert next(s for s in saved["screens"] if s["id"] == "core.users")["allowed"] is False

        seen = cashier_api.ok(cashier_api.get("/settings/screens"))
        assert seen["custom"] is True
        assert seen["home"] == "/pos"
        assert [(g["label"], [(i["id"], i["label"]) for i in g["items"]]) for g in seen["menu"]] == [
            ("الكاشير", [("pos.pos", "البيع")])]
        assert [(w["id"], w["size"]) for w in seen["dashboard"]] == [("pos.shift_status", "m")]
        # The layout arranges screens; access is unchanged.
        assert "core.users" not in _screen_ids(cashier_api)
    finally:
        admin_api.delete(f"/settings/designer/roles/{cashier_role}")
    back = cashier_api.ok(cashier_api.get("/settings/screens"))
    assert back["custom"] is False and len(back["menu"]) > 1


@pytest.mark.parametrize("bad, message", [
    ({"menu": [{"id": "g", "label": "x", "items": [{"screen": "nope.screen"}]}]}, "شاشة غير معروفة"),
    ({"menu": [{"id": "g", "label": "x", "items": [{"screen": "pos.pos"}, {"screen": "pos.pos"}]}]}, "مكررة"),
    ({"menu": [{"id": "Bad Id", "label": "x", "items": [{"screen": "pos.pos"}]}]}, "معرّف مجموعة"),
    ({"menu": [{"id": "g", "label": "x", "items": [{"screen": "pos.pos"}]}], "dashboard": [{"id": "pos.shift_status", "size": "xl"}]}, "مقاس"),
    ({"menu": [{"id": "g", "label": "x", "items": [{"screen": "pos.pos"}]}], "dashboard": ["nope.widget"]}, "عنصر لوحة"),
    ({"menu": []}, "شاشة واحدة"),
])
def test_role_layouts_are_validated(admin_api, bad, message):
    role = _role_id(admin_api, "cashier")
    r = admin_api.put(f"/settings/designer/roles/{role}", json=bad)
    assert r.status_code == 422, r.text
    assert message in r.json()["detail"]
    assert admin_api.ok(admin_api.get(f"/settings/designer/roles/{role}"))["custom"] is False


def test_custom_fields_forms_and_reports(admin_api, subcategory, reg):
    key = "e2e_" + uid("g").lower().replace("-", "_")[:20]
    try:
        # A built-in field's key can't be taken.
        assert admin_api.put("/settings/fields/product/barcode", json={"definition": {"label": "x"}}).status_code == 422
        admin_api.ok(admin_api.put(f"/settings/fields/product/{key}", json={
            "definition": {"label": "درجة الجودة", "type": "select", "options": ["A", "B"]}, "hidden": False, "position": 99}))

        # The default form puts it after the built-in fields; the barcode shows.
        form = admin_api.ok(admin_api.get("/settings/forms/product"))
        assert key in [f["key"] for f in form["sections"][-1]["fields"]]
        assert "barcode" in [f["key"] for s in form["sections"] for f in s["fields"]]

        # Arrange it: the field joins the main section, the barcode is hidden.
        main = [f["key"] for f in form["sections"][0]["fields"] if f["key"] != "barcode"]
        saved = admin_api.ok(admin_api.put("/settings/designer/forms/product", json={
            "sections": [{"id": "main", "label": "الأساسي", "fields": [*main, key]}], "hidden": ["barcode"]}))
        assert saved["custom"] is True
        assert [f["key"] for f in saved["sections"][0]["fields"]][-1] == key
        assert "barcode" in [f["key"] for f in saved["hidden"]]
        # A basic field can't be hidden.
        r = admin_api.put("/settings/designer/forms/product", json={
            "sections": [{"id": "main", "label": "الأساسي", "fields": [key]}], "hidden": ["name"]})
        assert r.status_code == 422

        # Values are checked, kept on the record, and reported.
        bad = admin_api.post("/products", json={"subcategory_id": subcategory["id"], "name": "E2E-PROD-" + uid("p"),
                                                "unit": "عدد", "retail_price": "10", "extra": {key: "C"}})
        assert bad.status_code == 422
        prod = admin_api.ok(admin_api.post("/products", json={
            "subcategory_id": subcategory["id"], "name": "E2E-PROD-" + uid("p"), "unit": "عدد",
            "retail_price": "10", "extra": {key: "A"}}), 200, 201)
        reg.add("product", prod["id"])
        assert prod["extra"][key] == "A"

        report = admin_api.ok(admin_api.get(f"/reports/fields/product/{key}"))
        assert {"value": "A", "count": 1} in report["rows"]

        export = admin_api.get("/export/products")
        assert export.status_code == 200
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(export.content)).active
        headers = [c.value for c in ws[1]]
        assert "درجة الجودة" in headers
        column = headers.index("درجة الجودة")
        assert "A" in [row[column] for row in ws.iter_rows(min_row=2, values_only=True)]
    finally:
        admin_api.delete("/settings/designer/forms/product")
        admin_api.delete(f"/settings/fields/product/{key}")
    assert admin_api.ok(admin_api.get("/settings/forms/product"))["custom"] is False


def test_customer_and_supplier_custom_fields(admin_api, reg):
    key = "e2e_" + uid("t").lower().replace("-", "_")[:20]
    try:
        admin_api.ok(admin_api.put(f"/settings/fields/customer/{key}", json={
            "definition": {"label": "رقم السجل", "type": "text", "required": True}}))
        admin_api.ok(admin_api.put(f"/settings/fields/supplier/{key}", json={
            "definition": {"label": "رقم السجل", "type": "number"}}))

        # Required on customers; unknown keys are refused.
        assert admin_api.post("/customers", json={"name": "E2E-CUST-" + uid("c")}).status_code == 422
        assert admin_api.post("/customers", json={"name": "E2E-CUST-" + uid("c"), "extra": {key: "1", "nope": 1}}).status_code == 422
        c = admin_api.ok(admin_api.post("/customers", json={"name": "E2E-CUST-" + uid("c"), "extra": {key: "CR-1"}}), 200, 201)
        reg.add("customer", c["id"])
        assert c["extra"][key] == "CR-1"

        s = admin_api.ok(admin_api.post("/suppliers", json={"name": "E2E-SUPP-" + uid("s"), "extra": {key: "42"}}), 200, 201)
        reg.add("supplier", s["id"])
        assert s["extra"][key] == 42
        # An update without extra keeps the values.
        u = admin_api.ok(admin_api.put(f"/suppliers/{s['id']}", json={"name": s["name"], "notes": "e2e"}))
        assert u["extra"][key] == 42
        assert admin_api.put(f"/suppliers/{s['id']}", json={"name": s["name"], "extra": {key: "abc"}}).status_code == 422
    finally:
        admin_api.delete(f"/settings/fields/customer/{key}")
        admin_api.delete(f"/settings/fields/supplier/{key}")
