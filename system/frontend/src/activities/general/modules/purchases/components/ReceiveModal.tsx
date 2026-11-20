// A goods receipt (PUR-4): what arrived now of each line (all that is left by default, 0 for
// nothing), at what unit cost, in which batch and with which expiry; what is paid with it (finance).
// Each receipt is its own document and posts its own ledger entry; the order is partly received
// until every line has arrived.
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { moneyEGP } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Button, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";
import { useVat } from "@app/lib/vat";
import { parseNumber } from "@activities/general/modules/inventory/lib";
import type { PurchaseDetail } from "../api";
import { type ReceiveRow, receiveIssues, receivePayload, receiveRows, receiveTotal } from "../lib";

export function ReceiveModal({ order, onClose }: { order: PurchaseDetail | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const canPay = useAuth((s) => s.can)("finance");
  const vat = useVat();
  const [rows, setRows] = useState<ReceiveRow[]>([]);
  const [paid, setPaid] = useState("");
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");
  const [inclusive, setInclusive] = useState<boolean | null>(null);

  useEffect(() => {
    if (!order) return;
    setRows(receiveRows(order.items));
    // A draft's planned payment is made with its first receipt.
    setPaid(order.status === "draft" && Number(order.amount_paid) > 0 ? String(Number(order.amount_paid)) : "");
    setSource("");
    setNotes("");
    setInclusive(order.prices_include_vat);
  }, [order]);

  const paying = canPay && (parseNumber(paid, 2)?.gt(0) ?? false);
  const issues = receiveIssues(rows);
  if (paid.trim() && parseNumber(paid, 2) === null) issues.push("المبلغ المدفوع غير صحيح");
  const set = (i: number, patch: Partial<ReceiveRow>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const receive = useMutation({
    mutationFn: () => api.post<{ receipt_number: string; status: string }>(`/purchases/${order!.id}/receive`, {
      items: receivePayload(rows),
      amount_paid: paying ? parseNumber(paid, 2)!.toString() : "0",
      ...(paying ? sourceFields(source) : {}),
      notes: notes.trim() || null,
      ...(vat.data?.vat_registered ? { prices_include_vat: inclusive ?? vat.data.prices_include_vat } : {}),
    }),
    onSuccess: (r) => {
      toast("success", r.status === "partial" ? `سُجّل الاستلام ${r.receipt_number} — الأمر مستلم جزئياً` : `سُجّل الاستلام ${r.receipt_number}`);
      for (const k of ["purchases", "purchase", "safes", "wallets", "suppliers", "stock", "products"]) qc.invalidateQueries({ queryKey: [k] });
      onClose();
    },
  });

  return (
    <Modal open={!!order} onClose={onClose} title={`استلام بضاعة — ${order?.po_number ?? ""}`} wide>
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!issues.length && (!paying || source) && !receive.isPending) receive.mutate(); }}>
        <p className="text-xs text-muted">
          أدخل ما وصل فعلاً: الكمية (0 لما لم يصل بعد، ويبقى لاستلام لاحق)، وتكلفة الوحدة كما في فاتورة المورد، ورقم التشغيلة والصلاحية عند الحاجة.
          تدخل الكميات المخزن ويُضاف قدرها إلى حساب المورد.
        </p>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-2 text-start">الصنف</th>
                <th className="p-2 text-start">المتبقي</th>
                <th className="p-2 text-start">المستلم الآن</th>
                <th className="p-2 text-start">تكلفة الوحدة</th>
                <th className="p-2 text-start">التشغيلة</th>
                <th className="p-2 text-start">الصلاحية</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.item_id} className="border-b border-line/60 last:border-0">
                  <td className="p-2 font-semibold">{r.product_name}</td>
                  <td className="num p-2 text-xs text-muted">{r.remaining} {r.unit}</td>
                  <td className="p-2"><Input className="num w-24" inputMode="decimal" aria-label={`الكمية المستلمة من ${r.product_name}`} value={r.qty} onChange={(e) => set(i, { qty: e.target.value })} /></td>
                  <td className="p-2"><Input className="num w-28" inputMode="decimal" aria-label={`تكلفة ${r.product_name}`} value={r.unit_cost} onChange={(e) => set(i, { unit_cost: e.target.value })} /></td>
                  <td className="p-2"><Input className="code w-28" dir="ltr" maxLength={64} aria-label={`تشغيلة ${r.product_name}`} value={r.batch_number} onChange={(e) => set(i, { batch_number: e.target.value })} /></td>
                  <td className="p-2"><Input type="date" className="w-40" aria-label={`صلاحية ${r.product_name}`} value={r.expiry_date} onChange={(e) => set(i, { expiry_date: e.target.value })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold text-muted">قيمة هذا الاستلام{vat.data?.vat_registered ? " (قبل حساب الضريبة)" : ""}</span>
          <span className="num text-lg font-black">{moneyEGP(receiveTotal(rows))}</span>
        </div>
        {vat.data?.vat_registered && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={inclusive ?? vat.data.prices_include_vat} onChange={(e) => setInclusive(e.target.checked)} />
            التكلفة شاملة ضريبة القيمة المضافة (تُسجَّل ضريبة مدخلات، والمخزون بالتكلفة قبل الضريبة)
          </label>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {canPay && (
            <div>
              <label htmlFor="rc-paid" className="mb-1 block text-xs font-semibold text-muted">المدفوع الآن (ج.م)</label>
              <Input id="rc-paid" className="num font-bold" inputMode="decimal" placeholder="0.00" value={paid} onChange={(e) => setPaid(e.target.value)} />
            </div>
          )}
          {paying && (
            <div>
              <label htmlFor="rc-source" className="mb-1 block text-xs font-semibold text-muted">دُفع من *</label>
              <PaySourceSelect id="rc-source" value={source} onChange={setSource} />
            </div>
          )}
          <div className="sm:col-span-2">
            <label htmlFor="rc-notes" className="mb-1 block text-xs font-semibold text-muted">ملاحظات (رقم فاتورة المورد مثلاً)</label>
            <Input id="rc-notes" maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        {!canPay && <p className="text-[11px] text-muted">الدفع للمورد يسجله من يملك صلاحية المالية؛ يُضاف كامل قيمة الاستلام إلى رصيد المورد.</p>}
        {issues.length > 0 && <p className="text-xs text-muted">{issues.join("، ")}</p>}
        {receive.isError && <ErrorBox message={(receive.error as Error).message} />}
        <Button type="submit" className="h-11 w-full font-bold" disabled={!!issues.length || (paying && !source) || receive.isPending}>
          {receive.isPending ? <Spinner /> : "تأكيد الاستلام"}
        </Button>
      </form>
    </Modal>
  );
}
