// Purchase orders (PUR-4): every order with its state and total, filtered by state or searched by
// number or supplier; a row opens the order (its lines, receipts, payments and returns).
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Plus, Truck } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, dateTime, moneyEGP } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, Empty, ErrorBox, Input } from "@/components/ui";
import { useTenantNav } from "@app/lib/tenant";
import type { POStatus, PurchaseRow } from "./api";
import { OrderForm } from "./components/OrderForm";
import { PurchasesHeader } from "./components/PurchasesHeader";
import { STATUS } from "./lib";

const PAGE = 25;
const FILTERS: [POStatus | "", string][] = [["", "الكل"], ["draft", "مسودات"], ["partial", "مستلمة جزئياً"], ["received", "مستلمة"], ["cancelled", "ملغاة"]];

export default function PurchasesPage() {
  const canBuy = useAuth((s) => s.can)("purchases");
  const navigate = useNavigate();
  const { tenantTo } = useTenantNav();
  const [status, setStatus] = useState<POStatus | "">("");
  const [typed, setTyped] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => { setSearch(typed.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [typed]);

  const list = useQuery({
    queryKey: ["purchases", "list", status, search, page],
    queryFn: () => api.get<{ items: PurchaseRow[]; total: number; pages: number }>("/purchases", {
      page, page_size: PAGE, status: status || undefined, search: search || undefined,
    }),
    placeholderData: keepPreviousData,
  });
  const open = (id: string) => navigate(tenantTo(`/purchases/${id}`));

  return (
    <div className="flex flex-col gap-6">
      <PurchasesHeader
        title="المشتريات"
        subtitle="أوامر الشراء من المسودة إلى الاستلام (كاملاً أو على دفعات) والمرتجع للمورد"
        actions={canBuy && <Button onClick={() => setCreating(true)}><Plus className="size-4" /> أمر شراء جديد</Button>}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="حالة الأمر">
          {FILTERS.map(([k, label]) => (
            <button key={k || "all"} role="tab" aria-selected={status === k} onClick={() => { setStatus(k); setPage(1); }}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${status === k ? "bg-elevated text-ink" : "text-muted hover:text-ink"}`}>
              {label}
            </button>
          ))}
        </div>
        <Input className="w-64" placeholder="ابحث برقم الأمر أو اسم المورد…" value={typed} onChange={(e) => setTyped(e.target.value)}
               aria-label="بحث في أوامر الشراء" />
      </div>

      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.items.length ? (
        <Empty
          text={status || search ? "لا توجد أوامر مطابقة" : "لا توجد أوامر شراء"}
          hint={status || search ? "غيّر الحالة أو البحث" : "أنشئ أول أمر شراء، أو ابدأ من «اقتراحات الشراء» للأصناف تحت حد الطلب."}
          icon={<Truck className="size-10" />}
          action={!status && !search && canBuy ? <Button onClick={() => setCreating(true)}><Plus className="size-4" /> أمر شراء جديد</Button> : undefined}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">الأمر</th>
                <th className="p-3 text-start">المورد</th>
                <th className="hidden p-3 text-start md:table-cell">المخزن</th>
                <th className="p-3 text-end">الإجمالي</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="hidden p-3 text-start sm:table-cell">التاريخ</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((po) => (
                <tr key={po.id} tabIndex={0} className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-elevated"
                    onClick={() => open(po.id)} onKeyDown={(e) => { if (e.key === "Enter") open(po.id); }}>
                  <td className="num p-3 font-bold" dir="ltr">{po.po_number}</td>
                  <td className="p-3">{po.supplier_name ?? "نقدي"}</td>
                  <td className="hidden p-3 text-xs md:table-cell">{po.warehouse_name ?? "—"}</td>
                  <td className="num p-3 text-end font-bold">
                    {po.total != null ? moneyEGP(po.total) : "—"}
                    {D(po.tax_amount ?? 0).gt(0) && <div className="text-[10px] font-normal text-muted">منها ضريبة {moneyEGP(po.tax_amount!)}</div>}
                  </td>
                  <td className="p-3"><Badge tone={STATUS[po.status]?.tone ?? "muted"}>{STATUS[po.status]?.label ?? po.status}</Badge></td>
                  <td className="hidden p-3 text-xs text-muted sm:table-cell">{dateTime(po.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(list.data?.pages ?? 1) > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>السابق</Button>
          <span className="num text-muted">صفحة {page} من {list.data!.pages} · {list.data!.total} أمر</span>
          <Button variant="outline" disabled={page >= list.data!.pages} onClick={() => setPage((p) => p + 1)}>التالي</Button>
        </div>
      )}

      <OrderForm open={creating} onClose={() => setCreating(false)} onSaved={open} />
    </div>
  );
}
