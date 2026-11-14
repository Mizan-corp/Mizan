import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/kit/table";
import { Calendar, CheckCircle2, Plus } from "lucide-react";
import { sound } from "@/lib/sound";
import { useClinic } from "../ClinicContext";
import { moneyEGP } from "../format";


export default function AppointmentsTab() {
  const c = useClinic();
  const { filteredAppts, actions, openDialog, perms } = c;
  return (
    <Card className="border-border/70 overflow-hidden shadow-xs bg-card/80">
      <div className="p-4 border-b border-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/10">
        <div>
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <Calendar className="size-4 text-primary" />
            جدول العيادات اليومية وقائمة النداء (Appointments & Queue)
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            تنظيم دخول المرضى، مواعيد الاستشارة، وتحصيل أتعاب الكشوفات
          </p>
        </div>
        {perms.book && (
        <Button
          onClick={() => {
            sound.click();
            openDialog({ kind: "booking" });
          }}
          size="sm"
          className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs h-8 gap-1.5 shadow-xs"
        >
          <Plus className="size-3.5" />
          حجز موعد كشف
        </Button>
        )}
      </div>

      <Table>
        <TableHeader>
          <TableRow className="bg-muted/30 hover:bg-muted/30 border-b border-border/60">
            <TableHead className="text-right">رقم الموعد والدور</TableHead>
            <TableHead className="text-right">اسم المريض والشكوى</TableHead>
            <TableHead className="text-right">الطبيب والعيادة</TableHead>
            <TableHead className="text-center">الموعد والتوقيت</TableHead>
            <TableHead className="text-right">أتعاب الكشف</TableHead>
            <TableHead className="text-center">حالة الدور</TableHead>
            <TableHead className="text-center">الإجراءات السريرية</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredAppts.map((a) => (
            <TableRow key={a.id} className="hover:bg-primary/[0.03] transition-colors border-b border-border/40">
              <TableCell>
                <div className="num font-bold text-foreground text-xs">{a.appointment_ref}</div>
                <Badge variant="outline" className="num text-[10px] mt-0.5 text-primary border-primary/30 bg-primary/5">
                  الدور #{a.queue_number}
                </Badge>
              </TableCell>
              <TableCell>
                <div className="font-bold text-foreground text-xs">{a.patient_name}</div>
                <div className="text-[11px] text-muted-foreground line-clamp-1">{a.chief_complaint}</div>
              </TableCell>
              <TableCell>
                <div className="text-xs font-medium text-foreground">{a.doctor_name}</div>
                <div className="text-[11px] text-muted-foreground">{a.department}</div>
              </TableCell>
              <TableCell className="text-center">
                <div className="num text-xs text-foreground">{a.appointment_date}</div>
                <div className="num text-[11px] text-muted-foreground">{a.time_slot}</div>
              </TableCell>
              <TableCell className="num text-xs font-bold text-foreground text-left">
                {moneyEGP(a.consultation_fee)}
              </TableCell>
              <TableCell className="text-center">
                <Badge
                  variant="outline"
                  className={
                    a.status === "in_consultation"
                      ? "border-primary/40 text-primary bg-primary/10 text-[10px] font-bold"
                      : a.status === "waiting"
                      ? "border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/10 text-[10px]"
                      : a.status === "completed"
                      ? "border-emerald-600/40 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 text-[10px]"
                      : "border-border text-muted-foreground text-[10px]"
                  }
                >
                  {a.status === "in_consultation"
                    ? "بالكشف حالياً"
                    : a.status === "waiting"
                    ? "بقائمة الانتظار"
                    : a.status === "completed"
                    ? "مكتمل الكشف"
                    : "مجدول"}
                </Badge>
              </TableCell>
              <TableCell className="text-center">
                <div className="flex items-center justify-center gap-1">
                  {perms.queue && a.status === "scheduled" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => actions.updateAppointmentStatus(a.id, "waiting")}
                      className="text-[10px] h-7 px-2 border-primary/30 text-foreground hover:bg-primary/5"
                    >
                      استدعاء للانتظار
                    </Button>
                  )}
                  {perms.queue && a.status === "waiting" && (
                    <Button
                      size="sm"
                      onClick={() => actions.updateAppointmentStatus(a.id, "in_consultation")}
                      className="text-[10px] h-7 px-2 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                    >
                      بدء الكشف الطبي
                    </Button>
                  )}
                  {perms.queue && a.status === "in_consultation" && (
                    <Button
                      size="sm"
                      onClick={() => actions.updateAppointmentStatus(a.id, "completed")}
                      className="text-[10px] h-7 px-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
                            >
                              إنهاء واعتماد
                            </Button>
                          )}
                          {a.status === "completed" && (
                            <div className="flex items-center justify-center gap-1">
                              <span className="text-emerald-400 text-xs flex items-center justify-center gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                تم الكشف
                              </span>
                              {perms.billing && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => actions.billAppointment(a.id)}
                                className="text-[10px] h-7 px-2 border-amber-500/40 text-amber-400 hover:bg-amber-500/10"
                              >
                                إصدار فاتورة
                              </Button>
                              )}
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
  );
}