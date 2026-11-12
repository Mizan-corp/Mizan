import { useState, type ComponentType } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Activity, Building2, Contact, CreditCard, Gauge, LogOut, Menu, ServerCog, Users } from "lucide-react";
import { MizanLogo } from "@/components/MizanLogo";
import { Avatar, AvatarFallback } from "@/components/kit/avatar";
import { Button } from "@/components/kit/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/kit/sheet";
import { signOutSession } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { cn } from "@/lib/utils";
import { appUrl } from "@/lib/urls";
import { useBilling, useOverview } from "@app/lib/data";

type Item = { to: string; label: string; icon: ComponentType<{ className?: string }>; end?: boolean; count?: number };

/** The side rail, built like the app's (AppSidebar). */
function Sidebar({ onNavigate, primary }: { onNavigate?: () => void; primary?: boolean }) {
  const user = useAuth((s) => s.user);
  const overview = useOverview();
  const billing = useBilling();

  const groups: { label: string; items: Item[] }[] = [
    {
      label: "Customers",
      items: [
        { to: "/", label: "Overview", icon: Gauge, end: true, count: overview.data?.attention.length },
        { to: "/workspaces", label: "Workspaces", icon: Building2 },
        { to: "/owners", label: "Owners", icon: Contact },
        { to: "/billing", label: "Billing", icon: CreditCard, count: billing.data?.summary.pending_count },
        { to: "/activity", label: "Activity", icon: Activity },
      ],
    },
    {
      label: "Platform",
      items: [
        { to: "/team", label: "Team", icon: Users },
        { to: "/system", label: "System", icon: ServerCog },
      ],
    },
  ];

  return (
    <div className="flex h-full flex-col border-e border-sidebar-border bg-sidebar text-sidebar-foreground">
      <NavLink to="/" onClick={onNavigate} className="flex h-16 items-center gap-3 border-b border-sidebar-border px-5 transition hover:bg-sidebar-accent/50">
        <span className="flex size-9 items-center justify-center rounded-lg border border-sidebar-border/30 bg-sidebar-primary/20 p-1">
          {/* The drawer copy can't use <MizanLogo>: its SVG gradient ids would resolve to the hidden rail. */}
          {primary ? <MizanLogo size="sm" variant="icon" theme="dark" /> : <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="size-6" />}
        </span>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate font-bold">Mizan</span>
          <span className="truncate text-xs text-sidebar-foreground/60">Admin panel</span>
        </div>
      </NavLink>

      <nav aria-label="Main" className="flex-1 overflow-y-auto px-3 py-4">
        <div className="flex flex-col gap-4">
          {groups.map((g) => (
            <div key={g.label}>
              <p className="px-3 pb-1 text-[11px] font-medium text-sidebar-foreground/50">{g.label}</p>
              <div className="flex flex-col gap-0.5">
                {g.items.map(({ to, label, icon: Icon, end, count }) => (
                  <NavLink
                    key={to}
                    to={to}
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
                        <Icon className={cn("size-4 shrink-0", isActive && "text-sidebar-primary")} aria-hidden />
                        <span className="flex-1 truncate">{label}</span>
                        {!!count && (
                          <span className="data rounded-full bg-sidebar-primary px-1.5 text-[10px] font-semibold text-sidebar-primary-foreground">
                            {count}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </div>
      </nav>

      <div className="shrink-0 border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5">
          <div className="bidi min-w-0 flex-1 leading-tight">
            <div className="truncate text-xs font-semibold">{user?.full_name}</div>
            <div className="code truncate text-[10px] text-sidebar-foreground/55">@{user?.username}</div>
          </div>
          <button
            onClick={() => signOutSession()}
            className="rounded-md p-1.5 text-sidebar-foreground/70 transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            title="Sign out"
            aria-label="Sign out"
          >
            <LogOut className="size-4" />
          </button>
        </div>
        <a href={appUrl("website", "/")} className="mt-1 block px-2 text-[10px] text-sidebar-foreground/50 hover:text-sidebar-foreground">
          Go to the Mizan website ↗
        </a>
      </div>
    </div>
  );
}

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Overview"],
  [/^\/workspaces/, "Workspaces"],
  [/^\/owners/, "Owners"],
  [/^\/billing/, "Billing"],
  [/^\/activity/, "Activity"],
  [/^\/team/, "Team"],
  [/^\/system/, "System"],
];

export default function Shell() {
  const user = useAuth((s) => s.user);
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const section = TITLES.find(([re]) => re.test(pathname))?.[1] ?? "";

  return (
    <div className="flex min-h-svh bg-background text-foreground">
      <aside className="sticky top-0 hidden h-svh w-64 shrink-0 lg:block">
        <Sidebar primary />
      </aside>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-72 p-0" showCloseButton={false}>
          <SheetTitle className="sr-only">Main menu</SheetTitle>
          <Sidebar onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/70 bg-card/90 px-4 backdrop-blur md:px-6">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Open menu">
              <Menu className="size-4" />
            </Button>
            <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="Mizan" className="size-8 lg:hidden" />
            <span className="text-sm font-semibold text-foreground">{section}</span>
          </div>
          <div className="flex h-9 items-center gap-2 rounded-lg px-2">
            <Avatar className="size-7 ring-1 ring-border">
              <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">
                {(user?.full_name || user?.username || "?").slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <span className="hidden flex-col items-start leading-tight md:flex">
              <span className="bidi text-xs font-semibold text-foreground">{user?.full_name}</span>
              <span className="text-[10px] text-muted-foreground">Mizan team</span>
            </span>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 md:px-6 lg:px-8">
          <div className="mx-auto max-w-[1180px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
