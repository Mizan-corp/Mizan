import { useState } from "react";
import {
  GitFork, Search, Plus, X
} from "lucide-react";
import {
  DepartmentItem,
  DepartmentCategory,
  HealthcareFacilityItem,
  BuildingItem
} from "../types";

interface DepartmentsProps {
  departments: DepartmentItem[];
  facilities: HealthcareFacilityItem[];
  buildings: BuildingItem[];
  currentFacilityId: string | "all";
  onAddDepartment: (dept: DepartmentItem) => void;
  onNavigate: (screenId: string) => void;
}

const CATEGORIES: Array<{ id: string; label: string; labelEn: string }> = [
  { id: "all", label: "جميع التصنيفات", labelEn: "All Categories" },
  { id: "clinical", label: "أقسام سريرية وعيادات", labelEn: "Clinical" },
  { id: "diagnostic", label: "مختبرات وتشخيص", labelEn: "Diagnostic" },
  { id: "surgical", label: "جراحة وعمليات", labelEn: "Surgical" },
  { id: "emergency", label: "طوارئ وحوادث", labelEn: "Emergency" },
  { id: "administrative", label: "إدارة وشؤون المرضى", labelEn: "Administrative" },
  { id: "support_services", label: "خدمات دعم مساندة", labelEn: "Support Services" },
];

export default function Screen07_Departments({
  departments,
  facilities,
  buildings,
  currentFacilityId,
  onAddDepartment,
  onNavigate,
}: DepartmentsProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedDeptDetail, setSelectedDeptDetail] = useState<DepartmentItem | null>(null);

  // New Department Form State
  const [name, setName] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [code, setCode] = useState("");
  const [category, setCategory] = useState<DepartmentCategory>("clinical");
  const [facilityId, setFacilityId] = useState(
    currentFacilityId !== "all" ? currentFacilityId : facilities[0]?.id || ""
  );
  const [buildingId, setBuildingId] = useState(buildings[0]?.id || "");
  const [floorId, setFloorId] = useState(buildings[0]?.floors[0]?.id || "");
  const [managerName, setManagerName] = useState("");
  const [managerTitle, setManagerTitle] = useState("رئيس القسم الطبي");
  const [operatingHours, setOperatingHours] = useState("08:00 ص - 08:00 م");
  const [description, setDescription] = useState("");

  // Filter departments
  const filtered = departments.filter((dept) => {
    const matchFacility = currentFacilityId === "all" || dept.facilityId === currentFacilityId;
    const matchCat = selectedCategory === "all" || dept.category === selectedCategory;
    const matchQ =
      !searchQuery ||
      dept.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      dept.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      dept.managerName.toLowerCase().includes(searchQuery.toLowerCase());
    return matchFacility && matchCat && matchQ;
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !code) return;

    const fac = facilities.find((f) => f.id === facilityId);
    const bld = buildings.find((b) => b.id === buildingId);
    const flr = bld?.floors.find((f) => f.id === floorId);

    const newDept: DepartmentItem = {
      id: `dept-${Date.now()}`,
      facilityId,
      facilityName: fac?.name || "المنشأة الطبية",
      code: code.toUpperCase(),
      name,
      nameEn: nameEn || name,
      category,
      buildingId,
      buildingName: bld?.name || "المبنى الرئيسي",
      floorId,
      floorName: flr?.name || "الطابق الأول",
      managerName: managerName || "د. رئيس القسم",
      managerTitle,
      staffCount: 1,
      unitsCount: 0,
      status: "active",
      description,
      availableServices: ["استشارات طبية عامة"],
      operatingHours,
    };

    onAddDepartment(newDept);
    setShowCreateModal(false);
    // Reset
    setName("");
    setNameEn("");
    setCode("");
    setDescription("");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-003 • الأقسام التخصصية
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            إدارة الأقسام الطبية والإدارية
          </h1>
          <p className="text-xs text-[#64748B]">
            تنظيم وتوزيع الأقسام السريرية والتشخيصية، رؤساء الأقسام، والمواقع المكانية في المستشفيات.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF] shadow-xs"
          >
            <Plus className="w-4 h-4" /> إضافة قسم طبي / إداري جديد
          </button>
        </div>
      </div>

      {/* Filter Category Pills & Search */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedCategory === cat.id
                  ? "bg-[#1E3A8A] text-white shadow-xs font-bold"
                  : "bg-white border border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC]"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="w-3.5 h-3.5 text-[#94A3B8] absolute right-3 top-2.5" />
            <input
              type="text"
              placeholder="بحث باسم القسم، الرمز الكودي أو رئيس القسم..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs pr-8 pl-3 py-2 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
            />
          </div>

          <div className="text-xs text-[#64748B]">
            إجمالي الأقسام المعروضة: <strong>{filtered.length}</strong> من أصل {departments.length}
          </div>
        </div>
      </div>

      {/* Departments Data Table */}
      <div className="rounded-xl border border-[#E2E8F0] bg-white overflow-hidden shadow-2xs">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-[#F8FAFC] text-[#475569] font-bold border-b border-[#E2E8F0]">
              <tr>
                <th className="py-3 px-4">اسم القسم والكود</th>
                <th className="py-3 px-4">المنشأة</th>
                <th className="py-3 px-4">التصنيف</th>
                <th className="py-3 px-4">رئيس القسم</th>
                <th className="py-3 px-4">الموقع المعماري</th>
                <th className="py-3 px-4">الوحدات والكوادر</th>
                <th className="py-3 px-4">الحالة</th>
                <th className="py-3 px-4 text-center">الإجراءات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {filtered.map((dept) => (
                <tr key={dept.id} className="hover:bg-[#F8FAFC]/80 transition-colors">
                  <td className="py-3 px-4">
                    <div className="font-bold text-[#0F172A]">{dept.name}</div>
                    <div className="text-[11px] font-mono text-[#64748B]">{dept.code}</div>
                  </td>
                  <td className="py-3 px-4 text-[#334155] font-medium">{dept.facilityName}</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200">
                      {dept.category}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="font-semibold text-[#0F172A]">{dept.managerName}</div>
                    <div className="text-[10px] text-[#64748B]">{dept.managerTitle}</div>
                  </td>
                  <td className="py-3 px-4 text-[#475569]">
                    <div>{dept.buildingName}</div>
                    <div className="text-[10px] text-[#64748B]">{dept.floorName}</div>
                  </td>
                  <td className="py-3 px-4 font-mono">
                    <span className="text-[#1E3A8A] font-bold">{dept.unitsCount}</span> وحدات •{" "}
                    <span className="text-[#0F172A] font-bold">{dept.staffCount}</span> كادر
                  </td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {dept.status === "active" ? "نشط" : dept.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <button
                      onClick={() => setSelectedDeptDetail(dept)}
                      className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-blue-50 text-[#1E3A8A] hover:bg-blue-100"
                    >
                      استعراض التفاصيل
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─── MODAL 1: CREATE DEPARTMENT ──────────────────────────────────── */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-base text-[#0F172A] flex items-center gap-2">
                <GitFork className="w-5 h-5 text-[#1E3A8A]" /> إضافة قسم طبي أو إداري جديد
              </h3>
              <button onClick={() => setShowCreateModal(false)} className="text-[#64748B] hover:text-[#0F172A]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">اسم القسم بالعربية *</label>
                  <input
                    type="text"
                    placeholder="مثال: قسم القلب والأوعية الدموية"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">اسم القسم بالإنجليزية</label>
                  <input
                    type="text"
                    placeholder="e.g. Cardiology Department"
                    value={nameEn}
                    onChange={(e) => setNameEn(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    dir="ltr"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">الرمز الكودي للقسم *</label>
                  <input
                    type="text"
                    placeholder="e.g. DPT-CARDIO"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">تصنيف القسم الطبي</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value as DepartmentCategory)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    <option value="clinical">سريري (Clinical)</option>
                    <option value="diagnostic">تشخيصي ومختبرات (Diagnostic)</option>
                    <option value="surgical">جراحي (Surgical)</option>
                    <option value="emergency">طوارئ (Emergency)</option>
                    <option value="administrative">إداري (Administrative)</option>
                    <option value="support_services">خدمات مساندة (Support)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">المنشأة التابع لها</label>
                  <select
                    value={facilityId}
                    onChange={(e) => setFacilityId(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    {facilities.map((fac) => (
                      <option key={fac.id} value={fac.id}>
                        {fac.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">المبنى المستضيف</label>
                  <select
                    value={buildingId}
                    onChange={(e) => {
                      setBuildingId(e.target.value);
                      const bld = buildings.find((b) => b.id === e.target.value);
                      if (bld && bld.floors[0]) setFloorId(bld.floors[0].id);
                    }}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    {buildings.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">الطابق</label>
                  <select
                    value={floorId}
                    onChange={(e) => setFloorId(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    {buildings
                      .find((b) => b.id === buildingId)
                      ?.floors.map((fl) => (
                        <option key={fl.id} value={fl.id}>
                          {fl.name}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">المسمى الوظيفي لرئيس القسم</label>
                  <input
                    type="text"
                    value={managerTitle}
                    onChange={(e) => setManagerTitle(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">رئيس القسم (HOD)</label>
                  <input
                    type="text"
                    placeholder="د. ياسر المنشاوي"
                    value={managerName}
                    onChange={(e) => setManagerName(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  />
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">ساعات العمل الرسمية</label>
                  <input
                    type="text"
                    value={operatingHours}
                    onChange={(e) => setOperatingHours(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">الوصف والمهام الطبية</label>
                <textarea
                  rows={2}
                  placeholder="تقديم رعاية قلبية تخصصية متكاملة..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[#F1F5F9] pt-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC]"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-[#1E3A8A] text-white font-bold hover:bg-[#1E40AF]"
                >
                  حفظ وتأكيد القسم
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── DRAWER: DEPARTMENT DETAILS ───────────────────────────────────── */}
      {selectedDeptDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/40">
          <div className="w-full max-w-lg h-full bg-white p-6 shadow-2xl space-y-5 overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <div>
                <h3 className="font-bold text-base text-[#0F172A]">{selectedDeptDetail.name}</h3>
                <span className="text-xs font-mono text-[#64748B]">{selectedDeptDetail.code}</span>
              </div>
              <button
                onClick={() => setSelectedDeptDetail(null)}
                className="text-[#64748B] hover:text-[#0F172A]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[#64748B]">المنشأة:</span>
                  <span className="font-semibold text-[#0F172A]">{selectedDeptDetail.facilityName}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#64748B]">الموقع:</span>
                  <span className="text-[#0F172A]">{selectedDeptDetail.buildingName} — {selectedDeptDetail.floorName}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#64748B]">رئيس القسم:</span>
                  <span className="font-bold text-[#1E3A8A]">{selectedDeptDetail.managerName}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#64748B]">ساعات العمل:</span>
                  <span className="font-semibold text-[#0F172A]">{selectedDeptDetail.operatingHours}</span>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-sm text-[#0F172A] mb-2">الوصف والمهام</h4>
                <p className="text-xs text-[#475569] leading-relaxed bg-white p-3 rounded-lg border border-[#E2E8F0]">
                  {selectedDeptDetail.description || "لا يوجد وصف مدخل."}
                </p>
              </div>

              <div>
                <h4 className="font-bold text-sm text-[#0F172A] mb-2">الخدمات المتاحة بالقسم</h4>
                <div className="flex flex-wrap gap-1.5">
                  {selectedDeptDetail.availableServices.map((svc) => (
                    <span key={svc} className="px-2.5 py-1 rounded-md bg-teal-50 text-teal-800 text-[11px] font-semibold border border-teal-200">
                      {svc}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-[#E2E8F0] flex gap-2">
                <button
                  onClick={() => {
                    setSelectedDeptDetail(null);
                    onNavigate("units_rooms");
                  }}
                  className="flex-1 py-2 rounded-lg bg-[#1E3A8A] text-white text-xs font-bold text-center hover:bg-[#1E40AF]"
                >
                  استعراض وحدات وغرف القسم
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
