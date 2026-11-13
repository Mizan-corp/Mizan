import { useState } from "react";
import {
  Hospital, Search, Plus, Download,
  LayoutGrid, List, Edit3, MapPin
} from "lucide-react";
import { HealthcareFacilityItem } from "../types";

interface FacilitiesProps {
  facilities: HealthcareFacilityItem[];
  onSelectFacility: (facilityId: string) => void;
  onNavigate: (screenId: string) => void;
  onAddFacility: () => void;
  onEditFacility: (facility: HealthcareFacilityItem) => void;
}

export default function Screen03_Facilities({
  facilities,
  onSelectFacility,
  onNavigate,
  onAddFacility,
  onEditFacility,
}: FacilitiesProps) {
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Filtered facilities
  const filtered = facilities.filter((f) => {
    const matchType = selectedType === "all" || f.type === selectedType;
    const matchQ =
      !searchQuery ||
      f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.nameEn.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.location.city.toLowerCase().includes(searchQuery.toLowerCase());
    return matchType && matchQ;
  });

  const toggleSelectAll = () => {
    if (selectedIds.length === filtered.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filtered.map((f) => f.id));
    }
  };

  const toggleSelectOne = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((x) => x !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const handleExport = () => {
    const jsonStr = JSON.stringify(filtered, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mizan-facilities-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-002 • Multi-Branch Operations
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            إدارة المنشآت الطبية والمستشفيات
          </h1>
          <p className="text-xs text-[#64748B]">
            استعراض وضبط فروع الشبكة الصحية، مراقبة البنية التحتية، وتعيين الكوادر الإدارية والطبية.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[#CBD5E1] bg-white text-xs font-medium text-[#475569] hover:bg-[#F8FAFC] shadow-2xs"
            title="تصدير قائمة المنشآت"
          >
            <Download className="w-3.5 h-3.5" /> تصدير
          </button>
          <button
            onClick={onAddFacility}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF] shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" /> إضافة منشأة جديدة
          </button>
        </div>
      </div>

      {/* Control Bar: Search, Type Filters & View Mode */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white p-3.5 rounded-xl border border-[#E2E8F0] shadow-2xs">
        {/* Type Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          {[
            { id: "all", label: "الكل" },
            { id: "hospital", label: "مستشفيات" },
            { id: "medical_center", label: "مراكز طبية" },
            { id: "clinic", label: "عيادات خارجية" },
            { id: "diagnostic_center", label: "مراكز تشخيصية" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedType(t.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedType === t.id
                  ? "bg-[#1E3A8A] text-white font-semibold shadow-xs"
                  : "bg-[#F8FAFC] text-[#475569] hover:bg-[#F1F5F9] border border-[#E2E8F0]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute right-3 top-2.5 w-3.5 h-3.5 text-[#94A3B8]" />
            <input
              type="text"
              placeholder="بحث بالاسم، الكود، المدينة..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs pr-8 pl-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:border-[#2563EB]"
            />
          </div>

          {/* Table / Grid Toggle */}
          <div className="flex rounded-lg border border-[#CBD5E1] p-0.5 bg-[#F8FAFC]">
            <button
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded text-xs ${viewMode === "table" ? "bg-white text-[#1E3A8A] shadow-xs font-bold" : "text-[#64748B]"}`}
              title="عرض جدولي"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded text-xs ${viewMode === "grid" ? "bg-white text-[#1E3A8A] shadow-xs font-bold" : "text-[#64748B]"}`}
              title="عرض بطاقات"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Multi-Select Bulk Actions Bar */}
      {selectedIds.length > 0 && (
        <div className="flex items-center justify-between p-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-900 text-xs animate-in fade-in">
          <div className="flex items-center gap-2">
            <span className="font-bold">تم تحديد {selectedIds.length} منشأة</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedIds([])}
              className="px-2.5 py-1 rounded bg-white border border-blue-200 text-blue-900 font-semibold hover:bg-blue-100"
            >
              إلغاء التحديد
            </button>
            <button
              onClick={handleExport}
              className="px-2.5 py-1 rounded bg-[#1E3A8A] text-white font-semibold hover:bg-[#1E40AF]"
            >
              تصدير المحدد
            </button>
          </div>
        </div>
      )}

      {/* ─── VIEW 1: DATA TABLE VIEW ──────────────────────────────────── */}
      {viewMode === "table" && (
        <div className="overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-right">
              <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[#64748B] font-semibold">
                <tr>
                  <th className="p-3 w-8">
                    <input
                      type="checkbox"
                      checked={selectedIds.length === filtered.length && filtered.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded text-[#1E3A8A]"
                    />
                  </th>
                  <th className="p-3">اسم المنشأة والكود</th>
                  <th className="p-3">النوع</th>
                  <th className="p-3">الموقع الجغرافي</th>
                  <th className="p-3">الأقسام</th>
                  <th className="p-3">المدير التشغيلي والطبي</th>
                  <th className="p-3">ساعات العمل</th>
                  <th className="p-3">الحالة</th>
                  <th className="p-3 text-center">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {filtered.map((fac) => {
                  const isChecked = selectedIds.includes(fac.id);
                  return (
                    <tr key={fac.id} className={`hover:bg-[#F8FAFC]/70 transition-colors ${isChecked ? "bg-blue-50/40" : ""}`}>
                      <td className="p-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSelectOne(fac.id)}
                          className="rounded text-[#1E3A8A]"
                        />
                      </td>
                      <td className="p-3">
                        <div className="font-bold text-sm text-[#0F172A]">{fac.name}</div>
                        <div className="text-[11px] text-[#64748B] font-mono mt-0.5">{fac.code} • {fac.nameEn}</div>
                      </td>
                      <td className="p-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-800 border border-slate-200">
                          {fac.type === "hospital" ? "مستشفى تخصصي" : fac.type === "medical_center" ? "مركز طبي" : fac.type === "diagnostic_center" ? "مركز تشخيصي" : "عيادات خارجية"}
                        </span>
                      </td>
                      <td className="p-3">
                        <div className="text-[#334155]">{fac.location.city}، {fac.location.governorate}</div>
                        <div className="text-[10px] text-[#64748B] mt-0.5">{fac.location.district}</div>
                      </td>
                      <td className="p-3">
                        <span className="font-mono font-bold text-[#1E3A8A] text-xs">
                          {fac.stats.departmentCount} قسم
                        </span>
                        <div className="text-[10px] text-[#64748B]">{fac.stats.roomCount} غرفة</div>
                      </td>
                      <td className="p-3">
                        <div className="font-medium text-[#0F172A]">{fac.administration.managerName}</div>
                        <div className="text-[10px] text-[#64748B]">{fac.administration.medicalDirector}</div>
                      </td>
                      <td className="p-3">
                        {fac.operations.is24HoursEmergency ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-teal-50 text-teal-800 border border-teal-200">
                            طوارئ 24/7
                          </span>
                        ) : (
                          <span className="text-[11px] text-[#64748B] font-mono">09:00 ص - 09:00 م</span>
                        )}
                      </td>
                      <td className="p-3">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                            fac.status === "active"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : fac.status === "under_construction"
                              ? "bg-amber-50 text-amber-700 border border-amber-200"
                              : "bg-rose-50 text-rose-700 border border-rose-200"
                          }`}
                        >
                          {fac.status === "active" ? "تشغيلي نشط" : fac.status === "under_construction" ? "قيد التشييد" : "معلق"}
                        </span>
                      </td>
                      <td className="p-3 text-center">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            onClick={() => {
                              onSelectFacility(fac.id);
                              onNavigate("facility_details");
                            }}
                            className="px-2.5 py-1 rounded bg-[#F1F5F9] text-[#1E3A8A] font-semibold hover:bg-[#1E3A8A] hover:text-white transition-colors"
                          >
                            عرض الملف
                          </button>
                          <button
                            onClick={() => onEditFacility(fac)}
                            className="p-1 rounded text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9]"
                            title="تعديل المنشأة"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Table Footer */}
          <div className="flex items-center justify-between border-t border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 text-xs text-[#64748B]">
            <span>عرض {filtered.length} من أصل {facilities.length} منشأة</span>
            <div className="flex items-center gap-1">
              <span className="px-2 py-0.5 rounded bg-white border border-[#CBD5E1] font-mono text-[11px] text-[#0F172A] font-bold">1</span>
            </div>
          </div>
        </div>
      )}

      {/* ─── VIEW 2: CARDS GRID VIEW ──────────────────────────────────── */}
      {viewMode === "grid" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((fac) => (
            <div
              key={fac.id}
              className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-blue-50 text-[#1E3A8A] border border-blue-200">
                      <Hospital className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-[#0F172A] leading-snug">{fac.name}</h3>
                      <span className="text-[10px] text-[#64748B] font-mono">{fac.code}</span>
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${
                      fac.status === "active"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}
                  >
                    {fac.status === "active" ? "نشط" : "قيد الإنشاء"}
                  </span>
                </div>

                <div className="flex items-center gap-1 text-[11px] text-[#64748B] mt-2">
                  <MapPin className="w-3.5 h-3.5 text-[#94A3B8]" />
                  <span>{fac.location.city} • {fac.location.district}</span>
                </div>

                <p className="text-xs text-[#475569] mt-3 line-clamp-2 leading-relaxed">
                  {fac.description}
                </p>

                {/* Sub-metrics */}
                <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-[#F1F5F9] text-center text-xs">
                  <div className="p-1.5 rounded bg-[#F8FAFC]">
                    <div className="text-[10px] text-[#64748B]">الأقسام</div>
                    <div className="font-mono font-bold text-[#0F172A]">{fac.stats.departmentCount}</div>
                  </div>
                  <div className="p-1.5 rounded bg-[#F8FAFC]">
                    <div className="text-[10px] text-[#64748B]">الغرف</div>
                    <div className="font-mono font-bold text-[#0F172A]">{fac.stats.roomCount}</div>
                  </div>
                  <div className="p-1.5 rounded bg-[#F8FAFC]">
                    <div className="text-[10px] text-[#64748B]">الخدمات</div>
                    <div className="font-mono font-bold text-[#0F172A]">{fac.stats.activeServicesCount}</div>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-[#E2E8F0] flex items-center justify-between">
                <span className="text-[11px] text-[#64748B] truncate max-w-[150px]">
                  المدير: <strong>{fac.administration.managerName}</strong>
                </span>
                <button
                  onClick={() => {
                    onSelectFacility(fac.id);
                    onNavigate("facility_details");
                  }}
                  className="px-3 py-1 text-xs font-semibold rounded-lg bg-[#1E3A8A] text-white hover:bg-[#1E40AF] transition-colors"
                >
                  عرض المنشأة
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
