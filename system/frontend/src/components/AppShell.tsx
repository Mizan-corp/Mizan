import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  Clock,
  LogOut,
  Menu,
  Search,
  Settings,
  ShieldCheck,
  Blocks,
  Palette,
  ChevronDown,
  Volume2,
  VolumeX,
  Cpu,
  Globe,
} from "lucide-react";
import { api } from "@/lib/api";
import { NAV_ITEMS, getSectorNavigation } from "@app/lib/nav";
import { SECTOR_BADGES, SECTOR_PRIMARY_ROUTES } from "@/lib/plans";
import { cn } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { useModulesStore } from "@app/stores/modules";
import { useI18nStore } from "@/i18n";
import { AutomationWorkerModal } from "@app/platform/automation_worker/AutomationWorkerModal";
import { MizanAppLauncher } from "@app/components/MizanAppLauncher";
import { MizanLogo } from "@/components/MizanLogo";
import { Avatar, AvatarFallback } from "@/components/kit/avatar";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/kit/dropdown-menu";
import { Sheet, SheetContent, SheetTitle } from "@/components/kit/sheet";
import { PageTransition } from "@/components/motion";
import { dateTime } from "@/lib/format";
import { CommandPalette, TrialBanner, useHotkeySearch } from "@app/components/shell-parts";
import { OnPremLicenceBanner } from "@app/components/OnPremLicenceBanner";
import { useUiStore } from "@/stores/ui";
import { sound } from "@/lib/sound";
import { Kbd } from "@/components/kit/kbd";
import { AppearanceSettingsModal } from "@app/components/AppearanceSettingsModal";
import { NotificationCenter } from "@app/components/NotificationCenter";
import { useTenantNav } from "@app/lib/tenant";

interface Warehouse {
  id: string;
  name: string;
  kind?: string;
}

export function useBranch() {
  const user = useAuth((s) => s.user);
  const { data } = useQuery<Warehouse[]>({
    queryKey: ["warehouses"],
    queryFn: () => api.get<Warehouse[]>("/stock/warehouses"),
    staleTime: 5 * 60_000,
  });
  const [branchId, setBranchState] = useState<string | null>(() => localStorage.getItem("mizan.branch") ?? localStorage.getItem("vendora.branch"));

  useEffect(() => {
    const handleStorage = () => {
      const stored = localStorage.getItem("mizan.branch") ?? localStorage.getItem("vendora.branch");
      if (stored) setBranchState(stored);
    };
    window.addEventListener("storage", handleStorage);
    window.addEventListener("mizan-branch-changed", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("mizan-branch-changed", handleStorage);
    };
  }, []);

  const setBranchId = (id: string | null) => {
    if (id) {
      localStorage.setItem("mizan.branch", id);
      localStorage.setItem("vendora.branch", id);
    } else {
      localStorage.removeItem("mizan.branch");
      localStorage.removeItem("vendora.branch");
    }
    setBranchState(id);
    window.dispatchEvent(new Event("mizan-branch-changed"));
  };

  const current = data?.find((w: Warehouse) => w.id === branchId) ?? data?.find((w: Warehouse) => w.id === user?.default_warehouse_id) ?? data?.[0];
  return { warehouses: data ?? [], branchId: current?.id ?? null, branchName: current?.name ?? "…", setBranchId };
}

/* ── 1. Classic Full Sidebar (Tree View) ── */
function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { can, tenant } = useAuth();
  const { hasModule, activePreset, presets } = useModulesStore();
  const { tenantTo, isPathActive } = useTenantNav();
  const currentPreset = presets.find((p) => p.id === activePreset);
  const tenantTrialEnds = tenant?.trial_ends_at
    ? new Intl.DateTimeFormat("ar-EG-u-nu-latn", { day: "numeric", month: "long" }).format(new Date(tenant.trial_ends_at))
    : "";

  const sectorBadge = tenant?.sector ? SECTOR_BADGES[tenant.sector] : null;
  const isSpecializedSector = Boolean(tenant?.sector && [
    "healthcare", "restaurant", "pharmacy", "school", "gym", "salon",
    "hotel", "wholesale", "construction", "manufacturing", "food",
    "pharmaceuticals", "property", "maintenance", "travel", "logistics", "warehousing",
  ].includes(tenant.sector));
  const sectorPrimaryPath = tenant?.sector ? SECTOR_PRIMARY_ROUTES[tenant.sector] : null;
  const sectorFeaturedItem = !isSpecializedSector && sectorPrimaryPath && sectorPrimaryPath !== "/" && sectorPrimaryPath !== "/pos"
    ? NAV_ITEMS.find((n) => n.to === sectorPrimaryPath)
    : null;

  const groups = getSectorNavigation(tenant?.sector, can, hasModule);

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground border-e border-sidebar-border">
      <Link
        to={tenantTo("/")}
        onClick={onNavigate}
        className="flex h-16 items-center gap-3 border-b border-sidebar-border px-5 transition hover:bg-sidebar-accent/50"
      >
        <span className="flex size-9 items-center justify-center rounded-lg bg-sidebar-primary/20 p-1 border border-sidebar-border/30">
          <MizanLogo size="sm" variant="icon" theme="dark" />
        </span>
        <div className="flex flex-col leading-tight min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-bold truncate max-w-[125px]">{tenant?.name ?? "ميزان"}</span>
            {sectorBadge ? (
              <span className="rounded bg-primary/20 px-1.5 py-0.5 text-[9px] font-bold text-primary shrink-0 border border-primary/30">
                {sectorBadge.split(" ")[0]}
              </span>
            ) : currentPreset ? (
              <span className="rounded bg-sidebar-primary/20 px-1.5 py-0.5 text-[9px] font-bold text-sidebar-primary shrink-0">
                {currentPreset.name.split(" ")[0]}
              </span>
            ) : null}
          </div>
          <span className="truncate text-xs text-sidebar-foreground/60">{tenant?.slug ? `/${tenant.slug}` : "مساحة العمل"}</span>
        </div>
      </Link>
      <nav aria-label="القائمة الرئيسية" className="flex-1 overflow-y-auto px-3 py-4">
        <div className="flex flex-col gap-4">
          {/* Sector Highlight Banner if vertical business */}
          {sectorFeaturedItem && (
            <div className="rounded-xl border border-primary/30 bg-primary/5 p-2 shadow-xs mb-1">
              <div className="flex items-center justify-between pb-1 px-1">
                <span className="text-[10px] font-bold text-primary flex items-center gap-1">
                  <span>منظومة النشاط التخصصية</span>
                </span>
                <span className="rounded-full bg-primary/20 px-1.5 py-0.2 text-[9px] font-bold text-primary">
                  {sectorBadge ? sectorBadge.split(" ")[0] : "مخصصة"} ✓
                </span>
              </div>
              <Link
                to={tenantTo(sectorFeaturedItem.to)}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs font-bold transition-all",
                  isPathActive(sectorFeaturedItem.to)
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "bg-sidebar-accent/80 hover:bg-sidebar-accent text-sidebar-foreground border border-sidebar-border/40"
                )}
              >
                <sectorFeaturedItem.icon className={cn("size-4 shrink-0", isPathActive(sectorFeaturedItem.to) ? "text-primary-foreground" : "text-primary")} />
                <span className="truncate">{sectorFeaturedItem.label}</span>
              </Link>
            </div>
          )}

          {groups.map((group) => (
            <div key={group.id} className="flex flex-col gap-1">
              <p className="px-3 pb-1 text-[11px] font-medium text-sidebar-foreground/50">{group.label}</p>
              {group.items.map((item) => {
                const active = isPathActive(item.to);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.to}
                    to={tenantTo(item.to)}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-2 focus-visible:outline-sidebar-ring",
                      active && "bg-sidebar-accent font-medium text-sidebar-accent-foreground",
                    )}
                  >
                    <Icon className={cn("size-4 shrink-0", active && "text-sidebar-primary")} aria-hidden />
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </div>
      </nav>
      {/* Pinned quick access footer for compact displays */}
      <div className="shrink-0 border-t border-sidebar-border bg-sidebar/95 p-3 backdrop-blur">
        <div className="mb-2 flex items-center justify-between gap-1">
          {can("settings") && (
            <Link
              to={tenantTo("/modules")}
              onClick={onNavigate}
              className={cn(
                "flex flex-1 items-center justify-center gap-1 rounded-md py-1.5 text-[11px] font-medium transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                isPathActive("/modules") ? "bg-sidebar-accent text-sidebar-accent-foreground font-semibold" : "text-sidebar-foreground/70"
              )}
              title="سوق الوحدات والأنشطة"
            >
              <Blocks className="size-3" />
              <span>الوحدات</span>
            </Link>
          )}

          {can("settings") && (
            <Link
              to={tenantTo("/settings")}
              onClick={onNavigate}
              className={cn(
                "flex flex-1 items-center justify-center gap-1 rounded-md py-1.5 text-[11px] font-medium transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                isPathActive("/settings") ? "bg-sidebar-accent text-sidebar-accent-foreground font-semibold" : "text-sidebar-foreground/70"
              )}
              title="إعدادات المتجر والنظام"
            >
              <Settings className="size-3" />
              <span>الإعدادات</span>
            </Link>
          )}

          {can("users") && (
            <Link
              to={tenantTo("/users")}
              onClick={onNavigate}
              className={cn(
                "flex flex-1 items-center justify-center gap-1 rounded-md py-1.5 text-[11px] font-medium transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                isPathActive("/users") ? "bg-sidebar-accent text-sidebar-accent-foreground font-semibold" : "text-sidebar-foreground/70"
              )}
              title="المستخدمون والصلاحيات"
            >
              <ShieldCheck className="size-3" />
              <span>المستخدمون</span>
            </Link>
          )}
        </div>

        {tenant?.plan === "trial" && (
          <Link to="/pricing" className="mb-2 block rounded-xl bg-sidebar-primary/15 p-2.5 ring-1 ring-sidebar-primary/30 transition hover:bg-sidebar-primary/25">
            <p className="text-xs font-bold text-sidebar-foreground">فعّل خطتك</p>
            <p className="mt-0.5 text-[10px] leading-4 text-sidebar-foreground/70">
              النسخة التجريبية حتى {tenantTrialEnds} — بياناتك محفوظة
            </p>
          </Link>
        )}
        <p className="px-1 text-[10px] text-sidebar-foreground/50">
          ميزان <span className="num">3.0</span> — نظام إدارة التجار
        </p>
      </div>
    </div>
  );
}

/* ── 2. Compact Icon Rail (High-Density Screen Real Estate) ── */
function AppRail({ onNavigate }: { onNavigate?: () => void }) {
  const { can, tenant } = useAuth();
  const { hasModule } = useModulesStore();
  const { tenantTo, isPathActive } = useTenantNav();
  const setAppearanceModalOpen = useUiStore((s) => s.setAppearanceModalOpen);

  const groups = getSectorNavigation(tenant?.sector, can, hasModule);
  const visible = groups.flatMap((g) => g.items);

  return (
    <div className="flex h-full w-16 flex-col items-center bg-sidebar text-sidebar-foreground border-e border-sidebar-border py-3">
      {/* Brand Icon */}
      <Link
        to={tenantTo("/")}
        className="mb-4 flex size-10 items-center justify-center rounded-lg bg-sidebar-primary/20 p-1 border border-sidebar-border/30 shadow-xs transition hover:scale-105"
        title="ميزان ERP"
      >
        <MizanLogo size="sm" variant="icon" theme="dark" />
      </Link>

      {/* Nav Icons */}
      <nav className="flex flex-1 flex-col items-center gap-1.5 overflow-y-auto px-2">
        {visible.map((item) => {
          const active = isPathActive(item.to);
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={tenantTo(item.to)}
              onClick={onNavigate}
              title={item.label}
              className={cn(
                "group relative flex size-10 items-center justify-center rounded-lg text-sidebar-foreground/75 transition-all hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                active && "bg-sidebar-accent font-semibold text-sidebar-accent-foreground shadow-xs ring-1 ring-sidebar-primary/40"
              )}
            >
              <Icon className={cn("size-5", active && "text-sidebar-primary")} />
              {/* Subtle active pill indicator on edge */}
              {active && <span className="absolute -inline-end-2 h-5 w-1 rounded-full bg-sidebar-primary" />}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Pinned Controls */}
      <div className="flex flex-col items-center gap-2 pt-2 border-t border-sidebar-border/60">
        <button
          onClick={() => setAppearanceModalOpen(true)}
          title="تخصيص المظهر والتخطيط"
          className="flex size-9 items-center justify-center rounded-lg text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition"
        >
          <Palette className="size-4" />
        </button>
      </div>
    </div>
  );
}

/* ── 3. Horizontal Top Navigation Bar (ERP Menu Bar) ── */
function AppTopNav() {
  const { can, tenant } = useAuth();
  const { hasModule } = useModulesStore();
  const { tenantTo, isPathActive } = useTenantNav();

  const groups = getSectorNavigation(tenant?.sector, can, hasModule);

  return (
    <div className="no-print hidden lg:flex items-center gap-1 border-b border-border/80 bg-card px-6 py-1.5 text-xs">
      <Link
        to={tenantTo("/")}
        className={cn(
          "px-2.5 py-1 rounded font-medium transition hover:bg-muted",
          isPathActive("/") ? "bg-primary text-primary-foreground font-semibold" : "text-foreground"
        )}
      >
        لوحة التحكم
      </Link>

      {groups.map((group) => {
        const hasActiveItem = group.items.some((item) => isPathActive(item.to));
        return (
          <DropdownMenu key={group.id}>
            <DropdownMenuTrigger
              render={
                <button
                  className={cn(
                    "flex items-center gap-1 px-2.5 py-1 rounded font-medium transition hover:bg-muted",
                    hasActiveItem ? "bg-accent text-accent-foreground font-semibold" : "text-muted-foreground hover:text-foreground"
                  )}
                />
              }
            >
              <span>{group.label}</span>
              <ChevronDown className="size-3 opacity-60" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-48">
              <DropdownMenuGroup>
                <DropdownMenuLabel>{group.label}</DropdownMenuLabel>
                {group.items.map((item) => {
                  const active = isPathActive(item.to);
                  const Icon = item.icon;
                  return (
                    <DropdownMenuItem key={item.to} render={<Link to={tenantTo(item.to)} />}>
                      <Icon className={cn("size-4 me-2", active && "text-primary")} />
                      <span className={cn(active && "font-semibold text-primary")}>{item.label}</span>
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      })}
    </div>
  );
}

function AppTopbar({ onOpenMenu, onOpenSearch }: { onOpenMenu: () => void; onOpenSearch: () => void }) {
  const navigate = useNavigate();
  const { user, tenant, logout } = useAuth();
  const { warehouses, branchId, branchName, setBranchId } = useBranch();
  const { density, toggleDensity, soundMuted, toggleSound, setAppearanceModalOpen } = useUiStore();
  const { locale, toggleLocale } = useI18nStore();
  const [automationOpen, setAutomationOpen] = useState(false);

  const shift = useQuery({
    queryKey: ["shift", "topbar", branchId],
    queryFn: () => api.get<{ id: string; started_at: string } | null>("/shifts/current", { warehouse_id: branchId! }),
    enabled: !!branchId,
    retry: false,
    refetchInterval: 60_000,
  });

  const { tenantTo } = useTenantNav();

  // Global F2 shortcut to jump to POS from any screen
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "F2" && !window.location.pathname.endsWith("/pos")) {
        e.preventDefault();
        sound.click();
        navigate(tenantTo("/pos"));
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate, tenantTo]);

  return (
    <header className="no-print sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/70 bg-card/90 px-4 backdrop-blur md:px-6">
      {/* Zone 1: Mobile toggle + App Launcher + Branch Selector */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={onOpenMenu} aria-label="فتح القائمة">
          <Menu className="size-4" />
        </Button>

        <MizanAppLauncher />

        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="outline" size="sm" className="h-8 gap-1.5 px-2.5 font-medium border-border/80 hover:bg-muted/50" />}>
            <Building2 className="size-3.5 text-primary" data-icon="inline-start" />
            <span className="max-w-32 truncate text-xs font-semibold">{branchName}</span>
            <ChevronDown className="size-3 opacity-50" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuGroup>
              <DropdownMenuLabel>الفروع والمخازن</DropdownMenuLabel>
              <DropdownMenuRadioGroup
                value={branchId ?? ""}
                onValueChange={(v) => {
                  sound.click();
                  localStorage.setItem("mizan.branch", String(v));
                  setBranchId(String(v));
                }}
              >
                {warehouses.map((b: Warehouse) => (
                  <DropdownMenuRadioItem key={b.id} value={b.id}>
                    {b.name}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Active Shift Indicator */}
        <Link to={tenantTo("/shifts")} className="hidden sm:block">
          {shift.data ? (
            <Badge variant="success" className="h-7 gap-1.5 px-2.5 text-[11px] font-semibold">
              <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" aria-hidden />
              وردية نشطة · <span className="num">{dateTime(shift.data.started_at)}</span>
            </Badge>
          ) : (
            <Badge variant="secondary" className="h-7 gap-1.5 px-2.5 text-[11px] text-muted-foreground hover:text-foreground">
              <Clock className="size-3" aria-hidden />
              بدون وردية
            </Badge>
          )}
        </Link>
      </div>

      {/* Zone 2: Centered Global Command Search */}
      <div className="flex-1 max-w-md mx-4 hidden md:block">
        <button
          onClick={onOpenSearch}
          className="flex h-9 w-full items-center gap-2 rounded-lg border border-border/80 bg-background/60 px-3 text-xs text-muted-foreground transition hover:border-border hover:bg-background hover:text-foreground shadow-2xs"
          aria-label="بحث شامل (Ctrl+K)"
        >
          <Search className="size-3.5 text-muted-foreground/70" aria-hidden />
          <span className="flex-1 text-start">ابحث أو أمر…</span>
          <Kbd className="text-[10px] bg-muted/60 text-muted-foreground border-border/60">⌘K</Kbd>
        </button>
      </div>

      {/* Zone 3: Mobile search + Notifications + Unified User Profile Menu */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-8 w-8 md:hidden" onClick={onOpenSearch} aria-label="بحث شامل">
          <Search className="size-4" />
        </Button>

        {/* Live In-App Notification Center */}
        <NotificationCenter />

        {/* Unified User Preferences & Profile Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" className="h-9 gap-2 px-2 hover:bg-muted/50 rounded-lg" />} aria-label="قائمة المستخدم">
            <Avatar className="size-7 ring-1 ring-border">
              <AvatarFallback className="text-xs font-semibold bg-primary/10 text-primary">{(user?.full_name ?? "؟").split(" ")[0].slice(0, 2)}</AvatarFallback>
            </Avatar>
            <span className="hidden flex-col items-start leading-tight md:flex">
              <span className="text-xs font-semibold text-foreground">{user?.full_name}</span>
              <span className="text-[10px] text-muted-foreground">{tenant?.name ?? user?.role}</span>
            </span>
            <ChevronDown className="size-3 text-muted-foreground/60 hidden md:block" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64 p-1.5 shadow-lg">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-xs font-semibold px-2 py-1.5">
                <p className="font-bold text-foreground">{user?.full_name}</p>
                <p className="text-[10px] text-muted-foreground font-normal">{user?.username} · {user?.role}</p>
              </DropdownMenuLabel>
              <div className="h-px bg-border/60 my-1" />

              <DropdownMenuItem onClick={() => navigate(tenantTo("/settings"))}>
                <Settings className="size-4" />
                <span>إعدادات النظام العامة</span>
              </DropdownMenuItem>

              <DropdownMenuItem onClick={() => setAppearanceModalOpen(true)}>
                <Palette className="size-4" />
                <span>تخصيص المظهر والثيمات</span>
              </DropdownMenuItem>

              <DropdownMenuItem onClick={toggleDensity}>
                <Clock className="size-4 opacity-70" />
                <span>كثافة الواجهة ({density === "compact" ? "كثيف ✓" : "مريح ✓"})</span>
              </DropdownMenuItem>

              <DropdownMenuItem onClick={toggleSound}>
                {soundMuted ? <VolumeX className="size-4 text-muted-foreground" /> : <Volume2 className="size-4 text-primary" />}
                <span>المؤثرات الصوتية ({soundMuted ? "مكتومة" : "مفعلة"})</span>
              </DropdownMenuItem>

              <DropdownMenuItem onClick={() => { sound.click(); toggleLocale(); }}>
                <Globe className="size-4" />
                <span>اللغة ({locale === "ar" ? "العربية" : "English"})</span>
              </DropdownMenuItem>

              <DropdownMenuItem onClick={() => { sound.click(); setAutomationOpen(true); }}>
                <Cpu className="size-4 text-indigo-500" />
                <span>جدولة الأتمتة (Cron Worker)</span>
              </DropdownMenuItem>

              <div className="h-px bg-border/60 my-1" />

              <DropdownMenuItem
                variant="destructive"
                onClick={() => {
                  sound.click();
                  logout();
                  navigate(tenantTo("/login"), { replace: true });
                }}
              >
                <LogOut className="size-4" />
                <span>تسجيل الخروج</span>
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <AutomationWorkerModal isOpen={automationOpen} onClose={() => setAutomationOpen(false)} />
    </header>
  );
}

export default function Shell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const pathname = useLocation().pathname;
  const fetchModules = useModulesStore((s) => s.fetchModules);
  const { layoutMode, appearanceModalOpen, setAppearanceModalOpen } = useUiStore();

  useEffect(() => {
    fetchModules();
  }, [fetchModules]);

  useHotkeySearch(() => setSearchOpen(true));

  return (
    <div className="flex min-h-svh bg-background text-foreground">
      {/* Sidebar Layout Mode */}
      {layoutMode === "sidebar" && (
        <aside className="no-print sticky top-0 hidden h-svh w-64 shrink-0 lg:block">
          <AppSidebar />
        </aside>
      )}

      {/* Rail Layout Mode */}
      {layoutMode === "rail" && (
        <aside className="no-print sticky top-0 hidden h-svh w-16 shrink-0 lg:block">
          <AppRail />
        </aside>
      )}

      {/* Mobile Drawer (Always Available on Small Screens) */}
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="right" className="w-72 p-0" showCloseButton={false}>
          <SheetTitle className="sr-only">القائمة الرئيسية</SheetTitle>
          <AppSidebar onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar onOpenMenu={() => setMenuOpen(true)} onOpenSearch={() => setSearchOpen(true)} />
        {layoutMode === "topnav" && <AppTopNav />}
        <TrialBanner />
        <OnPremLicenceBanner />
        <CommandPalette open={searchOpen} onOpenChange={setSearchOpen} />
        <AppearanceSettingsModal open={appearanceModalOpen} onOpenChange={setAppearanceModalOpen} />
        <main className="flex-1 px-4 py-6 md:px-6 lg:px-8">
          <PageTransition routeKey={pathname}>
            <Outlet />
          </PageTransition>
        </main>
      </div>
    </div>
  );
}
