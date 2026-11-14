import { Calendar, Hospital, UserPlus } from "lucide-react";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { sound } from "@/lib/sound";
import { useClinic } from "../ClinicContext";

// The clinic's masthead, with the front desk's two most common actions.
export default function ClinicHeader() {
  const { perms, openDialog } = useClinic();
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-border/80">
      <div>
        <div className="flex items-center gap-2">
          <span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary border border-primary/20">
            <Hospital className="size-5" />
          </span>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground font-serif">
            دفتر العيادات والمجمع الطبي التخصصي
          </h1>
          <Badge variant="outline" className="border-primary/30 text-primary bg-primary/5 text-xs font-mono">
            سجل سريري نشط
          </Badge>
        </div>
        <p className="text-xs sm:text-sm text-muted-foreground mt-1">
          إدارة متكاملة للسجلات الطبية (EMR)، حجز المواعيد والكشوفات، الروشتات الإلكترونية (e-Rx)، والمختبرات وأسِرّة التنويم ومطالبات التأمين
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {perms.manage && (
          <Button
            onClick={() => {
              sound.click();
              openDialog({ kind: "patient" });
            }}
            variant="outline"
            className="border-primary/30 text-foreground hover:bg-primary/5 gap-1.5 h-9 text-xs font-semibold"
          >
            <UserPlus className="size-4 text-primary" />
            فتح ملف مريض جديد (EMR)
          </Button>
        )}
        {perms.book && (
          <Button
            onClick={() => {
              sound.click();
              openDialog({ kind: "booking" });
            }}
            className="bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 h-9 text-xs font-semibold shadow-xs"
          >
            <Calendar className="size-4" />
            حجز موعد كشف فوري
          </Button>
        )}
      </div>
    </div>
  );
}
