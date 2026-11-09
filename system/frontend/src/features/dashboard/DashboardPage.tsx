/**
 * PAGE CONTRACT
 * Page: صحيفة اليوم / لوحة التحكم (/)
 * Archetype: Linear / Raycast Precision Terminal archetype with Arab merchant craft (دفتر اليوم الفاخر)
 * User: مدير الفرع يفتح النظام في بداية اليوم لمسح أرقام اليوم بثوانٍ واتخاذ القرار الفوري
 * Primary information: مبيعات اليوم (الرقم المهيمن) → اتجاه الـ 14 يومًا (SVG Sparkline) → النواقص العاجلة → سجل العمليات
 * Strict Anti-AI Tells: zero generic purple gradients, zero sterile 4-card grids, pure tabular numerals (.num), 1px precision borders
 */
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarRange,
  Clock,
  Receipt,
  ShoppingCart,
  TrendingUp,
  Sparkles,
  ArrowLeft,
} from "lucide-react";
import { api } from "@/lib/api";
import { useBranch } from "@app/components/AppShell";
import { ListState, Money, Num, StatusBadge, TableShell } from "@/components/app/shared";
import { Button } from "@/components/kit/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { Skeleton } from "@/components/kit/skeleton";
import { formatDateTime, formatNumber } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { useTenantNav } from "@app/lib/tenant";
import { SECTOR_BADGES, SECTOR_PRIMARY_ROUTES } from "@/lib/plans";

interface DailyReport {
  date: string;
  total_sales: number;
  total_items: number;
  invoice_count: number;
}
interface MonthlyReport {
  total_sales?: string | number;
  invoice_count?: number;
  [k: string]: unknown;
}
interface SaleRow {
  id: string;
  invoice_number: string;
  customer_name: string | null;
  total: string;
  status: string;
  created_at: string;
}
interface LowStockRow {
  product_id: string;
  product_name: string;
  current_qty: number;
  unit: string;
}

/** Build a 14-day series (oldest → newest) from the recent-sales list. */
function buildTrend(sales: SaleRow[]): { day: string; sales: number }[] {
  const byDay = new Map<string, number>();
  for (const s of sales) {
    if (s.status === "cancelled" || s.status === "quotation") continue;
    const key = (s.created_at ?? "").slice(0, 10);
    if (!key) continue;
    byDay.set(key, (byDay.get(key) ?? 0) + Number(s.total || 0));
  }
  const days: { day: string; sales: number }[] = [];
  const today = new Date();
  for (let back = 13; back >= 0; back--) {
    const d = new Date(today);
    d.setDate(d.getDate() - back);
    const key = d.toISOString().slice(0, 10);
    days.push({
      day: `${d.getDate()}/${d.getMonth() + 1}`,
      sales: Math.round((byDay.get(key) ?? 0) * 100) / 100,
    });
  }
  return days;
}

/** High-craft Linear/Raycast-inspired 14-day SVG Sparkline with gradient area under curve */
function Sparkline({ data, className }: { data: { day: string; sales: number }[]; className?: string }) {
  const max = Math.max(...data.map((d) => d.sales), 1);
  const min = Math.min(...data.map((d) => d.sales), 0);
  const range = max - min || 1;

  const pts = data
    .map((d, i) => {
      const x = (i / Math.max(data.length - 1, 1)) * 100;
      const y = 32 - ((d.sales - min) / range) * 26;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const areaPts = `0,32 ${pts} 100,32`;

  return (
    <div className="relative">
      <svg viewBox="0 0 100 34" preserveAspectRatio="none" className={className} aria-hidden>
        <defs>
          <linearGradient id="dash-spark-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <polygon points={areaPts} fill="url(#dash-spark-fill)" />
        <polyline
          points={pts}
          fill="none"
          stroke="var(--primary)"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}

export default function DashboardPage() {
  const { branchId, branchName } = useBranch();
  const tenant = useAuth((s) => s.tenant);
  const { tenantTo } = useTenantNav();

  const sectorBadge = tenant?.sector ? SECTOR_BADGES[tenant.sector] : null;
  const sectorPrimaryRoute = tenant?.sector ? SECTOR_PRIMARY_ROUTES[tenant.sector] : null;
  const showSectorHero = Boolean(sectorPrimaryRoute && sectorPrimaryRoute !== "/" && sectorPrimaryRoute !== "/pos");

  const daily = useQuery({
    queryKey: ["report", "daily"],
    queryFn: () => api.get<DailyReport>("/reports/sales/daily"),
  });
  const monthly = useQuery({
    queryKey: ["report", "monthly"],
    queryFn: () =>
      api.get<MonthlyReport>("/reports/sales/monthly", {
        year: new Date().getFullYear(),
        month: new Date().getMonth() + 1,
      }),
  });
  const lowStock = useQuery({
    queryKey: ["dash", "low", branchId],
    queryFn: () => api.get<LowStockRow[]>("/stock/low-stock", { warehouse_id: branchId! }),
    enabled: !!branchId,
  });
  const shift = useQuery({
    queryKey: ["shift", "dash", branchId],
    queryFn: () => api.get<{ id: string; started_at: string } | null>("/shifts/current", { warehouse_id: branchId! }),
    enabled: !!branchId,
    retry: false,
  });
  const recent = useQuery({
    queryKey: ["dash", "recent"],
    queryFn: () => api.get<SaleRow[]>("/sales", { page: 1, page_size: 14 }),
  });

  const salesList: SaleRow[] = Array.isArray(recent.data)
    ? recent.data
    : ((recent.data as any)?.items ?? []);
  const trend = buildTrend(salesList);
  const trendTotal = trend.reduce((s, d) => s + d.sales, 0);

  const dayTotal = Number(daily.data?.total_sales ?? 0);
  const dayCount = daily.data?.invoice_count ?? 0;
  const dayAvg = dayCount > 0 ? dayTotal / dayCount : 0;
  const yesterday = trend[trend.length - 2]?.sales ?? 0;
  const dayDelta = yesterday > 0 ? ((dayTotal - yesterday) / yesterday) * 100 : null;
  const lowCount = lowStock.data?.length ?? 0;
  const todayFormatted = new Intl.DateTimeFormat("ar-EG-u-nu-latn", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "Africa/Cairo",
  }).format(new Date());

  return (
    <div className="flex flex-col gap-6">
      {/* ── Precision Masthead ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/80 pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="flex size-2 rounded-full bg-emerald-500 animate-pulse" aria-hidden />
            <h1 className="text-sm font-extrabold tracking-tight text-foreground">
              دفتر اليوم المالي · {branchName}
            </h1>
            <span className="text-xs text-muted-foreground font-mono">({todayFormatted})</span>
          </div>
          <p className="text-xs text-muted-foreground">
            موجز النشاط التجاري اليومي، حركة المبيعات، ومراقبة المخزون اللحظية.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            nativeButton={false}
            render={<Link to="/pos" />}
            size="sm"
            className="font-bold text-xs shadow-xs gap-1.5"
          >
            <ShoppingCart data-icon="inline-start" className="size-3.5" />
            <span>نقطة البيع</span>
            <kbd className="ms-1 rounded bg-primary-foreground/20 px-1.5 py-0.5 text-[10px] font-mono">F2</kbd>
          </Button>
        </div>
      </div>

      {/* ── Specialized Sector Executive Hero ── */}
      {showSectorHero && sectorPrimaryRoute && (
        <div className="rounded-2xl border border-primary/30 bg-gradient-to-r from-primary/[0.08] via-primary/[0.03] to-background p-4 sm:p-5 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-lg bg-primary/20 text-primary shrink-0">
                <Sparkles className="size-4" />
              </span>
              <span className="rounded-full bg-primary/20 px-2.5 py-0.5 text-[10px] font-bold text-primary font-mono border border-primary/30 shrink-0">
                منظومة {sectorBadge || "النشاط"} التخصصية
              </span>
              <span className="text-[10px] text-muted-foreground font-medium truncate">مهيأة بالكامل لقطاعك ✓</span>
            </div>
            <h2 className="text-sm sm:text-base font-extrabold text-foreground truncate">
              {tenant?.sector === "healthcare"
                ? "نظام إدارة العيادات، المرضى، والملفات الطبية الرقمية (EMR & Clinic)"
                : tenant?.sector === "restaurant"
                ? "إدارة الصالة، الطاولات، وشاشات المطبخ التفاعلية (KDS & Restaurant-POS)"
                : tenant?.sector === "pharmacy"
                ? "إدارة الروشتات، التأمين الطبي، وتتبع الصلاحيات (FEFO & Pharmacy)"
                : tenant?.sector === "school"
                ? "شؤون الطلاب، تحصيل الأقساط المدرسية، وحافلات النقل"
                : tenant?.sector === "law_firm"
                ? "إدارة القضايا، الجلسات، وأمانات الموكلين (Legal Practice)"
                : `منظومة العمليات التخصصية لنشاط ${sectorBadge || tenant?.name || ""}`}
            </h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {tenant?.sector === "healthcare"
                ? "سجلات المرضى، أرتال الانتظار، الكشوفات الطبية، الروشتات الإلكترونية، وأسرّة التنويم والتحاليل جاهزة للتشغيل الفوري."
                : tenant?.sector === "restaurant"
                ? "خريطة الطاولات، شاشات المطبخ اللحظية KDS، وقوائم الوجبات ووصفات المكونات مهيأة."
                : `تم تخصيص شاشات العمليات وسجلات النشاط لتلائم قطاع ${sectorBadge || ""} وفق أفضل الممارسات والمعايير.`}
            </p>
          </div>

          <div className="shrink-0 flex items-center gap-2 w-full md:w-auto">
            <Link to={tenantTo(sectorPrimaryRoute)} className="w-full md:w-auto">
              <Button size="sm" className="w-full md:w-auto font-bold gap-2 shadow-xs text-xs h-9 px-4">
                <span>فتح شاشة {sectorBadge || "المنظومة التخصصية"}</span>
                <ArrowLeft className="size-3.5" />
              </Button>
            </Link>
          </div>
        </div>
      )}

      {/* ── Bento Grid Row 1: 4 KPI Cards ── */}
      <section aria-label="المؤشرات الرئيسية" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Today's Revenue */}
        <div className="precision-surface flex flex-col justify-between rounded-xl p-4 gap-3">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">إجمالي إيراد اليوم</span>
            <div className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Receipt className="size-3.5" />
            </div>
          </div>
          <div>
            {daily.isLoading ? (
              <Skeleton className="h-8 w-32" />
            ) : daily.isError ? (
              <span className="text-xs text-destructive">تعذر التحميل</span>
            ) : (
              <div className="flex items-baseline gap-1.5">
                <span className="num font-mono text-3xl font-black tracking-tight text-foreground">
                  {formatNumber(dayTotal)}
                </span>
                <span className="font-mono text-xs font-bold text-muted-foreground">ج.م</span>
              </div>
            )}
            <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/50 text-[11px] text-muted-foreground font-mono">
              {dayDelta !== null && (
                <span
                  className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold ${
                    dayDelta >= 0
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                      : "bg-destructive/10 text-destructive"
                  }`}
                >
                  {dayDelta >= 0 ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
                  {Math.abs(dayDelta).toFixed(1)}% عن أمس
                </span>
              )}
              <span>· <strong className="num text-foreground">{dayCount}</strong> فواتير</span>
              <span className="text-border">·</span>
              <span>متوسط: <strong className="num text-foreground"><Money value={dayAvg} /></strong></span>
            </div>
          </div>
        </div>

        {/* KPI 2: Monthly Sales */}
        <div className="precision-surface flex flex-col justify-between rounded-xl p-4 gap-3">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">مبيعات الشهر الحالي</span>
            <div className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <CalendarRange className="size-3.5" />
            </div>
          </div>
          <div>
            <div className="flex items-baseline gap-1.5">
              <span className="num font-mono text-3xl font-black tracking-tight text-foreground">
                {monthly.isError ? "—" : <Money value={Number(monthly.data?.total_sales ?? 0)} />}
              </span>
            </div>
            <div className="mt-2 pt-2 border-t border-border/50 text-[11px] text-muted-foreground font-mono">
              <Num value={monthly.data?.invoice_count ?? 0} /> عملية بيع مسجلة هذا الشهر
            </div>
          </div>
        </div>

        {/* KPI 3: Low-Stock Urgent Alert */}
        <div className={`precision-surface flex flex-col justify-between rounded-xl p-4 gap-3 ${lowCount > 0 ? "border-amber-500/40 bg-amber-500/[0.03]" : ""}`}>
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">الأصناف تحت حد الطلب</span>
            <div className={`flex size-7 items-center justify-center rounded-lg ${lowCount > 0 ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-muted text-muted-foreground"}`}>
              <AlertTriangle className="size-3.5" />
            </div>
          </div>
          <div>
            <div className="flex items-baseline gap-1.5">
              <span className={`num font-mono text-3xl font-black tracking-tight ${lowCount > 0 ? "text-amber-600 dark:text-amber-400" : "text-foreground"}`}>
                <Num value={lowCount} />
              </span>
              <span className="text-xs font-bold text-muted-foreground">صنف بحاجة لتوريد</span>
            </div>
            <div className="mt-2 pt-2 border-t border-border/50 text-[11px]">
              <Link to="/inventory" className="text-primary hover:underline font-medium inline-flex items-center gap-1">
                {lowCount > 0 ? "عرض قائمة النواقص العاجلة ←" : "المخزون متزن بالكامل ✓"}
              </Link>
            </div>
          </div>
        </div>

        {/* KPI 4: Shift Status */}
        <div className="precision-surface flex flex-col justify-between rounded-xl p-4 gap-3">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">حالة الوردية</span>
            <div className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Clock className="size-3.5" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              {shift.data ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                  <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
                  الوردية نشطة
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-destructive/15 px-2.5 py-0.5 text-xs font-bold text-destructive">
                  الوردية مغلقة
                </span>
              )}
            </div>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/50 text-[11px]">
              <span className="text-muted-foreground truncate font-mono">
                {shift.data ? formatDateTime(shift.data.started_at) : "لا توجد وردية مفتوحة"}
              </span>
              <Link to="/shifts" className="text-primary hover:underline font-bold shrink-0">
                {shift.data ? "إدارة الوردية ←" : "فتح وردية ←"}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Bento Grid Row 2: Sales Velocity Sparkline ── */}
      <div className="precision-surface flex flex-col justify-between gap-3 rounded-2xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <TrendingUp className="size-4 text-primary" />
              <h2 className="text-xs font-bold text-foreground">منحنى المبيعات والنشاط (١٤ يوماً)</h2>
            </div>
            <p className="text-[11px] text-muted-foreground">
              تطور الإيراد اليومي خلال الأسبوعين الماضيين لتحديد نمط المبيعات وسرعة حركة الأصناف.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-mono">
              إجمالي الـ ١٤ يوماً: <strong className="num text-foreground"><Money value={trendTotal} /></strong>
            </span>
            <span className="text-border">·</span>
            <span className="text-xs text-muted-foreground font-mono">
              متوسط اليوم: <strong className="num text-foreground"><Money value={trendTotal / 14} /></strong>
            </span>
          </div>
        </div>

        <div className="pt-2">
          <Sparkline data={trend} className="h-20 w-full" />
        </div>

        <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground border-t border-border/40 pt-2">
          <span>قبل ١٤ يوماً</span>
          <span>قبل ٧ أيام</span>
          <span>اليوم</span>
        </div>
      </div>

      {/* ── Two-Column Operational Split Surface: Recent Ledger & Low Stock Requisition ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.5fr_1fr]">
        {/* Column 1: Live Transactions Ledger */}
        <section aria-label="أحدث الفواتير" className="precision-surface flex flex-col rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between border-b border-border/80 bg-card p-3.5">
            <div className="flex items-center gap-2">
              <Receipt className="size-4 text-primary" />
              <h2 className="text-xs font-bold text-foreground">أحدث الفواتير والعمليات</h2>
            </div>
            <Button
              variant="ghost"
              size="sm"
              nativeButton={false}
              render={<Link to="/sales" />}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              عرض سجل الفواتير بالكامل ←
            </Button>
          </div>

          <div className="flex-1 p-2">
            <ListState
              status={recent.isLoading ? "loading" : recent.isError ? "error" : "ready"}
              isEmpty={(recent.data?.length ?? 0) === 0}
              onRetry={() => recent.refetch()}
              emptyTitle="لا توجد مبيعات مسجلة"
              emptyDescription="ستظهر هنا العمليات لحظياً بمجرد إتمام أول بيع عبر الكاشير."
              emptyAction={
                <Button nativeButton={false} render={<Link to="/pos" />} size="sm">
                  <ShoppingCart data-icon="inline-start" className="size-3.5" />
                  ابدأ البيع الآن [F2]
                </Button>
              }
            >
              <TableShell>
                <Table>
                  <TableHeader>
                    <TableRow className="text-[11px] border-b border-border/60">
                      <TableHead>رقم الفاتورة</TableHead>
                      <TableHead>العميل</TableHead>
                      <TableHead className="text-end">الإجمالي</TableHead>
                      <TableHead>الحالة</TableHead>
                      <TableHead className="hidden sm:table-cell w-[170px] whitespace-nowrap">التوقيت</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {salesList.slice(0, 7).map((inv) => (
                      <TableRow key={inv.id} className="text-xs hover:bg-secondary/30 transition-colors">
                        <TableCell className="num font-mono font-bold text-foreground">
                          {inv.invoice_number}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {inv.customer_name ?? "عميل نقدي"}
                        </TableCell>
                        <TableCell className="text-end font-mono font-black text-foreground">
                          <Money value={Number(inv.total)} />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={inv.status} />
                        </TableCell>
                        <TableCell className="num font-mono hidden text-[11px] text-muted-foreground sm:table-cell whitespace-nowrap w-[170px]">
                          {formatDateTime(inv.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableShell>
            </ListState>
          </div>
        </section>

        {/* Column 2: Low-Stock & Reorder Station */}
        <section aria-label="نواقص المخزن" className="precision-surface flex flex-col rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between border-b border-border/80 bg-card p-3.5">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-amber-500" />
              <h2 className="text-xs font-bold text-foreground">
                النواقص العاجلة {lowCount > 0 && <span className="num font-mono text-muted-foreground">({lowCount})</span>}
              </h2>
            </div>
            <Button
              variant="outline"
              size="sm"
              nativeButton={false}
              render={<Link to="/purchases" />}
              className="tactile-btn text-xs"
            >
              + طلب شراء
            </Button>
          </div>

          <div className="flex-1 p-3">
            <ListState
              status={lowStock.isLoading ? "loading" : lowStock.isError ? "error" : "ready"}
              isEmpty={lowCount === 0}
              onRetry={() => lowStock.refetch()}
              emptyTitle="المخزون متزن تماماً"
              emptyDescription="كافة الأصناف المسجلة في هذا الفرع أعلى من حد الطلب الأدنى."
              emptyAction={
                <Button variant="outline" size="sm" nativeButton={false} render={<Link to="/inventory" />}>
                  فحص تفاصيل المخزون
                </Button>
              }
            >
              <ul className="divide-y divide-border/40 space-y-1">
                {(lowStock.data ?? []).slice(0, 6).map((p) => (
                  <li key={p.product_id} className="flex items-center justify-between gap-3 py-2 text-xs">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-bold text-foreground">{p.product_name}</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">وحدة القياس: {p.unit}</p>
                    </div>

                    <div className="flex items-center gap-2.5">
                      <div className="text-end">
                        <span className="num font-mono text-xs font-black text-destructive">
                          <Num value={p.current_qty} />
                        </span>
                        <span className="text-[10px] text-muted-foreground ms-1">{p.unit}</span>
                      </div>

                      <Button
                        nativeButton={false}
                        render={<Link to="/purchases" />}
                        variant="ghost"
                        size="sm"
                        className="text-[11px] text-primary hover:bg-primary/10 px-2 py-0.5"
                      >
                        طلب
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </ListState>
          </div>
        </section>
      </div>
    </div>
  );
}
