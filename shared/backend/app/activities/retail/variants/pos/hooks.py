"""POS, retail variant: weighing-scale labels (ADR-006 phase 8).

Scales in shops print EAN-13 labels in the "restricted circulation" range (first digit 2):
  [prefix: 2 digits][item: item_digits][value: the rest][check digit]
The item is the product's scale code (PLU, the `scale_code` field this variant adds to
products); the value is the weight in grams (value "weight") or the price in piastres ("price").
Settings: pos.scale_barcode {prefixes, item_digits, value} in variant.json, or the activity's.
"""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import or_, select

from app.framework import variants

DEFAULTS = {"prefixes": [str(n) for n in range(20, 30)], "item_digits": 5, "value": "weight"}


def ean13_ok(code: str) -> bool:
    if len(code) != 13 or not code.isdigit():
        return False
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(code[:12]))
    return (10 - total % 10) % 10 == int(code[12])


def decode(code: str, cfg: dict) -> tuple[str, int] | None:
    """(item code, value) from a scale label, or None if this isn't one."""
    cfg = {**DEFAULTS, **(cfg or {})}
    item_digits = int(cfg["item_digits"])
    if not ean13_ok(code) or not any(code.startswith(p) for p in cfg["prefixes"]) or not 3 <= item_digits <= 6:
        return None
    item = code[2:2 + item_digits]
    return item, int(code[2 + item_digits:12])


async def scan(db, activity_id=None, code: str = "", **_):
    from app.activities.general.modules.inventory.models.product import Product

    cfg = {**DEFAULTS, **(variants.setting("pos", "scale_barcode", activity_id, {}) or {})}
    decoded = decode(code, cfg)
    if not decoded:
        return None
    item, value = decoded
    scale_code = Product.extra["scale_code"].astext
    product = (await db.execute(
        select(Product).where(or_(scale_code == item, scale_code == (item.lstrip("0") or "0")),
                              Product.is_active.is_(True)).limit(1)
    )).scalar_one_or_none()
    if product is None:
        return None
    if cfg["value"] == "price":
        price = Decimal(value) / 100
        unit_price = Decimal(product.retail_price or 0)
        if unit_price <= 0:
            return None
        qty = (price / unit_price).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        if qty <= 0:
            return None
        return {"product": product, "qty": qty, "scale": {"item": item, "price": str(price)}}
    qty = (Decimal(value) / 1000).quantize(Decimal("0.001"))
    if qty <= 0:
        return None
    return {"product": product, "qty": qty, "scale": {"item": item, "weight_kg": str(qty)}}
