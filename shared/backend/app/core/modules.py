"""Universal Modular App Engine for Mizan ERP.

Provides a pluggable module registry, business presets (Retail, Restaurant,
School, Services, Clinic), dependency resolution, and tenant-scoped module
activation.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.settings import StoreSetting
from app.catalog import canonical_module, canonical_modules
from app.framework.loader import manifest_index


@dataclass
class BusinessPreset:
    id: str
    name: str
    name_en: str
    icon: str
    badge: str
    description: str
    modules: list[str]


# Pre-packaged Business Vertical Bundles
BUSINESS_PRESETS: dict[str, BusinessPreset] = {
    "retail": BusinessPreset(
        id="retail",
        name="تجارة وتجزئة ومستودعات",
        name_en="Retail & Supermarket",
        icon="Store",
        badge="الأكثر شيوعاً",
        description="الحزمة الكاملة للمحلات التجارية، السوبرماركت، والمتاجر الاستهلاكية ومستودعات التجزئة.",
        modules=["core", "inventory", "pos", "finance", "hr"],
    ),
    "restaurant": BusinessPreset(
        id="restaurant",
        name="مطاعم، كافيهات، وضيافة",
        name_en="Restaurant & Hospitality",
        icon="UtensilsCrossed",
        badge="مخصص للمطاعم",
        description="إدارة متكاملة لصالة الطعام، تقسيم الطاولات، شاشات المطبخ، حسم مخزون المكونات الخام، والتوصيل.",
        modules=["core", "pos", "restaurant", "inventory", "finance"],
    ),
    "school": BusinessPreset(
        id="school",
        name="مدارس، جامعات، ومراكز تدريب",
        name_en="School & Academy",
        icon="GraduationCap",
        badge="مخصص للتعليم",
        description="إدارة شاملة لشؤون الطلاب، دفعات الأقساط، كشوف الحضور الأكاديمية، ورواتب المعلمين والموظفين.",
        modules=["core", "school", "finance", "hr"],
    ),
    "services": BusinessPreset(
        id="services",
        name="شركات خدمات، مكاتب، ومقاولات",
        name_en="Services & Consulting",
        icon="Briefcase",
        badge="مخصص للمشاريع",
        description="إصدار عروض الأسعار والمطالبات، تتبع عقود المشاريع والخدمات الاستشارية، وإدارة فريق العمل.",
        modules=["core", "services", "finance", "hr"],
    ),
    "pharmacy": BusinessPreset(
        id="pharmacy",
        name="صيدليات، مستودعات أدوية، ومراكز صرف",
        name_en="Pharmacy & Pharmaceuticals",
        icon="Pill",
        badge="مخصص للصيدليات",
        description="إدارة صرف الروشتات، حساب نسب التأمين، تتبع تواريخ الصلاحية والتشغيلات (FEFO)، وبدائل الأدوية العلمية، ودفتر السموم والمخدرات.",
        modules=["core", "inventory", "pos", "finance", "pharmacy"],
    ),
    "wholesale": BusinessPreset(
        id="wholesale",
        name="تجارة الجملة والتوزيع والتوريدات",
        name_en="Wholesale & Bulk Distribution",
        icon="Boxes",
        badge="توزيع وتوريدات",
        description="سلالم الأسعار الكمية، سقوف المديونية، تكلفة الاستيراد المفرغة Landed Cost، والشحن المباشر Drop-Shipping، ومكافآت التوزيع التراكمية.",
        modules=["core", "inventory", "finance", "wholesale"],
    ),
    "logistics": BusinessPreset(
        id="logistics",
        name="شحن ونقل وخدمات لوجستية وأساطيل",
        name_en="Logistics & Fleet Transportation",
        icon="Truck",
        badge="شحن وأساطيل",
        description="تتبع بوالص الشحن AWB/BoL، توجيه وتخطيط الرحلات، فحص دوري للمركبات، امتثال السائقين، إثبات التسليم الرقمي e-POD، وتكاليف الوقود.",
        modules=["core", "finance", "logistics"],
    ),
    "wms_3pl": BusinessPreset(
        id="wms_3pl",
        name="مستودعات وخدمات لوجستية للغير (3PL WMS)",
        name_en="3PL & Warehouse Management",
        icon="Warehouse",
        badge="مستودعات 3PL",
        description="إدارة مستودعات العملاء المتعددين، ترميز المواقع التخزينية، موجات الجمع والانتقاء، العبور السريع Cross-Docking، والفوترة الشهرية.",
        modules=["core", "inventory", "finance", "wms"],
    ),
    "ecommerce": BusinessPreset(
        id="ecommerce",
        name="تجارة إلكترونية ومتاجر متعددة القنوات",
        name_en="Omnichannel E-commerce",
        icon="Globe",
        badge="متاجر إلكترونية",
        description="ربط منصات المتاجر الرقمية، مخزون الأمان العازل، خط سير تجهيز الشحنات، تسوية بوابات الدفع، الدفع عند الاستلام COD، والمرتجعات RMA.",
        modules=["core", "inventory", "finance", "ecommerce"],
    ),
    "healthcare": BusinessPreset(
        id="healthcare",
        name="عيادات ومراكز طبية ومستشفيات",
        name_en="Clinics & Healthcare Hospital",
        icon="Stethoscope",
        badge="مراكز طبية",
        description="الملفات الطبية الإلكترونية EMR، حجز المواعيد والكشوفات، الروشتات الرقمية e-Rx، الفحوصات، وإدارة غرف وأسِرّة التنويم والمطالبات.",
        modules=["core", "healthcare_clinic", "pharmacy", "finance"],
    ),
    "law_firm": BusinessPreset(
        id="law_firm",
        name="مكاتب المحاماة والاستشارات القانونية",
        name_en="Law Firm & Legal Counsel",
        icon="Scale",
        badge="محاماة وقضايا",
        description="إدارة القضايا والملفات القضائية، أجندة الجلسات والطعون، فحص تعارض المصالح، الساعات المهنية المحتسبة، وأمانات الموكلين IOLTA.",
        modules=["core", "law", "finance"],
    ),
    "travel_agency": BusinessPreset(
        id="travel_agency",
        name="وكالات السياحة والسفر والحج والعمرة",
        name_en="Travel & Tourism Agency",
        icon="Plane",
        badge="سياحة وسفر",
        description="بناء وتصميم البرامج السياحية، حجوزات الطيران والفنادق ومنافست الركاب، محرك العمولات، وخزينة التأشيرات والجوازات.",
        modules=["core", "travel", "finance"],
    ),
    "hospitality_hotel": BusinessPreset(
        id="hospitality_hotel",
        name="فنادق ومنتجعات وشقق فندقية (PMS)",
        name_en="Hotel Property Management",
        icon="Building",
        badge="فنادق وضيافة",
        description="تسكين ومغادرة النزلاء (Check-in/Out)، فواتير الغرف والخدمات (Folio)، التدبير المنزلي، والتدقيق الليلي وإيرادات RevPAR.",
        modules=["core", "hospitality", "restaurant", "finance"],
    ),
    "gym_sports": BusinessPreset(
        id="gym_sports",
        name="أندية صحية وجيم وأكاديميات رياضية",
        name_en="Gym & Sports Fitness Club",
        icon="Dumbbell",
        badge="لياقة وجيم",
        description="إدارة عضويات الجيم وتجميد الاشتراكات، بوابات الدخول Turnstile، باقات التدريب الخاص PT، الحصص الجماعية، وقياسات InBody.",
        modules=["core", "gym", "pos", "finance"],
    ),
    "salon_spa": BusinessPreset(
        id="salon_spa",
        name="صالونات تجميل ومراكز سبا وعناية",
        name_en="Salon & Beauty Spa",
        icon="Scissors",
        badge="تجميل وسبا",
        description="مصفوفة الخدمات والمواعيد، تتبع صبغات الشعر وتركيبات العناية، كراسي التصفيف وغرف السبا، ومحرك عمولات المصففين.",
        modules=["core", "salon", "pos", "finance"],
    ),
    "creative_agency": BusinessPreset(
        id="creative_agency",
        name="وكالات دعاية وإعلان ومكاتب ترجمة",
        name_en="Creative & Translation Agency",
        icon="Palette",
        badge="دعاية وترجمة",
        description="المشاريع الإبداعية ومراحل التسليم، مصفوفة سعة الفريق، عقود الساعات الشهرية Retainers، والترجمة المعتمدة وحساب الكلمات.",
        modules=["core", "agency", "services", "finance"],
    ),
    "field_service": BusinessPreset(
        id="field_service",
        name="صيانة ميدانية وخدمات فنية وتشغيل (FSM)",
        name_en="Field Service & Technical Support",
        icon="Wrench",
        badge="صيانة ميدانية",
        description="أوامر العمل وبلاغات الأعطال، توجيه الفنيين GPS، مخزون سيارات الصيانة Van Inventory، عقود الصيانة AMC، ومراقبة SLA.",
        modules=["core", "field_service", "inventory", "finance"],
    ),
    "mfg": BusinessPreset(
        id="mfg",
        name="مصانع ميكانيكية وتجميع وهندسة صناعية",
        name_en="Discrete Manufacturing Plant",
        icon="Factory",
        badge="تصنيع وتجميع",
        description="شجرة المنتج متعددة المستويات BOM، تخطيط الاحتياجات MRP، مراكز التشغيل والمسارات، تكلفة أوامر التشغيل، ومؤشرات كفاءة المعدات OEE.",
        modules=["core", "manufacturing", "inventory", "purchases", "finance"],
    ),
    "fod": BusinessPreset(
        id="fod",
        name="صناعات غذائية، ألبان، ومشروبات (HACCP)",
        name_en="Food & Beverage Processing Plant",
        icon="Utensils",
        badge="أغذية ومشروبات",
        description="تركيبات ووصفات التصنيع، سلامة الغذاء ونقاط HACCP، السحب والاستدعاء الفوري Mock Recall، وتتبع التشغيلات FEFO.",
        modules=["core", "food_manufacturing", "inventory", "purchases", "finance"],
    ),
    "phm": BusinessPreset(
        id="phm",
        name="مصانع أدوية ومستحضرات طبية وكيميائية (cGMP)",
        name_en="Pharmaceutical GMP Factory",
        icon="ShieldCheck",
        badge="دوائي وكيميائي",
        description="سجلات التشغيل الدوائية EBR، اعتماد وضبط الجودة QP Release، تقارير الانحرافات وحالات CAPA، وتوقيعات 21 CFR Part 11 المعتمدة.",
        modules=["core", "pharma_manufacturing", "pharmacy", "inventory", "purchases", "finance"],
    ),
    "prn": BusinessPreset(
        id="prn",
        name="مطابع، علب كرتون، وخطوط تغليف",
        name_en="Commercial Printing & Packaging Plant",
        icon="Printer",
        badge="طباعة وتغليف",
        description="أوامر الطباعة Job Dockets، تخطيط المونتاج Imposition، إدارة الأحبار والورق GSM، وحساب تكلفة الماكينات بساعات MHR.",
        modules=["core", "printing", "manufacturing", "inventory", "purchases", "finance"],
    ),
    "cst": BusinessPreset(
        id="cst",
        name="شركات مقاولات، إنشاءات، وأعمال كهروميكانيكية",
        name_en="General Contracting & Construction",
        icon="HardHat",
        badge="مقاولات وإنشاءات",
        description="إدارة مشاريع البناء والمواقع، جداول الكميات BOQ، المستخلصات التنفيذية IPC، تتبع أوامر التغيير، وإدارة المعدات الثقيلة.",
        modules=["core", "construction", "inventory", "purchases", "finance", "hr"],
    ),
    "rec": BusinessPreset(
        id="rec",
        name="تطوير عقاري، مجمعات تجارية، وإدارة أملاك",
        name_en="Real Estate & Property Management",
        icon="Building2",
        badge="عقارات وأملاك",
        description="إدارة المولات والمباني، عقود الإيجار والتحصيل، الشيكات الآجلة PDC، رسوم الخدمات المشتركة CAM، وتحليل عوائد الاستثمار NOI.",
        modules=["core", "real_estate", "finance"],
    ),
    "agr": BusinessPreset(
        id="agr",
        name="شركات استصلاح زراعي، مزارع، وإنتاج حيواني",
        name_en="Commercial Agriculture & Livestock Farm",
        icon="Tractor",
        badge="زراعة وإنتاج",
        description="إدارة الأراضي والبيفوتات، جداول التسميد والمكافحة PHI، دورات الري، شحنات الحصاد GlobalG.A.P.، وقطعان الألبان والماشية.",
        modules=["core", "agriculture", "inventory", "purchases", "finance"],
    ),
    "eng": BusinessPreset(
        id="eng",
        name="محطات طاقة شمسية، توربينات، وشبكات كهرباء",
        name_en="Power Generation & Solar Plant",
        icon="Zap",
        badge="طاقة وكهرباء",
        description="إدارة محطات التوليد، ربط SCADA اللحظي، تصاريح العمل وعزل الطاقة PTW/LOTO، تسوية اتفاقيات PPA، ومراقبة الانبعاثات CEMS.",
        modules=["core", "energy", "inventory", "purchases", "finance", "hr"],
    ),
    "bnk": BusinessPreset(
        id="bnk",
        name="بنوك، مؤسسات تمويل، وشركات ائتمان",
        name_en="Banking & Financial Institutions",
        icon="Landmark",
        badge="مصارف وتمويل",
        description="إدارة الحسابات المصرفية، سجل المعاملات الفورية، الجدارة الائتمانية I-Score، تقييم خسائر الائتمان المتوقعة ECL، ومراقبة الامتثال AML.",
        modules=["core", "banking", "finance"],
    ),
    "ins": BusinessPreset(
        id="ins",
        name="شركات تأمين عام وطبي وإعادة تأمين",
        name_en="Insurance & Reinsurance",
        icon="Shield",
        badge="تأمين ومطالبات",
        description="إصدار وثائق التأمين، إدارة الحوادث والتعويضات FNOL، المعاينات الفنية، مخصصات IFRS 17، وتوزيع اتفاقيات إعادة التأمين.",
        modules=["core", "insurance", "finance"],
    ),
    "gov": BusinessPreset(
        id="gov",
        name="هيئات حكومية، صناديق سيادية، ومنظمات دولية",
        name_en="Government & Nonprofit",
        icon="Building",
        badge="قطاع عام ومنظمات",
        description="محاسبة الصناديق والمنح، الرقابة على الموازنات وحجز الارتباطات، سجلات المساعدات الإنسانية والتحقق البصري، والمناقصات الحكومية.",
        modules=["core", "government", "finance"],
    ),
    "ent": BusinessPreset(
        id="ent",
        name="مدن ملاهي، دور سينما، ومسارح وفعاليات",
        name_en="Entertainment & Theme Parks",
        icon="Ticket",
        badge="ترفيه ومهرجانات",
        description="تنظيم الفعاليات والمقاعد، بوابات التذاكر الإلكترونية، بطاقات شحن ألعاب الأركيد، وبوفيهات الأغذية السريعة.",
        modules=["core", "events", "pos", "finance"],
    ),
    "oil": BusinessPreset(
        id="oil",
        name="شركات استخراج بترول وغاز، حفر، ومستودعات صهاريج",
        name_en="Oil & Gas E&P",
        icon="Flame",
        badge="بترول وطاقة",
        description="إدارة حقول وآبار البترول والغاز، تقارير الإنتاج، تقرير الحفر اليومي DDR، قياسات صهاريج الخام والمصافي، ومطالبات الشركاء JV Cash Calls.",
        modules=["core", "oil_gas", "finance", "construction", "energy"],
    ),
}

DEFAULT_MODULES = ["core", "inventory", "pos", "finance", "hr"]
DEFAULT_PRESET = "retail"

SECTOR_TO_PRESET: dict[str, str] = {
    "retail": "retail", "restaurant": "restaurant", "pharmacy": "pharmacy",
    "consulting": "services", "school": "school", "wholesale": "wholesale",
    "logistics": "logistics", "wms_3pl": "wms_3pl", "ecommerce": "ecommerce",
    "healthcare": "healthcare", "law_firm": "services", "travel": "travel_agency",
    "hotel": "hospitality_hotel", "gym": "gym_sports", "salon": "salon_spa",
    "agency": "creative_agency", "field_service": "field_service",
    "discrete_mfg": "mfg", "food_mfg": "mfg", "pharma_mfg": "mfg", "printing": "prn",
    "construction": "cst", "real_estate": "rec", "agriculture": "agr", "energy": "services",
    "banking": "bnk", "insurance": "ins", "government": "gov", "entertainment": "ent",
    "oil_gas": "oil", "services": "services", "plumbing": "retail", "electrical": "retail",
    "tiles": "retail", "paint": "retail",
}


async def get_active_modules(db: AsyncSession) -> list[str]:
    """The current workspace's active modules: tenants.active_modules, the only source
    (ADR-006 phase 1; the installed_modules setting was folded into it by migration v50)."""
    from app.core.tenancy import current_tenant_id
    from app.models.tenant import Tenant

    tid = current_tenant_id.get()
    if tid is not None:
        mods = await db.scalar(select(Tenant.active_modules).where(Tenant.id == tid))
        if mods:
            return canonical_modules(["core", *mods])
    return list(DEFAULT_MODULES)


async def get_active_preset(db: AsyncSession) -> str:
    """Retrieve active preset identifier."""
    result = await db.execute(select(StoreSetting).where(StoreSetting.key == "active_business_preset"))
    row = result.scalar_one_or_none()
    if row and row.value:
        return row.value
    # Fallback for tenants created before preset was persisted: derive from sector.
    try:
        from app.core.tenancy import current_tenant_id
        from app.models.tenant import Tenant

        tid = current_tenant_id.get()
        if tid is not None:
            t = (await db.execute(select(Tenant).where(Tenant.id == tid))).scalar_one_or_none()
            if t and getattr(t, "sector", None):
                return SECTOR_TO_PRESET.get(t.sector, "retail")
    except Exception:
        pass
    return DEFAULT_PRESET


async def set_active_modules(db: AsyncSession, modules: list[str], preset_id: str | None = None) -> None:
    """Save the current workspace's active modules (with their dependencies) and preset."""
    from app.core.tenancy import current_tenant_id
    from app.models.tenant import Tenant

    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(status_code=400, detail="لا توجد منشأة محددة")

    clean_mods = canonical_modules(["core", *modules])
    for mod_id in list(clean_mods):
        for dep in manifest_index().get(mod_id, {}).get("dependencies", []):
            if dep not in clean_mods:
                clean_mods.append(dep)

    tenant = await db.get(Tenant, tid)
    if tenant is None:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    tenant.active_modules = clean_mods

    if preset_id:
        res_p = await db.execute(select(StoreSetting).where(StoreSetting.key == "active_business_preset"))
        row_p = res_p.scalar_one_or_none()
        if row_p:
            row_p.value = preset_id
        else:
            db.add(StoreSetting(key="active_business_preset", value=preset_id))

    await db.commit()


def require_module(module_id: str):
    """FastAPI dependency to guard endpoints requiring a specific active module."""
    module_id = canonical_module(module_id)

    from app.dependencies import get_current_user

    # Depends on the user so the workspace is bound before its modules are read; without it the
    # guard read the modules with no workspace bound (another workspace's, or several).
    async def _checker(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
        active = await get_active_modules(db)
        if module_id not in active:
            index = manifest_index()
            name = index.get(module_id, {}).get("name", module_id)
            raise HTTPException(
                status_code=403,
                detail=f"وحدة «{name}» غير مفعلة في اشتراك المنشأة الحالي. يمكنك تفعيلها من متجر الإضافات.",
            )
        return True

    return _checker
