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
import { Preview } from "./ThemesSection";

export const CLASSIC_THEME_ID = "mizan";
export const STUDIO_URL = "/studio-preview.html";

interface ThemeItem { id: string; name: string; swatches: string[]; radius?: string; current: boolean }
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
  const card = "rounded-2xl border border-line bg-card p-4";
  const chip = (on: boolean) =>
    `rounded-xl border px-3 py-1.5 text-xs transition cursor-pointer ${on ? "border-primary bg-primary text-primary-foreground font-bold" : "border-line hover:border-primary/50"}`;

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_minmax(0,22rem)]" data-testid="owner-theme-picker">
      <div className="space-y-3">
        <section className={card} aria-label="القالب">
          <h3 className="mb-2 text-sm font-bold">١. القالب</h3>
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {themes.data.items.map((t) => (
              <li key={t.id}>
                <button type="button" aria-pressed={draft.theme === t.id} onClick={() => set({ theme: t.id })}
                        className={`w-full overflow-hidden rounded-xl border-2 text-xs ${draft.theme === t.id ? "border-primary ring-2 ring-primary/20" : "border-line"}`}>
                  <Preview swatches={t.swatches} radius={t.radius} />
                  <span className="flex items-center justify-between gap-1 p-2 font-semibold">
                    {t.name}{t.id === CLASSIC_THEME_ID && <span className="text-[10px] font-normal text-muted-foreground">الكلاسيكي</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className={card} aria-label="الألوان">
          <h3 className="mb-2 text-sm font-bold">٢. الألوان</h3>
          <div className="flex flex-wrap gap-2">
            <button type="button" aria-pressed={draft.palette === ""} onClick={() => set({ palette: "" })} className={chip(draft.palette === "")}>ألوان القالب</button>
            {palettes.data.items.map((p) => (
              <button key={p.id} type="button" title={p.id} aria-label={`لوحة ${p.id}`} aria-pressed={draft.palette === p.id}
                      onClick={() => set({ palette: p.id })}
                      className={`flex items-center gap-0.5 rounded-xl border px-2 py-1.5 ${draft.palette === p.id ? "border-primary ring-2 ring-primary/30" : "border-line"}`}>
                {p.swatches.slice(0, 3).map((c) => <span key={c} className="size-4 rounded-full border border-black/10" style={{ background: c }} />)}
              </button>
            ))}
          </div>
        </section>
        <section className={card} aria-label="الخط">
          <h3 className="mb-2 text-sm font-bold">٣. الخط</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {(["body", "display"] as const).map((which) => (
              <label key={which} className="block text-xs font-semibold">
                {which === "body" ? "خط النصوص" : "خط العناوين"}
                <select className="mt-1 w-full rounded-lg border border-line bg-card px-2 py-1.5 text-xs font-normal"
                        value={draft[which]} onChange={(e) => set({ [which]: e.target.value } as Partial<Draft>)}>
                  <option value="">خط القالب</option>
                  {families.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              </label>
            ))}
          </div>
        </section>
        <section className={card} aria-label="شكل القوائم">
          <h3 className="mb-1 text-sm font-bold">٤. شكل القوائم</h3>
          <p className="mb-2 text-[11px] text-muted-foreground">يُحفظ على هذا الجهاز فقط، ولا يغيّر ما يراه الآخرون.</p>
          <div className="flex flex-wrap gap-2">
            {LAYOUT_MODES.map((l) => (
              <button key={l.id} type="button" aria-pressed={layoutMode === l.id} onClick={() => setLayoutMode(l.id)} className={chip(layoutMode === l.id)}>
                {layoutMode === l.id && <Check className="me-1 inline size-3" />}{l.name.replace(/\s*\(.*\)$/, "")}
              </button>
            ))}
          </div>
        </section>
      </div>
      <aside className={`${card} h-fit space-y-3 lg:sticky lg:top-4`} aria-label="معاينة">
        <p className="text-xs text-muted-foreground">معاينة حيّة. لا تُحفظ حتى تضغط «حفظ المظهر».</p>
        <div className="overflow-hidden rounded-xl border border-line"><Preview swatches={view.swatches} radius={view.radius} /></div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}>
            {save.isPending ? <Spinner /> : dirty ? "حفظ المظهر" : "تم الحفظ"}
          </Button>
          <Button variant="outline" disabled={save.isPending || (isClassic && !dirty)} onClick={() => { setDraft(CLASSIC_DRAFT); save.mutate(CLASSIC_DRAFT); }}>
            <RotateCcw /> رجوع إلى الكلاسيكي
          </Button>
        </div>
        <div className="border-t border-line pt-3">
          <p className="mb-2 text-[11px] text-muted-foreground">لتعديل أكثر: تصميم الصفحات والأقسام والكتل.</p>
          <Button variant="outline" onClick={() => window.open(STUDIO_URL, "_blank", "noopener,noreferrer")}>
            <ExternalLink /> تعديل أكثر في الاستوديو
          </Button>
        </div>
      </aside>
    </div>
  );
}
