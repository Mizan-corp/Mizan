// One purchase order (PUR-4): its lines (ordered, received, left), its goods receipts with what each
// brought (cost, batch, expiry), the movements it made on the supplier's account (invoices, payments
// with a receipt) and its returns. A draft is edited, cancelled, deleted or received; a partly
// received order receives the rest or is closed; received goods can go back to the supplier.
import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Ban, CheckCheck, FileUp, PackageCheck, Pencil, Printer, Trash2, Undo2 } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api, apiUrl, openPrintDoc } from "@/lib/api";
import { D, date as fmtDate, dateTime, money, moneyEGP, qty as fq } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, useToast } from "@/components/ui";
import { useTenantNav } from "@app/lib/tenant";
import { imageSrc } from "@activities/general/modules/inventory/lib";
import type { PurchaseDetail } from "../api";
import { OrderForm } from "../components/OrderForm";
import { PurchasesHeader } from "../components/PurchasesHeader";
import { ReceiveModal } from "../components/ReceiveModal";
import { ReturnModal } from "../components/ReturnModal";
import { actionsFor, STATUS } from "../lib";

type Confirm = "cancel" | "delete" | "close" | null;

export default function PurchaseOrderPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { tenantTo } = useTenantNav();
  const { toast } = useToast();
  const canBuy = useAuth((s) => s.can)("purchases");
  const [editing, setEditing] = useState(false);
  const [receiving, setReceiving] = useState(false);
  const [returning, setReturning] = useState(false);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const invoiceInput = useRef<HTMLInputElement>(null);
  const [deleted, setDeleted] = useState(false);
  const order = useQuery({ queryKey: ["purchases", "detail", id], queryFn: () => api.get<PurchaseDetail>(`/purchases/${id}`), enabled: !deleted });
  const po = order.data;

  const act = useMutation({
    mutationFn: (what: Exclude<Confirm, null>) =>
      what === "delete" ? api.del(`/purchases/${id}`) : api.post(`/purchases/${id}/${what}`, {}),
    onSuccess: (_r, what) => {
      toast("success", what === "delete" ? "حُذفت المسودة" : what === "cancel" ? "أُلغي أمر الشراء" : "أُغلق أمر الشراء");
      setConfirm(null);
      if (what === "delete") {
        setDeleted(true);
        qc.invalidateQueries({ queryKey: ["purchases", "list"] });
        navigate(tenantTo("/purchases"));
        return;
      }
      qc.invalidateQueries({ queryKey: ["purchases"] });
    },
    onError: (e) => { setConfirm(null); toast("error", (e as Error).message); },
  });

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.postForm(`/purchases/${id}/upload-invoice`, form);
    },
    onSuccess: () => { toast("success", "رُفعت فاتورة المورد"); qc.invalidateQueries({ queryKey: ["purchases", "detail", id] }); },
    onError: (e) => toast("error", (e as Error).message),
  });

  if (order.isLoading) return <div className="flex flex-col gap-3"><Skeleton className="h-16 w-full" /><Skeleton className="h-64 w-full" /></div>;
  if (order.isError || !po) {
    return (
      <div className="flex flex-col gap-4">
        <Link to={tenantTo("/purchases")} className="inline-flex items-center gap-1 text-sm text-primary"><ArrowRight className="size-4" /> أوامر الشراء</Link>
        <ErrorBox message={(order.error as Error)?.message ?? "أمر الشراء غير موجود"} onRetry={() => order.refetch()} />
      </div>
    );
  }
  const can = actionsFor(po.status);
  const left = po.items.reduce((s, i) => s.plus(D(i.qty_remaining)), D(0));

  return (
    <div className="flex flex-col gap-6">
      <Link to={tenantTo("/purchases")} className="inline-flex items-center gap-1 self-start text-xs font-semibold text-primary">
        <ArrowRight className="size-4" /> أوامر الشراء
      </Link>
      <PurchasesHeader
        title={<span className="flex items-center gap-3"><span className="num" dir="ltr">{po.po_number}</span><Badge tone={STATUS[po.status].tone}>{STATUS[po.status].label}</Badge></span>}
        subtitle={`${po.supplier_name ?? "شراء نقدي"} · ${po.warehouse_name ?? ""} · أنشأه ${po.created_by_name ?? "—"} في ${fmtDate(po.created_at)}`}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => openPrintDoc(`/print/purchase/${po.id}`).catch((e) => toast("error", (e as Error).message))}>
              <Printer className="size-4" /> طباعة الأمر
            </Button>
            {canBuy && can.edit && <Button variant="outline" size="sm" onClick={() => setEditing(true)}><Pencil className="size-4" /> تعديل</Button>}
            {canBuy && can.receive && <Button size="sm" onClick={() => setReceiving(true)}><PackageCheck className="size-4" /> {po.status === "partial" ? "استلام الباقي" : "استلام"}</Button>}
            {canBuy && can.returnGoods && <Button variant="outline" size="sm" onClick={() => setReturning(true)}><Undo2 className="size-4" /> مرتجع للمورد</Button>}
            {canBuy && can.close && <Button variant="ghost" size="sm" onClick={() => setConfirm("close")}><CheckCheck className="size-4" /> إغلاق دون الباقي</Button>}
            {canBuy && can.cancel && <Button variant="ghost" size="sm" onClick={() => setConfirm("cancel")}><Ban className="size-4" /> إلغاء</Button>}
            {canBuy && can.remove && <Button variant="ghost" size="sm" onClick={() => setConfirm("delete")}><Trash2 className="size-4 text-destructive" /> حذف</Button>}
          </>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="إجمالي الأمر" value={moneyEGP(po.ordered_total)} hint="الكميات المطلوبة بتكلفة الأمر" />
        <Stat label="قيمة المستلم" value={po.status === "draft" || po.status === "cancelled" ? "—" : moneyEGP(po.total)}
              hint={D(po.tax_amount ?? 0).gt(0) ? `منها ضريبة ${moneyEGP(po.tax_amount!)}` : "يُضاف إلى حساب المورد"} />
        <Stat label="المدفوع عند الاستلام" value={moneyEGP(po.status === "draft" ? 0 : po.amount_paid ?? 0)} hint={po.status === "draft" && D(po.amount_paid ?? 0).gt(0) ? `مخطط: ${moneyEGP(po.amount_paid)}` : ""} />
        <Stat label="المتبقي للاستلام" value={po.status === "cancelled" ? "—" : `${fq(left)}`} hint={po.status === "received" && left.gt(0) ? "أُغلق دون استلامه" : "وحدة من كل الأصناف"} />
      </div>
      {po.notes && <p className="rounded-xl border border-line bg-card p-3 text-sm text-muted">{po.notes}</p>}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-card p-3 text-sm">
        <span className="font-semibold">فاتورة المورد:</span>
        {po.invoice_image_url
          ? <a href={imageSrc(po.invoice_image_url, apiUrl) ?? "#"} target="_blank" rel="noreferrer" className="text-primary underline">عرض الملف المرفوع</a>
          : <span className="text-muted">لم تُرفع بعد</span>}
        <input ref={invoiceInput} type="file" accept="image/jpeg,image/png,image/gif,image/webp,application/pdf" className="hidden"
               onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
        {canBuy && (
          <Button variant="outline" size="sm" disabled={upload.isPending} onClick={() => invoiceInput.current?.click()}>
            <FileUp className="size-4" /> {po.invoice_image_url ? "استبدال" : "رفع صورة أو PDF"}
          </Button>
        )}
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-base font-bold">الأصناف</h2>
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">الصنف</th>
                <th className="p-3 text-end">المطلوب</th>
                <th className="p-3 text-end">المستلم</th>
                <th className="p-3 text-end">المتبقي</th>
                <th className="p-3 text-end">تكلفة الوحدة</th>
              </tr>
            </thead>
            <tbody>
              {po.items.map((i) => (
                <tr key={i.id} className="border-b border-line/60 last:border-0">
                  <td className="p-3 font-semibold">{i.product_name}</td>
                  <td className="num p-3 text-end">{fq(i.qty_ordered)} <span className="text-xs text-muted">{i.unit}</span></td>
                  <td className="num p-3 text-end">{fq(i.qty_received)}</td>
                  <td className={`num p-3 text-end ${D(i.qty_remaining).gt(0) ? "font-bold text-warning" : "text-muted"}`}>{fq(i.qty_remaining)}</td>
                  <td className="num p-3 text-end">{money(i.unit_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-base font-bold">إذونات الاستلام</h2>
        {!po.receipts.length ? (
          <Empty text={po.status === "received" ? "استُلم هذا الأمر قبل تسجيل الإذونات منفصلة" : "لم يُستلم شيء بعد"}
                 hint={po.status === "received" ? "الكميات المستلمة في جدول الأصناف أعلاه." : undefined} />
        ) : (
          <div className="flex flex-col gap-3">
            {po.receipts.map((r) => (
              <div key={r.id} className="rounded-xl border border-line bg-card">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line/60 px-4 py-2 text-sm">
                  <span className="flex items-center gap-2"><span className="num font-bold" dir="ltr">{r.receipt_number}</span><span className="text-xs text-muted">{dateTime(r.created_at)} · {r.created_by_name ?? ""}</span></span>
                  <span className="flex items-center gap-3 text-xs">
                    <span>القيمة <span className="num font-bold">{moneyEGP(r.total)}</span></span>
                    {D(r.amount_paid).gt(0) && <span>مدفوع <span className="num font-bold">{moneyEGP(r.amount_paid)}</span> من {r.safe_name ?? r.wallet_name}</span>}
                  </span>
                </div>
                <table className="w-full text-xs">
                  <tbody>
                    {r.items.map((it) => (
                      <tr key={it.id} className="border-b border-line/40 last:border-0">
                        <td className="px-4 py-2">{it.product_name}</td>
                        <td className="num px-4 py-2 text-end">{fq(it.qty)} × {money(it.unit_cost)}</td>
                        <td className="px-4 py-2 text-muted">{it.batch_number ? <>تشغيلة <span className="code" dir="ltr">{it.batch_number}</span></> : ""}{it.expiry_date ? ` · صلاحية ${fmtDate(it.expiry_date)}` : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {r.notes && <p className="px-4 py-2 text-xs text-muted">{r.notes}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="flex flex-col gap-3">
          <h2 className="text-base font-bold">حساب المورد من هذا الأمر</h2>
          {!po.payments.length ? <Empty text="لا حركات بعد" hint="تُسجَّل قيمة كل استلام وما دُفع معه، ومرتجعاته." /> : (
            <ul className="divide-y divide-line/60 rounded-xl border border-line bg-card text-sm">
              {po.payments.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-2 px-3 py-2">
                  <span className="min-w-0">
                    <span className="block truncate">{m.notes ?? (m.type === "debit" ? "مستحق للمورد" : "دفعة")}</span>
                    <span className="text-[11px] text-muted">{dateTime(m.created_at)}{m.safe_name || m.wallet_name ? ` · ${m.safe_name ?? m.wallet_name}` : ""}</span>
                  </span>
                  <span className={`num shrink-0 font-bold ${m.type === "debit" ? "text-destructive" : "text-success"}`}>
                    {m.type === "debit" ? "+" : "−"}{money(m.amount)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="flex flex-col gap-3">
          <h2 className="text-base font-bold">المرتجعات للمورد</h2>
          {!po.returns.length ? <Empty text="لا مرتجعات" /> : (
            <ul className="divide-y divide-line/60 rounded-xl border border-line bg-card text-sm">
              {po.returns.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-2 px-3 py-2">
                  <span><span className="num font-bold" dir="ltr">{r.return_number}</span> <span className="text-[11px] text-muted">{dateTime(r.created_at)}</span></span>
                  <span className="text-xs">
                    <span className="num font-bold">{moneyEGP(r.total)}</span>
                    {D(r.refund_amount).gt(0) && <span className="text-muted"> · مسترد {moneyEGP(r.refund_amount)}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <OrderForm open={editing} order={po} onClose={() => setEditing(false)} />
      <ReceiveModal order={receiving ? po : null} onClose={() => setReceiving(false)} />
      <ReturnModal order={returning ? po : null} onClose={() => setReturning(false)} />
      <ConfirmDialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        onConfirm={() => confirm && act.mutate(confirm)}
        title={confirm === "delete" ? "حذف المسودة" : confirm === "cancel" ? "إلغاء أمر الشراء" : "إغلاق أمر الشراء"}
        message={confirm === "delete" ? "تُحذف المسودة نهائياً؛ لم يُستلم بها شيء ولم يُدفع."
          : confirm === "cancel" ? "يبقى الأمر في السجل ملغياً ولا يمكن استلامه."
          : "يصبح الأمر مستلماً بما وصل فقط؛ لا يُستلم الباقي بعد ذلك (سجّل أمراً جديداً إن وصل). لا يُرحَّل شيء جديد."}
        confirmLabel={confirm === "delete" ? "حذف" : confirm === "cancel" ? "إلغاء الأمر" : "إغلاق"}
      />
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-card p-4">
      <p className="text-[11px] font-medium text-muted">{label}</p>
      <p className="num mt-1 text-lg font-bold">{value}</p>
      {hint && <p className="mt-0.5 text-[10px] text-muted">{hint}</p>}
    </div>
  );
}
