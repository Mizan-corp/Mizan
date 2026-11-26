// Expense categories (income or expense; a used one is stopped, never deleted, so history keeps it)
// and expense vendors (the parties an expense is paid to; stopped, never deleted).
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building, Pencil, Plus, Power, Tags, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { sound } from "@/lib/sound";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";

interface Category { id: string; name: string; type: "income" | "expense"; color: string | null; is_active: boolean }
interface Vendor {
  id: string; name: string; phone: string | null; address: string | null; tax_id: string | null; notes: string | null;
  is_active: boolean; expense_count: number;
}
type CategoryForm = { id?: string; name: string; type: Category["type"]; color: string };
type VendorForm = { id?: string; name: string; phone: string; address: string; tax_id: string; notes: string };

const TYPE_LABEL: Record<Category["type"], string> = { expense: "مصروفات", income: "إيرادات" };
const COLORS = ["#651E2C", "#B86B76", "#C58A35", "#27835C", "#1E3A8A", "#77716E"];

export function CategoriesVendorsWorkspace() {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <CategoriesSection />
      <VendorsSection />
    </div>
  );
}

function Rows({ n = 4 }: { n?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="جارٍ التحميل">
      {Array.from({ length: n }).map((_, i) => <Skeleton key={i} className="h-11 w-full rounded-xl" />)}
    </div>
  );
}

function CategoriesSection() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const manage = useAuth((s) => s.can("finance"));
  const [all, setAll] = useState(false);
  const [form, setForm] = useState<CategoryForm | null>(null);
  const [removing, setRemoving] = useState<Category | null>(null);
  const list = useQuery({
    queryKey: ["fin-cats", { all }],
    queryFn: () => api.get<Category[]>("/financial-categories", { include_inactive: all ? "true" : undefined }),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["fin-cats"] });
  const save = useMutation({
    mutationFn: (f: CategoryForm) => {
      const color = f.color || "#77716E";
      // The type is fixed once made: the ledger account a category maps to depends on it.
      return f.id
        ? api.put(`/financial-categories/${f.id}`, { name: f.name.trim(), color })
        : api.post("/financial-categories", { name: f.name.trim(), type: f.type, color });
    },
    onSuccess: (_r, f) => {
      sound.success();
      toast("success", f.id ? "حُفظ التصنيف" : "أُضيف التصنيف");
      setForm(null);
      refresh();
    },
    onError: () => sound.error(),
  });
  const remove = useMutation({
    mutationFn: (c: Category) => api.del(`/financial-categories/${c.id}`),
    onSuccess: () => {
      sound.success();
      toast("success", "حُذف التصنيف أو أُوقف إن كان مستخدماً");
      setRemoving(null);
      refresh();
    },
    onError: (e) => {
      sound.error();
      setRemoving(null);
      toast("error", (e as Error).message);
    },
  });
  const activate = useMutation({
    mutationFn: (c: Category) => api.put(`/financial-categories/${c.id}`, { is_active: true }),
    onSuccess: () => { toast("success", "أُعيد تفعيل التصنيف"); refresh(); },
    onError: (e) => toast("error", (e as Error).message),
  });

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-bold text-ink"><Tags className="size-4" /> تصنيفات المصروفات والإيرادات</h2>
          <p className="text-xs text-muted">التصنيف المستخدم في مصروف أو حركة درج يُوقف ولا يُحذف، ليبقى السجل كما هو.</p>
        </div>
        {manage && (
          <Button size="sm" onClick={() => setForm({ name: "", type: "expense", color: COLORS[0] })}><Plus className="size-4" /> تصنيف</Button>
        )}
      </div>
      <label className="flex items-center gap-2 text-xs text-muted">
        <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> إظهار الموقوفة
      </label>
      {list.isLoading ? <Rows /> : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <Empty text="لا توجد تصنيفات" hint="أضف تصنيفات مثل الإيجار والكهرباء والرواتب لتجميع المصروفات في التقارير" icon={<Tags className="size-10" />} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-2.5 text-start">التصنيف</th>
                <th className="p-2.5 text-start">النوع</th>
                <th className="p-2.5 text-start">الحالة</th>
                <th className="p-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((c) => (
                <tr key={c.id} className={`border-b border-line/60 last:border-0 ${c.is_active ? "" : "opacity-60"}`}>
                  <td className="p-2.5">
                    <span className="flex items-center gap-2 font-semibold">
                      <span className="size-3 rounded-full border border-line" style={{ background: c.color ?? "transparent" }} aria-hidden />
                      {c.name}
                    </span>
                  </td>
                  <td className="p-2.5 text-xs">{TYPE_LABEL[c.type] ?? c.type}</td>
                  <td className="p-2.5">{c.is_active ? <Badge tone="success">نشط</Badge> : <Badge tone="muted">موقوف</Badge>}</td>
                  <td className="p-2.5">
                    {manage && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل ${c.name}`}
                                onClick={() => setForm({ id: c.id, name: c.name, type: c.type, color: c.color ?? "" })}>
                          <Pencil className="size-4" />
                        </Button>
                        {c.is_active ? (
                          <Button variant="ghost" size="icon" className="size-8 px-0! text-danger" aria-label={`حذف ${c.name}`} onClick={() => setRemoving(c)}>
                            <Trash2 className="size-4" />
                          </Button>
                        ) : (
                          <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تفعيل ${c.name}`}
                                  disabled={activate.isPending} onClick={() => activate.mutate(c)}>
                            <Power className="size-4" />
                          </Button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "تعديل التصنيف" : "تصنيف جديد"}>
        {form && (
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!save.isPending && form.name.trim()) save.mutate(form); }}>
            <div>
              <label htmlFor="cat-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
              <Input id="cat-name" autoFocus maxLength={128} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label htmlFor="cat-type" className="mb-1 block text-xs font-semibold text-muted">النوع</label>
              <Select id="cat-type" value={form.type} disabled={!!form.id}
                      onChange={(e) => setForm({ ...form, type: e.target.value as Category["type"] })}>
                <option value="expense">مصروفات</option>
                <option value="income">إيرادات</option>
              </Select>
            </div>
            <div>
              <span className="mb-1 block text-xs font-semibold text-muted">اللون في التقارير</span>
              <div className="flex flex-wrap gap-2">
                {COLORS.map((c) => (
                  <button key={c} type="button" aria-label={`اللون ${c}`} aria-pressed={form.color === c}
                          onClick={() => setForm({ ...form, color: c })}
                          className={`size-7 rounded-full border-2 ${form.color === c ? "border-ink" : "border-transparent"}`}
                          style={{ background: c }} />
                ))}
              </div>
            </div>
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="w-full h-10 font-bold" disabled={save.isPending || !form.name.trim()}>
              {save.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>
      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && !remove.isPending && remove.mutate(removing)}
        title={`حذف التصنيف ${removing?.name ?? ""}`}
        message="إن كانت مصروفات أو حركات أدراج تحمل هذا التصنيف يُوقف ولا يُحذف، ويبقى ظاهراً في سجلها."
        confirmLabel="حذف أو إيقاف"
      />
    </section>
  );
}

function VendorsSection() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const manage = useAuth((s) => s.can("finance"));
  const [search, setSearch] = useState("");
  const [all, setAll] = useState(false);
  const [form, setForm] = useState<VendorForm | null>(null);
  const [stopping, setStopping] = useState<Vendor | null>(null);
  const list = useQuery({
    queryKey: ["fin-vendors", { search, all }],
    queryFn: () => api.get<Vendor[]>("/expense-vendors", { search: search.trim() || undefined, include_inactive: all ? "true" : undefined }),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["fin-vendors"] });
  const save = useMutation({
    mutationFn: (f: VendorForm) => {
      const body = { name: f.name.trim(), phone: f.phone.trim() || null, address: f.address.trim() || null,
                     tax_id: f.tax_id.trim() || null, notes: f.notes.trim() || null };
      return f.id ? api.put(`/expense-vendors/${f.id}`, body) : api.post("/expense-vendors", body);
    },
    onSuccess: (_r, f) => {
      sound.success();
      toast("success", f.id ? "حُفظت الجهة" : "أُضيفت الجهة");
      setForm(null);
      refresh();
    },
    onError: () => sound.error(),
  });
  const setActive = useMutation({
    mutationFn: ({ v, active }: { v: Vendor; active: boolean }) => api.put(`/expense-vendors/${v.id}`, { is_active: active }),
    onSuccess: (_r, { active }) => {
      toast("success", active ? "أُعيد تفعيل الجهة" : "أُوقفت الجهة");
      setStopping(null);
      refresh();
    },
    onError: (e) => {
      setStopping(null);
      toast("error", (e as Error).message);
    },
  });

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-bold text-ink"><Building className="size-4" /> جهات الصرف</h2>
          <p className="text-xs text-muted">من تُدفع لهم المصروفات (شركة الكهرباء، المالك، مقدم خدمة…). الموقوفة تبقى في سجل مصروفاتها.</p>
        </div>
        {manage && (
          <Button size="sm" onClick={() => setForm({ name: "", phone: "", address: "", tax_id: "", notes: "" })}><Plus className="size-4" /> جهة</Button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Input className="w-56" maxLength={128} placeholder="بحث بالاسم أو الهاتف" aria-label="بحث في الجهات" value={search}
               onChange={(e) => setSearch(e.target.value)} />
        <label className="flex items-center gap-2 text-xs text-muted">
          <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> إظهار الموقوفة
        </label>
      </div>
      {list.isLoading ? <Rows /> : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <Empty text={search ? "لا توجد جهات تطابق البحث" : "لا توجد جهات صرف"} icon={<Building className="size-10" />} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-2.5 text-start">الجهة</th>
                <th className="p-2.5 text-start">الهاتف</th>
                <th className="p-2.5 text-end">المصروفات</th>
                <th className="p-2.5" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((v) => (
                <tr key={v.id} className={`border-b border-line/60 last:border-0 ${v.is_active === false ? "opacity-60" : ""}`}>
                  <td className="p-2.5">
                    <div className="font-semibold">{v.name} {v.is_active === false && <Badge tone="muted">موقوفة</Badge>}</div>
                    {(v.tax_id || v.address) && <div className="text-[11px] text-muted">{[v.tax_id && `س.ض ${v.tax_id}`, v.address].filter(Boolean).join(" · ")}</div>}
                  </td>
                  <td className="num p-2.5 text-xs" dir="ltr">{v.phone ?? "—"}</td>
                  <td className="num p-2.5 text-end text-xs">{v.expense_count}</td>
                  <td className="p-2.5">
                    {manage && (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل ${v.name}`}
                                onClick={() => setForm({ id: v.id, name: v.name, phone: v.phone ?? "", address: v.address ?? "", tax_id: v.tax_id ?? "", notes: v.notes ?? "" })}>
                          <Pencil className="size-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={v.is_active === false ? `تفعيل ${v.name}` : `إيقاف ${v.name}`}
                                disabled={setActive.isPending}
                                onClick={() => (v.is_active === false ? setActive.mutate({ v, active: true }) : setStopping(v))}>
                          <Power className="size-4" />
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "تعديل الجهة" : "جهة صرف جديدة"}>
        {form && (
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!save.isPending && form.name.trim()) save.mutate(form); }}>
            <div>
              <label htmlFor="ven-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
              <Input id="ven-name" autoFocus maxLength={128} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="ven-phone" className="mb-1 block text-xs font-semibold text-muted">الهاتف</label>
                <Input id="ven-phone" dir="ltr" className="num" maxLength={32} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </div>
              <div>
                <label htmlFor="ven-tax" className="mb-1 block text-xs font-semibold text-muted">الرقم الضريبي</label>
                <Input id="ven-tax" dir="ltr" className="num" maxLength={64} value={form.tax_id} onChange={(e) => setForm({ ...form, tax_id: e.target.value })} />
              </div>
            </div>
            <div>
              <label htmlFor="ven-address" className="mb-1 block text-xs font-semibold text-muted">العنوان</label>
              <Input id="ven-address" maxLength={500} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </div>
            <div>
              <label htmlFor="ven-notes" className="mb-1 block text-xs font-semibold text-muted">ملاحظات</label>
              <Input id="ven-notes" maxLength={2000} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="w-full h-10 font-bold" disabled={save.isPending || !form.name.trim()}>
              {save.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>
      <ConfirmDialog
        open={!!stopping}
        onClose={() => setStopping(null)}
        onConfirm={() => stopping && setActive.mutate({ v: stopping, active: false })}
        title={`إيقاف ${stopping?.name ?? ""}`}
        message="لا تُعرض الجهة الموقوفة عند تسجيل مصروف جديد، وتبقى في سجل مصروفاتها."
        confirmLabel="إيقاف"
      />
    </section>
  );
}
