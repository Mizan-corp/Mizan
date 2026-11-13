import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowUpLeft, Cloud, Copy, Monitor, Network, Plus, Users } from "lucide-react";
import { toast } from "sonner";
import { actions, type DeploymentMode, useAction, useMe, useWorkspaces, type Workspace } from "@app/lib/data";
import { cn } from "@/lib/utils";
import { DownloadButton } from "@app/DownloadDialog";
import { staffLoginUrl, useOpenWorkspace } from "@app/lib/open";
import { ago, date, errorText, LICENCE_STATUS, MODE, money, num, paidState, planLabel, SECTORS, sectorLabel, trialState } from "@app/lib/format";
import { Badge, Button, ErrorNote, Field, Input, LoadError, Modal, ModalActions, PageHeader, PageSkeleton, Select } from "@app/ui";
import Tour from "@app/Tour";

export function PlanBadge({ w }: { w: Pick<Workspace, "plan" | "trial_days_left" | "status"> & Partial<Pick<Workspace, "licence" | "paid_until">> }) {
  if (w.status === "suspended") return <Badge tone="bad">موقوفة</Badge>;
  // Single-device and LAN: the licence is what decides whether it works.
  if (w.licence && w.licence.status !== "active") {
    const l = LICENCE_STATUS[w.licence.status];
    return <Badge tone={l.tone}>{l.label}</Badge>;
  }
  if (w.licence && w.plan === "trial") return <Badge tone="ok">ترخيص حتى {date(w.licence.valid_until)}</Badge>;
  if (w.plan !== "trial") {
    const p = paidState(w.paid_until);
    return p ? <Badge tone={p.tone}>{p.text}</Badge> : <Badge tone="wine">باقة {planLabel(w.plan)}</Badge>;
  }
  const t = trialState(w.trial_days_left);
  return <Badge tone={t.tone}>{t.text}</Badge>;
}

function WorkspaceCard({ w, first, onOpen, opening, planQuery = "" }: { w: Workspace; first: boolean; onOpen: () => void; opening: boolean; planQuery?: string }) {
  const trialEnded = (w.plan === "trial" && (w.trial_days_left ?? 0) < 0) || !!paidState(w.paid_until)?.ended;
  const onPrem = w.deployment_mode !== "cloud_saas";
  return (
    <article className="flex min-w-0 flex-col rounded-2xl border border-line bg-card shadow-xs" data-tour={first ? "workspace" : undefined}>
      <div className="flex items-start justify-between gap-3 p-5 pb-4">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-bold text-ink">{w.name}</h2>
          <p className="mt-0.5 text-[13px] text-mute">
            {sectorLabel(w.sector)}
            {onPrem && <span className="text-ink-2"> · {MODE[w.deployment_mode].short}</span>}
          </p>
        </div>
        <span data-tour={first ? "plan" : undefined}>
          <PlanBadge w={w} />
        </span>
      </div>

      {onPrem ? (
        <dl className="mx-5 grid grid-cols-3 gap-3 border-y border-line-soft py-3 text-sm">
          <div>
            <dt className="text-xs text-mute">الترخيص حتى</dt>
            <dd className={cn("mt-0.5 font-semibold", w.licence?.status === "active" ? "text-ink" : "text-bad")}>
              {w.licence?.valid_until ? date(w.licence.valid_until) : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-mute">الأجهزة المثبتة</dt>
            <dd className="data mt-0.5 font-semibold text-ink">{num(w.licence?.installations ?? 0)}</dd>
          </div>
          <div>
            <dt className="text-xs text-mute">آخر اتصال</dt>
            <dd className="mt-0.5 font-semibold text-ink">{w.licence?.last_seen_at ? ago(w.licence.last_seen_at) : "لم يُثبّت بعد"}</dd>
          </div>
        </dl>
      ) : (
      <dl className="mx-5 grid grid-cols-3 gap-3 border-y border-line-soft py-3 text-sm">
        <div>
          <dt className="text-xs text-mute">المستخدمون</dt>
          <dd className="data mt-0.5 flex items-center gap-1 font-semibold text-ink">
            <Users className="size-3.5 text-mute" /> {num(w.users_count)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-mute">آخر بيع</dt>
          <dd className="mt-0.5 font-semibold text-ink">{w.last_sale_at ? ago(w.last_sale_at) : "لا يوجد"}</dd>
        </div>
        <div>
          <dt className="text-xs text-mute">{w.plan === "trial" ? "السعر" : "مدفوع حتى"}</dt>
          <dd className="mt-0.5 font-semibold text-ink">
            {w.plan === "trial" ? "مجانًا" : w.paid_until ? date(w.paid_until) : money(w.monthly_price_egp)}
          </dd>
        </div>
      </dl>
      )}

      {w.slug && !onPrem && (
        <div className="mx-5 mt-3 flex items-center gap-2 text-[13px] text-mute">
          <span className="shrink-0">دخول الموظفين:</span>
          <span className="code truncate text-ink-2">{staffLoginUrl(w.slug).replace(/^https?:\/\//, "")}</span>
          <button
            className="shrink-0 rounded p-1 hover:bg-sand hover:text-ink"
            aria-label="نسخ رابط دخول الموظفين"
            onClick={() => navigator.clipboard.writeText(staffLoginUrl(w.slug!)).then(() => toast.success("تم نسخ الرابط"))}
          >
            <Copy className="size-3.5" />
          </button>
        </div>
      )}

      <div className="mt-auto flex flex-wrap gap-2 p-5 pt-4">
        {onPrem ? (
          <span data-tour={first ? "open" : undefined} className="flex flex-1">
            <DownloadButton workspace={w} className="flex-1" />
          </span>
        ) : (
          <Button
            variant="primary"
            onClick={onOpen}
            busy={opening}
            disabled={w.status === "suspended"}
            data-tour={first ? "open" : undefined}
            className="flex-1"
          >
            افتح النظام <ArrowUpLeft />
          </Button>
        )}
        <Link to={`/workspaces/${w.id}${planQuery}`} className="flex-1">
          <Button className="w-full" variant={trialEnded ? "primary" : "secondary"}>
            {w.plan === "trial" ? "اشترك" : "الاشتراك والفواتير"}
          </Button>
        </Link>
      </div>
    </article>
  );
}

function NewWorkspace({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const create = useAction(actions.createWorkspace);
  const empty = { name: "", sector: "retail", scale: "small", demo_data: true, mode: "cloud_saas" as DeploymentMode };
  const [form, setForm] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const close = () => {
    setForm(empty);
    setError(null);
    onClose();
  };
  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutateAsync(form).then(
      (w) => {
        toast.success(w.deployment_mode === "cloud_saas" ? `تم إنشاء ${w.name}` : `تم تسجيل ${w.name}. نزّل البرنامج من صفحتها.`);
        close();
        navigate(`/workspaces/${w.id}`);
      },
      (err) => setError(errorText(err)),
    );
  }
  return (
    <Modal
      open={open}
      onClose={close}
      title="مساحة عمل جديدة"
      description="لفرع آخر أو نشاط مختلف. لها بياناتها وموظفوها واشتراكها، وتبدأ بفترة تجريبية 14 يومًا. تدخلها بنفس اسم المستخدم وكلمة المرور."
    >
      <form onSubmit={submit} className="grid gap-4">
        <fieldset>
          <legend className="mb-1.5 text-sm font-semibold text-ink">كيف ستعمل؟</legend>
          <div className="grid gap-2" role="radiogroup">
            {(["cloud_saas", "desktop", "lan"] as const).map((m) => {
              const Icon = { cloud_saas: Cloud, desktop: Monitor, lan: Network }[m];
              const on = form.mode === m;
              return (
                <label
                  key={m}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors",
                    on ? "border-wine bg-wine-soft" : "border-line hover:bg-sand/50",
                  )}
                >
                  <input type="radio" name="mode" className="sr-only" checked={on} onChange={() => setForm({ ...form, mode: m })} />
                  <Icon className={cn("mt-0.5 size-5 shrink-0", on ? "text-wine" : "text-mute")} />
                  <span>
                    <span className="block text-sm font-semibold text-ink">{MODE[m].label}</span>
                    <span className="block text-xs leading-relaxed text-mute">{MODE[m].desc}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
        <Field label="اسم المنشأة">
          <Input required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="النشاط">
          <Select value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })}>
            {SECTORS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="الحجم">
          <Select value={form.scale} onChange={(e) => setForm({ ...form, scale: e.target.value })}>
            <option value="small">فرع واحد</option>
            <option value="medium">2–3 فروع</option>
            <option value="large">4 فروع أو أكثر</option>
          </Select>
        </Field>
        {form.mode === "cloud_saas" && (
        <label className="flex items-start gap-2.5 text-sm text-ink-2">
          <input type="checkbox" className="mt-1 size-4 accent-wine" checked={form.demo_data} onChange={(e) => setForm({ ...form, demo_data: e.target.checked })} />
          املأها ببيانات تجريبية لهذا النشاط (يمكنك حذفها لاحقًا)
        </label>
        )}
        {error && <ErrorNote>{error}</ErrorNote>}
        <ModalActions>
          <Button type="submit" variant="primary" busy={create.isPending}>
            إنشاء مساحة العمل
          </Button>
          <Button variant="ghost" onClick={close}>
            إلغاء
          </Button>
        </ModalActions>
      </form>
    </Modal>
  );
}

export default function Workspaces() {
  const q = useWorkspaces();
  const me = useMe();
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const { open, opening } = useOpenWorkspace();
  const navigate = useNavigate();
  // From the website's pricing page (#79): ?plan=…&cycle=… goes to that workspace's plans.
  const wanted = params.get("plan");
  const planQuery = wanted ? `?plan=${encodeURIComponent(wanted)}${params.get("cycle") ? `&cycle=${encodeURIComponent(params.get("cycle")!)}` : ""}` : "";
  const only = q.data?.items.length === 1 ? q.data.items[0] : null;
  useEffect(() => {
    if (wanted && only) navigate(`/workspaces/${only.id}${planQuery}`, { replace: true });
  }, [wanted, only, planQuery, navigate]);

  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const items = q.data.items;
  const firstName = (me.data?.full_name ?? "").split(" ")[0];
  const touring = !!me.data && (!me.data.tour_done || params.get("tour") === "1") && items.length > 0;

  return (
    <>
      <PageHeader
        title={firstName ? `أهلًا، ${firstName}` : "مساحات العمل"}
        description={
          items.length === 1 ? "لديك مساحة عمل واحدة." : items.length === 2 ? "لديك مساحتا عمل." : `لديك ${num(items.length)} مساحات عمل.`
        }
        actions={
          <Button onClick={() => setCreating(true)} data-tour="new">
            <Plus /> مساحة عمل جديدة
          </Button>
        }
      />

      {wanted && items.length > 1 && (
        <p className="mb-4 rounded-lg bg-wine-soft px-4 py-3 text-sm text-ink-2">
          اختر مساحة العمل التي تريد لها باقة {planLabel(wanted)}، ثم «الاشتراك والفواتير».
        </p>
      )}
      {items.length ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {items.map((w, i) => (
            <WorkspaceCard key={w.id} w={w} first={i === 0} onOpen={() => open(w)} opening={opening === w.id} planQuery={planQuery} />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-line bg-card px-6 py-14 text-center">
          <p className="font-semibold text-ink">لا توجد مساحات عمل بعد.</p>
          <p className="mt-1 text-sm text-mute">أنشئ أول مساحة عمل لمنشأتك وابدأ تجربة مجانية لمدة 14 يومًا.</p>
          <Button variant="primary" className="mt-5" onClick={() => setCreating(true)}>
            <Plus /> مساحة عمل جديدة
          </Button>
        </div>
      )}

      <NewWorkspace open={creating} onClose={() => setCreating(false)} />
      {touring && (
        <Tour
          workspace={items[0]}
          onOpenWorkspace={() => open(items[0])}
          onDone={() => {
            if (params.has("tour")) setParams({}, { replace: true });
          }}
        />
      )}
    </>
  );
}
