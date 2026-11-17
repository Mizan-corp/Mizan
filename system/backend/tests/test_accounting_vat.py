"""VAT on documents (ADR-014 D6, step 6 of D12).

- The VAT math: prices including or excluding VAT, discounts first, rounding per line, zero-rated and
  exempt codes, no VAT at all for a workspace that isn't registered.
- Sales (POS), returns, purchases, purchase returns and expenses store each line's code, rate, tax
  and net at the time of the document; their entries post VAT output / VAT input as the ADR's table
  says; the average cost takes the purchase cost without VAT.
- A return takes the original line's tax, even after the product's code changed.
- The VAT report reads the ledger; printed invoices show the stored VAT and the tax number.
- An unregistered workspace posts and prints exactly as before.
"""
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.activities.general.modules.accounting.services.vat import vat_report
from app.activities.general.modules.contacts.models.party import Customer, Supplier
from app.activities.general.modules.finance.services import expenses as expense_service
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement
from app.activities.general.modules.pos.models import Shift
from app.activities.general.modules.purchases import service as purchase_service
from app.activities.general.modules.purchases.schemas.purchase import (
    PurchaseCreate,
    PurchaseItemCreate,
    PurchaseReceive,
    PurchaseReturnCreate,
    PurchaseReturnItemIn,
)
from app.activities.general.modules.sales.schemas import SaleCreate, SaleItemCreate
from app.activities.general.modules.sales.services import sales as sales_service
from app.db.base import AsyncSessionLocal
from app.models.registry import load_all_models
from app.platform.auth.models.user import User
from app.platform.auth.security import hash_password
from app.platform.settings import vat
from app.platform.tenancy.context import bind_tenant, current_tenant_id, install_tenancy_events
from app.platform.tenancy.models import Tenant

load_all_models()
install_tenancy_events()

D = Decimal
MODULES = ["sales", "pos", "shifts", "inventory", "finance", "contacts", "purchases", "accounting"]
SAFE = "خزنة — الخزينة الرئيسية"
DRAWER = "درج كاشير — فرع وسط البلد"
db_only = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


# ── the math (no database) ─────────────────────────────────────────────────────────────────────

REG_INC = vat.VatSettings(registered=True, prices_include_vat=True, tax_number="123456789")
REG_EXC = vat.VatSettings(registered=True, prices_include_vat=False, tax_number="123456789")
UNREG = vat.VatSettings()


def test_line_tax_inclusive_exclusive_and_rounding():
    t = vat.line_tax(D("114"), "standard", True, True)
    assert (t.tax_code, t.tax_rate, t.net, t.tax) == ("standard", D("14"), D("100.00"), D("14.00"))
    # 10 / 1.14 = 8.7719… → net 8.77, tax is the rest, so net + tax is exactly what was paid.
    t = vat.line_tax(D("10"), "standard", True, True)
    assert (t.net, t.tax, t.gross) == (D("8.77"), D("1.23"), D("10.00"))
    # Excluding VAT: 9.99 × 14 % = 1.3986 → 1.40 on top.
    t = vat.line_tax(D("9.99"), "standard", True, False)
    assert (t.net, t.tax, t.gross) == (D("9.99"), D("1.40"), D("11.39"))
    # Half up: 0.25 × 14 % = 0.035 → 0.04.
    assert vat.line_tax(D("0.25"), "standard", True, False).tax == D("0.04")


def test_zero_rated_exempt_and_unregistered():
    for code in ("zero", "exempt"):
        t = vat.line_tax(D("50"), code, True, True)
        assert (t.tax_code, t.tax_rate, t.net, t.tax) == (code, D("0"), D("50.00"), D("0"))
    t = vat.line_tax(D("114"), "standard", False, True)
    assert (t.tax_code, t.tax_rate, t.net, t.tax) == (None, D("0"), D("114.00"), D("0"))
    # An unknown code falls back to the standard rate (the database only allows the three).
    assert vat.line_tax(D("114"), "nonsense", True, True).tax == D("14.00")
    assert vat.TAX_RATES == {"standard": D("14"), "zero": D("0"), "exempt": D("0")}


def test_discounts_come_first_and_the_invoice_discount_is_shared():
    # Lines after their own discount: 100 (standard) and 50 (exempt); invoice discount 10 → 6.67 / 3.33.
    taxes = vat.document_taxes([(D("100"), "standard"), (D("50"), "exempt")], D("10"), REG_INC)
    assert [(t.net, t.tax) for t in taxes] == [(D("81.87"), D("11.46")), (D("46.67"), D("0"))]
    assert sum(t.gross for t in taxes) == D("140.00")  # the same total as without VAT
    taxes = vat.document_taxes([(D("100"), "standard"), (D("50"), "exempt")], D("10"), REG_EXC)
    assert [(t.net, t.tax) for t in taxes] == [(D("93.33"), D("13.07")), (D("46.67"), D("0"))]
    assert vat.allocate([D("1"), D("1"), D("1")], D("1")) == [D("0.34"), D("0.33"), D("0.33")]
    # Weighed lines with fractions of a piastre (0.125 and 6.999, rounded alone 0.13 + 7.00): the lines
    # still add up to the document's own rounded total, 7.124 → 7.12.
    taxes = vat.document_taxes([(D("0.125") * D("1.00"), "standard"), (D("2.333") * D("3"), "standard")], 0, REG_INC)
    assert sum(t.gross for t in taxes) == D("7.12")
    assert vat.document_taxes([(D("114"), "standard")], 0, UNREG)[0].tax == D("0")


def test_return_portions_add_up_and_tax_numbers():
    parts = [vat.portion(D("14"), 0, 1, 3), vat.portion(D("14"), 1, 1, 3), vat.portion(D("14"), 2, 1, 3)]
    assert parts == [D("4.67"), D("4.66"), D("4.67")] and sum(parts) == D("14")
    assert vat.portion(D("14"), 0, 3, 3) == D("14.00")
    assert vat.clean_tax_number("123-456-789") == "123456789"
    assert vat.clean_tax_number(" ١٢٣ ٤٥٦ ٧٨٩ ") == "123456789"
    assert vat.clean_tax_number("") == ""
    with pytest.raises(ValueError, match="9 أرقام"):
        vat.clean_tax_number("12345")
    assert vat.format_tax_number("123456789") == "123-456-789"


# ── documents and postings ─────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    if not os.environ.get("DATABASE_URL"):
        yield
        return
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _env(registered=True, inclusive=True) -> dict:
    """A workspace with accounting; VAT-registered (prices including VAT unless told otherwise) or
    not. A branch, a cashier with an open shift, a customer, a supplier, a safe holding 1000, and two
    products with 50 units at cost 60: one standard-rated priced 114, one exempt priced 50."""
    t_id = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=t_id, name=f"VAT {t_id.hex[:6]}", slug=f"vat-{t_id.hex[:8]}", status="active", active_modules=MODULES))
        await s.flush()
        wh = Warehouse(id=uuid.uuid4(), tenant_id=t_id, code=f"WH-{t_id.hex[:4]}", name="فرع وسط البلد", is_active=True)
        cashier = User(id=uuid.uuid4(), tenant_id=t_id, username=f"vat_{t_id.hex[:8]}", full_name="كاشير", role="admin",
                       password_hash=hash_password("Pass123!"), is_manager=True,
                       permissions=["sales", "pos", "shifts", "purchases", "inventory", "finance"], is_active=True)
        std = Product(id=uuid.uuid4(), tenant_id=t_id, name="صنف خاضع", code=f"S-{t_id.hex[:6]}", retail_price=D("114"),
                      cost_price=D("60"), stock_status="tracked", is_active=True)
        exempt = Product(id=uuid.uuid4(), tenant_id=t_id, name="صنف معفى", code=f"E-{t_id.hex[:6]}", retail_price=D("50"),
                         cost_price=D("60"), stock_status="tracked", is_active=True, tax_code="exempt")
        customer = Customer(id=uuid.uuid4(), tenant_id=t_id, name="عميل", balance=D("0"))
        supplier = Supplier(id=uuid.uuid4(), tenant_id=t_id, name="مورد", balance=D("0"))
        s.add_all([wh, cashier, std, exempt, customer, supplier])
        await s.flush()
        shift = Shift(id=uuid.uuid4(), tenant_id=t_id, cashier_id=cashier.id, warehouse_id=wh.id, status="open",
                      initial_amount=D("1000"), started_at=datetime.now(UTC))
        s.add(shift)
        await s.commit()
    current_tenant_id.set(t_id)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t_id)
        safe_id = uuid.uuid4()
        await s.execute(text("INSERT INTO safes (id, tenant_id, name, balance) VALUES (:id, :t, 'الخزينة الرئيسية', 1000)"),
                        {"id": safe_id, "t": t_id})
        settings = {"vat_registered": "true" if registered else "false", "prices_include_vat": "true" if inclusive else "false"}
        if registered:
            settings["tax_number"] = "123456789"
        for k, v in settings.items():
            await s.execute(text("INSERT INTO store_settings (id, tenant_id, key, value) VALUES (:id, :t, :k, :v)"),
                            {"id": uuid.uuid4(), "t": t_id, "k": k, "v": v})
        for p in (std, exempt):
            await apply_movement(s, product_id=p.id, warehouse_id=wh.id, movement_type=MovementType.opening_stock,
                                 qty=D("50"), unit_cost=D("60"), created_by=cashier.id)
        await s.commit()
    return {"tenant_id": t_id, "warehouse_id": wh.id, "cashier_id": cashier.id, "product_id": std.id,
            "exempt_id": exempt.id, "shift_id": shift.id, "customer_id": customer.id, "supplier_id": supplier.id,
            "safe_id": safe_id}


def _sale(env, items, **kw) -> SaleCreate:
    return SaleCreate(warehouse_id=env["warehouse_id"], shift_id=env["shift_id"],
                      items=[SaleItemCreate(product_id=p, qty=D(q), unit_price=D(price), discount=D(disc))
                             for p, q, price, disc in items], **kw)


async def _user(s, env) -> User:
    user = await s.get(User, env["cashier_id"])
    s.expunge(user)
    return user


async def _set(source_type: str, source_id, event: str | None = None) -> set[tuple]:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("""
            SELECT COALESCE(a.role, a.name) AS acc, l.debit, l.credit
            FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id JOIN acc_entries e ON e.id = l.entry_id
            WHERE e.source_type = :st AND e.source_id = :sid AND (CAST(:ev AS text) IS NULL OR e.event = :ev)
        """), {"st": source_type, "sid": source_id, "ev": event})).all()
    return {(r.acc, r.debit, r.credit) for r in rows}


async def _balances() -> dict[str, Decimal]:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(
            "SELECT COALESCE(a.role, a.name) AS acc, SUM(l.debit - l.credit) AS bal "
            "FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id GROUP BY 1"))).all()
    return {r.acc: r.bal for r in rows}


async def _rows(sql: str, **params) -> list:
    async with AsyncSessionLocal() as s:
        return (await s.execute(text(sql), params)).all()


async def _print(sale_id) -> str:
    from app.platform.printing.routes.sale import print_sale

    async with AsyncSessionLocal() as s:
        return (await print_sale(sale_id, s, None)).body.decode()


@db_only
async def test_pos_sale_with_prices_including_vat_posts_vat_output():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, [(env["product_id"], "2", "114", "0")]), env["cashier_id"])
    assert (sale.net_total, sale.tax_amount) == (D("228.00"), D("28.00"))
    line = sale.items[0]
    assert (line.tax_code, line.tax_rate, line.tax_amount, line.net_amount) == ("standard", D("14.00"), D("28.00"), D("200.00"))
    assert await _set("sale", sale.id, "confirm") == {
        (DRAWER, D("228.00"), D("0.00")), ("sales", D("0.00"), D("200.00")), ("vat_output", D("0.00"), D("28.00")),
        ("cogs", D("120.00"), D("0.00")), ("inventory", D("0.00"), D("120.00"))}
    html = await _print(sale.id)
    assert "فاتورة ضريبية" in html and "123-456-789" in html and "ضريبة القيمة المضافة" in html
    from app.platform.printing.routes import ar_egp
    assert ar_egp(28) in html and ar_egp(200) in html and ar_egp(228) in html


@db_only
async def test_discounts_zero_and_exempt_lines_and_prices_excluding_vat():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, [(env["product_id"], "1", "114", "14"),
                                                              (env["exempt_id"], "1", "50", "0")], discount_amount=D("10")),
                                               env["cashier_id"])
    assert (sale.net_total, sale.tax_amount) == (D("140.00"), D("11.46"))
    by_code = {i.tax_code: (i.net_amount, i.tax_amount) for i in sale.items}
    assert by_code == {"standard": (D("81.87"), D("11.46")), "exempt": (D("46.67"), D("0.00"))}
    assert ("sales", D("0.00"), D("128.54")) in await _set("sale", sale.id, "confirm")

    env = await _env(inclusive=False)
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE products SET tax_code = 'zero' WHERE id = :id"), {"id": env["exempt_id"]})
        # Prices exclude VAT here: the product is listed at 100 (the server sells at the listed price).
        await s.execute(text("UPDATE products SET retail_price = 100 WHERE id = :id"), {"id": env["product_id"]})
        await s.commit()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, [(env["product_id"], "1", "100", "0"),
                                                              (env["exempt_id"], "2", "50", "0")]), env["cashier_id"])
    # 100 + 14 % on top, and 100 zero-rated: the customer pays 214.
    assert (sale.total, sale.net_total, sale.tax_amount) == (D("200.00"), D("214.00"), D("14.00"))
    assert {i.tax_code for i in sale.items} == {"standard", "zero"}
    lines = await _set("sale", sale.id, "confirm")
    assert {(DRAWER, D("214.00"), D("0.00")), ("sales", D("0.00"), D("200.00")), ("vat_output", D("0.00"), D("14.00"))} <= lines


@db_only
async def test_unregistered_workspace_is_unchanged():
    env = await _env(registered=False)
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, [(env["product_id"], "2", "114", "0")]), env["cashier_id"])
    assert (sale.net_total, sale.tax_amount) == (D("228.00"), D("0.00"))
    assert (sale.items[0].tax_code, sale.items[0].tax_amount, sale.items[0].tax_rate) == (None, D("0.00"), D("0.00"))
    assert await _set("sale", sale.id, "confirm") == {
        (DRAWER, D("228.00"), D("0.00")), ("sales", D("0.00"), D("228.00")),
        ("cogs", D("120.00"), D("0.00")), ("inventory", D("0.00"), D("120.00"))}
    html = await _print(sale.id)
    assert "ضريبة" not in html and "123-456-789" not in html
    # Returns, purchases and expenses carry no VAT either; an expense can't take a tax amount.
    async with AsyncSessionLocal() as s:
        out = await sales_service.partial_return_sale(s, sale.id, {"items": [{"product_id": env["product_id"], "qty": 1}]},
                                                      env["cashier_id"])
    assert await _set("sale_return", uuid.UUID(out["sale_id"])) == {
        ("sales_returns", D("114.00"), D("0.00")), (DRAWER, D("0.00"), D("114.00")),
        ("inventory", D("60.00"), D("0.00")), ("cogs", D("0.00"), D("60.00"))}
    po = await _receive(env, qty="10", cost="114")
    assert await _set("purchase", po) == {("inventory", D("1140.00"), D("0.00")), ("payables", D("0.00"), D("1140.00"))}
    async with AsyncSessionLocal() as s:
        with pytest.raises(HTTPException, match="غير مسجلة"):
            await expense_service.check_tax(s, D("114"), D("14"))
    assert "vat_output" not in await _balances() and "vat_input" not in await _balances()


@db_only
async def test_return_takes_the_original_lines_tax_after_the_code_changed():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, [(env["product_id"], "3", "114", "0")]), env["cashier_id"])
    assert sale.tax_amount == D("42.00")
    async with AsyncSessionLocal() as s:  # the product becomes exempt after the sale
        await s.execute(text("UPDATE products SET tax_code = 'exempt' WHERE id = :id"), {"id": env["product_id"]})
        await s.commit()
    async with AsyncSessionLocal() as s:
        first = await sales_service.partial_return_sale(s, sale.id, {"items": [{"product_id": env["product_id"], "qty": 1}]},
                                                        env["cashier_id"])
    ret = uuid.UUID(first["sale_id"])
    row = (await _rows("SELECT net_total, tax_amount FROM sales WHERE id = :id", id=ret))[0]
    assert (row.net_total, row.tax_amount) == (D("114.00"), D("14.00"))
    item = (await _rows("SELECT tax_code, tax_rate, tax_amount, net_amount FROM sale_items WHERE sale_id = :id", id=ret))[0]
    assert tuple(item) == ("standard", D("14.00"), D("14.00"), D("100.00"))
    assert await _set("sale_return", ret) >= {("sales_returns", D("100.00"), D("0.00")), ("vat_output", D("14.00"), D("0.00")),
                                              (DRAWER, D("0.00"), D("114.00"))}
    html = await _print(ret)
    assert "ضريبة القيمة المضافة" in html
    # The rest comes back: the sale's VAT is returned in full, to the piastre.
    async with AsyncSessionLocal() as s:
        await sales_service.return_sale(s, sale.id, env["cashier_id"])
    assert (await _balances())["vat_output"] == D("0.00")
    assert (await _rows("SELECT SUM(tax_amount) FROM sales WHERE return_of = :id", id=sale.id))[0][0] == D("42.00")


async def _receive(env, qty="10", cost="114", paid="0", **extra) -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        po = await purchase_service.create_purchase(s, PurchaseCreate(
            warehouse_id=env["warehouse_id"], supplier_id=env["supplier_id"],
            items=[PurchaseItemCreate(product_id=env["product_id"], qty=D(qty), unit_cost=D(cost))]), user)
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await purchase_service.receive_purchase(s, uuid.UUID(po["id"]), PurchaseReceive(
            amount_paid=D(paid), safe_id=env["safe_id"] if D(paid) else None, **extra), user)
    return uuid.UUID(po["id"])


@db_only
async def test_purchase_posts_vat_input_and_the_average_cost_is_without_vat():
    env = await _env()
    po = await _receive(env)  # 10 x 114 including VAT: 1000 + 140
    assert await _set("purchase", po, "receive") == {("inventory", D("1000.00"), D("0.00")), ("vat_input", D("140.00"), D("0.00")),
                                                     ("payables", D("0.00"), D("1140.00"))}
    p = (await _rows("SELECT avg_cost, cost_price FROM products WHERE id = :id", id=env["product_id"]))[0]
    assert abs(p.avg_cost - (D("50") * 60 + D("1000")) / 60) < D("0.001") and p.cost_price == D("100.00")
    assert (await _rows("SELECT unit_cost FROM stock_movements WHERE purchase_id = :id", id=po))[0][0] == D("100.00")
    order = (await _rows("SELECT tax_amount, prices_include_vat FROM purchase_orders WHERE id = :id", id=po))[0]
    assert tuple(order) == (D("140.00"), True)
    assert (await _rows("SELECT balance FROM suppliers WHERE id = :id", id=env["supplier_id"]))[0][0] == D("1140.00")

    # Four go back: the order's own VAT in proportion, even though the product is exempt by now.
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE products SET tax_code = 'exempt' WHERE id = :id"), {"id": env["product_id"]})
        await s.commit()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        ret = await purchase_service.create_purchase_return(s, po, PurchaseReturnCreate(
            items=[PurchaseReturnItemIn(product_id=env["product_id"], qty=D("4"))]), user)
    assert (ret["total"], ret["tax_amount"]) == (D("456.00"), D("56.00"))
    assert await _set("purchase_return", uuid.UUID(ret["id"])) == {
        ("payables", D("456.00"), D("0.00")), ("inventory", D("0.00"), D("400.00")), ("vat_input", D("0.00"), D("56.00"))}
    assert (await _rows("SELECT unit_cost FROM stock_movements WHERE movement_type = 'return_out'"))[0][0] == D("100.00")

    # Prices excluding VAT, said on the receipt: 10 x 100 + 14 % on top.
    env = await _env()
    po = await _receive(env, cost="100", prices_include_vat=False)
    assert await _set("purchase", po, "receive") == {("inventory", D("1000.00"), D("0.00")), ("vat_input", D("140.00"), D("0.00")),
                                                     ("payables", D("0.00"), D("1140.00"))}


@db_only
async def test_expense_input_vat_and_the_vat_report():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, [(env["product_id"], "2", "114", "0")]), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        await sales_service.partial_return_sale(s, sale.id, {"items": [{"product_id": env["product_id"], "qty": 1}]},
                                                env["cashier_id"])
    await _receive(env)  # input VAT 140
    async with AsyncSessionLocal() as s:
        with pytest.raises(HTTPException, match="أقل من مبلغه"):
            await expense_service.check_tax(s, D("14"), D("14"))
        tax = await expense_service.check_tax(s, D("114"), D("14"))
        await bind_tenant(s, env["tenant_id"])
        eid = uuid.uuid4()
        await s.execute(text(
            "INSERT INTO expenses (id, tenant_id, amount, tax_amount, description, safe_id, payment_method, date, status) "
            "VALUES (:id, :t, 114, :tax, 'صيانة', :s, 'cash', CURRENT_DATE, 'draft')"),
            {"id": eid, "t": env["tenant_id"], "tax": tax, "s": env["safe_id"]})
        await s.commit()
    async with AsyncSessionLocal() as s:
        await expense_service.decide(s, eid, True, None, await _user(s, env))
        await s.commit()
    assert await _set("expense", eid, "approve") == {("other_expenses", D("100.00"), D("0.00")),
                                                     ("vat_input", D("14.00"), D("0.00")), (SAFE, D("0.00"), D("114.00"))}

    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        r = await vat_report(s, env["tenant_id"])
    assert r["output"] == {"sales": 28.0, "returns": 14.0, "other": 0.0, "total": 14.0}
    assert r["input"] == {"purchases": 140.0, "returns": 0.0, "expenses": 14.0, "other": 0.0, "total": 154.0}
    assert r["net_payable"] == -140.0 and r["vat_registered"] and r["tax_number"] == "123-456-789"
    assert len(r["by_month"]) == 1 and r["by_month"][0]["net"] == -140.0
    std = [c for c in r["by_code"]["sales"] if c["tax_code"] == "standard"][0]
    assert (std["taxable"], std["tax"], std["documents"]) == (200.0, 28.0, 1)
    assert r["by_code"]["sale_returns"][0]["tax"] == 14.0
    assert r["by_code"]["purchases"][0]["taxable"] == 1000.0
    assert r["by_code"]["expenses"] == {"taxable": 100.0, "tax": 14.0, "documents": 1}


@db_only
async def test_vat_settings_are_checked():
    from app.platform.settings.router import _check_vat_settings

    env = await _env(registered=False)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        with pytest.raises(HTTPException) as e:
            await _check_vat_settings(s, {"vat_registered": True})
        assert e.value.status_code == 422 and "رقم التسجيل" in e.value.detail
        with pytest.raises(HTTPException):
            await _check_vat_settings(s, {"tax_number": "12-34"})
        out = await _check_vat_settings(s, {"vat_registered": True, "tax_number": "100-200-300", "prices_include_vat": False})
        assert out == {"vat_registered": "true", "tax_number": "100200300", "prices_include_vat": "false"}
        assert await _check_vat_settings(s, {"store_name": "x"}) == {"store_name": "x"}
