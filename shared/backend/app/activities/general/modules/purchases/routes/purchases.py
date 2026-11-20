import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_open_period, require_perm, verify_warehouse_access
from app.platform.permissions.access import can
from app.platform.auth.models.user import User
from app.activities.general.modules.purchases.schemas.purchase import (
    PurchaseCancel,
    PurchaseCreate,
    PurchaseReceive,
    PurchaseReturnCreate,
    PurchaseUpdate,
    QuickProductCreate,
)
from app.activities.general.modules.purchases.schemas.supplier_price import (
    SupplierPriceComparison,
    SupplierPriceCreate,
    SupplierPriceOut,
    SupplierPriceUpdate,
)
from app.activities.general.modules.purchases import service as purchase_service

router = APIRouter(prefix="/purchases", tags=["purchases"])


# Orders, their costs, price history and supplier prices are read by purchasing and by finance (PUR-5).
can_read = require_perm("purchases", "finance")


@router.get("/suggestions")
async def purchase_suggestions(db: AsyncSession = Depends(get_db), _=Depends(can_read)):
    """Active tracked products whose stock across all warehouses is at or below their reorder point
    (at most 500, lowest stock first)."""
    return await purchase_service.get_purchase_suggestions(db)


@router.get("")
async def list_purchases(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                         status: Literal["draft", "partial", "received", "cancelled"] | None = None,
                         supplier_id: uuid.UUID | None = None, search: str | None = Query(None, max_length=64),
                         db: AsyncSession = Depends(get_db), _=Depends(can_read)):
    """Purchase orders, newest first, each with its total (what was received once received in whole or
    in part); filtered by status, supplier, or a search in the number and the supplier's name."""
    return await purchase_service.list_purchases(db, page, page_size, status, supplier_id, search)


@router.get("/{po_id}")
async def get_purchase(po_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(can_read)):
    """The order, its lines (ordered, received, left), its goods receipts, returns and the movements it
    made on the supplier's account."""
    return await purchase_service.get_purchase(db, po_id)


def _require_finance(user: User) -> None:
    """Money leaving or entering a safe or wallet (ADR-014 D4) needs `finance`, not only `purchases`."""
    if not can(user, "finance"):
        raise HTTPException(403, purchase_service.FINANCE_NEEDED)


@router.post("")
async def create_purchase(data: PurchaseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("purchases")), _=Depends(require_open_period)):
    """A draft order for a warehouse the user works in. A payment planned on it needs `finance`."""
    await verify_warehouse_access(db, current_user, data.warehouse_id)
    if data.amount_paid:
        _require_finance(current_user)
    return await purchase_service.create_purchase(db, data, current_user)


@router.put("/{po_id}")
async def update_purchase(po_id: uuid.UUID, data: PurchaseUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("purchases"))):
    """Change a draft (supplier, branch, notes, lines) in a branch the user works in."""
    return await purchase_service.update_purchase(db, po_id, data, current_user)


@router.post("/{po_id}/cancel")
async def cancel_purchase(po_id: uuid.UUID, data: PurchaseCancel | None = None, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(require_perm("purchases"))):
    """Cancel a draft: kept, marked cancelled, never received."""
    return await purchase_service.cancel_purchase(db, po_id, current_user, data.reason if data else None)


@router.post("/{po_id}/close")
async def close_purchase(po_id: uuid.UUID, data: PurchaseCancel | None = None, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_perm("purchases"))):
    """A partly received order whose rest won't come: received with what arrived."""
    return await purchase_service.close_purchase(db, po_id, current_user, data.reason if data else None)


@router.delete("/{po_id}", status_code=204)
async def delete_purchase(po_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(require_perm("purchases"))):
    """Delete a draft (nothing was received or paid with it)."""
    await purchase_service.delete_purchase(db, po_id, current_user)


@router.post("/{po_id}/receive")
async def receive_purchase(po_id: uuid.UUID, data: PurchaseReceive = None, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(require_perm("purchases")), _=Depends(require_open_period)):
    """Receive what arrived of a draft or partly received order (a goods receipt): its stock comes in
    and the supplier is owed its value. Paying part of it now (`amount_paid` > 0, from a safe or
    wallet) also needs `finance`. Refused in a closed month."""
    data = data or PurchaseReceive()
    warehouse_id, planned = await purchase_service.order_warehouse(db, po_id)
    await verify_warehouse_access(db, current_user, warehouse_id)
    if (data.amount_paid if data.amount_paid is not None else planned) > 0:
        _require_finance(current_user)
    return await purchase_service.receive_purchase(db, po_id, data, current_user)


@router.get("/{po_id}/returns")
async def list_purchase_returns(po_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(can_read)):
    """The order's returns to the supplier, and what can still be returned per product."""
    return await purchase_service.list_purchase_returns(db, po_id)


@router.post("/{po_id}/returns", status_code=201)
async def create_purchase_return(po_id: uuid.UUID, data: PurchaseReturnCreate, db: AsyncSession = Depends(get_db),
                                 current_user: User = Depends(require_perm("purchases")), _=Depends(require_open_period)):
    """Return received goods to the supplier: stock out at the cost it came in at, and the supplier's
    balance goes down by the value (or a refund goes into a safe or wallet, which needs `finance`)."""
    warehouse_id, _ = await purchase_service.order_warehouse(db, po_id)
    await verify_warehouse_access(db, current_user, warehouse_id)
    if data.refund_amount:
        _require_finance(current_user)
    return await purchase_service.create_purchase_return(db, po_id, data, current_user)


@router.get("/price-history/{product_id}")
async def price_history(product_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(can_read)):
    return await purchase_service.get_price_history(db, product_id)


ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@router.post("/{po_id}/upload-invoice")
async def upload_invoice_image(po_id: uuid.UUID, file: UploadFile = File(...),
                                db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("purchases"))):
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(400, "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, GIF, WebP, PDF")
    contents = await file.read()
    from app.framework.storage import ensure_room

    await ensure_room(db, len(contents))  # storage quota (ADR-006 D3)
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "حجم الملف يتجاوز 10 ميجابايت")
    image_url = await purchase_service.upload_invoice_image(db, po_id, contents, file.filename or "invoice.jpg", file.content_type)
    return {"invoice_image_url": image_url}


@router.post("/quick-add-product")
async def quick_add_product(data: QuickProductCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("purchases"))):
    """Create a new product inline during purchase entry."""
    return await purchase_service.quick_add_product(db, data, current_user)


# ── Supplier Prices ────────────────────────────────────────────────────────
@router.get("/supplier-prices/product/{product_id}", response_model=SupplierPriceComparison)
async def get_product_supplier_prices(product_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(can_read)):
    """Get all supplier prices for a product with comparison."""
    return await purchase_service.get_product_supplier_prices(db, product_id)


@router.post("/supplier-prices", response_model=SupplierPriceOut)
async def create_supplier_price(
    data: SupplierPriceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_perm("purchases"))
):
    """Create or update supplier price."""
    return await purchase_service.create_supplier_price(db, data, current_user)


@router.put("/supplier-prices/{price_id}", response_model=SupplierPriceOut)
async def update_supplier_price(
    price_id: uuid.UUID,
    data: SupplierPriceUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("purchases"))
):
    """Update supplier price."""
    return await purchase_service.update_supplier_price(db, price_id, data)


@router.delete("/supplier-prices/{price_id}", status_code=204)
async def delete_supplier_price(
    price_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("purchases"))
):
    """Soft-delete supplier price."""
    await purchase_service.delete_supplier_price(db, price_id)
