"""Contacts: demo data for a new workspace (rows marked is_demo, removable by the owner).

Called by app/framework/demo.py in a fixed order with one random generator, so the same
workspace size gives the same data."""
from decimal import Decimal

from app.activities.general.modules.contacts.models.party import Customer, Supplier

CUSTOMER_NAMES = ["محمد عبد الله", "شركة النهضة للمقاولات", "ورشة السباك الحديثة", "أحمد سيد", "م. كريم فؤاد", "مؤسسة البناء المتين", "حسن إبراهيم", "ورشة الهرم للتكييف", "سمير رمضان", "شركة الأمل للتشطيبات", "مصطفى كامل", "ورشة النور", "عمرو زكي", "مؤسسة الصفوة", "إبراهيم نجيب", "شركة الوفاء", "ياسر عبد العال", "ورشة المعادي الحديثة", "خالد شوقي", "تسنيم للتركيبات"]
SUPPLIER_NAMES = ["شركة الأهرام للتوريدات", "مصنع الدلتا للبلاستك", "الوكيل التجاري الصيني", "مجموعة النيل التجارية", "مستوردون مصر", "مصنع الشرق للمواسير", "الشرق الأوسط للتوريدات", "بيت الخبرة للتوريدات", "النور للاستيراد", "المتحدون للتوريدات", "توكيل تركي", "إمبورت كو"]


async def seed(db, ctx) -> None:
    rng = ctx.rng
    ctx.customers = [Customer(id=ctx.new_id(), name=CUSTOMER_NAMES[i % len(CUSTOMER_NAMES)],
                              phone=f"01{rng.randrange(1, 3)}{rng.randrange(10**8)}", is_cash=(i == 0), is_demo=True)
                     for i in range(ctx.n_customers)]
    suppliers = [Supplier(id=ctx.new_id(), name=SUPPLIER_NAMES[i % len(SUPPLIER_NAMES)],
                          phone=f"02{rng.randrange(10**7)}", type="supplier", is_demo=True)
                 for i in range(ctx.n_suppliers)]
    if ctx.features and "credit" in ctx.features:
        for c in ctx.customers[1:4]:
            c.credit_limit = Decimal(rng.randrange(5_000, 50_000))
    db.add_all(ctx.customers)
    db.add_all(suppliers)
    await db.flush()
