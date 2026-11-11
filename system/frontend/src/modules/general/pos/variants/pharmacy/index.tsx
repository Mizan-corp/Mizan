/**
 * POS, pharmacy variant (ADR-006 phase 4): drug details on products and cart lines, and the
 * prescription a sale needs when it has prescription-only or controlled drugs. The rules
 * themselves are enforced by the backend (pos/variants/pharmacy/hooks.py); this shows them early.
 */
import { FileText, ShieldAlert } from "lucide-react";
import { Input } from "@/components/ui";
import type { FieldDef } from "@app/lib/workspace";

export interface DrugProduct {
  name: string;
  extra?: Record<string, unknown>;
}

const RX_KEYS = ["doctor_name", "patient_name"];
const CONTROLLED_KEYS = ["patient_national_id", "doctor_license"];

export function isRx(p: DrugProduct) {
  return Boolean(p.extra?.requires_prescription || p.extra?.is_controlled);
}
export function isControlled(p: DrugProduct) {
  return Boolean(p.extra?.is_controlled);
}

/** What the cart needs: the prescription fields that must be filled, and why. */
export function prescriptionNeeds(products: DrugProduct[]) {
  const rx = products.filter(isRx).map((p) => p.name);
  const controlled = products.filter(isControlled).map((p) => p.name);
  const required = rx.length ? [...RX_KEYS, ...(controlled.length ? CONTROLLED_KEYS : [])] : [];
  return { rx, controlled, required };
}

/** Scientific name, strength and form under a drug's name, with prescription/controlled badges. */
export function DrugInfo({ product, compact = false }: { product: DrugProduct; compact?: boolean }) {
  const e = product.extra ?? {};
  const detail = [e.scientific_name, e.strength, compact ? null : e.dosage_form].filter(Boolean).join(" · ");
  if (!detail && !isRx(product)) return null;
  return (
    <span className="flex flex-wrap items-center gap-1 text-[10px] leading-tight text-muted-foreground">
      {detail && <span dir="auto" className="truncate">{String(detail)}</span>}
      {isControlled(product) ? (
        <span className="inline-flex items-center gap-0.5 rounded bg-destructive/10 px-1 font-bold text-destructive">
          <ShieldAlert size={10} aria-hidden /> مراقب
        </span>
      ) : isRx(product) ? (
        <span className="inline-flex items-center gap-0.5 rounded bg-warning/15 px-1 font-bold text-warning">
          <FileText size={10} aria-hidden /> روشتة
        </span>
      ) : null}
    </span>
  );
}

/** The prescription inputs (the workspace's sale fields), shown when the cart needs them. */
export function PrescriptionPanel({
  fields,
  value,
  onChange,
  needs,
}: {
  fields: FieldDef[];
  value: Record<string, string>;
  onChange: (v: Record<string, string>) => void;
  needs: ReturnType<typeof prescriptionNeeds>;
}) {
  if (!needs.rx.length) return null;
  const missing = needs.required.filter((k) => !value[k]?.trim());
  return (
    <section
      aria-label="بيانات الروشتة"
      className={`rounded-xl border p-3 ${missing.length ? "border-warning/50 bg-warning/5" : "border-line bg-secondary/20"}`}
    >
      <div className="mb-2 flex items-start gap-2 text-xs">
        {needs.controlled.length ? <ShieldAlert size={16} className="mt-0.5 shrink-0 text-destructive" aria-hidden />
          : <FileText size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden />}
        <p className="leading-relaxed">
          <strong className="font-bold">{needs.controlled.length ? "أدوية مراقبة" : "أدوية تُصرف بروشتة"}:</strong>{" "}
          {(needs.controlled.length ? needs.controlled : needs.rx).join("، ")}
        </p>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {fields.filter((f) => !f.readonly).map((f) => {
          const required = needs.required.includes(f.key);
          const id = `rx-${f.key}`;
          return (
            <div key={f.key}>
              <label htmlFor={id} className="mb-0.5 block text-[11px] font-medium text-muted-foreground">
                {f.label ?? f.key}{required && <span className="text-destructive"> *</span>}
              </label>
              <Input
                id={id}
                dir={f.key.includes("national") || f.key.includes("license") || f.key === "rx_number" ? "ltr" : "auto"}
                value={value[f.key] ?? ""}
                aria-required={required}
                onChange={(e) => onChange({ ...value, [f.key]: e.target.value })}
                className="h-9 text-sm"
              />
            </div>
          );
        })}
      </div>
      {missing.length > 0 && (
        <p className="mt-2 text-[11px] text-warning" role="status">
          مطلوب قبل التأكيد: {fields.filter((f) => missing.includes(f.key)).map((f) => f.label ?? f.key).join("، ")}
        </p>
      )}
    </section>
  );
}
