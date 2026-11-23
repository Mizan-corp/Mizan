export interface BlogPost {
  slug: string;
  title: string;
  titleEn: string;
  excerpt: string;
  category: "engineering" | "retail" | "accounting" | "hardware";
  categoryLabel: string;
  readTime: string;
  date: string;
  /** The same date, ISO (structured data and the sitemap). */
  published: string;
  author: {
    name: string;
    role: string;
    avatar: string;
  };
  content: {
    intro: string;
    bodySections: {
      title: string;
      text: string;
      codeBlock?: {
        lang: string;
        code: string;
      };
    }[];
    conclusion: string;
  };
}

export const BLOG_POSTS: BlogPost[] = [
  {
    slug: "postgresql-rls-multi-tenancy",
    title: "كيف يضمن عزل Row-Level Security في PostgreSQL أمان بيانات المنشآت المتعددة في ميزان؟",
    titleEn: "How PostgreSQL Row-Level Security Guarantees Multi-Tenant Isolation in Mizan ERP",
    excerpt:
      "كيف تعزل قاعدة البيانات نفسها بيانات كل منشأة عن غيرها، بدلًا من الاعتماد على تذكّر المبرمج لشرط واحد في كل استعلام.",
    category: "engineering",
    categoryLabel: "هندسة البرمجيات",
    readTime: "7 دقائق",
    date: "28 أكتوبر 2026",
    published: "2026-10-28",
    author: {
      name: "فريق هندسة النواة",
      role: "Core Architecture Team",
      avatar: "/assets/marketing/avatar-1.webp",
    },
    content: {
      intro:
        "في أنظمة الـ ERP السحابية متعددة المنشآت (Multi-Tenant SaaS)، يُعد أمان وعزل بيانات العملاء المعيار الأهم على الإطلاق. تختار العديد من الأنظمة إما عزل قواعد البيانات بالكامل (Database-per-Tenant) وهو ما يؤدي إلى صعوبة بالغة في الترقية والصيانة، أو الاعتماد البسيط على شرط WHERE tenant_id = :id في شفرة التطبيق، وهو ما يحمل مخاطر خطأ بشري قد يكشف بيانات منشأة لأخرى. في ميزان ERP، اخترنا الحل الهندسي الأمثل: Row-Level Security على مستوى نواة PostgreSQL.",
      bodySections: [
        {
          title: "1. ما هو Row-Level Security (RLS)؟",
          text:
            "Row-Level Security هي ميزة مدمجة في محرك PostgreSQL تسمح بتحديد سياسات أمان تتحكم في الصفوف التي يمكن لكل مستخدم أو جلسة استرجاعها أو تعديلها. يتم تقييم السياسة مباشرة في النواة التنفيذية للاستعلام قبل إعادة أي بايت من البيانات.",
        },
        {
          title: "2. كيف يفعل ميزان سياسة الأمان؟",
          text:
            "عند وصول أي طلب إلى واجهة FastAPI، يقوم وسيط المصادقة باستخراج tenant_id الموثق من توكن الـ JWT، ثم يرسل أمراً فورياً لجلسة قاعدة البيانات قبل تنفيذ أي استعلام:",
          codeBlock: {
            lang: "sql",
            code: "-- ضبط معرف المنشأة الحالية في متغير الجلسة\nSET LOCAL app.current_tenant_id = 'c935140b-71a2-4c28-9bc3-7a9120489912';\n\n-- الآن، حتى لو قام المطور بكتابة SELECT * FROM products بدون WHERE،\n-- فإن المحرك يطبق السياسة تلقائياً ويعيد فقط منتجات هذه المنشأة!\nSELECT id, name, price FROM products;",
          },
        },
        {
          title: "3. نموذج الـ TenantScoped في SQLAlchemy",
          text:
            "لضمان عدم نسيان عمود tenant_id في أي جدول جديد، يرث كل موديل قاعدة بيانات في ميزان من كلاس موحد يحقن المفتاح الأجنبي وفهارس البحث اللحظية تلقائياً.",
        },
      ],
      conclusion:
        "بهذا النموذج تفرض قاعدة البيانات العزل بنفسها في كل استعلام، فلا تعتمد حماية بيانات المنشأة على أن يتذكر كل مبرمج كتابة الشرط الصحيح.",
    },
  },
  // The post on ESC/POS commands and a Saudi tax QR was withdrawn (it described code Mizan doesn't have); nginx sends its address to /blog.
  {
    slug: "why-modular-erps-win",
    title: "لماذا تتفوق أنظمة الـ ERP المعيارية على الأنظمة التقليدية الجامدة في المنشآت النامية؟",
    titleEn: "Why Modular ERPs Outperform Monolithic Systems in Growing Enterprises",
    excerpt:
      "مقارنة عملية بين الأنظمة الكلاسيكية (SAP، Oracle، البرامج المكتبية) والجيل الجديد من منصات الـ ERP المعيارية القابلة للتخصيص اللحظي.",
    category: "accounting",
    categoryLabel: "إدارة الأعمال",
    readTime: "5 دقائق",
    date: "19 أكتوبر 2026",
    published: "2026-10-19",
    author: {
      name: "مستشار حلول الأعمال",
      role: "Enterprise Solutions Consultant",
      avatar: "/assets/marketing/avatar-3.webp",
    },
    content: {
      intro:
        "لعقود طويلة، كانت أنظمة تخطيط الموارد المؤسسية مرادفة للتكلفة المرتفعة، عقود التنفيذ التي تمتد لأشهر أو سنوات، والواجهات المعقدة التي يصعب تدريب الموظفين عليها. اليوم، يعيد الجيل المعياري صياغة هذه المعادلة بالكامل.",
      bodySections: [
        {
          title: "1. فعّل ما تحتاجه فقط",
          text:
            "في ميزان ERP، إذا كنت تدير متجر تجزئة، فأنت لست مضطراً لرؤية شاشات المستشفيات أو حجز الطاولات. تفعل فقط: المخزون، نقطة البيع، والمالية. وحينما تقرر التوسع وفتح نشاط آخر كمطعم، تضيف له مساحة عمل بنشاطه من لوحة المالك نفسها.",
        },
        {
          title: "2. كشف حساب واحد ومخزون مركزي",
          text:
            "مع تفعيل المحاسبة، تُرحَّل مبيعات الكاشير والمشتريات والمصروفات والرواتب وفواتير العيادة إلى دفتر أستاذ واحد، فترى الإدارة المالية الصورة كاملة دون إدخال مزدوج.",
        },
      ],
      conclusion:
        "المستقبل ينتمي للأنظمة الرشيقة التي تنمو مع المنشأة خطوة بخطوة بدلاً من إرهاقها بتكاليف تأسيسية باهظة.",
    },
  },
  {
    slug: "offline-first-cashier-velocity",
    title: "كاشير لا يضيّع فاتورة عند انقطاع الإنترنت: كيف يحفظ ميزان المبيعات ويزامنها",
    titleEn: "A till that never loses a sale when the internet drops: how Mizan keeps and syncs sales",
    excerpt:
      "كيف يحفظ ميزان فواتير الكاشير على الجهاز عند انقطاع الإنترنت ويرسلها دون تكرار عند عودته، ومتى تختار تشغيله بدون إنترنت بالكامل.",
    category: "retail",
    categoryLabel: "التجزئة والكاشير",
    readTime: "6 دقائق",
    date: "12 أكتوبر 2026",
    published: "2026-10-12",
    author: {
      name: "مهندس أداء النظم",
      role: "Performance Engineering",
      avatar: "/assets/marketing/avatar-4.webp",
    },
    content: {
      intro:
        "توقف الكاشير لدقيقة واحدة في سوبرماركت أو مطعم في ساعة الذروة قد يعني خسارة عملاء وتكدس الطوابير. لذلك لا يضيّع ميزان أي فاتورة إذا انقطع الإنترنت لحظة الدفع.",
      bodySections: [
        {
          title: "1. طابور فواتير على الجهاز",
          text:
            "إذا تعذر الوصول إلى الخادم عند إتمام البيع، تُحفظ الفاتورة في طابور على الجهاز (IndexedDB). لكل فاتورة معرّف فريد يُنشأ على الجهاز قبل أول محاولة، فلا تُسجَّل مرتين مهما أُعيد إرسالها.",
        },
        {
          title: "2. المزامنة عند عودة الاتصال",
          text:
            "عند عودة الاتصال تُرسل الفواتير المحفوظة تلقائيًا. وإذا رفض الخادم فاتورة لسبب حقيقي (كنفاد الكمية) تظهر للكاشير ليقرر بشأنها، بدل إعادة المحاولة بلا نهاية.",
        },
        {
          title: "3. وإذا كان الإنترنت ضعيفًا دائمًا",
          text:
            "على السحابة يحتاج البحث عن الأصناف ومسح الباركود إلى الاتصال. فإذا كان الإنترنت في منطقتك غير مستقر، اختر عند إنشاء مساحة العمل التشغيل على جهاز واحد أو على شبكة المحل: يعمل ميزان عندها بالكامل بدون إنترنت.",
        },
      ],
      conclusion:
        "بهذا تجمع بين سهولة النظام السحابي واطمئنانك إلى أن فاتورة واحدة لن تضيع وقت الزحمة.",
    },
  },
];
