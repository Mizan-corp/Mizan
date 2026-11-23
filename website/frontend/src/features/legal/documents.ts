/**
 * The legal pages' text, in Arabic and English. Keep both languages saying the
 * same thing, and keep them true to how Mizan works (pricing in
 * shared/backend/app/core/plans.py, payments in ADR-004, on-site installs in ADR-005).
 * When a page changes, update BUSINESS.effective.
 */
import { BUSINESS as B } from "./business";

export type Block = string | { list: string[] };

export interface LegalSection {
  id: string;
  title: string;
  blocks: Block[];
}

export interface LegalContent {
  title: string;
  description: string;
  /** Plain-language summary shown first. */
  summary?: string[];
  sections: LegalSection[];
}

export type LegalSlug = "terms" | "privacy" | "refund-policy";

export const LEGAL_ORDER: LegalSlug[] = ["terms", "privacy", "refund-policy"];

const contactAr = `للتواصل: هاتف وواتساب ${B.phoneDisplay}، ${B.city.ar}.`;
const contactEn = `Contact: phone and WhatsApp ${B.phoneDisplay}, ${B.city.en}.`;

export const LEGAL_DOCS: Record<LegalSlug, { ar: LegalContent; en: LegalContent }> = {
  // ─── Terms of Service ───────────────────────────────────────────────────
  terms: {
    ar: {
      title: "شروط الاستخدام",
      description: "الاتفاق بينك وبين ميزان عند إنشاء حساب أو استخدام النظام أو الاشتراك فيه.",
      sections: [
        {
          id: "about",
          title: "من نحن ونطاق هذه الشروط",
          blocks: [
            `«ميزان» نظام لإدارة الأعمال (ERP) يُقدَّم كخدمة اشتراك، ويديره ${B.seller.ar} (${B.sellerType.ar})، ${B.city.ar}. يُشار إليه في هذه الشروط بـ«نحن».`,
            "تنطبق هذه الشروط على الموقع ولوحة المالك والنظام نفسه، سواء على السحابة أو مثبتًا على جهاز أو شبكة داخل منشأتك. بإنشاء حساب أو استخدام الخدمة أو الدفع، فإنك توافق عليها وعلى سياسة الخصوصية وسياسة الاسترداد.",
            "الخدمة موجهة للأنشطة التجارية والمهنية، ويجب أن يكون عمر من يُنشئ الحساب 18 عامًا على الأقل، وأن يكون مخولًا بالتصرف نيابة عن المنشأة.",
          ],
        },
        {
          id: "accounts",
          title: "الحسابات ومساحات العمل",
          blocks: [
            "يملك «حساب المالك» مساحة عمل أو أكثر، ويدير منها الاشتراكات والفواتير. ويضيف المالك موظفيه كمستخدمين داخل كل مساحة عمل بالصلاحيات التي يحددها.",
            {
              list: [
                "أنت مسؤول عن صحة البيانات التي تقدمها، وعن سرية كلمات المرور، وعن كل ما يتم من خلال حسابك وحسابات موظفيك.",
                "أبلغنا فورًا إذا اشتبهت في دخول غير مصرح به إلى حسابك.",
                "يمكنك إنشاء أكثر من مساحة عمل، ولكل منها اشتراكها الخاص.",
              ],
            },
          ],
        },
        {
          id: "trial",
          title: "التجربة المجانية",
          blocks: [
            "تبدأ كل مساحة عمل جديدة بتجربة مجانية لمدة 14 يومًا دون أي دفع، بحدود باقة التجربة المعروضة في صفحة الأسعار. عند انتهاء التجربة دون اشتراك، تصبح مساحة العمل للعرض فقط حتى تشترك، ولا تُحذف بياناتك.",
          ],
        },
        {
          id: "payment",
          title: "الباقات والأسعار والدفع",
          blocks: [
            "الأسعار بالجنيه المصري كما تظهر في صفحة الأسعار وفي لوحة المالك وقت الدفع، والمبلغ المعروض في صفحة الدفع هو المبلغ الذي يُخصم.",
            {
              list: [
                "يُدفع الاشتراك مقدمًا عن شهر أو سنة، من لوحة المالك، عبر بوابة الدفع Paymob (بطاقات بنكية ومحافظ إلكترونية حسب المتاح).",
                "لا نستلم بيانات بطاقتك ولا نحتفظ بها؛ تتم معالجتها بالكامل لدى Paymob.",
                "يتفعّل الاشتراك فور تأكيد Paymob لنجاح الدفع، ويمتد حتى نهاية المدة المدفوعة.",
                "إذا غيّرنا الأسعار، تسري الأسعار الجديدة على المدد التالية فقط، ونعلن عنها قبل تطبيقها.",
              ],
            },
          ],
        },
        {
          id: "renewal",
          title: "لا تجديد تلقائي",
          blocks: [
            "لا نحفظ وسيلة دفعك ولا نخصم أي مبلغ تلقائيًا. كل دفعة تغطي مدتها فقط، ولتستمر بعدها تدفع المدة التالية بنفسك من لوحة المالك.",
            "إذا انتهت المدة المدفوعة دون تجديد، يحق لنا جعل مساحة العمل للعرض فقط حتى التجديد، مع بقاء بياناتك محفوظة.",
          ],
        },
        {
          id: "cancellation",
          title: "الإلغاء والاسترداد",
          blocks: [
            "يمكنك التوقف في أي وقت بعدم تجديد الاشتراك، ويستمر وصولك الكامل حتى نهاية المدة المدفوعة. أما استرداد المبالغ فتحكمه سياسة الاسترداد.",
          ],
        },
        {
          id: "on-site",
          title: "التشغيل على جهاز واحد أو شبكة محلية",
          blocks: [
            "عند اختيار تشغيل مساحة العمل على جهاز واحد أو على شبكة منشأتك، تنزّل برنامج التثبيت مع ترخيص خاص بمساحة العمل:",
            {
              list: [
                "الترخيص صالح حتى نهاية المدة المدفوعة، ويتجدد عند الدفع ويحصل عليه الجهاز تلقائيًا عند اتصاله بالإنترنت، أو يمكنك إدخاله يدويًا.",
                "عند انتهاء الترخيص يبقى البرنامج متاحًا للعرض فقط حتى التجديد.",
                "الترخيص لمنشأتك فقط، ولا يجوز نقله لغيرها أو محاولة تعطيله أو التحايل عليه.",
                "بياناتك في هذه الحالة محفوظة على أجهزتك أنت؛ أنت مسؤول عن سلامة الأجهزة وعن الاحتفاظ بنسخ احتياطية خارجها (يأخذ البرنامج نسخة احتياطية يومية على الجهاز نفسه).",
              ],
            },
          ],
        },
        {
          id: "acceptable-use",
          title: "الاستخدام المقبول",
          blocks: [
            {
              list: [
                "استخدم الخدمة لأغراض مشروعة فقط ووفق القوانين المصرية، بما فيها قوانين الضرائب وحماية البيانات.",
                "لا تحاول الوصول إلى بيانات غيرك، أو تعطيل الخدمة، أو اختبار أمانها دون إذن كتابي منا.",
                "لا تنسخ البرنامج أو تعيد بيعه أو تفك شفرته، إلا بالقدر الذي يسمح به القانون.",
              ],
            },
          ],
        },
        {
          id: "your-data",
          title: "بياناتك",
          blocks: [
            "بيانات منشأتك (العملاء، الأصناف، الفواتير، الموظفون وغيرها) ملك لك. نعالجها فقط لتقديم الخدمة لك، كما توضح سياسة الخصوصية. وأنت مسؤول عن أن يكون لديك أساس قانوني لإدخال بيانات عملائك وموظفيك.",
            "يمكنك تصدير بياناتك من داخل النظام. وعند طلب إغلاق الحساب نحذف بيانات مساحة العمل خلال 30 يومًا، إلا ما يلزمنا القانون بالاحتفاظ به (مثل سجلات المدفوعات).",
          ],
        },
        {
          id: "availability",
          title: "توفر الخدمة والدعم",
          blocks: [
            "نعمل على أن تكون الخدمة متاحة ومستقرة دائمًا، لكننا لا نضمن عملها دون انقطاع أو أخطاء، وقد نوقفها مؤقتًا للصيانة أو التحديث. نقدم الدعم عبر الهاتف وواتساب في أيام وساعات العمل.",
            "النظام أداة تساعدك في عملك؛ تبقى أنت مسؤولًا عن مراجعة الأرقام والفواتير والإقرارات قبل اعتمادها أو تقديمها لأي جهة.",
          ],
        },
        {
          id: "ip",
          title: "الملكية الفكرية",
          blocks: [
            "البرنامج والتصميم والعلامة «ميزان» ملك لنا. يمنحك الاشتراك حق استخدام الخدمة لمنشأتك طوال مدة الاشتراك، ولا ينقل إليك أي ملكية.",
          ],
        },
        {
          id: "liability",
          title: "حدود المسؤولية",
          blocks: [
            "تُقدَّم الخدمة «كما هي». وفي حدود ما يسمح به القانون، لا نتحمل المسؤولية عن الخسائر غير المباشرة، مثل فوات الربح أو توقف العمل، ولا تتجاوز مسؤوليتنا الإجمالية عن أي مطالبة ما دفعته لنا مقابل الخدمة خلال الاثني عشر شهرًا السابقة لها.",
          ],
        },
        {
          id: "suspension",
          title: "الإيقاف وإنهاء الحساب",
          blocks: [
            "يحق لنا إيقاف مساحة عمل أو حساب عند مخالفة هذه الشروط أو الاستخدام غير المشروع، مع إخطارك متى أمكن. الإيقاف لا يحذف البيانات. ويمكنك طلب إغلاق حسابك في أي وقت.",
          ],
        },
        {
          id: "changes",
          title: "تعديل الشروط",
          blocks: [
            "قد نعدّل هذه الشروط، ونعلن عن التعديلات المهمة على الموقع أو في لوحة المالك قبل سريانها. استمرارك في استخدام الخدمة بعد سريان التعديل يعني موافقتك عليه.",
          ],
        },
        {
          id: "law",
          title: "القانون الواجب التطبيق",
          blocks: ["تخضع هذه الشروط للقانون المصري، وتختص المحاكم المصرية بنظر أي نزاع ينشأ عنها، بعد محاولة حله وديًا."],
        },
        { id: "contact", title: "التواصل", blocks: [contactAr] },
      ],
    },
    en: {
      title: "Terms of Service",
      description: "The agreement between you and Mizan when you create an account, use the system or subscribe.",
      sections: [
        {
          id: "about",
          title: "Who we are and what these terms cover",
          blocks: [
            `Mizan is business-management (ERP) software provided as a subscription service, operated by ${B.seller.en} (${B.sellerType.en}), ${B.city.en} ("we", "us").`,
            "These terms cover the website, the owner panel and the system itself, whether in the cloud or installed on a computer or network at your business. By creating an account, using the service or paying, you accept them, together with the Privacy Policy and the Refund Policy.",
            "The service is for businesses and professionals. Whoever creates the account must be at least 18 and authorised to act for the business.",
          ],
        },
        {
          id: "accounts",
          title: "Accounts and workspaces",
          blocks: [
            "An owner account owns one or more workspaces and manages their subscriptions and invoices. The owner adds staff as users inside each workspace, with the permissions they choose.",
            {
              list: [
                "You are responsible for the accuracy of the information you give, for keeping passwords secret, and for everything done through your account and your staff's accounts.",
                "Tell us immediately if you suspect unauthorised access to your account.",
                "You can create more than one workspace; each has its own subscription.",
              ],
            },
          ],
        },
        {
          id: "trial",
          title: "Free trial",
          blocks: [
            "Every new workspace starts with a free 14-day trial, without payment, within the trial limits shown on the pricing page. If the trial ends without a subscription, the workspace becomes read-only until you subscribe; your data is not deleted.",
          ],
        },
        {
          id: "payment",
          title: "Plans, prices and payment",
          blocks: [
            "Prices are in Egyptian pounds, as shown on the pricing page and in the owner panel at the time of payment. The amount shown on the payment page is the amount charged.",
            {
              list: [
                "Subscriptions are paid in advance for a month or a year, from the owner panel, through the Paymob payment gateway (bank cards and mobile wallets, as available).",
                "We never receive or store your card details; Paymob processes them.",
                "A subscription starts as soon as Paymob confirms the payment and lasts until the end of the period paid for.",
                "If we change prices, new prices apply only to later periods, and we announce them before they apply.",
              ],
            },
          ],
        },
        {
          id: "renewal",
          title: "No automatic renewal",
          blocks: [
            "We don't save your payment method and never charge you automatically. Each payment covers its own period; to continue afterwards, you pay for the next period yourself from the owner panel.",
            "If a paid period ends without renewal, we may make the workspace read-only until it's renewed; your data stays.",
          ],
        },
        {
          id: "cancellation",
          title: "Cancellation and refunds",
          blocks: [
            "You can stop at any time by not renewing; you keep full access until the end of the period you paid for. Refunds are governed by the Refund Policy.",
          ],
        },
        {
          id: "on-site",
          title: "Running on one computer or a local network",
          blocks: [
            "If you choose to run a workspace on one computer or on your business's network, you download the installer with a licence for that workspace:",
            {
              list: [
                "The licence is valid until the end of the paid period. It is extended when you pay; the computer picks it up automatically when online, or you enter it yourself.",
                "When the licence expires, the software stays available read-only until renewal.",
                "The licence is for your business only; it may not be transferred, disabled or circumvented.",
                "Your data then lives on your own devices: you are responsible for them and for keeping backups elsewhere (the software takes a daily backup on the same computer).",
              ],
            },
          ],
        },
        {
          id: "acceptable-use",
          title: "Acceptable use",
          blocks: [
            {
              list: [
                "Use the service lawfully and in line with Egyptian law, including tax and data-protection law.",
                "Don't try to access others' data, disrupt the service, or test its security without our written permission.",
                "Don't copy, resell or reverse-engineer the software, except as the law allows.",
              ],
            },
          ],
        },
        {
          id: "your-data",
          title: "Your data",
          blocks: [
            "Your business data (customers, products, invoices, employees and so on) belongs to you. We process it only to provide the service, as the Privacy Policy explains. You are responsible for having a lawful basis to enter your customers' and employees' data.",
            "You can export your data from the system. If you ask us to close your account, we delete the workspace's data within 30 days, except what the law requires us to keep (such as payment records).",
          ],
        },
        {
          id: "availability",
          title: "Availability and support",
          blocks: [
            "We work to keep the service available and stable, but we don't guarantee it will run without interruption or errors, and we may pause it for maintenance or updates. Support is by phone and WhatsApp during business days and hours.",
            "The system is a tool to help your work: you remain responsible for checking figures, invoices and returns before relying on them or filing them with any authority.",
          ],
        },
        {
          id: "ip",
          title: "Intellectual property",
          blocks: [
            "The software, its design and the Mizan name belong to us. A subscription gives your business the right to use the service for the subscription period; it doesn't transfer ownership.",
          ],
        },
        {
          id: "liability",
          title: "Limitation of liability",
          blocks: [
            "The service is provided \"as is\". To the extent the law allows, we are not liable for indirect losses such as lost profits or business interruption, and our total liability for any claim is limited to what you paid us for the service in the twelve months before it.",
          ],
        },
        {
          id: "suspension",
          title: "Suspension and closing accounts",
          blocks: [
            "We may suspend a workspace or account for breach of these terms or unlawful use, notifying you where possible. Suspension doesn't delete data. You may ask us to close your account at any time.",
          ],
        },
        {
          id: "changes",
          title: "Changes to these terms",
          blocks: [
            "We may change these terms and will announce important changes on the website or in the owner panel before they take effect. Continuing to use the service after that means you accept them.",
          ],
        },
        {
          id: "law",
          title: "Governing law",
          blocks: ["These terms are governed by Egyptian law, and Egyptian courts have jurisdiction over any dispute, after an attempt to settle it amicably."],
        },
        { id: "contact", title: "Contact", blocks: [contactEn] },
      ],
    },
  },

  // ─── Privacy Policy ─────────────────────────────────────────────────────
  privacy: {
    ar: {
      title: "سياسة الخصوصية",
      description: "ما البيانات التي نجمعها، ولماذا، ومع من نشاركها، وكيف تتحكم فيها.",
      summary: [
        "لا نبيع بياناتك، ولا نستخدم أدوات إعلانات.",
        "نعدّ زيارات موقعنا بأنفسنا بلا ملفات تعريف ارتباط؛ وGoogle Analytics لا يعمل إلا إذا وافقت عليه.",
        "بيانات منشأتك ملكك؛ نعالجها فقط لتقديم الخدمة.",
        "لا نستلم بيانات بطاقتك؛ تعالجها Paymob.",
      ],
      sections: [
        {
          id: "controller",
          title: "من المسؤول عن بياناتك",
          blocks: [
            `${B.seller.ar} (${B.sellerType.ar})، ${B.city.ar}، مشغّل «ميزان». نلتزم بقانون حماية البيانات الشخصية المصري رقم 151 لسنة 2020.`,
          ],
        },
        {
          id: "collect",
          title: "ما الذي نجمعه",
          blocks: [
            {
              list: [
                "بيانات الحساب: الاسم، اسم المستخدم، رقم الموبايل، البريد الإلكتروني (إن أدخلته)، وكلمة المرور محفوظة مشفرة بطريقة لا تسمح بقراءتها.",
                "بيانات منشأتك التي تدخلها في النظام: العملاء والموردون والأصناف والفواتير والموظفون وغيرها.",
                "بيانات الدفع: رقم العملية لدى Paymob والمبلغ وحالته. لا نستلم أرقام البطاقات.",
                "بيانات تقنية: عنوان IP ونوع المتصفح وسجلات الدخول والأخطاء، لأغراض الأمان وإصلاح المشكلات.",
                "عند التشغيل على جهاز أو شبكة: يرسل البرنامج عند اتصاله بالإنترنت معرّف التثبيت واسم الجهاز ونظام التشغيل وإصدار البرنامج وعنوان IP ووقت آخر نسخة احتياطية، لتجديد الترخيص. لا يرسل أي بيانات من أعمالك.",
              ],
            },
          ],
        },
        {
          id: "use",
          title: "لماذا نستخدمها",
          blocks: [
            {
              list: [
                "لتقديم الخدمة وتشغيل حسابك ومساحات عملك.",
                "لإصدار الفواتير وتفعيل الاشتراكات والتراخيص.",
                "للدعم الفني والتواصل معك بخصوص حسابك.",
                "لحماية الخدمة ومنع الاحتيال وإساءة الاستخدام.",
                "للالتزام بالقانون، مثل الاحتفاظ بسجلات المدفوعات.",
              ],
            },
          ],
        },
        {
          id: "browser",
          title: "ما نحفظه في متصفحك",
          blocks: [
            "نحفظ في متصفحك جلسة الدخول وتفضيلاتك (اللغة، المظهر، مساحة العمل الحالية، واختيارك بشأن Google Analytics) لتعمل الخدمة. لا نستخدم ملفات تعريف ارتباط إعلانية.",
          ],
        },
        {
          id: "website-analytics",
          title: "إحصاءات الموقع",
          blocks: [
            "على موقعنا (allmizan.live) نعدّ الزيارات بأنفسنا: عندما تفتح صفحة، أو تضغط على واتساب أو الاتصال، أو ترسل طلبًا، أو تبدأ التسجيل، يُضاف واحد إلى عدّاد يومي لتلك الصفحة ولغتها، ومعه اسم الموقع الذي جئت منه إن وُجد. لا نستخدم لذلك أي ملف تعريف ارتباط، ولا نحفظ عنوان IP ولا نوع المتصفح ولا أي معرّف لك، فلا يمكن ربط العدّاد بك.",
            "Google Analytics 4: لا يُحمَّل إلا إذا وافقت عليه في الشريط الذي يظهر على الموقع. عندها يضع ملفات تعريف ارتباط من Google ويرسل إليها بيانات استخدامك للموقع (الصفحات التي تفتحها، ونوع الجهاز والمتصفح، والموقع الجغرافي التقريبي) لنفهم كيف يُستخدم الموقع، وقد تُعالج خارج مصر. لا نستخدمه للإعلانات. يمكنك سحب موافقتك في أي وقت من «إعدادات الإحصاءات» أسفل الموقع. لا يعمل Google Analytics داخل النظام ولا في لوحة المالك.",
          ],
        },
        {
          id: "sharing",
          title: "مع من نشاركها",
          blocks: [
            "لا نبيع بياناتك ولا نؤجرها. نشاركها فقط مع مزودي الخدمة الذين نحتاجهم لتشغيل ميزان، وبالقدر اللازم:",
            {
              list: [
                "الاستضافة: خوادمنا الخاصة. الشبكة وحماية الاتصال والنسخ الاحتياطية المشفرة خارج الموقع: Cloudflare.",
                "الدفع: Paymob.",
                "الإشعارات على الأجهزة (عند تفعيلها): Google Firebase.",
                "إرسال البريد الإلكتروني (عند تفعيله): مزود بريد إلكتروني.",
                "إيصالات واتساب (إذا فعّلتها لمنشأتك): Meta (WhatsApp Business).",
                "إحصاءات الموقع (بموافقتك فقط): Google Analytics.",
              ],
            },
            "وقد نفصح عن بيانات إذا ألزمنا القانون أو جهة قضائية مختصة بذلك.",
          ],
        },
        {
          id: "location",
          title: "أين تُحفظ",
          blocks: [
            "على السحابة، تُحفظ البيانات في مراكز بيانات مزودي الاستضافة، وقد تكون خارج مصر، مع ضمانات حماية مناسبة. وعند التشغيل على جهاز أو شبكة داخل منشأتك، تبقى بيانات أعمالك على أجهزتك.",
          ],
        },
        {
          id: "retention",
          title: "مدة الاحتفاظ",
          blocks: [
            "نحتفظ بالبيانات طوال فترة نشاط حسابك. عند طلب الإغلاق نحذف بيانات مساحة العمل خلال 30 يومًا، وتُستبدل النسخ الاحتياطية تلقائيًا بعد ذلك، ونحتفظ بسجلات المدفوعات والفواتير المدة التي يفرضها القانون.",
          ],
        },
        {
          id: "security",
          title: "كيف نحميها",
          blocks: [
            {
              list: [
                "اتصال مشفر (HTTPS) في كل الخدمات.",
                "عزل بيانات كل منشأة عن غيرها داخل قاعدة البيانات نفسها.",
                "كلمات مرور مشفرة، وصلاحيات دقيقة لكل مستخدم، وسجل بالعمليات المهمة.",
              ],
            },
            "لا يوجد نظام آمن تمامًا؛ وإذا وقع حادث يمس بياناتك سنخطرك وفق ما يقتضيه القانون.",
          ],
        },
        {
          id: "rights",
          title: "حقوقك",
          blocks: [
            "يحق لك طلب الاطلاع على بياناتك الشخصية أو تصحيحها أو حذفها أو الحصول على نسخة منها، والاعتراض على معالجتها. تواصل معنا وسنرد خلال 30 يومًا.",
          ],
        },
        {
          id: "your-customers",
          title: "بيانات عملائك وموظفيك",
          blocks: [
            "البيانات الشخصية التي تدخلها عن عملائك وموظفيك تكون أنت مسؤولًا عنها، ونعالجها نحن نيابة عنك ووفق تعليماتك فقط لتقديم الخدمة.",
          ],
        },
        {
          id: "children",
          title: "القُصّر",
          blocks: ["الخدمة غير موجهة لمن هم دون 18 عامًا، ولا نجمع بياناتهم عن قصد."],
        },
        {
          id: "changes",
          title: "تعديل السياسة",
          blocks: ["قد نحدّث هذه السياسة، ونعلن عن التغييرات المهمة على الموقع أو في لوحة المالك."],
        },
        { id: "contact", title: "التواصل", blocks: [contactAr] },
      ],
    },
    en: {
      title: "Privacy Policy",
      description: "What data we collect, why, who we share it with, and how you control it.",
      summary: [
        "We don't sell your data, and we use no advertising tools.",
        "We count visits to our website ourselves, without cookies; Google Analytics runs only if you agree to it.",
        "Your business data is yours; we process it only to provide the service.",
        "We never receive your card details; Paymob processes them.",
      ],
      sections: [
        {
          id: "controller",
          title: "Who is responsible for your data",
          blocks: [
            `${B.seller.en} (${B.sellerType.en}), ${B.city.en}, who operates Mizan. We comply with Egypt's Personal Data Protection Law No. 151 of 2020.`,
          ],
        },
        {
          id: "collect",
          title: "What we collect",
          blocks: [
            {
              list: [
                "Account data: name, username, mobile number, email (if you give one), and your password, stored hashed so it can't be read.",
                "Your business data that you enter: customers, suppliers, products, invoices, employees and so on.",
                "Payment data: Paymob's transaction reference, the amount and its status. We never receive card numbers.",
                "Technical data: IP address, browser type, and sign-in and error logs, for security and troubleshooting.",
                "When running on a computer or network: when online, the software sends its installation id, computer name, operating system, version, IP address and the time of the last backup, to renew the licence. It sends none of your business data.",
              ],
            },
          ],
        },
        {
          id: "use",
          title: "Why we use it",
          blocks: [
            {
              list: [
                "To provide the service and run your account and workspaces.",
                "To invoice, and to activate subscriptions and licences.",
                "For support, and to contact you about your account.",
                "To protect the service and prevent fraud and abuse.",
                "To meet legal obligations, such as keeping payment records.",
              ],
            },
          ],
        },
        {
          id: "browser",
          title: "What we store in your browser",
          blocks: [
            "We store your sign-in session and preferences (language, appearance, current workspace, and your choice about Google Analytics) in your browser so the service works. We use no advertising cookies.",
          ],
        },
        {
          id: "website-analytics",
          title: "Website analytics",
          blocks: [
            "On our website (allmizan.live) we count visits ourselves: when you open a page, tap WhatsApp or call, send a request, or start signing up, one is added to a daily counter for that page and its language, with the name of the site you came from, if any. No cookie is used for this, and we store no IP address, no browser details and no identifier, so the counts can't be linked to you.",
            "Google Analytics 4: it loads only if you accept it in the banner on the website. It then sets Google cookies and sends Google data about how you use the site (the pages you open, your device and browser type, your approximate location) so we can understand how the site is used; this may be processed outside Egypt. We don't use it for advertising. You can withdraw your consent at any time from \"Analytics settings\" at the bottom of the website. Google Analytics never runs inside the system or the owner panel.",
          ],
        },
        {
          id: "sharing",
          title: "Who we share it with",
          blocks: [
            "We don't sell or rent your data. We share it only with the providers we need to run Mizan, and only as needed:",
            {
              list: [
                "Hosting: our own servers. Network, connection protection and encrypted off-site backups: Cloudflare.",
                "Payments: Paymob.",
                "Device notifications (when enabled): Google Firebase.",
                "Email delivery (when enabled): an email provider.",
                "WhatsApp receipts (if you turn them on for your business): Meta (WhatsApp Business).",
                "Website analytics (only with your consent): Google Analytics.",
              ],
            },
            "We may disclose data where the law or a competent court requires it.",
          ],
        },
        {
          id: "location",
          title: "Where it's stored",
          blocks: [
            "In the cloud, data is stored in our hosting providers' data centres, which may be outside Egypt, with appropriate safeguards. When running on a computer or network at your business, your business data stays on your devices.",
          ],
        },
        {
          id: "retention",
          title: "How long we keep it",
          blocks: [
            "We keep data while your account is active. If you ask us to close it, we delete the workspace's data within 30 days, backups are overwritten after that, and we keep payment records and invoices for as long as the law requires.",
          ],
        },
        {
          id: "security",
          title: "How we protect it",
          blocks: [
            {
              list: [
                "Encrypted connections (HTTPS) everywhere.",
                "Each business's data isolated from every other's inside the database.",
                "Hashed passwords, fine-grained permissions per user, and a log of important actions.",
              ],
            },
            "No system is perfectly secure; if an incident affects your data, we will notify you as the law requires.",
          ],
        },
        {
          id: "rights",
          title: "Your rights",
          blocks: [
            "You may ask to access, correct or delete your personal data, to receive a copy, or to object to its processing. Contact us and we'll reply within 30 days.",
          ],
        },
        {
          id: "your-customers",
          title: "Your customers' and employees' data",
          blocks: [
            "You are responsible for the personal data you enter about your customers and employees; we process it on your behalf and only on your instructions, to provide the service.",
          ],
        },
        {
          id: "children",
          title: "Minors",
          blocks: ["The service isn't meant for anyone under 18, and we don't knowingly collect their data."],
        },
        {
          id: "changes",
          title: "Changes to this policy",
          blocks: ["We may update this policy and will announce important changes on the website or in the owner panel."],
        },
        { id: "contact", title: "Contact", blocks: [contactEn] },
      ],
    },
  },

  // ─── Refund Policy ──────────────────────────────────────────────────────
  "refund-policy": {
    ar: {
      title: "سياسة الاسترداد والإلغاء",
      description: "متى يمكنك استرداد ما دفعته، وكيف تلغي، وكم يستغرق رد المبلغ.",
      summary: [
        "جرّب مجانًا 14 يومًا قبل أن تدفع أي شيء.",
        "استرداد كامل لأول دفعة اشتراك لمساحة العمل إذا طلبته خلال 14 يومًا منها.",
        "لا نخصم أي مبلغ تلقائيًا؛ للإلغاء يكفي ألا تجدد.",
      ],
      sections: [
        {
          id: "trial",
          title: "جرّب قبل أن تدفع",
          blocks: ["كل مساحة عمل تبدأ بتجربة مجانية لمدة 14 يومًا دون أي دفع، لتتأكد أن ميزان مناسب لك قبل الاشتراك."],
        },
        {
          id: "first-payment",
          title: "استرداد أول دفعة خلال 14 يومًا",
          blocks: [
            "إذا اشتركت ثم وجدت أن الخدمة لا تناسبك، نرد لك المبلغ كاملًا إذا طلبت ذلك خلال 14 يومًا من أول دفعة اشتراك لمساحة العمل، شهرية كانت أو سنوية.",
            "ينطبق ذلك مرة واحدة لكل مساحة عمل، على أول دفعة فقط.",
          ],
        },
        {
          id: "not-refundable",
          title: "ما لا يُسترد",
          blocks: [
            {
              list: [
                "دفعات تجديد الاشتراك للمدد التالية.",
                "أول دفعة إذا مر على دفعها أكثر من 14 يومًا.",
                "الجزء غير المستخدم من مدة مدفوعة عند التوقف في منتصفها.",
                "الدفعات عند الانتقال إلى باقة أخرى، إلا إذا كانت أول دفعة وطُلب استردادها خلال 14 يومًا.",
              ],
            },
          ],
        },
        {
          id: "errors",
          title: "الدفع المكرر أو الخاطئ",
          blocks: [
            "إذا خُصم منك المبلغ مرتين، أو خُصم ولم يتفعل اشتراكك، نرد المبلغ الزائد أو نفعّل الاشتراك فور التحقق، أيًا كان وقت الطلب.",
          ],
        },
        {
          id: "cancel",
          title: "كيف تلغي",
          blocks: [
            "لا يوجد تجديد تلقائي ولا نحفظ وسيلة دفعك، فلا حاجة لخطوة إلغاء: يكفي ألا تدفع المدة التالية. يستمر وصولك الكامل حتى نهاية المدة المدفوعة، ثم تصبح مساحة العمل للعرض فقط مع بقاء بياناتك.",
          ],
        },
        {
          id: "request",
          title: "كيف تطلب الاسترداد",
          blocks: [
            `راسلنا على واتساب أو اتصل بنا على ${B.phoneDisplay}، واذكر اسم مساحة العمل ورقم الموبايل المسجل ورقم الفاتورة أو عملية الدفع. نرد على الطلب خلال 3 أيام عمل.`,
          ],
        },
        {
          id: "timing",
          title: "متى يصلك المبلغ",
          blocks: [
            "يُرد المبلغ إلى وسيلة الدفع نفسها عبر Paymob. يصل عادة خلال 7 إلى 14 يوم عمل للبطاقات حسب البنك، وأسرع غالبًا للمحافظ الإلكترونية.",
            "عند الاسترداد ينتهي الاشتراك المدفوع وتصبح مساحة العمل للعرض فقط. ويسري الأمر نفسه على مساحات العمل المثبتة على جهاز أو شبكة: ينتهي الترخيص المدفوع.",
          ],
        },
        { id: "contact", title: "التواصل", blocks: [contactAr] },
      ],
    },
    en: {
      title: "Refund & Cancellation Policy",
      description: "When you can get your money back, how to cancel, and how long a refund takes.",
      summary: [
        "Try it free for 14 days before you pay anything.",
        "A full refund of a workspace's first subscription payment if you ask within 14 days of it.",
        "We never charge automatically; to cancel, just don't renew.",
      ],
      sections: [
        {
          id: "trial",
          title: "Try before you pay",
          blocks: ["Every workspace starts with a free 14-day trial, without payment, so you can be sure Mizan suits you before subscribing."],
        },
        {
          id: "first-payment",
          title: "Refund of the first payment within 14 days",
          blocks: [
            "If you subscribe and find the service isn't right for you, we refund the full amount if you ask within 14 days of a workspace's first subscription payment, monthly or annual.",
            "This applies once per workspace, to the first payment only.",
          ],
        },
        {
          id: "not-refundable",
          title: "What isn't refundable",
          blocks: [
            {
              list: [
                "Renewal payments for later periods.",
                "A first payment made more than 14 days ago.",
                "The unused part of a paid period when you stop partway through.",
                "Payments for moving to another plan, unless it's the first payment and the refund is requested within 14 days.",
              ],
            },
          ],
        },
        {
          id: "errors",
          title: "Duplicate or failed charges",
          blocks: [
            "If you were charged twice, or charged without your subscription being activated, we refund the extra amount or activate the subscription as soon as we've checked, whenever you ask.",
          ],
        },
        {
          id: "cancel",
          title: "How to cancel",
          blocks: [
            "Nothing renews automatically and we don't keep your payment method, so there's no cancellation step: just don't pay for the next period. You keep full access until the end of the period you paid for; then the workspace becomes read-only, with your data kept.",
          ],
        },
        {
          id: "request",
          title: "How to ask for a refund",
          blocks: [
            `Message us on WhatsApp or call ${B.phoneDisplay} with the workspace name, your registered mobile number and the invoice or payment reference. We answer within 3 business days.`,
          ],
        },
        {
          id: "timing",
          title: "When you get the money",
          blocks: [
            "Refunds go back to the same payment method through Paymob. Card refunds usually arrive within 7–14 business days depending on your bank; mobile wallets are usually faster.",
            "A refund ends the paid subscription and the workspace becomes read-only. The same applies to workspaces installed on a computer or network: the paid licence ends.",
          ],
        },
        { id: "contact", title: "Contact", blocks: [contactEn] },
      ],
    },
  },
};
