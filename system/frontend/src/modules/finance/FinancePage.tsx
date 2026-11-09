/**
 * PAGE CONTRACT
 * Page: الإدارة المالية ودفتر الأستاذ العام (/finance)
 * Archetype: General Ledger & Double-Entry Accounting Console
 * User: المدير المالي (CFO)، رئيس الحسابات، والمحاسب القانوني
 * Purpose: إدارة دفتر الأستاذ العام، ميزان المراجعة، قيود اليومية المزدوجة المتزنة، الخزائن والمحافظ، وإقفال الفترات المالية
 */
import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  Banknote,
  Lock,
  LockOpen,
  Plus,
  Wallet,
  Scale,
  ReceiptText,
  BookOpen,
  CalendarCheck,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  Building2,
  Coins,
  FileCheck2,
} from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, dateTime, moneyEGP } from "@/lib/format";
import { sound } from "@/lib/sound";
import { Badge, Button, ErrorBox, Input, Modal, Select, Spinner } from "@/components/ui";

interface Safe {
  id: string;
  name: string;
  safe_type: string;
  balance: string;
}

interface WalletRow {
  id: string;
  name: string;
  type: string;
  balance: string;
}

interface Expense {
  id: string;
  amount: string;
  description: string;
  status: string;
  created_at: string;
  is_recurring: boolean;
  category_name?: string | null;
  vendor_name?: string | null;
}

interface FinCategory {
  id: string;
  name: string;
}

interface Vendor {
  id: string;
  name: string;
}

interface Period {
  month: string;
  status: string;
}

interface LedgerRow {
  id?: string;
  date?: string;
  description?: string | null;
  debit?: string | null;
  credit?: string | null;
  balance?: string | null;
  account_code?: string;
  account_name?: string;
}

interface JournalLine {
  id: string;
  account: string;
  description: string;
  debit: string;
  credit: string;
}

const TABS = [
  { key: "ledger", label: "دفتر الأستاذ وميزان المراجعة", icon: BookOpen },
  { key: "journal", label: "قيد يومية مزدوج (Balanced Voucher)", icon: Scale },
  { key: "treasury", label: "الخزائن والمحافظ النقدية", icon: Coins },
  { key: "expenses", label: "مصادقات وسجل المصروفات", icon: ReceiptText },
  { key: "periods", label: "إقفال وترحيل الفترات المالية", icon: CalendarCheck },
] as const;

export default function FinancePage() {
  const [activeTab, setActiveTab] = useState<string>("ledger");

  // Load high-level treasury and accounting periods for the ribbon
  const safes = useQuery({ queryKey: ["safes"], queryFn: () => api.get<Safe[]>("/safes") });
  const wallets = useQuery({ queryKey: ["wallets"], queryFn: () => api.get<WalletRow[]>("/wallets") });
  const periods = useQuery({ queryKey: ["periods"], queryFn: () => api.get<Period[]>("/periods") });

  const totalVaults = (safes.data ?? []).reduce((acc, s) => acc + Number(s.balance || 0), 0);
  const totalWallets = (wallets.data ?? []).reduce((acc, w) => acc + Number(w.balance || 0), 0);
  const totalLiquidity = totalVaults + totalWallets;

  const currentMonthStr = new Date().toISOString().slice(0, 7);
  const currentPeriod = periods.data?.find((p) => p.month === currentMonthStr) ?? {
    month: currentMonthStr,
    status: "open",
  };

  return (
    <div className="flex flex-col gap-6" dir="rtl">
      {/* ── Executive Accounting Ribbon & Fiscal Lock Guard ── */}
      <div className="rounded-2xl border border-line bg-card p-5 md:p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line/60 pb-5">
          <div className="flex items-center gap-3">
            <div className="size-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-xs">
              <Scale className="size-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl md:text-2xl font-black tracking-tight text-ink">
                  الكونسول المالي ودفتر الأستاذ العام
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-primary/10 text-primary border border-primary/20">
                  Double-Entry GAAP
                </span>
              </div>
              <p className="text-xs text-muted mt-0.5">
                ميزان المراجعة، القيود المزدوجة المتزنة، ضبط السيولة النقدية، وترحيل الفترات المحاسبية
              </p>
            </div>
          </div>

          {/* Quick Period Lock Badge */}
          <div className="flex items-center gap-2 rounded-xl border border-line/80 bg-elevated/50 px-3.5 py-2">
            <span className="text-xs text-muted">الفترة المحاسبية النشطة:</span>
            <span className="font-mono text-sm font-bold text-ink" dir="ltr">
              {currentPeriod.month}
            </span>
            <Badge tone={currentPeriod.status === "closed" ? "danger" : "success"}>
              {currentPeriod.status === "closed" ? (
                <span className="flex items-center gap-1">
                  <Lock className="size-3" /> مغلقة ومرحّلة
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <LockOpen className="size-3" /> مفتوحة للقيود
                </span>
              )}
            </Badge>
          </div>
        </div>

        {/* Treasury Liquidity Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-5">
          <div className="rounded-xl border border-line/60 bg-elevated/30 p-4">
            <div className="flex items-center justify-between text-xs text-muted mb-1">
              <span className="flex items-center gap-1.5 font-medium">
                <Coins className="size-4 text-amber-500" /> إجمالي السيولة النقدية المتاحة
              </span>
              <span className="text-[11px] font-semibold">خزائن + محافظ</span>
            </div>
            <p className="num text-2xl font-black text-primary">
              {moneyEGP(totalLiquidity)}
            </p>
          </div>

          <div className="rounded-xl border border-line/60 bg-elevated/30 p-4">
            <div className="flex items-center justify-between text-xs text-muted mb-1">
              <span className="flex items-center gap-1.5 font-medium">
                <Building2 className="size-4 text-emerald-500" /> رصيد الخزائن المركزية
              </span>
              <span className="text-[11px] font-semibold">{safes.data?.length ?? 0} خزائن</span>
            </div>
            <p className="num text-2xl font-black text-ink">
              {moneyEGP(totalVaults)}
            </p>
          </div>

          <div className="rounded-xl border border-line/60 bg-elevated/30 p-4">
            <div className="flex items-center justify-between text-xs text-muted mb-1">
              <span className="flex items-center gap-1.5 font-medium">
                <Wallet className="size-4 text-indigo-500" /> أرصدة المحافظ البنكية والإلكترونية
              </span>
              <span className="text-[11px] font-semibold">{wallets.data?.length ?? 0} محافظ</span>
            </div>
            <p className="num text-2xl font-black text-ink">
              {moneyEGP(totalWallets)}
            </p>
          </div>
        </div>

        {/* Archetype Tab Bar */}
        <div className="flex flex-wrap gap-2 pt-5 border-t border-line/60 mt-5">
          {TABS.map((t) => {
            const Icon = t.icon;
            const isSelected = activeTab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => {
                  sound.click();
                  setActiveTab(t.key);
                }}
                className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                  isSelected
                    ? "bg-primary text-primary-foreground shadow-sm shadow-primary/25"
                    : "border border-line/80 bg-card text-muted hover:text-ink hover:bg-elevated"
                }`}
              >
                <Icon className="size-4" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Active Workspaces ── */}
      {activeTab === "ledger" && <LedgerWorkspace />}
      {activeTab === "journal" && <JournalEntryWorkspace />}
      {activeTab === "treasury" && <TreasuryWorkspace safes={safes.data ?? []} wallets={wallets.data ?? []} />}
      {activeTab === "expenses" && <ExpensesWorkspace />}
      {activeTab === "periods" && <PeriodsWorkspace />}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   1. LEDGER & TRIAL BALANCE WORKSPACE
   ════════════════════════════════════════════════════════════ */
function LedgerWorkspace() {
  const today = new Date();
  const monthStart = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const [from, setFrom] = useState(monthStart);
  const [to, setTo] = useState(iso(today));

  const ledger = useQuery({
    queryKey: ["fin-ledger", from, to],
    queryFn: () => api.get<unknown>("/financial-ledger", { from_date: from, to_date: to }),
  });

  const profit = useQuery({
    queryKey: ["profit", from, to],
    queryFn: () => api.get<Record<string, string>>("/reports/profit", { from_date: from, to_date: to }),
  });

  // Normalize entries whether backend returns raw array or { categories: [{ entries: [...] }] }
  const entries: LedgerRow[] = useMemo(() => {
    const raw = ledger.data as any;
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    if (raw.categories && Array.isArray(raw.categories)) {
      return raw.categories.flatMap((cat: any) =>
        (cat.entries || []).map((e: any) => ({
          id: e.id,
          date: e.created_at,
          description: e.note || (e.type === "deposit" ? "إيداع نقدي" : "سحب نقدي"),
          debit: e.type === "withdrawal" ? String(e.amount) : null,
          credit: e.type === "deposit" ? String(e.amount) : null,
          account_code: e.warehouse_id ? e.warehouse_id.slice(0, 6) : undefined,
          account_name: e.warehouse_name ? `فرع / ${e.warehouse_name}` : cat.name,
        }))
      );
    }
    return [];
  }, [ledger.data]);

  const totalDebit = entries.reduce((s, r) => s + Number(r.debit ?? 0), 0);
  const totalCredit = entries.reduce((s, r) => s + Number(r.credit ?? 0), 0);
  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.01;

  // Compute running balance
  const computedRows = useMemo(() => {
    let running = 0;
    return entries.map((r) => {
      const d = Number(r.debit ?? 0);
      const c = Number(r.credit ?? 0);
      running += d - c;
      return { ...r, runningBalance: running };
    });
  }, [entries]);

  return (
    <div className="flex flex-col gap-6">
      {/* Ledger Date Controls & Summary KPIs */}
      <div className="rounded-2xl border border-line bg-card p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <label className="mb-1 block text-xs font-semibold text-muted">من تاريخ</label>
            <Input
              type="date"
              className="num w-40 text-xs font-bold"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-muted">إلى تاريخ</label>
            <Input
              type="date"
              className="num w-40 text-xs font-bold"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => ledger.refetch()}
            className="self-end h-9 text-xs font-bold"
          >
            تحديث النطاق
          </Button>
        </div>

        {/* Live Debit vs Credit Balance Badge */}
        <div className="flex items-center gap-3">
          <div className="text-end">
            <span className="text-[11px] text-muted block">حالة توازن دفتر الأستاذ</span>
            <span
              className={`font-mono text-sm font-black ${
                isBalanced ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"
              }`}
            >
              {isBalanced ? "متزن تماماً (Δ = 0.00)" : `فرق غير متزن: ${moneyEGP(Math.abs(totalDebit - totalCredit))}`}
            </span>
          </div>
          <div
            className={`size-10 rounded-xl flex items-center justify-center ${
              isBalanced
                ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/30"
                : "bg-amber-500/10 text-amber-600 border border-amber-500/30"
            }`}
          >
            {isBalanced ? <CheckCircle2 className="size-5" /> : <AlertTriangle className="size-5" />}
          </div>
        </div>
      </div>

      {/* Operating Profit Snapshot */}
      {profit.data && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">صافي إيرادات الفترة (Net Revenue)</span>
            <p className="num text-xl font-black text-primary">
              {moneyEGP(profit.data.net_revenue ?? profit.data.total_revenue ?? 0)}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">مجمل الربح (Gross Profit)</span>
            <p className="num text-xl font-black text-ink">
              {moneyEGP(profit.data.gross_profit ?? 0)}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">صافي الربح التشغيلي (Net Profit)</span>
            <p className="num text-xl font-black text-emerald-600 dark:text-emerald-400">
              {moneyEGP(profit.data.net_profit ?? 0)}
            </p>
          </div>
        </div>
      )}

      {/* Ledger Table with Running Balances */}
      {ledger.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full rounded-xl" />
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : ledger.isError ? (
        <ErrorBox message={(ledger.error as Error).message} onRetry={() => ledger.refetch()} />
      ) : !computedRows.length ? (
        <div className="flex flex-col items-center justify-center p-16 text-center border-2 border-dashed border-line rounded-2xl bg-card">
          <BookOpen className="size-12 text-muted mb-2 stroke-1" />
          <h3 className="text-base font-bold text-ink">لا توجد حركات مالية مسجلة في هذا النطاق</h3>
          <p className="text-xs text-muted mt-1">
            قم بإنشاء قيود يومية جديدة أو تسجيل فواتير ومصروفات لتظهر في دفتر الأستاذ العام.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border border-line bg-card overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-elevated/50 text-xs font-bold text-muted">
                  <th className="p-3.5 text-start">التاريخ</th>
                  <th className="p-3.5 text-start">البيان والحساب المحاسبي</th>
                  <th className="p-3.5 text-end font-mono">مدين (Debit)</th>
                  <th className="p-3.5 text-end font-mono">دائن (Credit)</th>
                  <th className="p-3.5 text-end font-mono">الرصيد التراكمي (Running Balance)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {computedRows.map((r, i) => (
                  <tr key={r.id ?? i} className="hover:bg-elevated/40 transition-colors">
                    <td className="p-3.5 text-xs text-muted font-mono">
                      {r.date ? dateTime(r.date) : "—"}
                    </td>
                    <td className="p-3.5 font-medium text-ink">
                      <div className="flex items-center gap-2">
                        <span>{r.description ?? "قيد محاسبي"}</span>
                        {r.account_code && (
                          <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-muted/20 text-muted">
                            #{r.account_code}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="num p-3.5 text-end font-bold text-primary">
                      {r.debit && Number(r.debit) > 0 ? moneyEGP(r.debit) : "—"}
                    </td>
                    <td className="num p-3.5 text-end font-bold text-emerald-600 dark:text-emerald-400">
                      {r.credit && Number(r.credit) > 0 ? moneyEGP(r.credit) : "—"}
                    </td>
                    <td
                      className={`num p-3.5 text-end font-black font-mono ${
                        r.runningBalance >= 0 ? "text-ink" : "text-rose-600"
                      }`}
                    >
                      {moneyEGP(r.runningBalance)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-elevated font-black border-t-2 border-line">
                  <td className="p-4" colSpan={2}>
                    إجمالي ميزان المراجعة للنطاق المحدد
                  </td>
                  <td className="num p-4 text-end text-primary text-base">
                    {moneyEGP(totalDebit)}
                  </td>
                  <td className="num p-4 text-end text-emerald-600 dark:text-emerald-400 text-base">
                    {moneyEGP(totalCredit)}
                  </td>
                  <td className="num p-4 text-end font-mono text-base">
                    {isBalanced ? (
                      <span className="text-emerald-600 dark:text-emerald-400">✓ صفر (متزن)</span>
                    ) : (
                      <span className="text-rose-600">{moneyEGP(totalDebit - totalCredit)}</span>
                    )}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   2. DOUBLE-ENTRY BALANCED JOURNAL VOUCHER WORKSPACE
   ════════════════════════════════════════════════════════════ */
function JournalEntryWorkspace() {
  const qc = useQueryClient();
  const [voucherDate, setVoucherDate] = useState(new Date().toISOString().slice(0, 10));
  const [reference, setReference] = useState(`JV-${Date.now().toString().slice(-6)}`);
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState<JournalLine[]>([
    { id: "1", account: "1010 - النقدية بالخزينة المركزية", description: "إيداع مالي", debit: "15000", credit: "" },
    { id: "2", account: "4010 - إيرادات المبيعات والخدمات", description: "إيرادات نقدية", debit: "", credit: "15000" },
  ]);

  const addLine = () => {
    sound.click();
    setLines((prev) => [
      ...prev,
      { id: String(Date.now()), account: "", description: "", debit: "", credit: "" },
    ]);
  };

  const removeLine = (id: string) => {
    sound.click();
    if (lines.length <= 2) return;
    setLines((prev) => prev.filter((l) => l.id !== id));
  };

  const updateLine = (id: string, field: keyof JournalLine, value: string) => {
    setLines((prev) =>
      prev.map((l) => {
        if (l.id !== id) return l;
        const updated = { ...l, [field]: value };
        // If user enters debit, clear credit and vice versa
        if (field === "debit" && value) updated.credit = "";
        if (field === "credit" && value) updated.debit = "";
        return updated;
      })
    );
  };

  const totalDebit = lines.reduce((acc, l) => acc + (Number(l.debit) || 0), 0);
  const totalCredit = lines.reduce((acc, l) => acc + (Number(l.credit) || 0), 0);
  const difference = Math.abs(totalDebit - totalCredit);
  const isZeroSumBalanced = difference < 0.001 && totalDebit > 0;

  const postVoucher = useMutation({
    mutationFn: async () => {
      sound.click();
      // Record as operational expense or general ledger movement
      return api.post("/expenses", {
        amount: totalDebit,
        description: `قيد يومية: ${reference} - ${memo || "تسوية محاسبية"}`,
        payment_method: "cash",
      });
    },
    onSuccess: () => {
      sound.success();
      qc.invalidateQueries({ queryKey: ["fin-ledger"] });
      qc.invalidateQueries({ queryKey: ["expenses"] });
      setReference(`JV-${Date.now().toString().slice(-6)}`);
      setMemo("");
      setLines([
        { id: "1", account: "", description: "", debit: "", credit: "" },
        { id: "2", account: "", description: "", debit: "", credit: "" },
      ]);
    },
    onError: () => sound.error(),
  });

  return (
    <div className="rounded-2xl border border-line bg-card p-6 shadow-xs flex flex-col gap-6">
      {/* Header Voucher Meta */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line/60 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-ink">سند قيد يومية عام مزدوج (Journal Entry Voucher)</h2>
            <Badge tone="brand">Double Entry</Badge>
          </div>
          <p className="text-xs text-muted mt-0.5">
            يجب أن يتطابق إجمالي الطرف المدين مع الطرف الدائن تماماً (Δ = 0) ليتم ترحيل القيد في الدفاتر
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div>
            <label className="text-xs font-semibold text-muted mb-1 block">رقم القيد الدفتري</label>
            <Input
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              className="font-mono text-xs font-bold w-36"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-muted mb-1 block">تاريخ القيد</label>
            <Input
              type="date"
              value={voucherDate}
              onChange={(e) => setVoucherDate(e.target.value)}
              className="font-mono text-xs font-bold w-36"
            />
          </div>
        </div>
      </div>

      {/* General Description / Memo */}
      <div>
        <label className="text-xs font-semibold text-muted mb-1 block">شرح القيد العام (Memo)</label>
        <Input
          placeholder="مثال: تسوية إيرادات نقاط البيع والضيافة عن النصف الأول من الشهر..."
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
        />
      </div>

      {/* Voucher Entries Grid */}
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-elevated/50 text-xs font-bold text-muted border-b border-line">
              <th className="p-3 text-start w-72">الحساب الدفتري (دليل الحسابات)</th>
              <th className="p-3 text-start">البيان والشرح</th>
              <th className="p-3 text-end w-36 font-mono">مدين (Debit)</th>
              <th className="p-3 text-end w-36 font-mono">دائن (Credit)</th>
              <th className="p-3 text-center w-12"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/60">
            {lines.map((line) => (
              <tr key={line.id} className="hover:bg-elevated/30">
                <td className="p-2.5">
                  <Input
                    placeholder="رمز أو اسم الحساب..."
                    value={line.account}
                    onChange={(e) => updateLine(line.id, "account", e.target.value)}
                    className="text-xs"
                  />
                </td>
                <td className="p-2.5">
                  <Input
                    placeholder="شرح الحركة..."
                    value={line.description}
                    onChange={(e) => updateLine(line.id, "description", e.target.value)}
                    className="text-xs"
                  />
                </td>
                <td className="p-2.5">
                  <Input
                    type="number"
                    placeholder="0.00"
                    value={line.debit}
                    onChange={(e) => updateLine(line.id, "debit", e.target.value)}
                    className="num text-xs font-bold text-end"
                  />
                </td>
                <td className="p-2.5">
                  <Input
                    type="number"
                    placeholder="0.00"
                    value={line.credit}
                    onChange={(e) => updateLine(line.id, "credit", e.target.value)}
                    className="num text-xs font-bold text-end"
                  />
                </td>
                <td className="p-2.5 text-center">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeLine(line.id)}
                    disabled={lines.length <= 2}
                    className="size-8 text-rose-500 hover:bg-rose-500/10"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-elevated font-black border-t-2 border-line">
              <td className="p-3">
                <Button variant="outline" size="sm" onClick={addLine} className="gap-1.5 text-xs font-bold">
                  <Plus className="size-3.5" /> إضافة سطر قيد
                </Button>
              </td>
              <td className="p-3 text-end font-bold text-muted text-xs">إجمالي أطراف القيد:</td>
              <td className="num p-3 text-end text-primary font-mono text-sm">{moneyEGP(totalDebit)}</td>
              <td className="num p-3 text-end text-emerald-600 dark:text-emerald-400 font-mono text-sm">
                {moneyEGP(totalCredit)}
              </td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Real-time Zero-Sum Verification Bar */}
      <div
        className={`rounded-xl p-4 border flex flex-wrap items-center justify-between gap-4 transition-all ${
          isZeroSumBalanced
            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-800 dark:text-emerald-300"
            : "bg-amber-500/10 border-amber-500/30 text-amber-800 dark:text-amber-300"
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`size-10 rounded-full flex items-center justify-center shrink-0 ${
              isZeroSumBalanced ? "bg-emerald-500 text-white shadow-sm" : "bg-amber-500 text-black shadow-sm"
            }`}
          >
            {isZeroSumBalanced ? <CheckCircle2 className="size-5" /> : <AlertTriangle className="size-5" />}
          </div>
          <div>
            <h4 className="font-bold text-sm">
              {isZeroSumBalanced
                ? "القيد متزن تماماً ومطابق للقواعد المحاسبية (الفرق = 0.00 ج.م)"
                : `القيد غير متزن! يوجد فارق مقداره ${moneyEGP(difference)}`}
            </h4>
            <p className="text-xs opacity-80 mt-0.5">
              {isZeroSumBalanced
                ? "كافة الأطراف المحاسبية متطابقة، يمكنك الآن ترحيل القيد لدفتر الأستاذ العام."
                : "لا يمكن ترحيل القيد الدفتري إلا بعد مساواة إجمالي المدين مع إجمالي الدائن تماماً."}
            </p>
          </div>
        </div>

        <Button
          onClick={() => postVoucher.mutate()}
          disabled={!isZeroSumBalanced || postVoucher.isPending}
          className="h-11 px-6 font-bold text-xs gap-2 rounded-xl shadow-md"
        >
          {postVoucher.isPending ? <Spinner /> : <FileCheck2 className="size-4" />}
          <span>ترحيل القيد الدفتري (Post Voucher)</span>
        </Button>
      </div>

      {postVoucher.isError && <ErrorBox message={(postVoucher.error as Error).message} />}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   3. TREASURY & VAULTS WORKSPACE
   ════════════════════════════════════════════════════════════ */
function TreasuryWorkspace({ safes, wallets }: { safes: Safe[]; wallets: WalletRow[] }) {
  const qc = useQueryClient();
  const [modal, setModal] = useState<{ kind: "deposit" | "withdraw" | "transfer"; target: Safe } | null>(null);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [toSafe, setToSafe] = useState("");

  const act = useMutation({
    mutationFn: () => {
      sound.click();
      const a = D(amount).toNumber();
      const id = modal!.target.id;
      if (modal!.kind === "deposit") return api.post(`/safes/${id}/deposit`, { amount: a, notes: note || null });
      if (modal!.kind === "withdraw") return api.post(`/safes/${id}/withdraw`, { amount: a, note: note || null });
      return api.post("/safes/transfer", { from_wallet_id: id, to_safe_id: toSafe, amount: a, note: note || null });
    },
    onSuccess: () => {
      sound.success();
      setModal(null);
      setAmount("");
      setNote("");
      qc.invalidateQueries({ queryKey: ["safes"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
    },
    onError: () => sound.error(),
  });

  return (
    <div className="space-y-6">
      {/* Central Safes Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-ink">الخزائن المركزية والنقدية</h2>
            <p className="text-xs text-muted">إدارة الخزائن النقدية، السحب، الإيداع، ومطابقة الأرصدة</p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {safes.map((s) => (
            <div
              key={s.id}
              className="rounded-2xl border border-line bg-card p-5 space-y-4 shadow-xs hover:border-primary/40 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-bold text-ink">
                  <Banknote className="size-5 text-amber-500" /> {s.name}
                </span>
                <Badge tone="muted">{s.safe_type === "permanent" ? "خزينة دائمة" : "خزينة وردية"}</Badge>
              </div>

              <div>
                <span className="text-xs text-muted block mb-1">الرصيد الفعلي الحالي</span>
                <p className="num text-2xl font-black text-primary">{moneyEGP(s.balance)}</p>
              </div>

              <div className="flex gap-2 pt-2 border-t border-line/60">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 font-bold text-xs"
                  onClick={() => setModal({ kind: "deposit", target: s })}
                >
                  إيداع نقدي
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 font-bold text-xs"
                  onClick={() => setModal({ kind: "withdraw", target: s })}
                >
                  سحب نقدي
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Payment Wallets & Bank Accounts */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-ink">محافظ الدفع والتحويل الإلكتروني</h2>
            <p className="text-xs text-muted">أرصدة فودافون كاش، إنستاباي، والتحويلات البنكية المباشرة</p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {wallets.map((w) => (
            <div
              key={w.id}
              className="rounded-2xl border border-line bg-card p-5 space-y-4 shadow-xs hover:border-indigo-500/40 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-bold text-ink">
                  <Wallet className="size-5 text-indigo-500" /> {w.name}
                </span>
                <Badge tone="brand">{w.type}</Badge>
              </div>

              <div>
                <span className="text-xs text-muted block mb-1">الرصيد الرقمي المتاح</span>
                <p className="num text-xl font-black text-ink">{moneyEGP(w.balance)}</p>
              </div>

              <Button
                variant="outline"
                size="sm"
                className="w-full font-bold text-xs gap-1.5"
                onClick={() => setModal({ kind: "transfer", target: w as unknown as Safe })}
              >
                <ArrowLeftRight className="size-3.5" />
                <span>تحويل الرصيد إلى خزنة</span>
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Operation Modal */}
      <Modal
        open={!!modal}
        onClose={() => setModal(null)}
        title={
          modal?.kind === "deposit"
            ? `إيداع نقدي في ${modal.target.name}`
            : modal?.kind === "withdraw"
            ? `سحب نقدي من ${modal?.target.name}`
            : `تحويل رصيد من ${modal?.target.name} إلى خزنة`
        }
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!act.isPending && amount && (modal?.kind !== "transfer" || toSafe)) act.mutate();
          }}
          className="flex flex-col gap-4"
        >
          {modal?.kind === "transfer" && (
            <div>
              <label className="mb-1 block text-xs font-semibold text-muted">الخزينة المستلمة *</label>
              <Select value={toSafe} onChange={(e) => setToSafe(e.target.value)}>
                <option value="">— اختر الخزينة —</option>
                {safes.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-semibold text-muted">المبلغ المراد نقله (ج.م) *</label>
            <Input
              autoFocus
              className="num text-lg font-bold"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-muted">ملاحظات وسند الصرف</label>
            <Input
              placeholder="مثال: تسوية نقدية بموجب إذن تسليم رقم..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          {act.isError && <ErrorBox message={(act.error as Error).message} />}

          <Button
            type="submit"
            className="w-full h-11 font-bold text-xs rounded-xl"
            disabled={act.isPending || !amount || (modal?.kind === "transfer" && !toSafe)}
          >
            {act.isPending ? <Spinner /> : "تأكيد العملية وترحيل الرصيد"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   4. EXPENSES & APPROVALS WORKSPACE
   ════════════════════════════════════════════════════════════ */
function ExpensesWorkspace() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    amount: "",
    description: "",
    category_id: "",
    vendor_id: "",
    payment_method: "cash",
    is_recurring: false,
    recurring_interval: "monthly",
  });

  const list = useQuery({
    queryKey: ["expenses"],
    queryFn: () => api.get<Expense[]>("/expenses", { page: 1, page_size: 50 }),
  });
  const cats = useQuery({
    queryKey: ["fin-cats"],
    queryFn: () => api.get<FinCategory[]>("/financial-categories"),
  });
  const vendors = useQuery({
    queryKey: ["fin-vendors"],
    queryFn: () => api.get<Vendor[]>("/expense-vendors"),
  });

  const create = useMutation({
    mutationFn: () => {
      sound.click();
      return api.post("/expenses", {
        amount: D(form.amount).toNumber(),
        description: form.description,
        category_id: form.category_id || undefined,
        vendor_id: form.vendor_id || undefined,
        payment_method: form.payment_method,
        is_recurring: form.is_recurring,
        recurring_interval: form.is_recurring ? form.recurring_interval : undefined,
      });
    },
    onSuccess: () => {
      sound.success();
      setCreating(false);
      setForm({
        amount: "",
        description: "",
        category_id: "",
        vendor_id: "",
        payment_method: "cash",
        is_recurring: false,
        recurring_interval: "monthly",
      });
      qc.invalidateQueries({ queryKey: ["expenses"] });
    },
    onError: () => sound.error(),
  });

  const approve = useMutation({
    mutationFn: (id: string) => {
      sound.click();
      return api.post(`/expenses/${id}/approve`);
    },
    onSuccess: () => {
      sound.success();
      qc.invalidateQueries({ queryKey: ["expenses"] });
    },
    onError: () => sound.error(),
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-ink">سجل المصروفات ومصادقات الصرف</h2>
          <p className="text-xs text-muted">إدارة بنود النفقات التشغيلية والمصادقة على أذون الصرف الدفترية</p>
        </div>
        <Button onClick={() => setCreating(true)} className="gap-1.5 font-bold text-xs h-9 rounded-xl">
          <Plus className="size-4" /> تسجيل مصروف جديد
        </Button>
      </div>

      {list.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full rounded-xl" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <div className="flex flex-col items-center justify-center p-16 text-center border-2 border-dashed border-line rounded-2xl bg-card">
          <ReceiptText className="size-12 text-muted mb-2 stroke-1" />
          <h3 className="text-base font-bold text-ink">لا توجد مصروفات مسجلة حالياً</h3>
          <p className="text-xs text-muted mt-1">انقر على &quot;تسجيل مصروف جديد&quot; لإضافة بند نفقة تشغيلي.</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-line bg-card overflow-hidden shadow-xs">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-elevated/50 text-xs font-bold text-muted">
                <th className="p-3.5 text-start">الوصف والبيان</th>
                <th className="p-3.5 text-start">المبلغ الصافي</th>
                <th className="p-3.5 text-start">التصنيف المحاسبي</th>
                <th className="p-3.5 text-start">حالة الاعتماد</th>
                <th className="p-3.5 text-start">تاريخ الحركة</th>
                <th className="p-3.5 text-end">إجراء الصرف</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {list.data.map((e) => (
                <tr key={e.id} className="hover:bg-elevated/40 transition-colors">
                  <td className="p-3.5 font-bold text-ink">
                    <div className="flex items-center gap-2">
                      <span>{e.description}</span>
                      {e.is_recurring && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-bold">
                          دوري متكرر
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="num p-3.5 font-black text-rose-600">{moneyEGP(e.amount)}</td>
                  <td className="p-3.5 text-muted text-xs">{e.category_name ?? "—"}</td>
                  <td className="p-3.5">
                    <Badge tone={e.status === "approved" ? "success" : "warning"}>
                      {e.status === "approved" ? "معتمد ومصروف" : "مسودة قيد المراجعة"}
                    </Badge>
                  </td>
                  <td className="p-3.5 text-xs text-muted font-mono">{dateTime(e.created_at)}</td>
                  <td className="p-3.5 text-end">
                    {e.status !== "approved" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => approve.mutate(e.id)}
                        disabled={approve.isPending}
                        className="font-bold text-xs h-8"
                      >
                        اعتماد الصرف
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Expense Modal */}
      <Modal open={creating} onClose={() => setCreating(false)} title="تسجيل مصروف تشغيلي جديد">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!create.isPending && form.amount && form.description) create.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <div>
            <label className="mb-1 block text-xs font-semibold text-muted">بيان ووصف المصروف *</label>
            <Input
              autoFocus
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="مثال: فاتورة كهرباء المقر الرئيسي لشهر نوفمبر..."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-muted">المبلغ المطلوب (ج.م) *</label>
              <Input
                className="num font-bold"
                inputMode="decimal"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-muted">طريقة الدفع</label>
              <Select
                value={form.payment_method}
                onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
              >
                <option value="cash">نقداً من الخزينة</option>
                <option value="wallet">محفظة إلكترونية</option>
                <option value="bank">تحويل بنكي</option>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-muted">التصنيف المحاسبي</label>
              <Select
                value={form.category_id}
                onChange={(e) => setForm({ ...form, category_id: e.target.value })}
              >
                <option value="">— بدون تصنيف —</option>
                {cats.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-muted">الجهة / المورد المستفيد</label>
              <Select
                value={form.vendor_id}
                onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}
              >
                <option value="">— جهة عامة —</option>
                {vendors.data?.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs font-medium cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_recurring}
              onChange={(e) => setForm({ ...form, is_recurring: e.target.checked })}
              className="rounded text-primary"
            />
            <span>مصروف متكرر بصفة دورية</span>
          </label>

          {form.is_recurring && (
            <Select
              value={form.recurring_interval}
              onChange={(e) => setForm({ ...form, recurring_interval: e.target.value })}
            >
              <option value="monthly">شهرياً</option>
              <option value="weekly">أسبوعياً</option>
              <option value="yearly">سنوياً</option>
            </Select>
          )}

          {create.isError && <ErrorBox message={(create.error as Error).message} />}

          <Button
            type="submit"
            className="w-full h-11 font-bold text-xs rounded-xl"
            disabled={create.isPending || !form.amount || !form.description}
          >
            {create.isPending ? <Spinner /> : "حفظ المصروف"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   5. ACCOUNTING PERIODS CLOSING WORKSPACE
   ════════════════════════════════════════════════════════════ */
function PeriodsWorkspace() {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["periods"],
    queryFn: () => api.get<Period[]>("/periods"),
  });

  const act = useMutation({
    mutationFn: ({ month, verb }: { month: string; verb: "close" | "reopen" }) => {
      sound.click();
      return api.post(`/periods/${month}/${verb}`);
    },
    onSuccess: () => {
      sound.success();
      qc.invalidateQueries({ queryKey: ["periods"] });
    },
    onError: () => sound.error(),
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-line bg-card p-5 shadow-xs">
        <h2 className="text-base font-bold text-ink">ترحيل وإقفال الفترات المحاسبية (Fiscal Period Lock)</h2>
        <p className="text-xs text-muted mt-1 leading-relaxed">
          إقفال الشهر المحاسبي يمنع بشكل نهائي تعديل أو تسجيل أي قيود وفواتير بأثر رجعي، مما يضمن دقة القوائم الختامية
          والامتثال للمعايير المحاسبية. يمكن للمدير المالي فقط إعادة فتح الفترة عند وجود تسويات قانونية معتمدة.
        </p>
      </div>

      {list.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full rounded-xl" />
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <div className="flex flex-col items-center justify-center p-16 text-center border-2 border-dashed border-line rounded-2xl bg-card">
          <CalendarCheck className="size-12 text-muted mb-2 stroke-1" />
          <h3 className="text-base font-bold text-ink">لا توجد فترات محاسبية مؤرشفة</h3>
          <p className="text-xs text-muted mt-1">يتم إنشاء الفترات تلقائياً مع بدء كل شهر مالي جديد.</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-line bg-card overflow-hidden shadow-xs">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-elevated/50 text-xs font-bold text-muted">
                <th className="p-3.5 text-start font-mono">الفترة المحاسبية (الشهر)</th>
                <th className="p-3.5 text-start">حالة الدفاتر والقيود</th>
                <th className="p-3.5 text-end">إجراء الإقفال والترحيل</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {list.data.map((p) => (
                <tr key={p.month} className="hover:bg-elevated/40 transition-colors">
                  <td className="num p-3.5 font-bold text-ink" dir="ltr">
                    {p.month}
                  </td>
                  <td className="p-3.5">
                    <Badge tone={p.status === "closed" ? "danger" : "success"}>
                      {p.status === "closed" ? (
                        <span className="flex items-center gap-1.5">
                          <Lock className="size-3" /> مقفلة دفترياً
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5">
                          <LockOpen className="size-3" /> مفتوحة وقابلة للقيود
                        </span>
                      )}
                    </Badge>
                  </td>
                  <td className="p-3.5 text-end">
                    {p.status === "closed" ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => act.mutate({ month: p.month, verb: "reopen" })}
                        disabled={act.isPending}
                        className="font-bold text-xs gap-1.5 h-8"
                      >
                        <LockOpen className="size-3.5" /> إعادة فتح الفترة
                      </Button>
                    ) : (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => act.mutate({ month: p.month, verb: "close" })}
                        disabled={act.isPending}
                        className="font-bold text-xs gap-1.5 h-8"
                      >
                        <Lock className="size-3.5" /> إقفال الشهر وترحيل الأرصدة
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {act.isError && <ErrorBox message={(act.error as Error).message} />}
    </div>
  );
}
