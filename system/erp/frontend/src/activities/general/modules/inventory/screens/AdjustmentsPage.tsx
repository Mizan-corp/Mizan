// Stock entered by hand (INV-9): adjustments after a count, damage (with its reason), opening stock
// (its own permission), and transfers between two branches. Adjustments and damage post to the
// ledger (stock.adjusted); purchases, sales and returns only come from their documents.
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, ClipboardEdit, X } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { dateTime, qty as fq } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { useBranch } from "@app/components/AppShell";
import { Button, Card, Empty, ErrorBox, Input, Select, Spinner, useToast } from "@/components/ui";
import { type MovementRow, type Paged, type ProductRow, useWarehouses } from "../api";
import { InventoryHeader } from "../components/InventoryHeader";
import { ProductPicker } from "../components/ProductPicker";
import { HAND_MOVEMENTS, type HandMovement, handMovementIssues, movementLabel, parseNumber } from "../lib";

const PAGE = 20;

function useAvailable(productId: string | undefined, warehouseId: string) {
  return useQuery({
    queryKey: ["stock", "available", productId, warehouseId],
    queryFn: () => api.post<Record<string, number>>(`/stock/balance/bulk?warehouse_id=${warehouseId}`, [productId]),
    enabled: !!productId && !!warehouseId,
  });
}

function PickedProduct({ product, onClear, available }: { product: ProductRow; onClear: () => void; available?: number }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-line bg-elevated/40 px-3 py-2 text-sm">
      <span className="min-w-0 truncate font-semibold">{product.name}</span>
      <span className="flex shrink-0 items-center gap-2 text-xs text-muted">
        {available !== undefined && <>المتاح <span className="num font-bold text-ink">{fq(available)}</span> {product.unit}</>}
        <button type="button" className="rounded p-1 hover:bg-elevated" onClick={onClear} aria-label="تغيير الصنف"><X className="size-3.5" /></button>
      </span>
    </div>
  );
}

export default function AdjustmentsPage() {
  const can = useAuth((s) => s.can);
  const warehouses = useWarehouses();
  const { branchId } = useBranch();
  const [wid, setWid] = useState("");
  const branch = wid || branchId || warehouses.data?.[0]?.id || "";
  return (
    <div className="flex flex-col gap-6">
      <InventoryHeader title="التسويات والتحويلات" subtitle="تسوية الجرد والتالف والرصيد الافتتاحي يدوياً بسبب مكتوب، ونقل البضاعة بين الفروع" />
      {warehouses.isError ? (
        <ErrorBox message={(warehouses.error as Error).message} onRetry={() => warehouses.refetch()} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <AdjustmentForm canOpening={can("inventory:opening")} />
          <TransferForm />
        </div>
      )}
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-bold">آخر حركات المخزن</h2>
          <Select className="w-52" value={branch} onChange={(e) => setWid(e.target.value)} aria-label="المخزن">
            {(warehouses.data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        </div>
        <RecentMovements warehouseId={branch} />
      </section>
    </div>
  );
}

function AdjustmentForm({ canOpening }: { canOpening: boolean }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const warehouses = useWarehouses();
  const empty = { type: "adjustment_out" as HandMovement, warehouse_id: "", qty: "", unit_cost: "", note: "", batch: "", expiry: "" };
  const [f, setF] = useState(empty);
  const [product, setProduct] = useState<ProductRow | null>(null);
  const { branchId } = useBranch();
  const warehouseId = f.warehouse_id || branchId || warehouses.data?.[0]?.id || "";
  const available = useAvailable(product?.id, warehouseId);
  const inbound = f.type === "adjustment_in" || f.type === "opening_stock";
  const types = HAND_MOVEMENTS.filter((m) => m.type !== "opening_stock" || canOpening);
  const issues = handMovementIssues({ type: f.type, product_id: product?.id ?? "", warehouse_id: warehouseId, qty: f.qty, unit_cost: f.unit_cost, note: f.note });

  const send = useMutation({
    mutationFn: () => api.post("/stock/movements", {
      product_id: product!.id,
      warehouse_id: warehouseId,
      movement_type: f.type,
      qty: parseNumber(f.qty)!.toString(),
      unit_cost: inbound && f.unit_cost.trim() ? parseNumber(f.unit_cost, 2)!.toString() : "0",
      note: f.note.trim() || null,
      batch_number: inbound && f.batch.trim() ? f.batch.trim() : null,
      expiry_date: inbound && f.expiry ? f.expiry : null,
    }),
    onSuccess: () => {
      toast("success", "سُجّلت الحركة");
      setF({ ...empty, type: f.type, warehouse_id: f.warehouse_id });
      setProduct(null);
      for (const k of ["stock", "movements-ledger", "inventory-ledger-balances", "valuation", "low-stock-count"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });

  return (
    <Card className="flex flex-col gap-4">
      <p className="flex items-center gap-2 font-bold"><ClipboardEdit className="size-5" /> تسوية أو تالف</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="adj-type" className="mb-1 block text-xs font-semibold text-muted">نوع الحركة</label>
          <Select id="adj-type" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value as HandMovement })}>
            {types.map((m) => <option key={m.type} value={m.type}>{m.label}</option>)}
          </Select>
        </div>
        <div>
          <label htmlFor="adj-wh" className="mb-1 block text-xs font-semibold text-muted">المخزن</label>
          <Select id="adj-wh" value={warehouseId} onChange={(e) => setF({ ...f, warehouse_id: e.target.value })}>
            {(warehouses.data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        </div>
      </div>
      <p className="text-[11px] text-muted">{HAND_MOVEMENTS.find((m) => m.type === f.type)?.hint}</p>
      {product
        ? <PickedProduct product={product} onClear={() => setProduct(null)} available={available.data ? Number(available.data[product.id] ?? 0) : undefined} />
        : <ProductPicker id="adj-product" onPick={setProduct} />}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="adj-qty" className="mb-1 block text-xs font-semibold text-muted">الكمية *</label>
          <Input id="adj-qty" className="num" inputMode="decimal" value={f.qty} onChange={(e) => setF({ ...f, qty: e.target.value })} />
        </div>
        {inbound && (
          <div>
            <label htmlFor="adj-cost" className="mb-1 block text-xs font-semibold text-muted">تكلفة الوحدة (فارغة: متوسط التكلفة)</label>
            <Input id="adj-cost" className="num" inputMode="decimal" value={f.unit_cost} onChange={(e) => setF({ ...f, unit_cost: e.target.value })} />
          </div>
        )}
        {inbound && (
          <>
            <div>
              <label htmlFor="adj-batch" className="mb-1 block text-xs font-semibold text-muted">رقم التشغيلة (اختياري)</label>
              <Input id="adj-batch" className="code" dir="ltr" maxLength={64} value={f.batch} onChange={(e) => setF({ ...f, batch: e.target.value })} />
            </div>
            <div>
              <label htmlFor="adj-expiry" className="mb-1 block text-xs font-semibold text-muted">تاريخ الصلاحية</label>
              <Input id="adj-expiry" type="date" value={f.expiry} onChange={(e) => setF({ ...f, expiry: e.target.value })} />
            </div>
          </>
        )}
      </div>
      <div>
        <label htmlFor="adj-note" className="mb-1 block text-xs font-semibold text-muted">
          السبب {f.type === "damage" || f.type === "adjustment_out" ? "*" : "(اختياري)"}
        </label>
        <Input id="adj-note" maxLength={1000} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })}
               placeholder={f.type === "damage" ? "مثال: كسر أثناء النقل" : "مثال: فرق جرد نهاية الشهر"} />
      </div>
      {send.isError && <ErrorBox message={(send.error as Error).message} />}
      {issues.length > 0 && (f.qty || product) && <p className="text-xs text-muted">ناقص: {issues.join("، ")}</p>}
      <Button className="h-10 w-full font-bold" disabled={issues.length > 0 || send.isPending} onClick={() => send.mutate()}>
        {send.isPending ? <Spinner /> : "تسجيل الحركة"}
      </Button>
    </Card>
  );
}

function TransferForm() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const warehouses = useWarehouses();
  const list = warehouses.data ?? [];
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [qtyText, setQty] = useState("");
  const [note, setNote] = useState("");
  const [product, setProduct] = useState<ProductRow | null>(null);
  const { branchId } = useBranch();
  const source = from || branchId || list[0]?.id || "";
  const target = to || list.find((w) => w.id !== source)?.id || "";
  const available = useAvailable(product?.id, source);
  const q = parseNumber(qtyText);
  const same = !!source && source === target;
  const ready = !!product && !!q && q.gt(0) && !same && !!target;

  const send = useMutation({
    mutationFn: () => api.post<{ detail: string }>("/stock/transfer", {
      product_id: product!.id, from_warehouse_id: source, to_warehouse_id: target, qty: q!.toString(), note: note.trim() || null,
    }),
    onSuccess: () => {
      toast("success", "تم التحويل");
      setQty(""); setNote(""); setProduct(null);
      for (const k of ["stock", "movements-ledger", "inventory-ledger-balances", "valuation"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });

  return (
    <Card className="flex flex-col gap-4">
      <p className="flex items-center gap-2 font-bold"><ArrowLeftRight className="size-5" /> تحويل بين الفروع</p>
      {list.length < 2 ? (
        <Empty text="يلزم فرعان على الأقل" hint="أضف مخزناً أو فرعاً آخر من «المخازن والفروع» لتنقل البضاعة بينهما." />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="tr-from" className="mb-1 block text-xs font-semibold text-muted">من</label>
              <Select id="tr-from" value={source} onChange={(e) => setFrom(e.target.value)}>
                {list.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </div>
            <div>
              <label htmlFor="tr-to" className="mb-1 block text-xs font-semibold text-muted">إلى</label>
              <Select id="tr-to" value={target} onChange={(e) => setTo(e.target.value)}>
                {list.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </div>
          </div>
          {same && <p className="text-xs text-destructive">اختر مخزناً آخر للوجهة.</p>}
          {product
            ? <PickedProduct product={product} onClear={() => setProduct(null)} available={available.data ? Number(available.data[product.id] ?? 0) : undefined} />
            : <ProductPicker id="tr-product" onPick={setProduct} />}
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="tr-qty" className="mb-1 block text-xs font-semibold text-muted">الكمية *</label>
              <Input id="tr-qty" className="num" inputMode="decimal" value={qtyText} onChange={(e) => setQty(e.target.value)} />
            </div>
            <div>
              <label htmlFor="tr-note" className="mb-1 block text-xs font-semibold text-muted">ملاحظة</label>
              <Input id="tr-note" maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
          </div>
          <p className="text-[11px] text-muted">التحويل لا يغيّر قيمة المخزون في الدفاتر؛ للتحويل بمستند مرقّم استخدم «إذن صرف» في العمليات المخزنية.</p>
          {send.isError && <ErrorBox message={(send.error as Error).message} />}
          <Button className="h-10 w-full font-bold" disabled={!ready || send.isPending} onClick={() => send.mutate()}>
            {send.isPending ? <Spinner /> : "تحويل"}
          </Button>
        </>
      )}
    </Card>
  );
}

function RecentMovements({ warehouseId }: { warehouseId: string }) {
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ["movements-ledger", "recent", warehouseId, page],
    queryFn: () => api.get<Paged<MovementRow>>("/stock/movements", { warehouse_id: warehouseId, page, page_size: PAGE }),
    enabled: !!warehouseId,
    placeholderData: keepPreviousData,
  });
  if (!warehouseId) return null;
  if (list.isLoading) return <div className="flex flex-col gap-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>;
  if (list.isError) return <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />;
  if (!list.data?.items.length) return <Empty text="لا توجد حركات في هذا المخزن بعد" />;
  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-xs text-muted">
              <th className="p-3 text-start">التاريخ</th>
              <th className="p-3 text-start">الحركة</th>
              <th className="p-3 text-start">الصنف</th>
              <th className="p-3 text-end">الكمية</th>
              <th className="p-3 text-start">البيان</th>
            </tr>
          </thead>
          <tbody>
            {list.data.items.map((m) => {
              const meta = movementLabel(m.movement_type);
              return (
                <tr key={m.id} className="border-b border-line/60 last:border-0">
                  <td className="num p-3 text-xs text-muted">{dateTime(m.created_at)}</td>
                  <td className="p-3 text-xs">{meta.label}</td>
                  <td className="p-3 font-semibold">{m.product_name ?? "—"}</td>
                  <td className={`num p-3 text-end font-bold ${meta.inbound ? "text-success" : "text-destructive"}`} dir="ltr">
                    {meta.inbound ? "+" : "−"}{fq(m.qty)}
                  </td>
                  <td className="max-w-72 truncate p-3 text-xs text-muted">{m.note || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {list.data.pages > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>السابق</Button>
          <span className="num text-muted">صفحة {page} من {list.data.pages}</span>
          <Button variant="outline" disabled={page >= list.data.pages} onClick={() => setPage((p) => p + 1)}>التالي</Button>
        </div>
      )}
    </div>
  );
}
