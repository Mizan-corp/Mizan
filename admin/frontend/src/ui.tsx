import { cloneElement, type ComponentProps, type ReactElement, type ReactNode, useId, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { Dialog as DialogRoot, DialogContent, DialogDescription, DialogTitle } from "@/components/kit/dialog";
import { cn } from "@/lib/utils";
import type { ActivityItem } from "@app/lib/data";
import { describe } from "@app/lib/activity";
import { ago, dateTime, errorText, type Tone } from "@app/lib/format";

// ─── Buttons ───────────────────────────────────────────────────────────────

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-ox text-white hover:bg-ox-hover shadow-sm",
  secondary: "bg-card text-ink border border-line hover:border-ink-2/40 hover:bg-paper",
  ghost: "text-ink-2 hover:bg-line-soft hover:text-ink",
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
}: ComponentProps<"button"> & { variant?: ButtonVariant; size?: "sm" | "md"; busy?: boolean }) {
  return (
    <button
      type="button"
      disabled={disabled || busy}
      className={cn(
        "inline-flex select-none items-center justify-center gap-1.5 rounded-md font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-50 [&_svg]:size-4",
        size === "sm" ? "h-8 px-2.5 text-[13px]" : "h-9 px-3.5 text-sm",
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
  mute: "bg-line-soft text-mute",
  ox: "bg-ox-soft text-ox",
};
const DOT: Record<Tone, string> = {
  ok: "bg-ok",
  warn: "bg-warn",
  bad: "bg-bad",
  info: "bg-info",
  mute: "bg-mute/50",
  ox: "bg-ox",
};

export function Badge({ tone = "mute", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold whitespace-nowrap", TONE[tone], className)}>
      {children}
    </span>
  );
}

export function Dot({ tone, label }: { tone: Tone; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2" title={label}>
      <span className={cn("size-2 shrink-0 rounded-full", DOT[tone])} />
      {label}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return status === "suspended" ? <Badge tone="bad">Suspended</Badge> : <Badge tone="ok">Active</Badge>;
}

// ─── Layout pieces ─────────────────────────────────────────────────────────

export function PageHeader({
  title,
  description,
  actions,
  crumb,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  crumb?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {crumb && <div className="mb-1.5 text-[13px] text-mute">{crumb}</div>}
        <h1 className="text-[26px] font-bold leading-tight tracking-[-0.02em] text-ink">{title}</h1>
        {description && <p className="mt-1 text-sm text-mute">{description}</p>}
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
}: {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section className={cn("rounded-2xl border border-line bg-card shadow-xs", className)}>
      {(title || aside) && (
        <div className="flex items-center justify-between gap-3 border-b border-line-soft px-4 py-3">
          <h2 className="text-sm font-bold text-ink">{title}</h2>
          {aside && <div className="text-[13px] text-mute">{aside}</div>}
        </div>
      )}
      <div className={flush ? "" : "p-4"}>{children}</div>
    </section>
  );
}

/** A row of figures separated by rules; the ledger line at the top of a page. */
export function Figures({ items }: { items: { label: string; value: ReactNode; hint?: ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-2 overflow-hidden rounded-2xl border border-line bg-card shadow-xs sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]">
      {items.map((it) => (
        <div key={it.label} className="border-line-soft border-b px-4 py-3.5 sm:border-r sm:border-b-0 sm:last:border-r-0">
          <dt className="text-xs font-semibold text-mute">{it.label}</dt>
          <dd className="data mt-1.5 text-[24px] font-bold leading-none tracking-[-0.02em] text-ink">{it.value}</dd>
          {it.hint && <dd className="mt-1.5 text-xs text-mute">{it.hint}</dd>}
        </div>
      ))}
    </dl>
  );
}

// ─── Tabs ──────────────────────────────────────────────────────────────────

export function Tabs<T extends string>({
  value,
  onChange,
  items,
}: {
  value: T;
  onChange: (v: T) => void;
  items: { value: T; label: string; count?: number }[];
}) {
  return (
    <div role="tablist" className="no-scrollbar mb-5 flex gap-1 overflow-x-auto border-b border-line">
      {items.map((it) => (
        <button
          key={it.value}
          role="tab"
          aria-selected={value === it.value}
          onClick={() => onChange(it.value)}
          className={cn(
            "-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-semibold whitespace-nowrap transition-colors",
            value === it.value ? "border-ox text-ink" : "border-transparent text-mute hover:text-ink",
          )}
        >
          {it.label}
          {it.count != null && <span className="data rounded bg-line-soft px-1.5 text-[11px] text-ink-2">{it.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  onChange,
  items,
}: {
  value: T;
  onChange: (v: T) => void;
  items: { value: T; label: string; count?: number }[];
}) {
  return (
    <div className="inline-flex rounded-md border border-line bg-card p-0.5">
      {items.map((it) => (
        <button
          key={it.value}
          aria-pressed={value === it.value}
          onClick={() => onChange(it.value)}
          className={cn(
            "flex h-7 items-center gap-1.5 rounded px-2.5 text-[13px] font-semibold transition-colors",
            value === it.value ? "bg-ink text-white" : "text-ink-2 hover:bg-line-soft",
          )}
        >
          {it.label}
          {it.count != null && <span className={cn("data text-[11px]", value === it.value ? "text-white/70" : "text-mute")}>{it.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ─── Tables ────────────────────────────────────────────────────────────────

export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs font-semibold text-mute">
            {head.map((h, i) => (
              <th key={i} className="px-4 py-2.5 font-semibold whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line-soft">{children}</tbody>
      </table>
    </div>
  );
}

export const Td = ({ className, ...props }: ComponentProps<"td">) => (
  <td className={cn("px-4 py-3 align-middle", className)} {...props} />
);

// ─── Forms ─────────────────────────────────────────────────────────────────

const FIELD = "h-9 w-full rounded-md border border-line bg-card px-3 text-sm text-ink placeholder:text-mute/70 focus:border-ox focus:outline-none focus:ring-2 focus:ring-ox/15";

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactElement<{ id?: string; "aria-describedby"?: string }> }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-semibold text-ink">
        {label}
      </label>
      {cloneElement(children, { id, "aria-describedby": hint ? `${id}-hint` : undefined })}
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-mute">
          {hint}
        </p>
      )}
    </div>
  );
}

export const Input = ({ className, ...props }: ComponentProps<"input">) => <input className={cn(FIELD, className)} {...props} />;
export const Select = ({ className, ...props }: ComponentProps<"select">) => (
  <select className={cn(FIELD, "pr-8", className)} {...props} />
);
export const Textarea = ({ className, ...props }: ComponentProps<"textarea">) => (
  <textarea className={cn(FIELD, "h-auto min-h-20 py-2", className)} {...props} />
);

// ─── Dialogs ───────────────────────────────────────────────────────────────

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <DialogRoot open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent showCloseButton={false} className={cn("gap-0 rounded-2xl bg-card p-0 font-[family-name:var(--font-admin)]", wide ? "sm:max-w-xl" : "sm:max-w-md")}>
        <div className="flex items-start justify-between gap-4 border-b border-line-soft px-5 py-4">
          <div>
            <DialogTitle className="text-base font-bold text-ink">{title}</DialogTitle>
            {description && <DialogDescription className="mt-1 text-[13px] text-mute">{description}</DialogDescription>}
          </div>
          <button onClick={onClose} className="rounded p-1 text-mute hover:bg-line-soft hover:text-ink" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </DialogContent>
    </DialogRoot>
  );
}

export function ModalActions({ children }: { children: ReactNode }) {
  return <div className="-mx-5 mt-5 -mb-4 flex justify-end gap-2 border-t border-line-soft bg-paper/60 px-5 py-3">{children}</div>;
}

/** A confirmation that can require a reason. */
export function Confirm({
  open,
  onClose,
  title,
  body,
  confirmLabel,
  danger,
  withReason,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  body: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  withReason?: boolean;
  onConfirm: (reason: string) => Promise<unknown>;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const close = () => {
    setReason("");
    setError(null);
    onClose();
  };
  return (
    <Modal open={open} onClose={close} title={title}>
      <div className="text-sm text-ink-2">{body}</div>
      {withReason && (
        <div className="mt-4">
          <Field label="Reason" hint="Saved in the activity log.">
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why are you doing this?" />
          </Field>
        </div>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
      <ModalActions>
        <Button variant="ghost" onClick={close}>
          Cancel
        </Button>
        <Button
          variant={danger ? "danger" : "primary"}
          busy={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await onConfirm(reason.trim());
              close();
            } catch (e) {
              setError(errorText(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {confirmLabel}
        </Button>
      </ModalActions>
    </Modal>
  );
}

// ─── States ────────────────────────────────────────────────────────────────

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="mt-3 flex items-start gap-2 rounded-md bg-bad-soft px-3 py-2 text-[13px] text-bad">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

export function LoadError({ error, retry }: { error: unknown; retry: () => void }) {
  return (
    <div className="rounded-2xl border border-line bg-card px-6 py-10 text-center shadow-xs">
      <p className="text-sm font-semibold text-ink">This page couldn't load.</p>
      <p className="mt-1 text-[13px] text-mute">{errorText(error)}</p>
      <Button className="mt-4" onClick={retry}>
        Try again
      </Button>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="px-6 py-10 text-center">
      <p className="text-sm font-semibold text-ink">{title}</p>
      {children && <div className="mt-1 text-[13px] text-mute">{children}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-line-soft", className)} />;
}

export function PageSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <Skeleton className="mb-2 h-4 w-28" />
      <Skeleton className="mb-6 h-8 w-64" />
      <Skeleton className="mb-5 h-20 w-full" />
      <Skeleton className="h-72 w-full" />
    </div>
  );
}

// ─── Domain pieces ─────────────────────────────────────────────────────────

export function WorkspaceLink({ id, name, className }: { id: string | null; name: string; className?: string }) {
  if (!id) return <span className={cn("bidi font-semibold", className)}>{name}</span>;
  return (
    <Link to={`/workspaces/${id}`} className={cn("bidi font-semibold text-ink underline-offset-2 hover:text-ox hover:underline", className)}>
      {name}
    </Link>
  );
}

export function ActivityList({ items, empty = "Nothing has happened yet." }: { items: ActivityItem[]; empty?: string }) {
  if (!items.length) return <Empty title={empty} />;
  return (
    <ol className="divide-y divide-line-soft">
      {items.map((a) => (
        <li key={a.id} className="flex items-baseline justify-between gap-4 px-4 py-2.5">
          <p className="min-w-0 text-sm text-ink-2">
            {describe(a).map((p, i) =>
              typeof p === "string" ? <span key={i}>{p}</span> : <WorkspaceLink key={i} id={p.id} name={p.workspace} />,
            )}
            {a.actor && <span className="text-mute"> · {a.actor}</span>}
          </p>
          <time className="shrink-0 text-xs text-mute" dateTime={a.at} title={dateTime(a.at)}>
            {ago(a.at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
