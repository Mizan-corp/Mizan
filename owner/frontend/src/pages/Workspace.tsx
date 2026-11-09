import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowUpLeft, Check, ChevronRight, CreditCard, ShieldCheck } from "lucide-react";
import { actions, type Invoice, type Owner, type Plan, useMe, usePlans, useWorkspace, type Workspace as WorkspaceT } from "@app/lib/data";
import { useOpenWorkspace } from "@app/lib/open";
import { date, errorText, money, planLabel, sectorLabel, trialState } from "@app/lib/format";
import { cn } from "@/lib/utils";
import { Button, ErrorNote, Field, Input, LoadError, Meter, Modal, ModalActions, PageSkeleton, Panel, Money } from "@app/ui";
import { PlanBadge } from "@app/pages/Workspaces";
import { InvoiceTable } from "@app/pages/Invoices";

const ORDER = ["trial", "starter", "pro", "enterprise"];

function CurrentPlan({ w }: { w: WorkspaceT }) {
  if (w.plan === "trial") {
    const t = trialState(w.trial_days_left);
    return (
      <>
        <div className="title text-2xl text-ink">الفترة التجريبية</div>
        <p className={cn("mt-1 text-sm", t.tone === "bad" ? "text-bad" : t.tone === "warn" ? "text-warn" : "text-mute")}>
          {t.text}
          {w.trial_ends_at && ` · تنتهي ${date(w.trial_ends_at)}`}
        </p>
        <p className="mt-3 text-sm leading-relaxed text-ink-2">
          {(w.trial_days_left ?? 0) < 0
            ? "انتهت التجربة: البيانات محفوظة، لكن لا يمكن إضافة مبيعات جديدة حتى تشترك."
            : "كل الميزات متاحة أثناء التجربة. اشترك قبل انتهائها لتستمر بدون توقف."}
        </p>
      </>
    );
  }
  return (
    <>
      <div className="title text-2xl text-ink">باقة {planLabel(w.plan)}</div>
      <p className="mt-1 text-sm text-mute">
        <Money value={w.monthly_price_egp} /> شهريًا
        {w.paid_until && ` · مدفوعة حتى ${date(w.paid_until)}`}
      </p>
    </>
  );
}

function PayDialog({
  open,
  onClose,
  plan,
  cycle,
  workspace,
  me,
}: {
  open: boolean;
  onClose: () => void;
  plan: Plan;
  cycle: "monthly" | "annual";
  workspace: WorkspaceT;
  me: Owner;
}) {
  const [phone, setPhone] = useState(me.phone ?? "");
  const [email, setEmail] = useState(me.email ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const amount = cycle === "annual" ? plan.price_annual_egp : plan.price_monthly_egp;

  async function pay() {
    setBusy(true);
    setError(null);
    try {
      if (phone.trim() !== (me.phone ?? "") || email.trim() !== (me.email ?? "")) {
        await actions.updateMe({ phone: phone.trim(), email: email.trim() });
      }
      const r = await actions.checkout({ id: workspace.id, plan: plan.id, cycle });
      window.location.assign(r.checkout_url);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`باقة ${planLabel(plan.id)} · ${workspace.name}`}
      description="ستنتقل إلى صفحة الدفع الآمنة من Paymob. يتفعّل الاشتراك فور نجاح الدفع."
    >
      <div className="flex items-baseline justify-between rounded-lg bg-sand/60 px-4 py-3">
        <span className="text-sm text-ink-2">{cycle === "annual" ? "اشتراك سنوي" : "اشتراك شهري"}</span>
        <Money value={amount} className="text-xl font-bold text-ink" />
      </div>
      <div className="mt-4 grid gap-4">
        <Field label="رقم الموبايل" hint="لإيصال الدفع، ولمحافظ الموبايل.">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" dir="ltr" className="text-start" placeholder="01xxxxxxxxx" required />
        </Field>
        <Field label="البريد الإلكتروني" hint="يصلك عليه إيصال الدفع.">
          <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" dir="ltr" className="text-start" placeholder="name@example.com" />
        </Field>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      <ModalActions>
        <Button variant="primary" busy={busy} onClick={pay} disabled={phone.trim().length < 6}>
          <CreditCard /> ادفع {money(amount)}
        </Button>
        <Button variant="ghost" onClick={onClose}>
          إلغاء
        </Button>
      </ModalActions>
    </Modal>
  );
}

function Plans({ w, me }: { w: WorkspaceT; me: Owner }) {
  const q = usePlans();
  const [params] = useSearchParams();
  const [cycle, setCycle] = useState<"monthly" | "annual">(params.get("cycle") === "annual" ? "annual" : "monthly");
  const [paying, setPaying] = useState<Plan | null>(null);
  const wanted = params.get("plan");
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (wanted && q.data) ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [wanted, q.data]);

  if (!q.data) return null;
  const current = ORDER.indexOf(w.plan);

  return (
    <section ref={ref} id="plans" className="scroll-mt-24">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="title text-xl text-ink">{w.plan === "trial" ? "اختر باقتك" : "غيّر باقتك أو جدّدها"}</h2>
          <p className="mt-1 text-sm text-mute">الأسعار بالجنيه المصري. السنوي يوفّر شهرين تقريبًا.</p>
        </div>
        <div className="inline-flex rounded-lg border border-line bg-card p-1" role="radiogroup" aria-label="مدة الاشتراك">
          {(["monthly", "annual"] as const).map((c) => (
            <button
              key={c}
              role="radio"
              aria-checked={cycle === c}
              onClick={() => setCycle(c)}
              className={cn("h-8 rounded-md px-4 text-sm font-semibold transition-colors", cycle === c ? "bg-wine text-white" : "text-ink-2 hover:bg-sand")}
            >
              {c === "monthly" ? "شهري" : "سنوي"}
            </button>
          ))}
        </div>
      </div>

      {!q.data.online_payment && (
        <p className="mb-4 rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn">
          الدفع الإلكتروني غير متاح الآن. تواصل معنا لإتمام الاشتراك وسنفعّله لك يدويًا.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {q.data.plans.map((p) => {
          const rank = ORDER.indexOf(p.id);
          const isCurrent = p.id === w.plan;
          const highlight = wanted ? wanted === p.id : p.popular;
          const price = cycle === "annual" ? p.price_annual_egp : p.price_monthly_egp;
          const label = isCurrent ? "جدّد الاشتراك" : rank > current ? (w.plan === "trial" ? "اشترك" : "رقِّ إلى هذه الباقة") : "انتقل إلى هذه الباقة";
          return (
            <article
              key={p.id}
              className={cn("flex flex-col rounded-2xl border bg-card p-5 shadow-xs", highlight ? "border-wine ring-1 ring-wine" : "border-line")}
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-lg font-bold text-ink">{planLabel(p.id)}</h3>
                {isCurrent ? (
                  <span className="rounded-md bg-wine-soft px-2 py-0.5 text-xs font-semibold text-wine">باقتك الحالية</span>
                ) : (
                  p.popular && <span className="rounded-md bg-sand px-2 py-0.5 text-xs font-semibold text-ink-2">الأكثر اختيارًا</span>
                )}
              </div>
              <div className="mt-3 flex items-baseline gap-1">
                <Money value={price} className="text-3xl font-bold text-ink" />
                <span className="text-sm text-mute">/ {cycle === "annual" ? "سنة" : "شهر"}</span>
              </div>
              <ul className="mt-4 grid gap-2 text-sm text-ink-2">
                {p.features.slice(0, 5).map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="mt-0.5 size-4 shrink-0 text-ok" /> {f}
                  </li>
                ))}
              </ul>
              <Button
                variant={highlight ? "primary" : "secondary"}
                className="mt-5 w-full"
                disabled={!q.data.online_payment || w.status === "suspended"}
                onClick={() => setPaying(p)}
              >
                {label}
              </Button>
            </article>
          );
        })}
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-[13px] text-mute">
        <ShieldCheck className="size-4" /> الدفع ببطاقات فيزا وماستركارد وميزة والمحافظ عبر Paymob. لا نحتفظ ببيانات بطاقتك.
      </p>
      {paying && <PayDialog open onClose={() => setPaying(null)} plan={paying} cycle={cycle} workspace={w} me={me} />}
    </section>
  );
}

export default function Workspace() {
  const { id = "" } = useParams();
  const q = useWorkspace(id);
  const me = useMe();
  const { open, opening } = useOpenWorkspace();

  if (q.isPending || !me.data) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const { workspace: w, quotas, invoices } = q.data;

  return (
    <div className="grid grid-cols-1 gap-8">
      <div>
        <Link to="/" className="mb-2 inline-flex items-center gap-1 text-[13px] text-mute hover:text-ink">
          <ChevronRight className="size-4" /> مساحات العمل
        </Link>
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="title text-2xl leading-tight text-ink">{w.name}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-mute">
              <PlanBadge w={w} />
              <span>{sectorLabel(w.sector)}</span>
            </div>
          </div>
          <Button variant="primary" busy={opening === w.id} disabled={w.status === "suspended"} onClick={() => open(w)}>
            افتح النظام <ArrowUpLeft />
          </Button>
        </header>
        {w.status === "suspended" && (
          <p className="mt-4 rounded-lg bg-bad-soft px-4 py-3 text-sm text-bad">
            مساحة العمل هذه موقوفة من إدارة ميزان، ولا يستطيع أحد الدخول إليها. تواصل مع الدعم لإعادة تفعيلها.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel title="الاشتراك الحالي">
          <CurrentPlan w={w} />
        </Panel>
        <Panel title="الاستخدام">
          <div className="grid gap-4">
            <Meter label="المستخدمون" used={quotas.users.used} max={quotas.users.max} />
            <Meter label="الفروع" used={quotas.branches.used} max={quotas.branches.max} />
            <Meter label="فواتير البيع هذا الشهر" used={quotas.monthly_sales.used} max={quotas.monthly_sales.max} />
          </div>
        </Panel>
      </div>

      <Plans w={w} me={me.data} />

      <Panel title="فواتير مساحة العمل" flush>
        <InvoiceTable invoices={invoices as Invoice[]} />
      </Panel>
    </div>
  );
}
