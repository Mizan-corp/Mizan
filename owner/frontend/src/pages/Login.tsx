/**
 * Owners' sign-in (ADR-008; it was the ERP's /login in ADR-004). The system API signs owners in
 * (`/account/login`); the owner session then passes through the website, which keeps its own
 * copy, on its way back here. Platform staff are sent to the admin panel and employees to their
 * workspace's own sign-in page.
 */
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { MizanLogo } from "@/components/MizanLogo";
import { openWithSession } from "@/lib/handoff";
import { appUrl, safeInternalPath, workspaceUrl } from "@/lib/urls";
import { Button, ErrorNote, Field, Input } from "@app/ui";

const SYSTEM_API = ((import.meta.env.VITE_SYSTEM_API_URL as string | undefined) ?? "/system-api").replace(/\/+$/, "");

interface LoginResult { access_token?: string; employee_workspace?: string; admin_panel?: boolean }

/** Only paths inside the owner panel may be returned to. */
const safeNext = (raw: string | null) => safeInternalPath(raw);

async function signIn(login: string, password: string): Promise<LoginResult> {
  let res: Response;
  try {
    res = await fetch(`${SYSTEM_API}/account/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ login, password }),
    });
  } catch {
    throw new Error("تعذر الاتصال بالخادم — تحقق من اتصال الإنترنت");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 429) throw new Error("محاولات كثيرة. انتظر دقيقة ثم حاول مرة أخرى.");
    throw new Error(typeof body?.detail === "string" ? body.detail : "اسم المستخدم أو كلمة المرور غير صحيحة");
  }
  return body;
}

/** POST to the system API's public owner routes; Arabic errors. */
async function post<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${SYSTEM_API}${path}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new Error("تعذر الاتصال بالخادم — تحقق من اتصال الإنترنت");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 429) throw new Error("محاولات كثيرة. انتظر قليلًا ثم حاول مرة أخرى.");
    throw new Error(typeof data?.detail === "string" ? data.detail : "تحقق من البيانات وحاول مرة أخرى");
  }
  return data as T;
}

/** Forgot password (#71): a code to the account's verified email, then a new password. */
function Forgot({ initial, onBack, onDone }: { initial: string; onBack: () => void; onDone: (token: string) => void }) {
  const [step, setStep] = useState<"ask" | "reset">("ask");
  const [login, setLogin] = useState(initial);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);

  async function ask(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ detail: string }>("/account/password/forgot", { login: login.trim() });
      setSent(r.detail);
      setStep("reset");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reset(e: FormEvent) {
    e.preventDefault();
    if (password !== again) {
      setError("كلمتا المرور غير متطابقتين");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ access_token: string }>("/account/password/reset", { login: login.trim(), code: code.trim(), new_password: password });
      onDone(r.access_token);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return step === "ask" ? (
    <form onSubmit={ask} className="mt-6 grid gap-4">
      <p className="text-sm text-ink-2">اكتب اسم المستخدم أو بريدك المؤكَّد، ونرسل إلى بريدك رمزًا لاختيار كلمة مرور جديدة.</p>
      <Field label="اسم المستخدم أو البريد الإلكتروني">
        <Input value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" dir="ltr" className="text-start" autoFocus required />
      </Field>
      {error && <ErrorNote>{error}</ErrorNote>}
      <Button type="submit" variant="primary" size="lg" busy={busy} disabled={login.trim().length < 2}>أرسل الرمز</Button>
      <button type="button" onClick={onBack} className="text-sm text-mute hover:text-ink">العودة إلى الدخول</button>
    </form>
  ) : (
    <form onSubmit={reset} className="mt-6 grid gap-4">
      <p className="rounded-lg bg-info-soft p-3 text-sm text-info" role="status">{sent}</p>
      <Field label="الرمز المرسل إلى بريدك">
        <Input value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))} inputMode="numeric"
               autoComplete="one-time-code" dir="ltr" className="code text-center text-lg tracking-[0.4em]" placeholder="••••••" autoFocus required />
      </Field>
      <Field label="كلمة المرور الجديدة">
        <Input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="new-password" dir="ltr"
               className="text-start" minLength={8} required />
      </Field>
      <Field label="أعد كتابتها">
        <Input value={again} onChange={(e) => setAgain(e.target.value)} type="password" autoComplete="new-password" dir="ltr"
               className="text-start" minLength={8} required />
      </Field>
      <p className="-mt-2 text-[12px] text-mute">8 أحرف على الأقل. تتغيّر أيضًا لدخولك إلى مساحات عملك، وتنتهي جلساتك الأخرى.</p>
      {error && <ErrorNote>{error}</ErrorNote>}
      <Button type="submit" variant="primary" size="lg" busy={busy} disabled={code.length !== 6 || password.length < 8}>غيّر كلمة المرور وادخل</Button>
      <div className="flex justify-between text-sm">
        <button type="button" onClick={() => ask()} disabled={busy} className="text-wine hover:underline disabled:opacity-50">أرسل رمزًا جديدًا</button>
        <button type="button" onClick={onBack} className="text-mute hover:text-ink">العودة إلى الدخول</button>
      </div>
    </form>
  );
}

export default function Login() {
  const [params] = useSearchParams();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ slug: string } | null>(null);
  const [forgot, setForgot] = useState(false);
  const enter = (token: string) =>
    // Through the website, so it knows the owner is signed in, then back here.
    openWithSession("website", `/session?next=${encodeURIComponent(safeNext(params.get("next")))}`, token);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await signIn(login.trim(), password);
      if (r.admin_panel) {
        window.location.assign(appUrl("admin", "/"));
        return;
      }
      if (r.employee_workspace) {
        setNotice({ slug: r.employee_workspace });
        setBusy(false);
        return;
      }
      enter(r.access_token!);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-paper px-4 py-10" dir="rtl">
      <div className="w-full max-w-sm">
        <a href={appUrl("website", "/")} className="mb-8 flex justify-center" aria-label="ميزان">
          <MizanLogo size="md" />
        </a>
        <div className="rounded-2xl border border-line bg-card p-6 shadow-sm">
          <h1 className="text-xl font-bold text-ink">{forgot ? "استعادة كلمة المرور" : "دخول أصحاب الأعمال"}</h1>
          {!forgot && <p className="mt-1 text-sm text-mute">مساحات عملك واشتراكاتك وفواتيرك في مكان واحد.</p>}

          {forgot ? (
            <Forgot initial={login} onBack={() => setForgot(false)} onDone={enter} />
          ) : notice ? (
            <div className="mt-6 space-y-4">
              <p className="rounded-lg bg-info-soft p-3 text-sm text-info">
                هذا حساب موظف. يدخل الموظفون من صفحة الدخول الخاصة بمساحة عملهم؛ احفظ رابطها.
              </p>
              <a href={workspaceUrl(notice.slug, "/login")} className="block">
                <Button variant="primary" className="w-full">الذهاب إلى صفحة دخول مساحة العمل</Button>
              </a>
              <p className="code text-center text-[12px] text-mute" dir="ltr">{workspaceUrl(notice.slug, "/login").replace(/^https?:\/\//, "")}</p>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-6 grid gap-4">
              <Field label="اسم المستخدم">
                <Input value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" dir="ltr" className="text-start" autoFocus required />
              </Field>
              <div className="relative">
                <Field label="كلمة المرور">
                  <Input value={password} onChange={(e) => setPassword(e.target.value)} type={show ? "text" : "password"}
                         autoComplete="current-password" dir="ltr" className="pe-10 text-start" required />
                </Field>
                <button type="button" onClick={() => setShow(!show)} aria-label={show ? "إخفاء كلمة المرور" : "إظهار كلمة المرور"}
                        className="absolute bottom-0 end-0 grid h-11 w-11 place-items-center text-mute hover:text-ink">
                  {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {error && <ErrorNote>{error}</ErrorNote>}
              <Button type="submit" variant="primary" size="lg" busy={busy} disabled={!login.trim() || !password}>دخول</Button>
              <button type="button" onClick={() => { setForgot(true); setError(null); }} className="text-sm text-wine hover:underline">
                نسيت كلمة المرور؟
              </button>
            </form>
          )}
        </div>
        <p className="mt-6 text-center text-sm text-mute">
          ليس لديك حساب؟{" "}
          <a href={appUrl("website", "/signup")} className="font-semibold text-wine hover:underline">ابدأ تجربتك المجانية</a>
        </p>
      </div>
    </main>
  );
}
