import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { Bed, CheckCircle2, UserPlus } from "lucide-react";
import { sound } from "@/lib/sound";
import { useClinic } from "../ClinicContext";
import { moneyEGP } from "../format";


export default function BedsTab() {
  const c = useClinic();
  const { data: { beds }, actions, openDialog, perms } = c;
  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <Bed className="size-4 text-primary" />
            مخطط الأجنحة وأسِرّة التنويم والعناية المركزة (Inpatient Wards)
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            توزيع الغرف، معدلات الإشغال اللحظية، وتسكين وإخلاء المرضى
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-medium">
            <span className="size-2 rounded-full bg-emerald-500" /> شاغر متاح
          </span>
          <span className="flex items-center gap-1.5 text-destructive-ink font-medium">
            <span className="size-2 rounded-full bg-destructive" /> مشغول
          </span>
          <span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 font-medium">
            <span className="size-2 rounded-full bg-amber-500" /> تعقيم
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {beds.map((b) => (
          <Card
            key={b.id}
            className={`p-4 border shadow-xs transition-colors bg-card/80 ${
              b.status === "occupied"
                ? "border-destructive/30 bg-destructive/[0.03]"
                : b.status === "available"
                ? "border-emerald-600/30 bg-emerald-500/[0.03] hover:border-emerald-600/60"
                : "border-amber-500/30 bg-amber-500/[0.03]"
            }`}
          >
            <div className="flex items-center justify-between pb-2 border-b border-border/50">
              <span className="num font-bold text-sm text-foreground">{b.bed_code}</span>
              <Badge
                variant="outline"
                className={
                  b.status === "occupied"
                    ? "border-destructive/40 text-destructive-ink bg-destructive/10 text-xs"
                    : b.status === "available"
                    ? "border-emerald-600/40 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 text-xs"
                    : "border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/10 text-xs"
                }
              >
                {b.status === "occupied" ? "مشغول" : b.status === "available" ? "شاغر متاح" : "قيد التعقيم"}
              </Badge>
            </div>

            <div className="mt-3 space-y-1 text-xs">
              <div className="font-semibold text-foreground">{b.ward_name}</div>
              <div className="text-muted-foreground">{b.room_number} — {b.bed_type}</div>
              <div className="num font-bold text-primary pt-1">{moneyEGP(b.daily_rate)} / اليوم</div>
            </div>

            {b.status === "occupied" && (
              <div className="mt-3 p-2 rounded-lg bg-destructive/5 border border-destructive/20 text-xs">
                <span className="text-muted-foreground block text-[11px]">المريض المقيم:</span>
                <span className="font-bold text-foreground">{b.current_patient_name}</span>
                <span className="num text-[10px] text-muted-foreground block mt-0.5">تاريخ التسكين: {b.admission_date}</span>
              </div>
            )}

            <div className="mt-4 pt-2 border-t border-border/40 flex justify-end">
              {perms.ward && b.status === "available" && (
                <Button
                  size="sm"
                  onClick={() => {
                    sound.click();
                    openDialog({ kind: "admit", bed: b });
                  }}
                  className="w-full text-xs h-7 gap-1 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                >
                  <UserPlus className="size-3.5" />
                  تسكين مريض بالسرير
                </Button>
              )}
              {perms.ward && b.status === "occupied" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => actions.dischargeBed(b.id)}
                  className="w-full text-xs h-7 border-destructive/30 text-destructive-ink hover:bg-destructive/10"
                >
                  إخلاء السرير للتعقيم
                </Button>
              )}
              {perms.ward && b.status === "cleaning" && (
                <Button
                  size="sm"
                  onClick={() => actions.cleanBed(b.id)}
                  className="w-full text-xs h-7 gap-1 bg-amber-600 hover:bg-amber-500 text-white font-semibold"
                >
                  <CheckCircle2 className="size-3.5" />
                  اعتماد جاهزية السرير
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
