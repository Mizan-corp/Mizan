/** dev.allmizan.live: what developers can build on Mizan, and where to start (ADR-007). */
import { Link } from "react-router-dom";
import { ArrowLeft, Blocks, FileCheck2, Webhook } from "lucide-react";
import { DevHeader } from "./DevHeader";
import { devPath } from "./paths";
import { SDK_WHEEL } from "./devDocs";

const STEPS = [
  { icon: Blocks, title: "صِف وحدتك", body: "كيانات وحقول وشاشات وصلاحيات في ملفات JSON. يرسم ميزان القوائم والنماذج ويتحقق من القيم." },
  { icon: FileCheck2, title: "وقّعها", body: "مفتاح فريقك يشهد له ميزان، فيتحقق كل تثبيت من أن الحزمة منك ولم تتغير." },
  { icon: Webhook, title: "اربطها بخادمك", body: "واجهة /ext/v1 بنطاقات يوافق عليها صاحب المنشأة، وإشعارات موقّعة عند البيع وغيره." },
];

const CODE = `pip install https://dev.allmizan.live/sdk/${SDK_WHEEL}
mizan login
mizan module new acme.visits
mizan check acme.visits
mizan keys new --team acme
mizan package acme.visits`;

export default function DevHome() {
  return (
    <div dir="rtl" className="min-h-screen bg-[#FAF6F0] font-body text-[#262321]">
      <DevHeader />
      <main className="mx-auto max-w-6xl space-y-16 px-4 py-14 sm:px-6">
        <section className="grid items-center gap-10 lg:grid-cols-2">
          <div className="space-y-5">
            <h1 className="font-display text-4xl leading-tight tracking-tight sm:text-5xl">ابنِ على ميزان</h1>
            <p className="max-w-xl text-sm leading-relaxed text-[#77716E] sm:text-base">
              وحدات تضيف سجلات وشاشات جديدة لمنشآت ميزان، وتتصل بخادمك لتفعل ما تحتاجه أعمالها. تُثبَّت في مساحة العمل بموافقة صاحبها على كل ما تصل إليه.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to={devPath("/signup")} className="inline-flex items-center gap-2 rounded-full bg-[#651E2C] px-5 py-2.5 text-sm font-bold text-white shadow-xs hover:bg-[#521723]">
                أنشئ حساب مطور <ArrowLeft className="size-4" />
              </Link>
              <Link to={devPath("/docs/quickstart")} className="inline-flex items-center rounded-full border border-[#E7D6C1] bg-white px-5 py-2.5 text-sm font-bold text-[#651E2C] hover:border-[#651E2C]">
                البدء السريع
              </Link>
            </div>
          </div>
          <pre dir="ltr" className="overflow-x-auto rounded-2xl border border-[#35151D] bg-[#270F16] p-5 text-start font-mono text-xs leading-relaxed text-[#FAF6F0] shadow-lg">
            {CODE}
          </pre>
        </section>

        <section aria-labelledby="how" className="space-y-6">
          <h2 id="how" className="font-display text-2xl">كيف تعمل</h2>
          <ol className="grid gap-5 md:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <li key={title} className="space-y-3 rounded-2xl border border-[#E7D6C1] bg-white p-6 shadow-xs">
                <span className="flex items-center gap-2 text-[#651E2C]">
                  <Icon className="size-5" /> <span className="text-xs font-bold">الخطوة {i + 1}</span>
                </span>
                <h3 className="font-display text-lg font-bold">{title}</h3>
                <p className="text-sm leading-relaxed text-[#77716E]">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="rounded-2xl border border-[#E7D6C1] bg-white p-6 text-sm leading-relaxed text-[#77716E] shadow-xs">
          <h2 className="mb-2 font-display text-lg font-bold text-[#262321]">ما المتاح الآن</h2>
          الوحدات الوصفية (بلا كود داخل ميزان) تُثبَّت من ملف موقّع يعطيه المطور لصاحب المنشأة. متجر الوحدات والوحدات المدفوعة،
          ووحدات بكود يعمل داخل ميزان في حاويات معزولة، في المراحل التالية.{" "}
          <Link to={devPath("/docs/introduction")} className="font-semibold text-[#651E2C] hover:underline">التفاصيل</Link>
        </section>
      </main>
    </div>
  );
}
