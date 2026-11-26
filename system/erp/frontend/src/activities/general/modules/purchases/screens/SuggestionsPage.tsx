// Purchase suggestions (PUR-4): tracked products whose stock in all branches is at or below their
// reorder point, lowest first; the chosen ones become a draft order (their reorder quantity, or what
// brings them back above the point).
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Lightbulb, Plus } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, money, qty as fq } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Button, Empty, ErrorBox } from "@/components/ui";
import { useTenantNav } from "@app/lib/tenant";
import type { Suggestion } from "../api";
import { OrderForm } from "../components/OrderForm";
import { PurchasesHeader } from "../components/PurchasesHeader";
import { type OrderLine, suggestionLine } from "../lib";

export default function SuggestionsPage() {
  const canBuy = useAuth((s) => s.can)("purchases");
  const navigate = useNavigate();
  const { tenantTo } = useTenantNav();
  const list = useQuery({ queryKey: ["purchases", "suggestions"], queryFn: () => api.get<Suggestion[]>("/purchases/suggestions") });
  const [picked, setPicked] = useState<string[]>([]);
  const [lines, setLines] = useState<OrderLine[] | null>(null);
  const rows = useMemo(() => list.data ?? [], [list.data]);
  const all = rows.length > 0 && rows.every((r) => picked.includes(r.id));

  return (
    <div className="flex flex-col gap-6">
      <PurchasesHeader
        title="اقتراحات الشراء"
        subtitle="الأصناف المتتبعة التي وصل رصيدها في كل الفروع إلى حد إعادة الطلب أو أقل (حتى 500 صنف)"
        actions={canBuy && (
          <Button disabled={!picked.length} onClick={() => setLines(rows.filter((r) => picked.includes(r.id)).map(suggestionLine))}>
            <Plus className="size-4" /> أمر شراء للمحدد ({picked.length})
          </Button>
        )}
      />
      {list.isLoading ? (
        <div className="flex flex-col gap-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !rows.length ? (
        <Empty text="لا أصناف تحت حد إعادة الطلب" hint="تظهر هنا الأصناف التي لها حد إعادة طلب (من بطاقة الصنف أو شاشة المخزون) ونزل رصيدها إليه."
               icon={<Lightbulb className="size-10" />} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                {canBuy && (
                  <th className="w-10 p-3">
                    <input type="checkbox" aria-label="تحديد الكل" checked={all} onChange={(e) => setPicked(e.target.checked ? rows.map((r) => r.id) : [])} />
                  </th>
                )}
                <th className="p-3 text-start">الصنف</th>
                <th className="p-3 text-end">الرصيد الكلي</th>
                <th className="p-3 text-end">حد إعادة الطلب</th>
                <th className="p-3 text-end">الكمية المقترحة</th>
                <th className="p-3 text-end">آخر تكلفة</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-line/60 last:border-0">
                  {canBuy && (
                    <td className="p-3 text-center">
                      <input type="checkbox" aria-label={`تحديد ${r.name}`} checked={picked.includes(r.id)}
                             onChange={(e) => setPicked((p) => (e.target.checked ? [...p, r.id] : p.filter((x) => x !== r.id)))} />
                    </td>
                  )}
                  <td className="p-3 font-semibold">{r.name}{r.sku && <span className="num ms-2 text-[11px] text-muted" dir="ltr">{r.sku}</span>}</td>
                  <td className={`num p-3 text-end font-bold ${D(r.total_stock).lte(0) ? "text-destructive" : "text-warning"}`}>{fq(r.total_stock)} <span className="text-xs font-normal text-muted">{r.unit}</span></td>
                  <td className="num p-3 text-end">{fq(r.reorder_point)}</td>
                  <td className="num p-3 text-end">{fq(suggestionLine(r).qty)}</td>
                  <td className="num p-3 text-end">{r.cost_price != null ? money(r.cost_price) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <OrderForm open={!!lines} initialLines={lines ?? undefined} onClose={() => setLines(null)}
                 onSaved={(id) => { setPicked([]); navigate(tenantTo(`/purchases/${id}`)); }} />
    </div>
  );
}
