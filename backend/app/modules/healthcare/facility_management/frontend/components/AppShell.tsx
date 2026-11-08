import { Fragment, useState } from "react";
import {
  Building2, LayoutDashboard, GitFork, Layers,
  DoorOpen, MapPin, Clock, Calendar, Settings,
  Shield, FileText, ChevronDown, ChevronRight,
  Search, Bell, HelpCircle, Menu, X, ArrowLeft,
  Hospital
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
      { id: "org_profile", label: "ملف المنظمة والاعتمادات", labelEn: "Organization Profile", icon: Building2 },
      { id: "facilities", label: "إدارة المنشآت والمستشفيات", labelEn: "Facilities", icon: Hospital, badge: "5" },
      { id: "buildings", label: "المباني والطوابق", labelEn: "Buildings & Floors", icon: Layers },
      { id: "departments", label: "الأقسام الطبية والإدارية", labelEn: "Departments", icon: GitFork, badge: "12" },
      { id: "units_rooms", label: "الوحدات والغرف السريرية", labelEn: "Units & Rooms", icon: DoorOpen },
      { id: "service_locations", label: "نقاط تقديم الخدمات الطبية", labelEn: "Service Locations", icon: MapPin },
    ],
  },
  {
    id: "configuration",
    title: "الإعدادات والتشغيل",
    titleEn: "Operational Configuration",
    items: [
      { id: "operating_hours", label: "ساعات العمل والمناوبات", labelEn: "Operating Hours", icon: Clock },
      { id: "holidays", label: "العطلات والاستثناءات", labelEn: "Holidays & Exceptions", icon: Calendar },
      { id: "facility_settings", label: "إعدادات المنشأة والترقيم", labelEn: "Facility Settings", icon: Settings },
    ],
  },
  {
    id: "administration",
    title: "الحوكمة والرقابة",
    titleEn: "Governance & Security",
    items: [
      { id: "users_access", label: "المستخدمون وصلاحيات المنشأة", labelEn: "Users & Access", icon: Shield },
      { id: "audit_logs", label: "سجل التدقيق الإداري", labelEn: "Audit Logs", icon: FileText },
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    overview: true,
    organization: true,
    configuration: true,
    administration: true,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  const currentFacility = facilities.find((f) => f.id === currentFacilityId);

  const toggleGroup = (groupId: string) => {
    setExpandedGroups((prev) => ({ ...prev, [groupId]: !prev[groupId] }));
  };

  return (
    <div className="flex h-screen w-full bg-[#F8FAFC] text-[#0F172A] overflow-hidden font-sans select-none" dir="rtl">
      {/* ─── SIDEBAR (Desktop & Drawer) ─────────────────────────────────── */}
      <aside
        className={`fixed inset-y-0 right-0 z-40 flex flex-col border-l border-[#E2E8F0] bg-[#FFFFFF] transition-all duration-300 md:static ${
          sidebarCollapsed ? "w-20" : "w-72"
        } ${mobileDrawerOpen ? "translate-x-0 shadow-2xl" : "translate-x-full md:translate-x-0"}`}
      >
        {/* Brand Header */}
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-[#E2E8F0] px-4">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#0A2540] to-[#1E3A8A] text-white shadow-sm font-bold text-lg">
              <Hospital className="w-5 h-5 text-teal-300" />
            </div>
            {!sidebarCollapsed && (
              <div className="truncate">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-sm tracking-tight text-[#0F172A]">ميزان كير</span>
                  <span className="rounded bg-teal-50 px-1.5 py-0.2 text-[10px] font-semibold text-teal-700 border border-teal-200">
                    HLT-01
                  </span>
                </div>
                <p className="text-[11px] text-[#64748B] truncate">إدارة المنشآت والمرافق الصحية</p>
              </div>
            )}
          </div>
          <button
            onClick={() => setMobileDrawerOpen(false)}
            className="rounded-lg p-1.5 text-[#64748B] hover:bg-[#F1F5F9] md:hidden"
            aria-label="إغلاق القائمة"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Organization & Facility Switcher Controls */}
        {!sidebarCollapsed && (
          <div className="p-3 border-b border-[#E2E8F0] bg-[#F8FAFC]/70 space-y-2">
            <div>
              <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block mb-1">
                المجموعة الطبية (Organization)
              </label>
              <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-[#E2E8F0] shadow-2xs">
                <div className="flex items-center gap-2 truncate">
                  <div className="w-2 h-2 rounded-full bg-teal-500 shrink-0" />
                  <span className="text-xs font-semibold text-[#0F172A] truncate">
                    {organization.displayName}
                  </span>
                </div>
                <span className="text-[10px] font-mono font-medium text-[#64748B] bg-[#F1F5F9] px-1.5 py-0.5 rounded">
                  {organization.code}
                </span>
              </div>
            </div>

            <div>
              <label className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block mb-1">
                المنشأة المحددة (Facility Context)
              </label>
              <select
                value={currentFacilityId}
                onChange={(e) => onSelectFacility(e.target.value)}
                className="w-full text-xs font-medium py-1.5 px-2 rounded-lg bg-white border border-[#E2E8F0] text-[#0F172A] focus:outline-none focus:border-[#2563EB] shadow-2xs"
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
          </div>
        )}

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
          {NAV_GROUPS.map((group) => {
            const isExpanded = expandedGroups[group.id] ?? true;
            return (
              <div key={group.id} className="space-y-1">
                {!sidebarCollapsed ? (
                  <button
                    onClick={() => toggleGroup(group.id)}
                    className="flex w-full items-center justify-between px-2.5 py-1 text-[11px] font-bold text-[#64748B] uppercase tracking-wider hover:text-[#0F172A] transition-colors"
                  >
                    <span>{group.title}</span>
                    {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  </button>
                ) : (
                  <div className="h-2" />
                )}

                {(isExpanded || sidebarCollapsed) && (
                  <div className="space-y-0.5">
                    {group.items.map((item) => {
                      const Icon = item.icon;
                      const isActive = activeScreenId === item.id;
                      return (
                        <button
                          key={item.id}
                          onClick={() => {
                            onNavigate(item.id);
                            setMobileDrawerOpen(false);
                          }}
                          className={`group relative flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-xs font-medium transition-all ${
                            isActive
                              ? "bg-[#1E3A8A] text-white shadow-xs font-semibold"
                              : "text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A]"
                          }`}
                          title={sidebarCollapsed ? `${item.label} (${item.labelEn})` : undefined}
                        >
                          <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-teal-300" : "text-[#64748B] group-hover:text-[#0F172A]"}`} />
                          {!sidebarCollapsed && (
                            <>
                              <span className="truncate flex-1 text-right">{item.label}</span>
                              {item.badge && (
                                <span
                                  className={`rounded-full px-1.5 py-0.2 text-[10px] font-mono font-bold ${
                                    isActive ? "bg-white/20 text-white" : "bg-[#E2E8F0] text-[#334155]"
                                  }`}
                                >
                                  {item.badge}
                                </span>
                              )}
                            </>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* User Profile & Collapse Toggle */}
        <div className="border-t border-[#E2E8F0] p-3 bg-[#F8FAFC]/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#E2E8F0] text-[#1E3A8A] font-bold text-xs border border-[#CBD5E1]">
                ط.م
              </div>
              {!sidebarCollapsed && (
                <div className="truncate">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-[#0F172A] truncate">أ.د. طارق منصور</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" title="متصل الآن" />
                  </div>
                  <p className="text-[10px] text-[#64748B] truncate">المدير الطبي العام • مدير المنشأة</p>
                </div>
              )}
            </div>
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="hidden md:flex rounded-lg p-1.5 text-[#64748B] hover:bg-[#E2E8F0] transition-colors"
              title={sidebarCollapsed ? "توسيع القائمة الجانبية" : "طي القائمة الجانبية"}
            >
              {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ArrowLeft className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </aside>

      {/* Backdrop for mobile drawer */}
      {mobileDrawerOpen && (
        <div
          onClick={() => setMobileDrawerOpen(false)}
          className="fixed inset-0 z-30 bg-black/40 backdrop-blur-xs md:hidden"
        />
      )}

      {/* ─── MAIN CONTENT AREA ─────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Navigation Bar */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-[#E2E8F0] bg-white px-4 md:px-6 shadow-2xs z-20">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileDrawerOpen(true)}
              className="rounded-lg p-2 text-[#64748B] hover:bg-[#F1F5F9] md:hidden"
              aria-label="فتح القائمة"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Breadcrumb Navigation */}
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-[#64748B]">
              <span className="font-semibold text-[#0F172A]">ميزان للرعاية</span>
              <span>/</span>
              {breadcrumbs.map((b, idx) => (
                <Fragment key={idx}>
                  {b.screenId ? (
                    <button
                      onClick={() => onNavigate(b.screenId!)}
                      className="hover:text-[#2563EB] hover:underline"
                    >
                      {b.label}
                    </button>
                  ) : (
                    <span className="text-[#0F172A] font-semibold">{b.label}</span>
                  )}
                  {idx < breadcrumbs.length - 1 && <span>/</span>}
                </Fragment>
              ))}
            </div>
          </div>

          {/* Right Action Icons & Search */}
          <div className="flex items-center gap-3">
            {/* Global Quick Search */}
            <div className="relative hidden md:block w-72">
              <Search className="absolute right-3 top-2.5 w-3.5 h-3.5 text-[#94A3B8]" />
              <input
                type="text"
                placeholder="بحث سريع (مستشفى، قسم، مبنى، غرفة)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg bg-[#F8FAFC] pr-8 pl-12 py-1.5 text-xs border border-[#E2E8F0] text-[#0F172A] placeholder-[#94A3B8] focus:bg-white focus:outline-none focus:border-[#2563EB] transition-all"
              />
              <span className="absolute left-2.5 top-2 rounded bg-white px-1.5 py-0.5 text-[9px] font-mono text-[#64748B] border border-[#CBD5E1]">
                ⌘K
              </span>
            </div>

            {/* Context Badge */}
            <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs">
              <span className="text-[#64748B]">المنشأة:</span>
              <strong className="text-[#0F172A]">
                {currentFacility ? currentFacility.name : "جميع المنشآت"}
              </strong>
            </div>

            {/* Notifications Popover Trigger */}
            <div className="relative">
              <button
                onClick={() => setShowNotifications(!showNotifications)}
                className="relative rounded-lg p-2 text-[#64748B] hover:bg-[#F1F5F9] transition-colors"
                title="مركز الإشعارات والتنبيهات التشغيلية"
              >
                <Bell className="w-4 h-4" />
                <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-600" />
                </span>
              </button>

              {showNotifications && (
                <div className="absolute left-0 mt-2 w-80 rounded-xl border border-[#E2E8F0] bg-white p-3 shadow-lg z-50 text-right animate-in fade-in slide-in-from-top-1 duration-150">
                  <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2 mb-2">
                    <span className="text-xs font-bold text-[#0F172A]">التنبيهات التشغيلية للمرافق</span>
                    <span className="text-[10px] text-teal-700 bg-teal-50 px-1.5 py-0.2 rounded font-semibold">3 جديدة</span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]">
                      <div className="font-semibold text-[#0F172A]">اكتمال معايرة جناح الرنين MRI 3T</div>
                      <div className="text-[11px] text-[#64748B] mt-0.5">جاهز لاستقبال الحالات المجدولة في مستشفى ميزان المركزي.</div>
                      <div className="text-[9px] text-[#94A3B8] mt-1 font-mono">منذ 25 دقيقة</div>
                    </div>
                    <div className="p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]">
                      <div className="font-semibold text-[#0F172A]">تحديث رخصة العلاج الحر 2026</div>
                      <div className="text-[11px] text-[#64748B] mt-0.5">تمت إضافة وثيقة الاعتماد الجديدة إلى ملف المنظمة.</div>
                      <div className="text-[9px] text-[#94A3B8] mt-1 font-mono">اليوم، 10:14 ص</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Help / Docs */}
            <button
              onClick={() => setShowHelp(true)}
              className="rounded-lg p-2 text-[#64748B] hover:bg-[#F1F5F9] transition-colors"
              title="دليل الإرشادات والمعايير"
            >
              <HelpCircle className="w-4 h-4" />
            </button>

            {/* Quick Action Button */}
            {onQuickAction && (
              <button
                onClick={() => onQuickAction("new_facility")}
                className="hidden sm:inline-flex items-center gap-1.5 rounded-lg bg-[#1E3A8A] px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-[#1E40AF] transition-all"
              >
                <span>+ منشأة جديدة</span>
              </button>
            )}
          </div>
        </header>

        {/* Scrollable Screen Content Container */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 space-y-6">
          {children}
        </main>
      </div>

      {/* Help Modal */}
      {showHelp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl border border-[#E2E8F0] space-y-4 text-right">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-base text-[#0F172A] flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-teal-600" />
                دليل نظام إدارة المنشآت والمرافق (HLT-01)
              </h3>
              <button onClick={() => setShowHelp(false)} className="rounded-lg p-1 text-[#64748B] hover:bg-[#F1F5F9]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="text-xs text-[#475569] leading-relaxed space-y-2">
              <p>
                <strong>الهرمية التشغيلية:</strong> تنقسم المنظمة إلى منشآت ومستشفيات، ويحتوي كل مستشفى على مبانٍ وطوابق، وتتوزع الأقسام الطبية عبر الطوابق، بينما تقع الغرف والكبائن السريرية تحت مظلة الوحدات التشغيلية.
              </p>
              <p>
                <strong>الفرق بين الغرف والأسرة:</strong> هذا الموديل يدير البنية التحتية والمواقع الإنشائية (الغرف، العيادات، نقاط الفحص)، بينما تدار الأسرة وحركات التنويم والشاغرية عبر موديول الأسرة المخصص (HLT-08).
              </p>
              <p>
                <strong>ساعات العمل والاستثناءات:</strong> يمكن ضبط جداول عمل موحدة للمنشأة مع إمكانية تطبيق استثناءات وعطلات رسمية محددة لقسم دون آخر.
              </p>
            </div>
            <button
              onClick={() => setShowHelp(false)}
              className="w-full py-2 rounded-xl bg-[#0F172A] text-white text-xs font-semibold hover:bg-[#1E293B]"
            >
              فهمت، إغلاق الدليل
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
