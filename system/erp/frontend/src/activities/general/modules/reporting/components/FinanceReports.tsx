// The financial reports (reports:finance): profit, cash flow, debts' aging and the company overview.
// Each has its filters (a date range and a branch where the report takes them), CSV export and print.
import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { date as fmtDate, D } from "@/lib/format";
import { Badge, Empty, ErrorBox, Select } from "@/components/ui";
import { moneyIn, useCurrency } from "@app/lib/currency";
import { ExportButtons, type Range, RangeFilters, SkeletonRows, useBranches } from "@activities/general/modules/accounting/components/shared";
import type { Cell } from "@activities/general/modules/accounting/lib";
import type { AgingReport, AgingSide, CashFlowReport, Overview, ProfitReport } from "../api";
import { agingRows, BUCKET_LABEL, BUCKETS, bucketShare, cashFlowRows, flowLabel, METHOD_LABEL, MONEY_KIND, n, profitRows } from "../lib";

function useSubtitle(range: Range, single = false): string {
  const branches = useBranches();
  const branch = range.warehouse_id ? branches.data?.find((b) => b.id === range.warehouse_id)?.name ?? "" : "كل الفروع المتاحة لك";
  const period = single ? `في ${fmtDate(range.to)}` : `من ${fmtDate(range.from)} إلى ${fmtDate(range.to)}`;
  return `${period} — ${branch}`;
}

export function Loading<T>({ query, empty, emptyText, children }: {
  query: { isLoading: boolean; isError: boolean; error: unknown; refetch: () => unknown; data?: T };
  empty?: (d: T) => boolean; emptyText?: string; children: (d: T) => ReactNode;
}) {
  if (query.isLoading) return <SkeletonRows n={6} />;
  if (query.isError) return <ErrorBox message={(query.error as Error).message} onRetry={() => query.refetch()} />;
  if (query.data === undefined) return null;
  if (empty?.(query.data)) return <Empty text={emptyText ?? "لا توجد بيانات في هذه الفترة"} hint="غيّر الفترة أو الفرع" />;
  return <>{children(query.data)}</>;
}

function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: "neg" | "pos" }) {
  return (
    <div className="rounded-xl border border-line bg-card p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className={`num mt-1 text-xl font-black ${tone === "neg" ? "text-destructive" : ""}`}>{value}</p>
      {hint && <p className="mt-1 text-[11px] text-muted">{hint}</p>}
    </div>
  );
}

const SOURCE_NOTE = {
  ledger: "من القيود المحاسبية (دفتر اليومية)",
  operations: "من المستندات: الفواتير والمرتجعات والمصروفات المعتمدة وحركات الأدراج",
};

// ── profit ─────────────────────────────────────────────────────────────────────────────────

export function ProfitView({ range, onRange }: { range: Range; onRange: (r: Range) => void }) {
  const cur = useCurrency();
  const subtitle = useSubtitle(range);
  const q = useQuery({
    queryKey: ["rep-profit", range],
    queryFn: () => api.get<ProfitReport>("/reports/profit", { from_date: range.from, to_date: range.to, warehouse_id: range.warehouse_id || undefined }),
    enabled: !!range.from && !!range.to,
  });
  const rows = q.data ? profitRows(q.data) : [];
  return (
    <section className="flex flex-col gap-4">
      <RangeFilters value={range} onChange={onRange} />
      <Loading query={q}>
        {(p) => (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted">
                <Badge tone={p.source === "ledger" ? "brand" : "muted"}>{p.source === "ledger" ? "الدفاتر" : "المستندات"}</Badge>{" "}
                {SOURCE_NOTE[p.source]}
                {p.source === "operations" && p.ledger_start ? ` — الدفاتر تبدأ ${fmtDate(p.ledger_start)}، فالفترة قبلها تُحسب من المستندات.` : ""}
                {range.warehouse_id ? " تقرير الفرع لا يشمل مصروفات الشركة العامة." : ""}
              </p>
              <ExportButtons filename="profit" title="تقرير الأرباح" subtitle={subtitle} columns={["البند", "المبلغ"]}
                             rows={rows.map((r) => [r.label, n(r.amount)])} />
            </div>
            <div className="grid gap-3 sm:grid-cols-4">
              <Stat label="صافي المبيعات" value={moneyIn(p.net_revenue, cur)} />
              <Stat label="مجمل الربح" value={moneyIn(p.gross_profit, cur)} hint={`هامش ${p.gross_margin}%`} />
              <Stat label="المصروفات" value={moneyIn(p.total_expenses, cur)} />
              <Stat label={D(p.net_profit).gte(0) ? "صافي الربح" : "صافي الخسارة"} value={moneyIn(p.net_profit, cur)}
                    hint={`هامش ${p.net_margin}%`} tone={D(p.net_profit).lt(0) ? "neg" : undefined} />
            </div>
            <div className="mx-auto w-full max-w-3xl overflow-x-auto rounded-xl border border-line bg-card">
              <table className="w-full text-sm">
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className={`border-b border-line/60 last:border-0 ${r.kind === "result" ? "bg-elevated/60 font-black" : ""}`}>
                      <td className="p-2.5" style={r.kind === "line" ? { paddingInlineStart: "1.75rem" } : undefined}>{r.label}</td>
                      <td className={`num p-2.5 text-end ${D(r.amount).lt(0) ? "text-destructive" : ""}`}>{moneyIn(r.amount, cur)}</td>
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

// ── cash flow ──────────────────────────────────────────────────────────────────────────────

export function CashFlowView({ range, onRange }: { range: Range; onRange: (r: Range) => void }) {
  const cur = useCurrency();
  const subtitle = useSubtitle(range);
  const q = useQuery({
    queryKey: ["rep-cashflow", range],
    queryFn: () => api.get<CashFlowReport>("/reports/cash-flow", { from_date: range.from, to_date: range.to, warehouse_id: range.warehouse_id || undefined }),
    enabled: !!range.from && !!range.to,
  });
  return (
    <section className="flex flex-col gap-4">
      <RangeFilters value={range} onChange={onRange} />
      <Loading query={q} empty={(d) => !d.lines.length && d.opening_balance == null} emptyText="لم تتحرك أموال في هذه الفترة">
        {(cf) => (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-3xl text-xs text-muted">
                <Badge tone={cf.source === "ledger" ? "brand" : "muted"}>{cf.source === "ledger" ? "الدفاتر" : "المستندات"}</Badge>{" "}
                {cf.source === "ledger"
                  ? "حركة حسابات النقدية (الخزائن والبنوك والمحافظ والأدراج) لكل مستند؛ التحويل بين حسابات الشركة نفسها ليس تدفقاً نقدياً ولا يظهر."
                  : "من المستندات: المبيعات المحصلة والتحصيلات والمدفوعات والمصروفات المعتمدة والرواتب المصروفة. تحصيلات العملاء ومدفوعات الموردين والرواتب لا تخص فرعاً."}
              </p>
              <ExportButtons filename="cash-flow" title="التدفق النقدي" subtitle={subtitle} columns={["البند", "وارد", "منصرف", "الصافي"]}
                             rows={cashFlowRows(cf)} />
            </div>
            <div className="grid gap-3 sm:grid-cols-4">
              {cf.opening_balance != null && <Stat label="النقدية أول المدة" value={moneyIn(cf.opening_balance, cur)} />}
              <Stat label="إجمالي الوارد" value={moneyIn(cf.total_in, cur)} />
              <Stat label="إجمالي المنصرف" value={moneyIn(cf.total_out, cur)} />
              <Stat label="صافي التدفق" value={moneyIn(cf.net_cash_flow, cur)} tone={D(cf.net_cash_flow).lt(0) ? "neg" : undefined} />
              {cf.closing_balance != null && <Stat label="النقدية آخر المدة" value={moneyIn(cf.closing_balance, cur)} />}
            </div>
            <div className="overflow-x-auto rounded-xl border border-line bg-card">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-muted">
                    <th className="p-2.5 text-start">البند</th>
                    <th className="p-2.5 text-end">وارد</th>
                    <th className="p-2.5 text-end">منصرف</th>
                    <th className="p-2.5 text-end">الصافي</th>
                  </tr>
                </thead>
                <tbody>
                  {cf.lines.map((l) => (
                    <tr key={l.key} className="border-b border-line/60 last:border-0">
                      <td className="p-2.5">{flowLabel(l.key)}</td>
                      <td className="num p-2.5 text-end">{D(l.in).isZero() ? "" : moneyIn(l.in, cur)}</td>
                      <td className="num p-2.5 text-end">{D(l.out).isZero() ? "" : moneyIn(l.out, cur)}</td>
                      <td className={`num p-2.5 text-end font-semibold ${D(l.net).lt(0) ? "text-destructive" : ""}`}>{moneyIn(l.net, cur)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-line font-black">
                    <td className="p-2.5">الإجمالي</td>
                    <td className="num p-2.5 text-end">{moneyIn(cf.total_in, cur)}</td>
                    <td className="num p-2.5 text-end">{moneyIn(cf.total_out, cur)}</td>
                    <td className="num p-2.5 text-end">{moneyIn(cf.net_cash_flow, cur)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            {cf.sales_by_method && Object.keys(cf.sales_by_method).length > 0 && (
              <p className="text-xs text-muted">
                المبيعات المحصلة حسب طريقة الدفع:{" "}
                {Object.entries(cf.sales_by_method).map(([k, v]) => `${METHOD_LABEL[k] ?? k} ${moneyIn(v, cur)}`).join(" · ")}
              </p>
            )}
            {cf.accounts.length > 0 && (
              <>
                <h3 className="text-sm font-bold">حسب حساب النقدية</h3>
                <div className="overflow-x-auto rounded-xl border border-line bg-card">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line text-xs text-muted">
                        <th className="p-2.5 text-start">الحساب</th>
                        <th className="p-2.5 text-start">النوع</th>
                        <th className="p-2.5 text-end">أول المدة</th>
                        <th className="p-2.5 text-end">وارد</th>
                        <th className="p-2.5 text-end">منصرف</th>
                        <th className="p-2.5 text-end">آخر المدة</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cf.accounts.map((a) => (
                        <tr key={a.code} className="border-b border-line/60 last:border-0">
                          <td className="p-2.5"><span className="num text-xs text-muted" dir="ltr">{a.code}</span> {a.name}</td>
                          <td className="p-2.5 text-xs">{MONEY_KIND[a.kind] ?? a.kind}</td>
                          <td className="num p-2.5 text-end">{moneyIn(a.opening, cur)}</td>
                          <td className="num p-2.5 text-end">{moneyIn(a.in, cur)}</td>
                          <td className="num p-2.5 text-end">{moneyIn(a.out, cur)}</td>
                          <td className="num p-2.5 text-end font-semibold">{moneyIn(a.closing, cur)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </Loading>
    </section>
  );
}

// ── aging ──────────────────────────────────────────────────────────────────────────────────

export function AgingView({ range, onRange }: { range: Range; onRange: (r: Range) => void }) {
  const cur = useCurrency();
  const subtitle = useSubtitle(range, true);
  const [side, setSide] = useState<"customers" | "suppliers">("customers");
  const [open, setOpen] = useState<string | null>(null);
  const q = useQuery({
    queryKey: ["rep-aging", range.to, range.warehouse_id],
    queryFn: () => api.get<AgingReport>("/reports/aging", { as_of: range.to, warehouse_id: range.warehouse_id || undefined }),
    enabled: !!range.to,
  });
  const columns = [side === "customers" ? "العميل" : "المورد", ...BUCKETS.map((b) => BUCKET_LABEL[b]), "الإجمالي"];
  return (
    <section className="flex flex-col gap-4">
      <RangeFilters value={range} onChange={onRange} single>
        <div>
          <label htmlFor="aging-side" className="mb-1 block text-xs font-medium text-muted">الطرف</label>
          <Select id="aging-side" className="w-36" value={side} onChange={(e) => setSide(e.target.value as typeof side)}>
            <option value="customers">العملاء</option>
            <option value="suppliers">الموردون</option>
          </Select>
        </div>
      </RangeFilters>
      <Loading query={q}>
        {(a) => {
          const s: AgingSide = a[side];
          return (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="max-w-3xl text-xs text-muted">
                  {side === "customers"
                    ? "فواتير البيع الآجل المفتوحة كما كانت في التاريخ المحدد (ما سُدد أو رُدّ بعده لا يُحتسب)، حسب عمر الفاتورة."
                    : "فواتير الموردين حتى التاريخ المحدد بعد المدفوعات (تُسدَّد الأقدم أولاً)، حسب عمر الفاتورة."}
                  {s.count > s.items.length ? ` يُعرض أكبر ${s.items.length} من ${s.count}، والإجماليات تشمل الجميع.` : ""}
                </p>
                <ExportButtons filename={`aging-${side}`} title={`أعمار ديون ${side === "customers" ? "العملاء" : "الموردين"}`}
                               subtitle={subtitle} columns={columns} rows={agingRows(s)} />
              </div>
              {side === "suppliers" && s.included === false ? (
                <Empty text="ديون الموردين لا تخص فرعاً" hint="اختر «كل الفروع» لعرضها" />
              ) : !s.items.length ? (
                <Empty text={side === "customers" ? "لا ديون مفتوحة على العملاء" : "لا ديون مفتوحة للموردين"} />
              ) : (
                <>
                  <div className="grid gap-3 sm:grid-cols-5">
                    {BUCKETS.map((b) => (
                      <Stat key={b} label={BUCKET_LABEL[b]} value={moneyIn(s.totals[b], cur)} hint={`${bucketShare(s, b)}% من الإجمالي`} />
                    ))}
                    <Stat label="الإجمالي" value={moneyIn(s.totals.total, cur)} hint={`${s.count} ${side === "customers" ? "عميل" : "مورد"}`} />
                  </div>
                  <div className="overflow-x-auto rounded-xl border border-line bg-card">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-xs text-muted">
                          {columns.map((c, i) => <th key={c} className={`p-2.5 ${i ? "text-end" : "text-start"}`}>{c}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {s.items.map((p) => (
                          <AgingRow key={p.id} party={p} currency={cur} open={open === p.id} onToggle={() => setOpen(open === p.id ? null : p.id)} />
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

function AgingRow({ party, currency, open, onToggle }: { party: AgingSide["items"][number]; currency: string; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className="border-b border-line/60 last:border-0">
        <td className="p-2.5">
          {party.invoices?.length ? (
            <button type="button" className="font-semibold text-primary underline-offset-2 hover:underline" aria-expanded={open} onClick={onToggle}>{party.name}</button>
          ) : <span className="font-semibold">{party.name}</span>}
        </td>
        {BUCKETS.map((b) => <td key={b} className="num p-2.5 text-end">{D(party.buckets[b]).isZero() ? "" : moneyIn(party.buckets[b], currency)}</td>)}
        <td className="num p-2.5 text-end font-bold">{moneyIn(party.total_debt, currency)}</td>
      </tr>
      {open && party.invoices?.map((i) => (
        <tr key={i.invoice} className="border-b border-line/40 bg-elevated/40 text-xs">
          <td className="p-2 ps-8"><span className="num" dir="ltr">{i.invoice}</span> — {fmtDate(i.date)}</td>
          {BUCKETS.map((b) => <td key={b} className="num p-2 text-end">{i.bucket === b ? moneyIn(i.remaining, currency) : ""}</td>)}
          <td className="num p-2 text-end text-muted">من {moneyIn(i.total, currency)}</td>
        </tr>
      ))}
    </>
  );
}

// ── the company overview ───────────────────────────────────────────────────────────────────

export function OverviewView({ range, onRange }: { range: Range; onRange: (r: Range) => void }) {
  const cur = useCurrency();
  const q = useQuery({
    queryKey: ["rep-overview", range.from, range.to],
    queryFn: () => api.get<Overview>("/admin/overview", { from_date: range.from, to_date: range.to }),
    enabled: !!range.from && !!range.to,
  });
  const subtitle = `من ${fmtDate(range.from)} إلى ${fmtDate(range.to)} — الشركة كلها`;
  return (
    <section className="flex flex-col gap-4">
      <RangeFilters value={range} onChange={onRange} branch={false} />
      <Loading query={q}>
        {(o) => {
          const s = o.summary;
          const branchRows: Cell[][] = o.branches.map((b) => [b.name, b.invoice_count, n(b.revenue), n(b.gross_profit), n(b.cash_sales), n(b.credit_sales)]);
          return (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-muted">المبيعات بعد الخصومات والمرتجعات وبدون الضريبة؛ المخزون بمتوسط التكلفة؛ النقدية كما تتوقعها الأدراج المفتوحة.</p>
                <ExportButtons filename="overview-branches" title="نظرة عامة — الفروع" subtitle={subtitle}
                               columns={["الفرع", "الفواتير", "صافي المبيعات", "مجمل الربح", "نقدي", "آجل"]} rows={branchRows} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <Stat label="صافي المبيعات" value={moneyIn(s.total_revenue, cur)} />
                <Stat label="مجمل الربح" value={moneyIn(s.total_profit, cur)} hint={`هامش ${s.profit_margin}%`} />
                <Stat label="المخزون بالتكلفة" value={moneyIn(s.total_stock_cost, cur)} hint={`بسعر البيع ${moneyIn(s.total_stock_retail, cur)}`} />
                <Stat label="النقدية بالأدراج والخزائن" value={moneyIn(D(s.total_cash_in_drawers).plus(D(s.total_safes_balance)), cur)}
                      hint={`أدراج ${moneyIn(s.total_cash_in_drawers, cur)} · خزائن ${moneyIn(s.total_safes_balance, cur)}`} />
                <Stat label="صافي رأس المال العامل" value={moneyIn(s.net_capital, cur)}
                      hint={`لنا ${moneyIn(s.total_customer_debt, cur)} · علينا ${moneyIn(s.total_supplier_debt, cur)}`} />
              </div>
              <Table title="الفروع" head={["الفرع", "الفواتير", "صافي المبيعات", "مجمل الربح", "نقدي", "آجل"]}
                     rows={o.branches.map((b) => [b.name, b.invoice_count, moneyIn(b.revenue, cur), moneyIn(b.gross_profit, cur), moneyIn(b.cash_sales, cur), moneyIn(b.credit_sales, cur)])} />
              <div className="grid gap-4 lg:grid-cols-2">
                <Table title="المخزون حسب الفرع" head={["الفرع", "بالتكلفة", "بسعر البيع"]}
                       rows={o.stock_per_warehouse.map((w) => [w.name, moneyIn(w.stock_cost_value, cur), moneyIn(w.stock_retail_value, cur)])} />
                <Table title="الأدراج المفتوحة" head={["الفرع", "الكاشير", "النقدية المتوقعة"]}
                       rows={o.cash_drawers.map((d) => [d.name, d.cashier ?? "—", moneyIn(d.expected, cur)])} />
                <Table title="أكبر ديون العملاء" head={["العميل", "الهاتف", "المستحق"]}
                       rows={o.customer_debts.map((c) => [c.name, c.phone ?? "—", moneyIn(c.balance_due, cur)])} />
                <Table title="أكبر مستحقات الموردين" head={["المورد", "الهاتف", "المستحق"]}
                       rows={o.supplier_debts.map((c) => [c.name, c.phone ?? "—", moneyIn(c.balance, cur)])} />
                <Table title="أصناف تحت حد إعادة الطلب" head={["الصنف", "الكمية", "حد الطلب"]}
                       rows={o.low_stock.map((p) => [p.name, `${p.total_qty} ${p.unit ?? ""}`, String(p.reorder_point)])} />
              </div>
            </>
          );
        }}
      </Loading>
    </section>
  );
}

function Table({ title, head, rows }: { title: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-bold">{title}</h3>
      {!rows.length ? (
        <p className="rounded-xl border border-dashed border-line p-4 text-center text-xs text-muted">لا شيء</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-xs text-muted">{head.map((h, i) => <th key={h} className={`p-2.5 ${i ? "text-end" : "text-start"}`}>{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-line/60 last:border-0">
                  {r.map((c, j) => <td key={j} className={`p-2.5 ${j ? "num text-end" : "font-semibold"}`}>{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

