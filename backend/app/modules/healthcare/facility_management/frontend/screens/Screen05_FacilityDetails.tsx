import { useState } from "react";
import {
  Hospital, Building2, MapPin, Clock, Layers, GitFork,
  DoorOpen, Stethoscope, Users, Settings, Activity, Edit3, ArrowLeft,
  CheckCircle2, ShieldCheck, ChevronRight, Calendar, Plus
} from "lucide-react";
import {
  HealthcareFacilityItem,
  HealthcareOrganization,
  BuildingItem,
  DepartmentItem,
  UnitItem,
  RoomItem,
  ServiceLocationItem,
  FacilityActivityLogItem
} from "../types";

interface FacilityDetailsProps {
  facility: HealthcareFacilityItem;
  organization: HealthcareOrganization;
  buildings: BuildingItem[];
  departments: DepartmentItem[];
  units: UnitItem[];
  rooms: RoomItem[];
  serviceLocations: ServiceLocationItem[];
  activityLogs: FacilityActivityLogItem[];
  onNavigate: (screenId: string) => void;
  onEditFacility: (facility: HealthcareFacilityItem) => void;
  onBackToFacilities: () => void;
}

type TabKey =
  | "overview"
  | "departments"
  | "buildings"
  | "units_rooms"
  | "services"
  | "operating_hours"
  | "staff"
  | "settings"
  | "activity";

export default function Screen05_FacilityDetails({
  facility,
  organization,
  buildings,
  departments,
  units,
  rooms,
  serviceLocations,
  activityLogs,
  onNavigate,
  onEditFacility,
  onBackToFacilities,
}: FacilityDetailsProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  // Facility-scoped items
  const facBuildings = buildings.filter((b) => b.facilityId === facility.id);
  const facDepartments = departments.filter((d) => d.facilityId === facility.id);
  const facUnits = units.filter((u) => u.facilityId === facility.id);
  const facRooms = rooms.filter((r) => r.facilityId === facility.id);
  const facLocations = serviceLocations.filter((s) => s.facilityId === facility.id);
  const facLogs = activityLogs.filter((l) => l.facilityId === facility.id);

  const TABS = [
    { id: "overview", label: "نظرة عامة", labelEn: "Overview", icon: Building2 },
    { id: "departments", label: `الأقسام (${facDepartments.length})`, labelEn: "Departments", icon: GitFork },
    { id: "buildings", label: `المباني (${facBuildings.length})`, labelEn: "Buildings", icon: Layers },
    { id: "units_rooms", label: `الوحدات والغرف (${facUnits.length} وحدة • ${facRooms.length} غرفة)`, labelEn: "Units & Rooms", icon: DoorOpen },
    { id: "services", label: `الخدمات الطبية (${facLocations.length})`, labelEn: "Services", icon: Stethoscope },
    { id: "operating_hours", label: "ساعات العمل", labelEn: "Hours", icon: Clock },
    { id: "staff", label: `الكوادر المعينة (${facility.stats.staffCount})`, labelEn: "Staff", icon: Users },
    { id: "settings", label: "إعدادات المنشأة", labelEn: "Settings", icon: Settings },
    { id: "activity", label: `سجل العمليات (${facLogs.length})`, labelEn: "Activity", icon: Activity },
  ];

  return (
    <div className="space-y-6">
      {/* Back Button & Breadcrumb */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBackToFacilities}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#1E3A8A] hover:underline"
        >
          <ArrowLeft className="w-4 h-4" /> العودة إلى قائمة المنشآت
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onEditFacility(facility)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-xs font-medium text-[#475569] hover:bg-[#F8FAFC]"
          >
            <Edit3 className="w-3.5 h-3.5" /> تعديل بيانات المنشأة
          </button>
          <button
            onClick={() => onNavigate("operating_hours")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF]"
          >
            <Calendar className="w-3.5 h-3.5" /> ضبط الجداول والمناوبات
          </button>
        </div>
      </div>

      {/* Hero Header Card */}
      <div className="rounded-2xl border border-[#E2E8F0] bg-white p-6 shadow-2xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-[#0A2540] to-[#1E3A8A] flex items-center justify-center text-teal-300 font-bold text-2xl shadow-sm shrink-0">
              <Hospital className="w-8 h-8" />
            </div>

            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-bold text-[#0F172A]">{facility.name}</h1>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#F1F5F9] text-[#475569] font-medium">
                  {facility.code}
                </span>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-bold ${
                    facility.status === "active"
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-amber-50 text-amber-700 border border-amber-200"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-current ml-1.5" />
                  {facility.status === "active" ? "منشأة نشطة ومفعلة" : "قيد التجهيز"}
                </span>
                {facility.operations.is24HoursEmergency && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                    🚑 طوارئ 24/7
                  </span>
                )}
              </div>

              <div className="text-xs text-[#64748B] flex flex-wrap items-center gap-3">
                <span className="font-medium text-[#334155]">{facility.nameEn}</span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-[#94A3B8]" />
                  {facility.location.governorate}، {facility.location.city} — {facility.location.address}
                </span>
                <span>•</span>
                <span className="text-teal-700 font-semibold">{organization.displayName}</span>
              </div>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 shrink-0">
            <div className="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] text-center min-w-[90px]">
              <div className="text-[10px] text-[#64748B] font-medium">المباني</div>
              <div className="text-lg font-mono font-bold text-[#0F172A]">{facility.stats.buildingCount}</div>
            </div>
            <div className="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] text-center min-w-[90px]">
              <div className="text-[10px] text-[#64748B] font-medium">الأقسام</div>
              <div className="text-lg font-mono font-bold text-[#0F172A]">{facility.stats.departmentCount}</div>
            </div>
            <div className="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] text-center min-w-[90px]">
              <div className="text-[10px] text-[#64748B] font-medium">الغرف</div>
              <div className="text-lg font-mono font-bold text-[#0F172A]">{facility.stats.roomCount}</div>
            </div>
            <div className="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] text-center min-w-[90px]">
              <div className="text-[10px] text-[#64748B] font-medium">الكادر الطبي</div>
              <div className="text-lg font-mono font-bold text-[#0F172A]">{facility.stats.staffCount}</div>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 overflow-x-auto border-t border-[#E2E8F0] mt-6 pt-3">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabKey)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                  isActive
                    ? "bg-[#1E3A8A] text-white shadow-xs"
                    : "text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9]"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-teal-300" : "text-[#94A3B8]"}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── TAB 1: OVERVIEW ─────────────────────────────────────────── */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Description */}
            <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-3">
              <h3 className="font-bold text-sm text-[#0F172A] flex items-center gap-2">
                <Building2 className="w-4 h-4 text-[#1E3A8A]" /> نبذة عن المنشأة والقدرات التشغيلية
              </h3>
              <p className="text-xs text-[#475569] leading-relaxed">
                {facility.description || "لم يتم إدخال وصف تفصيلي بعد."}
              </p>
            </div>

            {/* Operating Hours Summary */}
            <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-3">
              <h3 className="font-bold text-sm text-[#0F172A] flex items-center gap-2">
                <Clock className="w-4 h-4 text-[#1E3A8A]" /> جدول العمل ومواعيد الاستقبال
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]">
                  <span className="text-[#64748B] block text-[11px] mb-1">الساعات القياسية للعيادات</span>
                  <span className="font-semibold text-[#0F172A]">{facility.operations.standardHours}</span>
                </div>
                <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]">
                  <span className="text-[#64748B] block text-[11px] mb-1">أيام العمل المعتمدة</span>
                  <span className="font-semibold text-[#0F172A]">{facility.operations.workingDays.join("، ")}</span>
                </div>
              </div>
            </div>

            {/* Accreditation details */}
            <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-3">
              <h3 className="font-bold text-sm text-[#0F172A] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" /> التراخيص والاعتمادات الصحية
              </h3>
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between p-3 rounded-lg bg-emerald-50/50 border border-emerald-200">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <div>
                      <div className="font-bold text-emerald-950">ترخيص وزارة الصحة والسكان المصرية (MOH)</div>
                      <div className="text-[11px] text-emerald-700">ترخيص تشغيل مستشفى تخصصي رقم MOH-EG-2024-8841</div>
                    </div>
                  </div>
                  <span className="font-mono text-[11px] font-semibold text-emerald-800">ساري حتى 2027/12</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-blue-50/50 border border-blue-200">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-blue-600" />
                    <div>
                      <div className="font-bold text-blue-950">اعتماد الهيئة العامة للاعتماد والرقابة الصحية (GAHAR)</div>
                      <div className="text-[11px] text-blue-700">معايير المستشفيات الآمنة GAHAR-2023-V2</div>
                    </div>
                  </div>
                  <span className="font-mono text-[11px] font-semibold text-blue-800">معتمد حتى 2026/09</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Sidebar Contacts & Info */}
          <div className="space-y-6">
            <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
              <h3 className="font-bold text-sm text-[#0F172A]">القيادة الإدارية والطبية</h3>
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-[#64748B] block text-[11px]">مدير المنشأة</span>
                  <span className="font-bold text-[#0F172A]">{facility.administration.managerName}</span>
                </div>
                <div>
                  <span className="text-[#64748B] block text-[11px]">المدير الطبي</span>
                  <span className="font-bold text-[#0F172A]">{facility.administration.medicalDirector || "غير محدد"}</span>
                </div>
                <div>
                  <span className="text-[#64748B] block text-[11px]">البريد الإلكتروني المباشر</span>
                  <span className="font-mono text-[#0F172A]">{facility.administration.managerEmail}</span>
                </div>
                <div>
                  <span className="text-[#64748B] block text-[11px]">رقم الهاتف الرئيسي</span>
                  <span className="font-mono text-[#0F172A]">{facility.administration.managerPhone}</span>
                </div>
                <div>
                  <span className="text-[#64748B] block text-[11px]">طوارئ وتنسيق العمليات</span>
                  <span className="text-[#0F172A]">{facility.administration.adminContact || "لا يوجد جهة مخصصة"}</span>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-4 text-xs text-[#64748B] space-y-2">
              <div className="font-bold text-[#0F172A]">بيانات التسجيل النظامي</div>
              <div>تاريخ الإنشاء: {new Date(facility.createdAt).toLocaleDateString("ar-EG")}</div>
              <div>آخر تحديث: {new Date(facility.updatedAt).toLocaleDateString("ar-EG")}</div>
              <div>العملة المعتمدة: {facility.operations.currency}</div>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 2: DEPARTMENTS ──────────────────────────────────────── */}
      {activeTab === "departments" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-[#0F172A]">
              الأقسام التابعة للمنشأة ({facDepartments.length} قسماً)
            </h3>
            <button
              onClick={() => onNavigate("departments")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF]"
            >
              <Plus className="w-3.5 h-3.5" /> إضافة قسم للمنشأة
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {facDepartments.map((dept) => (
              <div
                key={dept.id}
                className="rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-2xs hover:border-[#CBD5E1] transition-all space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="font-bold text-sm text-[#0F172A]">{dept.name}</h4>
                    <span className="text-[10px] font-mono text-[#64748B]">{dept.code}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700">
                    {dept.category}
                  </span>
                </div>

                <div className="text-xs text-[#64748B] space-y-1">
                  <div>رئيس القسم: <strong className="text-[#334155]">{dept.managerName}</strong></div>
                  <div>الموقع: {dept.buildingName} — {dept.floorName}</div>
                </div>

                <div className="pt-2 border-t border-[#F1F5F9] flex items-center justify-between text-xs text-[#64748B]">
                  <span>{dept.unitsCount} وحدات • {dept.staffCount} كادر</span>
                  <button
                    onClick={() => onNavigate("departments")}
                    className="text-[#1E3A8A] font-semibold hover:underline flex items-center gap-1 text-[11px]"
                  >
                    تفاصيل <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── TAB 3: BUILDINGS & FLOORS ───────────────────────────────── */}
      {activeTab === "buildings" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-[#0F172A]">
              المباني والمجمعات التابعة ({facBuildings.length} مبنى)
            </h3>
            <button
              onClick={() => onNavigate("buildings")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF]"
            >
              <Plus className="w-3.5 h-3.5" /> إدارة المباني والطوابق
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {facBuildings.map((bld) => (
              <div key={bld.id} className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-slate-100 text-[#1E3A8A]">
                      <Layers className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="font-bold text-sm text-[#0F172A]">{bld.name}</h4>
                      <span className="font-mono text-xs text-[#64748B]">{bld.code}</span>
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700">
                    {bld.status}
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="text-[#64748B]">الطوابق المسجلة:</div>
                  <div className="space-y-1">
                    {bld.floors.map((fl) => (
                      <div
                        key={fl.id}
                        className="p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] flex items-center justify-between"
                      >
                        <span className="font-medium text-[#0F172A]">{fl.name}</span>
                        <span className="text-[11px] text-[#64748B]">
                          {fl.departmentsCount} قسم • {fl.roomsCount} غرفة
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── TAB 4: UNITS & ROOMS ────────────────────────────────────── */}
      {activeTab === "units_rooms" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-[#0F172A]">
              الغرف السريرية والعيادات ({facRooms.length} غرفة)
            </h3>
            <button
              onClick={() => onNavigate("units_rooms")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF]"
            >
              <DoorOpen className="w-3.5 h-3.5" /> فتح شاشة الوحدات والغرف
            </button>
          </div>

          <div className="rounded-xl border border-[#E2E8F0] bg-white overflow-hidden shadow-2xs">
            <table className="w-full text-right text-xs">
              <thead className="bg-[#F8FAFC] text-[#475569] font-bold border-b border-[#E2E8F0]">
                <tr>
                  <th className="py-2.5 px-4">رقم الغرفة</th>
                  <th className="py-2.5 px-4">الاسم والنوع</th>
                  <th className="py-2.5 px-4">الوحدة التابعة</th>
                  <th className="py-2.5 px-4">الحالة التشغيلية</th>
                  <th className="py-2.5 px-4">التجهيزات الطبية</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {facRooms.map((rm) => (
                  <tr key={rm.id} className="hover:bg-[#F8FAFC]">
                    <td className="py-2.5 px-4 font-mono font-bold text-[#1E3A8A]">{rm.code}</td>
                    <td className="py-2.5 px-4 font-medium text-[#0F172A]">{rm.name}</td>
                    <td className="py-2.5 px-4 text-[#64748B]">{rm.unitName}</td>
                    <td className="py-2.5 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700">
                        {rm.availability}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-[#64748B]">
                      {rm.equipmentReferences.slice(0, 2).join("، ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── TAB 5: SERVICES ─────────────────────────────────────────── */}
      {activeTab === "services" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-[#0F172A]">
              نقاط تقديم الخدمات الطبية المعتمدة ({facLocations.length})
            </h3>
            <button
              onClick={() => onNavigate("service_locations")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF]"
            >
              <Stethoscope className="w-3.5 h-3.5" /> إدارة نقاط الخدمات
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {facLocations.map((loc) => (
              <div key={loc.id} className="rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-2xs space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="font-bold text-sm text-[#0F172A]">{loc.name}</h4>
                    <span className="font-mono text-xs text-[#64748B]">{loc.code}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-50 text-teal-800">
                    {loc.status}
                  </span>
                </div>
                <div className="text-xs text-[#64748B]">
                  القسم: <strong className="text-[#334155]">{loc.departmentName}</strong> — الغرفة: {loc.roomCode}
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {loc.supportedServices.map((svc) => (
                    <span key={svc} className="text-[10px] px-2 py-0.5 rounded bg-[#F1F5F9] text-[#334155]">
                      {svc}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── TAB 6: OPERATING HOURS ──────────────────────────────────── */}
      {activeTab === "operating_hours" && (
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-[#0F172A]">مصفوفة ساعات العمل الأسبوعية للمنشأة</h3>
            <button
              onClick={() => onNavigate("operating_hours")}
              className="text-xs font-semibold text-[#1E3A8A] hover:underline"
            >
              تعديل الجدول الكامل والمناوبات ←
            </button>
          </div>
          <p className="text-xs text-[#64748B]">
            ساعات العمل القياسية: <strong>{facility.operations.standardHours}</strong>. قسم الطوارئ يعمل{" "}
            <strong>{facility.operations.is24HoursEmergency ? "24/7 دون توقف" : "خلال ساعات العمل فقط"}</strong>.
          </p>
        </div>
      )}

      {/* ─── TAB 7: STAFF ────────────────────────────────────────────── */}
      {activeTab === "staff" && (
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-[#0F172A]">
              الكوادر الطبية والإدارية المعينة ({facility.stats.staffCount} فرد)
            </h3>
            <button
              onClick={() => onNavigate("users_access")}
              className="text-xs font-semibold text-[#1E3A8A] hover:underline"
            >
              إدارة صلاحيات الكوادر ←
            </button>
          </div>
          <p className="text-xs text-[#64748B]">
            يتم ربط الكوادر الطبية (أطباء، تمريض، فنيين) بالأقسام والوحدات عبر نظام الصلاحيات ومصفوفة الأدوار RBAC.
          </p>
        </div>
      )}

      {/* ─── TAB 8: SETTINGS ─────────────────────────────────────────── */}
      {activeTab === "settings" && (
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-[#0F172A]">سياسات وإعدادات المنشأة المخصصة</h3>
            <button
              onClick={() => onNavigate("facility_settings")}
              className="text-xs font-semibold text-[#1E3A8A] hover:underline"
            >
              تعديل كافة إعدادات المنشأة ←
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-3 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0]">
              <span className="text-[#64748B] block mb-1">بادئة ملفات المرضى (MRN Prefix)</span>
              <span className="font-mono font-bold text-[#0F172A]">{facility.code}-MRN</span>
            </div>
            <div className="p-3 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0]">
              <span className="text-[#64748B] block mb-1">العملة والمنطقة الزمنية</span>
              <span className="font-semibold text-[#0F172A]">{facility.operations.currency} • {facility.operations.timeZone}</span>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 9: ACTIVITY ─────────────────────────────────────────── */}
      {activeTab === "activity" && (
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
          <h3 className="font-bold text-sm text-[#0F172A]">
            سجل العمليات والتدقيق الخاص بالمنشأة ({facLogs.length})
          </h3>
          <div className="space-y-3">
            {facLogs.map((log) => (
              <div
                key={log.id}
                className="p-3 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] flex items-start justify-between text-xs"
              >
                <div>
                  <div className="font-bold text-[#0F172A]">{log.action}</div>
                  <div className="text-[11px] text-[#64748B] mt-0.5">{log.details}</div>
                  <div className="text-[10px] text-[#94A3B8] mt-1">
                    بواسطة: {log.actorName} ({log.actorRole})
                  </div>
                </div>
                <span className="text-[10px] font-mono text-[#64748B]">
                  {new Date(log.timestamp).toLocaleString("ar-EG")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
