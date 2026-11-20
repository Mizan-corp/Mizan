import uuid
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_open_period, require_perm, verify_warehouse_access
from app.platform.auth.models.user import User
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.schemas.stock import StockMovementCreate, StockMovementOut, TransferRequest
from app.activities.general.modules.inventory.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.activities.general.modules.inventory.services import stock as stock_service
from app.activities.general.modules.inventory.services import warehouses as warehouses_service
from app.activities.general.modules.inventory.services.products import READ_PERMISSIONS
from app.platform.audit.service import log as audit_log

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/warehouses", response_model=list[dict])
async def list_warehouses(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Warehouse).where(Warehouse.is_active))
    return [{"id": str(w.id), "code": w.code, "name": w.name, "warehouse_type": w.warehouse_type} for w in result.scalars().all()]


@router.post("/warehouses")
async def create_warehouse(data: WarehouseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("settings"))):
    if current_user.tenant_id:
        from app.platform.billing.services.plan_gating import check_branch_creation_limit
        await check_branch_creation_limit(db, current_user.tenant_id)
    await warehouses_service.ensure_code_free(db, data.code)
    w = Warehouse(code=data.code, name=data.name, warehouse_type=data.warehouse_type)
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return {"id": str(w.id), "code": w.code, "name": w.name, "warehouse_type": w.warehouse_type}


@router.put("/warehouses/{wh_id}")
async def update_warehouse(wh_id: uuid.UUID, data: WarehouseUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("settings"))):
    """Edit a warehouse. One that still holds stock (or an open shift) can't be deactivated."""
    w = await warehouses_service.update(db, wh_id, data, current_user)
    await db.commit()
    await db.refresh(w)
    return {"id": str(w.id), "code": w.code, "name": w.name, "warehouse_type": w.warehouse_type, "is_active": w.is_active}


@router.delete("/warehouses/{wh_id}", status_code=204)
async def delete_warehouse(wh_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("settings"))):
    await warehouses_service.deactivate(db, wh_id, current_user)
    await db.commit()


@router.post("/balance/bulk")
async def get_balance_bulk(warehouse_id: uuid.UUID, product_ids: list[uuid.UUID] = Body(..., max_length=1000), db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(require_perm(*READ_PERMISSIONS))):
    """POST body: list of product UUIDs. Returns {product_id: qty} plus a __tracked__ map."""
    from sqlalchemy import text as sqlt

    from app.activities.general.modules.inventory.models.stock_balance import StockBalance
    await verify_warehouse_access(db, current_user, warehouse_id)
    if not product_ids:
        return {}
    result = await db.execute(
        select(StockBalance.product_id, StockBalance.qty)
        .where(StockBalance.warehouse_id == warehouse_id, StockBalance.product_id.in_(product_ids))
    )
    out = {str(row.product_id): float(row.qty) for row in result.all()}
    st_rows = (await db.execute(sqlt(
        "SELECT product_id FROM warehouse_product_status WHERE warehouse_id=:wid AND status='tracked' AND product_id = ANY(:ids)"
    ), {"wid": warehouse_id, "ids": list(product_ids)})).fetchall()
    raised = {str(r[0]) for r in st_rows}
    out["__tracked__"] = {str(pid): str(pid) in raised for pid in product_ids}
    return out


@router.post("/balance/total")
async def get_total_balance_bulk(product_ids: list[uuid.UUID] = Body(..., max_length=1000), db: AsyncSession = Depends(get_db),
                                 _=Depends(require_perm(*READ_PERMISSIONS))):
    """Total stock across ALL warehouses. POST body: list of product UUIDs."""
    from sqlalchemy import func

    from app.activities.general.modules.inventory.models.stock_balance import StockBalance
    if not product_ids:
        return {}
    result = await db.execute(
        select(
            StockBalance.product_id,
            func.coalesce(func.sum(StockBalance.qty), 0).label("qty")
        )
        .where(StockBalance.product_id.in_(product_ids))
        .group_by(StockBalance.product_id)
    )
    return {str(row.product_id): float(row.qty) for row in result.all()}


@router.get("/balance/breakdown/{product_id}")
async def get_balance_breakdown(product_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm(*READ_PERMISSIONS))):
    """Stock per warehouse for a single product — uses maintained balances."""
    from sqlalchemy import func

    from app.activities.general.modules.inventory.models.stock_balance import StockBalance
    rows = await db.execute(
        select(
            Warehouse.name.label("warehouse_name"),
            Warehouse.warehouse_type,
            func.coalesce(StockBalance.qty, 0).label("qty")
        )
        .outerjoin(StockBalance, (StockBalance.product_id == product_id) & (StockBalance.warehouse_id == Warehouse.id))
        .order_by(Warehouse.name)
    )
    return [dict(r._mapping) for r in rows.fetchall()]


_DOCUMENT_TYPES = {
    "purchase": "المشتريات تُسجَّل باستلام أمر شراء من شاشة المشتريات",
    "return_out": "مرتجع المشتريات يُسجَّل من شاشة المشتريات (أمر الشراء)",
    "sale": "المبيعات تُسجَّل بفاتورة بيع",
    "return_in": "مرتجع المبيعات يُسجَّل من الفاتورة الأصلية",
    "transfer_in": "التحويل بين المخازن يُسجَّل من شاشة التحويل أو إذن الصرف",
    "transfer_out": "التحويل بين المخازن يُسجَّل من شاشة التحويل أو إذن الصرف",
}


async def _check_hand_movement(db: AsyncSession, user: User, item: StockMovementCreate) -> None:
    """A movement entered by hand: only adjustments and damage (they post to the ledger as
    stock.adjusted); opening stock with its own permission; everything else comes from its document.
    The warehouse must exist, be active and be one the user works in; the product must exist."""
    from fastapi import HTTPException

    from app.activities.general.modules.inventory.models.product import Product
    from app.core.exceptions import NotFoundError
    from app.platform.permissions.access import can

    kind = str(item.movement_type)
    if kind in _DOCUMENT_TYPES:
        raise HTTPException(400, f"لا تُسجَّل حركة من هذا النوع يدوياً — {_DOCUMENT_TYPES[kind]}")
    if kind == stock_service.OPENING_TYPE and not can(user, "inventory:opening"):
        raise HTTPException(403, "تسجيل الرصيد الافتتاحي يتطلب صلاحية «الرصيد الافتتاحي للمخزون»")
    if kind != stock_service.OPENING_TYPE and kind not in stock_service.HAND_TYPES:
        raise HTTPException(400, "نوع الحركة غير مسموح يدوياً")
    w = (await db.execute(select(Warehouse).where(Warehouse.id == item.warehouse_id))).scalar_one_or_none()
    if not w:
        raise NotFoundError("المخزن غير موجود")
    if not w.is_active:
        raise HTTPException(400, f"المخزن «{w.name}» موقوف")
    await verify_warehouse_access(db, user, item.warehouse_id)
    if not await db.scalar(select(Product.id).where(Product.id == item.product_id)):
        raise NotFoundError("الصنف غير موجود")


@router.post("/movements", response_model=StockMovementOut)
async def add_movement(data: StockMovementCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("inventory")), _=Depends(require_open_period)):
    """A stock adjustment, damage or (with `inventory:opening`) opening stock, entered by hand."""
    await _check_hand_movement(db, current_user, data)
    mv = await stock_service.record_movement(db, data, current_user.id)
    await audit_log(db, "stock", "adjustment", current_user.id, current_user.full_name, mv.id,
                    {"product_id": str(data.product_id), "warehouse_id": str(data.warehouse_id),
                     "qty": str(data.qty), "type": str(data.movement_type)}, "حركة مخزون يدوية")
    await db.commit()
    await db.refresh(mv)
    return mv


@router.delete("/movements", status_code=204)
async def reset_warehouse_stock(
    warehouse_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("settings")),
):
    """Delete a warehouse's hand-entered stock movements while it is being set up (see
    warehouses_service.reset_stock: refused once documents, transfers or the ledger involve them)."""
    await warehouses_service.reset_stock(db, warehouse_id, current_user)
    await db.commit()


@router.get("/movements")
async def list_movements(
    product_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("inventory")),
):
    await verify_warehouse_access(db, current_user, warehouse_id)
    from math import ceil

    from sqlalchemy import text as sqlt
    conditions = ["1=1"]
    params: dict = {}
    if product_id:
        conditions.append("sm.product_id = :product_id")
        params["product_id"] = product_id
    if warehouse_id:
        conditions.append("sm.warehouse_id = :warehouse_id")
        params["warehouse_id"] = warehouse_id
    where_sql = " AND ".join(conditions)

    count_result = await db.execute(sqlt(f"SELECT COUNT(*) FROM stock_movements sm WHERE {where_sql}"), params)
    total = count_result.scalar_one() or 0
    pages = max(1, ceil(total / page_size))
    offset = (page - 1) * page_size

    params["limit"] = page_size
    params["offset"] = offset
    rows = await db.execute(sqlt(f"""
        SELECT sm.*, p.name as product_name, w.name as warehouse_name
        FROM stock_movements sm
        LEFT JOIN products p ON p.id = sm.product_id
        LEFT JOIN warehouses w ON w.id = sm.warehouse_id
        WHERE {where_sql}
        ORDER BY sm.created_at DESC LIMIT :limit OFFSET :offset
    """), params)
    items = [dict(r._mapping) for r in rows.fetchall()]
    return {"items": items, "total": total, "page": page, "size": page_size, "pages": pages}


@router.post("/adjustment/bulk")
async def bulk_adjustment(data: list[StockMovementCreate], db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("inventory")), _=Depends(require_open_period)):
    """Several hand-entered movements at once (adjustments, damage, opening stock with its permission),
    all or none. Body: [{"product_id", "warehouse_id", "movement_type": "adjustment_in", "qty": 10, "note"}]"""
    from fastapi import HTTPException
    if len(data) > 500:
        raise HTTPException(400, "عدد البنود كبير جداً (الحد الأقصى 500)")
    for item in data:
        await _check_hand_movement(db, current_user, item)
    for item in data:
        mv = await stock_service.record_movement(db, item, current_user.id)
        await audit_log(db, "stock", "adjustment", current_user.id, current_user.full_name, mv.id,
                        {"product_id": str(item.product_id), "warehouse_id": str(item.warehouse_id),
                         "qty": str(item.qty), "type": str(item.movement_type)}, "تسوية مخزون")
    await db.commit()
    return {"detail": f"تم تسجيل {len(data)} حركة"}


@router.post("/transfer")
async def transfer(data: TransferRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("inventory"))):
    """Move stock between two different warehouses, both of which the user works in."""
    from fastapi import HTTPException
    if data.from_warehouse_id == data.to_warehouse_id:
        raise HTTPException(400, "لا يمكن التحويل من المخزن إلى نفسه — اختر مخزناً آخر للوجهة")
    await verify_warehouse_access(db, current_user, data.from_warehouse_id)
    await verify_warehouse_access(db, current_user, data.to_warehouse_id)
    result = await stock_service.transfer_stock(db, data, current_user)
    await db.commit()
    return {"detail": "تم التحويل", "ref_id": str(result["ref_id"])}


@router.get("/low-stock")
async def low_stock(warehouse_id: uuid.UUID, threshold: Decimal = Query(Decimal("5"), ge=0, le=Decimal("1000000")), db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("inventory", "purchases"))):
    await verify_warehouse_access(db, current_user, warehouse_id)
    rows = await stock_service.get_low_stock(db, warehouse_id, threshold)
    return [{"product_id": str(p.id), "product_name": p.name, "current_qty": qty, "unit": p.unit} for p, qty in rows]


@router.get("/valuation")
async def valuation(warehouse_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("inventory", "reports"))):
    """The warehouse's stock at average cost (as the ledger values it) and at retail price."""
    await verify_warehouse_access(db, current_user, warehouse_id)
    row = await stock_service.get_valuation(db, warehouse_id)
    return {"total_cost_value": row.cost_value or 0, "total_retail_value": row.retail_value or 0, "product_count": row.product_count or 0}
