import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/kit/dialog";
import { Button } from "@/components/kit/button";
import { Kbd } from "@/components/kit/kbd";
import { Link } from "react-router-dom";
import { useUiStore, LAYOUT_MODES } from "@/stores/ui";
import { useAuth } from "@/stores/auth";
import { sound } from "@/lib/sound";
import { Check, Moon, Sun, PanelLeft, Rows, AppWindow, Columns, Palette } from "lucide-react";

export function AppearanceSettingsModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const tenantTheme = useAuth((s) => s.tenant?.theme?.name);
  const canManageThemes = useAuth((s) => s.can("themes.manage"));
  const {
    layoutMode,
    setLayoutMode,
    density,
    setDensity,
    themeMode,
    setThemeMode,
  } = useUiStore();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl p-0 gap-0 overflow-hidden border border-border bg-card shadow-2xl">
        <DialogHeader className="p-6 pb-4 border-b border-border/80 bg-muted/20">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle className="text-base font-bold text-foreground">
                تخصيص المظهر وتخطيط النظام
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                الوضع الداكن وطريقة عرض القوائم وكثافة الشاشة على جهازك
              </DialogDescription>
            </div>
            <Kbd className="hidden sm:inline-flex">ESC</Kbd>
          </div>
        </DialogHeader>

        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {/* The workspace's theme is chosen by its admin for everyone (ADR-010 D3). */}
          <div className="flex items-start justify-between gap-3 rounded-lg border border-border bg-muted/30 p-3">
            <div className="flex items-start gap-2.5">
              <Palette className="mt-0.5 size-4 shrink-0 text-primary" />
              <div>
                <p className="text-xs font-semibold text-foreground">مظهر المنشأة: {tenantTheme ?? "ميزان"}</p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
                  الألوان والخطوط واحدة لكل من في المنشأة، ويختارها مديرها. هنا تختار ما يخص جهازك فقط: الوضع الداكن والتخطيط والكثافة.
                </p>
              </div>
            </div>
            {canManageThemes && (
              <Link to="/modules#themes" onClick={() => onOpenChange(false)}
                    className="inline-flex h-8 shrink-0 items-center rounded-md border border-input bg-card px-3 text-xs font-medium shadow-xs hover:bg-accent">
                المظاهر
              </Link>
            )}
          </div>

          {/* 2. Layout Modes */}
          <div>
            <div className="flex items-center justify-between mb-2.5">
              <label className="text-xs font-semibold text-foreground">
                تخطيط الشاشة وهيكل القوائم (Navigation Layout)
              </label>
              <span className="text-[11px] text-muted-foreground">قابل للتبديل الفوري دون إعادة تحميل</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {LAYOUT_MODES.map((l) => {
                const isSelected = layoutMode === l.id;
                const Icon =
                  l.id === "sidebar" ? PanelLeft : l.id === "rail" ? Columns : AppWindow;
                return (
                  <button
                    key={l.id}
                    type="button"
                    onClick={() => setLayoutMode(l.id)}
                    className={`flex flex-col text-start p-3 rounded-lg border transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 ring-1 ring-primary shadow-xs"
                        : "border-border hover:border-foreground/20 hover:bg-muted/40"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <Icon className={`size-4 ${isSelected ? "text-primary" : "text-muted-foreground"}`} />
                      {isSelected && <Check className="size-3.5 text-primary" />}
                    </div>
                    <span className="text-xs font-bold text-foreground mb-1">{l.name}</span>
                    <p className="text-[10px] text-muted-foreground leading-relaxed line-clamp-2">
                      {l.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. Density & Dark Mode Toggles */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-border/60">
            {/* View Density */}
            <div>
              <label className="text-xs font-semibold text-foreground block mb-2">
                كثافة البيانات (View Density)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setDensity("compact")}
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-md border text-xs font-medium transition ${
                    density === "compact"
                      ? "border-primary bg-primary text-primary-foreground font-semibold"
                      : "border-border hover:bg-muted text-foreground"
                  }`}
                >
                  <Rows className="size-3.5" />
                  <span>عالي الكثافة (Terminal)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setDensity("comfortable")}
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-md border text-xs font-medium transition ${
                    density === "comfortable"
                      ? "border-primary bg-primary text-primary-foreground font-semibold"
                      : "border-border hover:bg-muted text-foreground"
                  }`}
                >
                  <span>مريح (Comfortable)</span>
                </button>
              </div>
            </div>

            {/* Dark / Light Mode */}
            <div>
              <label className="text-xs font-semibold text-foreground block mb-2">
                نمط الإضاءة (Light / Dark)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setThemeMode("light")}
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-md border text-xs font-medium transition ${
                    themeMode === "light"
                      ? "border-primary bg-primary text-primary-foreground font-semibold"
                      : "border-border hover:bg-muted text-foreground"
                  }`}
                >
                  <Sun className="size-3.5" />
                  <span>فاتح (Light)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setThemeMode("dark")}
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-md border text-xs font-medium transition ${
                    themeMode === "dark"
                      ? "border-primary bg-primary text-primary-foreground font-semibold"
                      : "border-border hover:bg-muted text-foreground"
                  }`}
                >
                  <Moon className="size-3.5" />
                  <span>داكن (Dark)</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border/80 bg-muted/20 flex items-center justify-between">
          <span className="text-[11px] text-muted-foreground">
            تُحفظ كافة خياراتك تلقائياً على هذا الجهاز
          </span>
          <Button
            size="sm"
            onClick={() => {
              sound.click();
              onOpenChange(false);
            }}
          >
            تم وحفظ
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
