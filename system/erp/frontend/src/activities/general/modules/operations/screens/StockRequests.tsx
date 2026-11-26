// Stock requests (OPS-4): a branch asks another for goods; a manager approves (operations:approve) or
// rejects; once approved, someone working in both branches fulfils it, which makes a dispatch
// (DSP-…) for the requested quantities or less. The maker may cancel it before approval.
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardList, Send, X } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { dateTime, qty as fq } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { newLocalId } from "@app/lib/offline";
import { parseNumber } from "@activities/general/modules/inventory/lib";

interface RequestItem { product_id: string; name: string; qty: number }
interface RequestDoc {
  id: string;
  doc_number: string;
  status: string | null;
  created_by: string | null;
  created_at: string;
  metadata: {
    from?: string; to?: string; items?: RequestItem[]; notes?: string | null; employee?: string;
    approved_by?: string; cancelled_by?: string; cancel_reason?: string; dispatch_number?: string;
    fulfilled_items?: { product_id: string; qty: number }[];
  };
}

const REQUEST_STATUS: Record<string, { label: string; tone: "muted" | "success" | "warning" | "danger" | "brand" }> = {
  pending: { label: "بانتظار الاعتماد", tone: "warning" },
  approved: { label: "معتمد — بانتظار الصرف", tone: "brand" },
  fulfilled: { label: "تم الصرف", tone: "success" },
  cancelled: { label: "ملغى", tone: "danger" },
};

type Action = { kind: "approve" | "cancel"; doc: RequestDoc } | null;

export function StockRequests() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { can, user } = useAuth();
  const approver = can("operations:approve");
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [action, setAction] = useState<Action>(null);
  const [reason, setReason] = useState("");
  const [fulfilling, setFulfilling] = useState<RequestDoc | null>(null);
  const list = useQuery({
    queryKey: ["operations", "requests", status, page],
    queryFn: () => api.get<{ items: RequestDoc[]; total: number; pages: number }>("/operations/", {
      doc_type: "stock_request", status: status || undefined, page, page_size: 25,
    }),
    placeholderData: keepPreviousData,
  });
  const act = useMutation({
    mutationFn: ({ kind, doc }: NonNullable<Action>) =>
      api.post(`/operations/stock-requests/${doc.id}/${kind}`, kind === "cancel" ? { reason: reason.trim() || null } : { note: reason.trim() || null }),
    onSuccess: (_r, v) => {
      toast("success", v.kind === "approve" ? `اعتُمد الطلب ${v.doc.doc_number}` : `أُلغي الطلب ${v.doc.doc_number}`);
      setAction(null); setReason("");
      qc.invalidateQueries({ queryKey: ["operations"] });
    },
    onError: (e) => { setAction(null); toast("error", (e as Error).message); },
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="req-status" className="text-xs font-semibold text-muted">الحالة</label>
        <Select id="req-status" className="w-56" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">كل الطلبات</option>
          {Object.entries(REQUEST_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </Select>
      </div>
      {list.isLoading ? (
        <div className="flex flex-col gap-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}</div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.items.length ? (
        <Empty text="لا توجد طلبات" hint={status ? "غيّر الحالة لرؤية غيرها" : "يُنشأ الطلب من «طلب مخزون»"} icon={<ClipboardList className="size-10" />} />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data.items.map((d) => {
            const st = REQUEST_STATUS[d.status ?? "pending"] ?? { label: d.status ?? "—", tone: "muted" as const };
            const mine = !!user && d.created_by === String(user.id);
            const s = d.status ?? "pending";
            return (
              <div key={d.id} className="rounded-xl border border-line bg-card p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="num font-bold" dir="ltr">{d.doc_number}</span>
                    <Badge tone={st.tone}>{st.label}</Badge>
                    <span className="text-xs text-muted">من {d.metadata.from} إلى {d.metadata.to} · {d.metadata.employee} · {dateTime(d.created_at)}</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {approver && s === "pending" && (
                      <Button size="sm" onClick={() => setAction({ kind: "approve", doc: d })}><Check className="size-4" /> اعتماد</Button>
                    )}
                    {s === "approved" && can("operations") && (
                      <Button size="sm" onClick={() => setFulfilling(d)}><Send className="size-4" /> صرف</Button>
                    )}
                    {((approver && (s === "pending" || s === "approved")) || (mine && s === "pending")) && (
                      <Button size="sm" variant="ghost" onClick={() => setAction({ kind: "cancel", doc: d })}>
                        <X className="size-4" /> {approver && !mine ? "رفض" : "إلغاء"}
                      </Button>
                    )}
                  </div>
                </div>
                <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  {(d.metadata.items ?? []).map((i) => {
                    const sent = d.metadata.fulfilled_items?.find((f) => f.product_id === i.product_id);
                    return (
                      <li key={i.product_id}>
                        {i.name} <span className="num font-bold">× {fq(i.qty)}</span>
                        {s === "fulfilled" && <span className="text-muted"> (صُرف <span className="num">{fq(sent?.qty ?? 0)}</span>)</span>}
                      </li>
                    );
                  })}
                </ul>
                {(d.metadata.notes || d.metadata.dispatch_number || d.metadata.cancel_reason || d.metadata.approved_by) && (
                  <p className="mt-2 text-[11px] text-muted">
                    {d.metadata.notes && <>ملاحظات: {d.metadata.notes}. </>}
                    {d.metadata.approved_by && <>اعتمده {d.metadata.approved_by}. </>}
                    {d.metadata.dispatch_number && <>صُرف بإذن <span className="num" dir="ltr">{d.metadata.dispatch_number}</span>. </>}
                    {d.metadata.cancelled_by && <>ألغاه {d.metadata.cancelled_by}{d.metadata.cancel_reason ? `: ${d.metadata.cancel_reason}` : ""}.</>}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
      {(list.data?.pages ?? 1) > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>السابق</Button>
          <span className="num text-muted">صفحة {page} من {list.data!.pages}</span>
          <Button variant="outline" disabled={page >= list.data!.pages} onClick={() => setPage((p) => p + 1)}>التالي</Button>
        </div>
      )}

      <Modal open={!!action} onClose={() => { setAction(null); setReason(""); }}
             title={action ? `${action.kind === "approve" ? "اعتماد" : "إلغاء"} الطلب ${action.doc.doc_number}` : ""}>
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted">
            {action?.kind === "approve"
              ? "بعد الاعتماد يُصرف الطلب من المخزن المصدر بإذن صرف. لا تتحرك البضاعة الآن."
              : "يُلغى الطلب ولا يمكن صرفه بعد ذلك؛ يبقى في السجل."}
          </p>
          <div>
            <label htmlFor="req-reason" className="mb-1 block text-xs font-semibold text-muted">{action?.kind === "approve" ? "ملاحظة (اختياري)" : "السبب"}</label>
            <Input id="req-reason" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <Button className="h-10 w-full font-bold" variant={action?.kind === "cancel" ? "danger" : "default"} disabled={act.isPending}
                  onClick={() => action && act.mutate(action)}>
            {act.isPending ? <Spinner /> : action?.kind === "approve" ? "اعتماد" : "إلغاء الطلب"}
          </Button>
        </div>
      </Modal>
      <FulfilModal doc={fulfilling} onClose={() => setFulfilling(null)} />
    </div>
  );
}

function FulfilModal({ doc, onClose }: { doc: RequestDoc | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [qty, setQty] = useState<Record<string, string>>({});
  const [clientId] = useState(newLocalId);
  const items = doc?.metadata.items ?? [];
  const value = (i: RequestItem) => qty[i.product_id] ?? String(i.qty);
  const bad = items.some((i) => {
    const q = value(i).trim() === "" ? null : parseNumber(value(i));
    return value(i).trim() !== "" && (q === null || q.gt(i.qty));
  });
  const lines = items.map((i) => ({ product_id: i.product_id, qty: parseNumber(value(i)) })).filter((l) => l.qty && l.qty.gt(0));
  const send = useMutation({
    mutationFn: () => api.post<{ dispatch: { doc_number: string } }>(`/operations/stock-requests/${doc!.id}/fulfil`, {
      items: lines.map((l) => ({ product_id: l.product_id, qty: l.qty!.toString() })), client_id: clientId,
    }),
    onSuccess: (r) => {
      toast("success", `صُرف الطلب بإذن الصرف ${r.dispatch.doc_number}`);
      setQty({});
      for (const k of ["operations", "stock", "movements-ledger"]) qc.invalidateQueries({ queryKey: [k] });
      onClose();
    },
  });
  return (
    <Modal open={!!doc} onClose={() => { setQty({}); onClose(); }} title={`صرف الطلب ${doc?.doc_number ?? ""}`}>
      <div className="flex flex-col gap-4">
        <p className="text-xs text-muted">
          يُنشأ إذن صرف من {doc?.metadata.from} إلى {doc?.metadata.to}. اصرف المطلوب أو أقل منه (0 لصنف لا يُصرف)؛ يلزم أن يكون الرصيد كافياً في المخزن المصدر.
        </p>
        <ul className="divide-y divide-line/60 rounded-xl border border-line">
          {items.map((i) => (
            <li key={i.product_id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
              <span className="min-w-0 truncate">{i.name} <span className="text-xs text-muted">(المطلوب <span className="num">{fq(i.qty)}</span>)</span></span>
              <Input className="num w-24" inputMode="decimal" aria-label={`الكمية المصروفة من ${i.name}`} value={value(i)}
                     onChange={(e) => setQty((q) => ({ ...q, [i.product_id]: e.target.value }))} />
            </li>
          ))}
        </ul>
        {bad && <p className="text-xs text-destructive">كمية غير صحيحة أو أكبر من المطلوب.</p>}
        {send.isError && <ErrorBox message={(send.error as Error).message} />}
        <Button className="h-10 w-full font-bold" disabled={bad || !lines.length || send.isPending} onClick={() => send.mutate()}>
          {send.isPending ? <Spinner /> : "إنشاء إذن الصرف"}
        </Button>
      </div>
    </Modal>
  );
}
