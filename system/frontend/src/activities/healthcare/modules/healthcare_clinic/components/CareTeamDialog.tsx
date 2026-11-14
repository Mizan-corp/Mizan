import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, UserPlus, UsersRound } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/kit/dialog";
import { useAuth } from "@/stores/auth";
import type { Clinician } from "../types";


interface CareTeamMember {
  id: string;
  user_id: string;
  full_name: string;
  role: string;
  created_at: string;
}

export const CARE_TEAM_ROLES: Record<string, string> = {
  attending: "الطبيب المعالج",
  consultant: "استشاري",
  nurse: "تمريض",
  other: "أخرى",
};

const selectClass = "h-8 rounded-md border border-input bg-background px-2 text-xs";

// The clinicians on a patient's care team (#113): they read and write the patient's clinical record.
export default function CareTeamDialog({
  patient,
  onClose,
}: {
  patient: { id: string; full_name: string } | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const manage = useAuth((s) => s.can)("clinic:manage|clinic");
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("attending");
  const [busy, setBusy] = useState(false);
  const key = ["clinic-care-team", patient?.id];

  const { data: members = [], isLoading, error } = useQuery<CareTeamMember[]>({
    queryKey: key,
    queryFn: () => api.get(`/clinic/patients/${patient!.id}/care-team`),
    enabled: !!patient,
  });
  const { data: clinicians = [] } = useQuery<Clinician[]>({
    queryKey: ["clinic-clinicians"],
    queryFn: () => api.get("/clinic/clinicians"),
    enabled: !!patient && manage,
  });
  const candidates = clinicians.filter((c) => !members.some((m) => m.user_id === c.id));

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: key });
    queryClient.invalidateQueries({ queryKey: ["clinic-patients"] });
  };

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patient || !userId) return;
    setBusy(true);
    try {
      await api.post(`/clinic/patients/${patient.id}/care-team`, { user_id: userId, role });
      toast("success", "تمت الإضافة إلى فريق الرعاية");
      setUserId("");
      refresh();
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذرت الإضافة إلى فريق الرعاية");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (member: CareTeamMember) => {
    if (!patient) return;
    try {
      await api.del(`/clinic/patients/${patient.id}/care-team/${member.id}`);
      toast("success", `أُزيل ${member.full_name} من فريق الرعاية`);
      refresh();
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذرت الإزالة من فريق الرعاية");
    }
  };

  return (
    <Dialog open={!!patient} onOpenChange={(open) => !open && onClose()}>
      <DialogContent dir="rtl" className="text-right">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UsersRound className="size-5 text-primary" />
            فريق رعاية {patient?.full_name}
          </DialogTitle>
          <DialogDescription>
            يطّلع أعضاء الفريق على الملف الطبي للمريض. يُضاف الطبيب تلقائياً عند حجز موعد له.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <p className="text-xs text-muted-foreground py-4 text-center">جارٍ التحميل...</p>
        ) : error ? (
          <p className="text-xs text-destructive-ink py-4 text-center">
            {(error as Error).message || "تعذر تحميل فريق الرعاية"}
          </p>
        ) : members.length === 0 ? (
          <p className="text-xs text-muted-foreground py-4 text-center">لا يوجد أعضاء في فريق الرعاية بعد.</p>
        ) : (
          <ul className="divide-y divide-border/50 rounded-lg border border-border/60">
            {members.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-semibold text-foreground truncate">{m.full_name}</span>
                  <Badge variant="outline" className="text-[10px]">{CARE_TEAM_ROLES[m.role] || m.role}</Badge>
                </div>
                {manage && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove(m)}
                    aria-label={`إزالة ${m.full_name} من فريق الرعاية`}
                    className="h-7 px-2 text-destructive-ink"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}

        {manage && (
          <form onSubmit={add} className="flex flex-wrap items-end gap-2 pt-2 border-t border-border/40 text-xs">
            <div className="flex-1 min-w-40">
              <label htmlFor="care-team-user" className="block text-muted-foreground mb-1">إضافة عضو</label>
              <select id="care-team-user" value={userId} onChange={(e) => setUserId(e.target.value)} className={`${selectClass} w-full`}>
                <option value="">اختر طبيباً أو ممرضاً</option>
                {candidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.full_name}{c.role ? ` — ${c.role}` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="care-team-role" className="block text-muted-foreground mb-1">الدور</label>
              <select id="care-team-role" value={role} onChange={(e) => setRole(e.target.value)} className={selectClass}>
                {Object.entries(CARE_TEAM_ROLES).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <Button type="submit" size="sm" disabled={!userId || busy} className="h-8 text-xs gap-1">
              <UserPlus className="size-3.5" />
              إضافة
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
