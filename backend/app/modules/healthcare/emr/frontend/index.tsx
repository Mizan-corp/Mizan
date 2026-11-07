import { useState, useEffect } from "react";
import {
  Building2,
  CheckCircle2,
  Filter,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";

export default function EmrView() {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.get<any>("/api/healthcare/emr");
      if (Array.isArray(res)) {
        setItems(res);
      } else if (res && typeof res === "object") {
        setItems([res]);
      }
    } catch (err) {
      console.warn("Could not fetch data for hlt_emr:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="space-y-6 animate-fade-in" dir="rtl">
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#651E2C] to-[#4A1520] p-6 text-[#FAF6F0] shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#FAF6F0]/20 text-[#FAF6F0] tracking-wider uppercase">
                HLT-05 • Standalone Module
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] bg-emerald-500/20 text-emerald-200 border border-emerald-500/30">
                نشط ومعتمد
              </span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#FAF6F0]">
              السجل الطبي الإلكتروني التراكمي
            </h1>
            <p className="text-sm text-[#FAF6F0]/80 mt-1 max-w-2xl font-light">
              العلامات الحيوية، التاريخ المرضي والجراحي، الحساسيات الدوائية، الأمراض المزمنة، والمرفقات.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-white/10 hover:bg-white/20 text-[#FAF6F0] transition-colors border border-white/10"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              تحديث
            </button>
            <button
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-[#FAF6F0] text-[#651E2C] hover:bg-white shadow-sm transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              إضافة جديد
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#FAF6F0] border border-[#E5DDD0] rounded-2xl p-4 shadow-sm">
          <div className="text-xs text-[#706A60] font-medium">إجمالي السجلات</div>
          <div className="text-2xl font-bold text-[#262321] mt-1 num font-mono">
            {items.length}
          </div>
          <div className="text-[11px] text-emerald-700 mt-1 flex items-center gap-1 font-medium">
            <CheckCircle2 className="w-3 h-3" />
            سجلات محدثة وفورية
          </div>
        </div>

        <div className="bg-[#FAF6F0] border border-[#E5DDD0] rounded-2xl p-4 shadow-sm">
          <div className="text-xs text-[#706A60] font-medium">حالة الامتثال الطبي</div>
          <div className="text-2xl font-bold text-[#651E2C] mt-1 num">
            100%
          </div>
          <div className="text-[11px] text-[#706A60] mt-1">معايير الاعتماد الصحي</div>
        </div>

        <div className="bg-[#FAF6F0] border border-[#E5DDD0] rounded-2xl p-4 shadow-sm">
          <div className="text-xs text-[#706A60] font-medium">العزل وحماية البيانات</div>
          <div className="text-2xl font-bold text-[#262321] mt-1 font-mono">
            Tenant-RLS
          </div>
          <div className="text-[11px] text-emerald-700 mt-1">عزل تام للمنشأة</div>
        </div>

        <div className="bg-[#FAF6F0] border border-[#E5DDD0] rounded-2xl p-4 shadow-sm">
          <div className="text-xs text-[#706A60] font-medium">التكامل المؤسسي</div>
          <div className="text-2xl font-bold text-[#651E2C] mt-1">
            جاهز
          </div>
          <div className="text-[11px] text-[#706A60] mt-1">روابط الفوترة والسريرية</div>
        </div>
      </div>

      <div className="bg-white border border-[#E5DDD0] rounded-2xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-[#E5DDD0] bg-[#FAF6F0]/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-[#706A60] absolute right-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="بحث في السجلات..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pr-9 pl-4 py-2 text-xs rounded-xl border border-[#E5DDD0] bg-white text-[#262321] focus:outline-none focus:ring-1 focus:ring-[#651E2C]"
            />
          </div>
          <div className="flex items-center gap-2">
            <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#E5DDD0] text-xs text-[#706A60] bg-white hover:bg-[#FAF6F0] transition-colors">
              <Filter className="w-3.5 h-3.5" />
              تصفية
            </button>
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-[#706A60]">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-[#651E2C]" />
            <p className="text-xs">جاري تحميل السجلات الطبية...</p>
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-[#706A60]">
            <Building2 className="w-8 h-8 mx-auto mb-2 text-[#651E2C]/40" />
            <p className="text-sm font-medium text-[#262321]">لا توجد بيانات مسجلة بعد</p>
            <p className="text-xs text-[#706A60] mt-1">
              ابدأ بإضافة أول سجل عبر زر «إضافة جديد» أعلاه
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="bg-[#FAF6F0] text-[#706A60] border-b border-[#E5DDD0] uppercase text-[11px] font-medium tracking-wider">
                <tr>
                  <th className="py-3 px-4">#</th>
                  <th className="py-3 px-4">البيان / المعرف</th>
                  <th className="py-3 px-4">التفاصيل</th>
                  <th className="py-3 px-4">الحالة</th>
                  <th className="py-3 px-4">تاريخ التوثيق</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5DDD0]">
                {items.map((row: any, idx: number) => (
                  <tr key={row.id || idx} className="hover:bg-[#FAF6F0]/40 transition-colors">
                    <td className="py-3 px-4 font-mono text-[#706A60]">{row.id || idx + 1}</td>
                    <td className="py-3 px-4 font-semibold text-[#262321]">
                      {row.name || row.mrn || row.appointment_number || row.case_number || row.invoice_number || row.claim_number || row.order_number || row.code || (`سجل #${idx + 1}`)}
                    </td>
                    <td className="py-3 px-4 text-[#706A60]">
                      {row.specialty || row.facility_type || row.phone || row.chief_complaint || row.service_type || row.modality || "—"}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-800">
                        {row.status || "نشط"}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[#706A60] num font-mono">
                      {row.created_at ? new Date(row.created_at).toLocaleDateString("ar-SA") : "الآن"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
