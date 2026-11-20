import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy import text as sqlt
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ForbiddenError, NotFoundError
from app.core.ratelimit import RateLimiter
from app.framework.events import notify
from app.activities.general.modules.pos.models import DrawerTransaction, DrawerTxType, Shift, ShiftStatus

if TYPE_CHECKING:
    from app.platform.auth.models.user import User


async def _find_employee_by_user_id(db: AsyncSession, user_id: uuid.UUID):
    """Find hr_employees record by matching user_id FK column."""
    result = await db.execute(
        sqlt("SELECT e.id FROM hr_employees e WHERE e.user_id = :uid AND e.is_active = TRUE LIMIT 1"),
        {"uid": user_id}
    )
    emp = result.scalar_one_or_none()
    if emp:
        return emp
    # Fallback: match emp_code = user UUID (legacy data)
    result = await db.execute(
        sqlt("SELECT e.id FROM hr_employees e WHERE e.emp_code = :uid_text AND e.is_active = TRUE LIMIT 1"),
        {"uid_text": str(user_id)}
    )
    return result.scalar_one_or_none()


async def _record_payroll_variance(db: AsyncSession, shift_id, difference, current_user_id, actor=None):
    """Record shift variance as payroll advance/deduction."""
    if difference == 0:
        return
    record_type = "خصم" if difference < 0 else "مكافأة"
    shift = await db.get(Shift, shift_id)
    if not shift or not shift.cashier_id:
        return
    branch = (await db.execute(sqlt("SELECT name FROM warehouses WHERE id = :id"), {"id": shift.warehouse_id})).scalar()
    opened = shift.started_at.strftime("%Y-%m-%d") if shift.started_at else ""
    note = f"فرق عجز/زيادة الدرج — وردية {branch or 'الفرع'} {opened}".strip()
    emp_id = await _find_employee_by_user_id(db, shift.cashier_id)
    if emp_id:
        await db.execute(sqlt("""
            INSERT INTO hr_advances (id, employee_id, amount, note, record_type, date, created_by)
            VALUES (gen_random_uuid(), :eid, :amt, :note, :rtype, NOW(), :uid)
        """), {"eid": emp_id, "amt": abs(float(difference)), "note": note, "rtype": record_type, "uid": str(actor or current_user_id)})


async def open_shift(db: AsyncSession, cashier_id: uuid.UUID, warehouse_id: uuid.UUID, initial_amount: Decimal, supervisor_id: uuid.UUID | None = None) -> Shift:
    """Open a new shift. One open shift per (cashier, warehouse): concurrent opens wait on an
    advisory lock keyed in SQL (hashtext: the same in every process, unlike Python's hash()), and
    a partial unique index refuses a second open shift whatever happens (POS-3)."""
    from sqlalchemy.exc import IntegrityError

    from app.platform.tenancy.context import current_tenant_id

    if initial_amount < 0:
        raise BusinessError("مبلغ العهدة لا يمكن أن يكون سالباً")
    wh = (await db.execute(sqlt("SELECT is_active FROM warehouses WHERE id = :id"), {"id": warehouse_id})).first()
    if wh is None:
        raise NotFoundError("الفرع غير موجود")
    if wh.is_active is False:
        raise BusinessError("هذا الفرع موقوف")
    if supervisor_id is not None:
        sup = (await db.execute(sqlt("SELECT is_active FROM users WHERE id = :id"), {"id": supervisor_id})).first()
        if sup is None or not sup.is_active:
            raise NotFoundError("المشرف غير موجود")
    await db.execute(sqlt("SELECT pg_advisory_xact_lock(hashtext(:k))"),
                     {"k": f"shift-open:{current_tenant_id.get()}:{cashier_id}:{warehouse_id}"})

    existing = await db.execute(
        select(Shift.id).where(
            Shift.warehouse_id == warehouse_id,
            Shift.cashier_id == cashier_id,
            Shift.status == ShiftStatus.open
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        raise BusinessError("لديك وردية مفتوحة بالفعل في هذا الفرع")

    shift = Shift(
        cashier_id=cashier_id,
        warehouse_id=warehouse_id,
        supervisor_id=supervisor_id,
        initial_amount=initial_amount,
    )
    db.add(shift)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("لديك وردية مفتوحة بالفعل في هذا الفرع")
    await db.refresh(shift)
    return shift


async def close_shift(db: AsyncSession, shift_id: uuid.UUID, closing_balance: Decimal, next_day_drawer: Decimal | None, notes: str | None, closed_by: uuid.UUID) -> dict:
    """Close a shift: compute summary, store expected_balance + difference."""
    result = await db.execute(select(Shift).where(Shift.id == shift_id).with_for_update())
    shift = result.scalar_one_or_none()
    if not shift:
        raise NotFoundError("الوردية غير موجودة")
    if shift.status != ShiftStatus.open:
        raise BusinessError("الوردية مغلقة بالفعل")
    if shift.cashier_id and shift.cashier_id != closed_by:
        raise ForbiddenError("الدرج مسجل باسم موظف آخر — لا يمكنك إغلاقه")

    keep = _next_day_drawer(closing_balance, next_day_drawer)
    summary = await compute_summary(db, shift_id)
    expected = summary["expected_balance"]
    difference = closing_balance - expected

    shift.status = ShiftStatus.closed
    shift.closing_balance = closing_balance
    shift.expected_balance = expected
    shift.difference = difference
    shift.next_day_drawer = keep
    shift.notes = notes
    shift.closed_by = closed_by
    shift.closed_at = datetime.now(UTC)

    await notify("shift.closed", db, shift=shift, user_id=closed_by)
    await db.commit()
    await db.refresh(shift)

    return {
        **{c.name: getattr(shift, c.name) for c in shift.__table__.columns},
        "variance": float(difference),
        "expected_balance": float(expected),
    }


async def _deposit_to_safe(db: AsyncSession, shift: Shift, amount: Decimal, manager_id, user_id) -> None:
    """The cash a manager takes out of the drawer when closing a shift (ADR-014 D4) goes into the
    workspace's safe, as a deposit for that shift (the ledger moves it from the branch drawer to the
    safe). The close request names no safe, so this happens only when the workspace has exactly one
    active cash safe; with none or several the amount stays recorded on the shift and nothing moves."""
    from app.activities.general.modules.finance.services import safes
    from app.platform.auth.models.user import User

    if not amount or amount <= 0:
        return
    safe_ids = (await db.execute(sqlt(
        "SELECT id FROM safes WHERE is_active AND COALESCE(safe_type, 'cash') <> 'bank' ORDER BY created_at, id"
    ))).scalars().all()
    if len(safe_ids) != 1:
        return
    user = await db.get(User, user_id)
    note = "إيداع نقدية وردية عند الإغلاق بحضور المدير"
    await safes.deposit(db, safe_ids[0], amount, user, shift_id=shift.id, warehouse_id=shift.warehouse_id,
                        received_by_id=manager_id, notes=note)
    await notify("safe.deposited", db, movement_id=uuid.uuid4(), safe_id=safe_ids[0], amount=amount,
                 shift_id=shift.id, note=note, user_id=user_id)


# ─── Manager approvals (POS-4) ─────────────────────────────────────────────────────────────────
# A manager approves at the counter by typing their password (closing with a manager, revenue
# delivery). Guessing it is slowed and then stopped: each user may ask for APPROVAL_ATTEMPTS a
# window, and APPROVAL_FAILURES wrong passwords by one user lock that user's approvals for the rest
# of the window, whichever manager they name. The lock is the guesser's only: counting per manager
# across the workspace would let one cashier lock every colleague's approvals on purpose. Counted in
# Redis when REDIS_URL is set (every worker), otherwise per process.
APPROVAL_ATTEMPTS = RateLimiter(max_requests=10, window_seconds=300)
APPROVAL_FAILURES = RateLimiter(max_requests=5, window_seconds=900)
APPROVAL_LOCKED = "تم إيقاف اعتماد المدير مؤقتاً بعد محاولات خاطئة متكررة — حاول مرة أخرى بعد 15 دقيقة"
NOT_AN_APPROVER = "المدير غير موجود أو لا يملك صلاحية اعتماد الورديات"


def can_approve(user) -> bool:
    """Who approves at the counter: a role that supervises shifts (`supervise`: managers by
    default), or a user flagged as a manager whose role holds `shifts`."""
    from app.platform.permissions.access import can

    return can(user, "supervise") or (bool(user.is_manager) and can(user, "shifts"))


async def _actor(db: AsyncSession, actor) -> "User":
    from app.platform.auth.models.user import User

    from app.platform.permissions.access import load_acting

    if isinstance(actor, User):
        if not hasattr(actor, "effective_permissions"):  # not loaded by a route (a direct call)
            await load_acting(db, actor)
        return actor
    user = await db.get(User, actor)
    if user is None:
        raise NotFoundError("المستخدم غير موجود")
    await load_acting(db, user)
    return user


async def verify_approver(db: AsyncSession, manager_id: uuid.UUID, password: str, actor) -> "User":
    """The manager approving `actor`'s request with their password: an active user of this
    workspace who can approve (can_approve). Rate limited and locked after repeated failures."""
    from app.platform.auth.models.user import User
    from app.platform.auth.security import verify_password
    from app.platform.permissions.access import load_acting

    tid = actor.tenant_id
    await APPROVAL_ATTEMPTS.hit(f"pos-approve:user:{actor.id}")
    keys = (f"pos-approve-fail:user:{actor.id}",)
    for key in keys:
        if await APPROVAL_FAILURES.count(key) >= APPROVAL_FAILURES.max_requests:
            raise HTTPException(429, APPROVAL_LOCKED, headers={"Retry-After": str(APPROVAL_FAILURES.window_seconds)})
    if manager_id == actor.id:
        mgr = actor
    else:
        mgr = (await db.execute(select(User).where(User.id == manager_id))).scalar_one_or_none()
        if mgr is not None:
            await load_acting(db, mgr)
    if mgr is None or not mgr.is_active or mgr.tenant_id != tid or not can_approve(mgr):
        raise BusinessError(NOT_AN_APPROVER)
    if not verify_password(password or "", mgr.password_hash):
        for key in keys:
            await APPROVAL_FAILURES.add(key)
        raise ForbiddenError("كلمة مرور المدير غير صحيحة")
    for key in keys:
        await APPROVAL_FAILURES.reset(key)
    return mgr


def _next_day_drawer(closing: Decimal, next_day_drawer: Decimal | None) -> Decimal:
    """What stays in the drawer for the next shift: all of it unless said, never below zero nor
    more than was counted (POS-5: a larger amount made the deposit to the safe negative)."""
    if next_day_drawer is None:
        return closing
    if next_day_drawer < 0:
        raise BusinessError("المبلغ المتروك في الدرج لا يمكن أن يكون سالباً")
    if next_day_drawer > closing:
        raise BusinessError("المبلغ المتروك في الدرج أكبر من الرصيد الفعلي عند الإغلاق")
    return next_day_drawer


async def close_shift_with_manager(db: AsyncSession, shift_id: uuid.UUID, data, actor) -> dict:
    """Close a shift with a manager present: the manager approves with their password
    (verify_approver) and receives the cash taken out of the drawer."""
    actor = await _actor(db, actor)
    current_user_id = actor.id
    keep = _next_day_drawer(data.closing_balance, data.next_day_drawer)
    mgr = await verify_approver(db, data.manager_id, data.manager_password, actor)

    result = await db.execute(select(Shift).where(Shift.id == shift_id).with_for_update())
    shift = result.scalar_one_or_none()
    if not shift:
        raise NotFoundError("الوردية غير موجودة")
    if shift.status != ShiftStatus.open:
        raise BusinessError("الوردية مغلقة بالفعل")

    summary = await compute_summary(db, shift_id)
    expected = summary["expected_balance"]
    closing = data.closing_balance
    difference = closing - expected

    deposit_amount = closing - keep

    shift.status = ShiftStatus.closed
    shift.closing_balance = closing
    shift.expected_balance = expected
    shift.difference = difference
    shift.next_day_drawer = keep
    shift.notes = data.notes
    shift.closed_by = current_user_id
    shift.deposit_received_by = mgr.id
    shift.deposit_amount = deposit_amount
    shift.closed_at = datetime.now(UTC)

    # Apply variance to payroll as deduction/bonus
    await _record_payroll_variance(db, shift_id, difference, current_user_id, current_user_id)
    await _deposit_to_safe(db, shift, deposit_amount, mgr.id, current_user_id)

    from app.platform.audit.service import log as audit_log

    await audit_log(db, "shift", "close_with_manager", current_user_id, actor.full_name, shift.id,
                    {"closing_balance": str(closing), "expected_balance": str(expected), "next_day_drawer": str(keep),
                     "deposit_amount": str(deposit_amount), "approved_by": mgr.full_name},
                    f"إغلاق وردية باعتماد {mgr.full_name}")
    await notify("shift.closed", db, shift=shift, user_id=current_user_id)
    await db.commit()
    await db.refresh(shift)

    return {
        **{c.name: getattr(shift, c.name) for c in shift.__table__.columns},
        "variance": float(difference),
        "expected_balance": float(expected),
    }


async def compute_summary(db: AsyncSession, shift_id: uuid.UUID) -> dict:
    """Compute full financial summary for a shift.

    expected_balance = cash-only balance in the physical drawer.
    Wallet transactions are tracked separately and do NOT affect the drawer.
    """
    shift = await db.get(Shift, shift_id)
    if not shift:
        raise NotFoundError("الوردية غير موجودة")

    live = (DrawerTransaction.shift_id == shift_id, DrawerTransaction.cancelled_at.is_(None))
    tx_count = await db.execute(select(func.count()).where(*live))

    # Aggregate the shift's drawer transactions by type (for display totals); cancelled rows don't count.
    rows = await db.execute(
        select(DrawerTransaction.type, func.sum(DrawerTransaction.amount).label("total"))
        .where(*live)
        .group_by(DrawerTransaction.type)
    )
    totals: dict[str, Decimal] = {}
    for row in rows:
        key = row.type.value if hasattr(row.type, 'value') else str(row.type)
        totals[key] = Decimal(str(row.total or 0))

    sales            = totals.get("sale", Decimal("0"))
    returns          = totals.get("return", Decimal("0"))
    expenses         = totals.get("expense", Decimal("0"))
    deposits         = totals.get("deposit", Decimal("0"))
    withdrawals      = totals.get("withdrawal", Decimal("0"))
    revenue_delivery = totals.get("revenue_delivery", Decimal("0"))

    # How the shift's sales were paid, from their payment lines (POS-6): a split payment counts
    # each part under its own method (it used to count the whole sale under the first one). Sales
    # recorded before payment lines existed count whole, under their payment method.
    pay_rows = await db.execute(sqlt("""
        SELECT method, wallet_name, wallet_type,
               COUNT(DISTINCT sale_id) AS count, COALESCE(SUM(amount), 0) AS total
        FROM (
            SELECT sp.method, pw.name AS wallet_name, pw.type AS wallet_type, s.id AS sale_id, sp.amount
            FROM sales s
            JOIN sale_payments sp ON sp.sale_id = s.id
            LEFT JOIN payment_wallets pw ON pw.id = sp.wallet_id
            WHERE s.shift_id = :sid AND s.status = 'confirmed'
            UNION ALL
            SELECT s.payment_method, pw.name, pw.type, s.id, s.net_total
            FROM sales s
            LEFT JOIN payment_wallets pw ON pw.id = s.wallet_id
            WHERE s.shift_id = :sid AND s.status = 'confirmed'
              AND NOT EXISTS (SELECT 1 FROM sale_payments sp WHERE sp.sale_id = s.id)
        ) lines
        GROUP BY method, wallet_name, wallet_type
        ORDER BY method, wallet_name
    """), {"sid": shift_id})
    payment_breakdown = [dict(r._mapping) for r in pay_rows.fetchall()]

    # What came in other than cash or on credit (wallets, bank, cheques).
    wallet_sales = sum((Decimal(str(p["total"])) for p in payment_breakdown if p["method"] not in ("cash", "credit")),
                       Decimal("0"))

    # Wallet deposits/expenses from drawer transactions
    wallet_tx_rows = await db.execute(sqlt("""
        SELECT dt.payment_method, pw.name as wallet_name, pw.type as wallet_type,
               dt.type as tx_type, SUM(dt.amount) as total
        FROM drawer_transactions dt
        LEFT JOIN payment_wallets pw ON pw.id = dt.wallet_id
        WHERE dt.shift_id = :sid AND dt.payment_method = 'wallet' AND dt.cancelled_at IS NULL
        AND dt.type IN ('deposit','expense','withdrawal')
        GROUP BY dt.payment_method, pw.name, pw.type, dt.type
    """), {"sid": shift_id})
    wallet_tx_breakdown = [dict(r._mapping) for r in wallet_tx_rows.fetchall()]

    # ── Cash-only expected balance ─────────────────────────────────────────
    # Only transactions with payment_method != 'wallet' affect the physical drawer.
    raw = await db.execute(
        select(DrawerTransaction.type, DrawerTransaction.amount, DrawerTransaction.payment_method)
        .where(*live)
    )
    cash_sums: dict[str, Decimal] = {}
    for r in raw.fetchall():
        t = r.type.value if hasattr(r.type, 'value') else str(r.type)
        amt = Decimal(str(r.amount or 0))
        pm = r.payment_method or "cash"
        if pm == "wallet":
            continue  # wallet transactions don't touch the physical drawer
        cash_sums[t] = cash_sums.get(t, Decimal("0")) + amt

    cash_sales            = cash_sums.get("sale", Decimal("0"))
    cash_returns          = cash_sums.get("return", Decimal("0"))
    cash_expenses         = cash_sums.get("expense", Decimal("0"))
    cash_deposits         = cash_sums.get("deposit", Decimal("0"))
    cash_withdrawals      = cash_sums.get("withdrawal", Decimal("0"))
    cash_revenue_delivery = cash_sums.get("revenue_delivery", Decimal("0"))

    # This is the ONLY expected_balance used everywhere (cash drawer only)
    expected = (
        shift.initial_amount
        + cash_sales + cash_deposits
        - cash_returns - cash_expenses - cash_withdrawals - cash_revenue_delivery
    )
    cash_in_drawer = expected
    variance = (shift.closing_balance - expected) if shift.closing_balance is not None else None

    return {
        "shift_id": shift_id,
        "initial_amount": shift.initial_amount,
        "sales_total": sales,
        "returns_total": returns,
        "expenses_total": expenses,
        "deposits_total": deposits,
        "withdrawals_total": withdrawals,
        "revenue_delivery_total": revenue_delivery,
        "expected_balance": expected,
        "cash_in_drawer": cash_in_drawer,
        "wallet_total": wallet_sales,
        "closing_balance": shift.closing_balance,
        "variance": variance,
        "transaction_count": tx_count.scalar_one(),
        "payment_breakdown": payment_breakdown,
        "wallet_tx_breakdown": wallet_tx_breakdown,
    }


async def _receiver(db: AsyncSession, to_user_id: uuid.UUID, shift: Shift):
    """Who takes over a drawer (POS-5): an active user of this workspace, not the shift's own
    cashier, whose role holds `shifts`, and who works in the shift's branch (assigned to it, or a
    manager / `supervise` holder)."""
    from app.platform.auth.models.user import User, user_warehouses
    from app.platform.permissions.access import can, load_acting

    if to_user_id == shift.cashier_id:
        raise BusinessError("لا يمكن تسليم العهدة إلى صاحب الوردية نفسه")
    user = (await db.execute(select(User).where(User.id == to_user_id))).scalar_one_or_none()
    if user is None or not user.is_active or user.tenant_id != shift.tenant_id:
        raise NotFoundError("المستلم غير موجود أو موقوف")
    await load_acting(db, user)
    if not can(user, "shifts"):
        raise BusinessError(f"{user.full_name} لا يملك صلاحية الورديات والدرج")
    if not (user.is_manager or can(user, "supervise")):
        assigned = (await db.execute(select(user_warehouses.c.warehouse_id).where(
            user_warehouses.c.user_id == user.id, user_warehouses.c.warehouse_id == shift.warehouse_id))).first()
        if assigned is None:
            raise BusinessError(f"{user.full_name} غير مسند إلى فرع هذه الوردية")
    return user


async def transfer_drawer(db: AsyncSession, shift_id: uuid.UUID, to_user_id: uuid.UUID, amount: Decimal, from_user_id: uuid.UUID | None, notes: str | None = None, closed_by: uuid.UUID | None = None) -> Shift:
    """Hand over a drawer to another user: close the current shift and open theirs with the
    amount handed over. `from_user_id` None: a manager or supervisor hands over someone's drawer.
    The receiver is checked (_receiver); the shift, the new shift and the handover document name
    people by name, and the document is made by whoever did it (closed_by)."""
    from app.platform.archive.models import ArchivedDocument, DocType
    from app.platform.auth.models.user import User

    result = await db.execute(select(Shift).where(Shift.id == shift_id).with_for_update())
    shift = result.scalar_one_or_none()
    if not shift:
        raise NotFoundError("الوردية غير موجودة")
    if shift.status != ShiftStatus.open:
        raise BusinessError("الوردية غير مفتوحة")
    # None = admin/privileged bypass; otherwise enforce ownership
    if from_user_id is not None and shift.cashier_id and shift.cashier_id != from_user_id:
        raise ForbiddenError("الدرج مسجل باسم موظف آخر")
    if amount is None or amount < 0:
        raise BusinessError("المبلغ المسلَّم لا يمكن أن يكون سالباً")
    receiver = await _receiver(db, to_user_id, shift)
    # Prevent duplicate open shifts for the receiver
    existing = await db.execute(
        select(Shift.id).where(
            Shift.warehouse_id == shift.warehouse_id,
            Shift.cashier_id == to_user_id,
            Shift.status == ShiftStatus.open
        ).with_for_update()
    )
    if existing.scalar_one_or_none():
        raise BusinessError("المستلم لديه وردية مفتوحة بالفعل في هذا الفرع — يرجى إغلاقها أولاً")

    actor = closed_by or from_user_id or shift.cashier_id
    giver = (await db.execute(select(User.full_name).where(User.id == shift.cashier_id))).scalar() or ""
    actor_name = (await db.execute(select(User.full_name).where(User.id == actor))).scalar() or ""
    extra = f" — {notes}" if notes else ""
    shift.status = ShiftStatus.closed
    shift.closing_balance = amount
    shift.next_day_drawer = amount
    shift.closed_by = actor
    shift.closed_at = datetime.now(UTC)
    shift.notes = f"تسليم عهدة إلى {receiver.full_name}{extra}"
    # Compute and store expected_balance for audit trail
    summary = await compute_summary(db, shift_id)
    expected = summary["expected_balance"]
    shift.expected_balance = expected
    shift.difference = amount - expected

    # Apply variance to payroll as deduction/bonus (same as close_shift_with_manager)
    difference = amount - expected
    await _record_payroll_variance(db, shift_id, difference, actor, actor)
    await notify("shift.closed", db, shift=shift, user_id=actor)

    new_shift = Shift(
        cashier_id=to_user_id,
        initial_amount=amount,
        warehouse_id=shift.warehouse_id,
        supervisor_id=shift.supervisor_id,
        notes=f"استلام عهدة من {giver}" if giver else "استلام عهدة",
    )
    db.add(new_shift)

    doc_number = f"HND-{datetime.now(UTC).strftime('%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
    db.add(ArchivedDocument(
        doc_number=doc_number,
        doc_type=DocType.shift_handover,
        amount=amount,
        ref_id=shift.id,
        created_by=actor,
        metadata_={
            "from_user": str(shift.cashier_id) if shift.cashier_id else "",
            "to_user": str(to_user_id),
            "from_user_name": giver,
            "to_user_name": receiver.full_name,
            "handed_over_by": actor_name,
            "amount": float(amount),
            "notes": notes or "",
        }
    ))
    from app.platform.audit.service import log as audit_log

    await audit_log(db, "shift", "transfer", actor, actor_name, shift.id,
                    {"to": receiver.full_name, "from": giver, "amount": str(amount), "expected_balance": str(expected),
                     "doc_number": doc_number}, f"تسليم عهدة إلى {receiver.full_name}")

    await db.commit()
    await db.refresh(new_shift)
    return new_shift


async def shift_people(db: AsyncSession, shift: Shift) -> dict:
    """Who the shifts screen offers for a shift: the managers who can approve at the counter
    (closing with a manager, revenue delivery: can_approve) and the colleagues the drawer can be
    handed to (the rules of _receiver, and no open shift of their own in the branch)."""
    from app.platform.auth.models.user import User, user_warehouses
    from app.platform.permissions.access import can, load_acting

    users = (await db.execute(select(User).where(User.tenant_id == shift.tenant_id, User.is_active.is_(True))
                              .order_by(User.full_name).limit(500))).scalars().all()
    assigned = set((await db.execute(select(user_warehouses.c.user_id).where(
        user_warehouses.c.warehouse_id == shift.warehouse_id))).scalars().all())
    busy = set((await db.execute(select(Shift.cashier_id).where(
        Shift.warehouse_id == shift.warehouse_id, Shift.status == ShiftStatus.open))).scalars().all())
    approvers, receivers = [], []
    for user in users:
        await load_acting(db, user)
        person = {"id": str(user.id), "full_name": user.full_name}
        if can_approve(user):
            approvers.append(person)
        if user.id != shift.cashier_id and user.id not in busy and can(user, "shifts") \
                and (user.is_manager or can(user, "supervise") or user.id in assigned):
            receivers.append(person)
    return {"approvers": approvers, "receivers": receivers}


MANUAL_TYPES = (DrawerTxType.deposit, DrawerTxType.expense, DrawerTxType.withdrawal)


async def add_transaction(db: AsyncSession, shift_id: uuid.UUID, tx_type: DrawerTxType, amount: Decimal, created_by: uuid.UUID, note: str | None = None, category_id: uuid.UUID | None = None, payment_method: str = "cash", wallet_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None) -> DrawerTransaction:
    """Add a drawer row by hand to the user's open shift: money in, an expense or money out
    (POS-1). Sale and return rows come only from their documents (a hand-made one lowered the
    expected cash and posted nothing), revenue delivery only from revenue_delivery(). The wallet,
    category and customer named are checked in this workspace."""
    tx_type = DrawerTxType(str(getattr(tx_type, "value", tx_type)))
    if tx_type not in MANUAL_TYPES:
        raise BusinessError("لا يُسجَّل يدوياً في الدرج إلا إيداع أو مصروف أو سحب")
    if amount is None or Decimal(str(amount)) <= 0:
        raise BusinessError("المبلغ يجب أن يكون أكبر من صفر")
    payment_method = payment_method or "cash"
    if payment_method not in ("cash", "wallet"):
        raise BusinessError("طريقة الدفع في الدرج نقدي أو محفظة فقط")
    result = await db.execute(select(Shift).where(Shift.id == shift_id).with_for_update())
    shift = result.scalar_one_or_none()
    if not shift:
        raise NotFoundError("الوردية غير موجودة")
    if shift.status != ShiftStatus.open:
        raise BusinessError("لا توجد وردية مفتوحة")
    if shift.cashier_id and shift.cashier_id != created_by:
        raise ForbiddenError("الدرج مسجل باسم موظف آخر")
    if payment_method == "wallet":
        if not wallet_id:
            raise BusinessError("يجب اختيار المحفظة")
        w = (await db.execute(sqlt("SELECT is_active FROM payment_wallets WHERE id = :id"), {"id": wallet_id})).first()
        if w is None:
            raise NotFoundError("المحفظة غير موجودة")
        if w.is_active is False:
            raise BusinessError("هذه المحفظة موقوفة")
    else:
        wallet_id = None
    if category_id is not None and (await db.execute(
            sqlt("SELECT 1 FROM financial_categories WHERE id = :id"), {"id": category_id})).first() is None:
        raise NotFoundError("التصنيف غير موجود")
    if customer_id is not None:
        if tx_type != DrawerTxType.deposit:
            raise BusinessError("تحصيل دين العميل يكون إيداعاً في الدرج")
        if (await db.execute(sqlt("SELECT 1 FROM customers WHERE id = :id FOR UPDATE"), {"id": customer_id})).first() is None:
            raise NotFoundError("العميل غير موجود")

    dt = DrawerTransaction(
        shift_id=shift_id,
        type=tx_type,
        amount=amount,
        note=note,
        category_id=category_id,
        payment_method=payment_method,
        wallet_id=wallet_id,
        created_by=created_by,
    )
    db.add(dt)

    # Update wallet balance if wallet payment
    if wallet_id and payment_method == "wallet":
        from app.activities.general.modules.finance.services.wallets import record_wallet_tx
        if tx_type == DrawerTxType.deposit:
            await record_wallet_tx(db, wallet_id, amount, "deposit", None, note, created_by)
        elif tx_type in (DrawerTxType.expense, DrawerTxType.withdrawal):
            await record_wallet_tx(db, wallet_id, -amount, "expense", None, note, created_by)

    # Customer debt payment, linked to its drawer row so cancelling the row reverses it.
    if customer_id and tx_type == DrawerTxType.deposit:
        from app.activities.general.modules.contacts.models.customer_payment import CustomerPayment
        on_wallet = bool(wallet_id and payment_method == "wallet")
        payment = CustomerPayment(
            id=uuid.uuid4(),
            customer_id=customer_id,
            amount=amount,
            note=note,
            created_by=created_by,
            method="wallet" if on_wallet else "cash",
            wallet_id=wallet_id if on_wallet else None,
            shift_id=None if on_wallet else shift_id,
        )
        db.add(payment)
        await db.flush()
        dt.customer_payment_id = payment.id
        # Never clamped at zero (POS-7): paying more than the debt leaves a credit the ledger shows too.
        await db.execute(sqlt(
            "UPDATE customers SET balance = COALESCE(balance,0) - :amt WHERE id = :cid",
        ), {"amt": Decimal(str(amount)), "cid": customer_id})
        await notify("customer_payment.received", db, payment=payment, user_id=created_by)

    await db.flush()
    await notify("drawer.transaction_added", db, tx=dt, shift=shift, user_id=created_by)
    await db.commit()
    await db.refresh(dt)
    return dt


async def revenue_delivery(db: AsyncSession, shift_id: uuid.UUID, data, current_user: "User") -> dict:
    """Mid-shift revenue delivery from the drawer to a safe — authorised by a manager's password.
    The money goes in through the finance safes service (row lock, numbered DEP document), never
    more than the cash the drawer should hold, from the user's own shift (or, for a supervisor, a
    shift of a branch they reach) into an active safe (POS-2)."""
    from app.activities.general.modules.finance.services import safes
    from app.dependencies import verify_warehouse_access
    from app.platform.permissions.access import can

    current_user = await _actor(db, current_user)
    mgr = await verify_approver(db, data.manager_id, data.manager_password, current_user)

    result = await db.execute(select(Shift).where(Shift.id == shift_id).with_for_update())
    shift = result.scalar_one_or_none()
    if not shift:
        raise NotFoundError("الوردية غير موجودة")
    if shift.status != ShiftStatus.open:
        raise BusinessError("الوردية مغلقة بالفعل")
    privileged = bool(current_user.is_manager or can(current_user, "supervise"))
    if shift.cashier_id and shift.cashier_id != current_user.id and not privileged:
        raise ForbiddenError("الدرج مسجل باسم موظف آخر")
    await verify_warehouse_access(db, current_user, shift.warehouse_id)

    safe = (await db.execute(sqlt("SELECT name, is_active FROM safes WHERE id = :id FOR UPDATE"),
                             {"id": data.safe_id})).first()
    if safe is None:
        raise NotFoundError("الخزنة غير موجودة")
    if not safe.is_active:
        raise BusinessError("الخزنة موقوفة")

    amount = Decimal(str(data.amount))
    in_drawer = Decimal(str((await compute_summary(db, shift_id))["expected_balance"]))
    if amount > in_drawer:
        raise BusinessError(f"المبلغ أكبر من النقدية المتوقعة في الدرج ({in_drawer:.2f} ج.م)")

    dt = DrawerTransaction(
        shift_id=shift_id,
        type=DrawerTxType.revenue_delivery,
        amount=amount,
        note=f"تسليم إيرادات إلى الخزنة. {data.notes or ''}",
        created_by=current_user.id,
    )
    db.add(dt)
    await db.flush()
    await notify("drawer.revenue_delivered", db, tx=dt, shift=shift, safe_id=data.safe_id, user_id=current_user.id)

    out = await safes.deposit(db, data.safe_id, amount, current_user, shift_id=shift.id,
                              warehouse_id=shift.warehouse_id, received_by_id=mgr.id,
                              notes=f"إيرادات من وردية — {data.notes or ''}")
    from app.platform.audit.service import log as audit_log

    await audit_log(db, "shift", "revenue_delivery", current_user.id, current_user.full_name, shift.id,
                    {"amount": str(amount), "safe_id": str(data.safe_id), "doc_number": out["doc_number"],
                     "received_by": str(mgr.id)}, f"تسليم إيرادات {out['doc_number']}")
    await db.commit()
    return {
        "doc_number": out["doc_number"],
        "amount": float(amount),
        "safe": safe.name,
        "received_by": mgr.full_name,
    }


async def delete_drawer_transaction(db: AsyncSession, tx_id: uuid.UUID, current_user_id: uuid.UUID) -> None:
    """Cancel a drawer row entered by hand (who may is checked by the route: those who approve at
    the counter, in a branch they reach). The row is kept and marked cancelled (ADR-014 D4), so the
    shift's totals skip it; a wallet movement it made is reversed, and a customer receipt it
    recorded is reversed by a negative receipt and the debt comes back. Rows of a sale or a return
    are changed through the sale (cancel or return), not here. Audited."""
    result = await db.execute(sqlt("""
        SELECT dt.*, sh.status as shift_status
        FROM drawer_transactions dt
        JOIN shifts sh ON sh.id = dt.shift_id
        WHERE dt.id = :id
        FOR UPDATE OF dt
    """), {"id": tx_id})
    row = result.fetchone()
    if not row:
        raise NotFoundError("العملية غير موجودة")
    tx = dict(row._mapping)
    if tx["shift_status"] == "closed":
        raise BusinessError("لا يمكن حذف معاملة من وردية مغلقة")
    if tx["cancelled_at"] is not None:
        raise BusinessError("هذه العملية ملغاة بالفعل")
    if tx["ref_id"] is not None:
        raise BusinessError("هذه العملية تخص فاتورة — ألغِ الفاتورة أو سجّل مرتجعاً بدلاً من حذفها")

    amt = Decimal(str(tx["amount"]))
    # Reverse wallet balance if wallet payment
    if tx.get("wallet_id") and tx.get("payment_method") == "wallet":
        from app.activities.general.modules.finance.services.wallets import record_wallet_tx
        if tx["type"] == "deposit":
            await record_wallet_tx(db, tx["wallet_id"], -amt, "deposit_reversed", tx_id, "حذف دواخل", current_user_id)
        elif tx["type"] in ("expense", "withdrawal"):
            await record_wallet_tx(db, tx["wallet_id"], amt, "expense_reversed", tx_id, "حذف خوارج", current_user_id)

    if tx.get("customer_payment_id"):
        from app.activities.general.modules.contacts.models.customer_payment import CustomerPayment
        paid = await db.get(CustomerPayment, tx["customer_payment_id"])
        if paid:
            db.add(CustomerPayment(customer_id=paid.customer_id, amount=-Decimal(str(paid.amount)),
                                   note=f"إلغاء دفعة من الدرج{(' — ' + paid.note) if paid.note else ''}",
                                   created_by=current_user_id))
            await db.execute(sqlt("UPDATE customers SET balance = COALESCE(balance,0) + :amt WHERE id = :cid"),
                             {"amt": Decimal(str(paid.amount)), "cid": paid.customer_id})

    await db.execute(sqlt("UPDATE drawer_transactions SET cancelled_at = now(), cancelled_by = :uid WHERE id = :id"),
                     {"uid": current_user_id, "id": tx_id})
    await notify("drawer.transaction_cancelled", db, tx=tx, user_id=current_user_id)
    from app.platform.audit.service import log as audit_log

    name = (await db.execute(sqlt("SELECT full_name FROM users WHERE id = :id"), {"id": current_user_id})).scalar()
    await audit_log(db, "shift", "cancel_drawer_tx", current_user_id, name, tx["shift_id"],
                    {"tx_id": str(tx_id), "type": str(tx["type"]), "amount": str(amt),
                     "payment_method": tx.get("payment_method") or "cash"},
                    f"إلغاء حركة درج ({amt:.2f} ج.م)")
    await db.commit()


# ─── Scanning (ADR-006 phase 8) ────────────────────────────────────────────────────────────────

async def scan(db: AsyncSession, code: str) -> dict:
    """What a scanned code adds to the cart: {"product", "qty", "scale"}.

    A product's barcode (or one of its extra barcodes) adds one. Otherwise the workspace's POS
    variant may read the code (`pos.scan`): the retail variant decodes weighing-scale labels."""
    from app.framework.hooks import emit
    from app.activities.general.modules.inventory.services.products import get_product_by_barcode

    code = code.strip()
    try:
        return {"product": await get_product_by_barcode(db, code), "qty": Decimal(1), "scale": None}
    except NotFoundError:
        pass
    for found in await emit("pos.scan", db, code=code):
        if found:
            return found
    raise NotFoundError("لا يوجد صنف بهذا الباركود")
