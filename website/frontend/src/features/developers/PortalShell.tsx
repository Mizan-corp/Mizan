/** The signed-in developer portal: side rail and header, like the owner panel's Shell. */
import { useState, type ComponentType } from "react";
import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { BookOpen, KeyRound, LogOut, Menu, UserRound, Users } from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/kit/sheet";
import { Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";
import { LanguageToggle } from "./DevHeader";
import { useDevI18n } from "./i18n";
import { DEV_BASE, devPath } from "./paths";
import { signOutDeveloper, useDeveloper } from "./session";

const NAV: { to: string; en: string; ar: string; icon: ComponentType<{ className?: string }>; end?: boolean }[] = [
  { to: "/portal", en: "Teams", ar: "الفرق", icon: Users, end: true },
  { to: "/portal/tokens", en: "CLI tokens", ar: "رموز سطر الأوامر", icon: KeyRound },
  { to: "/portal/account", en: "Account", ar: "حسابي", icon: UserRound },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { me } = useDeveloper();
  const { t } = useDevI18n();
  return (
    <div className="flex h-full flex-col border-e border-sidebar-border bg-sidebar text-sidebar-foreground">
      <NavLink to={devPath("/")} onClick={onNavigate} className="flex h-16 items-center gap-3 border-b border-sidebar-border px-5 transition hover:bg-sidebar-accent/50">
        <span className="flex size-9 items-center justify-center rounded-lg border border-sidebar-border/30 bg-sidebar-primary/20 p-1">
          <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="size-6" />
        </span>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate font-bold">{t("Mizan", "ميزان")}</span>
          <span className="truncate text-xs text-sidebar-foreground/60">{t("Developer portal", "بوابة المطورين")}</span>
        </div>
      </NavLink>

      <nav aria-label={t("Portal menu", "قائمة البوابة")} className="flex-1 overflow-y-auto px-3 py-4">
        <div className="flex flex-col gap-0.5">
          {NAV.map(({ to, en, ar, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={devPath(to)}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-2 focus-visible:outline-sidebar-ring",
                  isActive && "bg-sidebar-accent font-medium text-sidebar-accent-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={cn("size-4 shrink-0", isActive && "text-sidebar-primary")} />
                  <span className="truncate">{t(en, ar)}</span>
                </>
              )}
            </NavLink>
          ))}
          <NavLink
            to={devPath("/docs")}
            onClick={onNavigate}
            className="mt-3 flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          >
            <BookOpen className="size-4 shrink-0" />
            <span className="truncate">{t("Docs", "التوثيق")}</span>
          </NavLink>
        </div>
      </nav>

      <div className="shrink-0 border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5">
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-xs font-semibold">{me?.full_name}</div>
            <div className="code truncate text-[10px] text-sidebar-foreground/55" dir="ltr">{me?.email}</div>
          </div>
          <button
            type="button"
            onClick={() => void signOutDeveloper()}
            className="rounded-md p-1.5 text-sidebar-foreground/70 transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            title={t("Sign out", "تسجيل الخروج")}
            aria-label={t("Sign out", "تسجيل الخروج")}
          >
            <LogOut className="size-4 rtl:-scale-x-100" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PortalShell() {
  const { token, me, query } = useDeveloper();
  const { t, dir, isAr } = useDevI18n();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  if (!token) return <Navigate to={devPath(`/login?next=${encodeURIComponent(pathname)}`)} replace />;
  if (!me) {
    return (
      <div className="grid min-h-svh place-items-center bg-background">
        {query.isError ? <p className="text-sm text-muted-foreground">{t("Couldn't load your account. Reload the page.", "تعذر تحميل حسابك. أعد تحميل الصفحة.")}</p> : <Spinner />}
      </div>
    );
  }
  const rel = DEV_BASE && pathname.startsWith(DEV_BASE) ? pathname.slice(DEV_BASE.length) || "/" : pathname;
  const item = NAV.find((n) => n.to === rel);
  const section = item ? t(item.en, item.ar) : rel.startsWith("/portal/teams/") ? t("Team", "الفريق") : "";

  return (
    <div dir={dir} className="flex min-h-svh bg-background text-foreground">
      <aside className="sticky top-0 hidden h-svh w-64 shrink-0 lg:block">
        <Sidebar />
      </aside>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side={isAr ? "right" : "left"} className="w-72 p-0" showCloseButton={false}>
          <SheetTitle className="sr-only">{t("Portal menu", "قائمة البوابة")}</SheetTitle>
          <Sidebar onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/70 bg-card/90 px-4 backdrop-blur md:px-6">
          <div className="flex items-center gap-2">
            <button type="button" className="grid size-9 place-items-center rounded-md hover:bg-accent lg:hidden" onClick={() => setMenuOpen(true)} aria-label={t("Open the menu", "فتح القائمة")}>
              <Menu className="size-4" />
            </button>
            <span className="text-sm font-semibold text-foreground">{section}</span>
          </div>
          <span className="flex items-center gap-1">
            <LanguageToggle className="text-xs" />
          </span>
        </header>
        <main className="flex-1 px-4 py-6 md:px-6 lg:px-8">
          <div className="mx-auto max-w-[1100px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
