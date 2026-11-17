"""Posting rules for purchases, supplier accounts and purchase returns (ADR-014 D3, step 3).

Purchase received (source 'purchase', event 'receive'), one entry, dated today:
    Dr inventory (the lines at their unit cost, without VAT), Dr VAT input (the order's tax_amount,
    ADR-014 D6) / Cr payables (party: the supplier) for the whole invoice
    and, for the amount paid at receipt: Dr payables (party) / Cr the safe or wallet it left from
Supplier payment (source 'supplier_tx', event 'payment'): Dr payables (party) / Cr the safe or wallet
Supplier charge, a debit entered by hand (source 'supplier_tx', event 'charge'): "we owe more"
    without goods (an invoice for a service, a fee): Dr other expenses / Cr payables (party)
Purchase return (source 'purchase_return', event 'confirm'), at the cost the goods came in at:
    Dr payables (party) for what lowers the supplier's balance, and Dr the safe or wallet for what
    the supplier paid back / Cr inventory (without VAT), Cr VAT input (the return's tax_amount)
A purchase order with no supplier posts its payables with no party.
"""
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import role, source_account, tenant_of
from app.activities.general.modules.accounting.services.posting import cr, dr, post, today


def _party(supplier_id) -> dict:
    return {"party_type": "supplier", "party_id": supplier_id} if supplier_id else {}


async def on_purchase_received(db: AsyncSession, *, purchase: dict, user_id=None, **_) -> None:
    tid = tenant_of(purchase)
    total = Decimal(str(purchase["total"] or 0))
    if total <= 0:
        return
    paid = Decimal(str(purchase.get("amount_paid") or 0))
    payables = await role(db, tid, "payables")
    party = _party(purchase.get("supplier_id"))
    wh = purchase.get("warehouse_id")
    tax = Decimal(str(purchase.get("tax_amount") or 0))
    lines = [dr(await role(db, tid, "inventory"), total - tax, warehouse_id=wh), cr(payables, total, warehouse_id=wh, **party)]
    if tax:
        lines.append(dr(await role(db, tid, "vat_input"), tax, warehouse_id=wh))
    if paid > 0:
        money = await source_account(db, tid, safe_id=purchase.get("safe_id"), wallet_id=purchase.get("wallet_id"))
        lines += [dr(payables, paid, warehouse_id=wh, **party), cr(money, paid, warehouse_id=wh)]
    await post(db, tid, "purchase", purchase["id"], "receive", today(), lines,
               memo=f"فاتورة مشتريات {purchase['po_number']}", warehouse_id=wh, user_id=user_id)


async def on_supplier_payment(db: AsyncSession, *, transaction: dict, user_id=None, **_) -> None:
    tid = tenant_of(transaction)
    amount = Decimal(str(transaction["amount"] or 0))
    if amount <= 0:
        return
    money = await source_account(db, tid, safe_id=transaction.get("safe_id"), wallet_id=transaction.get("wallet_id"))
    party = _party(transaction["supplier_id"])
    await post(db, tid, "supplier_tx", transaction["id"], "payment", today(),
               [dr(await role(db, tid, "payables"), amount, **party), cr(money, amount)],
               memo="دفعة لمورد" + (f" — {transaction['notes']}" if transaction.get("notes") else ""),
               user_id=user_id)


async def on_supplier_charge(db: AsyncSession, *, transaction: dict, user_id=None, **_) -> None:
    tid = tenant_of(transaction)
    amount = Decimal(str(transaction["amount"] or 0))
    if amount <= 0:
        return
    party = _party(transaction["supplier_id"])
    await post(db, tid, "supplier_tx", transaction["id"], "charge", today(),
               [dr(await role(db, tid, "other_expenses"), amount),
                cr(await role(db, tid, "payables"), amount, **party)],
               memo="مستحق لمورد (قيد يدوي)" + (f" — {transaction['notes']}" if transaction.get("notes") else ""),
               user_id=user_id)


async def on_purchase_returned(db: AsyncSession, *, purchase_return: dict, user_id=None, **_) -> None:
    tid = tenant_of(purchase_return)
    total = Decimal(str(purchase_return["total"] or 0))
    if total <= 0:
        return
    refund = Decimal(str(purchase_return.get("refund_amount") or 0))
    wh = purchase_return.get("warehouse_id")
    tax = Decimal(str(purchase_return.get("tax_amount") or 0))
    lines = [cr(await role(db, tid, "inventory"), total - tax, warehouse_id=wh)]
    if tax:
        lines.append(cr(await role(db, tid, "vat_input"), tax, warehouse_id=wh))
    if refund > 0:
        money = await source_account(db, tid, safe_id=purchase_return.get("safe_id"),
                                     wallet_id=purchase_return.get("wallet_id"))
        lines.append(dr(money, refund, warehouse_id=wh))
    if total - refund > 0:
        lines.append(dr(await role(db, tid, "payables"), total - refund, warehouse_id=wh,
                        **_party(purchase_return.get("supplier_id"))))
    await post(db, tid, "purchase_return", purchase_return["id"], "confirm", today(), lines,
               memo=f"مرتجع مشتريات {purchase_return['return_number']}", warehouse_id=wh, user_id=user_id)
