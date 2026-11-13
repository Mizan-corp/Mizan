/** dev.allmizan.live: what developers can build on Mizan, and where to start (ADR-007). */
import { Link } from "react-router-dom";
import { ArrowRight, Blocks, FileCheck2, Webhook } from "lucide-react";
import { DevHeader } from "./DevHeader";
import { SDK_WHEEL } from "./devDocs";
import { useDevI18n } from "./i18n";
import { devPath } from "./paths";

const CODE = `pip install https://dev.allmizan.live/sdk/${SDK_WHEEL}
mizan login
mizan activity new acme.laundry
mizan check acme.laundry
mizan keys new --team acme
mizan package acme.laundry`;

export default function DevHome() {
  const { t, dir } = useDevI18n();
  const steps = [
    { icon: Blocks, title: t("Describe your module", "صِف وحدتك"),
      body: t("Entities, fields, screens and permissions in JSON files. Mizan draws the lists and forms and validates every value.",
              "كيانات وحقول وشاشات وصلاحيات في ملفات JSON. يرسم ميزان القوائم والنماذج ويتحقق من القيم.") },
    { icon: FileCheck2, title: t("Sign it", "وقّعها"),
      body: t("Mizan certifies your team's key, so every install can check the package is yours and unchanged.",
              "مفتاح فريقك يشهد له ميزان، فيتحقق كل تثبيت من أن الحزمة منك ولم تتغير.") },
    { icon: Webhook, title: t("Connect your server", "اربطها بخادمك"),
      body: t("The /ext/v1 API, limited to the scopes the business owner approves, and signed webhooks on sales and more.",
              "واجهة /ext/v1 بنطاقات يوافق عليها صاحب المنشأة، وإشعارات موقّعة عند البيع وغيره.") },
  ];
  return (
    <div dir={dir} className="min-h-screen bg-[#FAF6F0] font-body text-[#262321]">
      <DevHeader />
      <main className="mx-auto max-w-6xl space-y-16 px-4 py-14 sm:px-6">
        <section className="grid items-center gap-10 lg:grid-cols-2">
          <div className="space-y-5">
            <h1 className="font-display text-4xl leading-tight tracking-tight sm:text-5xl">{t("Build on Mizan", "ابنِ على ميزان")}</h1>
            <p className="max-w-xl text-sm leading-relaxed text-[#77716E] sm:text-base">
              {t("Build a whole business activity with the framework Mizan's own are built on: its modules, how it adapts Mizan's POS, stock and sales, its menus and roles, its look and its demo data. Or build single modules and theme packs that businesses install after approving what they can access.",
                 "ابنِ نشاطًا تجاريًا كاملًا بالإطار الذي بُنيت به أنشطة ميزان نفسها: وحداته، وكيف يكيّف نقطة البيع والمخزون والمبيعات، وقوائمه وأدواره، ومظهره وبياناته التجريبية. أو ابنِ وحدات ومظاهر مفردة تُثبّتها المنشآت بعد موافقتها على ما تصل إليه.")}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to={devPath("/signup")} className="inline-flex items-center gap-2 rounded-full bg-[#651E2C] px-5 py-2.5 text-sm font-bold text-white shadow-xs hover:bg-[#521723]">
                {t("Create a developer account", "أنشئ حساب مطور")} <ArrowRight className="size-4 rtl:-scale-x-100" />
              </Link>
              <Link to={devPath("/docs/activities")} className="inline-flex items-center rounded-full border border-[#E7D6C1] bg-white px-5 py-2.5 text-sm font-bold text-[#651E2C] hover:border-[#651E2C]">
                {t("Build an activity", "ابنِ نشاطًا")}
              </Link>
              <Link to={devPath("/docs/quickstart")} className="inline-flex items-center rounded-full px-3 py-2.5 text-sm font-bold text-[#651E2C] hover:underline">
                {t("Quickstart", "البدء السريع")}
              </Link>
            </div>
          </div>
          <pre dir="ltr" className="overflow-x-auto rounded-2xl border border-[#35151D] bg-[#270F16] p-5 text-left font-mono text-xs leading-relaxed text-[#FAF6F0] shadow-lg">
            {CODE}
          </pre>
        </section>

        <section aria-labelledby="how" className="space-y-6">
          <h2 id="how" className="font-display text-2xl">{t("How it works", "كيف تعمل")}</h2>
          <ol className="grid gap-5 md:grid-cols-3">
            {steps.map(({ icon: Icon, title, body }, i) => (
              <li key={i} className="space-y-3 rounded-2xl border border-[#E7D6C1] bg-white p-6 shadow-xs">
                <span className="flex items-center gap-2 text-[#651E2C]">
                  <Icon className="size-5" /> <span className="text-xs font-bold">{t(`Step ${i + 1}`, `الخطوة ${i + 1}`)}</span>
                </span>
                <h3 className="font-display text-lg font-bold">{title}</h3>
                <p className="text-sm leading-relaxed text-[#77716E]">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="rounded-2xl border border-[#E7D6C1] bg-white p-6 text-sm leading-relaxed text-[#77716E] shadow-xs">
          <h2 className="mb-2 font-display text-lg font-bold text-[#262321]">{t("Available now", "ما المتاح الآن")}</h2>
          {t("Declarative modules (no code running inside Mizan), installed from a signed file the developer gives the business owner. The module marketplace, paid modules, and modules with code running inside Mizan in isolated containers come next.",
             "الوحدات الوصفية (بلا كود داخل ميزان) تُثبَّت من ملف موقّع يعطيه المطور لصاحب المنشأة. متجر الوحدات والوحدات المدفوعة، ووحدات بكود يعمل داخل ميزان في حاويات معزولة، في المراحل التالية.")}{" "}
          <Link to={devPath("/docs/introduction")} className="font-semibold text-[#651E2C] hover:underline">{t("Details", "التفاصيل")}</Link>
        </section>
      </main>
    </div>
  );
}
