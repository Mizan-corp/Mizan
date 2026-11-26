import { createElement, Suspense } from "react";
import { RefreshCw } from "lucide-react";
import type { HealthcareModule } from "../healthcareModules";

// One of the suite's standalone screens, full width, with a way back to the daily clinic.
export default function StandaloneModuleView({ module, onBack }: { module: HealthcareModule; onBack: () => void }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-border/60">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 text-xs font-semibold text-[#1E3A8A] hover:text-[#0A2540] bg-blue-50/80 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
        >
          ← العودة إلى دفتر العيادات السريعة
        </button>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-mono bg-muted/50 px-2.5 py-0.5 rounded-md">
            {module.code} • {module.title}
          </span>
        </div>
      </div>
      {module.preview && (
        <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900">
          <strong className="font-semibold">معاينة:</strong> هذه الشاشة تعرض بيانات توضيحية، والتعديلات عليها لا تُحفظ بعد.
          إدارة المنشآت والمباني والغرف الفعلية قيد التطوير.
        </div>
      )}
      <Suspense
        fallback={
          <div className="p-16 text-center text-muted-foreground bg-card border border-border rounded-2xl">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-[#1E3A8A]" />
            <p className="text-sm font-medium">جاري تحميل الوحدة الطبية المستقلة...</p>
            <p className="text-xs text-muted-foreground mt-1">تطبيق قواعد العزل الأمني والتكامل المؤسسي</p>
          </div>
        }
      >
        {createElement(module.component)}
      </Suspense>
    </div>
  );
}
