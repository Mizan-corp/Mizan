import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowUpLeft, Check, ChevronRight, CreditCard, FlaskConical, ShieldCheck, Smartphone } from "lucide-react";
import {
  actions,
  type Invoice,
  type Owner,
  type PaymentMethod,
  type Plan,
  useAction,
  useMe,
  usePlans,
  useStorage,
  useWorkspace,
  type Workspace as WorkspaceT,
} from "@app/lib/data";
import { useOpenWorkspace } from "@app/lib/open";
import { ago, date, errorText, LICENCE_STATUS, MODE, money, paidState, planLabel, sectorLabel, trialState } from "@app/lib/format";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { appUrl, workspaceUrl } from "@/lib/urls";
import { Badge, Button, ErrorNote, Field, Input, LoadError, Meter, Modal, ModalActions, PageSkeleton, Panel, Money } from "@app/ui";
import { PlanBadge } from "@app/pages/Workspaces";
import { DownloadButton } from "@app/DownloadDialog";
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
  const p = paidState(w.paid_until);
  return (
    <>
      <div className="title text-2xl text-ink">باقة {planLabel(w.plan)}</div>
      <p className={cn("mt-1 text-sm", p?.tone === "bad" ? "text-bad" : p?.tone === "warn" ? "text-warn" : "text-mute")}>
        <Money value={w.monthly_price_egp} /> شهريًا
        {w.paid_until && ` · ${p?.ended ? "انتهت في" : "مدفوعة حتى"} ${date(w.paid_until)}`}
      </p>
      {p && (
        <p className="mt-3 text-sm leading-relaxed text-ink-2">
          {p.ended
            ? "انتهت فترة الاشتراك: مساحة العمل للقراءة فقط وبياناتك محفوظة. جدّد لتعود الإضافة والتعديل فورًا."
            : "جدّد قبل نهاية الفترة لتستمر بدون توقف؛ تبدأ الفترة الجديدة من نهاية الحالية."}
        </p>
      )}
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
  methods,
  testMode,
}: {
  open: boolean;
  onClose: () => void;
  plan: Plan;
  cycle: "monthly" | "annual";
  workspace: WorkspaceT;
  me: Owner;
  methods: PaymentMethod[];
  testMode: boolean;
}) {
  const [phone, setPhone] = useState(me.phone ?? "");
  const [email, setEmail] = useState(me.email ?? "");
  const choices = methods.filter((m): m is "card" | "wallet" => m === "card" || m === "wallet");
  const [method, setMethod] = useState<"card" | "wallet" | undefined>(choices[0]);
  const [wallet, setWallet] = useState(me.phone ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const amount = cycle === "annual" ? plan.price_annual_egp : plan.price_monthly_egp;
  const walletOk = /^(?:\+?20|0020)?0?1[0125]\d{8}$/.test(wallet.replace(/[\s-]/g, ""));
  const ready = phone.trim().length >= 6 && (method !== "wallet" || walletOk);

  async function pay() {
    setBusy(true);
    setError(null);
    try {
      if (phone.trim() !== (me.phone ?? "") || email.trim() !== (me.email ?? "")) {
        await actions.updateMe({ phone: phone.trim(), email: email.trim() });
      }
      const r = await actions.checkout({
        id: workspace.id,
        plan: plan.id,
        cycle,
        method,
        wallet_number: method === "wallet" ? wallet.trim() : undefined,
      });
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
      description={
        method === "wallet"
          ? "ستنتقل إلى صفحة Paymob لتأكيد الدفع من محفظتك. يتفعّل الاشتراك فور نجاح الدفع."
          : "ستنتقل إلى صفحة الدفع الآمنة من Paymob. يتفعّل الاشتراك فور نجاح الدفع."
      }
    >
      {testMode && (
        <div className="mb-3 flex items-start gap-2 rounded-lg bg-warn/12 px-3.5 py-2.5 text-[13px] text-ink-2">
          <FlaskConical className="mt-0.5 size-4 shrink-0 text-warn" />
          <span>وضع التجربة: الدفع عبر Paymob التجريبي، ولا يُخصم أي مال حقيقي.</span>
        </div>
      )}
      <div className="flex items-baseline justify-between rounded-lg bg-sand/60 px-4 py-3">
        <span className="text-sm text-ink-2">{cycle === "annual" ? "اشتراك سنوي" : "اشتراك شهري"}</span>
        <Money value={amount} className="text-xl font-bold text-ink" />
      </div>
      {choices.length > 0 && (
        <fieldset className="mt-4">
          <legend className="mb-2 text-sm font-semibold text-ink">طريقة الدفع</legend>
          <div className="grid grid-cols-2 gap-2" role="radiogroup">
            {(["card", "wallet"] as const).map((m) => {
              const available = choices.includes(m);
              const selected = method === m;
              const Icon = m === "card" ? CreditCard : Smartphone;
              return (
                <button
                  key={m}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  disabled={!available}
                  onClick={() => setMethod(m)}
                  className={cn(
                    "flex items-start gap-2.5 rounded-lg border p-3 text-start transition-colors focus-visible:outline-2 focus-visible:outline-wine disabled:cursor-not-allowed disabled:opacity-55",
                    selected ? "border-wine bg-wine-soft" : "border-line bg-card hover:border-ink-2/30",
                  )}
                >
                  <Icon className={cn("mt-0.5 size-5 shrink-0", selected ? "text-wine" : "text-mute")} />
                  <span>
                    <span className="block text-sm font-semibold text-ink">{m === "card" ? "بطاقة بنكية" : "محفظة إلكترونية"}</span>
                    <span className="block text-[12px] leading-snug text-mute">
                      {!available
                        ? "قريبًا"
                        : m === "card"
                          ? "فيزا، ماستركارد، ميزة"
                          : "فودافون كاش، أورنچ، اتصالات، وي"}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>
      )}
      <div className="mt-4 grid gap-4">
        {method === "wallet" && (
          <Field
            label="رقم المحفظة"
            hint={walletOk || !wallet ? "الرقم المسجل عليه المحفظة. ستؤكد الدفع برمز من محفظتك." : "11 رقمًا يبدأ بـ 010 أو 011 أو 012 أو 015."}
          >
            <Input
              value={wallet}
              onChange={(e) => setWallet(e.target.value)}
              inputMode="tel"
              dir="ltr"
              className="text-start"
              placeholder="01xxxxxxxxx"
              aria-invalid={!!wallet && !walletOk}
            />
          </Field>
        )}
        <Field label="رقم الموبايل" hint="لإيصال الدفع.">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" dir="ltr" className="text-start" placeholder="01xxxxxxxxx" required />
        </Field>
        <Field label="البريد الإلكتروني" hint="يصلك عليه إيصال الدفع.">
          <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" dir="ltr" className="text-start" placeholder="name@example.com" />
        </Field>
      </div>
      <p className="mt-4 text-[12px] leading-relaxed text-mute">
        بالدفع توافق على{" "}
        <a href={appUrl("website", "/terms")} target="_blank" rel="noopener noreferrer" className="font-semibold text-wine hover:underline">
          شروط الاستخدام
        </a>{" "}
        و
        <a href={appUrl("website", "/refund-policy")} target="_blank" rel="noopener noreferrer" className="font-semibold text-wine hover:underline">
          سياسة الاسترداد
        </a>
        . لا يتجدد الاشتراك تلقائيًا، ويمكن استرداد أول دفعة خلال 14 يومًا.
      </p>
      {error && <ErrorNote>{error}</ErrorNote>}
      <ModalActions>
        <Button variant="primary" busy={busy} onClick={pay} disabled={!ready}>
          {method === "wallet" ? <Smartphone /> : <CreditCard />} ادفع {money(amount)}
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
      {paying && (
        <PayDialog
          open
          onClose={() => setPaying(null)}
          plan={paying}
          cycle={cycle}
          workspace={w}
          me={me}
          methods={q.data.payment_methods ?? []}
          testMode={!!q.data.test_mode}
        />
      )}
    </section>
  );
}

function size(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} جيجابايت`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} ميجابايت`;
  return `${Math.max(1, Math.round(bytes / 1024))} كيلوبايت`;
}

/** Storage: used against the plan's limit, and what takes the space, by module (ADR-006 D3). */
function Storage({ id }: { id: string }) {
  const [refresh, setRefresh] = useState(false);
  const q = useStorage(id, refresh);
  const s = q.data;
  return (
    <Panel
      title="مساحة التخزين"
      aside={
        <button type="button" className="text-xs font-semibold text-wine hover:underline disabled:opacity-50"
          disabled={q.isFetching} onClick={() => setRefresh(true)}>
          {q.isFetching ? "جارٍ القياس…" : "قِس الآن"}
        </button>
      }
    >
      {q.isLoading ? (
        <div className="h-16 animate-pulse rounded-lg bg-sand/60" aria-busy="true" />
      ) : q.isError || !s ? (
        <p className="text-sm text-bad">تعذّر قياس المساحة الآن.</p>
      ) : (
        <div className="grid gap-4">
          <div>
            <div className="mb-1.5 flex items-baseline justify-between text-sm">
              <span className="text-ink-2">المستخدم</span>
              <span className="data text-ink">{size(s.used_bytes)} <span className="text-mute">/ {size(s.limit_bytes)}</span></span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-sand" role="meter" aria-valuenow={s.percent} aria-valuemax={100} aria-label="مساحة التخزين">
              <div className={cn("h-full rounded-full", s.state === "full" ? "bg-bad" : s.state === "warn" ? "bg-warn" : "bg-wine")}
                style={{ width: `${Math.max(2, Math.min(100, s.percent))}%` }} />
            </div>
            {s.state !== "ok" && (
              <p className={cn("mt-2 text-sm", s.state === "full" ? "text-bad" : "text-warn")}>
                {s.state === "full"
                  ? "المساحة ممتلئة: رفع الملفات متوقف، والبيع والعمل اليومي مستمران. احذف بيانات وحدات لا تحتاجها أو رقِّ الباقة."
                  : "اقتربت المساحة من حد الباقة."}
              </p>
            )}
          </div>
          <ul className="divide-y divide-line-soft text-sm">
            {s.by_module.slice(0, 8).map((m) => (
              <li key={m.module} className="flex items-center justify-between gap-3 py-2">
                <span className="text-ink-2">
                  {m.name}
                  {m.kept && <span className="ms-2 text-xs text-mute">(وحدة مُزالة، بياناتها محفوظة مؤقتًا)</span>}
                </span>
                <span className="data text-ink">{size(m.bytes)}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-mute">آخر قياس: {date(s.measured_at)}</p>
        </div>
      )}
    </Panel>
  );
}

/** Name, address and deletion (#74). The URL name is the workspace's address. */
function Settings({ w, staff }: { w: WorkspaceT; staff: number }) {
  const navigate = useNavigate();
  const [name, setName] = useState(w.name);
  const [slug, setSlug] = useState(w.slug ?? "");
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [typed, setTyped] = useState("");
  const save = useAction(actions.updateWorkspace);
  const remove = useAction(actions.deleteWorkspace);
  const { open, opening } = useOpenWorkspace();
  const slugChanged = !!w.slug && slug !== w.slug;
  const dirty = name.trim() !== w.name || slugChanged;
  const isTrial = w.plan === "trial";

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    save.mutateAsync({ id: w.id, name: name.trim() !== w.name ? name.trim() : undefined, slug: slugChanged ? slug : undefined })
      .then(() => toast.success("تم الحفظ"), (err) => setError(errorText(err)));
  }

  return (
    <Panel title="إعدادات مساحة العمل">
      <form onSubmit={submit} className="grid max-w-lg gap-4">
        <Field label="اسم مساحة العمل">
          <Input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={128} />
        </Field>
        {w.slug && (
          <Field
            label="الرابط"
            hint={slugChanged
              ? <span className="text-warn">الرابط القديم وأي إشارات مرجعية إليه ستتوقف. أخبر فريقك بالرابط الجديد.</span>
              : <span className="code" dir="ltr">{workspaceUrl(slug || "…").replace(/^https?:\/\//, "").replace(/\/$/, "")}</span>}
          >
            <Input value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                   dir="ltr" className="code text-start" minLength={3} maxLength={48} required />
          </Field>
        )}
        {error && <ErrorNote>{error}</ErrorNote>}
        <div>
          <Button type="submit" variant="primary" busy={save.isPending} disabled={!dirty}>حفظ</Button>
        </div>
      </form>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line-soft pt-5">
        <p className="text-sm text-ink-2">
          {staff} {staff === 1 ? "مستخدم" : "مستخدمين"} في مساحة العمل. تُدار الحسابات والصلاحيات من داخل النظام.
        </p>
        {w.deployment_mode === "cloud_saas" && (
          <Button size="sm" busy={opening === w.id} disabled={w.status === "suspended"} onClick={() => open(w, "/users")}>
            إدارة الموظفين
          </Button>
        )}
      </div>

      <div className="mt-6 border-t border-line-soft pt-5">
        <h3 className="text-sm font-semibold text-ink">حذف مساحة العمل</h3>
        {isTrial ? (
          <>
            <p className="mt-1 text-[13px] text-mute">يحذف كل بياناتها وملفاتها نهائيًا، ولا يمكن التراجع.</p>
            <Button size="sm" variant="danger" className="mt-3" onClick={() => { setTyped(""); setDeleting(true); }}>
              حذف مساحة العمل
            </Button>
          </>
        ) : (
          <p className="mt-1 text-[13px] text-mute">مساحات العمل المدفوعة تُغلق عن طريق الدعم، حتى لا يضيع ما دفعت مقابله.</p>
        )}
      </div>

      <Modal open={deleting} onClose={() => setDeleting(false)} title="حذف مساحة العمل نهائيًا"
             description={<>اكتب اسمها <b className="text-ink">{w.name}</b> للتأكيد.</>}>
        <Input value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="اسم مساحة العمل للتأكيد" autoFocus />
        {remove.isError && <ErrorNote>{errorText(remove.error)}</ErrorNote>}
        <ModalActions>
          <Button variant="danger" busy={remove.isPending} disabled={typed !== w.name}
                  onClick={() => remove.mutateAsync({ id: w.id, confirm: typed }).then(() => { toast.success("حُذفت مساحة العمل"); navigate("/"); })}>
            حذف نهائيًا
          </Button>
          <Button onClick={() => setDeleting(false)}>إلغاء</Button>
        </ModalActions>
      </Modal>
    </Panel>
  );
}

export default function Workspace() {
  const { id = "" } = useParams();
  const q = useWorkspace(id);
  const me = useMe();
  const { open, opening } = useOpenWorkspace();

  if (q.isPending || !me.data) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const { workspace: w, quotas, invoices, installations } = q.data;
  const onPrem = w.deployment_mode !== "cloud_saas";

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
          {onPrem ? (
            <DownloadButton workspace={w} />
          ) : (
            <Button variant="primary" busy={opening === w.id} disabled={w.status === "suspended"} onClick={() => open(w)}>
              افتح النظام <ArrowUpLeft />
            </Button>
          )}
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
        {onPrem ? (
          <Panel title="الترخيص والأجهزة" aside={MODE[w.deployment_mode].label}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={LICENCE_STATUS[w.licence?.status ?? "none"].tone}>{LICENCE_STATUS[w.licence?.status ?? "none"].label}</Badge>
              {w.licence?.valid_until && <span className="text-sm text-ink-2">حتى {date(w.licence.valid_until)}</span>}
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-mute">
              الدفع يمدّد الترخيص حتى نهاية الفترة المدفوعة. يتجدد على الجهاز تلقائيًا عند اتصاله بالإنترنت.
            </p>
            {installations.length ? (
              <ul className="mt-4 divide-y divide-line-soft border-t border-line-soft">
                {installations.map((i) => (
                  <li key={i.id} className="flex items-baseline justify-between gap-3 py-2.5 text-sm">
                    <span className="min-w-0">
                      <span className="code text-ink">{i.hostname ?? "جهاز"}</span>
                      <span className="text-xs text-mute"> · {i.os ?? "—"}{i.app_version && ` · v${i.app_version}`}</span>
                      {i.update_to && (
                        <span className="mt-0.5 block text-xs text-warn">
                          يتوفر الإصدار {i.update_to}: من هذا الجهاز شغّل <span className="code" dir="ltr">mizan-server update</span> كمسؤول. يأخذ نسخة احتياطية أولًا ويرجع تلقائيًا لو فشل.
                        </span>
                      )}
                    </span>
                    <span className="shrink-0 text-xs text-mute">آخر اتصال {ago(i.last_seen_at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 rounded-lg bg-sand/60 px-3 py-2.5 text-sm text-ink-2">لم يُثبَّت البرنامج على أي جهاز بعد.</p>
            )}
          </Panel>
        ) : (
        <Panel title="الاستخدام">
          <div className="grid gap-4">
            <Meter label="المستخدمون" used={quotas.users.used} max={quotas.users.max} />
            <Meter label="الفروع" used={quotas.branches.used} max={quotas.branches.max} />
            <Meter label="فواتير البيع هذا الشهر" used={quotas.monthly_sales.used} max={quotas.monthly_sales.max} />
          </div>
        </Panel>
        )}
      </div>

      {w.deployment_mode === "cloud_saas" && <Storage id={w.id} />}

      <Plans w={w} me={me.data} />

      <Panel title="فواتير مساحة العمل" flush>
        <InvoiceTable invoices={invoices as Invoice[]} />
      </Panel>

      <Settings key={`${w.name}|${w.slug}`} w={w} staff={quotas.users.used} />
    </div>
  );
}
