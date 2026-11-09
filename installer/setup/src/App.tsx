import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CloudOff,
  Copy,
  FileKey2,
  FolderOpen,
  KeyRound,
  Loader2,
  MonitorSmartphone,
  Network,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import QRCode from "qrcode";
import logo from "./logo-tile.svg";
import {
  type InstallOptions,
  type Licence,
  openMizan,
  openPath,
  pickLicenceFile,
  type Progress,
  readLicence,
  runInstall,
  type SetupInfo,
  setupInfo,
  type Summary,
} from "./api";

type Step = "welcome" | "licence" | "account" | "options" | "install" | "done";
const STEPS: { id: Step; label: string }[] = [
  { id: "welcome", label: "مرحبًا" },
  { id: "licence", label: "الترخيص" },
  { id: "account", label: "حساب المدير" },
  { id: "options", label: "الإعدادات" },
  { id: "install", label: "التثبيت" },
  { id: "done", label: "جاهز" },
];

const dateFmt = new Intl.DateTimeFormat("ar-EG-u-nu-latn", { day: "numeric", month: "long", year: "numeric" });
const MODE = {
  desktop: { label: "جهاز واحد", icon: MonitorSmartphone },
  lan: { label: "شبكة محلية", icon: Network },
} as const;

function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

// ─── Small pieces ──────────────────────────────────────────────────────────

function Button({
  variant = "primary",
  className,
  children,
  ...props
}: React.ComponentProps<"button"> & { variant?: "primary" | "secondary" | "ghost" }) {
  return (
    <button
      type="button"
      className={cx(
        "inline-flex h-11 items-center justify-center gap-2 rounded-xl px-5 text-[15px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45 [&_svg]:size-4",
        variant === "primary" && "bg-wine text-paper shadow-sm hover:bg-wine-hover",
        variant === "secondary" && "border border-line bg-card text-ink hover:bg-sand/60",
        variant === "ghost" && "text-ink-2 hover:bg-sand/70",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-[13px] text-mute">{hint}</span>}
    </label>
  );
}

const INPUT =
  "h-11 w-full rounded-xl border border-line bg-card px-3.5 text-[15px] text-ink outline-none placeholder:text-mute/60 focus:border-wine focus:ring-2 focus:ring-wine/15";

function Title({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <header className="mb-7">
      <h1 className="text-[26px] font-bold leading-snug tracking-tight text-ink">{children}</h1>
      {sub && <p className="mt-2 text-[15px] leading-relaxed text-mute">{sub}</p>}
    </header>
  );
}

function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className="mt-4 flex items-start gap-2.5 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span className="leading-relaxed">{children}</span>
    </div>
  );
}

// ─── Side panel ────────────────────────────────────────────────────────────

function Side({ step, info, licence }: { step: Step; info: SetupInfo | null; licence: Licence | null }) {
  const at = STEPS.findIndex((s) => s.id === step);
  return (
    <aside className="arcs flex w-[250px] shrink-0 flex-col bg-merlot px-6 py-7 text-paper">
      <div className="flex items-center gap-3">
        <img src={logo} alt="" className="size-11 rounded-xl" />
        <div className="leading-tight">
          <div className="text-lg font-bold">ميزان</div>
          <div className="text-xs text-paper/60">تثبيت {licence ? MODE[licence.mode].label : "ميزان"}</div>
        </div>
      </div>

      <ol className="mt-10 grid gap-1">
        {STEPS.map((s, i) => {
          const state = i < at ? "done" : i === at ? "current" : "todo";
          return (
            <li key={s.id} className={cx("flex items-center gap-3 rounded-lg px-2 py-2 text-sm", state === "current" && "bg-white/8")}>
              <span
                className={cx(
                  "grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-bold",
                  state === "done" && "bg-rose/90 text-white",
                  state === "current" && "bg-paper text-merlot",
                  state === "todo" && "border border-white/20 text-paper/50",
                )}
              >
                {state === "done" ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span className={cx(state === "todo" ? "text-paper/50" : "text-paper", state === "current" && "font-semibold")}>{s.label}</span>
            </li>
          );
        })}
      </ol>

      <div className="mt-auto text-[11px] leading-relaxed text-paper/45">
        {licence && <div className="mb-1 truncate text-paper/70">{licence.workspace.name}</div>}
        <span className="code">Mizan Setup {info?.version ?? ""}</span>
      </div>
    </aside>
  );
}

// ─── Screens ───────────────────────────────────────────────────────────────

function Welcome({ slide, licence }: { slide: number; licence: Licence | null }) {
  const lan = licence?.mode === "lan";
  const slides = [
    {
      icon: Sparkles,
      title: licence ? `أهلا بك، سنثبّت ميزان لـ ${licence.workspace.name}` : "أهلا بك في ميزان",
      body: "معالج قصير يجهّز كل شيء: قاعدة البيانات، النظام، وحساب المدير. يستغرق دقيقتين تقريبًا.",
    },
    lan
      ? { icon: Network, title: "هذا الجهاز سيكون خادم منشأتك", body: "أجهزة الكاشير والمكاتب تتصل به عبر شبكتك الداخلية، حتى لو انقطع الإنترنت. اتركه مُشغّلًا أثناء العمل." }
      : { icon: CloudOff, title: "يعمل على هذا الجهاز، بدون إنترنت", body: "بياناتك محفوظة على جهازك، مع نسخة احتياطية تلقائية كل يوم. لا يتصل به أي جهاز آخر." },
    {
      icon: ShieldCheck,
      title: "ترخيص يتجدد وحده",
      body: "عندما تدفع الاشتراك من لوحة المالك، يتجدد الترخيص تلقائيًا عند اتصال الجهاز بالإنترنت. لا يتصل أبدًا؟ أدخل المفتاح الجديد يدويًا من داخل البرنامج.",
    },
  ];
  const s = slides[slide];
  const Icon = s.icon;
  return (
    <div key={slide} className="slide-in flex h-full flex-col justify-center">
      <div className="mb-8 grid size-20 place-items-center rounded-3xl bg-wine/8 ring-1 ring-wine/15">
        <Icon className="size-9 text-wine" strokeWidth={1.6} />
      </div>
      <h1 className="max-w-lg text-[30px] font-bold leading-[1.45] tracking-tight text-ink">{s.title}</h1>
      <p className="mt-4 max-w-lg text-[16px] leading-8 text-ink-2">{s.body}</p>
      <div className="mt-10 flex gap-1.5" aria-label={`الشريحة ${slide + 1} من ${slides.length}`}>
        {slides.map((_, i) => (
          <span key={i} className={cx("h-1.5 rounded-full transition-all", i === slide ? "w-7 bg-wine" : "w-1.5 bg-line")} />
        ))}
      </div>
    </div>
  );
}

const SOURCE: Record<string, string> = {
  stamp: "مدمج في برنامج التثبيت",
  file: "وجدناه بجانب برنامج التثبيت",
  downloads: "وجدناه في مجلد التنزيلات",
  clipboard: "وجدناه فيما نسخته",
  typed: "أدخلته بنفسك",
};

function LicenceStep({
  licence,
  source,
  onLicence,
}: {
  licence: Licence | null;
  source: string | null;
  onLicence: (key: string, l: Licence, source: string) => void;
}) {
  const [editing, setEditing] = useState(!licence);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function use(input: { text?: string; path?: string }, src: string) {
    setError(null);
    try {
      const r = await readLicence(input);
      onLicence(r.key, r.licence, src);
      setEditing(false);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  const expired = licence ? new Date(licence.valid_until).getTime() < Date.now() : false;
  return (
    <div className="slide-in">
      <Title sub="المفتاح يحدد مساحة العمل التي ستُنشأ على هذا الجهاز ومدة الاشتراك.">الترخيص</Title>
      {licence && !editing ? (
        <div className="rounded-2xl border border-line bg-card p-5 shadow-xs">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xl font-bold text-ink">{licence.workspace.name}</div>
              <div className="mt-1 text-sm text-mute">{licence.owner ? `المالك: ${licence.owner.full_name}` : ""}</div>
            </div>
            <span className="flex items-center gap-1.5 rounded-lg bg-wine/8 px-2.5 py-1 text-sm font-semibold text-wine">
              {(() => {
                const I = MODE[licence.mode].icon;
                return <I className="size-4" />;
              })()}
              {MODE[licence.mode].label}
            </span>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-line pt-4 text-sm">
            <div>
              <dt className="text-mute">ساري حتى</dt>
              <dd className={cx("mt-0.5 font-semibold", expired ? "text-bad" : "text-ink")}>{dateFmt.format(new Date(licence.valid_until))}</dd>
            </div>
            <div>
              <dt className="text-mute">المصدر</dt>
              <dd className="mt-0.5 font-semibold text-ink">{SOURCE[source ?? "typed"]}</dd>
            </div>
          </dl>
          {expired && <ErrorBox>انتهى هذا الترخيص. يمكنك التثبيت، لكن البرنامج سيعمل للعرض فقط حتى تجدّد الاشتراك.</ErrorBox>}
          <button onClick={() => setEditing(true)} className="mt-4 text-sm font-semibold text-wine hover:underline">
            استخدم مفتاحًا آخر
          </button>
        </div>
      ) : (
        <div>
          <Field label="مفتاح الترخيص" hint="من لوحة المالك: مساحة العمل ← «تنزيل» ← انسخ المفتاح.">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              dir="ltr"
              placeholder="MZN1.…"
              className={cx(INPUT, "code h-auto resize-none py-3 text-xs leading-relaxed")}
            />
          </Field>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => use({ text }, "typed")} disabled={text.trim().length < 20}>
              <KeyRound /> استخدم المفتاح
            </Button>
            <Button
              variant="secondary"
              onClick={async () => {
                const path = await pickLicenceFile();
                if (path) await use({ path }, "file");
              }}
            >
              <FileKey2 /> اختر ملف ترخيص (.mzn)
            </Button>
            {licence && (
              <Button variant="ghost" onClick={() => setEditing(false)}>
                إلغاء
              </Button>
            )}
          </div>
          {error && <ErrorBox>{error}</ErrorBox>}
        </div>
      )}
    </div>
  );
}

function AccountStep({
  username,
  setUsername,
  password,
  setPassword,
  confirm,
  setConfirm,
  demo,
  setDemo,
}: {
  username: string;
  setUsername: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  confirm: string;
  setConfirm: (v: string) => void;
  demo: boolean;
  setDemo: (v: boolean) => void;
}) {
  const mismatch = confirm.length > 0 && confirm !== password;
  return (
    <div className="slide-in">
      <Title sub="بهذا الحساب تدخل إلى ميزان على هذا الجهاز، وتضيف الموظفين من داخل البرنامج.">حساب المدير</Title>
      <div className="grid max-w-md gap-4">
        <Field label="اسم المستخدم">
          <input className={cx(INPUT, "code text-start")} value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </Field>
        <Field label="كلمة المرور" hint="8 أحرف على الأقل. احفظها في مكان آمن.">
          <input type="password" className={cx(INPUT, "code text-start")} value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Field label="تأكيد كلمة المرور">
          <input type="password" className={cx(INPUT, "code text-start", mismatch && "border-bad")} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </Field>
        {mismatch && <p className="-mt-2 text-[13px] text-bad">كلمتا المرور غير متطابقتين.</p>}
        <label className="mt-1 flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-card p-3.5">
          <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} className="mt-1 size-4 accent-wine" />
          <span>
            <span className="block text-sm font-semibold text-ink">املأه ببيانات تجريبية</span>
            <span className="block text-[13px] text-mute">أصناف وعملاء ومبيعات لنشاطك، لتجربة النظام. يمكنك حذفها لاحقًا.</span>
          </span>
        </label>
      </div>
    </div>
  );
}

function OptionsStep({
  licence,
  dir,
  setDir,
  port,
  setPort,
}: {
  licence: Licence;
  dir: string;
  setDir: (v: string) => void;
  port: string;
  setPort: (v: string) => void;
}) {
  const lan = licence.mode === "lan";
  return (
    <div className="slide-in">
      <Title sub="الإعدادات المقترحة مناسبة لمعظم المنشآت.">جاهز للتثبيت</Title>
      <div className="grid max-w-lg gap-4">
        <Field label="مجلد البرنامج">
          <input className={cx(INPUT, "code text-start text-sm")} value={dir} onChange={(e) => setDir(e.target.value)} />
        </Field>
        {lan && (
          <Field label="المنفذ على الشبكة" hint="443 هو المنفذ المعتاد للمواقع الآمنة، فتفتح الأجهزة العنوان بدون رقم منفذ.">
            <input className={cx(INPUT, "code w-32 text-start")} value={port} inputMode="numeric" onChange={(e) => setPort(e.target.value.replace(/\D/g, ""))} />
          </Field>
        )}
      </div>
      <ul className="mt-7 grid max-w-lg gap-2.5 text-[14px] text-ink-2">
        {[
          "قاعدة بيانات خاصة بميزان على هذا الجهاز (PostgreSQL)",
          lan ? "خادم آمن (HTTPS) على شبكتك الداخلية، بعنوان mizan.local" : "يعمل على هذا الجهاز فقط، ولا يظهر على الشبكة",
          "خدمة تعمل في الخلفية وتبدأ مع تشغيل الجهاز",
          "نسخة احتياطية تلقائية كل يوم",
          lan ? "" : "اختصار «ميزان» على سطح المكتب",
        ]
          .filter(Boolean)
          .map((t) => (
            <li key={t} className="flex items-start gap-2.5">
              <Check className="mt-0.5 size-4 shrink-0 text-ok" />
              {t}
            </li>
          ))}
      </ul>
    </div>
  );
}

const STAGES: { id: string; label: string; lan?: boolean; desktop?: boolean }[] = [
  { id: "extract", label: "نسخ ملفات البرنامج" },
  { id: "check", label: "التحقق من الترخيص والجهاز" },
  { id: "prepare", label: "تجهيز المجلدات والإعدادات" },
  { id: "database", label: "إعداد قاعدة البيانات" },
  { id: "workspace", label: "إنشاء مساحة العمل" },
  { id: "network", label: "شهادة الأمان للشبكة", lan: true },
  { id: "service", label: "تسجيل خدمة ميزان" },
  { id: "start", label: "تشغيل ميزان" },
  { id: "shortcuts", label: "اختصار سطح المكتب", desktop: true },
];

function InstallStep({
  mode,
  states,
  extract,
  error,
  onRetry,
  log,
}: {
  mode: "desktop" | "lan";
  states: Record<string, string>;
  extract: number;
  error: string | null;
  onRetry: () => void;
  log: string[];
}) {
  const stages = STAGES.filter((s) => (s.lan ? mode === "lan" : s.desktop ? mode === "desktop" : true));
  const finished = stages.filter((s) => ["done", "skipped"].includes(states[s.id])).length;
  const pct = Math.round(((finished + (states.extract === "progress" ? extract : 0)) / stages.length) * 100);
  const [showLog, setShowLog] = useState(false);
  return (
    <div className="slide-in">
      <Title sub={error ? undefined : "لا تغلق هذه النافذة. يستغرق دقيقة أو اثنتين."}>{error ? "تعذّر إكمال التثبيت" : "جاري التثبيت…"}</Title>
      <div className="mb-6 h-2 max-w-lg overflow-hidden rounded-full bg-sand">
        <div className={cx("h-full rounded-full transition-all duration-500", error ? "bg-bad" : "bg-wine")} style={{ width: `${Math.max(pct, 3)}%` }} />
      </div>
      <ol className="grid max-w-lg gap-2">
        {stages.map((s) => {
          const st = states[s.id];
          return (
            <li key={s.id} className={cx("flex items-center gap-3 text-[15px]", !st && "text-mute/70")}>
              <span className="grid size-6 place-items-center">
                {st === "done" ? (
                  <Check className="size-4 text-ok" />
                ) : st === "skipped" ? (
                  <span className="size-1.5 rounded-full bg-line" />
                ) : st === "error" ? (
                  <AlertTriangle className="size-4 text-bad" />
                ) : st ? (
                  <Loader2 className="size-4 animate-spin text-wine" />
                ) : (
                  <span className="size-1.5 rounded-full bg-line" />
                )}
              </span>
              <span className={cx(st === "running" || st === "progress" ? "font-semibold text-ink" : st ? "text-ink-2" : "")}>
                {s.label}
                {s.id === "extract" && st === "progress" && <span className="code mr-2 text-xs text-mute">{Math.round(extract * 100)}%</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {error && (
        <>
          <ErrorBox>{error}</ErrorBox>
          <div className="mt-4 flex gap-2">
            <Button onClick={onRetry}>
              <RefreshCcw /> حاول مرة أخرى
            </Button>
            <Button variant="secondary" onClick={() => navigator.clipboard.writeText(log.join("\n"))}>
              <Copy /> انسخ التفاصيل للدعم
            </Button>
            <Button variant="ghost" onClick={() => setShowLog(!showLog)}>
              التفاصيل
            </Button>
          </div>
          {showLog && <pre className="code mt-3 max-h-40 overflow-auto rounded-xl bg-ink p-3 text-[11px] leading-relaxed text-paper/80">{log.join("\n")}</pre>}
        </>
      )}
    </div>
  );
}

function DoneStep({ summary }: { summary: Summary }) {
  const lan = summary.mode === "lan";
  const [qr, setQr] = useState<string | null>(null);
  const main = lan ? summary.addresses[0] ?? summary.url : summary.url;
  useEffect(() => {
    if (lan && main) QRCode.toDataURL(main, { margin: 1, width: 220, color: { dark: "#35151D", light: "#FFFFFF" } }).then(setQr);
  }, [lan, main]);

  return (
    <div className="slide-in">
      <div className="mb-5 grid size-14 place-items-center rounded-2xl bg-ok/12">
        <Check className="size-7 text-ok" strokeWidth={2.4} />
      </div>
      <Title sub={`ادخل باسم المستخدم ${summary.admin} وكلمة المرور التي اخترتها.`}>
        {lan ? `خادم ميزان جاهز لـ ${summary.workspace}` : `ميزان جاهز على هذا الجهاز`}
      </Title>
      {lan ? (
        <div className="flex gap-6">
          <div className="min-w-0 flex-1">
            <h2 className="mb-2 text-sm font-bold text-ink">على أجهزة الكاشير والمكاتب</h2>
            <ol className="grid gap-2 text-[14px] leading-relaxed text-ink-2">
              <li>1. افتح هذا العنوان في المتصفح (أو امسح الرمز بالجوال):</li>
              {summary.addresses.map((a) => (
                <li key={a} className="flex items-center gap-2">
                  <span className="code rounded-lg bg-card px-2.5 py-1 text-[13px] text-ink ring-1 ring-line">{a}</span>
                  <button onClick={() => navigator.clipboard.writeText(a)} className="rounded p-1 text-mute hover:text-ink" aria-label="نسخ">
                    <Copy className="size-3.5" />
                  </button>
                </li>
              ))}
              <li>2. مرة واحدة لكل جهاز: ثبّت شهادة الأمان من رابط «شهادة الأمان» في صفحة الدخول، ليعمل الكاشير بدون إنترنت.</li>
              <li>3. من قائمة المتصفح اختر «تثبيت التطبيق» ليظهر ميزان كبرنامج.</li>
            </ol>
          </div>
          {qr && <img src={qr} alt={main} className="size-40 shrink-0 rounded-xl ring-1 ring-line" />}
        </div>
      ) : (
        <p className="max-w-lg text-[15px] leading-8 text-ink-2">
          أضفنا اختصار «ميزان» على سطح المكتب. البرنامج يعمل في الخلفية ويبدأ مع تشغيل الجهاز، ويأخذ نسخة احتياطية كل يوم.
        </p>
      )}
      <p className="mt-6 text-[13px] text-mute">
        البيانات والنسخ الاحتياطية في: <span className="code">{summary.data_dir}</span>
      </p>
    </div>
  );
}

// ─── The wizard ────────────────────────────────────────────────────────────

export default function App() {
  const [info, setInfo] = useState<SetupInfo | null>(null);
  const [step, setStep] = useState<Step>("welcome");
  const [slide, setSlide] = useState(0);
  const [key, setKey] = useState<string | null>(null);
  const [licence, setLicence] = useState<Licence | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [demo, setDemo] = useState(false);
  const [dir, setDir] = useState("");
  const [port, setPort] = useState("443");
  const [states, setStates] = useState<Record<string, string>>({});
  const [extract, setExtract] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    setupInfo().then((i) => {
      setInfo(i);
      setDir(i.install_dir);
      if (i.found && i.licence) {
        setKey(i.found.key);
        setLicence(i.licence);
        setSource(i.found.source);
        setUsername(i.licence.owner?.login ?? "admin");
      }
      if (!i.is_admin && i.platform === "windows") setPort("443");
    });
  }, []);

  const canNext = useMemo(() => {
    if (step === "licence") return !!licence && !!key;
    if (step === "account") return username.trim().length >= 3 && password.length >= 8 && password === confirm;
    if (step === "options") return dir.trim().length > 2 && (licence?.mode !== "lan" || (Number(port) > 0 && Number(port) < 65536));
    return true;
  }, [step, licence, key, username, password, confirm, dir, port]);

  async function install() {
    if (!licence || !key) return;
    setStep("install");
    setStates({});
    setError(null);
    setLog([]);
    const options: InstallOptions = {
      licence: key,
      admin_password: password,
      admin_username: username.trim(),
      install_dir: dir.trim(),
      port: licence.mode === "lan" ? Number(port) : undefined,
      demo,
    };
    try {
      const s = await runInstall(options, (p: Progress) => {
        setLog((l) => [...l, JSON.stringify(p)]);
        if (p.step === "extract" && p.status === "progress" && p.total) setExtract((p.done ?? 0) / p.total);
        setStates((st) => ({ ...st, [p.step]: p.status }));
        if (p.status === "error") setError(p.message ?? "حدث خطأ");
      });
      setSummary(s);
      setStep("done");
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  const back = () => {
    if (step === "welcome") setSlide((s) => Math.max(0, s - 1));
    else if (step === "licence") {
      setStep("welcome");
      setSlide(2);
    } else if (step === "account") setStep("licence");
    else if (step === "options") setStep("account");
  };
  const next = () => {
    if (step === "welcome") {
      if (slide < 2) setSlide(slide + 1);
      else setStep("licence");
    } else if (step === "licence") setStep("account");
    else if (step === "account") setStep("options");
    else if (step === "options") void install();
  };

  if (!info) {
    return (
      <div className="grid h-full place-items-center">
        <Loader2 className="size-6 animate-spin text-wine" />
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <Side step={step} info={info} licence={licence} />
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-11 pb-6 pt-10">
          {!info.has_payload && (
            <div className="mb-5 rounded-xl bg-warn/12 px-4 py-2.5 text-[13px] text-ink-2">نسخة تطوير بدون ملفات البرنامج: التثبيت سيفشل.</div>
          )}
          {step === "welcome" && <Welcome slide={slide} licence={licence} />}
          {step === "licence" && (
            <LicenceStep
              licence={licence}
              source={source}
              onLicence={(k, l, s) => {
                setKey(k);
                setLicence(l);
                setSource(s);
                if (!username) setUsername(l.owner?.login ?? "admin");
              }}
            />
          )}
          {step === "account" && (
            <AccountStep
              {...{ username, setUsername, password, setPassword, confirm, setConfirm, demo, setDemo }}
            />
          )}
          {step === "options" && licence && <OptionsStep licence={licence} dir={dir} setDir={setDir} port={port} setPort={setPort} />}
          {step === "install" && licence && (
            <InstallStep mode={licence.mode} states={states} extract={extract} error={error} onRetry={() => setStep("options")} log={log} />
          )}
          {step === "done" && summary && <DoneStep summary={summary} />}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-line bg-paper/80 px-11 py-4">
          {step === "done" && summary ? (
            <>
              <div className="flex gap-2">
                <Button onClick={() => openMizan(summary.mode === "lan" ? summary.addresses[0] ?? summary.url : summary.url, summary.mode === "desktop")}>
                  افتح ميزان <ArrowLeft />
                </Button>
                {summary.ca_certificate && (
                  <Button variant="secondary" onClick={() => openPath(summary.ca_certificate!.replace(/[\\/][^\\/]*$/, ""))}>
                    <FolderOpen /> مجلد شهادة الأمان
                  </Button>
                )}
              </div>
              <Button variant="ghost" onClick={() => window.close()}>
                إغلاق
              </Button>
            </>
          ) : step === "install" ? (
            <span className="text-[13px] text-mute">{error ? "" : "جاري التثبيت…"}</span>
          ) : (
            <>
              <Button onClick={next} disabled={!canNext}>
                {step === "options" ? (
                  <>
                    <ShieldCheck /> ثبّت الآن
                  </>
                ) : (
                  <>
                    التالي <ArrowLeft />
                  </>
                )}
              </Button>
              {(step !== "welcome" || slide > 0) && (
                <Button variant="ghost" onClick={back}>
                  <ArrowRight /> السابق
                </Button>
              )}
            </>
          )}
        </footer>
      </main>
    </div>
  );
}
