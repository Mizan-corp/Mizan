/**
 * PAGE CONTRACT
 * Page: تهيئة مساحة العمل (/onboarding)
 * User: تاجر أو مدير يسجل للتو — نجهز له مساحة عمل فورية مهيأة على طبيعة نشاطه التجاري
 * Primary information: نوع النشاط التجاري → اسم المنشأة وحجمها → لوحة الألوان والوحدات → إنشاء
 * Primary action: step 0..1 → «التالي»؛ step 2 → «أنشئ مساحة عملي الآن»؛ busy → جارٍ التجهيز
 * Art Direction: Warm Editorial Luxury (Oxblood, Deep Merlot, Warm Ivory, Muted Rose)
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  Check,
  Scale as ScaleIcon,
  Palette,
  Sparkles,
  Building2,
  Building,
  Store,
  Layers,
  Search,
  ShoppingCart,
  UtensilsCrossed,
  Pill,
  Briefcase,
  GraduationCap,
  Truck,
  Warehouse,
  Globe,
  Stethoscope,
  Plane,
  Hotel,
  Dumbbell,
  Wrench,
  Factory,
  Apple,
  FlaskConical,
  Printer,
  HardHat,
  Wheat,
  Zap,
  Landmark,
  ShieldCheck,
  Ticket,
  Flame,
  X,
  type LucideIcon,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { openWithSession } from "@/lib/handoff";
import { saveOwnerSession } from "@app/lib/ownerSession";
import { type TenantInfo } from "@/stores/auth";
import { applyTheme, type ThemePack } from "@/lib/theme";
import { Button, ErrorBox, Input } from "@/components/ui";
import {
  PALETTE_OPTIONS,
  SECTOR_OPTIONS,
  getSectorModules,
  getSectorDefaultFeatures,
} from "@/lib/plans";
import { cn } from "@/lib/utils";
import { MizanLogo } from "@/components/MizanLogo";

interface OwnerDraft {
  full_name: string;
  username: string;
  password: string;
  email?: string;
  phone?: string;
}

interface ThemeSummary {
  id: string;
  name: string;
  name_en?: string;
  description: string;
  swatches: string[];
  fonts?: { body?: string; display?: string };
  radius?: string;
}

interface ActivityBranding {
  themes: string[];
  fonts: { body: string; display: string };
  note: string;
}

interface ThemeFontFileEntry {
  family: string;
  src: string;
  weight?: string;
  style?: "normal" | "italic";
}

interface BrandingOptions {
  themes: ThemeSummary[];
  full: Record<string, ThemePack>;
  activities: Record<string, ActivityBranding>;
  families: string[];
  family_files: Record<string, ThemeFontFileEntry[]>;
}

const STEPS = ["النشاط التجاري", "بيانات المنشأة", "الهوية البصرية", "الوحدات"];

interface SectorMeta {
  value: string;
  label: string;
  desc: string;
  category: "commerce" | "food" | "health" | "services" | "construction" | "industry";
  icon: LucideIcon;
  badge?: string;
  popular?: boolean;
}

const SECTOR_META_MAP: Record<string, { category: SectorMeta["category"]; icon: LucideIcon; badge?: string; popular?: boolean }> = {
  // Commerce & Retail
  retail: { category: "commerce", icon: ShoppingCart, badge: "Retail-POS", popular: true },
  wholesale: { category: "commerce", icon: Truck, badge: "تسعير كميات", popular: true },
  ecommerce: { category: "commerce", icon: Globe, badge: "ربط متجر", popular: true },
  warehousing: { category: "commerce", icon: Warehouse, badge: "مستودعات 3PL" },
  logistics: { category: "commerce", icon: Truck, badge: "بوالص وأساطيل" },

  // Food & Hospitality
  restaurant: { category: "food", icon: UtensilsCrossed, badge: "KDS وطاولات", popular: true },
  hotel: { category: "food", icon: Hotel, badge: "حجوزات وغرف" },
  travel: { category: "food", icon: Plane, badge: "حجوزات طيران" },
  entertainment: { category: "food", icon: Ticket, badge: "بوابات وتذاكر" },

  // Health & Wellness
  pharmacy: { category: "health", icon: Pill, badge: "تشغيلات وصلاحية", popular: true },
  healthcare: { category: "health", icon: Stethoscope, badge: "ملفات وتأمين", popular: true },
  gym: { category: "health", icon: Dumbbell, badge: "بوابات واشتراكات" },
  salon: { category: "health", icon: Sparkles, badge: "خدمات ومواعيد" },

  // Services & Professions
  consulting: { category: "services", icon: Briefcase, badge: "ساعات قابلة للفوترة" },
  legal: { category: "services", icon: ScaleIcon, badge: "قضايا وأمانات" },
  agency: { category: "services", icon: Palette, badge: "مشاريع وعقود" },
  maintenance: { category: "services", icon: Wrench, badge: "أوامر شغل وفنيون" },
  school: { category: "services", icon: GraduationCap, badge: "أقساط ورسوم" },
  services: { category: "services", icon: Building2, badge: "خدمات وعقود" },

  // Construction & Property
  construction: { category: "construction", icon: HardHat, badge: "BOQ ومستخلصات", popular: true },
  property: { category: "construction", icon: Building, badge: "عقود وصيانة" },
  plumbing: { category: "construction", icon: Store, badge: "معارض وتشطيبات" },

  // Industry & Energy
  manufacturing: { category: "industry", icon: Factory, badge: "BOM وMRP" },
  food: { category: "industry", icon: Apple, badge: "خلطات وسلامة" },
  pharmaceuticals: { category: "industry", icon: FlaskConical, badge: "معايير GMP" },
  printing: { category: "industry", icon: Printer, badge: "تذاكر ومونتاج" },
  agriculture: { category: "industry", icon: Wheat, badge: "محاصيل وثروة" },
  energy: { category: "industry", icon: Zap, badge: "عدادات وصيانة" },
  petroleum: { category: "industry", icon: Flame, badge: "آبار وتشغيل" },
  banking: { category: "industry", icon: Landmark, badge: "قيود مزدوجة" },
  insurance: { category: "industry", icon: ShieldCheck, badge: "وثائق ومطالبات" },
  government: { category: "industry", icon: Landmark, badge: "صناديق وموازنات" },
};

const CATEGORIES = [
  { id: "all", label: "كافة القطاعات" },
  { id: "commerce", label: "تجارة وتجزئة" },
  { id: "food", label: "مطاعم وضيافة" },
  { id: "health", label: "صحة ورياضة" },
  { id: "services", label: "خدمات واستشارات" },
  { id: "construction", label: "مقاولات وعقار" },
  { id: "industry", label: "صناعة وإنتاج" },
] as const;

export default function OnboardingWizard() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const draft: OwnerDraft | null = (() => {
    try {
      return JSON.parse(
        sessionStorage.getItem("mizan.owner") ?? sessionStorage.getItem("vendora.owner") ?? "null"
      );
    } catch {
      return null;
    }
  })();

  const initialSector = searchParams.get("sector") || "retail";
  const [step, setStep] = useState(0);
  const [sector, setSector] = useState(initialSector);
  const [sectorCategory, setSectorCategory] = useState<string>("all");
  const [sectorSearch, setSectorSearch] = useState<string>("");
  const [company, setCompany] = useState("");
  const [scale, setScale] = useState("medium");
  const [palette, setPalette] = useState<string>("mizan");
  const [branding, setBranding] = useState<BrandingOptions | null>(null);
  const [bodyFont, setBodyFont] = useState<string>("");
  const [displayFont, setDisplayFont] = useState<string>("");
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [features, setFeatures] = useState<string[]>(() => getSectorDefaultFeatures(initialSector));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSelectSector(newSector: string) {
    setSector(newSector);
    setFeatures(getSectorDefaultFeatures(newSector));
    const rec = branding?.activities?.[newSector]?.themes?.[0];
    if (rec && branding?.full?.[rec]) handleSelectPalette(rec);
  }

  // Ensure features are updated if sector changes externally or initializes
  useEffect(() => {
    const validModuleIds = new Set(getSectorModules(sector).map((m) => m.id));
    const hasAnyCurrentModule = features.some((f) => validModuleIds.has(f));
    if (!hasAnyCurrentModule || features.length === 0) {
      setFeatures(getSectorDefaultFeatures(sector));
    }
  }, [sector]);

  // Enriched sectors list
  const enrichedSectors: SectorMeta[] = useMemo(() => {
    return SECTOR_OPTIONS.map((s) => {
      const meta = SECTOR_META_MAP[s.value] || { category: "services", icon: Store };
      return {
        ...s,
        category: meta.category,
        icon: meta.icon,
        badge: meta.badge,
        popular: meta.popular,
      };
    });
  }, []);

  // Filtered sectors by search and category
  const filteredSectors = useMemo(() => {
    return enrichedSectors.filter((s) => {
      const matchesCategory = sectorCategory === "all" || s.category === sectorCategory;
      const q = sectorSearch.trim().toLowerCase();
      const matchesSearch =
        !q ||
        s.label.toLowerCase().includes(q) ||
        s.desc.toLowerCase().includes(q) ||
        s.value.toLowerCase().includes(q) ||
        (s.badge && s.badge.toLowerCase().includes(q));
      return matchesCategory && matchesSearch;
    });
  }, [enrichedSectors, sectorCategory, sectorSearch]);

  // Real theme packs + this sector's recommendations; the static grid is the fallback.
  useEffect(() => {
    let live = true;
    api.get<BrandingOptions>("/platform/branding")
      .then((b) => {
        if (!live) return;
        setBranding(b);
        const rec = b.activities?.[sector]?.themes?.[0];
        if (rec && b.full?.[rec]) {
          setPalette(rec);
          const body = b.full[rec].fonts?.body ?? "";
          const display = b.full[rec].fonts?.display ?? body;
          setBodyFont(body);
          setDisplayFont(display);
          const files = [...(b.full[rec].fonts?.files ?? [])];
          applyTheme({ ...b.full[rec], fonts: { ...b.full[rec].fonts, body, display, files } });
        }
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load each advertised family once, so its option chip previews the real face.
  useEffect(() => {
    if (!branding) return;
    const css = Object.values(branding.family_files ?? {})
      .flat()
      .map((f) => `@font-face { font-family: "${f.family}"; src: url("${f.src}"); font-weight: ${f.weight ?? "400"}; font-style: ${f.style ?? "normal"}; font-display: swap; }`)
      .join("\n");
    const el = document.createElement("style");
    el.id = "mizan-branding-families";
    el.textContent = css;
    document.head.appendChild(el);
    return () => el.remove();
  }, [branding]);

  // Leaving the wizard restores the site's own look.
  useEffect(
    () => () => {
      applyTheme(null);
      document.documentElement.removeAttribute("data-theme");
    },
    []
  );

  if (!draft || !draft.email || !draft.phone) {
    // No account step yet, or one saved before signup asked for the email and phone (#72).
    return (
      <Centered>
        <Emptyish />
      </Centered>
    );
  }

  function toggleFeature(v: string) {
    setFeatures((f) => (f.includes(v) ? f.filter((x) => x !== v) : [...f, v]));
  }

  function applyWithFonts(themeId: string, body: string, display: string) {
    const pack = branding?.full?.[themeId];
    if (!pack) return;
    const files = [...(pack.fonts?.files ?? [])];
    for (const fam of [body, display]) {
      if (!fam || files.some((f) => f.family === fam)) continue;
      files.push(...(branding?.family_files?.[fam] ?? []));
    }
    applyTheme({ ...pack, fonts: { ...pack.fonts, body: body || pack.fonts?.body, display: display || pack.fonts?.display, files } });
  }

  function handleSelectPalette(themeId: string) {
    setPalette(themeId);
    const pack = branding?.full?.[themeId];
    const body = pack?.fonts?.body ?? "";
    const display = pack?.fonts?.display ?? body;
    setBodyFont(body);
    setDisplayFont(display);
    applyWithFonts(themeId, body, display);
  }

  function handlePickFont(which: "body" | "display", fam: string) {
    const body = which === "body" ? fam : bodyFont;
    const display = which === "display" ? fam : displayFont;
    setBodyFont(body);
    setDisplayFont(display);
    applyWithFonts(palette, body, display);
  }

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ access_token: string; owner_token: string; tenant: TenantInfo }>("/platform/signup", {
        company_name: company,
        sector,
        scale,
        palette,
        fonts: bodyFont ? { body: bodyFont, display: displayFont || bodyFont } : undefined,
        features,
        owner_username: draft!.username,
        owner_password: draft!.password,
        owner_full_name: draft!.full_name,
        owner_email: draft!.email ?? "",
        owner_phone: draft!.phone ?? "",
      });

      sessionStorage.removeItem("mizan.owner");
      sessionStorage.removeItem("vendora.owner");

      // The new owner lands in the owner panel, signed in, where a short tour
      // shows their workspace, how to open it, the trial and subscriptions.
      saveOwnerSession(r.owner_token);
      openWithSession("owner", "/", r.owner_token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("اسم المستخدم محجوز — ارجع للخطوة السابقة واختر اسمًا آخر.");
        setStep(0);
      } else {
        setError(err instanceof ApiError ? err.message : "تعذر تجهيز مساحة العمل — حاول مجددًا");
      }
    } finally {
      setBusy(false);
    }
  }

  const selectedSectorObj = enrichedSectors.find((s) => s.value === sector);
  const activityBranding = branding?.activities?.[sector];
  const recIds = activityBranding?.themes ?? [];
  const recThemes = recIds
    .map((id) => branding?.themes.find((t) => t.id === id))
    .filter((t): t is ThemeSummary => Boolean(t));
  const selectedTheme = branding?.themes.find((t) => t.id === palette);

  function ThemeCard({ t }: { t: ThemeSummary }) {
    const isSelected = palette === t.id;
    return (
      <button
        type="button"
        onClick={() => handleSelectPalette(t.id)}
        aria-pressed={isSelected}
        className={cn(
          "group relative flex flex-col gap-2.5 rounded-xl border p-3.5 text-start transition-all cursor-pointer",
          isSelected
            ? "border-primary bg-primary/[0.06] ring-1 ring-primary shadow-sm"
            : "border-line bg-card hover:border-primary/40 hover:bg-secondary/50"
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <span
            className="text-xs font-bold text-foreground truncate"
            style={t.fonts?.body ? { fontFamily: `"${t.fonts.body}", sans-serif` } : undefined}
          >
            {t.name}
          </span>
          <span
            className={cn(
              "grid size-4 shrink-0 place-items-center rounded-full border transition-all",
              isSelected
                ? "border-primary bg-primary text-primary-foreground scale-110"
                : "border-muted-foreground/30 opacity-40 group-hover:opacity-100"
            )}
          >
            {isSelected && <Check className="size-2.5 stroke-[3]" />}
          </span>
        </div>
        <div className="flex items-center gap-1.5" aria-hidden>
          {(t.swatches ?? []).slice(0, 5).map((sw, i) => (
            <span
              key={i}
              className="size-5 rounded-md border border-black/10 shadow-xs"
              style={{ background: sw }}
            />
          ))}
        </div>
        <span className="block text-[10px] text-muted-foreground leading-relaxed line-clamp-2">
          {t.description}
        </span>
        {t.fonts?.body && (
          <span className="text-[9px] font-mono text-muted-foreground/70" dir="ltr">
            {t.fonts.body}
            {t.fonts.display && t.fonts.display !== t.fonts.body ? ` + ${t.fonts.display}` : ""}
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="grid min-h-svh place-items-center bg-background p-4 text-foreground selection:bg-primary selection:text-primary-foreground">
      <div className="w-full max-w-4xl py-6 transition-all duration-300">
        <Link to="/" className="mb-6 flex items-center justify-center gap-3">
          <MizanLogo size="lg" />
        </Link>

        <div className="rounded-2xl border border-line bg-card p-5 sm:p-8 shadow-xl backdrop-blur-sm">
          {/* Step Progress Indicator */}
          <div className="mb-6 flex items-center gap-3" aria-label={`خطوة ${step + 1} من 4`}>
            {STEPS.map((label, i) => (
              <div key={label} className="flex flex-1 flex-col gap-1.5">
                <div
                  className={cn(
                    "h-1.5 rounded-full transition-all duration-300",
                    i <= step ? "bg-primary shadow-xs" : "bg-secondary"
                  )}
                />
                <span
                  className={cn(
                    "text-xs font-medium transition-colors",
                    i === step ? "font-bold text-foreground" : "text-muted-foreground"
                  )}
                >
                  <span className="font-mono me-1">{i + 1}.</span>
                  {label}
                </span>
              </div>
            ))}
          </div>

          {/* ══════════════════════════════════════════════════════════════════
              Step 0: Business Sector (Curated, Categorized, Searchable)
              ══════════════════════════════════════════════════════════════════ */}
          {step === 0 && (
            <fieldset className="space-y-4">
              <div>
                <legend className="flex items-center gap-2 text-lg sm:text-xl font-bold text-foreground">
                  <Building2 className="size-5 text-primary shrink-0" />
                  ما هو نوع وطبيعة نشاطك التجاري؟
                </legend>
                <p className="mt-1 text-xs text-muted-foreground">
                  سيقوم محرك ميزان بتهيئة الدليل المحاسبي، شاشات نقاط البيع، والمخزون، وقوالب الفواتير لتناسب قطاعك فورياً.
                </p>
              </div>

              {/* Search & Category Filter Toolbar */}
              <div className="space-y-2.5 pt-1">
                <div className="relative">
                  <Search className="absolute start-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                  <input
                    type="text"
                    value={sectorSearch}
                    onChange={(e) => setSectorSearch(e.target.value)}
                    placeholder="ابحث عن نشاطك (مثال: سوبرماركت، مطعم، صيدلية، مقاولات، ملابس...)"
                    className="w-full h-10 rounded-xl border border-line bg-background pe-9 ps-9 text-xs font-medium placeholder:text-muted-foreground/60 focus:border-primary focus:outline-hidden focus:ring-1 focus:ring-primary transition"
                  />
                  {sectorSearch && (
                    <button
                      type="button"
                      onClick={() => setSectorSearch("")}
                      className="absolute end-2.5 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground rounded-md"
                      title="مسح البحث"
                    >
                      <X className="size-3.5" />
                    </button>
                  )}
                </div>

                {/* Category Filter Pills */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs scrollbar-none">
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => {
                        setSectorCategory(cat.id);
                      }}
                      className={cn(
                        "shrink-0 rounded-lg px-3 py-1.5 font-medium transition text-[11px]",
                        sectorCategory === cat.id
                          ? "bg-primary text-primary-foreground font-bold shadow-xs"
                          : "border border-line bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary"
                      )}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sectors Grid with Controlled Scroll */}
              <div className="max-h-[50vh] sm:max-h-[52vh] overflow-y-auto pe-1 space-y-2 focus:outline-hidden">
                {filteredSectors.length === 0 ? (
                  <div className="py-12 text-center text-muted-foreground border border-dashed border-line rounded-xl">
                    <p className="text-sm font-semibold">لا يوجد قطاع مطابق لبحثك: &quot;{sectorSearch}&quot;</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      جرب البحث بكلمة أبسط أو اختر &quot;تجارة وتجزئة&quot; أو &quot;خدمات عامة&quot;.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setSectorSearch("");
                        setSectorCategory("all");
                      }}
                      className="mt-3 text-xs font-bold text-primary hover:underline"
                    >
                      عرض كافة القطاعات
                    </button>
                  </div>
                ) : (
                  <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredSectors.map((o) => {
                      const IconComponent = o.icon;
                      const isSelected = sector === o.value;
                      return (
                        <button
                          key={o.value}
                          type="button"
                          onClick={() => handleSelectSector(o.value)}
                          aria-pressed={isSelected}
                          className={cn(
                            "group relative flex flex-col justify-between rounded-xl border p-3.5 text-start transition-all duration-200 cursor-pointer",
                            isSelected
                              ? "border-primary bg-primary/[0.06] shadow-sm ring-1 ring-primary"
                              : "border-line bg-card hover:border-primary/40 hover:bg-secondary/50"
                          )}
                        >
                          <div>
                            <div className="flex items-center justify-between gap-2 mb-2">
                              <span
                                className={cn(
                                  "grid size-8 place-items-center rounded-lg transition-colors",
                                  isSelected
                                    ? "bg-primary text-primary-foreground shadow-xs"
                                    : "bg-primary/10 text-primary group-hover:bg-primary/20"
                                )}
                              >
                                <IconComponent className="size-4" />
                              </span>

                              <div className="flex items-center gap-1.5">
                                {o.badge && (
                                  <span
                                    className={cn(
                                      "rounded px-1.5 py-0.5 text-[9px] font-mono font-medium",
                                      isSelected
                                        ? "bg-primary/20 text-primary font-bold"
                                        : "bg-secondary text-muted-foreground"
                                    )}
                                  >
                                    {o.badge}
                                  </span>
                                )}
                                <span
                                  className={cn(
                                    "grid size-4 place-items-center rounded-full border transition-all",
                                    isSelected
                                      ? "border-primary bg-primary text-primary-foreground scale-110"
                                      : "border-muted-foreground/30 opacity-40 group-hover:opacity-100"
                                  )}
                                >
                                  {isSelected && <Check className="size-2.5 stroke-[3]" />}
                                </span>
                              </div>
                            </div>

                            <span className="block text-xs font-bold text-foreground leading-snug line-clamp-1">
                              {o.label.split("(")[0].trim()}
                            </span>
                            <span className="mt-1 block text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                              {o.desc}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Selected Sector Summary Banner */}
              {selectedSectorObj && (
                <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 flex items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="grid size-7 place-items-center rounded-lg bg-primary text-primary-foreground shrink-0">
                      <selectedSectorObj.icon className="size-3.5" />
                    </span>
                    <div className="min-w-0">
                      <p className="font-bold text-foreground truncate">
                        القطاع المختار: {selectedSectorObj.label.split("(")[0].trim()}
                      </p>
                      <p className="text-[10px] text-muted-foreground truncate">{selectedSectorObj.desc}</p>
                    </div>
                  </div>
                  <span className="shrink-0 text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
                    جاهز للتخصيص ✓
                  </span>
                </div>
              )}
            </fieldset>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              Step 1: Company Profile & Scale
              ══════════════════════════════════════════════════════════════════ */}
          {step === 1 && (
            <fieldset className="space-y-5">
              <div>
                <legend className="flex items-center gap-2 text-lg sm:text-xl font-bold text-foreground">
                  <Sparkles className="size-5 text-primary shrink-0" />
                  اسم منشأتك وحجم فروعها
                </legend>
                <p className="mt-1 text-xs text-muted-foreground">
                  هذا الاسم يظهر في الترويسة والفواتير الرسمية وتقارير الفروع ويمكنك تعديله في أي وقت.
                </p>
              </div>

              <div>
                <label className="text-xs font-semibold text-foreground mb-1.5 block">
                  اسم الشركة / المنشأة أو المحل التجاري *
                </label>
                <Input
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="مثال: مجمع الوادي التجاري، مطعم وكافيه البستان، صيدلية النور"
                  autoFocus
                  className="h-11 text-sm font-medium"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-foreground mb-2 block">
                  حجم الفروع ونقاط التشغيل
                </label>
                <div className="grid gap-3 sm:grid-cols-3">
                  {[
                    {
                      value: "small",
                      label: "فرع واحد",
                      desc: "محل أو مكتب فردي وفريق عمل مركز",
                      icon: Store,
                    },
                    {
                      value: "medium",
                      label: "٢–٣ فروع",
                      desc: "أكثر من فرع مع مستودع مركزي ومزامنة",
                      icon: Building,
                    },
                    {
                      value: "large",
                      label: "٤ فروع وأكثر",
                      desc: "سلسلة فروع ممتدة وشبكة توزيع كبرى",
                      icon: Building2,
                    },
                  ].map((o) => {
                    const ScaleIconComp = o.icon;
                    const isSelected = scale === o.value;
                    return (
                      <button
                        key={o.value}
                        type="button"
                        onClick={() => setScale(o.value)}
                        className={cn(
                          "flex flex-col items-start p-4 rounded-xl border text-start transition-all cursor-pointer",
                          isSelected
                            ? "border-primary bg-primary/5 ring-1 ring-primary shadow-xs"
                            : "border-line bg-card hover:border-primary/40 hover:bg-secondary/50"
                        )}
                      >
                        <div className="flex items-center justify-between w-full mb-2">
                          <span
                            className={cn(
                              "grid size-8 place-items-center rounded-lg",
                              isSelected ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
                            )}
                          >
                            <ScaleIconComp className="size-4" />
                          </span>
                          <span
                            className={cn(
                              "size-4 rounded-full border grid place-items-center",
                              isSelected ? "border-primary bg-primary text-primary-foreground" : "border-border"
                            )}
                          >
                            {isSelected && <Check className="size-2.5" />}
                          </span>
                        </div>
                        <span className="block text-xs font-bold text-foreground">{o.label}</span>
                        <span className="mt-1 block text-[11px] text-muted-foreground leading-relaxed">
                          {o.desc}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </fieldset>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              Step 2: Theme Palette & Modular Features
              ══════════════════════════════════════════════════════════════════ */}
          {/* ══════════════════════════════════════════════════════════════════
              Step 2: Brand identity - real theme packs, live preview
              ══════════════════════════════════════════════════════════════════ */}
          {step === 2 && (
            <fieldset className="space-y-5">
              <div>
                <legend className="flex items-center gap-2 text-lg sm:text-xl font-bold text-foreground">
                  <Palette className="size-5 text-primary shrink-0" />
                  هوية منشأتك البصرية
                </legend>
                <p className="mt-1 text-xs text-muted-foreground">
                  ترشيحاتنا التصميمية لنشاطك — المعاينة تُطبق فوراً على هذه الصفحة بألوانها
                  وخطوطها الحقيقية، وتقدر تغيّر كل حاجة لاحقاً من الإعدادات.
                </p>
              </div>

              {branding ? (
                <>
                  {recThemes.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-1.5">
                        <Sparkles className="size-3.5 text-primary" />
                        <span className="text-xs font-bold text-foreground">ترشيحات تناسب نشاطك</span>
                      </div>
                      {activityBranding?.note && (
                        <p className="text-[11px] text-muted-foreground mb-2.5 leading-relaxed">
                          {activityBranding.note}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-2">
                        {recThemes.map((t) => {
                          const isSelected = palette === t.id;
                          return (
                            <button
                              key={t.id}
                              type="button"
                              onClick={() => handleSelectPalette(t.id)}
                              aria-pressed={isSelected}
                              className={cn(
                                "flex items-center gap-2 rounded-full border pe-3 ps-1.5 py-1.5 transition-all cursor-pointer",
                                isSelected
                                  ? "border-primary bg-primary/[0.08] ring-1 ring-primary shadow-xs"
                                  : "border-line bg-card hover:border-primary/40 hover:bg-secondary/50"
                              )}
                            >
                              <span className="flex -space-x-1.5" aria-hidden>
                                {(t.swatches ?? []).slice(0, 3).map((sw, i) => (
                                  <span
                                    key={i}
                                    className="size-5 rounded-full border-2 border-card shadow-xs"
                                    style={{ background: sw, zIndex: 3 - i }}
                                  />
                                ))}
                              </span>
                              <span className="text-xs font-bold text-foreground">{t.name}</span>
                              {isSelected && <Check className="size-3.5 text-primary stroke-[3]" />}
                            </button>
                          );
                        })}
                        <button
                          type="button"
                          onClick={() => setCatalogOpen(true)}
                          className="flex items-center gap-1.5 rounded-full border border-dashed border-line px-3 py-1.5 text-xs font-bold text-muted-foreground hover:border-primary/40 hover:text-foreground transition cursor-pointer"
                        >
                          <Palette className="size-3.5" />
                          تصفح كل المظاهر ({branding.themes.length})
                        </button>
                      </div>
                    </div>
                  )}

                  {/* The one clear preview: what is applied right now. */}
                  {selectedTheme && (
                    <div className="rounded-xl border border-line bg-secondary/40 p-4">
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="flex -space-x-1.5 shrink-0" aria-hidden>
                            {(selectedTheme.swatches ?? []).slice(0, 4).map((sw, i) => (
                              <span
                                key={i}
                                className="size-6 rounded-full border-2 border-card shadow-xs"
                                style={{ background: sw, zIndex: 4 - i }}
                              />
                            ))}
                          </span>
                          <div className="min-w-0">
                            <p className="text-sm font-bold text-foreground truncate">{selectedTheme.name}</p>
                            <p className="text-[10px] text-muted-foreground truncate">{selectedTheme.name_en}</p>
                          </div>
                        </div>
                        <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full shrink-0">
                          مطبق الآن على الصفحة ✓
                        </span>
                      </div>
                      {selectedTheme.description && (
                        <p className="mt-2 text-[11px] text-muted-foreground leading-relaxed">
                          {selectedTheme.description}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Independent typography: body and display faces, real preview. */}
                  {branding.families?.length > 0 && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {(
                        [
                          { which: "body" as const, label: "خط النصوص", value: bodyFont, hint: "القوائم والنماذج والفواتير" },
                          { which: "display" as const, label: "خط العناوين", value: displayFont, hint: "العناوين والأسماء الكبيرة" },
                        ]
                      ).map((row) => (
                        <div key={row.which}>
                          <label className="text-xs font-semibold text-foreground block">
                            {row.label}
                            <span className="block text-[10px] font-normal text-muted-foreground">{row.hint}</span>
                          </label>
                          <div className="mt-1.5 flex flex-wrap gap-1.5">
                            {branding.families.map((fam) => {
                              const isSelected = row.value === fam;
                              return (
                                <button
                                  key={fam}
                                  type="button"
                                  onClick={() => handlePickFont(row.which, fam)}
                                  aria-pressed={isSelected}
                                  className={cn(
                                    "rounded-lg border px-3 py-1.5 text-xs transition cursor-pointer",
                                    isSelected
                                      ? "border-primary bg-primary/[0.08] text-foreground font-bold ring-1 ring-primary"
                                      : "border-line bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground"
                                  )}
                                  style={{ fontFamily: `"${fam}", sans-serif` }}
                                >
                                  {fam}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div>
                  <label className="text-xs font-semibold text-foreground mb-2 block">
                    لوحة الألوان الرسمية
                  </label>
                  <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                    {PALETTE_OPTIONS.map((o) => {
                      const isSelected = palette === o.value;
                      return (
                        <button
                          key={o.value}
                          type="button"
                          onClick={() => handleSelectPalette(o.value)}
                          className={cn(
                            "flex items-start gap-3 rounded-xl border p-3 text-start transition cursor-pointer",
                            isSelected
                              ? "border-primary bg-primary/5 ring-1 ring-primary shadow-xs"
                              : "border-line bg-card hover:border-primary/40 hover:bg-secondary/50"
                          )}
                        >
                          <span
                            className="mt-0.5 size-5 shrink-0 rounded-full border border-black/10 shadow-xs"
                            style={{ background: o.swatch }}
                            aria-hidden
                          />
                          <div className="min-w-0">
                            <span className="block text-xs font-bold text-foreground truncate">{o.label}</span>
                            <span className="mt-0.5 block text-[10px] text-muted-foreground leading-relaxed line-clamp-2">
                              {o.desc}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </fieldset>
          )}

          {/* ══════════════════════════════════════════════════════════════════
              Step 3: Modular features
              ══════════════════════════════════════════════════════════════════ */}
          {step === 3 && (
            <fieldset className="space-y-5">
              <div>
                <legend className="flex items-center gap-2 text-lg sm:text-xl font-bold text-foreground">
                  <Layers className="size-5 text-primary shrink-0" />
                  الوحدات والمنظومات المبدئية
                </legend>
                <p className="mt-1 text-xs text-muted-foreground">
                  حددنا هذه المنظومات آلياً لتناسب نشاطك — فعّل أو عطّل أي وحدة بضغطة واحدة.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <div className="flex items-center gap-2">
                    <Layers className="size-4 text-primary" />
                    <span className="text-xs font-bold text-foreground">
                      وحدات قطاع (
                      <span className="text-primary font-bold">{selectedSectorObj?.label.split("(")[0].trim() || "المنشأة"}</span>)
                    </span>
                  </div>
                  <span className="text-[10px] text-muted-foreground bg-primary/10 text-primary font-bold px-2 py-0.5 rounded-full font-mono">
                    {features.length} مفعلة
                  </span>
                </div>
                <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3 max-h-[48vh] overflow-y-auto pe-1">
                  {getSectorModules(sector).map((o) => {
                    const isSelected = features.includes(o.id);
                    return (
                      <button
                        key={o.id}
                        type="button"
                        onClick={() => toggleFeature(o.id)}
                        className={cn(
                          "flex flex-col justify-between rounded-xl border p-3.5 text-start transition cursor-pointer group",
                          isSelected
                            ? "border-primary bg-primary/5 ring-1 ring-primary shadow-xs"
                            : "border-line bg-card hover:border-primary/40 hover:bg-secondary/50"
                        )}
                      >
                        <div>
                          <div className="flex items-start justify-between gap-2 mb-1.5">
                            <span className="block text-xs font-bold text-foreground group-hover:text-primary transition-colors">
                              {o.label}
                            </span>
                            <span
                              className={cn(
                                "mt-0.5 grid size-4 shrink-0 place-items-center rounded-md border transition-all",
                                isSelected
                                  ? "border-primary bg-primary text-primary-foreground"
                                  : "border-muted-foreground/30 bg-secondary/40"
                              )}
                            >
                              {isSelected && <Check className="size-2.5 stroke-[3]" />}
                            </span>
                          </div>
                          <span className="block text-[10px] text-muted-foreground leading-relaxed line-clamp-2">
                            {o.desc}
                          </span>
                        </div>
                        {o.badge && (
                          <div className="mt-2.5 pt-2 border-t border-border/40 flex items-center justify-between">
                            <span
                              className={cn(
                                "text-[9px] font-mono px-1.5 py-0.5 rounded font-bold",
                                isSelected ? "bg-primary/20 text-primary" : "bg-secondary text-muted-foreground"
                              )}
                            >
                              {o.badge}
                            </span>
                            <span className="text-[9px] text-muted-foreground/70">
                              {isSelected ? "جاهز للتشغيل ✓" : "معطل"}
                            </span>
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            </fieldset>
          )}

          {error && (
            <div className="mt-5">
              <ErrorBox message={error} />
            </div>
          )}

          {/* Wizard Action Controls */}
          <div className="sticky bottom-0 z-10 -mx-5 sm:-mx-8 -mb-5 sm:-mb-8 mt-8 flex items-center justify-between gap-3 border-t border-border/60 bg-card/95 px-5 sm:px-8 py-3 backdrop-blur-sm rounded-b-2xl">
            <Button
              variant="outline"
              onClick={() => (step === 0 ? nav("/signup") : setStep((s) => s - 1))}
              className="text-xs font-medium"
            >
              ← رجوع
            </Button>

            {step < 3 ? (
              <Button
                onClick={() => setStep((s) => s + 1)}
                disabled={step === 1 && !company.trim()}
                className="font-bold text-xs px-6"
              >
                التالي ←
              </Button>
            ) : (
              <Button onClick={create} disabled={busy} className="font-bold text-xs px-6 shadow-md">
                {busy ? "جارٍ تجهيز مساحة عملك..." : "أنشئ مساحة عملي الآن ✓"}
              </Button>
            )}
          </div>
        </div>

        {/* Full palette catalog lives behind a dialog, not on the wizard body. */}
        {catalogOpen && branding && (
          <div
            className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
            onClick={() => setCatalogOpen(false)}
          >
            <div
              className="w-full max-w-4xl max-h-[85vh] overflow-y-auto rounded-2xl border border-line bg-card p-5 sm:p-6 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
              role="dialog"
              aria-label="كل المظاهر"
            >
              <div className="flex items-center justify-between gap-3 mb-4">
                <div>
                  <h2 className="text-base font-bold text-foreground">كل المظاهر ({branding.themes.length})</h2>
                  <p className="text-[11px] text-muted-foreground">اختيارك يُطبق فوراً على الصفحة خلف النافذة.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setCatalogOpen(false)}
                  className="grid size-8 place-items-center rounded-lg border border-line text-muted-foreground hover:text-foreground hover:bg-secondary/60 transition"
                  aria-label="إغلاق"
                >
                  <X className="size-4" />
                </button>
              </div>
              <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                {branding.themes.map((t) => (
                  <ThemeCard key={t.id} t={t} />
                ))}
              </div>
            </div>
          </div>
        )}

        <p className="mt-4 text-center text-xs text-muted-foreground">
          ستدخل مباشرة على مساحة عمل مهيأة بالكامل، ويمكنك تغيير الأنشطة والوحدات في أي وقت.
        </p>
      </div>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="min-h-svh bg-background text-foreground">{children}</div>;
}

function Emptyish() {
  return (
    <div className="mx-auto max-w-sm rounded-2xl border border-line bg-card p-8 text-center mt-20 shadow-lg">
      <span className="mx-auto mb-4 grid size-12 place-items-center rounded-xl bg-primary/10 text-primary">
        <ScaleIcon className="size-6" />
      </span>
      <h1 className="font-bold text-foreground">ابدأ من صفحة الحساب</h1>
      <p className="mt-2 text-xs text-muted-foreground">
        يقوم المعالج بقراءة بيانات حسابك من خطوة التسجيل الأولى.
      </p>
      <Link to="/signup" className="mt-5 inline-block">
        <Button>إنشاء حساب جديد</Button>
      </Link>
    </div>
  );
}
