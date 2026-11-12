import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/kit/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/kit/dialog";
import { IS_ON_PREMISE } from "@app/lib/deployment";

interface OnPremStatus {
  mode: string;
  workspace: string | null;
  licence: { status: "active" | "expired" | "revoked" | "missing" | "invalid"; valid_until: string | null; days_left: number | null };
  last_check_in_at: string | null;
}

const WARN_DAYS = 14;

/** On a single-device or LAN install: warns before the licence ends, and lets an admin enter a new key. */
export function OnPremLicenceBanner() {
  const user = useAuth((s) => s.user);
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const q = useQuery({
    queryKey: ["onprem-status"],
    queryFn: () => api.get<OnPremStatus>("/onprem/status"),
    enabled: IS_ON_PREMISE,
    refetchInterval: 10 * 60_000,
  });
  if (!IS_ON_PREMISE || !q.data) return null;

  const { status, days_left, valid_until } = q.data.licence;
  const isAdmin = user?.role === "admin";
  const until = valid_until ? new Intl.DateTimeFormat("ar-EG-u-nu-latn", { dateStyle: "long" }).format(new Date(valid_until)) : "";
  if (status === "active" && (days_left ?? 0) > WARN_DAYS) return null;

  const message =
    status === "active"
      ? `ينتهي ترخيص ميزان على هذا الجهاز في ${until} (بعد ${days_left} يوم). جدّد الاشتراك من لوحة المالك.`
      : status === "expired"
        ? "انتهى ترخيص ميزان على هذا الجهاز: البيانات للعرض فقط حتى تجدّد الاشتراك أو تدخل مفتاحًا جديدًا."
        : status === "revoked"
          ? "تم إيقاف ترخيص هذه النسخة: البيانات للعرض فقط. تواصل مع الدعم."
          : "لا يوجد ترخيص صالح لهذه النسخة: البيانات للعرض فقط. أدخل مفتاح الترخيص من لوحة المالك.";

  async function save() {
    setBusy(true);
    try {
      await api.post("/onprem/licence", { key: key.trim() });
      toast.success("تم تحديث الترخيص");
      setOpen(false);
      setKey("");
      await qc.invalidateQueries({ queryKey: ["onprem-status"] });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "تعذر تحديث الترخيص");
    } finally {
      setBusy(false);
    }
  }

  async function checkNow() {
    setBusy(true);
    try {
      const r = await api.post<{ ok: boolean }>("/onprem/check-in");
      toast[r.ok ? "success" : "error"](r.ok ? "تم التحقق مع ميزان" : "لا يوجد اتصال بالإنترنت الآن");
      await qc.invalidateQueries({ queryKey: ["onprem-status"] });
    } finally {
      setBusy(false);
    }
  }

  const severe = status !== "active";
  return (
    <div
      className={`no-print flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 border-b px-4 py-2.5 text-sm font-medium ${
        severe ? "border-destructive/30 bg-destructive/15 text-destructive-ink" : "border-warning/30 bg-warning/15 text-foreground"
      }`}
    >
      <span>{message}</span>
      {isAdmin && (
        <span className="flex gap-2">
          <Button size="sm" variant="outline" onClick={checkNow} disabled={busy}>
            <RefreshCw /> تحقق الآن
          </Button>
          <Button size="sm" onClick={() => setOpen(true)}>
            <KeyRound /> أدخل مفتاح ترخيص
          </Button>
        </span>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent dir="rtl">
          <DialogHeader>
            <DialogTitle>مفتاح ترخيص جديد</DialogTitle>
            <DialogDescription>
              انسخه من لوحة المالك (زر «تنزيل» لمساحة العمل). يُستخدم للأجهزة التي لا تتصل بالإنترنت.
            </DialogDescription>
          </DialogHeader>
          <textarea
            value={key}
            onChange={(e) => setKey(e.target.value)}
            dir="ltr"
            rows={5}
            placeholder="MZN1.…"
            className="w-full rounded-lg border border-input bg-background p-3 font-mono text-xs focus:border-ring focus:outline-none"
          />
          <DialogFooter>
            <Button onClick={save} disabled={busy || key.trim().length < 20}>
              حفظ المفتاح
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
