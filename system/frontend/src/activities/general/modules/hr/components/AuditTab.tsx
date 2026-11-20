// The HR audit log: salary changes, payroll entry adjustments, advances added, cancelled and
// carried; newest first, paged.
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { Badge, Empty, ErrorBox, Select } from "@/components/ui";
import { pageCount } from "../../finance/lib";
import { AUDIT_ACTION, AUDIT_ENTITY, type Paged } from "../lib";
import { Pager, Rows } from "./common";

interface AuditRow {
  id: string; action_type: string; entity_type: string; entity_id: string | null; reason: string | null;
  details: Record<string, unknown> | null; created_at: string | null; performed_by_name: string | null; employee_name: string | null;
}

const PAGE_SIZE = 50;
const FIELD: Record<string, string> = {
  monthly_salary: "الراتب", bonus: "المكافأة", deductions: "الخصومات", drawer_variance: "فرق الدرج", net_salary: "الصافي",
  amount: "المبلغ", type: "النوع", month: "الشهر", from: "من شهر", to: "إلى شهر",
};

/** "الراتب: 2600 ← 3000 · المبلغ: 500" from the details the server logged. */
function describe(details: Record<string, unknown> | null): string {
  if (!details) return "";
  return Object.entries(details)
    .filter(([k]) => k in FIELD)
    .map(([k, v]) => {
      if (v && typeof v === "object" && "from" in v && "to" in v) {
        const c = v as { from: unknown; to: unknown };
        return `${FIELD[k]}: ${String(c.from)} ← ${String(c.to)}`;
      }
      return `${FIELD[k]}: ${String(v)}`;
    })
    .join(" · ");
}

export function AuditTab() {
  const [entity, setEntity] = useState("");
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["hr-audit", entity, page],
    queryFn: () => api.get<Paged<AuditRow>>("/hr/audit-log", { entity_type: entity || undefined, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
  const rows = q.data?.items ?? [];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end gap-3">
        <div>
          <label htmlFor="audit-entity" className="mb-1 block text-xs font-medium text-muted">النوع</label>
          <Select id="audit-entity" className="w-52" value={entity} onChange={(e) => { setEntity(e.target.value); setPage(1); }}>
            <option value="">الكل</option>
            {Object.entries(AUDIT_ENTITY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </div>
      </div>
      {q.isLoading ? <Rows /> : q.isError ? (
        <ErrorBox message={(q.error as Error).message} onRetry={() => q.refetch()} />
      ) : !rows.length ? (
        <Empty text="لا توجد حركات في سجل التدقيق" icon={<ScrollText className="size-10" />} />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="p-3 text-start">الوقت</th>
                  <th className="p-3 text-start">العملية</th>
                  <th className="p-3 text-start">الموظف</th>
                  <th className="p-3 text-start">التفاصيل</th>
                  <th className="p-3 text-start">بواسطة</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-line/60 last:border-0">
                    <td className="p-3 text-xs text-muted whitespace-nowrap">{dateTime(r.created_at)}</td>
                    <td className="p-3"><Badge tone="muted">{AUDIT_ACTION[r.action_type] ?? r.action_type}</Badge> <span className="text-xs">{AUDIT_ENTITY[r.entity_type] ?? r.entity_type}</span></td>
                    <td className="p-3 text-xs">{r.employee_name ?? "—"}</td>
                    <td className="p-3 text-xs text-muted">{[r.reason, describe(r.details)].filter(Boolean).join(" — ") || "—"}</td>
                    <td className="p-3 text-xs">{r.performed_by_name ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pages={pageCount(q.data?.total ?? 0, PAGE_SIZE)} total={q.data?.total ?? 0} unit="حركة" busy={q.isFetching} onPage={setPage} />
        </>
      )}
    </div>
  );
}
