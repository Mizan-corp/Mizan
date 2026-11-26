// Expenses and their approval: a paged, filtered list; a draft is edited, approved (the money leaves
// its safe or wallet) or rejected; after a decision only the notes and the recurrence change; an
// approved expense is cancelled (its money goes back), never deleted. A recurring expense makes its
// next draft by itself each night when it is due (FIN-9).
import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Check, Pencil, Plus, ReceiptText, Repeat, Trash2, X } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, date as fmtDate } from "@/lib/format";
import { sound } from "@/lib/sound";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";
import { moneyIn, useCurrency } from "@app/lib/currency";
import { useVat } from "@app/lib/vat";
import {
  amountOrNull, EXPENSE_STATUS, expenseActions, type ExpenseForm, type ExpenseStatus, INTERVAL_LABEL, pageCount,
  recurrenceBody, type RecurringInterval,
} from "../lib";

interface Expense {
  id: string;
  amount: string;
  tax_amount?: string;
  description: string;
  status: ExpenseStatus;
  date: string;
  is_recurring: boolean;
  recurring_interval: RecurringInterval | null;
  recurring_end_date: string | null;
  recurred_from: string | null;
  payment_method: string | null;
  safe_id: string | null;
  wallet_id: string | null;
  category_id: string | null;
  vendor_id: string | null;
  warehouse_id: string | null;
  notes: string | null;
  category_name?: string | null;
  vendor_name?: string | null;
  warehouse_name?: string | null;
  created_by_name?: string | null;
}

interface ExpensePage { data: Expense[]; total: number; page: number; page_size: number }
interface Named { id: string; name: string; type?: string; is_active?: boolean }

const PAGE_SIZE = 25;
const sourceOf = (e: Expense) => (e.wallet_id ? `wallet:${e.wallet_id}` : e.safe_id ? `safe:${e.safe_id}` : "");

const emptyForm = (): ExpenseForm => ({
  description: "", amount: "", tax_amount: "", date: "", category_id: "", vendor_id: "", warehouse_id: "",
  payment_method: "cash", source: "", notes: "", is_recurring: false, recurring_interval: "monthly", recurring_end_date: "",
});

const formOf = (e: Expense): ExpenseForm => ({
  description: e.description, amount: D(e.amount).toFixed(2), tax_amount: D(e.tax_amount ?? 0).gt(0) ? D(e.tax_amount!).toFixed(2) : "",
  date: e.date ?? "", category_id: e.category_id ?? "", vendor_id: e.vendor_id ?? "", warehouse_id: e.warehouse_id ?? "",
  payment_method: e.payment_method ?? "cash", source: sourceOf(e), notes: e.notes ?? "", is_recurring: e.is_recurring,
  recurring_interval: e.recurring_interval ?? "monthly", recurring_end_date: e.recurring_end_date ?? "",
});

export function ExpensesWorkspace() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const cur = useCurrency();
  const vat = useVat();
  const manage = useAuth((s) => s.can("finance"));
  const [filters, setFilters] = useState({ status: "", search: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<{ row: Expense | null; form: ExpenseForm } | null>(null);
  const [approving, setApproving] = useState<Expense | null>(null);
  const [approveSource, setApproveSource] = useState("");
  const [rejecting, setRejecting] = useState<Expense | null>(null);
  const [rejectNote, setRejectNote] = useState("");
  const [cancelling, setCancelling] = useState<Expense | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [deleting, setDeleting] = useState<Expense | null>(null);

  const list = useQuery({
    queryKey: ["expenses", filters, page],
    queryFn: () => api.get<ExpensePage>("/expenses", { ...filters, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
  const cats = useQuery({ queryKey: ["fin-cats"], queryFn: () => api.get<Named[]>("/financial-categories") });
  const vendors = useQuery({ queryKey: ["fin-vendors"], queryFn: () => api.get<Named[]>("/expense-vendors"), enabled: manage });
  const branches = useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<Named[]>("/stock/warehouses") });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["expenses"] });
    qc.invalidateQueries({ queryKey: ["safes"] });
    qc.invalidateQueries({ queryKey: ["wallets"] });
  };
  const done = (msg: string) => {
    sound.success();
    toast("success", msg);
    refresh();
  };

  const save = useMutation({
    mutationFn: ({ row, form }: { row: Expense | null; form: ExpenseForm }) => {
      const notesOnly = row && expenseActions(row).edit === "notes";
      if (notesOnly) return api.put(`/expenses/${row.id}`, { notes: form.notes || null, ...recurrenceBody(form) });
      const src = sourceFields(form.source);
      const body = {
        description: form.description.trim(),
        amount: amountOrNull(form.amount),
        tax_amount: vat.data?.vat_registered && form.tax_amount ? amountOrNull(form.tax_amount) ?? "0" : "0",
        date: form.date || undefined,
        category_id: form.category_id || null,
        vendor_id: form.vendor_id || null,
        warehouse_id: form.warehouse_id || null,
        payment_method: src.wallet_id ? "wallet" : form.payment_method,
        ...src,
        notes: form.notes || null,
        ...recurrenceBody(form),
      };
      return row ? api.put(`/expenses/${row.id}`, body) : api.post("/expenses", body);
    },
    onSuccess: (_r, v) => {
      setEditing(null);
      done(v.row ? "حُفظ المصروف" : "سُجّل المصروف مسودةً بانتظار الاعتماد");
    },
    onError: () => sound.error(),
  });

  const approve = useMutation({
    mutationFn: () => api.post(`/expenses/${approving!.id}/approve`, { approved: true, ...sourceFields(approveSource) }),
    onSuccess: () => {
      setApproving(null);
      done("اعتُمد المصروف وصُرف المبلغ");
    },
    onError: () => sound.error(),
  });
  const reject = useMutation({
    mutationFn: () => api.post(`/expenses/${rejecting!.id}/approve`, { approved: false, notes: rejectNote || null }),
    onSuccess: () => {
      setRejecting(null);
      setRejectNote("");
      done("رُفض المصروف");
    },
    onError: () => sound.error(),
  });
  const cancel = useMutation({
    mutationFn: () => api.post(`/expenses/${cancelling!.id}/cancel`, { reason: cancelReason || null }),
    onSuccess: () => {
      setCancelling(null);
      setCancelReason("");
      done("أُلغي المصروف وعاد المبلغ إلى مصدره");
    },
    onError: () => sound.error(),
  });
  const remove = useMutation({
    mutationFn: (e: Expense) => api.del(`/expenses/${e.id}`),
    onSuccess: () => {
      setDeleting(null);
      done("حُذف المصروف");
    },
    onError: (e) => {
      setDeleting(null);
      sound.error();
      toast("error", (e as Error).message);
    },
  });

  const rows = list.data?.data ?? [];
  const pages = pageCount(list.data?.total ?? 0, PAGE_SIZE);
  const setFilter = (k: keyof typeof filters, v: string) => {
    setFilters({ ...filters, [k]: v });
    setPage(1);
  };
  const filtered = useMemo(() => Object.values(filters).some(Boolean), [filters]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-ink">سجل المصروفات واعتمادها</h2>
          <p className="text-xs text-muted">
            يخرج المبلغ من الخزنة أو المحفظة عند الاعتماد. المصروف المعتمد لا يُحذف: يُلغى فيعود المبلغ إلى مصدره.
            المصروف الدوري يُنشئ مسودته التالية تلقائياً عند حلول موعدها.
          </p>
        </div>
        {manage && (
          <Button onClick={() => setEditing({ row: null, form: emptyForm() })} className="gap-1.5 font-bold text-xs h-9 rounded-xl">
            <Plus className="size-4" /> تسجيل مصروف جديد
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-card p-3">
        <div>
          <label htmlFor="exp-search" className="mb-1 block text-xs font-medium text-muted">بحث</label>
          <Input id="exp-search" className="w-52" maxLength={128} value={filters.search} placeholder="البيان أو الجهة"
                 onChange={(e) => setFilter("search", e.target.value)} />
        </div>
        <div>
          <label htmlFor="exp-status" className="mb-1 block text-xs font-medium text-muted">الحالة</label>
          <Select id="exp-status" className="w-44" value={filters.status} onChange={(e) => setFilter("status", e.target.value)}>
            <option value="">كل الحالات</option>
            {(Object.keys(EXPENSE_STATUS) as ExpenseStatus[]).map((s) => <option key={s} value={s}>{EXPENSE_STATUS[s].label}</option>)}
          </Select>
        </div>
        <div>
          <label htmlFor="exp-from" className="mb-1 block text-xs font-medium text-muted">من تاريخ</label>
          <Input id="exp-from" type="date" className="num w-40" value={filters.date_from} onChange={(e) => setFilter("date_from", e.target.value)} />
        </div>
        <div>
          <label htmlFor="exp-to" className="mb-1 block text-xs font-medium text-muted">إلى تاريخ</label>
          <Input id="exp-to" type="date" className="num w-40" value={filters.date_to} onChange={(e) => setFilter("date_to", e.target.value)} />
        </div>
        {filtered && (
          <Button variant="ghost" size="sm" onClick={() => { setFilters({ status: "", search: "", date_from: "", date_to: "" }); setPage(1); }}>
            <X className="size-4" /> مسح الفلاتر
          </Button>
        )}
      </div>

      {list.isLoading ? (
        <div className="space-y-2" aria-busy="true" aria-label="جارٍ التحميل">
          <Skeleton className="h-12 w-full rounded-xl" />
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !rows.length ? (
        <Empty text={filtered ? "لا توجد مصروفات تطابق الفلاتر" : "لا توجد مصروفات مسجلة بعد"}
               hint={filtered ? "غيّر الفلاتر أو امسحها" : "سجّل مصروفاً ثم اعتمده ليُصرف من الخزنة أو المحفظة"}
               icon={<ReceiptText className="size-10" />}
               action={manage && !filtered ? <Button onClick={() => setEditing({ row: null, form: emptyForm() })}><Plus className="size-4" /> تسجيل مصروف</Button> : undefined} />
      ) : (
        <div className="rounded-2xl border border-line bg-card overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-elevated/50 text-xs font-bold text-muted">
                  <th className="p-3 text-start">التاريخ</th>
                  <th className="p-3 text-start">البيان</th>
                  <th className="p-3 text-end">المبلغ</th>
                  <th className="p-3 text-start">التصنيف / الجهة</th>
                  <th className="p-3 text-start">الحالة</th>
                  <th className="p-3 text-end">إجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {rows.map((e) => {
                  const can = expenseActions(e);
                  return (
                    <tr key={e.id} className="hover:bg-elevated/40 transition-colors">
                      <td className="p-3 text-xs text-muted whitespace-nowrap">{fmtDate(e.date)}</td>
                      <td className="p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`font-semibold ${e.status === "cancelled" ? "line-through text-muted" : "text-ink"}`}>{e.description}</span>
                          {e.is_recurring && (
                            <Badge tone="brand"><Repeat className="size-3" /> {INTERVAL_LABEL[e.recurring_interval ?? "monthly"]}</Badge>
                          )}
                          {e.recurred_from && <span className="text-[11px] text-muted">تكرار تلقائي</span>}
                        </div>
                        {(e.warehouse_name || e.notes) && (
                          <div className="mt-0.5 text-[11px] text-muted">{[e.warehouse_name, e.notes].filter(Boolean).join(" · ")}</div>
                        )}
                      </td>
                      <td className="num p-3 text-end font-bold whitespace-nowrap">
                        {moneyIn(e.amount, cur)}
                        {D(e.tax_amount ?? 0).gt(0) && <div className="text-[10px] font-normal text-muted">منها ضريبة {moneyIn(e.tax_amount!, cur)}</div>}
                      </td>
                      <td className="p-3 text-xs text-muted">{[e.category_name, e.vendor_name].filter(Boolean).join(" · ") || "—"}</td>
                      <td className="p-3"><Badge tone={EXPENSE_STATUS[e.status]?.tone ?? "muted"}>{EXPENSE_STATUS[e.status]?.label ?? e.status}</Badge></td>
                      <td className="p-3">
                        {manage && (
                          <div className="flex items-center justify-end gap-1">
                            {can.approve && (
                              <Button variant="outline" size="sm" className="h-8 text-xs font-bold"
                                      onClick={() => { setApproving(e); setApproveSource(sourceOf(e)); }}>
                                <Check className="size-3.5" /> اعتماد
                              </Button>
                            )}
                            {can.reject && (
                              <Button variant="ghost" size="sm" className="h-8 text-xs text-danger" onClick={() => { setRejecting(e); setRejectNote(""); }}>
                                رفض
                              </Button>
                            )}
                            {can.cancel && (
                              <Button variant="ghost" size="sm" className="h-8 gap-1 text-xs text-danger" onClick={() => setCancelling(e)}>
                                <Ban className="size-3.5" /> إلغاء
                              </Button>
                            )}
                            {e.payment_method !== "payroll" && (
                              <Button variant="ghost" size="icon" aria-label={`تعديل ${e.description}`} className="size-8 px-0!"
                                      onClick={() => setEditing({ row: e, form: formOf(e) })}>
                                <Pencil className="size-4" />
                              </Button>
                            )}
                            {can.remove && (
                              <Button variant="ghost" size="icon" aria-label={`حذف ${e.description}`} className="size-8 px-0! text-danger"
                                      onClick={() => setDeleting(e)}>
                                <Trash2 className="size-4" />
                              </Button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-xs text-muted">
            <span className="num">{list.data?.total ?? 0} مصروف</span>
            {pages > 1 && (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1 || list.isFetching} onClick={() => setPage(page - 1)}>السابق</Button>
                <span className="num">صفحة {page} من {pages}</span>
                <Button variant="outline" size="sm" disabled={page >= pages || list.isFetching} onClick={() => setPage(page + 1)}>التالي</Button>
              </div>
            )}
          </div>
        </div>
      )}

      <Modal open={!!approving} onClose={() => setApproving(null)} title={`اعتماد صرف — ${approving?.description ?? ""}`}>
        <form className="flex flex-col gap-4" onSubmit={(ev) => { ev.preventDefault(); if (!approve.isPending && approveSource) approve.mutate(); }}>
          <div className="rounded-xl border border-line bg-elevated/40 p-3 text-xs">
            <span className="text-muted">المبلغ: </span>
            <strong className="num text-sm font-bold">{moneyIn(approving?.amount ?? 0, cur)}</strong>
          </div>
          <div>
            <label htmlFor="approve-source" className="mb-1 block text-xs font-semibold text-muted">يُصرف من *</label>
            <PaySourceSelect id="approve-source" value={approveSource} onChange={setApproveSource} />
            <p className="mt-1 text-[11px] text-muted">لا يُصرف مصروف أكبر من رصيد الخزنة ما دام إعداد «حظر المصروفات التي تتجاوز رصيد الخزينة» مفعّلاً (مركز الوحدات).</p>
          </div>
          {approve.isError && <ErrorBox message={(approve.error as Error).message} />}
          <Button type="submit" className="w-full h-11 font-bold text-xs rounded-xl" disabled={approve.isPending || !approveSource}>
            {approve.isPending ? <Spinner /> : "اعتماد وصرف المبلغ"}
          </Button>
        </form>
      </Modal>

      <Modal open={!!rejecting} onClose={() => setRejecting(null)} title={`رفض مصروف — ${rejecting?.description ?? ""}`}>
        <form className="flex flex-col gap-4" onSubmit={(ev) => { ev.preventDefault(); if (!reject.isPending) reject.mutate(); }}>
          <p className="text-xs text-muted leading-relaxed">
            لا يخرج أي مبلغ. المصروف المرفوض مغلق: لا يُعتمد بعد ذلك، ويمكن حذفه أو تسجيله من جديد كمسودة.
          </p>
          <div>
            <label htmlFor="reject-note" className="mb-1 block text-xs font-semibold text-muted">سبب الرفض</label>
            <Input id="reject-note" maxLength={2000} value={rejectNote} onChange={(ev) => setRejectNote(ev.target.value)} />
          </div>
          {reject.isError && <ErrorBox message={(reject.error as Error).message} />}
          <Button type="submit" variant="danger" className="w-full h-11 font-bold text-xs rounded-xl" disabled={reject.isPending}>
            {reject.isPending ? <Spinner /> : "تأكيد الرفض"}
          </Button>
        </form>
      </Modal>

      <Modal open={!!cancelling} onClose={() => setCancelling(null)} title={`إلغاء مصروف — ${cancelling?.description ?? ""}`}>
        <form className="flex flex-col gap-4" onSubmit={(ev) => { ev.preventDefault(); if (!cancel.isPending) cancel.mutate(); }}>
          <p className="text-xs text-muted leading-relaxed">
            سيعود مبلغ <strong className="num text-ink">{moneyIn(cancelling?.amount ?? 0, cur)}</strong> إلى الخزنة أو المحفظة
            التي صُرف منها، ويبقى المصروف في السجل بحالة ملغى.
          </p>
          <div>
            <label htmlFor="cancel-reason" className="mb-1 block text-xs font-semibold text-muted">سبب الإلغاء</label>
            <Input id="cancel-reason" maxLength={500} value={cancelReason} onChange={(ev) => setCancelReason(ev.target.value)} />
          </div>
          {cancel.isError && <ErrorBox message={(cancel.error as Error).message} />}
          <Button type="submit" variant="danger" className="w-full h-11 font-bold text-xs rounded-xl" disabled={cancel.isPending}>
            {cancel.isPending ? <Spinner /> : "تأكيد الإلغاء وإرجاع المبلغ"}
          </Button>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && !remove.isPending && remove.mutate(deleting)}
        title={`حذف ${deleting?.description ?? "المصروف"}`}
        message="يُحذف المصروف نهائياً (لم يُصرف منه شيء). لا يمكن التراجع."
        confirmLabel="حذف"
      />

      {editing && (
        <ExpenseFormModal
          editing={editing}
          onChange={(form) => setEditing({ ...editing, form })}
          onClose={() => setEditing(null)}
          onSubmit={() => !save.isPending && save.mutate(editing)}
          pending={save.isPending}
          error={save.isError ? (save.error as Error).message : null}
          vatRegistered={!!vat.data?.vat_registered}
          categories={(cats.data ?? []).filter((c) => c.type !== "income")}
          vendors={vendors.data ?? []}
          branches={branches.data ?? []}
          currency={cur}
        />
      )}
    </div>
  );
}

function ExpenseFormModal({ editing, onChange, onClose, onSubmit, pending, error, vatRegistered, categories, vendors, branches, currency }: {
  editing: { row: Expense | null; form: ExpenseForm };
  onChange: (f: ExpenseForm) => void;
  onClose: () => void;
  onSubmit: () => void;
  pending: boolean;
  error: string | null;
  vatRegistered: boolean;
  categories: Named[];
  vendors: Named[];
  branches: Named[];
  currency: string;
}) {
  const { row, form } = editing;
  const notesOnly = !!row && expenseActions(row).edit === "notes";
  const set = (patch: Partial<ExpenseForm>) => onChange({ ...form, ...patch });
  const amountOk = notesOnly || amountOrNull(form.amount) !== null;
  const valid = notesOnly || (form.description.trim() && amountOk);
  return (
    <Modal open onClose={onClose} title={row ? `تعديل مصروف — ${row.description}` : "تسجيل مصروف جديد"} wide>
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (valid) onSubmit(); }}>
        {notesOnly && (
          <p className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-xs">
            {EXPENSE_STATUS[row!.status].label}: لا يتغير المبلغ ولا المصدر بعد القرار. يمكن تعديل الملاحظات وإيقاف التكرار أو تحديد نهايته.
          </p>
        )}
        {!notesOnly && (
          <>
            <div>
              <label htmlFor="ex-desc" className="mb-1 block text-xs font-semibold text-muted">البيان *</label>
              <Input id="ex-desc" autoFocus maxLength={1000} value={form.description} onChange={(e) => set({ description: e.target.value })}
                     placeholder="مثال: فاتورة كهرباء المقر الرئيسي" />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label htmlFor="ex-amount" className="mb-1 block text-xs font-semibold text-muted">المبلغ ({currency}) *</label>
                <Input id="ex-amount" className="num font-bold" inputMode="decimal" value={form.amount} onChange={(e) => set({ amount: e.target.value })} />
                {form.amount && !amountOk && <p className="mt-1 text-[11px] text-danger">رقم موجب بحد أقصى منزلتين عشريتين</p>}
              </div>
              {vatRegistered && (
                <div>
                  <label htmlFor="ex-tax" className="mb-1 block text-xs font-semibold text-muted">منها ضريبة القيمة المضافة</label>
                  <Input id="ex-tax" className="num" inputMode="decimal" value={form.tax_amount} onChange={(e) => set({ tax_amount: e.target.value })} />
                </div>
              )}
              <div>
                <label htmlFor="ex-date" className="mb-1 block text-xs font-semibold text-muted">التاريخ</label>
                <Input id="ex-date" type="date" className="num" value={form.date} onChange={(e) => set({ date: e.target.value })} />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label htmlFor="ex-cat" className="mb-1 block text-xs font-semibold text-muted">التصنيف</label>
                <Select id="ex-cat" value={form.category_id} onChange={(e) => set({ category_id: e.target.value })}>
                  <option value="">— بدون تصنيف —</option>
                  {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </div>
              <div>
                <label htmlFor="ex-vendor" className="mb-1 block text-xs font-semibold text-muted">الجهة المستفيدة</label>
                <Select id="ex-vendor" value={form.vendor_id} onChange={(e) => set({ vendor_id: e.target.value })}>
                  <option value="">— جهة عامة —</option>
                  {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                </Select>
              </div>
              <div>
                <label htmlFor="ex-branch" className="mb-1 block text-xs font-semibold text-muted">الفرع</label>
                <Select id="ex-branch" value={form.warehouse_id} onChange={(e) => set({ warehouse_id: e.target.value })}>
                  <option value="">— مصروف عام للشركة —</option>
                  {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </Select>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="ex-method" className="mb-1 block text-xs font-semibold text-muted">طريقة الدفع</label>
                <Select id="ex-method" value={form.payment_method} onChange={(e) => set({ payment_method: e.target.value })}>
                  <option value="cash">نقداً</option>
                  <option value="bank">تحويل بنكي</option>
                  <option value="cheque">شيك</option>
                  <option value="card">بطاقة</option>
                  <option value="wallet">محفظة إلكترونية</option>
                </Select>
              </div>
              <div>
                <label htmlFor="ex-source" className="mb-1 block text-xs font-semibold text-muted">يُصرف من</label>
                <PaySourceSelect id="ex-source" value={form.source} onChange={(v) => set({ source: v })} emptyLabel="— يُحدد عند الاعتماد —" />
              </div>
            </div>
          </>
        )}
        <div>
          <label htmlFor="ex-notes" className="mb-1 block text-xs font-semibold text-muted">ملاحظات</label>
          <Input id="ex-notes" maxLength={2000} value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
        </div>
        <fieldset className="rounded-xl border border-line p-3">
          <label className="flex items-center gap-2 text-xs font-semibold">
            <input type="checkbox" checked={form.is_recurring} onChange={(e) => set({ is_recurring: e.target.checked })} />
            مصروف دوري (تُنشأ مسودته التالية تلقائياً كل فترة)
          </label>
          {form.is_recurring && (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="ex-interval" className="mb-1 block text-xs font-medium text-muted">يتكرر</label>
                <Select id="ex-interval" value={form.recurring_interval} onChange={(e) => set({ recurring_interval: e.target.value as RecurringInterval })}>
                  {(Object.keys(INTERVAL_LABEL) as RecurringInterval[]).map((k) => <option key={k} value={k}>{INTERVAL_LABEL[k]}</option>)}
                </Select>
              </div>
              <div>
                <label htmlFor="ex-end" className="mb-1 block text-xs font-medium text-muted">حتى تاريخ (اختياري)</label>
                <Input id="ex-end" type="date" className="num" value={form.recurring_end_date} onChange={(e) => set({ recurring_end_date: e.target.value })} />
              </div>
            </div>
          )}
        </fieldset>
        {error && <ErrorBox message={error} />}
        <Button type="submit" className="w-full h-11 font-bold text-xs rounded-xl" disabled={pending || !valid}>
          {pending ? <Spinner /> : row ? "حفظ التعديل" : "حفظ المصروف"}
        </Button>
      </form>
    </Modal>
  );
}
