/**
 * The frames dashboard widgets render in (ADR-006 phase 5). A module's widget (declared in its
 * manifest's "widgets", registered in its index.ts) draws its content inside one of these; the
 * dashboard places it on the grid by the size the manifest gives it.
 */
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "default" | "warn";

/** A small figure: label, icon, the value, and a footer line. */
export function KpiCard({ label, icon: Icon, tone = "default", children, footer }: {
  label: string;
  icon: LucideIcon;
  tone?: Tone;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const warn = tone === "warn";
  return (
    <div className={cn("precision-surface flex h-full flex-col justify-between gap-3 rounded-xl p-4", warn && "border-amber-500/40 bg-amber-500/[0.03]")}>
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">{label}</span>
        <div className={cn("flex size-7 items-center justify-center rounded-lg", warn ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-primary/10 text-primary")}>
          <Icon className="size-3.5" />
        </div>
      </div>
      <div>
        {children}
        {footer && <div className="mt-2 flex items-center gap-2 border-t border-border/50 pt-2 text-[11px] text-muted-foreground">{footer}</div>}
      </div>
    </div>
  );
}

/** A list or chart with a title bar and an optional action. */
export function PanelCard({ label, icon: Icon, iconClassName, action, children, className }: {
  label: ReactNode;
  icon: LucideIcon;
  iconClassName?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("precision-surface flex h-full flex-col overflow-hidden rounded-2xl", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-border/80 bg-card p-3.5">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className={cn("size-4 shrink-0 text-primary", iconClassName)} />
          <h2 className="truncate text-xs font-bold text-foreground">{label}</h2>
        </div>
        {action}
      </div>
      <div className="flex-1 p-2">{children}</div>
    </section>
  );
}
