"""Pharmacy: demo data for a new workspace.

CATALOG (category -> trade names) becomes products through modules/general/inventory/seed.py;
seed() then fills each drug's details (the inventory pharmacy variant's product fields) and splits
its stock into batches with expiry dates (a few close to expiry, one expired), so FEFO, expiry
alerts and prescription rules have something to show.
"""
from datetime import timedelta
from decimal import Decimal

# trade name -> (scientific name, dosage form, strength, prescription required, controlled)
DRUGS: dict[str, tuple[str, str, str, bool, bool]] = {
    "بنادول 500 مجم": ("Paracetamol", "أقراص", "500 mg", False, False),
    "بروفين 400 مجم": ("Ibuprofen", "أقراص", "400 mg", False, False),
    "كتافلام 50 مجم": ("Diclofenac potassium", "أقراص", "50 mg", False, False),
    "أوجمنتين 1 جم": ("Amoxicillin + Clavulanic acid", "أقراص", "1 g", True, False),
    "زيثروماكس 500 مجم": ("Azithromycin", "أقراص", "500 mg", True, False),
    "سيبروفلوكساسين 500 مجم": ("Ciprofloxacin", "أقراص", "500 mg", True, False),
    "فلاجيل 500 مجم": ("Metronidazole", "أقراص", "500 mg", True, False),
    "جلوكوفاج 850 مجم": ("Metformin", "أقراص", "850 mg", True, False),
    "كونكور 5 مجم": ("Bisoprolol", "أقراص", "5 mg", True, False),
    "نورفاسك 5 مجم": ("Amlodipine", "أقراص", "5 mg", True, False),
    "ليبيتور 20 مجم": ("Atorvastatin", "أقراص", "20 mg", True, False),
    "نيكسيوم 40 مجم": ("Esomeprazole", "كبسولات", "40 mg", False, False),
    "أنتينال كبسولات": ("Nifuroxazide", "كبسولات", "200 mg", False, False),
    "زيرتك 10 مجم": ("Cetirizine", "أقراص", "10 mg", False, False),
    "كونجستال": ("Paracetamol + Chlorpheniramine + Pseudoephedrine", "أقراص", "", False, False),
    "توسيفان شراب": ("Dextromethorphan", "شراب", "120 ml", False, False),
    "فنتولين بخاخ": ("Salbutamol", "بخاخ", "100 mcg", True, False),
    "ترامادول 50 مجم": ("Tramadol", "كبسولات", "50 mg", True, True),
    "زاناكس 0.5 مجم": ("Alprazolam", "أقراص", "0.5 mg", True, True),
    "ليريكا 75 مجم": ("Pregabalin", "كبسولات", "75 mg", True, True),
    "فيوسيدين كريم": ("Fusidic acid", "مرهم", "2%", False, False),
    "بيتادين محلول": ("Povidone-iodine", "أخرى", "10%", False, False),
    "قطرة توبراديكس": ("Tobramycin + Dexamethasone", "قطرة", "5 ml", True, False),
    "فيتامين سي فوار 1000 مجم": ("Ascorbic acid", "أكياس", "1000 mg", False, False),
    "فيتامين د3 5000 وحدة": ("Cholecalciferol", "كبسولات", "5000 IU", False, False),
    "أوميجا 3 كبسولات": ("Omega-3 fatty acids", "كبسولات", "1000 mg", False, False),
}

CATALOG: list[tuple[str, list[str]]] = [
    ("مسكنات وخافض حرارة", ["بنادول 500 مجم", "بروفين 400 مجم", "كتافلام 50 مجم", "كونجستال"]),
    ("مضادات حيوية", ["أوجمنتين 1 جم", "زيثروماكس 500 مجم", "سيبروفلوكساسين 500 مجم", "فلاجيل 500 مجم"]),
    ("أمراض مزمنة", ["جلوكوفاج 850 مجم", "كونكور 5 مجم", "نورفاسك 5 مجم", "ليبيتور 20 مجم"]),
    ("جهاز هضمي وحساسية", ["نيكسيوم 40 مجم", "أنتينال كبسولات", "زيرتك 10 مجم", "توسيفان شراب", "فنتولين بخاخ"]),
    ("أدوية مراقبة (جدول)", ["ترامادول 50 مجم", "زاناكس 0.5 مجم", "ليريكا 75 مجم"]),
    ("جلدية وعيون", ["فيوسيدين كريم", "بيتادين محلول", "قطرة توبراديكس"]),
    ("فيتامينات ومكملات", ["فيتامين سي فوار 1000 مجم", "فيتامين د3 5000 وحدة", "أوميجا 3 كبسولات"]),
]


def drug_extra(name: str) -> dict:
    """The drug's details; demo product names may carry a suffix ("— استيراد")."""
    key = max((k for k in DRUGS if name.startswith(k)), key=len, default=None)
    if key is None:
        return {}
    scientific, form, strength, rx, controlled = DRUGS[key]
    extra = {"scientific_name": scientific, "dosage_form": form, "strength": strength,
             "requires_prescription": rx, "is_controlled": controlled}
    return {k: v for k, v in extra.items() if v not in ("", None)}


async def seed(db, ctx) -> None:
    """Drug details on the products, and their stock split into batches (lots = stock)."""
    from sqlalchemy import text

    from app.activities.pharmacy.modules.batches.models import Lot

    today = ctx.now.date()
    for product in ctx.products:
        product.extra = {**(product.extra or {}), **drug_extra(product.name)}
    await db.flush()
    balances = (await db.execute(text(
        "SELECT product_id, warehouse_id, qty FROM stock_balances WHERE tenant_id = :t AND qty > 0"
    ), {"t": ctx.tenant_id})).all()
    for i, (product_id, warehouse_id, qty) in enumerate(balances):
        qty = Decimal(qty)
        parts = 1 if qty < 6 else ctx.rng.choice((1, 2, 2, 3))
        shares = [qty // parts] * parts
        shares[-1] += qty - sum(shares)
        for n, share in enumerate(shares):
            if share <= 0:
                continue
            if i % 11 == 0 and n == 0:
                expiry = today - timedelta(days=ctx.rng.randint(5, 40))     # expired: shows in alerts, never sold
            elif i % 4 == 0 and n == 0:
                expiry = today + timedelta(days=ctx.rng.randint(15, 80))    # expiring soon
            else:
                expiry = today + timedelta(days=ctx.rng.randint(150, 720))
            db.add(Lot(tenant_id=ctx.tenant_id, product_id=product_id, warehouse_id=warehouse_id,
                       batch_number=f"B{expiry:%y%m}-{ctx.rng.randint(100, 999)}{n}", expiry_date=expiry, qty=share))
    await db.flush()
