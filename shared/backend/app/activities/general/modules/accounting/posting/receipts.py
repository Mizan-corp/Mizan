"""Posting rules for what customers owe (ADR-014 D3).

Customer receipt (source 'customer_payment', event 'confirm'):
    Dr the safe / wallet / branch drawer (or the default bank for bank and cheque) / Cr receivables (party)
Balance adjustment (source 'customer_adjustment', event 'confirm'), amount = the signed change:
    opening    : up: Dr receivables / Cr opening balance equity;  down: the opposite
    adjustment : up: Dr receivables / Cr other income;  down: Dr other expenses / Cr receivables
"""
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import payment_account, role, shift_warehouse, tenant_of
from app.activities.general.modules.accounting.services.posting import cr, dr, post, today


async def on_customer_payment(db: AsyncSession, *, payment, user_id=None, **_) -> None:
    amount = Decimal(str(payment.amount or 0))
    if amount <= 0:
        return
    tid = tenant_of(payment)
    wh = await shift_warehouse(db, payment.shift_id)
    money = await payment_account(db, tid, payment.method, safe_id=payment.safe_id, wallet_id=payment.wallet_id,
                                  drawer_warehouse=wh)
    party = {"party_type": "customer", "party_id": payment.customer_id}
    await post(db, tid, "customer_payment", payment.id, "confirm", today(),
               [dr(money, amount), cr(await role(db, tid, "receivables"), amount, **party)],
               memo="تحصيل من عميل" + (f" — {payment.note}" if payment.note else ""), warehouse_id=wh,
               user_id=user_id or payment.created_by)


async def on_customer_adjustment(db: AsyncSession, *, adjustment, user_id=None, **_) -> None:
    delta = Decimal(str(adjustment.amount or 0))
    if not delta:
        return
    tid = tenant_of(adjustment)
    receivables = await role(db, tid, "receivables")
    party = {"party_type": "customer", "party_id": adjustment.customer_id}
    amount = abs(delta)
    if adjustment.kind == "opening":
        equity = await role(db, tid, "opening_equity")
        lines = ([dr(receivables, amount, **party), cr(equity, amount)] if delta > 0
                 else [dr(equity, amount), cr(receivables, amount, **party)])
        memo = "رصيد افتتاحي لعميل"
    elif delta > 0:
        lines = [dr(receivables, amount, **party), cr(await role(db, tid, "other_income"), amount)]
        memo = "تسوية رصيد عميل (زيادة)"
    else:
        lines = [dr(await role(db, tid, "other_expenses"), amount), cr(receivables, amount, **party)]
        memo = "تسوية رصيد عميل (تخفيض)"
    if adjustment.note:
        memo += f" — {adjustment.note}"
    await post(db, tid, "customer_adjustment", adjustment.id, "confirm", today(), lines, memo=memo,
               user_id=user_id or adjustment.created_by)
