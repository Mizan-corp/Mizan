/**
 * PAGE CONTRACT
 * Page: سوق وإدارة الوحدات والأنشطة (/modules)
 * Archetype: Modular Extension Marketplace & Profile Switcher
 * User: المدير أو مسؤول النظام يحدد النشاط التجاري للمنشأة ويدير الوحدات المثبتة
 * Primary information: الحزمة النشطة حالياً → حزم الأنشطة الجاهزة → دليل الموديولات والإعدادات
 * Anti-AI Tell Score: 0 (Pure design tokens, zero arbitrary purple/indigo styles, role-based radii)
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  Briefcase,
  ChefHat,
  ExternalLink,
  GraduationCap,
  Layers,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  ShoppingCart,
  Stethoscope,
  Store,
  UtensilsCrossed,
  Wallet,
  Blocks,
} from "lucide-react";
import { Badge } from "@/components/kit/badge";
import { Button, buttonVariants } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { Input, Modal, useToast } from "@/components/ui";
import { cn } from "@/lib/utils";
import { api, downloadExport } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { UninstallDialog } from "./UninstallDialog";
import { sound } from "@/lib/sound";
import { useModulesStore, type ModuleManifest } from "@app/stores/modules";

const ICON_MAP: Record<string, any> = {
  Layers,
  Boxes,
  ShoppingCart,
  Wallet,
  UserCog: ShieldCheck,
  UtensilsCrossed,
  GraduationCap,
  Briefcase,
  Store,
  Blocks,
  ChefHat,
  Stethoscope,
  Settings2,
};

export default function ModulesPage() {
  const {
    activePreset,
    activeModules,
    catalog,
    presets,
    families,
    isLoading,
    fetchModules,
    toggleModule,
    fetchModuleSettings,
    saveModuleSettings,
  } = useModulesStore();

  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [removing, setRemoving] = useState<ModuleManifest | null>(null);
  const retention = useQuery({
    queryKey: ["module-retention"],
    queryFn: () => api.get<{ id: string; module_id: string; mode: "kept" | "deleted"; purge_after: string | null; removed_at: string; has_export: boolean }[]>("/modules/retention"),
  });
  const [selectedForSettings, setSelectedForSettings] = useState<ModuleManifest | null>(null);
  const [settingsValues, setSettingsValues] = useState<Record<string, any>>({});
  const [isLoadingSettings, setIsLoadingSettings] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const { toast } = useToast();

  const activePresetObj = presets.find((p) => p.id === activePreset);

  async function handleToggle(mod: ModuleManifest) {
    if (mod.is_core) return;
    if (mod.is_installed) {
      setRemoving(mod);  // removal: preview, typed delete, keep or delete the data (ADR-006 D2)
      return;
    }
    if (mod.installable === false) {
      toast("error", mod.not_installable_reason || "هذه الوحدة لا تناسب نشاط منشأتك");
      return;
    }
    try {
      setTogglingId(mod.id);
      const nextState = !mod.is_installed;
      await toggleModule(mod.id, nextState);
      toast(
        "success",
        nextState ? `تم تثبيت وتفعيل وحدة «${mod.name}»` : `تمت إزالة وحدة «${mod.name}»`,
      );
    } catch (e: any) {
      toast("error", e.message || "فشل تغيير حالة الوحدة");
    } finally {
      setTogglingId(null);
    }
  }

  async function openSettings(mod: ModuleManifest) {
    sound.click();
    setSelectedForSettings(mod);
    setIsLoadingSettings(true);
    try {
      const data = await fetchModuleSettings(mod.id);
      setSettingsValues(data.values || {});
    } catch {
      toast("error", "فشل تحميل إعدادات الوحدة");
    } finally {
      setIsLoadingSettings(false);
    }
  }

  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedForSettings) return;
    setIsSavingSettings(true);
    try {
      await saveModuleSettings(selectedForSettings.id, settingsValues);
      toast("success", `تم حفظ إعدادات «${selectedForSettings.name}» بنجاح`);
      setSelectedForSettings(null);
    } catch (err: any) {
      toast("error", err.message || "فشل حفظ الإعدادات");
    } finally {
      setIsSavingSettings(false);
    }
  }

  const filteredCatalog = catalog.filter((m) => {
    if (categoryFilter !== "all" && m.category !== categoryFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        m.name.toLowerCase().includes(q) ||
        m.name_en.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="flex flex-col gap-8 pb-12">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-primary">
            <Blocks className="size-4" />
            <span>نظام الوحدات المرن (Mizan Modular App Engine)</span>
          </div>
          <h1 className="mt-1 flex items-center gap-2.5 text-2xl font-black tracking-tight text-foreground">
            سوق الإضافات وحزم الأنشطة
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            حوّل النظام بنقرة واحدة ليلائم أي نشاط تجاري: تجارة وتجزئة، مطاعم وكافيهات، مدارس وأكاديميات، أو مكاتب وشركات خدمية.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {activePresetObj && (
            <div className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs text-primary">
              <span className="size-2 rounded-full bg-primary animate-pulse" />
              <span>النشاط المفعّل:</span>
              <strong className="font-bold">{activePresetObj.name}</strong>
              <span className="num font-bold">({activeModules.length} وحدات نشطة)</span>
            </div>
          )}

          <Button
            variant="ghost"
            size="sm"
            className="size-8"
            onClick={() => {
              sound.click();
              fetchModules();
            }}
            title="تحديث البيانات"
          >
            <RefreshCw className={`size-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>


      {/* Live Industry Quick Links if Restaurant or School is Active */}
      {activeModules.includes("restaurant") && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-lg bg-amber-500 text-white">
                <UtensilsCrossed className="size-5" />
              </span>
              <div>
                <p className="font-bold text-sm text-foreground">
                  وحدة إدارة المطاعم والكافيهات مفعلة الآن!
                </p>
                <p className="text-muted-foreground">
                  يمكنك إدارة الصالة وتوزيع الطاولات، أو متابعة شاشات المطبخ اللحظية (KDS).
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Link
                to="/restaurant/tables"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-8 gap-1.5 text-xs bg-card")}
              >
                إدارة الصالة والطاولات
                <ArrowRight className="size-3" />
              </Link>
              <Link
                to="/restaurant/kitchen"
                className={cn(buttonVariants({ size: "sm" }), "h-8 gap-1.5 text-xs")}
              >
                شاشة المطبخ (KDS)
                <ExternalLink className="size-3" />
              </Link>
            </div>
          </div>
        </div>
      )}

      {activeModules.includes("school") && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <GraduationCap className="size-5" />
              </span>
              <div>
                <p className="font-bold text-sm text-foreground">
                  وحدة المدارس والمراكز التعليمية مفعلة الآن!
                </p>
                <p className="text-muted-foreground">
                  سجلات الطلاب، تحصيل الأقساط والمصروفات الدراسية، وكشوف الحضور.
                </p>
              </div>
            </div>

            <Link
              to="/school/students"
              className={cn(buttonVariants({ size: "sm" }), "h-8 gap-1.5 text-xs")}
            >
              فتح شؤون الطلاب والأقساط
              <ArrowRight className="size-3" />
            </Link>
          </div>
        </div>
      )}

      {/* Section 2: Individual Modules Catalog */}
      <section className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-6">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold text-foreground">
              <Layers className="size-5 text-primary" />
              دليل الوحدات والإضافات المنفردة (Module Catalog)
            </h2>
            <p className="text-xs text-muted-foreground">
              تفعيل أو إلغاء تثبيت أي وحدة بشكل مستقل لتخصيص مساحة العمل حسب رغبتك
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Search Input */}
            <div className="relative w-64">
              <Search className="absolute start-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="ابحث عن وحدة…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="ps-9 h-8 text-xs"
              />
            </div>

            {/* Family Filter Pills */}
            <div className="flex flex-wrap items-center gap-1">
              {[
                { k: "all", l: "الكل" },
                ...families
                  .filter((f) => catalog.some((m) => m.category === f.id))
                  .map((f) => ({ k: f.id, l: f.name })),
              ].map((c) => (
                <button
                  key={c.k}
                  onClick={() => {
                    sound.click();
                    setCategoryFilter(c.k);
                  }}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                    categoryFilter === c.k
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {c.l}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Modules Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredCatalog.map((mod) => {
            const Icon = ICON_MAP[mod.icon] ?? Layers;
            const isInstalled = mod.is_installed;
            const isToggling = togglingId === mod.id;

            return (
              <Card
                key={mod.id}
                className={`flex flex-col justify-between p-4 transition-all ${
                  isInstalled
                    ? "border-border/90 bg-card shadow-xs"
                    : "border-border/40 opacity-75 hover:opacity-100"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span
                        className={`flex size-10 items-center justify-center rounded-xl ${
                          isInstalled
                            ? "bg-primary/10 text-primary"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        <Icon className="size-5" />
                      </span>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <h3 className="font-bold text-xs text-foreground">{mod.name}</h3>
                          {mod.badge && (
                            <Badge variant="warning" className="h-4 px-1 text-[9px] font-bold">
                              {mod.badge}
                            </Badge>
                          )}
                        </div>
                        <p className="text-[10px] text-muted-foreground font-mono">v{mod.version}</p>
                      </div>
                    </div>

                    {/* Toggle Switch */}
                    {mod.is_core ? (
                      <span className="rounded bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                        نواة أساسية
                      </span>
                    ) : (
                      <button
                        onClick={() => handleToggle(mod)}
                        disabled={isToggling || (!isInstalled && mod.installable === false)}
                        title={!isInstalled && mod.installable === false ? mod.not_installable_reason : undefined}
                        aria-label={isInstalled ? "إزالة الوحدة" : "تثبيت الوحدة"}
                        className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                          isInstalled ? "bg-primary" : "bg-muted"
                        }`}
                      >
                        <span
                          className={`pointer-events-none inline-block size-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                            isInstalled ? "-translate-x-4" : "translate-x-0"
                          }`}
                        />
                      </button>
                    )}
                  </div>

                  <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                    {mod.description}
                  </p>
                  {!isInstalled && mod.installable === false && (
                    <p className="mt-2 text-[11px] text-muted-foreground/80">{mod.not_installable_reason}</p>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-border/40 flex items-center justify-between text-[10px] text-muted-foreground">
                  <span>
                    {mod.dependencies.length > 0 ? (
                      <>تعتمد على: <span className="font-medium">{mod.dependencies.join("، ")}</span></>
                    ) : (
                      "مستقلة بذاتها"
                    )}
                  </span>

                  <div className="flex items-center gap-2">
                    {mod.settings_schema && mod.settings_schema.length > 0 && (
                      <button
                        type="button"
                        onClick={() => openSettings(mod)}
                        className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold text-primary hover:bg-primary/10 transition-colors border border-primary/20"
                        title="تخصيص إعدادات الوحدة"
                      >
                        <Settings2 className="size-3" />
                        الإعدادات
                      </button>
                    )}
                    <span className={`font-semibold ${isInstalled ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                      {isInstalled ? "● مثبتة" : "○ غير نشطة"}
                    </span>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Module Settings Modal */}
      <Modal
        open={!!selectedForSettings}
        onClose={() => setSelectedForSettings(null)}
        title={selectedForSettings ? `إعدادات وحدة: ${selectedForSettings.name}` : ""}
      >
        {selectedForSettings && (
          <form onSubmit={handleSaveSettings} className="flex flex-col gap-4 text-xs">
            <div className="flex items-center gap-3 p-3 rounded-xl bg-muted/40 border border-border/70">
              <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                {(() => {
                  const Icon = ICON_MAP[selectedForSettings.icon] || Blocks;
                  return <Icon className="size-4.5" />;
                })()}
              </span>
              <div>
                <p className="font-bold text-foreground text-xs">{selectedForSettings.name}</p>
                <p className="text-[10px] text-muted-foreground">{selectedForSettings.description}</p>
              </div>
            </div>

            {isLoadingSettings ? (
              <div className="grid place-items-center p-8">
                <span className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              </div>
            ) : (
              <div className="flex flex-col gap-3 max-h-[60vh] overflow-y-auto px-0.5">
                {(selectedForSettings.settings_schema || []).map((field) => {
                  if (field.type === "boolean") {
                    return (
                      <label
                        key={field.key}
                        className="flex items-start justify-between gap-3 p-3 rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/30 cursor-pointer transition-colors"
                      >
                        <div className="flex flex-col gap-0.5">
                          <span className="font-bold text-xs text-foreground">{field.label}</span>
                          {field.description && (
                            <span className="text-[11px] text-muted-foreground leading-relaxed">
                              {field.description}
                            </span>
                          )}
                        </div>
                        <input
                          type="checkbox"
                          checked={Boolean(settingsValues[field.key])}
                          onChange={(e) =>
                            setSettingsValues((prev) => ({
                              ...prev,
                              [field.key]: e.target.checked,
                            }))
                          }
                          className="mt-0.5 size-4.5 rounded accent-primary cursor-pointer"
                        />
                      </label>
                    );
                  }

                  if (field.type === "select") {
                    return (
                      <div
                        key={field.key}
                        className="flex flex-col gap-1.5 p-3 rounded-xl border border-border/60 bg-muted/20"
                      >
                        <label className="font-bold text-xs text-foreground">{field.label}</label>
                        {field.description && (
                          <p className="text-[11px] text-muted-foreground">{field.description}</p>
                        )}
                        <select
                          value={settingsValues[field.key] ?? field.default ?? ""}
                          onChange={(e) =>
                            setSettingsValues((prev) => ({
                              ...prev,
                              [field.key]: e.target.value,
                            }))
                          }
                          className="h-9 rounded-lg border border-border bg-card px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
                        >
                          {(field.options || []).map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>
                    );
                  }

                  if (field.type === "number") {
                    return (
                      <div
                        key={field.key}
                        className="flex flex-col gap-1.5 p-3 rounded-xl border border-border/60 bg-muted/20"
                      >
                        <label className="font-bold text-xs text-foreground">{field.label}</label>
                        {field.description && (
                          <p className="text-[11px] text-muted-foreground">{field.description}</p>
                        )}
                        <Input
                          type="number"
                          step="any"
                          className="num font-mono text-sm h-9 bg-card"
                          value={settingsValues[field.key] ?? field.default ?? ""}
                          onChange={(e) =>
                            setSettingsValues((prev) => ({
                              ...prev,
                              [field.key]: parseFloat(e.target.value) || 0,
                            }))
                          }
                          required
                        />
                      </div>
                    );
                  }

                  return (
                    <div
                      key={field.key}
                      className="flex flex-col gap-1.5 p-3 rounded-xl border border-border/60 bg-muted/20"
                    >
                      <label className="font-bold text-xs text-foreground">{field.label}</label>
                      {field.description && (
                        <p className="text-[11px] text-muted-foreground">{field.description}</p>
                      )}
                      <Input
                        type="text"
                        className="text-xs h-9 bg-card"
                        value={settingsValues[field.key] ?? field.default ?? ""}
                        onChange={(e) =>
                          setSettingsValues((prev) => ({
                            ...prev,
                            [field.key]: e.target.value,
                          }))
                        }
                        required
                      />
                    </div>
                  );
                })}
              </div>
            )}

            <div className="flex items-center gap-2 pt-2 border-t border-border/60">
              <Button
                type="button"
                variant="outline"
                className="flex-1 h-9 text-xs"
                onClick={() => setSelectedForSettings(null)}
              >
                إلغاء
              </Button>
              <Button
                type="submit"
                disabled={isSavingSettings || isLoadingSettings}
                className="flex-1 h-9 font-bold text-xs"
              >
                {isSavingSettings ? "جارٍ الحفظ..." : "حفظ الإعدادات"}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      <UninstallDialog
        module={removing}
        onClose={() => setRemoving(null)}
        onDone={(message) => {
          setRemoving(null);
          toast("success", message);
          fetchModules();
          retention.refetch();
        }}
      />

      {!!retention.data?.length && (
        <section className="flex flex-col gap-2" aria-label="وحدات أُزيلت">
          <h2 className="text-sm font-bold text-foreground">وحدات أُزيلت</h2>
          <ul className="divide-y divide-line rounded-xl border border-line text-xs">
            {retention.data.map((r) => {
              const name = catalog.find((m) => m.id === r.module_id)?.name ?? r.module_id;
              return (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                  <span className="font-bold">{name}</span>
                  {r.mode === "kept" ? (
                    <span className="text-muted-foreground">بياناتها محفوظة حتى <span className="num">{r.purge_after?.slice(0, 10)}</span> — ثبّتها لاستعادتها</span>
                  ) : (
                    <span className="flex items-center gap-2 text-muted-foreground">
                      حُذفت بياناتها
                      {r.has_export && (
                        <button type="button" className="font-semibold text-primary hover:underline"
                          onClick={() => downloadExport(`/modules/retention/${r.id}/export`, {}, `${r.module_id}-data.json.gz`)}>
                          تنزيل النسخة
                        </button>
                      )}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
