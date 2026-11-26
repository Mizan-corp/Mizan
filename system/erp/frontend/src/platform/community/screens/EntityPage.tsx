/**
 * A community module's records (ADR-007 D2): list, search, add, edit and delete, drawn from the
 * entity the module declares. Route: /x/:module/:entity.
 */
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Blocks, Circle, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { Badge } from "@/components/kit/badge";
import { api, ApiError } from "@/lib/api";
import { Button, Card, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { iconFor } from "@app/lib/nav";

type FieldType = "text" | "number" | "money" | "date" | "boolean" | "select" | "reference";
interface Field { key: string; type?: FieldType; label: string; required?: boolean; options?: string[]; to?: string }
interface Entity {
  id: string; name: string; name_en: string; title?: string; fields: Field[]; list?: string[];
  form?: { sections: { id: string; label?: string; fields: string[] }[] };
}
interface Definition { module: { id: string; name: string; icon?: string; version: string; developer: string }; entity: Entity; title?: string }
interface RecordRow { id: string; data: Record<string, unknown>; created_at: string | null }
interface Page { items: RecordRow[]; total: number; page: number; pages: number; labels: Record<string, string> }

const money = new Intl.NumberFormat("ar-EG-u-nu-latn", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function show(f: Field, value: unknown, labels: Record<string, string>): string {
  if (value === null || value === undefined || value === "") return "—";
  if (f.type === "boolean") return value ? "نعم" : "لا";
  if (f.type === "money") return `${money.format(Number(value))} ج.م`;
  if (f.type === "reference") return labels[String(value)] ?? "—";
  return String(value);
}

function ReferenceInput({ base, field, value, label, onChange }: {
  base: string; field: Field; value: string; label?: string; onChange: (v: string) => void;
}) {
  const [q, setQ] = useState("");
  const opts = useQuery({
    queryKey: ["community-options", base, field.key, q],
    queryFn: () => api.get<{ items: { id: string; label: string }[] }>(`${base}/options/${field.key}`, { q: q || undefined }),
  });
  const items = opts.data?.items ?? [];
  const hasCurrent = !value || items.some((i) => i.id === value);
  return (
    <div className="space-y-1.5">
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ابحث…" aria-label={`ابحث في ${field.label}`} />
      <Select value={value} onChange={(e) => onChange(e.target.value)} aria-label={field.label}>
        <option value="">—</option>
        {!hasCurrent && <option value={value}>{label ?? "المختار حاليًا"}</option>}
        {items.map((i) => (
          <option key={i.id} value={i.id}>{i.label}</option>
        ))}
      </Select>
    </div>
  );
}

function RecordForm({ base, entity, initial, labels, onDone }: {
  base: string; entity: Entity; initial: RecordRow | null; labels: Record<string, string>; onDone: () => void;
}) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [values, setValues] = useState<Record<string, unknown>>(initial?.data ?? {});
  const byKey = useMemo(() => Object.fromEntries(entity.fields.map((f) => [f.key, f])), [entity]);
  const sections = entity.form?.sections?.length
    ? entity.form.sections
    : [{ id: "main", label: undefined, fields: entity.fields.map((f) => f.key) }];
  const save = useMutation({
    mutationFn: () => (initial ? api.put(`${base}/records/${initial.id}`, values) : api.post(`${base}/records`, values)),
    onSuccess: () => {
      toast("success", initial ? "تم الحفظ" : "تمت الإضافة");
      qc.invalidateQueries({ queryKey: ["community-records", base] });
      onDone();
    },
    onError: (e) => toast("error", e instanceof ApiError ? e.message : "تعذر الحفظ"),
  });
  const set = (k: string, v: unknown) => setValues((s) => ({ ...s, [k]: v }));

  function input(f: Field) {
    const v = values[f.key];
    const id = `f-${f.key}`;
    switch (f.type) {
      case "boolean":
        return <input id={id} type="checkbox" className="size-4" checked={!!v} onChange={(e) => set(f.key, e.target.checked)} />;
      case "select":
        return (
          <Select id={id} value={String(v ?? "")} onChange={(e) => set(f.key, e.target.value || null)}>
            <option value="">—</option>
            {f.options?.map((o) => <option key={o} value={o}>{o}</option>)}
          </Select>
        );
      case "reference":
        return <ReferenceInput base={base} field={f} value={String(v ?? "")} label={labels[String(v ?? "")]} onChange={(x) => set(f.key, x || null)} />;
      case "date":
        return <Input id={id} type="date" value={String(v ?? "")} onChange={(e) => set(f.key, e.target.value || null)} />;
      case "number":
      case "money":
        return <Input id={id} type="number" step={f.type === "money" ? "0.01" : "any"} dir="ltr" value={String(v ?? "")}
                      onChange={(e) => set(f.key, e.target.value === "" ? null : e.target.value)} />;
      default:
        return <Input id={id} value={String(v ?? "")} onChange={(e) => set(f.key, e.target.value)} />;
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {sections.map((s) => (
        <fieldset key={s.id} className="space-y-3">
          {s.label && <legend className="mb-1 text-sm font-bold text-foreground">{s.label}</legend>}
          {s.fields.filter((k) => byKey[k]).map((k) => (
            <div key={k} className="space-y-1">
              <label htmlFor={`f-${k}`} className="text-xs font-semibold text-muted-foreground">
                {byKey[k].label}{byKey[k].required && <span className="text-destructive-ink"> *</span>}
              </label>
              {input(byKey[k])}
            </div>
          ))}
        </fieldset>
      ))}
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>{save.isPending ? <Spinner /> : "حفظ"}</Button>
        <Button type="button" variant="outline" onClick={onDone}>إلغاء</Button>
      </div>
    </form>
  );
}

export default function EntityPage() {
  const { module = "", entity = "" } = useParams();
  const base = `/community/${encodeURIComponent(module)}/${encodeURIComponent(entity)}`;
  const { toast } = useToast();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<RecordRow | "new" | null>(null);
  const [deleting, setDeleting] = useState<RecordRow | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setSearch(q); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => { setQ(""); setSearch(""); setPage(1); setEditing(null); }, [module, entity]);

  const def = useQuery({ queryKey: ["community-entity", base], queryFn: () => api.get<Definition>(base) });
  const rows = useQuery({
    queryKey: ["community-records", base, search, page],
    queryFn: () => api.get<Page>(`${base}/records`, { q: search || undefined, page }),
    enabled: def.isSuccess,
  });
  const remove = useMutation({
    mutationFn: (r: RecordRow) => api.del(`${base}/records/${r.id}`),
    onSuccess: () => {
      toast("success", "تم الحذف");
      setDeleting(null);
      qc.invalidateQueries({ queryKey: ["community-records", base] });
    },
    onError: (e) => toast("error", e instanceof ApiError ? e.message : "تعذر الحذف"),
  });

  if (def.isPending) return <div className="flex justify-center p-12"><Spinner /></div>;
  if (def.isError) return <ErrorBox message={def.error instanceof ApiError ? def.error.message : "تعذر تحميل الشاشة"} onRetry={() => def.refetch()} />;

  const { module: mod, entity: ent } = def.data;
  const known = iconFor(mod.icon);
  const Icon = known === Circle ? Blocks : known;
  const fields = Object.fromEntries(ent.fields.map((f) => [f.key, f]));
  const columns = (ent.list?.length ? ent.list : ent.fields.slice(0, 4).map((f) => f.key)).filter((k) => fields[k]);
  const labels = rows.data?.labels ?? {};

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-border/80 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Icon className="size-5 text-primary" />
            <h1 className="text-xl font-bold text-foreground">{def.data.title ?? ent.name}</h1>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {mod.name} · <Badge variant="outline">وحدة مطور: {mod.developer}</Badge> · <span dir="ltr">v{mod.version}</span>
          </p>
        </div>
        <Button onClick={() => setEditing("new")}><Plus /> إضافة {ent.name}</Button>
      </header>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute top-1/2 start-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="بحث…" className="ps-9" aria-label="بحث" />
      </div>

      <Card className="overflow-hidden p-0">
        {rows.isPending ? (
          <div className="flex justify-center p-10"><Spinner /></div>
        ) : rows.isError ? (
          <ErrorBox message="تعذر تحميل السجلات" onRetry={() => rows.refetch()} />
        ) : !rows.data.items.length ? (
          <Empty text={search ? "لا توجد نتائج" : `لا توجد سجلات ${ent.name} بعد`}
                 action={!search && <Button size="sm" onClick={() => setEditing("new")}><Plus /> إضافة</Button>} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                {columns.map((k) => <TableHead key={k}>{fields[k].label}</TableHead>)}
                <TableHead className="w-24"><span className="sr-only">إجراءات</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.data.items.map((r) => (
                <TableRow key={r.id}>
                  {columns.map((k) => <TableCell key={k}>{show(fields[k], r.data[k], labels)}</TableCell>)}
                  <TableCell>
                    <div className="flex gap-1">
                      <Button size="icon-sm" variant="ghost" onClick={() => setEditing(r)} aria-label="تعديل"><Pencil /></Button>
                      <Button size="icon-sm" variant="ghost" onClick={() => setDeleting(r)} aria-label="حذف"><Trash2 /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {rows.data && rows.data.pages > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>السابق</Button>
          <span className="num text-muted-foreground">{page} / {rows.data.pages}</span>
          <Button size="sm" variant="outline" disabled={page >= rows.data.pages} onClick={() => setPage((p) => p + 1)}>التالي</Button>
        </div>
      )}

      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === "new" ? `إضافة ${ent.name}` : `تعديل ${ent.name}`}>
        {editing !== null && (
          <RecordForm key={editing === "new" ? "new" : editing.id} base={base} entity={ent}
                      initial={editing === "new" ? null : editing} labels={labels} onDone={() => setEditing(null)} />
        )}
      </Modal>

      <Modal open={deleting !== null} onClose={() => setDeleting(null)} title={`حذف ${ent.name}`}>
        <p className="text-sm text-muted-foreground">سيُحذف هذا السجل. لا يمكن التراجع.</p>
        <div className="mt-4 flex gap-2">
          <Button variant="destructive" disabled={remove.isPending} onClick={() => deleting && remove.mutate(deleting)}>
            {remove.isPending ? <Spinner /> : "حذف"}
          </Button>
          <Button variant="outline" onClick={() => setDeleting(null)}>إلغاء</Button>
        </div>
      </Modal>
    </div>
  );
}
