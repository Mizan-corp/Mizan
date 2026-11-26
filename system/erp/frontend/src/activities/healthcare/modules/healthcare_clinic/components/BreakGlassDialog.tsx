import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { Button } from "@/components/kit/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/kit/dialog";
import { Textarea } from "@/components/kit/textarea";
import { errorMessage } from "../useClinicActions";

const MIN_REASON = 10;

// Break-glass (#113): a clinician outside the patient's care team opens the record for 60 minutes,
// with a reason; the access is logged and the privacy officer reviews it.
export default function BreakGlassDialog({
  patient,
  onClose,
}: {
  patient: { id: string; full_name: string } | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const valid = reason.trim().length >= MIN_REASON;

  const close = () => {
    setReason("");
    onClose();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patient || !valid) return;
    setBusy(true);
    try {
      const res: { detail?: string } = await api.post(`/clinic/patients/${patient.id}/break-glass`, { reason: reason.trim() });
      toast("success", res?.detail || "تم فتح الملف الطبي مؤقتاً");
      for (const key of ["clinic-patients", "clinic-encounters", "clinic-prescriptions", "clinic-labs"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
      close();
    } catch (err) {
      toast("error", errorMessage(err, "تعذر فتح الوصول الطارئ"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!patient} onOpenChange={(open) => !open && close()}>
      <DialogContent dir="rtl" className="text-right">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert className="size-5 text-destructive-ink" />
              وصول طارئ إلى ملف {patient?.full_name}
            </DialogTitle>
            <DialogDescription>
              لست ضمن فريق رعاية هذا المريض. يفتح الوصول الطارئ ملفه الطبي لك وحدك لمدة 60 دقيقة، ويُسجَّل
              مع السبب ويراجعه مسؤول الخصوصية.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5 text-xs">
            <label htmlFor="break-glass-reason" className="block text-muted-foreground">
              سبب الوصول *
            </label>
            <Textarea
              id="break-glass-reason"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="مثال: المريض في قسم الطوارئ فاقداً للوعي والطبيب المعالج غير متاح"
              aria-invalid={reason.length > 0 && !valid}
              className="text-xs"
            />
            <p className={reason.length > 0 && !valid ? "text-destructive-ink" : "text-muted-foreground"}>
              {MIN_REASON} أحرف على الأقل ({reason.trim().length})
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={close} className="h-8 text-xs">
              إلغاء
            </Button>
            <Button type="submit" variant="destructive" disabled={!valid || busy} className="h-8 text-xs font-semibold">
              {busy ? "جارٍ الفتح..." : "فتح الملف وتسجيل الوصول"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
