import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.framework import idempotency
from app.activities.general.modules.contacts.models.party import Customer
from app.activities.general.modules.finance.services.access import require_finance_or_manager
from app.platform.auth.models.user import User
from app.activities.general.modules.contacts.schemas import (CustomerCreate, CustomerPaymentCreate, CustomerUpdate, PaymentReverse,
                                                             SetBalanceRequest)
from app.activities.general.modules.contacts import service as contacts_service

router = APIRouter(tags=["parties"])

NOT_FOUND = contacts_service.CUSTOMER_NOT_FOUND
FULL_CUSTOMER_READERS = ("customers", "sales", "pos", "finance", "reports")
PICKER_FIELDS = ("id", "name", "phone", "is_active")


async def _clean_extra(db: AsyncSession, extra: dict | None, current: dict | None = None) -> dict:
    """A customer's custom field values, checked against the workspace's fields."""
    from app.framework.fields import clean_extra
    from app.framework.hooks import workspace_activity

    return await clean_extra(db, "customer", extra, await workspace_activity(db), current=current)


def _filters(search: str | None, include_inactive: bool) -> tuple[str, dict]:
    params: dict = {}
    where_parts = ["1=1"] if include_inactive else ["c.is_active"]
    if search:
        where_parts.append("(c.name ILIKE :search OR c.phone ILIKE :search)")
        params["search"] = f"%{search}%"
    return " AND ".join(where_parts), params


# ── Customers ────────────────────────────────────────────────────────────────
@router.get("/customers")
async def list_customers(search: Annotated[str | None, Query(max_length=128)] = None, include_inactive: bool = False,
                         limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0),
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Customers by name (the POS and every picker use it; a bare list, paged by limit/offset).
    The totals of the same filter are at /customers/summary. Balances, credit limits and the rest go
    to who works with customers (`customers`, `sales`, `pos`, `finance`, `reports`); anyone else signed
    in gets the picker's fields only."""
    from app.platform.permissions.access import can

    where, params = _filters(search, include_inactive)
    rows = await db.execute(text(f"""
        SELECT c.*, c.balance AS balance_due
        FROM customers c
        WHERE {where}
        ORDER BY c.name, c.id
        LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset})
    if can(user, *FULL_CUSTOMER_READERS):
        return [dict(r._mapping) for r in rows.fetchall()]
    return [{k: r._mapping[k] for k in PICKER_FIELDS} for r in rows.fetchall()]


@router.get("/customers/summary")
async def customers_summary(search: Annotated[str | None, Query(max_length=128)] = None, include_inactive: bool = False,
                            db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    """What the customer list's cards show, over every customer of the filter (not one page)."""
    where, params = _filters(search, include_inactive)
    row = (await db.execute(text(f"""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE c.balance > 0) AS debtors,
               COALESCE(SUM(c.balance) FILTER (WHERE c.balance > 0), 0) AS total_due,
               COUNT(*) FILTER (WHERE c.credit_limit > 0 AND c.balance > c.credit_limit) AS over_limit
        FROM customers c WHERE {where}
    """), params)).mappings().one()
    return dict(row)


@router.post("/customers")
async def create_customer(data: CustomerCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    """A customer. Without `credit_limit` in the request it gets the workspace's default credit limit
    (setting `default_credit_limit`; 0: none); `credit_limit: null` sent on purpose means no limit."""
    payload = data.model_dump()
    if "credit_limit" not in data.model_fields_set:
        payload["credit_limit"] = await contacts_service.default_credit_limit(db)
    payload["extra"] = await _clean_extra(db, payload.get("extra"))
    from app.platform.community.events import deliver_soon, publish

    c = Customer(**payload)
    db.add(c)
    await db.flush()
    hooks = await publish(db, "customer.created", {"id": str(c.id), "name": c.name, "phone": c.phone})
    await db.commit()
    deliver_soon(hooks)
    await db.refresh(c)
    return c


@router.put("/customers/{cid}")
async def update_customer(cid: uuid.UUID, data: CustomerUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    """Change only the fields sent. The balance changes through payments and adjustments only."""
    result = await db.execute(select(Customer).where(Customer.id == cid))
    c = result.scalar_one_or_none()
    if not c:
        raise NotFoundError(NOT_FOUND)
    changes = data.model_dump(exclude_unset=True)
    if "extra" in changes:
        changes["extra"] = await _clean_extra(db, changes["extra"], current=c.extra)
    for k, v in changes.items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return c


@router.get("/customers/{cid}/account")
async def customer_account(cid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers", "finance"))):
    """The statement's totals: invoiced on credit, returned, paid, adjusted, and the balance due."""
    return await contacts_service.account(db, cid)


@router.get("/customers/{cid}/ledger")
async def customer_ledger(
    cid: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    newest_first: bool = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("customers", "finance")),
):
    """The customer's statement: credit invoices, returns, receipts (and their reversals) and
    adjustments in date order, with the balance after each line; {items, total, page, pages}."""
    return await contacts_service.statement(db, cid, page, page_size, newest_first)


@router.put("/customers/{cid}/balance")
async def set_customer_balance(cid: uuid.UUID, data: SetBalanceRequest, db: AsyncSession = Depends(get_db),
                               current_user: User = Depends(require_finance_or_manager)):
    """Opening balance or correction: the difference is recorded as an adjustment, never overwritten.
    Lowering a balance writes off debt, so it needs `finance` or a manager, not `customers`."""
    result = await contacts_service.adjust_balance(db, cid, data.balance, data.note, current_user)
    await db.commit()
    return result


@router.delete("/customers/{cid}")
async def delete_customer(cid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_finance_or_manager)):
    """Only a customer with no sales, payments or adjustments is deleted; others are deactivated."""
    result = await db.execute(select(Customer).where(Customer.id == cid).with_for_update())
    c = result.scalar_one_or_none()
    if not c:
        raise NotFoundError(NOT_FOUND)
    if await contacts_service.has_transactions(db, cid):
        raise HTTPException(409, "لا يمكن حذف عميل له معاملات (مبيعات أو دفعات أو تسويات). يمكنك إيقافه بدلًا من ذلك")
    await db.delete(c)
    await db.commit()
    return {"ok": True}


@router.post("/customers/{cid}/deactivate")
async def deactivate_customer(cid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_finance_or_manager)):
    return await _set_active(db, cid, False)


@router.post("/customers/{cid}/activate")
async def activate_customer(cid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_finance_or_manager)):
    return await _set_active(db, cid, True)


async def _set_active(db: AsyncSession, cid: uuid.UUID, active: bool) -> dict:
    c = (await db.execute(select(Customer).where(Customer.id == cid))).scalar_one_or_none()
    if not c:
        raise NotFoundError(NOT_FOUND)
    c.is_active = active
    await db.commit()
    return {"id": str(cid), "is_active": active}


def _payment_out(p) -> dict:
    return {"id": str(p.id), "amount": float(p.amount), "note": p.note, "sale_id": str(p.sale_id) if p.sale_id else None,
            "method": p.method, "safe_id": str(p.safe_id) if p.safe_id else None,
            "wallet_id": str(p.wallet_id) if p.wallet_id else None, "shift_id": str(p.shift_id) if p.shift_id else None,
            "reverses_id": str(p.reverses_id) if p.reverses_id else None,
            "created_at": p.created_at.isoformat()}


@router.post("/customers/{cid}/payments")
async def add_payment(cid: uuid.UUID, data: CustomerPaymentCreate, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(require_perm("customers")),
                      idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Record a payment received from customer. With sale_id it pays that credit invoice (never more
    than is due on it). A retry with the same Idempotency-Key or client_id returns the first receipt."""
    key = idempotency.key_of(idempotency_key, data.client_id)
    payload = {"customer_id": cid, **data.model_dump(exclude={"client_id"})}
    if (replay := await idempotency.claim(db, "customer.payment", key, payload, current_user.id)) is not None:
        return replay
    p = await contacts_service.receive_payment(db, cid, data.amount, current_user, sale_id=data.sale_id, note=data.note,
                                               method=data.method, safe_id=data.safe_id, wallet_id=data.wallet_id)
    await db.flush()
    await db.refresh(p)
    result = _payment_out(p)
    await idempotency.remember(db, "customer.payment", key, result)
    await db.commit()
    return result


@router.post("/customers/payments/{pid}/reverse")
async def reverse_payment(pid: uuid.UUID, data: PaymentReverse, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(require_perm("finance"))):
    """Undo a receipt into a safe or wallet: the money goes back out, the customer owes it again,
    the ledger entry is reversed. Needs `finance`."""
    reversal = await contacts_service.reverse_payment(db, pid, data.reason.strip(), current_user)
    await db.flush()
    await db.refresh(reversal)
    out = _payment_out(reversal)
    await db.commit()
    return out
