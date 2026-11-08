import {
  Building2, LayoutDashboard, GitFork, Layers,
  DoorOpen, MapPin, Clock, Calendar, Settings,
  Shield, FileText, Hospital, Plus
} from "lucide-react";
import { HealthcareOrganization, HealthcareFacilityItem } from "../types";

export interface NavItem {
  id: string;
  label: string;
  labelEn: string;
  icon: any;
  badge?: string | number;
}

export interface NavGroup {
  id: string;
  title: string;
  titleEn: string;
  items: NavItem[];
}

interface AppShellProps {
  organization: HealthcareOrganization;
  facilities: HealthcareFacilityItem[];
  currentFacilityId: string | "all";
  onSelectFacility: (facilityId: string | "all") => void;
  activeScreenId: string;
  onNavigate: (screenId: string) => void;
  breadcrumbs: Array<{ label: string; screenId?: string }>;
  children: React.ReactNode;
  onQuickAction?: (action: string) => void;
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: "overview",
    title: "نظرة عامة",
    titleEn: "Overview",
    items: [
      { id: "dashboard", label: "لوحة التحكم والمؤشرات", labelEn: "Dashboard", icon: LayoutDashboard },
    ],
  },
  {
    id: "organization",
    title: "الهيكل المؤسسي والمرافق",
    titleEn: "Organization & Facilities",
    items: [
      { id: "org_profile", label: "ملف المنظمة والاعتمادات", labelEn: "Org Profile", icon: Building2 },
      { id: "facilities", label: "المنشآت والمستشفيات", labelEn: "Facilities", icon: Hospital, badge: "5" },
      { id: "buildings", label: "المباني والطوابق", labelEn: "Buildings", icon: Layers },
      { id: "departments", label: "الأقسام الطبية", labelEn: "Departments", icon: GitFork, badge: "12" },
      { id: "units_rooms", label: "الوحدات والغرف السريرية", labelEn: "Units & Rooms", icon: DoorOpen },
      { id: "service_locations", label: "نقاط تقديم الخدمات", labelEn: "Service Points", icon: MapPin },
    ],
  },
  {
    id: "configuration",
    title: "الإعدادات والتشغيل",
    titleEn: "Configuration",
    items: [
      { id: "operating_hours", label: "ساعات العمل والمناوبات", labelEn: "Hours & Shifts", icon: Clock },
      { id: "holidays", label: "العطلات والاستثناءات", labelEn: "Holidays", icon: Calendar },
      { id: "facility_settings", label: "إعدادات المنشأة والترقيم", labelEn: "Facility Settings", icon: Settings },
    ],
  },
  {
    id: "administration",
    title: "الحوكمة والرقابة",
    titleEn: "Governance",
    items: [
      { id: "users_access", label: "المستخدمون وصلاحيات المنشأة", labelEn: "Access Scopes", icon: Shield },
      { id: "audit_logs", label: "سجل التدقيق الإداري", labelEn: "Audit Trail", icon: FileText },
    ],
  },
];

export default function AppShell({
  organization,
  facilities,
  currentFacilityId,
  onSelectFacility,
  activeScreenId,
  onNavigate,
  breadcrumbs,
  children,
  onQuickAction,
}: AppShellProps) {
  return (
    <div className="w-full space-y-5 text-[#0F172A] font-sans text-right" dir="rtl">
      {/* ─── 1. EXECUTIVE HEALTHCARE SUITE HEADER ───────────────────────── */}
      <div className="rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-2xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Identity & Context Badges */}
          <div className="flex items-start sm:items-center gap-3.5">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-[#0A2540] to-[#1E3A8A] flex items-center justify-center text-teal-300 shadow-sm shrink-0">
              <Hospital className="w-6 h-6" />
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-bold text-base tracking-tight text-[#0F172A]">
                  منظومة إدارة المنشآت والمرافق الصحية
                </span>
                <span className="rounded bg-teal-50 px-2 py-0.5 text-[10px] font-bold text-teal-800 border border-teal-200">
                  HLT-01 • Core Management
                </span>
                <span className="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-[#1E3A8A] border border-blue-200 font-mono">
                  {organization.code}
                </span>
              </div>

              {/* Breadcrumb Trail */}
              <div className="flex items-center gap-1.5 text-xs text-[#64748B] mt-1">
                <span>{organization.displayName}</span>
                <span>•</span>
                {breadcrumbs.map((b, idx) => (
                  <span key={idx} className="flex items-center gap-1.5">
                    {b.screenId ? (
                      <button
                        onClick={() => onNavigate(b.screenId!)}
                        className="hover:text-[#1E3A8A] hover:underline"
                      >
                        {b.label}
                      </button>
                    ) : (
                      <span className="font-semibold text-[#0F172A]">{b.label}</span>
                    )}
                    {idx < breadcrumbs.length - 1 && <span>/</span>}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Controls: Facility Selector & Quick Actions */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Facility Context Dropdown */}
            <div className="flex items-center gap-2 bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-1.5 shadow-2xs">
              <span className="text-[11px] font-bold text-[#64748B] shrink-0">نطاق المنشأة:</span>
              <select
                value={currentFacilityId}
                onChange={(e) => onSelectFacility(e.target.value)}
                className="bg-transparent text-xs font-bold text-[#0F172A] focus:outline-none cursor-pointer"
              >
                <option value="all">🏢 جميع المنشآت ({facilities.length} منشآت)</option>
                {facilities.map((fac) => (
                  <option key={fac.id} value={fac.id}>
                    {fac.type === "hospital" ? "🏥" : fac.type === "medical_center" ? "🏛️" : fac.type === "diagnostic_center" ? "🔬" : "🩺"}{" "}
                    {fac.name} ({fac.code})
                  </option>
                ))}
              </select>
            </div>

            {/* Quick Actions Dropdown / Buttons */}
            {onQuickAction && (
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => onQuickAction("add_facility")}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF] transition-colors shadow-2xs cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> إضافة منشأة
                </button>
                <button
                  onClick={() => onQuickAction("add_department")}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-white border border-[#CBD5E1] text-[#334155] text-xs font-medium hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> إضافة قسم
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ─── 2. SECTOR NAVIGATION TABS STRIP ──────────────────────────── */}
        <div className="flex items-center gap-1 overflow-x-auto border-t border-[#F1F5F9] mt-4 pt-3 scrollbar-thin">
          {NAV_GROUPS.flatMap((group) => group.items).map((item) => {
            const Icon = item.icon;
            const isActive = activeScreenId === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  isActive
                    ? "bg-[#1E3A8A] text-white shadow-xs"
                    : "text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9]"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-teal-300" : "text-[#94A3B8]"}`} />
                <span>{item.label}</span>
                {item.badge && (
                  <span
                    className={`rounded-full px-1.5 py-0.2 text-[10px] font-mono font-bold ${
                      isActive ? "bg-white/20 text-white" : "bg-[#E2E8F0] text-[#334155]"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── 3. ACTIVE SCREEN CONTENT AREA ─────────────────────────────── */}
      <main className="w-full animate-in fade-in duration-200">
        {children}
      </main>
    </div>
  );
}
