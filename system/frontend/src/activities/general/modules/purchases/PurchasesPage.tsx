import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackageCheck, Plus, Undo2, X } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { dateTime, D, money, moneyEGP } from "@/lib/format";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner } from "@/components/ui";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";
import { useAuth } from "@/stores/auth";

interface PO {
  id: string; po_number: string; supplier_name: string | null; status: string; amount_paid: string | null;
  total: string | null; created_at: string; notes: string | null;
}
interface Supplier { id: string; name: string }
interface Warehouse { id: string; name: string }
interface Product { id: string; name: string; code: string | null; cost_price: string }
interface LineItem { product: Product; qty: string; unit_cost: string }
interface Returnable { product_id: string; product_name: string | null; unit_cost: string; received: string; returned: string; returnable: string }
interface ReturnInfo { returns: { id: string; return_number: string; total: string; created_at: string }[]; returnable: Returnable[] }

export default function PurchasesPage() {
  const qc = useQueryClient();
  // Paying a supplier or taking a refund moves money in a safe or wallet: that needs "finance".
  const canPay = useAuth().can("finance");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<LineItem[]>([]);
  const [productSearch, setProductSearch] = useState("");
  const [receiving, setReceiving] = useState<PO | null>(null);
  const [paidNow, setPaidNow] = useState("");
  const [paySource, setPaySource] = useState("");
  const [returning, setReturning] = useState<PO | null>(null);
  const [retQty, setRetQty] = useState<Record<string, string>>({});
  const [refund, setRefund] = useState("");
  const [refundSource, setRefundSource] = useState("");

  const list = useQuery({
    queryKey: ["purchases", page],
    queryFn: async () => {
      const res = await api.get<{ items: PO[]; total: number; pages: number } | PO[]>("/purchases", { page, page_size: 25 });
      return Array.isArray(res) ? res : res.items ?? [];
    },
  });
  const suppliers = useQuery({
    queryKey: ["suppliers-list"],
    queryFn: async () => {
      const res = await api.get<{ items: Supplier[] } | Supplier[]>("/suppliers");
      return Array.isArray(res) ? res : res.items ?? [];
    },
  });
  const warehouses = useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<Warehouse[]>("/stock/warehouses") });
  const found = useQuery({
    queryKey: ["po-product-search", productSearch],
    queryFn: () => api.get<{ items: Product[] }>("/products", { search: productSearch, page: 1, page_size: 8 }),
    enabled: creating && productSearch.trim().length > 1,
  });

  const total = items.reduce((s, i) => s.plus(D(i.qty || "0").times(D(i.unit_cost || "0"))), D(0));

  const create = useMutation({
    mutationFn: () =>
      api.post("/purchases", {
        warehouse_id: warehouseId || warehouses.data?.[0]?.id,
        supplier_id: supplierId || null,
        notes: notes || null,
        items: items.map((i) => ({
          product_id: i.product.id,
          qty: D(i.qty || "0").toNumber(),
          unit_cost: D(i.unit_cost || "0").toNumber(),
        })).filter((i) => i.qty > 0),
      }),
    onSuccess: () => {
      setCreating(false);
      setItems([]); setNotes(""); setSupplierId(""); setProductSearch("");
      qc.invalidateQueries({ queryKey: ["purchases"] });
    },
  });

  const receive = useMutation({
    mutationFn: () =>
      api.post(`/purchases/${receiving!.id}/receive`, {
        items: [],
        amount_paid: canPay && paying ? Number(paidNow) : 0,
        ...(canPay && paying ? sourceFields(paySource) : {}),
      }),
    onSuccess: () => {
      setReceiving(null);
      setPaidNow("");
      setPaySource("");
      qc.invalidateQueries({ queryKey: ["purchases"] });
      qc.invalidateQueries({ queryKey: ["safes"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
      qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });
  const paying = canPay && Number.isFinite(Number(paidNow)) && Number(paidNow) > 0;

  const retInfo = useQuery({
    queryKey: ["purchase-returns", returning?.id],
    queryFn: () => api.get<ReturnInfo>(`/purchases/${returning!.id}/returns`),
    enabled: !!returning,
  });
  const retLines = (retInfo.data?.returnable ?? []).filter((r) => D(retQty[r.product_id] || "0").gt(0));
  const retTotal = retLines.reduce((s, r) => s.plus(D(retQty[r.product_id]).times(D(r.unit_cost))), D(0));
  const refunding = canPay && Number.isFinite(Number(refund)) && Number(refund) > 0;
  const closeReturn = () => { setReturning(null); setRetQty({}); setRefund(""); setRefundSource(""); };
  const doReturn = useMutation({
    mutationFn: () =>
      api.post(`/purchases/${returning!.id}/returns`, {
        items: retLines.map((r) => ({ product_id: r.product_id, qty: D(retQty[r.product_id]).toNumber() })),
        ...(refunding ? { refund_amount: Number(refund), ...sourceFields(refundSource) } : {}),
      }),
    onSuccess: () => {
      closeReturn();
      for (const key of ["purchases", "safes", "wallets", "suppliers", "stock"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">المشتريات</h1>
        <Button onClick={() => { setCreating(true); if (!warehouseId && warehouses.data?.[0]) setWarehouseId(warehouses.data[0].id); }}>
          <Plus size={16} /> أمر شراء جديد
        </Button>
      </div>

      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
            <Skeleton className="h-10 w-full" />
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <Empty text="لا توجد أوامر شراء" hint="أنشئ أول أمر شراء" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">المستند</th>
                <th className="p-3 text-start">المورد</th>
                <th className="p-3 text-start">الإجمالي</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="p-3 text-start">التاريخ</th>
                <th className="p-3 text-start"></th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((po) => (
                <tr key={po.id} className="border-b border-line/60 last:border-0 hover:bg-elevated">
                  <td className="num p-3 font-bold" dir="ltr">{po.po_number}</td>
                  <td className="p-3">{po.supplier_name ?? "—"}</td>
                  <td className="num p-3 font-bold">{po.total ? moneyEGP(po.total) : "—"}</td>
                  <td className="p-3">
                    <Badge tone={po.status === "received" ? "success" : po.status === "cancelled" ? "danger" : "brand"}>
                      {po.status === "received" ? "مستلم" : po.status === "cancelled" ? "ملغي" : po.status === "partial" ? "جزئي" : "مسودة"}
                    </Badge>
                  </td>
                  <td className="p-3 text-xs text-muted">{dateTime(po.created_at)}</td>
                  <td className="p-3">
                    {po.status !== "received" && po.status !== "cancelled" && (
                      <Button
                        variant="outline"
                        onClick={() => {
                          setReceiving(po);
                          setPaidNow(po.amount_paid && Number(po.amount_paid) > 0 ? po.amount_paid : "");
                        }}
                      >
                        <PackageCheck size={16} /> استلام
                      </Button>
                    )}
                    {po.status === "received" && (
                      <Button variant="outline" onClick={() => setReturning(po)}>
                        <Undo2 size={16} /> مرتجع للمورد
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}


      {list.data?.length === 25 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>السابق</Button>
          <span className="num text-muted">صفحة {page}</span>
          <Button variant="outline" onClick={() => setPage((p) => p + 1)}>التالي</Button>
        </div>
      )}

      <Modal open={!!receiving} onClose={() => setReceiving(null)} title={`استلام أمر الشراء ${receiving?.po_number ?? ""}`}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!receive.isPending && (!paying || paySource)) receive.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <p className="text-xs text-muted">
            {canPay
              ? "تدخل الكميات المخزن بتكلفة الأمر. ما يُدفع الآن يخرج من الخزنة أو المحفظة المختارة، والباقي يُضاف إلى رصيد المورد."
              : "تدخل الكميات المخزن بتكلفة الأمر، ويُضاف الإجمالي إلى رصيد المورد. الدفع للمورد يسجله من يملك صلاحية المالية."}
          </p>
          {canPay && (
            <div>
              <label htmlFor="po-paid" className="mb-1 block text-sm font-medium">المدفوع الآن (ج.م)</label>
              <Input id="po-paid" className="num font-bold" inputMode="decimal" placeholder="0.00" value={paidNow}
                     onChange={(e) => setPaidNow(e.target.value)} />
            </div>
          )}
          {paying && (
            <div>
              <label htmlFor="po-source" className="mb-1 block text-sm font-medium">دُفع من *</label>
              <PaySourceSelect id="po-source" value={paySource} onChange={setPaySource} />
            </div>
          )}
          {receive.isError && <ErrorBox message={(receive.error as Error).message} />}
          <Button type="submit" className="w-full h-11 font-bold" disabled={receive.isPending || (paying && !paySource)}>
            {receive.isPending ? <Spinner /> : "تأكيد الاستلام"}
          </Button>
        </form>
      </Modal>

      <Modal open={!!returning} onClose={closeReturn} title={`مرتجع مشتريات — ${returning?.po_number ?? ""}`}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!doReturn.isPending && retLines.length && (!refunding || refundSource)) doReturn.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <p className="text-xs text-muted">
            ترجع البضاعة للمورد بتكلفتها في أمر الشراء وتخرج من المخزن. تُخصم القيمة من رصيد المورد، أو تدخل الخزنة أو المحفظة إن استرددت المبلغ نقداً.
          </p>
          {retInfo.isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : retInfo.isError ? (
            <ErrorBox message={(retInfo.error as Error).message} onRetry={() => retInfo.refetch()} />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-line">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-muted">
                    <th className="p-2 text-start">المنتج</th>
                    <th className="p-2 text-start">المتاح للإرجاع</th>
                    <th className="p-2 text-start">تكلفة الوحدة</th>
                    <th className="p-2 text-start">الكمية المرتجعة</th>
                  </tr>
                </thead>
                <tbody>
                  {retInfo.data?.returnable.map((r) => (
                    <tr key={r.product_id} className="border-b border-line/60 last:border-0">
                      <td className="p-2 font-semibold">{r.product_name ?? "—"}</td>
                      <td className="num p-2">{D(r.returnable).toString()}</td>
                      <td className="num p-2">{money(r.unit_cost)}</td>
                      <td className="p-2">
                        <input className="num w-20 rounded-md border border-line bg-surface p-1.5 text-center" inputMode="decimal"
                          disabled={D(r.returnable).lte(0)} value={retQty[r.product_id] ?? ""} aria-label="الكمية المرتجعة"
                          onChange={(e) => setRetQty((q) => ({ ...q, [r.product_id]: e.target.value }))} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex items-center justify-between text-sm">
            <span className="font-semibold text-muted">قيمة المرتجع</span>
            <span className="num font-black">{moneyEGP(retTotal)}</span>
          </div>
          {canPay && (
            <div>
              <label htmlFor="ret-refund" className="mb-1 block text-sm font-medium">المسترد نقداً من المورد (ج.م) — اختياري</label>
              <Input id="ret-refund" className="num font-bold" inputMode="decimal" placeholder="0.00" value={refund}
                     onChange={(e) => setRefund(e.target.value)} />
            </div>
          )}
          {refunding && (
            <div>
              <label htmlFor="ret-source" className="mb-1 block text-sm font-medium">استُلم في *</label>
              <PaySourceSelect id="ret-source" value={refundSource} onChange={setRefundSource} />
            </div>
          )}
          {doReturn.isError && <ErrorBox message={(doReturn.error as Error).message} />}
          <Button type="submit" className="w-full h-11 font-bold"
                  disabled={doReturn.isPending || !retLines.length || (refunding && !refundSource)}>
            {doReturn.isPending ? <Spinner /> : "تأكيد المرتجع"}
          </Button>
        </form>
      </Modal>

      <Modal open={creating} onClose={() => setCreating(false)} title="أمر شراء جديد" wide>
        <div className="flex flex-col gap-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-medium">المورد</label>
              <Select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                <option value="">— نقدي —</option>
                {suppliers.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">المخزن</label>
              <Select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                {warehouses.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">ملاحظات</label>
              <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">إضافة منتج</label>
            <Input placeholder="ابحث بالاسم…" value={productSearch} onChange={(e) => setProductSearch(e.target.value)} />
            {!!found.data?.items.length && (
              <div className="mt-2 grid gap-1 rounded-lg border border-line p-2">
                {found.data.items.map((p) => (
                  <button
                    key={p.id}
                    className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-elevated"
                    onClick={() => {
                      setItems((it) => [...it, { product: p, qty: "1", unit_cost: p.cost_price }]);
                      setProductSearch("");
                    }}
                  >
                    <span className="font-semibold">{p.name}</span>
                    <span className="num text-xs text-muted">{money(p.cost_price)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {!!items.length && (
            <div className="overflow-x-auto rounded-xl border border-line">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-muted">
                    <th className="p-2 text-start">المنتج</th>
                    <th className="p-2 text-start">الكمية</th>
                    <th className="p-2 text-start">تكلفة الوحدة</th>
                    <th className="p-2 text-start">الإجمالي</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, idx) => (
                    <tr key={it.product.id} className="border-b border-line/60 last:border-0">
                      <td className="p-2 font-semibold">{it.product.name}</td>
                      <td className="p-2">
                        <input className="num w-20 rounded-md border border-line bg-surface p-1.5 text-center" inputMode="decimal"
                          value={it.qty} onChange={(e) => setItems((arr) => arr.map((x, j) => j === idx ? { ...x, qty: e.target.value } : x))} aria-label="الكمية" />
                      </td>
                      <td className="p-2">
                        <input className="num w-24 rounded-md border border-line bg-surface p-1.5 text-center" inputMode="decimal"
                          value={it.unit_cost} onChange={(e) => setItems((arr) => arr.map((x, j) => j === idx ? { ...x, unit_cost: e.target.value } : x))} aria-label="التكلفة" />
                      </td>
                      <td className="num p-2 font-bold">{money(D(it.qty || "0").times(D(it.unit_cost || "0")))}</td>
                      <td className="p-2">
                        <button className="rounded p-1 text-danger hover:bg-elevated" onClick={() => setItems((arr) => arr.filter((_, j) => j !== idx))} aria-label="حذف">
                          <X size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex items-center justify-between border-t border-border/60 pt-3">
            <span className="text-sm font-semibold text-muted-foreground">الإجمالي الكلي لأمر الشراء</span>
            <span className="num text-xl font-black text-primary">{money(total)} <span className="text-sm font-sans font-normal text-muted-foreground">ج.م</span></span>
          </div>

          {create.isError && <ErrorBox message={(create.error as Error).message} />}
          <Button className="w-full h-11 font-bold text-sm shadow-md" disabled={create.isPending || !items.length} onClick={() => create.mutate()}>
            {create.isPending ? <Spinner /> : "حفظ أمر الشراء"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
