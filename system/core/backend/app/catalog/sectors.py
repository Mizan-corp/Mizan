"""Business sectors, plans and onboarding defaults shared by every Mizan service.

Used by the website (signup/onboarding), the system (tenant resolution) and the
admin panel (tenant provisioning).
"""

from app.catalog import GENERAL, activities

TRIAL_DAYS = 14

PLANS = [
    {"id": "starter", "name": "باقة البداية (Starter)", "price_egp": 450,
     "tagline": "للمتاجر والمنشآت الناشئة — فرع واحد متكامل",
     "features": ["فرع واحد · حتى 5 مستخدمين", "نقطة بيع + مخزون + مبيعات", "طباعة إيصالات حرارية 80mm/58mm", "شاشات مطبخ KDS أو ماسح باركود"]},
    {"id": "pro", "name": "باقة المحترفين (Pro)", "price_egp": 850, "popular": True,
     "tagline": "الأكثر طلباً — صالات الجيم، المطاعم، والسلاسل",
     "features": ["حتى 3 فروع · 15 مستخدمًا", "كافة كوليكشنات الأنشطة (نوادي، مطاعم، مدارس)", "بيانات كل منشأة معزولة ومحمية", "رواتب وموظفون HR ونسخ احتياطي يومي"]},
    {"id": "enterprise", "name": "باقة المؤسسات (Enterprise)", "price_egp": 1950,
     "tagline": "لسلاسل الأعمال الكبرى والمشاريع متعددة الفروع",
     "features": ["فروع ومستخدمون بلا حدود", "خادم VPS مخصص مع عزل أمني فائق", "ترخيص نسخة سطح مكتب أوفلاين (.exe)", "دومين مخصص وتخزين سحابي غير محدود"]},
]

# Activities come from app/catalog/activities.json (ADR-006); these names stay for callers.
SECTORS = [a for a in activities() if a != GENERAL]
SCALES = ["small", "medium", "large"]

SECTOR_PRIMARY_MODULES: dict[str, list[str]] = {a: activities()[a]["modules"] for a in SECTORS}

SECTOR_PRIMARY_ROUTES: dict[str, str] = {a: activities()[a]["home"] for a in SECTORS}

PALETTE_HUES = {
    "mizan": 350,
    "slate": 240,
    "cobalt": 250,
    "emerald": 155,
    "amber": 75,
    "monokai": 255,
    "water": 250,
    "copper": 55,
    "midnight": 230,
    "ruby": 0,
    "rose": 340,
    "grape": 290,
    "violet": 275,
    "indigo": 255,
    "ocean": 215,
    "cyan": 190,
    "teal": 170,
    "olive": 145,
    "lime": 95,
    "honey": 50,
    "tangerine": 25,
}


SCALE_ALIASES = {
    "growing": "medium",
    "starter": "small",
    "micro": "small",
    "enterprise": "large",
}
