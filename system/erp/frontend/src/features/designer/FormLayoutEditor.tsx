/**
 * A record's form: sections, the order of fields in them, and which fields are left out.
 * Built-in fields come from the module; custom ones from the "الحقول المخصصة" tab. A basic or
 * required field can be moved but not hidden.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, FolderPlus, Lock, RotateCcw, Save } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, ConfirmDialog, ErrorBox, Input, Select, Spinner, useToast } from "@/components/ui";
import { Skeleton } from "@/components/kit/skeleton";
import type { FormField, RecordForm } from "@app/framework/forms";
import { move, newId } from "./api";
import { EditorBlock, RowControls } from "./parts";

interface SectionDraft { id: string; label: string; fields: string[] }
interface FormDraft { sections: SectionDraft[]; hidden: string[] }

function toDraft(f: RecordForm): FormDraft {
  return {
    sections: f.sections.map((s) => ({ id: s.id, label: s.label, fields: s.fields.map((x) => x.key) })),
    hidden: f.hidden.map((x) => x.key),
  };
}

export function FormLayoutEditor({ record }: { record: string }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const data = useQuery({
    queryKey: ["designer-form", record],
    queryFn: () => api.get<RecordForm>(`/settings/designer/forms/${record}`),
  });
  const [draft, setDraft] = useState<FormDraft | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  useEffect(() => { if (data.data) setDraft(toDraft(data.data)); }, [data.data]);

  const fields = useMemo(() => {
    const all = [...(data.data?.sections.flatMap((s) => s.fields) ?? []), ...(data.data?.hidden ?? [])];
    return new Map<string, FormField>(all.map((f) => [f.key, f]));
  }, [data.data]);
  const dirty = !!draft && !!data.data && JSON.stringify(draft) !== JSON.stringify(toDraft(data.data));

  const after = (r: RecordForm | null) => {
    if (r) qc.setQueryData(["designer-form", record], r);
    else qc.invalidateQueries({ queryKey: ["designer-form", record] });
    qc.invalidateQueries({ queryKey: ["designer"] });
    qc.invalidateQueries({ queryKey: ["record-form", record] });
  };
  const save = useMutation({
    mutationFn: () => api.put<RecordForm>(`/settings/designer/forms/${record}`, draft),
    onSuccess: (r) => { after(r); toast("success", "تم حفظ النموذج"); },
    onError: (e: Error) => toast("error", e.message),
  });
  const reset = useMutation({
    mutationFn: () => api.del(`/settings/designer/forms/${record}`),
    onSuccess: () => { after(null); setConfirmReset(false); toast("success", "عاد النموذج إلى الافتراضي"); },
    onError: (e: Error) => toast("error", e.message),
  });

  if (data.isLoading || !draft) {
    return <div className="flex flex-col gap-4" aria-busy="true">{[0, 1].map((i) => <Skeleton key={i} className="h-48 w-full rounded-xl" />)}</div>;
  }
  if (data.isError) return <ErrorBox message={(data.error as Error).message} onRetry={() => data.refetch()} />;
  const form = data.data!;

  const setSections = (sections: SectionDraft[]) => setDraft({ ...draft, sections });
  const setSection = (si: number, s: SectionDraft) => setSections(draft.sections.map((x, i) => (i === si ? s : x)));
  const hide = (si: number, key: string) => setDraft({
    sections: draft.sections.map((x, i) => (i === si ? { ...x, fields: x.fields.filter((k) => k !== key) } : x)),
    hidden: [...draft.hidden, key],
  });
  const show = (key: string) => {
    const last = draft.sections.length - 1;
    setDraft({
      sections: draft.sections.map((x, i) => (i === last ? { ...x, fields: [...x.fields, key] } : x)),
      hidden: draft.hidden.filter((k) => k !== key),
    });
  };
  const removeSection = (si: number) => {
    // Its fields go to the section before it (or the next one); the last section can't go.
    const target = si > 0 ? si - 1 : 1;
    const moved = draft.sections[si].fields;
    setSections(draft.sections.map((x, i) => (i === target ? { ...x, fields: [...x.fields, ...moved] } : x)).filter((_, i) => i !== si));
  };

  const kind = (f: FormField | undefined) => f?.builtin ? "أساسي" : "مخصص";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-bold">نموذج {form.label}</h2>
          <Badge tone={form.custom ? "brand" : "muted"}>{form.custom ? "مخصص لهذه المنشأة" : "الافتراضي"}</Badge>
        </div>
        <div className="flex items-center gap-2">
          {form.custom && (
            <Button variant="outline" size="sm" onClick={() => setConfirmReset(true)} disabled={reset.isPending}>
              <RotateCcw className="size-3.5" /> استعادة الافتراضي
            </Button>
          )}
          {dirty && <Button variant="ghost" size="sm" onClick={() => setDraft(toDraft(form))}>تجاهل التعديلات</Button>}
          <Button size="sm" onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
            {save.isPending ? <Spinner /> : <Save className="size-3.5" />} حفظ
          </Button>
        </div>
      </div>

      <EditorBlock
        title="الأقسام والحقول"
        description="رتّب الحقول داخل الأقسام وانقلها بينها. الحقل المقفل أساسي أو مطلوب فلا يُخفى."
        actions={
          <Button variant="outline" size="sm" onClick={() => setSections([...draft.sections, { id: newId("s"), label: "قسم جديد", fields: [] }])}>
            <FolderPlus className="size-3.5" /> قسم
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          {draft.sections.map((s, si) => (
            <div key={s.id} className="rounded-lg border border-border/70">
              <div className="flex items-center gap-2 border-b border-border/60 bg-secondary/40 px-3 py-2">
                <Input aria-label="اسم القسم" className="h-8 max-w-xs text-sm font-semibold" value={s.label} maxLength={64}
                       onChange={(e) => setSection(si, { ...s, label: e.target.value })} />
                <span className="text-xs text-muted-foreground">{s.fields.length} حقل</span>
                <div className="ms-auto">
                  <RowControls what={s.label} index={si} count={draft.sections.length} onMove={(d) => setSections(move(draft.sections, si, d))}
                               onRemove={() => removeSection(si)} removeLabel="حذف القسم" canRemove={draft.sections.length > 1} />
                </div>
              </div>
              <ul className="divide-y divide-border/50">
                {s.fields.map((key, fi) => {
                  const f = fields.get(key);
                  return (
                    <li key={key} className="flex flex-wrap items-center gap-2 px-3 py-1.5">
                      <span className="min-w-0 flex-1 truncate text-sm">{f?.label ?? key}</span>
                      <Badge tone={f?.builtin ? "muted" : "brand"}>{kind(f)}</Badge>
                      {f?.locked && <Lock className="size-3.5 text-muted-foreground" aria-label="لا يُخفى" />}
                      {draft.sections.length > 1 && (
                        <Select aria-label={`نقل «${f?.label ?? key}» إلى قسم`} className="h-8 w-auto text-xs" value={s.id}
                                onChange={(e) => {
                                  const to = draft.sections.findIndex((x) => x.id === e.target.value);
                                  setSections(draft.sections.map((x, i) => i === si ? { ...x, fields: x.fields.filter((k) => k !== key) }
                                    : i === to ? { ...x, fields: [...x.fields, key] } : x));
                                }}>
                          {draft.sections.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                        </Select>
                      )}
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => hide(si, key)} disabled={f?.locked}
                              aria-label={`إخفاء «${f?.label ?? key}»`}>
                        <EyeOff className="size-3.5" /> إخفاء
                      </Button>
                      <RowControls what={f?.label ?? key} index={fi} count={s.fields.length} onMove={(d) => setSection(si, { ...s, fields: move(s.fields, fi, d) })} />
                    </li>
                  );
                })}
                {!s.fields.length && <li className="px-3 py-3 text-xs text-muted-foreground">قسم فارغ: لن يظهر في النموذج.</li>}
              </ul>
            </div>
          ))}
        </div>
      </EditorBlock>

      <EditorBlock title="حقول غير ظاهرة" description="حقول متاحة لا يعرضها النموذج الآن.">
        {draft.hidden.length ? (
          <ul className="flex flex-wrap gap-2">
            {draft.hidden.map((key) => {
              const f = fields.get(key);
              return (
                <li key={key}>
                  <Button variant="outline" size="sm" onClick={() => show(key)} aria-label={`إظهار «${f?.label ?? key}»`}>
                    <Eye className="size-3.5" /> {f?.label ?? key}
                    <span className="text-[10px] text-muted-foreground">({kind(f)})</span>
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">كل الحقول ظاهرة.</p>
        )}
      </EditorBlock>

      <ConfirmDialog
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        onConfirm={() => reset.mutate()}
        title="استعادة النموذج الافتراضي"
        message={`سيعود ترتيب نموذج «${form.label}» وأقسامه إلى الافتراضي. الحقول المخصصة لا تُحذف.`}
        confirmLabel="استعادة"
      />
    </div>
  );
}
