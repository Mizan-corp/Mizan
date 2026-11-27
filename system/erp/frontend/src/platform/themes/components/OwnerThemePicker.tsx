/**
 * The owner's simple appearance picker (Settings > المظهر). Four choices, a live preview,
 * one Save. It only offers what Mizan ships (themes, palettes, font families), through the
 * same `/themes` API the module centre uses. Classic ("mizan") is the default and one click
 * brings it back. Anything deeper (page design, blocks) lives in Studio.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, Palette, RotateCcw, Type, LayoutPanelLeft, Sparkles } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { useUiStore, LAYOUT_MODES } from "@/stores/ui";
import type { ThemePack } from "@/lib/theme";
import { Button, Spinner, useToast } from "@/components/ui";

/** A small but real-looking app screen in a theme's colours: menu, top bar, stat cards, chart, button. */
export function MiniApp({ swatches, radius = "0.875rem", big = false, shell = "sidebar" }: { swatches: string[]; radius?: string; big?: boolean; shell?: string }) {
  const [primary = "#651E2C", background = "#FAF6F0", sidebar = "#35151D", accent = "#E7D6C1", card = "#FFFFFF"] = swatches;
  const r = `calc(${radius} * 0.5)`;
  const menu = (
    <div className={shell === "topnav" ? "flex items-center gap-1.5 px-2.5 py-1.5" : `flex ${shell === "rail" ? "w-[12%] items-center" : "w-[24%]"} flex-col gap-1.5 p-2`} style={{ background: sidebar }}>
      <div className="size-2.5 rounded-sm" style={{ background: primary, filter: "brightness(1.6)" }} />
      {[0, 1, 2, 3].slice(0, big ? 4 : 3).map((i) => (
        <div key={i} className={`h-1.5 rounded-full ${shell === "rail" ? "w-2.5" : shell === "topnav" ? "w-8" : "w-full"}`} style={{ background: card, opacity: i === 0 ? 0.85 : 0.3 }} />
      ))}
    </div>
  );
  return (
    <div aria-hidden className={`flex overflow-hidden ${shell === "topnav" ? "flex-col" : ""} ${big ? "h-56" : "h-36"}`} style={{ background }}>
      {menu}
      <div className="flex-1 space-y-1.5 p-2.5">
        <div className="flex items-center justify-between">
          <div className="h-2 w-1/3 rounded-full" style={{ background: sidebar, opacity: 0.8 }} />
          <div className="size-3 rounded-full" style={{ background: accent }} />
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-1 p-1.5 shadow-sm" style={{ background: card, borderRadius: r }}>
              <div className="h-1 w-2/3 rounded-full" style={{ background: accent }} />
              <div className="h-2 w-1/2 rounded-full" style={{ background: i === 0 ? primary : sidebar, opacity: i === 0 ? 1 : 0.55 }} />
            </div>
          ))}
        </div>
        <div className="flex h-[34%] items-end gap-1 p-1.5 shadow-sm" style={{ background: card, borderRadius: r }}>
          {[40, 65, 50, 85, 60, 95, 70].map((h, i) => <div key={i} className="flex-1 rounded-sm" style={{ height: `${h}%`, background: i === 5 ? primary : accent }} />)}
        </div>
        <div className="h-3.5 w-14" style={{ background: primary, borderRadius: r }} />
      </div>
    </div>
  );
}

const SHELL_NAMES: Record<string, string> = { sidebar: "قائمة جانبية كاملة", rail: "شريط أيقونات", topnav: "قائمة علوية" };

function Step({ n, icon: Icon, title, hint, children }: { n: number; icon: typeof Palette; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-[#DECFC0] bg-white p-5 shadow-sm" aria-label={title}>
      <div className="mb-4 flex items-center gap-3">
        <span className="flex size-9 items-center justify-center rounded-xl bg-[#651E2C]/10 text-[#651E2C]"><Icon className="size-[18px]" /></span>
        <div>
          <h3 className="text-sm font-bold text-[#35151D]"><span className="text-[#651E2C]">{n}.</span> {title}</h3>
          {hint && <p className="text-[11px] text-[#77716E]">{hint}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

export const CLASSIC_THEME_ID = "mizan";
export const STUDIO_URL = "/studio-preview.html";

interface ThemeItem { id: string; name: string; description?: string; swatches: string[]; radius?: string; current: boolean }
interface PaletteItem { id: string; swatches: string[] }
export interface Draft { theme: string; palette: string; body: string; display: string }

/** The one request Save sends: theme, palette ("" = the theme's own) and fonts, in one call. */
export function savePayload(d: Draft) {
  const fonts: { body?: string; display?: string } = {};
  if (d.body) fonts.body = d.body;
  if (d.display) fonts.display = d.display;
  return { id: d.theme, palette: d.palette, fonts };
}

export const CLASSIC_DRAFT: Draft = { theme: CLASSIC_THEME_ID, palette: "", body: "", display: "" };

export function OwnerThemePicker() {
  const can = useAuth((s) => s.can);
  const tenant = useAuth((s) => s.tenant);
  const setTenant = useAuth((s) => s.setTenant);
  const manage = can("themes.manage");
  const { layoutMode, setLayoutMode } = useUiStore();
  const { toast } = useToast();
  const qc = useQueryClient();

  const themes = useQuery({ queryKey: ["themes"], queryFn: () => api.get<{ current: string; items: ThemeItem[] }>("/themes"), enabled: manage });
  const palettes = useQuery({
    queryKey: ["theme-palettes"],
    queryFn: () => api.get<{ items: PaletteItem[]; families: string[] }>("/themes/palettes"),
    enabled: manage,
  });
  const current = useQuery({ queryKey: ["themes", "current"], queryFn: () => api.get<ThemePack>("/themes/current"), enabled: manage });

  const saved: Draft | null = current.data
    ? { theme: current.data.id, palette: current.data.palette ?? "", body: current.data.fonts?.body ?? "", display: current.data.fonts?.display ?? "" }
    : null;
  const [draft, setDraft] = useState<Draft | null>(null);
  useEffect(() => { if (saved && !draft) setDraft(saved); }, [saved, draft]);

  const save = useMutation({
    mutationFn: (d: Draft) => api.put<ThemePack>("/themes/current", savePayload(d)),
    onSuccess: (t) => {
      if (tenant) setTenant({ ...tenant, theme: t, palette: { ...tenant.palette, name: t.id } });
      qc.invalidateQueries({ queryKey: ["themes"] });
      qc.invalidateQueries({ queryKey: ["theme-profiles"] });
      setDraft(null);
      toast("success", "حُفظ المظهر");
    },
    onError: (e) => toast("error", e instanceof ApiError ? e.message : "تعذر حفظ المظهر"),
  });

  const view = useMemo(() => {
    const th = themes.data?.items.find((t) => t.id === draft?.theme);
    const pl = palettes.data?.items.find((p) => p.id === draft?.palette);
    return { swatches: pl?.swatches ?? th?.swatches ?? [], radius: th?.radius };
  }, [themes.data, palettes.data, draft]);

  if (!manage) {
    return <p className="rounded-xl border border-line bg-card p-4 text-sm text-muted-foreground">اختيار المظهر متاح لمن يملك صلاحية «اختيار مظهر المنشأة».</p>;
  }
  if (!draft || !themes.data || !palettes.data) return <div className="flex justify-center p-10"><Spinner /></div>;

  const dirty = !saved || JSON.stringify(saved) !== JSON.stringify(draft);
  const isClassic = JSON.stringify(draft) === JSON.stringify(CLASSIC_DRAFT);
  const set = (p: Partial<Draft>) => setDraft({ ...draft, ...p });
  const families = palettes.data.families;
  const ring = (on: boolean) => (on ? "border-[#651E2C] ring-4 ring-[#651E2C]/15" : "border-[#DECFC0] hover:border-[#651E2C]/50");
  const tick = <span className="absolute end-2 top-2 flex size-5 items-center justify-center rounded-full bg-[#651E2C] text-white shadow"><Check className="size-3" /></span>;

  return (
    <div className="space-y-5" data-testid="owner-theme-picker">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#DECFC0] bg-[#FAF6F0] p-4">
        <div>
          <p className="text-sm font-bold text-[#35151D]">اختر شكل منشأتك</p>
          <p className="text-[11px] text-[#77716E]">كل الخيارات جاهزة ومعتمدة. التغييرات لا تُحفظ حتى تضغط «حفظ المظهر».</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={save.isPending || (isClassic && !dirty)} onClick={() => { setDraft(CLASSIC_DRAFT); save.mutate(CLASSIC_DRAFT); }}>
            <RotateCcw /> رجوع إلى الكلاسيكي
          </Button>
          <Button disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)} className="bg-[#651E2C] px-6 text-[#FAF6F0] hover:bg-[#521723]">
            {save.isPending ? <Spinner /> : dirty ? "حفظ المظهر" : "تم الحفظ"}
          </Button>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <div className="space-y-5">
          <Step n={1} icon={Sparkles} title="القالب" hint="الألوان والحواف والإحساس العام">
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {themes.data.items.map((t) => {
                const on = draft.theme === t.id;
                return (
                  <li key={t.id}>
                    <button type="button" aria-pressed={on} onClick={() => set({ theme: t.id })}
                            className={`relative block w-full overflow-hidden rounded-2xl border-2 bg-white text-start transition ${ring(on)}`}>
                      <MiniApp swatches={t.swatches} radius={t.radius} />
                      {on && tick}
                      <span className="block p-3">
                        <span className="flex items-center gap-2 text-sm font-bold text-[#35151D]">
                          {t.name}
                          {t.id === CLASSIC_THEME_ID && <span className="rounded-full bg-[#651E2C]/10 px-2 py-0.5 text-[10px] font-semibold text-[#651E2C]">الكلاسيكي</span>}
                        </span>
                        {t.description && <span className="mt-0.5 line-clamp-1 block text-[11px] font-normal text-[#77716E]">{t.description}</span>}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Step>
          <Step n={2} icon={Palette} title="الألوان" hint="غيّر الألوان فقط دون تغيير القالب">
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-4">
              <button type="button" aria-pressed={draft.palette === ""} onClick={() => set({ palette: "" })}
                      className={`relative rounded-xl border-2 bg-white p-3 text-start text-xs font-semibold transition ${ring(draft.palette === "")}`}>
                <span className="mb-2 flex h-6 overflow-hidden rounded-lg border border-black/5 bg-[repeating-linear-gradient(45deg,#f3ece2,#f3ece2_6px,#fff_6px,#fff_12px)]" />
                ألوان القالب
                {draft.palette === "" && tick}
              </button>
              {palettes.data.items.map((p) => (
                <button key={p.id} type="button" title={p.id} aria-label={`لوحة ${p.id}`} aria-pressed={draft.palette === p.id}
                        onClick={() => set({ palette: p.id })}
                        className={`relative rounded-xl border-2 bg-white p-3 text-start text-xs font-semibold transition ${ring(draft.palette === p.id)}`}>
                  <span className="mb-2 flex h-6 overflow-hidden rounded-lg border border-black/5">
                    {p.swatches.slice(0, 5).map((c) => <span key={c} className="flex-1" style={{ background: c }} />)}
                  </span>
                  <span className="block truncate" dir="ltr">{p.id}</span>
                  {draft.palette === p.id && tick}
                </button>
              ))}
            </div>
          </Step>
          <Step n={3} icon={Type} title="الخط" hint="خطوط معتمدة ومضمّنة فقط">
            <div className="grid gap-4 sm:grid-cols-2">
              {(["body", "display"] as const).map((which) => (
                <div key={which}>
                  <p className="mb-1.5 text-xs font-semibold text-[#35151D]">{which === "body" ? "خط النصوص" : "خط العناوين"}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {[{ id: "", label: "خط القالب" }, ...families.map((f) => ({ id: f, label: f }))].map((f) => (
                      <button key={f.id} type="button" aria-pressed={draft[which] === f.id} onClick={() => set({ [which]: f.id } as Partial<Draft>)}
                              style={f.id ? { fontFamily: `"${f.id}", sans-serif` } : undefined}
                              className={`rounded-xl border-2 px-3 py-2 text-xs transition ${ring(draft[which] === f.id)} ${draft[which] === f.id ? "bg-[#651E2C]/5 font-bold" : "bg-white"}`}>
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-3 rounded-xl bg-[#FAF6F0] p-3 text-sm text-[#35151D]" style={draft.body ? { fontFamily: `"${draft.body}", sans-serif` } : undefined}>
              مثال: فاتورة رقم 1042 · إجمالي 1,250.00 ج.م
            </p>
          </Step>
          <Step n={4} icon={LayoutPanelLeft} title="شكل القوائم" hint="يُحفظ على هذا الجهاز فقط ولا يغيّر ما يراه الآخرون">
            <div className="grid gap-3 sm:grid-cols-3">
              {LAYOUT_MODES.map((l) => {
                const on = layoutMode === l.id;
                return (
                  <button key={l.id} type="button" aria-pressed={on} onClick={() => setLayoutMode(l.id)}
                          className={`relative overflow-hidden rounded-2xl border-2 bg-white text-start transition ${ring(on)}`}>
                    <MiniApp swatches={view.swatches} radius={view.radius} shell={l.id} />
                    {on && tick}
                    <span className="block p-3 text-xs font-bold text-[#35151D]">{SHELL_NAMES[l.id] ?? l.name.replace(/\s*\(.*\)$/, "")}</span>
                  </button>
                );
              })}
            </div>
          </Step>
        </div>

        <aside className="h-fit space-y-4 lg:sticky lg:top-4" aria-label="معاينة">
          <div className="overflow-hidden rounded-2xl border border-[#DECFC0] bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-[#DECFC0] px-4 py-2.5">
              <span className="text-xs font-bold text-[#35151D]">معاينة حيّة</span>
              <span className="flex gap-1">{view.swatches.slice(0, 4).map((c) => <span key={c} className="size-3 rounded-full border border-black/10" style={{ background: c }} />)}</span>
            </div>
            <MiniApp swatches={view.swatches} radius={view.radius} big shell={layoutMode} />
          </div>
          <div className="rounded-2xl border border-dashed border-[#651E2C]/40 bg-[#651E2C]/5 p-4">
            <p className="text-sm font-bold text-[#35151D]">تريد تعديلاً أعمق؟</p>
            <p className="mb-3 mt-0.5 text-[11px] text-[#77716E]">صمّم الصفحات والأقسام والكتل بالسحب والإفلات في الاستوديو.</p>
            <Button variant="outline" className="w-full bg-white" onClick={() => window.open(STUDIO_URL, "_blank", "noopener,noreferrer")}>
              <ExternalLink /> تعديل أكثر في الاستوديو
            </Button>
          </div>
        </aside>
      </div>
    </div>
  );
}
