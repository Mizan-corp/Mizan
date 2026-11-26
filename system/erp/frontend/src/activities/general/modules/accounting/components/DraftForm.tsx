// The manual journal entry form (ADR-014 D9): date, branch, memo and lines, with the balance shown
// as it is typed and the posting rules checked in the browser; saved as a draft, or saved and posted.
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus, Scale, X } from "lucide-react";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { Button, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import type { Draft, PostResult } from "../api";
import { allowedParties, emptyLine, type LineForm, lineIssues, PARTY_LABEL, postable, requiredParty, todayCairo, toPayload, totals } from "../lib";
import { AccountSelect, PartySelect, useBranches, useChart } from "./shared";

function fromDraft(d: Draft): LineForm[] {
  return d.lines.map((l) => ({
    ...emptyLine(),
    account_id: l.account_id,
    debit: l.debit ? l.debit.toFixed(2) : "",
    credit: l.credit ? l.credit.toFixed(2) : "",
    party_type: l.party_type ?? "",
    party_id: l.party_id ?? "",
    warehouse_id: l.warehouse_id ?? "",
  }));
}

export function DraftForm({ open, draft, onClose }: { open: boolean; draft: Draft | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const chart = useChart();
  const branches = useBranches();
  const [date, setDate] = useState(todayCairo());
  const [memo, setMemo] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [lines, setLines] = useState<LineForm[]>([emptyLine(), emptyLine()]);
  const [serverProblems, setServerProblems] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    setDate(draft?.date ?? todayCairo());
    setMemo(draft?.memo ?? "");
    setWarehouseId(draft?.warehouse_id ?? "");
    setLines(draft ? [...fromDraft(draft), emptyLine()] : [emptyLine(), emptyLine()]);
    setServerProblems(draft?.problems ?? []);
  }, [open, draft]);

  const choices = useMemo(() => postable(chart.rows), [chart.rows]);
  const t = totals(lines);
  const issues = lineIssues(lines, chart.byId);

  const setLine = (key: string, patch: Partial<LineForm>) =>
    setLines((all) => all.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const onAccount = (key: string, accountId: string) => {
    const role = chart.byId.get(accountId)?.role;
    const required = requiredParty(role);
    setLines((all) => all.map((l) => {
      if (l.key !== key) return l;
      const keep = l.party_type && allowedParties(role).includes(l.party_type);
      return { ...l, account_id: accountId, party_type: keep ? l.party_type : required ?? "", party_id: keep ? l.party_id : "" };
    }));
  };

  const save = useMutation({
    mutationFn: async (post: boolean) => {
      const body = toPayload({ date, memo, warehouse_id: warehouseId, lines });
      const saved = draft ? await api.put<Draft>(`/accounting/drafts/${draft.id}`, body) : await api.post<Draft>("/accounting/drafts", body);
      if (!post) return { saved, posted: null as PostResult | null };
      if (saved.problems.length) return { saved, posted: null };
      return { saved, posted: await api.post<PostResult>(`/accounting/drafts/${saved.id}/post`) };
    },
    onSuccess: ({ saved, posted }, post) => {
      qc.invalidateQueries({ queryKey: ["accounting"] });
      if (posted) {
        for (const key of ["customers", "suppliers", "safes", "wallets"]) qc.invalidateQueries({ queryKey: [key] });
        toast("success", `رُحِّل القيد ${posted.entry.number}`);
        onClose();
      } else if (post) {
        setServerProblems(saved.problems);
        toast("warning", "حُفظت المسودة ولم تُرحَّل: راجع الملاحظات");
      } else {
        toast("success", "حُفظت المسودة");
        onClose();
      }
    },
  });

  const shown = issues.length ? issues : serverProblems;

  return (
    <Modal open={open} onClose={onClose} title={draft ? "تعديل قيد يومية (مسودة)" : "قيد يومية جديد"} wide>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => { e.preventDefault(); if (!save.isPending) save.mutate(false); }}
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor="je-date" className="mb-1 block text-sm font-medium">تاريخ القيد *</label>
            <Input id="je-date" type="date" required max={todayCairo()} value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <label htmlFor="je-branch" className="mb-1 block text-sm font-medium">الفرع</label>
            <Select id="je-branch" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              <option value="">— بدون فرع —</option>
              {branches.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </Select>
          </div>
          <div>
            <label htmlFor="je-memo" className="mb-1 block text-sm font-medium">البيان</label>
            <Input id="je-memo" maxLength={500} value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="مثال: إثبات إهلاك الشهر" />
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-2 text-start">الحساب</th>
                <th className="p-2 text-start">الطرف</th>
                <th className="w-28 p-2 text-start">مدين</th>
                <th className="w-28 p-2 text-start">دائن</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => {
                const role = chart.byId.get(l.account_id)?.role;
                const parties = allowedParties(role);
                return (
                  <tr key={l.key} className="border-b border-line/60 align-top last:border-0">
                    <td className="p-2">
                      <AccountSelect value={l.account_id} onChange={(id) => onAccount(l.key, id)} rows={choices} className="min-w-52"
                                     placeholder={chart.isLoading ? "جارٍ تحميل الدليل…" : "— اختر الحساب —"} />
                    </td>
                    <td className="p-2">
                      {parties.length ? (
                        <div className="flex flex-col gap-1">
                          {parties.length > 1 && (
                            <Select value={l.party_type} onChange={(e) => setLine(l.key, { party_type: e.target.value as LineForm["party_type"], party_id: "" })}>
                              {parties.map((p) => <option key={p} value={p}>{PARTY_LABEL[p]}</option>)}
                            </Select>
                          )}
                          {!requiredParty(role) && !l.party_type ? (
                            <button type="button" className="text-start text-xs text-primary underline"
                                    onClick={() => setLine(l.key, { party_type: parties[0] })}>
                              + {PARTY_LABEL[parties[0]]}
                            </button>
                          ) : l.party_type ? (
                            <PartySelect type={l.party_type} value={l.party_id} onChange={(id) => setLine(l.key, { party_id: id })} className="min-w-40" />
                          ) : null}
                        </div>
                      ) : (
                        <span className="text-xs text-muted">—</span>
                      )}
                    </td>
                    <td className="p-2">
                      <Input className="num text-center" inputMode="decimal" aria-label={`مدين السطر ${i + 1}`} placeholder="0.00"
                             value={l.debit} onChange={(e) => setLine(l.key, { debit: e.target.value, ...(e.target.value ? { credit: "" } : {}) })} />
                    </td>
                    <td className="p-2">
                      <Input className="num text-center" inputMode="decimal" aria-label={`دائن السطر ${i + 1}`} placeholder="0.00"
                             value={l.credit} onChange={(e) => setLine(l.key, { credit: e.target.value, ...(e.target.value ? { debit: "" } : {}) })} />
                    </td>
                    <td className="p-2">
                      <button type="button" aria-label="حذف السطر" className="rounded p-1 text-destructive hover:bg-elevated disabled:opacity-40"
                              disabled={lines.length <= 2} onClick={() => setLines((all) => all.filter((x) => x.key !== l.key))}>
                        <X size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button type="button" variant="outline" size="sm" onClick={() => setLines((all) => [...all, emptyLine()])}>
            <Plus className="size-4" /> سطر
          </Button>
          <div
            role="status"
            className={`flex flex-wrap items-center gap-4 rounded-xl border px-4 py-2 text-sm ${
              t.balanced ? "border-success/40 bg-success/10" : "border-warning/40 bg-warning/10"
            }`}
          >
            <span>مدين <b className="num">{money(t.debit)}</b></span>
            <span>دائن <b className="num">{money(t.credit)}</b></span>
            {t.balanced ? (
              <span className="flex items-center gap-1 font-bold"><CheckCircle2 className="size-4" /> متوازن</span>
            ) : (
              <span className="flex items-center gap-1 font-bold"><Scale className="size-4" /> الفرق <span className="num">{money(t.difference.abs())}</span></span>
            )}
          </div>
        </div>

        {shown.length > 0 && (
          <ul className="list-inside list-disc rounded-xl border border-line bg-elevated/50 p-3 text-xs leading-6 text-muted">
            {shown.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        {save.isError && <ErrorBox message={(save.error as Error).message} />}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="outline" disabled={save.isPending || !t.filled}>
            {save.isPending && !save.variables ? <Spinner /> : "حفظ كمسودة"}
          </Button>
          <Button type="button" disabled={save.isPending || issues.length > 0} onClick={() => save.mutate(true)}>
            {save.isPending && save.variables ? <Spinner /> : "حفظ وترحيل"}
          </Button>
          <span className="self-center text-xs text-muted">
            المسودة لا تؤثر على الأرصدة. الترحيل يسجل القيد في الدفاتر ويحرّك أرصدة العملاء والموردين والخزائن المذكورة فيه.
          </span>
        </div>
      </form>
    </Modal>
  );
}
