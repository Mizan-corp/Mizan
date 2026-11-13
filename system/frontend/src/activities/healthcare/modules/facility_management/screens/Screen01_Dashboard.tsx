import { useState } from "react";
import {
  Hospital, Building2, GitFork, DoorOpen, Activity,
  ChevronRight, ChevronDown, Plus, Settings,
  CheckCircle2, Layers, ExternalLink
} from "lucide-react";
import { HealthcareOrganization, HealthcareFacilityItem, DepartmentItem, FacilityActivityLogItem } from "../types";

interface DashboardProps {
  organization: HealthcareOrganization;
  facilities: HealthcareFacilityItem[];
  departments: DepartmentItem[];
  activityLogs?: FacilityActivityLogItem[];
  onNavigate: (screenId: string) => void;
  onSelectFacility: (facilityId: string) => void;
  onAddFacility?: () => void;
  onAddDepartment?: () => void;
}

export default function Screen01_Dashboard({
  organization,
  facilities,
  departments,
  onNavigate,
  onSelectFacility,
  onAddFacility,
  onAddDepartment,
}: DashboardProps) {
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({
    "org-root": true,
    "fac-central-hosp": true,
    "fac-downtown-med": false,
    "fac-west-clinic": false,
  });

  const toggleNode = (nodeId: string) => {
    setExpandedNodes((prev) => ({ ...prev, [nodeId]: !prev[nodeId] }));
  };

  // Metrics
  const totalFacilities = facilities.length;
  const activeBranches = facilities.filter((f) => f.status === "active").length;
  const totalDepartments = departments.length;
  const totalUnits = facilities.reduce((acc, f) => acc + f.stats.unitCount, 0);
  const totalServices = facilities.reduce((acc, f) => acc + f.stats.activeServicesCount, 0);

  // Distribution by type
  const typeCounts = {
    hospital: facilities.filter((f) => f.type === "hospital").length,
    medical_center: facilities.filter((f) => f.type === "medical_center").length,
    clinic: facilities.filter((f) => f.type === "clinic").length,
    diagnostic_center: facilities.filter((f) => f.type === "diagnostic_center").length,
    specialized_center: facilities.filter((f) => f.type === "specialized_center").length,
  };

  return (
    <div className="space-y-6">
      {/* Editorial Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-[#E2E8F0] pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01 • Core Foundation
            </span>
            <span className="text-xs text-[#64748B]">نظام الإدارة المركزية المتكامل</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            نظرة عامة على المنظمة والمرافق الصحية
          </h1>
          <p className="text-xs text-[#64748B] mt-0.5 max-w-2xl">
            إدارة شبكة المستشفيات والمراكز التخصصية والعيادات، مراقبة الهيكل المؤسسي، وجدولة الموارد السريرية.
          </p>
        </div>

        {/* Quick Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={onAddFacility}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF] transition-all shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>إضافة منشأة جديدة</span>
          </button>
          <button
            onClick={onAddDepartment}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white border border-[#E2E8F0] text-[#0F172A] text-xs font-semibold hover:bg-[#F8FAFC] transition-colors shadow-2xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>إضافة قسم طبي</span>
          </button>
          <button
            onClick={() => onNavigate("org_profile")}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white border border-[#E2E8F0] text-[#475569] text-xs font-medium hover:bg-[#F8FAFC] transition-colors shadow-2xs"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>ملف المنظمة</span>
          </button>
        </div>
      </div>

      {/* ─── TOP KPI CARDS ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {[
          {
            title: "إجمالي المنشآت",
            titleEn: "Total Facilities",
            value: totalFacilities,
            sub: "مستشفيات ومراكز",
            trend: "+1 قيد الإنشاء",
            icon: Hospital,
            color: "text-blue-600 bg-blue-50 border-blue-200",
          },
          {
            title: "الفروع النشطة",
            titleEn: "Active Branches",
            value: activeBranches,
            sub: `${Math.round((activeBranches / totalFacilities) * 100)}% معدل التشغيل`,
            trend: "جاهزية تشغيلية",
            icon: Building2,
            color: "text-emerald-600 bg-emerald-50 border-emerald-200",
          },
          {
            title: "الأقسام السريرية",
            titleEn: "Departments",
            value: totalDepartments,
            sub: "تخصصات جراحية وباطنية",
            trend: "+3 هذا العام",
            icon: GitFork,
            color: "text-indigo-600 bg-indigo-50 border-indigo-200",
          },
          {
            title: "الوحدات والغرف",
            titleEn: "Registered Units",
            value: totalUnits,
            sub: "وحدة تشغيلية معتمدة",
            trend: "140 غرفة سريرية",
            icon: DoorOpen,
            color: "text-teal-600 bg-teal-50 border-teal-200",
          },
          {
            title: "الخدمات الطبية",
            titleEn: "Active Services",
            value: totalServices,
            sub: "خدمات فحص وجراحة",
            trend: "مفعلة في المنظومة",
            icon: Activity,
            color: "text-purple-600 bg-purple-50 border-purple-200",
          },
        ].map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div
              key={idx}
              className="rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-2xs hover:shadow-xs transition-shadow"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-[#64748B] truncate">{kpi.title}</span>
                <div className={`p-1.5 rounded-lg border ${kpi.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-[#0F172A] font-mono tracking-tight">
                {kpi.value}
              </div>
              <div className="flex items-center justify-between text-[10px] text-[#64748B] mt-1 pt-2 border-t border-[#F1F5F9]">
                <span>{kpi.sub}</span>
                <span className="text-teal-700 font-semibold bg-teal-50/80 px-1 rounded">{kpi.trend}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* ─── MIDDLE SECTION: DISTRIBUTION & HIERARCHY TREE ────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* A. Facility Distribution by Type */}
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
            <div>
              <h3 className="font-bold text-sm text-[#0F172A]">توزيع المنشآت حسب النوع</h3>
              <p className="text-[11px] text-[#64748B]">تصنيف المرافق الصحية في المجموعة</p>
            </div>
            <span className="text-xs font-mono font-bold text-[#1E3A8A] bg-blue-50 px-2 py-0.5 rounded">
              {totalFacilities} منشآت
            </span>
          </div>

          <div className="space-y-3">
            {[
              { type: "مستشفى تخصصي (Hospital)", count: typeCounts.hospital, color: "bg-blue-600", pct: 40 },
              { type: "مركز طبي (Medical Center)", count: typeCounts.medical_center, color: "bg-teal-600", pct: 20 },
              { type: "عيادات خارجية (Clinic)", count: typeCounts.clinic, color: "bg-indigo-600", pct: 20 },
              { type: "مركز تشخيصي (Diagnostic Center)", count: typeCounts.diagnostic_center, color: "bg-purple-600", pct: 20 },
              { type: "مراكز متخصصة (Specialized)", count: typeCounts.specialized_center, color: "bg-amber-600", pct: 0 },
            ].map((row, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-[#334155]">{row.type}</span>
                  <span className="font-mono font-bold text-[#0F172A]">{row.count}</span>
                </div>
                <div className="h-2 w-full rounded-full bg-[#F1F5F9] overflow-hidden">
                  <div className={`h-full rounded-full ${row.color}`} style={{ width: `${row.pct}%` }} />
                </div>
              </div>
            ))}
          </div>

          <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-xs text-[#475569] flex items-center justify-between">
            <span>الاعتماد الرئيسي: <strong>GAHAR (جهار)</strong></span>
            <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded text-[11px] font-semibold border border-emerald-200">
              ساري ومعتمد
            </span>
          </div>
        </div>

        {/* B. Organization Structure Tree */}
        <div className="lg:col-span-2 rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
            <div>
              <h3 className="font-bold text-sm text-[#0F172A] flex items-center gap-2">
                <Layers className="w-4 h-4 text-teal-600" />
                الهيكل التنظيمي للمجموعة (Organization Hierarchy Tree)
              </h3>
              <p className="text-[11px] text-[#64748B]">انقر لتوسيع أو تصفح الأقسام والمستشفيات</p>
            </div>
            <button
              onClick={() => onNavigate("facilities")}
              className="text-xs text-[#2563EB] hover:underline font-semibold flex items-center gap-1"
            >
              إدارة الكل <ChevronRight className="w-3.5 h-3.5 rotate-180" />
            </button>
          </div>

          {/* Interactive Tree View */}
          <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-3 text-xs space-y-2 max-h-72 overflow-y-auto">
            {/* Root Node */}
            <div>
              <div
                onClick={() => toggleNode("org-root")}
                className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-white cursor-pointer font-bold text-[#0F172A]"
              >
                {expandedNodes["org-root"] ? <ChevronDown className="w-4 h-4 text-[#64748B]" /> : <ChevronRight className="w-4 h-4 text-[#64748B]" />}
                <Building2 className="w-4 h-4 text-indigo-700" />
                <span>{organization.legalName}</span>
                <span className="text-[10px] font-mono bg-indigo-50 text-indigo-700 px-1.5 py-0.2 rounded border border-indigo-200">
                  {organization.code}
                </span>
              </div>

              {expandedNodes["org-root"] && (
                <div className="mr-6 mt-1 border-r-2 border-[#CBD5E1] pr-3 space-y-2">
                  {facilities.map((fac) => {
                    const isExpanded = expandedNodes[fac.id] ?? false;
                    const facDepts = departments.filter((d) => d.facilityId === fac.id);
                    return (
                      <div key={fac.id}>
                        <div
                          onClick={() => toggleNode(fac.id)}
                          className="flex items-center justify-between p-1.5 rounded-lg hover:bg-white cursor-pointer"
                        >
                          <div className="flex items-center gap-2">
                            {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-[#64748B]" /> : <ChevronRight className="w-3.5 h-3.5 text-[#64748B]" />}
                            <Hospital className="w-3.5 h-3.5 text-blue-700" />
                            <span className="font-semibold text-[#1E293B]">{fac.name}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-[#64748B] font-mono">{facDepts.length} أقسام</span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectFacility(fac.id);
                                onNavigate("facility_details");
                              }}
                              className="text-[10px] text-teal-700 hover:underline font-semibold"
                            >
                              عرض الملف
                            </button>
                          </div>
                        </div>

                        {/* Child Departments */}
                        {isExpanded && (
                          <div className="mr-5 mt-1 border-r border-[#CBD5E1] pr-3 space-y-1">
                            {facDepts.length > 0 ? (
                              facDepts.map((d) => (
                                <div key={d.id} className="flex items-center justify-between py-1 text-[11px] text-[#475569] hover:text-[#0F172A]">
                                  <div className="flex items-center gap-2">
                                    <GitFork className="w-3 h-3 text-[#94A3B8]" />
                                    <span>{d.name}</span>
                                  </div>
                                  <span className="text-[10px] font-mono text-[#94A3B8]">{d.code}</span>
                                </div>
                              ))
                            ) : (
                              <div className="text-[11px] text-[#94A3B8] italic py-0.5">
                                لا توجد أقسام مسجلة حالياً
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ─── SECTION C: FACILITIES OVERVIEW DATA TABLE ────────────────── */}
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[#F1F5F9] pb-3">
          <div>
            <h3 className="font-bold text-sm text-[#0F172A]">دليل المنشآت والمستشفيات المسجلة</h3>
            <p className="text-[11px] text-[#64748B]">قائمة تفصيلية بالحالة التشغيلية ومديري الفروع</p>
          </div>
          <button
            onClick={() => onNavigate("facilities")}
            className="text-xs text-[#1E3A8A] font-semibold hover:underline flex items-center gap-1 self-start sm:self-auto"
          >
            عرض جميع المرافق والتحكم الكامل <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-right">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[#64748B] font-semibold">
              <tr>
                <th className="p-3">اسم المنشأة والكود</th>
                <th className="p-3">النوع</th>
                <th className="p-3">المدينة والمنطقة</th>
                <th className="p-3">الأقسام</th>
                <th className="p-3">المدير التشغيلي والطبي</th>
                <th className="p-3">الحالة</th>
                <th className="p-3 text-center">الإجراءات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {facilities.map((fac) => (
                <tr key={fac.id} className="hover:bg-[#F8FAFC]/70 transition-colors">
                  <td className="p-3">
                    <div className="font-bold text-[#0F172A]">{fac.name}</div>
                    <div className="text-[10px] text-[#64748B] font-mono mt-0.5">{fac.code}</div>
                  </td>
                  <td className="p-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-800 border border-slate-200">
                      {fac.type === "hospital" ? "مستشفى" : fac.type === "medical_center" ? "مركز طبي" : fac.type === "diagnostic_center" ? "مركز تشخيصي" : "عيادات"}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="text-[#334155]">{fac.location.city}</div>
                    <div className="text-[10px] text-[#64748B]">{fac.location.district}</div>
                  </td>
                  <td className="p-3 font-mono font-bold text-[#1E3A8A]">
                    {fac.stats.departmentCount} قسم
                  </td>
                  <td className="p-3">
                    <div className="font-medium text-[#0F172A]">{fac.administration.managerName}</div>
                    <div className="text-[10px] text-[#64748B]">{fac.administration.medicalDirector}</div>
                  </td>
                  <td className="p-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        fac.status === "active"
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : fac.status === "under_construction"
                          ? "bg-amber-50 text-amber-700 border border-amber-200"
                          : "bg-rose-50 text-rose-700 border border-rose-200"
                      }`}
                    >
                      {fac.status === "active" ? "نشط وتشغيلي" : fac.status === "under_construction" ? "قيد الإنشاء" : "معلق"}
                    </span>
                  </td>
                  <td className="p-3 text-center">
                    <div className="inline-flex items-center gap-1.5">
                      <button
                        onClick={() => {
                          onSelectFacility(fac.id);
                          onNavigate("facility_details");
                        }}
                        className="px-2.5 py-1 text-[11px] font-semibold rounded bg-[#F1F5F9] text-[#1E3A8A] hover:bg-[#1E3A8A] hover:text-white transition-colors"
                      >
                        عرض التفاصيل
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─── SECTION D: RECENT ACTIVITY FEED ─────────────────────────── */}
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
          <div>
            <h3 className="font-bold text-sm text-[#0F172A]">سجل التحديثات والأنشطة الإدارية الأخيرة</h3>
            <p className="text-[11px] text-[#64748B]">تتبع تغييرات البنية التحتية، اعتمادات الأقسام، وساعات العمل</p>
          </div>
          <button
            onClick={() => onNavigate("audit_logs")}
            className="text-xs text-[#64748B] hover:text-[#0F172A] flex items-center gap-1 font-medium"
          >
            سجل التدقيق الكامل <ChevronRight className="w-3.5 h-3.5 rotate-180" />
          </button>
        </div>

        <div className="space-y-3">
          {[
            {
              action: "تعديل جدول العمل وتفعيل وردية إضافية",
              facility: "مستشفى ميزان المركزي",
              actor: "م. كريم فهمي (مدير المنشأة)",
              time: "منذ 18 دقيقة",
              details: "إضافة وردية مسائية لعيادات القلب لاستيعاب الحالات المجدولة.",
            },
            {
              action: "اعتماد غرفة العمليات الكبسولية OR-01",
              facility: "مستشفى ميزان المركزي",
              actor: "أ.د. طارق منصور (المدير الطبي)",
              time: "منذ ساعتين",
              details: "اكتمال فحص أنظمة التعقيم الإيجابي وتدفق الهواء الرقائقي.",
            },
            {
              action: "تجديد شهادة اعتماد الطوارئ لدى وزارة الصحة",
              facility: "مستشفى ميزان المركزي",
              actor: "سها الشناوي (مديرة الجودة)",
              time: "اليوم، 09:30 ص",
              details: "رفع السعة التشغيلية إلى 16 كبينة فرز وطوارئ متكاملة.",
            },
          ].map((item, idx) => (
            <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]">
              <div className="p-2 rounded-lg bg-teal-50 text-teal-700 border border-teal-200 mt-0.5">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div className="flex-1 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#0F172A]">{item.action}</span>
                  <span className="text-[10px] text-[#64748B] font-mono">{item.time}</span>
                </div>
                <div className="text-[11px] text-[#475569] mt-0.5">
                  المنشأة: <strong className="text-[#0F172A]">{item.facility}</strong> • المنفذ: {item.actor}
                </div>
                <div className="text-[11px] text-[#64748B] mt-1 bg-white p-2 rounded border border-[#E2E8F0]/70">
                  {item.details}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
