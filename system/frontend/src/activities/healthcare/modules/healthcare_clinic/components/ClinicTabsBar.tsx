import type { ReactNode } from "react";
import { Bed, Calendar, CalendarClock, FileText, HeartPulse, Lock, Pill, Search, ShieldCheck, Users } from "lucide-react";
import { Input } from "@/components/kit/input";
import { useClinic } from "../ClinicContext";
import type { ClinicTab } from "../types";

function TabButton({ id, icon, children }: { id: ClinicTab; icon: ReactNode; children: ReactNode }) {
  const { tab, handleTabChange } = useClinic();
  const active = tab === id;
  return (
    <button
      onClick={() => handleTabChange(id)}
      aria-current={active ? "page" : undefined}
      className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
        active
          ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
          : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
      }`}
    >
      {icon}
      {children}
    </button>
  );
}

const Count = ({ n }: { n: number }) => <>(<span className="num">{n}</span>)</>;

// The clinic's ledger tabs and the search box (?tab= in the URL).
export default function ClinicTabsBar({ onSearch }: { onSearch: (value: string) => void }) {
  const { perms, data, search } = useClinic();
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/70 pb-1">
      <div className="flex flex-wrap items-center gap-1">
        <TabButton id="appointments" icon={<Calendar className="size-3.5" />}>
          الكشوفات والانتظار <Count n={data.appointmentsTotal} />
        </TabButton>
        <TabButton id="patients" icon={<Users className="size-3.5" />}>
          سجلات المرضى (EMR) <Count n={data.patientsTotal} />
        </TabButton>
        <TabButton id="emr" icon={<HeartPulse className="size-3.5" />}>
          الكشوفات السريرية <Count n={data.encounters.length} />
        </TabButton>
        <TabButton id="rx_labs" icon={<Pill className="size-3.5" />}>
          الروشتات والتحاليل <Count n={data.prescriptions.length + data.labOrders.length} />
        </TabButton>
        <TabButton id="beds" icon={<Bed className="size-3.5" />}>
          أسرّة التنويم <Count n={data.beds.length} />
        </TabButton>
        {perms.billing && (
          <TabButton id="billing" icon={<FileText className="size-3.5" />}>
            الفواتير والتحصيل <Count n={data.invoices.length} />
          </TabButton>
        )}
        {perms.manage && (
          <TabButton id="scheduling" icon={<CalendarClock className="size-3.5" />}>
            الأقسام والجداول
          </TabButton>
        )}
        {perms.privacy && (
          <TabButton id="privacy" icon={<Lock className="size-3.5" />}>
            الخصوصية والوصول
          </TabButton>
        )}
        {perms.billing && (
          <TabButton id="claims" icon={<ShieldCheck className="size-3.5" />}>
            مطالبات التأمين <Count n={data.claims.length} />
          </TabButton>
        )}
      </div>

      <div className="relative w-full sm:w-64">
        <Search className="size-4 absolute right-3 top-2.5 text-muted-foreground" />
        <Input
          placeholder="بحث بالمريض، الطبيب، أو الكود..."
          aria-label="بحث"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          className="pr-9 h-9 text-xs"
        />
      </div>
    </div>
  );
}
