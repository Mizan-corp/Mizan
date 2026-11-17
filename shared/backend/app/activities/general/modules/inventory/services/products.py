"""Product service — business logic for products, categories, subcategories, barcodes."""
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.core.pagination import Page
from app.activities.general.modules.inventory.models.product import Category, Product, ProductBarcode, Subcategory
from app.platform.auth.models.user import User
from app.activities.general.modules.inventory.schemas.product import (
    CategoryCreate,
    CategoryOut,
    MoveProduct,
    ProductBarcodeCreate,
    ProductBarcodeOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    SubcategoryCreate,
    SubcategoryOut,
)
from app.platform.audit.service import log as audit_log
from app.platform.permissions.access import can

# Who reads the catalogue (INV-8): whoever sells, buys, moves stock or reports on it, so a cashier
# still finds what to sell. Costs (the last purchase price and the average cost) only to those who
# value stock; the others get them as null.
READ_PERMISSIONS = ("inventory", "purchases", "operations", "pos", "sales", "quotations", "reports")
COST_PERMISSIONS = ("inventory", "purchases", "reports")

PRODUCT_NOT_FOUND = "الصنف غير موجود"
CATEGORY_NOT_FOUND = "التصنيف غير موجود"
SUBCATEGORY_NOT_FOUND = "التصنيف الفرعي غير موجود"
BARCODE_NOT_FOUND = "الباركود غير موجود"
NO_ACTIVE_PRODUCT_FOR_BARCODE = "لا يوجد صنف نشط بهذا الباركود"


def sees_costs(user: User | None) -> bool:
    return user is not None and can(user, *COST_PERMISSIONS)


def for_viewer(out, user: User | None):
    """A product schema as `user` may see it: without costs unless they hold a cost permission."""
    if not sees_costs(user):
        out.cost_price = None
        out.avg_cost = None
    return out


async def _commit_or_conflict(db: AsyncSession, message: str) -> None:
    """Commit; a unique index refusing the row (two requests at once) is a 409, not a 500."""
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(message) from None


# ── Categories ──────────────────────────────────────────────────────────────

def _category_taken(name: str) -> str:
    return f"يوجد تصنيف باسم «{name}» بالفعل"


def _subcategory_taken(name: str) -> str:
    return f"يوجد تصنيف فرعي باسم «{name}» في هذا التصنيف بالفعل"


async def _ensure_category_name_free(db: AsyncSession, name: str, own_id: uuid.UUID | None = None) -> None:
    q = select(Category.id).where(Category.name == name)
    if own_id:
        q = q.where(Category.id != own_id)
    if await db.scalar(q.limit(1)):
        raise ConflictError(_category_taken(name))


async def list_categories(db: AsyncSession) -> list[CategoryOut]:
    return (await db.execute(
        select(Category).order_by(func.nullif(Category.code, '').asc().nullslast(), Category.name)
    )).scalars().all()


async def create_category(db: AsyncSession, data: CategoryCreate, current_user_id: uuid.UUID) -> CategoryOut:
    await _ensure_category_name_free(db, data.name)
    cat = Category(name=data.name, code=data.code or None, image_url=data.image_url or None)
    db.add(cat)
    await _commit_or_conflict(db, _category_taken(data.name))
    await db.refresh(cat)
    return cat


async def update_category(db: AsyncSession, cat_id: uuid.UUID, data: CategoryCreate, current_user_id: uuid.UUID) -> CategoryOut:
    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise NotFoundError(CATEGORY_NOT_FOUND)
    await _ensure_category_name_free(db, data.name, cat_id)
    cat.name = data.name
    cat.code = data.code or None
    await _commit_or_conflict(db, _category_taken(data.name))
    await db.refresh(cat)
    return cat


async def delete_category(db: AsyncSession, cat_id: uuid.UUID) -> None:
    from sqlalchemy import text as sqlt

    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise NotFoundError(CATEGORY_NOT_FOUND)
    count = await db.scalar(sqlt(
        "SELECT COUNT(*) FROM products p JOIN subcategories s ON s.id = p.subcategory_id WHERE s.category_id = :id AND p.is_active = true"
    ), {"id": cat_id})
    if count and count > 0:
        raise BusinessError(f"لا يمكن حذف التصنيف — يوجد {count} منتج نشط مرتبط به")
    # Detach soft-deleted (inactive) products so FK RESTRICT doesn't block deletion
    await db.execute(sqlt(
        "UPDATE products SET subcategory_id = NULL FROM subcategories s WHERE s.category_id = :id AND products.subcategory_id = s.id AND products.is_active = false"
    ), {"id": cat_id})
    await db.delete(cat)
    await db.commit()


# ── Subcategories ────────────────────────────────────────────────────────────

async def list_subcategories(db: AsyncSession, category_id: uuid.UUID | None = None) -> list[SubcategoryOut]:
    q = select(Subcategory)
    if category_id:
        q = q.where(Subcategory.category_id == category_id)
    q = q.order_by(func.nullif(Subcategory.code, '').asc().nullslast(), Subcategory.name)
    return (await db.execute(q)).scalars().all()


async def _check_subcategory(db: AsyncSession, data: SubcategoryCreate, own_id: uuid.UUID | None = None) -> None:
    """The category is the workspace's (an id from elsewhere is a 404, not a foreign-key error), and
    no other subcategory of it has the name (the same name may sit under two categories)."""
    if not await db.scalar(select(Category.id).where(Category.id == data.category_id)):
        raise NotFoundError(CATEGORY_NOT_FOUND)
    q = select(Subcategory.id).where(Subcategory.category_id == data.category_id, Subcategory.name == data.name)
    if own_id:
        q = q.where(Subcategory.id != own_id)
    if await db.scalar(q.limit(1)):
        raise ConflictError(_subcategory_taken(data.name))


async def create_subcategory(db: AsyncSession, data: SubcategoryCreate) -> SubcategoryOut:
    await _check_subcategory(db, data)
    sub = Subcategory(category_id=data.category_id, name=data.name, code=data.code or None)
    db.add(sub)
    await _commit_or_conflict(db, _subcategory_taken(data.name))
    await db.refresh(sub)
    return sub


async def update_subcategory(db: AsyncSession, sub_id: uuid.UUID, data: SubcategoryCreate) -> SubcategoryOut:
    result = await db.execute(select(Subcategory).where(Subcategory.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise NotFoundError(SUBCATEGORY_NOT_FOUND)
    await _check_subcategory(db, data, sub_id)
    sub.name = data.name
    sub.category_id = data.category_id
    sub.code = data.code or None
    await _commit_or_conflict(db, _subcategory_taken(data.name))
    await db.refresh(sub)
    return sub


async def delete_subcategory(db: AsyncSession, sub_id: uuid.UUID) -> None:
    from sqlalchemy import text as sqlt

    result = await db.execute(select(Subcategory).where(Subcategory.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise NotFoundError(SUBCATEGORY_NOT_FOUND)
    count = await db.scalar(sqlt("SELECT COUNT(*) FROM products WHERE subcategory_id = :id AND is_active = true"), {"id": sub_id})
    if count and count > 0:
        raise BusinessError(f"لا يمكن حذف التصنيف الفرعي — يوجد {count} منتج نشط مرتبط به")
    # Detach soft-deleted (inactive) products so FK RESTRICT doesn't block deletion
    await db.execute(sqlt("UPDATE products SET subcategory_id = NULL WHERE subcategory_id = :id AND is_active = false"), {"id": sub_id})
    await db.delete(sub)
    await db.commit()


# ── Products ─────────────────────────────────────────────────────────────────

async def list_products(
    db: AsyncSession,
    search: str | None = None,
    subcategory_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User | None = None,
) -> Page:
    """One page of the active products with their stock (the branch's, or the company's) and the
    total. Costs are null unless the user may see them."""
    from app.activities.general.modules.inventory.models.stock_balance import StockBalance
    from app.dependencies import verify_warehouse_access
    if current_user:
        await verify_warehouse_access(db, current_user, warehouse_id)
    base_q = select(Product).where(Product.is_active)
    count_q = select(func.count(Product.id)).where(Product.is_active)

    if search:
        like = f"%{search}%"
        # Name, code, barcode, or any of the activity's fields (a drug's scientific name…).
        match = or_(Product.name.ilike(like), Product.code.ilike(like), Product.barcode.ilike(like),
                    cast(Product.extra, String).ilike(like))
        base_q = base_q.where(match)
        count_q = count_q.where(match)
    if subcategory_id:
        base_q = base_q.where(Product.subcategory_id == subcategory_id)
        count_q = count_q.where(Product.subcategory_id == subcategory_id)
    if category_id:
        base_q = base_q.join(Subcategory).where(Subcategory.category_id == category_id)
        count_q = count_q.join(Subcategory).where(Subcategory.category_id == category_id)

    base_q = base_q.order_by(func.nullif(Product.code, '').asc().nullslast(), Product.name)

    total = (await db.execute(count_q)).scalar_one() or 0
    pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    products = (await db.execute(base_q.offset(offset).limit(page_size))).scalars().all()

    from app.activities.general.modules.inventory.schemas.product import ProductOutWithBalance

    items_out: list[ProductOutWithBalance] = []
    for p in products:
        items_out.append(for_viewer(ProductOutWithBalance.model_validate(p), current_user))

    product_ids = [p.id for p in products]
    if product_ids:
        # The maintained balances (the sum of the movements, services/stock.apply_movement).
        bal_q = select(StockBalance.product_id, func.coalesce(func.sum(StockBalance.qty), 0)) \
            .where(StockBalance.product_id.in_(product_ids))
        if warehouse_id:
            bal_q = bal_q.where(StockBalance.warehouse_id == warehouse_id)
        bal_rows = (await db.execute(bal_q.group_by(StockBalance.product_id))).all()
        bal_map = {str(r[0]): Decimal(str(r[1])) for r in bal_rows}

        # Per-warehouse tracking status (only applies in warehouse scope)
        wh_status: dict[str, str] = {}
        if warehouse_id:
            wh_rows = (await db.execute(text(
                "SELECT product_id, status FROM warehouse_product_status WHERE warehouse_id = :wid"
            ), {"wid": warehouse_id})).fetchall()
            wh_status = {str(r[0]): str(r[1]) for r in wh_rows}

        for po in items_out:
            po.current_qty = bal_map.get(str(po.id), Decimal("0"))
            if warehouse_id:
                po.stock_status = wh_status.get(str(po.id), 'untracked')

    return Page(items=items_out, total=total, page=page, size=page_size, pages=pages)


async def _clean_extra(db: AsyncSession, extra: dict | None, current: dict | None = None) -> dict:
    """A product's extra values, checked against the workspace's product fields (ADR-006 phase 4)."""
    from app.framework.fields import clean_extra
    from app.framework.hooks import workspace_activity

    return await clean_extra(db, "product", extra, await workspace_activity(db), current=current)


def _barcode_taken(barcode: str, name: str) -> str:
    return f"الباركود «{barcode}» مستخدم للصنف «{name}»"


def _barcode_in_use(barcode: str | None) -> str:
    """What a unique index refusing a product's barcode (two saves at once) says."""
    return f"الباركود «{barcode}» مستخدم لصنف آخر" if barcode else "تعذّر حفظ الصنف: يتعارض مع صنف آخر"


async def ensure_barcode_free(db: AsyncSession, barcode: str | None, product_id: uuid.UUID | None = None) -> None:
    """A barcode identifies one active product of the workspace, as its main barcode or one of its
    extra ones (a scan must find one product). `product_id`: the product it is for (its own
    barcodes don't count). Inactive products' main barcodes may be reused."""
    if not barcode:
        return
    others = [Product.is_active]
    if product_id:
        others.append(Product.id != product_id)
    name = await db.scalar(select(Product.name).where(Product.barcode == barcode, *others).limit(1))
    if name is None:
        name = await db.scalar(select(Product.name).join(ProductBarcode, ProductBarcode.product_id == Product.id)
                               .where(ProductBarcode.barcode == barcode, *others).limit(1))
    if name is not None:
        raise ConflictError(_barcode_taken(barcode, name))


async def _check_subcategory_exists(db: AsyncSession, subcategory_id: uuid.UUID | None) -> None:
    if subcategory_id and not await db.scalar(select(Subcategory.id).where(Subcategory.id == subcategory_id)):
        raise NotFoundError(SUBCATEGORY_NOT_FOUND)


async def create_product(db: AsyncSession, data: ProductCreate, current_user_id: uuid.UUID) -> ProductOut:
    payload = data.model_dump()
    for key in ("code", "barcode"):
        if not payload.get(key):
            payload[key] = None
    await _check_subcategory_exists(db, data.subcategory_id)
    await ensure_barcode_free(db, payload["barcode"])
    payload["extra"] = await _clean_extra(db, payload.get("extra"))
    p = Product(**payload)
    db.add(p)
    await _commit_or_conflict(db, _barcode_in_use(payload["barcode"]))
    await db.refresh(p)
    return p


async def get_product_by_barcode(db: AsyncSession, barcode: str) -> Product:
    """The active product a scanned code belongs to: its main barcode first, then its extra ones.
    Inactive products are never found; should old data hold one code twice, the first is taken."""
    p = (await db.execute(select(Product).where(Product.barcode == barcode, Product.is_active)
                          .order_by(Product.created_at, Product.id).limit(1))).scalars().first()
    if p:
        return p
    p = (await db.execute(
        select(Product)
        .join(ProductBarcode, ProductBarcode.product_id == Product.id)
        .where(ProductBarcode.barcode == barcode, Product.is_active)
        .order_by(Product.created_at, Product.id).limit(1)
    )).scalars().first()
    if not p:
        raise NotFoundError(NO_ACTIVE_PRODUCT_FOR_BARCODE)
    return p


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.barcodes))
        .where(Product.id == product_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundError(PRODUCT_NOT_FOUND)
    return p


async def update_product(
    db: AsyncSession,
    product_id: uuid.UUID,
    data: ProductUpdate,
    current_user: User,
) -> ProductOut:
    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundError(PRODUCT_NOT_FOUND)
    payload = data.model_dump(exclude_none=True)
    for key in ("code", "barcode"):
        if key in payload and not payload[key]:
            payload[key] = None  # "" clears it
    if "subcategory_id" in payload:
        await _check_subcategory_exists(db, payload["subcategory_id"])
    barcode = payload.get("barcode", p.barcode)
    if payload.get("is_active", p.is_active) and barcode and (barcode != p.barcode or not p.is_active):
        await ensure_barcode_free(db, barcode, p.id)
    if "extra" in payload:
        payload["extra"] = await _clean_extra(db, payload["extra"], current=p.extra)
    for k, v in payload.items():
        setattr(p, k, v)
    await audit_log(db, "product", "update", current_user.id, current_user.full_name, product_id, data.model_dump(mode="json", exclude_none=True), "تعديل المنتج")
    from app.platform.community.events import deliver_soon, publish

    hooks = await publish(db, "product.updated", {"id": str(p.id), "code": p.code, "name": p.name,
                                                  "retail_price": str(p.retail_price), "is_active": p.is_active})
    await _commit_or_conflict(db, _barcode_in_use(barcode))
    deliver_soon(hooks)
    await db.refresh(p)
    return p


async def delete_product(db: AsyncSession, product_id: uuid.UUID) -> None:
    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundError(PRODUCT_NOT_FOUND)
    p.is_active = False  # soft delete — preserves stock movement history
    await db.commit()


# ── Product Movements ────────────────────────────────────────────────────────

async def product_movements(
    db: AsyncSession,
    product_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Per-product movement log — used in product analytics. `to_date` is included whole."""
    from math import ceil

    if not await db.scalar(select(Product.id).where(Product.id == product_id)):
        raise NotFoundError(PRODUCT_NOT_FOUND)
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, "تاريخ البداية بعد تاريخ النهاية")
    conditions = ["sm.product_id = :product_id"]
    params: dict = {"product_id": product_id}
    if from_date:
        params["from_date"] = datetime.combine(from_date, time.min, tzinfo=UTC)
        conditions.append("sm.created_at >= :from_date")
    if to_date:
        params["to_date"] = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=UTC)
        conditions.append("sm.created_at < :to_date")
    where_sql = " AND ".join(conditions)
    total = (await db.execute(text(f"SELECT COUNT(*) FROM stock_movements sm WHERE {where_sql}"), params)).scalar() or 0
    pages = max(1, ceil(total / page_size))
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    rows = await db.execute(text(f"""
        SELECT sm.*, p.name as product_name, w.name as warehouse_name,
               u.full_name as created_by_name
        FROM stock_movements sm
        LEFT JOIN products p ON p.id = sm.product_id
        LEFT JOIN warehouses w ON w.id = sm.warehouse_id
        LEFT JOIN users u ON u.id = sm.created_by
        WHERE {where_sql}
        ORDER BY sm.created_at DESC LIMIT :limit OFFSET :offset
    """), params)
    items = [dict(r._mapping) for r in rows.fetchall()]
    return {"items": items, "total": total, "page": page, "size": page_size, "pages": pages}


# ── Product Barcodes ─────────────────────────────────────────────────────────

async def _ensure_extra_barcode_free(db: AsyncSession, barcode: str, product_id: uuid.UUID) -> None:
    """An extra barcode is unique in the workspace's barcode table (any product, inactive ones too)
    and no other active product uses it as its main barcode."""
    if await db.scalar(select(ProductBarcode.id).where(ProductBarcode.barcode == barcode).limit(1)):
        raise ConflictError(f"الباركود «{barcode}» مسجَّل بالفعل")
    await ensure_barcode_free(db, barcode, product_id)


async def add_barcode(
    db: AsyncSession,
    product_id: uuid.UUID,
    data: ProductBarcodeCreate,
    current_user: User,
) -> ProductBarcodeOut:
    """Add a barcode to a product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundError(PRODUCT_NOT_FOUND)
    await _ensure_extra_barcode_free(db, data.barcode, product_id)

    # If marking as primary, unmark all other barcodes for this product
    if data.is_primary:
        for other in (
            await db.execute(
                select(ProductBarcode)
                .where(ProductBarcode.product_id == product_id)
                .where(ProductBarcode.is_primary)
            )
        ).scalars().all():
            other.is_primary = False

    bc = ProductBarcode(product_id=product_id, barcode=data.barcode, is_primary=data.is_primary)
    db.add(bc)
    await audit_log(db, "product", "barcode_add", current_user.id, current_user.full_name, product_id, {"barcode": data.barcode}, "إضافة رمز شريطي")
    await _commit_or_conflict(db, f"الباركود «{data.barcode}» مسجَّل بالفعل")
    await db.refresh(bc)
    return bc


async def update_barcode(
    db: AsyncSession,
    barcode_id: uuid.UUID,
    data: ProductBarcodeCreate,
    current_user: User,
) -> ProductBarcodeOut:
    """Update a barcode (change barcode string or mark as primary)."""
    result = await db.execute(select(ProductBarcode).where(ProductBarcode.id == barcode_id))
    bc = result.scalar_one_or_none()
    if not bc:
        raise NotFoundError(BARCODE_NOT_FOUND)

    if data.barcode != bc.barcode:
        await _ensure_extra_barcode_free(db, data.barcode, bc.product_id)

    # If marking as primary, unmark all other barcodes for this product
    if data.is_primary and not bc.is_primary:
        for other_bc in (await db.execute(
            select(ProductBarcode)
            .where(ProductBarcode.product_id == bc.product_id)
            .where(ProductBarcode.is_primary)
        )).scalars().all():
            other_bc.is_primary = False

    old_barcode = bc.barcode
    bc.barcode = data.barcode
    bc.is_primary = data.is_primary
    await audit_log(db, "product", "barcode_update", current_user.id, current_user.full_name, bc.product_id, {"from": old_barcode, "to": data.barcode}, "تعديل رمز شريطي")
    await _commit_or_conflict(db, f"الباركود «{data.barcode}» مسجَّل بالفعل")
    await db.refresh(bc)
    return bc


async def delete_barcode(
    db: AsyncSession,
    barcode_id: uuid.UUID,
    current_user: User,
) -> None:
    """Delete a barcode."""
    result = await db.execute(select(ProductBarcode).where(ProductBarcode.id == barcode_id))
    bc = result.scalar_one_or_none()
    if not bc:
        raise NotFoundError(BARCODE_NOT_FOUND)

    product_id = bc.product_id
    barcode_str = bc.barcode
    await db.delete(bc)
    await audit_log(db, "product", "barcode_delete", current_user.id, current_user.full_name, product_id, {"barcode": barcode_str}, "حذف رمز شريطي")
    await db.commit()


# ── Move Product ─────────────────────────────────────────────────────────────

async def move_product(
    db: AsyncSession,
    product_id: uuid.UUID,
    data: MoveProduct,
    current_user: User,
) -> dict[str, str]:
    """Move product to a different subcategory."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundError(PRODUCT_NOT_FOUND)

    new_subcategory_id = data.subcategory_id

    # Validate new subcategory exists
    sub_result = await db.execute(select(Subcategory).where(Subcategory.id == new_subcategory_id))
    if not sub_result.scalar_one_or_none():
        raise NotFoundError("التصنيف الفرعي الجديد غير موجود")

    old_subcat = str(p.subcategory_id)
    p.subcategory_id = new_subcategory_id
    await audit_log(db, "product", "move", current_user.id, current_user.full_name, product_id, {"from_subcategory": old_subcat, "to_subcategory": str(p.subcategory_id)}, "نقل منتج بين الفئات")
    await db.commit()
    return {"detail": "Moved"}


# ── Product Image ────────────────────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024


async def upload_product_image(
    db: AsyncSession,
    product_id: uuid.UUID,
    file_content: bytes,
    filename: str,
    content_type: str,
) -> str:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, GIF, WebP")
    if len(file_content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "حجم الملف يتجاوز 5 ميجابايت")

    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundError(PRODUCT_NOT_FOUND)

    from app.framework import files

    p.image_url = await files.store(db, file_content, kind="product_image", owner_id=str(product_id),
                                    filename=filename or "img.png", content_type=content_type)
    await db.commit()
    return p.image_url


async def set_reorder_level(db, product_ids, level, tenant_id=None) -> int:
    """Set the reorder level (and point) of several products; returns how many changed."""
    from sqlalchemy import func, update

    from app.activities.general.modules.inventory.models.product import Product

    stmt = update(Product).where(Product.id.in_(product_ids))
    if tenant_id:  # besides row-level security
        stmt = stmt.where(Product.tenant_id == tenant_id)
    result = await db.execute(stmt.values(reorder_level=level, reorder_point=level, updated_at=func.now()))
    return result.rowcount
