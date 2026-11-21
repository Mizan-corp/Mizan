// Editing a draft or a quotation (nothing taken or paid yet): its customer, lines, discounts and
// notes. Lines are priced by the server at the product's price now, unless the user may sell at
// another price (the POS setting and sales:override_price), who then types it.
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { moneyEGP } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Button, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { usePosSettings } from "@activities/general/modules/pos/api";
import { canOverridePrice, listedPrice } from "@activities/general/modules/pos/lib";
import type { SaleDetail } from "../api";
import { editBody, editTotal, type EditLine, lineIssue } from "../lib";

interface Customer { id: string; name: string }
interface Product { id: string; name: string; retail_price: string; wholesale_price: string; unit?: string }

export function EditDocumentModal({ docId, onClose }: { docId: string | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const can = useAuth((s) => s.can);
  const override = canOverridePrice(usePosSettings(), can);
  const [lines, setLines] = useState<EditLine[]>([]);
  const [discount, setDiscount] = useState("0");
  const [notes, setNotes] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [find, setFind] = useState("");

  const doc = useQuery({
    queryKey: ["sale", docId],
    queryFn: () => api.get<SaleDetail>(`/sales/${docId}`),
    enabled: !!docId,
    // A refetch would reset the form being edited.
    refetchOnWindowFocus: false,
  });
  const customers = useQuery({
    queryKey: ["customers", "picker"],
    queryFn: () => api.get<Customer[]>("/customers", { limit: 1000 }),
    enabled: !!docId,
  });
  const products = useQuery({
    queryKey: ["products", "picker", find],
    queryFn: () => api.get<{ items: Product[] }>("/products", { search: find, page_size: 8 }),
    enabled: !!docId && find.trim().length > 0,
  });

  const d = doc.data;
  useEffect(() => {
    if (!d) return;
    setLines((d.items ?? []).map((i) => ({
      product_id: i.product_id, product_name: i.product_name, qty: String(Number(i.qty)),
      unit_price: String(Number(i.unit_price)), discount: String(Number(i.discount ?? 0)),
    })));
    setDiscount(String(Number(d.discount_amount ?? 0)));
    setNotes(d.notes ?? "");
    setCustomerId(d.customer_id ?? "");
    setFind("");
  }, [d]);

  const save = useMutation({
    mutationFn: () => api.put(`/sales/${docId}`, editBody({ lines, discount, notes, customer_id: customerId }, override)),
    onSuccess: () => {
      toast("success", "حُفظت التعديلات");
      for (const key of ["sales", "sale", "sales-summary"]) qc.invalidateQueries({ queryKey: [key] });
      onClose();
    },
  });

  const mode = d?.sale_mode === "wholesale" ? "wholesale" : "retail";
  const issue = lines.length ? lines.map(lineIssue).find(Boolean) ?? null : "أضف صنفاً واحداً على الأقل";
  const set = (i: number, patch: Partial<EditLine>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const add = (p: Product) => {
    setLines((ls) => ls.some((l) => l.product_id === p.id)
      ? ls.map((l) => (l.product_id === p.id ? { ...l, qty: String(Number(l.qty) + 1) } : l))
      : [...ls, { product_id: p.id, product_name: p.name, qty: "1", unit_price: listedPrice(p, mode).toString(), discount: "0" }]);
    setFind("");
  };
  const kind = d?.status === "quotation" ? "عرض السعر" : "المسودة";

  return (
    <Modal open={!!docId} onClose={onClose} title={`تعديل ${kind} ${d?.invoice_number ?? ""}`} wide>
      {doc.isLoading ? (
        <div className="flex flex-col gap-2"><Skeleton className="h-10 w-full" /><Skeleton className="h-32 w-full" /></div>
      ) : doc.isError ? (
        <ErrorBox message={(doc.error as Error).message} onRetry={() => doc.refetch()} />
      ) : d && (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!save.isPending && !issue) save.mutate();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="edit-customer" className="mb-1 block text-xs font-semibold text-muted-foreground">العميل</label>
              <Select id="edit-customer" value={customerId} onChange={(e) => setCustomerId(e.target.value)} disabled={customers.isLoading}>
                <option value="">عميل نقدي</option>
                {d.customer_id && !customers.data?.some((c) => c.id === d.customer_id) && (
                  <option value={d.customer_id}>{d.customer_name ?? "العميل الحالي"}</option>
                )}
                {customers.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </div>
            <div>
              <label htmlFor="edit-find" className="mb-1 block text-xs font-semibold text-muted-foreground">إضافة صنف</label>
              <div className="relative">
                <Search className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input id="edit-find" className="ps-8" placeholder="اسم الصنف أو الباركود" value={find} onChange={(e) => setFind(e.target.value)} />
                {find.trim() && (
                  <div className="absolute inset-x-0 top-full z-10 mt-1 max-h-56 overflow-y-auto rounded-lg border border-line bg-card shadow-lg">
                    {products.isLoading ? (
                      <p className="p-3 text-xs text-muted-foreground">جارٍ البحث…</p>
                    ) : products.isError ? (
                      <p className="p-3 text-xs text-destructive-ink">{(products.error as Error).message}</p>
                    ) : !products.data?.items.length ? (
                      <p className="p-3 text-xs text-muted-foreground">لا توجد أصناف مطابقة</p>
                    ) : products.data.items.map((p) => (
                      <button key={p.id} type="button" onClick={() => add(p)}
                              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-start text-sm hover:bg-muted/60">
                        <span className="truncate">{p.name}</span>
                        <span className="num shrink-0 text-xs text-muted-foreground">{moneyEGP(listedPrice(p, mode))}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-muted/40 text-xs text-muted-foreground">
                  <th className="p-2 text-start">الصنف</th>
                  <th className="p-2 text-start">الكمية</th>
                  <th className="p-2 text-start">السعر</th>
                  <th className="p-2 text-start">خصم البند</th>
                  <th className="p-2" />
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={l.product_id} className="border-b border-line/60 last:border-0">
                    <td className="max-w-48 truncate p-2">{l.product_name}</td>
                    <td className="p-2">
                      <Input className="num h-8 w-20" inputMode="decimal" aria-label={`كمية ${l.product_name}`} value={l.qty}
                             onChange={(e) => set(i, { qty: e.target.value })} />
                    </td>
                    <td className="p-2">
                      {override ? (
                        <Input className="num h-8 w-24" inputMode="decimal" aria-label={`سعر ${l.product_name}`} value={l.unit_price}
                               onChange={(e) => set(i, { unit_price: e.target.value })} />
                      ) : (
                        <span className="num text-xs">{moneyEGP(l.unit_price)}</span>
                      )}
                    </td>
                    <td className="p-2">
                      <Input className="num h-8 w-20" inputMode="decimal" aria-label={`خصم ${l.product_name}`} value={l.discount}
                             onChange={(e) => set(i, { discount: e.target.value })} />
                    </td>
                    <td className="p-2 text-end">
                      <Button type="button" variant="ghost" size="sm" aria-label={`حذف ${l.product_name}`}
                              onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}>
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </td>
                  </tr>
                ))}
                {!lines.length && (
                  <tr><td colSpan={5} className="p-4 text-center text-xs text-muted-foreground"><Plus className="me-1 inline size-3.5" />ابحث عن صنف لإضافته</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {!override && (
            <p className="text-[11px] text-muted-foreground">تُسعَّر الأصناف عند الحفظ بسعرها الحالي في بطاقة الصنف.</p>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="edit-discount" className="mb-1 block text-xs font-semibold text-muted-foreground">خصم على الفاتورة</label>
              <Input id="edit-discount" className="num" inputMode="decimal" value={discount} onChange={(e) => setDiscount(e.target.value)} />
            </div>
            <div>
              <label htmlFor="edit-notes" className="mb-1 block text-xs font-semibold text-muted-foreground">ملاحظات</label>
              <Input id="edit-notes" maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center justify-between rounded-xl border border-line bg-secondary/30 p-3 text-sm">
            <span className="text-muted-foreground">الإجمالي التقديري (تُحسب الضريبة عند الحفظ)</span>
            <span className="num font-bold">{moneyEGP(editTotal(lines, discount))}</span>
          </div>
          {issue && lines.length > 0 && <p className="text-xs text-destructive-ink">{issue}</p>}
          {save.isError && <ErrorBox message={(save.error as Error).message} />}
          <div className="flex gap-2">
            <Button type="submit" className="h-10 flex-1 font-bold" disabled={save.isPending || !!issue}>
              {save.isPending ? <Spinner /> : "حفظ التعديلات"}
            </Button>
            <Button type="button" variant="ghost" className="h-10 flex-1" onClick={onClose}>إلغاء</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
