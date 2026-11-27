/**
 * The owner's simple appearance picker (Settings > المظهر). Four choices, a live preview,
 * one Save. It only offers what Mizan ships (themes, palettes, font families), through the
 * same `/themes` API the module centre uses. Classic ("mizan") is the default and one click
 * brings it back. Anything deeper (page design, blocks) lives in Studio.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, RotateCcw } from "lucide-react";
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

/** Small template thumbnail: a screen in the theme's colours. */
function Thumb({ swatches }: { swatches: string[] }) {
  const [primary = "#651E2C", background = "#FAF6F0", sidebar = "#35151D", , card = "#FFFFFF"] = swatches;
  return (
    <div aria-hidden className="flex h-[74px] overflow-hidden rounded-[11px]" style={{ background }}>
      <div className="flex-1 space-y-1.5 p-2">
        <div className="h-2 w-2/3 rounded" style={{ background: sidebar }} />
        <div className="h-5 rounded-md" style={{ background: card }}><div className="m-1.5 h-1.5 w-1/3 rounded" style={{ background: primary }} /></div>
      </div>
      <div className="w-[28%]" style={{ background: sidebar }} />
    </div>
  );
}

/** The big live preview: the real home screen's structure in the chosen colours and menu shape. */
export function HomePreview({ swatches, radius = "0.875rem", shell = "sidebar", fontFamily }: { swatches: string[]; radius?: string; shell?: string; fontFamily?: string }) {
  const [primary = "#651E2C", background = "#FAF6F0", sidebar = "#35151D", accent = "#E7D6C1", card = "#FFFFFF"] = swatches;
  const r = `calc(${radius} * 1.1)`;
  const top = shell === "topnav";
  const rail = shell === "rail";
  const menu = (
    <div className={top ? "flex items-center gap-4 px-5 py-3" : `flex flex-col gap-1 ${rail ? "w-16 items-center px-2" : "w-[200px] px-3.5"} py-5`}
         style={{ background: sidebar, color: card }}>
      <div className={`flex items-center gap-2.5 ${top ? "" : "mb-5"} ${rail ? "justify-center" : ""} font-bold`}>
        <span className="size-6 rounded-lg" style={{ background: primary, filter: "brightness(1.35)" }} />{!rail && <span className="text-sm">متجر ميزان</span>}
      </div>
      {NAV.map((n, i) => (
        <div key={n} className={`${rail ? "size-8" : top ? "px-3 py-1.5" : "px-3 py-2.5"} flex items-center justify-center rounded-[10px] text-xs ${i === 0 ? "font-bold" : "opacity-70"}`}
             style={i === 0 ? { background: primary, color: "#fff" } : undefined}>
          {rail ? <span className="size-2 rounded-sm bg-current" /> : n}
        </div>
      ))}
    </div>
  );
  return (
    <div aria-hidden className={`flex h-full min-h-[430px] overflow-hidden ${top ? "flex-col" : ""}`} style={{ background, fontFamily }}>
      {menu}
      <div className="flex-1 space-y-4 p-6">
        <div className="flex items-center justify-between">
          <h4 className="text-xl font-bold" style={{ color: sidebar }}>صباح الخير، أحمد</h4>
          <span className="size-8 rounded-full" style={{ background: accent }} />
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[["مبيعات اليوم", "12,480"], ["الفواتير", "186"], ["الأرباح", "3,920"]].map(([l, v], i) => (
            <div key={l} className="p-3.5 shadow-sm" style={{ background: card, borderRadius: r }}>
              <p className="text-[11px] opacity-60" style={{ color: sidebar }}>{l}</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: i === 0 ? primary : sidebar }}>{v}</p>
            </div>
          ))}
        </div>
        <div className="flex h-44 items-end gap-3 p-4 shadow-sm" style={{ background: card, borderRadius: r }}>
          {[40, 62, 50, 80, 95, 66, 72, 45, 84, 58].map((h, i) => <div key={i} className="flex-1 rounded-t-md" style={{ height: `${h}%`, background: i === 4 ? primary : accent }} />)}
        </div>
        <span className="inline-block px-5 py-2 text-xs font-bold" style={{ background: primary, color: "#fff", borderRadius: r }}>إتمام البيع</span>
      </div>
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="mb-2.5 text-xs font-bold text-[#9A8C86]">{children}</p>;
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
  const pick = (on: boolean) => (on ? "border-[#651E2C] bg-[#FBF3F4]" : "border-[#EADFD2] hover:border-[#651E2C]/40");

  return (
    <div className="grid gap-0 overflow-hidden rounded-3xl border border-[#DECFC0] bg-white shadow-sm lg:grid-cols-[22rem_1fr]" data-testid="owner-theme-picker">
      <div className="flex min-h-[640px] flex-col">
        <div className="flex-1 p-6">
          <div role="tablist" className="mb-6 flex rounded-2xl bg-[#F3ECE3] p-1">
            {TABS.map((t) => (
              <button key={t.id} role="tab" type="button" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
                      className={`flex-1 rounded-xl py-2.5 text-xs font-bold transition ${tab === t.id ? "bg-white text-[#651E2C] shadow-sm" : "text-[#8A7A74]"}`}>
                {t.label}
              </button>
            ))}
          </div>

          {tab === "theme" && (
            <div>
              <Label>القوالب</Label>
              <ul className="grid grid-cols-2 gap-3">
                {themes.data.items.map((t) => {
                  const on = draft.theme === t.id;
                  return (
                    <li key={t.id}>
                      <button type="button" aria-pressed={on} onClick={() => set({ theme: t.id })}
                              className={`w-full rounded-2xl border-2 p-1.5 text-start transition ${on ? "border-[#651E2C] bg-white shadow-lg shadow-[#651E2C]/15" : "border-transparent bg-[#FAF6F0] hover:border-[#651E2C]/30"}`}>
                        <Thumb swatches={t.swatches} />
                        <span className="flex items-center justify-between gap-1 px-1.5 pb-1 pt-2 text-[13px] font-bold text-[#35151D]">
                          {t.name}
                          {t.id === CLASSIC_THEME_ID && <em className="rounded-full bg-[#651E2C] px-2 py-0.5 text-[10px] font-bold not-italic text-white">الكلاسيكي</em>}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {tab === "colors" && (
            <div>
              <Label>الألوان</Label>
              <p className="mb-4 text-[11px] text-[#9A8C86]">غيّر الألوان فقط دون تغيير القالب.</p>
              <div className="flex flex-wrap gap-3">
                <button type="button" aria-pressed={draft.palette === ""} onClick={() => set({ palette: "" })}
                        className={`rounded-full border-2 px-4 py-2 text-xs font-bold ${pick(draft.palette === "")}`}>ألوان القالب</button>
                {palettes.data.items.map((p) => (
                  <button key={p.id} type="button" title={p.id} aria-label={`لوحة ${p.id}`} aria-pressed={draft.palette === p.id} onClick={() => set({ palette: p.id })}
                          className={`size-11 rounded-full ring-offset-2 transition ${draft.palette === p.id ? "ring-[3px] ring-[#651E2C]" : "ring-1 ring-[#E1D6C9]"}`}
                          style={{ background: `linear-gradient(135deg, ${p.swatches[0]} 55%, ${p.swatches[2] ?? p.swatches[1]} 55%)` }} />
                ))}
              </div>
            </div>
          )}

          {tab === "font" && (
            <div className="space-y-6">
              {(["body", "display"] as const).map((which) => (
                <div key={which}>
                  <Label>{which === "body" ? "خط النصوص" : "خط العناوين"}</Label>
                  <div className="grid grid-cols-2 gap-2.5">
                    {[{ id: "", label: "خط القالب" }, ...palettes.data.families.map((f) => ({ id: f, label: f }))].map((f) => (
                      <button key={f.id} type="button" aria-pressed={draft[which] === f.id} onClick={() => set({ [which]: f.id } as Partial<Draft>)}
                              className={`rounded-2xl border-[1.5px] p-3 text-center transition ${pick(draft[which] === f.id)}`}>
                        <b className="block text-2xl" style={fam(f.id)}>أبجد</b>
                        <small className="text-[11px] text-[#9A8C86]">{f.label}</small>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "menus" && (
            <div>
              <Label>شكل القوائم</Label>
              <p className="mb-4 text-[11px] text-[#9A8C86]">يُحفظ على هذا الجهاز فقط ولا يغيّر ما يراه الآخرون.</p>
              <div className="space-y-2.5">
                {LAYOUT_MODES.map((l) => (
                  <button key={l.id} type="button" aria-pressed={layoutMode === l.id} onClick={() => setLayoutMode(l.id)}
                          className={`flex w-full items-center justify-between rounded-2xl border-[1.5px] p-4 text-start text-sm font-bold transition ${pick(layoutMode === l.id)}`}>
                    {SHELL_NAMES[l.id] ?? l.name.replace(/\s*\(.*\)$/, "")}
                    {layoutMode === l.id && <Check className="size-4 text-[#651E2C]" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="flex gap-2.5 border-t border-[#EADFD2] bg-white p-5">
          <Button variant="outline" className="flex-[0.8]" disabled={save.isPending || (isClassic && !dirty)} onClick={() => { setDraft(CLASSIC_DRAFT); save.mutate(CLASSIC_DRAFT); }}>
            <RotateCcw /> رجوع إلى الكلاسيكي
          </Button>
          <Button className="flex-1 bg-[#651E2C] text-[#FAF6F0] shadow-lg shadow-[#651E2C]/30 hover:bg-[#521723]" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}>
            {save.isPending ? <Spinner /> : dirty ? "حفظ المظهر" : "تم الحفظ"}
          </Button>
        </div>
      </div>

      <div className="flex flex-col bg-[#EFE8DE] p-6">
        <div className="mb-4 flex items-center justify-between">
          <span className="text-xs text-[#8A7A74]">معاينة مباشرة بصفحة «الرئيسية». لا يُحفظ شيء قبل الضغط على «حفظ المظهر».</span>
          <button type="button" onClick={() => window.open(STUDIO_URL, "_blank", "noopener,noreferrer")}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-white px-4 py-2 text-xs font-bold text-[#651E2C] shadow-sm hover:shadow">
            <ExternalLink className="size-3.5" /> تعديل أكثر في الاستوديو
          </button>
        </div>
        <div className="relative flex-1 overflow-hidden rounded-3xl border border-[#EADFD2] bg-white shadow-2xl shadow-[#35151D]/20">
          <HomePreview swatches={view.swatches} radius={view.radius} shell={layoutMode} fontFamily={draft.body ? `"${draft.body}", sans-serif` : undefined} />
          <span className="absolute bottom-4 end-4 rounded-full bg-[#35151D]/90 px-4 py-2 text-xs text-white">
            {view.name}{draft.palette ? ` · ${draft.palette}` : ""}{draft.body ? ` · ${draft.body}` : ""}
          </span>
        </div>
      </div>
    </div>
  );
}
