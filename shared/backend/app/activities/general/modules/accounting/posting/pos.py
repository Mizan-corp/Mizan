"""Posting rules for the cashier drawer (ADR-014 D3). Each branch has one drawer account.

Drawer row added by hand (source 'drawer_tx', event 'confirm'); rows of a sale, a return or a
customer receipt are posted with their document, not here:
    deposit:            Dr drawer (or the wallet it went to) / Cr the category's income account,
                        else other income
    expense/withdrawal: Dr the category's expense account, else other expenses / Cr drawer (or wallet)
Drawer row cancelled: the reversing entry of the row's entry (or of the customer receipt it held).
Revenue delivered to a safe (source 'drawer_tx', event 'revenue_delivery'):
    Dr the safe / Cr the drawer
Shift closed with a difference (source 'shift', event 'close'):
    short: Dr cash shortage / Cr drawer;  over: Dr drawer / Cr cash surplus
"""
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import drawer_account, role, tenant_of
from app.activities.general.modules.accounting.services import chart
from app.activities.general.modules.accounting.services.posting import cr, dr, post, reverse_source, today

MANUAL_TYPES = ("deposit", "expense", "withdrawal")


def _v(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _type(tx) -> str:
    t = _v(tx, "type")
    return getattr(t, "value", t)


async def on_drawer_transaction(db: AsyncSession, *, tx, shift, user_id=None, **_) -> None:
    kind = _type(tx)
    if kind not in MANUAL_TYPES or _v(tx, "ref_id") or _v(tx, "customer_payment_id"):
        return
    tid = tenant_of(shift)
    amount = Decimal(str(_v(tx, "amount") or 0))
    if amount <= 0:
        return
    if _v(tx, "payment_method") == "wallet" and _v(tx, "wallet_id"):
        money = await chart.money_account(db, tid, "wallet", _v(tx, "wallet_id"))
    else:
        money = await drawer_account(db, tid, shift.warehouse_id)
    counter = await chart.category_account(db, tid, _v(tx, "category_id"), "income" if kind == "deposit" else "expense")
    lines = [dr(money, amount), cr(counter, amount)] if kind == "deposit" else [dr(counter, amount), cr(money, amount)]
    label = {"deposit": "دواخل درج", "expense": "مصروف من الدرج", "withdrawal": "مسحوبات من الدرج"}[kind]
    note = _v(tx, "note")
    await post(db, tid, "drawer_tx", _v(tx, "id"), "confirm", today(), lines,
               memo=f"{label}{' — ' + note if note else ''}", warehouse_id=shift.warehouse_id,
               user_id=user_id or _v(tx, "created_by"))


async def on_drawer_cancelled(db: AsyncSession, *, tx, user_id=None, **_) -> None:
    tid = tenant_of(tx)
    if _v(tx, "customer_payment_id"):
        await reverse_source(db, tid, "customer_payment", _v(tx, "customer_payment_id"), "confirm", user_id=user_id,
                             memo="إلغاء تحصيل من الدرج")
    else:
        await reverse_source(db, tid, "drawer_tx", _v(tx, "id"), "confirm", user_id=user_id, memo="إلغاء حركة درج")


async def on_revenue_delivered(db: AsyncSession, *, tx, shift, safe_id, user_id=None, **_) -> None:
    tid = tenant_of(shift)
    amount = Decimal(str(_v(tx, "amount") or 0))
    safe = await chart.money_account(db, tid, "safe", safe_id)
    drawer = await drawer_account(db, tid, shift.warehouse_id)
    await post(db, tid, "drawer_tx", _v(tx, "id"), "revenue_delivery", today(), [dr(safe, amount), cr(drawer, amount)],
               memo="توريد إيرادات الدرج إلى الخزنة", warehouse_id=shift.warehouse_id, user_id=user_id)


async def on_shift_closed(db: AsyncSession, *, shift, user_id=None, **_) -> None:
    diff = Decimal(str(shift.difference or 0))
    if not diff:
        return
    tid = tenant_of(shift)
    drawer = await drawer_account(db, tid, shift.warehouse_id)
    if diff < 0:
        lines = [dr(await role(db, tid, "cash_shortage"), -diff), cr(drawer, -diff)]
        memo = "عجز الدرج عند إغلاق الوردية"
    else:
        lines = [dr(drawer, diff), cr(await role(db, tid, "cash_surplus"), diff)]
        memo = "زيادة الدرج عند إغلاق الوردية"
    await post(db, tid, "shift", shift.id, "close", today(), lines, memo=memo, warehouse_id=shift.warehouse_id,
               user_id=user_id or shift.closed_by)
