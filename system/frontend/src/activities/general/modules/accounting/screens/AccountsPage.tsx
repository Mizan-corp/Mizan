// The chart of accounts (ADR-014 D2): the tree with each account's balance today, adding
// sub-accounts and renaming or stopping accounts, and which account each financial category
// posts to (accounting:settings to change; accounting:view to read).
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronLeft, Pencil, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import type { AccountNode, FinancialCategory, TrialBalance } from "../api";
import { type ChartRow, flattenChart, natural, TYPE_LABEL } from "../lib";
import { AccountingHeader, ExportButtons, Money, PERM, SkeletonRows } from "../components/shared";

const MONEY_KIND: Record<string, string> = { safe: "خزنة", wallet: "محفظة", drawer: "درج", default_bank: "بنك" };

export default function AccountsPage() {
  const can = useAuth((s) => s.can);
  const canEdit = can(PERM.settings);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState<ChartRow | null>(null);
  const [editing, setEditing] = useState<ChartRow | null>(null);
  const tree = useQuery({ queryKey: ["accounting", "accounts"], queryFn: () => api.get<AccountNode[]>("/accounting/accounts") });
  // Balances today: the trial balance of the whole ledger, groups rolled up.
  const tb = useQuery({
    queryKey: ["accounting", "trial-balance", "chart"],
    queryFn: () => api.get<TrialBalance>("/accounting/trial-balance", { include_zero: "true" }),
  });
  const balances = useMemo(() => new Map((tb.data?.accounts ?? []).map((a) => [a.id, a.closing])), [tb.data]);
  const rows = useMemo(() => flattenChart(tree.data ?? [], collapsed), [tree.data, collapsed]);
  const toggle = (id: string) => setCollapsed((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const allRows = useMemo(() => flattenChart(tree.data ?? []), [tree.data]);
  const exportRows = allRows.map((r) => [r.code, `${"  ".repeat(r.level)}${r.name}`, TYPE_LABEL[r.type], r.is_group ? "تجميعي" : "فرعي",
                                         r.active ? "نشط" : "موقوف", natural(r.type, balances.get(r.id) ?? 0)]);

  return (
    <div className="flex flex-col gap-6">
      <AccountingHeader
        title="دليل الحسابات"
        subtitle="الحسابات التجميعية تجمع أرصدة ما تحتها ولا يُرحَّل عليها. القيود التلقائية تعرف الحسابات بدورها، فتغيير الأسماء آمن."
        actions={<ExportButtons filename="chart-of-accounts" title="دليل الحسابات" subtitle="الأرصدة حتى اليوم"
                                columns={["الرقم", "الحساب", "النوع", "تجميعي/فرعي", "الحالة", "الرصيد"]} rows={exportRows} />}
      />
      {tree.isLoading ? (
        <SkeletonRows n={10} />
      ) : tree.isError ? (
        <ErrorBox message={(tree.error as Error).message} onRetry={() => tree.refetch()} />
      ) : !rows.length ? (
        <Empty text="دليل الحسابات فارغ" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">الرقم</th>
                <th className="p-3 text-start">الحساب</th>
                <th className="p-3 text-start">النوع</th>
                <th className="p-3 text-end">الرصيد</th>
                {canEdit && <th className="p-3" />}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className={`border-b border-line/60 last:border-0 ${r.is_group ? "bg-elevated/40 font-semibold" : ""}`}>
                  <td className="num p-3 text-xs" dir="ltr">{r.code}</td>
                  <td className="p-3">
                    <div className="flex items-center gap-1" style={{ paddingInlineStart: `${r.level * 1.25}rem` }}>
                      {r.hasChildren ? (
                        <button type="button" onClick={() => toggle(r.id)} className="rounded p-0.5 hover:bg-elevated"
                                aria-label={collapsed.has(r.id) ? "عرض الفروع" : "إخفاء الفروع"} aria-expanded={!collapsed.has(r.id)}>
                          {collapsed.has(r.id) ? <ChevronLeft className="size-4" /> : <ChevronDown className="size-4" />}
                        </button>
                      ) : <span className="inline-block w-5" />}
                      <span className={r.active ? "" : "text-muted line-through"}>{r.name}</span>
                      {r.money_kind && <Badge>{MONEY_KIND[r.money_kind]}</Badge>}
                      {!r.active && <Badge tone="warning">موقوف</Badge>}
                    </div>
                  </td>
                  <td className="p-3 text-xs text-muted">{TYPE_LABEL[r.type]}</td>
                  <td className="p-3 text-end">
                    {tb.isLoading ? "…" : balances.get(r.id) ? <Money value={natural(r.type, balances.get(r.id)!)} /> : <span className="text-muted">—</span>}
                  </td>
                  {canEdit && (
                    <td className="p-3">
                      <div className="flex justify-end gap-1">
                        {r.is_group && (
                          <Button variant="ghost" size="sm" onClick={() => setAdding(r)} aria-label={`حساب فرعي تحت ${r.name}`}>
                            <Plus className="size-4" />
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => setEditing(r)} aria-label={`تعديل ${r.name}`}>
                          <Pencil className="size-4" />
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <CategoryMapping canEdit={canEdit} chart={allRows} />
      <AddAccount parent={adding} onClose={() => setAdding(null)} />
      {editing && <EditAccount key={editing.id} account={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function AddAccount({ parent, onClose }: { parent: ChartRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [isGroup, setIsGroup] = useState(false);
  const add = useMutation({
    mutationFn: () => api.post("/accounting/accounts", { parent_id: parent!.id, name: name.trim(), code: code.trim() || null, is_group: isGroup }),
    onSuccess: () => {
      toast("success", "أُضيف الحساب");
      qc.invalidateQueries({ queryKey: ["accounting"] });
      setName(""); setCode(""); setIsGroup(false);
      onClose();
    },
  });
  return (
    <Modal open={!!parent} onClose={onClose} title={`حساب فرعي تحت «${parent?.name ?? ""}»`}>
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (name.trim() && !add.isPending) add.mutate(); }}>
        <div>
          <label htmlFor="acc-name" className="mb-1 block text-sm font-medium">اسم الحساب *</label>
          <Input id="acc-name" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label htmlFor="acc-code" className="mb-1 block text-sm font-medium">رقم الحساب (اختياري)</label>
          <Input id="acc-code" dir="ltr" className="num" maxLength={32} pattern="[0-9A-Za-z.\-]+" value={code}
                 placeholder={`${parent?.code ?? ""}001`} onChange={(e) => setCode(e.target.value)} />
          <p className="mt-1 text-xs text-muted">يُرقَّم تلقائياً تحت الحساب الأب إن تُرك فارغاً.</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isGroup} onChange={(e) => setIsGroup(e.target.checked)} />
          حساب تجميعي (تُضاف تحته حسابات ولا يُرحَّل عليه)
        </label>
        {add.isError && <ErrorBox message={(add.error as Error).message} />}
        <Button type="submit" className="h-11 font-bold" disabled={add.isPending || !name.trim()}>{add.isPending ? <Spinner /> : "إضافة"}</Button>
      </form>
    </Modal>
  );
}

function EditAccount({ account, onClose }: { account: ChartRow; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [name, setName] = useState(account.name);
  const [nameEn, setNameEn] = useState(account.name_en ?? "");
  const [active, setActive] = useState(account.active);
  const save = useMutation({
    mutationFn: () => api.put(`/accounting/accounts/${account.id}`, { name: name.trim(), name_en: nameEn.trim() || null, active }),
    onSuccess: () => { toast("success", "حُفظ الحساب"); qc.invalidateQueries({ queryKey: ["accounting"] }); onClose(); },
  });
  const usedByRules = !!account.role || !!account.money_kind;
  return (
    <Modal open onClose={onClose} title={`تعديل الحساب ${account.code}`}>
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (name.trim() && !save.isPending) save.mutate(); }}>
        <div>
          <label htmlFor="acc-edit-name" className="mb-1 block text-sm font-medium">الاسم *</label>
          <Input id="acc-edit-name" required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label htmlFor="acc-edit-en" className="mb-1 block text-sm font-medium">الاسم بالإنجليزية</label>
          <Input id="acc-edit-en" dir="ltr" maxLength={200} value={nameEn} onChange={(e) => setNameEn(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={active} disabled={usedByRules && active} onChange={(e) => setActive(e.target.checked)} />
          الحساب نشط
        </label>
        {usedByRules && <p className="text-xs text-muted">تستخدمه القيود التلقائية، فلا يمكن إيقافه.</p>}
        {save.isError && <ErrorBox message={(save.error as Error).message} />}
        <Button type="submit" className="h-11 font-bold" disabled={save.isPending || !name.trim()}>{save.isPending ? <Spinner /> : "حفظ"}</Button>
      </form>
    </Modal>
  );
}

function CategoryMapping({ canEdit, chart }: { canEdit: boolean; chart: ChartRow[] }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const cats = useQuery({ queryKey: ["financial-categories"], queryFn: () => api.get<FinancialCategory[]>("/financial-categories") });
  const set = useMutation({
    mutationFn: ({ id, account_id }: { id: string; account_id: string }) =>
      api.put(`/accounting/categories/${id}/account`, { account_id: account_id || null }),
    onSuccess: () => { toast("success", "حُفظ ربط البند"); qc.invalidateQueries({ queryKey: ["financial-categories"] }); },
    onError: (e) => toast("error", (e as Error).message),
  });
  const options = (type: string) => chart.filter((r) => !r.is_group && r.active && r.type === (type === "income" ? "income" : "expense"));
  const name = (id: string | null) => (id ? chart.find((r) => r.id === id) : undefined);
  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-base font-bold">ربط بنود الإيرادات والمصروفات بالحسابات</h2>
        <p className="text-xs text-muted">كل مصروف أو إيراد يُرحَّل على حساب بنده. البند غير المربوط يذهب إلى «مصروفات أخرى» أو «إيرادات متنوعة».</p>
      </div>
      {cats.isLoading ? (
        <SkeletonRows n={3} />
      ) : cats.isError ? (
        <ErrorBox message={(cats.error as Error).message} onRetry={() => cats.refetch()} />
      ) : !cats.data?.length ? (
        <Empty text="لا توجد بنود مالية" hint="تُضاف البنود من شاشة المالية" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">البند</th>
                <th className="p-3 text-start">النوع</th>
                <th className="p-3 text-start">الحساب</th>
              </tr>
            </thead>
            <tbody>
              {cats.data.map((c) => (
                <tr key={c.id} className="border-b border-line/60 last:border-0">
                  <td className="p-3 font-medium">{c.name}</td>
                  <td className="p-3 text-xs text-muted">{c.type === "income" ? "إيراد" : "مصروف"}</td>
                  <td className="p-3">
                    {canEdit ? (
                      <Select className="max-w-80" value={c.account_id ?? ""} disabled={set.isPending} aria-label={`حساب ${c.name}`}
                              onChange={(e) => set.mutate({ id: c.id, account_id: e.target.value })}>
                        <option value="">{c.type === "income" ? "إيرادات متنوعة (افتراضي)" : "مصروفات أخرى (افتراضي)"}</option>
                        {options(c.type).map((r) => <option key={r.id} value={r.id}>{`${r.code} — ${r.name}`}</option>)}
                      </Select>
                    ) : (
                      <span>{name(c.account_id) ? `${name(c.account_id)!.code} — ${name(c.account_id)!.name}` : "الافتراضي"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
