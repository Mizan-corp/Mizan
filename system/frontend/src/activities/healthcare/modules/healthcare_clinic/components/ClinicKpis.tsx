import type { ReactNode } from "react";
import { Bed, Calendar, Microscope, Users } from "lucide-react";
import { Card } from "@/components/kit/card";
import { useClinic } from "../ClinicContext";
import QueryState from "./QueryState";

function Kpi({ label, icon, value, children }: { label: string; icon: ReactNode; value: ReactNode; children: ReactNode }) {
  return (
    <Card className="p-4 border-border/70 bg-card/80 shadow-xs hover:border-primary/40 transition-colors">
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-xs font-medium">{label}</span>
        <div className="p-2 rounded-lg bg-primary/10 text-primary">{icon}</div>
      </div>
      <div className="mt-3">
        <div className="num text-2xl font-bold tracking-tight text-foreground">{value}</div>
        <p className="text-xs text-muted-foreground mt-1">{children}</p>
      </div>
    </Card>
  );
}

// Today's operational figures (GET /clinic/summary).
export default function ClinicKpis() {
  const { summary, queries } = useClinic().data;
  return (
    <QueryState query={{ ...queries.summary, isLoading: false }} what="مؤشرات اليوم" className="">
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      <Kpi label="مواعيد وكشوفات اليوم" icon={<Calendar className="size-4" />} value={summary.today_appointments_count}>
        <span className="num font-semibold text-primary">{summary.waiting_queue_count}</span> في صالة الانتظار
      </Kpi>
      <Kpi label="إشغال أسِرّة التنويم والأجنحة" icon={<Bed className="size-4" />} value={`${summary.bed_occupancy_percent}%`}>
        <span className="num font-semibold">{summary.occupied_beds}</span> شاغر من <span className="num font-semibold">{summary.total_beds}</span> سرير
      </Kpi>
      <Kpi label="سجلات المرضى النشطة (Master Index)" icon={<Users className="size-4" />} value={summary.total_registered_patients}>
        ملف طبي إلكتروني معتمد
      </Kpi>
      <Kpi label="الفحوصات والتحاليل المعلقة" icon={<Microscope className="size-4" />} value={summary.pending_lab_orders_count}>
        بانتظار الاعتماد المخبري
      </Kpi>
    </div>
    </QueryState>
  );
}
