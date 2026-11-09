import { cloneElement, type ComponentProps, type ReactElement, type ReactNode, useId } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { Dialog as DialogRoot, DialogContent, DialogDescription, DialogTitle } from "@/components/kit/dialog";
import { cn } from "@/lib/utils";
import { errorText, type Tone } from "@app/lib/format";

// ─── Buttons ───────────────────────────────────────────────────────────────

type Variant = "primary" | "secondary" | "ghost" | "danger";
const BUTTON: Record<Variant, string> = {
  primary: "bg-wine text-white hover:bg-wine-hover shadow-sm",
  secondary: "bg-card text-ink border border-line hover:border-ink-2/30 hover:bg-sand/50",
  ghost: "text-ink-2 hover:bg-sand hover:text-ink",
  danger: "bg-bad text-white hover:bg-bad/90",
};

export function Button({
  variant = "secondary",
  size = "md",
  busy,
  className,
  children,
  disabled,
  ...props
}: ComponentProps<"button"> & { variant?: Variant; size?: "sm" | "md" | "lg"; busy?: boolean }) {
  return (
    <button
      type="button"
      disabled={disabled || busy}
      className={cn(
        "inline-flex select-none items-center justify-center gap-2 rounded-lg font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
        size === "sm" ? "h-8 px-3 text-[13px]" : size === "lg" ? "h-11 px-5 text-[15px]" : "h-10 px-4 text-sm",
        BUTTON[variant],
        className,
      )}
      {...props}
    >
      {busy && <Loader2 className="animate-spin" />}
      {children}
    </button>
  );
}

// ─── Status ────────────────────────────────────────────────────────────────

const TONE: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  info: "bg-info-soft text-info",
  mute: "bg-sand text-mute",
  wine: "bg-wine-soft text-wine",
};

export function Badge({ tone = "mute", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold whitespace-nowrap", TONE[tone], className)}>
      {children}
    </span>
  );
}

// ─── Layout ────────────────────────────────────────────────────────────────

export function PageHeader({ title, description, actions }: { title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="title text-[28px] leading-tight text-ink">{title}</h1>
        {description && <p className="mt-1.5 text-[15px] text-mute">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Panel({
  title,
  aside,
  children,
  className,
  flush,
  ...rest
}: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; flush?: boolean } & Omit<ComponentProps<"section">, "title">) {
  return (
    <section className={cn("rounded-xl border border-line bg-card", className)} {...rest}>
      {(title || aside) && (
        <div className="flex items-center justify-between gap-3 border-b border-line-soft px-5 py-3.5">
          <h2 className="text-[15px] font-bold text-ink">{title}</h2>
          {aside && <div className="text-[13px] text-mute">{aside}</div>}
        </div>
      )}
      <div className={flush ? "" : "p-5"}>{children}</div>
    </section>
  );
}

export function Meter({ label, used, max }: { label: string; used: number; max: number }) {
  const unlimited = !max || max >= 9999;
  const pct = unlimited ? 0 : Math.min(100, Math.round((used / max) * 100));
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-sm">
        <span className="text-ink-2">{label}</span>
        <span className="data text-ink">
          {used} <span className="text-mute">/ {unlimited ? "غير محدود" : max}</span>
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-sand" role="meter" aria-valuenow={used} aria-valuemax={max} aria-label={label}>
        <div className={cn("h-full rounded-full", pct >= 90 ? "bg-bad" : pct >= 70 ? "bg-warn" : "bg-wine")} style={{ width: `${unlimited ? 4 : Math.max(pct, 2)}%` }} />
      </div>
    </div>
  );
}

// ─── Forms ─────────────────────────────────────────────────────────────────

const FIELD =
  "h-11 w-full rounded-lg border border-line bg-card px-3.5 text-[15px] text-ink placeholder:text-mute/70 focus:border-wine focus:outline-none focus:ring-2 focus:ring-wine/15";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: ReactNode;
  children: ReactElement<{ id?: string; "aria-describedby"?: string }>;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-semibold text-ink">
        {label}
      </label>
      {cloneElement(children, { id, "aria-describedby": hint ? `${id}-hint` : undefined })}
      {hint && (
        <p id={`${id}-hint`} className="mt-1.5 text-[13px] text-mute">
          {hint}
        </p>
      )}
    </div>
  );
}

export const Input = ({ className, ...props }: ComponentProps<"input">) => <input className={cn(FIELD, className)} {...props} />;
export const Select = ({ className, ...props }: ComponentProps<"select">) => <select className={cn(FIELD, "pe-8", className)} {...props} />;

// ─── Dialogs ───────────────────────────────────────────────────────────────

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  return (
    <DialogRoot open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent showCloseButton={false} dir="rtl" className="gap-0 rounded-xl bg-card p-0 font-[family-name:var(--font-owner)] sm:max-w-md">
        <div className="flex items-start justify-between gap-4 border-b border-line-soft px-5 py-4">
          <div>
            <DialogTitle className="text-base font-bold text-ink">{title}</DialogTitle>
            {description && <DialogDescription className="mt-1 text-[13px] leading-relaxed text-mute">{description}</DialogDescription>}
          </div>
          <button onClick={onClose} className="rounded p-1 text-mute hover:bg-sand hover:text-ink" aria-label="إغلاق">
            <X className="size-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </DialogContent>
    </DialogRoot>
  );
}

export function ModalActions({ children }: { children: ReactNode }) {
  return <div className="-mx-5 mt-5 -mb-4 flex justify-start gap-2 border-t border-line-soft bg-paper/70 px-5 py-3">{children}</div>;
}

// ─── States ────────────────────────────────────────────────────────────────

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="mt-3 flex items-start gap-2 rounded-lg bg-bad-soft px-3 py-2.5 text-[13px] text-bad">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

export function LoadError({ error, retry }: { error: unknown; retry: () => void }) {
  return (
    <div className="rounded-xl border border-line bg-card px-6 py-12 text-center">
      <p className="font-semibold text-ink">تعذر تحميل هذه الصفحة.</p>
      <p className="mt-1 text-[13px] text-mute">{errorText(error)}</p>
      <Button className="mt-4" onClick={retry}>
        حاول مرة أخرى
      </Button>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="px-6 py-12 text-center">
      <p className="font-semibold text-ink">{title}</p>
      {children && <div className="mt-1 text-[13px] text-mute">{children}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-sand", className)} />;
}

export function PageSkeleton() {
  return (
    <div aria-busy="true" aria-label="جارٍ التحميل">
      <Skeleton className="mb-7 h-9 w-64" />
      <div className="grid gap-5 md:grid-cols-2">
        <Skeleton className="h-56" />
        <Skeleton className="h-56" />
      </div>
    </div>
  );
}
