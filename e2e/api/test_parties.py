"""parties module: customers (CRUD, account, ledger, payments, balance) and
suppliers (CRUD, ledger, transactions)."""
import uuid

from helpers import uid, to_uuid

from conftest import customer, supplier, wh, product, subcategory, db, safe, cashier_api  # noqa: F401


# ---------------- customers ----------------
def test_customer_crud(admin_api, reg):
    name = f"E2E-CUST-{uid('c')}"
    r = admin_api.post("/customers", json={"name": name, "phone": "01000000001",
                                           "credit_limit": "500"})
    cu = admin_api.ok(r, 200, 201)
    reg.add("customer", cu["id"])
    assert cu["name"] == name

    lst = admin_api.ok(admin_api.get("/customers", params={"search": name[:10]}))
    assert any(x["id"] == cu["id"] for x in (lst if isinstance(lst, list) else lst.get("items", [])))

    upd = admin_api.ok(admin_api.put(f"/customers/{cu['id']}",
                                     json={"name": name + "-R", "credit_limit": "1000"}))
    assert upd["name"].endswith("-R")

    acct = admin_api.ok(admin_api.get(f"/customers/{cu['id']}/account"))
    assert acct["customer_id"] == cu["id"] or "balance" in acct

    ledger = admin_api.ok(admin_api.get(f"/customers/{cu['id']}/ledger"))
    assert "items" in ledger or isinstance(ledger, list)

    r = admin_api.delete(f"/customers/{cu['id']}")
    assert r.status_code in (200, 204), r.text[:200]


def test_customer_balance_and_payment(admin_api, reg, customer, db, safe):
    r = admin_api.put(f"/customers/{customer['id']}/balance",
                      json={"balance": "250", "note": "e2e-set"})
    admin_api.ok(r, 200)

    p = admin_api.post(f"/customers/{customer['id']}/payments",
                       json={"amount": "100", "note": "e2e-pay", "safe_id": safe["id"]})
    pay = admin_api.ok(p, 200, 201)
    reg.add("payment", pay.get("id", to_uuid(pay)) if pay else uuid.uuid4())
    # The audit trail points at the payment it records.
    logged = db.one("SELECT count(*) FROM audit_log WHERE entity_type = 'customer_payment' AND entity_id = %s", (pay["id"],))
    assert logged[0] == 1

    acct = admin_api.ok(admin_api.get(f"/customers/{customer['id']}/account"))
    assert acct["customer_id"] == customer["id"] or "balance" in acct

    lst = admin_api.ok(admin_api.get("/customers", params={"search": customer["name"][:10]}))
    rows = lst if isinstance(lst, list) else lst.get("items", [])
    row = next(x for x in rows if x["id"] == customer["id"])
    assert 0 <= float(row.get("balance", 0)) <= 250


# ---------------- suppliers ----------------
def test_supplier_crud(admin_api, reg):
    name = f"E2E-SUPP-{uid('s')}"
    r = admin_api.post("/suppliers", json={"name": name, "phone": "01000000002", "notes": "e2e"})
    su = admin_api.ok(r, 200, 201)
    reg.add("supplier", su["id"])

    lst = admin_api.ok(admin_api.get("/suppliers"))
    rows = lst if isinstance(lst, list) else lst.get("items", [])
    assert any(x["id"] == su["id"] for x in rows)

    upd = admin_api.ok(admin_api.put(f"/suppliers/{su['id']}", json={"name": name + "-R"}))
    assert upd["name"].endswith("-R")

    ledger = admin_api.ok(admin_api.get(f"/suppliers/{su['id']}/ledger"))
    assert "transactions" in ledger or "items" in ledger or isinstance(ledger, list)

    admin_api.ok(admin_api.post(f"/suppliers/{su['id']}/transactions",
                                json={"amount": 50, "type": "debit", "notes": "e2e"}), 200, 201)
    # a payment must say which safe or wallet paid it
    r = admin_api.post(f"/suppliers/{su['id']}/transactions", json={"amount": 10, "type": "credit"})
    assert r.status_code == 400, r.text[:200]

    # a supplier with movements is deactivated, not deleted (ADR-014 D4)
    r = admin_api.delete(f"/suppliers/{su['id']}")
    assert r.status_code == 409, r.text[:200]
    admin_api.ok(admin_api.post(f"/suppliers/{su['id']}/deactivate"))


def test_supplier_transaction_type_validation(admin_api, supplier):
    r = admin_api.post(f"/suppliers/{supplier['id']}/transactions",
                       json={"amount": 1, "type": "bad"})
    assert r.status_code == 422

def test_customer_statement_is_paged_with_a_running_balance(admin_api, reg, customer, safe):
    admin_api.ok(admin_api.put(f"/customers/{customer['id']}/balance", json={"balance": "300", "note": "e2e"}))
    pay = admin_api.ok(admin_api.post(f"/customers/{customer['id']}/payments",
                                      json={"amount": "100", "safe_id": safe["id"]}))
    reg.add("payment", pay["id"])
    page = admin_api.ok(admin_api.get(f"/customers/{customer['id']}/ledger", params={"page_size": 1}))
    assert page["total"] == 2 and page["pages"] == 2 and len(page["items"]) == 1
    assert page["items"][0]["type"] == "opening" and page["items"][0]["balance"] == 300.0
    last = admin_api.ok(admin_api.get(f"/customers/{customer['id']}/ledger", params={"page_size": 1, "page": 2}))
    assert last["items"][0]["type"] == "payment" and last["items"][0]["balance"] == 200.0
    acct = admin_api.ok(admin_api.get(f"/customers/{customer['id']}/account"))
    assert acct["balance_due"] == 200.0 and acct["total_paid"] == 100.0
    assert admin_api.get("/customers/00000000-0000-0000-0000-000000000000/ledger").status_code == 404
    summary = admin_api.ok(admin_api.get("/customers/summary", params={"search": customer["name"]}))
    assert summary["total"] == 1 and float(summary["total_due"]) == 200.0


def test_customer_receipt_is_idempotent_and_reversible(admin_api, cashier_api, reg, customer, safe, db):
    admin_api.ok(admin_api.put(f"/customers/{customer['id']}/balance", json={"balance": "50"}))
    body = {"amount": "20", "safe_id": safe["id"], "client_id": str(uuid.uuid4())}
    first = admin_api.ok(admin_api.post(f"/customers/{customer['id']}/payments", json=body))
    again = admin_api.ok(admin_api.post(f"/customers/{customer['id']}/payments", json=body))
    reg.add("payment", first["id"])
    assert first["id"] == again["id"]
    assert cashier_api.post(f"/customers/payments/{first['id']}/reverse", json={"reason": "e2e"}).status_code == 403
    rev = admin_api.ok(admin_api.post(f"/customers/payments/{first['id']}/reverse", json={"reason": "e2e خطأ"}))
    reg.add("payment", rev["id"])
    assert rev["amount"] == -20.0 and rev["reverses_id"] == first["id"]
    assert admin_api.post(f"/customers/payments/{first['id']}/reverse", json={"reason": "e2e خطأ"}).status_code == 409
    bal = db.one("SELECT balance FROM customers WHERE id = %s", (customer["id"],))[0]
    assert float(bal) == 50.0


def test_cashier_cannot_write_off_or_remove_customers(cashier_api, customer):
    assert cashier_api.put(f"/customers/{customer['id']}/balance", json={"balance": "0"}).status_code == 403
    assert cashier_api.post(f"/customers/{customer['id']}/deactivate").status_code == 403
    assert cashier_api.delete(f"/customers/{customer['id']}").status_code == 403
    assert cashier_api.put(f"/customers/{customer['id']}", json={"name": None}).status_code == 422
