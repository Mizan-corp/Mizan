import { type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Building2, LogOut, ReceiptText, UserRound } from "lucide-react";
import { cn } from "@/lib/utils";
import { appUrl } from "@/lib/urls";
import { useMe } from "@app/lib/data";
import { signOut } from "@app/lib/session";

export function Mark({ className = "size-8" }: { className?: string }) {
  // The Mizan scale reduced to a beam and two pans.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#651E2C" />
      <path d="M16 7v18M8 11h16M8 11l-3 7h6zM24 11l-3 7h6zM11 25h10" stroke="#F5EBDD" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function NavItem({ to, icon, children, end, tour }: { to: string; icon: ReactNode; children: ReactNode; end?: boolean; tour?: string }) {
  return (
    <NavLink
      to={to}
      end={end}
      data-tour={tour}
      className={({ isActive }) =>
        cn(
          "flex h-9 shrink-0 items-center gap-2 rounded-lg px-3 text-sm font-semibold whitespace-nowrap transition-colors [&_svg]:size-4",
          isActive ? "bg-wine-soft text-wine" : "text-ink-2 hover:bg-sand hover:text-ink",
        )
      }
    >
      {icon}
      {children}
    </NavLink>
  );
}

export default function Shell() {
  const me = useMe();

  return (
    <div className="min-h-svh">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3 sm:px-8">
          <a href="/" className="flex items-center gap-2.5">
            <Mark />
            <div className="leading-tight">
              <div className="title text-lg text-ink">ميزان</div>
              <div className="text-[11px] font-semibold text-mute">حساب المالك</div>
            </div>
          </a>
          <nav aria-label="الرئيسية" className="order-3 -mx-1 flex w-full gap-1 overflow-x-auto px-1 sm:order-none sm:w-auto">
            <NavItem to="/" end icon={<Building2 />}>
              مساحات العمل
            </NavItem>
            <NavItem to="/invoices" icon={<ReceiptText />} tour="nav-invoices">
              الفواتير
            </NavItem>
            <NavItem to="/account" icon={<UserRound />}>
              حسابي
            </NavItem>
          </nav>
          <div className="ms-auto flex items-center gap-2">
            <div className="hidden text-end leading-tight sm:block">
              <div className="text-[13px] font-semibold text-ink">{me.data?.full_name}</div>
              <div className="code text-[11px] text-mute">{me.data?.login}</div>
            </div>
            <button
              onClick={signOut}
              className="rounded-lg p-2 text-mute hover:bg-sand hover:text-ink"
              title="تسجيل الخروج"
              aria-label="تسجيل الخروج"
            >
              <LogOut className="size-4 rtl:-scale-x-100" />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1120px] px-5 py-8 sm:px-8">
        <Outlet />
      </main>

      <footer className="mx-auto max-w-[1120px] px-5 pb-10 text-[13px] text-mute sm:px-8">
        <a href={appUrl("website", "/")} className="hover:text-ink">
          mizan-co.vercel.app
        </a>
        <span className="mx-2">·</span>
        المدفوعات تتم بأمان عبر Paymob
      </footer>
    </div>
  );
}
