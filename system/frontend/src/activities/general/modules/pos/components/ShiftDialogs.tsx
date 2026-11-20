// The shifts screen's dialogs (POS-8): closing (alone or with a manager who receives the cash),
// revenue delivery to a safe with a manager's approval, handing the drawer to a colleague, and a
// shift's summary. Approvers and colleagues come from /shifts/{id}/people (the server's rules).
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { D, dateTime, money, moneyEGP } from "@/lib/format";
import { Badge, Button, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { closeDifference, nextDayIssue } from "../lib";

export interface Shift {
  id: string;
  cashier_id: string | null;
  cashier_name?: string | null;
  warehouse_id: string | null;
  status: "open" | "closed";
  initial_amount: string;
  closing_balance: string | null;
  expected_balance: string | null;
  difference: string | null;
  next_day_drawer: string | null;
  deposit_amount: string | null;
  notes: string | null;
  started_at: string;
  closed_at: string | null;
}

export interface PaymentLine { method: string; wallet_name: string | null; count: number; total: string | number }

export interface ShiftSummary {
  shift_id: string;
  initial_amount: string;
  sales_total: string;
  returns_total: string;
  expenses_total: string;
  deposits_total: string;
  withdrawals_total: string;
  revenue_delivery_total: string;
  expected_balance: string;
  wallet_total: string | null;
  closing_balance: string | null;
  variance: string | null;
  transaction_count: number;
  payment_breakdown: PaymentLine[];
}

interface Person { id: string; full_name: string }
interface People { approvers: Person[]; receivers: Person[] }
interface SafeRow { id: string; name: string; safe_type: string; is_active?: boolean }

const METHOD_LABEL: Record<string, string> = { cash: "نقدي", wallet: "محفظة", credit: "آجل", bank: "تحويل بنكي", cheque: "شيك" };

function usePeople(shiftId: string | null) {
  return useQuery({
    queryKey: ["shift-people", shiftId],
    queryFn: () => api.get<People>(`/shifts/${shiftId}/people`),
    enabled: !!shiftId,
  });
}

function refreshShift(qc: ReturnType<typeof useQueryClient>) {
  for (const key of ["shift", "shifts", "shift-txs", "shift-summary", "safes", "shift-people"]) qc.invalidateQueries({ queryKey: [key] });
}

/** The figures of a shift: what came in and out of the drawer and how its sales were paid. */
export function SummaryView({ s }: { s: ShiftSummary }) {
  const tiles: [string, string | number, string?][] = [
    ["العهدة الافتتاحية", s.initial_amount],
    ["المبيعات", s.sales_total, "+"],
    ["الإيداعات", s.deposits_total, "+"],
    ["المرتجعات", s.returns_total, "−"],
    ["المصروفات", s.expenses_total, "−"],
    ["السحوبات", s.withdrawals_total, "−"],
    ["المورَّد إلى الخزنة", s.revenue_delivery_total, "−"],
  ];
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles.map(([label, value, sign]) => (
          <div key={label} className="rounded-lg border border-line p-2.5">
            <p className="text-[11px] text-muted-foreground">{label}</p>
            <p className="num text-sm font-semibold">{sign && D(value).gt(0) ? `${sign} ` : ""}{money(value)}</p>
          </div>
        ))}
        <div className="rounded-lg border border-primary/40 bg-primary/5 p-2.5">
          <p className="text-[11px] font-semibold text-primary">النقدية المتوقعة في الدرج</p>
          <p className="num text-base font-bold">{moneyEGP(s.expected_balance)}</p>
        </div>
      </div>
      {s.payment_breakdown.length > 0 && (
        <div className="rounded-lg border border-line p-2.5">
          <p className="mb-1.5 text-xs font-semibold text-muted-foreground">المبيعات حسب طريقة الدفع</p>
          <ul className="flex flex-col gap-1 text-sm">
            {s.payment_breakdown.map((p, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span>{METHOD_LABEL[p.method] ?? p.method}{p.wallet_name ? ` — ${p.wallet_name}` : ""}
                  <span className="num ms-1 text-xs text-muted-foreground">({p.count} فاتورة)</span>
                </span>
                <span className="num font-semibold">{moneyEGP(p.total)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-[11px] text-muted-foreground">النقدي وحده في الدرج؛ المحافظ والبنك والآجل خارجه.</p>
        </div>
      )}
    </div>
  );
}

function ManagerFields({ people, managerId, setManagerId, password, setPassword, idPrefix }: {
  people: ReturnType<typeof usePeople>; managerId: string; setManagerId: (v: string) => void;
  password: string; setPassword: (v: string) => void; idPrefix: string;
}) {
  if (people.isError) return <ErrorBox message={(people.error as Error).message} onRetry={() => people.refetch()} />;
  const none = people.isSuccess && !people.data.approvers.length;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div>
        <label htmlFor={`${idPrefix}-mgr`} className="mb-1 block text-xs font-semibold text-muted-foreground">المدير المعتمِد *</label>
        <Select id={`${idPrefix}-mgr`} value={managerId} onChange={(e) => setManagerId(e.target.value)} disabled={people.isLoading || none}>
          <option value="">{people.isLoading ? "جارٍ التحميل…" : none ? "لا يوجد من يعتمد" : "— اختر المدير —"}</option>
          {people.data?.approvers.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
        </Select>
      </div>
      <div>
        <label htmlFor={`${idPrefix}-pw`} className="mb-1 block text-xs font-semibold text-muted-foreground">كلمة مرور المدير *</label>
        <Input id={`${idPrefix}-pw`} type="password" autoComplete="off" maxLength={256} value={password} onChange={(e) => setPassword(e.target.value)} />
      </div>
    </div>
  );
}

// ── Close ─────────────────────────────────────────────────────────────────────────────────────

export function CloseShiftModal({ shift, summary, onClose }: { shift: Shift | null; summary: ShiftSummary | undefined; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [counted, setCounted] = useState("");
  const [keep, setKeep] = useState("");
  const [notes, setNotes] = useState("");
  const [withManager, setWithManager] = useState(false);
  const [managerId, setManagerId] = useState("");
  const [password, setPassword] = useState("");
  const people = usePeople(shift && withManager ? shift.id : null);

  useEffect(() => {
    setCounted(""); setKeep(""); setNotes(""); setWithManager(false); setManagerId(""); setPassword("");
  }, [shift?.id]);

  const diff = summary ? closeDifference(counted, summary.expected_balance) : null;
  const keepIssue = nextDayIssue(counted, keep);
  const close = useMutation({
    mutationFn: () => {
      const body = { closing_balance: counted, next_day_drawer: keep.trim() === "" ? null : keep, notes: notes.trim() || null };
      return withManager
        ? api.post<{ variance: number }>(`/shifts/${shift!.id}/close-with-manager`, { ...body, manager_id: managerId, manager_password: password })
        : api.post<{ variance: number }>(`/shifts/${shift!.id}/close`, body);
    },
    onSuccess: (r) => {
      const v = Number(r?.variance ?? 0);
      toast(v === 0 ? "success" : "warning", v === 0 ? "أُغلقت الوردية — الدرج مطابق" : `أُغلقت الوردية — ${v < 0 ? "عجز" : "زيادة"} ${money(Math.abs(v))} ج.م`);
      refreshShift(qc);
      onClose();
    },
  });
  const blocked = close.isPending || counted.trim() === "" || !Number.isFinite(Number(counted)) || Number(counted) < 0 || !!keepIssue
    || (withManager && (!managerId || !password));

  return (
    <Modal open={!!shift} onClose={onClose} title="إغلاق الوردية" wide>
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!blocked) close.mutate(); }}>
        {summary ? <SummaryView s={summary} /> : <p className="text-xs text-muted-foreground">جارٍ حساب ملخص الوردية…</p>}
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="close-counted" className="mb-1 block text-xs font-semibold text-muted-foreground">النقدية المعدودة في الدرج *</label>
            <Input id="close-counted" autoFocus className="num text-lg font-bold" inputMode="decimal" value={counted} onChange={(e) => setCounted(e.target.value)} />
            {diff && (
              <p className={`mt-1 text-xs font-semibold ${diff.value.isZero() ? "text-success-ink" : diff.value.lt(0) ? "text-destructive-ink" : "text-warning-ink"}`}>
                {diff.label}{diff.value.isZero() ? "" : ` ${money(diff.value.abs())} ج.م`}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="close-keep" className="mb-1 block text-xs font-semibold text-muted-foreground">يُترك في الدرج للوردية التالية</label>
            <Input id="close-keep" className="num" inputMode="decimal" placeholder="كل المعدود" value={keep} onChange={(e) => setKeep(e.target.value)} />
            {keepIssue && <p className="mt-1 text-xs text-destructive-ink">{keepIssue}</p>}
          </div>
        </div>
        <div>
          <label htmlFor="close-notes" className="mb-1 block text-xs font-semibold text-muted-foreground">ملاحظات</label>
          <Input id="close-notes" maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={withManager} onChange={(e) => setWithManager(e.target.checked)} />
          الإغلاق بحضور مدير يستلم الباقي (المعدود ناقص المتروك) ويعتمد بكلمة مروره
        </label>
        {withManager && (
          <>
            <ManagerFields people={people} managerId={managerId} setManagerId={setManagerId} password={password} setPassword={setPassword} idPrefix="close" />
            <p className="text-[11px] text-muted-foreground">
              يُودَع المستلَم في خزنة المنشأة إن كانت لها خزنة نقدية واحدة نشطة، ويُسجَّل الفرق على الموظف (خصم أو مكافأة).
            </p>
          </>
        )}
        {close.isError && <ErrorBox message={(close.error as Error).message} />}
        <div className="flex gap-2">
          <Button type="submit" variant="danger" className="h-10 flex-1 font-bold" disabled={blocked}>
            {close.isPending ? <Spinner /> : "إغلاق الوردية"}
          </Button>
          <Button type="button" variant="ghost" className="h-10 flex-1" onClick={onClose}>تراجع</Button>
        </div>
      </form>
    </Modal>
  );
}

// ── Revenue delivery ──────────────────────────────────────────────────────────────────────────

export function RevenueDeliveryModal({ shift, expected, onClose }: { shift: Shift | null; expected: string | undefined; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [safeId, setSafeId] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [managerId, setManagerId] = useState("");
  const [password, setPassword] = useState("");
  const people = usePeople(shift?.id ?? null);
  const safes = useQuery({ queryKey: ["safes"], queryFn: () => api.get<SafeRow[]>("/safes"), enabled: !!shift });
  const active = (safes.data ?? []).filter((s) => s.is_active !== false);

  useEffect(() => {
    setSafeId(""); setAmount(""); setNotes(""); setManagerId(""); setPassword("");
  }, [shift?.id]);

  const over = expected !== undefined && amount.trim() !== "" && D(Number(amount) || 0).gt(D(expected));
  const deliver = useMutation({
    mutationFn: () => api.post<{ doc_number: string; safe: string; received_by: string }>(`/shifts/${shift!.id}/revenue-delivery`, {
      amount, safe_id: safeId, manager_id: managerId, manager_password: password, notes: notes.trim() || null,
    }),
    onSuccess: (r) => {
      toast("success", `تم التوريد إلى ${r.safe} — مستند ${r.doc_number} (استلم ${r.received_by})`);
      refreshShift(qc);
      onClose();
    },
  });
  const blocked = deliver.isPending || !safeId || !(Number(amount) > 0) || over || !managerId || !password;

  return (
    <Modal open={!!shift} onClose={onClose} title="توريد إيرادات من الدرج إلى خزنة">
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!blocked) deliver.mutate(); }}>
        {expected !== undefined && (
          <p className="rounded-lg border border-line bg-secondary/30 p-2.5 text-sm">
            النقدية المتوقعة في الدرج الآن: <strong className="num">{moneyEGP(expected)}</strong>
          </p>
        )}
        <div>
          <label htmlFor="rd-safe" className="mb-1 block text-xs font-semibold text-muted-foreground">الخزنة *</label>
          {safes.isError ? (
            <ErrorBox message={(safes.error as Error).message} onRetry={() => safes.refetch()} />
          ) : (
            <Select id="rd-safe" value={safeId} onChange={(e) => setSafeId(e.target.value)} disabled={safes.isLoading}>
              <option value="">{safes.isSuccess && !active.length ? "لا توجد خزائن — أضفها من شاشة المالية" : "— اختر الخزنة —"}</option>
              {active.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          )}
        </div>
        <div>
          <label htmlFor="rd-amount" className="mb-1 block text-xs font-semibold text-muted-foreground">المبلغ (ج.م) *</label>
          <Input id="rd-amount" className="num text-lg font-bold" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
          {over && <p className="mt-1 text-xs text-destructive-ink">المبلغ أكبر من النقدية المتوقعة في الدرج</p>}
        </div>
        <ManagerFields people={people} managerId={managerId} setManagerId={setManagerId} password={password} setPassword={setPassword} idPrefix="rd" />
        <div>
          <label htmlFor="rd-notes" className="mb-1 block text-xs font-semibold text-muted-foreground">ملاحظات</label>
          <Input id="rd-notes" maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        {deliver.isError && <ErrorBox message={(deliver.error as Error).message} />}
        <Button type="submit" className="h-10 w-full font-bold" disabled={blocked}>
          {deliver.isPending ? <Spinner /> : "توريد المبلغ"}
        </Button>
      </form>
    </Modal>
  );
}

// ── Handover ──────────────────────────────────────────────────────────────────────────────────

export function HandoverModal({ shift, expected, onClose }: { shift: Shift | null; expected: string | undefined; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [toUser, setToUser] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const people = usePeople(shift?.id ?? null);

  useEffect(() => {
    setToUser(""); setNotes("");
    setAmount(expected !== undefined ? D(expected).toFixed(2) : "");
  }, [shift?.id, expected]);

  const diff = expected !== undefined ? closeDifference(amount, expected) : null;
  const handover = useMutation({
    mutationFn: () => api.post<Shift>(`/shifts/${shift!.id}/transfer`, { to_user_id: toUser, amount, notes: notes.trim() || null }),
    onSuccess: (r) => {
      toast("success", `سُلِّمت العهدة إلى ${r.cashier_name ?? "الزميل"} — أُغلقت ورديتك`);
      refreshShift(qc);
      onClose();
    },
  });
  const receivers = people.data?.receivers ?? [];
  const blocked = handover.isPending || !toUser || amount.trim() === "" || !(Number(amount) >= 0);

  return (
    <Modal open={!!shift} onClose={onClose} title="تسليم العهدة لزميل">
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!blocked) handover.mutate(); }}>
        <p className="text-xs text-muted-foreground">
          تُغلق ورديتك بالمبلغ المسلَّم وتُفتح للزميل وردية بنفس المبلغ في هذا الفرع، ويُسجَّل مستند تسليم والفرق على صاحب الوردية.
        </p>
        <div>
          <label htmlFor="ho-user" className="mb-1 block text-xs font-semibold text-muted-foreground">المستلم *</label>
          {people.isError ? (
            <ErrorBox message={(people.error as Error).message} onRetry={() => people.refetch()} />
          ) : (
            <Select id="ho-user" value={toUser} onChange={(e) => setToUser(e.target.value)} disabled={people.isLoading}>
              <option value="">{people.isLoading ? "جارٍ التحميل…" : receivers.length ? "— اختر الزميل —" : "لا يوجد زميل متاح في هذا الفرع"}</option>
              {receivers.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
            </Select>
          )}
        </div>
        <div>
          <label htmlFor="ho-amount" className="mb-1 block text-xs font-semibold text-muted-foreground">المبلغ المسلَّم فعلاً (ج.م) *</label>
          <Input id="ho-amount" className="num text-lg font-bold" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
          {diff && !diff.value.isZero() && (
            <p className="mt-1 text-xs text-warning-ink">{diff.label} {money(diff.value.abs())} ج.م عن المتوقع</p>
          )}
        </div>
        <div>
          <label htmlFor="ho-notes" className="mb-1 block text-xs font-semibold text-muted-foreground">ملاحظات</label>
          <Input id="ho-notes" maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        {handover.isError && <ErrorBox message={(handover.error as Error).message} />}
        <Button type="submit" className="h-10 w-full font-bold" disabled={blocked}>
          {handover.isPending ? <Spinner /> : "تسليم العهدة"}
        </Button>
      </form>
    </Modal>
  );
}

// ── A past shift ──────────────────────────────────────────────────────────────────────────────

export function ShiftSummaryModal({ shift, onClose }: { shift: Shift | null; onClose: () => void }) {
  const summary = useQuery({
    queryKey: ["shift-summary", shift?.id],
    queryFn: () => api.get<ShiftSummary>(`/shifts/${shift!.id}/summary`),
    enabled: !!shift,
  });
  return (
    <Modal open={!!shift} onClose={onClose} title={`وردية ${shift?.cashier_name ?? ""} — ${shift ? dateTime(shift.started_at) : ""}`} wide>
      {shift && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge tone={shift.status === "open" ? "success" : "muted"}>{shift.status === "open" ? "مفتوحة" : "مغلقة"}</Badge>
            {shift.closed_at && <span>أُغلقت {dateTime(shift.closed_at)}</span>}
            {shift.notes && <span>· {shift.notes}</span>}
          </div>
          {summary.isLoading ? (
            <div className="grid place-items-center p-8"><Spinner /></div>
          ) : summary.isError ? (
            <ErrorBox message={(summary.error as Error).message} onRetry={() => summary.refetch()} />
          ) : summary.data && (
            <>
              <SummaryView s={summary.data} />
              {summary.data.closing_balance != null && (
                <p className="text-sm">
                  المعدود عند الإغلاق <strong className="num">{moneyEGP(summary.data.closing_balance)}</strong>
                  {summary.data.variance != null && Number(summary.data.variance) !== 0 && (
                    <span className={Number(summary.data.variance) < 0 ? "text-destructive-ink" : "text-warning-ink"}>
                      {" "}— {Number(summary.data.variance) < 0 ? "عجز" : "زيادة"} <span className="num">{money(Math.abs(Number(summary.data.variance)))}</span>
                    </span>
                  )}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </Modal>
  );
}
