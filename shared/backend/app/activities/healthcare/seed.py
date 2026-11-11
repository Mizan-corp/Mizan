"""Healthcare: demo data for a new workspace. CATALOG: category -> item names (Arabic trade
names), turned into products by modules/general/inventory/seed.py."""

CATALOG: list[tuple[str, list[str]]] = [
    ('أدوية ومسكنات', ['مسكن باراسيتامول 500 مجم', 'مضاد حيوي كبسولات 1 جم', 'فيتامين C فوار 1000 مجم', 'أقراص استحلاب للحلق']),
    ('عناية ومستلزمات', ['شاش معقم طبي 10×10', 'لاصق جروح طبي علبة', 'كحول طبي معقم 70% 500 مل', 'جهاز قياس ضغط رقمي']),
    ('فيتامينات ومكملات', ['أوميجا 3 بلس كبسولات', 'فيتامين د 5000 وحدة', 'مكمل غذائي كالسيوم وزنك']),
]


async def seed(db, ctx) -> None:
    """After the general demo data: the clinic's own records (patients, appointments, beds…)."""
    from app.modules.healthcare.healthcare_clinic.seed import seed_clinic_records

    await seed_clinic_records(db, str(ctx.tenant_id))
