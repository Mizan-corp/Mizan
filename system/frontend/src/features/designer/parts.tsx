import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, X } from "lucide-react";
import { cn } from "@/lib/utils";

function IconButton({ label, onClick, disabled, children, danger }: {
  label: string; onClick: () => void; disabled?: boolean; children: ReactNode; danger?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-30",
        danger && "hover:bg-destructive/10 hover:text-destructive-ink",
      )}
    >
      {children}
    </button>
  );
}

/** Up, down and remove for a row in an ordered list. */
export function RowControls({ what, index, count, onMove, onRemove, removeLabel, canRemove = true }: {
  what: string;
  index: number;
  count: number;
  onMove: (delta: -1 | 1) => void;
  onRemove?: () => void;
  removeLabel?: string;
  canRemove?: boolean;
}) {
  return (
    <div className="flex shrink-0 items-center">
      <IconButton label={`نقل «${what}» لأعلى`} onClick={() => onMove(-1)} disabled={index === 0}><ArrowUp className="size-3.5" /></IconButton>
      <IconButton label={`نقل «${what}» لأسفل`} onClick={() => onMove(1)} disabled={index === count - 1}><ArrowDown className="size-3.5" /></IconButton>
      {onRemove && (
        <IconButton label={`${removeLabel ?? "إزالة"} «${what}»`} onClick={onRemove} disabled={!canRemove} danger><X className="size-3.5" /></IconButton>
      )}
    </div>
  );
}

/** A titled block of the editor. */
export function EditorBlock({ title, description, actions, children }: {
  title: string; description?: string; actions?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/70 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-foreground">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}
