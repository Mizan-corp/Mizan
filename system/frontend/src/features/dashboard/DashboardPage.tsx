/**
 * PAGE CONTRACT
 * Page: صحيفة اليوم / لوحة التحكم (/)
 * Archetype: Linear / Raycast Precision Terminal archetype with Arab merchant craft (دفتر اليوم الفاخر)
 * User: مدير الفرع يفتح النظام في بداية اليوم لمسح أرقام اليوم بثوانٍ واتخاذ القرار الفوري
 * Primary information: the acting role's widgets, in the order its dashboard lists them.
 *
 * The widgets come from /settings/screens (ADR-006 phase 5): modules declare them in their
 * manifest, the activity (or the role's own layout, set in the builder) arranges them, and only
 * those the role's permissions allow are listed. Each renders from its module's index.ts.
 */
import { Suspense } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, LayoutDashboard, ShoppingCart, Sparkles } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Button } from "@/components/kit/button";
import { Skeleton } from "@/components/kit/skeleton";
import { SECTOR_BADGES } from "@/lib/plans";
import { cn } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { useBranch } from "@app/components/AppShell";
import { widgetComponent } from "@app/framework/registry";
import { useRoleScreens, type DashboardWidget } from "@app/lib/nav";
import { useTenantNav } from "@app/lib/tenant";

const SPAN: Record<string, string> = {
  s: "col-span-1",
  m: "col-span-1 sm:col-span-2",
  l: "col-span-1 sm:col-span-2 lg:col-span-4",
};

function WidgetFrame({ widget }: { widget: DashboardWidget }) {
  const Widget = widgetComponent(widget.id);
  const span = SPAN[widget.size ?? "s"] ?? SPAN.s;
  const height = widget.size === "s" || !widget.size ? "h-32" : "h-64";
  const unavailable = (
    <div className={cn("precision-surface flex items-center justify-center rounded-xl p-4 text-xs text-muted-foreground", height)}>
      تعذر عرض «{widget.label}»
    </div>
  );
  return (
    <div className={span} data-widget={widget.id}>
      {Widget ? (
        <ErrorBoundary fallback={unavailable}>
          <Suspense fallback={<Skeleton className={cn("w-full rounded-xl", height)} />}>
            <Widget />
          </Suspense>
        </ErrorBoundary>
      ) : (
        unavailable
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { branchName } = useBranch();
  const tenant = useAuth((s) => s.tenant);
  const { tenantTo } = useTenantNav();
  const screens = useRoleScreens();
  const widgets = screens.data?.dashboard ?? [];
  const home = screens.data?.home;
  const homeScreen = home && home !== "/" && home !== "/pos" ? screens.data?.screens.find((s) => s.path === home) : undefined;
  const sectorBadge = tenant?.sector ? SECTOR_BADGES[tenant.sector] : null;
  const canSell = screens.data?.screens.some((s) => s.path === "/pos");

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
              دفتر اليوم · {branchName}
            </h1>
            <span className="text-xs text-muted-foreground font-mono">({todayFormatted})</span>
          </div>
          <p className="text-xs text-muted-foreground">
            موجز النشاط اليومي كما يحتاجه دورك في العمل.
          </p>
        </div>

        {canSell && (
          <Button nativeButton={false} render={<Link to={tenantTo("/pos")} />} size="sm" className="font-bold text-xs shadow-xs gap-1.5">
            <ShoppingCart data-icon="inline-start" className="size-3.5" />
            <span>نقطة البيع</span>
            <kbd className="ms-1 rounded bg-primary-foreground/20 px-1.5 py-0.5 text-[10px] font-mono">F2</kbd>
          </Button>
        )}
      </div>

      {/* ── The role's main screen ── */}
      {homeScreen && (
        <div className="flex flex-col items-start justify-between gap-4 rounded-2xl border border-primary/30 bg-primary/[0.05] p-4 shadow-xs sm:p-5 md:flex-row md:items-center">
          <div className="min-w-0 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/20 text-primary">
                <Sparkles className="size-4" />
              </span>
              <span className="shrink-0 rounded-full border border-primary/30 bg-primary/20 px-2.5 py-0.5 font-mono text-[10px] font-bold text-primary">
                منظومة {sectorBadge || "النشاط"} التخصصية
              </span>
            </div>
            <h2 className="truncate text-sm font-extrabold text-foreground sm:text-base">{homeScreen.label}</h2>
            <p className="text-xs leading-relaxed text-muted-foreground">الشاشة الرئيسية لدورك في هذا النشاط.</p>
          </div>
          <Button nativeButton={false} render={<Link to={tenantTo(homeScreen.path)} />} size="sm" className="h-9 w-full gap-2 px-4 text-xs font-bold shadow-xs md:w-auto">
            <span>فتح {homeScreen.label}</span>
            <ArrowLeft className="size-3.5" />
          </Button>
        </div>
      )}

      {/* ── The role's widgets ── */}
      {screens.isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true" aria-label="جارٍ تحميل اللوحة">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
      ) : screens.isError ? (
        <div className="precision-surface flex flex-col items-center gap-3 rounded-2xl p-8 text-center">
          <p className="text-sm text-destructive">تعذر تحميل لوحة التحكم.</p>
          <Button variant="outline" size="sm" onClick={() => screens.refetch()}>إعادة المحاولة</Button>
        </div>
      ) : widgets.length === 0 ? (
        <div className="precision-surface flex flex-col items-center gap-2 rounded-2xl p-8 text-center">
          <LayoutDashboard className="size-6 text-muted-foreground" />
          <p className="text-sm font-bold text-foreground">لا توجد مؤشرات لدورك</p>
          <p className="text-xs text-muted-foreground">استخدم القائمة للوصول إلى شاشاتك، أو اطلب من المالك إضافة مؤشرات إلى لوحة دورك.</p>
        </div>
      ) : (
        <section aria-label="المؤشرات" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {widgets.map((w) => <WidgetFrame key={w.id} widget={w} />)}
        </section>
      )}
    </div>
  );
}
