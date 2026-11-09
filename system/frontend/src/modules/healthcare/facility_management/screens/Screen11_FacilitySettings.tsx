import { useState } from "react";
import {
  Sliders, Hash, Globe, Bell, Shield,
  Save, CheckCircle2, Building2
} from "lucide-react";
import { HealthcareFacilityItem } from "../types";

interface FacilitySettingsProps {
  facility: HealthcareFacilityItem;
  onUpdateFacility: (updated: HealthcareFacilityItem) => void;
}

type SettingsSection =
  | "general"
  | "regional"
  | "operational"
  | "numbering"
  | "notifications"
  | "access";

export default function Screen11_FacilitySettings({
  facility,
  onUpdateFacility,
}: FacilitySettingsProps) {
  const [activeSection, setActiveSection] = useState<SettingsSection>("general");
  const [hasChanges, setHasChanges] = useState(false);
  const [showToast, setShowToast] = useState(false);

  // Editable settings state
  const [settings, setSettings] = useState({
    displayName: facility.name,
    displayNameEn: facility.nameEn,
    publicPhone: facility.administration.managerPhone,
    publicEmail: facility.administration.managerEmail,
    emergencyHelpline: "+20 100 892 4110",

    currency: facility.operations.currency,
    timeZone: facility.operations.timeZone,
    dateFormat: "YYYY-MM-DD",
    primaryLanguage: "العربية (مصر)",

    // Operational Policies
    bookingWindowDays: 30,
    cancellationWindowHours: 24,
    maxSimultaneousBookings: 3,
    checkInWindowMinutes: 15,
    autoCancelNoShowMinutes: 30,

    // Numbering & Identifiers
    mrnPrefix: `${facility.code}-MRN`,
    invoicePrefix: `${facility.code}-INV`,
    appointmentPrefix: `${facility.code}-APT`,
    labOrderPrefix: `${facility.code}-LAB`,

    // Notifications
    smsSenderId: "MIZAN-HEALTH",
    emailSenderName: `${facility.name} — إشعارات ميزان`,
    enableSmsReminders: true,
    enableEmailConfirmations: true,
    enableWhatsappAlerts: true,
  });

  const handleChange = (key: string, value: any) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    const updatedFacility: HealthcareFacilityItem = {
      ...facility,
      name: settings.displayName,
      nameEn: settings.displayNameEn,
      administration: {
        ...facility.administration,
        managerPhone: settings.publicPhone,
        managerEmail: settings.publicEmail,
      },
      operations: {
        ...facility.operations,
        currency: settings.currency,
        timeZone: settings.timeZone,
      },
      updatedAt: new Date().toISOString(),
    };

    onUpdateFacility(updatedFacility);
    setHasChanges(false);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3500);
  };

  const SECTIONS = [
    { id: "general", label: "البيانات العامة والعلامة", labelEn: "General & Branding", icon: Building2 },
    { id: "regional", label: "الإعدادات الإقليمية والعملة", labelEn: "Regional & Currency", icon: Globe },
    { id: "operational", label: "سياسات المواعيد والحجز", labelEn: "Operational Policies", icon: Sliders },
    { id: "numbering", label: "تسلسل الأرقام والبادئات", labelEn: "Numbering & Prefixes", icon: Hash },
    { id: "notifications", label: "قنوات الإشعارات والرسائل", labelEn: "Notifications", icon: Bell },
    { id: "access", label: "نطاق الصلاحيات والأمان", labelEn: "Security & Roles", icon: Shield },
  ];

  return (
    <div className="space-y-6">
      {/* Toast Feedback */}
      {showToast && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-800 text-white text-xs font-bold shadow-xl animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-300" />
          <span>تم حفظ وتحديث إعدادات المنشأة بنجاح</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-005 • إعدادات المنشأة المخصصة
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            إعدادات المنشأة والسياسات التشغيلية
          </h1>
          <p className="text-xs text-[#64748B]">
            تخصيص قواعد الحجز، ترقيم السجلات الطبية والمالية، وإشعارات المرضى لمنشأة:{" "}
            <strong className="text-[#0F172A]">{facility.name}</strong> ({facility.code}).
          </p>
        </div>

        {hasChanges && (
          <button
            onClick={handleSave}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-700 text-white text-xs font-bold hover:bg-emerald-800 shadow-xs"
          >
            <Save className="w-4 h-4" /> حفظ التغييرات
          </button>
        )}
      </div>

      {/* Two Columns: Section Tabs + Content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Nav Tabs (4 cols) */}
        <div className="lg:col-span-4 space-y-1">
          {SECTIONS.map((sec) => {
            const Icon = sec.icon;
            const isActive = activeSection === sec.id;
            return (
              <button
                key={sec.id}
                onClick={() => setActiveSection(sec.id as SettingsSection)}
                className={`flex items-center justify-between w-full p-3 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-[#1E3A8A] text-white shadow-xs font-bold"
                    : "bg-white border border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC]"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`w-4 h-4 ${isActive ? "text-teal-300" : "text-[#64748B]"}`} />
                  <span>{sec.label}</span>
                </div>
                <span className={`text-[10px] ${isActive ? "text-teal-200" : "text-[#94A3B8]"}`}>
                  {sec.labelEn}
                </span>
              </button>
            );
          })}
        </div>

        {/* Right Side: Configuration Panels (8 cols) */}
        <div className="lg:col-span-8 bg-white rounded-xl border border-[#E2E8F0] p-6 shadow-2xs">
          <form onSubmit={handleSave} className="space-y-6 text-xs">
            {/* SECTION 1: GENERAL & BRANDING */}
            {activeSection === "general" && (
              <div className="space-y-4">
                <div className="border-b border-[#F1F5F9] pb-3">
                  <h3 className="font-bold text-sm text-[#0F172A]">البيانات التعريفية والواجهة العامة</h3>
                  <p className="text-xs text-[#64748B]">الاسم الموجه للجمهور وقنوات الاتصال الرسمية للمنشأة.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="font-bold text-[#334155] block mb-1">الاسم المعروض بالعربية</label>
                    <input
                      type="text"
                      value={settings.displayName}
                      onChange={(e) => handleChange("displayName", e.target.value)}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    />
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">الاسم المعروض بالإنجليزية</label>
                    <input
                      type="text"
                      value={settings.displayNameEn}
                      onChange={(e) => handleChange("displayNameEn", e.target.value)}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                      dir="ltr"
                    />
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">هاتف الاستعلامات العام</label>
                    <input
                      type="text"
                      value={settings.publicPhone}
                      onChange={(e) => handleChange("publicPhone", e.target.value)}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                      dir="ltr"
                    />
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">خط الطوارئ الساخن 24/7</label>
                    <input
                      type="text"
                      value={settings.emergencyHelpline}
                      onChange={(e) => handleChange("emergencyHelpline", e.target.value)}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                      dir="ltr"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* SECTION 2: REGIONAL & CURRENCY */}
            {activeSection === "regional" && (
              <div className="space-y-4">
                <div className="border-b border-[#F1F5F9] pb-3">
                  <h3 className="font-bold text-sm text-[#0F172A]">الإعدادات الإقليمية والمحلية</h3>
                  <p className="text-xs text-[#64748B]">تحديد العملة المالية المعتمدة للفواتير وتنسيق الوقت والتاريخ.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="font-bold text-[#334155] block mb-1">العملة الأساسية للفوترة</label>
                    <select
                      value={settings.currency}
                      onChange={(e) => handleChange("currency", e.target.value)}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                    >
                      <option value="EGP">جنيه مصري (EGP)</option>
                      <option value="SAR">ريال سعودي (SAR)</option>
                      <option value="AED">درهم إماراتي (AED)</option>
                      <option value="USD">دولار أمريكي (USD)</option>
                    </select>
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">المنطقة الزمنية (Time Zone)</label>
                    <input
                      type="text"
                      disabled
                      value={settings.timeZone}
                      className="w-full p-2.5 rounded-lg border border-[#E2E8F0] bg-[#F1F5F9] text-[#64748B]"
                    />
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">تنسيق التاريخ في التقارير</label>
                    <select
                      value={settings.dateFormat}
                      onChange={(e) => handleChange("dateFormat", e.target.value)}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                    >
                      <option value="YYYY-MM-DD">YYYY-MM-DD (2026-11-08)</option>
                      <option value="DD/MM/YYYY">DD/MM/YYYY (08/11/2026)</option>
                    </select>
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">اللغة الرسمية للمنشأة</label>
                    <input
                      type="text"
                      disabled
                      value={settings.primaryLanguage}
                      className="w-full p-2.5 rounded-lg border border-[#E2E8F0] bg-[#F1F5F9] text-[#64748B]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* SECTION 3: OPERATIONAL POLICIES */}
            {activeSection === "operational" && (
              <div className="space-y-4">
                <div className="border-b border-[#F1F5F9] pb-3">
                  <h3 className="font-bold text-sm text-[#0F172A]">سياسات الجدولة والمواعيد</h3>
                  <p className="text-xs text-[#64748B]">قواعد حجز المرضى، الإلغاء، وتسجيل الحضور المسبق.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="font-bold text-[#334155] block mb-1">نافذة الحجز المسبق (أيام)</label>
                    <input
                      type="number"
                      value={settings.bookingWindowDays}
                      onChange={(e) => handleChange("bookingWindowDays", parseInt(e.target.value))}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    />
                    <p className="text-[10px] text-[#64748B] mt-0.5">الحد الأقصى للأيام المتاح حجز مواعيد خلالها مستقبلاً.</p>
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">نافذة الإلغاء المسموح (ساعات)</label>
                    <input
                      type="number"
                      value={settings.cancellationWindowHours}
                      onChange={(e) => handleChange("cancellationWindowHours", parseInt(e.target.value))}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    />
                    <p className="text-[10px] text-[#64748B] mt-0.5">يجب على المريض إلغاء الموعد قبل هذا الوقت لتجنب الغرامة.</p>
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">فترة تسجيل الحضور المسبق (دقائق)</label>
                    <input
                      type="number"
                      value={settings.checkInWindowMinutes}
                      onChange={(e) => handleChange("checkInWindowMinutes", parseInt(e.target.value))}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    />
                    <p className="text-[10px] text-[#64748B] mt-0.5">وقت حضور المريض لغرفة الانتظار قبل موعد الطبيب.</p>
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">إلغاء تلقائي عند التخلف (دقائق)</label>
                    <input
                      type="number"
                      value={settings.autoCancelNoShowMinutes}
                      onChange={(e) => handleChange("autoCancelNoShowMinutes", parseInt(e.target.value))}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    />
                    <p className="text-[10px] text-[#64748B] mt-0.5">تحويل الحالة إلى تخلف عن الحضور (No-Show).</p>
                  </div>
                </div>
              </div>
            )}

            {/* SECTION 4: NUMBERING & PREFIXES */}
            {activeSection === "numbering" && (
              <div className="space-y-4">
                <div className="border-b border-[#F1F5F9] pb-3">
                  <h3 className="font-bold text-sm text-[#0F172A]">بادئات الترقيم والسجلات الطبية والمالية</h3>
                  <p className="text-xs text-[#64748B]">توليد الأرقام التسلسلية لملفات المرضى والفواتير لتجنب تداخل الفروع.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="font-bold text-[#334155] block mb-1">بادئة ملف المريض (Patient MRN)</label>
                    <input
                      type="text"
                      value={settings.mrnPrefix}
                      onChange={(e) => handleChange("mrnPrefix", e.target.value)}
                      className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                      dir="ltr"
                    />
                    <p className="text-[10px] text-[#64748B] mt-0.5">مثال على الرقم المتولد: {settings.mrnPrefix}-2026-00412</p>
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">بادئة الفواتير المالية (Invoices)</label>
                    <input
                      type="text"
                      value={settings.invoicePrefix}
                      onChange={(e) => handleChange("invoicePrefix", e.target.value)}
                      className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                      dir="ltr"
                    />
                    <p className="text-[10px] text-[#64748B] mt-0.5">مثال على الفاتورة: {settings.invoicePrefix}-88912</p>
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">بادئة حجز المواعيد (Appointments)</label>
                    <input
                      type="text"
                      value={settings.appointmentPrefix}
                      onChange={(e) => handleChange("appointmentPrefix", e.target.value)}
                      className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                      dir="ltr"
                    />
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">بادئة طلبات المختبر والأشعة</label>
                    <input
                      type="text"
                      value={settings.labOrderPrefix}
                      onChange={(e) => handleChange("labOrderPrefix", e.target.value)}
                      className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                      dir="ltr"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* SECTION 5: NOTIFICATIONS */}
            {activeSection === "notifications" && (
              <div className="space-y-4">
                <div className="border-b border-[#F1F5F9] pb-3">
                  <h3 className="font-bold text-sm text-[#0F172A]">إشعارات المرضى وقنوات التواصل</h3>
                  <p className="text-xs text-[#64748B]">إعدادات رسائل التذكير وتأكيد الحجوزات ونتائج التحاليل.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="font-bold text-[#334155] block mb-1">اسم مرسل الرسائل النصية (SMS Sender ID)</label>
                    <input
                      type="text"
                      value={settings.smsSenderId}
                      onChange={(e) => handleChange("smsSenderId", e.target.value)}
                      className="w-full p-2.5 font-mono rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                      dir="ltr"
                    />
                  </div>

                  <div>
                    <label className="font-bold text-[#334155] block mb-1">اسم مرسل البريد الإلكتروني</label>
                    <input
                      type="text"
                      value={settings.emailSenderName}
                      onChange={(e) => handleChange("emailSenderName", e.target.value)}
                      className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                    />
                  </div>
                </div>

                <div className="space-y-2 pt-2">
                  <label className="flex items-center gap-2 p-3 rounded-lg border border-[#E2E8F0] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.enableSmsReminders}
                      onChange={(e) => handleChange("enableSmsReminders", e.target.checked)}
                      className="rounded text-[#1E3A8A]"
                    />
                    <div>
                      <span className="font-bold text-[#0F172A] block">إرسال رسائل SMS تذكيرية قبل الموعد بـ 24 ساعة</span>
                      <span className="text-[11px] text-[#64748B]">تقلل نسبة تخلف المرضى عن الحضور بنسبة تتجاوز 40%.</span>
                    </div>
                  </label>

                  <label className="flex items-center gap-2 p-3 rounded-lg border border-[#E2E8F0] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.enableWhatsappAlerts}
                      onChange={(e) => handleChange("enableWhatsappAlerts", e.target.checked)}
                      className="rounded text-[#1E3A8A]"
                    />
                    <div>
                      <span className="font-bold text-[#0F172A] block">تفعيل إشعارات واتساب لتقارير ونتائج المختبر والأشعة</span>
                      <span className="text-[11px] text-[#64748B]">إرسال روابط مشفرة وآمنة لتحميل نتائج الفحوصات الطبية فور اعتمادها.</span>
                    </div>
                  </label>
                </div>
              </div>
            )}

            {/* SECTION 6: SECURITY & ACCESS */}
            {activeSection === "access" && (
              <div className="space-y-4">
                <div className="border-b border-[#F1F5F9] pb-3">
                  <h3 className="font-bold text-sm text-[#0F172A]">نطاق الأمان والصلاحيات للمنشأة</h3>
                  <p className="text-xs text-[#64748B]">حوكمة وصول المستخدمين وفق معايير RBAC و ABAC.</p>
                </div>

                <div className="p-4 rounded-xl bg-slate-50 border border-[#E2E8F0] space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#0F172A]">
                    <Shield className="w-4 h-4 text-teal-600" />
                    <span>محددات النفاذ الخاصة بالمنشأة ({facility.code}):</span>
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-xs text-[#64748B]">
                    <li>لا يمكن للموظفين الوصول لبيانات هذه المنشأة إلا بعد تعيينهم صراحة في نطاق الفرع.</li>
                    <li>يتم تطبيق سياسات التدقيق الإداري الكامل (Audit Logging) على كافة التعديلات.</li>
                    <li>إلغاء القفل الطارئ (Break-Glass Protocol) متاح فقط للأطباء الاستشاريين المرخصين.</li>
                  </ul>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-2 border-t border-[#F1F5F9] pt-4">
              <button
                type="submit"
                className="px-6 py-2.5 rounded-lg bg-[#1E3A8A] text-white font-bold hover:bg-[#1E40AF] shadow-xs"
              >
                حفظ التعديلات
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
