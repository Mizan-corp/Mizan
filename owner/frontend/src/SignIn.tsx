import { type FormEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/stores/auth";
import { appUrl } from "@/lib/urls";
import { actions } from "@app/lib/data";
import { errorText } from "@app/lib/format";
import { Mark } from "@app/Shell";
import { Button, ErrorNote, Field, Input } from "@app/ui";

/**
 * Signing in on the platform opens the owner panel. Staff sign in on their
 * workspace's own login page instead, which opens the app directly.
 */
export default function SignIn({ notice }: { notice?: string }) {
  const qc = useQueryClient();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(notice ?? null);
  const [slug, setSlug] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await actions.login({ login: login.trim(), password });
      qc.setQueryData(["me"], r.owner);
      useAuth.getState().setToken(r.access_token);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-svh lg:grid-cols-[1fr_1.1fr]">
      <div className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <a href={appUrl("website", "/")} className="mb-10 flex items-center gap-2.5">
            <Mark />
            <span className="title text-xl text-ink">ميزان</span>
          </a>
          <h1 className="title text-[28px] leading-snug text-ink">ادخل إلى حسابك</h1>
          <p className="mt-2 text-[15px] text-mute">مساحات عملك واشتراكاتك وفواتيرك في مكان واحد.</p>

          <form onSubmit={submit} className="mt-8 grid gap-4">
            <Field label="اسم المستخدم">
              <Input autoComplete="username" autoFocus required dir="ltr" className="text-start" value={login} onChange={(e) => setLogin(e.target.value)} />
            </Field>
            <Field label="كلمة المرور">
              <Input type="password" autoComplete="current-password" required dir="ltr" className="text-start" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            {error && <ErrorNote>{error}</ErrorNote>}
            <Button type="submit" variant="primary" size="lg" busy={busy} className="mt-2 w-full">
              دخول
            </Button>
          </form>

          <p className="mt-6 text-sm text-mute">
            ليس لديك حساب؟{" "}
            <a href={appUrl("website", "/signup")} className="font-semibold text-wine hover:underline">
              ابدأ تجربة مجانية
            </a>
          </p>

          <details className="mt-8 rounded-xl border border-line bg-card p-4 text-sm">
            <summary className="cursor-pointer font-semibold text-ink">موظف في منشأة؟</summary>
            <p className="mt-2 text-mute">الموظفون يدخلون من صفحة الدخول الخاصة بمساحة العمل. اكتب اسم الرابط الذي أعطاه لك المدير:</p>
            <form
              className="mt-3 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (slug.trim()) window.location.assign(appUrl("system", `/c/${encodeURIComponent(slug.trim().toLowerCase())}/login`));
              }}
            >
              <Input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="my-store" dir="ltr" className="code h-10 text-start" aria-label="اسم رابط مساحة العمل" />
              <Button type="submit">متابعة</Button>
            </form>
          </details>
        </div>
      </div>

      <aside className="relative hidden overflow-hidden bg-wine lg:block" aria-hidden>
        <div className="absolute inset-0 opacity-[0.07] [background-image:radial-gradient(#fff_1px,transparent_1px)] [background-size:22px_22px]" />
        <div className="relative flex h-full flex-col justify-end p-14 text-[#F5EBDD]">
          <svg viewBox="0 0 200 120" className="mb-10 w-72 opacity-90">
            <path d="M100 10v95M30 30h140M30 30l-18 40h36zM170 30l-18 40h36zM70 105h60" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M12 70a18 8 0 0 0 36 0M152 70a18 8 0 0 0 36 0" stroke="currentColor" strokeWidth="2.5" fill="none" />
          </svg>
          <p className="title max-w-md text-[30px] leading-[1.6]">كل منشآتك، بحساب واحد.</p>
          <p className="mt-3 max-w-md text-[15px] leading-relaxed text-[#F5EBDD]/75">
            افتح أي مساحة عمل بضغطة، تابع الفترة التجريبية، واشترك أو جدّد بالبطاقة أو المحفظة.
          </p>
        </div>
      </aside>
    </div>
  );
}
