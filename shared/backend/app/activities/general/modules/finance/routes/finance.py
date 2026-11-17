"""Financial categories, users' permissions, the drawer movements by category, the audit log."""
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User
from app.activities.general.modules.finance.schemas.finance import FinancialCategoryCreate, FinancialCategoryUpdate, PermissionsUpdate

router = APIRouter(tags=["finance"])

CATEGORY_NOT_FOUND = "التصنيف غير موجود"


# ── Financial Categories ───────────────────────────────────────────────────
@router.get("/financial-categories")
async def list_categories(include_inactive: bool = False, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    r = await db.execute(text(
        "SELECT * FROM financial_categories WHERE (:all OR is_active IS NOT FALSE) ORDER BY type, name"
    ), {"all": include_inactive})
    return [dict(row._mapping) for row in r.fetchall()]


@router.post("/financial-categories")
async def create_category(data: FinancialCategoryCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    r = await db.execute(text("""
        INSERT INTO financial_categories (name, type, color) VALUES (:name, :type, :color) RETURNING *
    """), data.model_dump())
    await db.commit()
    return dict(r.mappings().one())


@router.put("/financial-categories/{cat_id}")
async def update_category(cat_id: uuid.UUID, data: FinancialCategoryUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    """Change only the fields sent."""
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    row = (await db.execute(text("SELECT * FROM financial_categories WHERE id = :id FOR UPDATE"), {"id": cat_id})).mappings().first()
    if row is None:
        raise NotFoundError(CATEGORY_NOT_FOUND)
    if not updates:
        return dict(row)
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    row = (await db.execute(text(f"UPDATE financial_categories SET {sets}, updated_at = now() WHERE id = :id RETURNING *"),
                            {**updates, "id": cat_id})).mappings().one()
    await db.commit()
    return dict(row)


@router.delete("/financial-categories/{cat_id}", status_code=204)
async def delete_category(cat_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    """An unused category is deleted; one that expenses or drawer movements carry is stopped instead,
    so their history keeps its category. The use is checked first: drawer movements' foreign key is
    ON DELETE SET NULL, so a delete went through and cleared their category."""
    from sqlalchemy.exc import IntegrityError

    if not await db.scalar(text("SELECT 1 FROM financial_categories WHERE id = :id FOR UPDATE"), {"id": cat_id}):
        raise NotFoundError(CATEGORY_NOT_FOUND)
    used = await db.scalar(text("""
        SELECT EXISTS (SELECT 1 FROM expenses WHERE category_id = :id)
            OR EXISTS (SELECT 1 FROM drawer_transactions WHERE category_id = :id)
    """), {"id": cat_id})
    stop = text("UPDATE financial_categories SET is_active = false, updated_at = now() WHERE id = :id")
    if used:
        await db.execute(stop, {"id": cat_id})
    else:
        try:
            async with db.begin_nested():
                await db.execute(text("DELETE FROM financial_categories WHERE id=:id"), {'id': cat_id})
        except IntegrityError:  # another table refers to it
            await db.execute(stop, {"id": cat_id})
    await db.commit()


# ── User Permissions ───────────────────────────────────────────────────────
@router.get("/permissions/{user_id}")
async def get_permissions(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("users"))):
    """The permissions of the role the user acts as (ADR-006 phase 3), and the manager flag."""
    from app.platform.permissions.access import roles_of

    row = (await db.execute(text("SELECT active_role_id, is_manager FROM users WHERE id=:id"), {"id": user_id})).fetchone()
    if not row:
        raise HTTPException(404)
    roles = await roles_of(db, user_id)
    acting = next((r for r in roles if r["id"] == row[0]), roles[0] if roles else None)
    return {"permissions": sorted(acting["grants"] or []) if acting else [], "is_manager": bool(row[1])}


@router.put("/permissions/{user_id}")
async def update_permissions(user_id: uuid.UUID, data: PermissionsUpdate, db: AsyncSession = Depends(get_db),
                             current_user: User = Depends(require_perm("users"))):
    """Set a user's access: their standard role if the list matches it, else a role of their own.

    No privilege escalation: you can only grant permissions your own role holds, you can't change
    the access of someone whose role holds more than yours, and only a manager or an admin sets the
    manager flag. Every permission the platform or this workspace declares can be granted."""
    from app.platform.auth.models.user import User as _User
    from app.platform.community.service import workspace_permissions
    from app.platform.permissions.access import all_permissions, ensure_within, roles_of, set_access

    user = await db.get(_User, user_id)
    if not user:
        raise HTTPException(404, "المستخدم غير موجود")
    grants = sorted(set(data.permissions))
    known = set(all_permissions()) | {p["id"] for p in await workspace_permissions(db)}
    unknown = set(grants) - known
    if unknown:
        raise HTTPException(400, f"صلاحيات غير معروفة: {', '.join(sorted(unknown))}")
    ensure_within(current_user, grants)
    roles = await roles_of(db, user_id)
    acting = next((r for r in roles if r["id"] == user.active_role_id), roles[0] if roles else None)
    ensure_within(current_user, (acting or {}).get("grants") or [])  # can't take over someone above you
    holds_admin = "admin" in getattr(current_user, "effective_permissions", frozenset())
    if data.is_manager != bool(user.is_manager) and not (current_user.is_manager or holds_admin):
        raise HTTPException(403, "تعيين المدير يحتاج إلى مدير أو مسؤول النظام")
    await set_access(db, user, user.role, grants)
    user.is_manager = data.is_manager
    await db.commit()
    return {"detail": "updated"}



# ── Financial Ledger by Category ──────────────────────────────────────────
@router.get("/financial-ledger")
async def financial_ledger(
    from_date: date, to_date: date,
    warehouse_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("finance")),
):
    """
    Returns all drawer transactions grouped by financial category.
    Shows total per category + individual entries — like customer accounts but for expenses/income.
    """
    from app.activities.general.modules.finance.services.access import branch_scope
    from app.activities.general.modules.finance.services.ledger import day_bounds

    branches = await branch_scope(db, current_user, warehouse_id)
    start, end = day_bounds(from_date, to_date)

    q = """
        SELECT dt.id, dt.type, dt.amount, dt.note, dt.created_at,
               fc.name as category_name, fc.type as category_type, fc.color,
               s.warehouse_id, w.name as warehouse_name,
               u.full_name as cashier_name
        FROM drawer_transactions dt
        JOIN shifts s ON dt.shift_id = s.id
        LEFT JOIN financial_categories fc ON dt.category_id = fc.id
        LEFT JOIN warehouses w ON s.warehouse_id = w.id
        LEFT JOIN users u ON dt.created_by = u.id
        WHERE dt.created_at >= :start AND dt.created_at < :end
        AND dt.type IN ('expense', 'deposit', 'withdrawal')
        AND dt.cancelled_at IS NULL
    """
    params = {'start': start, 'end': end}
    if branches is not None:
        q += " AND s.warehouse_id = ANY(:whs)"
        params['whs'] = branches
    q += " ORDER BY dt.created_at DESC"

    rows = (await db.execute(text(q), params)).fetchall()
    cols = ['id','type','amount','note','created_at','category_name','category_type','color','warehouse_id','warehouse_name','cashier_name']
    entries = [dict(zip(cols, r, strict=False)) for r in rows]

    # Group by category
    from collections import defaultdict
    by_category: dict = defaultdict(lambda: {'total': 0.0, 'count': 0, 'entries': []})
    uncategorized = {'total': 0.0, 'count': 0, 'entries': []}

    for e in entries:
        e['amount'] = float(e['amount'])
        e['created_at'] = e['created_at'].isoformat() if e['created_at'] else None
        e['warehouse_id'] = str(e['warehouse_id']) if e['warehouse_id'] else None
        cat = e['category_name'] or 'غير مصنف'
        if e['category_name']:
            by_category[cat]['total'] += e['amount']
            by_category[cat]['count'] += 1
            by_category[cat]['color'] = e['color']
            by_category[cat]['type'] = e['category_type']
            by_category[cat]['entries'].append(e)
        else:
            uncategorized['total'] += e['amount']
            uncategorized['count'] += 1
            uncategorized['entries'].append(e)

    categories_out = [
        {'name': k, 'total': v['total'], 'count': v['count'],
         'color': v.get('color','#64748b'), 'type': v.get('type','expense'), 'entries': v['entries']}
        for k, v in sorted(by_category.items(), key=lambda x: -x[1]['total'])
    ]
    if uncategorized['count']:
        categories_out.append({'name': 'غير مصنف', 'total': uncategorized['total'],
                                'count': uncategorized['count'], 'color': '#94a3b8',
                                'type': 'expense', 'entries': uncategorized['entries']})

    total_expense = sum(e['amount'] for e in entries if e['type'] in ('expense','withdrawal'))
    total_income  = sum(e['amount'] for e in entries if e['type'] == 'deposit')

    return {
        'from_date': from_date.isoformat(), 'to_date': to_date.isoformat(),
        'total_expense': total_expense, 'total_income': total_income,
        'net': total_income - total_expense,
        'categories': categories_out,
    }


# ── Audit Log ─────────────────────────────────────────────────────────────────
@router.get("/audit-log")
async def get_audit_log(
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("admin"))
):
    conditions = ["1=1"]
    params: dict = {"limit": limit}
    if entity_type:
        conditions.append("entity_type = :etype")
        params["etype"] = entity_type
    if entity_id:
        conditions.append("entity_id = :eid")
        params["eid"] = entity_id
    rows = await db.execute(text(f"""
        SELECT al.*, u.full_name as user_display
        FROM audit_log al
        LEFT JOIN users u ON u.id = al.user_id
        WHERE {' AND '.join(conditions)}
        ORDER BY al.created_at DESC LIMIT :limit
    """), params)
    return [dict(r._mapping) for r in rows.fetchall()]
