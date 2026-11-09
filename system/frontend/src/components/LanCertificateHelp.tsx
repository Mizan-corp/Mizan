import { useQuery } from "@tanstack/react-query";
import { Download, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { IS_ON_PREMISE } from "@app/lib/deployment";

const STEPS: { device: string; steps: string }[] = [
  {
    device: "ويندوز",
    steps: "افتح الملف ← «تثبيت الشهادة» ← «الجهاز المحلي» ← «وضع كل الشهادات في المخزن التالي» ← «جهات الترقيم المصدق الجذر الموثوق بها» ← إنهاء، ثم أعد فتح المتصفح.",
  },
  {
    device: "أندرويد",
    steps: "الإعدادات ← الأمان ← «التشفير وبيانات الاعتماد» ← «تثبيت شهادة» ← «شهادة CA» ← اختر الملف.",
  },
  {
    device: "آيفون وآيباد",
    steps: "افتح الملف ← الإعدادات ← «تم تنزيل ملف التعريف» ← تثبيت. ثم: عام ← حول ← «إعدادات الثقة بالشهادات» ← فعّل «Mizan local network».",
  },
];

/**
 * LAN installs, on the sign-in page: each till installs the server's certificate
 * once, so the browser trusts https://mizan.local and the offline sale queue works.
 */
export function LanCertificateHelp() {
  const q = useQuery({
    queryKey: ["onprem-status"],
    queryFn: () => api.get<{ ca_certificate?: boolean }>("/onprem/status"),
    enabled: IS_ON_PREMISE,
    staleTime: 10 * 60_000,
  });
  if (!IS_ON_PREMISE || !q.data?.ca_certificate) return null;

  return (
    <details className="group pt-4 border-t border-[#E6DCD2] text-xs text-[#4D4744]">
      <summary className="flex cursor-pointer list-none items-center justify-center gap-1.5 font-semibold text-[#651E2C] hover:underline">
        <ShieldCheck className="h-3.5 w-3.5" />
        أول مرة على هذا الجهاز؟ ثبّت شهادة الأمان
      </summary>
      <div className="mt-3 space-y-2.5 rounded-2xl bg-[#FAF6F0] border border-[#DECFC0] p-3.5 leading-relaxed">
        <p>مرة واحدة لكل جهاز كاشير أو مكتب: تجعل المتصفح يثق بخادم ميزان، فيعمل البيع حتى أثناء انقطاع الشبكة.</p>
        <a
          href="/api/onprem/ca.crt"
          download="mizan-ca.crt"
          className="inline-flex items-center gap-1.5 rounded-xl bg-[#651E2C] px-3 py-1.5 font-semibold text-white hover:bg-[#521723]"
        >
          <Download className="h-3.5 w-3.5" /> تنزيل شهادة الأمان
        </a>
        <dl className="space-y-1.5">
          {STEPS.map((s) => (
            <div key={s.device}>
              <dt className="font-semibold text-[#262321]">{s.device}</dt>
              <dd>{s.steps}</dd>
            </div>
          ))}
        </dl>
      </div>
    </details>
  );
}
