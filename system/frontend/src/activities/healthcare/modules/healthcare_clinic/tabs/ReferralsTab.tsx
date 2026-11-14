import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeftRight, Check, ChevronDown, ChevronUp, Lock, X } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { useClinic } from "../ClinicContext";
import QueryState from "../components/QueryState";
import { PRIORITY_LABELS, STATUS_LABELS } from "../referralLabels";
import { useClinicMutation } from "../useClinicActions";
import { CLINIC_KEYS } from "../useClinicData";
import type { Referral, ReferralDetail, ReferralPriority } from "../types";

type Box = "incoming" | "outgoing" | "all";

const PRIORITY_TONE: Record<ReferralPriority, string> = {
  routine: "border-border text-muted-foreground",
  urgent: "border-warning/40 text-warning-ink bg-warning/10",
  emergency: "border-destructive/40 text-destructive-ink bg-destructive/10",
};

function EncounterSummary({ id }: { id: string }) {
  const query = useQuery<ReferralDetail>({ queryKey: [...CLINIC_KEYS.referrals, "detail", id], queryFn: () => api.get(`/clinic/referrals/${id}`) });
  const d = query.data;
  return (
    <QueryState query={query} what="ملخص الإحالة" className="pt-2">
      {d && !d.record_access ? (
        <p className="text-[11px] text-muted-foreground flex items-center gap-1.5 pt-2">
          <Lock className="size-3" />
          ملف المريض متاح بعد قبول الإحالة (تنضم إلى فريق رعايته).
        </p>
      ) : d?.last_encounter ? (
        <div className="mt-2 rounded-lg border border-border/60 bg-muted/10 p-3 text-xs space-y-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-bold">
              آخر كشف <span className="num">{d.last_encounter.encounter_ref}</span>
              <span className="num text-muted-foreground font-normal"> ({d.last_encounter.encounter_date})</span>
            </span>
            <span className="text-muted-foreground">{d.last_encounter.doctor_name} — {d.last_encounter.department}</span>
          </div>
          <div className="num text-[11px] text-muted-foreground">
            BP {d.last_encounter.bp_systolic}/{d.last_encounter.bp_diastolic} · HR {d.last_encounter.heart_rate} · SpO2 {d.last_encounter.spo2}% · {d.last_encounter.temperature}°C
          </div>
          <div><span className="text-muted-foreground">الشكوى: </span>{d.last_encounter.chief_complaint}</div>
          <div>
            <span className="font-semibold text-primary">[{d.last_encounter.icd10_code} {d.last_encounter.icd10_description}]</span>{" "}
            {d.last_encounter.clinical_notes}
          </div>
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground pt-2">لا توجد كشوفات مسجلة لهذا المريض.</p>
      )}
    </QueryState>
  );
}

function ReferralCard({ r }: { r: Referral }) {
  const run = useClinicMutation();
  const [open, setOpen] = useState(false);
  const act = (path: string, json: object, ok: string) =>
    run(() => api.post(`/clinic/referrals/${r.id}/${path}`, json), ok, "تعذر تحديث الإحالة", ["referrals", "patients", "encounters"]);
  const decline = () => {
    const note = window.prompt("سبب الاعتذار عن الإحالة:");
    if (note && note.trim()) void act("decline", { note }, "تم الاعتذار عن الإحالة وإبلاغ الطبيب المحيل");
  };
  return (
    <Card className="p-4 border-border/70 bg-card/80 shadow-xs space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-xs font-bold text-foreground">
            {r.patient_name} <span className="num text-muted-foreground font-normal">({r.patient_mrn})</span>
          </div>
          <div className="text-[11px] text-muted-foreground mt-0.5">
            <span className="num">{r.referral_ref}</span> · من {r.from_doctor_name || "—"} إلى {r.to_department_name}
            {r.to_doctor_name ? ` (${r.to_doctor_name})` : ""}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge variant="outline" className={`text-[10px] ${PRIORITY_TONE[r.priority]}`}>{PRIORITY_LABELS[r.priority]}</Badge>
          <Badge variant="outline" className="text-[10px]">{STATUS_LABELS[r.status]}</Badge>
        </div>
      </div>
      {r.reason !== null ? (
        <div className="text-xs space-y-1">
          <div><span className="text-muted-foreground">السبب: </span>{r.reason}</div>
          {r.triage_notes && <div><span className="text-muted-foreground">الفرز: </span>{r.triage_notes}</div>}
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground flex items-center gap-1"><Lock className="size-3" />التفاصيل السريرية للطبيبين فقط</p>
      )}
      {r.response_note && <div className="text-[11px] text-muted-foreground">الرد: {r.response_note}</div>}
      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        {r.can_respond && (
          <>
            <Button size="sm" className="h-7 text-[10px] gap-1" onClick={() => void act("accept", {}, "تم قبول الإحالة وإضافتك إلى فريق رعاية المريض")}>
              <Check className="size-3" />قبول وضم المريض
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1" onClick={decline}><X className="size-3" />اعتذار</Button>
          </>
        )}
        {r.can_complete && (
          <Button size="sm" variant="outline" className="h-7 text-[10px]" onClick={() => void act("complete", {}, "تم إكمال الإحالة")}>
            إكمال الإحالة
          </Button>
        )}
        {r.reason !== null && (
          <Button size="sm" variant="ghost" className="h-7 text-[10px] gap-1 mr-auto" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}ملخص الكشف
          </Button>
        )}
      </div>
      {open && <EncounterSummary id={r.id} />}
    </Card>
  );
}

// Referrals between departments (#45): what reaches me or my department, what I sent, and for the
// front desk every referral (without the clinical text).
export default function ReferralsTab() {
  const { perms } = useClinic();
  const boxes: { id: Box; label: string }[] = [
    ...(perms.doctor ? [{ id: "incoming" as Box, label: "الواردة إليّ وإلى قسمي" }, { id: "outgoing" as Box, label: "المرسلة مني" }] : []),
    ...(perms.manage ? [{ id: "all" as Box, label: "جميع الإحالات" }] : []),
  ];
  const [box, setBox] = useState<Box>(boxes[0]?.id ?? "all");
  const query = useQuery<Referral[]>({ queryKey: [...CLINIC_KEYS.referrals, box], queryFn: () => api.get("/clinic/referrals", { box }) });
  const rows = query.data ?? [];
  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <ArrowLeftRight className="size-4 text-primary" />
            الإحالات بين الأقسام
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">يُحيل الطبيب من ملف المريض؛ وبالقبول ينضم الطبيب المستقبل إلى فريق رعايته.</p>
        </div>
        <div className="flex gap-1 rounded-lg border border-border p-0.5" role="tablist">
          {boxes.map((b) => (
            <button key={b.id} role="tab" aria-selected={box === b.id} onClick={() => setBox(b.id)}
              className={`px-3 py-1.5 text-[11px] rounded-md font-semibold cursor-pointer ${box === b.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}>
              {b.label}
            </button>
          ))}
        </div>
      </div>
      <QueryState query={query} what="الإحالات" className="">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {rows.map((r) => <ReferralCard key={r.id} r={r} />)}
          {rows.length === 0 && (
            <p className="md:col-span-2 py-8 text-center text-xs text-muted-foreground rounded-xl border border-dashed border-border">
              لا توجد إحالات هنا.
            </p>
          )}
        </div>
      </QueryState>
    </div>
  );
}
