// The purchases screens' header: the title and the module's own tabs.
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { History, Lightbulb, Truck } from "lucide-react";
import { useAuth } from "@/stores/auth";
import { useTenantNav } from "@app/lib/tenant";

const TABS = [
  { path: "/purchases", label: "أوامر الشراء", icon: Truck },
  { path: "/purchases/suggestions", label: "اقتراحات الشراء", icon: Lightbulb },
  { path: "/purchases/price-history", label: "سجل أسعار الشراء", icon: History },
];

export function PurchasesHeader({ title, subtitle, actions }: { title: ReactNode; subtitle: string; actions?: ReactNode }) {
  const can = useAuth((s) => s.can);
  const { tenantTo } = useTenantNav();
  const location = useLocation();
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{title}</h1>
          <p className="mt-0.5 text-xs text-muted">{subtitle}</p>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {can("purchases|finance") && (
        <nav className="no-print flex flex-wrap gap-2" aria-label="أقسام المشتريات">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = location.pathname.endsWith(t.path);
            return (
              <Link key={t.path} to={tenantTo(t.path)} aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                      active ? "bg-primary text-primary-foreground shadow-sm shadow-primary/25" : "border border-line/80 bg-card text-muted hover:bg-elevated hover:text-ink"
                    }`}>
                <Icon className="size-4" />
                {t.label}
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
