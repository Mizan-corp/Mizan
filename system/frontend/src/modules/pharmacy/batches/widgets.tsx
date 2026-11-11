// Batches dashboard widget (manifest "widgets"): expired and soon-to-expire batches still in stock.
import { Link } from "react-router-dom";
import { CalendarClock } from "lucide-react";
import { ListState, Num } from "@/components/app/shared";
import { Button } from "@/components/kit/button";
import { useBranch } from "@app/components/AppShell";
import { PanelCard } from "@app/framework/widgets";
import { useTenantNav } from "@app/lib/tenant";
import { useExpiringBatches } from "./api";

export function ExpiringSoon() {
  const { branchId } = useBranch();
  const expiring = useExpiringBatches(branchId, 90);
  const { tenantTo } = useTenantNav();
  const rows = expiring.data ?? [];
  const expired = rows.filter((r) => r.days_left < 0).length;
  return (
    <PanelCard
      label={<>تشغيلات منتهية أو تنتهي خلال ٩٠ يوماً {rows.length > 0 && <span className="num font-mono text-muted-foreground">({rows.length})</span>}</>}
      icon={CalendarClock}
      iconClassName={expired > 0 ? "text-destructive" : "text-amber-500"}
      action={
        <Button variant="ghost" size="sm" nativeButton={false} render={<Link to={tenantTo("/pharmacy?tab=batches")} />} className="text-xs text-muted-foreground hover:text-foreground">
          كل التشغيلات ←
        </Button>
      }
    >
      <div className="p-1">
        <ListState
          status={expiring.isLoading ? "loading" : expiring.isError ? "error" : "ready"}
          isEmpty={rows.length === 0}
          onRetry={() => expiring.refetch()}
          emptyTitle="لا توجد تشغيلات قريبة الانتهاء"
          emptyDescription="كل التشغيلات المتوفرة في هذا الفرع صالحة لأكثر من ٩٠ يوماً."
        >
          <ul className="divide-y divide-border/40">
            {rows.slice(0, 6).map((b) => (
              <li key={b.id} className="flex items-center justify-between gap-3 py-2 text-xs">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold text-foreground">{b.product_name}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    تشغيلة <span className="num font-mono" dir="ltr">{b.batch_number}</span> · الكمية <Num value={Number(b.qty)} />
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-0.5">
                  <span className="num font-mono text-[11px] text-muted-foreground" dir="ltr">{b.expiry_date}</span>
                  <span className={`text-[10px] font-bold ${b.days_left < 0 ? "text-destructive" : "text-amber-600 dark:text-amber-400"}`}>
                    {b.days_left < 0 ? "منتهية" : b.days_left === 0 ? "تنتهي اليوم" : `بعد ${b.days_left} يوم`}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </ListState>
      </div>
    </PanelCard>
  );
}
