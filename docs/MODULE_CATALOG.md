# Mizan ERP — Module Catalog

Every module, generated from the manifests by `python manage.py module catalog` (a test fails when
it's out of date); ids are folder names. A business activity is one folder (ADR-010):
`shared/backend/app/activities/<activity>/modules/<module_id>/`, screens in
`system/frontend/src/activities/<activity>/modules/<module_id>/`, with the activity's variants of
other activities' modules in `activities/<activity>/variants/<module>/`.
Status: **active** (built, offered) or *planned* (laid out from the SRS, not offered yet).

## General (`general`, general)

يرثه كل نشاط: جهات الاتصال، الأصناف، المخزون، المبيعات، المشتريات، المالية، نقاط البيع، الموظفون، التقارير

Turns on: `core`, `contacts`, `inventory`, `operations`, `sales`, `purchases`, `finance`, `pos`, `hr`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `accounting` | Accounting (double-entry ledger) | **active** | دليل الحسابات ودفتر اليومية بالقيد المزدوج: قيود تلقائية للمبيعات والمشتريات والمرتجعات والدرج والخزائن والمحافظ والمصروفات والرواتب،… |
| `assets` | Asset management | *planned* |  |
| `contacts` | Contacts & Partners | **active** | سجل الموردين والعملاء، كشوف الحسابات التفصيلية، حدود الائتمان وسقوف المديونية، وأرصدة الذمم. |
| `customer_portal` | Customer portal | *planned* |  |
| `documents` | Document management | *planned* |  |
| `finance` | Finance & Treasury | **active** | الخزائن والحسابات البنكية والمحافظ الإلكترونية، المصروفات واعتمادها، بنود الصرف، حركة الخزينة اليومية، وإقفال الفترات الشهرية. |
| `helpdesk` | Help Desk | **active** | Internal service offerings with independent optional catalog. Request/work compatibility in progress. |
| `hr` | Human Resources & Payroll | **active** | سجلات الموظفين، مسيرات الرواتب الشهرية، الحضور والانصراف، والسلف والخصومات. |
| `inventory` | Inventory & Supply | **active** | تتبع الأرصدة اللحظية، إدارة الفروع والمستودعات، تسويات الجرد، وأوامر الشراء والتوريد. |
| `loyalty` | Loyalty rewards | *planned* |  |
| `operations` | Stock Operations | **active** | أذون الصرف بين المخازن والفروع (وإلغاؤها) وطلبات النواقص (اعتمادها وصرفها أو إلغاؤها)، بترقيم مستقل لكل منشأة. |
| `pos` | Point of Sale (POS) | **active** | إصدار الفواتير الفوري، دعم قارئ الباركود، الشاشات اللمسية، إدارة أدراج الكاشير والورديات. |
| `pricing` | Pricing engine | *planned* |  |
| `projects` | Project management | *planned* |  |
| `purchases` | Purchases & Procurement | **active** | أوامر الشراء، استلام البضائع، سجل أسعار الموردين التاريخية، ومتابعة فواتير الشراء. |
| `quality` | Quality management | *planned* |  |
| `reporting` | Reporting engine | **active** | تقارير المبيعات والأرباح والمخزون والتدفق النقدي وأعمار الديون، محدودة بفروع المستخدم. |
| `sales` | Sales & Invoicing | **active** | إصدار أوامر البيع وعروض الأسعار، الفواتير الضريبية، المرتجعات، وتتبع مدفوعات العملاء. |
| `scheduling` | Scheduling engine | *planned* |  |
| `storefront` | Tenant Storefront & Omnichannel Ordering | *planned* | موقع إلكتروني ومتجر لكل منشأة مع مصمم صفحات وقوالب (ADR-015). النسخة السابقة متوقفة حتى إعادة البناء. |
| `subscription_billing` | Subscription billing | *planned* |  |
| `supplier_portal` | Supplier portal | *planned* |  |
| `website` | Website | **active** | إدارة بيانات الموقع من أي نشاط: الطلبات الواردة من الموقع والمنتجات المنشورة وخصائص الموقع، مع تشغيل الاستوديو في تبويب مستقل (ADR-015).… |
| `workflow` | Workflow engine | *planned* |  |

## Creative Agency (`agency`, services)

إدارة ملخصات العملاء، مهام، مراجعة تصاميم، وفواتير مشروعات

Turns on: `agency`, `finance`, `operations`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `agency` | Creative, Media & Translation Agency Management | **active** | إدارة المشاريع الإبداعية ومراحل التسليم (Deliverables & Sprints)، سعة وإشغال فريق العمل (Resource Capacity)، تتبع استهلاك ساعات العقود… |

## Agriculture (`agriculture`, projects)

أحواض زراعية، دورات محصولية، أسمدة، وتتبع محاصيل وثروة حيوانية

Turns on: `agriculture`, `inventory`, `operations`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `agriculture` | Commercial Agriculture & Farm Management ERP | **active** | هيكل الأراضي والبيفوتات الزراعية بالمعيار الفداني، تخطيط المواسم والمحاصيل، برامج التسميد والمكافحة وفترات الأمان (PHI)، دورات الري… |

## Banking & Microfinance (`banking`, institutions)

محرك قيود مزدوجة لحظي، قروض، فوائد، ومراقبة غسيل أموال

Turns on: `banking`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `anti_money_laundering` | Anti-money laundering (AML) | *planned* |  |
| `bank_accounts` | Customer and account master, balances | *planned* |  |
| `bank_transactions` | Transaction engine and immutable logs | *planned* |  |
| `banking` | الأنظمة المصرفية والتمويل (Banking & Financial Institutions) | **active** | الحسابات المصرفية الموحدة (CIF)، سجل العمليات اللحظية، محرك الإقراض والتقييم الائتماني (I-Score)، مراقبة غسيل الأموال (AML) وتطبيق… |
| `consolidation` | Multi-entity consolidation | *planned* |  |
| `customer_verification` | Know your customer (KYC) | *planned* |  |
| `loans` | Loans, interest and fees | *planned* |  |
| `regulatory_reporting` | Regulatory reporting | *planned* |  |
| `risk_management` | Risk, exposure and authorization | *planned* |  |
| `settlements` | Payments, settlement and reconciliation | *planned* |  |

## Construction (`construction`, projects)

مقايسات BOQ، مستخلصات، مقاولو باطن، ومعدات ثقيلة

Turns on: `construction`, `inventory`, `operations`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `construction` | Construction & Contracting ERP | **active** | إدارة المشروعات الإنشائية وهيكل تجزئة العمل (WBS)، جداول الكميات (BOQ)، مستخلصات التنفيذ (IPC) ونسب الاستقطاع وحسن التنفيذ، أوامر… |

## Consulting (`consulting`, services)

ساعات قابلة للفوترة، خطابات تكليف، عقود، وتقارير أرباح المشروعات

Turns on: `services`, `finance`, `hr`, `helpdesk`. Adapts: `helpdesk`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `services` | Professional Services | **active** | عروض الأسعار، عقود المشاريع، المطالبات والفوترة الزمنية، ومتابعة تسليمات العملاء. |

## E-commerce (`ecommerce`, commerce)

ربط المتاجر، مزامنة المخزون اللحظية، وتجهيز الشحنات

Turns on: `ecommerce`, `inventory`, `sales`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `ecommerce` | Omnichannel E-commerce & Fulfillment | **active** | ربط ومزامنة منصات المتاجر الرقمية (Shopify, WooCommerce, Amazon, Noon, Salla, Zid)، إدارة مخزون الأمان العازل لمنع الإفراط في البيع، خط… |

## Energy & Utilities (`energy`, projects)

أصول، صيانة تنبؤية، قراءات عدادات، وتصاريح عمل وأمان بيئي

Turns on: `energy`, `inventory`, `operations`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `energy` | Energy & Power Generation Plant ERP | **active** | شجرة الأصول القياسية (ISO 14224 / KKS)، استيعاب بيانات SCADA والحساسات اللحظية (MW/Frequency)، الصيانة التنبؤية، تسوية اتفاقيات شراء… |

## Entertainment (`entertainment`, food_hospitality)

تذاكر، بوابات دخول، بطاقات ألعاب، وتوزيع إيرادات فعاليات

Turns on: `events`, `pos`, `finance`, `operations`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `event_settlements` | Revenue sharing and settlement | *planned* |  |
| `events` | الترفيه والفعاليات والملاهي (Entertainment & Events) | **active** | كتالوج الفعاليات والعروض، حجز المقاعد المدرجة (VIP / Gold)، بوابات الدخول السريع (Turnstiles)، بطاقات الألعاب الإلكترونية (RFID Arcade)،… |
| `gaming_assets` | Gaming equipment and assets | *planned* |  |
| `packages` | Packages and bundles | *planned* |  |
| `season_passes` | Memberships and season passes | *planned* |  |
| `tickets` | Tickets, capacity, scanning, pricing, refunds | *planned* |  |
| `venues` | Event scheduling and venues | *planned* |  |

## Food Mfg (`food`, industry)

وصفات وخلطات، تتبع تشغيلات، صلاحيات، ورقابة سلامة الغذاء

Turns on: `food_manufacturing`, `inventory`, `operations`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `food_manufacturing` | Food & Beverage Process Manufacturing | **active** | إدارة وصفات الخلط والتصنيع المستمر، تتبع التشغيلات العكسي والتصاعدي، نقاط التحكم الحرجة (HACCP)، إدارة تواريخ الصلاحية (FEFO)، واختبارات… |

## Gov & Nonprofits (`government`, institutions)

محاسبة صناديق، موازنات ومخصصات، مناقصات، ومساعدات مستفيدين

Turns on: `government`, `finance`, `operations`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `accountability_reporting` | Audit and accountability reporting | *planned* |  |
| `beneficiaries` | Beneficiaries and citizens | *planned* |  |
| `budgets` | Budgets, controls and multi-year planning | *planned* |  |
| `fund_accounting` | Fund accounting and restricted funds | *planned* |  |
| `government` | القطاع الحكومي والمنظمات غير الهادفة للربح (Government & NGOs) | **active** | محاسبة الصناديق والمخصصات (Fund Accounting)، الارتباط المالي وحجز الموازنة (Encumbrance)، إدارة المنح والجهات المانحة، سجل المستفيدين… |
| `grants` | Grants and funding | *planned* |  |
| `program_performance` | Program and outcome performance | *planned* |  |
| `public_expenditure` | Public expenditure tracking | *planned* |  |
| `public_projects` | Public-sector projects | *planned* |  |
| `tenders` | Procurement compliance and tendering | *planned* |  |

## Gym (`gym`, services)

اشتراكات، بوابات دخول ذكية، حصص تدريب شخصي، وكافيتيريا Gym-POS

Turns on: `gym`, `pos`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `check_in` | Member check-in | *planned* |  |
| `classes` | Classes and trainer scheduling | *planned* |  |
| `gym` | Gym & Fitness Sports Club Management | **active** | إدارة عضويات الجيم واشتراكات اللياقة، بوابات العبور الإلكترونية (Turnstiles)، باقات التدريب الخاص (PT)، جداول الحصص الجماعية، وقياسات… |
| `memberships` | Membership lifecycle | *planned* |  |
| `trainer_commissions` | Trainer commissions | *planned* |  |

## Healthcare (`healthcare`, health)

ملفات مرضى، حجز مواعيد، روشتات، وفواتير تأمين طبي

Turns on: `healthcare_clinic`, `pharmacy`, `finance`, `inventory`, `hr`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `admissions` | Inpatient Admission & Discharge Management | *planned* | أوامر التنويم، تسكين الأسرة، تحويلات الأجنحة، ملخصات الخروج، ومتابعة الإقامة السريرية. |
| `appointments` | Appointment & Scheduling Management | *planned* | حجز المواعيد، جداول الأطباء، منع التعارض، قوائم الانتظار، وإدارة دور الانتظار اللحظي. |
| `beds` | Bed, Ward & Room Management | *planned* | مخطط الأجنحة، حالة الأسرة اللحظية (شاغر، مشغول، تعقيم، صيانة)، وتسعيرة الإقامة اليومية. |
| `consultation` | Consultation & Clinical Workflow | *planned* | توثيق الكشف السريري (SOAP)، الشكوى الحالية، التشخيص (ICD-10)، الوصفات والطلبات الطبية. |
| `electronic_prescriptions` | Electronic prescriptions | *planned* |  |
| `emergency` | Emergency Department & Triage Management | *planned* | استقبال الطوارئ، تصنيف خطورة الحالات (ESI 1-5)، مسارات الإنعاش السريع، وتسكين أسرة الطوارئ. |
| `emr` | Longitudinal Electronic Medical Records (EMR) | *planned* | العلامات الحيوية، التاريخ المرضي والجراحي، الحساسيات الدوائية، الأمراض المزمنة، والمرفقات. |
| `equipment_maintenance` | Medical Equipment & Maintenance Management | *planned* | سجل الأجهزة الطبية، الصيانة الوقائية، شهادات المعايرة الدورية، وتذاكر الأعطال والإصلاح. |
| `facility_management` | Healthcare Facility & Organization Management | *planned* | إدارة المنشآت الطبية، المستشفيات، الفروع، الأقسام، العيادات، وساعات العمل والاعتمادات. |
| `health_insurance` | Insurance & Claims Management | *planned* | شركات التأمين، بوالص المرضى، الموافقات المسبقة، تقديم المطالبات الإلكترونية، والتسوية والرفض. |
| `healthcare_clinic` | Healthcare & Clinic/Hospital ERP | **active** | السجلات الطبية الإلكترونية (EMR)، حجز المواعيد والكشوفات، الروشتات الرقمية (e-Rx)، الفحوصات والتحاليل، وإدارة غرف وأسِرّة التنويم… |
| `hospital_analytics` | Clinical Analytics & Business Intelligence | *planned* | نسبة إشغال الأسرة (BOR)، متوسط مدة الإقامة (ALOS)، إنتاجية الأطباء، ومؤشرات الجودة ومكافحة العدوى. |
| `hospital_pharmacy` | Hospital Pharmacy & Medication Management | *planned* | دليل الأدوية والبدائل، صرف الروشتات الرقمية، تتبع الصلاحيات (FEFO)، وسجل الأدوية المراقبة. |
| `laboratory` | Laboratory Information Management (LIS) | *planned* | دليل الفحوصات، باركود العينات، النتائج المخبرية، المعدلات الطبيعية، والتنبيه بالقيم الحرجة. |
| `medical_accounting` | Accounting & Healthcare Financial Management | *planned* | مراكز تكلفة الأقسام، عمولات وأتعاب الأطباء، إيرادات العيادات والأجنحة، وقيود اليومية التلقائية. |
| `medical_billing` | Billing, Invoicing & Patient Accounts | *planned* | تسعيرة الخدمات، فواتير الكشوفات والإجراءات، حساب نسبة التحمل، سندات القبض، ودفعات المرضى. |
| `medical_staff` | Doctor & Medical Staff Management | *planned* | ملفات الأطباء، التخصصات، التراخيص المهنية، بدلات الكشفية، وجداول المناوبات والورديات. |
| `medical_supplies` | Medical Inventory & Procurement | *planned* | المستلزمات الطبية، أدوات الجراحة، تتبع التشغيلات والصلاحيات، طلبات الشراء، وأرصدة الأقسام. |
| `medical_workforce` | HR & Clinical Workforce Management | *planned* | تراخيص المزاولة الطبية، الامتيازات السريرية، ساعات التعليم الطبي المستمر (CME)، وتبادل الورديات. |
| `nursing` | Nursing Care & Medication Administration | *planned* | خطة الرعاية التمريضية، سجل إعطاء الدواء (MAR)، توازن السوائل، وتقارير تسليم الورديات. |
| `patient_identity` | Patient Registration & Master Patient Index | *planned* | ملفات المرضى، الرقم الطبي الموحد (MRN)، الهوية الوطنية، فحص الازدواجية، ودمج السجلات. |
| `patient_notifications` | Healthcare Notifications & Alerts | *planned* | تذكير المواعيد عبر SMS/واتساب، تنبيهات النتائج المخبرية الحرجة، استدعاء الأطباء، وإشعارات الفواتير. |
| `patient_portal` | Patient Portal & Digital Services | *planned* | حسابات المرضى، حجز المواعيد الذاتي، استعراض نتائج التحاليل والأشعة، وسجل الوصفات والتقارير. |
| `radiology` | Radiology & Imaging Management (RIS/PACS) | *planned* | طلبات الأشعة (X-Ray, CT, MRI, US)، أجهزة التصوير، تقارير أطباء الأشعة، وحالة الفحوصات. |
| `surgery` | Operating Room & Surgery Management | *planned* | جدولة غرف العمليات، الفريق الجراحي والتخدير، قائمة التحقق الجراحية (WHO)، وغرفة الإفاقة. |
| `telemedicine` | Telemedicine & Virtual Consultations | *planned* | جلسات الفيديو المشفرة، غرف الانتظار الافتراضية، التوثيق السريري عن بعد، والروشتات الرقمية. |

## Hotels & Resorts (`hotel`, food_hospitality)

حجوزات، غرف، فواتير إقامة، وتدقيق ليلي ومطاعم فندقية

Turns on: `hospitality`, `restaurant`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `banquet_events` | Banquets, Events & Conference Halls | **active** | حجوزات قاعات الحفلات والاجتماعات، تنظيم برامج الضيافة والبوفيه المفتوح، وتنسيق الفعاليات. |
| `billing_folio` | Guest Folio & Incidentals Room Posting | **active** | إدارة كشوف حسابات النزلاء (Folio)، ترحيل مصاريف المطعم والميني بار والخدمات، وتسوية الفواتير. |
| `hospitality` | Hotel Property Management System (PMS) | **active** | إدارة الغرف الفندقية، الحجوزات والتسكين (Check-in/Check-out)، فواتير النزلاء (Folio)، مهام التدبير المنزلي (Housekeeping)، والتدقيق… |
| `hotel_pms` | Hotel Property Management System | **active** | خريطة الغرف التفاعلية، الحجوزات، تسكين ومغادرة النزلاء (Check-in/Check-out)، وتتبع حالات الغرف. |
| `housekeeping` | Hotel Housekeeping & Cleaning Operations | **active** | إدارة مهام التدبير المنزلي، تنظيف الغرف بعد المغادرة أو التسكين، وتعيين الفرق وجدولتها. |
| `night_audit` | Night Audit & Hospitality Metrics | **active** | التدقيق الليلي الدوري، احتساب متوسط السعر اليومي (ADR)، العائد على الغرفة المتاحة (RevPAR)، والإقفال المحاسبي اليومي. |
| `room_rates` | Room rates by season | *planned* |  |

## Insurance (`insurance`, institutions)

وثائق، تسعير اكتواري، مطالبات، واحتياطيات فنية وإعادة تأمين

Turns on: `insurance`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `agent_commissions` | Broker and agent commissions | *planned* |  |
| `claims` | Claims processing and reserves | *planned* |  |
| `fraud_detection` | Fraud detection and risk scoring | *planned* |  |
| `insurance` | إدارة التأمين وإعادة التأمين (Insurance ERP) | **active** | وثائق التأمين (السيارات، الطبي، الممتلكات)، احتساب الأقساط الاكتوارية، مطالبات الحوادث (FNOL) والمعاينات، مخصصات IFRS 17، واتفاقيات… |
| `insurance_products` | Products and coverage | *planned* |  |
| `insurance_reporting` | Insurance regulatory reporting | *planned* |  |
| `policies` | Policies, underwriting, renewals | *planned* |  |
| `policyholder_portal` | Policyholder portal | *planned* |  |
| `premiums` | Premium rating, billing and collection | *planned* |  |
| `reinsurance` | Reinsurance | *planned* |  |

## Law Firm (`legal`, services)

إدارة القضايا، مواعيد الجلسات، وسجلات أموال العملاء وحسابات الأمانة

Turns on: `law`, `finance`, `hr`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `law` | Law Firm & Legal Practice Management | **active** | إدارة القضايا والملفات القضائية، الأجندة وجلسات المحاكم، فحص تعارض المصالح، الساعات المهنية المحتسبة، حسابات أمانات العملاء المفرزة،… |

## Logistics (`logistics`, logistics)

بوالص شحن، تتبع مسارات، إدارة أساطيل، وتكاليف وقود

Turns on: `logistics`, `finance`, `operations`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `logistics` | Logistics & Fleet Transportation | **active** | تتبع دورة حياة الشحنات وبوالص الشحن (AWB / BoL)، تخطيط المسارات وإدارة أساطيل المركبات، امتثال السائقين، تسعير الشحن والرسوم التكميلية،… |

## Field Service (`maintenance`, services)

أوامر شغل، توجيه فنيين، قطع غيار متنقلة، وتوقيعات عملاء

Turns on: `field_service`, `inventory`, `operations`, `finance`, `helpdesk`. Adapts: `helpdesk`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `field_service` | Field Service & Maintenance Management | **active** | أوامر العمل الميدانية وبلاغات الأعطال، تتبع الفنيين ومواقع العمل (GPS Dispatch)، مخزون سيارات الصيانة (Van Inventory)، اتفاقيات مستوى… |

## Manufacturing (`manufacturing`, industry)

شجرة منتج BOM، مراكز تشغيل، تخطيط مواد MRP، وتكاليف إنتاج

Turns on: `manufacturing`, `inventory`, `operations`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `bill_of_materials` | Bill of materials | *planned* |  |
| `manufacturing` | Discrete Manufacturing & Assembly | **active** | إدارة شجرة المنتج متعددة المستويات (BOM)، مراكز العمل ومسارات التشغيل، تخطيط الاحتياجات (MRP)، أوامر الإنتاج، الرقابة على صالة التصنيع،… |
| `material_planning` | Material requirements planning (MRP) | *planned* |  |
| `production` | Production and work orders | *planned* |  |

## Oil & Gas (`petroleum`, projects)

آبار، إنتاج يومي، محاسبة مشاركات نفطية، وأمان تشغيلي

Turns on: `oil_gas`, `operations`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `contractors` | Contractors and service companies | *planned* |  |
| `custody_transfer` | Hydrocarbon inventory and custody transfer | *planned* |  |
| `drilling` | Drilling and field activity | *planned* |  |
| `emissions` | Environmental and emissions reporting | *planned* |  |
| `field_logistics` | Field procurement and logistics | *planned* |  |
| `field_maintenance` | Maintenance and reliability | *planned* |  |
| `health_safety_environment` | HSE, incidents and permit-to-work | *planned* |  |
| `hydrocarbon_production` | Production volumes and cost allocation | *planned* |  |
| `joint_ventures` | Joint venture cost allocation | *planned* |  |
| `oil_gas` | عمليات البترول والغاز واستخراج الطاقة (Oil & Gas ERP) | **active** | شجرة الآبار والمكامن البترولية، تقارير الإنتاج اليومي وتخصيص الهيدروكربونات، تقرير الحفر اليومي (DDR / IADC)، مستودعات صهاريج الخام… |
| `spare_parts` | Equipment and spare parts | *planned* |  |
| `wells` | Fields, sites, wells and assets | *planned* |  |

## Pharma Mfg (`pharmaceuticals`, industry)

سجلات تشغيل إلكترونية، معايير GMP، ورقابة جودة وتتبع حرج

Turns on: `pharma_manufacturing`, `inventory`, `operations`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `pharma_manufacturing` | Pharmaceutical & Chemical GMP Manufacturing | **active** | سجلات التشغيل الإلكترونية (EBR)، الإفراج الدوائي QP Batch Release، إدارة الحيود والإجراءات التصحيحية (CAPA)، التوقيعات الرقمية 21 CFR… |

## Pharmacy (`pharmacy`, health)

دواء، تشغيلات، تواريخ صلاحية، رقابة صرف وتأمين صحي

Turns on: `pharmacy`, `batches`, `inventory`, `pos`, `finance`. Adapts: `inventory`, `pos`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `batches` | Batches and expiry (FEFO) | **active** | التشغيلات وتواريخ الصلاحية لكل صنف وفرع؛ البيع من الأقرب انتهاءً (FEFO)، ومنع بيع المنتهي والمحجوز، وتتبّع أين ذهبت كل تشغيلة. |
| `drug_interactions` | Drug interaction checking | *planned* |  |
| `drug_master` | Drug master | *planned* |  |
| `insurance_claims` | Insurance claims | *planned* |  |
| `pharmacy` | Pharmacy & Medication Dispensing | **active** | منظومة صيدلانية متكاملة: دليل الأدوية بالاسم العلمي والتجاري، تتبع الصلاحيات والتشغيلات (FEFO)، صرف الروشتات، التأمين الطبي، وسجل… |
| `prescriptions` | Prescriptions | *planned* |  |
| `recalls` | Recalled and quarantined medication | *planned* |  |

## Print & Packaging (`printing`, industry)

تذاكر تشغيل، مونتاج، استهلاك أحبار وورق، وهالك تجهيز

Turns on: `printing`, `inventory`, `operations`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `printing` | Printing & Packaging ERP | **active** | تذاكر الشغل والطباعة Job Dockets، تخطيط المونتاج وتوزيع الصفحات Imposition، جدولة ماكينات الطباعة وتغيير الأحبار، تكلفة ساعات التشغيل… |

## Real Estate (`property`, projects)

وحدات، عقود إيجار، تحصيل شيكات، وصيانة وإيرادات صافية

Turns on: `real_estate`, `finance`, `operations`, `helpdesk`. Adapts: `helpdesk`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `real_estate` | Real Estate & Property Management ERP | **active** | محفظة العقارات والوحدات السكنية والتجارية، مصفوفة الشواغر والإشغال، دورة عقود الإيجار، حافظة الشيكات المؤجلة (PDC)، رسوم الصيانة… |

## Restaurant (`restaurant`, food_hospitality)

إدارة صالة، طاولات، وشاشات مطبخ KDS تفاعلية وRestaurant-POS

Turns on: `restaurant`, `pos`, `inventory`, `finance`. Adapts: `pos`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `delivery` | Delivery platforms | *planned* |  |
| `kitchen_display` | Kitchen Display System | **active** | شاشات تحضير الطلبات اللحظية لطهاة المطبخ والبار، ترتيب التذاكر حسب الأولوية، ومتابعة أوقات الإعداد. |
| `menu` | Menu and modifiers | *planned* |  |
| `recipes` | Recipes and ingredient BOM | *planned* |  |
| `restaurant` | Restaurant & Dining Hall | **active** | مخطط صالة الطعام، إدارة وحجز الطاولات، تتبع الجلسات وأوقات الانتظار، وإجمالي حسابات الضيوف الجارية. |
| `tables` | Table management and floor plan | *planned* |  |
| `waste` | Food waste and spoilage | *planned* |  |

## Retail (`retail`, commerce)

سوبرماركت، معارض، ومخازن تجارية وRetail-POS مع موازين وباركود

Turns on: `pos`, `inventory`, `sales`, `finance`, `hr`. Adapts: `pos`.

## Salon & Spa (`salon`, services)

مواعيد مصففين، باقات خدمات، وعمولات موظفين ومستهلكات

Turns on: `salon`, `pos`, `finance`, `helpdesk`. Adapts: `helpdesk`, `pos`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `salon` | Salon, Spa & Personal Care Management | **active** | دليل الخدمات وفترات التنفيذ (Duration Matrix)، أجندة مصففي الشعر والغرف، تتبع تركيبات الصبغة وسجل العميلات، محرك عمولات المصففين،… |

## School (`school`, education)

شؤون الطلاب، أقساط، وإيصالات رسوم مدرسية وحافلات نقل

Turns on: `school`, `finance`, `hr`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `enrollment` | Admissions and enrollment | *planned* |  |
| `exams` | Examinations and grading | *planned* |  |
| `school` | School & Education Management | **active** | شؤون وقيد الطلاب، إدارة المراحل والفصول، تحصيل الأقساط والمصروفات المجدولة، وإصدار إيصالات السداد الإلكترونية. |
| `timetable` | Classes and timetable | *planned* |  |
| `transcripts` | Student transcripts | *planned* |  |
| `tuition` | Tuition fees and installments | *planned* |  |

## Travel Agency (`travel`, food_hospitality)

برامج سياحية، حجوزات طيران وفنادق، وفواتير موحدة للمجموعات

Turns on: `travel`, `sales`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `travel` | Travel & Tourism Agency Management | **active** | بناء وتصميم البرامج السياحية (Itinerary Builder)، حجوزات الطيران والفنادق ومنافست الركاب، محرك العمولات والهوامش، وخزينة الجوازات… |

## 3PL WMS (`warehousing`, logistics)

مستودعات متعددة العملاء، استلام، وتوزيع حسب مواقع التخزين

Turns on: `wms`, `inventory`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `wms` | 3PL & Warehouse Management System | **active** | إدارة مستودعات العملاء المتعددين وتتبع ملكية المخزون لكل عميل، المواقع التخزينية المرمزة (Zone-Aisle-Rack-Shelf-Bin)، خوارزميات التخزين… |

## Wholesale (`wholesale`, commerce)

أسعار كميات، قوائم أسعار عملاء، تسعير حسب الحجم والخصومات

Turns on: `wholesale`, `inventory`, `sales`, `finance`.

| Module | Name | Status | What it does |
|---|---|---|---|
| `wholesale` | Wholesale & Bulk Distribution | **active** | سلالم التسعير الكمي المتدرج، قوائم أسعار العملاء المتعاقد عليها، قيود الائتمان وسقوف المديونية، تكلفة الاستيراد المفرغة (Landed Cost)،… |

## Platform modules (`app/platform/`)

| Module | Name | What it does |
|---|---|---|
| `automation_worker` | Background Automation & Cron Worker | جدولة وأتمتة العمليات اليومية: إغلاق الورديات التلقائي منتصف الليل، متابعة اشتراكات المستأجرين، وإنشاء التقارير والتنبيهات الدورية. |
| `community` | Community modules | وحدات مجتمع المطورين المثبتة من ملف (.mzm): سجلاتها وشاشاتها وصلاحياتها (ADR-007). |
| `core` | Base & Core System | المحرك الأساسي للنظام، إدارة المستأجرين، المستخدمين، الصلاحيات، الإعدادات، وسجل التدقيق الرقابي. |
| `customization` | Tenant customization |  |
| `i18n` | Internationalization & Multi-language | التبديل بين العربية والإنجليزية مع التكييف الديناميكي لاتجاه الواجهة (RTL / LTR) والخطوط. |
| `marketplace` | Module marketplace and self-configuration |  |
| `site` | Site | باني المواقع: صفحات الموقع ومسوداتها ونشرها ومراجعاتها (ADR-015، الخطوة S2). |
| `themes` | Themes | مظهر المنشأة: ألوان وخطوط وحركة، من ميزان ومن نشاطها ومن حزم المطورين الموقّعة (ADR-010). |

## Connectors (`app/integrations/`)

| Module | Name | What it does |
|---|---|---|
| `fawry` | Fawry payments |  |
| `instapay` | InstaPay payments |  |
| `pos_hardware` | POS Hardware & Thermal Printing | إدارة أجهزة نقاط البيع، قارئ الباركود اللاسلكي والسلكي، طابعات الفواتير الحرارية 80mm و 58mm، ودرج النقدية. |
| `webhooks` | Integration engine and webhooks |  |
| `whatsapp_gateway` | WhatsApp Business & Digital Receipt Dispatch | إرسال إيصالات رقمية وفواتير تلقائياً إلى WhatsApp العملاء عند إتمام البيع أو طلب المتجر، مع قوالب رسائل قابلة للتخصيص. |

## From outside developers

Community modules, theme packs and whole activities from developers are installed per workspace
from signed packages (ADR-007, ADR-010); they aren't in this catalogue. See `dev.allmizan.live/docs`.
