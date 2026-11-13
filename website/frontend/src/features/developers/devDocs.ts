/**
 * The developer documentation (ADR-007 D6), at dev.allmizan.live/docs. Keep it true to the code:
 * the manifest and entity rules are app/framework/manifest.py, the API is
 * app/platform/community/ext_api.py, webhooks app/platform/community/events.py, the CLI sdk/python.
 */
import type { DocSection } from "@app/features/docs/docsData";
import { EN } from "./devDocs.en";

import { DOCS_UPDATED as UPDATED, EXT_API as EXT, SDK_URL } from "./sdk";

export { SDK_WHEEL } from "./sdk";

const THEME = `{
  "id": "acme.sunrise",
  "name": "شروق",
  "name_en": "Sunrise",
  "version": "1.0.0",
  "kind": "theme",
  "description": "برتقالي دافئ وحواف دائرية وحركة هادئة.",
  "colors": {
    "light": {"background": "#FAF6F0", "foreground": "#262321", "primary": "oklch(0.55 0.17 40)", "...": "..."},
    "dark":  {"background": "#270F16", "foreground": "#FAF6F0", "primary": "oklch(0.72 0.15 50)", "...": "..."}
  },
  "fonts": {
    "body": "Sunrise Sans",
    "files": [{"family": "Sunrise Sans", "src": "assets/sunrise-sans.woff2", "weight": "100 900"}]
  },
  "radius": "1.25rem",
  "shadows": "raised",
  "motion": "reduced"
}`;

const ACTIVITY_LAYOUT = `acme.laundry/
  manifest.json          kind "activity": family, modules, menus, roles, terms, theme
  modules/
    acme.laundry_orders/ its own modules (manifest.json + entities/)
  variants/
    pos/variant.json     how it adapts Mizan's POS: extra fields, terms, settings
  themes/
    fresh/theme.json     its themes
  seed/orders.json       demo records`;

const ACTIVITY_MANIFEST = `{
  "id": "acme.laundry",
  "name": "مغسلة",
  "name_en": "Laundry",
  "version": "1.0.0",
  "kind": "activity",
  "family": "services",
  "modules": ["pos", "inventory", "sales", "finance", "hr", "acme.laundry_orders"],
  "optional": [],
  "terms": {"item": "قطعة"},
  "home": "/pos",
  "theme": "acme.laundry_fresh",
  "positions": [{"code": "counter_clerk", "name": "موظف الاستقبال", "name_en": "Counter clerk", "suggested_roles": ["cashier"]}],
  "menu": [{"id": "orders", "label": "الطلبات", "items": [
    {"screen": "acme.laundry_orders/order", "label": "طلبات العملاء"},
    {"screen": "pos.pos", "label": "الكاشير"}
  ]}],
  "dashboard": ["pos.recent_sales"],
  "roles": {"cashier": {"home": "pos.pos", "menu": [], "dashboard": ["pos.recent_sales"]}}
}`;

const AR: DocSection[] = [
  {
    id: "start",
    title: "البداية",
    titleEn: "Getting started",
    items: [
      {
        slug: "introduction",
        title: "ما هي وحدات المطورين؟",
        titleEn: "What community modules are",
        description: "ماذا تستطيع وحدتك أن تضيف إلى ميزان اليوم، وكيف تصل إلى المنشآت.",
        category: "البداية",
        lastUpdated: UPDATED,
        content: {
          overview:
            "وحدة المطور تضيف إلى مساحة عمل في ميزان سجلات جديدة (كيانات) بشاشاتها: قائمة وبحث ونموذج إضافة وتعديل، وصلاحيات يمنحها صاحب المنشأة لأدوار موظفيه، وتظهر في قائمة التطبيق تحت «وحدات إضافية». وإن احتاجت منطقًا خاصًا فإنها تتصل بخادمك أنت: يقرأ ويكتب عبر واجهة الربط (/ext/v1) ويستقبل إشعارات موقّعة عند الأحداث.",
          sections: [
            {
              id: "declarative",
              title: "وحدات وصفية الآن",
              body:
                "الوحدة اليوم ملفات JSON فقط: ملف التعريف manifest.json وملف لكل كيان في entities/. لا يُشغَّل أي كود من خارج ميزان داخل خوادمه؛ هذا ما يجعل تثبيت وحدتك آمنًا لصاحب المنشأة. الكود الخاص بك يعمل على خادمك، ويصل إلى بيانات المنشأة فقط بما وافق عليه صاحبها (النطاقات).\n\nوحدات بكود يعمل داخل ميزان (في حاويات معزولة) ستأتي حين تنتقل المنصة إلى خوادمها الخاصة.",
              callout: { type: "note", text: "طريقتان للوصول إلى المنشآت: النشر في السوق (يراجعه فريق ميزان ثم تثبّته أي منشأة من متجرها)، أو إعطاء صاحب المنشأة الملف الموقّع (.mzm) مباشرة. القوائم المدفوعة لاحقًا؛ الآن كلها مجانية." },
            },
            {
              id: "pieces",
              title: "الأجزاء",
              body:
                "• بوابة المطورين (dev.allmizan.live/portal): حسابك وفريقك ومفاتيح التوقيع ورموز سطر الأوامر.\n• أداة mizan (حزمة mizan-sdk لبايثون): إنشاء وحدة وفحصها وتوقيعها.\n• ملف الحزمة .mzm: يرفعه صاحب المنشأة من «مركز الوحدات ← وحدات المطورين ← تثبيت من ملف».\n• واجهة الربط /ext/v1 والإشعارات (Webhooks) لخادمك.",
            },
          ],
        },
      },
      {
        slug: "quickstart",
        title: "البدء السريع",
        titleEn: "Quickstart",
        description: "من حساب جديد إلى وحدة مثبتة في مساحة عمل في دقائق.",
        category: "البداية",
        lastUpdated: UPDATED,
        content: {
          overview: "تحتاج بايثون 3.10 أو أحدث. الخطوات: حساب وفريق في البوابة، ثم الأداة، ثم الوحدة.",
          sections: [
            {
              id: "account",
              title: "1. الحساب والفريق",
              body:
                "أنشئ حسابًا في البوابة، ثم فريقًا. معرّف الفريق (مثل acme) هو الجزء الأول من معرّف كل وحداتك (acme.visits) ولا يتغير. ثم أنشئ من «رموز سطر الأوامر» رمزًا لجهازك.",
            },
            {
              id: "install",
              title: "2. تثبيت الأداة وتسجيل الدخول",
              body: "ثبّت mizan-sdk ثم سجّل الدخول بالرمز (يبدأ بـ mzd_).",
              codeBlock: { language: "bash", code: `pip install ${SDK_URL}\nmizan login\nmizan whoami` },
            },
            {
              id: "module",
              title: "3. الوحدة",
              body:
                "أنشئ وحدة من القالب، عدّلها، وافحصها بنفس قواعد المنصة. ثم أنشئ مفتاح توقيع لفريقك (يُسجَّل وتُحفظ شهادته تلقائيًا) ووقّع الحزمة.",
              codeBlock: {
                language: "bash",
                code: "mizan module new acme.visits\nmizan check acme.visits\nmizan keys new --team acme\nmizan package acme.visits      # acme.visits-0.1.0.mzm",
              },
            },
            {
              id: "try",
              title: "4. التثبيت في مساحة عمل",
              body:
                "في مساحة عمل تملكها: مركز الوحدات ← وحدات المطورين ← «تثبيت من ملف»، اختر الحزمة، راجع ما تصل إليه ووافق. تظهر شاشاتها في القائمة تحت «وحدات إضافية».",
              callout: { type: "tip", text: "أنشئ مساحة عمل تجريبية من allmizan.live/signup لتجربة وحداتك دون لمس بيانات حقيقية." },
            },
          ],
        },
      },
    ],
  },
  {
    id: "build",
    title: "البناء",
    titleEn: "Building",
    items: [
      {
        slug: "manifest",
        title: "ملف التعريف manifest.json",
        titleEn: "The manifest",
        description: "معرّف الوحدة وإصدارها وكياناتها وصلاحياتها وقائمتها ونطاقاتها.",
        category: "البناء",
        lastUpdated: UPDATED,
        content: {
          overview: "يقع في جذر الحزمة. هذه كل حقوله؛ ما ليس هنا مرفوض.",
          sections: [
            {
              id: "example",
              title: "مثال كامل",
              body: "",
              codeBlock: {
                language: "json",
                filename: "manifest.json",
                code: `{
  "id": "acme.visits",
  "name": "الزيارات",
  "name_en": "Visits",
  "version": "1.0.0",
  "kind": "community",
  "icon": "CalendarCheck",
  "description": "متابعة زيارات العملاء.",
  "entities": ["visit"],
  "permissions": [
    {"id": "acme.visits.view", "name": "عرض الزيارات", "name_en": "View visits"}
  ],
  "menu": [
    {"entity": "visit", "label": "الزيارات", "icon": "CalendarCheck", "permission": "acme.visits.view"}
  ],
  "scopes": ["customers:read", "events:sale.confirmed"],
  "webhooks": {"url": "https://acme.example/mizan", "events": ["sale.confirmed"]}
}`,
              },
            },
            {
              id: "rules",
              title: "القواعد",
              body:
                "• id: «<فريقك>.<الوحدة>» بحروف إنجليزية صغيرة وأرقام و _ ؛ الجزء الأول يجب أن يطابق معرّف الفريق صاحب مفتاح التوقيع.\n• version: MAJOR.MINOR.PATCH. رفع الإصدار ثم التثبيت فوق القديم يحدّث الوحدة ويُبقي سجلاتها.\n• kind: دائمًا \"community\".\n• icon: اسم أيقونة من مكتبة lucide (مثل CalendarCheck).\n• entities: حتى 20 كيانًا، لكل منها ملف entities/<id>.json.\n• permissions: معرّفاتها تبدأ بمعرّف الوحدة. عنصر القائمة الذي يذكر صلاحية لا يراه إلا من يملكها؛ بدونها يراه كل مستخدمي المنشأة. مدير المنشأة يملكها كلها، وصاحب المنشأة يمنحها للأدوار الأخرى من شاشة الأدوار.\n• menu: عنصر لكل شاشة كيان تريد ظهورها في القائمة.\n• scopes و webhooks: انظر «النطاقات» و«الإشعارات».\n• ممنوع: router و models و frontend و category و activity.",
            },
            {
              id: "package",
              title: "محتوى الحزمة",
              body:
                "manifest.json و README.md و CHANGELOG.md في الجذر، و entities/ و i18n/ و assets/ (ملفات json و png و svg و webp و jpg و md و txt). حجم الحزمة حتى 4 ميجابايت.",
            },
          ],
        },
      },
      {
        slug: "entities",
        title: "الكيانات والشاشات",
        titleEn: "Entities and screens",
        description: "الحقول وأنواعها، الربط بسجلات المنشأة، أعمدة القائمة وأقسام النموذج.",
        category: "البناء",
        lastUpdated: UPDATED,
        content: {
          overview:
            "الكيان نوع سجل جديد. يرسم ميزان شاشته من تعريفه: جدول بالأعمدة التي تختارها مع بحث وصفحات، ونموذج إضافة وتعديل بأقسامك، وحذف. تُتحقق القيم على الخادم في كل مرة (من الشاشة أو من واجهة الربط).",
          sections: [
            {
              id: "example",
              title: "مثال",
              body: "",
              codeBlock: {
                language: "json",
                filename: "entities/visit.json",
                code: `{
  "id": "visit",
  "name": "زيارة",
  "name_en": "Visit",
  "title": "customer",
  "fields": [
    {"key": "customer", "type": "reference", "to": "customers", "label": "العميل", "required": true},
    {"key": "on", "type": "date", "label": "التاريخ"},
    {"key": "fee", "type": "money", "label": "الرسوم"},
    {"key": "state", "type": "select", "options": ["مجدولة", "تمت"], "label": "الحالة"}
  ],
  "list": ["on", "customer", "state"],
  "form": {"sections": [{"id": "main", "label": "الزيارة", "fields": ["customer", "on", "fee", "state"]}]}
}`,
              },
            },
            {
              id: "types",
              title: "أنواع الحقول",
              body:
                "• text: نص (حتى 2000 حرف).\n• number: رقم.\n• money: مبلغ بقرشين عشريين (يُخزَّن نصًا مثل \"150.50\").\n• date: تاريخ YYYY-MM-DD.\n• boolean: نعم/لا.\n• select: واحد من options.\n• reference: معرّف سجل آخر؛ to إما أحد كيانات وحدتك، أو customers أو suppliers أو products أو employees أو branches (ويحتاج نطاق القراءة المقابل، مثل customers:read). يتأكد ميزان أن السجل موجود في نفس المنشأة.\n\nحتى 60 حقلًا لكل كيان. required يجعل الحقل مطلوبًا.",
            },
            {
              id: "screens",
              title: "العنوان والقائمة والنموذج",
              body:
                "• title: الحقل الذي يمثّل السجل حين يُشار إليه (في قوائم الاختيار والجداول). إن كان هو نفسه مرجعًا يُعرض اسم السجل المشار إليه.\n• list: أعمدة الجدول (بدونها أول أربعة حقول).\n• form.sections: أقسام النموذج وترتيب حقولها (بدونها قسم واحد بكل الحقول).\n• البحث يشمل حقول النص والاختيار.",
            },
          ],
        },
      },
      {
        slug: "scopes",
        title: "النطاقات (ما تصل إليه الوحدة)",
        titleEn: "Scopes",
        description: "ما يوافق عليه صاحب المنشأة قبل التثبيت، وما يسمح به كل نطاق.",
        category: "البناء",
        lastUpdated: UPDATED,
        content: {
          overview:
            "سجلات وحدتك لا تحتاج نطاقًا. أي شيء آخر من بيانات المنشأة تطلبه في scopes، ويعرضه ميزان على صاحب المنشأة بكلمات واضحة قبل التثبيت؛ وعند التحديث تُعلَّم النطاقات الجديدة. لا تثبيت دون الموافقة عليها كلها.",
          sections: [
            {
              id: "data",
              title: "نطاقات البيانات",
              body:
                "• customers:read — قراءة العملاء\n• customers:write — إضافة العملاء\n• suppliers:read — قراءة الموردين\n• products:read — قراءة الأصناف والأسعار\n• stock:read — قراءة أرصدة المخزون\n• sales:read — قراءة فواتير المبيعات وبنودها\n• employees:read — قراءة بيانات الموظفين\n• branches:read — قراءة الفروع",
            },
            {
              id: "events",
              title: "نطاقات الأحداث",
              body:
                "• events:sale.confirmed — عند تأكيد فاتورة بيع\n• events:sale.returned — عند مرتجع مبيعات (كلي أو جزئي)\n• events:customer.created — عند إضافة عميل\n• events:product.updated — عند تعديل صنف\n\nrecord.created و record.updated (سجلات وحدتك) لا تحتاج نطاقًا.",
              callout: { type: "tip", text: "اطلب أقل ما تحتاجه: كل نطاق إضافي سبب لتردد صاحب المنشأة في التثبيت." },
            },
          ],
        },
      },
      {
        slug: "themes",
        title: "حزم المظاهر",
        titleEn: "Theme packs",
        description: "ألوان وخطوط وحواف وظلال وحركة لمساحة عمل كاملة.",
        category: "البناء",
        lastUpdated: UPDATED,
        content: {
          overview:
            "حزمة المظهر تغيّر شكل ميزان كله في مساحة عمل: ألوانه في الوضعين الفاتح والداكن، وخطوطه، واستدارة الحواف، والظلال، والحركة. يثبّتها مدير المنشأة ويجعلها مظهرها؛ فيراها كل من فيها، والمستندات المطبوعة كذلك. المظهر بلا كود ولا يصل إلى أي بيانات.",
          sections: [
            { id: "example", title: "manifest.json", body: "حزمة المظهر ملف manifest.json نوعه \"theme\"، وملفات خطوطه في assets/. ابدأ من مظهر ميزان نفسه بالأمر mizan theme new acme.sunrise.", codeBlock: { language: "json", filename: "manifest.json", code: THEME } },
            {
              id: "colors",
              title: "الألوان",
              body:
                "colors.light و colors.dark تضبطان رموز التصميم في التطبيق. المطلوب: background و foreground و card و card-foreground و primary و primary-foreground و secondary و secondary-foreground و muted و muted-foreground و accent و accent-foreground و border و input و ring و sidebar و sidebar-foreground و sidebar-primary و sidebar-primary-foreground و sidebar-accent و sidebar-accent-foreground و sidebar-border و sidebar-ring. واختياريًا: popover و destructive و success و warning (ولكل منها -foreground) و chart-1 … chart-5.\n\nالقيم #hex أو rgb() أو oklch(). يجب أن يبقى النص مقروءًا: تباين 4.5 للنص على الخلفية وعلى البطاقة وعلى الشريط الجانبي، و3 للباقي. يخبرك mizan check بأي زوج لا يكفي.",
            },
            {
              id: "fonts",
              title: "الخطوط والحواف والظلال والحركة",
              body:
                "• fonts.body و fonts.display و fonts.mono: أسماء الخطوط. ضع ملفاتها في assets/ واذكرها في fonts.files ({family, src, weight: \"400\" أو مدى \"100 900\", style})؛ يقدّمها ميزان بنفسه فتعمل المظاهر على الخوادم المحلية دون إنترنت. خط بلا ملفات يجب أن يكون موجودًا على الجهاز.\n• radius: استدارة الحواف الأساسية، مثل 0.75rem.\n• shadows: flat أو soft أو raised.\n• motion: full أو reduced أو none (للكاشير المزدحم ولسهولة الوصول).\n• density: comfortable أو compact، افتراضي يستطيع كل مستخدم تغييره على جهازه.",
              callout: { type: "tip", text: "تطبيق ميزان عربي غالبًا: اختر خطوطًا فيها الحروف العربية، وإلا ظهر النص العربي بالخط الافتراضي." },
            },
            { id: "ship", title: "توزيع المظهر", body: "mizan check و mizan package كما للوحدات؛ ويثبّته صاحب المنشأة من مركز الوحدات ← المظاهر ← تثبيت مظهر من ملف، ثم يختاره. التثبيت لا يغيّر المظهر الحالي. وللأنشطة أيضًا مظاهرها الخاصة (activities/<activity>/themes/)." },
          ],
        },
      },
      {
        slug: "activities",
        title: "الأنشطة التجارية",
        titleEn: "Business activities",
        description: "نشاط كامل لميزان: وحدات وتكييفات وقوائم وأدوار ومظاهر وبيانات تجريبية.",
        category: "البناء",
        lastUpdated: UPDATED,
        content: {
          overview:
            "كل منشأة في ميزان تعمل على نشاط: تجزئة، صيدلية، مطعم… يحدد النشاط الوحدات التي تحصل عليها المنشأة، وكيف تتكيف مع المهنة، ومصطلحاتها، وقوائم كل دور ولوحته، ووظائفها، ومظهرها، وبياناتها التجريبية. أنشطة ميزان نفسها مبنية بهذه الطريقة تمامًا، مجلد لكل نشاط، وتستطيع بناء نشاط لمهنة لا يغطيها ميزان بعد بالإطار نفسه.",
          sections: [
            { id: "layout", title: "الهيكل", body: "أنشئ واحدًا بالأمر mizan activity new acme.laundry: نشاط صغير مكتمل تبدأ منه.", codeBlock: { language: "text", code: ACTIVITY_LAYOUT } },
            { id: "manifest", title: "manifest.json", body: "", codeBlock: { language: "json", filename: "manifest.json", code: ACTIVITY_MANIFEST } },
            {
              id: "rules",
              title: "ما يحتويه",
              body:
                "• family: general أو commerce أو food_hospitality أو health أو education أو services أو logistics أو industry أو projects أو institutions.\n• modules و optional: وحدات ميزان (pos و inventory و sales و finance و hr …) ووحداته الخاصة (<الفريق>.<الوحدة>، كل منها وحدة مطور في modules/).\n• menu و dashboard و roles: مجموعات قوائم من الشاشات. شاشات ميزان بالصيغة <الوحدة>.<الشاشة> (pos.pos و inventory.products)، وشاشات كياناتك <الوحدة>/<الكيان>. اللوحات تذكر عناصرها (pos.recent_sales). و roles تعطي كل دور (cashier …) شاشته الرئيسية وقائمته ولوحته.\n• terms: مصطلحات المهنة (\"item\": \"قطعة\").\n• positions: المسميات الوظيفية والأدوار المقترحة لها.\n• theme: أحد مظاهره (themes/) أو مظاهر ميزان.\n• variants/<الوحدة>/variant.json: حقول إضافية على سجلات ميزان (fields.sale و fields.product …) ومصطلحات وإعدادات افتراضية.\n• seed/*.json: سجلات تجريبية لكياناته.\n\nيتحقق mizan check من الشكل، ويتحقق ميزان من كل مرجع (الوحدات والشاشات واللوحات والسجلات والمظاهر) عند استلام الحزمة.",
              callout: { type: "note", text: "حزم الأنشطة وصفية مثل وحدات المطورين: لا كود في التكييفات بعد (أنشطة ميزان تضيف قواعدها في hooks.py). انشره (mizan publish)؛ وبعد أن يقبله فريق ميزان يستطيع أصحاب المنشآت تحويل منشأة قائمة إليه من لوحة المالك (ويوافق الفريق على كل تحويل أيضًا). تُثبَّت وحداته بالصلاحيات التي تعلنها، وتُثبَّت مظاهره، وتسري قوائمه ومصطلحاته وتكييفاته ووظائفه. التحديثات المقبولة تصل إلى كل منشأة تشغّله: تنضم الوحدات الجديدة ولا يُزال شيء. لا تُضاف بيانات seed إلى منشأة عاملة، ولا يمكن بعد إنشاء منشأة جديدة من نشاط مطور." },
            },
          ],
        },
      },
    ],
  },
  {
    id: "connect",
    title: "الربط بخادمك",
    titleEn: "Your server",
    items: [
      {
        slug: "api",
        title: "واجهة الربط /ext/v1",
        titleEn: "The extension API",
        description: "رمز التثبيت، السجلات، وبيانات المنشأة بحسب النطاقات.",
        category: "الربط بخادمك",
        lastUpdated: UPDATED,
        content: {
          overview: `كل تثبيت لوحدتك في منشأة له رمز (يبدأ بـ mzx_) يعطيك إياه صاحبها من «مركز الوحدات ← وحدات المطورين ← رمز الربط». الرمز يرى تلك المنشأة وحدها، وبالنطاقات التي وافق عليها فقط. العنوان: ${EXT}`,
          sections: [
            {
              id: "auth",
              title: "المصادقة والحدود",
              body:
                "أرسل الرمز في ترويسة Authorization. حتى 240 طلبًا في الدقيقة. إنشاء رمز جديد يوقف القديم فورًا، وإزالة الوحدة توقفه كذلك.\n\nالأخطاء: 401 رمز مفقود أو ملغى، 403 نطاق غير ممنوح أو منشأة موقوفة، 404 غير موجود، 422 قيمة غير صالحة (الرسالة في detail).",
              codeBlock: { language: "bash", code: `curl ${EXT}/me -H "Authorization: Bearer mzx_..."` },
            },
            {
              id: "records",
              title: "سجلات وحدتك",
              body:
                "• GET /records/{entity}?q=&page= — قائمة (50 في الصفحة): {items, total, page, pages, labels}\n• POST /records/{entity} — إضافة (القيم بمفاتيح الحقول)\n• GET /records/{entity}/{id}\n• PATCH /records/{entity}/{id} — تعديل جزئي\n• DELETE /records/{entity}/{id}",
              codeBlock: {
                language: "python",
                filename: "server.py",
                code: `from mizan_sdk import MizanClient\n\nclient = MizanClient("mzx_...")\nprint(client.me())          # المنشأة والوحدة والنطاقات\nvisits = client.records("visit")\nv = visits.create({"customer": "<customer id>", "on": "2026-11-15", "state": "مجدولة"})\nvisits.update(v["id"], {"state": "تمت"})`,
              },
            },
            {
              id: "builtin",
              title: "بيانات المنشأة",
              body:
                "القوائم تقبل limit (حتى 200) و offset وتعيد {items, total}.\n• GET /customers?q= (customers:read) و POST /customers {name, phone, address} (customers:write)\n• GET /suppliers (suppliers:read)\n• GET /products?q= (products:read) — الاسم أو الكود أو الباركود\n• GET /stock?product_id= (stock:read)\n• GET /sales?since=<ISO time> (sales:read) — الفواتير المؤكدة الأحدث أولًا، مع بنودها\n• GET /employees (employees:read)\n• GET /branches (branches:read)\n\nالمبالغ نصوص عشرية (\"150.50\") والأوقات ISO 8601.",
            },
          ],
        },
      },
      {
        slug: "webhooks",
        title: "الإشعارات (Webhooks)",
        titleEn: "Webhooks",
        description: "أحداث موقّعة إلى خادمك، مع إعادة المحاولة وسجل يراه صاحب المنشأة.",
        category: "الربط بخادمك",
        lastUpdated: UPDATED,
        content: {
          overview:
            "حدّد في manifest.json عنوان خادمك والأحداث (webhooks.url و webhooks.events). يُسجَّل كل حدث مع التغيير نفسه فلا يضيع، ويُرسَل فورًا؛ وإن فشل أُعيدت المحاولة بعد 1 و5 و30 دقيقة ثم 2 و6 و12 ساعة، ثم يُترك. يرى صاحب المنشأة سجلها في «الإشعارات».",
          sections: [
            {
              id: "request",
              title: "الطلب",
              body:
                "POST بمحتوى JSON إلى عنوان HTTPS عام (لا عناوين محلية أو خاصة)، مع الترويسات Mizan-Event و Mizan-Delivery و Mizan-Timestamp و Mizan-Signature. ردّ بأي رمز 2xx خلال 5 ثوانٍ.",
              codeBlock: {
                language: "json",
                code: `{
  "id": "<delivery id>",
  "event": "sale.confirmed",
  "created_at": "2026-11-13T09:50:00+00:00",
  "workspace": {"id": "<workspace id>"},
  "module": "acme.visits",
  "data": {"id": "...", "invoice_number": "INV-1042", "customer_id": "...", "branch_id": "...",
           "total": "250.00", "net_total": "250.00", "is_credit": false,
           "lines": [{"product_id": "...", "qty": "1", "unit_price": "250.00", "discount": "0"}]}
}`,
              },
            },
            {
              id: "verify",
              title: "التحقق من التوقيع",
              body:
                "Mizan-Signature هي sha256=<HMAC-SHA256 لـ \"<timestamp>.<الجسم كما وصل>\" بسر التوقيع>. سر التوقيع يظهر مع رمز الربط. ارفض ما يزيد عمره عن 5 دقائق، واستخدم Mizan-Delivery لتجاهل التكرار.",
              codeBlock: {
                language: "python",
                code: `from mizan_sdk import WebhookError, verify_webhook\n\ndef handle(request):\n    try:\n        event = verify_webhook(SECRET, request.body,\n                               request.headers["Mizan-Timestamp"], request.headers["Mizan-Signature"])\n    except WebhookError:\n        return 400\n    ...`,
              },
              callout: { type: "warning", text: "تحقق دائمًا من التوقيع على الجسم الخام قبل إعادة ترميزه؛ أي تغيير فيه يبطل التوقيع." },
            },
            {
              id: "events",
              title: "الأحداث وبياناتها",
              body:
                "• sale.confirmed — الفاتورة وبنودها (كما في المثال).\n• sale.returned — الفاتورة الأصلية مع return {total} (ومعرّف المرتجع ورقمه في المرتجع الجزئي).\n• customer.created — {id, name, phone}\n• product.updated — {id, code, name, retail_price, is_active}\n• record.created / record.updated — {entity, id, data} لسجلات وحدتك.",
            },
          ],
        },
      },
    ],
  },
  {
    id: "ship",
    title: "التوقيع والتوزيع",
    titleEn: "Signing and shipping",
    items: [
      {
        slug: "signing",
        title: "مفاتيح التوقيع والشهادات",
        titleEn: "Signing keys",
        description: "لماذا توقَّع الحزم، وكيف يشهد ميزان لمفتاحك، وإلغاء مفتاح.",
        category: "التوقيع والتوزيع",
        lastUpdated: UPDATED,
        content: {
          overview:
            "كل حزمة موقّعة بمفتاح Ed25519 خاص يبقى على جهازك. تسجّل نصفه العام لفريقك في البوابة فيصدر ميزان له شهادة (تبدأ بـ MZD1). عند التثبيت يتحقق ميزان — حتى في الخوادم المحلية دون إنترنت — من أن الشهادة منه، وأن التوقيع من المفتاح المشهود له، وأن الملفات لم تتغير، وأن معرّف الوحدة يبدأ بمعرّف الفريق.",
          sections: [
            {
              id: "keys",
              title: "المفاتيح",
              body:
                "mizan keys new --team <فريقك> ينشئ المفتاح في ~/.mizan ويسجله ويحفظ شهادته. أو انسخ المفتاح العام الذي يطبعه إلى «المفاتيح» في صفحة الفريق واحفظ الشهادة في ~/.mizan/default.cert. لكل فريق حتى 10 مفاتيح فعالة؛ أي عضو يسجل مفتاحًا، والمالكون فقط يلغونها.",
              callout: { type: "warning", text: "المفتاح الخاص يوقّع باسم فريقك: لا تشاركه ولا ترفعه إلى مستودع. إن تسرب فألغه من البوابة وأنشئ غيره." },
            },
            {
              id: "revoke",
              title: "الإلغاء",
              body:
                "بعد إلغاء مفتاح يرفض ميزان السحابي تثبيت أي حزمة موقّعة به (والوحدات المثبتة سابقًا تبقى). وقّع إصدارًا جديدًا بمفتاح آخر.",
            },
          ],
        },
      },
      {
        slug: "installing",
        title: "التثبيت والتحديث والإزالة",
        titleEn: "Installing",
        description: "ما يراه صاحب المنشأة وما يحدث للسجلات.",
        category: "التوقيع والتوزيع",
        lastUpdated: UPDATED,
        content: {
          overview:
            "يثبّت الوحدة من يملك صلاحية «تثبيت وإزالة وحدات المطورين» (مدير المنشأة): مركز الوحدات ← وحدات المطورين ← تثبيت من ملف. يرى اسمها ومطورها وما تضيفه والنطاقات وإلى أين ترسل إشعاراتها، ولا يُفعَّل زر التثبيت قبل موافقته.",
          sections: [
            {
              id: "update",
              title: "التحديث",
              body: "ارفع إصدارًا أحدث بنفس المعرّف: تُستبدل التعريفات وتبقى السجلات. إن طلب نطاقات جديدة تُعلَّم «جديد» ويوافق عليها صاحب المنشأة.",
            },
            {
              id: "remove",
              title: "الإزالة",
              body:
                "يختار صاحب المنشأة: إزالة مع الاحتفاظ بالسجلات (تعود عند إعادة التثبيت)، أو إزالة وحذف السجلات نهائيًا. في الحالتين يتوقف رمز الربط فورًا.",
            },
          ],
        },
      },
      {
        slug: "publishing",
        title: "النشر في السوق",
        titleEn: "Publishing",
        description: "إرسال وحدة أو مظهر للمراجعة، وما تفحصه المراجعة، والتحديثات.",
        category: "التوقيع والتوزيع",
        lastUpdated: UPDATED,
        content: {
          overview:
            "الوحدات والمظاهر المنشورة تظهر في «المتجر» داخل مركز الوحدات في كل منشأة. أرسل حزمة موقّعة بالأمر mizan publish أو بزر «إرسال حزمة» في صفحة فريقك في البوابة. يراجعها فريق ميزان؛ وعند القبول يوقّع ميزان على هذه الحزمة بعينها وينشرها. وتُنشر الأنشطة بالطريقة نفسها؛ لا تُثبَّت من المتجر بل تتحوّل المنشأة إليها (انظر «الأنشطة التجارية»). القوائم مجانية حاليًا؛ والمدفوعة لاحقًا.",
          sections: [
            {
              id: "send",
              title: "الإرسال",
              body: "الأمر mizan publish يحزم المجلد ويرسله إلى الفريق الذي يبدأ به المعرّف (acme.visits ← acme)، ويرسل أيضًا ملف .mzm بنيته من قبل. صفحة فريقك تعرض كل إصدار أرسلته وحالته: قيد المراجعة أو مقبول أو مرفوض (مع ملاحظة المراجع) أو مسحوب. يمكنك سحب الإصدار ما دام قيد المراجعة.",
              codeBlock: { language: "bash", code: "mizan publish acme.visits          # يحزم ثم يرسل\nmizan publish acme.visits-1.2.0.mzm" },
            },
            {
              id: "review",
              title: "ما تفحصه المراجعة",
              body: "أولًا الفحوص نفسها التي تجري عند التثبيت من ملف: التوقيع، وشهادة ميزان لمفتاحك، وأن المفتاح غير ملغى، وأن المعرّف ضمن نطاق فريقك، وقواعد ملف التعريف. ثم يطّلع شخص على ما تضيفه الوحدة، والصلاحيات التي تطلبها (الصلاحيات الجديدة في التحديث تظهر مميزة)، والعنوان الذي ترسل إليه الأحداث، وملفاتها. اطلب الصلاحيات التي تستخدمها فقط، واكتب وصف الوحدة بعربية واضحة.",
            },
            {
              id: "updates",
              title: "التحديثات",
              body: "ارفع رقم الإصدار (1.0.0 ← 1.1.0) وانشر من جديد؛ يُرسل كل إصدار مرة واحدة، ويجب أن يكون أحدث من المنشور. يبقى الإصدار المنشور في المتجر حتى يُقبل الجديد. المنشآت التي ثبّتت الوحدة ترى «تحديث متاح» وتوافق على أي صلاحيات جديدة.",
            },
            {
              id: "delist",
              title: "الإزالة من المتجر",
              body: "يستطيع فريق ميزان إزالة وحدة أو مظهر من المتجر (مثلًا بعد بلاغ أمني) مع سبب يظهر في صفحة فريقك. لا يمكن تثبيتها بعد ذلك، والمنشآت التي ثبّتتها تحتفظ بها. وإلغاء مفتاح التوقيع يوقف أيضًا التثبيتات الجديدة لكل ما وقّعه.",
            },
          ],
        },
      },
      {
        slug: "cli",
        title: "أداة mizan",
        titleEn: "The CLI",
        description: "كل الأوامر.",
        category: "التوقيع والتوزيع",
        lastUpdated: UPDATED,
        content: {
          overview: `ثبّتها بـ pip install ${SDK_URL} . الملفات في ~/.mizan (أو MIZAN_HOME).`,
          sections: [
            {
              id: "commands",
              title: "الأوامر",
              body: "",
              codeBlock: {
                language: "bash",
                code: `mizan login [--token mzd_...]     # رمز من البوابة (أو MIZAN_TOKEN)
mizan whoami                      # حسابك وفرقك
mizan logout
mizan module new acme.visits      # وحدة من القالب
mizan theme new acme.sunrise      # حزمة مظهر من مظهر ميزان
mizan activity new acme.laundry   # نشاط تجاري كامل
mizan check [folder]              # نفس فحص المنصة
mizan keys new [--team acme] [--name laptop]
mizan package [folder] [--key ...] [--certificate ...] [--out ...]
mizan publish [folder|file.mzm] [--team acme]   # يرسلها إلى السوق للمراجعة`,
              },
            },
          ],
        },
      },
    ],
  },
];

/** The developer docs in the platform's language (English by default). */
export function devDocSections(locale: "ar" | "en"): DocSection[] {
  return locale === "ar" ? AR : EN;
}
