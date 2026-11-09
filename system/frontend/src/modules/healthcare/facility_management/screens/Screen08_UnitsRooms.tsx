import { useState } from "react";
import {
  DoorOpen, Layers, Plus, Search, Info, X
} from "lucide-react";
import {
  UnitItem,
  RoomItem,
  DepartmentItem,
  HealthcareFacilityItem,
  UnitType,
  RoomType,
  RoomAvailabilityStatus
} from "../types";

interface UnitsRoomsProps {
  units: UnitItem[];
  rooms: RoomItem[];
  departments: DepartmentItem[];
  facilities: HealthcareFacilityItem[];
  currentFacilityId: string | "all";
  onAddUnit: (unit: UnitItem) => void;
  onAddRoom: (room: RoomItem) => void;
  onUpdateRoomStatus: (roomId: string, status: RoomAvailabilityStatus) => void;
}

export default function Screen08_UnitsRooms({
  units,
  rooms,
  departments,
  facilities,
  currentFacilityId,
  onAddUnit,
  onAddRoom,
  onUpdateRoomStatus,
}: UnitsRoomsProps) {
  const [selectedUnitId, setSelectedUnitId] = useState<string>("all");
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showAddRoomModal, setShowAddRoomModal] = useState(false);
  const [showAddUnitModal, setShowAddUnitModal] = useState(false);

  // New Room Form State
  const [newRoomCode, setNewRoomCode] = useState("");
  const [newRoomName, setNewRoomName] = useState("");
  const [newRoomType, setNewRoomType] = useState<RoomType>("consultation_room");
  const [newRoomUnitId, setNewRoomUnitId] = useState(units[0]?.id || "");
  const [newRoomCapacity, setNewRoomCapacity] = useState(1);
  const [newRoomEquipment, setNewRoomEquipment] = useState("");

  // New Unit Form State
  const [newUnitName, setNewUnitName] = useState("");
  const [newUnitCode, setNewUnitCode] = useState("");
  const [newUnitType, setNewUnitType] = useState<UnitType>("outpatient_clinic");
  const [newUnitDeptId, setNewUnitDeptId] = useState(departments[0]?.id || "");
  const [newUnitManager, setNewUnitManager] = useState("");

  // Filtered Units
  const filteredUnits = units.filter((u) => {
    const matchFacility = currentFacilityId === "all" || u.facilityId === currentFacilityId;
    const matchDept = selectedDepartmentId === "all" || u.departmentId === selectedDepartmentId;
    return matchFacility && matchDept;
  });

  // Filtered Rooms
  const filteredRooms = rooms.filter((r) => {
    const matchFacility = currentFacilityId === "all" || r.facilityId === currentFacilityId;
    const matchDept = selectedDepartmentId === "all" || r.departmentId === selectedDepartmentId;
    const matchUnit = selectedUnitId === "all" || r.unitId === selectedUnitId;
    const matchStatus = statusFilter === "all" || r.availability === statusFilter;
    const matchQ =
      !searchQuery ||
      r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.unitName.toLowerCase().includes(searchQuery.toLowerCase());
    return matchFacility && matchDept && matchUnit && matchStatus && matchQ;
  });

  const handleCreateRoom = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRoomCode || !newRoomName) return;

    const unit = units.find((u) => u.id === newRoomUnitId);

    const room: RoomItem = {
      id: `rm-${Date.now()}`,
      facilityId: unit?.facilityId || facilities[0]?.id || "",
      departmentId: unit?.departmentId || departments[0]?.id || "",
      unitId: newRoomUnitId,
      unitName: unit?.name || "الوحدة الطبية",
      floorId: "fl-1",
      code: newRoomCode.toUpperCase(),
      name: newRoomName,
      roomType: newRoomType,
      capacity: newRoomCapacity,
      availability: "available",
      equipmentReferences: newRoomEquipment
        ? newRoomEquipment.split(",").map((s) => s.trim())
        : ["سرير فحص قياسي"],
    };

    onAddRoom(room);
    setShowAddRoomModal(false);
    setNewRoomCode("");
    setNewRoomName("");
    setNewRoomEquipment("");
  };

  const handleCreateUnit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUnitName || !newUnitCode) return;

    const dept = departments.find((d) => d.id === newUnitDeptId);

    const unit: UnitItem = {
      id: `unit-${Date.now()}`,
      facilityId: dept?.facilityId || facilities[0]?.id || "",
      departmentId: newUnitDeptId,
      departmentName: dept?.name || "القسم",
      code: newUnitCode.toUpperCase(),
      name: newUnitName,
      nameEn: newUnitName,
      unitType: newUnitType,
      assignedManager: newUnitManager || "مشرف الوحدة",
      roomsCount: 0,
      status: "active",
    };

    onAddUnit(unit);
    setShowAddUnitModal(false);
    setNewUnitName("");
    setNewUnitCode("");
  };

  const getStatusBadge = (status: RoomAvailabilityStatus) => {
    switch (status) {
      case "available":
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">🟢 متاح للاستخدام</span>;
      case "occupied":
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">🔵 مشغول بمريض</span>;
      case "sanitizing":
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">🟡 قيد التعقيم والتطهير</span>;
      case "maintenance":
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-50 text-purple-700 border border-purple-200">🟣 صيانة دورية</span>;
      case "out_of_service":
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">🔴 خارج الخدمة</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-003 • البنية التحتية للغرف
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            إدارة الوحدات والغرف السريرية
          </h1>
          <p className="text-xs text-[#64748B]">
            تهيئة غرف الكشف، غرف العمليات، مكاتب الاستشارة، ووحدات الرعاية والتشخيص وتجهيزاتها الطبية.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddUnitModal(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[#CBD5E1] bg-white text-xs font-semibold text-[#475569] hover:bg-[#F8FAFC]"
          >
            <Plus className="w-3.5 h-3.5" /> إضافة وحدة
          </button>
          <button
            onClick={() => setShowAddRoomModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF] shadow-xs"
          >
            <Plus className="w-4 h-4" /> إضافة غرفة سريرية
          </button>
        </div>
      </div>

      {/* Important Disclaimer Banner */}
      <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4 flex items-start gap-3 text-xs text-blue-900 shadow-2xs">
        <Info className="w-5 h-5 text-[#1E3A8A] shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <span className="font-bold">تنويه تشغيلي حول إدارة الأسرة وإشغال المرضى:</span>
          {" "}تختص هذه الشاشة بتهيئة البنية المادية للمنشأة (الغرف، التجهيزات، العيادات، غرف العمليات). أما حركة التنويم، إشغال الأسرة اليومي، ونقل المرضى بين الأجنحة فيتم إدارتها عبر موديول{" "}
          <strong className="underline">HLT-08 (Inpatient Bed Management)</strong>.
        </div>
      </div>

      {/* Navigation Cascading Bar (Facility -> Department -> Unit) */}
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-2xs grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
        <div>
          <label className="font-bold text-[#64748B] block mb-1">تصفية حسب القسم</label>
          <select
            value={selectedDepartmentId}
            onChange={(e) => {
              setSelectedDepartmentId(e.target.value);
              setSelectedUnitId("all");
            }}
            className="w-full p-2 rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] focus:outline-none focus:border-[#1E3A8A]"
          >
            <option value="all">جميع الأقسام ({departments.length})</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.code})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="font-bold text-[#64748B] block mb-1">تصفية حسب الوحدة</label>
          <select
            value={selectedUnitId}
            onChange={(e) => setSelectedUnitId(e.target.value)}
            className="w-full p-2 rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] focus:outline-none focus:border-[#1E3A8A]"
          >
            <option value="all">جميع الوحدات ({filteredUnits.length})</option>
            {filteredUnits.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="font-bold text-[#64748B] block mb-1">الحالة التشغيلية</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full p-2 rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] focus:outline-none focus:border-[#1E3A8A]"
          >
            <option value="all">جميع الحالات</option>
            <option value="available">متاح للاستخدام</option>
            <option value="occupied">مشغول</option>
            <option value="sanitizing">قيد التعقيم</option>
            <option value="maintenance">صيانة</option>
            <option value="out_of_service">خارج الخدمة</option>
          </select>
        </div>

        <div>
          <label className="font-bold text-[#64748B] block mb-1">البحث المباشر</label>
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 top-2.5" />
            <input
              type="text"
              placeholder="رقم الغرفة، الاسم..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pr-8 pl-2 py-2 rounded-lg border border-[#CBD5E1] bg-[#F8FAFC] focus:outline-none focus:border-[#1E3A8A]"
            />
          </div>
        </div>
      </div>

      {/* Rooms Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredRooms.map((rm) => (
          <div
            key={rm.id}
            className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs hover:border-[#CBD5E1] transition-all flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-[#1E3A8A] bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                      {rm.code}
                    </span>
                    <h3 className="font-bold text-sm text-[#0F172A]">{rm.name}</h3>
                  </div>
                  <span className="text-[11px] text-[#64748B] mt-1 block">
                    الوحدة: <strong className="text-[#334155]">{rm.unitName}</strong>
                  </span>
                </div>
              </div>

              <div className="my-2">{getStatusBadge(rm.availability)}</div>

              <div className="text-xs text-[#64748B] space-y-1 mt-3">
                <div className="flex items-center justify-between">
                  <span>النوع:</span>
                  <span className="font-semibold text-[#0F172A]">{rm.roomType}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>السعة السريرية:</span>
                  <span className="font-mono font-bold text-[#0F172A]">{rm.capacity} مريض</span>
                </div>
              </div>

              {/* Equipment Tags */}
              <div className="mt-3 pt-3 border-t border-[#F1F5F9]">
                <div className="text-[10px] text-[#64748B] font-bold mb-1.5">الأجهزة والمعدات الثابتة:</div>
                <div className="flex flex-wrap gap-1">
                  {rm.equipmentReferences.map((eq) => (
                    <span
                      key={eq}
                      className="px-2 py-0.5 rounded bg-[#F8FAFC] border border-[#E2E8F0] text-[10px] text-[#475569]"
                    >
                      {eq}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Change Status Fast Actions */}
            <div className="mt-4 pt-3 border-t border-[#E2E8F0] flex items-center justify-between text-xs">
              <span className="text-[11px] text-[#64748B]">تغيير الحالة:</span>
              <div className="flex gap-1">
                {rm.availability !== "available" && (
                  <button
                    onClick={() => onUpdateRoomStatus(rm.id, "available")}
                    className="px-2 py-1 rounded bg-emerald-50 text-emerald-800 text-[10px] font-bold hover:bg-emerald-100"
                    title="تفريغ وإتاحة"
                  >
                    متاح
                  </button>
                )}
                {rm.availability !== "sanitizing" && (
                  <button
                    onClick={() => onUpdateRoomStatus(rm.id, "sanitizing")}
                    className="px-2 py-1 rounded bg-amber-50 text-amber-800 text-[10px] font-bold hover:bg-amber-100"
                    title="تحويل للتعقيم"
                  >
                    تعقيم
                  </button>
                )}
                {rm.availability !== "maintenance" && (
                  <button
                    onClick={() => onUpdateRoomStatus(rm.id, "maintenance")}
                    className="px-2 py-1 rounded bg-purple-50 text-purple-800 text-[10px] font-bold hover:bg-purple-100"
                    title="تحويل للصيانة"
                  >
                    صيانة
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredRooms.length === 0 && (
        <div className="p-12 text-center text-[#64748B] bg-white rounded-xl border border-[#E2E8F0]">
          لا توجد غرف تطابق معايير التصفية الحالية.
        </div>
      )}

      {/* ─── MODAL 1: CREATE ROOM ───────────────────────────────────────── */}
      {showAddRoomModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-base text-[#0F172A] flex items-center gap-2">
                <DoorOpen className="w-5 h-5 text-[#1E3A8A]" /> إضافة غرفة سريرية أو عيادة فحص
              </h3>
              <button onClick={() => setShowAddRoomModal(false)} className="text-[#64748B] hover:text-[#0F172A]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateRoom} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">رقم/رمز الغرفة الكودي *</label>
                  <input
                    type="text"
                    placeholder="e.g. RM-101"
                    value={newRoomCode}
                    onChange={(e) => setNewRoomCode(e.target.value)}
                    className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">اسم الغرفة الرسمي *</label>
                  <input
                    type="text"
                    placeholder="عيادة استشارة القلب 1"
                    value={newRoomName}
                    onChange={(e) => setNewRoomName(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">نوع الغرفة</label>
                  <select
                    value={newRoomType}
                    onChange={(e) => setNewRoomType(e.target.value as RoomType)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    <option value="consultation_room">غرفة كشف واستشارة (Consultation)</option>
                    <option value="procedure_room">غرفة إجراءات وتدخلات (Procedure)</option>
                    <option value="operating_theatre">غرفة عمليات جراحية (OR)</option>
                    <option value="recovery_room">غرفة إفاقة وملاحظة (Recovery)</option>
                    <option value="blood_draw_station">محطة سحب عينات (Blood Draw)</option>
                    <option value="ultrasound_room">غرفة موجات صوتية (Ultrasound)</option>
                    <option value="mri_suite">جناح رنين مغناطيسي (MRI)</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-[#334155] block mb-1">الوحدة التابعة لها</label>
                  <select
                    value={newRoomUnitId}
                    onChange={(e) => setNewRoomUnitId(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    {units.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name} ({u.departmentName})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">السعة السريرية (المرضى)</label>
                  <input
                    type="number"
                    value={newRoomCapacity}
                    onChange={(e) => setNewRoomCapacity(parseInt(e.target.value) || 1)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    min={1}
                  />
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">الأجهزة والمعدات الملحقة</label>
                  <input
                    type="text"
                    placeholder="ECG، سرير فحص..."
                    value={newRoomEquipment}
                    onChange={(e) => setNewRoomEquipment(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[#F1F5F9] pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddRoomModal(false)}
                  className="px-4 py-2 rounded-lg border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC]"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-[#1E3A8A] text-white font-bold hover:bg-[#1E40AF]"
                >
                  حفظ الغرفة
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL 2: CREATE UNIT ───────────────────────────────────────── */}
      {showAddUnitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-base text-[#0F172A] flex items-center gap-2">
                <Layers className="w-5 h-5 text-[#1E3A8A]" /> إضافة وحدة تخصصية جديدة
              </h3>
              <button onClick={() => setShowAddUnitModal(false)} className="text-[#64748B] hover:text-[#0F172A]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateUnit} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-[#334155] block mb-1">اسم الوحدة بالعربية *</label>
                <input
                  type="text"
                  placeholder="مثال: وحدة قسطرة القلب ورعاية الحالات الحرجة"
                  value={newUnitName}
                  onChange={(e) => setNewUnitName(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">رمز الوحدة الكودي *</label>
                  <input
                    type="text"
                    placeholder="e.g. UNT-CATH"
                    value={newUnitCode}
                    onChange={(e) => setNewUnitCode(e.target.value)}
                    className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">نوع الوحدة</label>
                  <select
                    value={newUnitType}
                    onChange={(e) => setNewUnitType(e.target.value as UnitType)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                  >
                    <option value="outpatient_clinic">عيادات خارجية</option>
                    <option value="inpatient_ward">جناح تنويم</option>
                    <option value="icu_ccu">عناية مركزة ICU</option>
                    <option value="day_surgery">جراحة اليوم الواحد</option>
                    <option value="imaging_suite">أجنحة الأشعة</option>
                    <option value="laboratory_section">أقسام المختبر</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">القسم التابع له</label>
                <select
                  value={newUnitDeptId}
                  onChange={(e) => setNewUnitDeptId(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                >
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.facilityName})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">مشرف الوحدة المسؤول</label>
                <input
                  type="text"
                  placeholder="د. مصطفى الشناوي"
                  value={newUnitManager}
                  onChange={(e) => setNewUnitManager(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[#F1F5F9] pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddUnitModal(false)}
                  className="px-4 py-2 rounded-lg border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC]"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-[#1E3A8A] text-white font-bold hover:bg-[#1E40AF]"
                >
                  إضافة الوحدة
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
