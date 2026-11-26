"""Posting rules for sales (ADR-014 D3): confirmed sales, return documents, cancellations.

Sale confirmed (source 'sale', event 'confirm'), one entry:
    Dr  each payment line's money account (drawer / safe / wallet / bank), or receivables
        with the customer as party for the part on credit
    Cr  sales (net of discounts and of VAT: the sum of the payment lines, which is the sale's
        net_total, less its tax_amount)
    Cr  VAT output (the sale's tax_amount, ADR-014 D6; none when the workspace isn't VAT-registered)
    Dr  cost of goods sold / Cr inventory, at the lines' average cost (SaleItem.unit_cost x qty)
Return document (source 'sale_return', event 'confirm'):
    Dr  sales returns (without VAT), Dr VAT output (the return's tax_amount) / Cr each refund
        line's money account or receivables
    Dr  inventory / Cr cost of goods sold, at the cost the lines left at
Sale cancelled: the reversing entry of the sale's entry.
"""
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import payment_account, role, shift_warehouse, tenant_of
from app.activities.general.modules.accounting.services.posting import cr, dr, post, reverse_source, today


async def _payments(db: AsyncSession, sale_id) -> list:
    return (await db.execute(text(
        "SELECT method, wallet_id, safe_id, SUM(amount) AS amount FROM sale_payments WHERE sale_id = :id "
        "GROUP BY method, wallet_id, safe_id ORDER BY method"), {"id": sale_id})).all()


async def _cost(db: AsyncSession, sale_id) -> Decimal:
    return Decimal(str(await db.scalar(text(
        "SELECT COALESCE(SUM(qty * COALESCE(unit_cost, 0)), 0) FROM sale_items WHERE sale_id = :id"),
        {"id": sale_id}) or 0)).quantize(Decimal("0.01"))


async def _money_lines(db, tid, doc, payments, *, debit: bool) -> tuple[list, Decimal]:
    wh = await shift_warehouse(db, doc.shift_id) or doc.warehouse_id
    out, total = [], Decimal("0")
    for p in payments:
        amount = Decimal(str(p.amount or 0))
        if amount <= 0:
            continue
        total += amount
        if p.method == "credit":
            account = await role(db, tid, "receivables")
            party = {"party_type": "customer", "party_id": doc.customer_id}
        else:
            account = await payment_account(db, tid, p.method, safe_id=p.safe_id, wallet_id=p.wallet_id, drawer_warehouse=wh)
            party = {}
        out.append((dr if debit else cr)(account, amount, warehouse_id=doc.warehouse_id, **party))
    return out, total


async def on_sale_confirmed(db: AsyncSession, *, sale, user_id=None, **_) -> None:
    tid = tenant_of(sale)
    await db.flush()
    lines, revenue = await _money_lines(db, tid, sale, await _payments(db, sale.id), debit=True)
    tax = Decimal(str(sale.tax_amount or 0))
    lines.append(cr(await role(db, tid, "sales"), revenue - tax))
    if tax:
        lines.append(cr(await role(db, tid, "vat_output"), tax))
    cost = await _cost(db, sale.id)
    if cost > 0:
        lines += [dr(await role(db, tid, "cogs"), cost), cr(await role(db, tid, "inventory"), cost)]
    await post(db, tid, "sale", sale.id, "confirm", today(), lines, memo=f"فاتورة مبيعات {sale.invoice_number}",
               warehouse_id=sale.warehouse_id, user_id=user_id or sale.created_by)


async def on_sale_returned(db: AsyncSession, *, sale, returned=None, user_id=None, **_) -> None:
    if returned is None:
        return
    ret = returned
    tid = tenant_of(ret)
    await db.flush()
    lines, refunded = await _money_lines(db, tid, ret, await _payments(db, ret.id), debit=False)
    tax = Decimal(str(ret.tax_amount or 0))
    lines.append(dr(await role(db, tid, "sales_returns"), refunded - tax))
    if tax:
        lines.append(dr(await role(db, tid, "vat_output"), tax))
    cost = await _cost(db, ret.id)
    if cost > 0:
        lines += [dr(await role(db, tid, "inventory"), cost), cr(await role(db, tid, "cogs"), cost)]
    await post(db, tid, "sale_return", ret.id, "confirm", today(), lines,
               memo=f"مرتجع مبيعات {ret.invoice_number} من {sale.invoice_number}",
               warehouse_id=ret.warehouse_id, user_id=user_id or ret.created_by)


async def on_sale_cancelled(db: AsyncSession, *, sale, user_id=None, **_) -> None:
    await reverse_source(db, tenant_of(sale), "sale", sale.id, "confirm", user_id=user_id,
                         memo=f"إلغاء فاتورة {sale.invoice_number}")
