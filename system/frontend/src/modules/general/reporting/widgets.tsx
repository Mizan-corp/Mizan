// Reporting's dashboard widgets (manifest "widgets"): today's revenue, this month, the 14-day trend.
import { ArrowDownRight, ArrowUpRight, CalendarRange, Receipt, TrendingUp } from "lucide-react";
import { Money, Num } from "@/components/app/shared";
import { Skeleton } from "@/components/kit/skeleton";
import { formatNumber } from "@/lib/format";
import { KpiCard, PanelCard } from "@app/framework/widgets";
import { useDailySales, useMonthlySales, useSalesTrend } from "./api";

export function SalesToday() {
  const daily = useDailySales();
  const trend = useSalesTrend(14);
  const total = Number(daily.data?.total_sales ?? 0);
  const count = daily.data?.invoice_count ?? 0;
  const days = trend.data ?? [];
  const yesterday = Number(days[days.length - 2]?.total_sales ?? 0);
  const delta = yesterday > 0 ? ((total - yesterday) / yesterday) * 100 : null;
  return (
    <KpiCard
      label="إجمالي إيراد اليوم"
      icon={Receipt}
      footer={
        <>
          {delta !== null && (
            <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold ${delta >= 0 ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-destructive/10 text-destructive-ink"}`}>
              {delta >= 0 ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
              {Math.abs(delta).toFixed(1)}% عن أمس
            </span>
          )}
          <span><strong className="num text-foreground">{count}</strong> فواتير</span>
          <span className="text-border">·</span>
          <span>متوسط: <strong className="num text-foreground"><Money value={count > 0 ? total / count : 0} /></strong></span>
        </>
      }
    >
      {daily.isLoading ? (
        <Skeleton className="h-8 w-32" />
      ) : daily.isError ? (
        <span className="text-xs text-destructive-ink">تعذر التحميل</span>
      ) : (
        <div className="flex items-baseline gap-1.5">
          <span className="num font-mono text-3xl font-black tracking-tight text-foreground">{formatNumber(total)}</span>
          <span className="font-mono text-xs font-bold text-muted-foreground">ج.م</span>
        </div>
      )}
    </KpiCard>
  );
}

export function SalesMonth() {
  const monthly = useMonthlySales();
  return (
    <KpiCard
      label="مبيعات الشهر الحالي"
      icon={CalendarRange}
      footer={<span><Num value={monthly.data?.invoice_count ?? 0} /> عملية بيع مسجلة هذا الشهر</span>}
    >
      {monthly.isLoading ? (
        <Skeleton className="h-8 w-32" />
      ) : monthly.isError ? (
        <span className="text-xs text-destructive-ink">تعذر التحميل</span>
      ) : (
        <span className="num font-mono text-3xl font-black tracking-tight text-foreground">
          <Money value={Number(monthly.data?.total_sales ?? 0)} />
        </span>
      )}
    </KpiCard>
  );
}

function Sparkline({ data, className }: { data: number[]; className?: string }) {
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => `${((i / Math.max(data.length - 1, 1)) * 100).toFixed(1)},${(32 - ((v - min) / range) * 26).toFixed(1)}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 34" preserveAspectRatio="none" className={className} aria-hidden>
      <defs>
        <linearGradient id="dash-spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <polygon points={`0,32 ${pts} 100,32`} fill="url(#dash-spark-fill)" />
      <polyline points={pts} fill="none" stroke="var(--primary)" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function SalesTrend() {
  const trend = useSalesTrend(14);
  const values = (trend.data ?? []).map((d) => Number(d.total_sales || 0));
  const total = values.reduce((s, v) => s + v, 0);
  return (
    <PanelCard
      label="منحنى المبيعات والنشاط (١٤ يوماً)"
      icon={TrendingUp}
      action={
        <span className="text-xs text-muted-foreground font-mono">
          الإجمالي: <strong className="num text-foreground"><Money value={total} /></strong>
          <span className="hidden sm:inline">
            <span className="mx-2 text-border">·</span>
            متوسط اليوم: <strong className="num text-foreground"><Money value={total / 14} /></strong>
          </span>
        </span>
      }
    >
      <div className="px-2 pt-2">
        {trend.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : trend.isError ? (
          <p className="py-6 text-center text-xs text-destructive-ink">تعذر تحميل المنحنى</p>
        ) : (
          <Sparkline data={values} className="h-20 w-full" />
        )}
        {/* The line runs oldest to newest from left to right; the labels follow it, not the text direction. */}
        <div dir="ltr" className="mt-2 flex items-center justify-between border-t border-border/40 pt-2 text-[11px] font-mono text-muted-foreground">
          <span>قبل ١٤ يوماً</span>
          <span>قبل ٧ أيام</span>
          <span>اليوم</span>
        </div>
      </div>
    </PanelCard>
  );
}
