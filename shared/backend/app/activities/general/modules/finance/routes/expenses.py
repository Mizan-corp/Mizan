import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text as sqlt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.base import get_db
from app.dependencies import require_open_period, require_perm, verify_warehouse_access
from app.platform.auth.models.user import User
from app.platform.tenancy import clock
from app.activities.general.modules.finance.schemas.expense import ExpenseStatus, ExpenseApprove, ExpenseCancel, ExpenseCreate, ExpenseUpdate, ExpenseVendorCreate, ExpenseVendorUpdate
from app.activities.general.modules.finance.services import expenses as expenses_service
from app.activities.general.modules.finance.services.access import branch_scope

router = APIRouter(tags=["expenses"])


NO_CHANGES = "لا توجد حقول للتعديل"
EXPENSE_NOT_FOUND = "المصروف غير موجود"


async def _check_refs(db: AsyncSession, user, fields: dict) -> None:
    """The vendor, category, branch, safe and wallet an expense names must be the workspace's
    (404 otherwise, never a database error), and the branch one the user may use."""
    checks = {"vendor_id": ("expense_vendors", "الجهة غير موجودة"),
              "category_id": ("financial_categories", "التصنيف غير موجود"),
              "warehouse_id": ("warehouses", "الفرع غير موجود"),
              "safe_id": ("safes", "الخزنة غير موجودة"),
              "wallet_id": ("payment_wallets", "المحفظة غير موجودة")}
    for field, (table, message) in checks.items():
        value = fields.get(field)
        if value and not await db.scalar(sqlt(f"SELECT 1 FROM {table} WHERE id = :id"), {"id": value}):
            raise HTTPException(404, message)
    if fields.get("warehouse_id"):
        await verify_warehouse_access(db, user, fields["warehouse_id"])


def _branch_filter(branches: list[uuid.UUID] | None, where_parts: list[str], params: dict) -> None:
    """A user limited to some branches sees their branches' expenses and the company-wide ones."""
    if branches is not None:
        where_parts.append("(e.warehouse_id IS NULL OR e.warehouse_id = ANY(:whs))")
        params["whs"] = branches


# ── Expense Vendors ────────────────────────────────────────────────────────

@router.get("/expense-vendors")
async def list_vendors(search: Annotated[str | None, Query(max_length=128)] = None, include_inactive: bool = False,
                       db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    where = ["(:all OR v.is_active IS NOT FALSE)"]
    params: dict = {"all": include_inactive}
    if search:
        where.append("(v.name ILIKE :s OR v.phone ILIKE :s)")
        params["s"] = f"%{search}%"
    rows = await db.execute(sqlt(f"""
        SELECT v.*, (SELECT COUNT(*) FROM expenses e WHERE e.vendor_id = v.id) as expense_count
        FROM expense_vendors v WHERE {' AND '.join(where)}
        ORDER BY v.name
    """), params)
    return [dict(r._mapping) for r in rows.fetchall()]


@router.post("/expense-vendors", status_code=201)
async def create_vendor(data: ExpenseVendorCreate, db: AsyncSession = Depends(get_db),
                        current_user=Depends(require_perm("finance"))):
    r = await db.execute(sqlt("""
        INSERT INTO expense_vendors (name, phone, address, tax_id, notes, created_by)
        VALUES (:name, :phone, :address, :tax_id, :notes, :by)
        RETURNING *
    """), {"name": data.name, "phone": data.phone, "address": data.address,
            "tax_id": data.tax_id, "notes": data.notes, "by": current_user.id})
    await db.commit()
    return dict(r.mappings().first())


@router.put("/expense-vendors/{vid}")
async def update_vendor(vid: uuid.UUID, data: ExpenseVendorUpdate, db: AsyncSession = Depends(get_db),
                        _=Depends(require_perm("finance"))):
    """Change only the fields sent."""
    updates = data.model_dump(exclude_unset=True)
    for required in ("name", "is_active"):
        if required in updates and updates[required] is None:
            updates.pop(required)
    if not updates:
        raise HTTPException(400, NO_CHANGES)
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    r = await db.execute(sqlt(f"UPDATE expense_vendors SET {sets} WHERE id = :id RETURNING *"),
                         {**updates, "id": vid})
    row = r.mappings().first()
    if not row:
        raise NotFoundError("الجهة غير موجودة")
    await db.commit()
    return dict(row)


# ── Expenses ───────────────────────────────────────────────────────────────

@router.get("/expenses")
async def list_expenses(
    search: Annotated[str | None, Query(max_length=128)] = None,
    vendor_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    status: ExpenseStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    recurring: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("finance")),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "تاريخ البداية بعد تاريخ النهاية")
    branches = await branch_scope(db, current_user, warehouse_id)
    params: dict = {}
    where_parts = ["1=1"]
    if search:
        where_parts.append("(e.description ILIKE :s OR v.name ILIKE :s)")
        params["s"] = f"%{search}%"
    if vendor_id:
        where_parts.append("e.vendor_id = :vid")
        params["vid"] = vendor_id
    if category_id:
        where_parts.append("e.category_id = :cid")
        params["cid"] = category_id
    if warehouse_id:
        where_parts.append("e.warehouse_id = :wid")
        params["wid"] = warehouse_id
    else:
        _branch_filter(branches, where_parts, params)
    if status:
        where_parts.append("e.status = :st")
        params["st"] = status
    if date_from:
        where_parts.append("e.date >= :df")
        params["df"] = date_from
    if date_to:
        where_parts.append("e.date <= :dt")
        params["dt"] = date_to
    if recurring is not None:
        where_parts.append("e.is_recurring = :rec")
        params["rec"] = recurring
    where = " AND ".join(where_parts)
    offset = (page - 1) * page_size
    count = await db.execute(sqlt(f"SELECT COUNT(*) FROM expenses e LEFT JOIN expense_vendors v ON v.id = e.vendor_id WHERE {where}"), params)
    total = count.scalar()
    rows = await db.execute(sqlt(f"""
        SELECT e.*, v.name as vendor_name, fc.name as category_name, w.name as warehouse_name,
            u.full_name as created_by_name
        FROM expenses e
        LEFT JOIN expense_vendors v ON v.id = e.vendor_id
        LEFT JOIN financial_categories fc ON fc.id = e.category_id
        LEFT JOIN warehouses w ON w.id = e.warehouse_id
        LEFT JOIN users u ON u.id = e.created_by
        WHERE {where}
        ORDER BY e.date DESC, e.created_at DESC
        LIMIT :lim OFFSET :off
    """), {**params, "lim": page_size, "off": offset})
    return {"data": [dict(r._mapping) for r in rows.fetchall()], "total": total, "page": page, "page_size": page_size}


@router.post("/expenses", status_code=201)
async def create_expense(data: ExpenseCreate, db: AsyncSession = Depends(get_db),
                         current_user=Depends(require_perm("finance")), _=Depends(require_open_period)):
    await _check_refs(db, current_user, data.model_dump())
    tax = await expenses_service.check_tax(db, data.amount, data.tax_amount)
    r = await db.execute(sqlt("""
        INSERT INTO expenses (vendor_id, category_id, warehouse_id, amount, tax_amount, description, date,
            payment_method, wallet_id, safe_id, is_recurring, recurring_interval, recurring_end_date,
            notes, created_by, status)
        VALUES (:vendor_id, :category_id, :warehouse_id, :amount, :tax_amount, :description,
            :date, :payment_method, :wallet_id, :safe_id,
            :is_recurring, :recurring_interval, :recurring_end_date, :notes, :by, 'draft')
        RETURNING *
    """), {
        "vendor_id": data.vendor_id, "category_id": data.category_id,
        "warehouse_id": data.warehouse_id, "amount": data.amount, "tax_amount": tax,
        "description": data.description, "date": data.date or clock.today(),  # the workspace's day, not the database's
        "payment_method": data.payment_method, "wallet_id": data.wallet_id,
        "safe_id": data.safe_id, "is_recurring": data.is_recurring,
        "recurring_interval": data.recurring_interval,
        "recurring_end_date": data.recurring_end_date,
        "notes": data.notes, "by": current_user.id,
    })
    await db.commit()
    return dict(r.mappings().first())


@router.put("/expenses/{eid}")
async def update_expense(eid: uuid.UUID, data: ExpenseUpdate, db: AsyncSession = Depends(get_db),
                         _: User = Depends(require_perm("finance"))):
    current = (await db.execute(sqlt("SELECT status, amount, tax_amount FROM expenses WHERE id = :id FOR UPDATE"),
                                {"id": eid})).first()
    if current is None:
        raise NotFoundError(EXPENSE_NOT_FOUND)
    existing = current.status
    # Exclude 'status' — it must be changed via the approve/reject/cancel endpoints only
    allowed = set(ExpenseUpdate.model_fields.keys()) - {"status"}
    if existing in expenses_service.FINAL_STATUSES or existing == "rejected":
        allowed = {"notes"}  # decided (the money moved, was put back, or was refused): only the notes change
    changes = data.model_dump(exclude_unset=True)
    changes.pop("status", None)
    for required in ("amount", "description", "date"):
        if required in changes and changes[required] is None:
            changes.pop(required)
    if set(changes) - allowed:
        raise HTTPException(409, "لا يمكن تعديل مصروف معتمد أو ملغى أو مرفوض، يمكن تعديل الملاحظات فقط. لتصحيحه سجّل مصروفًا جديدًا")
    updates = {k: v for k, v in changes.items() if k in allowed}
    if not updates:
        raise HTTPException(400, NO_CHANGES)
    await _check_refs(db, _, updates)
    if "amount" in updates or "tax_amount" in updates:
        updates["tax_amount"] = await expenses_service.check_tax(
            db, updates.get("amount") or current.amount,
            updates["tax_amount"] if updates.get("tax_amount") is not None else current.tax_amount)
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    r = await db.execute(sqlt(f"UPDATE expenses SET {sets} WHERE id = :id RETURNING *"),
                         {**updates, "id": eid})
    await db.commit()
    return dict(r.mappings().first())


@router.post("/expenses/{eid}/approve")
async def approve_expense(eid: uuid.UUID, data: ExpenseApprove, db: AsyncSession = Depends(get_db),
                          current_user=Depends(require_perm("finance"))):
    await _check_refs(db, current_user, {"safe_id": data.safe_id, "wallet_id": data.wallet_id})
    row = await expenses_service.decide(db, eid, data.approved, data.notes, current_user,
                                        safe_id=data.safe_id, wallet_id=data.wallet_id)
    await db.commit()
    return row


@router.post("/expenses/{eid}/cancel")
async def cancel_expense(eid: uuid.UUID, data: ExpenseCancel | None = None, db: AsyncSession = Depends(get_db),
                         current_user=Depends(require_perm("finance"))):
    """Cancel an approved expense: its money goes back to the safe or wallet it came from."""
    row = await expenses_service.cancel(db, eid, data.reason if data else None, current_user)
    await db.commit()
    return row


@router.delete("/expenses/{eid}", status_code=204)
async def delete_expense(eid: uuid.UUID, db: AsyncSession = Depends(get_db),
                         _=Depends(require_perm("finance"))):
    """Only drafts and rejected expenses are deleted; an approved one is cancelled instead."""
    status = (await db.execute(sqlt("SELECT status FROM expenses WHERE id = :id FOR UPDATE"), {"id": eid})).scalar_one_or_none()
    if status is None:
        raise NotFoundError(EXPENSE_NOT_FOUND)
    if status in expenses_service.FINAL_STATUSES:
        raise HTTPException(409, "لا يمكن حذف مصروف معتمد أو ملغى. استخدم الإلغاء لإرجاع المبلغ")
    await db.execute(sqlt("DELETE FROM expenses WHERE id = :id"), {"id": eid})
    await db.commit()


# ── Expense Summary ────────────────────────────────────────────────────────

@router.get("/expenses/summary")
async def expense_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("finance", "reports")),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "تاريخ البداية بعد تاريخ النهاية")
    branches = await branch_scope(db, current_user, warehouse_id)
    params: dict = {}
    where_parts = ["e.status = 'approved'"]
    if date_from:
        where_parts.append("e.date >= :df")
        params["df"] = date_from
    if date_to:
        where_parts.append("e.date <= :dt")
        params["dt"] = date_to
    if warehouse_id:
        where_parts.append("e.warehouse_id = :wid")
        params["wid"] = warehouse_id
    else:
        _branch_filter(branches, where_parts, params)
    where = " AND ".join(where_parts)
    r = await db.execute(sqlt(f"""
        SELECT
            COALESCE(SUM(e.amount), 0) as total,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE e.is_recurring) as recurring_count,
            COALESCE(SUM(e.amount) FILTER (WHERE e.is_recurring), 0) as recurring_total
        FROM expenses e WHERE {where}
    """), params)
    summary = dict(r.mappings().first())

    cats = await db.execute(sqlt(f"""
        SELECT fc.name, fc.color, SUM(e.amount) as total, COUNT(*) as count
        FROM expenses e JOIN financial_categories fc ON fc.id = e.category_id
        WHERE {where}
        GROUP BY fc.name, fc.color ORDER BY total DESC
    """), params)
    summary["by_category"] = [dict(r._mapping) for r in cats.fetchall()]
    return summary
