import { AlertTriangle } from "lucide-react";

/** The desktop app was opened but the local Mizan server isn't answering. */
export default function NotRunning() {
  return (
    <div className="flex h-full flex-col justify-center px-10">
      <AlertTriangle className="mb-4 size-9 text-warn" />
      <h1 className="text-xl font-bold text-ink">ميزان لا يعمل الآن على هذا الجهاز</h1>
      <p className="mt-2 text-[15px] leading-7 text-ink-2">
        خدمة ميزان متوقفة. أعد تشغيل الجهاز، أو شغّلها من سطر الأوامر: <span className="code text-sm">mizan-server start</span>. إذا تكرر ذلك، تواصل مع
        الدعم.
      </p>
      <button onClick={() => window.close()} className="mt-6 self-start rounded-xl bg-wine px-5 py-2.5 text-sm font-semibold text-paper">
        إغلاق
      </button>
    </div>
  );
}
