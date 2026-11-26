// The sales ledgers (reports): a day's products (sold per price, returned) and drawer expenses, and
// the weekly / monthly / yearly summary of sales, returns, expenses and the net.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { date as fmtDate, D, qty as fq } from "@/lib/format";
import { Input, Select } from "@/components/ui";
import { moneyIn, useCurrency } from "@app/lib/currency";
import { ExportButtons, useBranches } from "@activities/general/modules/accounting/components/shared";
import type { Cell } from "@activities/general/modules/accounting/lib";
import type { DailyItems, PeriodRow } from "../api";
import { n } from "../lib";
import { Loading } from "./FinanceReports";

function BranchSelect({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  const branches = useBranches();
  return (
    <Select id={id} className="w-44" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">كل الفروع المتاحة لك</option>
      {branches.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
    </Select>
  );
}

export function DailyItemsView({ day, onDay }: { day: string; onDay: (d: string) => void }) {
  const cur = useCurrency();
  const [branch, setBranch] = useState("");
  const q = useQuery({
    queryKey: ["rep-daily-items", day, branch],
    queryFn: () => api.get<DailyItems>("/reports/ledger/daily-items", { target_date: day, warehouse_id: branch || undefined }),
    enabled: !!day,
  });
  const totals = (d: DailyItems) => ({
    sold: d.items.reduce((s, i) => s.plus(D(i.total)), D(0)),
    returned: d.items.reduce((s, i) => s.plus(D(i.returns)), D(0)),
    expenses: d.expenses.reduce((s, e) => s.plus(D(e.total)), D(0)),
  });
  const exportRows: Cell[][] = (q.data?.items ?? []).map((i) => [i.name, i.unit ?? "", n(i.price), i.qty, n(i.total), n(i.returns)]);
  return (
    <section className="flex flex-col gap-4">
      <div className="no-print flex flex-wrap items-end gap-3 rounded-xl border border-line bg-card p-3">
        <div>
          <label htmlFor="di-day" className="mb-1 block text-xs font-medium text-muted">اليوم</label>
          <Input id="di-day" type="date" className="num w-44" value={day} onChange={(e) => onDay(e.target.value)} />
        </div>
        <div>
          <label htmlFor="di-branch" className="mb-1 block text-xs font-medium text-muted">الفرع</label>
          <BranchSelect id="di-branch" value={branch} onChange={setBranch} />
        </div>
      </div>
      <Loading query={q} empty={(d) => !d.items.length && !d.expenses.length} emptyText="لا مبيعات ولا مصروفات في هذا اليوم">
        {(d) => {
          const t = totals(d);
          return (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-muted">
                  المبيعات <span className="num font-semibold text-ink">{moneyIn(t.sold, cur)}</span> · المرتجعات{" "}
                  <span className="num font-semibold text-ink">{moneyIn(t.returned, cur)}</span> · مصروفات الأدراج{" "}
                  <span className="num font-semibold text-ink">{moneyIn(t.expenses, cur)}</span> · الصافي{" "}
                  <span className="num font-semibold text-ink">{moneyIn(t.sold.minus(t.returned).minus(t.expenses), cur)}</span>
                  {" "}(بعد الخصومات وبدون الضريبة)
                </p>
                <ExportButtons filename={`daily-items-${day}`} title="دفتر اليوم — الأصناف" subtitle={fmtDate(day)}
                               columns={["الصنف", "الوحدة", "السعر", "الكمية", "الإجمالي", "المرتجع"]} rows={exportRows} />
              </div>
              {d.items.length > 0 && (
                <div className="overflow-x-auto rounded-xl border border-line bg-card">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line text-xs text-muted">
                        <th className="p-2.5 text-start">الصنف</th>
                        <th className="p-2.5 text-end">السعر</th>
                        <th className="p-2.5 text-end">الكمية</th>
                        <th className="p-2.5 text-end">الإجمالي</th>
                        <th className="p-2.5 text-end">المرتجع</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.items.map((i, k) => (
                        <tr key={`${i.product_id}-${k}`} className="border-b border-line/60 last:border-0">
                          <td className="p-2.5 font-semibold">{i.name}</td>
                          <td className="num p-2.5 text-end">{moneyIn(i.price, cur)}</td>
                          <td className="num p-2.5 text-end">{fq(i.qty)} {i.unit ?? ""}</td>
                          <td className="num p-2.5 text-end">{moneyIn(i.total, cur)}</td>
                          <td className="num p-2.5 text-end">{D(i.returns).isZero() ? "" : moneyIn(i.returns, cur)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {d.expenses.length > 0 && (
                <>
                  <h3 className="text-sm font-bold">مصروفات الأدراج</h3>
                  <div className="overflow-x-auto rounded-xl border border-line bg-card">
                    <table className="w-full text-sm">
                      <tbody>
                        {d.expenses.map((e, k) => (
                          <tr key={k} className="border-b border-line/60 last:border-0">
                            <td className="p-2.5">{e.note}</td>
                            <td className="num p-2.5 text-end">{moneyIn(e.total, cur)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </>
          );
        }}
      </Loading>
    </section>
  );
}

const PERIOD_LABEL = { weekly: "أسبوعي", monthly: "شهري", yearly: "سنوي" } as const;

export function PeriodicLedgerView() {
  const cur = useCurrency();
  const [period, setPeriod] = useState<keyof typeof PERIOD_LABEL>("monthly");
  const [branch, setBranch] = useState("");
  const q = useQuery({
    queryKey: ["rep-periodic", period, branch],
    queryFn: () => api.get<PeriodRow[]>("/reports/ledger/periodic", { period, warehouse_id: branch || undefined }),
  });
  const rows: Cell[][] = (q.data ?? []).map((r) => [r.period, n(r.income), n(r.returns), n(r.expenses), n(r.net)]);
  return (
    <section className="flex flex-col gap-4">
      <div className="no-print flex flex-wrap items-end gap-3 rounded-xl border border-line bg-card p-3">
        <div>
          <label htmlFor="pl-period" className="mb-1 block text-xs font-medium text-muted">التجميع</label>
          <Select id="pl-period" className="w-32" value={period} onChange={(e) => setPeriod(e.target.value as typeof period)}>
            {Object.entries(PERIOD_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </div>
        <div>
          <label htmlFor="pl-branch" className="mb-1 block text-xs font-medium text-muted">الفرع</label>
          <BranchSelect id="pl-branch" value={branch} onChange={setBranch} />
        </div>
      </div>
      <Loading query={q} empty={(d) => !d.length} emptyText="لا حركة في آخر 52 فترة">
        {(d) => (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted">آخر 52 فترة، الأحدث أولاً. المبيعات والمرتجعات بعد الخصومات وبدون الضريبة؛ المصروفات: المعتمدة ومصروفات الأدراج.</p>
              <ExportButtons filename={`periodic-${period}`} title={`الدفتر الدوري — ${PERIOD_LABEL[period]}`} subtitle=""
                             columns={["الفترة", "المبيعات", "المرتجعات", "المصروفات", "الصافي"]} rows={rows} />
            </div>
            <div className="overflow-x-auto rounded-xl border border-line bg-card">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-muted">
                    <th className="p-2.5 text-start">الفترة</th>
                    <th className="p-2.5 text-end">المبيعات</th>
                    <th className="p-2.5 text-end">المرتجعات</th>
                    <th className="p-2.5 text-end">المصروفات</th>
                    <th className="p-2.5 text-end">الصافي</th>
                  </tr>
                </thead>
                <tbody>
                  {d.map((r) => (
                    <tr key={r.period} className="border-b border-line/60 last:border-0">
                      <td className="num p-2.5" dir="ltr">{r.period}</td>
                      <td className="num p-2.5 text-end">{moneyIn(r.income, cur)}</td>
                      <td className="num p-2.5 text-end">{moneyIn(r.returns, cur)}</td>
                      <td className="num p-2.5 text-end">{moneyIn(r.expenses, cur)}</td>
                      <td className={`num p-2.5 text-end font-semibold ${D(r.net).lt(0) ? "text-destructive" : ""}`}>{moneyIn(r.net, cur)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Loading>
    </section>
  );
}
