// Collections (INV-9): a named set of products with its own price (a gift box, a combo), and how
// many can be assembled from a branch's stock. Nothing sells a collection yet: the till and the sales
// invoice sell products only (README, known limits), so this screen says so.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info, Layers, Pencil, Plus, Trash2, X } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, money, qty as fq } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { type Collection, type Paged, type ProductRow, useWarehouses } from "../api";
import { InventoryHeader } from "../components/InventoryHeader";
import { ProductPicker } from "../components/ProductPicker";
import { componentsValue, parseNumber } from "../lib";

interface Line { product_id: string; name: string; qty: string }
/** What the availability route answers when no item's stock is tracked (nothing limits the count). */
const UNTRACKED = 999;
interface Form { id?: string; name: string; description: string; retail_price: string; wholesale_price: string; items: Line[] }

export default function CollectionsPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const manage = useAuth((s) => s.can)("inventory");
  const warehouses = useWarehouses();
  const [wid, setWid] = useState("");
  const branch = wid || warehouses.data?.[0]?.id || "";
  const list = useQuery({ queryKey: ["collections"], queryFn: () => api.get<Paged<Collection>>("/collections", { page_size: 200 }) });
  const [form, setForm] = useState<Form | null>(null);
  const [deleting, setDeleting] = useState<Collection | null>(null);

  const formIssues = !form ? [] : [
    !form.name.trim() && "الاسم",
    parseNumber(form.retail_price, 2) === null && "سعر البيع",
    form.wholesale_price.trim() && parseNumber(form.wholesale_price, 2) === null && "سعر الجملة",
    !form.items.length && "صنف واحد على الأقل",
    form.items.some((i) => !parseNumber(i.qty)?.gt(0)) && "كميات الأصناف",
  ].filter(Boolean) as string[];

  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = {
        name: f.name.trim(), description: f.description.trim(),
        retail_price: parseNumber(f.retail_price, 2)!.toString(),
        wholesale_price: (parseNumber(f.wholesale_price, 2) ?? D(0)).toString(),
        items: f.items.map((i) => ({ product_id: i.product_id, qty: parseNumber(i.qty)!.toString() })),
      };
      return f.id ? api.put(`/collections/${f.id}`, body) : api.post("/collections", body);
    },
    onSuccess: (_r, f) => { toast("success", f.id ? "حُفظت المجموعة" : "أُضيفت المجموعة"); setForm(null); qc.invalidateQueries({ queryKey: ["collections"] }); },
  });
  const remove = useMutation({
    mutationFn: (c: Collection) => api.del(`/collections/${c.id}`),
    onSuccess: () => { toast("success", "حُذفت المجموعة"); setDeleting(null); qc.invalidateQueries({ queryKey: ["collections"] }); },
    onError: (e) => { setDeleting(null); toast("error", (e as Error).message); },
  });

  const openNew = () => setForm({ name: "", description: "", retail_price: "", wholesale_price: "", items: [] });
  const openEdit = (c: Collection) => setForm({
    id: c.id, name: c.name, description: c.description ?? "", retail_price: String(c.retail_price), wholesale_price: String(c.wholesale_price),
    items: (c.items ?? []).map((i) => ({ product_id: i.product_id, name: i.product_name ?? "", qty: String(D(i.qty)) })),
  });
  const addProduct = (p: ProductRow) => form && setForm({ ...form, items: [...form.items, { product_id: p.id, name: p.name, qty: "1" }] });

  return (
    <div className="flex flex-col gap-6">
      <InventoryHeader
        title="المجموعات"
        subtitle="عبوات أو عروض من عدة أصناف بسعر واحد، وكم منها يمكن تجميعه من رصيد الفرع"
        actions={manage && <Button onClick={openNew}><Plus className="size-4" /> مجموعة جديدة</Button>}
      />
      <div className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3 text-xs">
        <Info className="mt-0.5 size-4 shrink-0" />
        <span>المجموعات للتسعير ومتابعة ما يمكن تجميعه فقط: نقطة البيع وفاتورة البيع تبيعان الأصناف منفردة، فأضف أصناف المجموعة إلى الفاتورة عند بيعها.</span>
      </div>
      <div className="flex items-center gap-2">
        <label htmlFor="col-branch" className="text-xs font-semibold text-muted">المتاح في</label>
        <Select id="col-branch" className="w-52" value={branch} onChange={(e) => setWid(e.target.value)}>
          {(warehouses.data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </Select>
      </div>

      {list.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-40 w-full rounded-2xl" />)}</div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.items.length ? (
        <Empty text="لا توجد مجموعات" hint="أنشئ مجموعة (مثل «كرتونة رمضان») من أصناف موجودة وحدد سعرها."
               icon={<Layers className="size-10" />} action={manage && <Button onClick={openNew}><Plus className="size-4" /> مجموعة جديدة</Button>} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {list.data.items.map((c) => (
            <CollectionCard key={c.id} c={c} warehouseId={branch} manage={manage} onEdit={() => openEdit(c)} onDelete={() => setDeleting(c)} />
          ))}
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "تعديل المجموعة" : "مجموعة جديدة"} wide>
        {form && (
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!formIssues.length && !save.isPending) save.mutate(form); }}>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-3">
                <label htmlFor="col-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
                <Input id="col-name" autoFocus maxLength={128} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div>
                <label htmlFor="col-retail" className="mb-1 block text-xs font-semibold text-muted">سعر البيع *</label>
                <Input id="col-retail" className="num" inputMode="decimal" value={form.retail_price} onChange={(e) => setForm({ ...form, retail_price: e.target.value })} />
              </div>
              <div>
                <label htmlFor="col-wholesale" className="mb-1 block text-xs font-semibold text-muted">سعر الجملة</label>
                <Input id="col-wholesale" className="num" inputMode="decimal" value={form.wholesale_price} onChange={(e) => setForm({ ...form, wholesale_price: e.target.value })} />
              </div>
              <div>
                <label htmlFor="col-desc" className="mb-1 block text-xs font-semibold text-muted">وصف</label>
                <Input id="col-desc" maxLength={2000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
            </div>
            <ProductPicker onPick={addProduct} exclude={form.items.map((i) => i.product_id)} />
            {!!form.items.length && (
              <ul className="divide-y divide-line/60 rounded-xl border border-line">
                {form.items.map((i, idx) => (
                  <li key={i.product_id} className="flex items-center gap-2 px-3 py-2 text-sm">
                    <span className="min-w-0 flex-1 truncate font-semibold">{i.name}</span>
                    <Input className="num w-24" inputMode="decimal" aria-label={`كمية ${i.name}`} value={i.qty}
                           onChange={(e) => setForm({ ...form, items: form.items.map((x, j) => (j === idx ? { ...x, qty: e.target.value } : x)) })} />
                    <button type="button" className="rounded p-1 text-destructive hover:bg-elevated" aria-label={`حذف ${i.name}`}
                            onClick={() => setForm({ ...form, items: form.items.filter((_, j) => j !== idx) })}>
                      <X className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {formIssues.length > 0 && <p className="text-xs text-muted">ناقص أو غير صحيح: {formIssues.join("، ")}</p>}
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="h-10 w-full font-bold" disabled={!!formIssues.length || save.isPending}>
              {save.isPending ? <Spinner /> : "حفظ المجموعة"}
            </Button>
          </form>
        )}
      </Modal>

      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting)}
                     title={deleting ? `حذف «${deleting.name}»` : ""} message="تُحذف المجموعة من القائمة؛ الأصناف وأرصدتها لا تتأثر."
                     confirmLabel="حذف" />
    </div>
  );
}

function CollectionCard({ c, warehouseId, manage, onEdit, onDelete }: {
  c: Collection; warehouseId: string; manage: boolean; onEdit: () => void; onDelete: () => void;
}) {
  const avail = useQuery({
    queryKey: ["collections", "availability", c.id, warehouseId],
    queryFn: () => api.get<{ can_make: number }>(`/collections/${c.id}/availability`, { warehouse_id: warehouseId }),
    enabled: !!warehouseId,
  });
  const parts = componentsValue(c.items);
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="truncate text-base font-bold">{c.name}</h2>
          {c.description && <p className="truncate text-xs text-muted">{c.description}</p>}
        </div>
        {manage && (
          <div className="flex shrink-0 gap-1">
            <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل ${c.name}`} onClick={onEdit}><Pencil className="size-4" /></Button>
            <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`حذف ${c.name}`} onClick={onDelete}><Trash2 className="size-4 text-destructive" /></Button>
          </div>
        )}
      </div>
      <ul className="flex flex-col gap-1 text-xs">
        {(c.items ?? []).map((i) => (
          <li key={i.product_id} className="flex justify-between gap-2"><span className="truncate">{i.product_name}</span><span className="num shrink-0">× {fq(i.qty)}</span></li>
        ))}
      </ul>
      <div className="mt-auto flex items-end justify-between gap-2 border-t border-line/60 pt-3">
        <div>
          <p className="num text-lg font-black text-primary">{money(c.retail_price)} <span className="text-xs font-normal text-muted">ج.م</span></p>
          <p className="text-[11px] text-muted">منفردة: <span className="num">{money(parts)}</span></p>
        </div>
        {avail.isLoading ? <Skeleton className="h-6 w-20" /> : avail.isError ? <Badge tone="danger">تعذر حساب المتاح</Badge>
          : (avail.data?.can_make ?? 0) >= UNTRACKED ? <Badge tone="muted">أصنافها لا يُتتبع رصيدها</Badge>
          : <Badge tone={avail.data && avail.data.can_make > 0 ? "success" : "warning"}>يمكن تجميع <span className="num">{avail.data?.can_make ?? 0}</span></Badge>}
      </div>
    </section>
  );
}
