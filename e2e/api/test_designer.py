"""Role screens and custom fields (ADR-006 phase 5). The designer editing endpoints were removed in step 8d."""
import io

from helpers import uid


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


def test_custom_fields_need_the_designer_permission(admin_api, cashier_api):
    assert admin_api.get("/settings/designer").status_code in (404, 405)  # the editing API is gone (step 8d)
    assert admin_api.get("/settings/designer/shell").status_code in (404, 405)
    assert cashier_api.get("/settings/fields/product").status_code == 403


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
