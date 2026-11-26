// A purchase order's form: a new draft (from scratch or from purchase suggestions) or a draft's
// changes (supplier, branch, notes, lines). One line per product.
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { Button, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { useBranch } from "@app/components/AppShell";
import { useWarehouses } from "@activities/general/modules/inventory/api";
import { ProductPicker } from "@activities/general/modules/inventory/components/ProductPicker";
import { parseNumber } from "@activities/general/modules/inventory/lib";
import type { PurchaseDetail, Supplier } from "../api";
import { type OrderLine, orderIssues, orderTotal } from "../lib";

export function useSuppliers() {
  return useQuery({
    queryKey: ["suppliers-list"],
    queryFn: async () => {
      const res = await api.get<{ items: Supplier[] } | Supplier[]>("/suppliers", { page_size: 500 });
      return Array.isArray(res) ? res : res.items ?? [];
    },
  });
}

export function OrderForm({ open, order, initialLines, onClose, onSaved }: {
  open: boolean; order?: PurchaseDetail | null; initialLines?: OrderLine[]; onClose: () => void; onSaved?: (id: string) => void;
}) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const suppliers = useSuppliers();
  const warehouses = useWarehouses();
  const [supplierId, setSupplierId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<OrderLine[]>([]);

  useEffect(() => {
    if (!open) return;
    setSupplierId(order?.supplier_id ?? "");
    setWarehouseId(order?.warehouse_id ?? "");
    setNotes(order?.notes ?? "");
    setLines(order
      ? order.items.map((i) => ({ product_id: i.product_id, name: i.product_name, qty: String(Number(i.qty_ordered)), unit_cost: String(Number(i.unit_cost)) }))
      : initialLines ?? []);
  }, [open, order, initialLines]);

  const { branchId } = useBranch();
  const branch = warehouseId || branchId || warehouses.data?.[0]?.id || "";
  const issues = orderIssues(lines);
  const save = useMutation({
    mutationFn: () => {
      const items = lines.map((l) => ({ product_id: l.product_id, qty: parseNumber(l.qty)!.toString(), unit_cost: parseNumber(l.unit_cost, 2)!.toString() }));
      if (order) {
        return api.put(`/purchases/${order.id}`, {
          supplier_id: supplierId || null, clear_supplier: !supplierId, warehouse_id: branch, notes, items,
        }).then(() => ({ id: order.id }));
      }
      return api.post<{ id: string }>("/purchases", { warehouse_id: branch, supplier_id: supplierId || null, notes: notes || null, items });
    },
    onSuccess: (r) => {
      toast("success", order ? "حُفظ أمر الشراء" : "أُنشئ أمر الشراء");
      qc.invalidateQueries({ queryKey: ["purchases"] });
      onClose();
      onSaved?.(r.id);
    },
  });

  return (
    <Modal open={open} onClose={onClose} title={order ? `تعديل ${order.po_number}` : "أمر شراء جديد"} wide>
      <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); if (!issues.length && !save.isPending) save.mutate(); }}>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor="po-supplier" className="mb-1 block text-xs font-semibold text-muted">المورد</label>
            <Select id="po-supplier" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
              <option value="">— شراء نقدي بلا مورد —</option>
              {suppliers.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </div>
          <div>
            <label htmlFor="po-warehouse" className="mb-1 block text-xs font-semibold text-muted">يُستلم في</label>
            <Select id="po-warehouse" value={branch} onChange={(e) => setWarehouseId(e.target.value)}>
              {warehouses.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          </div>
          <div>
            <label htmlFor="po-notes" className="mb-1 block text-xs font-semibold text-muted">ملاحظات</label>
            <Input id="po-notes" maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        <ProductPicker showCost exclude={lines.map((l) => l.product_id)}
                       onPick={(p) => setLines((ls) => [...ls, { product_id: p.id, name: p.name, qty: "1", unit_cost: String(Number(p.cost_price ?? 0)) }])} />
        {!!lines.length && (
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="p-2 text-start">الصنف</th>
                  <th className="p-2 text-start">الكمية</th>
                  <th className="p-2 text-start">تكلفة الوحدة</th>
                  <th className="p-2 text-end">الإجمالي</th>
                  <th className="p-2"><span className="sr-only">حذف</span></th>
                </tr>
              </thead>
              <tbody>
                {lines.map((l, idx) => (
                  <tr key={l.product_id} className="border-b border-line/60 last:border-0">
                    <td className="p-2 font-semibold">{l.name}</td>
                    <td className="p-2">
                      <Input className="num w-24" inputMode="decimal" aria-label={`كمية ${l.name}`} value={l.qty}
                             onChange={(e) => setLines((ls) => ls.map((x, j) => (j === idx ? { ...x, qty: e.target.value } : x)))} />
                    </td>
                    <td className="p-2">
                      <Input className="num w-28" inputMode="decimal" aria-label={`تكلفة ${l.name}`} value={l.unit_cost}
                             onChange={(e) => setLines((ls) => ls.map((x, j) => (j === idx ? { ...x, unit_cost: e.target.value } : x)))} />
                    </td>
                    <td className="num p-2 text-end font-bold">{money(orderTotal([l]))}</td>
                    <td className="p-2">
                      <button type="button" className="rounded p-1 text-destructive hover:bg-elevated" aria-label={`حذف ${l.name}`}
                              onClick={() => setLines((ls) => ls.filter((_, j) => j !== idx))}>
                        <X className="size-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-line/60 pt-3">
          <span className="text-sm font-semibold text-muted">إجمالي الأمر (قبل الضريبة إن لم تكن التكلفة شاملة)</span>
          <span className="num text-xl font-black text-primary">{money(orderTotal(lines))} <span className="text-sm font-normal text-muted">ج.م</span></span>
        </div>
        {lines.length > 0 && issues.length > 0 && <p className="text-xs text-muted">غير صحيح: {issues.join("، ")}</p>}
        {save.isError && <ErrorBox message={(save.error as Error).message} />}
        <Button type="submit" className="h-11 w-full font-bold" disabled={!!issues.length || save.isPending}>
          {save.isPending ? <Spinner /> : order ? "حفظ التعديل" : "حفظ أمر الشراء (مسودة)"}
        </Button>
      </form>
    </Modal>
  );
}
