import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/kit/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { Textarea } from "@/components/kit/textarea";

interface AccessLogRow {
  id: string;
  user_name: string;
  patient_id: string | null;
  patient_name: string | null;
  resource: string;
  how: string;
  rows: number;
  created_at: string;
}

interface Grant {
  id: string;
  patient_name: string;
  user_name: string;
  reason: string;
  starts_at: string;
  expires_at: string;
  revoked_at: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  state: "active" | "expired" | "revoked";
}

const RESOURCES: Record<string, string> = {
  patient: "الملف الطبي",
  encounters: "الكشوفات",
  prescriptions: "الروشتات",
  lab_orders: "التحاليل",
};

const HOW: Record<string, string> = {
  all: "صلاحية جميع المرضى",
  setting: "إعداد العيادة (الجميع)",
  team: "فريق الرعاية",
  break_glass: "وصول طارئ",
  queue: "قائمة عمل",
};

const STATES: Record<Grant["state"], { label: string; className: string }> = {
  active: { label: "سارٍ", className: "border-destructive/40 text-destructive-ink bg-destructive/10" },
  expired: { label: "منتهٍ", className: "border-border text-muted-foreground" },
  revoked: { label: "ملغى", className: "border-border text-muted-foreground line-through" },
};

const PAGE = 50;
const when = (iso: string) => new Date(iso).toLocaleString("ar-EG", { dateStyle: "short", timeStyle: "short" });

// The privacy officer's view (clinic:privacy, #113): who read which patient's clinical data and how,
// and the break-glass accesses to review.
export default function PrivacyTab() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [unreviewedOnly, setUnreviewedOnly] = useState(true);
  const [page, setPage] = useState(0);
  const [reviewing, setReviewing] = useState<Grant | null>(null);
  const [note, setNote] = useState("");

  const grants = useQuery<Grant[]>({
    queryKey: ["clinic-break-glass", unreviewedOnly],
    queryFn: () => api.get("/clinic/break-glass", { unreviewed: unreviewedOnly ? "true" : undefined }),
  });
  const log = useQuery<{ total: number; items: AccessLogRow[] }>({
    queryKey: ["clinic-access-log", page],
    queryFn: () => api.get("/clinic/access-log", { limit: PAGE, offset: page * PAGE }),
  });

  const refreshGrants = () => queryClient.invalidateQueries({ queryKey: ["clinic-break-glass"] });

  const review = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewing) return;
    try {
      await api.post(`/clinic/break-glass/${reviewing.id}/review`, { note });
      toast("success", "تم تسجيل المراجعة");
      setReviewing(null);
      setNote("");
      refreshGrants();
    } catch (err: any) {
      toast("error", err?.message || "تعذر تسجيل المراجعة");
    }
  };

  const revoke = async (g: Grant) => {
    try {
      await api.post(`/clinic/break-glass/${g.id}/revoke`);
      toast("success", "تم إلغاء الوصول الطارئ");
      refreshGrants();
    } catch (err: any) {
      toast("error", err?.message || "تعذر إلغاء الوصول");
    }
  };

  const total = log.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <div className="space-y-6">
      <Card className="border-border/70 overflow-hidden shadow-xs bg-card/80">
        <div className="p-4 border-b border-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/10">
          <div>
            <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
              <ShieldAlert className="size-4 text-primary" />
              الوصول الطارئ إلى الملفات الطبية
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              كل فتح لملف مريض من خارج فريق رعايته، مع السبب. راجع كل حالة وألغِ الوصول غير المبرر.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs text-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={unreviewedOnly}
              onChange={(e) => setUnreviewedOnly(e.target.checked)}
              className="size-4 accent-primary"
            />
            غير المراجَعة فقط
          </label>
        </div>
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30 hover:bg-muted/30">
              <TableHead className="text-right">المستخدم والمريض</TableHead>
              <TableHead className="text-right">السبب</TableHead>
              <TableHead className="text-center">الوقت</TableHead>
              <TableHead className="text-center">الحالة</TableHead>
              <TableHead className="text-center">إجراءات</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {grants.isLoading ? (
              <TableRow><TableCell colSpan={5} className="text-center text-xs text-muted-foreground py-6">جارٍ التحميل...</TableCell></TableRow>
            ) : grants.error ? (
              <TableRow><TableCell colSpan={5} className="text-center text-xs text-destructive-ink py-6">{(grants.error as Error).message}</TableCell></TableRow>
            ) : (grants.data ?? []).length === 0 ? (
              <TableRow><TableCell colSpan={5} className="text-center text-xs text-muted-foreground py-6">لا توجد حالات وصول طارئ {unreviewedOnly ? "بانتظار المراجعة" : ""}</TableCell></TableRow>
            ) : (
              (grants.data ?? []).map((g) => (
                <TableRow key={g.id}>
                  <TableCell>
                    <div className="text-xs font-bold text-foreground">{g.user_name}</div>
                    <div className="text-[11px] text-muted-foreground">المريض: {g.patient_name}</div>
                  </TableCell>
                  <TableCell className="max-w-72">
                    <p className="text-xs text-foreground whitespace-normal break-words">{g.reason}</p>
                    {g.reviewed_at && (
                      <p className="text-[11px] text-muted-foreground mt-1">المراجعة: {g.review_note || "بلا ملاحظة"}</p>
                    )}
                  </TableCell>
                  <TableCell className="text-center num text-[11px] text-muted-foreground">
                    {when(g.starts_at)}
                    <div>حتى {when(g.expires_at)}</div>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant="outline" className={`text-[10px] ${STATES[g.state].className}`}>{STATES[g.state].label}</Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      {!g.reviewed_at && (
                        <Button size="sm" variant="outline" onClick={() => setReviewing(g)} className="text-[10px] h-7 px-2">
                          مراجعة
                        </Button>
                      )}
                      {g.state === "active" && (
                        <Button size="sm" variant="destructive" onClick={() => revoke(g)} className="text-[10px] h-7 px-2">
                          إلغاء الوصول
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      <Card className="border-border/70 overflow-hidden shadow-xs bg-card/80">
        <div className="p-4 border-b border-border/60 bg-muted/10">
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <ClipboardList className="size-4 text-primary" />
            سجل الاطلاع على البيانات السريرية
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">من اطّلع على بيانات أي مريض، ومتى، وبأي صفة.</p>
        </div>
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30 hover:bg-muted/30">
              <TableHead className="text-right">الوقت</TableHead>
              <TableHead className="text-right">المستخدم</TableHead>
              <TableHead className="text-right">المريض</TableHead>
              <TableHead className="text-right">البيانات</TableHead>
              <TableHead className="text-right">صفة الوصول</TableHead>
              <TableHead className="text-center">السجلات</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {log.isLoading ? (
              <TableRow><TableCell colSpan={6} className="text-center text-xs text-muted-foreground py-6">جارٍ التحميل...</TableCell></TableRow>
            ) : log.error ? (
              <TableRow><TableCell colSpan={6} className="text-center text-xs text-destructive-ink py-6">{(log.error as Error).message}</TableCell></TableRow>
            ) : (log.data?.items ?? []).length === 0 ? (
              <TableRow><TableCell colSpan={6} className="text-center text-xs text-muted-foreground py-6">لا توجد قراءات مسجلة بعد</TableCell></TableRow>
            ) : (
              (log.data?.items ?? []).map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="num text-[11px] text-muted-foreground">{when(r.created_at)}</TableCell>
                  <TableCell className="text-xs font-medium text-foreground">{r.user_name}</TableCell>
                  <TableCell className="text-xs text-foreground">{r.patient_name || (r.patient_id ? "مريض محذوف" : "قائمة")}</TableCell>
                  <TableCell className="text-xs">{RESOURCES[r.resource] || r.resource}</TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${r.how === "break_glass" ? "border-destructive/40 text-destructive-ink bg-destructive/10" : ""}`}
                    >
                      {HOW[r.how] || r.how}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center num text-xs">{r.rows}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        {pages > 1 && (
          <div className="flex items-center justify-between p-3 border-t border-border/60 text-xs">
            <span className="text-muted-foreground">
              صفحة <span className="num">{page + 1}</span> من <span className="num">{pages}</span>
            </span>
            <div className="flex gap-1">
              <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)} className="h-7 text-[11px]">
                السابق
              </Button>
              <Button size="sm" variant="outline" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)} className="h-7 text-[11px]">
                التالي
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Dialog open={!!reviewing} onOpenChange={(open) => !open && setReviewing(null)}>
        <DialogContent dir="rtl" className="text-right">
          <form onSubmit={review} className="space-y-4">
            <DialogHeader>
              <DialogTitle>مراجعة وصول طارئ</DialogTitle>
              <DialogDescription>
                {reviewing?.user_name} — المريض: {reviewing?.patient_name}
                <span className="block mt-1 text-foreground">السبب: {reviewing?.reason}</span>
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-1.5 text-xs">
              <label htmlFor="review-note" className="block text-muted-foreground">ملاحظة المراجعة</label>
              <Textarea id="review-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)}
                placeholder="مثال: مبرر — حالة طوارئ موثقة" className="text-xs" />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setReviewing(null)} className="h-8 text-xs">إلغاء</Button>
              <Button type="submit" className="h-8 text-xs font-semibold">تسجيل المراجعة</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
