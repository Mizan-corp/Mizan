/**
 * Removing a module (ADR-006 D2): what goes with it, then the owner types `delete` and chooses to
 * keep its data hidden for 30 days (reinstalling restores it) or delete it now after an export.
 */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { Button, ErrorBox, Input, Modal, Spinner } from "@/components/ui";
import { Skeleton } from "@/components/kit/skeleton";

interface Preview {
  module: string;
  removed: { id: string; name: string }[];
  data: { module: string; table: string; rows: number }[];
  roles: string[];
  data_kept_always: string[];
  keep_days: number;
  blocked_by: string[];
}

export function UninstallDialog({ module, onClose, onDone }: {
  module: { id: string; name: string } | null;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [mode, setMode] = useState<"keep" | "delete">("keep");
  const [typed, setTyped] = useState("");
  const preview = useQuery({
    queryKey: ["uninstall-preview", module?.id],
    queryFn: () => api.get<Preview>(`/modules/${module!.id}/uninstall-preview`),
    enabled: !!module,
    retry: false,
  });
  const remove = useMutation({
    mutationFn: () => api.post<{ removed: string[]; purge_after: string | null }>(`/modules/${module!.id}/uninstall`, { confirm: typed, data: mode }),
    onSuccess: (r) => {
      setTyped(""); setMode("keep");
      onDone(r.purge_after
        ? `أزيلت الوحدة؛ بياناتها محفوظة حتى ${r.purge_after.slice(0, 10)} وتعود عند إعادة التثبيت`
        : "أزيلت الوحدة وحُذفت بياناتها (مع نسخة قابلة للتنزيل)");
    },
  });
  const p = preview.data;
  const rows = p?.data.reduce((n, d) => n + d.rows, 0) ?? 0;
  const blocked = !!p?.blocked_by.length;

  return (
    <Modal open={!!module} onClose={onClose} title={`إزالة وحدة «${module?.name ?? ""}»`}>
      {preview.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
      ) : preview.isError ? (
        <ErrorBox message={(preview.error as Error).message} />
      ) : p ? (
        <form className="flex flex-col gap-4 text-sm" onSubmit={(e) => { e.preventDefault(); if (typed.trim() === "delete" && !blocked) remove.mutate(); }}>
          {blocked ? (
            <ErrorBox message={`لا يمكن إزالتها: نشاط المنشأة يعتمد عليها (${p.blocked_by.join("، ")})`} />
          ) : (
            <>
              <div className="flex gap-2 rounded-lg border border-warning/40 bg-warning/5 p-3">
                <AlertTriangle size={18} className="mt-0.5 shrink-0 text-warning" aria-hidden />
                <ul className="flex flex-col gap-1">
                  <li>ستُزال: <strong>{p.removed.map((m) => m.name).join("، ")}</strong></li>
                  {rows > 0 && <li>بياناتها: <span className="num font-bold">{rows}</span> سجل في {p.data.length} جدول</li>}
                  {p.roles.length > 0 && <li>أدوار تستخدم صلاحياتها: {p.roles.join("، ")}</li>}
                  {p.data_kept_always.length > 0 && <li>بيانات الوحدات الأساسية لا تُحذف أبدًا لأن باقي النظام يعتمد عليها.</li>}
                </ul>
              </div>
              <fieldset className="flex flex-col gap-2">
                <legend className="mb-1 font-medium">ماذا نفعل ببياناتها؟</legend>
                <label className="flex items-start gap-2 rounded-lg border border-line p-2.5">
                  <input type="radio" name="data" checked={mode === "keep"} onChange={() => setMode("keep")} className="mt-1" />
                  <span><strong>الاحتفاظ بها {p.keep_days} يومًا</strong> مخفية؛ إعادة تثبيت الوحدة تعيدها كما كانت، وبعدها تُحذف.</span>
                </label>
                <label className="flex items-start gap-2 rounded-lg border border-line p-2.5">
                  <input type="radio" name="data" checked={mode === "delete"} onChange={() => setMode("delete")} className="mt-1" />
                  <span><strong>حذفها الآن</strong> بعد أخذ نسخة يمكنك تنزيلها من قائمة «وحدات أُزيلت».</span>
                </label>
              </fieldset>
              <label className="flex flex-col gap-1">
                للتأكيد اكتب <code className="rounded bg-secondary px-1" dir="ltr">delete</code>
                <Input dir="ltr" autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="اكتب delete للتأكيد" />
              </label>
            </>
          )}
          {remove.isError && <ErrorBox message={(remove.error as Error).message} />}
          <div className="flex gap-2">
            <Button type="submit" variant="danger" disabled={blocked || typed.trim() !== "delete" || remove.isPending}>
              {remove.isPending ? <Spinner /> : "إزالة الوحدة"}
            </Button>
            <Button type="button" variant="outline" onClick={onClose}>إلغاء</Button>
          </div>
        </form>
      ) : null}
    </Modal>
  );
}
