import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { ArrowLeftRight, HeartPulse, Plus } from "lucide-react";
import { sound } from "@/lib/sound";
import { useClinic } from "../ClinicContext";
import QueryState from "../components/QueryState";

export default function EMRTab() {
  const c = useClinic();
  const { filteredEncounters, openDialog, perms } = c;
  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <HeartPulse className="size-4 text-primary" />
            سجلات الاستشارات والتشخيص السريري (Clinical Encounters)
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            العلامات الحيوية (Vitals)، تصنيف الأمراض الدولي (ICD-10)، والملاحظات التخصصية
          </p>
        </div>
        {perms.doctor && (
        <Button
          onClick={() => {
            sound.click();
            openDialog({ kind: "encounter" });
          }}
          size="sm"
          className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs h-8 gap-1.5 shadow-xs font-semibold"
        >
          <Plus className="size-3.5" />
          توثيق كشف سريري جديد
        </Button>
        )}
      </div>

      <QueryState query={c.data.queries.encounters} what="الكشوفات السريرية" className="">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredEncounters.map((enc) => (
          <Card key={enc.id} className="p-4 border-border/70 space-y-3 bg-card/80 shadow-xs hover:border-primary/40 transition-colors">
            <div className="flex items-center justify-between border-b border-border/60 pb-2">
              <div>
                <span className="num font-bold text-xs text-foreground">{enc.encounter_ref}</span>
                <span className="num text-xs text-muted-foreground mr-2">({enc.encounter_date})</span>
              </div>
              <Badge variant="outline" className="border-primary/30 text-primary bg-primary/5 text-xs font-mono font-bold">
                ICD-10: {enc.icd10_code}
              </Badge>
            </div>

            <div className="flex items-center justify-between text-xs">
              <div>
                <span className="text-muted-foreground">المريض: </span>
                <span className="font-bold text-foreground">{enc.patient_name}</span>
              </div>
              <div>
                <span className="text-muted-foreground">الطبيب: </span>
                <span className="font-medium text-foreground">{enc.doctor_name} ({enc.department})</span>
              </div>
            </div>

            {/* Vitals Grid */}
            <div className="grid grid-cols-5 gap-2 p-2 rounded-lg bg-muted/20 border border-border/50 text-center">
              <div>
                <div className="text-[10px] text-muted-foreground">ضغط الدم BP</div>
                <div className="num text-xs font-bold text-foreground">{enc.bp_systolic}/{enc.bp_diastolic}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">النبض HR</div>
                <div className="num text-xs font-bold text-foreground">{enc.heart_rate} bpm</div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">الحرارة Temp</div>
                <div className="num text-xs font-bold text-foreground">{enc.temperature} °C</div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">الأكسجين SpO2</div>
                <div className="num text-xs font-bold text-foreground">{enc.spo2}%</div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">التشخيص</div>
                <div className="num text-xs font-bold text-primary">{enc.icd10_code}</div>
              </div>
            </div>

            <div>
              <div className="text-xs text-muted-foreground">الشكوى الأولية:</div>
              <div className="text-xs text-foreground font-medium mt-0.5">{enc.chief_complaint}</div>
            </div>

            <div>
              <div className="text-xs text-muted-foreground">التشخيص والملاحظات السريرية وخطة العلاج:</div>
              <div className="text-xs text-foreground bg-muted/10 p-2.5 rounded-lg border border-border/50 mt-1 leading-relaxed">
                <span className="font-semibold text-primary">[{enc.icd10_description}]</span> {enc.clinical_notes}
              </div>
            </div>

            {perms.doctor && (
              <div className="flex justify-end">
                <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1 border-primary/30"
                  onClick={() => openDialog({ kind: "referral", patient: { id: enc.patient_id, full_name: enc.patient_name }, encounterId: enc.id })}>
                  <ArrowLeftRight className="size-3" />
                  إحالة
                </Button>
              </div>
            )}
          </Card>
        ))}
        {filteredEncounters.length === 0 && (
          <p className="md:col-span-2 py-8 text-center text-xs text-muted-foreground rounded-xl border border-dashed border-border">
            {c.search.trim() ? "لا توجد كشوفات تطابق البحث." : "لا توجد كشوفات سريرية لمرضاك بعد."}
          </p>
        )}
      </div>
      </QueryState>
    </div>
  );
}