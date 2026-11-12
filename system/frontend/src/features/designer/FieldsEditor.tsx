/**
 * Custom fields per record (ADR-006 phase 4 fields, edited here): the workspace adds its own and
 * relabels, requires or hides the ones its activity adds. Values are kept on each record, show on
 * its form (arranged in the forms tab) and are columns in the exports and the field reports.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { Skeleton } from "@/components/kit/skeleton";
import { Switch } from "@/components/kit/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { TableShell } from "@/components/app/shared";
import type { FieldType } from "@app/framework/forms";
import { RECORD_LABELS, TYPE_LABELS, type FieldDefinition } from "./api";

interface Draft { key: string; label: string; type: FieldType; options: string; required: boolean; searchable: boolean; hidden: boolean }
const EMPTY: Draft = { key: "", label: "", type: "text", options: "", required: false, searchable: false, hidden: false };
const KEY = /^[a-z][a-z0-9_]{0,47}$/;

export function FieldsEditor({ record }: { record: string }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const list = useQuery({
    queryKey: ["designer-fields", record],
    queryFn: () => api.get<FieldDefinition[]>(`/settings/fields/${record}`),
  });
  const [editing, setEditing] = useState<{ draft: Draft; existing: FieldDefinition | null } | null>(null);
  const [removing, setRemoving] = useState<FieldDefinition | null>(null);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["designer-fields", record] });
    qc.invalidateQueries({ queryKey: ["record-form", record] });
    qc.invalidateQueries({ queryKey: ["designer-form", record] });
    qc.invalidateQueries({ queryKey: ["workspace-profile"] });
  };
  const save = useMutation({
    mutationFn: ({ draft, existing }: { draft: Draft; existing: FieldDefinition | null }) => {
      const definition: Record<string, unknown> = {
        label: draft.label.trim(), type: existing && existing.source !== "workspace" ? existing.type : draft.type,
        required: draft.required, searchable: draft.searchable,
      };
      if ((definition.type as FieldType) === "select") {
        definition.options = draft.options.split(/[\n،,]/).map((o) => o.trim()).filter(Boolean);
      }
      const position = existing ? (list.data ?? []).findIndex((f) => f.key === existing.key) : (list.data?.length ?? 0);
      return api.put(`/settings/fields/${record}/${draft.key}`, { definition, hidden: draft.hidden, position });
    },
    onSuccess: () => { refresh(); setEditing(null); toast("success", "تم حفظ الحقل"); },
  });
  const toggleHidden = useMutation({
    mutationFn: (f: FieldDefinition) => api.put(`/settings/fields/${record}/${f.key}`, {
      definition: { label: f.label, type: f.type, required: f.required, searchable: f.searchable, options: f.options },
      hidden: !f.hidden, position: (list.data ?? []).findIndex((x) => x.key === f.key),
    }),
    onSuccess: refresh,
    onError: (e: Error) => toast("error", e.message),
  });
  const remove = useMutation({
    mutationFn: (f: FieldDefinition) => api.del(`/settings/fields/${record}/${f.key}`),
    onSuccess: () => { refresh(); setRemoving(null); toast("success", "تم"); },
    onError: (e: Error) => toast("error", e.message),
  });

  const openNew = () => setEditing({ draft: { ...EMPTY }, existing: null });
  const openEdit = (f: FieldDefinition) => setEditing({
    existing: f,
    draft: { key: f.key, label: f.label ?? "", type: f.type, options: (f.options ?? []).join("\n"), required: !!f.required, searchable: !!f.searchable, hidden: f.hidden },
  });

  const d = editing?.draft;
  const fromActivity = !!editing?.existing && editing.existing.source !== "workspace";
  const keyTaken = !editing?.existing && !!d && (list.data ?? []).some((f) => f.key === d.key);
  const invalid = !d || !d.label.trim() || !KEY.test(d.key) || keyTaken || (d.type === "select" && !d.options.trim() && !fromActivity);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          حقول {RECORD_LABELS[record] ?? record}: تُحفظ مع كل سجل وتظهر في نموذجه وفي التصدير وتقارير الحقول.
        </p>
        <Button size="sm" onClick={openNew}><Plus className="size-3.5" /> حقل جديد</Button>
      </div>

      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data!.length ? (
        <Empty text="لا توجد حقول مخصصة" hint={`أضف حقلًا لتسجّل بيانات إضافية على ${RECORD_LABELS[record] ?? record}.`}
               action={<Button size="sm" onClick={openNew}><Plus className="size-3.5" /> حقل جديد</Button>} />
      ) : (
        <TableShell>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>الحقل</TableHead>
                <TableHead className="hidden sm:table-cell">النوع</TableHead>
                <TableHead className="hidden md:table-cell">المصدر</TableHead>
                <TableHead>مطلوب</TableHead>
                <TableHead>ظاهر</TableHead>
                <TableHead className="w-24"><span className="sr-only">إجراءات</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.data!.map((f) => (
                <TableRow key={f.key} className={f.hidden ? "opacity-60" : ""}>
                  <TableCell>
                    <div className="font-medium">{f.label || f.key}</div>
                    <div className="font-mono text-[11px] text-muted-foreground" dir="ltr">{f.key}</div>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-sm">{TYPE_LABELS[f.type] ?? f.type}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Badge tone={f.source === "workspace" ? "brand" : "muted"}>{f.source === "workspace" ? "خاص بالمنشأة" : "من النشاط"}</Badge>
                  </TableCell>
                  <TableCell className="text-sm">{f.readonly ? "يملؤه النظام" : f.required ? "نعم" : "—"}</TableCell>
                  <TableCell>
                    <Switch checked={!f.hidden} onCheckedChange={() => toggleHidden.mutate(f)} disabled={toggleHidden.isPending}
                            aria-label={`${f.hidden ? "إظهار" : "إخفاء"} «${f.label || f.key}»`} />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => openEdit(f)} aria-label={`تعديل «${f.label || f.key}»`}>
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => setRemoving(f)}
                              aria-label={f.source === "workspace" ? `حذف «${f.label || f.key}»` : `إعادة «${f.label || f.key}» للافتراضي`}>
                        {f.source === "workspace" ? <Trash2 className="size-3.5" /> : <RotateCcw className="size-3.5" />}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableShell>
      )}

      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing?.existing ? `تعديل «${editing.existing.label || editing.existing.key}»` : "حقل جديد"}>
        {d && (
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (!invalid && !save.isPending) save.mutate(editing!); }}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="fld-label" className="mb-1.5 block text-xs font-semibold">اسم الحقل *</label>
                <Input id="fld-label" autoFocus value={d.label} maxLength={128} onChange={(e) => setEditing({ ...editing!, draft: { ...d, label: e.target.value } })} />
              </div>
              <div>
                <label htmlFor="fld-key" className="mb-1.5 block text-xs font-semibold">المفتاح (بالإنجليزية) *</label>
                <Input id="fld-key" dir="ltr" className="font-mono" value={d.key} disabled={!!editing!.existing} placeholder="warranty_months"
                       onChange={(e) => setEditing({ ...editing!, draft: { ...d, key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") } })} />
                {keyTaken && <p className="mt-1 text-xs text-destructive-ink">هذا المفتاح مستخدم.</p>}
              </div>
              <div>
                <label htmlFor="fld-type" className="mb-1.5 block text-xs font-semibold">النوع</label>
                <Select id="fld-type" value={d.type} disabled={fromActivity} onChange={(e) => setEditing({ ...editing!, draft: { ...d, type: e.target.value as FieldType } })}>
                  {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
              </div>
              <div className="flex flex-col justify-end gap-2 pb-1">
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={d.required} onCheckedChange={(v: boolean) => setEditing({ ...editing!, draft: { ...d, required: v } })} /> مطلوب
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={d.searchable} onCheckedChange={(v: boolean) => setEditing({ ...editing!, draft: { ...d, searchable: v } })} /> يُبحث به
                </label>
              </div>
            </div>
            {d.type === "select" && (
              <div>
                <label htmlFor="fld-options" className="mb-1.5 block text-xs font-semibold">الخيارات (كل خيار في سطر) *</label>
                <textarea id="fld-options" rows={4} value={d.options}
                          className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
                          onChange={(e) => setEditing({ ...editing!, draft: { ...d, options: e.target.value } })} />
              </div>
            )}
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="h-10 w-full font-bold" disabled={invalid || save.isPending}>
              {save.isPending ? <Spinner /> : "حفظ الحقل"}
            </Button>
          </form>
        )}
      </Modal>

      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing)}
        title={removing?.source === "workspace" ? "حذف الحقل" : "إعادة الحقل للافتراضي"}
        message={removing?.source === "workspace"
          ? `سيُحذف «${removing?.label || removing?.key}» من النماذج. القيم المحفوظة على السجلات تبقى.`
          : `سيعود «${removing?.label || removing?.key}» كما يحدده النشاط.`}
        confirmLabel={removing?.source === "workspace" ? "حذف" : "إعادة"}
      />
    </div>
  );
}
