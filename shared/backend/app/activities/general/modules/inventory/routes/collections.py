"""Product Collections — packages of multiple products sold as one unit."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import Page
from app.db.base import get_db
from app.dependencies import require_perm, verify_warehouse_access
from app.platform.auth.models.user import User
from app.activities.general.modules.inventory.schemas.collection import CollectionCreate, CollectionUpdate
from app.activities.general.modules.inventory.services.products import READ_PERMISSIONS, sees_costs

router = APIRouter(prefix="/collections", tags=["collections"])

COLLECTION_NOT_FOUND = "المجموعة غير موجودة"


@router.get("")
async def list_collections(
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm(*READ_PERMISSIONS)),
):
    """Active collections with their items; the items' costs only for those who may see costs."""
    total_row = await db.execute(text("SELECT COUNT(*) FROM product_collections WHERE is_active = true"))
    total = total_row.scalar()
    offset = (page - 1) * page_size
    rows = await db.execute(text("""
        SELECT pc.*,
               json_agg(json_build_object(
                 'id', ci.id, 'product_id', ci.product_id,
                 'qty', ci.qty, 'product_name', p.name, 'unit', p.unit,
                 'retail_price', p.retail_price, 'cost_price', p.cost_price
               ) ORDER BY p.name) FILTER (WHERE ci.id IS NOT NULL) as items
        FROM product_collections pc
        LEFT JOIN collection_items ci ON ci.collection_id = pc.id
        LEFT JOIN products p ON p.id = ci.product_id
        WHERE pc.is_active = true
        GROUP BY pc.id ORDER BY pc.name
        OFFSET :offset LIMIT :limit
    """), {"offset": offset, "limit": page_size})
    items = [dict(r._mapping) for r in rows.fetchall()]
    if not sees_costs(current_user):
        for coll in items:
            for item in coll.get("items") or []:
                item["cost_price"] = None
    pages = (total + page_size - 1) // page_size
    return Page(items=items, total=total, page=page, size=page_size, pages=pages)


async def _check_items(db: AsyncSession, data: CollectionCreate) -> None:
    """Each product once, and every one the workspace's (another workspace's id is a 404, not a
    foreign-key error)."""
    ids = [i.product_id for i in data.items]
    if len(set(ids)) != len(ids):
        raise HTTPException(400, "الصنف مكرر في المجموعة — اجمع كميته في سطر واحد")
    if ids:
        found = (await db.execute(text("SELECT id FROM products WHERE id = ANY(:ids)"), {"ids": ids})).scalars().all()
        if len(set(found)) != len(ids):
            raise NotFoundError("صنف غير موجود")


async def _insert_items(db: AsyncSession, cid, data: CollectionCreate) -> None:
    for item in data.items:
        await db.execute(text("""
            INSERT INTO collection_items (collection_id, product_id, qty)
            VALUES (:cid, :pid, :qty)
        """), {"cid": cid, "pid": item.product_id, "qty": item.qty})


@router.post("", status_code=201)
async def create_collection(data: CollectionCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory"))):
    await _check_items(db, data)
    r = await db.execute(text("""
        INSERT INTO product_collections (name, description, retail_price, wholesale_price, is_active)
        VALUES (:name, :desc, :retail, :wholesale, true) RETURNING *
    """), {"name": data.name, "desc": data.description, "retail": data.retail_price, "wholesale": data.wholesale_price})
    coll = dict(r.fetchone()._mapping)
    await _insert_items(db, coll["id"], data)
    await db.commit()
    return coll


@router.put("/{cid}")
async def update_collection(cid: uuid.UUID, data: CollectionUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory"))):
    await _check_items(db, data)
    r = await db.execute(text("""
        UPDATE product_collections SET name=:name, description=:desc,
        retail_price=:retail, wholesale_price=:wholesale WHERE id=:id AND is_active
    """), {"name": data.name, "desc": data.description, "retail": data.retail_price,
           "wholesale": data.wholesale_price, "id": cid})
    if r.rowcount == 0:
        raise NotFoundError(COLLECTION_NOT_FOUND)
    # Replace items
    await db.execute(text("DELETE FROM collection_items WHERE collection_id=:id"), {"id": cid})
    await _insert_items(db, cid, data)
    await db.commit()
    return {"ok": True}


@router.delete("/{cid}", status_code=204)
async def delete_collection(cid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory"))):
    r = await db.execute(text("UPDATE product_collections SET is_active=false WHERE id=:id AND is_active"), {"id": cid})
    if r.rowcount == 0:
        raise NotFoundError(COLLECTION_NOT_FOUND)
    await db.commit()


@router.get("/{cid}/availability")
async def collection_availability(cid: uuid.UUID, warehouse_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                                  current_user: User = Depends(require_perm(*READ_PERMISSIONS))):
    """How many of this collection can be assembled from current stock in warehouse."""
    await verify_warehouse_access(db, current_user, warehouse_id)
    if not await db.scalar(text("SELECT 1 FROM product_collections WHERE id = :id AND is_active"), {"id": cid}):
        raise NotFoundError(COLLECTION_NOT_FOUND)
    items = await db.execute(text("""
        SELECT ci.product_id, ci.qty as needed, p.name, p.stock_status,
               COALESCE(sb.qty, 0) as available
        FROM collection_items ci
        JOIN products p ON p.id = ci.product_id
        LEFT JOIN stock_balances sb ON sb.product_id = ci.product_id AND sb.warehouse_id = :wid
        WHERE ci.collection_id = :cid
    """), {"cid": cid, "wid": warehouse_id})
    rows = [dict(r._mapping) for r in items.fetchall()]
    if not rows:
        return {"can_make": 0, "items": []}
    # How many collections can we make? Untracked products (services) don't limit it.
    can_make = None
    for r in rows:
        if r["stock_status"] == "untracked":
            continue
        needed, available = Decimal(str(r["needed"])), Decimal(str(r["available"]))
        possible = int(available // needed) if needed > 0 and available > 0 else 0
        if can_make is None or possible < can_make:
            can_make = possible
    return {"can_make": can_make if can_make is not None else 999, "items": rows}
