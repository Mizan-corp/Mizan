/**
 * PAGE CONTRACT
 * Page: الإدارة المالية (/finance)
 * Archetype: Treasury & expenses console
 * User: المدير المالي، رئيس الحسابات، والمحاسب
 * Purpose: حركة الخزينة والمصروفات، الخزائن والمحافظ، اعتماد المصروفات وإلغاؤها، وإقفال الفترات.
 * There is no general ledger yet: the journal and trial balance come with ADR-014 (D9).
 */
import { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  Banknote,
  Landmark,
  Lock,
  LockOpen,
  Plus,
  Wallet,
  ReceiptText,
  BookOpen,
  CalendarCheck,
  Trash2,
  Building2,
  Coins,
  Ban,
} from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, dateTime, moneyEGP } from "@/lib/format";
import { sound } from "@/lib/sound";
import { Badge, Button, ErrorBox, Input, Modal, Select, Spinner } from "@/components/ui";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";

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
  status: "draft" | "approved" | "rejected" | "cancelled";
  created_at: string;
  is_recurring: boolean;
  payment_method: string | null;
  safe_id: string | null;
  wallet_id: string | null;
  category_name?: string | null;
  vendor_name?: string | null;
}

interface ExpensePage {
  data: Expense[];
  total: number;
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
  { key: "periods", label: "إقفال الفترات المالية", icon: CalendarCheck },
] as const;

export default function FinancePage() {
  const [activeTab, setActiveTab] = useState<string>("cash");

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
      {activeTab === "cash" && <CashMovementsWorkspace />}
      {activeTab === "treasury" && <TreasuryWorkspace safes={safes.data ?? []} wallets={wallets.data ?? []} />}
      {activeTab === "expenses" && <ExpensesWorkspace />}
      {activeTab === "periods" && <PeriodsWorkspace />}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   1. CASH MOVEMENTS — the shift drawers' deposits, withdrawals and expenses.
   Not a ledger: the journal and trial balance come with ADR-014 (D9).
   ════════════════════════════════════════════════════════════ */
const CASH_TYPE_LABEL: Record<CashEntry["type"], string> = { deposit: "إيداع", withdrawal: "سحب", expense: "مصروف" };

function CashMovementsWorkspace() {
  const today = new Date();
  const monthStart = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const [from, setFrom] = useState(monthStart);
  const [to, setTo] = useState(iso(today));

  const movements = useQuery({
    queryKey: ["fin-ledger", from, to],
    queryFn: () => api.get<CashMovements>("/financial-ledger", { from_date: from, to_date: to }),
  });

  const profit = useQuery({
    queryKey: ["profit", from, to],
    queryFn: () => api.get<Record<string, string>>("/reports/profit", { from_date: from, to_date: to }),
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
          <p className="num text-xl font-black text-emerald-600 dark:text-emerald-400">{moneyEGP(movements.data?.total_income ?? 0)}</p>
        </div>
        <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
          <span className="text-xs text-muted block mb-1 font-medium">إجمالي المنصرف</span>
          <p className="num text-xl font-black text-rose-600">{moneyEGP(movements.data?.total_expense ?? 0)}</p>
        </div>
        <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
          <span className="text-xs text-muted block mb-1 font-medium">الصافي</span>
          <p className="num text-xl font-black text-ink">{moneyEGP(movements.data?.net ?? 0)}</p>
        </div>
      </div>

      {profit.data && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">صافي إيرادات الفترة</span>
            <p className="num text-xl font-black text-primary">
              {moneyEGP(profit.data.net_revenue ?? profit.data.total_revenue ?? 0)}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">مجمل الربح</span>
            <p className="num text-xl font-black text-ink">{moneyEGP(profit.data.gross_profit ?? 0)}</p>
          </div>
          <div className="rounded-xl border border-line bg-card p-4 shadow-xs">
            <span className="text-xs text-muted block mb-1 font-medium">صافي الربح التشغيلي</span>
            <p className="num text-xl font-black text-emerald-600 dark:text-emerald-400">{moneyEGP(profit.data.net_profit ?? 0)}</p>
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
                      {r.type === "deposit" ? moneyEGP(r.amount) : "—"}
                    </td>
                    <td className="num p-3.5 text-end font-bold text-rose-600">
                      {r.type !== "deposit" ? moneyEGP(r.amount) : "—"}
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

/* ════════════════════════════════════════════════════════════
   2. TREASURY & VAULTS WORKSPACE
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
                <Badge tone="muted">
                  {s.safe_type === "bank" ? "حساب بنكي" : s.safe_type === "permanent" ? "خزينة دائمة" : "خزينة وردية"}
                </Badge>
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
   3. EXPENSES & APPROVALS WORKSPACE
   ════════════════════════════════════════════════════════════ */
const EXPENSE_STATUS: Record<Expense["status"], { label: string; tone: "success" | "warning" | "danger" | "muted" }> = {
  draft: { label: "مسودة بانتظار الاعتماد", tone: "warning" },
  approved: { label: "معتمد ومصروف", tone: "success" },
  rejected: { label: "مرفوض", tone: "danger" },
  cancelled: { label: "ملغى (أُعيد المبلغ)", tone: "muted" },
};

const sourceOf = (e: Expense) => (e.wallet_id ? `wallet:${e.wallet_id}` : e.safe_id ? `safe:${e.safe_id}` : "");

function ExpensesWorkspace() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const emptyForm = {
    amount: "",
    description: "",
    category_id: "",
    vendor_id: "",
    payment_method: "cash",
    source: "",
    is_recurring: false,
    recurring_interval: "monthly",
  };
  const [form, setForm] = useState(emptyForm);
  const [approving, setApproving] = useState<Expense | null>(null);
  const [approveSource, setApproveSource] = useState("");
  const [cancelling, setCancelling] = useState<Expense | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  const list = useQuery({
    queryKey: ["expenses"],
    queryFn: () => api.get<ExpensePage>("/expenses", { page: 1, page_size: 50 }),
  });
  const cats = useQuery({
    queryKey: ["fin-cats"],
    queryFn: () => api.get<FinCategory[]>("/financial-categories"),
  });
  const vendors = useQuery({
    queryKey: ["fin-vendors"],
    queryFn: () => api.get<Vendor[]>("/expense-vendors"),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["expenses"] });
    qc.invalidateQueries({ queryKey: ["safes"] });
    qc.invalidateQueries({ queryKey: ["wallets"] });
  };

  const create = useMutation({
    mutationFn: () => {
      sound.click();
      const src = sourceFields(form.source);
      return api.post("/expenses", {
        amount: D(form.amount).toNumber(),
        description: form.description,
        category_id: form.category_id || undefined,
        vendor_id: form.vendor_id || undefined,
        payment_method: src.wallet_id ? "wallet" : form.payment_method,
        ...src,
        is_recurring: form.is_recurring,
        recurring_interval: form.is_recurring ? form.recurring_interval : undefined,
      });
    },
    onSuccess: () => {
      sound.success();
      setCreating(false);
      setForm(emptyForm);
      refresh();
    },
    onError: () => sound.error(),
  });

  const approve = useMutation({
    mutationFn: () => {
      sound.click();
      return api.post(`/expenses/${approving!.id}/approve`, { approved: true, ...sourceFields(approveSource) });
    },
    onSuccess: () => {
      sound.success();
      setApproving(null);
      refresh();
    },
    onError: () => sound.error(),
  });

  const cancel = useMutation({
    mutationFn: () => {
      sound.click();
      return api.post(`/expenses/${cancelling!.id}/cancel`, { reason: cancelReason || null });
    },
    onSuccess: () => {
      sound.success();
      setCancelling(null);
      setCancelReason("");
      refresh();
    },
    onError: () => sound.error(),
  });

  const remove = useMutation({
    mutationFn: (id: string) => {
      sound.click();
      return api.del(`/expenses/${id}`);
    },
    onSuccess: () => {
      sound.success();
      refresh();
    },
    onError: () => sound.error(),
  });

  const rows = list.data?.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-ink">سجل المصروفات واعتمادها</h2>
          <p className="text-xs text-muted">
            يخرج المبلغ من الخزنة أو المحفظة عند الاعتماد. المصروف المعتمد لا يُحذف: يُلغى فيعود المبلغ إلى مصدره.
          </p>
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
      ) : !rows.length ? (
        <div className="flex flex-col items-center justify-center p-16 text-center border-2 border-dashed border-line rounded-2xl bg-card">
          <ReceiptText className="size-12 text-muted mb-2 stroke-1" />
          <h3 className="text-base font-bold text-ink">لا توجد مصروفات مسجلة حالياً</h3>
          <p className="text-xs text-muted mt-1">انقر على &quot;تسجيل مصروف جديد&quot; لإضافة بند نفقة تشغيلي.</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-line bg-card overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-elevated/50 text-xs font-bold text-muted">
                  <th className="p-3.5 text-start">الوصف والبيان</th>
                  <th className="p-3.5 text-start">المبلغ</th>
                  <th className="p-3.5 text-start">التصنيف</th>
                  <th className="p-3.5 text-start">الحالة</th>
                  <th className="p-3.5 text-start">التاريخ</th>
                  <th className="p-3.5 text-end">إجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {rows.map((e) => (
                  <tr key={e.id} className="hover:bg-elevated/40 transition-colors">
                    <td className="p-3.5 font-bold text-ink">
                      <div className="flex items-center gap-2">
                        <span className={e.status === "cancelled" ? "line-through text-muted" : ""}>{e.description}</span>
                        {e.is_recurring && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-bold">دوري متكرر</span>
                        )}
                      </div>
                    </td>
                    <td className="num p-3.5 font-black text-rose-600">{moneyEGP(e.amount)}</td>
                    <td className="p-3.5 text-muted text-xs">{e.category_name ?? "—"}</td>
                    <td className="p-3.5">
                      <Badge tone={EXPENSE_STATUS[e.status]?.tone ?? "muted"}>{EXPENSE_STATUS[e.status]?.label ?? e.status}</Badge>
                    </td>
                    <td className="p-3.5 text-xs text-muted font-mono">{dateTime(e.created_at)}</td>
                    <td className="p-3.5">
                      <div className="flex items-center justify-end gap-1.5">
                        {e.status === "draft" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setApproving(e);
                              setApproveSource(sourceOf(e));
                            }}
                            className="font-bold text-xs h-8"
                          >
                            اعتماد الصرف
                          </Button>
                        )}
                        {(e.status === "draft" || e.status === "rejected") && (
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="حذف المصروف"
                            onClick={() => remove.mutate(e.id)}
                            disabled={remove.isPending}
                            className="size-8 px-0! text-rose-500 hover:bg-rose-500/10"
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        )}
                        {e.status === "approved" && e.payment_method !== "payroll" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setCancelling(e)}
                            className="font-bold text-xs h-8 gap-1 text-rose-600"
                          >
                            <Ban className="size-3.5" /> إلغاء
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {remove.isError && <ErrorBox message={(remove.error as Error).message} />}

      {/* Approve: the money leaves the chosen safe or wallet */}
      <Modal open={!!approving} onClose={() => setApproving(null)} title={`اعتماد صرف — ${approving?.description ?? ""}`}>
        <form
          onSubmit={(ev) => {
            ev.preventDefault();
            if (!approve.isPending && approveSource) approve.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <div className="rounded-xl border border-line bg-elevated/40 p-3 text-xs">
            <span className="text-muted">المبلغ: </span>
            <strong className="num text-sm font-bold text-rose-600">{moneyEGP(approving?.amount ?? 0)}</strong>
          </div>
          <div>
            <label htmlFor="approve-source" className="mb-1 block text-xs font-semibold text-muted">يُصرف من *</label>
            <PaySourceSelect id="approve-source" value={approveSource} onChange={setApproveSource} />
          </div>
          {approve.isError && <ErrorBox message={(approve.error as Error).message} />}
          <Button type="submit" className="w-full h-11 font-bold text-xs rounded-xl" disabled={approve.isPending || !approveSource}>
            {approve.isPending ? <Spinner /> : "اعتماد وصرف المبلغ"}
          </Button>
        </form>
      </Modal>

      {/* Cancel: the money goes back */}
      <Modal open={!!cancelling} onClose={() => setCancelling(null)} title={`إلغاء مصروف — ${cancelling?.description ?? ""}`}>
        <form
          onSubmit={(ev) => {
            ev.preventDefault();
            if (!cancel.isPending) cancel.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <p className="text-xs text-muted leading-relaxed">
            سيعود مبلغ <strong className="num text-ink">{moneyEGP(cancelling?.amount ?? 0)}</strong> إلى الخزنة أو المحفظة
            التي صُرف منها، ويبقى المصروف في السجل بحالة ملغى.
          </p>
          <div>
            <label htmlFor="cancel-reason" className="mb-1 block text-xs font-semibold text-muted">سبب الإلغاء</label>
            <Input id="cancel-reason" value={cancelReason} onChange={(ev) => setCancelReason(ev.target.value)} />
          </div>
          {cancel.isError && <ErrorBox message={(cancel.error as Error).message} />}
          <Button type="submit" variant="danger" className="w-full h-11 font-bold text-xs rounded-xl" disabled={cancel.isPending}>
            {cancel.isPending ? <Spinner /> : "تأكيد الإلغاء وإرجاع المبلغ"}
          </Button>
        </form>
      </Modal>

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
                <option value="cash">نقداً</option>
                <option value="bank">تحويل بنكي / شيك</option>
                <option value="wallet">محفظة إلكترونية</option>
              </Select>
            </div>
          </div>

          <div>
            <label htmlFor="expense-source" className="mb-1 block text-xs font-semibold text-muted">يُصرف من</label>
            <PaySourceSelect
              id="expense-source"
              value={form.source}
              onChange={(v) => setForm({ ...form, source: v })}
              emptyLabel="— يُحدد عند الاعتماد —"
            />
            <p className="mt-1 text-[11px] text-muted">لا يُعتمد المصروف إلا بعد تحديد الخزنة أو الحساب البنكي أو المحفظة.</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-muted">التصنيف</label>
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
   4. ACCOUNTING PERIODS CLOSING WORKSPACE
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
        <h2 className="text-base font-bold text-ink">إقفال الفترات المالية</h2>
        <p className="text-xs text-muted mt-1 leading-relaxed">
          يسجّل إقفال الشهر أن حساباته رُوجعت. منع التسجيل في شهر مغلق من كل الشاشات يأتي مع دفتر القيود (ADR-014).
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
                <th className="p-3.5 text-start font-mono">الشهر</th>
                <th className="p-3.5 text-start">الحالة</th>
                <th className="p-3.5 text-end">الإجراء</th>
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
                          <Lock className="size-3" /> مقفلة
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5">
                          <LockOpen className="size-3" /> مفتوحة
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
                        <Lock className="size-3.5" /> إقفال الشهر
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
