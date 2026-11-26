/**
 * PAGE CONTRACT
 * Page: الإدارة المالية (/finance)
 * Archetype: Treasury & expenses console
 * User: المدير المالي، رئيس الحسابات، والمحاسب
 * Purpose: حركة الخزينة والمصروفات، الخزائن والمحافظ (إنشاء وتعديل وإيقاف)، اعتماد المصروفات وإلغاؤها، وإقفال الفترات.
 * The journal, trial balance and reports are the accounting module's screens (ADR-014).
 */
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Landmark, Lock, LockOpen, Wallet, ReceiptText, BookOpen, CalendarCheck, Building2, Coins, Tags } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { D, dateTime } from "@/lib/format";
import { sound } from "@/lib/sound";
import { Badge, ErrorBox, Input } from "@/components/ui";
import { moneyIn, useCurrency } from "@app/lib/currency";
import type { PeriodMonth, Safe, WalletRow } from "./api";
import { CategoriesVendorsWorkspace } from "./components/CategoriesVendorsWorkspace";
import { ExpensesWorkspace } from "./components/ExpensesWorkspace";
import { PeriodsWorkspace } from "./components/PeriodsWorkspace";
import { TreasuryWorkspace } from "./components/TreasuryWorkspace";

interface CashEntry {
  id: string;
  type: "deposit" | "withdrawal" | "expense";
  amount: number;
  note: string | null;
  created_at: string | null;
  category_name: string | null;
  warehouse_name: string | null;
  cashier_name: string | null;
}

interface CashMovements {
  total_income: number;
  total_expense: number;
  net: number;
  categories: { name: string; entries: CashEntry[] }[];
}

const TABS = [
  { key: "cash", label: "حركة الخزينة والمصروفات", icon: BookOpen },
  { key: "treasury", label: "الخزائن والمحافظ النقدية", icon: Coins },
  { key: "expenses", label: "مصادقات وسجل المصروفات", icon: ReceiptText },
  { key: "categories", label: "التصنيفات وجهات الصرف", icon: Tags },
  { key: "periods", label: "إقفال الفترات المالية", icon: CalendarCheck },
] as const;

export default function FinancePage() {
  const [activeTab, setActiveTab] = useState<string>("cash");
  const cur = useCurrency();

  // Load high-level treasury and accounting periods for the ribbon
  const safes = useQuery({ queryKey: ["safes"], queryFn: () => api.get<Safe[]>("/safes") });
  const wallets = useQuery({ queryKey: ["wallets"], queryFn: () => api.get<WalletRow[]>("/wallets") });
  const periods = useQuery({ queryKey: ["periods"], queryFn: () => api.get<PeriodMonth[]>("/periods") });

  const totalVaults = (safes.data ?? []).reduce((acc, s) => acc.plus(D(s.balance ?? 0)), D(0));
  const totalWallets = (wallets.data ?? []).reduce((acc, w) => acc.plus(D(w.balance ?? 0)), D(0));
  const totalLiquidity = totalVaults.plus(totalWallets);

  const currentPeriod = periods.data?.find((p) => p.current) ?? {
    month: new Date().toISOString().slice(0, 7),
    status: "open",
  };

  return (
    <div className="flex flex-col gap-6" dir="rtl">
      {/* ── Executive Accounting Ribbon & Fiscal Lock Guard ── */}
      <div className="rounded-2xl border border-line bg-card p-5 md:p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line/60 pb-5">
          <div className="flex items-center gap-3">
            <div className="size-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-xs">
              <Landmark className="size-6" />
            </div>
            <div>
              <h1 className="text-xl md:text-2xl font-black tracking-tight text-ink">الإدارة المالية</h1>
              <p className="text-xs text-muted mt-0.5">
                حركة الخزينة والمصروفات، الخزائن والمحافظ، وإقفال الفترات
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
                  <Lock className="size-3" /> مغلقة
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <LockOpen className="size-3" /> مفتوحة
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
              {moneyIn(totalLiquidity, cur)}
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
              {moneyIn(totalVaults, cur)}
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
              {moneyIn(totalWallets, cur)}
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
      {activeTab === "cash" && <CashMovementsWorkspace />}
      {activeTab === "treasury" && <TreasuryWorkspace />}
      {activeTab === "expenses" && <ExpensesWorkspace />}
      {activeTab === "categories" && <CategoriesVendorsWorkspace />}
      {activeTab === "periods" && <PeriodsWorkspace />}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   1. CASH MOVEMENTS — the shift drawers' deposits, withdrawals and expenses.
   Not a ledger: the journal and trial balance come with ADR-014 (D9).
   ════════════════════════════════════════════════════════════ */
const CASH_TYPE_LABEL: Record<CashEntry["type"], string> = { deposit: "إيداع", withdrawal: "سحب", expense: "مصروف" };

/** Money comes as decimal strings (REP-15). */
interface Profit { net_revenue: string; gross_profit: string; net_profit: string; source: "ledger" | "operations" }

function CashMovementsWorkspace() {
  const cur = useCurrency();
  const today = new Date();
  const monthStart = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const [from, setFrom] = useState(monthStart);
  const [to, setTo] = useState(iso(today));

  const movements = useQuery({
    queryKey: ["fin-ledger", from, to],
    queryFn: () => api.get<CashMovements>("/financial-ledger", { from_date: from, to_date: to }),
  });

  // Profit needs reports:finance; it comes from the ledger when accounting is on (source "ledger").
  const canProfit = useAuth((s) => s.can("reports:finance"));
  const profit = useQuery({
    queryKey: ["profit", from, to],
    queryFn: () => api.get<Profit>("/reports/profit", { from_date: from, to_date: to }),
    enabled: canProfit,
  });

  const rows: CashEntry[] = useMemo(
    () =>
      (movements.data?.categories ?? [])
        .flatMap((c) => c.entries.map((e) => ({ ...e, category_name: e.category_name ?? c.name })))
        .sort((x, y) => (y.created_at ?? "").localeCompare(x.created_at ?? "")),
    [movements.data],
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-line bg-card p-5 shadow-xs flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-semibold text-muted">من تاريخ</label>
            <Input type="date" className="num w-40 text-xs font-bold" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-muted">إلى تاريخ</label>
            <Input type="date" className="num w-40 text-xs font-bold" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
        </div>
        <p className="text-xs text-muted max-w-md">
          إيداعات ومسحوبات ومصروفات أدراج الورديات في الفترة المحددة. هذه ليست قيودًا محاسبية ولا ميزان مراجعة.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
          <span className="text-xs text-muted block mb-1 font-medium">إجمالي الوارد</span>
          <p className="num text-xl font-black text-emerald-600 dark:text-emerald-400">{moneyIn(movements.data?.total_income ?? 0, cur)}</p>
        </div>
        <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
          <span className="text-xs text-muted block mb-1 font-medium">إجمالي المنصرف</span>
          <p className="num text-xl font-black text-rose-600">{moneyIn(movements.data?.total_expense ?? 0, cur)}</p>
        </div>
        <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
          <span className="text-xs text-muted block mb-1 font-medium">الصافي</span>
          <p className="num text-xl font-black text-ink">{moneyIn(movements.data?.net ?? 0, cur)}</p>
        </div>
      </div>

      {canProfit && profit.isError && (
        <ErrorBox message={(profit.error as Error).message} onRetry={() => profit.refetch()} />
      )}
      {canProfit && profit.data && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">صافي إيرادات الفترة</span>
            <p className="num text-xl font-black text-primary">
              {moneyIn(profit.data.net_revenue, cur)}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">مجمل الربح</span>
            <p className="num text-xl font-black text-ink">{moneyIn(profit.data.gross_profit, cur)}</p>
          </div>
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">صافي الربح</span>
            <p className="num text-xl font-black text-emerald-600 dark:text-emerald-400">{moneyIn(profit.data.net_profit, cur)}</p>
            <span className="text-[11px] text-muted block mt-1">
              {profit.data.source === "ledger" ? "من القيود المحاسبية" : "من المستندات، بعد المصروفات المعتمدة وبدون الضريبة"}
            </span>
          </div>
        </div>
      )}

      {movements.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full rounded-xl" />
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : movements.isError ? (
        <ErrorBox message={(movements.error as Error).message} onRetry={() => movements.refetch()} />
      ) : !rows.length ? (
        <div className="flex flex-col items-center justify-center p-16 text-center border-2 border-dashed border-line rounded-2xl bg-card">
          <BookOpen className="size-12 text-muted mb-2 stroke-1" />
          <h3 className="text-base font-bold text-ink">لا توجد حركات في هذه الفترة</h3>
          <p className="text-xs text-muted mt-1">تظهر هنا إيداعات ومسحوبات ومصروفات أدراج الورديات.</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-line bg-card overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-elevated/50 text-xs font-bold text-muted">
                  <th className="p-3.5 text-start">التاريخ</th>
                  <th className="p-3.5 text-start">البيان</th>
                  <th className="p-3.5 text-start">النوع</th>
                  <th className="p-3.5 text-start">التصنيف</th>
                  <th className="p-3.5 text-start">الفرع</th>
                  <th className="p-3.5 text-end">وارد</th>
                  <th className="p-3.5 text-end">منصرف</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-elevated/40 transition-colors">
                    <td className="p-3.5 text-xs text-muted font-mono">{r.created_at ? dateTime(r.created_at) : "—"}</td>
                    <td className="p-3.5 font-medium text-ink">{r.note || "—"}</td>
                    <td className="p-3.5">
                      <Badge tone={r.type === "deposit" ? "success" : "warning"}>{CASH_TYPE_LABEL[r.type] ?? r.type}</Badge>
                    </td>
                    <td className="p-3.5 text-xs text-muted">{r.category_name ?? "—"}</td>
                    <td className="p-3.5 text-xs text-muted">{r.warehouse_name ?? "—"}</td>
                    <td className="num p-3.5 text-end font-bold text-emerald-600 dark:text-emerald-400">
                      {r.type === "deposit" ? moneyIn(r.amount, cur) : "—"}
                    </td>
                    <td className="num p-3.5 text-end font-bold text-rose-600">
                      {r.type !== "deposit" ? moneyIn(r.amount, cur) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
