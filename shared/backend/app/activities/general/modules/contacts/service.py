"""Contacts: customer receipts (and their reversal), balance adjustments, and the customer's
statement. Callers commit."""
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.framework.events import notify
from app.activities.general.modules.contacts.models.customer_payment import CustomerPayment
from app.activities.general.modules.contacts.models.party import Customer
from app.activities.general.modules.sales.models.sale import Sale
from app.platform.audit.service import log as audit_log

CUSTOMER_NOT_FOUND = "العميل غير موجود"


async def default_credit_limit(db: AsyncSession) -> Decimal | None:
    """The workspace's `default_credit_limit` (manifest setting): the limit a new customer gets when
    none is given. 0, empty or unreadable: no limit."""
    from decimal import InvalidOperation

    from app.framework.loader import registry

    try:
        value = (await registry.get_settings(db, "contacts"))["values"].get("default_credit_limit")
        limit = Decimal(str(value)).quantize(Decimal("0.01")) if value not in (None, "") else None
    except (KeyError, InvalidOperation, ValueError):
        return None
    return limit if limit is not None and Decimal("0") < limit < Decimal("1e12") else None

# What a credit sale put on the customer's account (its credit payment lines; a sale from before
# those lines existed: its whole net), what its returns took off it, and what receipts paid on it.
INVOICE_DUE = """
    SELECT COALESCE(cr.amount, CASE WHEN cr.n = 0 AND COALESCE(s.is_credit, false)
                                    THEN COALESCE(it.lines, 0) - COALESCE(s.discount_amount, 0) ELSE 0 END) AS credit,
           COALESCE((SELECT SUM(rp.amount) FROM sale_payments rp JOIN sales r ON r.id = rp.sale_id
                     WHERE r.return_of = s.id AND r.status = 'returned' AND rp.method = 'credit'), 0) AS returned,
           COALESCE((SELECT SUM(cp.amount) FROM customer_payments cp WHERE cp.sale_id = s.id), 0) AS paid
    FROM sales s
    LEFT JOIN LATERAL (SELECT SUM(sp.amount) FILTER (WHERE sp.method = 'credit') AS amount, COUNT(*) AS n
                       FROM sale_payments sp WHERE sp.sale_id = s.id) cr ON true
    LEFT JOIN LATERAL (SELECT SUM(si.qty * si.unit_price - si.discount) AS lines FROM sale_items si
                       WHERE si.sale_id = s.id) it ON true
    WHERE s.id = :id
"""


async def _payable_invoice(db: AsyncSession, customer_id: uuid.UUID, sale_id: uuid.UUID, amount: Decimal) -> Sale:
    """The invoice a receipt pays: a confirmed credit sale of this customer (not cancelled, not a
    return), locked, with at least `amount` still due on it."""
    from app.activities.general.modules.sales.models.sale import SaleStatus

    sale = (await db.execute(select(Sale).where(Sale.id == sale_id).with_for_update())).scalar_one_or_none()
    if not sale:
        raise HTTPException(404, "الفاتورة غير موجودة")
    if str(sale.customer_id) != str(customer_id):
        raise HTTPException(400, "الفاتورة لا تخص هذا العميل")
    if sale.return_of is not None or sale.status != SaleStatus.confirmed:
        raise HTTPException(409, "لا يُسدَّد إلا على فاتورة مؤكدة (ليست ملغاة ولا مرتجعة)")
    row = (await db.execute(text(INVOICE_DUE), {"id": sale_id})).one()
    if Decimal(row.credit) <= 0:
        raise HTTPException(409, "الفاتورة ليست آجلة: لا يوجد عليها مبلغ مستحق للعميل")
    due = Decimal(row.credit) - Decimal(row.returned) - Decimal(row.paid)
    if amount > due:
        raise HTTPException(409, f"المبلغ أكبر من المتبقي على الفاتورة ({max(due, Decimal('0'))} ج.م)")
    return sale


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
        raise NotFoundError(CUSTOMER_NOT_FOUND)
    sale_warehouse = None
    if sale_id:
        sale = await _payable_invoice(db, customer_id, sale_id, amount)
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

        # Linked to the receipt, so cancelling the drawer row reverses the receipt.
        db.add(DrawerTransaction(shift_id=shift.id, type=DrawerTxType.deposit, amount=amount, note=label, created_by=user.id,
                                 customer_payment_id=payment.id))
    else:
        await payments.money_in(db, amount, safe_id=safe_id, wallet_id=wallet_id, ref_type="customer_payment",
                                ref_id=payment.id, note=label, user_id=user.id)
    await notify("customer_payment.received", db, payment=payment, user_id=user.id)
    return payment


async def adjust_balance(db: AsyncSession, customer_id: uuid.UUID, new_balance: Decimal, note: str | None, user) -> dict:
    """Set a customer's balance by recording an adjustment for the difference: the opening balance
    when the customer has no history yet, a correction otherwise. Nothing is overwritten silently."""
    from app.activities.general.modules.contacts.models.customer_payment import CustomerAdjustment

    customer = (await db.execute(select(Customer).where(Customer.id == customer_id).with_for_update())).scalar_one_or_none()
    if not customer:
        raise NotFoundError(CUSTOMER_NOT_FOUND)
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
        await notify("customer_adjustment.created", db, adjustment=adjustment, user_id=user.id)
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


ALREADY_REVERSED = "هذه الدفعة عُكست من قبل"


async def reverse_payment(db: AsyncSession, payment_id: uuid.UUID, reason: str, user) -> CustomerPayment:
    """Undo a receipt taken into a safe or wallet: the money goes back out of it, the customer owes
    the amount again (and the invoice, if it paid one), and the ledger entry is reversed. Recorded as
    a reversal (a negative receipt pointing to the original), never by deleting or editing it. A
    receipt into a cashier's drawer is undone by cancelling its drawer movement (shift screen)."""
    from app.activities.general.modules.finance.services import payments

    paid = (await db.execute(select(CustomerPayment).where(CustomerPayment.id == payment_id).with_for_update())).scalar_one_or_none()
    if paid is None:
        raise HTTPException(404, "الدفعة غير موجودة")
    if paid.amount is None or Decimal(str(paid.amount)) <= 0 or paid.reverses_id is not None:
        raise HTTPException(409, "هذه حركة عكس، لا تُعكس")
    if await db.scalar(text("SELECT 1 FROM customer_payments WHERE reverses_id = :id"), {"id": payment_id}):
        raise HTTPException(409, ALREADY_REVERSED)
    if paid.shift_id is not None:
        raise HTTPException(409, "استُلمت هذه الدفعة في درج وردية: ألغِ حركة الدرج من شاشة الوردية")
    if not paid.safe_id and not paid.wallet_id:
        raise HTTPException(409, "لا يُعرف أين دخل مبلغ هذه الدفعة، فلا يمكن عكسها. سجّل تسوية رصيد بدلاً من ذلك")
    customer = (await db.execute(select(Customer).where(Customer.id == paid.customer_id).with_for_update())).scalar_one()
    amount = Decimal(str(paid.amount))
    note = f"عكس دفعة من {customer.name} — {reason}"
    reversal = CustomerPayment(customer_id=paid.customer_id, sale_id=paid.sale_id, amount=-amount, note=note,
                               created_by=user.id, method=paid.method, safe_id=paid.safe_id, wallet_id=paid.wallet_id,
                               reverses_id=paid.id)
    db.add(reversal)
    await db.flush()
    await payments.money_out(db, amount, safe_id=paid.safe_id, wallet_id=paid.wallet_id,
                             ref_type="customer_payment_reversal", ref_id=reversal.id, note=note, user_id=user.id)
    customer.balance = (customer.balance or 0) + amount
    if paid.sale_id:
        await db.execute(text(
            "UPDATE sales SET paid_amount = GREATEST(COALESCE(paid_amount, 0) - :amt, 0) WHERE id = :sid"
        ), {"amt": amount, "sid": paid.sale_id})
    await audit_log(db, "customer_payment", "reverse", user.id, user.full_name, paid.id,
                    {"customer_id": str(paid.customer_id), "amount": float(amount), "reversal_id": str(reversal.id),
                     "reason": reason}, f"عكس دفعة من {customer.name}")
    await notify("customer_payment.reversed", db, payment=paid, reversal=reversal, user_id=user.id)
    return reversal


# A customer's statement: every line that changed what they owe, oldest first. `signed` is the change
# (+ owes more, − owes less); `amount` is what the line shows (adjustments keep their sign).
STATEMENT = """
    WITH lines AS (
        SELECT s.id, s.created_at AS at,
               CASE WHEN s.status = 'returned' THEN 'return' ELSE 'invoice' END AS type,
               s.invoice_number AS ref, NULL::text AS note, s.payment_method AS method, s.id AS sale_id,
               s.net_total AS document_total, d.amount,
               CASE WHEN s.status = 'returned' THEN -d.amount ELSE d.amount END AS signed,
               false AS can_reverse
        FROM sales s
        LEFT JOIN LATERAL (SELECT SUM(sp.amount) FILTER (WHERE sp.method = 'credit') AS amount, COUNT(*) AS n
                           FROM sale_payments sp WHERE sp.sale_id = s.id) cr ON true
        LEFT JOIN LATERAL (SELECT SUM(si.qty * si.unit_price - si.discount) AS lines FROM sale_items si
                           WHERE si.sale_id = s.id) it ON true
        CROSS JOIN LATERAL (SELECT COALESCE(cr.amount, CASE WHEN cr.n = 0 AND COALESCE(s.is_credit, false)
                                   THEN COALESCE(it.lines, 0) - COALESCE(s.discount_amount, 0) ELSE 0 END) AS amount) d
        WHERE s.customer_id = :cid AND d.amount > 0
          AND ((s.status = 'confirmed' AND s.return_of IS NULL) OR (s.status = 'returned' AND s.return_of IS NOT NULL))
        UNION ALL
        SELECT p.id, p.created_at, CASE WHEN p.amount < 0 THEN 'payment_reversal' ELSE 'payment' END,
               left(p.id::text, 8), p.note, p.method, p.sale_id, NULL, ABS(p.amount), -p.amount,
               (p.amount > 0 AND p.shift_id IS NULL AND (p.safe_id IS NOT NULL OR p.wallet_id IS NOT NULL)
                AND NOT EXISTS (SELECT 1 FROM customer_payments r WHERE r.reverses_id = p.id))
        FROM customer_payments p WHERE p.customer_id = :cid
        UNION ALL
        SELECT a.id, a.created_at, a.kind, left(a.id::text, 8), a.note, NULL, NULL, NULL, a.amount, a.amount, false
        FROM customer_adjustments a WHERE a.customer_id = :cid
    )
"""


async def _customer(db: AsyncSession, customer_id: uuid.UUID) -> Customer:
    c = (await db.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
    if c is None:
        raise NotFoundError(CUSTOMER_NOT_FOUND)
    return c


async def statement(db: AsyncSession, customer_id: uuid.UUID, page: int, page_size: int, newest_first: bool = False) -> dict:
    """One page of the statement, with the balance after each line (over the whole statement)."""
    await _customer(db, customer_id)
    total = (await db.execute(text(STATEMENT + "SELECT COUNT(*) FROM lines"), {"cid": customer_id})).scalar_one()
    order = "DESC" if newest_first else "ASC"
    rows = (await db.execute(text(STATEMENT + f"""
        SELECT l.*, SUM(l.signed) OVER (ORDER BY l.at, l.id) AS balance FROM lines l
        ORDER BY l.at {order}, l.id {order} LIMIT :lim OFFSET :off
    """), {"cid": customer_id, "lim": page_size, "off": (page - 1) * page_size})).mappings().all()
    items = [{"id": str(r["id"]), "type": r["type"], "ref": r["ref"], "note": r["note"], "method": r["method"],
              "sale_id": str(r["sale_id"]) if r["sale_id"] else None, "date": r["at"].isoformat(),
              "amount": float(r["amount"]), "debit": float(r["signed"]) if r["signed"] > 0 else 0.0,
              "credit": float(-r["signed"]) if r["signed"] < 0 else 0.0, "balance": float(r["balance"]),
              "document_total": float(r["document_total"]) if r["document_total"] is not None else None,
              "can_reverse": bool(r["can_reverse"])} for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size)}


async def account(db: AsyncSession, customer_id: uuid.UUID) -> dict:
    """The statement's totals: what was invoiced on credit, returned, paid and adjusted."""
    c = await _customer(db, customer_id)
    agg = (await db.execute(text(STATEMENT + """
        SELECT COALESCE(SUM(amount) FILTER (WHERE type = 'invoice'), 0) AS total_invoiced,
               COALESCE(SUM(amount) FILTER (WHERE type = 'return'), 0) AS total_returned,
               COALESCE(SUM(-signed) FILTER (WHERE type IN ('payment', 'payment_reversal')), 0) AS total_paid,
               COALESCE(SUM(signed) FILTER (WHERE type IN ('opening', 'adjustment')), 0) AS total_adjustments,
               COALESCE(SUM(signed), 0) AS balance_due
        FROM lines
    """), {"cid": customer_id})).mappings().one()
    return {
        "customer_id": str(customer_id),
        "customer_name": c.name,
        "phone": c.phone,
        "total_invoiced": float(agg["total_invoiced"]),
        "total_returned": float(agg["total_returned"]),
        "total_paid": float(agg["total_paid"]),
        "total_adjustments": float(agg["total_adjustments"]),
        "balance_due": float(agg["balance_due"]),
        "balance": float(c.balance or 0),
        "credit_limit": float(c.credit_limit) if c.credit_limit else None,
    }
