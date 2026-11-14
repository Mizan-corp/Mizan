import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import { api } from "@/lib/api";
import { errorMessage, useDialogMutation } from "../useClinicActions";
import { CLINIC_KEYS } from "../useClinicData";
import { PRIORITY_LABELS } from "../referralLabels";
import type { Clinician, Department, PatientRef, ReferralPriority } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import { InlineRetry } from "./QueryState";
import { labelClass, selectClass } from "./formStyles";

const textareaClass = "w-full rounded-md border border-input bg-background px-3 py-2 text-xs leading-relaxed";

// Refers a patient to a department, optionally a doctor on its roster (POST /clinic/referrals, #45).
// The receiving doctor joins the care team on accepting.
export default function ReferralDialog({ patient, encounterId, onClose }: { patient: PatientRef; encounterId?: string; onClose: () => void }) {
  const { run, busy } = useDialogMutation();
  const [form, setForm] = useState({ to_department_id: "", to_doctor_user_id: "", priority: "routine" as ReferralPriority, reason: "", triage_notes: "" });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });
  const departments = useQuery<Department[]>({ queryKey: CLINIC_KEYS.departments, queryFn: () => api.get("/clinic/departments") });
  const roster = useQuery<Clinician[]>({
    queryKey: [...CLINIC_KEYS.clinicians, form.to_department_id],
    queryFn: () => api.get("/clinic/clinicians", { department_id: form.to_department_id }),
    enabled: !!form.to_department_id,
  });
  const doctors = (roster.data ?? []).filter((d) => d.is_doctor);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(
      () => api.post("/clinic/referrals", {
        patient_id: patient.id, ...form, to_doctor_user_id: form.to_doctor_user_id || null, encounter_id: encounterId ?? null,
      }),
      "تم إرسال الإحالة إلى القسم المستقبل", "تعذر إرسال الإحالة", ["referrals"],
    );
    if (ok) onClose();
  };

  return (
    <ClinicModal title={`إحالة ${patient.full_name} إلى قسم آخر`} icon={<ArrowLeftRight className="size-5 text-primary" />}
      onClose={onClose} size="lg" scroll>
      <form onSubmit={submit} className="space-y-3.5 text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="ref-dep" className={labelClass}>القسم المستقبل *</label>
            <select id="ref-dep" required value={form.to_department_id}
              onChange={(e) => set({ to_department_id: e.target.value, to_doctor_user_id: "" })} className={selectClass}>
              <option value="">اختر القسم</option>
              {(departments.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            {departments.isError && (
              <InlineRetry message={errorMessage(departments.error, "تعذر تحميل الأقسام")} onRetry={() => void departments.refetch()} />
            )}
          </div>
          <div>
            <label htmlFor="ref-doc" className={labelClass}>الطبيب (اختياري)</label>
            <select id="ref-doc" value={form.to_doctor_user_id} onChange={(e) => set({ to_doctor_user_id: e.target.value })}
              className={selectClass} disabled={!form.to_department_id}>
              <option value="">أي طبيب في القسم</option>
              {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
            </select>
            {roster.isError && <InlineRetry message={errorMessage(roster.error, "تعذر تحميل أطباء القسم")} onRetry={() => void roster.refetch()} />}
          </div>
        </div>
        <fieldset>
          <legend className={labelClass}>الأولوية</legend>
          <div className="flex gap-2" role="radiogroup">
            {(Object.keys(PRIORITY_LABELS) as ReferralPriority[]).map((p) => (
              <label key={p} className={`flex-1 cursor-pointer rounded-md border px-3 py-2 text-center font-semibold ${
                form.priority === p ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground"}`}>
                <input type="radio" name="ref-priority" value={p} checked={form.priority === p} onChange={() => set({ priority: p })} className="sr-only" />
                {PRIORITY_LABELS[p]}
              </label>
            ))}
          </div>
        </fieldset>
        <div>
          <label htmlFor="ref-reason" className={labelClass}>سبب الإحالة *</label>
          <textarea id="ref-reason" required minLength={5} rows={3} value={form.reason}
            onChange={(e) => set({ reason: e.target.value })} className={textareaClass} placeholder="مثال: اشتباه التهاب رئوي، للتقييم والمتابعة" />
        </div>
        <div>
          <label htmlFor="ref-triage" className={labelClass}>ملاحظات الفرز والحالة</label>
          <textarea id="ref-triage" rows={3} value={form.triage_notes}
            onChange={(e) => set({ triage_notes: e.target.value })} className={textareaClass} placeholder="العلامات الحيوية الحالية، ما أُعطي من علاج…" />
          <p className="text-[10px] text-muted-foreground mt-1">
            يطّلع عليها أطباء القسم المستقبل؛ وعند القبول ينضم الطبيب إلى فريق رعاية المريض ويصل إلى ملفه{encounterId ? " وملخص هذا الكشف" : ""}.
          </p>
        </div>
        <ModalActions busy={busy} onCancel={onClose} submitLabel="إرسال الإحالة" />
      </form>
    </ClinicModal>
  );
}
