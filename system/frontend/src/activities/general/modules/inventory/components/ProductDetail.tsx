// One product's card (INV-9): its stock per branch, extra barcodes, picture, movement log and
// purchase prices, and stopping or bringing it back. Opened from the products screen.
import { useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Pencil, Power, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api, apiUrl } from "@/lib/api";
import { date as fmtDate, dateTime, money, qty as fq } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import type { MovementRow, Paged, ProductDetail as Product } from "../api";
import { imageSrc, movementLabel } from "../lib";

type Tab = "stock" | "barcodes" | "image" | "movements" | "prices";

export function ProductDetailModal({ productId, onClose, onEdit }: { productId: string | null; onClose: () => void; onEdit: (p: Product) => void }) {
  const can = useAuth((s) => s.can);
  const qc = useQueryClient();
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("stock");
  const [confirmStop, setConfirmStop] = useState(false);
  const product = useQuery({
    queryKey: ["product", productId],
    queryFn: () => api.get<Product>(`/products/${productId}`),
    enabled: !!productId,
  });
  const p = product.data;
  const setActive = useMutation({
    mutationFn: (active: boolean) => (active ? api.put(`/products/${productId}`, { is_active: true }) : api.del(`/products/${productId}`)),
    onSuccess: (_r, active) => {
      toast("success", active ? "أُعيد تفعيل الصنف" : "أُوقف الصنف");
      setConfirmStop(false);
      qc.invalidateQueries({ queryKey: ["product", productId] });
      qc.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (e) => { setConfirmStop(false); toast("error", (e as Error).message); },
  });
  const tabs: [Tab, string][] = [
    ["stock", "الرصيد بالفروع"], ["barcodes", "الباركودات"], ["image", "الصورة"], ["movements", "سجل الحركة"],
    ...(can("purchases|finance") ? [["prices", "أسعار الشراء"] as [Tab, string]] : []),
  ];

  return (
    <Modal open={!!productId} onClose={() => { setTab("stock"); onClose(); }} title={p ? p.name : "الصنف"} wide>
      {product.isLoading ? (
        <div className="flex flex-col gap-2"><Skeleton className="h-8 w-full" /><Skeleton className="h-40 w-full" /></div>
      ) : product.isError ? (
        <ErrorBox message={(product.error as Error).message} onRetry={() => product.refetch()} />
      ) : p ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              {p.code && <span className="code" dir="ltr">{p.code}</span>}
              {p.barcode && <span className="num" dir="ltr">{p.barcode}</span>}
              <span>سعر التجزئة <span className="num font-bold text-ink">{money(p.retail_price)}</span></span>
              {p.avg_cost != null && <span>متوسط التكلفة <span className="num font-bold text-ink">{money(p.avg_cost)}</span></span>}
              {p.is_active ? <Badge tone="success">نشط</Badge> : <Badge tone="danger">موقوف</Badge>}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => onEdit(p)}><Pencil className="size-4" /> تعديل</Button>
              <Button variant={p.is_active ? "ghost" : "outline"} size="sm" disabled={setActive.isPending}
                      onClick={() => (p.is_active ? setConfirmStop(true) : setActive.mutate(true))}>
                <Power className="size-4" /> {p.is_active ? "إيقاف" : "إعادة التفعيل"}
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap gap-1" role="tablist">
            {tabs.map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                      className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${tab === k ? "bg-elevated text-ink" : "text-muted hover:text-ink"}`}>
                {label}
              </button>
            ))}
          </div>
          {tab === "stock" && <StockByBranch productId={p.id} unit={p.unit} />}
          {tab === "barcodes" && <Barcodes product={p} />}
          {tab === "image" && <Picture product={p} />}
          {tab === "movements" && <Movements productId={p.id} />}
          {tab === "prices" && <PurchasePrices productId={p.id} />}
          <ConfirmDialog open={confirmStop} onClose={() => setConfirmStop(false)} onConfirm={() => setActive.mutate(false)}
                         title={`إيقاف «${p.name}»`}
                         message="يختفي الصنف من البيع والشراء والبحث، ويبقى سجله وأرصدته ومستنداته كما هي. يمكن إعادة تفعيله لاحقاً."
                         confirmLabel="إيقاف" />
        </div>
      ) : null}
    </Modal>
  );
}

function StockByBranch({ productId, unit }: { productId: string; unit: string }) {
  const rows = useQuery({
    queryKey: ["stock", "breakdown", productId],
    queryFn: () => api.get<{ warehouse_name: string; warehouse_type: string; qty: string }[]>(`/stock/balance/breakdown/${productId}`),
  });
  if (rows.isLoading) return <Skeleton className="h-24 w-full" />;
  if (rows.isError) return <ErrorBox message={(rows.error as Error).message} onRetry={() => rows.refetch()} />;
  if (!rows.data?.length) return <Empty text="لا توجد مخازن" />;
  return (
    <ul className="divide-y divide-line/60 rounded-xl border border-line">
      {rows.data.map((r) => (
        <li key={r.warehouse_name} className="flex justify-between px-3 py-2 text-sm">
          <span>{r.warehouse_name}</span>
          <span className="num font-bold">{fq(r.qty)} <span className="text-xs font-normal text-muted">{unit}</span></span>
        </li>
      ))}
    </ul>
  );
}

function Barcodes({ product }: { product: Product }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [code, setCode] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["product", product.id] });
  const add = useMutation({
    mutationFn: () => api.post(`/products/${product.id}/barcodes`, { barcode: code.trim() }),
    onSuccess: () => { toast("success", "أُضيف الباركود"); setCode(""); refresh(); },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.del(`/barcodes/${id}`),
    onSuccess: () => { toast("success", "حُذف الباركود"); refresh(); },
    onError: (e) => toast("error", (e as Error).message),
  });
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted">باركودات إضافية للصنف نفسه (عبوة أخرى، مورد آخر): القراءة بأي منها تجد الصنف. الباركود الرئيسي يُعدَّل من بيانات الصنف.</p>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (code.trim() && !add.isPending) add.mutate(); }}>
        <Input className="num" dir="ltr" maxLength={64} placeholder="امسح أو اكتب الباركود" value={code} onChange={(e) => setCode(e.target.value)}
               aria-label="باركود جديد" />
        <Button type="submit" disabled={!code.trim() || add.isPending}>{add.isPending ? <Spinner /> : "إضافة"}</Button>
      </form>
      {add.isError && <ErrorBox message={(add.error as Error).message} />}
      {!product.barcodes.length ? (
        <Empty text="لا توجد باركودات إضافية" />
      ) : (
        <ul className="divide-y divide-line/60 rounded-xl border border-line">
          {product.barcodes.map((b) => (
            <li key={b.id} className="flex items-center justify-between px-3 py-2 text-sm">
              <span className="num" dir="ltr">{b.barcode}</span>
              <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`حذف ${b.barcode}`} disabled={remove.isPending}
                      onClick={() => remove.mutate(b.id)}>
                <Trash2 className="size-4 text-destructive" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Picture({ product }: { product: Product }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const input = useRef<HTMLInputElement>(null);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["product", product.id] }); qc.invalidateQueries({ queryKey: ["products"] }); };
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.postForm(`/products/${product.id}/image`, form);
    },
    onSuccess: () => { toast("success", "حُفظت الصورة"); refresh(); },
  });
  const remove = useMutation({
    mutationFn: () => api.del(`/products/${product.id}/image`),
    onSuccess: () => { toast("success", "حُذفت الصورة"); refresh(); },
    onError: (e) => toast("error", (e as Error).message),
  });
  const src = imageSrc(product.image_url, apiUrl);
  return (
    <div className="flex flex-col items-center gap-3">
      {src ? (
        <img src={src} alt={product.name} className="max-h-56 rounded-xl border border-line object-contain" />
      ) : (
        <Empty text="لا توجد صورة" hint="تظهر الصورة في نقطة البيع. JPEG أو PNG أو WebP حتى 5 ميجابايت." />
      )}
      <input ref={input} type="file" accept="image/jpeg,image/png,image/gif,image/webp" className="hidden"
             onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
      <div className="flex gap-2">
        <Button variant="outline" disabled={upload.isPending} onClick={() => input.current?.click()}>
          {upload.isPending ? <Spinner /> : <><ImagePlus className="size-4" /> {src ? "تغيير الصورة" : "رفع صورة"}</>}
        </Button>
        {src && <Button variant="ghost" disabled={remove.isPending} onClick={() => remove.mutate()}><Trash2 className="size-4 text-destructive" /> حذف</Button>}
      </div>
      {upload.isError && <ErrorBox message={(upload.error as Error).message} />}
    </div>
  );
}

function Movements({ productId }: { productId: string }) {
  const [range, setRange] = useState({ from: "", to: "" });
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ["product-movements", productId, range, page],
    queryFn: () => api.get<Paged<MovementRow>>(`/products/${productId}/movements`, {
      from_date: range.from || undefined, to_date: range.to || undefined, page, page_size: 25,
    }),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="pm-from" className="mb-1 block text-xs font-medium text-muted">من تاريخ</label>
          <Input id="pm-from" type="date" className="w-40" value={range.from} onChange={(e) => { setRange({ ...range, from: e.target.value }); setPage(1); }} />
        </div>
        <div>
          <label htmlFor="pm-to" className="mb-1 block text-xs font-medium text-muted">إلى تاريخ</label>
          <Input id="pm-to" type="date" className="w-40" value={range.to} onChange={(e) => { setRange({ ...range, to: e.target.value }); setPage(1); }} />
        </div>
      </div>
      {list.isLoading ? <Skeleton className="h-32 w-full" />
        : list.isError ? <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
        : !list.data?.items.length ? <Empty text="لا توجد حركات" hint={range.from || range.to ? "غيّر الفترة" : undefined} />
        : (
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="p-2 text-start">التاريخ</th>
                  <th className="p-2 text-start">الحركة</th>
                  <th className="p-2 text-start">المخزن</th>
                  <th className="p-2 text-end">الكمية</th>
                  <th className="p-2 text-end">التكلفة</th>
                  <th className="p-2 text-start">البيان</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((m) => {
                  const meta = movementLabel(m.movement_type);
                  return (
                    <tr key={m.id} className="border-b border-line/60 last:border-0">
                      <td className="num p-2 text-xs text-muted">{dateTime(m.created_at)}</td>
                      <td className="p-2 text-xs">{meta.label}</td>
                      <td className="p-2 text-xs">{m.warehouse_name ?? "—"}</td>
                      <td className={`num p-2 text-end font-bold ${meta.inbound ? "text-success" : "text-destructive"}`} dir="ltr">
                        {meta.inbound ? "+" : "−"}{fq(m.qty)}
                      </td>
                      <td className="num p-2 text-end text-xs">{money(m.unit_cost)}</td>
                      <td className="max-w-56 truncate p-2 text-xs text-muted">{m.note || "—"}{m.created_by_name ? ` · ${m.created_by_name}` : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      {list.data && list.data.pages > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>السابق</Button>
          <span className="num text-muted">صفحة {page} من {list.data.pages}</span>
          <Button variant="outline" size="sm" disabled={page >= list.data.pages} onClick={() => setPage((p) => p + 1)}>التالي</Button>
        </div>
      )}
    </div>
  );
}

interface PriceRow { id: string; created_at: string; supplier_name: string | null; po_number: string | null; old_cost: string; new_cost: string }

export function PurchasePrices({ productId }: { productId: string }) {
  const rows = useQuery({
    queryKey: ["purchases", "price-history", productId],
    queryFn: () => api.get<PriceRow[]>(`/purchases/price-history/${productId}`),
  });
  if (rows.isLoading) return <Skeleton className="h-32 w-full" />;
  if (rows.isError) return <ErrorBox message={(rows.error as Error).message} onRetry={() => rows.refetch()} />;
  if (!rows.data?.length) return <Empty text="لم يُشترَ هذا الصنف بعد" hint="تُسجَّل تكلفة كل استلام لأمر شراء هنا." />;
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th className="p-2 text-start">التاريخ</th>
            <th className="p-2 text-start">أمر الشراء</th>
            <th className="p-2 text-start">المورد</th>
            <th className="p-2 text-end">التكلفة السابقة</th>
            <th className="p-2 text-end">تكلفة الشراء</th>
          </tr>
        </thead>
        <tbody>
          {rows.data.map((r) => {
            const up = Number(r.new_cost) > Number(r.old_cost);
            return (
              <tr key={r.id} className="border-b border-line/60 last:border-0">
                <td className="p-2 text-xs">{fmtDate(r.created_at)}</td>
                <td className="num p-2 text-xs" dir="ltr">{r.po_number ?? "—"}</td>
                <td className="p-2 text-xs">{r.supplier_name ?? "نقدي"}</td>
                <td className="num p-2 text-end text-xs text-muted">{money(r.old_cost)}</td>
                <td className={`num p-2 text-end font-bold ${up ? "text-destructive" : "text-success"}`}>{money(r.new_cost)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
