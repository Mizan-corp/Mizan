/**
 * PAGE CONTRACT
 * Page: الورديات (/shifts)
 * User: كاشير يدير درجه في الفرع، ومشرف يراجع الورديات
 * Outcome: فتح وردية، تسجيل حركات الدرج، توريد الإيرادات، تسليم العهدة، إغلاق الوردية بعد مراجعة الملخص
 * Primary information: حالة الوردية، النقدية المتوقعة في الدرج، حركات الدرج، سجل الورديات
 * Permissions: الشاشة لـ shifts؛ إلغاء حركة الدرج لمن يعتمد في الكاشير (supervise، أو مدير يملك shifts)؛
 *   اعتماد الإغلاق والتوريد بكلمة مرور مدير؛ ملخص وردية زميل للمشرف وحده.
 * Required states: loading, error (retry), no open shift (open form), open shift, empty history
 */
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Banknote, Clock, LockKeyhole, Printer, Undo2, Unlock } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, dateTime, money, moneyEGP } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, Card, ConfirmDialog, Empty, ErrorBox, Input, Select, Spinner, useToast } from "@/components/ui";
import { printDocument } from "@app/lib/documents";
import { useBranch } from "@app/components/AppShell";
import { canApprove, canCancelTx, MANUAL_TYPES, TX_LABEL, txIn } from "../lib";
import {
  CloseShiftModal, HandoverModal, RevenueDeliveryModal, type Shift, ShiftSummaryModal, type ShiftSummary, SummaryView,
} from "../components/ShiftDialogs";

interface Warehouse { id: string; name: string }
interface Tx {
  id: string; type: string; amount: string; note: string | null; created_at: string; ref_id: string | null;
  category_id: string | null; payment_method: string | null; wallet_id: string | null; cancelled_at: string | null;
}
interface Category { id: string; name: string; type: string; is_active?: boolean }
interface WalletRow { id: string; name: string }

const HISTORY_PAGE = 20;

export default function ShiftsPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const can = useAuth((s) => s.can);
  const user = useAuth((s) => s.user);
  const approver = canApprove(!!user?.is_manager, can);
  const supervisor = !!user?.is_manager || can("supervise");
  const { branchId, setBranchId } = useBranch();
  const [warehouseId, setWarehouseId] = useState("");
  const [openAmount, setOpenAmount] = useState("0");
  const [tx, setTx] = useState({ type: "expense", amount: "", note: "", method: "cash", wallet_id: "", category_id: "" });
  const [cancelling, setCancelling] = useState<Tx | null>(null);
  const [closing, setClosing] = useState(false);
  const [delivering, setDelivering] = useState(false);
  const [handing, setHanding] = useState(false);
  const [viewing, setViewing] = useState<Shift | null>(null);
  const [historyPage, setHistoryPage] = useState(0);

  const wh = useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<Warehouse[]>("/stock/warehouses") });
  const wid = warehouseId || branchId || wh.data?.[0]?.id || "";

  const current = useQuery({
    queryKey: ["shift", "current", wid],
    queryFn: () => api.get<Shift | null>("/shifts/current", { warehouse_id: wid }),
    enabled: !!wid,
    retry: false,
  });
  const shift = current.data ?? null;
  const summary = useQuery({
    queryKey: ["shift-summary", shift?.id],
    queryFn: () => api.get<ShiftSummary>(`/shifts/${shift!.id}/summary`),
    enabled: !!shift,
  });
  const txs = useQuery({
    queryKey: ["shift-txs", shift?.id],
    queryFn: () => api.get<Tx[]>(`/shifts/${shift!.id}/transactions`),
    enabled: !!shift,
  });
  const categories = useQuery({
    queryKey: ["financial-categories"],
    queryFn: () => api.get<Category[]>("/financial-categories"),
    enabled: !!shift,
    retry: false,
  });
  const wallets = useQuery({ queryKey: ["wallets"], queryFn: () => api.get<WalletRow[]>("/wallets"), enabled: !!shift });
  const history = useQuery({
    queryKey: ["shifts", wid, historyPage],
    queryFn: () => api.get<Shift[]>("/shifts", { warehouse_id: wid, limit: HISTORY_PAGE, offset: historyPage * HISTORY_PAGE }),
    enabled: !!wid,
    placeholderData: keepPreviousData,
  });

  const refresh = () => {
    for (const key of ["shift", "shifts", "shift-txs", "shift-summary"]) qc.invalidateQueries({ queryKey: [key] });
  };
  const openShift = useMutation({
    mutationFn: () => api.post("/shifts/open", { warehouse_id: wid, initial_amount: openAmount || "0" }),
    onSuccess: () => { toast("success", "فُتحت الوردية"); refresh(); },
  });
  const addTx = useMutation({
    mutationFn: () =>
      api.post(`/shifts/${shift!.id}/transactions`, {
        type: tx.type,
        amount: tx.amount,
        note: tx.note.trim() || null,
        payment_method: tx.method,
        wallet_id: tx.method === "wallet" ? tx.wallet_id || null : null,
        category_id: tx.type === "expense" && tx.category_id ? tx.category_id : null,
      }),
    onSuccess: () => {
      toast("success", "سُجِّلت الحركة");
      setTx((t) => ({ ...t, amount: "", note: "" }));
      refresh();
    },
  });
  const cancelTx = useMutation({
    mutationFn: (id: string) => api.del(`/shifts/transactions/${id}`),
    onSuccess: () => { toast("success", "أُلغيت الحركة"); setCancelling(null); refresh(); },
    onError: (e) => { setCancelling(null); toast("error", (e as Error).message); },
  });

  const expenseCats = (categories.data ?? []).filter((c) => c.type === "expense" && c.is_active !== false);
  const catName = (id: string | null) => (id ? categories.data?.find((c) => c.id === id)?.name : undefined);
  const txReady = Number(tx.amount) > 0 && (tx.method !== "wallet" || !!tx.wallet_id);
  const expected = summary.data?.expected_balance;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">الورديات</h1>
          <p className="text-sm text-muted-foreground">درج الكاشير في الفرع: حركاته، توريده، تسليمه وإغلاقه</p>
        </div>
        {wh.isError ? (
          <ErrorBox message={(wh.error as Error).message} onRetry={() => wh.refetch()} />
        ) : (
          <Select aria-label="الفرع" value={wid} className="w-auto" disabled={wh.isLoading}
                  onChange={(e) => { setWarehouseId(e.target.value); setBranchId(e.target.value); setHistoryPage(0); }}>
            {wh.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        )}
      </div>

      {current.isLoading || (!wid && wh.isLoading) ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
          <Skeleton className="h-10 w-full" />
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : current.isError ? (
        <ErrorBox message={(current.error as Error).message} onRetry={() => current.refetch()} />
      ) : !shift ? (
        <Card className="space-y-4">
          <p className="flex items-center gap-2 font-bold"><Unlock size={18} /> لا توجد وردية مفتوحة لك في هذا الفرع</p>
          <form
            onSubmit={(e) => { e.preventDefault(); if (!openShift.isPending && wid) openShift.mutate(); }}
            className="flex flex-wrap items-end gap-3"
          >
            <div>
              <label htmlFor="open-amount" className="mb-1 block text-sm font-medium">العهدة الافتتاحية (ج.م)</label>
              <Input id="open-amount" autoFocus className="num w-40 font-bold" inputMode="decimal" value={openAmount}
                     onChange={(e) => setOpenAmount(e.target.value)} />
            </div>
            <Button type="submit" className="h-10 font-bold" disabled={openShift.isPending || !wid || !(Number(openAmount || 0) >= 0)}>
              {openShift.isPending ? <Spinner /> : "فتح الوردية"}
            </Button>
          </form>
          {openShift.isError && <ErrorBox message={(openShift.error as Error).message} />}
        </Card>
      ) : (
        <Card className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="flex items-center gap-2 font-bold text-success-ink"><Clock size={18} /> وردية مفتوحة</p>
              <p className="text-xs text-muted-foreground">منذ {dateTime(shift.started_at)}{shift.cashier_name ? ` · ${shift.cashier_name}` : ""}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => printDocument(`/print/shift/${shift.id}`)}>
                <Printer size={16} /> تقرير الوردية
              </Button>
              <Button variant="outline" onClick={() => setDelivering(true)} disabled={!summary.data || D(expected ?? 0).lte(0)}>
                <Banknote size={16} /> توريد إلى خزنة
              </Button>
              <Button variant="outline" onClick={() => setHanding(true)} disabled={!summary.data}>
                <ArrowLeftRight size={16} /> تسليم العهدة
              </Button>
              <Button variant="danger" onClick={() => setClosing(true)}>
                <LockKeyhole size={16} /> إغلاق الوردية
              </Button>
            </div>
          </div>

          {summary.isLoading ? (
            <Skeleton className="h-28 w-full" />
          ) : summary.isError ? (
            <ErrorBox message={(summary.error as Error).message} onRetry={() => summary.refetch()} />
          ) : summary.data && <SummaryView s={summary.data} />}

          <div className="rounded-xl border border-line p-3">
            <p className="mb-2 text-sm font-bold">حركة درج جديدة</p>
            <form
              onSubmit={(e) => { e.preventDefault(); if (!addTx.isPending && txReady) addTx.mutate(); }}
              className="flex flex-wrap items-end gap-2"
            >
              <div>
                <label htmlFor="tx-type" className="mb-1 block text-xs text-muted-foreground">النوع</label>
                <Select id="tx-type" value={tx.type} onChange={(e) => setTx({ ...tx, type: e.target.value })} className="w-auto">
                  {MANUAL_TYPES.map((t) => <option key={t} value={t}>{TX_LABEL[t]}</option>)}
                </Select>
              </div>
              <div>
                <label htmlFor="tx-amount" className="mb-1 block text-xs text-muted-foreground">المبلغ</label>
                <Input id="tx-amount" className="num w-32 font-bold" inputMode="decimal" value={tx.amount}
                       onChange={(e) => setTx({ ...tx, amount: e.target.value })} />
              </div>
              <div>
                <label htmlFor="tx-method" className="mb-1 block text-xs text-muted-foreground">من</label>
                <Select id="tx-method" value={tx.method} onChange={(e) => setTx({ ...tx, method: e.target.value })} className="w-auto">
                  <option value="cash">الدرج (نقدي)</option>
                  <option value="wallet">محفظة</option>
                </Select>
              </div>
              {tx.method === "wallet" && (
                <div>
                  <label htmlFor="tx-wallet" className="mb-1 block text-xs text-muted-foreground">المحفظة</label>
                  <Select id="tx-wallet" value={tx.wallet_id} onChange={(e) => setTx({ ...tx, wallet_id: e.target.value })} className="w-auto">
                    <option value="">— اختر —</option>
                    {wallets.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                  </Select>
                </div>
              )}
              {tx.type === "expense" && !categories.isError && (
                <div>
                  <label htmlFor="tx-cat" className="mb-1 block text-xs text-muted-foreground">بند المصروف</label>
                  <Select id="tx-cat" value={tx.category_id} onChange={(e) => setTx({ ...tx, category_id: e.target.value })}
                          className="w-auto" disabled={categories.isLoading}>
                    <option value="">بدون بند</option>
                    {expenseCats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </Select>
                </div>
              )}
              <div className="min-w-48 flex-1">
                <label htmlFor="tx-note" className="mb-1 block text-xs text-muted-foreground">البيان</label>
                <Input id="tx-note" maxLength={1000} value={tx.note} onChange={(e) => setTx({ ...tx, note: e.target.value })} />
              </div>
              <Button type="submit" variant="outline" disabled={addTx.isPending || !txReady}>
                {addTx.isPending ? <Spinner /> : "إضافة"}
              </Button>
            </form>
            {addTx.isError && <p className="mt-2 text-sm text-destructive-ink">{(addTx.error as Error).message}</p>}
          </div>

          <div>
            <p className="mb-2 text-sm font-bold">حركات الدرج</p>
            {txs.isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : txs.isError ? (
              <ErrorBox message={(txs.error as Error).message} onRetry={() => txs.refetch()} />
            ) : !txs.data?.length ? (
              <Empty text="لا توجد حركات بعد" hint="تظهر هنا المبيعات النقدية والمرتجعات والإيداعات والمصروفات والسحوبات." />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-line">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line bg-muted/40 text-xs text-muted-foreground">
                      <th className="p-2 text-start">الوقت</th>
                      <th className="p-2 text-start">الحركة</th>
                      <th className="p-2 text-start">البيان</th>
                      <th className="p-2 text-end">المبلغ</th>
                      <th className="p-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {txs.data.map((t) => {
                      const cancelled = !!t.cancelled_at;
                      return (
                        <tr key={t.id} className={`border-b border-line/60 last:border-0 ${cancelled ? "opacity-60" : ""}`}>
                          <td className="num p-2 text-xs text-muted-foreground">{dateTime(t.created_at)}</td>
                          <td className="p-2">
                            <span className="flex flex-wrap items-center gap-1">
                              <Badge tone={txIn(t.type) ? "success" : t.type === "expense" ? "danger" : "warning"}>{TX_LABEL[t.type] ?? t.type}</Badge>
                              {t.payment_method === "wallet" && <Badge tone="muted">محفظة</Badge>}
                              {cancelled && <Badge tone="muted">ملغاة</Badge>}
                            </span>
                          </td>
                          <td className="p-2 text-xs text-muted-foreground">
                            {[catName(t.category_id), t.note].filter(Boolean).join(" · ") || "—"}
                          </td>
                          <td className={`num p-2 text-end font-bold ${cancelled ? "line-through" : ""}`}>
                            {txIn(t.type) ? "+" : "−"} {money(t.amount)}
                          </td>
                          <td className="p-2 text-end">
                            {canCancelTx(t, shift.status === "open", approver) && (
                              <Button variant="ghost" size="sm" aria-label={`إلغاء الحركة ${money(t.amount)}`} onClick={() => setCancelling(t)}>
                                <Undo2 className="size-4 text-destructive" />
                              </Button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Card>
      )}

      <Card>
        <h2 className="mb-3 font-bold">سجل الورديات</h2>
        {history.isLoading ? (
          <div className="grid place-items-center p-6"><Spinner /></div>
        ) : history.isError ? (
          <ErrorBox message={(history.error as Error).message} onRetry={() => history.refetch()} />
        ) : !history.data?.length ? (
          <Empty text={historyPage ? "لا توجد ورديات أخرى" : "لا توجد ورديات بعد في هذا الفرع"} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted-foreground">
                  <th className="p-2 text-start">الكاشير</th>
                  <th className="p-2 text-start">الافتتاح</th>
                  <th className="p-2 text-start">الإغلاق</th>
                  <th className="p-2 text-end">العهدة</th>
                  <th className="p-2 text-end">المتوقع</th>
                  <th className="p-2 text-end">المعدود</th>
                  <th className="p-2 text-end">الفرق</th>
                  <th className="p-2 text-start">الحالة</th>
                </tr>
              </thead>
              <tbody>
                {history.data.map((s) => {
                  const mine = s.cashier_id === user?.id;
                  const open = mine || supervisor;
                  const diff = s.difference != null ? Number(s.difference) : null;
                  return (
                    <tr key={s.id} className={`border-b border-line/60 last:border-0 ${open ? "cursor-pointer hover:bg-muted/40" : ""}`}
                        onClick={() => open && setViewing(s)}>
                      <td className="p-2">{s.cashier_name ?? "—"}</td>
                      <td className="num p-2 text-xs text-muted-foreground">{dateTime(s.started_at)}</td>
                      <td className="num p-2 text-xs text-muted-foreground">{s.closed_at ? dateTime(s.closed_at) : "—"}</td>
                      <td className="num p-2 text-end">{money(s.initial_amount)}</td>
                      <td className="num p-2 text-end">{s.expected_balance != null ? money(s.expected_balance) : "—"}</td>
                      <td className="num p-2 text-end">{s.closing_balance != null ? money(s.closing_balance) : "—"}</td>
                      <td className={`num p-2 text-end ${diff && diff < 0 ? "text-destructive-ink" : diff ? "text-warning-ink" : ""}`}>
                        {diff == null ? "—" : diff === 0 ? "مطابق" : `${diff < 0 ? "عجز" : "زيادة"} ${money(Math.abs(diff))}`}
                      </td>
                      <td className="p-2">
                        <Badge tone={s.status === "open" ? "success" : "muted"}>{s.status === "open" ? "مفتوحة" : "مغلقة"}</Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {(historyPage > 0 || (history.data?.length ?? 0) === HISTORY_PAGE) && (
          <div className="mt-3 flex items-center justify-center gap-3 text-sm">
            <Button variant="outline" disabled={historyPage === 0} onClick={() => setHistoryPage((p) => p - 1)}>الأحدث</Button>
            <span className="num text-muted-foreground">صفحة {historyPage + 1}</span>
            <Button variant="outline" disabled={(history.data?.length ?? 0) < HISTORY_PAGE} onClick={() => setHistoryPage((p) => p + 1)}>الأقدم</Button>
          </div>
        )}
      </Card>

      <ConfirmDialog
        open={!!cancelling}
        onClose={() => setCancelling(null)}
        onConfirm={() => cancelling && !cancelTx.isPending && cancelTx.mutate(cancelling.id)}
        title={`إلغاء حركة ${cancelling ? TX_LABEL[cancelling.type] ?? "" : ""} ${cancelling ? moneyEGP(cancelling.amount) : ""}`}
        message="تبقى الحركة في السجل مُعلَّمة ملغاة ولا تدخل في رصيد الدرج؛ تُعكس حركة المحفظة إن وُجدت، ويعود دين العميل إن كانت تحصيلاً."
        confirmLabel="إلغاء الحركة"
      />
      <CloseShiftModal shift={closing ? shift : null} summary={summary.data} onClose={() => setClosing(false)} />
      <RevenueDeliveryModal shift={delivering ? shift : null} expected={expected} onClose={() => setDelivering(false)} />
      <HandoverModal shift={handing ? shift : null} expected={expected} onClose={() => setHanding(false)} />
      <ShiftSummaryModal shift={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}
