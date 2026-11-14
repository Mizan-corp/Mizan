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
import { useState } from "react";
import { AlertCircle, Lock, ShieldAlert, UserPlus, Users, UsersRound } from "lucide-react";
import { sound } from "@/lib/sound";
import { useClinic } from "../ClinicContext";
import ListPager from "../components/ListPager";
import BreakGlassDialog from "../components/BreakGlassDialog";
import CareTeamDialog from "../components/CareTeamDialog";

import type { PatientRef } from "../types";

export default function PatientsTab() {
  const c = useClinic();
  const {
    data, paging, search, openDialog,
  } = c;
  const { perms } = c;
  const clinician = perms.clinician;
  const [breakGlassFor, setBreakGlassFor] = useState<PatientRef | null>(null);
  const [careTeamFor, setCareTeamFor] = useState<PatientRef | null>(null);
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
        {perms.manage && (
        <Button
          onClick={() => {
            sound.click();
            openDialog({ kind: "patient" });
          }}
          size="sm"
          className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs h-8 gap-1.5 shadow-xs"
        >
          <UserPlus className="size-3.5" />
          تسجيل مريض جديد
        </Button>
        )}
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
          {data.patients.map((pat) => (
            <TableRow key={pat.id} className="hover:bg-primary/[0.03] transition-colors border-b border-border/40">
              <TableCell>
                <div className="font-bold text-foreground text-xs flex items-center gap-1.5">
                  {pat.full_name}
                  {!pat.clinical_access && (
                    <span title="الملف الطبي مقيد: لست ضمن فريق رعاية المريض" aria-label="الملف الطبي مقيد">
                      <Lock className="size-3 text-muted-foreground" />
                    </span>
                  )}
                  {pat.access === "break_glass" && (
                    <Badge variant="outline" className="text-[10px] border-destructive/40 text-destructive-ink bg-destructive/10">
                      وصول طارئ
                    </Badge>
                  )}
                </div>
                <Badge variant="outline" className="num text-[10px] mt-0.5 text-primary border-primary/30 bg-primary/5">
                  {pat.patient_mrn}
                </Badge>
              </TableCell>
              <TableCell>
                <div className="num text-xs text-foreground">{pat.phone}</div>
                <div className="num text-[11px] text-muted-foreground">{pat.national_id}</div>
              </TableCell>
              <TableCell className="text-center">
                {pat.clinical_access ? (
                  <span className="px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 text-xs font-bold">
                    {pat.blood_group}
                  </span>
                ) : (
                  <span className="text-[11px] text-muted-foreground">—</span>
                )}
                <div className="num text-[11px] text-muted-foreground mt-0.5">{pat.date_of_birth} ({pat.gender})</div>
              </TableCell>
              <TableCell>
                {pat.clinical_access ? (
                  <>
                    <div className="text-xs text-destructive-ink font-medium flex items-center gap-1">
                      <AlertCircle className="size-3 shrink-0" />
                      {pat.allergies}
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-0.5">{pat.chronic_conditions}</div>
                  </>
                ) : (
                  <div className="text-[11px] text-muted-foreground flex items-center gap-1">
                    <Lock className="size-3 shrink-0" />
                    بيانات سريرية مقيدة
                  </div>
                )}
              </TableCell>
              <TableCell>
                <div className="text-xs font-medium text-foreground">{pat.insurance_provider}</div>
                <div className="text-[11px] text-muted-foreground">
                  تحمل المريض: <span className="num font-semibold">{pat.copay_percent}%</span> {pat.insurance_policy_no !== "N/A" && `(${pat.insurance_policy_no})`}
                </div>
              </TableCell>
              <TableCell className="text-center">
                <div className="flex flex-wrap items-center justify-center gap-1">
                  {perms.book && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      openDialog({ kind: "booking", patient: pat });
                    }}
                    className="text-[10px] h-7 px-2 border-primary/30 text-foreground hover:bg-primary/5"
                  >
                    حجز كشف
                  </Button>
                  )}
                  {(perms.manage || pat.clinical_access) && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setCareTeamFor({ id: pat.id, full_name: pat.full_name })}
                    aria-label={`فريق رعاية ${pat.full_name}`}
                    className="text-[10px] h-7 px-2 border-primary/30 text-foreground hover:bg-primary/5 gap-1"
                  >
                    <UsersRound className="size-3" />
                    الفريق
                  </Button>
                  )}
                  {clinician && !pat.clinical_access && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => setBreakGlassFor({ id: pat.id, full_name: pat.full_name })}
                      className="text-[10px] h-7 px-2 gap-1"
                    >
                      <ShieldAlert className="size-3" />
                      وصول طارئ
                    </Button>
                  )}
                  {perms.doctor && pat.clinical_access && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      openDialog({ kind: "prescription", patient: pat });
                    }}
                    className="text-[10px] h-7 px-2 border-primary/30 text-foreground hover:bg-primary/5"
                  >
                    روشتة e-Rx
                  </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
          {data.patients.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="py-6 text-center text-muted-foreground text-xs">
                {search.trim() ? "لا يوجد مريض يطابق البحث (الاسم، رقم الملف، الرقم القومي أو الهاتف)." : "لا توجد ملفات مرضى بعد."}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      <ListPager paging={paging.patients} total={data.patientsTotal} pages={data.patientsPages} />
      <BreakGlassDialog patient={breakGlassFor} onClose={() => setBreakGlassFor(null)} />
      <CareTeamDialog patient={careTeamFor} onClose={() => setCareTeamFor(null)} />
    </Card>
  );
}