"""Retail: demo data for a new workspace.

CATALOG (category -> (item name, retail price in EGP)) becomes products through
modules/general/inventory/seed.py; seed() then makes them look like a supermarket's: packaged goods
are sold by the piece, and the fresh counter (fruit, vegetables, cheese, meat) by weight, each with
the scale code (PLU) its labels carry, so the till's scale labels work out of the box (POS retail
variant).
"""
WEIGHED = "خضار وفاكهة ولحوم بالوزن"

CATALOG: list[tuple[str, list]] = [
    ('مواد غذائية وبقالة', [('أرز مصري درجة أولى 1 كجم', 38), ('سكر أبيض ناعم 1 كجم', 37), ('زيت عباد الشمس 800 مل', 82),
                           ('مكرونة فرن 400 جم', 18), ('شاي أسود فاخر 250 جم', 65)]),
    ('ألبان وأجبان', [('جبنة بيضاء براميلي 1 كجم', 140), ('لبن كامل الدسم 1 لتر', 42), ('جبنة رومي قديمة 500 جم', 175),
                      ('زبادي طبيعي 105 جم', 9)]),
    ('مشروبات وعصائر', [('عصير برتقال طبيعي 1 لتر', 55), ('مياه معدنية 1.5 لتر', 9), ('مشروب غازي كانز 330 مل', 15)]),
    ('منظفات وعناية', [('مسحوق غسيل أوتوماتيك 3 كجم', 245), ('سائل غسيل أطباق 1 لتر', 48), ('صابون يد معقم 120 جم', 22),
                       ('مناديل مطبخ رول', 28)]),
    (WEIGHED, [('طماطم (بالكيلو)', 18), ('خيار (بالكيلو)', 22), ('بطاطس (بالكيلو)', 20), ('موز (بالكيلو)', 40),
               ('جبنة رومي (بالكيلو)', 320), ('لحم بقري مفروم (بالكيلو)', 420)]),
]


async def seed(db, ctx) -> None:
    """Units, and scale codes for the weighed items."""
    plu = 101
    for product in ctx.products:
        if "(بالكيلو)" in product.name:
            product.unit = "كجم"
            product.barcode = None  # weighed at the counter: the scale prints the label
            product.extra = {**(product.extra or {}), "scale_code": f"{plu:05d}"}
            plu += 1
        else:
            product.unit = "عدد"
    await db.flush()
