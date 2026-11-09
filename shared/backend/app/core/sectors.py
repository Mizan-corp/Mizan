"""Business sectors, plans and onboarding defaults shared by every Mizan service.

Used by the website (signup/onboarding), the system (tenant resolution) and the
admin panel (tenant provisioning).
"""

TRIAL_DAYS = 14

PLANS = [
    {"id": "starter", "name": "باقة البداية (Starter)", "price_egp": 450,
     "tagline": "للمتاجر والمنشآت الناشئة — فرع واحد متكامل",
     "features": ["فرع واحد · حتى 5 مستخدمين", "نقطة بيع + مخزون + مبيعات", "طباعة إيصالات حرارية 80mm/58mm", "شاشات مطبخ KDS أو ماسح باركود"]},
    {"id": "pro", "name": "باقة المحترفين (Pro)", "price_egp": 850, "popular": True,
     "tagline": "الأكثر طلباً — صالات الجيم، المطاعم، والسلاسل",
     "features": ["حتى 3 فروع · 15 مستخدمًا", "كافة كوليكشنات الأنشطة (نوادي، مطاعم، مدارس)", "قاعدة بيانات سحابية مستقلة (Neon Postgres)", "رواتب وموظفون HR ونسخ احتياطي يومي"]},
    {"id": "enterprise", "name": "باقة المؤسسات (Enterprise)", "price_egp": 1950,
     "tagline": "لسلاسل الأعمال الكبرى والمشاريع متعددة الفروع",
     "features": ["فروع ومستخدمون بلا حدود", "خادم VPS مخصص مع عزل أمني فائق", "ترخيص نسخة سطح مكتب أوفلاين (.exe)", "دومين مخصص وتخزين سحابي غير محدود"]},
]

SECTORS = [
    # Phase 1: Core Business Systems
    "retail", "restaurant", "pharmacy", "consulting", "school",
    # Phase 2: Distribution and Logistics
    "wholesale", "logistics", "wms_3pl", "ecommerce",
    # Phase 3: Service-Based Systems
    "healthcare", "law_firm", "travel", "hotel", "gym", "salon", "agency", "field_service",
    # Phase 4: Manufacturing and Production
    "discrete_mfg", "food_mfg", "pharma_mfg", "printing",
    # Phase 5: Projects and Infrastructure
    "construction", "real_estate", "agriculture", "energy",
    # Phase 6: Specialized Systems
    "banking", "insurance", "government", "entertainment", "oil_gas",
    # Legacy aliases for backward compatibility
    "services", "plumbing", "electrical", "tiles", "paint",
]
SCALES = ["small", "medium", "large"]

SECTOR_PRIMARY_MODULES: dict[str, list[str]] = {
    # Phase 1: Core Business Systems
    "retail": ["pos", "inventory", "sales", "finance", "hr"],
    "restaurant": ["restaurant", "pos", "inventory", "finance"],
    "pharmacy": ["pharmacy", "inventory", "pos", "finance"],
    "consulting": ["services", "finance", "hr"],
    "school": ["school", "finance", "hr"],
    # Phase 2: Distribution and Logistics
    "wholesale": ["wholesale", "inventory", "sales", "finance"],
    "logistics": ["logistics", "finance", "operations"],
    "wms_3pl": ["wms", "inventory", "finance"],
    "ecommerce": ["ecommerce", "inventory", "sales", "finance"],
    # Phase 3: Service-Based Systems
    "healthcare": ["healthcare_clinic", "pharmacy", "finance", "inventory", "hr"],
    "law_firm": ["law", "finance", "hr"],
    "travel": ["travel", "sales", "finance"],
    "hotel": ["hospitality", "restaurant", "finance"],
    "gym": ["gym", "pos", "finance"],
    "salon": ["salon", "pos", "finance"],
    "agency": ["agency", "finance", "operations"],
    "field_service": ["field_service", "inventory", "operations", "finance"],
    # Phase 4: Manufacturing and Production
    "discrete_mfg": ["mfg", "inventory", "operations", "finance"],
    "food_mfg": ["fod", "inventory", "operations", "finance"],
    "pharma_mfg": ["phm", "inventory", "operations", "finance"],
    "printing": ["prn", "inventory", "operations", "finance"],
    # Phase 5: Projects and Infrastructure
    "construction": ["cst", "inventory", "operations", "finance"],
    "real_estate": ["rec", "finance", "operations"],
    "agriculture": ["agr", "inventory", "operations", "finance"],
    "energy": ["eng", "inventory", "operations", "finance"],
    # Phase 6: Specialized Systems
    "banking": ["bnk", "finance"],
    "insurance": ["ins", "finance"],
    "government": ["gov", "finance", "operations"],
    "entertainment": ["ent", "pos", "finance", "operations"],
    "oil_gas": ["oil", "operations", "finance"],
    # Legacy aliases
    "services": ["services", "finance", "hr"],
    "plumbing": ["pos", "inventory", "finance"],
    "electrical": ["pos", "inventory", "finance"],
    "tiles": ["pos", "inventory", "finance"],
    "paint": ["pos", "inventory", "finance"],
}

SECTOR_PRIMARY_ROUTES: dict[str, str] = {
    # Phase 1: Core Business Systems
    "retail": "/pos",
    "restaurant": "/restaurant/tables",
    "pharmacy": "/pharmacy",
    "consulting": "/services",
    "school": "/school/students",
    # Phase 2: Distribution and Logistics
    "wholesale": "/wholesale",
    "logistics": "/logistics",
    "wms_3pl": "/wms",
    "ecommerce": "/ecommerce",
    # Phase 3: Service-Based Systems
    "healthcare": "/clinic",
    "law_firm": "/law",
    "travel": "/travel",
    "hotel": "/hospitality",
    "gym": "/gym",
    "salon": "/salon",
    "agency": "/agency",
    "field_service": "/field-service",
    # Phase 4: Manufacturing and Production
    "discrete_mfg": "/mfg",
    "food_mfg": "/fod",
    "pharma_mfg": "/phm",
    "printing": "/prn",
    # Phase 5: Projects and Infrastructure
    "construction": "/cst",
    "real_estate": "/rec",
    "agriculture": "/agr",
    "energy": "/eng",
    # Phase 6: Specialized Systems
    "banking": "/bnk",
    "insurance": "/ins",
    "government": "/gov",
    "entertainment": "/ent",
    "oil_gas": "/oil",
    # Legacy aliases
    "services": "/services",
    "plumbing": "/pos",
    "electrical": "/pos",
    "tiles": "/pos",
    "paint": "/pos",
}

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
}


SCALE_ALIASES = {
    "growing": "medium",
    "starter": "small",
    "micro": "small",
    "enterprise": "large",
}
