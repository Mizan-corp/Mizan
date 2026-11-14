import { useEffect, useId, type ReactNode } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";

// The frame every clinic form dialog shares: overlay, card, close button, title, footer buttons.
export function ClinicModal({
  title,
  icon,
  subtitle,
  onClose,
  size = "md",
  scroll = false,
  children,
}: {
  title: ReactNode;
  icon: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  size?: "md" | "lg";
  scroll?: boolean;
  children: ReactNode;
}) {
  const titleId = useId();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <Card
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`w-full ${size === "lg" ? "max-w-lg" : "max-w-md"} p-6 bg-card border-border shadow-2xl relative text-right ${scroll ? "max-h-[90vh] overflow-y-auto" : ""}`}
        dir="rtl"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="إغلاق"
          className="absolute left-4 top-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
        >
          <X className="w-4 h-4" />
        </button>
        <h3 id={titleId} className={`text-base font-bold text-foreground ${subtitle ? "mb-1" : "mb-4"} flex items-center gap-2`}>
          {icon}
          {title}
        </h3>
        {subtitle && <p className="text-xs text-muted-foreground mb-4 font-mono">{subtitle}</p>}
        {children}
      </Card>
    </div>
  );
}

export function ModalActions({
  onCancel,
  submitLabel,
  submitClassName = "bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs",
  busy = false,
}: {
  onCancel: () => void;
  submitLabel: string;
  submitClassName?: string;
  busy?: boolean;
}) {
  return (
    <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/40">
      <Button type="button" variant="outline" onClick={onCancel} className="h-8 text-xs">
        إلغاء
      </Button>
      <Button type="submit" disabled={busy} className={`h-8 text-xs ${submitClassName}`}>
        {submitLabel}
      </Button>
    </div>
  );
}
