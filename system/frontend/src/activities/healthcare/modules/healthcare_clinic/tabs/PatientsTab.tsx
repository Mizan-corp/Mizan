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
import { AlertCircle, UserPlus, Users } from "lucide-react";
import { sound } from "@/lib/sound";
import { useClinic } from "../ClinicContext";

export default function PatientsTab() {
  const c = useClinic();
  const {
    filteredPatients, setIsPatientModalOpen, setIsBookingOpen,
    setBookingForm, setIsRxModalOpen, setRxForm, bookingForm, rxForm,
  } = c;
  return (
    <Card className="border-border/70 overflow-hidden shadow-xs bg-card/80">
      <div className="p-4 border-b border-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/10">
        <div>
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <Users className="size-4 text-primary" />
            سجل المرضى المعتمد (Master Patient Index - EMR)
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            الملفات الطبية الرقمية، أرقام السجل الطبي (MRN)، الحساسيات الدوائية، والشركات الضامنة
          </p>
        </div>
        <Button
          onClick={() => {
            sound.click();
            setIsPatientModalOpen(true);
          }}
          size="sm"
          className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs h-8 gap-1.5 shadow-xs"
        >
          <UserPlus className="size-3.5" />
          تسجيل مريض جديد
        </Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow className="bg-muted/30 hover:bg-muted/30 border-b border-border/60">
            <TableHead className="text-right">رقم الملف (MRN) والمريض</TableHead>
            <TableHead className="text-right">الرقم القومي والتواصل</TableHead>
            <TableHead className="text-center">فصيلة الدم والميلاد</TableHead>
            <TableHead className="text-right">الحساسيات والأمراض المزمنة</TableHead>
            <TableHead className="text-right">التأمين والتحمل</TableHead>
            <TableHead className="text-center">إجراءات سريرية سريعة</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredPatients.map((pat: any) => (
            <TableRow key={pat.id} className="hover:bg-primary/[0.03] transition-colors border-b border-border/40">
              <TableCell>
                <div className="font-bold text-foreground text-xs">{pat.full_name}</div>
                <Badge variant="outline" className="num text-[10px] mt-0.5 text-primary border-primary/30 bg-primary/5">
                  {pat.patient_mrn}
                </Badge>
              </TableCell>
              <TableCell>
                <div className="num text-xs text-foreground">{pat.phone}</div>
                <div className="num text-[11px] text-muted-foreground">{pat.national_id}</div>
              </TableCell>
              <TableCell className="text-center">
                <span className="px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 text-xs font-bold">
                  {pat.blood_group}
                </span>
                <div className="num text-[11px] text-muted-foreground mt-0.5">{pat.date_of_birth} ({pat.gender})</div>
              </TableCell>
              <TableCell>
                <div className="text-xs text-destructive-ink font-medium flex items-center gap-1">
                  <AlertCircle className="size-3 shrink-0" />
                  {pat.allergies}
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{pat.chronic_conditions}</div>
              </TableCell>
              <TableCell>
                <div className="text-xs font-medium text-foreground">{pat.insurance_provider}</div>
                <div className="text-[11px] text-muted-foreground">
                  تحمل المريض: <span className="num font-semibold">{pat.copay_percent}%</span> {pat.insurance_policy_no !== "N/A" && `(${pat.insurance_policy_no})`}
                </div>
              </TableCell>
              <TableCell className="text-center">
                <div className="flex items-center justify-center gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setBookingForm({
                        ...bookingForm,
                        patient_id: pat.id,
                        patient_name: pat.full_name,
                      });
                      setIsBookingOpen(true);
                    }}
                    className="text-[10px] h-7 px-2 border-primary/30 text-foreground hover:bg-primary/5"
                  >
                    حجز كشف
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setRxForm({
                        ...rxForm,
                        patient_id: pat.id,
                        patient_name: pat.full_name,
                      });
                      setIsRxModalOpen(true);
                    }}
                    className="text-[10px] h-7 px-2 border-primary/30 text-foreground hover:bg-primary/5"
                  >
                    روشتة e-Rx
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}