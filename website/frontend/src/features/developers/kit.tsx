/** Layout pieces of the developer portal, built like the owner panel's (owner/frontend/src/ui.tsx). */
import type { ReactNode } from "react";
import { Copy } from "lucide-react";
import { useToast } from "@/components/ui";
import { cn } from "@/lib/utils";

export function PageHeader({ title, description, actions }: { title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold leading-tight text-foreground">{title}</h1>
        {description && <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Panel({ title, aside, children, className, flush }: {
  title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; flush?: boolean;
}) {
  return (
    <section className={cn("rounded-2xl border border-line bg-card shadow-xs", className)}>
      {(title || aside) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <h2 className="text-[15px] font-bold text-foreground">{title}</h2>
          {aside && <div className="text-sm text-muted-foreground">{aside}</div>}
        </div>
      )}
      <div className={flush ? "" : "p-5"}>{children}</div>
    </section>
  );
}

export function Field({ label, hint, htmlFor, children }: { label: string; hint?: ReactNode; htmlFor: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium text-foreground">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** A secret or long value with a copy button. */
export function CopyValue({ value, label }: { value: string; label: string }) {
  const { toast } = useToast();
  return (
    <div className="flex items-center gap-2">
      <code dir="ltr" className="code min-w-0 flex-1 truncate rounded-md border border-line bg-muted/40 px-2.5 py-2 text-xs">{value}</code>
      <button
        type="button"
        aria-label={`انسخ ${label}`}
        onClick={() => navigator.clipboard?.writeText(value).then(() => toast("success", "نُسخ"))}
        className="grid size-9 shrink-0 place-items-center rounded-md border border-input bg-card text-muted-foreground transition hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40"
      >
        <Copy className="size-4" />
      </button>
    </div>
  );
}

export const when = (iso: string | null | undefined) =>
  iso ? new Intl.DateTimeFormat("ar-EG-u-nu-latn", { dateStyle: "medium" }).format(new Date(iso)) : "—";
