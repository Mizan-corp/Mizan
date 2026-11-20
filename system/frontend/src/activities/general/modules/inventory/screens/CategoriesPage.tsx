// Categories and their subcategories (INV-9): add, rename, move a subcategory, delete one no active
// product uses. A product is filed under a subcategory; a category groups subcategories.
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderPlus, FolderTree, Pencil, Plus, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { type Category, type Subcategory, useCategories, useSubcategories } from "../api";
import { InventoryHeader } from "../components/InventoryHeader";
import { groupSubcategories } from "../lib";

type Form =
  | { kind: "category"; id?: string; name: string; code: string }
  | { kind: "subcategory"; id?: string; name: string; code: string; category_id: string };
type Deleting = { kind: "category"; row: Category } | { kind: "subcategory"; row: Subcategory };

export default function CategoriesPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const manage = useAuth((s) => s.can)("inventory");
  const cats = useCategories();
  const subs = useSubcategories();
  const [form, setForm] = useState<Form | null>(null);
  const [deleting, setDeleting] = useState<Deleting | null>(null);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["categories"] });
    qc.invalidateQueries({ queryKey: ["subcategories"] });
  };

  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = f.kind === "category"
        ? { name: f.name.trim(), code: f.code.trim() || null }
        : { name: f.name.trim(), code: f.code.trim() || null, category_id: f.category_id };
      const base = f.kind === "category" ? "/categories" : "/subcategories";
      return f.id ? api.put(`${base}/${f.id}`, body) : api.post(base, body);
    },
    onSuccess: (_r, f) => {
      toast("success", f.id ? "حُفظ التعديل" : f.kind === "category" ? "أُضيف التصنيف" : "أُضيف التصنيف الفرعي");
      setForm(null);
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: (d: Deleting) => api.del(`/${d.kind === "category" ? "categories" : "subcategories"}/${d.row.id}`),
    onSuccess: () => { toast("success", "حُذف"); setDeleting(null); refresh(); },
    onError: (e) => { setDeleting(null); toast("error", (e as Error).message); },
  });

  const groups = groupSubcategories(cats.data ?? [], subs.data ?? []);
  const loading = cats.isLoading || subs.isLoading;
  const failed = cats.isError ? cats : subs.isError ? subs : null;
  const valid = !!form && !!form.name.trim() && (form.kind === "category" || !!form.category_id);

  return (
    <div className="flex flex-col gap-6">
      <InventoryHeader
        title="التصنيفات"
        subtitle="تُرتَّب الأصناف في تصنيفات فرعية داخل تصنيفات رئيسية؛ يُحذف التصنيف إذا لم يرتبط به صنف نشط"
        actions={manage && (
          <Button onClick={() => setForm({ kind: "category", name: "", code: "" })}>
            <FolderPlus className="size-4" /> تصنيف جديد
          </Button>
        )}
      />

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-36 w-full rounded-2xl" />)}</div>
      ) : failed ? (
        <ErrorBox message={(failed.error as Error).message} onRetry={() => { cats.refetch(); subs.refetch(); }} />
      ) : !groups.length ? (
        <Empty text="لا توجد تصنيفات بعد" hint="أضف تصنيفاً رئيسياً (مثل «مشروبات») ثم تصنيفاته الفرعية (مثل «عصائر»)."
               icon={<FolderTree className="size-10" />}
               action={manage && <Button onClick={() => setForm({ kind: "category", name: "", code: "" })}><FolderPlus className="size-4" /> تصنيف جديد</Button>} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {groups.map(({ category, subcategories }) => (
            <section key={category.id} className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-bold">{category.name}</h2>
                  {category.code && <span className="code text-[11px] text-muted" dir="ltr">{category.code}</span>}
                </div>
                {manage && (
                  <div className="flex shrink-0 gap-1">
                    <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل ${category.name}`}
                            onClick={() => setForm({ kind: "category", id: category.id, name: category.name, code: category.code ?? "" })}>
                      <Pencil className="size-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`حذف ${category.name}`}
                            onClick={() => setDeleting({ kind: "category", row: category })}>
                      <Trash2 className="size-4 text-destructive" />
                    </Button>
                  </div>
                )}
              </div>
              {subcategories.length ? (
                <ul className="divide-y divide-line/60 rounded-xl border border-line/70">
                  {subcategories.map((s) => (
                    <li key={s.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                      <span className="min-w-0 truncate">{s.name}{s.code && <span className="code ms-2 text-[11px] text-muted" dir="ltr">{s.code}</span>}</span>
                      {manage && (
                        <span className="flex shrink-0 gap-1">
                          <Button variant="ghost" size="icon" className="size-7 px-0!" aria-label={`تعديل ${s.name}`}
                                  onClick={() => setForm({ kind: "subcategory", id: s.id, name: s.name, code: s.code ?? "", category_id: s.category_id })}>
                            <Pencil className="size-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="size-7 px-0!" aria-label={`حذف ${s.name}`}
                                  onClick={() => setDeleting({ kind: "subcategory", row: s })}>
                            <Trash2 className="size-3.5 text-destructive" />
                          </Button>
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted"><Badge tone="warning">بلا تصنيفات فرعية</Badge> أضف تصنيفاً فرعياً لتضع فيه الأصناف.</p>
              )}
              {manage && (
                <Button variant="outline" size="sm" className="self-start"
                        onClick={() => setForm({ kind: "subcategory", name: "", code: "", category_id: category.id })}>
                  <Plus className="size-4" /> تصنيف فرعي
                </Button>
              )}
            </section>
          ))}
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)}
             title={!form ? "" : form.kind === "category" ? (form.id ? "تعديل التصنيف" : "تصنيف جديد") : (form.id ? "تعديل التصنيف الفرعي" : "تصنيف فرعي جديد")}>
        {form && (
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (valid && !save.isPending) save.mutate(form); }}>
            {form.kind === "subcategory" && (
              <div>
                <label htmlFor="cat-parent" className="mb-1 block text-xs font-semibold text-muted">التصنيف الرئيسي *</label>
                <Select id="cat-parent" value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
                  {(cats.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </div>
            )}
            <div>
              <label htmlFor="cat-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
              <Input id="cat-name" autoFocus maxLength={128} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label htmlFor="cat-code" className="mb-1 block text-xs font-semibold text-muted">الكود (اختياري، للترتيب)</label>
              <Input id="cat-code" className="code" dir="ltr" maxLength={32} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </div>
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="h-10 w-full font-bold" disabled={!valid || save.isPending}>
              {save.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting)}
        title={deleting ? `حذف «${deleting.row.name}»` : ""}
        message={deleting?.kind === "category"
          ? "يُحذف التصنيف وتصنيفاته الفرعية. يُرفض الحذف إذا ارتبط بها صنف نشط؛ الأصناف الموقوفة تبقى بلا تصنيف."
          : "يُحذف التصنيف الفرعي. يُرفض الحذف إذا ارتبط به صنف نشط؛ الأصناف الموقوفة تبقى بلا تصنيف."}
        confirmLabel="حذف"
      />
    </div>
  );
}
