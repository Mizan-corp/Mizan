"""Printed documents (PLAT-5): every print route and its PDF.

- Every text a document prints that came from the workspace (store, customer, supplier, product,
  unit, user, branch, notes, document numbers) is escaped: markup typed into any of them shows as
  text, never as markup.
- Each route needs the permission of its document and a branch the user reaches; another branch is a
  403, an unknown document (or another workspace's) a 404. A browser tab gets errors as an Arabic page.
- The dispatch and hand-over documents print from what operations and the shift hand-over leave
  behind (they read tables that never existed: always a 500).
"""
import html
import json
import os
import uuid
from decimal import Decimal
from urllib.parse import quote

import pytest

from app.activities.general.modules.contacts.models.party import Customer, Supplier
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.services.stock import apply_movement
from app.activities.general.modules.pos import service as pos_service
from app.activities.general.modules.pos.models import DrawerTxType
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from tests.conftest import give_roles
from tests.test_reporting import _client, _scenario, _sql, _token

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


def M(field: str) -> str:
    """Markup typed into one field."""
    return f"<i id={field}>"


def assert_escaped(page: str, *fields: str) -> None:
    assert "<i id=" not in page, "markup printed as markup"
    for f in fields:
        assert html.escape(M(f)) in page, f"{f} not printed (escaped)"


async def _documents() -> dict:
    """The reports' scenario (two branches; a manager, a branch-1 cashier and a branch-1 clerk with
    `reports`), with markup in every text field, and one document of each kind."""
    env = await _scenario()
    t, u, wh1, wh2 = env["tenant_id"], env["users"], env["warehouse_id"], env["warehouse2_id"]
    for key, value in (("store_name", M("store")), ("store_address", M("address")),
                       ("contact_phones", json.dumps([{"name": M("cname"), "phone": M("cphone")}]))):
        await _sql(env, "INSERT INTO store_settings (id, tenant_id, key, value) VALUES (:id, :t, :k, :v) "
                        "ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value",
                   id=uuid.uuid4(), t=t, k=key, v=value)
    await _sql(env, "UPDATE warehouses SET name = :n WHERE id = :id", n=M("branch"), id=wh1)
    await _sql(env, "UPDATE warehouses SET name = :n WHERE id = :id", n=M("branch2"), id=wh2)
    await _sql(env, "UPDATE products SET name = :n, unit = :u WHERE id = :id", n=M("product"), u=M("unit"), id=env["product_id"])
    await _sql(env, "UPDATE users SET full_name = :n WHERE id = :id", n=M("cashier"), id=env["cashier_id"])
    await _sql(env, "UPDATE users SET full_name = :n WHERE id = :id", n=M("manager"), id=u["manager"])

    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        cust = Customer(id=uuid.uuid4(), tenant_id=t, name=M("customer"), phone=M("phone"), address=M("caddr"),
                        balance=Decimal("0"))
        sup = Supplier(id=uuid.uuid4(), tenant_id=t, name=M("supplier"), phone=M("sphone"), address=M("saddr"))
        s.add_all([cust, sup])
        await s.commit()
    sale = (await _sql(env, "SELECT id FROM sales WHERE warehouse_id = :wh AND status = 'confirmed' AND return_of IS NULL "
                            "ORDER BY created_at LIMIT 1", wh=wh1))[0][0]
    ret = (await _sql(env, "SELECT id, return_of FROM sales WHERE return_of IS NOT NULL LIMIT 1"))[0]
    await _sql(env, "UPDATE sales SET customer_id = :c, notes = :n, invoice_number = :i WHERE id = :id",
               c=cust.id, n=M("notes"), i=M("number"), id=sale)
    await _sql(env, "UPDATE sales SET invoice_number = :i WHERE id = :id", i=M("orig"), id=ret.return_of)
    await _sql(env, "UPDATE sales SET invoice_number = :i, customer_id = :c WHERE id = :id", i=M("retnum"), c=cust.id, id=ret.id)
    sale2 = (await _sql(env, "SELECT id FROM sales WHERE warehouse_id = :wh LIMIT 1", wh=wh2))[0][0]

    po = uuid.uuid4()
    await _sql(env, """INSERT INTO purchase_orders (id, tenant_id, po_number, supplier_id, warehouse_id, created_by, status,
                       amount_paid, notes, received_by_name, tax_amount)
                       VALUES (:id, :t, :n, :s, :wh, :by, 'draft', 0, :notes, :rb, 0)""",
               id=po, t=t, n=M("po"), s=sup.id, wh=wh1, by=u["manager"], notes=M("pnotes"), rb=M("receiver"))
    await _sql(env, "INSERT INTO purchase_order_items (id, tenant_id, po_id, product_id, qty_ordered, qty_received, unit_cost, extra, tax_rate, tax_amount) "
                    "VALUES (:id, :t, :po, :p, 2, 0, 60, '{}'::jsonb, 0, 0)", id=uuid.uuid4(), t=t, po=po, p=env["product_id"])

    current_tenant_id.set(t)
    async with AsyncSessionLocal() as s:
        await pos_service.add_transaction(s, env["shift_id"], DrawerTxType.deposit, Decimal("5"), env["cashier_id"],
                                          note=M("drawer"))
    ref = uuid.uuid4()
    async with AsyncSessionLocal() as s:
        await apply_movement(s, product_id=env["product_id"], warehouse_id=wh1, movement_type=MovementType.transfer_out,
                             qty=Decimal("1"), ref_id=ref, ref_type="dispatch", created_by=u["manager"])
        await apply_movement(s, product_id=env["product_id"], warehouse_id=wh2, movement_type=MovementType.transfer_in,
                             qty=Decimal("1"), ref_id=ref, ref_type="dispatch", created_by=u["manager"])
        await s.commit()
    archived = {}
    for kind, number, meta, ref_id in (
        ("dispatch_order", M("dsp"), {"from": "x", "to": "y", "notes": M("dnotes")}, ref),
        ("shift_handover", M("hnd"), {"from_user": str(env["cashier_id"]), "to_user": str(u["manager"]),
                                      "from_user_name": M("from"), "to_user_name": M("to"), "notes": M("hnotes")}, env["shift_id"]),
        ("purchase_invoice", M("arc"), {"supplier": M("asupplier"), "notes": M("anotes"), "warehouse_id": str(wh1)}, None),
    ):
        doc = uuid.uuid4()
        await _sql(env, "INSERT INTO archived_documents (id, tenant_id, doc_number, doc_type, customer_name, amount, metadata, "
                        "ref_id, created_by) VALUES (:id, :t, :n, :k, :c, 10, CAST(:m AS jsonb), :r, :by)",
                   id=doc, t=t, n=number, k=kind, c=M("acust"), m=json.dumps(meta), r=ref_id, by=u["manager"])
        archived[kind] = doc

    async with AsyncSessionLocal() as s:  # a user who prints nothing: customers only, branch 1
        nobody = User(id=uuid.uuid4(), tenant_id=t, username=f"nobody_{t.hex[:8]}", full_name="nobody", role="cashier",
                      password_hash=hash_password("Pass12345!"), permissions=["customers"], is_active=True)
        s.add(nobody)
        await give_roles(s)
        await s.commit()
    env.update(sale=sale, ret=ret.id, sale2=sale2, po=po, archive=archived, nobody=nobody.id)
    return env


def _routes(env: dict) -> dict[str, tuple[str, tuple[str, ...]]]:
    """Each document: its path (after /print and /print/pdf) and the fields it prints."""
    return {
        "sale": (f"/sale/{env['sale']}", ("store", "address", "cname", "cphone", "customer", "phone", "caddr", "branch",
                                          "product", "unit", "notes", "number", "cashier")),
        "return": (f"/sale/{env['ret']}", ("store", "retnum", "orig", "customer", "product", "unit", "cashier")),
        "purchase": (f"/purchase/{env['po']}", ("store", "supplier", "sphone", "saddr", "branch", "manager", "pnotes", "po",
                                                "product", "unit", "receiver")),
        "shift": (f"/shift/{env['shift_id']}", ("store", "branch", "cashier", "product", "unit", "drawer", "retnum")),
        "dispatch": (f"/dispatch/{quote(M('dsp'), safe='')}", ("store", "dsp", "branch", "branch2", "product", "unit", "dnotes",
                                                              "manager")),
        "handover": (f"/handover/{quote(M('hnd'), safe='')}", ("store", "hnd", "from", "to", "branch", "hnotes")),
        "archive": (f"/archive/{env['archive']['purchase_invoice']}", ("store", "arc", "manager", "asupplier", "anotes")),
        "inventory": (f"/inventory/{env['warehouse_id']}", ("store", "address", "branch", "product", "unit")),
    }


async def test_every_document_and_its_pdf_escape_what_users_typed(monkeypatch):
    """Fails on the old code: document numbers, status labels and the store's name went out as typed
    (and the store's name never showed), dispatch and hand-over answered 500."""
    from app.platform.printing import routes as printing

    async def no_pdf(page, zoom=1.0):  # the PDF's HTML comes back as the printable page
        raise OSError("no pango here")

    monkeypatch.setattr(printing, "html_to_pdf", no_pdf)
    env = await _documents()
    tok = _token(env["users"]["manager"], env["tenant_id"], scope="print")
    async with _client() as c:
        for name, (path, fields) in _routes(env).items():
            for prefix in ("/print", "/print/pdf"):
                r = await c.get(prefix + path, params={"token": tok})
                assert r.status_code == 200, (name, prefix, r.text[:300])
                assert r.headers["content-type"].startswith("text/html")
                assert_escaped(r.text, *fields)


async def test_the_pdf_footer_and_file_name_carry_no_markup():
    from app.platform.printing.routes import _css_string, wrap_pdf

    page = wrap_pdf("<p>x</p>", 'a"b', footer_html='M"}</style><script>x</script>\\')
    assert "<script>" not in page and "</style><script>" not in page and "<title>a&quot;b</title>" in page
    assert _css_string('a"b\\c<d>\n') == "abcd"


async def test_each_document_needs_its_permission_and_branch():
    """Fails on the old code: any print token printed any document of the workspace, inventory too."""
    env = await _documents()
    t, u = env["tenant_id"], env["users"]
    tok = {k: _token(v, t, scope="print") for k, v in u.items()}
    tok["nobody"] = _token(env["nobody"], t, scope="print")
    tok["owner"] = _token(env["cashier_id"], t, scope="print")  # the branch-1 shift's cashier
    routes = _routes(env)
    async with _client() as c:
        async def status(path: str, who: str, **headers) -> int:
            return (await c.get("/print" + path, params={"token": tok[who]}, headers=headers)).status_code

        # A user with none of the documents' permissions prints none of them.
        for name, (path, _) in routes.items():
            assert await status(path, "nobody") == 403, name
        # The cashier prints their branch's sales, not someone else's shift, purchases, the archive,
        # dispatch orders, the stock sheet or another branch's sale; the shift's own cashier prints it.
        assert await status(routes["sale"][0], "cashier") == 200
        assert await status(routes["shift"][0], "cashier") == 403
        assert await status(routes["shift"][0], "owner") == 200
        assert await status(f"/sale/{env['sale2']}", "cashier") == 403
        for name in ("purchase", "archive", "dispatch", "inventory"):
            assert await status(routes[name][0], "cashier") == 403, name
        # The clerk (reports, branch 1): the stock sheet of their branch, not the other one's; not
        # someone else's shift or hand-over.
        assert await status(routes["inventory"][0], "clerk") == 200
        assert await status(f"/inventory/{env['warehouse2_id']}", "clerk") == 403
        assert await status(f"/shift/{env['shift2_id']}", "cashier") == 403
        assert await status(routes["handover"][0], "clerk") == 403
        assert await status(routes["handover"][0], "cashier") == 403
        assert await status(routes["handover"][0], "owner") == 200  # a party to it
        # Unknown documents and branches are 404s.
        for path in (f"/sale/{uuid.uuid4()}", f"/purchase/{uuid.uuid4()}", f"/shift/{uuid.uuid4()}", f"/archive/{uuid.uuid4()}",
                     f"/inventory/{uuid.uuid4()}", "/dispatch/NOPE-1", "/handover/NOPE-1"):
            assert await status(path, "manager") == 404, path
        # A browser tab gets the refusal as an Arabic page.
        r = await c.get("/print" + routes["purchase"][0], params={"token": tok["cashier"]}, headers={"Accept": "text/html"})
        assert r.status_code == 403 and r.headers["content-type"].startswith("text/html")
        assert "تعذرت الطباعة" in r.text and "ليس لديك صلاحية طباعة المشتريات" in r.text
        r = await c.get(f"/print/sale/{env['sale']}", params={"token": "expired"}, headers={"Accept": "text/html"})
        assert r.status_code == 401 and "انتهت صلاحية رابط الطباعة" in r.text
        r = await c.get("/print/sale/not-a-uuid", params={"token": tok["manager"]}, headers={"Accept": "text/html"})
        assert r.status_code == 422 and "رابط الطباعة غير صالح" in r.text
        # An API client still gets JSON.
        assert (await c.get("/print" + routes["purchase"][0], params={"token": tok["cashier"]})).json()["detail"]
        # A session token is not a print token.
        r = await c.get("/print" + routes["sale"][0], headers={"Authorization": "Bearer " + _token(u["manager"], t)})
        assert r.status_code in (401, 403)
        assert (await c.get("/print/pdf" + routes["sale"][0], params={"token": tok["manager"], "paper_size": "A4<x>"})).status_code == 422


async def test_another_workspaces_documents_are_not_found():
    env, other = await _documents(), await _scenario()
    tok = _token(env["users"]["manager"], env["tenant_id"], scope="print")
    other_sale = (await _sql(other, "SELECT id FROM sales LIMIT 1"))[0][0]
    async with _client() as c:
        for path, extra in ((f"/print/sale/{other_sale}", {}), (f"/print/inventory/{other['warehouse_id']}", {}),
                            (f"/print/shift/{other['shift_id']}", {}), (f"/print/pdf/inventory/{other['warehouse_id']}", {}),
                            ("/reports/inventory/print", {"warehouse_id": str(other["warehouse_id"])})):
            r = await c.get(path, params={"token": tok, **extra})
            assert r.status_code == 404, (path, r.text[:200])
