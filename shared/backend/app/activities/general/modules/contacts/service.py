"""Contacts: customer payments. Callers commit."""
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.activities.general.modules.contacts.models.customer_payment import CustomerPayment
from app.activities.general.modules.contacts.models.party import Customer
from app.activities.general.modules.sales.models.sale import Sale
from app.platform.audit.service import log as audit_log


async def receive_payment(db: AsyncSession, customer_id: uuid.UUID, amount: Decimal, user, *,
                          sale_id: uuid.UUID | None = None, note: str | None = None, method: str | None = None,
                          safe_id: uuid.UUID | None = None, wallet_id: uuid.UUID | None = None) -> CustomerPayment:
    """Money received from a customer: lowers their balance, credits the invoice if one is given,
    and goes where the payment says (ADR-014 D4): into the chosen safe or wallet, or, for cash with
    no source chosen, into the receiving cashier's open drawer. Without either it is refused."""
    from app.activities.general.modules.finance.services import payments

    if amount <= 0:
        raise HTTPException(400, "المبلغ يجب أن يكون أكبر من 0")
    if safe_id and wallet_id:
        raise HTTPException(400, payments.ONE_SOURCE)
    customer = (await db.execute(select(Customer).where(Customer.id == customer_id).with_for_update())).scalar_one_or_none()
    if not customer:
        raise NotFoundError()
    sale_warehouse = None
    if sale_id:
        sale = (await db.execute(select(Sale).where(Sale.id == sale_id))).scalar_one_or_none()
        if not sale:
            raise HTTPException(404, "الفاتورة غير موجودة")
        if str(sale.customer_id) != str(customer_id):
            raise HTTPException(400, "الفاتورة لا تخص هذا العميل")
        sale_warehouse = sale.warehouse_id

    method = payments.method_of(safe_id, wallet_id, method)
    shift = None
    if not safe_id and not wallet_id:
        if method != "cash":
            raise HTTPException(400, "حدد الخزنة (أو الحساب البنكي) أو المحفظة التي استلمت المبلغ")
        # Into the cashier's open drawer (the invoice's warehouse's shift, if there is an invoice).
        from app.activities.general.modules.pos.models import Shift, ShiftStatus

        shift_query = select(Shift).where(Shift.cashier_id == user.id, Shift.status == ShiftStatus.open)
        if sale_warehouse:
            shift_query = shift_query.where(Shift.warehouse_id == sale_warehouse)
        shift = (await db.execute(shift_query.limit(1))).scalar_one_or_none()
        if shift is None:
            raise HTTPException(400, "لا توجد وردية مفتوحة لك — اختر الخزنة أو المحفظة التي استلمت المبلغ")

    payment = CustomerPayment(customer_id=customer_id, sale_id=sale_id, amount=amount, note=note, created_by=user.id,
                              method=method, safe_id=safe_id, wallet_id=wallet_id, shift_id=shift.id if shift else None)
    db.add(payment)
    customer.balance = (customer.balance or 0) - amount
    if sale_id:
        await db.execute(text(
            "UPDATE sales SET paid_amount = COALESCE(paid_amount, 0) + :amt, last_paid_at = NOW() WHERE id = :sid"
        ), {"amt": amount, "sid": sale_id})
    await db.flush()  # the payment has its id before the audit entry and the money movement refer to it
    await audit_log(db, "customer_payment", "create", user.id, user.full_name, payment.id,
                    {"customer_id": str(customer_id), "amount": float(amount), "sale_id": str(sale_id) if sale_id else None,
                     "method": method, "safe_id": str(safe_id) if safe_id else None,
                     "wallet_id": str(wallet_id) if wallet_id else None},
                    f"دفعة من {customer.name}")

    label = f"دفعة من {customer.name}" + (f" — {note}" if note else "")
    if shift is not None:
        from app.activities.general.modules.pos.models import DrawerTransaction, DrawerTxType

        db.add(DrawerTransaction(shift_id=shift.id, type=DrawerTxType.deposit, amount=amount, note=label, created_by=user.id))
    else:
        await payments.money_in(db, amount, safe_id=safe_id, wallet_id=wallet_id, ref_type="customer_payment",
                                ref_id=payment.id, note=label, user_id=user.id)
    return payment


async def adjust_balance(db: AsyncSession, customer_id: uuid.UUID, new_balance: Decimal, note: str | None, user) -> dict:
    """Set a customer's balance by recording an adjustment for the difference: the opening balance
    when the customer has no history yet, a correction otherwise. Nothing is overwritten silently."""
    from app.activities.general.modules.contacts.models.customer_payment import CustomerAdjustment

    customer = (await db.execute(select(Customer).where(Customer.id == customer_id).with_for_update())).scalar_one_or_none()
    if not customer:
        raise NotFoundError()
    before = Decimal(str(customer.balance or 0))
    new_balance = Decimal(str(new_balance))
    delta = new_balance - before
    adjustment = None
    if delta != 0:
        kind = "adjustment" if await has_transactions(db, customer_id) else "opening"
        adjustment = CustomerAdjustment(customer_id=customer_id, kind=kind, amount=delta, balance_before=before,
                                        balance_after=new_balance, note=note, created_by=user.id)
        db.add(adjustment)
        customer.balance = new_balance
        await db.flush()
        await audit_log(db, "customer_adjustment", "create", user.id, user.full_name, adjustment.id,
                        {"customer_id": str(customer_id), "kind": kind, "amount": float(delta),
                         "balance_before": float(before), "balance_after": float(new_balance)},
                        f"تسوية رصيد {customer.name}")
    return {"id": str(customer_id), "balance": float(new_balance),
            "adjustment_id": str(adjustment.id) if adjustment else None,
            "kind": adjustment.kind if adjustment else None, "amount": float(delta)}


async def has_transactions(db: AsyncSession, customer_id: uuid.UUID) -> bool:
    """Whether the customer has any sales, payments or balance adjustments."""
    return bool((await db.execute(text("""
        SELECT EXISTS (SELECT 1 FROM sales WHERE customer_id = :id)
            OR EXISTS (SELECT 1 FROM customer_payments WHERE customer_id = :id)
            OR EXISTS (SELECT 1 FROM customer_adjustments WHERE customer_id = :id)
    """), {"id": customer_id})).scalar())
