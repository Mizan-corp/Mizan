// The accounting reports (ADR-014 D8), all read from the ledger: trial balance, income statement,
// balance sheet, general ledger per account, a customer's / supplier's / employee's statement, and
// the reconciliation of the ledger with the operational balances, and the VAT report (D6). Date
// range and branch filters; each exports to CSV or prints.
import { useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CheckCircle2, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { date as fmtDate } from "@/lib/format";
import { Badge, Button, Empty, ErrorBox, Input, Select } from "@/components/ui";
import type { BalanceSheet, BalanceSheetRow, GeneralLedger, IncomeStatement, LinesPage, PartyStatement, PartyType, Reconciliation,
  StatementEntryLine, TrialBalance, VatCodeRow, VatReport } from "../api";
import { type Cell, fiscalYearOf, fiscalYearRange, monthLabel, monthRange, PARTY_LABEL, sourceLabel, todayCairo } from "../lib";
import { EntryDetailModal } from "../components/EntryDetail";
import { AccountingHeader, AccountSelect, ExportButtons, Money, PartySelect, type Range, RangeFilters, SkeletonRows,
  useAccountingState, useBranches, useChart } from "../components/shared";

const TABS = [
  { key: "trial", label: "ميزان المراجعة" },
  { key: "income", label: "قائمة الدخل" },
  { key: "balance", label: "الميزانية" },
  { key: "ledger", label: "دفتر الأستاذ" },
  { key: "party", label: "كشف حساب" },
  { key: "reconciliation", label: "المطابقة" },
  { key: "vat", label: "ضريبة القيمة المضافة" },
] as const;
type Tab = (typeof TABS)[number]["key"];

function q(range: Range): Record<string, string> {
  return { from: range.from, to: range.to, warehouse_id: range.warehouse_id };
}

function useSubtitle(range: Range, single = false): string {
  const branches = useBranches();
  const branch = range.warehouse_id ? branches.data?.find((b) => b.id === range.warehouse_id)?.name ?? "" : "كل الفروع";
  const period = single ? `في ${fmtDate(range.to || todayCairo())}` : `من ${range.from ? fmtDate(range.from) : "البداية"} إلى ${range.to ? fmtDate(range.to) : "اليوم"}`;
  return `${period} — ${branch}`;
}

export default function ReportsPage() {
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((t) => t.key === params.get("tab"))?.key ?? "trial") as Tab;
  const state = useAccountingState();
  const today = todayCairo();
  const fyStart = state.data ? fiscalYearRange(fiscalYearOf(today, state.data.fiscal_year_start), state.data.fiscal_year_start).from : `${today.slice(0, 4)}-01-01`;
  const [range, setRange] = useState<Range | null>(null);
  const r: Range = range ?? { from: fyStart, to: today, warehouse_id: "" };
  const [openEntry, setOpenEntry] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-6">
      <AccountingHeader title="التقارير المحاسبية" subtitle="كل الأرقام من دفتر اليومية وحده. تقرير الفرع لا يشمل السطور التي لا تخص فرعاً (كتحصيل في خزنة رئيسية)." />
      <div className="no-print flex flex-wrap gap-1 border-b border-line" role="tablist">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key}
                  onClick={() => setParams((p) => { p.set("tab", t.key); return p; }, { replace: true })}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm font-semibold ${tab === t.key ? "border-primary text-ink" : "border-transparent text-muted hover:text-ink"}`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab !== "reconciliation" && (
        <RangeFilters value={r} onChange={setRange} single={tab === "balance"} branch={tab !== "vat"}>
          {tab === "vat" && (
            <div>
              <label htmlFor="vat-month" className="mb-1 block text-xs font-medium text-muted">شهر الإقرار</label>
              <Input id="vat-month" type="month" className="w-40" value={r.from.slice(0, 7) === r.to.slice(0, 7) ? r.from.slice(0, 7) : ""}
                     onChange={(e) => e.target.value && setRange({ ...r, ...monthRange(e.target.value) })} />
            </div>
          )}
        </RangeFilters>
      )}
      {tab === "trial" && <TrialBalanceReport range={r} />}
      {tab === "income" && <IncomeReport range={r} />}
      {tab === "balance" && <BalanceSheetReport range={r} />}
      {tab === "ledger" && <LedgerReport range={r} onOpen={setOpenEntry} />}
      {tab === "party" && <PartyReport range={r} onOpen={setOpenEntry} />}
      {tab === "reconciliation" && <ReconciliationReport />}
      {tab === "vat" && <VatReportView range={r} />}
      <EntryDetailModal entryId={openEntry} onClose={() => setOpenEntry(null)} onOpen={setOpenEntry} />
    </div>
  );
}

function Loading<T>({ query, empty, children }: { query: { isLoading: boolean; isError: boolean; error: unknown; refetch: () => unknown; data?: T };
  empty?: (d: T) => boolean; children: (d: T) => ReactNode }) {
  if (query.isLoading) return <SkeletonRows n={8} />;
  if (query.isError) return <ErrorBox message={(query.error as Error).message} onRetry={() => query.refetch()} />;
  if (query.data === undefined) return null;
  if (empty?.(query.data)) return <Empty text="لا توجد قيود في هذه الفترة" hint="غيّر الفترة أو الفرع" />;
  return <>{children(query.data)}</>;
}

function Balanced({ ok, difference }: { ok: boolean; difference?: number }) {
  return ok ? (
    <Badge tone="success"><CheckCircle2 className="size-3.5" /> متوازن</Badge>
  ) : (
    <Badge tone="warning"><TriangleAlert className="size-3.5" /> غير متوازن{difference !== undefined ? ` (الفرق ${difference.toFixed(2)})` : ""}</Badge>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="no-print flex items-center gap-2 text-xs text-muted">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /> {label}
    </label>
  );
}

const indent = (level: number) => ({ paddingInlineStart: `${0.75 + level * 1.1}rem` });

// ── trial balance ────────────────────────────────────────────────────────────────────────────

function TrialBalanceReport({ range }: { range: Range }) {
  const [includeZero, setIncludeZero] = useState(false);
  const [groups, setGroups] = useState(true);
  const subtitle = useSubtitle(range);
  const query = useQuery({
    queryKey: ["accounting", "trial-balance", range, includeZero],
    queryFn: () => api.get<TrialBalance>("/accounting/trial-balance", { ...q(range), include_zero: String(includeZero) }),
  });
  const rows = (query.data?.accounts ?? []).filter((a) => groups || !a.is_group);
  const columns = ["الرقم", "الحساب", "أول المدة مدين", "أول المدة دائن", "حركة مدين", "حركة دائن", "آخر المدة مدين", "آخر المدة دائن"];
  const exportRows: Cell[][] = rows.map((a) => [a.code, a.name, a.opening_debit, a.opening_credit, a.debit, a.credit, a.closing_debit, a.closing_credit]);
  if (query.data) {
    const t = query.data.totals;
    exportRows.push(["", "الإجمالي", t.opening_debit, t.opening_credit, t.debit, t.credit, t.closing_debit, t.closing_credit]);
  }
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-4">
          {query.data && <Balanced ok={query.data.balanced} />}
          <Toggle label="إظهار الحسابات بلا حركة" checked={includeZero} onChange={setIncludeZero} />
          <Toggle label="إظهار الحسابات التجميعية" checked={groups} onChange={setGroups} />
        </div>
        <ExportButtons filename="trial-balance" title="ميزان المراجعة" subtitle={subtitle} columns={columns} rows={exportRows} />
      </div>
      <Loading query={query} empty={(d) => !d.accounts.length}>
        {(d) => (
          <div className="overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="p-2 text-start" rowSpan={2}>الحساب</th>
                  <th className="p-2 text-center" colSpan={2}>أول المدة</th>
                  <th className="p-2 text-center" colSpan={2}>حركة الفترة</th>
                  <th className="p-2 text-center" colSpan={2}>آخر المدة</th>
                </tr>
                <tr className="border-b border-line text-xs text-muted">
                  {["مدين", "دائن", "مدين", "دائن", "مدين", "دائن"].map((h, i) => <th key={i} className="p-2 text-end">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} className={`border-b border-line/60 last:border-0 ${a.is_group ? "bg-elevated/40 font-semibold" : ""}`}>
                    <td className="p-2" style={groups ? indent(a.level) : undefined}>
                      <span className="num text-xs text-muted" dir="ltr">{a.code}</span> {a.name}
                    </td>
                    {[a.opening_debit, a.opening_credit, a.debit, a.credit, a.closing_debit, a.closing_credit].map((v, i) => (
                      <td key={i} className="p-2 text-end">{v ? <Money value={v} /> : ""}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-line font-bold">
                  <td className="p-2">الإجمالي</td>
                  {[d.totals.opening_debit, d.totals.opening_credit, d.totals.debit, d.totals.credit, d.totals.closing_debit, d.totals.closing_credit].map((v, i) => (
                    <td key={i} className="p-2 text-end"><Money value={v} /></td>
                  ))}
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Loading>
    </section>
  );
}

// ── income statement ─────────────────────────────────────────────────────────────────────────

function IncomeReport({ range }: { range: Range }) {
  const [includeClosing, setIncludeClosing] = useState(false);
  const subtitle = useSubtitle(range);
  const query = useQuery({
    queryKey: ["accounting", "income-statement", range, includeClosing],
    queryFn: () => api.get<IncomeStatement>("/accounting/income-statement", { ...q(range), include_closing: String(includeClosing) }),
  });
  const rows: { label: string; amount: number; kind: "line" | "section" | "result"; code?: string }[] = [];
  const d = query.data;
  if (d) {
    const section = (label: string, s: IncomeStatement["revenue"]) => {
      rows.push({ label, amount: s.total, kind: "section" });
      s.lines.forEach((l) => rows.push({ label: l.name, code: l.code, amount: l.amount, kind: "line" }));
    };
    section("الإيرادات", d.revenue);
    section("مردودات المبيعات", d.sales_returns);
    rows.push({ label: "صافي المبيعات", amount: d.net_sales, kind: "result" });
    section("تكلفة البضاعة المباعة", d.cogs);
    rows.push({ label: "مجمل الربح", amount: d.gross_profit, kind: "result" });
    section("المصروفات التشغيلية", d.operating_expenses);
    rows.push({ label: "ربح التشغيل", amount: d.operating_profit, kind: "result" });
    section("إيرادات أخرى", d.other_income);
    section("مصروفات أخرى", d.other_expenses);
    rows.push({ label: d.net_profit >= 0 ? "صافي الربح" : "صافي الخسارة", amount: d.net_profit, kind: "result" });
  }
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Toggle label="بعد قيد إقفال السنة (تصبح أرقام السنة المقفلة صفراً)" checked={includeClosing} onChange={setIncludeClosing} />
        <ExportButtons filename="income-statement" title="قائمة الدخل" subtitle={subtitle} columns={["البند", "الرقم", "المبلغ"]}
                       rows={rows.map((r) => [r.label, r.code ?? "", r.amount])} />
      </div>
      <Loading query={query}>
        {() => (
          <div className="mx-auto w-full max-w-3xl overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-sm">
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className={`border-b border-line/60 last:border-0 ${r.kind === "result" ? "bg-elevated/60 font-black" : r.kind === "section" ? "font-semibold" : ""}`}>
                    <td className="p-2.5" style={r.kind === "line" ? indent(1) : undefined}>
                      {r.code && <span className="num me-1.5 text-xs text-muted" dir="ltr">{r.code}</span>}{r.label}
                    </td>
                    <td className="p-2.5 text-end"><Money value={r.amount} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Loading>
    </section>
  );
}

// ── balance sheet ────────────────────────────────────────────────────────────────────────────

function BalanceSheetReport({ range }: { range: Range }) {
  const subtitle = useSubtitle(range, true);
  const query = useQuery({
    queryKey: ["accounting", "balance-sheet", range.to, range.warehouse_id],
    queryFn: () => api.get<BalanceSheet>("/accounting/balance-sheet", { as_of: range.to, warehouse_id: range.warehouse_id }),
  });
  const d = query.data;
  const exportRows: Cell[][] = [];
  if (d) {
    const add = (title: string, accounts: BalanceSheetRow[], total: number) => {
      exportRows.push([title, "", ""]);
      accounts.forEach((a) => exportRows.push([`${"  ".repeat(a.level)}${a.name}`, a.code, a.amount]));
      exportRows.push([`إجمالي ${title}`, "", total]);
    };
    add("الأصول", d.assets.accounts, d.assets.total);
    add("الخصوم", d.liabilities.accounts, d.liabilities.total);
    add("حقوق الملكية", d.equity.accounts, d.equity.accounts_total);
    exportRows.push(["أرباح سنوات سابقة لم تُقفل", "", d.equity.prior_years_profit], ["ربح السنة الحالية", "", d.equity.current_year_profit],
                    ["إجمالي حقوق الملكية", "", d.equity.total], ["إجمالي الخصوم وحقوق الملكية", "", d.total_liabilities_and_equity]);
  }
  const block = (title: string, accounts: BalanceSheetRow[], extra: ReactNode, total: number) => (
    <div className="overflow-x-auto rounded-xl border border-line bg-card">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line"><th className="p-2.5 text-start text-base" colSpan={2}>{title}</th></tr></thead>
        <tbody>
          {accounts.map((a) => (
            <tr key={a.id} className={`border-b border-line/60 ${a.is_group ? "font-semibold" : ""}`}>
              <td className="p-2" style={indent(a.level)}><span className="num text-xs text-muted" dir="ltr">{a.code}</span> {a.name}</td>
              <td className="p-2 text-end"><Money value={a.amount} /></td>
            </tr>
          ))}
          {extra}
        </tbody>
        <tfoot><tr className="border-t-2 border-line bg-elevated/60 font-black"><td className="p-2.5">الإجمالي</td><td className="p-2.5 text-end"><Money value={total} /></td></tr></tfoot>
      </table>
    </div>
  );
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {d ? <Balanced ok={d.balanced} difference={d.difference} /> : <span />}
        <ExportButtons filename="balance-sheet" title="الميزانية (المركز المالي)" subtitle={subtitle} columns={["البند", "الرقم", "المبلغ"]} rows={exportRows} />
      </div>
      <Loading query={query}>
        {(b) => (
          <div className="grid gap-4 lg:grid-cols-2">
            {block("الأصول", b.assets.accounts, null, b.assets.total)}
            <div className="flex flex-col gap-4">
              {block("الخصوم", b.liabilities.accounts, null, b.liabilities.total)}
              {block("حقوق الملكية", b.equity.accounts, (
                <>
                  <tr className="border-b border-line/60"><td className="p-2" style={indent(1)}>أرباح سنوات سابقة لم تُقفل</td><td className="p-2 text-end"><Money value={b.equity.prior_years_profit} /></td></tr>
                  <tr className="border-b border-line/60"><td className="p-2" style={indent(1)}>ربح السنة الحالية</td><td className="p-2 text-end"><Money value={b.equity.current_year_profit} /></td></tr>
                </>
              ), b.equity.total)}
              <div className="flex items-center justify-between rounded-xl border border-line bg-elevated/60 p-3 font-black">
                <span>إجمالي الخصوم وحقوق الملكية</span><Money value={b.total_liabilities_and_equity} />
              </div>
            </div>
          </div>
        )}
      </Loading>
    </section>
  );
}

// ── general ledger and party statement ───────────────────────────────────────────────────────

const LINES_PAGE = 100;

function LinesTable({ data, onOpen, showAccount, showParty, page, setPage }: {
  data: LinesPage; onOpen: (id: string) => void; showAccount: boolean; showParty: boolean; page: number; setPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(data.count / LINES_PAGE));
  return (
    <>
      <div className="overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-xs text-muted">
              <th className="p-2 text-start">التاريخ</th>
              <th className="p-2 text-start">القيد</th>
              <th className="p-2 text-start">المصدر / البيان</th>
              {showAccount && <th className="p-2 text-start">الحساب</th>}
              {showParty && <th className="p-2 text-start">الطرف</th>}
              <th className="p-2 text-end">مدين</th>
              <th className="p-2 text-end">دائن</th>
              <th className="p-2 text-end">الرصيد</th>
            </tr>
          </thead>
          <tbody>
            {page === 1 && (
              <tr className="border-b border-line/60 bg-elevated/40 text-xs font-semibold">
                <td className="p-2" colSpan={3 + Number(showAccount) + Number(showParty)}>رصيد أول المدة</td>
                <td className="p-2" colSpan={2} />
                <td className="p-2 text-end"><Money value={data.opening_balance} /></td>
              </tr>
            )}
            {data.lines.map((l: StatementEntryLine, i) => (
              <tr key={`${l.entry_id}-${i}`} className="border-b border-line/60 last:border-0 hover:bg-elevated">
                <td className="p-2 text-xs">{fmtDate(l.date)}</td>
                <td className="p-2"><button type="button" className="num font-bold text-primary underline" dir="ltr" onClick={() => onOpen(l.entry_id)}>{l.number}</button></td>
                <td className="max-w-72 p-2 text-xs"><div>{sourceLabel(l.source_type, l.event)}</div>{l.memo && <div className="truncate text-muted">{l.memo}</div>}</td>
                {showAccount && <td className="p-2 text-xs"><span className="num text-muted" dir="ltr">{l.account_code}</span> {l.account_name}</td>}
                {showParty && <td className="p-2 text-xs">{l.party_name ?? "—"}</td>}
                <td className="p-2 text-end">{l.debit ? <Money value={l.debit} /> : ""}</td>
                <td className="p-2 text-end">{l.credit ? <Money value={l.credit} /> : ""}</td>
                <td className="p-2 text-end font-semibold"><Money value={l.balance} /></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-line font-bold">
              <td className="p-2" colSpan={3 + Number(showAccount) + Number(showParty)}>إجمالي الفترة ({data.count} سطر) — رصيد آخر المدة</td>
              <td className="p-2 text-end"><Money value={data.total_debit} /></td>
              <td className="p-2 text-end"><Money value={data.total_credit} /></td>
              <td className="p-2 text-end"><Money value={data.closing_balance} /></td>
            </tr>
          </tfoot>
        </table>
      </div>
      {pages > 1 && (
        <div className="no-print flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>السابق</Button>
          <span className="num text-muted">صفحة {page} من {pages}</span>
          <Button variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>التالي</Button>
        </div>
      )}
    </>
  );
}

function lineExport(data: LinesPage | undefined, withParty: boolean): { columns: string[]; rows: Cell[][] } {
  const columns = ["التاريخ", "القيد", "المصدر", "البيان", "الحساب", ...(withParty ? ["الطرف"] : []), "مدين", "دائن", "الرصيد"];
  const rows: Cell[][] = (data?.lines ?? []).map((l) => [l.date, l.number, sourceLabel(l.source_type, l.event), l.memo ?? "",
    `${l.account_code} ${l.account_name}`, ...(withParty ? [l.party_name ?? ""] : []), l.debit, l.credit, l.balance]);
  if (data) rows.unshift(["", "", "رصيد أول المدة", "", "", ...(withParty ? [""] : []), null, null, data.opening_balance]);
  return { columns, rows };
}

function LedgerReport({ range, onOpen }: { range: Range; onOpen: (id: string) => void }) {
  const chart = useChart();
  const [accountId, setAccountId] = useState("");
  const [page, setPage] = useState(1);
  const subtitle = useSubtitle(range);
  const query = useQuery({
    queryKey: ["accounting", "general-ledger", accountId, range, page],
    queryFn: () => api.get<GeneralLedger>(`/accounting/general-ledger/${accountId}`, { ...q(range), page, page_size: LINES_PAGE }),
    enabled: !!accountId,
    placeholderData: keepPreviousData,
  });
  const ex = lineExport(query.data, true);
  const acc = chart.byId.get(accountId);
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-72 flex-1">
          <label htmlFor="gl-acc" className="mb-1 block text-xs font-medium text-muted">الحساب (الحساب التجميعي يشمل ما تحته)</label>
          <AccountSelect id="gl-acc" value={accountId} onChange={(id) => { setAccountId(id); setPage(1); }} rows={chart.rows} />
        </div>
        <ExportButtons filename="general-ledger" title={`دفتر الأستاذ — ${acc ? `${acc.code} ${acc.name}` : ""}`} subtitle={subtitle} {...ex}
                       disabled={!query.data} />
      </div>
      {!accountId ? (
        <Empty text="اختر حساباً لعرض حركته" hint="كل سطر مع رصيده الجاري ورابط قيده" />
      ) : (
        <Loading query={query}>
          {(d) => (
            <>
              <p className="text-xs text-muted">الرصيد بطبيعة الحساب ({d.normal_side === "debit" ? "مدين" : "دائن"}). التصدير يشمل الصفحة المعروضة.</p>
              <LinesTable data={d} onOpen={onOpen} showAccount={d.account.is_group} showParty page={page} setPage={setPage} />
            </>
          )}
        </Loading>
      )}
    </section>
  );
}

function PartyReport({ range, onOpen }: { range: Range; onOpen: (id: string) => void }) {
  const [type, setType] = useState<PartyType>("customer");
  const [partyId, setPartyId] = useState("");
  const [page, setPage] = useState(1);
  const subtitle = useSubtitle(range);
  const query = useQuery({
    queryKey: ["accounting", "party-statement", type, partyId, range, page],
    queryFn: () => api.get<PartyStatement>(`/accounting/party-statement/${type}/${partyId}`, { ...q(range), page, page_size: LINES_PAGE }),
    enabled: !!partyId,
    placeholderData: keepPreviousData,
  });
  const ex = lineExport(query.data, false);
  const d = query.data;
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="ps-type" className="mb-1 block text-xs font-medium text-muted">النوع</label>
            <Select id="ps-type" className="w-32" value={type} onChange={(e) => { setType(e.target.value as PartyType); setPartyId(""); setPage(1); }}>
              {(["customer", "supplier", "employee"] as const).map((t) => <option key={t} value={t}>{PARTY_LABEL[t]}</option>)}
            </Select>
          </div>
          <div>
            <label htmlFor="ps-party" className="mb-1 block text-xs font-medium text-muted">{PARTY_LABEL[type]}</label>
            <PartySelect id="ps-party" type={type} value={partyId} onChange={(id) => { setPartyId(id); setPage(1); }} className="w-64" />
          </div>
        </div>
        <ExportButtons filename="party-statement" title={`كشف حساب ${PARTY_LABEL[type]} — ${d?.party.name ?? ""}`} subtitle={subtitle} {...ex}
                       disabled={!d} />
      </div>
      {!partyId ? (
        <Empty text={`اختر ${PARTY_LABEL[type]} لعرض كشف حسابه من الدفاتر`} />
      ) : (
        <Loading query={query}>
          {(s) => (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-line bg-card p-3">
                  <p className="text-xs text-muted">{s.meaning === "what_they_owe_us" ? "رصيده في الدفاتر (مستحق لنا)" : "رصيده في الدفاتر (مستحق له)"}</p>
                  <p className="text-xl font-black"><Money value={s.ledger_balance} /></p>
                </div>
                {s.operational_balance !== null && (
                  <>
                    <div className="rounded-xl border border-line bg-card p-3">
                      <p className="text-xs text-muted">رصيده في شاشة {type === "customer" ? "العملاء" : "الموردين"}</p>
                      <p className="text-xl font-black"><Money value={s.operational_balance} /></p>
                    </div>
                    <div className={`rounded-xl border p-3 ${s.matches ? "border-success/40 bg-success/10" : "border-warning/40 bg-warning/10"}`}>
                      <p className="text-xs text-muted">الفرق</p>
                      <p className="text-xl font-black">{s.matches ? "مطابق" : <Money value={s.difference} />}</p>
                    </div>
                  </>
                )}
              </div>
              <LinesTable data={s} onOpen={onOpen} showAccount showParty={false} page={page} setPage={setPage} />
            </>
          )}
        </Loading>
      )}
    </section>
  );
}

// ── reconciliation ───────────────────────────────────────────────────────────────────────────

function ReconciliationReport() {
  const query = useQuery({ queryKey: ["accounting", "reconciliation"], queryFn: () => api.get<Reconciliation>("/accounting/reconciliation") });
  const rows = useMemo(() => (query.data?.items ?? []).map((i): Cell[] => [i.label, i.ledger, i.operational, i.difference, i.ok ? "مطابق" : "فرق"]), [query.data]);
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          للتنبيه فقط: الدفاتر هي المرجع، ولا يغيّر هذا الفحص أي رصيد. يُجرى أيضاً كل ليلة ويُنبَّه المحاسب عند وجود فروق. أدراج الكاشير وسلف الموظفين لا تُقارن.
        </p>
        <ExportButtons filename="reconciliation" title="مطابقة الدفاتر مع الأرصدة" subtitle={query.data ? fmtDate(query.data.as_of) : ""}
                       columns={["البند", "الدفاتر", "الأرصدة التشغيلية", "الفرق", "الحالة"]} rows={rows} />
      </div>
      <Loading query={query}>
        {(d) => (
          <>
            <div className={`flex items-center gap-2 rounded-xl border p-3 text-sm font-semibold ${d.ok ? "border-success/40 bg-success/10" : "border-warning/40 bg-warning/10"}`}>
              {d.ok ? <CheckCircle2 className="size-4" /> : <TriangleAlert className="size-4" />}
              {d.ok ? "الدفاتر مطابقة للأرصدة التشغيلية" : `${d.differences.length} بند به فرق`}
            </div>
            <div className="overflow-x-auto rounded-xl border border-line bg-card">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-muted">
                    <th className="p-2 text-start">البند</th>
                    <th className="p-2 text-end">الدفاتر</th>
                    <th className="p-2 text-end">الأرصدة التشغيلية</th>
                    <th className="p-2 text-end">الفرق</th>
                    <th className="p-2 text-start" />
                  </tr>
                </thead>
                <tbody>
                  {d.items.map((i) => (
                    <tr key={i.key} className="border-b border-line/60 last:border-0">
                      <td className="p-2">{i.label}</td>
                      <td className="p-2 text-end"><Money value={i.ledger} /></td>
                      <td className="p-2 text-end"><Money value={i.operational} /></td>
                      <td className="p-2 text-end font-semibold"><Money value={i.difference} /></td>
                      <td className="p-2">{i.ok ? <Badge tone="success">مطابق</Badge> : <Badge tone="warning">فرق</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {d.parties.length > 0 && (
              <>
                <h3 className="text-sm font-bold">عملاء وموردون يختلف رصيدهم عن الدفاتر</h3>
                <div className="overflow-x-auto rounded-xl border border-line bg-card">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line text-xs text-muted">
                        <th className="p-2 text-start">الاسم</th>
                        <th className="p-2 text-start">النوع</th>
                        <th className="p-2 text-end">الدفاتر</th>
                        <th className="p-2 text-end">الرصيد التشغيلي</th>
                        <th className="p-2 text-end">الفرق</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.parties.map((p) => (
                        <tr key={`${p.party_type}-${p.id}`} className="border-b border-line/60 last:border-0">
                          <td className="p-2">{p.name ?? "—"}</td>
                          <td className="p-2 text-xs">{PARTY_LABEL[p.party_type]}</td>
                          <td className="p-2 text-end"><Money value={p.ledger} /></td>
                          <td className="p-2 text-end"><Money value={p.operational} /></td>
                          <td className="p-2 text-end font-semibold"><Money value={p.difference} /></td>
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

// ── VAT (ADR-014 D6) ─────────────────────────────────────────────────────────────────────────

function VatReportView({ range }: { range: Range }) {
  const subtitle = useSubtitle({ ...range, warehouse_id: "" });
  const query = useQuery({
    queryKey: ["accounting", "vat-report", range.from, range.to],
    queryFn: () => api.get<VatReport>("/accounting/vat-report", { from: range.from, to: range.to }),
  });
  const d = query.data;
  const summary: { label: string; amount: number; kind: "line" | "section" | "result" }[] = d ? [
    { label: "ضريبة المخرجات (المبيعات)", amount: d.output.total, kind: "section" },
    { label: "على المبيعات", amount: d.output.sales, kind: "line" },
    { label: "ناقص: على مردودات المبيعات", amount: -d.output.returns, kind: "line" },
    ...(d.output.other ? [{ label: "قيود أخرى", amount: d.output.other, kind: "line" as const }] : []),
    { label: "ضريبة المدخلات (المشتريات والمصروفات)", amount: d.input.total, kind: "section" },
    { label: "على المشتريات", amount: d.input.purchases, kind: "line" },
    { label: "ناقص: على مردودات المشتريات", amount: -d.input.returns, kind: "line" },
    { label: "على المصروفات", amount: d.input.expenses, kind: "line" },
    ...(d.input.other ? [{ label: "قيود أخرى", amount: d.input.other, kind: "line" as const }] : []),
    { label: d.net_payable >= 0 ? "صافي الضريبة المستحقة للمصلحة" : "رصيد دائن يُرحَّل للفترة التالية", amount: d.net_payable, kind: "result" },
  ] : [];
  const codeRows: Cell[][] = [];
  const sections: { title: string; rows: VatCodeRow[] }[] = d ? [
    { title: "المبيعات", rows: d.by_code.sales }, { title: "مردودات المبيعات", rows: d.by_code.sale_returns },
    { title: "المشتريات", rows: d.by_code.purchases }, { title: "مردودات المشتريات", rows: d.by_code.purchase_returns },
  ] : [];
  sections.forEach((sec) => sec.rows.forEach((row) => codeRows.push([sec.title, row.label, row.documents, row.taxable, row.tax])));
  if (d && d.by_code.expenses.documents) codeRows.push(["المصروفات", "—", d.by_code.expenses.documents, d.by_code.expenses.taxable, d.by_code.expenses.tax]);
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {d?.vat_registered ? `رقم التسجيل الضريبي: ${d.tax_number}` : "المنشأة غير مسجلة في ضريبة القيمة المضافة (من الإعدادات)."}
          {" "}الأرقام من حسابي ضريبة المخرجات والمدخلات في الدفاتر؛ التفصيل حسب نوع الضريبة من المستندات نفسها.
        </p>
        <ExportButtons filename="vat-report" title="إقرار ضريبة القيمة المضافة" subtitle={subtitle} columns={["البند", "المبلغ"]}
                       rows={summary.map((x) => [x.label, x.amount])} />
      </div>
      <Loading query={query}>
        {(v) => (
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="overflow-x-auto rounded-xl border border-line bg-card">
              <table className="w-full text-sm">
                <tbody>
                  {summary.map((x, i) => (
                    <tr key={i} className={`border-b border-line/60 last:border-0 ${x.kind === "result" ? "bg-elevated/60 font-black" : x.kind === "section" ? "font-semibold" : ""}`}>
                      <td className="p-2.5" style={x.kind === "line" ? indent(1) : undefined}>{x.label}</td>
                      <td className="p-2.5 text-end"><Money value={x.amount} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-col gap-4">
              {v.by_month.length > 1 && (
                <div className="overflow-x-auto rounded-xl border border-line bg-card">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-line text-xs text-muted">
                      <th className="p-2 text-start">الشهر</th><th className="p-2 text-end">مخرجات</th><th className="p-2 text-end">مدخلات</th><th className="p-2 text-end">الصافي</th>
                    </tr></thead>
                    <tbody>
                      {v.by_month.map((m) => (
                        <tr key={m.month} className="border-b border-line/60 last:border-0">
                          <td className="p-2">{monthLabel(m.month)}</td>
                          <td className="p-2 text-end"><Money value={m.output} /></td>
                          <td className="p-2 text-end"><Money value={m.input} /></td>
                          <td className="p-2 text-end font-semibold"><Money value={m.net} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold">حسب نوع الضريبة (من المستندات)</h3>
                <ExportButtons filename="vat-by-code" title="ضريبة القيمة المضافة حسب النوع" subtitle={subtitle}
                               columns={["المستندات", "النوع", "العدد", "القيمة قبل الضريبة", "الضريبة"]} rows={codeRows} />
              </div>
              {codeRows.length === 0 ? (
                <Empty text="لا توجد مستندات بضريبة في هذه الفترة" />
              ) : (
                <div className="overflow-x-auto rounded-xl border border-line bg-card">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-line text-xs text-muted">
                      <th className="p-2 text-start">المستندات</th><th className="p-2 text-start">النوع</th><th className="p-2 text-end">العدد</th>
                      <th className="p-2 text-end">القيمة قبل الضريبة</th><th className="p-2 text-end">الضريبة</th>
                    </tr></thead>
                    <tbody>
                      {codeRows.map((row, i) => (
                        <tr key={i} className="border-b border-line/60 last:border-0">
                          <td className="p-2">{row[0]}</td><td className="p-2 text-xs">{row[1]}</td>
                          <td className="num p-2 text-end">{row[2]}</td>
                          <td className="p-2 text-end"><Money value={row[3] as number} /></td>
                          <td className="p-2 text-end font-semibold"><Money value={row[4] as number} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </Loading>
    </section>
  );
}
