/** Developer sign-in and sign-up (a developer account, separate from owner accounts). */
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { Button, Input, Spinner } from "@/components/ui";
import { safeInternalPath } from "@/lib/urls";
import { DevHeader } from "./DevHeader";
import { Field } from "./kit";
import { devPath } from "./paths";
import { portal, PortalError, saveDeveloperSession, useDeveloperToken } from "./session";

export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = useDeveloperToken();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const next = safeInternalPath(params.get("next"), devPath("/portal"));
  if (token) return <Navigate to={next} replace />;

  const signup = mode === "signup";
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = signup ? { email, full_name: fullName, password } : { email, password };
      const r = await portal<{ access_token: string }>("POST", signup ? "/signup" : "/login", body);
      saveDeveloperSession(r.access_token);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof PortalError ? err.message : "حدث خطأ غير متوقع");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div dir="rtl" className="min-h-screen bg-[#FAF6F0] font-body text-[#262321]">
      <DevHeader />
      <main className="mx-auto flex max-w-md flex-col px-4 py-14">
        <div className="rounded-2xl border border-[#E7D6C1] bg-card p-6 shadow-xs sm:p-8">
          <h1 className="font-display text-2xl">{signup ? "حساب مطور جديد" : "دخول المطورين"}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {signup ? "حساب للبوابة، منفصل عن حساب مالك المنشأة." : "بوابة مطوري ميزان: الفرق ومفاتيح التوقيع ورموز سطر الأوامر."}
          </p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            {signup && (
              <Field label="الاسم" htmlFor="dev-name">
                <Input id="dev-name" value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" minLength={2} maxLength={128} required />
              </Field>
            )}
            <Field label="البريد الإلكتروني" htmlFor="dev-email">
              <Input id="dev-email" type="email" dir="ltr" className="text-start" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
            </Field>
            <div className="relative">
              <Field label="كلمة المرور" htmlFor="dev-password" hint={signup ? "8 أحرف على الأقل." : undefined}>
                <Input id="dev-password" type={show ? "text" : "password"} dir="ltr" className="pe-10 text-start" value={password}
                       onChange={(e) => setPassword(e.target.value)} autoComplete={signup ? "new-password" : "current-password"}
                       minLength={signup ? 8 : undefined} required />
              </Field>
              <button type="button" onClick={() => setShow(!show)} aria-label={show ? "إخفاء كلمة المرور" : "إظهار كلمة المرور"}
                      className="absolute end-0 top-[1.85rem] grid size-9 place-items-center text-muted-foreground hover:text-foreground">
                {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
            {error && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive-ink">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy || !email || !password || (signup && (fullName.trim().length < 2 || password.length < 8))}>
              {busy ? <Spinner /> : signup ? "إنشاء الحساب" : "دخول"}
            </Button>
          </form>
        </div>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          {signup ? "لديك حساب؟ " : "ليس لديك حساب؟ "}
          <Link to={devPath(signup ? "/login" : "/signup")} className="font-semibold text-[#651E2C] hover:underline">
            {signup ? "سجّل الدخول" : "أنشئ حساب مطور"}
          </Link>
        </p>
      </main>
    </div>
  );
}
