import { useState } from "react";
import {
  MapPin, Plus, Search, X
} from "lucide-react";
import {
  ServiceLocationItem,
  HealthcareFacilityItem,
  DepartmentItem,
  RoomItem,
  ServiceDeliveryType
} from "../types";

interface ServiceLocationsProps {
  serviceLocations: ServiceLocationItem[];
  facilities: HealthcareFacilityItem[];
  departments: DepartmentItem[];
  rooms: RoomItem[];
  currentFacilityId: string | "all";
  onAddServiceLocation: (loc: ServiceLocationItem) => void;
  onUpdateStatus: (id: string, status: "active" | "temporarily_closed" | "maintenance") => void;
}

const SERVICE_TYPE_OPTIONS: Array<{ id: ServiceDeliveryType; label: string }> = [
  { id: "consultation", label: "كشف واستشارة طبية" },
  { id: "diagnostic_imaging", label: "أشعة ورنين وتصوير طبي" },
  { id: "laboratory_test", label: "سحب عينات وتحاليل" },
  { id: "surgical_procedure", label: "إجراءات جراحية وتدخلات" },
  { id: "wound_care", label: "غيار جروح وتمريض" },
  { id: "vaccination", label: "تطعيمات ولقاحات" },
  { id: "dialysis", label: "جلسات غسيل كلوي" },
  { id: "physiotherapy", label: "علاج طبيعي وتأهيل" },
  { id: "emergency_triage", label: "فرز طوارئ وحالات عاجلة" },
];

export default function Screen09_ServiceLocations({
  serviceLocations,
  facilities,
  departments,
  rooms,
  currentFacilityId,
  onAddServiceLocation,
  onUpdateStatus,
}: ServiceLocationsProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>("all");
  const [showDrawer, setShowDrawer] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState<ServiceLocationItem | null>(null);

  // New Service Location Form State
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [facilityId, setFacilityId] = useState(
    currentFacilityId !== "all" ? currentFacilityId : facilities[0]?.id || ""
  );
  const [departmentId, setDepartmentId] = useState(departments[0]?.id || "");
  const [roomId, setRoomId] = useState(rooms[0]?.id || "");
  const [selectedTypes, setSelectedTypes] = useState<ServiceDeliveryType[]>(["consultation"]);
  const [assignedStaff, setAssignedStaff] = useState("");
  const [schedule, setSchedule] = useState("08:00 ص - 04:00 م (السبت - الخميس)");

  const filtered = serviceLocations.filter((loc) => {
    const matchFacility = currentFacilityId === "all" || loc.facilityId === currentFacilityId;
    const matchType =
      selectedTypeFilter === "all" ||
      loc.supportedServices.includes(selectedTypeFilter as ServiceDeliveryType);
    const matchQ =
      !searchQuery ||
      loc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      loc.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      loc.departmentName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      loc.roomCode.toLowerCase().includes(searchQuery.toLowerCase());
    return matchFacility && matchType && matchQ;
  });

  const toggleType = (t: ServiceDeliveryType) => {
    if (selectedTypes.includes(t)) {
      if (selectedTypes.length > 1) {
        setSelectedTypes(selectedTypes.filter((x) => x !== t));
      }
    } else {
      setSelectedTypes([...selectedTypes, t]);
    }
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !code) return;

    const fac = facilities.find((f) => f.id === facilityId);
    const dept = departments.find((d) => d.id === departmentId);
    const rm = rooms.find((r) => r.id === roomId);

    const newLoc: ServiceLocationItem = {
      id: `sl-${Date.now()}`,
      code: code.toUpperCase(),
      name,
      facilityId,
      facilityName: fac?.name || "المنشأة الطبية",
      departmentId,
      departmentName: dept?.name || "القسم",
      unitId: rm?.unitId || "unit-1",
      unitName: rm?.unitName || "الوحدة",
      roomId,
      roomCode: rm?.code || "RM-01",
      supportedServices: selectedTypes,
      assignedStaff: assignedStaff
        ? assignedStaff.split(",").map((s) => s.trim())
        : ["فريق التمريض الطبي"],
      availabilitySchedule: schedule,
      status: "active",
    };

    onAddServiceLocation(newLoc);
    setShowDrawer(false);
    setName("");
    setCode("");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-007 • نقاط تقديم الرعاية
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            نقاط تقديم الخدمات الطبية (Service Locations)
          </h1>
          <p className="text-xs text-[#64748B]">
            ربط الخدمات الطبية المقدمة للمرضى بالمواقع المكانية والغرف والكوادر المعتمدة ومواعيد تقديمها.
          </p>
        </div>

        <button
          onClick={() => setShowDrawer(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF] shadow-xs"
        >
          <Plus className="w-4 h-4" /> إضافة نقطة خدمة طبية
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-3.5 h-3.5 text-[#94A3B8] absolute right-3 top-2.5" />
          <input
            type="text"
            placeholder="بحث باسم النقطة، القسم، الغرفة أو الكود..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-xs pr-8 pl-3 py-2 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-bold text-[#64748B] shrink-0">نوع الخدمة:</label>
          <select
            value={selectedTypeFilter}
            onChange={(e) => setSelectedTypeFilter(e.target.value)}
            className="text-xs p-2 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
          >
            <option value="all">كافة أنواع الخدمات</option>
            {SERVICE_TYPE_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Service Locations Table */}
      <div className="rounded-xl border border-[#E2E8F0] bg-white overflow-hidden shadow-2xs">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-[#F8FAFC] text-[#475569] font-bold border-b border-[#E2E8F0]">
              <tr>
                <th className="py-3 px-4">نقطة الخدمة والكود</th>
                <th className="py-3 px-4">القسم والغرفة</th>
                <th className="py-3 px-4">أنواع الخدمات الطبية</th>
                <th className="py-3 px-4">أوقات التقديم والجدول</th>
                <th className="py-3 px-4">الكوادر المعينة</th>
                <th className="py-3 px-4">الحالة</th>
                <th className="py-3 px-4 text-center">إجراءات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {filtered.map((loc) => (
                <tr key={loc.id} className="hover:bg-[#F8FAFC]/80 transition-colors">
                  <td className="py-3 px-4">
                    <div className="font-bold text-[#0F172A]">{loc.name}</div>
                    <div className="text-[11px] font-mono text-[#64748B]">{loc.code}</div>
                  </td>
                  <td className="py-3 px-4">
                    <div className="font-medium text-[#0F172A]">{loc.departmentName}</div>
                    <div className="text-[11px] font-mono text-teal-700">غرفة: {loc.roomCode}</div>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {loc.supportedServices.map((svc) => (
                        <span
                          key={svc}
                          className="px-2 py-0.5 rounded bg-blue-50 text-blue-800 text-[10px] font-medium border border-blue-100"
                        >
                          {svc}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-[#475569]">{loc.availabilitySchedule}</td>
                  <td className="py-3 px-4 text-[#475569]">
                    {loc.assignedStaff.slice(0, 2).join("، ")}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        loc.status === "active"
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}
                    >
                      {loc.status === "active" ? "مفعل وجاهز" : "معطل مؤقتاً"}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <button
                      onClick={() => setSelectedLocation(loc)}
                      className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-[#F1F5F9] text-[#1E3A8A] hover:bg-[#E2E8F0]"
                    >
                      تفاصيل النقطة
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─── DRAWER 1: CREATE SERVICE LOCATION ───────────────────────────── */}
      {showDrawer && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/40">
          <div className="w-full max-w-lg h-full bg-white p-6 shadow-2xl space-y-4 overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-base text-[#0F172A] flex items-center gap-2">
                <MapPin className="w-5 h-5 text-[#1E3A8A]" /> إضافة نقطة تقديم خدمة طبية
              </h3>
              <button onClick={() => setShowDrawer(false)} className="text-[#64748B] hover:text-[#0F172A]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-[#334155] block mb-1">اسم نقطة الخدمة بالعربية *</label>
                <input
                  type="text"
                  placeholder="مثال: محطة الفحص بالموجات الصوتية 1"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  required
                />
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">الرمز الكودي للنقطة *</label>
                <input
                  type="text"
                  placeholder="e.g. SL-ECHO-01"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">المنشأة</label>
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
                  <label className="font-bold text-[#334155] block mb-1">القسم المستضيف</label>
                  <select
                    value={departmentId}
                    onChange={(e) => setDepartmentId(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">الغرفة المخصصة</label>
                <select
                  value={roomId}
                  onChange={(e) => setRoomId(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                >
                  {rooms.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.code} — {r.name} ({r.unitName})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-2">أنواع الرعاية المقدمة في هذه النقطة</label>
                <div className="grid grid-cols-2 gap-2">
                  {SERVICE_TYPE_OPTIONS.map((opt) => (
                    <label
                      key={opt.id}
                      className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer text-xs ${
                        selectedTypes.includes(opt.id)
                          ? "border-[#1E3A8A] bg-blue-50 text-[#1E3A8A] font-bold"
                          : "border-[#E2E8F0] text-[#475569]"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedTypes.includes(opt.id)}
                        onChange={() => toggleType(opt.id)}
                        className="rounded text-[#1E3A8A]"
                      />
                      <span>{opt.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">مواعيد التقديم والجدول</label>
                <input
                  type="text"
                  value={schedule}
                  onChange={(e) => setSchedule(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">الكوادر والمسؤولين (مفصولة بفواصل)</label>
                <input
                  type="text"
                  placeholder="أ.د. شريف الجمال، مروة عادل (تمريض)"
                  value={assignedStaff}
                  onChange={(e) => setAssignedStaff(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[#F1F5F9] pt-3">
                <button
                  type="button"
                  onClick={() => setShowDrawer(false)}
                  className="px-4 py-2 rounded-lg border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC]"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-[#1E3A8A] text-white font-bold hover:bg-[#1E40AF]"
                >
                  حفظ وتأكيد النقطة
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── DRAWER 2: DETAILS INSPECTION ─────────────────────────────────── */}
      {selectedLocation && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/40">
          <div className="w-full max-w-md h-full bg-white p-6 shadow-2xl space-y-4 overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <div>
                <h3 className="font-bold text-base text-[#0F172A]">{selectedLocation.name}</h3>
                <span className="text-xs font-mono text-[#64748B]">{selectedLocation.code}</span>
              </div>
              <button onClick={() => setSelectedLocation(null)} className="text-[#64748B] hover:text-[#0F172A]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-3 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0] space-y-2">
                <div className="flex justify-between">
                  <span className="text-[#64748B]">المنشأة:</span>
                  <span className="font-bold text-[#0F172A]">{selectedLocation.facilityName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748B]">القسم:</span>
                  <span className="font-semibold text-[#0F172A]">{selectedLocation.departmentName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748B]">الغرفة المعتمدة:</span>
                  <span className="font-mono font-bold text-[#1E3A8A]">{selectedLocation.roomCode}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748B]">جدول التقديم:</span>
                  <span className="text-[#0F172A]">{selectedLocation.availabilitySchedule}</span>
                </div>
              </div>

              <div>
                <span className="font-bold text-[#0F172A] block mb-2">أنواع الرعاية الطبية المقدمة:</span>
                <div className="flex flex-wrap gap-1">
                  {selectedLocation.supportedServices.map((s) => (
                    <span key={s} className="px-2 py-1 rounded bg-teal-50 text-teal-800 font-semibold border border-teal-200">
                      {s}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <span className="font-bold text-[#0F172A] block mb-2">الكوادر الطبية والفنية المعينة:</span>
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0] space-y-1">
                  {selectedLocation.assignedStaff.map((st) => (
                    <div key={st} className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-teal-600" />
                      <span>{st}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-[#E2E8F0] flex gap-2">
                <button
                  onClick={() => {
                    const newSt = selectedLocation.status === "active" ? "temporarily_closed" : "active";
                    onUpdateStatus(selectedLocation.id, newSt);
                    setSelectedLocation({ ...selectedLocation, status: newSt });
                  }}
                  className={`flex-1 py-2 rounded-lg text-xs font-bold text-center ${
                    selectedLocation.status === "active"
                      ? "bg-amber-100 text-amber-800 hover:bg-amber-200"
                      : "bg-emerald-600 text-white hover:bg-emerald-700"
                  }`}
                >
                  {selectedLocation.status === "active" ? "تعطيل مؤقت للنقطة" : "إعادة التفعيل"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
