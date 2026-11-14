import { Hospital } from "lucide-react";
import { HEALTHCARE_CATEGORIES, HEALTHCARE_MODULES_MAP } from "../healthcareModules";

// The suite's 24 standalone screens (HLT-01..24) as pills, filtered by category.
export default function HealthcareSuiteNav({
  activeModuleKey,
  onSelect,
  activeCategory,
  onCategoryChange: setActiveCategory,
}: {
  activeModuleKey: string | null;
  onSelect: (key: string | null) => void;
  activeCategory: string;
  onCategoryChange: (category: string) => void;
}) {

  return (
    <div className="bg-card border border-border/80 rounded-2xl p-4 shadow-xs space-y-3">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-[#651E2C] text-[#FAF6F0]">
            Mizan Healthcare ERP
          </span>
          <span className="text-xs text-muted-foreground font-medium">
            مصفوفة الرعاية الصحية والمستشفيات (24 وحدة معتمدة HLT-01..24)
          </span>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => onSelect(null)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer ${
              !activeModuleKey
                ? "bg-[#651E2C] text-[#FAF6F0] shadow-xs"
                : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            <Hospital className="w-3.5 h-3.5" />
            العيادة السريعة اليومية
          </button>

          {HEALTHCARE_CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-colors ${
                activeCategory === cat
                  ? "bg-[#651E2C]/10 text-[#651E2C] font-semibold"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
              }`}
            >
              {cat === "All" ? "الكل (24)" : cat}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scrollbar-thin">
        {Object.entries(HEALTHCARE_MODULES_MAP)
          .filter(([, mod]) => activeCategory === "All" || mod.category === activeCategory)
          .map(([key, mod]) => {
            const IconComp = mod.icon;
            const isSelected = activeModuleKey === key;
            return (
              <button
                key={key}
                onClick={() => onSelect(key)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-all border shrink-0 cursor-pointer ${
                  isSelected
                    ? "bg-[#651E2C] text-[#FAF6F0] border-[#651E2C] shadow-xs font-semibold"
                    : "bg-card border-border/70 text-muted-foreground hover:border-[#651E2C]/40 hover:text-foreground hover:bg-muted/30"
                }`}
              >
                <IconComp className="w-3.5 h-3.5" />
                <span className="font-mono text-[10px] opacity-75">{mod.code}</span>
                <span>{mod.title}</span>
                {mod.preview && (
                  <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">معاينة</span>
                )}
              </button>
            );
          })}
      </div>
    </div>
  );
}
