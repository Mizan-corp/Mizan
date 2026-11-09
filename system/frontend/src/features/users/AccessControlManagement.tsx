import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield, Users, Briefcase, KeyRound, FileText, CheckCircle2,
  Search, Plus, RefreshCw, Lock, Unlock, Sparkles,
  AlertOctagon, HelpCircle, UserCheck, ShieldAlert
} from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner } from "@/components/ui";

// ─── Interfaces ─────────────────────────────────────────────────────────────

interface AccountTypeInfo {
  code: string;
  name: string;
  name_en: string;
  description: string;
  can_access_clinical: boolean;
  isolation_level: string;
}

interface OrgPositionItem {
  id: string;
  code: string;
  name: string;
  name_en: string;
  category: string;
  department_name?: string;
  description?: string;
}

interface SysRoleItem {
  id: string;
  code: string;
  name: string;
  name_en: string;
  description?: string;
  is_system: boolean;
  is_clinical: boolean;
  permissions: string[];
}

interface SysPermissionItem {
  id: string;
  code: string;
  module: string;
  action: string;
  name: string;
  name_en: string;
  description?: string;
  is_clinical: boolean;
  data_sensitivity: "normal" | "sensitive" | "restricted";
}

interface UserSummary {
  id: string;
  username: string;
  full_name: string;
  role: string;
  account_type?: string;
  is_active: boolean;
  is_manager: boolean;
  is_superadmin?: boolean;
  permissions?: string[];
  positions?: Array<{ id: string; name: string; category: string; is_primary: boolean }>;
}

interface EffectiveProfile {
  user_id: string;
  username: string;
  full_name: string;
  account_type: string;
  is_superadmin: boolean;
  has_break_glass: boolean;
  positions: string[];
  roles: string[];
  permissions_count: number;
  permissions: string[];
  clinical_permissions: string[];
  accessible_facility_ids: number[];
  accessible_department_ids: number[];
  assigned_patient_ids: number[];
}

interface AuditLogEntry {
  id: string;
  user_id?: string;
  account_type?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  is_clinical: boolean;
  decision: "granted" | "denied" | "break_glass";
  ip_address?: string;
  details?: any;
  created_at: string;
}

// ─── Category Group Helper ─────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, { ar: string; en: string; group: string; color: string }> = {
  executive_admin: { ar: "الإدارة والتنفيذ", en: "Executive & Admin", group: "A", color: "bg-purple-100 text-purple-800 border-purple-200" },
  medical_staff: { ar: "الكوادر الطبية", en: "Medical Staff", group: "B", color: "bg-blue-100 text-blue-800 border-blue-200" },
  nursing_staff: { ar: "الكوادر التمريضية", en: "Nursing Staff", group: "C", color: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  lab_radiology: { ar: "المختبر والأشعة", en: "Laboratory & Radiology", group: "D", color: "bg-cyan-100 text-cyan-800 border-cyan-200" },
  pharmacy: { ar: "الصيدلة الدوائية", en: "Pharmacy", group: "E", color: "bg-teal-100 text-teal-800 border-teal-200" },
  finance_insurance: { ar: "المالية والتأمين", en: "Finance & Insurance", group: "F", color: "bg-amber-100 text-amber-800 border-amber-200" },
  human_resources: { ar: "الموارد البشرية", en: "Human Resources", group: "G", color: "bg-rose-100 text-rose-800 border-rose-200" },
  procurement_maintenance: { ar: "المشتريات والمخازن والصيانة", en: "Procurement & Maintenance", group: "H", color: "bg-orange-100 text-orange-800 border-orange-200" },
  procurement_inventory: { ar: "المشتريات والمخازن والصيانة", en: "Procurement & Maintenance", group: "H", color: "bg-orange-100 text-orange-800 border-orange-200" },
  it_technical: { ar: "تقنية المعلومات والأنظمة", en: "IT & Technical", group: "I", color: "bg-slate-100 text-slate-800 border-slate-200" },
};

export default function AccessControlManagement() {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<"users" | "positions" | "accounts" | "roles" | "break_glass" | "audit">("users");

  // Filter States
  const [positionCategoryFilter, setPositionCategoryFilter] = useState<string>("all");
  const [positionSearch, setPositionSearch] = useState<string>("");
  const [userSearch, setUserSearch] = useState<string>("");
  const [auditClinicalOnly, setAuditClinicalOnly] = useState<boolean>(false);

  // Modals & Target User
  const [selectedUser, setSelectedUser] = useState<UserSummary | null>(null);
  const [effectiveProfile, setEffectiveProfile] = useState<EffectiveProfile | null>(null);

  // Position Assign Modal State
  const [assignPosOpen, setAssignPosOpen] = useState(false);
  const [posForm, setPosForm] = useState({ position_id: "", department_name: "", is_primary: true });

  // Role Assign Modal State
  const [assignRoleOpen, setAssignRoleOpen] = useState(false);
  const [roleForm, setRoleForm] = useState({ role_id: "", facility_id: "", department_id: "", valid_until: "" });

  // Override Modal State
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideForm, setOverrideForm] = useState({ permission_code: "", override_type: "allow", reason: "" });

  // Break-Glass Form
  const [breakGlassForm, setBreakGlassForm] = useState({ target_patient_id: "", grant_reason: "", duration_hours: 4 });
  const [breakGlassResult, setBreakGlassResult] = useState<string | null>(null);

  // ─── Queries ─────────────────────────────────────────────────────────────

  const usersQuery = useQuery({
    queryKey: ["authz-users"],
    queryFn: () => api.get<UserSummary[]>("/users"),
  });

  const accountTypesQuery = useQuery({
    queryKey: ["authz-account-types"],
    queryFn: () => api.get<{ account_types: AccountTypeInfo[]; isolation_policy: any }>("/authz/account-types"),
  });

  const positionsQuery = useQuery({
    queryKey: ["authz-positions"],
    queryFn: () => api.get<OrgPositionItem[]>("/authz/positions"),
  });

  const rolesQuery = useQuery({
    queryKey: ["authz-roles"],
    queryFn: () => api.get<SysRoleItem[]>("/authz/roles"),
  });

  const permsQuery = useQuery({
    queryKey: ["authz-permissions"],
    queryFn: () => api.get<SysPermissionItem[]>("/authz/permissions"),
  });

  const auditQuery = useQuery({
    queryKey: ["authz-audit", auditClinicalOnly],
    queryFn: () => api.get<AuditLogEntry[]>(`/authz/audit-logs${auditClinicalOnly ? "?is_clinical=true" : ""}`),
  });

  // ─── Mutations ───────────────────────────────────────────────────────────

  const assignPositionMutation = useMutation({
    mutationFn: () => api.post(`/authz/users/${selectedUser!.id}/assign-position`, {
      position_id: posForm.position_id,
      department_name: posForm.department_name || undefined,
      is_primary: posForm.is_primary,
    }),
    onSuccess: () => {
      setAssignPosOpen(false);
      setPosForm({ position_id: "", department_name: "", is_primary: true });
      qc.invalidateQueries({ queryKey: ["authz-users"] });
      if (selectedUser) loadEffectiveProfile(selectedUser);
    },
  });

  const assignRoleMutation = useMutation({
    mutationFn: () => api.post(`/authz/users/${selectedUser!.id}/assign-role`, {
      role_id: roleForm.role_id,
      facility_id: roleForm.facility_id ? parseInt(roleForm.facility_id, 10) : undefined,
      department_id: roleForm.department_id ? parseInt(roleForm.department_id, 10) : undefined,
      valid_until: roleForm.valid_until ? new Date(roleForm.valid_until).toISOString() : undefined,
    }),
    onSuccess: () => {
      setAssignRoleOpen(false);
      setRoleForm({ role_id: "", facility_id: "", department_id: "", valid_until: "" });
      qc.invalidateQueries({ queryKey: ["authz-users"] });
      if (selectedUser) loadEffectiveProfile(selectedUser);
    },
  });

  const overrideMutation = useMutation({
    mutationFn: () => api.post(`/authz/users/${selectedUser!.id}/permission-override`, {
      permission_code: overrideForm.permission_code,
      override_type: overrideForm.override_type,
      reason: overrideForm.reason || undefined,
    }),
    onSuccess: () => {
      setOverrideOpen(false);
      setOverrideForm({ permission_code: "", override_type: "allow", reason: "" });
      if (selectedUser) loadEffectiveProfile(selectedUser);
    },
  });

  const breakGlassMutation = useMutation({
    mutationFn: () => api.post<{ message: string; expires_at: string }>("/authz/break-glass", {
      target_patient_id: breakGlassForm.target_patient_id ? parseInt(breakGlassForm.target_patient_id, 10) : undefined,
      grant_reason: breakGlassForm.grant_reason,
      duration_hours: Number(breakGlassForm.duration_hours),
    }),
    onSuccess: (data) => {
      setBreakGlassResult(data.message);
      setBreakGlassForm({ target_patient_id: "", grant_reason: "", duration_hours: 4 });
      qc.invalidateQueries({ queryKey: ["authz-audit"] });
    },
  });

  const seedCatalogMutation = useMutation({
    mutationFn: () => api.post("/authz/seed", {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["authz-positions"] });
      qc.invalidateQueries({ queryKey: ["authz-roles"] });
      qc.invalidateQueries({ queryKey: ["authz-permissions"] });
    },
  });

  // ─── Helpers ─────────────────────────────────────────────────────────────

  async function loadEffectiveProfile(u: UserSummary) {
    setSelectedUser(u);
    try {
      const res = await api.get<EffectiveProfile>(`/authz/users/${u.id}/effective-permissions`);
      setEffectiveProfile(res);
    } catch (err) {
      console.error("Failed to load effective profile", err);
    }
  }

  // Filtered lists
  const filteredPositions = (positionsQuery.data || []).filter((p) => {
    const matchCat = positionCategoryFilter === "all" || p.category === positionCategoryFilter;
    const matchQ = !positionSearch ||
      p.name.toLowerCase().includes(positionSearch.toLowerCase()) ||
      p.name_en.toLowerCase().includes(positionSearch.toLowerCase()) ||
      p.code.toLowerCase().includes(positionSearch.toLowerCase());
    return matchCat && matchQ;
  });

  const filteredUsers = (usersQuery.data || []).filter((u) => {
    return !userSearch ||
      u.username.toLowerCase().includes(userSearch.toLowerCase()) ||
      u.full_name.toLowerCase().includes(userSearch.toLowerCase()) ||
      (u.account_type && u.account_type.toLowerCase().includes(userSearch.toLowerCase()));
  });

  return (
    <div className="flex flex-col gap-6" dir="rtl">
      {/* Editorial Luxury Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#651E2C] via-[#521924] to-[#3B111A] p-6 text-[#FAF6F0] shadow-md border border-[#7D2637]/40">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-semibold bg-[#FAF6F0]/20 text-[#FAF6F0] backdrop-blur-sm border border-[#FAF6F0]/20">
                <Shield className="w-3.5 h-3.5 text-amber-300" />
                منظومة الصلاحيات والتحكم المتقدمة • RBAC + ABAC Suite
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] bg-emerald-500/25 text-emerald-200 border border-emerald-400/30 font-medium">
                معيار HIPAA / GDPR
              </span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#FAF6F0]">
              إدارة الصلاحيات، المسميات الوظيفية، وأنواع الحسابات
            </h1>
            <p className="text-sm text-[#FAF6F0]/80 mt-1 max-w-3xl font-light leading-relaxed">
              فصل هيكلي صارم بين <strong className="text-amber-200 font-semibold">المسمى الوظيفي</strong> (ما يشغله الموظف)، 
              و<strong className="text-amber-200 font-semibold">نوع الحساب</strong> (طبيعة الحساب)، 
              و<strong className="text-amber-200 font-semibold">الأدوار والصلاحيات</strong> (RBAC + ABAC مع العزل السريري الكامل للمدراء التقنيين).
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                qc.invalidateQueries({ queryKey: ["authz-users"] });
                qc.invalidateQueries({ queryKey: ["authz-positions"] });
                qc.invalidateQueries({ queryKey: ["authz-roles"] });
                qc.invalidateQueries({ queryKey: ["authz-permissions"] });
                qc.invalidateQueries({ queryKey: ["authz-audit"] });
              }}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-white/10 hover:bg-white/20 text-[#FAF6F0] transition-colors border border-white/15"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              تحديث البيانات
            </button>
            <button
              onClick={() => seedCatalogMutation.mutate()}
              disabled={seedCatalogMutation.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-[#FAF6F0] text-[#651E2C] hover:bg-white shadow-sm transition-all disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-600" />
              {seedCatalogMutation.isPending ? "جارٍ التهيئة..." : "إعادة تهيئة الدليل (98 مسمى)"}
            </button>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex flex-wrap gap-2 border-b border-[#E5DDD0] pb-2">
        {[
          { key: "users", label: "المستخدمون والتعيينات", icon: Users, count: usersQuery.data?.length },
          { key: "positions", label: "دليل المسميات (98 وظيفة)", icon: Briefcase, count: positionsQuery.data?.length ?? 98 },
          { key: "accounts", label: "أنواع الحسابات (9 فئات)", icon: UserCheck, count: 9 },
          { key: "roles", label: "الأدوار ومصفوفة الصلاحيات", icon: Shield, count: rolesQuery.data?.length },
          { key: "break_glass", label: "كسر الزجاج للطوارئ", icon: AlertOctagon, badge: "حرج" },
          { key: "audit", label: "سجل تدقيق الوصول (HIPAA)", icon: FileText, count: auditQuery.data?.length },
        ].map((t) => {
          const Icon = t.icon;
          const isActive = activeTab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key as any)}
              className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? "bg-[#651E2C] text-[#FAF6F0] shadow-sm font-semibold"
                  : "bg-[#FAF6F0] text-[#706A60] hover:bg-[#F3ECE0] border border-[#E5DDD0]"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-amber-300" : "text-[#706A60]"}`} />
              <span>{t.label}</span>
              {t.count !== undefined && (
                <span className={`px-2 py-0.5 rounded-full text-xs num font-mono ${
                  isActive ? "bg-white/20 text-[#FAF6F0]" : "bg-[#E5DDD0] text-[#262321]"
                }`}>
                  {t.count}
                </span>
              )}
              {t.badge && (
                <span className="px-1.5 py-0.2 rounded text-[10px] bg-rose-500/20 text-rose-700 font-bold border border-rose-300">
                  {t.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ─── TAB 1: USERS & ACTIVE ASSIGNMENTS ───────────────────────────────── */}
      {activeTab === "users" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#FAF6F0] p-4 rounded-xl border border-[#E5DDD0]">
            <div className="relative w-full sm:w-80">
              <Search className="absolute right-3 top-2.5 w-4 h-4 text-[#706A60]" />
              <input
                type="text"
                placeholder="بحث بالاسم، اسم المستخدم، نوع الحساب..."
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                className="w-full pr-9 pl-3 py-2 text-sm rounded-lg bg-white border border-[#E5DDD0] text-[#262321] focus:outline-none focus:border-[#651E2C]"
              />
            </div>
            <div className="text-xs text-[#706A60]">
              إجمالي المستخدمين: <strong className="text-[#262321] font-mono">{filteredUsers.length}</strong>
            </div>
          </div>

          {usersQuery.isLoading ? (
            <div className="flex items-center justify-center p-12 text-[#706A60]">
              <Spinner />
              <span className="mr-2">جارٍ تحميل المستخدمين...</span>
            </div>
          ) : filteredUsers.length === 0 ? (
            <Empty text="لم يتم العثور على مستخدمين مطابقين" />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-[#E5DDD0] bg-white shadow-xs">
              <table className="w-full text-sm text-right">
                <thead className="bg-[#FAF6F0] border-b border-[#E5DDD0] text-xs text-[#706A60] font-semibold">
                  <tr>
                    <th className="p-3.5">المستخدم</th>
                    <th className="p-3.5">نوع الحساب</th>
                    <th className="p-3.5">المسمى الوظيفي (Job Title)</th>
                    <th className="p-3.5">الدور النظامي (RBAC)</th>
                    <th className="p-3.5">العزل السريري</th>
                    <th className="p-3.5">الحالة</th>
                    <th className="p-3.5 text-center">الإجراءات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5DDD0]/60">
                  {filteredUsers.map((u) => {
                    const isTechAdmin = u.role === "admin" || u.is_superadmin;
                    return (
                      <tr key={u.id} className="hover:bg-[#FAF6F0]/60 transition-colors">
                        <td className="p-3.5">
                          <div className="font-semibold text-[#262321]">{u.full_name}</div>
                          <div className="text-xs text-[#706A60] font-mono mt-0.5" dir="ltr">@{u.username}</div>
                        </td>
                        <td className="p-3.5">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-[#651E2C]/10 text-[#651E2C] border border-[#651E2C]/20">
                            {u.account_type || "employee"}
                          </span>
                        </td>
                        <td className="p-3.5">
                          {u.positions && u.positions.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {u.positions.map((p, idx) => (
                                <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-amber-50 text-amber-800 border border-amber-200 font-medium">
                                  {p.name}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-[#706A60] italic">غير معيّن</span>
                          )}
                        </td>
                        <td className="p-3.5">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-200">
                            {u.role}
                          </span>
                        </td>
                        <td className="p-3.5">
                          {isTechAdmin ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-rose-50 text-rose-700 border border-rose-200 font-medium">
                              <Lock className="w-3 h-3 text-rose-600" />
                              معزول عن السجلات السريرية
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                              <Unlock className="w-3 h-3 text-emerald-600" />
                              حسب الدور السريري
                            </span>
                          )}
                        </td>
                        <td className="p-3.5">
                          <Badge tone={u.is_active ? "success" : "muted"}>
                            {u.is_active ? "نشط" : "معطل"}
                          </Badge>
                        </td>
                        <td className="p-3.5 text-center">
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              onClick={() => {
                                setSelectedUser(u);
                                setPosForm({ position_id: "", department_name: "", is_primary: true });
                                setAssignPosOpen(true);
                              }}
                              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-amber-50 text-amber-800 border border-amber-300 hover:bg-amber-100 transition-colors"
                              title="إسناد مسمى وظيفي من دليل الـ 98 وظيفة"
                            >
                              المسمى
                            </button>
                            <button
                              onClick={() => {
                                setSelectedUser(u);
                                setRoleForm({ role_id: "", facility_id: "", department_id: "", valid_until: "" });
                                setAssignRoleOpen(true);
                              }}
                              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-blue-50 text-blue-800 border border-blue-300 hover:bg-blue-100 transition-colors"
                              title="إسناد دور وصلاحيات مع نطاق المنشأة ABAC"
                            >
                              الدور
                            </button>
                            <button
                              onClick={() => loadEffectiveProfile(u)}
                              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-[#FAF6F0] text-[#651E2C] border border-[#651E2C]/30 hover:bg-[#651E2C] hover:text-white transition-colors"
                              title="فحص الصلاحيات الفعلية والتجاوزات"
                            >
                              الصلاحيات الفعلية
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ─── TAB 2: ORGANIZATIONAL POSITIONS CATALOG (98 JOB TITLES) ──────── */}
      {activeTab === "positions" && (
        <div className="space-y-6">
          <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-sm leading-relaxed flex items-start gap-3">
            <HelpCircle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold block mb-0.5">قاعدة التصميم المعماري الأساسية:</strong>
              المسميات الوظيفية (Job Titles) تمثل ما يقوم به الموظف واقعياً في المنشأة الصحية (98 مسمى مصنف عبر المجموعات من A إلى I)، 
              ولا تمنح صلاحيات برمجية مباشرة داخل النظام. الصلاحيات تُمنح حصراً عبر الأدوار (Roles) والنطاقات الجغرافية (ABAC) 
              لمنع الخلط بين المسمى الإداري والصلاحية التقنية.
            </div>
          </div>

          {/* Filter Pills & Search */}
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 bg-[#FAF6F0] p-4 rounded-xl border border-[#E5DDD0]">
            <div className="flex flex-wrap gap-1.5">
              <button
                onClick={() => setPositionCategoryFilter("all")}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  positionCategoryFilter === "all"
                    ? "bg-[#651E2C] text-white font-semibold"
                    : "bg-white text-[#706A60] border border-[#E5DDD0] hover:bg-[#E5DDD0]"
                }`}
              >
                جميع المجموعات (98)
              </button>
              {Object.entries(CATEGORY_LABELS).map(([k, meta]) => (
                <button
                  key={k}
                  onClick={() => setPositionCategoryFilter(k)}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    positionCategoryFilter === k
                      ? "bg-[#651E2C] text-white font-semibold"
                      : "bg-white text-[#706A60] border border-[#E5DDD0] hover:bg-[#E5DDD0]"
                  }`}
                >
                  <span className="font-mono font-bold mr-1">[{meta.group}]</span>
                  {meta.ar}
                </button>
              ))}
            </div>

            <div className="relative w-full md:w-64">
              <Search className="absolute right-3 top-2.5 w-4 h-4 text-[#706A60]" />
              <input
                type="text"
                placeholder="بحث بالاسم العربي أو الإنجليزي..."
                value={positionSearch}
                onChange={(e) => setPositionSearch(e.target.value)}
                className="w-full pr-9 pl-3 py-1.5 text-xs rounded-lg bg-white border border-[#E5DDD0] text-[#262321] focus:outline-none focus:border-[#651E2C]"
              />
            </div>
          </div>

          {/* Position Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredPositions.map((pos) => {
              const meta = CATEGORY_LABELS[pos.category] || { ar: pos.category, en: pos.category, group: "?", color: "bg-gray-100 text-gray-800" };
              return (
                <div
                  key={pos.code}
                  className="rounded-xl border border-[#E5DDD0] bg-white p-4 shadow-2xs hover:shadow-sm hover:border-[#651E2C]/40 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${meta.color}`}>
                        مجموعة {meta.group} • {meta.ar}
                      </span>
                      <span className="text-[11px] font-mono text-[#706A60] bg-[#FAF6F0] px-2 py-0.5 rounded border border-[#E5DDD0]">
                        {pos.code}
                      </span>
                    </div>

                    <h3 className="text-base font-bold text-[#262321] mt-1">
                      {pos.name}
                    </h3>
                    <div className="text-xs text-[#706A60] font-sans mt-0.5 font-medium" dir="ltr">
                      {pos.name_en}
                    </div>

                    <p className="text-xs text-[#706A60] mt-2.5 leading-relaxed line-clamp-2">
                      {pos.description || "منصب وظيفي تنفيذي / سريري معتمد في الهيكل التنظيمي للمستشفيات والعيادات."}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[#E5DDD0]/60 flex items-center justify-between text-[11px] text-[#706A60]">
                    <span>القسم الافتراضي: <strong>{pos.department_name || meta.ar}</strong></span>
                    <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">معتمد</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ─── TAB 3: ACCOUNT TYPES & ISOLATION POLICIES ──────────────────────── */}
      {activeTab === "accounts" && (
        <div className="space-y-6">
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-950 text-sm leading-relaxed flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-rose-700 shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold block mb-0.5">سياسة العزل السريري الصارمة (Technical vs Clinical Boundary):</strong>
              الحسابات ذات النوع <code>administrator</code> (مدراء النظام والتقنيين) معزولة تماماً ولا تملك أي حق وصول تلقائي 
              للسجلات الطبية التراكمية (EMR) أو الوصفات الدوائية لضمان خصوصية المرضى والامتثال للأنظمة الصحية العالمية (HIPAA/GDPR). 
              الوصول للبيانات الطبية يتطلب إما إسناد دور سريري معتمد أو تفعيل إذن "كسر الزجاج" للطوارئ مع توثيق السبب كاملاً.
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(accountTypesQuery.data?.account_types || []).map((acc) => {
              const isRestricted = !acc.can_access_clinical;
              return (
                <div
                  key={acc.code}
                  className="rounded-xl border border-[#E5DDD0] bg-white p-5 shadow-2xs hover:shadow-sm transition-all"
                >
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-bold">
                      {acc.code}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                      acc.can_access_clinical
                        ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                        : "bg-rose-100 text-rose-800 border border-rose-200"
                    }`}>
                      {acc.can_access_clinical ? "مسموح بالوصول السريري" : "معزول عن السجلات السريرية"}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-[#262321]">{acc.name}</h3>
                  <div className="text-xs text-[#706A60] font-mono mt-0.5" dir="ltr">{acc.name_en}</div>

                  <p className="text-xs text-[#706A60] mt-3 leading-relaxed">
                    {acc.description}
                  </p>

                  <div className="mt-4 pt-3 border-t border-[#E5DDD0] text-[11px] text-[#706A60] flex items-center justify-between">
                    <span>مستوى العزل: <strong>{acc.isolation_level}</strong></span>
                    {isRestricted ? (
                      <span className="text-rose-600 flex items-center gap-1 font-semibold">
                        <Lock className="w-3 h-3" /> عزل EMR
                      </span>
                    ) : (
                      <span className="text-emerald-600 flex items-center gap-1 font-semibold">
                        <CheckCircle2 className="w-3 h-3" /> سريري
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ─── TAB 4: ROLES & PERMISSIONS MATRIX (RBAC + ABAC) ───────────────── */}
      {activeTab === "roles" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Roles List */}
            <div className="lg:col-span-1 space-y-3">
              <h3 className="text-base font-bold text-[#262321] flex items-center gap-2">
                <Shield className="w-4 h-4 text-[#651E2C]" />
                الأدوار القياسية في المنظومة ({rolesQuery.data?.length || 0})
              </h3>
              <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                {(rolesQuery.data || []).map((r) => (
                  <div
                    key={r.code}
                    className="p-3.5 rounded-xl border border-[#E5DDD0] bg-white hover:border-[#651E2C] transition-all cursor-default"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-sm text-[#262321]">{r.name}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        r.is_clinical ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"
                      }`}>
                        {r.is_clinical ? "دور سريري" : "دور إداري / مالي"}
                      </span>
                    </div>
                    <div className="text-xs text-[#706A60] font-mono mt-0.5" dir="ltr">{r.code}</div>
                    <p className="text-xs text-[#706A60] mt-2 line-clamp-2">{r.description}</p>
                    <div className="mt-2 text-[11px] text-[#651E2C] font-semibold">
                      عدد الصلاحيات المضمنة: {r.permissions?.length || 0}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Granular Permissions Matrix */}
            <div className="lg:col-span-2 space-y-3">
              <h3 className="text-base font-bold text-[#262321] flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-[#651E2C]" />
                مصفوفة الصلاحيات الدقيقة ({permsQuery.data?.length || 0})
              </h3>
              <div className="overflow-x-auto rounded-xl border border-[#E5DDD0] bg-white shadow-2xs max-h-[600px]">
                <table className="w-full text-xs text-right">
                  <thead className="bg-[#FAF6F0] border-b border-[#E5DDD0] text-[#706A60] sticky top-0">
                    <tr>
                      <th className="p-3">رمز الصلاحية</th>
                      <th className="p-3">المجال / الموديل</th>
                      <th className="p-3">الوصف</th>
                      <th className="p-3">طبيعة الصلاحية</th>
                      <th className="p-3">حساسية البيانات</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5DDD0]">
                    {(permsQuery.data || []).map((p) => (
                      <tr key={p.code} className="hover:bg-[#FAF6F0]/40">
                        <td className="p-3 font-mono font-bold text-[#651E2C]" dir="ltr">
                          {p.code}
                        </td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-semibold font-mono">
                            {p.module}
                          </span>
                        </td>
                        <td className="p-3 text-[#262321] font-medium">
                          {p.name}
                        </td>
                        <td className="p-3">
                          {p.is_clinical ? (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800 font-semibold">
                              سريرية (EMR)
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700">
                              إدارية / تشغيلية
                            </span>
                          )}
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            p.data_sensitivity === "restricted"
                              ? "bg-rose-100 text-rose-800"
                              : p.data_sensitivity === "sensitive"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-blue-100 text-blue-800"
                          }`}>
                            {p.data_sensitivity === "restricted" ? "مقيد / محمي" : p.data_sensitivity === "sensitive" ? "حساس" : "عادي"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 5: EMERGENCY BREAK-GLASS PROTOCOL ─────────────────────────── */}
      {activeTab === "break_glass" && (
        <div className="space-y-6 max-w-3xl mx-auto">
          <div className="p-5 rounded-2xl bg-gradient-to-br from-rose-900 to-rose-950 text-white shadow-md border border-rose-700">
            <div className="flex items-center gap-2 mb-2">
              <AlertOctagon className="w-6 h-6 text-amber-400 animate-pulse" />
              <h2 className="text-xl font-bold">بروتوكول كسر الزجاج للطوارئ السريرية (Break-Glass Protocol)</h2>
            </div>
            <p className="text-xs text-rose-100 leading-relaxed mt-2">
              يُستخدم هذا البروتوكول حصراً في حالات الطوارئ القصوى عندما يحتاج الطبيب أو الممارس الصحي الوصول الفوري 
              لسجل مريض في حالة حرجة دون وجود إسناد مسبق. تفعيل البروتوكول يمنح صلاحيات سريرية مؤقتة 
              ويرسل إشعاراً فورياً لفريق الامتثال ويسجل تدقيقاً غير قابل للحذف في سجل الـ HIPAA.
            </p>
          </div>

          {breakGlassResult && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-sm flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <span>{breakGlassResult}</span>
              </div>
              <button onClick={() => setBreakGlassResult(null)} className="text-xs font-bold underline">إغلاق</button>
            </div>
          )}

          <div className="p-6 rounded-2xl border border-[#E5DDD0] bg-white shadow-xs space-y-4">
            <h3 className="font-bold text-base text-[#262321] border-b border-[#E5DDD0] pb-2">
              طلب تفعيل إذن الوصول الطارئ
            </h3>

            <div>
              <label className="block text-xs font-bold text-[#706A60] mb-1">
                رقم ملف المريض المستهدف (Patient ID / MRN) — اختياري إذا كان لطوارئ المنشأة
              </label>
              <Input
                type="number"
                placeholder="مثال: 1042"
                value={breakGlassForm.target_patient_id}
                onChange={(e) => setBreakGlassForm({ ...breakGlassForm, target_patient_id: e.target.value })}
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-[#706A60] mb-1">
                المدة الزمنية للتصريح المؤقت (بالساعات)
              </label>
              <Select
                value={String(breakGlassForm.duration_hours)}
                onChange={(e) => setBreakGlassForm({ ...breakGlassForm, duration_hours: Number(e.target.value) })}
              >
                <option value="1">ساعة واحدة (حالة طارئة حرجة)</option>
                <option value="2">ساعتان (إنعاش / عمليات عاجلة)</option>
                <option value="4">4 ساعات (مناوبة طوارئ ER)</option>
                <option value="8">8 ساعات (وردية كاملة)</option>
                <option value="24">24 ساعة (تحت إشراف مباشر)</option>
              </Select>
            </div>

            <div>
              <label className="block text-xs font-bold text-[#706A60] mb-1">
                المبرر الطبي الدقيق والتفصيلي (إلزامي — لا يقل عن 10 أحرف) *
              </label>
              <textarea
                rows={4}
                value={breakGlassForm.grant_reason}
                onChange={(e) => setBreakGlassForm({ ...breakGlassForm, grant_reason: e.target.value })}
                placeholder="اذكر بدقة الحالة السريرية، أسباب تجاوز الإسناد الاعتيادي، ورمز الحالة الطارئة..."
                className="w-full text-xs p-3 rounded-lg border border-[#E5DDD0] focus:outline-none focus:border-[#651E2C] text-[#262321]"
              />
            </div>

            {breakGlassMutation.isError && (
              <ErrorBox message={(breakGlassMutation.error as Error).message} />
            )}

            <Button
              variant="danger"
              className="w-full h-11 font-bold text-sm bg-[#651E2C] hover:bg-[#521924]"
              disabled={breakGlassMutation.isPending || breakGlassForm.grant_reason.trim().length < 10}
              onClick={() => breakGlassMutation.mutate()}
            >
              {breakGlassMutation.isPending ? <Spinner /> : "تأكيد وتفعيل كسر الزجاج وتوثيق التدقيق السريري"}
            </Button>
          </div>
        </div>
      )}

      {/* ─── TAB 6: ACCESS AUDIT LOG (HIPAA / GDPR) ─────────────────────────── */}
      {activeTab === "audit" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#FAF6F0] p-4 rounded-xl border border-[#E5DDD0]">
            <div className="flex items-center gap-2">
              <label className="text-xs font-bold text-[#262321] cursor-pointer flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={auditClinicalOnly}
                  onChange={(e) => setAuditClinicalOnly(e.target.checked)}
                  className="rounded border-[#E5DDD0] text-[#651E2C]"
                />
                عرض طلبات الوصول للبيانات السريرية فقط (EMR Clinical Records)
              </label>
            </div>
            <div className="text-xs text-[#706A60]">
              سجلات التدقيق المعروضة: <strong className="text-[#262321] font-mono">{auditQuery.data?.length || 0}</strong>
            </div>
          </div>

          {auditQuery.isLoading ? (
            <div className="flex items-center justify-center p-12 text-[#706A60]">
              <Spinner />
              <span className="mr-2">جارٍ جلب سجلات التدقيق...</span>
            </div>
          ) : !auditQuery.data?.length ? (
            <Empty text="لا توجد سجلات تدقيق وصول مطابقة" />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-[#E5DDD0] bg-white shadow-2xs">
              <table className="w-full text-xs text-right">
                <thead className="bg-[#FAF6F0] border-b border-[#E5DDD0] text-[#706A60] font-semibold">
                  <tr>
                    <th className="p-3">التوقيت (UTC)</th>
                    <th className="p-3">نوع الحساب</th>
                    <th className="p-3">الإجراء المطلوب</th>
                    <th className="p-3">المورد / المعرف</th>
                    <th className="p-3">الطبيعة</th>
                    <th className="p-3">القرار</th>
                    <th className="p-3">عنوان IP</th>
                    <th className="p-3">التفاصيل</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5DDD0]/60">
                  {auditQuery.data.map((log) => (
                    <tr key={log.id} className="hover:bg-[#FAF6F0]/40">
                      <td className="p-3 font-mono text-[#706A60]" dir="ltr">
                        {log.created_at ? new Date(log.created_at).toLocaleString("ar-SA") : "—"}
                      </td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-mono font-medium">
                          {log.account_type || "employee"}
                        </span>
                      </td>
                      <td className="p-3 font-mono font-bold text-[#262321]" dir="ltr">
                        {log.action}
                      </td>
                      <td className="p-3 font-mono text-[#706A60]" dir="ltr">
                        {log.resource_type}:{log.resource_id || "all"}
                      </td>
                      <td className="p-3">
                        {log.is_clinical ? (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-rose-100 text-rose-800 font-bold">
                            سريري EMR
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700">
                            إداري
                          </span>
                        )}
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          log.decision === "granted"
                            ? "bg-emerald-100 text-emerald-800"
                            : log.decision === "break_glass"
                            ? "bg-amber-100 text-amber-800 border border-amber-300"
                            : "bg-rose-100 text-rose-800"
                        }`}>
                          {log.decision === "granted" ? "ممنوح" : log.decision === "break_glass" ? "كسر زجاج" : "مرفوض"}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-[#706A60]" dir="ltr">
                        {log.ip_address || "127.0.0.1"}
                      </td>
                      <td className="p-3 text-[11px] text-[#706A60] max-w-xs truncate" title={JSON.stringify(log.details)}>
                        {log.details?.reason || (log.details ? JSON.stringify(log.details) : "—")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ─── MODAL: ASSIGN ORGANIZATIONAL POSITION (JOB TITLE) ───────────── */}
      <Modal open={assignPosOpen} onClose={() => setAssignPosOpen(false)} title={`تعيين مسمى وظيفي — ${selectedUser?.full_name || ""}`} wide>
        <div className="space-y-4" dir="rtl">
          <p className="text-xs text-[#706A60] leading-relaxed">
            اختر المسمى الوظيفي الرسمي للموظف من دليل الـ 98 وظيفة القياسي. المسمى الوظيفي يحدد الصفة المهنية والقسم.
          </p>

          <div>
            <label className="block text-xs font-bold text-[#262321] mb-1">اختر المسمى الوظيفي *</label>
            <Select
              value={posForm.position_id}
              onChange={(e) => {
                const pid = e.target.value;
                const pos = positionsQuery.data?.find((x) => x.id === pid);
                setPosForm({
                  ...posForm,
                  position_id: pid,
                  department_name: pos?.department_name || posForm.department_name,
                });
              }}
            >
              <option value="">-- اختر من قائمة الـ 98 وظيفة --</option>
              {positionsQuery.data?.map((p) => {
                const meta = CATEGORY_LABELS[p.category] || { group: "?" };
                return (
                  <option key={p.id} value={p.id}>
                    [{meta.group}] {p.name} — {p.name_en} ({p.code})
                  </option>
                );
              })}
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-[#262321] mb-1">اسم القسم / الوحدة</label>
              <Input
                placeholder="القسم الإداري أو السريري"
                value={posForm.department_name}
                onChange={(e) => setPosForm({ ...posForm, department_name: e.target.value })}
              />
            </div>
            <div className="flex items-center pt-5">
              <label className="text-xs font-bold text-[#262321] cursor-pointer flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={posForm.is_primary}
                  onChange={(e) => setPosForm({ ...posForm, is_primary: e.target.checked })}
                  className="rounded border-[#E5DDD0] text-[#651E2C]"
                />
                مسمى أساسي (Primary Position)
              </label>
            </div>
          </div>

          {assignPositionMutation.isError && (
            <ErrorBox message={(assignPositionMutation.error as Error).message} />
          )}

          <Button
            className="w-full h-10 font-bold bg-[#651E2C] hover:bg-[#521924] text-white"
            disabled={assignPositionMutation.isPending || !posForm.position_id}
            onClick={() => assignPositionMutation.mutate()}
          >
            {assignPositionMutation.isPending ? <Spinner /> : "تأكيد تعيين المسمى الوظيفي"}
          </Button>
        </div>
      </Modal>

      {/* ─── MODAL: ASSIGN ROLE & ABAC SCOPE ──────────────────────────────── */}
      <Modal open={assignRoleOpen} onClose={() => setAssignRoleOpen(false)} title={`إسناد دور وصلاحيات (RBAC + ABAC) — ${selectedUser?.full_name || ""}`} wide>
        <div className="space-y-4" dir="rtl">
          <p className="text-xs text-[#706A60] leading-relaxed">
            إسناد دور نظامي محدد مع تحديد نطاق المنشأة والقسم (ABAC Boundary) والصلاحية الزمنية.
          </p>

          <div>
            <label className="block text-xs font-bold text-[#262321] mb-1">الدور النظامي *</label>
            <Select
              value={roleForm.role_id}
              onChange={(e) => setRoleForm({ ...roleForm, role_id: e.target.value })}
            >
              <option value="">-- اختر الدور --</option>
              {rolesQuery.data?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} ({r.code}) — {r.is_clinical ? "سريري" : "إداري"}
                </option>
              ))}
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-[#262321] mb-1">
                معرف المنشأة (ABAC Facility ID) — اختياري
              </label>
              <Input
                type="number"
                placeholder="اتركه فارغاً لجميع المنشآت"
                value={roleForm.facility_id}
                onChange={(e) => setRoleForm({ ...roleForm, facility_id: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-[#262321] mb-1">
                تاريخ انتهاء الصلاحية (اختياري)
              </label>
              <Input
                type="date"
                value={roleForm.valid_until}
                onChange={(e) => setRoleForm({ ...roleForm, valid_until: e.target.value })}
              />
            </div>
          </div>

          {assignRoleMutation.isError && (
            <ErrorBox message={(assignRoleMutation.error as Error).message} />
          )}

          <Button
            className="w-full h-10 font-bold bg-[#651E2C] hover:bg-[#521924] text-white"
            disabled={assignRoleMutation.isPending || !roleForm.role_id}
            onClick={() => assignRoleMutation.mutate()}
          >
            {assignRoleMutation.isPending ? <Spinner /> : "إسناد الدور مع عزل النطاق"}
          </Button>
        </div>
      </Modal>

      {/* ─── MODAL: EFFECTIVE PERMISSIONS & OVERRIDES ──────────────────────── */}
      <Modal open={!!effectiveProfile} onClose={() => setEffectiveProfile(null)} title={`الصلاحيات الفعلية والعزل — ${effectiveProfile?.full_name || ""}`} wide>
        <div className="space-y-4" dir="rtl">
          {effectiveProfile && (
            <>
              {/* Summary Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-[#FAF6F0] p-3 rounded-xl border border-[#E5DDD0] text-center">
                <div>
                  <div className="text-[11px] text-[#706A60]">نوع الحساب</div>
                  <div className="text-xs font-bold text-[#262321] font-mono mt-0.5">{effectiveProfile.account_type}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#706A60]">إجمالي الصلاحيات</div>
                  <div className="text-xs font-bold text-[#262321] font-mono mt-0.5">{effectiveProfile.permissions_count}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#706A60]">صلاحيات سريرية</div>
                  <div className="text-xs font-bold text-emerald-800 font-mono mt-0.5">{effectiveProfile.clinical_permissions?.length || 0}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#706A60]">كسر زجاج نشط</div>
                  <div className="text-xs font-bold mt-0.5">
                    {effectiveProfile.has_break_glass ? (
                      <span className="text-rose-600 font-bold">نشط الآن</span>
                    ) : (
                      <span className="text-[#706A60]">لا يوجد</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Roles & Positions Assigned */}
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="font-semibold text-[#262321]">الأدوار المسندة:</span>
                {effectiveProfile.roles.length > 0 ? (
                  effectiveProfile.roles.map((r, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 font-medium">
                      {r}
                    </span>
                  ))
                ) : (
                  <span className="text-[#706A60] italic">لا توجد أدوار مخصصة</span>
                )}
              </div>

              {/* Permissions list */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-bold text-[#262321]">قائمة الصلاحيات الفعلية الممنوحة:</h4>
                  <button
                    onClick={() => setOverrideOpen(true)}
                    className="text-xs font-bold text-[#651E2C] hover:underline flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" /> إضافة استثناء يدوي (Override)
                  </button>
                </div>
                <div className="max-h-60 overflow-y-auto p-2 border border-[#E5DDD0] rounded-xl bg-white grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                  {effectiveProfile.permissions.map((p) => {
                    const isClin = effectiveProfile.clinical_permissions.includes(p);
                    return (
                      <div
                        key={p}
                        className={`p-1.5 rounded text-[11px] font-mono border flex items-center justify-between ${
                          isClin
                            ? "bg-emerald-50 text-emerald-900 border-emerald-200"
                            : "bg-[#FAF6F0] text-[#262321] border-[#E5DDD0]"
                        }`}
                      >
                        <span dir="ltr">{p}</span>
                        {isClin && <span className="text-[9px] bg-emerald-200 text-emerald-900 px-1 rounded">EMR</span>}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* ─── MODAL: EXPLICIT PERMISSION OVERRIDE ─────────────────────────── */}
      <Modal open={overrideOpen} onClose={() => setOverrideOpen(false)} title="إضافة استثناء صلاحية (Allow / Deny Override)">
        <div className="space-y-4" dir="rtl">
          <div>
            <label className="block text-xs font-bold text-[#262321] mb-1">اختر رمز الصلاحية *</label>
            <Select
              value={overrideForm.permission_code}
              onChange={(e) => setOverrideForm({ ...overrideForm, permission_code: e.target.value })}
            >
              <option value="">-- اختر الصلاحية --</option>
              {permsQuery.data?.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.code} — {p.name}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#262321] mb-1">نوع الاستثناء *</label>
            <Select
              value={overrideForm.override_type}
              onChange={(e) => setOverrideForm({ ...overrideForm, override_type: e.target.value })}
            >
              <option value="allow">سماح صريح (Explicit Allow)</option>
              <option value="deny">حظر وحجب صريح (Explicit Deny)</option>
            </Select>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#262321] mb-1">سبب الاستثناء (للتوثيق)</label>
            <Input
              placeholder="اكتب سبب منح أو منع هذه الصلاحية للمستخدم"
              value={overrideForm.reason}
              onChange={(e) => setOverrideForm({ ...overrideForm, reason: e.target.value })}
            />
          </div>

          {overrideMutation.isError && (
            <ErrorBox message={(overrideMutation.error as Error).message} />
          )}

          <Button
            className="w-full h-10 font-bold bg-[#651E2C] hover:bg-[#521924] text-white"
            disabled={overrideMutation.isPending || !overrideForm.permission_code}
            onClick={() => overrideMutation.mutate()}
          >
            {overrideMutation.isPending ? <Spinner /> : "تطبيق الاستثناء"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
