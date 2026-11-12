import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, PackagePlus, Send } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, dateTime } from "@/lib/format";
import { Button, Card, Empty, ErrorBox, Input, Select, Spinner } from "@/components/ui";

interface Warehouse { id: string; name: string }
interface Product { id: string; name: string; code: string | null; cost_price: string }
interface OpRow { id?: string; doc_number?: string; doc_type?: string; created_at?: string; [k: string]: unknown }
interface Line { product: Product; qty: string; unit_cost: string }

function ProductSearch({ onPick }: { onPick: (p: Product) => void }) {
  const [q, setQ] = useState("");
  const found = useQuery({
    queryKey: ["op-product-search", q],
    queryFn: () => api.get<{ items: Product[] }>("/products", { search: q, page: 1, page_size: 8 }),
    enabled: q.trim().length > 1,
  });
  return (
    <div>
      <Input placeholder="ابحث عن منتج…" value={q} onChange={(e) => setQ(e.target.value)} />
      {!!found.data?.items.length && (
        <div className="mt-2 grid gap-1 rounded-lg border border-line p-2">
          {found.data.items.map((p) => (
            <button key={p.id} className="rounded-md px-2 py-1.5 text-start text-sm hover:bg-elevated" onClick={() => { onPick(p); setQ(""); }}>
              {p.name} <span className="num text-xs text-muted">{p.code}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Lines({ lines, setLines, showCost }: { lines: Line[]; setLines: React.Dispatch<React.SetStateAction<Line[]>>; showCost: boolean }) {
  return (
    <div className="space-y-2">
      {lines.map((l, i) => (
        <div key={l.product.id} className="flex flex-wrap items-center gap-2">
          <span className="min-w-0 flex-1 truncate text-sm font-semibold">{l.product.name}</span>
          <Input
            className="num w-20" inputMode="decimal" placeholder="كمية" aria-label="الكمية"
            value={l.qty}
            onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, qty: e.target.value } : x))}
          />
          {showCost && (
            <Input
              className="num w-24" inputMode="decimal" placeholder="تكلفة" aria-label="التكلفة"
              value={l.unit_cost}
              onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, unit_cost: e.target.value } : x))}
            />
          )}
          <button className="rounded p-1 text-danger" onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))} aria-label="حذف">✕</button>
        </div>
      ))}
    </div>
  );
}

export default function OperationsPage() {
  const [tab, setTab] = useState("dispatch");
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">العمليات</h1>
      <div className="flex flex-wrap gap-2">
        {[
          { k: "dispatch", l: "إذن صرف" },
          { k: "receipt", l: "استلام بضاعة" },
          { k: "request", l: "طلب مخزون" },
          { k: "history", l: "السجل" },
        ].map((t) => (
          <button
            key={t.k}
            onClick={() => setTab(t.k)}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${tab === t.k ? "bg-brand text-brand-ink" : "border border-line text-muted hover:text-ink"}`}
          >
            {t.l}
          </button>
        ))}
      </div>
      {tab === "dispatch" && <DispatchForm />}
      {tab === "receipt" && <ReceiptForm />}
      {tab === "request" && <RequestForm />}
      {tab === "history" && <History />}
    </div>
  );
}

function useWarehouses() {
  return useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<Warehouse[]>("/stock/warehouses") });
}

const DOC_TYPE_LABELS: Record<string, string> = {
  dispatch_order: "إذن صرف",
  goods_receipt: "استلام بضاعة",
  stock_request: "طلب مخزون",
};

function DispatchForm() {
  const qc = useQueryClient();
  const wh = useWarehouses();
  const warehouses = Array.isArray(wh.data) ? wh.data : [];
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([]);

  const effectiveFrom = from || warehouses[0]?.id || "";
  const effectiveTo = to || (warehouses[1]?.id ?? warehouses[0]?.id ?? "");
  const isSameWarehouse = Boolean(effectiveFrom && effectiveTo && effectiveFrom === effectiveTo);

  const run = useMutation({
    mutationFn: () =>
      api.post("/operations/dispatch", {
        from_warehouse_id: effectiveFrom,
        to_warehouse_id: effectiveTo,
        notes: notes || undefined,
        items: lines.map((l) => ({ product_id: l.product.id, qty: D(l.qty).toNumber(), note: null })),
      }),
    onSuccess: () => { setLines([]); setNotes(""); qc.invalidateQueries({ queryKey: ["operations"] }); },
  });

  return (
    <Card className="max-w-2xl space-y-3">
      <p className="flex items-center gap-2 font-bold"><Send size={18} /> إذن صرف — نقل بضاعة من فرع لآخر مع مستند</p>
      {warehouses.length < 2 && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-500">
          تنبيه: يتطلب إذن الصرف وجود مستودعين أو فرعين على الأقل للنقل بينهما.
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted mb-1 block">من مستودع:</label>
          <Select value={effectiveFrom} onChange={(e) => setFrom(e.target.value)}>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        </div>
        <div>
          <label className="text-xs text-muted mb-1 block">إلى مستودع:</label>
          <Select value={effectiveTo} onChange={(e) => setTo(e.target.value)}>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        </div>
      </div>
      {isSameWarehouse && warehouses.length > 1 && (
        <p className="text-xs text-danger font-medium">لا يمكن أن يكون مستودع المصدر ومستودع الوجهة نفس المستودع.</p>
      )}
      <ProductSearch onPick={(p) => !lines.find((l) => l.product.id === p.id) && setLines((ls) => [...ls, { product: p, qty: "", unit_cost: p.cost_price }])} />
      <Lines lines={lines} setLines={setLines} showCost={false} />
      <Input placeholder="ملاحظات" value={notes} onChange={(e) => setNotes(e.target.value)} />
      {run.isError && <ErrorBox message={(run.error as Error).message} />}
      {run.isSuccess && <Card className="border-success/40 bg-success/10 p-3 text-sm text-success-ink">تم إنشاء إذن الصرف بنجاح</Card>}
      <Button
        className="w-full"
        disabled={run.isPending || !lines.length || lines.some((l) => !l.qty) || isSameWarehouse || warehouses.length < 2}
        onClick={() => run.mutate()}
      >
        {run.isPending ? <Spinner /> : "إنشاء إذن الصرف"}
      </Button>
    </Card>
  );
}

function ReceiptForm() {
  const qc = useQueryClient();
  const wh = useWarehouses();
  const warehouses = Array.isArray(wh.data) ? wh.data : [];
  const [warehouseId, setWarehouseId] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([]);

  const effectiveWh = warehouseId || warehouses[0]?.id || "";

  const run = useMutation({
    mutationFn: () =>
      api.post("/operations/goods-receipt", {
        warehouse_id: effectiveWh,
        supplier_name: supplierName || undefined,
        notes: notes || undefined,
        items: lines.map((l) => ({
          product_id: l.product.id,
          qty: D(l.qty).toNumber(),
          unit_cost: D(l.unit_cost || l.product.cost_price).toNumber(),
        })),
      }),
    onSuccess: () => { setLines([]); setSupplierName(""); setNotes(""); qc.invalidateQueries({ queryKey: ["operations"] }); },
  });

  return (
    <Card className="max-w-2xl space-y-3">
      <p className="flex items-center gap-2 font-bold"><PackagePlus size={18} /> استلام بضاعة من مورد — يضاف للمخزن بالتكلفة</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted mb-1 block">المستودع المستلم:</label>
          <Select value={effectiveWh} onChange={(e) => setWarehouseId(e.target.value)}>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        </div>
        <div>
          <label className="text-xs text-muted mb-1 block">المورد:</label>
          <Input placeholder="اسم المورد (اختياري)" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} />
        </div>
      </div>
      <ProductSearch onPick={(p) => !lines.find((l) => l.product.id === p.id) && setLines((ls) => [...ls, { product: p, qty: "", unit_cost: p.cost_price }])} />
      <Lines lines={lines} setLines={setLines} showCost />
      <Input placeholder="ملاحظات" value={notes} onChange={(e) => setNotes(e.target.value)} />
      {run.isError && <ErrorBox message={(run.error as Error).message} />}
      {run.isSuccess && <Card className="border-success/40 bg-success/10 p-3 text-sm text-success-ink">تم تسجيل الاستلام بنجاح</Card>}
      <Button className="w-full" disabled={run.isPending || !lines.length || lines.some((l) => !l.qty) || !effectiveWh} onClick={() => run.mutate()}>
        {run.isPending ? <Spinner /> : "تسجيل الاستلام"}
      </Button>
    </Card>
  );
}

function RequestForm() {
  const qc = useQueryClient();
  const wh = useWarehouses();
  const warehouses = Array.isArray(wh.data) ? wh.data : [];
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([]);

  const effectiveFrom = from || warehouses[0]?.id || "";
  const effectiveTo = to || (warehouses[1]?.id ?? warehouses[0]?.id ?? "");
  const isSameWarehouse = Boolean(effectiveFrom && effectiveTo && effectiveFrom === effectiveTo);

  const run = useMutation({
    mutationFn: () =>
      api.post("/operations/stock-request", {
        from_warehouse_id: effectiveFrom,
        to_warehouse_id: effectiveTo,
        notes: notes || undefined,
        items: lines.map((l) => ({ product_id: l.product.id, qty: D(l.qty).toNumber() })),
      }),
    onSuccess: () => { setLines([]); setNotes(""); qc.invalidateQueries({ queryKey: ["operations"] }); },
  });

  return (
    <Card className="max-w-2xl space-y-3">
      <p className="flex items-center gap-2 font-bold"><ClipboardList size={18} /> طلب مخزون — طلب بضاعة من فرع آخر</p>
      {warehouses.length < 2 && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-500">
          تنبيه: يتطلب طلب المخزون وجود مستودعين أو فرعين على الأقل للطلب بينهما.
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted mb-1 block">طلب من مستودع:</label>
          <Select value={effectiveFrom} onChange={(e) => setFrom(e.target.value)}>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        </div>
        <div>
          <label className="text-xs text-muted mb-1 block">إلى مستودع:</label>
          <Select value={effectiveTo} onChange={(e) => setTo(e.target.value)}>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </Select>
        </div>
      </div>
      {isSameWarehouse && warehouses.length > 1 && (
        <p className="text-xs text-danger font-medium">لا يمكن أن يكون مستودع المصدر ومستودع الوجهة نفس المستودع.</p>
      )}
      <ProductSearch onPick={(p) => !lines.find((l) => l.product.id === p.id) && setLines((ls) => [...ls, { product: p, qty: "", unit_cost: p.cost_price }])} />
      <Lines lines={lines} setLines={setLines} showCost={false} />
      <Input placeholder="ملاحظات" value={notes} onChange={(e) => setNotes(e.target.value)} />
      {run.isError && <ErrorBox message={(run.error as Error).message} />}
      {run.isSuccess && <Card className="border-success/40 bg-success/10 p-3 text-sm text-success-ink">تم إرسال الطلب بنجاح</Card>}
      <Button
        className="w-full"
        disabled={run.isPending || !lines.length || lines.some((l) => !l.qty) || isSameWarehouse || warehouses.length < 2}
        onClick={() => run.mutate()}
      >
        {run.isPending ? <Spinner /> : "إرسال الطلب"}
      </Button>
    </Card>
  );
}

function History() {
  const q = useQuery({ queryKey: ["operations"], queryFn: () => api.get<OpRow[]>("/operations/") });
  const items: OpRow[] = Array.isArray(q.data) ? q.data : ((q.data as any)?.items ?? []);

  return q.isLoading ? (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
      <Skeleton className="h-10 w-full" />
      {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
    </div>
  ) : q.isError ? (
    <ErrorBox message={(q.error as Error).message} onRetry={() => q.refetch()} />
  ) : !items.length ? (
    <Empty text="لا توجد عمليات" />
  ) : (
    <div className="overflow-x-auto rounded-xl border border-line bg-card">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted bg-secondary/20">
            <th className="p-3 text-start">المستند</th>
            <th className="p-3 text-start">النوع</th>
            <th className="p-3 text-start">التاريخ</th>
          </tr>
        </thead>
        <tbody>
          {items.slice(0, 60).map((r, i) => (
            <tr key={(r.id as string) ?? i} className="border-b border-line/60 last:border-0 hover:bg-secondary/10 transition-colors">
              <td className="num p-3 font-bold text-foreground" dir="ltr">{r.doc_number ?? "—"}</td>
              <td className="p-3">
                <span className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-foreground">
                  {DOC_TYPE_LABELS[String(r.doc_type)] ?? String(r.doc_type ?? "—")}
                </span>
              </td>
              <td className="p-3 text-xs text-muted">{r.created_at ? dateTime(String(r.created_at)) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
