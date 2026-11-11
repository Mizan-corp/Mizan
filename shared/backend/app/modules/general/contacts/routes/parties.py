import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.modules.general.contacts.models.customer_payment import CustomerPayment
from app.modules.general.contacts.models.party import Customer
from app.modules.general.sales.models.sale import Sale, SaleStatus
from app.platform.auth.models.user import User
from app.modules.general.contacts.schemas import CustomerCreate, CustomerPaymentCreate, CustomerUpdate, SetBalanceRequest
from app.modules.general.contacts import service as contacts_service

router = APIRouter(tags=["parties"])


async def _clean_extra(db: AsyncSession, extra: dict | None, current: dict | None = None) -> dict:
    """A customer's custom field values, checked against the workspace's fields."""
    from app.framework.fields import clean_extra
    from app.framework.hooks import workspace_activity

    return await clean_extra(db, "customer", extra, await workspace_activity(db), current=current)


# ── Customers ────────────────────────────────────────────────────────────────
@router.get("/customers")
async def list_customers(search: str | None = None, limit: int = Query(200, le=1000), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    from sqlalchemy import text as sqlt
    params: dict = {}
    where_parts = ["1=1"]
    if search:
        where_parts.append("c.name ILIKE :search")
        params["search"] = f"%{search}%"
    where = " AND ".join(where_parts)
    # Add basic pagination to avoid returning an unbounded result set
    params.update({"limit": limit, "offset": offset})
    rows = await db.execute(sqlt(f"""
        SELECT c.*, c.balance AS balance_due
        FROM customers c
        WHERE {where}
        ORDER BY c.name
        LIMIT :limit OFFSET :offset
    """    ), params)
    return [dict(r._mapping) for r in rows.fetchall()]


@router.post("/customers")
async def create_customer(data: CustomerCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    payload = data.model_dump()
    payload["extra"] = await _clean_extra(db, payload.get("extra"))
    c = Customer(**payload)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@router.put("/customers/{cid}")
async def update_customer(cid: uuid.UUID, data: CustomerUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    result = await db.execute(select(Customer).where(Customer.id == cid))
    c = result.scalar_one_or_none()
    if not c:
        raise NotFoundError()
    changes = data.model_dump(exclude_unset=True)
    if "extra" in changes:
        changes["extra"] = await _clean_extra(db, changes["extra"], current=c.extra)
    for k, v in changes.items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return c


@router.get("/customers/{cid}/account")
async def customer_account(cid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Customer ledger: total invoiced, total paid, balance due."""
    from sqlalchemy import text as sqlt
    c = (await db.execute(select(Customer).where(Customer.id == cid))).scalar_one_or_none()
    if not c:
        raise NotFoundError()

    r = await db.execute(sqlt("""
        SELECT
            COALESCE((
                SELECT SUM(invoice_net)
                FROM (
                    SELECT s.id,
                           SUM(si.qty * si.unit_price - si.discount) - COALESCE(s.discount_amount, 0) AS invoice_net
                    FROM sales s
                    JOIN sale_items si ON si.sale_id = s.id
                    WHERE s.customer_id = :cid AND s.is_credit = true AND s.status = 'confirmed'
                    GROUP BY s.id, s.discount_amount
                ) inv
            ), 0) AS total_invoiced,
            COALESCE((
                SELECT SUM(invoice_net)
                FROM (
                    SELECT s.id,
                           SUM(si.qty * si.unit_price - si.discount) AS invoice_net
                    FROM sales s
                    JOIN sale_items si ON si.sale_id = s.id
                    WHERE s.customer_id = :cid AND s.status = 'returned' AND s.is_credit = true
                    GROUP BY s.id
                ) ret
            ), 0) AS total_returned,
            COALESCE((SELECT SUM(amount) FROM customer_payments WHERE customer_id = :cid), 0)
            AS total_paid
    """), {"cid": cid})
    agg = dict(r.fetchone()._mapping)

    return {
        "customer_id": str(cid),
        "customer_name": c.name,
        "phone": c.phone,
        "total_invoiced": float(agg["total_invoiced"]),
        "total_returned": float(agg["total_returned"]),
        "total_paid": float(agg["total_paid"]),
        "balance_due": float(agg["total_invoiced"]) - float(agg["total_returned"]) - float(agg["total_paid"]),
        "credit_limit": float(c.credit_limit) if c.credit_limit else None,
    }


@router.get("/customers/{cid}/ledger")
async def customer_ledger(
    cid: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Full chronological ledger: invoices + returns + payments with pagination."""
    from sqlalchemy.orm import selectinload

    sales_count_q = select(func.count()).select_from(Sale).where(
        Sale.customer_id == cid,
        Sale.status.in_([SaleStatus.confirmed, SaleStatus.returned]),
        Sale.is_credit,
    )
    sales_total = (await db.execute(sales_count_q)).scalar() or 0

    payments_count_q = select(func.count()).select_from(CustomerPayment).where(
        CustomerPayment.customer_id == cid,
    )
    payments_total = (await db.execute(payments_count_q)).scalar() or 0

    offset = (page - 1) * page_size

    sales = (await db.execute(
        select(Sale).options(selectinload(Sale.items))
        .where(Sale.customer_id == cid,
               Sale.status.in_([SaleStatus.confirmed, SaleStatus.returned]),
               Sale.is_credit)
        .order_by(Sale.created_at.asc())
        .offset(offset).limit(page_size)
    )).scalars().all()

    payments = (await db.execute(
        select(CustomerPayment).where(CustomerPayment.customer_id == cid)
        .order_by(CustomerPayment.created_at.desc())
        .offset(offset).limit(page_size)
    )).scalars().all()

    entries = []
    for s in sales:
        total = sum(float(i.qty) * float(i.unit_price) - float(i.discount) for i in s.items)
        entries.append({
            "type": "invoice" if s.status == SaleStatus.confirmed else "return",
            "ref": s.invoice_number,
            "amount": total,
            "date": s.created_at.isoformat(),
            "items_count": len(s.items),
        })
    for p in payments:
        entries.append({
            "type": "payment",
            "ref": str(p.id)[:8],
            "amount": float(p.amount),
            "note": p.note,
            "date": p.created_at.isoformat(),
        })
    entries.sort(key=lambda e: e["date"])

    return [*entries, {
        "__pagination": {
            "page": page,
            "page_size": page_size,
            "sales_total": sales_total,
            "payments_total": payments_total,
            "sales_pages": max(1, (sales_total + page_size - 1) // page_size),
            "payments_pages": max(1, (payments_total + page_size - 1) // page_size),
        },
    }]


@router.put("/customers/{cid}/balance")
async def set_customer_balance(cid: uuid.UUID, data: SetBalanceRequest, db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    result = await db.execute(select(Customer).where(Customer.id == cid).with_for_update())
    c = result.scalar_one_or_none()
    if not c:
        raise NotFoundError()
    balance = data.balance
    c.balance = balance
    await db.commit()
    return {"id": str(cid), "balance": float(balance)}


@router.delete("/customers/{cid}")
async def delete_customer(cid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    result = await db.execute(select(Customer).where(Customer.id == cid))
    c = result.scalar_one_or_none()
    if not c:
        raise NotFoundError()
    await db.delete(c)
    await db.commit()
    return {"ok": True}


@router.post("/customers/{cid}/payments")
async def add_payment(cid: uuid.UUID, data: CustomerPaymentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("customers"))):
    """Record a payment received from customer.  If sale_id is provided, the payment is attributed to that invoice."""
    p = await contacts_service.receive_payment(db, cid, data.amount, current_user, sale_id=data.sale_id, note=data.note)
    await db.commit()
    await db.refresh(p)
    return {"id": str(p.id), "amount": float(p.amount), "note": p.note, "sale_id": str(p.sale_id) if p.sale_id else None, "created_at": p.created_at.isoformat()}


