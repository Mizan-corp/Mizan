import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileSignature, Plus, Undo2 } from "lucide-react";
import { api, apiUrl, downloadExport } from "@/lib/api";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Input } from "@/components/kit/input";
import { useToast } from "@/components/ui";
import { errorMessage, useDialogMutation } from "../useClinicActions";
import type { Consent, ConsentKind, SignerRelation } from "../types";
import QueryState, { InlineRetry } from "./QueryState";
import SignaturePad from "./SignaturePad";
import { labelClass, selectClass } from "./formStyles";

const KINDS: Record<ConsentKind, string> = {
  procedure: "إجراء طبي", surgery: "عملية جراحية", data_sharing: "مشاركة البيانات الطبية", other: "أخرى",
};
const RELATIONS: Record<SignerRelation, string> = {
  self: "المريض نفسه", guardian: "الوصي القانوني", parent: "ولي الأمر", spouse: "الزوج / الزوجة", other: "أخرى",
};
const TEMPLATES: Record<ConsentKind, string> = {
  procedure: "أقر أنا الموقع أدناه بأن الطبيب المعالج شرح لي طبيعة الإجراء المذكور والغرض منه ومخاطره المحتملة والبدائل المتاحة، وأُتيحت لي فرصة طرح الأسئلة.\nوأوافق بإرادتي الحرة على إجرائه.",
  surgery: "أقر أنا الموقع أدناه بأن الجراح شرح لي طبيعة العملية الجراحية والتخدير اللازم ومخاطرهما المحتملة ومضاعفاتهما والبدائل المتاحة.\nوأوافق على إجراء العملية وما يستلزمه من إجراءات طبية ضرورية أثناءها.",
  data_sharing: "أوافق على مشاركة بياناتي الطبية اللازمة مع الجهة المذكورة للغرض المحدد فقط، مع الحفاظ على سريتها.\nوأعلم أنه يحق لي سحب هذه الموافقة في أي وقت.",
  other: "",
};
const textareaClass = "w-full rounded-md border border-input bg-background px-3 py-2 text-xs leading-relaxed";

function SignatureImage({ id }: { id: string }) {
  const link = useQuery<{ url: string }>({
    queryKey: ["clinic-consent-signature", id],
    queryFn: () => api.get(`/clinic/consents/${id}/signature-link`),
    staleTime: 4 * 60 * 1000, // the link lives 5 minutes
  });
  if (link.isError) return <InlineRetry message={errorMessage(link.error, "تعذر عرض التوقيع")} onRetry={() => void link.refetch()} />;
  if (!link.data) return <div className="h-16 w-40 rounded bg-muted/40 animate-pulse" aria-busy="true" />;
  return <img src={apiUrl(link.data.url)} alt="توقيع الموافقة" className="h-16 max-w-48 object-contain rounded border border-border/60 bg-white" />;
}

function NewConsent({ patientId, encounterId, onDone }: { patientId: string; encounterId?: string; onDone: () => void }) {
  const { run, busy } = useDialogMutation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ kind: "procedure" as ConsentKind, title: "", body: TEMPLATES.procedure, signer_name: "", signer_relation: "self" as SignerRelation });
  const [signature, setSignature] = useState<string | null>(null);
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!signature) return;
    const ok = await run(() => api.post(`/clinic/patients/${patientId}/consents`, { ...form, signature_png: signature, encounter_id: encounterId ?? null }),
      "تم حفظ نموذج الموافقة الموقّع", "تعذر حفظ نموذج الموافقة", []);
    if (ok) {
      void queryClient.invalidateQueries({ queryKey: ["clinic-consents", patientId] });
      onDone();
    }
  };
  return (
    <form onSubmit={submit} className="space-y-3 text-xs rounded-lg border border-border/60 p-3 bg-muted/10">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <div>
          <label htmlFor="cns-kind" className={labelClass}>نوع الموافقة</label>
          <select id="cns-kind" value={form.kind} className={selectClass}
            onChange={(e) => { const kind = e.target.value as ConsentKind; set({ kind, body: form.body === TEMPLATES[form.kind] ? TEMPLATES[kind] : form.body }); }}>
            {(Object.keys(KINDS) as ConsentKind[]).map((k) => <option key={k} value={k}>{KINDS[k]}</option>)}
          </select>
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="cns-title" className={labelClass}>الإجراء / موضوع الموافقة *</label>
          <Input id="cns-title" required minLength={3} value={form.title} onChange={(e) => set({ title: e.target.value })}
            className="h-9 text-xs" placeholder="مثال: منظار معدة تشخيصي" />
        </div>
      </div>
      <div>
        <label htmlFor="cns-body" className={labelClass}>نص الموافقة *</label>
        <textarea id="cns-body" required minLength={10} rows={4} value={form.body} onChange={(e) => set({ body: e.target.value })} className={textareaClass} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div>
          <label htmlFor="cns-signer" className={labelClass}>اسم الموقّع *</label>
          <Input id="cns-signer" required minLength={3} value={form.signer_name} onChange={(e) => set({ signer_name: e.target.value })} className="h-9 text-xs" />
        </div>
        <div>
          <label htmlFor="cns-relation" className={labelClass}>صفة الموقّع</label>
          <select id="cns-relation" value={form.signer_relation} onChange={(e) => set({ signer_relation: e.target.value as SignerRelation })} className={selectClass}>
            {(Object.keys(RELATIONS) as SignerRelation[]).map((k) => <option key={k} value={k}>{RELATIONS[k]}</option>)}
          </select>
        </div>
      </div>
      <div>
        <span className={labelClass}>التوقيع *</span>
        <SignaturePad onChange={setSignature} label="لوحة توقيع الموافقة" />
      </div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] text-muted-foreground">تُسجَّل أنت شاهداً على التوقيع، ويُحفظ التوقيع في تخزين خاص لا يُفتح إلا من ملف المريض.</p>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" className="h-8 text-xs" onClick={onDone}>إلغاء</Button>
          <Button type="submit" size="sm" className="h-8 text-xs" disabled={busy || !signature}>حفظ الموافقة الموقّعة</Button>
        </div>
      </div>
    </form>
  );
}

// Consent forms of a patient (#43): the list with the signatures, PDF, withdrawal, and signing a new one.
export default function ConsentsPanel({ patientId, encounterId, canSign }: { patientId: string; encounterId?: string; canSign: boolean }) {
  const { toast } = useToast();
  const { run } = useDialogMutation();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const query = useQuery<Consent[]>({ queryKey: ["clinic-consents", patientId], queryFn: () => api.get(`/clinic/patients/${patientId}/consents`) });
  const rows = query.data ?? [];

  const pdf = async (c: Consent) => {
    try {
      await downloadExport(`/clinic/consents/${c.id}/pdf`, undefined, `${c.consent_ref}.pdf`);
    } catch (err) {
      toast("error", errorMessage(err, "تعذر تنزيل ملف الموافقة"));
    }
  };
  const revoke = async (c: Consent) => {
    const reason = window.prompt("سبب سحب الموافقة (تبقى في الملف مع تاريخ السحب):");
    if (!reason?.trim()) return;
    const ok = await run(() => api.post(`/clinic/consents/${c.id}/revoke`, { reason }), "تم تسجيل سحب الموافقة", "تعذر سحب الموافقة", []);
    if (ok) void queryClient.invalidateQueries({ queryKey: ["clinic-consents", patientId] });
  };

  return (
    <div className="space-y-3">
      {canSign && !adding && (
        <div className="flex justify-end">
          <Button size="sm" className="h-8 text-xs gap-1.5" onClick={() => setAdding(true)}><Plus className="size-3.5" />نموذج موافقة جديد</Button>
        </div>
      )}
      {adding && <NewConsent patientId={patientId} encounterId={encounterId} onDone={() => setAdding(false)} />}
      <QueryState query={query} what="نماذج الموافقة" className="">
        {rows.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground rounded-xl border border-dashed border-border">
            لا توجد نماذج موافقة موقّعة لهذا المريض.
          </p>
        ) : (
          <ul className="space-y-2">
            {rows.map((c) => (
              <li key={c.id} className="rounded-lg border border-border/60 p-3 flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
                <div className="space-y-1 text-xs min-w-0">
                  <div className="font-bold flex items-center gap-2 flex-wrap">
                    <FileSignature className="size-3.5 text-primary shrink-0" />
                    {c.title}
                    <Badge variant="outline" className="text-[10px]">{KINDS[c.kind]}</Badge>
                    {c.status === "revoked" && <Badge variant="outline" className="text-[10px] border-destructive/40 text-destructive-ink bg-destructive/10">مسحوبة</Badge>}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    <span className="num">{c.consent_ref}</span> · وقّعها {c.signer_name} ({RELATIONS[c.signer_relation]}) ·
                    الشاهد {c.witness_name} · <span className="num">{new Date(c.signed_at).toLocaleString("ar-EG")}</span>
                  </div>
                  {c.revoked_at && <div className="text-[11px] text-destructive-ink">سبب السحب: {c.revoke_reason}</div>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <SignatureImage id={c.id} />
                  <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1" onClick={() => void pdf(c)}><Download className="size-3" />PDF</Button>
                  {canSign && c.status === "active" && (
                    <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1" onClick={() => void revoke(c)}><Undo2 className="size-3" />سحب</Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </div>
  );
}
