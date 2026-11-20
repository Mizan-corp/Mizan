// Goods sent back to the supplier from what an order's receipts brought in: at the order's own
// cost (and VAT, in proportion), lowering the supplier's balance or refunded into a safe or wallet.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, money, moneyEGP } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Button, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";
import { parseNumber } from "@activities/general/modules/inventory/lib";
import type { PurchaseRow, Returnable } from "../api";

export function ReturnModal({ order, onClose }: { order: PurchaseRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const canPay = useAuth((s) => s.can)("finance");
  const [qty, setQty] = useState<Record<string, string>>({});
  const [refund, setRefund] = useState("");
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");
  const info = useQuery({
    queryKey: ["purchases", "returns", order?.id],
    queryFn: () => api.get<{ returnable: Returnable[] }>(`/purchases/${order!.id}/returns`),
    enabled: !!order,
  });
  const lines = (info.data?.returnable ?? []).filter((r) => (parseNumber(qty[r.product_id]) ?? D(0)).gt(0));
  const bad = (info.data?.returnable ?? []).some((r) => {
    const raw = qty[r.product_id]?.trim();
    if (!raw) return false;
    const q = parseNumber(raw);
    return q === null || q.gt(D(r.returnable));
  });
  const total = lines.reduce((s, r) => s.plus(parseNumber(qty[r.product_id])!.times(D(r.unit_cost).plus(D(r.unit_tax ?? 0)))), D(0));
  const refunding = canPay && (parseNumber(refund, 2)?.gt(0) ?? false);
  const close = () => { setQty({}); setRefund(""); setSource(""); setNotes(""); onClose(); };

  const send = useMutation({
    mutationFn: () => api.post<{ return_number: string }>(`/purchases/${order!.id}/returns`, {
      items: lines.map((r) => ({ product_id: r.product_id, qty: parseNumber(qty[r.product_id])!.toString() })),
      notes: notes.trim() || null,
      ...(refunding ? { refund_amount: parseNumber(refund, 2)!.toString(), ...sourceFields(source) } : {}),
    }),
    onSuccess: (r) => {
      toast("success", `سُجّل المرتجع ${r.return_number}`);
      for (const k of ["purchases", "safes", "wallets", "suppliers", "stock"]) qc.invalidateQueries({ queryKey: [k] });
      close();
    },
  });

  return (
    <Modal open={!!order} onClose={close} title={`مرتجع للمورد — ${order?.po_number ?? ""}`} wide>
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (lines.length && !bad && (!refunding || source) && !send.isPending) send.mutate(); }}>
        <p className="text-xs text-muted">
          ترجع البضاعة بتكلفتها في أمر الشراء وتخرج من المخزن، بحد أقصى ما استُلم ولم يُرجع. تُخصم القيمة من رصيد المورد، أو تدخل الخزنة أو المحفظة إن استرددتها نقداً.
        </p>
        {info.isLoading ? <Skeleton className="h-20 w-full" /> : info.isError ? (
          <ErrorBox message={(info.error as Error).message} onRetry={() => info.refetch()} />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="p-2 text-start">الصنف</th>
                  <th className="p-2 text-start">المستلم</th>
                  <th className="p-2 text-start">المتاح للإرجاع</th>
                  <th className="p-2 text-start">تكلفة الوحدة</th>
                  <th className="p-2 text-start">الكمية المرتجعة</th>
                </tr>
              </thead>
              <tbody>
                {info.data?.returnable.map((r) => (
                  <tr key={r.product_id} className="border-b border-line/60 last:border-0">
                    <td className="p-2 font-semibold">{r.product_name ?? "—"}</td>
                    <td className="num p-2 text-xs">{D(r.received).toString()}</td>
                    <td className="num p-2">{D(r.returnable).toString()}</td>
                    <td className="num p-2">{money(r.unit_cost)}</td>
                    <td className="p-2">
                      <Input className="num w-24" inputMode="decimal" disabled={D(r.returnable).lte(0)} aria-label={`الكمية المرتجعة من ${r.product_name ?? ""}`}
                             value={qty[r.product_id] ?? ""} onChange={(e) => setQty((q) => ({ ...q, [r.product_id]: e.target.value }))} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {bad && <p className="text-xs text-destructive">كمية غير صحيحة أو أكبر من المتاح للإرجاع.</p>}
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold text-muted">قيمة المرتجع (تقريبية؛ يحسبها الخادم بدقة)</span>
          <span className="num font-black">{moneyEGP(total)}</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {canPay && (
            <div>
              <label htmlFor="ret-refund" className="mb-1 block text-xs font-semibold text-muted">المسترد نقداً من المورد — اختياري</label>
              <Input id="ret-refund" className="num font-bold" inputMode="decimal" placeholder="0.00" value={refund} onChange={(e) => setRefund(e.target.value)} />
            </div>
          )}
          {refunding && (
            <div>
              <label htmlFor="ret-source" className="mb-1 block text-xs font-semibold text-muted">استُلم في *</label>
              <PaySourceSelect id="ret-source" value={source} onChange={setSource} />
            </div>
          )}
          <div className="sm:col-span-2">
            <label htmlFor="ret-notes" className="mb-1 block text-xs font-semibold text-muted">السبب</label>
            <Input id="ret-notes" maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        {send.isError && <ErrorBox message={(send.error as Error).message} />}
        <Button type="submit" className="h-11 w-full font-bold" disabled={!lines.length || bad || (refunding && !source) || send.isPending}>
          {send.isPending ? <Spinner /> : "تأكيد المرتجع"}
        </Button>
      </form>
    </Modal>
  );
}
