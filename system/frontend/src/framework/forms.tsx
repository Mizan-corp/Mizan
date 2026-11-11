/**
 * Record forms as the workspace arranged them (ADR-006 phase 5). /settings/forms/<record> gives
 * the sections and fields: built-in ones (the page supplies their controls) and custom ones
 * (rendered here by type, values in the record's `extra`). The builder edits the arrangement.
 */
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Input, Select } from "@/components/ui";
import { Skeleton } from "@/components/kit/skeleton";
import { Switch } from "@/components/kit/switch";
import { cn } from "@/lib/utils";

export type FieldType = "text" | "number" | "date" | "boolean" | "select";
export interface FormField {
  key: string;
  label: string;
  builtin: boolean;
  locked: boolean;
  type?: FieldType;
  options?: string[] | null;
  required?: boolean;
  readonly?: boolean;
}
export interface FormSection { id: string; label: string; fields: FormField[] }
export interface RecordForm { record: string; label: string; custom: boolean; sections: FormSection[]; hidden: FormField[] }
export type ExtraValues = Record<string, unknown>;

export function useRecordForm(record: string) {
  return useQuery({
    queryKey: ["record-form", record],
    queryFn: () => api.get<RecordForm>(`/settings/forms/${record}`),
    staleTime: 5 * 60_000,
  });
}

/** Custom field values to send: empty ones left out (the server clears them). */
export function cleanExtra(values: ExtraValues): ExtraValues {
  return Object.fromEntries(Object.entries(values).filter(([, v]) => v !== "" && v !== undefined && v !== null));
}

/** Required custom fields still empty (their labels), to block saving early. */
export function missingRequired(form: RecordForm | undefined, values: ExtraValues): string[] {
  return (form?.sections ?? []).flatMap((s) => s.fields)
    .filter((f) => !f.builtin && f.required && !f.readonly && (values[f.key] === undefined || values[f.key] === ""))
    .map((f) => f.label);
}

export function CustomFieldInput({ field, value, onChange, id }: {
  field: FormField; value: unknown; onChange: (v: unknown) => void; id: string;
}) {
  const disabled = !!field.readonly;
  switch (field.type) {
    case "boolean":
      return (
        <div className="flex h-9 items-center">
          <Switch id={id} checked={value === true} onCheckedChange={(v: boolean) => onChange(v)} disabled={disabled} />
        </div>
      );
    case "select":
      return (
        <Select id={id} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
          <option value="">— اختر —</option>
          {(field.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
        </Select>
      );
    case "number":
      return <Input id={id} className="num" inputMode="decimal" dir="ltr" value={(value as string | number) ?? ""} disabled={disabled}
                    onChange={(e) => onChange(e.target.value)} />;
    case "date":
      return <Input id={id} type="date" className="num" value={(value as string) ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
    default:
      return <Input id={id} value={(value as string) ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
  }
}

/**
 * The form's fields in the workspace's sections. `builtin` maps a built-in field's key to its
 * control (the page keeps its own state and validation); `required` marks built-in ones with *.
 * Until the layout loads, or if it can't, the built-in controls show in the page's order.
 */
export function RecordFormFields({ record, builtin, required = [], wide = [], extra, onExtra }: {
  record: string;
  builtin: Record<string, ReactNode>;
  required?: string[];
  wide?: string[];
  extra: ExtraValues;
  onExtra: (values: ExtraValues) => void;
}) {
  const form = useRecordForm(record);
  if (form.isLoading) {
    return <div className="flex flex-col gap-3" aria-busy="true">{Object.keys(builtin).slice(0, 3).map((k) => <Skeleton key={k} className="h-14 w-full" />)}</div>;
  }
  const sections: FormSection[] = form.data?.sections ?? [{
    id: "main", label: "", fields: Object.keys(builtin).map((key) => ({ key, label: key, builtin: true, locked: false })),
  }];
  const many = sections.length > 1;
  return (
    <div className="flex flex-col gap-4">
      {sections.map((s) => (
        <fieldset key={s.id} className={cn("flex flex-col gap-3", many && "rounded-lg border border-border/70 p-3")}>
          {many && <legend className="px-1 text-xs font-bold text-muted-foreground">{s.label}</legend>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {s.fields.map((f) => {
              const control = f.builtin ? builtin[f.key] : (
                <CustomFieldInput id={`f-${record}-${f.key}`} field={f} value={extra[f.key]} onChange={(v) => onExtra({ ...extra, [f.key]: v })} />
              );
              if (control === undefined) return null; // a built-in field this page doesn't edit
              const star = f.builtin ? required.includes(f.key) : f.required && !f.readonly;
              return (
                <div key={f.key} className={cn((wide.includes(f.key) || f.key === "name") && "sm:col-span-2")}>
                  <label htmlFor={`f-${record}-${f.key}`} className="mb-1.5 block text-xs font-semibold text-foreground">
                    {f.label}{star && " *"}
                  </label>
                  {control}
                </div>
              );
            })}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
