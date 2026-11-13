/**
 * The module centre's community section (ADR-007 step 3): modules from outside developers,
 * installed from a signed .mzm file after the owner approves what they may access.
 */
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Blocks, Copy, FileUp, KeyRound, ShieldCheck, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { Badge } from "@/components/kit/badge";
import { Button, Modal, Spinner, useToast } from "@/components/ui";

interface Scope { id: string; text: string; new: boolean }
interface Summary {
  id: string; name: string; version: string; developer: string; description: string;
  entities: { id: string; name: string; fields: number }[]; scopes: Scope[];
  permissions: { id: string; name: string }[]; sends_to: string | null; installed_version: string | null;
}
interface Installed { id: string; name: string; version: string; developer: string; description: string; entities: { id: string; name: string }[] }

/** "حقل واحد", "حقلان", "3 حقول", "11 حقلًا". */
function fieldCount(n: number): string {
  if (n === 1) return "حقل واحد";
  if (n === 2) return "حقلان";
  if (n >= 3 && n <= 10) return `${n} حقول`;
  return `${n} حقلًا`;
}

export function CommunityModules() {
  const can = useAuth((s) => s.can);
  const { toast } = useToast();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [removing, setRemoving] = useState<Installed | null>(null);
  const [tokenFor, setTokenFor] = useState<Installed | null>(null);
  const [secret, setSecret] = useState<{ token: string; webhook_secret: string } | null>(null);
  const manage = can("community.manage");

  const list = useQuery({
    queryKey: ["community-installed"],
    queryFn: () => api.get<{ items: Installed[] }>("/community/modules"),
    enabled: manage,
  });

  const inspect = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData();
      form.append("file", f);
      return api.postForm<Summary>("/community/packages/inspect", form);
    },
    onSuccess: (s) => { setSummary(s); setAgreed(false); },
    onError: (e) => { setFile(null); toast("error", e instanceof ApiError ? e.message : "تعذر قراءة الملف"); },
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["community-installed"] });
    qc.invalidateQueries({ queryKey: ["role-screens"] });
    qc.invalidateQueries();
  };

  const install = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("file", file!);
      form.append("approved_scopes", JSON.stringify(summary!.scopes.map((s) => s.id)));
      return api.postForm<Installed>("/community/packages/install", form);
    },
    onSuccess: (m) => {
      toast("success", `تم تثبيت «${m.name}»`);
      setSummary(null);
      setFile(null);
      refresh();
    },
    onError: (e) => toast("error", e instanceof ApiError ? e.message : "تعذر التثبيت"),
  });

  const uninstall = useMutation({
    mutationFn: (v: { id: string; deleteRecords: boolean }) =>
      api.del(`/community/modules/${encodeURIComponent(v.id)}${v.deleteRecords ? "?delete_records=true" : ""}`),
    onSuccess: () => { toast("success", "أُزيلت الوحدة"); setRemoving(null); refresh(); },
    onError: (e) => toast("error", e instanceof ApiError ? e.message : "تعذر الإزالة"),
  });

  const issue = useMutation({
    mutationFn: (id: string) => api.post<{ token: string; webhook_secret: string }>(`/community/modules/${encodeURIComponent(id)}/token`),
    onSuccess: (r) => setSecret(r),
    onError: (e) => toast("error", e instanceof ApiError ? e.message : "تعذر إنشاء الرمز"),
  });

  if (!manage) return null;

  function choose(f: File | undefined) {
    if (!f) return;
    setFile(f);
    inspect.mutate(f);
  }

  const items = list.data?.items ?? [];
  return (
    <section className="flex flex-col gap-3" aria-label="وحدات المطورين">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold text-foreground">وحدات المطورين</h2>
          <p className="text-xs text-muted-foreground">وحدات من مطورين خارجيين، تُثبَّت من ملف موقَّع (.mzm) بعد موافقتك على ما تصل إليه.</p>
        </div>
        <input ref={input} type="file" accept=".mzm,application/zip" className="hidden"
               onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
        <Button size="sm" variant="outline" disabled={inspect.isPending} onClick={() => input.current?.click()}>
          {inspect.isPending ? <Spinner /> : <FileUp />} تثبيت من ملف
        </Button>
      </div>

      {items.length > 0 && (
        <ul className="divide-y divide-line rounded-xl border border-line text-sm">
          {items.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <div className="flex min-w-0 items-start gap-2.5">
                <Blocks className="mt-0.5 size-4 shrink-0 text-primary" />
                <div className="min-w-0">
                  <p className="font-bold text-foreground">{m.name} <span className="code text-xs font-normal text-muted-foreground" dir="ltr">v{m.version}</span></p>
                  <p className="text-xs text-muted-foreground">
                    المطور: <span className="code">{m.developer}</span> · {m.entities.map((e) => e.name).join("، ")}
                  </p>
                </div>
              </div>
              <span className="flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => { setSecret(null); setTokenFor(m); }} aria-label={`رمز الربط لـ ${m.name}`}>
                  <KeyRound /> رمز الربط
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setRemoving(m)} aria-label={`إزالة ${m.name}`}><Trash2 /> إزالة</Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <Modal open={!!summary} onClose={() => { setSummary(null); setFile(null); }}
             title={summary ? (summary.installed_version ? `تحديث «${summary.name}»` : `تثبيت «${summary.name}»`) : ""}>
        {summary && (
          <div className="space-y-4 text-sm">
            <p className="text-muted-foreground">
              <span className="code" dir="ltr">{summary.id} v{summary.version}</span> · المطور <span className="code">{summary.developer}</span>
              {summary.installed_version && <> · المثبت الآن <span className="code" dir="ltr">v{summary.installed_version}</span></>}
            </p>
            {summary.description && <p>{summary.description}</p>}
            <div>
              <p className="mb-1 font-semibold">يضيف</p>
              <ul className="list-disc ps-5 text-muted-foreground">
                {summary.entities.map((e) => <li key={e.id}>سجلات «{e.name}» ({fieldCount(e.fields)})</li>)}
              </ul>
            </div>
            <div className="rounded-lg border border-line p-3">
              <p className="mb-1.5 flex items-center gap-1.5 font-semibold"><ShieldCheck className="size-4 text-primary" /> يحتاج الوصول إلى</p>
              {summary.scopes.length ? (
                <ul className="space-y-1">
                  {summary.scopes.map((s) => (
                    <li key={s.id} className="flex items-center gap-2">
                      <span>• {s.text}</span>
                      {s.new && <Badge variant="warning">جديد</Badge>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted-foreground">سجلاته فقط، ولا شيء من بياناتك الأخرى.</p>
              )}
              {summary.sends_to && (
                <p className="mt-2 text-xs text-muted-foreground">
                  يرسل الأحداث التي يحتاجها إلى خادم المطور: <span className="code" dir="ltr">{summary.sends_to}</span>
                </p>
              )}
            </div>
            <label className="flex items-start gap-2">
              <input type="checkbox" className="mt-1 size-4" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
              <span>أوافق على ما تصل إليه هذه الوحدة، وأثق في مطورها.</span>
            </label>
            <div className="flex gap-2">
              <Button disabled={!agreed || install.isPending} onClick={() => install.mutate()}>
                {install.isPending ? <Spinner /> : summary.installed_version ? "تحديث" : "تثبيت"}
              </Button>
              <Button variant="outline" onClick={() => { setSummary(null); setFile(null); }}>إلغاء</Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={!!tokenFor} onClose={() => { setTokenFor(null); setSecret(null); }} title={tokenFor ? `رمز الربط لـ «${tokenFor.name}»` : ""}>
        {tokenFor && (
          <div className="space-y-4 text-sm">
            {!secret ? (
              <>
                <p className="text-muted-foreground">
                  يحتاجه خادم المطور ليصل إلى ما وافقت عليه في مساحة العمل هذه. إنشاء رمز جديد يوقف أي رمز سابق فورًا.
                </p>
                <Button disabled={issue.isPending} onClick={() => issue.mutate(tokenFor.id)}>
                  {issue.isPending ? <Spinner /> : <KeyRound />} إنشاء رمز جديد
                </Button>
              </>
            ) : (
              <>
                <p className="text-muted-foreground">انسخهما الآن وأعطهما لمطور الوحدة؛ لن يظهر الرمز مرة أخرى.</p>
                {([["رمز الربط (API)", secret.token], ["سر توقيع الإشعارات (Webhooks)", secret.webhook_secret]] as const).map(([label, value]) => (
                  <div key={label} className="space-y-1">
                    <p className="text-xs font-semibold text-muted-foreground">{label}</p>
                    <div className="flex items-center gap-2">
                      <code className="code min-w-0 flex-1 truncate rounded-md border border-line bg-muted/40 px-2 py-1.5 text-xs" dir="ltr">{value}</code>
                      <Button size="icon-sm" variant="outline" aria-label={`انسخ ${label}`}
                              onClick={() => navigator.clipboard?.writeText(value).then(() => toast("success", "نُسخ"))}>
                        <Copy />
                      </Button>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </Modal>

      <Modal open={!!removing} onClose={() => setRemoving(null)} title={removing ? `إزالة «${removing.name}»` : ""}>
        {removing && (
          <div className="space-y-4 text-sm">
            <p className="text-muted-foreground">تختفي شاشاتها. اختر ما يحدث لسجلاتها:</p>
            <div className="flex flex-wrap gap-2">
              <Button disabled={uninstall.isPending} onClick={() => uninstall.mutate({ id: removing.id, deleteRecords: false })}>
                إزالة مع الاحتفاظ بالسجلات
              </Button>
              <Button variant="destructive" disabled={uninstall.isPending} onClick={() => uninstall.mutate({ id: removing.id, deleteRecords: true })}>
                إزالة وحذف السجلات نهائيًا
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">مع الاحتفاظ: تعود السجلات عند تثبيت الوحدة مرة أخرى.</p>
          </div>
        )}
      </Modal>
    </section>
  );
}
