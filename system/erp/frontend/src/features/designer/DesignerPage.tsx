/**
 * PAGE CONTRACT
 * Page: مصمم الشاشات والنماذج (/designer)
 * User: the owner, or staff with the `designer` permission (ADR-006 D4, phase 5)
 * Outcome: each role sees its own main screen, menu and dashboard; forms are arranged and carry
 *          the workspace's own fields.
 * Required states: loading (skeleton), error (retry), unsaved changes (save / discard), saved (toast)
 * Responsive: role/record list above the editor below 1024px, beside it from 1024px.
 */
import { useState } from "react";
import { PageHeader } from "@/components/app/shared";
import { Badge, ErrorBox } from "@/components/ui";
import { Skeleton } from "@/components/kit/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/kit/tabs";
import { cn } from "@/lib/utils";
import { RECORD_LABELS, useDesignerOverview } from "./api";
import { FieldsEditor } from "./FieldsEditor";
import { FormLayoutEditor } from "./FormLayoutEditor";
import { RoleLayoutEditor } from "./RoleLayoutEditor";

type Tab = "roles" | "forms" | "fields";

function Picker({ label, items, value, onChange }: {
  label: string;
  items: { id: string; name: string; note?: string; custom?: boolean }[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  return (
    <nav aria-label={label} className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
      {items.map((i) => (
        <button
          key={i.id}
          type="button"
          onClick={() => onChange(i.id)}
          aria-current={value === i.id ? "true" : undefined}
          className={cn(
            "flex shrink-0 items-center justify-between gap-2 rounded-md px-3 py-2 text-start text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
            value === i.id ? "bg-primary/10 font-semibold text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
          )}
        >
          <span className="truncate">{i.name}</span>
          {i.custom && <Badge tone="brand">مخصص</Badge>}
        </button>
      ))}
    </nav>
  );
}

export default function DesignerPage() {
  const overview = useDesignerOverview();
  const [tab, setTab] = useState<Tab>("roles");
  const [roleId, setRoleId] = useState<string | null>(null);
  const [formRecord, setFormRecord] = useState<string | null>(null);
  const [fieldRecord, setFieldRecord] = useState<string | null>(null);

  const roles = overview.data?.roles ?? [];
  const forms = overview.data?.forms ?? [];
  const fieldRecords = overview.data?.field_records ?? [];
  const currentRole = roleId ?? roles[0]?.id ?? null;
  const currentForm = formRecord ?? forms[0]?.record ?? null;
  const currentFields = fieldRecord ?? fieldRecords[0] ?? null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="مصمم الشاشات والنماذج"
        description="لكل دور شاشته الرئيسية وقائمته ولوحته، ولكل نموذج ترتيبه وحقوله. التصميم يرتّب ما يملكه الدور ولا يمنح صلاحيات."
      />

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="roles">شاشات الأدوار</TabsTrigger>
          <TabsTrigger value="forms">النماذج</TabsTrigger>
          <TabsTrigger value="fields">الحقول المخصصة</TabsTrigger>
        </TabsList>
      </Tabs>

      {overview.isLoading ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[14rem_1fr]" aria-busy="true">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      ) : overview.isError ? (
        <ErrorBox message={(overview.error as Error).message} onRetry={() => overview.refetch()} />
      ) : (
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[14rem_1fr]">
          <aside className="min-w-0 lg:sticky lg:top-4">
            {tab === "roles" && (
              <Picker label="الأدوار" value={currentRole} onChange={setRoleId}
                      items={roles.map((r) => ({ id: r.id, name: r.name, custom: r.custom }))} />
            )}
            {tab === "forms" && (
              <Picker label="النماذج" value={currentForm} onChange={setFormRecord}
                      items={forms.map((f) => ({ id: f.record, name: f.label, custom: f.custom }))} />
            )}
            {tab === "fields" && (
              <Picker label="السجلات" value={currentFields} onChange={setFieldRecord}
                      items={fieldRecords.map((r) => ({ id: r, name: RECORD_LABELS[r] ?? r }))} />
            )}
          </aside>
          <div className="min-w-0">
            {tab === "roles" && currentRole && <RoleLayoutEditor key={currentRole} roleId={currentRole} />}
            {tab === "forms" && currentForm && <FormLayoutEditor key={currentForm} record={currentForm} />}
            {tab === "fields" && currentFields && <FieldsEditor key={currentFields} record={currentFields} />}
          </div>
        </div>
      )}
    </div>
  );
}
