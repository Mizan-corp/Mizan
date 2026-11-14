import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { Microscope, Pill, Plus } from "lucide-react";
import { sound } from "@/lib/sound";
import { useClinic } from "../ClinicContext";
import QueryState from "../components/QueryState";

export default function RxLabsTab() {
  const c = useClinic();
  const {
    filteredRx, filteredLabs, actions, openDialog, perms,
  } = c;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Prescriptions */}
      <Card className="border-border/70 overflow-hidden shadow-xs bg-card/80">
        <div className="p-4 border-b border-border/60 flex items-center justify-between bg-muted/10">
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <Pill className="size-4 text-primary" />
            الروشتات والوصفات الطبية الإلكترونية (e-Rx)
          </h3>
          {perms.doctor && (
          <Button
            onClick={() => {
              sound.click();
              openDialog({ kind: "prescription" });
            }}
            size="sm"
            className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs h-7 px-2.5 gap-1 font-semibold shadow-xs"
          >
            <Plus className="size-3.5" />
            روشتة جديدة
          </Button>
          )}
        </div>

        <QueryState query={c.data.queries.prescriptions} what="الروشتات">
        <div className="divide-y divide-border/40">
          {filteredRx.map((rx) => (
            <div key={rx.id} className="p-4 space-y-2 hover:bg-primary/[0.02] transition">
              <div className="flex items-center justify-between">
                <span className="num font-bold text-xs text-foreground">{rx.rx_ref}</span>
                <Badge
                  variant="outline"
                  className={
                    rx.status === "dispensed"
                      ? "border-emerald-600/40 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 text-[10px]"
                      : "border-primary/40 text-primary bg-primary/10 text-[10px] font-bold"
                  }
                >
                  {rx.status === "dispensed" ? "تم الصرف بنجاح" : "بانتظار الصرف"}
                </Badge>
              </div>

              <div className="flex items-center justify-between text-xs">
                <div>
                  <span className="text-muted-foreground">المريض: </span>
                  <span className="font-bold text-foreground">{rx.patient_name}</span>
                </div>
                <div className="num text-muted-foreground text-[11px]">{rx.issue_date}</div>
              </div>

              <div className="p-2.5 rounded-lg bg-muted/20 border border-border/50 space-y-1">
                <div className="font-bold text-xs text-primary">{rx.medication_name}</div>
                <div className="text-[11px] text-muted-foreground flex items-center gap-2">
                  <span>الجرعة: {rx.dosage}</span>
                  <span>•</span>
                  <span>التكرار: {rx.frequency}</span>
                  <span>•</span>
                  <span>المدة: <span className="num font-semibold">{rx.duration_days}</span> يوم</span>
                </div>
                <div className="text-[11px] text-foreground">{rx.instructions}</div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-[11px] text-muted-foreground">الطبيب: {rx.doctor_name}</span>
                {perms.dispense && rx.status === "pending" && (
                  <Button
                    size="sm"
                    onClick={() => actions.dispensePrescription(rx.id)}
                    className="text-xs h-7 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                  >
                    صرف الدواء الآن
                  </Button>
                )}
              </div>
            </div>
          ))}
          {filteredRx.length === 0 && (
            <p className="py-8 text-center text-xs text-muted-foreground">
              {c.search.trim() ? "لا توجد روشتات تطابق البحث." : "لا توجد روشتات بعد."}
            </p>
          )}
        </div>
        </QueryState>
      </Card>

      {/* Diagnostic Labs */}
      <Card className="border-border/70 overflow-hidden shadow-xs bg-card/80">
        <div className="p-4 border-b border-border/60 flex items-center justify-between bg-muted/10">
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <Microscope className="size-4 text-primary" />
            الفحوصات والتحاليل المخبرية والتصوير الطبي
          </h3>
          {perms.doctor && (
          <Button
            onClick={() => {
              sound.click();
              openDialog({ kind: "lab" });
            }}
            size="sm"
            className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs h-7 px-2.5 gap-1 font-semibold shadow-xs"
          >
            <Plus className="size-3.5" />
            طلب فحص جديد
          </Button>
          )}
        </div>

        <QueryState query={c.data.queries.labOrders} what="طلبات المختبر">
        <div className="divide-y divide-border/40">
          {filteredLabs.map((lab) => (
            <div key={lab.id} className="p-4 space-y-2 hover:bg-primary/[0.02] transition">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="num font-bold text-xs text-foreground">{lab.order_ref}</span>
                  <span className="num text-[10px] text-muted-foreground px-1.5 py-0.5 rounded bg-muted border border-border/40">
                    {lab.specimen_barcode}
                  </span>
                </div>
                <Badge
                  variant="outline"
                  className={
                    lab.status === "reported"
                      ? "border-emerald-600/40 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 text-[10px]"
                      : "border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/10 text-[10px]"
                  }
                >
                  {lab.status === "reported" ? "معتمد وموثق" : "قيد الفحص المخبري"}
                </Badge>
              </div>

              <div className="font-bold text-xs text-foreground">{lab.test_name}</div>
              <div className="text-[11px] text-muted-foreground">{lab.category} — المريض: {lab.patient_name}</div>

              <div className="p-2.5 rounded-lg bg-muted/20 border border-border/50 space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">النتيجة:</span>
                  <span className="num font-bold text-primary">{lab.result_value}</span>
                </div>
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted-foreground">المعدل المرجعي:</span>
                  <span className="text-muted-foreground">{lab.reference_range}</span>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-[11px] text-muted-foreground">الطبيب: {lab.doctor_name}</span>
                {perms.lab && lab.status !== "reported" && (
                  <Button
                    size="sm"
                    onClick={() => {
                      openDialog({ kind: "labResult", order: lab });
                    }}
                    className="text-xs h-7 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                  >
                    تسجيل النتيجة
                  </Button>
                )}
              </div>
            </div>
          ))}
          {filteredLabs.length === 0 && (
            <p className="py-8 text-center text-xs text-muted-foreground">
              {c.search.trim() ? "لا توجد طلبات فحص تطابق البحث." : "لا توجد طلبات فحص بعد."}
            </p>
          )}
        </div>
        </QueryState>
      </Card>
    </div>
  );
}
