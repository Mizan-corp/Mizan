/**
 * PAGE CONTRACT
 * Page: الموارد البشرية (/hr)
 * User: مدير الموارد البشرية والمحاسب (صلاحية payroll)
 * Purpose: الموظفون (إضافة وتعديل وإيقاف)، الحضور (يدوي واستيراد ملف البصمة وتقريره)، السلف والخصومات
 * والمكافآت، الورديات، إعدادات الرواتب، وسجل التدقيق. حساب الرواتب واعتمادها وصرفها في /hr/payroll.
 */
import { useSearchParams } from "react-router-dom";
import { CalendarClock, Clock, HandCoins, ScrollText, Settings2, Users } from "lucide-react";
import { AdvancesTab } from "./components/AdvancesTab";
import { AttendanceTab } from "./components/AttendanceTab";
import { AuditTab } from "./components/AuditTab";
import { EmployeesTab } from "./components/EmployeesTab";
import { SettingsTab } from "./components/SettingsTab";
import { ShiftsTab } from "./components/ShiftsTab";

const TABS = [
  { key: "employees", label: "الموظفون", icon: Users },
  { key: "attendance", label: "الحضور", icon: CalendarClock },
  { key: "advances", label: "السلف والخصومات", icon: HandCoins },
  { key: "shifts", label: "الورديات", icon: Clock },
  { key: "settings", label: "إعدادات الرواتب", icon: Settings2 },
  { key: "audit", label: "سجل التدقيق", icon: ScrollText },
] as const;
type Tab = (typeof TABS)[number]["key"];

export default function HrPage() {
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((t) => t.key === params.get("tab"))?.key ?? "employees") as Tab;
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">الموارد البشرية</h1>
        <p className="mt-0.5 text-xs text-muted">الموظفون والحضور والسلف والورديات وقواعد حساب الرواتب.</p>
      </div>
      <nav className="flex flex-wrap gap-2" role="tablist" aria-label="أقسام الموارد البشرية">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button key={t.key} role="tab" aria-selected={active}
                    onClick={() => setParams((p) => { p.set("tab", t.key); return p; }, { replace: true })}
                    className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                      active ? "bg-primary text-primary-foreground shadow-sm shadow-primary/25" : "border border-line/80 bg-card text-muted hover:bg-elevated hover:text-ink"
                    }`}>
              <Icon className="size-4" /> {t.label}
            </button>
          );
        })}
      </nav>
      {tab === "employees" && <EmployeesTab />}
      {tab === "attendance" && <AttendanceTab />}
      {tab === "advances" && <AdvancesTab />}
      {tab === "shifts" && <ShiftsTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "audit" && <AuditTab />}
    </div>
  );
}
