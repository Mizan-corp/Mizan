"""What the server decides about a sale, whatever the client sent (production readiness, Phase A).

- SAL-1: prices are the product's (retail or wholesale) unless the POS setting
  `allow_price_override` is on and the user holds `sales:override_price`; discounts follow the
  sales setting `allow_manual_discount`; selling more than the stock follows the inventory
  setting `prevent_negative_stock` and `sales:negative_stock`. No flag from the client changes
  any of this.
- SAL-3: the shift a sale goes into is the user's own open shift in the sale's branch; cash
  needs one, and the POS setting `require_active_shift` asks for one for every sale.
- SAL-9: ids from the request are found in the workspace (404 in Arabic) before anything is
  written.
"""
import uuid
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


async def module_setting(db: AsyncSession, module_id: str, key: str, default):
    """A module's setting in this workspace (its manifest default when never saved)."""
    from app.framework.loader import registry

    try:
        values = (await registry.get_settings(db, module_id))["values"]
    except KeyError:
        return default
    return values.get(key, default)


async def setting_on(db: AsyncSession, module_id: str, key: str, default: bool) -> bool:
    return _truthy(await module_setting(db, module_id, key, default))


async def load_actor(db: AsyncSession, user_id: uuid.UUID, actor=None):
    """The user acting, with the permissions of the role they act as."""
    from app.platform.auth.models.user import User
    from app.platform.permissions.access import load_acting

    user = actor if actor is not None and actor.id == user_id else await db.get(User, user_id)
    if user is None:
        raise NotFoundError("المستخدم غير موجود")
    if getattr(user, "effective_permissions", None) is None:
        await load_acting(db, user)
    return user


def can(user, *perms: str) -> bool:
    from app.platform.permissions.access import can as _can

    return _can(user, *perms)


async def check_references(db: AsyncSession, *, warehouse_id=None, customer_id=None, wallet_ids=()) -> None:
    """The branch, customer and wallets named by a sale exist in this workspace."""
    if warehouse_id is not None:
        found = (await db.execute(text("SELECT is_active FROM warehouses WHERE id = :id"), {"id": warehouse_id})).first()
        if found is None:
            raise NotFoundError("الفرع غير موجود")
        if found.is_active is False:
            raise BusinessError("هذا الفرع موقوف")
    if customer_id is not None:
        if (await db.execute(text("SELECT 1 FROM customers WHERE id = :id"), {"id": customer_id})).first() is None:
            raise NotFoundError("العميل غير موجود")
    for wallet_id in {w for w in wallet_ids if w}:
        found = (await db.execute(text("SELECT is_active FROM payment_wallets WHERE id = :id"), {"id": wallet_id})).first()
        if found is None:
            raise NotFoundError("المحفظة غير موجودة")
        if found.is_active is False:
            raise BusinessError("هذه المحفظة موقوفة")


def _listed_price(product, sale_mode) -> Decimal:
    retail = Decimal(str(product.retail_price or 0))
    wholesale = Decimal(str(product.wholesale_price or 0))
    if str(getattr(sale_mode, "value", sale_mode)) == "wholesale" and wholesale > 0:
        return wholesale
    return retail


async def fill_listed_prices(db: AsyncSession, items, sale_mode) -> None:
    """Lines sent without a price (an edited draft or quotation) take the product's price now."""
    missing = [i for i in items if i.unit_price is None]
    if not missing:
        return
    rows = {r.id: r for r in (await db.execute(text(
        "SELECT id, retail_price, wholesale_price FROM products WHERE id = ANY(:ids)"
    ), {"ids": list({i.product_id for i in missing})})).all()}
    for item in missing:
        product = rows.get(item.product_id)
        if product is None:
            raise NotFoundError("الصنف غير موجود")
        item.unit_price = _listed_price(product, sale_mode)


async def check_prices(db: AsyncSession, items, sale_mode, invoice_discount, actor) -> None:
    """Every line is a product of this workspace sold at its price, and discounts are allowed
    (SAL-1). `items` have product_id, unit_price and discount."""
    ids = list({i.product_id for i in items})
    rows = {r.id: r for r in (await db.execute(text(
        "SELECT id, name, retail_price, wholesale_price FROM products WHERE id = ANY(:ids)"
    ), {"ids": ids})).all()}
    override = None
    for item in items:
        product = rows.get(item.product_id)
        if product is None:
            raise NotFoundError("الصنف غير موجود")
        listed = _listed_price(product, sale_mode)
        price = Decimal(str(item.unit_price))
        if price != listed:
            if override is None:
                override = (await setting_on(db, "pos", "allow_price_override", False)
                            and can(actor, "sales:override_price"))
            if not override:
                raise BusinessError(
                    f"سعر «{product.name}» هو {listed:.2f} — البيع بسعر آخر ({price:.2f}) يحتاج تفعيل "
                    "«السماح بتعديل سعر البيع يدوياً» في إعدادات نقطة البيع وصلاحية «البيع بسعر غير سعر الصنف»")
    discounted = Decimal(str(invoice_discount or 0)) > 0 or any(Decimal(str(i.discount or 0)) > 0 for i in items)
    if discounted and not await setting_on(db, "sales", "allow_manual_discount", True) \
            and not can(actor, "sales:override_price"):
        raise BusinessError("الخصم اليدوي غير مسموح في إعدادات المبيعات")


def totals(items, invoice_discount) -> tuple[Decimal, Decimal, Decimal]:
    """(gross, net, line discounts) of a sale; the net can't be below zero."""
    gross = sum((Decimal(str(i.qty)) * Decimal(str(i.unit_price)) for i in items), Decimal("0"))
    line_discounts = sum((Decimal(str(i.discount or 0)) for i in items), Decimal("0"))
    net = gross - line_discounts - Decimal(str(invoice_discount or 0))
    if net < 0:
        raise BusinessError("الخصم أكبر من إجمالي الفاتورة")
    return gross, net, line_discounts


async def negative_stock_allowed(db: AsyncSession, actor) -> bool:
    """Selling more than the branch holds: only when the workspace doesn't prevent it, or for a
    user holding `sales:negative_stock`."""
    if not await setting_on(db, "inventory", "prevent_negative_stock", True):
        return True
    return can(actor, "sales:negative_stock")


def cash_involved(*, payments=None, is_credit=False, paid_amount=None, wallet_id=None, payment_method="cash") -> bool:
    """Whether part of a sale is paid in cash (the money then goes into a drawer)."""
    if payments:
        return any(p.method == "cash" for p in payments)
    if is_credit:
        return bool(paid_amount and Decimal(str(paid_amount)) > 0)
    if wallet_id:
        return False
    return (payment_method or "cash") == "cash"


async def sale_shift(db: AsyncSession, user_id: uuid.UUID, warehouse_id: uuid.UUID, shift_id: uuid.UUID | None,
                     *, cash: bool, require_setting: bool = True) -> uuid.UUID | None:
    """The shift a sale goes into: the one named, if it is the user's, open and in the sale's
    branch; otherwise the user's open shift in that branch. Cash can't be taken without one; with
    `require_active_shift` on (the default), no sale can. The shift row is share-locked so it
    can't be closed while the sale is written."""
    from app.activities.general.modules.pos.models import Shift, ShiftStatus

    if shift_id is not None:
        shift = (await db.execute(select(Shift).where(Shift.id == shift_id).with_for_update(read=True))).scalar_one_or_none()
        if shift is None:
            raise NotFoundError("الوردية غير موجودة")
        if shift.cashier_id != user_id:
            raise BusinessError("هذه الوردية لا تخصك")
        if shift.status != ShiftStatus.open:
            raise BusinessError("هذه الوردية مغلقة — افتح وردية جديدة")
        if shift.warehouse_id != warehouse_id:
            raise BusinessError("هذه الوردية مفتوحة في فرع غير فرع الفاتورة")
        return shift.id
    found = (await db.execute(
        select(Shift.id).where(Shift.cashier_id == user_id, Shift.warehouse_id == warehouse_id,
                               Shift.status == ShiftStatus.open)
        .order_by(Shift.started_at.desc()).limit(1).with_for_update(read=True)
    )).scalar_one_or_none()
    if found is not None:
        return found
    if cash:
        raise BusinessError("لا توجد وردية مفتوحة لك في هذا الفرع — افتح وردية لتسجيل النقدية")
    if require_setting and await setting_on(db, "pos", "require_active_shift", True):
        raise BusinessError("إعدادات نقطة البيع تشترط وردية مفتوحة للبيع — افتح وردية أولاً")
    return None
