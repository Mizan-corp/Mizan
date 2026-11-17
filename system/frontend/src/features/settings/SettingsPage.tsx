import { useEffect, useRef, useState } from "react";
import { IS_ON_PREMISE } from "@app/lib/deployment";
import { NetworkDevices } from "./NetworkDevices";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Paintbrush,
  Store,
  User as UserIcon,
  Upload,
  Image as ImageIcon,
  ExternalLink,
  Check,
  Eye,
  Trash2,
  Lock,
  Wifi,
} from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { Button, Card, ErrorBox, Input, Select, Spinner } from "@/components/ui";
import { useAuth } from "@/stores/auth";
import { useModulesStore } from "@app/stores/modules";
import { useVat } from "@app/lib/vat";

interface Settings {
  store_name?: string;
  store_phone?: string;
  store_address?: string;
  currency?: string;
  paper_size?: string;
  low_stock_threshold?: string;
  logo_url?: string;
  login_title?: string;
  login_subtitle?: string;
  login_cover_url?: string;
  login_support_contact?: string;
  theme_primary?: string;
  login_show_powered_by?: string | boolean;
  // VAT (ADR-014 D6): stored as "true" / "false"; the tax number as 9 digits.
  vat_registered?: string | boolean;
  prices_include_vat?: string | boolean;
  tax_number?: string;
}

const on = (v: string | boolean | undefined, fallback: boolean) =>
  v === undefined || v === "" ? fallback : v === true || v === "true";

interface UserSettings {
  theme?: string;
  language?: string;
  notify_low_stock?: boolean;
  notify_sales?: boolean;
}

const COLOR_PRESETS = [
  { label: "عنابي ميزان التحريري", value: "#651E2C" },
  { label: "كحلي كلاسيكي", value: "#1E3A8A" },
  { label: "زمردي غامق", value: "#134E4A" },
  { label: "عنبري ملكي", value: "#78350F" },
  { label: "رمادي فحمي", value: "#1E293B" },
];

export default function SettingsPage() {
  const qc = useQueryClient();
  const tenant = useAuth((s) => s.tenant);
  const hasStorefront = useModulesStore((s) => s.hasModule("storefront"));
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api.get<Settings>("/settings") });
  const uq = useQuery({ queryKey: ["user-settings"], queryFn: () => api.get<{ settings: UserSettings }>("/users/me/settings") });
  // The VAT settings come from the signed-in endpoint (the workspace's own values, checked).
  const vatq = useVat();

  const [form, setForm] = useState<Settings>({});
  const [dirty, setDirty] = useState(false);
  const [uform, setUform] = useState<UserSettings>({});
  const [udirty, setUdirty] = useState(false);
  const [activeTab, setActiveTab] = useState<"branding" | "store" | "personal" | "devices">("branding");

  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingCover, setUploadingCover] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const logoInputRef = useRef<HTMLInputElement>(null);
  const coverInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (q.data && !dirty) {
      const v = vatq.data;
      setForm(v ? { ...q.data, vat_registered: String(v.vat_registered), prices_include_vat: String(v.prices_include_vat),
                    tax_number: v.tax_number_display || v.tax_number } : q.data);
    }
  }, [q.data, vatq.data, dirty]);

  useEffect(() => {
    if (uq.data && !udirty) setUform(uq.data.settings ?? {});
  }, [uq.data, udirty]);

  const save = useMutation({
    mutationFn: () =>
      api.put("/settings", {
        store_name: form.store_name,
        store_phone: form.store_phone,
        store_address: form.store_address,
        currency: form.currency,
        paper_size: form.paper_size,
        low_stock_threshold: form.low_stock_threshold,
        logo_url: form.logo_url,
        login_title: form.login_title,
        login_subtitle: form.login_subtitle,
        login_cover_url: form.login_cover_url,
        login_support_contact: form.login_support_contact,
        theme_primary: form.theme_primary,
        login_show_powered_by: form.login_show_powered_by === false ? "false" : "true",
        vat_registered: on(form.vat_registered, false) ? "true" : "false",
        prices_include_vat: on(form.prices_include_vat, true) ? "true" : "false",
        tax_number: form.tax_number ?? "",
      }),
    onSuccess: () => {
      setDirty(false);
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const usave = useMutation({
    mutationFn: () => api.put("/users/me/settings", { settings: uform }),
    onSuccess: () => {
      setUdirty(false);
      qc.invalidateQueries({ queryKey: ["user-settings"] });
    },
  });

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    setUploadError(null);
    try {
      const data = new FormData();
      data.append("file", file);
      const res = await api.postForm<{ logo_url: string }>("/settings/upload-logo", data);
      setForm((prev) => ({ ...prev, logo_url: res.logo_url }));
      setDirty(true);
    } catch (err: any) {
      setUploadError(err?.message || "تعذر رفع الشعار، يرجى المحاولة بصورة أخرى");
    } finally {
      setUploadingLogo(false);
      if (logoInputRef.current) logoInputRef.current.value = "";
    }
  }

  async function handleCoverUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingCover(true);
    setUploadError(null);
    try {
      const data = new FormData();
      data.append("file", file);
      const res = await api.postForm<{ cover_url: string }>("/settings/upload-cover", data);
      setForm((prev) => ({ ...prev, login_cover_url: res.cover_url }));
      setDirty(true);
    } catch (err: any) {
      setUploadError(err?.message || "تعذر رفع صورة الغلاف");
    } finally {
      setUploadingCover(false);
      if (coverInputRef.current) coverInputRef.current.value = "";
    }
  }

  const previewLoginUrl = tenant?.slug ? `/c/${tenant.slug}/login` : "/login";

  type StoreFieldKey =
    | "store_name"
    | "store_phone"
    | "store_address"
    | "currency"
    | "paper_size"
    | "low_stock_threshold";

  const fields: { key: StoreFieldKey; label: string }[] = [
    { key: "store_name", label: "اسم المتجر / المنشأة" },
    { key: "store_phone", label: "الهاتف" },
    { key: "store_address", label: "العنوان" },
    { key: "currency", label: "العملة" },
    { key: "paper_size", label: "مقاس الورق" },
    { key: "low_stock_threshold", label: "حد المخزون المنخفض" },
  ];

  if (q.isLoading || uq.isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 p-4" aria-busy="true" aria-label="جارٍ التحميل">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-12 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (q.isError) {
    return (
      <div className="mx-auto max-w-4xl p-4">
        <ErrorBox message={(q.error as Error).message} onRetry={() => q.refetch()} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6 text-[#262321]">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#DECFC0] pb-5">
        <div>
          <h1 className="text-2xl sm:text-3xl font-serif-ar font-bold text-[#35151D] tracking-tight">
            الإعدادات والتخصيص
          </h1>
          <p className="text-xs sm:text-sm text-[#77716E] mt-1">
            إدارة الهوية البصرية، بوابة تسجيل الدخول، إعدادات الفوترة، والتفضيلات الشخصية.
          </p>
        </div>

        {/* Global Save Button */}
        {activeTab !== "personal" && (
          <div className="flex items-center gap-2">
            <Button
              disabled={save.isPending || !dirty}
              onClick={() => save.mutate()}
              className="bg-[#651E2C] hover:bg-[#521723] text-[#FAF6F0] rounded-xl px-5 py-2 text-sm font-semibold shadow-sm"
            >
              {save.isPending ? <Spinner /> : dirty ? "حفظ التغييرات" : "تم الحفظ"}
            </Button>
            {dirty && (
              <Button
                variant="ghost"
                onClick={() => {
                  setForm(q.data ?? {});
                  setDirty(false);
                }}
                className="text-[#77716E] hover:text-[#262321]"
              >
                تراجع
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Tabs Switcher */}
      <div className="flex items-center gap-1.5 p-1 bg-[#FAF6F0] border border-[#DECFC0] rounded-2xl max-w-fit">
        <button
          onClick={() => setActiveTab("branding")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
            activeTab === "branding"
              ? "bg-[#651E2C] text-[#FAF6F0] shadow-sm"
              : "text-[#77716E] hover:text-[#262321] hover:bg-[#FFFFFF]"
          }`}
        >
          <Paintbrush className="h-4 w-4" />
          <span>الهوية وتسجيل الدخول</span>
        </button>

        <button
          onClick={() => setActiveTab("store")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
            activeTab === "store"
              ? "bg-[#651E2C] text-[#FAF6F0] shadow-sm"
              : "text-[#77716E] hover:text-[#262321] hover:bg-[#FFFFFF]"
          }`}
        >
          <Store className="h-4 w-4" />
          <span>المتجر والفوترة</span>
        </button>

        <button
          onClick={() => setActiveTab("personal")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
            activeTab === "personal"
              ? "bg-[#651E2C] text-[#FAF6F0] shadow-sm"
              : "text-[#77716E] hover:text-[#262321] hover:bg-[#FFFFFF]"
          }`}
        >
          <UserIcon className="h-4 w-4" />
          <span>إعداداتي الشخصية</span>
        </button>

        {IS_ON_PREMISE && (
          <button
            onClick={() => setActiveTab("devices")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
              activeTab === "devices"
                ? "bg-[#651E2C] text-[#FAF6F0] shadow-sm"
                : "text-[#77716E] hover:text-[#262321] hover:bg-[#FFFFFF]"
            }`}
          >
            <Wifi className="h-4 w-4" />
            <span>الأجهزة على الشبكة</span>
          </button>
        )}
      </div>

      {uploadError && <ErrorBox message={uploadError} />}
      {save.isError && <ErrorBox message={(save.error as Error).message} />}

      {/* ── TAB 1: BRANDING & LOGIN CUSTOMIZATION ── */}
      {activeTab === "branding" && (
        <div className="space-y-6">
          {/* Live Preview Header Card */}
          <Card className="p-5 bg-gradient-to-l from-[#FAF6F0] to-[#FFFFFF] border border-[#DECFC0] rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <h3 className="text-sm font-semibold text-[#262321]">
                  بوابة تسجيل الدخول المخصصة لشركتك
                </h3>
              </div>
              <p className="text-xs text-[#77716E]">
                يصل موظفوك إلى مساحة العمل عبر الرابط المخصص لمنشأتك مع شعارك ورسالتك الترحيبية.
              </p>
            </div>

            <a
              href={previewLoginUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#FFFFFF] border border-[#DECFC0] text-xs font-semibold text-[#651E2C] hover:bg-[#FAF6F0] transition-colors shadow-2xs whitespace-nowrap"
            >
              <Eye className="h-4 w-4 text-[#651E2C]" />
              <span>معاينة صفحة الدخول الحالية</span>
              <ExternalLink className="h-3.5 w-3.5 opacity-60" />
            </a>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Form Inputs (Left 7 Cols) */}
            <div className="lg:col-span-7 space-y-6">
              {/* Card: Logo & Identity */}
              <Card className="p-6 bg-[#FFFFFF] border border-[#DECFC0] rounded-2xl space-y-4">
                <h3 className="text-base font-semibold text-[#262321] flex items-center gap-2">
                  <ImageIcon className="h-4 w-4 text-[#651E2C]" />
                  <span>الشعار واسم المنشأة</span>
                </h3>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-[#262321]">
                    اسم المنشأة / العلامة التجارية (يظهر في عنوان صفحة الدخول)
                  </label>
                  <Input
                    value={form.store_name ?? ""}
                    placeholder="مثال: مجمع الأمل الطبي أو صيدليات النخبة"
                    onChange={(e) => {
                      setForm({ ...form, store_name: e.target.value });
                      setDirty(true);
                    }}
                  />
                </div>

                {/* Logo Section */}
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-[#262321]">
                    شعار المنشأة (Logo)
                  </label>

                  <div className="flex items-center gap-4">
                    {form.logo_url ? (
                      <div className="relative group">
                        <img
                          src={form.logo_url}
                          alt="Logo"
                          className="h-16 w-16 rounded-xl border border-[#DECFC0] object-contain p-1 bg-[#FAF6F0]"
                          onError={(e) => {
                            e.currentTarget.style.display = "none";
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            setForm({ ...form, logo_url: "" });
                            setDirty(true);
                          }}
                          className="absolute -top-2 -right-2 p-1 bg-red-600 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
                          title="حذف الشعار"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ) : (
                      <div className="h-16 w-16 rounded-xl border border-dashed border-[#DECFC0] flex items-center justify-center bg-[#FAF6F0] text-[#77716E]">
                        <ImageIcon className="h-6 w-6 opacity-40" />
                      </div>
                    )}

                    <div className="flex-1 space-y-2">
                      <input
                        ref={logoInputRef}
                        type="file"
                        accept="image/png,image/jpeg,image/webp,image/gif"
                        className="hidden"
                        onChange={handleLogoUpload}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        disabled={uploadingLogo}
                        onClick={() => logoInputRef.current?.click()}
                        className="w-full border border-[#DECFC0] bg-[#FAF6F0] hover:bg-[#FFFFFF] text-xs font-semibold py-2 rounded-xl flex items-center justify-center gap-2"
                      >
                        {uploadingLogo ? (
                          <Spinner className="size-4" />
                        ) : (
                          <>
                            <Upload className="h-3.5 w-3.5 text-[#651E2C]" />
                            <span>رفع شعار من الجهاز (PNG, JPG, WebP)</span>
                          </>
                        )}
                      </Button>

                      <Input
                        value={form.logo_url ?? ""}
                        placeholder="أو أدخل رابط الشعار مباشرة (https://...)"
                        className="text-xs"
                        onChange={(e) => {
                          setForm({ ...form, logo_url: e.target.value });
                          setDirty(true);
                        }}
                      />
                    </div>
                  </div>
                </div>
              </Card>

              {/* Card: Login Page Texts & Cover */}
              <Card className="p-6 bg-[#FFFFFF] border border-[#DECFC0] rounded-2xl space-y-4">
                <h3 className="text-base font-semibold text-[#262321] flex items-center gap-2">
                  <Paintbrush className="h-4 w-4 text-[#651E2C]" />
                  <span>تخصيص نصوص ومظهر صفحة تسجيل الدخول</span>
                </h3>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-[#262321]">
                    العنوان الترحيبي الرئيسي (Login Headline)
                  </label>
                  <Input
                    value={form.login_title ?? ""}
                    placeholder="مثال: مرحباً بكم في بوابة مجمع الأمل الطبي"
                    onChange={(e) => {
                      setForm({ ...form, login_title: e.target.value });
                      setDirty(true);
                    }}
                  />
                  <p className="text-[11px] text-[#77716E] mt-1">
                    اتركه فارغاً لاستخدام العنوان الافتراضي &quot;مرحباً بعودتك&quot;.
                  </p>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-[#262321]">
                    الوصف الترحيبي الفرعي (Login Subtitle)
                  </label>
                  <Input
                    value={form.login_subtitle ?? ""}
                    placeholder="مثال: بوابة الأطباء والكوادر الإدارية — نظام الرعاية الشامل"
                    onChange={(e) => {
                      setForm({ ...form, login_subtitle: e.target.value });
                      setDirty(true);
                    }}
                  />
                </div>

                {/* Cover Image */}
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-[#262321]">
                    صورة الغلاف الجانبي (Cover Background Image)
                  </label>

                  <div className="flex items-center gap-4">
                    {form.login_cover_url ? (
                      <div className="relative group">
                        <img
                          src={form.login_cover_url}
                          alt="Cover"
                          className="h-16 w-24 rounded-xl border border-[#DECFC0] object-cover"
                          onError={(e) => {
                            e.currentTarget.style.display = "none";
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            setForm({ ...form, login_cover_url: "" });
                            setDirty(true);
                          }}
                          className="absolute -top-2 -right-2 p-1 bg-red-600 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
                          title="حذف صورة الغلاف"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ) : (
                      <div className="h-16 w-24 rounded-xl border border-dashed border-[#DECFC0] flex items-center justify-center bg-[#FAF6F0] text-[#77716E]">
                        <ImageIcon className="h-6 w-6 opacity-40" />
                      </div>
                    )}

                    <div className="flex-1 space-y-2">
                      <input
                        ref={coverInputRef}
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        className="hidden"
                        onChange={handleCoverUpload}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        disabled={uploadingCover}
                        onClick={() => coverInputRef.current?.click()}
                        className="w-full border border-[#DECFC0] bg-[#FAF6F0] hover:bg-[#FFFFFF] text-xs font-semibold py-2 rounded-xl flex items-center justify-center gap-2"
                      >
                        {uploadingCover ? (
                          <Spinner className="size-4" />
                        ) : (
                          <>
                            <Upload className="h-3.5 w-3.5 text-[#651E2C]" />
                            <span>رفع صورة غلاف للمنشأة</span>
                          </>
                        )}
                      </Button>

                      <Input
                        value={form.login_cover_url ?? ""}
                        placeholder="أو أدخل رابط الصورة (https://...)"
                        className="text-xs"
                        onChange={(e) => {
                          setForm({ ...form, login_cover_url: e.target.value });
                          setDirty(true);
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Primary Theme Color */}
                <div className="space-y-2 pt-2 border-t border-[#DECFC0]/60">
                  <label className="block text-xs font-semibold text-[#262321]">
                    لون الزر الرئيسي للعلامة التجارية (Brand Accent Color)
                  </label>

                  <div className="flex flex-wrap items-center gap-2">
                    {COLOR_PRESETS.map((preset) => {
                      const isSelected =
                        (form.theme_primary || "#651E2C").toLowerCase() ===
                        preset.value.toLowerCase();
                      return (
                        <button
                          key={preset.value}
                          type="button"
                          onClick={() => {
                            setForm({ ...form, theme_primary: preset.value });
                            setDirty(true);
                          }}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs transition-all ${
                            isSelected
                              ? "border-[#262321] ring-2 ring-[#651E2C]/20 font-bold bg-[#FAF6F0]"
                              : "border-[#DECFC0] bg-[#FFFFFF] hover:bg-[#FAF6F0]"
                          }`}
                        >
                          <span
                            className="h-3.5 w-3.5 rounded-full border border-black/10"
                            style={{ backgroundColor: preset.value }}
                          />
                          <span>{preset.label}</span>
                          {isSelected && <Check className="h-3 w-3 text-[#651E2C]" />}
                        </button>
                      );
                    })}

                    <div className="flex items-center gap-2 ms-auto">
                      <input
                        type="color"
                        value={form.theme_primary || "#651E2C"}
                        onChange={(e) => {
                          setForm({ ...form, theme_primary: e.target.value });
                          setDirty(true);
                        }}
                        className="h-8 w-8 cursor-pointer rounded-lg border border-[#DECFC0] p-0.5 bg-transparent"
                        title="اختر لوناً مخصصاً"
                      />
                      <Input
                        value={form.theme_primary || "#651E2C"}
                        onChange={(e) => {
                          setForm({ ...form, theme_primary: e.target.value });
                          setDirty(true);
                        }}
                        className="w-24 text-xs font-mono uppercase"
                      />
                    </div>
                  </div>
                </div>

                {/* Support Contact */}
                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-[#262321]">
                    معلومات الدعم الفني والمساعدة (يظهر أسفل نموذج الدخول)
                  </label>
                  <Input
                    value={form.login_support_contact ?? ""}
                    placeholder="مثال: هاتف الدعم: 920000000 أو support@company.com"
                    onChange={(e) => {
                      setForm({ ...form, login_support_contact: e.target.value });
                      setDirty(true);
                    }}
                  />
                </div>

                {/* Powered by Toggle */}
                <div className="flex items-center gap-3 pt-2">
                  <input
                    id="toggle-powered"
                    type="checkbox"
                    checked={form.login_show_powered_by !== false && form.login_show_powered_by !== "false"}
                    onChange={(e) => {
                      setForm({ ...form, login_show_powered_by: e.target.checked });
                      setDirty(true);
                    }}
                    className="h-4 w-4 rounded text-[#651E2C] border-[#DECFC0] focus:ring-[#651E2C]"
                  />
                  <label htmlFor="toggle-powered" className="text-xs text-[#262321] cursor-pointer">
                    إظهار شارة &quot;مشغّل بواسطة منصة ميزان ERP&quot; أسفل صفحة الدخول
                  </label>
                </div>
              </Card>
            </div>

            {/* Interactive Live Preview (Right 5 Cols) */}
            <div className="lg:col-span-5">
              <div className="sticky top-6 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-[#77716E]">
                    محاكاة حية للمظهر
                  </span>
                  <span className="text-[11px] text-[#77716E]">
                    تتحدث تلقائياً مع التعديلات
                  </span>
                </div>

                {/* Simulated Login Page Preview Container */}
                <div className="rounded-3xl border border-[#DECFC0] overflow-hidden shadow-lg bg-[#FAF6F0]">
                  {/* Simulated Browser Bar */}
                  <div className="px-3 py-2 bg-[#FAF6F0] border-b border-[#DECFC0] flex items-center gap-2 text-[10px] text-[#77716E] font-mono">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 rounded-full bg-red-400" />
                      <span className="w-2 h-2 rounded-full bg-yellow-400" />
                      <span className="w-2 h-2 rounded-full bg-green-400" />
                    </div>
                    <span className="truncate bg-[#FFFFFF] px-2 py-0.5 rounded border border-[#DECFC0] w-full text-center dir-ltr">
                      mizan.cloud{previewLoginUrl}
                    </span>
                  </div>

                  {/* Simulated Split View */}
                  <div className="grid grid-cols-12 min-h-[360px]">
                    {/* Left simulated banner (5 cols) */}
                    <div
                      className="col-span-5 bg-[#35151D] text-[#FAF6F0] p-4 flex flex-col justify-between relative overflow-hidden"
                      style={
                        form.login_cover_url
                          ? {
                              backgroundImage: `linear-gradient(rgba(53, 21, 29, 0.85), rgba(53, 21, 29, 0.95)), url('${form.login_cover_url}')`,
                              backgroundSize: "cover",
                              backgroundPosition: "center",
                            }
                          : undefined
                      }
                    >
                      <div className="flex items-center gap-1.5">
                        {form.logo_url ? (
                          <img
                            src={form.logo_url}
                            alt="Logo"
                            className="h-6 w-auto max-w-[60px] rounded object-contain bg-white/10 p-0.5"
                          />
                        ) : (
                          <div className="h-4 w-4 rounded-full bg-[#D4626E]" />
                        )}
                        <span className="text-[9px] font-bold truncate">
                          {form.store_name || "ميزان"}
                        </span>
                      </div>

                      <div className="my-auto py-2 space-y-1 text-center">
                        <p className="text-[10px] font-serif-ar leading-tight text-[#FAF6F0]">
                          {form.login_title || "مرحباً بعودتك،"}
                        </p>
                        <p className="text-[8px] text-[#E7D6C1]/80 line-clamp-2">
                          {form.login_subtitle || (form.store_name ? `إلى مساحة عمل ${form.store_name}` : "نظام موحد ومرن لإدارة أعمالك.")}
                        </p>
                      </div>

                      <div className="text-[7px] text-[#E7D6C1]/50 font-mono">
                        © {new Date().getFullYear()} {form.store_name || "Mizan"}
                      </div>
                    </div>

                    {/* Right simulated form (7 cols) */}
                    <div className="col-span-7 bg-[#FFFFFF] p-4 flex flex-col justify-between">
                      <div className="space-y-3">
                        <div className="space-y-1">
                          <h4 className="text-xs font-semibold text-[#262321] truncate">
                            {form.store_name ? `تسجيل الدخول إلى ${form.store_name}` : "تسجيل الدخول"}
                          </h4>
                          <p className="text-[8px] text-[#77716E]">
                            أدخل بيانات حسابك للمتابعة
                          </p>
                        </div>

                        <div className="space-y-1.5">
                          <div className="h-6 rounded bg-[#FAF6F0] border border-[#DECFC0] flex items-center px-2 text-[8px] text-[#77716E]">
                            اسم المستخدم
                          </div>
                          <div className="h-6 rounded bg-[#FAF6F0] border border-[#DECFC0] flex items-center px-2 text-[8px] text-[#77716E] justify-between">
                            <span>••••••••</span>
                            <Lock className="h-2.5 w-2.5 opacity-50" />
                          </div>
                          <button
                            type="button"
                            style={{ backgroundColor: form.theme_primary || "#651E2C" }}
                            className="w-full text-white text-[9px] font-semibold py-1.5 rounded-full shadow-2xs"
                          >
                            تسجيل الدخول
                          </button>
                        </div>

                        {form.login_support_contact && (
                          <div className="p-1.5 rounded bg-[#FAF6F0] border border-[#DECFC0] text-[7px] text-center text-[#77716E] truncate">
                            {form.login_support_contact}
                          </div>
                        )}
                      </div>

                      {(form.login_show_powered_by !== false && form.login_show_powered_by !== "false") && (
                        <div className="pt-2 border-t border-[#DECFC0]/60 text-center text-[7px] text-[#77716E]/70 font-mono">
                          مشغّل بواسطة ميزان ERP
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="text-center">
                  <a
                    href={previewLoginUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-[#651E2C] hover:underline font-semibold inline-flex items-center gap-1"
                  >
                    <span>فتح صفحة تسجيل الدخول كاملة في متصفحك</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: STORE & BILLING SETTINGS ── */}
      {activeTab === "devices" && IS_ON_PREMISE && <NetworkDevices />}

      {activeTab === "store" && (
        <div className="space-y-6">
          <Card className="p-6 bg-[#FFFFFF] border border-[#DECFC0] rounded-2xl space-y-4">
            <h2 className="text-base font-semibold text-[#262321]">
              إعدادات المتجر والفوترة العامة
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {fields.map((f) => (
                <div key={f.key}>
                  <label className="mb-1 block text-xs font-semibold text-[#262321]">
                    {f.label}
                  </label>
                  <Input
                    value={form[f.key] ?? ""}
                    onChange={(e) => {
                      setForm({ ...form, [f.key]: e.target.value });
                      setDirty(true);
                    }}
                  />
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-6 bg-[#FFFFFF] border border-[#DECFC0] rounded-2xl space-y-4">
            <div>
              <h2 className="text-base font-semibold text-[#262321]">ضريبة القيمة المضافة</h2>
              <p className="text-xs text-[#77716E] mt-0.5">
                تُحسب الضريبة لكل سطر عند إصدار المستند وتُحفظ معه، وتظهر على الفواتير والإيصالات مع رقم التسجيل الضريبي.
                التغيير يسري على المستندات الجديدة فقط.
              </p>
            </div>
            <label className="flex items-center gap-3 text-sm text-[#262321] cursor-pointer">
              <input
                type="checkbox"
                className="h-4 w-4 rounded text-[#651E2C] border-[#DECFC0]"
                checked={on(form.vat_registered, false)}
                onChange={(e) => {
                  setForm({ ...form, vat_registered: e.target.checked ? "true" : "false" });
                  setDirty(true);
                }}
              />
              المنشأة مسجلة في ضريبة القيمة المضافة
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="tax-number" className="mb-1 block text-xs font-semibold text-[#262321]">
                  رقم التسجيل الضريبي (9 أرقام)
                </label>
                <Input
                  id="tax-number"
                  dir="ltr"
                  inputMode="numeric"
                  placeholder="123-456-789"
                  value={form.tax_number ?? ""}
                  onChange={(e) => {
                    setForm({ ...form, tax_number: e.target.value });
                    setDirty(true);
                  }}
                />
                {form.tax_number && form.tax_number.replace(/[\s-]/g, "").length !== 9 && (
                  <p className="mt-1 text-[11px] text-red-700">الرقم يتكون من 9 أرقام، ويمكن كتابته بشرطات</p>
                )}
              </div>
              <div>
                <span className="mb-1 block text-xs font-semibold text-[#262321]">أسعار البيع</span>
                <label className="flex items-center gap-3 text-sm text-[#262321] cursor-pointer">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded text-[#651E2C] border-[#DECFC0]"
                    disabled={!on(form.vat_registered, false)}
                    checked={on(form.prices_include_vat, true)}
                    onChange={(e) => {
                      setForm({ ...form, prices_include_vat: e.target.checked ? "true" : "false" });
                      setDirty(true);
                    }}
                  />
                  الأسعار شاملة الضريبة
                </label>
                <p className="mt-1 text-[11px] text-[#77716E]">
                  {on(form.prices_include_vat, true)
                    ? "سعر 114 ج.م لصنف خاضع = 100 قبل الضريبة + 14 ضريبة."
                    : "سعر 100 ج.م لصنف خاضع تُضاف إليه 14 ج.م ضريبة عند البيع."}
                </p>
              </div>
            </div>
          </Card>

          {hasStorefront && tenant?.slug && (
            <Card className="p-6 bg-[#FFFFFF] border border-[#DECFC0] rounded-2xl flex items-center justify-between">
              <div>
                <p className="font-semibold text-sm text-[#262321]">المتجر الإلكتروني العام</p>
                <p className="text-xs text-[#77716E]">
                  واجهة العملاء العامة تعمل تلقائياً من هذه البيانات
                </p>
              </div>
              <a
                href={`/store/${tenant.slug}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FAF6F0] border border-[#DECFC0] text-xs font-semibold text-[#651E2C] hover:bg-[#FFFFFF] transition-colors"
              >
                <span>فتح المتجر الإلكتروني</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </Card>
          )}
        </div>
      )}

      {/* ── TAB 3: PERSONAL SETTINGS ── */}
      {activeTab === "personal" && (
        <div className="space-y-6">
          <Card className="p-6 bg-[#FFFFFF] border border-[#DECFC0] rounded-2xl space-y-4">
            <div className="border-b border-[#DECFC0]/60 pb-3">
              <h2 className="text-base font-semibold text-[#262321]">
                إعداداتي (تفضيلات المستخدم الشخصية)
              </h2>
              <p className="text-xs text-[#77716E] mt-0.5">
                هذه الإعدادات خاصة بحسابك ولا تؤثر على بقية مستخدمي المنشأة.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-xs font-semibold text-[#262321]">
                  السمة (Theme)
                </label>
                <Select
                  value={uform.theme ?? "default"}
                  onChange={(e) => {
                    setUform({ ...uform, theme: e.target.value });
                    setUdirty(true);
                  }}
                >
                  <option value="default">افتراضي (Warm Editorial Luxury)</option>
                  <option value="dark">داكن (Dark)</option>
                  <option value="light">فاتح (Light)</option>
                </Select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-[#262321]">
                  اللغة (Language)
                </label>
                <Select
                  value={uform.language ?? "ar"}
                  onChange={(e) => {
                    setUform({ ...uform, language: e.target.value });
                    setUdirty(true);
                  }}
                >
                  <option value="ar">العربية (RTL)</option>
                  <option value="en">English (LTR)</option>
                </Select>
              </div>
            </div>

            <div className="space-y-2 pt-2 border-t border-[#DECFC0]/60">
              <div className="flex items-center gap-2">
                <input
                  id="notify_stock"
                  type="checkbox"
                  checked={uform.notify_low_stock ?? true}
                  onChange={(e) => {
                    setUform({ ...uform, notify_low_stock: e.target.checked });
                    setUdirty(true);
                  }}
                  className="h-4 w-4 rounded text-[#651E2C] border-[#DECFC0]"
                />
                <label htmlFor="notify_stock" className="text-xs text-[#262321] cursor-pointer">
                  تلقي تنبيهات عند انخفاض المخزون
                </label>
              </div>

              <div className="flex items-center gap-2">
                <input
                  id="notify_sales"
                  type="checkbox"
                  checked={uform.notify_sales ?? true}
                  onChange={(e) => {
                    setUform({ ...uform, notify_sales: e.target.checked });
                    setUdirty(true);
                  }}
                  className="h-4 w-4 rounded text-[#651E2C] border-[#DECFC0]"
                />
                <label htmlFor="notify_sales" className="text-xs text-[#262321] cursor-pointer">
                  تلقي إشعارات المبيعات والعمليات الجديدة
                </label>
              </div>
            </div>

            {usave.isError && <ErrorBox message={(usave.error as Error).message} />}

            <div className="pt-2 flex items-center gap-2">
              <Button
                disabled={usave.isPending || !udirty}
                onClick={() => usave.mutate()}
                className="bg-[#651E2C] hover:bg-[#521723] text-[#FAF6F0] rounded-xl px-5 py-2 text-sm font-semibold shadow-sm"
              >
                {usave.isPending ? <Spinner /> : udirty ? "حفظ إعداداتي" : "تم الحفظ"}
              </Button>
              {udirty && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setUform(uq.data?.settings ?? {});
                    setUdirty(false);
                  }}
                  className="text-[#77716E] hover:text-[#262321]"
                >
                  تراجع
                </Button>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
