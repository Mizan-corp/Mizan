import { useEffect, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { Link } from "@app/seo/LocaleLink";
import {
  User as UserIcon,
  AtSign,
  Lock,
  Mail,
  Phone,
  ArrowRight,
  ArrowLeft,
  Globe,
  Check,
} from "lucide-react";
import { ErrorBox, Spinner } from "@/components/ui";
import { useAuth } from "@/stores/auth";
import { sound } from "@/lib/sound";
import { MizanLogo } from "@/components/MizanLogo";
import { useTranslation } from "@/i18n";
import { appUrl } from "@/lib/urls";
import { openWithSession } from "@/lib/handoff";
import { useOwner } from "@app/lib/ownerSession";
import { track } from "@app/analytics";

export default function SignupPage() {
  const { locale, dir } = useTranslation();
  const isAr = locale === "ar";

  const draft: { full_name?: string; username?: string; email?: string; phone?: string } = (() => {
    try {
      return JSON.parse(
        sessionStorage.getItem("mizan.owner") ??
          sessionStorage.getItem("vendora.owner") ??
          "{}"
      );
    } catch {
      return {};
    }
  })();

  const [fullName, setFullName] = useState(draft.full_name ?? "");
  const [username, setUsername] = useState(draft.username ?? "");
  const [email, setEmail] = useState(draft.email ?? "");
  const [phone, setPhone] = useState(draft.phone ?? "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  // A signed-in owner adds workspaces and picks plans in their panel, not by signing up again (#79).
  const owner = useOwner();
  useEffect(() => {
    if (owner) openWithSession("owner", "/", owner.token);
  }, [owner]);

  const setSignupDraft = () => useAuth.setState({});

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    if (!/^[\w.\-]+$/u.test(username) || username.length < 3) {
      sound.error();
      setError(isAr ? "اسم المستخدم يجب أن يكون 3 أحرف على الأقل ويحتوي على أحرف/أرقام/._- فقط (يمكن استخدام العربية)" : "Username must be at least 3 characters (letters, numbers, . _ -).");
      setBusy(false);
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      sound.error();
      setError(isAr ? "اكتب بريدًا إلكترونيًا صحيحًا؛ نرسل إليه رمز التأكيد والإيصالات." : "Enter a valid email; we send the confirmation code and receipts there.");
      setBusy(false);
      return;
    }
    if (!/^\+?[0-9 ]{8,20}$/.test(phone.trim())) {
      sound.error();
      setError(isAr ? "اكتب رقم هاتف صحيحًا (أرقام فقط، مثل 01001234567)." : "Enter a valid phone number (digits only, e.g. 01001234567).");
      setBusy(false);
      return;
    }
    try {
      sound.click();
      const payload = JSON.stringify({ full_name: fullName, username, password, email: email.trim(), phone: phone.trim() });
      sessionStorage.setItem("mizan.owner", payload);
      setSignupDraft();
      track("signup_start");
      navigate("/onboarding");
    } catch (err: any) {
      sound.error();
      setError(
        err?.message ||
          (isAr ? "حدث خطأ أثناء حفظ البيانات" : "An error occurred during registration.")
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      dir={dir}
      className={`min-h-screen grid grid-cols-1 lg:grid-cols-12 bg-[#FAF6F0] text-[#262321] ${
        isAr ? "font-body" : "font-sans"
      }`}
    >
      {/* ── LEFT PANEL: Deep Merlot Architectural Brand Cover (#35151D) ── */}
      <div className="lg:col-span-5 bg-[#35151D] text-[#FAF6F0] hero-concentric-arcs p-8 sm:p-12 lg:p-16 flex flex-col justify-between relative overflow-hidden border-b lg:border-b-0 lg:border-e border-[#481822]">
        {/* Top Header */}
        <div className="flex items-center justify-between z-10">
          <Link to="/" aria-label={isAr ? "ميزان ERP: الصفحة الرئيسية" : "Mizan ERP: home"}>
            <MizanLogo size="lg" theme="dark" locale={locale} />
          </Link>
          <RouterLink
            to={isAr ? "/en/signup" : "/signup"}
            hrefLang={isAr ? "en" : "ar"}
            lang={isAr ? "en" : "ar"}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/15 bg-white/5 text-xs text-[#E7D6C1] hover:bg-white/10 transition-colors"
          >
            <Globe className="h-3.5 w-3.5 text-[#D4626E]" aria-hidden="true" />
            <span>{isAr ? "English" : "العربية"}</span>
          </RouterLink>
        </div>

        {/* Center Brand Statement matching Image 4 */}
        <div className="my-auto py-12 space-y-4 text-center z-10 max-w-sm mx-auto">
          <div className="flex justify-center mb-6">
            <div className="p-4 rounded-3xl bg-white/5 border border-white/10 shadow-2xl backdrop-blur-md">
              <MizanLogo size="xl" variant="icon" theme="dark" />
            </div>
          </div>

          <h2
            className={`text-2xl sm:text-3xl lg:text-4xl font-normal text-[#FAF6F0] tracking-tight leading-snug ${
              isAr ? "font-serif-ar" : "font-serif-en"
            }`}
          >
            {isAr ? "ابدأ رحلتك معنا،" : "Start your journey,"}
            <br />
            <span className="italic text-[#D4626E]">
              {isAr ? "نحو إدارة أكثر توازناً." : "into perfect balance."}
            </span>
          </h2>

          <p className="text-xs sm:text-sm text-[#E7D6C1]/80 leading-relaxed font-light">
            {isAr
              ? "تجربة سحابية مجانية لمدة 14 يوماً. بدون بطاقة ائتمانية وبجاهزية تشغيل فورية."
              : "A free 14-day trial. No credit card required. Ready in a minute."}
          </p>

          <div className="pt-4 flex flex-col gap-2 text-start text-xs text-[#E7D6C1]/90 bg-white/5 p-4 rounded-2xl border border-white/10">
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-[#27835C] shrink-0" />
              <span>{isAr ? "عزل كامل لبيانات كل منشأة" : "Each business's data isolated"}</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-[#27835C] shrink-0" />
              <span>{isAr ? "كاشير سريع يحفظ الفواتير عند انقطاع النت" : "A fast till that keeps sales when offline"}</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-[#27835C] shrink-0" />
              <span>{isAr ? "دعم فني عبر واتساب والهاتف" : "Support over WhatsApp and phone"}</span>
            </div>
          </div>
        </div>

        {/* Bottom Status */}
        <div className="pt-6 border-t border-white/10 flex items-center justify-between text-xs text-[#E7D6C1]/60 z-10 font-mono">
          <span>© {__BUILD_YEAR__} Mizan ERP</span>
          <span className="flex items-center gap-1.5 text-[#27835C]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#27835C]" />
            <span>{isAr ? "تسجيل آمن ومشفر" : "Secure Registration"}</span>
          </span>
        </div>
      </div>

      {/* ── RIGHT PANEL: Warm Ivory Form Area (#FAF6F0) ── */}
      <div className="lg:col-span-7 flex items-center justify-center p-6 sm:p-12 lg:p-16">
        <div className="w-full max-w-md space-y-8 bg-[#FFFFFF] p-8 sm:p-10 rounded-3xl border border-[#DECFC0] shadow-xl">
          <div className="space-y-2 text-start">
            <h1
              className={`text-2xl sm:text-3xl font-semibold text-[#262321] tracking-tight ${
                isAr ? "font-serif-ar" : "font-serif-en"
              }`}
            >
              {isAr ? "إنشاء حساب جديد" : "Create Your Account"}
            </h1>
            <p className="text-xs sm:text-sm text-[#77716E]">
              {isAr
                ? "خطوة واحدة فقط وسنساعدك في تجهيز مساحة عمل شركتك واختيار الوحدات."
                : "Step 1 of 2: Create your admin credentials to setup your workspace."}
            </p>
          </div>

          {error && <ErrorBox message={error} />}

          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5 text-start">
              <label htmlFor="reg-fullname" className="text-xs font-semibold text-[#262321]">
                {isAr ? "الاسم الكامل" : "Full Name"}
              </label>
              <div className="relative">
                <UserIcon className="absolute top-1/2 -translate-y-1/2 start-3.5 h-4 w-4 text-[#77716E]" />
                <input
                  id="reg-fullname"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  autoFocus
                  autoComplete="name"
                  placeholder={isAr ? "مثال: م. أحمد كمال" : "e.g. John Doe"}
                  className="w-full rounded-xl border border-[#DECFC0] bg-[#FAF6F0] py-2.5 ps-10 pe-3 text-sm text-[#262321] placeholder:text-[#77716E]/70 focus:border-[#651E2C] focus:bg-[#FFFFFF] focus:outline-none transition-colors"
                />
              </div>
            </div>

            <div className="space-y-1.5 text-start">
              <label htmlFor="reg-username" className="text-xs font-semibold text-[#262321]">
                {isAr ? "اسم المستخدم أو المعرف" : "Username"}
              </label>
              <div className="relative">
                <AtSign className="absolute top-1/2 -translate-y-1/2 start-3.5 h-4 w-4 text-[#77716E]" />
                <input
                  id="reg-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoComplete="username"
                  placeholder={isAr ? "مثال: mizan_admin" : "e.g. mizan_admin"}
                  className="w-full rounded-xl border border-[#DECFC0] bg-[#FAF6F0] py-2.5 ps-10 pe-3 text-sm text-[#262321] placeholder:text-[#77716E]/70 focus:border-[#651E2C] focus:bg-[#FFFFFF] focus:outline-none transition-colors font-mono"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5 text-start">
                <label htmlFor="reg-email" className="text-xs font-semibold text-[#262321]">
                  {isAr ? "البريد الإلكتروني" : "Email"}
                </label>
                <div className="relative">
                  <Mail className="absolute top-1/2 -translate-y-1/2 start-3.5 h-4 w-4 text-[#77716E]" />
                  <input
                    id="reg-email"
                    type="email"
                    dir="ltr"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    placeholder="name@example.com"
                    className="w-full rounded-xl border border-[#DECFC0] bg-[#FAF6F0] py-2.5 ps-10 pe-3 text-sm text-start text-[#262321] placeholder:text-[#77716E]/70 focus:border-[#651E2C] focus:bg-[#FFFFFF] focus:outline-none transition-colors"
                  />
                </div>
              </div>
              <div className="space-y-1.5 text-start">
                <label htmlFor="reg-phone" className="text-xs font-semibold text-[#262321]">
                  {isAr ? "رقم الهاتف" : "Phone"}
                </label>
                <div className="relative">
                  <Phone className="absolute top-1/2 -translate-y-1/2 start-3.5 h-4 w-4 text-[#77716E]" />
                  <input
                    id="reg-phone"
                    type="tel"
                    dir="ltr"
                    inputMode="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                    autoComplete="tel"
                    placeholder="01001234567"
                    className="w-full rounded-xl border border-[#DECFC0] bg-[#FAF6F0] py-2.5 ps-10 pe-3 text-sm text-start text-[#262321] placeholder:text-[#77716E]/70 focus:border-[#651E2C] focus:bg-[#FFFFFF] focus:outline-none transition-colors"
                  />
                </div>
              </div>
              <p className="-mt-2 text-[11px] text-[#77716E] sm:col-span-2">
                {isAr ? "نرسل إلى بريدك رمز تأكيد، وإيصالات الدفع، ورمز استعادة كلمة المرور إن نسيتها." : "We email you a confirmation code, payment receipts, and a reset code if you forget your password."}
              </p>
            </div>

            <div className="space-y-1.5 text-start">
              <label htmlFor="reg-password" className="text-xs font-semibold text-[#262321]">
                {isAr ? "كلمة المرور" : "Password"}
              </label>
              <div className="relative">
                <Lock className="absolute top-1/2 -translate-y-1/2 start-3.5 h-4 w-4 text-[#77716E]" />
                <input
                  id="reg-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  autoComplete="new-password"
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-[#DECFC0] bg-[#FAF6F0] py-2.5 ps-10 pe-3 text-sm text-[#262321] placeholder:text-[#77716E]/70 focus:border-[#651E2C] focus:bg-[#FFFFFF] focus:outline-none transition-colors"
                />
              </div>
              <span className="text-[11px] text-[#77716E]">
                {isAr ? "يجب أن تحتوي على 6 خانات على الأقل" : "Must be at least 6 characters"}
              </span>
            </div>

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-full bg-[#651E2C] hover:bg-[#521723] text-[#FAF6F0] py-3.5 text-sm font-semibold shadow-md transition-all flex items-center justify-center gap-2 hover:scale-[1.01] disabled:opacity-50 mt-2"
            >
              {busy ? (
                <Spinner className="size-4" />
              ) : (
                <>
                  <span>{isAr ? "متابعة لتجهيز المنشأة" : "Continue to Workspace Setup"}</span>
                  {isAr ? <ArrowLeft className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
                </>
              )}
            </button>
            <p className="text-center text-[11px] leading-relaxed text-[#77716E]">
              {isAr ? "بإنشاء الحساب فإنك توافق على " : "By creating an account you agree to the "}
              <Link to="/terms" target="_blank" className="font-semibold text-[#651E2C] hover:underline">
                {isAr ? "شروط الاستخدام" : "Terms of Service"}
              </Link>
              {isAr ? " و" : " and "}
              <Link to="/privacy" target="_blank" className="font-semibold text-[#651E2C] hover:underline">
                {isAr ? "سياسة الخصوصية" : "Privacy Policy"}
              </Link>
              .
            </p>
          </form>

          <div className="pt-4 border-t border-[#E6DCD2] text-center text-xs text-[#77716E]">
            <span>{isAr ? "لديك حساب بالفعل؟" : "Already have an account?"} </span>
            <a href={appUrl("owner", "/login")} className="font-semibold text-[#651E2C] hover:underline">
              {isAr ? "تسجيل الدخول" : "Sign In"}
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
