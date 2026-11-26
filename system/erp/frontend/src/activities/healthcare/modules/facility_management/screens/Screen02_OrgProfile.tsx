import { useState } from "react";
import {
  Building2, FileText, MapPin, Globe, Sliders,
  Upload, Check, AlertTriangle, Save, RotateCcw,
  FileCheck
} from "lucide-react";
import { HealthcareOrganization } from "../types";

interface OrgProfileProps {
  organization: HealthcareOrganization;
  onUpdateOrganization: (updated: HealthcareOrganization) => void;
}

export default function Screen02_OrgProfile({
  organization,
  onUpdateOrganization,
}: OrgProfileProps) {
  const [activeSubTab, setActiveSubTab] = useState<"general" | "legal" | "address" | "regional" | "preferences">("general");
  const [form, setForm] = useState<HealthcareOrganization>({ ...organization });
  const [isDirty, setIsDirty] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleChange = (path: string, value: any) => {
    setIsDirty(true);
    setSaveSuccess(false);
    const keys = path.split(".");
    setForm((prev) => {
      const copy = JSON.parse(JSON.stringify(prev));
      let cur = copy;
      for (let i = 0; i < keys.length - 1; i++) {
        cur = cur[keys[i]];
      }
      cur[keys[keys.length - 1]] = value;
      return copy;
    });
  };

  const handleSave = () => {
    onUpdateOrganization(form);
    setIsDirty(false);
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 4000);
  };

  const handleCancel = () => {
    setForm({ ...organization });
    setIsDirty(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-001 • Master Profile
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            ملف المنظمة والاعتمادات القانونية
          </h1>
          <p className="text-xs text-[#64748B]">
            البيانات الرسمية للمجموعة، التراخيص الوزارية، العناوين المركزية، وإعدادات العمليات الإقليمية.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isDirty && (
            <button
              onClick={handleCancel}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-xs font-medium text-[#475569] hover:bg-[#F8FAFC]"
            >
              <RotateCcw className="w-3.5 h-3.5" /> إلغاء التعديلات
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={!isDirty}
            className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold shadow-xs transition-all ${
              isDirty
                ? "bg-[#1E3A8A] text-white hover:bg-[#1E40AF]"
                : "bg-[#E2E8F0] text-[#94A3B8] cursor-not-allowed"
            }`}
          >
            <Save className="w-3.5 h-3.5" /> حفظ التغييرات
          </button>
        </div>
      </div>

      {/* Unsaved Changes Banner */}
      {isDirty && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>لديك تعديلات غير محفوظة في ملف المنظمة. يرجى الضغط على حفظ لتأكيدها.</span>
          </div>
          <button onClick={handleSave} className="font-bold underline text-amber-900 text-xs">
            حفظ الآن
          </button>
        </div>
      )}

      {/* Save Success Toast */}
      {saveSuccess && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center gap-2 animate-in fade-in">
          <Check className="w-4 h-4 text-emerald-600" />
          <span>تم حفظ بيانات وتراخيص المنظمة بنجاح في سجلات النظام.</span>
        </div>
      )}

      {/* Secondary Left Tabs Navigation & Content */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Navigation Column */}
        <div className="space-y-1">
          {[
            { id: "general", label: "المعلومات العامة والتعريف", icon: Building2 },
            { id: "legal", label: "التراخيص والاعتمادات الرسمية", icon: FileText, badge: "معتمد" },
            { id: "address", label: "العناوين وبيانات الاتصال", icon: MapPin },
            { id: "regional", label: "الإعدادات الإقليمية والعملة", icon: Globe },
            { id: "preferences", label: "تفضيلات وقواعد الترقيم", icon: Sliders },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeSubTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveSubTab(tab.id as any)}
                className={`w-full flex items-center justify-between p-3 rounded-xl text-xs font-medium transition-all text-right ${
                  isActive
                    ? "bg-[#1E3A8A] text-white shadow-xs font-semibold"
                    : "bg-white text-[#475569] hover:bg-[#F8FAFC] border border-[#E2E8F0]"
                }`}
              >
                <div className="flex items-center gap-2.5 truncate">
                  <Icon className={`w-4 h-4 ${isActive ? "text-teal-300" : "text-[#64748B]"}`} />
                  <span className="truncate">{tab.label}</span>
                </div>
                {tab.badge && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold ${
                    isActive ? "bg-white/20 text-white" : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  }`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Tab Content Panel */}
        <div className="md:col-span-3 rounded-xl border border-[#E2E8F0] bg-white p-6 shadow-2xs space-y-6">
          {/* 1. GENERAL INFORMATION */}
          {activeSubTab === "general" && (
            <div className="space-y-4">
              <div className="border-b border-[#F1F5F9] pb-3">
                <h3 className="font-bold text-sm text-[#0F172A]">المعلومات العامة والهوية المؤسسية</h3>
                <p className="text-[11px] text-[#64748B]">الاسم التجاري والقانوني للشبكة الطبية</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">الاسم القانوني للمنظمة (Legal Entity) *</label>
                  <input
                    type="text"
                    value={form.legalName}
                    onChange={(e) => handleChange("legalName", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">الاسم التجاري المعروض (Display Name) *</label>
                  <input
                    type="text"
                    value={form.displayName}
                    onChange={(e) => handleChange("displayName", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">كود المنظمة المرجعي (Org Code) *</label>
                  <input
                    type="text"
                    value={form.code}
                    onChange={(e) => handleChange("code", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">طبيعة المنظمة ونوع النشاط</label>
                  <input
                    type="text"
                    value={form.type}
                    onChange={(e) => handleChange("type", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">الموقع الإلكتروني الرسمي</label>
                  <input
                    type="text"
                    value={form.website}
                    onChange={(e) => handleChange("website", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">البريد الإلكتروني الرسمي للمراسلات</label>
                  <input
                    type="email"
                    value={form.contactEmail}
                    onChange={(e) => handleChange("contactEmail", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">رقم الهاتف المركزي والخط الساخن</label>
                  <input
                    type="text"
                    value={form.phone}
                    onChange={(e) => handleChange("phone", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#334155] mb-1">الوصف التعريفي للشبكة الطبية</label>
                <textarea
                  rows={3}
                  value={form.description}
                  onChange={(e) => handleChange("description", e.target.value)}
                  className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#2563EB]"
                />
              </div>
            </div>
          )}

          {/* 2. LEGAL & REGISTRATION */}
          {activeSubTab === "legal" && (
            <div className="space-y-5">
              <div className="border-b border-[#F1F5F9] pb-3 flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-sm text-[#0F172A]">التراخيص الطبية والسجل التجاري</h3>
                  <p className="text-[11px] text-[#64748B]">بيانات الاعتماد لدى وزارة الصحة وهيئة الرقابة والاعتماد (GAHAR)</p>
                </div>
                <span className="text-[11px] text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-bold">
                  ساري المفعول حتى 2030
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">رقم السجل التجاري *</label>
                  <input
                    type="text"
                    value={form.registrationNumber}
                    onChange={(e) => handleChange("registrationNumber", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">الرقم الضريبي الموحد *</label>
                  <input
                    type="text"
                    value={form.taxId}
                    onChange={(e) => handleChange("taxId", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">رقم ترخيص المنشأة الطبية (MOH) *</label>
                  <input
                    type="text"
                    value={form.healthcareLicenseNumber}
                    onChange={(e) => handleChange("healthcareLicenseNumber", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono font-bold text-teal-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">جهة التسجيل والاعتماد</label>
                  <input
                    type="text"
                    value={form.registrationAuthority}
                    onChange={(e) => handleChange("registrationAuthority", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">تاريخ إصدار الترخيص</label>
                  <input
                    type="date"
                    value={form.issueDate}
                    onChange={(e) => handleChange("issueDate", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">تاريخ انتهاء الترخيص</label>
                  <input
                    type="date"
                    value={form.expiryDate}
                    onChange={(e) => handleChange("expiryDate", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono text-emerald-800"
                  />
                </div>
              </div>

              {/* Uploaded Documents List */}
              <div className="space-y-2 pt-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#0F172A]">الوثائق الرسمية وشهادات الاعتماد المرفقة</span>
                  <button className="text-xs text-[#2563EB] hover:underline font-semibold flex items-center gap-1">
                    <Upload className="w-3.5 h-3.5" /> رفع وثيقة ترخيص جديدة
                  </button>
                </div>

                <div className="space-y-2">
                  {form.documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between p-2.5 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] text-xs"
                    >
                      <div className="flex items-center gap-2.5">
                        <FileCheck className="w-4 h-4 text-emerald-600" />
                        <div>
                          <div className="font-semibold text-[#0F172A]">{doc.name}</div>
                          <div className="text-[10px] text-[#64748B] font-mono">
                            الحجم: {doc.size} • تاريخ الرفع: {doc.uploadDate}
                          </div>
                        </div>
                      </div>
                      <span className="text-[11px] text-teal-700 font-semibold bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                        معتمد رسمياً
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 3. ADDRESS & CONTACT */}
          {activeSubTab === "address" && (
            <div className="space-y-4">
              <div className="border-b border-[#F1F5F9] pb-3">
                <h3 className="font-bold text-sm text-[#0F172A]">العناوين الجغرافية وبيانات المقر الرئيسي</h3>
                <p className="text-[11px] text-[#64748B]">الموقع الرئيسي للمجموعة ومكتب الفوترة المركزي</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">الدولة *</label>
                  <input
                    type="text"
                    value={form.address.country}
                    onChange={(e) => handleChange("address.country", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">المحافظة / الإمارة *</label>
                  <input
                    type="text"
                    value={form.address.governorate}
                    onChange={(e) => handleChange("address.governorate", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">المدينة *</label>
                  <input
                    type="text"
                    value={form.address.city}
                    onChange={(e) => handleChange("address.city", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">الحي / المنطقة</label>
                  <input
                    type="text"
                    value={form.address.district}
                    onChange={(e) => handleChange("address.district", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">الرمز البريدي</label>
                  <input
                    type="text"
                    value={form.address.postalCode}
                    onChange={(e) => handleChange("address.postalCode", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#334155] mb-1">العنوان التفصيلي للمقر الرئيسي</label>
                <input
                  type="text"
                  value={form.address.primaryAddress}
                  onChange={(e) => handleChange("address.primaryAddress", e.target.value)}
                  className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-[#334155] mb-1">عنوان الفوترة والمطالبات المركزية</label>
                <input
                  type="text"
                  value={form.address.billingAddress}
                  onChange={(e) => handleChange("address.billingAddress", e.target.value)}
                  className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1]"
                />
              </div>
            </div>
          )}

          {/* 4. REGIONAL SETTINGS */}
          {activeSubTab === "regional" && (
            <div className="space-y-4">
              <div className="border-b border-[#F1F5F9] pb-3">
                <h3 className="font-bold text-sm text-[#0F172A]">الإعدادات الإقليمية والمحاسبية</h3>
                <p className="text-[11px] text-[#64748B]">تحديد العملة الأساسية، المنطقة الزمنية، والسنة المالية</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">العملة الأساسية للنظام (Currency) *</label>
                  <select
                    value={form.regionalSettings.currency}
                    onChange={(e) => handleChange("regionalSettings.currency", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] bg-white font-mono font-bold"
                  >
                    <option value="EGP">EGP — الجنيه المصري (Egyptian Pound)</option>
                    <option value="SAR">SAR — الريال السعودي (Saudi Riyal)</option>
                    <option value="AED">AED — الدرهم الإماراتي (UAE Dirham)</option>
                    <option value="USD">USD — الدولار الأمريكي (US Dollar)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">المنطقة الزمنية (Time Zone) *</label>
                  <select
                    value={form.regionalSettings.timeZone}
                    onChange={(e) => handleChange("regionalSettings.timeZone", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] bg-white font-mono"
                  >
                    <option value="Africa/Cairo (UTC+02:00)">Africa/Cairo (توقيت القاهرة الرسمي UTC+02:00)</option>
                    <option value="Asia/Riyadh (UTC+03:00)">Asia/Riyadh (توقيت مكة المكرمة UTC+03:00)</option>
                    <option value="Asia/Dubai (UTC+04:00)">Asia/Dubai (توقيت الإمارات UTC+04:00)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">اللغة الافتراضية</label>
                  <select
                    value={form.regionalSettings.defaultLanguage}
                    onChange={(e) => handleChange("regionalSettings.defaultLanguage", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] bg-white"
                  >
                    <option value="ar">العربية (Arabic - RTL)</option>
                    <option value="en">English (LTR)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">تنسيق عرض التاريخ</label>
                  <select
                    value={form.regionalSettings.dateFormat}
                    onChange={(e) => handleChange("regionalSettings.dateFormat", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] bg-white font-mono"
                  >
                    <option value="DD/MM/YYYY">DD/MM/YYYY (يوم/شهر/سنة)</option>
                    <option value="YYYY-MM-DD">YYYY-MM-DD (معيار ISO الدولي)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#334155] mb-1">بداية السنة المالية</label>
                  <input
                    type="text"
                    value={form.regionalSettings.fiscalYearStart}
                    onChange={(e) => handleChange("regionalSettings.fiscalYearStart", e.target.value)}
                    className="w-full text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono"
                  />
                </div>
              </div>
            </div>
          )}

          {/* 5. PREFERENCES */}
          {activeSubTab === "preferences" && (
            <div className="space-y-4">
              <div className="border-b border-[#F1F5F9] pb-3">
                <h3 className="font-bold text-sm text-[#0F172A]">تفضيلات الحوكمة وقواعد الترقيم</h3>
                <p className="text-[11px] text-[#64748B]">تخصيص السلوكيات العامة على مستوى شبكة المستشفيات</p>
              </div>

              <div className="space-y-3">
                <label className="flex items-center gap-3 p-3 rounded-xl border border-[#E2E8F0] hover:bg-[#F8FAFC] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.preferences.autoNotifyOnStatusChange}
                    onChange={(e) => handleChange("preferences.autoNotifyOnStatusChange", e.target.checked)}
                    className="rounded text-[#1E3A8A] w-4 h-4"
                  />
                  <div>
                    <div className="text-xs font-bold text-[#0F172A]">إرسال إشعار فوري لمديري المستشفيات عند تغيير حالة أي منشأة</div>
                    <div className="text-[11px] text-[#64748B]">إشعار آلي عبر البريد والنظام عند تعليق أو صيانة أي قسم أو مبنى.</div>
                  </div>
                </label>

                <label className="flex items-center gap-3 p-3 rounded-xl border border-[#E2E8F0] hover:bg-[#F8FAFC] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.preferences.requireDepartmentSignoff}
                    onChange={(e) => handleChange("preferences.requireDepartmentSignoff", e.target.checked)}
                    className="rounded text-[#1E3A8A] w-4 h-4"
                  />
                  <div>
                    <div className="text-xs font-bold text-[#0F172A]">طلب اعتماد المدير الطبي قبل تفعيل أي قسم سريري جديد</div>
                    <div className="text-[11px] text-[#64748B]">اشتراط التوقيع الإلكتروني لمطابقة معايير جهار (GAHAR).</div>
                  </div>
                </label>

                <div className="p-3 rounded-xl border border-[#E2E8F0] space-y-2">
                  <label className="block text-xs font-bold text-[#0F172A]">بادئة الترقيم الموحدة للسجلات (Numbering Prefix)</label>
                  <input
                    type="text"
                    value={form.preferences.numberingPrefix}
                    onChange={(e) => handleChange("preferences.numberingPrefix", e.target.value)}
                    className="w-48 text-xs p-2 rounded-lg border border-[#CBD5E1] font-mono font-bold"
                  />
                  <p className="text-[11px] text-[#64748B]">تُستخدم في توليد أكواد المنشآت والغرف تلقائياً (مثال: MHG-01-A-101).</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
