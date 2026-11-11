// POS dashboard widgets (manifest "widgets"): the branch's shift and the latest invoices.
import { Link } from "react-router-dom";
import { Clock, Receipt, ShoppingCart } from "lucide-react";
import { ListState, Money, StatusBadge, TableShell } from "@/components/app/shared";
import { Button } from "@/components/kit/button";
import { Skeleton } from "@/components/kit/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { formatDateTime } from "@/lib/format";
import { useBranch } from "@app/components/AppShell";
import { KpiCard, PanelCard } from "@app/framework/widgets";
import { useTenantNav } from "@app/lib/tenant";
import { useCurrentShift, useRecentSales } from "./api";

export function ShiftStatus() {
  const { branchId } = useBranch();
  const shift = useCurrentShift(branchId);
  const { tenantTo } = useTenantNav();
  return (
    <KpiCard
      label="حالة الوردية"
      icon={Clock}
      footer={
        <div className="flex w-full items-center justify-between gap-2">
          <span className="truncate font-mono">{shift.data ? formatDateTime(shift.data.started_at) : "لا توجد وردية مفتوحة"}</span>
          <Link to={tenantTo("/shifts")} className="shrink-0 font-bold text-primary hover:underline">
            {shift.data ? "إدارة الوردية ←" : "فتح وردية ←"}
          </Link>
        </div>
      }
    >
      {shift.isLoading ? (
        <Skeleton className="h-6 w-28" />
      ) : shift.data ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-bold text-emerald-600 dark:text-emerald-400">
          <span className="size-2 animate-pulse rounded-full bg-emerald-500" />
          الوردية نشطة
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-destructive/15 px-2.5 py-0.5 text-xs font-bold text-destructive">
          الوردية مغلقة
        </span>
      )}
    </KpiCard>
  );
}

export function RecentSales() {
  const recent = useRecentSales(7);
  const { tenantTo } = useTenantNav();
  const rows = recent.data ?? [];
  return (
    <PanelCard
      label="أحدث الفواتير والعمليات"
      icon={Receipt}
      action={
        <Button variant="ghost" size="sm" nativeButton={false} render={<Link to={tenantTo("/sales")} />} className="text-xs text-muted-foreground hover:text-foreground">
          عرض السجل كاملاً ←
        </Button>
      }
    >
      <ListState
        status={recent.isLoading ? "loading" : recent.isError ? "error" : "ready"}
        isEmpty={rows.length === 0}
        onRetry={() => recent.refetch()}
        emptyTitle="لا توجد مبيعات مسجلة"
        emptyDescription="ستظهر هنا العمليات لحظياً بمجرد إتمام أول بيع عبر الكاشير."
        emptyAction={
          <Button nativeButton={false} render={<Link to={tenantTo("/pos")} />} size="sm">
            <ShoppingCart data-icon="inline-start" className="size-3.5" />
            ابدأ البيع الآن [F2]
          </Button>
        }
      >
        <TableShell>
          <Table>
            <TableHeader>
              <TableRow className="border-b border-border/60 text-[11px]">
                <TableHead>رقم الفاتورة</TableHead>
                <TableHead>العميل</TableHead>
                <TableHead className="text-end">الإجمالي</TableHead>
                <TableHead>الحالة</TableHead>
                <TableHead className="hidden w-[170px] whitespace-nowrap sm:table-cell">التوقيت</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((inv) => (
                <TableRow key={inv.id} className="text-xs transition-colors hover:bg-secondary/30">
                  <TableCell className="num font-mono font-bold text-foreground">{inv.invoice_number}</TableCell>
                  <TableCell className="text-muted-foreground">{inv.customer_name ?? "عميل نقدي"}</TableCell>
                  <TableCell className="text-end font-mono font-black text-foreground"><Money value={Number(inv.total)} /></TableCell>
                  <TableCell><StatusBadge status={inv.status} /></TableCell>
                  <TableCell className="num hidden w-[170px] whitespace-nowrap font-mono text-[11px] text-muted-foreground sm:table-cell">{formatDateTime(inv.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableShell>
      </ListState>
    </PanelCard>
  );
}
