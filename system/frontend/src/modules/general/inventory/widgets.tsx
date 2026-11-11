// Inventory dashboard widgets (manifest "widgets"): items below their reorder level in the branch.
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { ListState, Num } from "@/components/app/shared";
import { Button } from "@/components/kit/button";
import { Skeleton } from "@/components/kit/skeleton";
import { useBranch } from "@app/components/AppShell";
import { KpiCard, PanelCard } from "@app/framework/widgets";
import { useTenantNav } from "@app/lib/tenant";
import { useLowStock } from "./api";

export function LowStockCount() {
  const { branchId } = useBranch();
  const low = useLowStock(branchId);
  const { tenantTo } = useTenantNav();
  const count = low.data?.length ?? 0;
  return (
    <KpiCard
      label="الأصناف تحت حد الطلب"
      icon={AlertTriangle}
      tone={count > 0 ? "warn" : "default"}
      footer={
        <Link to={tenantTo("/inventory")} className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
          {count > 0 ? "عرض قائمة النواقص ←" : "المخزون متزن بالكامل ✓"}
        </Link>
      }
    >
      {low.isLoading ? (
        <Skeleton className="h-8 w-20" />
      ) : low.isError ? (
        <span className="text-xs text-destructive">تعذر التحميل</span>
      ) : (
        <div className="flex items-baseline gap-1.5">
          <span className={`num font-mono text-3xl font-black tracking-tight ${count > 0 ? "text-amber-600 dark:text-amber-400" : "text-foreground"}`}>
            <Num value={count} />
          </span>
          <span className="text-xs font-bold text-muted-foreground">صنف بحاجة لتوريد</span>
        </div>
      )}
    </KpiCard>
  );
}

export function LowStock() {
  const { branchId } = useBranch();
  const low = useLowStock(branchId);
  const { tenantTo } = useTenantNav();
  const rows = low.data ?? [];
  return (
    <PanelCard
      label={<>النواقص العاجلة {rows.length > 0 && <span className="num font-mono text-muted-foreground">({rows.length})</span>}</>}
      icon={AlertTriangle}
      iconClassName="text-amber-500"
      action={
        <Button variant="outline" size="sm" nativeButton={false} render={<Link to={tenantTo("/purchases")} />} className="tactile-btn text-xs">
          + طلب شراء
        </Button>
      }
    >
      <div className="p-1">
        <ListState
          status={low.isLoading ? "loading" : low.isError ? "error" : "ready"}
          isEmpty={rows.length === 0}
          onRetry={() => low.refetch()}
          emptyTitle="المخزون متزن تماماً"
          emptyDescription="كافة الأصناف المسجلة في هذا الفرع أعلى من حد الطلب الأدنى."
          emptyAction={
            <Button variant="outline" size="sm" nativeButton={false} render={<Link to={tenantTo("/inventory")} />}>
              فحص تفاصيل المخزون
            </Button>
          }
        >
          <ul className="divide-y divide-border/40">
            {rows.slice(0, 6).map((p) => (
              <li key={p.product_id} className="flex items-center justify-between gap-3 py-2 text-xs">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold text-foreground">{p.product_name}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">وحدة القياس: {p.unit}</p>
                </div>
                <div className="text-end">
                  <span className="num font-mono text-xs font-black text-destructive"><Num value={p.current_qty} /></span>
                  <span className="ms-1 text-[10px] text-muted-foreground">{p.unit}</span>
                </div>
              </li>
            ))}
          </ul>
        </ListState>
      </div>
    </PanelCard>
  );
}
