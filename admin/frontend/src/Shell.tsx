import { type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Activity, Building2, CreditCard, Gauge, LogOut, ServerCog, Users } from "lucide-react";
import { useAuth } from "@/stores/auth";
import { cn } from "@/lib/utils";
import { appUrl } from "@/lib/urls";
import { useBilling, useOverview } from "@app/lib/data";

function Mark() {
  // The Mizan scale reduced to a beam and two pans.
  return (
    <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
      <rect width="32" height="32" rx="7" fill="#651E2C" />
      <path d="M16 7v18M8 11h16M8 11l-3 7h6zM24 11l-3 7h6zM11 25h10" stroke="#F5EBDD" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function NavItem({ to, icon, children, count, end }: { to: string; icon: ReactNode; children: ReactNode; count?: number; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "group flex h-9 shrink-0 items-center gap-2 rounded-md px-2.5 text-sm font-semibold whitespace-nowrap transition-colors lg:gap-2.5 [&_svg]:size-4",
          isActive ? "bg-white/10 text-white" : "text-rail-text/80 hover:bg-rail-hover hover:text-white",
        )
      }
    >
      {icon}
      <span className="lg:flex-1">{children}</span>
      {!!count && <span className="data rounded bg-ox px-1.5 text-[11px] font-medium text-white">{count}</span>}
    </NavLink>
  );
}

export default function Shell() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const overview = useOverview();
  const billing = useBilling();
  const needs = overview.data?.attention.length;
  const pending = billing.data?.summary.pending_count;

  return (
    <div className="min-h-svh lg:grid lg:grid-cols-[228px_1fr]">
      <div className="sticky top-0 z-30 bg-rail lg:static">
      <aside className="flex items-center gap-2 px-3 py-2 text-rail-text lg:sticky lg:top-0 lg:h-svh lg:flex-col lg:items-stretch lg:gap-0 lg:py-4">
        <div className="flex items-center gap-2.5 px-1.5 lg:mb-6">
          <Mark />
          <div className="hidden leading-tight sm:block">
            <div className="text-[15px] font-extrabold tracking-[-0.01em] text-white">Mizan</div>
            <div className="text-[11px] font-semibold tracking-[0.08em] text-rail-mute uppercase">Admin</div>
          </div>
        </div>

        <div className="no-scrollbar flex flex-1 gap-0.5 overflow-x-auto lg:block lg:flex-none lg:overflow-visible">
        <nav aria-label="Main" className="flex gap-0.5 lg:grid">
          <NavItem to="/" end icon={<Gauge />} count={needs}>
            Overview
          </NavItem>
          <NavItem to="/workspaces" icon={<Building2 />}>
            Workspaces
          </NavItem>
          <NavItem to="/billing" icon={<CreditCard />} count={pending}>
            Billing
          </NavItem>
          <NavItem to="/activity" icon={<Activity />}>
            Activity
          </NavItem>
        </nav>

        <div className="mt-6 mb-1.5 hidden px-2.5 text-[11px] font-semibold tracking-[0.08em] text-rail-mute uppercase lg:block">Platform</div>
        <nav aria-label="Platform" className="flex gap-0.5 lg:grid">
          <NavItem to="/team" icon={<Users />}>
            Team
          </NavItem>
          <NavItem to="/system" icon={<ServerCog />}>
            System
          </NavItem>
        </nav>
        </div>

        <div className="lg:mt-auto lg:border-t lg:border-white/10 lg:pt-3">
          <div className="flex items-center gap-2.5 px-1.5">
            <div className="hidden size-8 place-items-center lg:grid rounded-full bg-white/10 text-xs font-bold text-white">
              {(user?.full_name || user?.username || "?").slice(0, 1).toUpperCase()}
            </div>
            <div className="hidden min-w-0 flex-1 leading-tight lg:block">
              <div className="bidi truncate text-[13px] font-semibold text-white">{user?.full_name}</div>
              <div className="truncate text-[11px] text-rail-mute">@{user?.username}</div>
            </div>
            <button
              onClick={logout}
              className="rounded p-1.5 text-rail-mute hover:bg-rail-hover hover:text-white"
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOut className="size-4" />
            </button>
          </div>
          <a href={appUrl("system", "/")} className="mt-2 hidden px-1.5 text-[11px] text-rail-mute hover:text-white lg:block">
            Go to the Mizan app ↗
          </a>
        </div>
      </aside>
      </div>

      <main className="min-w-0 px-5 py-7 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-[1180px]">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
