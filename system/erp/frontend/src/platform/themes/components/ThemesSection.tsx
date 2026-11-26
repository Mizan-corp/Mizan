/**
 * The module centre's themes (ADR-010 D3): the workspace's one theme, chosen by its admin from
 * Mizan's themes, the activity's, and signed theme packages installed from file.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, FileUp, Palette, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import type { ThemePack } from "@/lib/theme";
import { Badge, Button, ConfirmDialog, Modal, Spinner, useToast } from "@/components/ui";

interface ThemeSummary {
  id: string; name: string; name_en: string; description: string; version: string;
  source: "mizan" | "activity" | "package"; developer: string | null; activity: string | null;
  current: boolean; swatches: string[]; fonts: { body?: string; display?: string }; radius?: string; motion?: string;
}
interface Inspected extends ThemeSummary { installed_version: string | null; files: string[] }
interface RegistryPalette { id: string; source: string; license: string; swatches: string[] }
interface BrandingProfile { id: string; name: string; theme: string; palette: string | null; fonts: Record<string, string> }

const SOURCE: Record<ThemeSummary["source"], string> = { mizan: "من ميزان", activity: "من نشاطك", package: "من مطور" };

/** A small picture of the app in the theme's colours: sidebar, page, a card and the brand colour. */
export function Preview({ swatches, radius }: { swatches: string[]; radius?: string }) {
  const [primary, background, sidebar, accent, card] = swatches;
  const r = radius ?? "0.75rem";
  return (
    <div aria-hidden className="flex h-20 overflow-hidden border-b border-line" style={{ background }}>
      <div className="w-1/4" style={{ background: sidebar }}>
        <div className="mx-2 mt-3 h-1.5 rounded-full opacity-70" style={{ background: primary }} />
        <div className="mx-2 mt-1.5 h-1.5 rounded-full opacity-30" style={{ background: card }} />
      </div>
      <div className="flex-1 space-y-1.5 p-2.5">
        <div className="h-7 border border-black/5 p-1.5" style={{ background: card, borderRadius: `calc(${r} * 0.6)` }}>
          <div className="h-1.5 w-2/3 rounded-full" style={{ background: accent }} />
        </div>
        <div className="h-4 w-16" style={{ background: primary, borderRadius: `calc(${r} * 0.5)` }} />
      </div>
    </div>
  );
}

export function ThemesSection() {
  const can = useAuth((s) => s.can);
  const tenant = useAuth((s) => s.tenant);
  const setTenant = useAuth((s) => s.setTenant);
  const { toast } = useToast();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const section = useRef<HTMLElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [inspected, setInspected] = useState<Inspected | null>(null);
  const [removing, setRemoving] = useState<ThemeSummary | null>(null);
  const manage = can("themes.manage");

  const list = useQuery({
    queryKey: ["themes"],
    queryFn: () => api.get<{ current: string; items: ThemeSummary[] }>("/themes"),
    enabled: manage,
  });
  useEffect(() => {
    if (window.location.hash === "#themes" && list.isSuccess) section.current?.scrollIntoView({ block: "start" });
  }, [list.isSuccess]);

  const apply = (theme: ThemePack) => {
    if (tenant) setTenant({ ...tenant, theme, palette: { ...tenant.palette, name: theme.id } });
    qc.invalidateQueries({ queryKey: ["themes"] });
    qc.invalidateQueries({ queryKey: ["theme-profiles"] });
  };
  const fail = (e: unknown, fallback: string) => toast("error", e instanceof ApiError ? e.message : fallback);

  const choose = useMutation({
    mutationFn: (id: string) => api.put<ThemePack>("/themes/current", { id }),
    onSuccess: (t) => { apply(t); toast("success", `أصبح «${t.name}» مظهر المنشأة`); },
    onError: (e) => fail(e, "تعذر تغيير المظهر"),
  });
  const palettes = useQuery({
    queryKey: ["theme-palettes"],
    queryFn: () => api.get<{ items: RegistryPalette[]; families: string[] }>("/themes/palettes"),
    enabled: manage,
  });
  const currentTheme = useQuery({ queryKey: ["themes", "current"], queryFn: () => api.get<ThemePack>("/themes/current"), enabled: manage });
  const customize = useMutation({
    mutationFn: (patch: { palette?: string; fonts?: { body?: string; display?: string } }) =>
      api.put<ThemePack>("/themes/current", { id: currentTheme.data?.id, ...patch }),
    onSuccess: (t) => { apply(t); toast("success", "حُفظ التخصيص"); },
    onError: (e) => fail(e, "تعذر حفظ التخصيص"),
  });

  // The workspace's branding profiles: every theme edit auto-saves one, plus named
  // saves below. Workspace-scoped - the same behavior on cloud, desktop and LAN.
  const profiles = useQuery({
    queryKey: ["theme-profiles"],
    queryFn: () => api.get<{ items: BrandingProfile[] }>("/themes/profiles"),
    enabled: manage,
  });
  const [profileName, setProfileName] = useState("");
  const applyProfile = useMutation({
    mutationFn: (id: string) => api.post<ThemePack>(`/themes/profiles/${id}/apply`),
    onSuccess: (t) => { apply(t); toast("success", "طُبّق ملف الهوية"); },
    onError: (e) => fail(e, "تعذر تطبيق ملف الهوية"),
  });
  const saveProfile = useMutation({
    mutationFn: (name: string) => api.post<BrandingProfile>("/themes/profiles", { name }),
    onSuccess: () => {
      setProfileName("");
      qc.invalidateQueries({ queryKey: ["theme-profiles"] });
      toast("success", "حُفظ ملف الهوية");
    },
    onError: (e) => fail(e, "تعذر حفظ ملف الهوية"),
  });
  const deleteProfile = useMutation({
    mutationFn: (id: string) => api.del(`/themes/profiles/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["theme-profiles"] });
      toast("success", "حُذف ملف الهوية");
    },
    onError: (e) => fail(e, "تعذر حذف ملف الهوية"),
  });

  const inspect = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData();
      form.append("file", f);
      return api.postForm<Inspected>("/themes/packages/inspect", form);
    },
    onSuccess: setInspected,
    onError: (e) => { setFile(null); fail(e, "تعذر قراءة الملف"); },
  });
  const install = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("file", file!);
      return api.postForm<ThemeSummary>("/themes/packages/install", form);
    },
    onSuccess: (t) => {
      toast("success", `ثُبّت «${t.name}»`);
      setInspected(null);
      setFile(null);
      qc.invalidateQueries({ queryKey: ["themes"] });
    },
    onError: (e) => fail(e, "تعذر التثبيت"),
  });
  const remove = useMutation({
    mutationFn: (t: ThemeSummary) => api.del(`/themes/${encodeURIComponent(t.id)}`),
    onSuccess: () => { toast("success", "أُزيل المظهر"); setRemoving(null); qc.invalidateQueries({ queryKey: ["themes"] }); },
    onError: (e) => fail(e, "تعذرت الإزالة"),
  });

  if (!manage) return null;
  const items = list.data?.items ?? [];

  return (
    <section ref={section} id="themes" className="flex scroll-mt-20 flex-col gap-3" aria-label="المظاهر">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-bold text-foreground"><Palette className="size-4 text-primary" /> المظاهر</h2>
          <p className="text-xs text-muted-foreground">مظهر واحد للمنشأة يراه كل من فيها، والمستندات المطبوعة كذلك: الألوان والخطوط والحواف والحركة.</p>
        </div>
        <input ref={input} type="file" accept=".mzm,application/zip" className="hidden"
               onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); inspect.mutate(f); } e.target.value = ""; }} />
        <Button size="sm" variant="outline" disabled={inspect.isPending} onClick={() => input.current?.click()}>
          {inspect.isPending ? <Spinner /> : <FileUp />} تثبيت مظهر من ملف
        </Button>
      </div>

      {list.isPending ? (
        <div className="flex justify-center p-8"><Spinner /></div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((t) => (
            <li key={t.id} className={`overflow-hidden rounded-xl border bg-card ${t.current ? "border-primary ring-1 ring-primary" : "border-line"}`}>
              <Preview swatches={t.swatches} radius={t.radius} />
              <div className="space-y-2 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-foreground">{t.name}</p>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {t.source === "package" && <>المطور <span className="code" dir="ltr">{t.developer}</span> · v{t.version}{t.fonts.body && " · "}</>}
                      {t.fonts.body && <>الخط {t.fonts.body}</>}
                    </p>
                  </div>
                  {t.current ? <Badge tone="brand"><Check className="size-3" /> الحالي</Badge> : <Badge>{SOURCE[t.source]}</Badge>}
                </div>
                {t.description && <p className="line-clamp-2 text-xs text-muted-foreground">{t.description}</p>}
                <div className="flex gap-1.5">
                  <Button size="sm" disabled={t.current || choose.isPending} onClick={() => choose.mutate(t.id)}>
                    {choose.isPending && choose.variables === t.id ? <Spinner /> : t.current ? "مستخدم الآن" : "استخدام"}
                  </Button>
                  {t.source === "package" && !t.current && (
                    <Button size="sm" variant="ghost" onClick={() => setRemoving(t)} aria-label={`إزالة ${t.name}`}><Trash2 /></Button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal open={!!inspected} onClose={() => { setInspected(null); setFile(null); }}
             title={inspected ? (inspected.installed_version ? `تحديث «${inspected.name}»` : `تثبيت «${inspected.name}»`) : ""}>
        {inspected && (
          <div className="space-y-4 text-sm">
            <div className="overflow-hidden rounded-lg border border-line"><Preview swatches={inspected.swatches} radius={inspected.radius} /></div>
            <p className="text-muted-foreground">
              <span className="code" dir="ltr">{inspected.id} v{inspected.version}</span> · المطور <span className="code" dir="ltr">{inspected.developer}</span>
              {inspected.installed_version && <> · المثبت الآن <span className="code" dir="ltr">v{inspected.installed_version}</span></>}
            </p>
            {inspected.description && <p>{inspected.description}</p>}
            <p className="text-xs text-muted-foreground">
              مظهر فقط: ألوان{inspected.fonts.body ? ` وخط «${inspected.fonts.body}»` : ""} وحركة {inspected.motion === "none" ? "متوقفة" : inspected.motion === "reduced" ? "مخففة" : "كاملة"}.
              لا يصل إلى أي من بيانات المنشأة. التثبيت لا يغيّر المظهر الحالي حتى تختاره.
            </p>
            <div className="flex gap-2">
              <Button disabled={install.isPending} onClick={() => install.mutate()}>
                {install.isPending ? <Spinner /> : inspected.installed_version ? "تحديث" : "تثبيت"}
              </Button>
              <Button variant="outline" onClick={() => { setInspected(null); setFile(null); }}>إلغاء</Button>
            </div>
          </div>
        )}
      </Modal>
      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing)}
        title="إزالة المظهر"
        message={`سيُزال «${removing?.name ?? ""}» من هذه المنشأة. يمكنك تثبيته من ملفه مرة أخرى.`}
        confirmLabel="إزالة"
      />
      {/* Independent customization: recolor the current theme with any registry palette,
          and pick body/display faces — each without switching themes (ADR-010 D3). */}
      {currentTheme.data && palettes.data && (
        <div className="rounded-xl border border-line bg-card p-3 space-y-3">
          <div>
            <p className="text-xs font-bold text-foreground">لوحة الألوان</p>
            <p className="text-[10px] text-muted-foreground">ألوان المظهر نفسه، أو لوحة مستقلة تُغيّر الألوان فقط</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => customize.mutate({ palette: "" })}
                aria-pressed={!currentTheme.data.palette}
                className={`rounded-lg border px-2.5 py-1.5 text-xs transition cursor-pointer ${!currentTheme.data.palette ? "border-primary bg-primary/[0.08] font-bold text-foreground ring-1 ring-primary" : "border-line text-muted-foreground hover:border-primary/40"}`}
              >
                ألوان المظهر
              </button>
              {palettes.data.items.map((pl) => {
                const sel = currentTheme.data.palette === pl.id;
                return (
                  <button
                    key={pl.id}
                    type="button"
                    title={`${pl.source} — ${pl.license}`}
                    onClick={() => customize.mutate({ palette: sel ? "" : pl.id })}
                    aria-pressed={sel}
                    className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition cursor-pointer ${sel ? "border-primary bg-primary/[0.08] font-bold text-foreground ring-1 ring-primary" : "border-line text-muted-foreground hover:border-primary/40"}`}
                  >
                    <span className="flex gap-0.5">
                      {pl.swatches.map((c) => <span key={c} className="size-3 rounded-full border border-black/10" style={{ background: c }} />)}
                    </span>
                    {pl.id}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {(["body", "display"] as const).map((which) => (
              <div key={which}>
                <label className="text-xs font-bold text-foreground block">{which === "body" ? "خط النصوص" : "خط العناوين"}</label>
                <select
                  className="mt-1 w-full rounded-lg border border-line bg-card px-2 py-1.5 text-xs"
                  value={currentTheme.data.fonts?.[which] ?? ""}
                  onChange={(e) => customize.mutate({ fonts: { ...currentTheme.data.fonts, [which]: e.target.value } })}
                >
                  {palettes.data.families.map((fam) => <option key={fam} value={fam}>{fam}</option>)}
                </select>
              </div>
            ))}
          </div>
          {customize.isPending && <Spinner />}
          {profiles.data && (
            <div>
              <p className="text-xs font-bold text-foreground">ملفات الهوية</p>
              <p className="text-[10px] text-muted-foreground">
                أي تعديل على المظهر يُحفظ هنا تلقائيًا كملف خاص بهذه المساحة (المظهر الأصلي لا يتغيّر). احفظ الحالي باسم، واختر ملفًا لتطبيقه.
              </p>
              <form
                className="mt-1.5 flex gap-1.5"
                onSubmit={(e) => {
                  e.preventDefault();
                  const n = profileName.trim();
                  if (n.length >= 2) saveProfile.mutate(n);
                }}
              >
                <input
                  className="min-w-0 flex-1 rounded-lg border border-line bg-card px-2 py-1.5 text-xs"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  placeholder="اسم الملف، مثل: هوية الفرع الجديد"
                  maxLength={80}
                />
                <Button size="sm" type="submit" disabled={profileName.trim().length < 2 || saveProfile.isPending}>
                  {saveProfile.isPending ? <Spinner /> : "احفظ الحالي"}
                </Button>
              </form>
              {profiles.data.items.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {profiles.data.items.map((p) => (
                    <span key={p.id} className="inline-flex items-center rounded-lg border border-line text-xs">
                      <button
                        type="button"
                        title={`${p.theme}${p.palette ? ` + ${p.palette}` : ""}`}
                        disabled={applyProfile.isPending}
                        onClick={() => applyProfile.mutate(p.id)}
                        className="px-2.5 py-1.5 text-muted-foreground transition cursor-pointer hover:text-foreground disabled:opacity-50"
                      >
                        {applyProfile.isPending && applyProfile.variables === p.id ? <Spinner /> : p.name}
                      </button>
                      <button
                        type="button"
                        aria-label={`حذف ${p.name}`}
                        disabled={deleteProfile.isPending}
                        onClick={() => deleteProfile.mutate(p.id)}
                        className="border-s border-line px-1.5 py-1.5 text-muted-foreground transition cursor-pointer hover:text-danger disabled:opacity-50"
                      >
                        {deleteProfile.isPending && deleteProfile.variables === p.id ? <Spinner /> : <Trash2 className="size-3" />}
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
