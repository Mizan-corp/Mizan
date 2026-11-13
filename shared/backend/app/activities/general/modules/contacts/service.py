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
                          sale_id: uuid.UUID | None = None, note: str | None = None) -> CustomerPayment:
    """Money received from a customer: lowers their balance, credits the invoice if one is given,
    and goes into the receiving cashier's open drawer."""
    if amount <= 0:
        raise HTTPException(400, "المبلغ يجب أن يكون أكبر من 0")
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

    payment = CustomerPayment(customer_id=customer_id, sale_id=sale_id, amount=amount, note=note, created_by=user.id)
    db.add(payment)
    customer.balance = (customer.balance or 0) - amount
    if sale_id:
        await db.execute(text(
            "UPDATE sales SET paid_amount = COALESCE(paid_amount, 0) + :amt, last_paid_at = NOW() WHERE id = :sid"
        ), {"amt": amount, "sid": sale_id})
    await db.flush()  # the payment has its id before the audit entry refers to it
    await audit_log(db, "customer_payment", "create", user.id, user.full_name, payment.id,
                    {"customer_id": str(customer_id), "amount": float(amount), "sale_id": str(sale_id) if sale_id else None},
                    f"دفعة من {customer.name}")

    # Into the cashier's open drawer (the invoice's warehouse's shift, if there is an invoice).
    from app.activities.general.modules.pos.models import DrawerTransaction, DrawerTxType, Shift, ShiftStatus

    shift_query = select(Shift).where(Shift.cashier_id == user.id, Shift.status == ShiftStatus.open)
    if sale_warehouse:
        shift_query = shift_query.where(Shift.warehouse_id == sale_warehouse)
    shift = (await db.execute(shift_query.limit(1))).scalar_one_or_none()
    if shift:
        db.add(DrawerTransaction(shift_id=shift.id, type=DrawerTxType.deposit, amount=amount,
                                 note=f"دفعة من {customer.name}" + (f" — {note}" if note else ""), created_by=user.id))
    return payment
