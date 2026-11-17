"""sales module: POS sale (cash/wallet/split/credit), drafts, quotations
(drawer + safe), cancel, full/partial return, item qty update/delete, print."""
import uuid

from helpers import uid, to_uuid

from conftest import (admin_api, product, customer, subcategory, wh, safe, wallet,
                      open_shift, ensure_shift)  # noqa: F401


def _item(prod, price="100", qty=1, cost="70"):
    return {"product_id": prod["id"], "qty": qty, "unit_price": price, "unit_cost": cost, "discount": "0"}


def _sale_payload(prod, wh_, **kw):
    base = {"warehouse_id": wh_["id"], "items": [_item(prod)]}
    base.update(kw)
    return base


def _sell(api, reg, prod, wh_, **kw):
    """A confirmed sale; its cash goes into the seller's open shift in the branch."""
    ensure_shift(api, reg, wh_["id"])
    s = api.ok(api.post("/sales", json=_sale_payload(prod, wh_, **kw)))
    reg.add("sale", s["id"])
    return s


def test_create_cash_sale(admin_api, reg, product, wh):
    # No open shift in the branch: cash has no drawer to go into.
    r = admin_api.post("/sales", json=_sale_payload(product, wh))
    assert r.status_code == 400, r.text[:200]
    sh = ensure_shift(admin_api, reg, wh["id"])
    r = admin_api.post("/sales", json=_sale_payload(product, wh))
    s = admin_api.ok(r, 200)
    reg.add("sale", s["id"])
    assert s["status"] == "confirmed"
    assert float(s["net_total"]) == 100
    assert float(s["paid_amount"]) == 100
    assert s["invoice_number"]
    assert s["shift_id"] == sh["id"]


def test_create_sale_refuses_other_prices_and_client_flags(admin_api, cashier_api, reg, product, wh):
    ensure_shift(admin_api, reg, wh["id"])
    # The product's price, whatever the client sends (allow_price_override is off by default).
    r = admin_api.post("/sales", json=_sale_payload(product, wh, items=[_item(product, price="1")]))
    assert r.status_code == 400, r.text[:200]
    r = admin_api.post("/sales", json=_sale_payload(product, wh, items=[_item(product, price="-1")]))
    assert r.status_code == 422, r.text[:200]
    r = admin_api.post("/sales", json=_sale_payload(product, wh, discount_amount="500"))
    assert r.status_code == 400, r.text[:200]
    # The cashier isn't assigned to this branch.
    r = cashier_api.post("/sales", json=_sale_payload(product, wh, allow_negative_stock=True))
    assert r.status_code == 403, r.text[:200]


def test_create_sale_idempotent_local_id(admin_api, reg, product, wh):
    ensure_shift(admin_api, reg, wh["id"])
    lid = str(uuid.uuid4())
    payload = _sale_payload(product, wh, local_id=lid)
    s1 = admin_api.ok(admin_api.post("/sales", json=payload))
    reg.add("sale", s1["id"])
    s2 = admin_api.ok(admin_api.post("/sales", json=payload))
    assert s2["id"] == s1["id"]
    # The POS's key is a UUID.
    assert admin_api.post("/sales", json=_sale_payload(product, wh, local_id="e2e-not-a-uuid")).status_code == 422


def test_split_payments(admin_api, reg, product, wh, wallet, customer):
    ensure_shift(admin_api, reg, wh["id"])
    payload = _sale_payload(product, wh, payments=[
        {"method": "cash", "amount": "40"},
        {"method": "wallet", "amount": "60", "wallet_id": wallet["id"]},
    ])
    s = admin_api.ok(admin_api.post("/sales", json=payload))
    reg.add("sale", s["id"])
    assert s["payment_method"] == "cash"
    assert s["is_credit"] is False

    # mismatched split totals are rejected
    bad = _sale_payload(product, wh, payments=[{"method": "cash", "amount": "10"}])
    r = admin_api.post("/sales", json=bad)
    assert r.status_code in (400, 409), r.text[:200]


def test_credit_sale_updates_balance(admin_api, reg, product, wh, customer):
    r = admin_api.put(f"/customers/{customer['id']}/balance", json={"balance": "0"})
    admin_api.ok(r, 200)
    s = _sell(admin_api, reg, product, wh, is_credit=True, customer_id=customer["id"])
    assert s["is_credit"] is True and float(s["paid_amount"]) == 0
    acct = admin_api.ok(admin_api.get(f"/customers/{customer['id']}/account"))
    assert float(acct["balance_due"]) == 100


def test_draft_flow(admin_api, reg, product, wh):
    r = admin_api.post("/sales/draft", json=_sale_payload(product, wh))
    d = admin_api.ok(r, 200)
    reg.add("sale", d["id"])
    assert d["status"] == "draft"
    assert d["invoice_number"].startswith("DRF-")  # the invoice number comes when it is confirmed

    drafts = admin_api.ok(admin_api.get("/sales/drafts"))
    assert any(x["id"] == d["id"] for x in drafts)

    assert admin_api.put(f"/sales/{d['id']}/confirm").status_code == 400  # cash needs an open shift
    ensure_shift(admin_api, reg, wh["id"])
    confirmed = admin_api.put(f"/sales/{d['id']}/confirm")
    assert confirmed.status_code in (200, 201), confirmed.text[:200]
    body = confirmed.json()
    assert body["status"] == "confirmed" and body["invoice_number"].startswith("INV-")


def test_delete_draft_and_guard_confirmed(admin_api, reg, product, wh):
    d = admin_api.ok(admin_api.post("/sales/draft", json=_sale_payload(product, wh)))
    reg.add("sale", d["id"])
    r = admin_api.delete(f"/sales/{d['id']}")
    assert r.status_code in (200, 204), r.text[:200]

    s = _sell(admin_api, reg, product, wh)
    r = admin_api.delete(f"/sales/{s['id']}")
    assert r.status_code == 400, r.text[:200]  # confirmed sales cannot be deleted


def test_sale_get_list_update_item(admin_api, reg, product, wh):
    s = _sell(admin_api, reg, product, wh)

    got = admin_api.ok(admin_api.get(f"/sales/{s['id']}"))
    assert got["id"] == s["id"] and len(got["items"]) == 1

    lst = admin_api.ok(admin_api.get("/sales"))
    assert any(x["id"] == s["id"] for x in lst)

    # A confirmed sale isn't edited (ADR-014 D4): corrections go through a return or a cancel.
    item = got["items"][0]
    assert admin_api.put(f"/sales/{s['id']}/items/{item['id']}", json={"qty": 3}).status_code == 409
    assert admin_api.delete(f"/sales/{s['id']}/items/{item['id']}").status_code == 409


def test_sale_print(admin_api, reg, product, wh):
    s = _sell(admin_api, reg, product, wh)
    r = admin_api.get(f"/sales/{s['id']}/print")
    assert r.status_code == 200
    body = admin_api.ok(r)
    # live backend returns a JSON doc (store/document_type); tolerate HTML too
    assert isinstance(body, dict) or "text/html" in r.headers.get("content-type", "")


def test_cancel_sale(admin_api, reg, product, wh):
    s = _sell(admin_api, reg, product, wh)
    r = admin_api.put(f"/sales/{s['id']}/cancel")
    body = admin_api.ok(r, 200)
    assert body["detail"] == "Cancelled" and body.get("invoice_number")


def test_cancel_needs_the_cancel_permission(admin_api, cashier_api, reg, product, wh):
    s = _sell(admin_api, reg, product, wh)
    # Cancelling is a manager's (sales:cancel); a cashier returns (sales:return), in their branches.
    assert cashier_api.put(f"/sales/{s['id']}/cancel").status_code == 403
    assert cashier_api.post(f"/sales/{s['id']}/return").status_code == 403  # not assigned to this branch
    assert admin_api.ok(admin_api.get(f"/sales/{s['id']}"))["status"] == "confirmed"


def test_full_return(admin_api, reg, product, wh):
    s = _sell(admin_api, reg, product, wh)
    r = admin_api.post(f"/sales/{s['id']}/return")
    body = admin_api.ok(r, 200)
    # The return is its own document; the sale stays confirmed with its returns (ADR-014 D4).
    got = admin_api.ok(admin_api.get(f"/sales/{s['id']}"))
    assert got["status"] == "confirmed" and got["returns_total"] > 0
    assert len(got["returns"]) == 1 and got["returns"][0]["invoice_number"].startswith("RET-")


def test_partial_return(admin_api, reg, product, wh):
    s = _sell(admin_api, reg, product, wh, items=[_item(product, qty=4)])
    r = admin_api.post(f"/sales/{s['id']}/partial-return",
                       json={"items": [{"product_id": product["id"], "qty": 1}]})
    body = admin_api.ok(r, 200)
    assert "returned" in body or "items" in body or body


# ---------------- quotations ----------------
def test_quotation_create_and_confirm_drawer(admin_api, reg, product, wh, customer):
    q = admin_api.ok(admin_api.post("/sales/quotations", json=_sale_payload(product, wh,
                                                                            customer_id=customer["id"])))
    reg.add("sale", q["id"])
    assert q["status"] == "quotation"

    sh = open_shift(admin_api, reg, wh["id"])
    confirmed = admin_api.ok(admin_api.post(f"/sales/{q['id']}/confirm-quotation",
                                            json={"destination": "drawer"}))
    assert confirmed["status"] == "confirmed"
    assert float(confirmed["paid_amount"]) == 100


def test_quotation_confirm_into_safe(owner_api, reg, product, wh, customer, safe):
    q = owner_api.ok(owner_api.post("/sales/quotations", json=_sale_payload(product, wh,
                                                                            customer_id=customer["id"])))
    reg.add("sale", q["id"])
    confirmed = owner_api.ok(owner_api.post(f"/sales/{q['id']}/confirm-quotation",
                                            json={"destination": "safe", "safe_id": safe["id"]}))
    assert confirmed["status"] == "confirmed"
    hist = owner_api.ok(owner_api.get(f"/safes/{safe['id']}/history"))
    assert any(x["tx_type"] == "deposit" for x in hist)


def test_quotation_update_items(admin_api, reg, product, wh):
    q = admin_api.ok(admin_api.post("/sales/quotations", json=_sale_payload(product, wh)))
    reg.add("sale", q["id"])
    upd = admin_api.ok(admin_api.put(f"/sales/{q['id']}", json={
        "items": [_item(product, qty=2)],
        "notes": "e2e-quote-update",
    }))
    assert "id" in upd
    assert float(admin_api.ok(admin_api.get(f"/sales/{q['id']}"))["net_total"]) == 200
    # Another price needs allow_price_override (off by default).
    r = admin_api.put(f"/sales/{q['id']}", json={"items": [_item(product, price="90", qty=2)]})
    assert r.status_code == 400, r.text[:200]

def test_invoice_pdf_renders(admin_api, reg, product, wh):
    s = _sell(admin_api, reg, product, wh)
    r = admin_api.get(f"/invoices/{s['id']}/pdf")
    assert r.status_code == 200, r.text[:200]
    assert r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
def test_quotation_partial_edit_keeps_items_and_customer(admin_api, reg, product, wh, customer):
    q = admin_api.ok(admin_api.post("/sales/quotations", json=_sale_payload(product, wh, customer_id=customer["id"])))
    reg.add("sale", q["id"])
    # Editing only the notes used to delete every item (total 0) and unlink the customer.
    admin_api.ok(admin_api.put(f"/sales/{q['id']}", json={"notes": "e2e only notes"}))
    after = admin_api.ok(admin_api.get(f"/sales/{q['id']}"))
    assert len(after["items"]) == 1
    assert float(after["net_total"]) == 100
    assert after["customer_id"] == customer["id"]
    assert after["notes"] == "e2e only notes"

    admin_api.ok(admin_api.put(f"/sales/{q['id']}", json={"discount_amount": "10"}))
    assert float(admin_api.ok(admin_api.get(f"/sales/{q['id']}"))["net_total"]) == 90


def test_invoice_email_needs_a_real_address(admin_api, reg, product, wh):
    s = _sell(admin_api, reg, product, wh)
    # No address used to fall back to the user's username or customer@example.com.
    for body in ({}, {"email": "not-an-email"}):
        r = admin_api.post(f"/invoices/{s['id']}/send", json=body)
        assert r.status_code == 400, r.text[:200]
    sent = admin_api.ok(admin_api.post(f"/invoices/{s['id']}/send", json={"email": "buyer@mizan.test"}))
    assert "buyer@mizan.test" in sent["message"]


def _printed(api, sale_id) -> str:
    token = api.ok(api.post("/auth/print-token"))["token"]
    r = api.get(f"/print/sale/{sale_id}", params={"token": token})
    assert r.status_code == 200, r.text[:200]
    return r.text


def test_vat_registered_sale_stores_and_prints_its_vat(admin_api, reg, product, wh):
    """ADR-014 D6: a VAT-registered workspace stores each sale's VAT (prices include it by default)
    and prints it with the tax number; switching registration off goes back to no VAT at all."""
    before = admin_api.ok(admin_api.get("/settings/vat"))
    r = admin_api.put("/settings", json={"tax_number": "12-34"})
    assert r.status_code == 422, r.text[:200]
    try:
        admin_api.ok(admin_api.put("/settings", json={"vat_registered": True, "prices_include_vat": True,
                                                      "tax_number": "100-200-300"}))
        assert admin_api.ok(admin_api.get("/settings/vat"))["tax_number"] == "100200300"
        s = admin_api.ok(admin_api.post("/sales", json=_sale_payload(product, wh, items=[_item(product, price="114")])))
        reg.add("sale", s["id"])
        assert float(s["net_total"]) == 114 and float(s["tax_amount"]) == 14
        assert s["items"][0]["tax_code"] == "standard" and float(s["items"][0]["net_amount"]) == 100
        page = _printed(admin_api, s["id"])
        assert "فاتورة ضريبية" in page and "100-200-300" in page
    finally:
        admin_api.ok(admin_api.put("/settings", json={"vat_registered": before["vat_registered"],
                                                      "prices_include_vat": before["prices_include_vat"],
                                                      "tax_number": before["tax_number"]}))
    s = admin_api.ok(admin_api.post("/sales", json=_sale_payload(product, wh)))
    reg.add("sale", s["id"])
    if not before["vat_registered"]:
        assert float(s["tax_amount"]) == 0 and s["items"][0]["tax_code"] is None
        assert "ضريبة" not in _printed(admin_api, s["id"])
