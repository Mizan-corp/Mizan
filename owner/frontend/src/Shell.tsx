import { useState, type ComponentType } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Building2, LogOut, Menu, ReceiptText, UserRound } from "lucide-react";
import { MizanLogo } from "@/components/MizanLogo";
import { Avatar, AvatarFallback } from "@/components/kit/avatar";
import { Button } from "@/components/kit/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/kit/sheet";
import { cn } from "@/lib/utils";
import { appUrl } from "@/lib/urls";
import { useMe } from "@app/lib/data";
import { signOut } from "@app/lib/session";
import { VerifyEmailBanner } from "@app/components/VerifyEmail";

const NAV: { to: string; label: string; icon: ComponentType<{ className?: string }>; end?: boolean; tour?: string }[] = [
  { to: "/", label: "مساحات العمل", icon: Building2, end: true },
  { to: "/invoices", label: "الفواتير", icon: ReceiptText, tour: "nav-invoices" },
  { to: "/account", label: "حسابي", icon: UserRound },
];

/** The side rail, built like the app's (AppSidebar). */
function Sidebar({ onNavigate, tour }: { onNavigate?: () => void; tour?: boolean }) {
  const me = useMe();
  return (
    <div className="flex h-full flex-col border-e border-sidebar-border bg-sidebar text-sidebar-foreground">
      <NavLink to="/" onClick={onNavigate} className="flex h-16 items-center gap-3 border-b border-sidebar-border px-5 transition hover:bg-sidebar-accent/50">
        <span className="flex size-9 items-center justify-center rounded-lg border border-sidebar-border/30 bg-sidebar-primary/20 p-1">
          {/* The drawer copy can't use <MizanLogo>: its SVG gradient ids would resolve to the hidden rail. */}
          {tour ? <MizanLogo size="sm" variant="icon" theme="dark" /> : <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="size-6" />}
        </span>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate font-bold">ميزان</span>
          <span className="truncate text-xs text-sidebar-foreground/60">لوحة المالك</span>
        </div>
      </NavLink>

      <nav aria-label="القائمة الرئيسية" className="flex-1 overflow-y-auto px-3 py-4">
        <p className="px-3 pb-1 text-[11px] font-medium text-sidebar-foreground/50">حسابك على ميزان</p>
        <div className="flex flex-col gap-0.5">
          {NAV.map(({ to, label, icon: Icon, end, tour: t }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onNavigate}
              data-tour={tour ? t : undefined}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-2 focus-visible:outline-sidebar-ring",
                  isActive && "bg-sidebar-accent font-medium text-sidebar-accent-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={cn("size-4 shrink-0", isActive && "text-sidebar-primary")} aria-hidden />
                  <span className="truncate">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      <div className="shrink-0 border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5">
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-xs font-semibold">{me.data?.full_name}</div>
            <div className="code truncate text-[10px] text-sidebar-foreground/55">{me.data?.login}</div>
          </div>
          <button
            onClick={signOut}
            className="rounded-md p-1.5 text-sidebar-foreground/70 transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            title="تسجيل الخروج"
            aria-label="تسجيل الخروج"
          >
            <LogOut className="size-4 rtl:-scale-x-100" />
          </button>
        </div>
        <p className="mt-1 px-2 text-[10px] text-sidebar-foreground/50">المدفوعات تتم بأمان عبر Paymob</p>
      </div>
    </div>
  );
}

const TITLES: Record<string, string> = { "/": "مساحات العمل", "/invoices": "الفواتير", "/account": "حسابي" };

export default function Shell() {
  const me = useMe();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const section = TITLES[pathname] ?? (pathname.startsWith("/workspaces") ? "مساحة العمل" : pathname.startsWith("/payment") ? "الدفع" : "");

  return (
    <div className="flex min-h-svh bg-background text-foreground">
      <aside className="sticky top-0 hidden h-svh w-64 shrink-0 lg:block">
        <Sidebar tour />
      </aside>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="right" className="w-72 p-0" showCloseButton={false}>
          <SheetTitle className="sr-only">القائمة الرئيسية</SheetTitle>
          <Sidebar onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/70 bg-card/90 px-4 backdrop-blur md:px-6">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMenuOpen(true)} aria-label="فتح القائمة">
              <Menu className="size-4" />
            </Button>
            {/* An <img>, not <MizanLogo>: its SVG gradient ids would point into the hidden side rail. */}
            <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="ميزان" className="size-8 lg:hidden" />
            <span className="text-sm font-semibold text-foreground">{section}</span>
          </div>
          <div className="flex items-center gap-2">
            <a href={appUrl("website", "/")} className="hidden rounded-lg px-2 py-1 text-xs text-muted-foreground hover:bg-muted/50 hover:text-foreground sm:block">
              موقع ميزان
            </a>
            <div className="flex h-9 items-center gap-2 rounded-lg px-2">
              <Avatar className="size-7 ring-1 ring-border">
                <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">
                  {(me.data?.full_name ?? "؟").split(" ")[0].slice(0, 2)}
                </AvatarFallback>
              </Avatar>
              <span className="hidden flex-col items-start leading-tight md:flex">
                <span className="text-xs font-semibold text-foreground">{me.data?.full_name}</span>
                <span className="text-[10px] text-muted-foreground">مالك</span>
              </span>
            </div>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 md:px-6 lg:px-8">
          <div className="mx-auto max-w-[1180px]">
            {pathname !== "/account" && <VerifyEmailBanner />}
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
