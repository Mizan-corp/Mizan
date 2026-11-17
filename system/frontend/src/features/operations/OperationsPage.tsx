import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, PackagePlus, Send } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, dateTime } from "@/lib/format";
import { Badge, Button, Card, ConfirmDialog, Empty, ErrorBox, Input, Select, Spinner } from "@/components/ui";
import { newLocalId } from "@app/lib/offline";
import { useAuth } from "@/stores/auth";
import { useTenantNav } from "@app/lib/tenant";

interface Warehouse { id: string; name: string }
interface Product { id: string; name: string; code: string | null; cost_price: string }
interface OpRow { id: string; doc_number: string; doc_type: string; status?: string | null; created_at: string; metadata?: Record<string, unknown> | null }
interface OpPage { items: OpRow[]; total: number; page: number; pages: number }
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
      {tab === "receipt" && <ReceiptNotice />}
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
  // One id per document being written: a retry (double click, lost answer) returns the same document.
  const [clientId, setClientId] = useState(newLocalId);

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
        client_id: clientId,
      }),
    onSuccess: () => { setLines([]); setNotes(""); setClientId(newLocalId()); qc.invalidateQueries({ queryKey: ["operations"] }); },
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

/** Goods from a supplier come in through a purchase order: the supplier is owed the amount and the
 * stock's value reaches the ledger. The receipt that used to be here did neither (OPS-1). */
function ReceiptNotice() {
  const { tenantTo } = useTenantNav();
  const { can } = useAuth();
  return (
    <Card className="max-w-2xl space-y-3">
      <p className="flex items-center gap-2 font-bold"><PackagePlus size={18} /> استلام بضاعة من مورد</p>
      <p className="text-sm text-muted">
        يُسجَّل استلام البضاعة من المورد بأمر شراء من شاشة المشتريات: تدخل الكميات المخزن بتكلفتها، ويُضاف المبلغ
        إلى حساب المورد، ويُرحَّل المخزون إلى الدفاتر. لنقل بضاعة بين الفروع استخدم «إذن صرف».
      </p>
      {can("purchases") && (
        <Link to={tenantTo("/purchases")} className="inline-flex rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-brand-ink">
          الانتقال إلى المشتريات
        </Link>
      )}
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
  // One id per document being written: a retry (double click, lost answer) returns the same document.
  const [clientId, setClientId] = useState(newLocalId);

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
        client_id: clientId,
      }),
    onSuccess: () => { setLines([]); setNotes(""); setClientId(newLocalId()); qc.invalidateQueries({ queryKey: ["operations"] }); },
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

const STATUS_LABELS: Record<string, { label: string; tone: "muted" | "success" | "warning" | "danger" }> = {
  done: { label: "تم", tone: "success" },
  pending: { label: "قيد الانتظار", tone: "warning" },
  cancelled: { label: "ملغى", tone: "danger" },
};

const PAGE_SIZE = 50;

function History() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const [page, setPage] = useState(1);
  const [cancelling, setCancelling] = useState<OpRow | null>(null);
  const q = useQuery({
    queryKey: ["operations", page],
    queryFn: () => api.get<OpPage>("/operations/", { page, page_size: PAGE_SIZE }),
  });
  const cancel = useMutation({
    mutationFn: (row: OpRow) => api.post(`/operations/${row.id}/cancel`, {}),
    onSuccess: () => { setCancelling(null); qc.invalidateQueries({ queryKey: ["operations"] }); },
    onError: () => setCancelling(null),
  });
  const items = q.data?.items ?? [];
  const pages = q.data?.pages ?? 1;
  const canCancel = can("operations:cancel");

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
    <div className="flex flex-col gap-3">
      {cancel.isError && <ErrorBox message={(cancel.error as Error).message} />}
      <div className="overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-xs text-muted bg-secondary/20">
              <th className="p-3 text-start">المستند</th>
              <th className="p-3 text-start">النوع</th>
              <th className="p-3 text-start">الحالة</th>
              <th className="p-3 text-start">التاريخ</th>
              {canCancel && <th className="p-3 text-start"><span className="sr-only">إجراءات</span></th>}
            </tr>
          </thead>
          <tbody>
            {items.map((r) => {
              const status = r.status ? STATUS_LABELS[r.status] : undefined;
              return (
                <tr key={r.id} className="border-b border-line/60 last:border-0 hover:bg-secondary/10 transition-colors">
                  <td className="num p-3 font-bold text-foreground" dir="ltr">{r.doc_number ?? "—"}</td>
                  <td className="p-3">
                    <span className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-foreground">
                      {DOC_TYPE_LABELS[String(r.doc_type)] ?? String(r.doc_type ?? "—")}
                    </span>
                  </td>
                  <td className="p-3">{status ? <Badge tone={status.tone}>{status.label}</Badge> : "—"}</td>
                  <td className="p-3 text-xs text-muted">{r.created_at ? dateTime(String(r.created_at)) : "—"}</td>
                  {canCancel && (
                    <td className="p-3 text-end">
                      {r.doc_type === "dispatch_order" && r.status !== "cancelled" && (
                        <Button variant="ghost" className="h-8 text-danger" disabled={cancel.isPending} onClick={() => setCancelling(r)}>
                          إلغاء الإذن
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-xs text-muted">
        <span>إجمالي المستندات: <span className="num">{q.data?.total ?? 0}</span></span>
        {pages > 1 && (
          <div className="flex items-center gap-2">
            <Button variant="ghost" className="h-8" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>السابق</Button>
            <span className="num">{page} / {pages}</span>
            <Button variant="ghost" className="h-8" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>التالي</Button>
          </div>
        )}
      </div>
      <ConfirmDialog
        open={!!cancelling}
        onClose={() => setCancelling(null)}
        onConfirm={() => cancelling && cancel.mutate(cancelling)}
        title="إلغاء إذن الصرف"
        message={`ستعود كميات الإذن ${cancelling?.doc_number ?? ""} من مخزن الوجهة إلى مخزن المصدر. لا يمكن التراجع عن الإلغاء.`}
        confirmLabel="إلغاء الإذن"
      />
    </div>
  );
}
