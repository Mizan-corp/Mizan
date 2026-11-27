/**
 * The owner's simple appearance picker (Settings > المظهر). Four choices, a live preview,
 * one Save. It only offers what Mizan ships (themes, palettes, font families), through the
 * same `/themes` API the module centre uses. Classic ("mizan") is the default and one click
 * brings it back. Anything deeper (page design, blocks) lives in Studio.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { useUiStore, LAYOUT_MODES } from "@/stores/ui";
import type { ThemePack } from "@/lib/theme";
import { Button, Spinner, useToast } from "@/components/ui";

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

type Tab = "theme" | "colors" | "font" | "menus";
const TABS: { id: Tab; label: string }[] = [
  { id: "theme", label: "القالب" }, { id: "colors", label: "الألوان" }, { id: "font", label: "الخط" }, { id: "menus", label: "القوائم" },
];
const SHELL_NAMES: Record<string, string> = { sidebar: "قائمة جانبية كاملة", rail: "شريط أيقونات", topnav: "قائمة علوية" };
const NAV = ["الرئيسية", "الكاشير", "الفواتير", "المخزون", "التقارير"];
const DISPLAY = "Almarai, Tajawal, sans-serif";

/** Template thumbnail: a small screen in the theme's colours (menu on the right, RTL). */
function Thumb({ swatches }: { swatches: string[] }) {
  const [primary = "#651E2C", background = "#FAF6F0", sidebar = "#35151D", , card = "#FFFFFF"] = swatches;
  return (
    <div aria-hidden className="flex h-[74px] overflow-hidden rounded-[11px]" style={{ background }}>
      <div className="flex-1 p-2">
        <div className="mb-1.5 h-2 w-[70%] rounded" style={{ background: sidebar }} />
        <div className="h-5 rounded-md opacity-80" style={{ background: card }}><div className="m-1.5 h-1.5 w-1/3 rounded" style={{ background: primary }} /></div>
      </div>
      <div className="w-[28%]" style={{ background: sidebar }} />
    </div>
  );
}

/** The live preview: the home screen (menu, greeting, stat cards with deltas, chart) in the chosen colours, menu shape and font. */
export function HomePreview({ swatches, radius = "0.875rem", shell = "sidebar", fontFamily }: { swatches: string[]; radius?: string; shell?: string; fontFamily?: string }) {
  const [primary = "#651E2C", background = "#FAF6F0", sidebar = "#35151D", accent = "#E7D6C1", card = "#FFFFFF"] = swatches;
  const r = `calc(${radius} * 1.15)`;
  const top = shell === "topnav";
  const rail = shell === "rail";
  const stats = [["مبيعات اليوم", "12,480", "8.4%"], ["الفواتير", "186", "3.1%"], ["الأرباح", "3,920", "5.7%"]];
  return (
    <div aria-hidden className={`flex h-full w-full ${top ? "flex-col" : ""}`} style={{ background, fontFamily }}>
      <div className={top ? "flex items-center gap-5 px-6 py-3.5" : `${rail ? "w-[72px] px-3" : "w-[210px] px-4"} py-[22px]`} style={{ background: sidebar, color: card }}>
        <div className={`flex items-center gap-2.5 font-bold ${top ? "" : "mb-[22px]"} ${rail ? "justify-center" : ""}`} style={{ fontFamily: DISPLAY }}>
          <span className="size-[26px] shrink-0 rounded-lg" style={{ background: primary }} />{!rail && <span className="text-[15px]">متجر ميزان</span>}
        </div>
        <div className={top ? "flex gap-1" : "space-y-1"}>
          {NAV.map((n, i) => (
            <div key={n} className={`rounded-[10px] text-[13px] ${rail ? "flex size-10 items-center justify-center" : "px-3 py-2.5"} ${i === 0 ? "" : "opacity-75"}`}
                 style={i === 0 ? { background: primary, color: "#fff" } : undefined}>
              {rail ? <span className="size-2 rounded-sm bg-current" /> : n}
            </div>
          ))}
        </div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col px-7 py-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-[22px] font-bold" style={{ color: sidebar, fontFamily: DISPLAY }}>صباح الخير، أحمد</h2>
          <span className="size-[34px] rounded-full" style={{ background: accent }} />
        </div>
        <div className="mb-4 grid grid-cols-3 gap-3.5">
          {stats.map(([l, v, d]) => (
            <div key={l} className="p-4 shadow-[0_2px_10px_rgba(53,21,29,0.05)]" style={{ background: card, borderRadius: r }}>
              <small className="text-xs opacity-60" style={{ color: sidebar }}>{l}</small>
              <b className="mt-1.5 block text-[26px] leading-tight" style={{ color: sidebar, fontFamily: DISPLAY }}>{v}</b>
              <span className="text-xs text-[#27835C]">▲ {d}</span>
            </div>
          ))}
        </div>
        <div className="flex h-[230px] flex-none items-end gap-3.5 p-[18px] shadow-[0_2px_10px_rgba(53,21,29,0.05)]" style={{ background: card, borderRadius: r }}>
          {[40, 62, 50, 80, 95, 66, 72, 45, 84, 58].map((h, i) => <i key={i} className="block flex-1 rounded-t-lg rounded-b-[3px]" style={{ height: `${h}%`, background: i === 4 ? primary : accent }} />)}
        </div>
      </div>
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="mb-2.5 text-xs font-bold tracking-[0.2px] text-[#9A8C86]">{children}</p>;
}

export function OwnerThemePicker() {
  const can = useAuth((s) => s.can);
  const tenant = useAuth((s) => s.tenant);
  const setTenant = useAuth((s) => s.setTenant);
  const manage = can("themes.manage");
  const { layoutMode, setLayoutMode } = useUiStore();
  const { toast } = useToast();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("theme");
  const refs = useRef<Record<Tab, HTMLElement | null>>({ theme: null, colors: null, font: null, menus: null });
  const go = (t: Tab) => { setTab(t); refs.current[t]?.scrollIntoView({ behavior: "smooth", block: "start" }); };

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
    return { swatches: pl?.swatches ?? th?.swatches ?? [], radius: th?.radius, name: th?.name ?? "" };
  }, [themes.data, palettes.data, draft]);

  if (!manage) {
    return <p className="rounded-xl border border-line bg-card p-4 text-sm text-muted-foreground">اختيار المظهر متاح لمن يملك صلاحية «اختيار مظهر المنشأة».</p>;
  }
  if (!draft || !themes.data || !palettes.data) return <div className="flex justify-center p-10"><Spinner /></div>;

  const dirty = !saved || JSON.stringify(saved) !== JSON.stringify(draft);
  const isClassic = JSON.stringify(draft) === JSON.stringify(CLASSIC_DRAFT);
  const set = (p: Partial<Draft>) => setDraft({ ...draft, ...p });
  const fam = (f: string) => (f ? { fontFamily: `"${f}", sans-serif` } : undefined);
  const section = (id: Tab) => ({ ref: (el: HTMLElement | null) => { refs.current[id] = el; }, className: "mb-6 scroll-mt-1" });

  return (
    <div className="grid h-[calc(100vh-7rem)] min-h-[700px] overflow-hidden rounded-[22px] border border-[#E7DCCF] bg-[#EFE8DE] lg:grid-cols-[420px_1fr]" data-testid="owner-theme-picker">
      <div className="flex min-h-0 flex-col bg-white shadow-[-1px_0_0_#E7DCCF]">
        <div className="min-h-0 flex-1 overflow-y-auto px-7 pt-7">
          <p className="mb-1.5 text-xs text-[#9A8C86]">الإعدادات ‹ المظهر</p>
          <h1 className="mb-[22px] text-[26px] font-bold text-[#35151D]" style={{ fontFamily: DISPLAY }}>مظهر المتجر</h1>
          <div role="tablist" className="sticky top-0 z-10 mb-[22px] flex rounded-[14px] bg-[#F3ECE3] p-1">
            {TABS.map((t) => (
              <button key={t.id} role="tab" type="button" aria-selected={tab === t.id} onClick={() => go(t.id)}
                      className={`flex-1 rounded-[11px] py-2.5 text-[13px] font-bold transition ${tab === t.id ? "bg-white text-[#651E2C] shadow-[0_2px_8px_rgba(53,21,29,0.08)]" : "text-[#8A7A74]"}`}>
                {t.label}
              </button>
            ))}
          </div>

          <section {...section("theme")} aria-label="القوالب">
            <Label>القوالب</Label>
            <ul className="grid grid-cols-2 gap-3">
              {themes.data.items.map((t) => {
                const on = draft.theme === t.id;
                return (
                  <li key={t.id}>
                    <button type="button" aria-pressed={on} onClick={() => set({ theme: t.id })}
                            className={`w-full rounded-2xl border-2 p-1.5 text-start transition ${on ? "border-[#651E2C] bg-white shadow-[0_8px_22px_rgba(101,30,44,0.13)]" : "border-transparent bg-[#FAF6F0] hover:border-[#651E2C]/30"}`}>
                      <Thumb swatches={t.swatches} />
                      <span className="flex items-center justify-between px-1.5 pb-1 pt-2 text-[13px] font-bold text-[#35151D]">
                        {t.name}
                        {t.id === CLASSIC_THEME_ID && <em className="rounded-full bg-[#651E2C] px-2 py-0.5 text-[10px] font-bold not-italic text-white">الكلاسيكي</em>}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>

          <section {...section("colors")} aria-label="الألوان">
            <Label>الألوان</Label>
            <div className="flex flex-wrap gap-2.5">
              <button type="button" aria-pressed={draft.palette === ""} onClick={() => set({ palette: "" })}
                      className={`rounded-full px-4 text-xs font-bold ${draft.palette === "" ? "bg-[#651E2C] text-white" : "bg-[#F3ECE3] text-[#651E2C]"}`}>ألوان القالب</button>
              {palettes.data.items.map((p) => (
                <button key={p.id} type="button" title={p.id} aria-label={`لوحة ${p.id}`} aria-pressed={draft.palette === p.id} onClick={() => set({ palette: p.id })}
                        className={`size-[38px] rounded-full shadow-[inset_0_0_0_3px_#fff,0_0_0_1px_#E1D6C9] ${draft.palette === p.id ? "!shadow-[inset_0_0_0_3px_#fff,0_0_0_3px_#651E2C]" : ""}`}
                        style={{ background: p.swatches[0] }} />
              ))}
            </div>
          </section>

          <section {...section("font")} aria-label="الخط">
            {(["body", "display"] as const).map((which) => (
              <div key={which} className="mb-5">
                <Label>{which === "body" ? "خط النصوص" : "خط العناوين"}</Label>
                <div className="grid grid-cols-2 gap-2.5">
                  {[{ id: "", label: "خط القالب" }, ...palettes.data.families.map((f) => ({ id: f, label: f }))].map((f) => (
                    <button key={f.id} type="button" aria-pressed={draft[which] === f.id} onClick={() => set({ [which]: f.id } as Partial<Draft>)}
                            className={`rounded-[14px] border-[1.5px] p-3 text-center transition ${draft[which] === f.id ? "border-[#651E2C] bg-[#FBF3F4]" : "border-[#EADFD2]"}`}>
                      <b className="mb-0.5 block text-[22px]" style={fam(f.id)}>أبجد</b>
                      <small className="text-[11px] text-[#9A8C86]">{f.label}</small>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </section>

          <section {...section("menus")} aria-label="شكل القوائم">
            <Label>شكل القوائم</Label>
            <div className="grid grid-cols-3 gap-2.5">
              {LAYOUT_MODES.map((l) => (
                <button key={l.id} type="button" aria-pressed={layoutMode === l.id} onClick={() => setLayoutMode(l.id)}
                        className={`rounded-[14px] border-[1.5px] p-3 text-center text-xs font-bold transition ${layoutMode === l.id ? "border-[#651E2C] bg-[#FBF3F4] text-[#651E2C]" : "border-[#EADFD2] text-[#35151D]"}`}>
                  {SHELL_NAMES[l.id] ?? l.name.replace(/\s*\(.*\)$/, "")}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-[#9A8C86]">يُحفظ على هذا الجهاز فقط ولا يغيّر ما يراه الآخرون.</p>
          </section>
          <div className="h-4" />
        </div>
        <div className="flex gap-2.5 border-t border-[#EADFD2] bg-white px-7 py-4">
          <Button variant="outline" className="h-auto flex-[0.8] rounded-[13px] bg-[#F3ECE3] py-[13px] text-sm font-bold text-[#651E2C]" disabled={save.isPending || (isClassic && !dirty)}
                  onClick={() => { setDraft(CLASSIC_DRAFT); save.mutate(CLASSIC_DRAFT); }}>
            <RotateCcw /> رجوع إلى الكلاسيكي
          </Button>
          <Button className="h-auto flex-1 rounded-[13px] bg-[#651E2C] py-[13px] text-sm font-bold text-white shadow-[0_6px_16px_rgba(101,30,44,0.27)] hover:bg-[#521723]" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}>
            {save.isPending ? <Spinner /> : dirty ? "حفظ المظهر" : "تم الحفظ"}
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-col px-11 py-[34px]">
        <div className="mb-[18px] flex items-center justify-between">
          <span className="text-[13px] text-[#8A7A74]">معاينة مباشرة بصفحة «الرئيسية»</span>
          <button type="button" onClick={() => window.open(STUDIO_URL, "_blank", "noopener,noreferrer")}
                  className="rounded-full bg-white px-4 py-2 text-xs font-bold text-[#651E2C] shadow-[0_2px_8px_rgba(53,21,29,0.06)]">
            تعديل أكثر في الاستوديو ↗
          </button>
        </div>
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-[26px] border border-[#EADFD2] bg-white shadow-[0_30px_70px_rgba(53,21,29,0.15)]">
          <HomePreview swatches={view.swatches} radius={view.radius} shell={layoutMode} fontFamily={draft.body ? `"${draft.body}", sans-serif` : undefined} />
          <span className="absolute bottom-[22px] end-[22px] rounded-full bg-[#35151D]/90 px-4 py-[9px] text-xs text-white">
            {view.name}{draft.palette ? ` · ${draft.palette}` : ""}{draft.body ? ` · ${draft.body}` : ""}
          </span>
        </div>
      </div>
    </div>
  );
}
