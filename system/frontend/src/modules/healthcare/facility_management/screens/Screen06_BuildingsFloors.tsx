import { useState } from "react";
import {
  Layers, Building2, Plus, Search, ChevronRight,
  DoorOpen, GitFork, X
} from "lucide-react";
import { BuildingItem, FloorItem, HealthcareFacilityItem, DepartmentItem, RoomItem } from "../types";

interface BuildingsFloorsProps {
  buildings: BuildingItem[];
  facilities: HealthcareFacilityItem[];
  departments: DepartmentItem[];
  rooms: RoomItem[];
  currentFacilityId: string | "all";
  onAddBuilding: (b: BuildingItem) => void;
  onAddFloor: (buildingId: string, f: FloorItem) => void;
}

export default function Screen06_BuildingsFloors({
  buildings,
  facilities,
  departments,
  rooms,
  currentFacilityId,
  onAddBuilding,
  onAddFloor,
}: BuildingsFloorsProps) {
  const [selectedBuildingId, setSelectedBuildingId] = useState<string>(
    buildings[0]?.id || ""
  );
  const [selectedFloorId, setSelectedFloorId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddBuildingModal, setShowAddBuildingModal] = useState(false);
  const [showAddFloorModal, setShowAddFloorModal] = useState(false);

  // New building form state
  const [newBldName, setNewBldName] = useState("");
  const [newBldNameEn, setNewBldNameEn] = useState("");
  const [newBldCode, setNewBldCode] = useState("");
  const [newBldFacilityId, setNewBldFacilityId] = useState(
    currentFacilityId !== "all" ? currentFacilityId : facilities[0]?.id || ""
  );
  const [newBldLocation, setNewBldLocation] = useState("");
  const [newBldManager, setNewBldManager] = useState("");

  // New floor form state
  const [newFlNumber, setNewFlNumber] = useState<number>(1);
  const [newFlName, setNewFlName] = useState("");
  const [newFlNameEn, setNewFlNameEn] = useState("");

  // Filter buildings by facility
  const filteredBuildings = buildings.filter((b) => {
    const matchFacility = currentFacilityId === "all" || b.facilityId === currentFacilityId;
    const matchQ =
      !searchQuery ||
      b.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      b.code.toLowerCase().includes(searchQuery.toLowerCase());
    return matchFacility && matchQ;
  });

  const activeBuilding =
    buildings.find((b) => b.id === selectedBuildingId) || filteredBuildings[0];

  const activeFloor = activeBuilding?.floors.find((f) => f.id === selectedFloorId) || null;

  // Departments on active floor / building
  const floorDepts = departments.filter((d) =>
    activeFloor ? d.floorId === activeFloor.id : d.buildingId === activeBuilding?.id
  );

  // Rooms on active floor / building
  const floorRooms = rooms.filter((r) =>
    activeFloor ? r.floorId === activeFloor.id : false
  );

  const handleCreateBuilding = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBldName || !newBldCode) return;
    const bld: BuildingItem = {
      id: `bld-${Date.now()}`,
      facilityId: newBldFacilityId,
      code: newBldCode.toUpperCase(),
      name: newBldName,
      nameEn: newBldNameEn || newBldName,
      floorsCount: 0,
      locationWithinFacility: newBldLocation || "الحرم الرئيسي",
      managerName: newBldManager || "مدير العمليات",
      status: "active",
      floors: [],
    };
    onAddBuilding(bld);
    setSelectedBuildingId(bld.id);
    setSelectedFloorId(null);
    setShowAddBuildingModal(false);
    setNewBldName("");
    setNewBldCode("");
  };

  const handleCreateFloor = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBuilding || !newFlName) return;
    const fl: FloorItem = {
      id: `fl-${Date.now()}`,
      buildingId: activeBuilding.id,
      facilityId: activeBuilding.facilityId,
      floorNumber: newFlNumber,
      name: newFlName,
      nameEn: newFlNameEn || newFlName,
      departmentsCount: 0,
      unitsCount: 0,
      roomsCount: 0,
      status: "active",
    };
    onAddFloor(activeBuilding.id, fl);
    setSelectedFloorId(fl.id);
    setShowAddFloorModal(false);
    setNewFlName("");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-003 • البنية المعمارية
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            إدارة المباني والأجنحة والطوابق
          </h1>
          <p className="text-xs text-[#64748B]">
            تنظيم وتخطيط الهيكل المعماري للمستشفيات، توزيع الطوابق، وتوزيع الأقسام الطبية على المستويات.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddBuildingModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF] shadow-xs"
          >
            <Plus className="w-4 h-4" /> إضافة مبنى أو برج جديد
          </button>
        </div>
      </div>

      {/* Two-Panel Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT PANEL: Building & Floors Tree (4 Cols) */}
        <div className="lg:col-span-4 rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#1E3A8A]" /> شجرة المباني والمستويات
            </h2>
            <span className="text-xs font-mono font-medium text-[#64748B] bg-[#F1F5F9] px-2 py-0.5 rounded">
              {filteredBuildings.length} مبنى
            </span>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[#94A3B8] absolute right-3 top-2.5" />
            <input
              type="text"
              placeholder="بحث في أسماء المباني..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs pr-8 pl-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:border-[#1E3A8A]"
            />
          </div>

          {/* Tree View */}
          <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
            {filteredBuildings.map((bld) => {
              const isSelectedBuilding = activeBuilding?.id === bld.id;
              return (
                <div
                  key={bld.id}
                  className={`rounded-lg border transition-all ${
                    isSelectedBuilding
                      ? "border-[#1E3A8A] bg-blue-50/20"
                      : "border-[#E2E8F0] bg-white hover:border-[#CBD5E1]"
                  }`}
                >
                  {/* Building Header Item */}
                  <div
                    onClick={() => {
                      setSelectedBuildingId(bld.id);
                      setSelectedFloorId(null);
                    }}
                    className={`flex items-center justify-between p-3 cursor-pointer rounded-t-lg ${
                      isSelectedBuilding && !selectedFloorId ? "bg-blue-100/50" : ""
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Building2
                        className={`w-4 h-4 shrink-0 ${
                          isSelectedBuilding ? "text-[#1E3A8A]" : "text-[#64748B]"
                        }`}
                      />
                      <div className="truncate">
                        <div className="text-xs font-bold text-[#0F172A] truncate">{bld.name}</div>
                        <div className="text-[10px] text-[#64748B] font-mono">{bld.code}</div>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-[#475569] bg-[#E2E8F0] px-1.5 py-0.2 rounded">
                      {bld.floors.length} طابق
                    </span>
                  </div>

                  {/* Floors Sub-list */}
                  {bld.floors.length > 0 && (
                    <div className="border-t border-[#F1F5F9] px-2 py-1.5 space-y-1 bg-[#F8FAFC]/50">
                      {bld.floors.map((fl) => {
                        const isSelectedFloor = selectedFloorId === fl.id;
                        return (
                          <div
                            key={fl.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedBuildingId(bld.id);
                              setSelectedFloorId(fl.id);
                            }}
                            className={`flex items-center justify-between px-2.5 py-1.5 rounded cursor-pointer text-xs transition-colors ${
                              isSelectedFloor
                                ? "bg-[#1E3A8A] text-white font-semibold"
                                : "text-[#475569] hover:bg-white"
                            }`}
                          >
                            <span className="truncate">{fl.name}</span>
                            <span
                              className={`text-[10px] font-mono ${
                                isSelectedFloor ? "text-teal-200" : "text-[#64748B]"
                              }`}
                            >
                              الطابق {fl.floorNumber}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT PANEL: Details Inspector (8 Cols) */}
        <div className="lg:col-span-8 space-y-6">
          {activeBuilding ? (
            <div className="space-y-6">
              {/* Inspection Card Header */}
              <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="p-3 rounded-xl bg-blue-50 text-[#1E3A8A] border border-blue-200">
                      {activeFloor ? <Layers className="w-6 h-6" /> : <Building2 className="w-6 h-6" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-bold text-[#0F172A]">
                          {activeFloor ? `${activeFloor.name} — ${activeBuilding.name}` : activeBuilding.name}
                        </h2>
                        <span className="font-mono text-xs text-[#64748B] px-1.5 py-0.5 rounded bg-[#F1F5F9]">
                          {activeFloor ? `FL-${activeFloor.floorNumber}` : activeBuilding.code}
                        </span>
                      </div>
                      <p className="text-xs text-[#64748B] mt-0.5">
                        {activeFloor
                          ? `طابق مخصص للخدمات الطبية والتنويم • الحالة: ${activeFloor.status}`
                          : `الموقع: ${activeBuilding.locationWithinFacility} • مسؤول الصيانة: ${activeBuilding.managerName}`}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {!activeFloor && (
                      <button
                        onClick={() => setShowAddFloorModal(true)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF]"
                      >
                        <Plus className="w-3.5 h-3.5" /> إضافة طابق للمبنى
                      </button>
                    )}
                    {activeFloor && (
                      <button
                        onClick={() => setSelectedFloorId(null)}
                        className="px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-xs font-medium text-[#475569] hover:bg-[#F8FAFC]"
                      >
                        عرض كامل المبنى
                      </button>
                    )}
                  </div>
                </div>

                {/* Metrics bar */}
                <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-[#F1F5F9] text-center text-xs">
                  <div className="p-2 rounded-lg bg-[#F8FAFC]">
                    <span className="text-[#64748B] block text-[11px]">الطوابق</span>
                    <span className="font-mono font-bold text-[#0F172A]">{activeBuilding.floors.length}</span>
                  </div>
                  <div className="p-2 rounded-lg bg-[#F8FAFC]">
                    <span className="text-[#64748B] block text-[11px]">الأقسام المشغولة</span>
                    <span className="font-mono font-bold text-[#0F172A]">{floorDepts.length}</span>
                  </div>
                  <div className="p-2 rounded-lg bg-[#F8FAFC]">
                    <span className="text-[#64748B] block text-[11px]">الغرف السريرية</span>
                    <span className="font-mono font-bold text-[#0F172A]">
                      {activeFloor ? floorRooms.length : 32}
                    </span>
                  </div>
                </div>
              </div>

              {/* Floor Plan Schematic Placeholder */}
              <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-sm text-[#0F172A]">
                    {activeFloor ? `المخطط الهيكلي: ${activeFloor.name}` : "التوزيع المعماري للمبنى"}
                  </h3>
                  <span className="text-[10px] text-teal-700 bg-teal-50 px-2 py-0.5 rounded font-semibold border border-teal-200">
                    Schematic Layout V2
                  </span>
                </div>

                {activeFloor ? (
                  <div className="p-6 rounded-xl border border-dashed border-[#CBD5E1] bg-[#F8FAFC] flex flex-col items-center justify-center text-center space-y-2 min-h-[160px]">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#1E3A8A]">
                      <DoorOpen className="w-5 h-5 text-teal-600" />
                      <span>خريطة الأجنحة والغرف المسجلة في الطابق ({floorRooms.length} غرفة مفعلة)</span>
                    </div>
                    <div className="flex flex-wrap gap-2 justify-center max-w-lg mt-2">
                      {floorRooms.map((rm) => (
                        <div
                          key={rm.id}
                          className="px-2.5 py-1.5 rounded-lg bg-white border border-[#CBD5E1] text-[11px] font-mono text-[#0F172A] shadow-2xs flex items-center gap-1.5"
                        >
                          <span className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span>{rm.code}</span>
                        </div>
                      ))}
                      {floorRooms.length === 0 && (
                        <p className="text-xs text-[#64748B]">
                          لا توجد غرف مسجلة في هذا الطابق حالياً. يمكنك ربط الغرف من شاشة الوحدات والغرف.
                        </p>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {activeBuilding.floors.map((fl) => (
                      <div
                        key={fl.id}
                        onClick={() => setSelectedFloorId(fl.id)}
                        className="p-3 rounded-lg border border-[#E2E8F0] hover:border-[#1E3A8A] cursor-pointer bg-[#F8FAFC] transition-colors flex items-center justify-between"
                      >
                        <div>
                          <div className="text-xs font-bold text-[#0F172A]">{fl.name}</div>
                          <div className="text-[10px] text-[#64748B]">
                            {fl.departmentsCount} أقسام • {fl.roomsCount} غرفة
                          </div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-[#94A3B8]" />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Housed Departments Table */}
              <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-3">
                <h3 className="font-bold text-sm text-[#0F172A] flex items-center gap-2">
                  <GitFork className="w-4 h-4 text-[#1E3A8A]" />
                  الأقسام الطبية والإدارية المستضافة ({floorDepts.length})
                </h3>

                <div className="overflow-x-auto">
                  <table className="w-full text-right text-xs">
                    <thead className="bg-[#F8FAFC] text-[#475569] font-bold border-b border-[#E2E8F0]">
                      <tr>
                        <th className="py-2 px-3">القسم</th>
                        <th className="py-2 px-3">الكود</th>
                        <th className="py-2 px-3">التصنيف</th>
                        <th className="py-2 px-3">رئيس القسم</th>
                        <th className="py-2 px-3">الوحدات التابعة</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E2E8F0]">
                      {floorDepts.map((d) => (
                        <tr key={d.id} className="hover:bg-[#F8FAFC]">
                          <td className="py-2.5 px-3 font-semibold text-[#0F172A]">{d.name}</td>
                          <td className="py-2.5 px-3 font-mono text-[#64748B]">{d.code}</td>
                          <td className="py-2.5 px-3 text-[#1E3A8A] font-medium">{d.category}</td>
                          <td className="py-2.5 px-3 text-[#334155]">{d.managerName}</td>
                          <td className="py-2.5 px-3 font-mono text-[#64748B]">{d.unitsCount} وحدات</td>
                        </tr>
                      ))}
                      {floorDepts.length === 0 && (
                        <tr>
                          <td colSpan={5} className="py-4 text-center text-xs text-[#94A3B8]">
                            لا توجد أقسام مسجلة في هذا النطاق حالياً.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center text-[#64748B] bg-white rounded-xl border border-[#E2E8F0]">
              يرجى اختيار مبنى من القائمة أو إضافة مبنى جديد.
            </div>
          )}
        </div>
      </div>

      {/* ─── MODAL 1: ADD BUILDING ───────────────────────────────────────── */}
      {showAddBuildingModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-base text-[#0F172A] flex items-center gap-2">
                <Building2 className="w-5 h-5 text-[#1E3A8A]" /> إضافة مبنى أو برج طبي جديد
              </h3>
              <button
                onClick={() => setShowAddBuildingModal(false)}
                className="text-[#64748B] hover:text-[#0F172A]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateBuilding} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-[#334155] block mb-1">اسم المبنى بالعربية *</label>
                <input
                  type="text"
                  placeholder="مثال: برج الجراحة والأورام"
                  value={newBldName}
                  onChange={(e) => setNewBldName(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  required
                />
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">اسم المبنى بالإنجليزية</label>
                <input
                  type="text"
                  placeholder="e.g. Surgical & Oncology Tower"
                  value={newBldNameEn}
                  onChange={(e) => setNewBldNameEn(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  dir="ltr"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">رمز المبنى الكودي *</label>
                  <input
                    type="text"
                    placeholder="e.g. BLD-SURG"
                    value={newBldCode}
                    onChange={(e) => setNewBldCode(e.target.value)}
                    className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">المنشأة التابع لها</label>
                  <select
                    value={newBldFacilityId}
                    onChange={(e) => setNewBldFacilityId(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    {facilities.map((fac) => (
                      <option key={fac.id} value={fac.id}>
                        {fac.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">الموقع داخل الحرم الطبي</label>
                <input
                  type="text"
                  placeholder="مثال: الجناح الغربي، متصل بمبنى العيادات عبر جسر الطابق الثاني"
                  value={newBldLocation}
                  onChange={(e) => setNewBldLocation(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">مسؤول الصيانة والتشغيل للمبنى</label>
                <input
                  type="text"
                  placeholder="م. أحمد الشريف"
                  value={newBldManager}
                  onChange={(e) => setNewBldManager(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[#F1F5F9] pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddBuildingModal(false)}
                  className="px-4 py-2 rounded-lg border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC]"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-[#1E3A8A] text-white font-bold hover:bg-[#1E40AF]"
                >
                  حفظ المبنى
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL 2: ADD FLOOR ─────────────────────────────────────────── */}
      {showAddFloorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-base text-[#0F172A] flex items-center gap-2">
                <Layers className="w-5 h-5 text-[#1E3A8A]" /> إضافة طابق إلى: {activeBuilding?.name}
              </h3>
              <button
                onClick={() => setShowAddFloorModal(false)}
                className="text-[#64748B] hover:text-[#0F172A]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateFloor} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">رقم الطابق (Floor Number)</label>
                  <input
                    type="number"
                    value={newFlNumber}
                    onChange={(e) => setNewFlNumber(parseInt(e.target.value) || 0)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  />
                  <p className="text-[10px] text-[#64748B] mt-0.5">0 = الأرضي، -1 = البدروم</p>
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">اسم الطابق بالعربية *</label>
                  <input
                    type="text"
                    placeholder="مثال: الطابق الثاني - جناح العمليات"
                    value={newFlName}
                    onChange={(e) => setNewFlName(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">اسم الطابق بالإنجليزية</label>
                <input
                  type="text"
                  placeholder="e.g. 2nd Floor - Surgical Ward"
                  value={newFlNameEn}
                  onChange={(e) => setNewFlNameEn(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  dir="ltr"
                />
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[#F1F5F9] pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddFloorModal(false)}
                  className="px-4 py-2 rounded-lg border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC]"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-[#1E3A8A] text-white font-bold hover:bg-[#1E40AF]"
                >
                  إضافة الطابق
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
