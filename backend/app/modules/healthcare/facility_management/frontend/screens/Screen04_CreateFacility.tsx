import { useState } from "react";
import {
  Hospital, CheckCircle2, ArrowRight, ArrowLeft,
  Building2, MapPin, User, Clock, ShieldCheck, Save, X, Sparkles
} from "lucide-react";
import {
  HealthcareFacilityItem,
  HealthcareOrganization,
  FacilityType,
  FacilityStatus
} from "../types";

interface CreateFacilityProps {
  organization: HealthcareOrganization;
  existingFacilities: HealthcareFacilityItem[];
  onSave: (newFacility: HealthcareFacilityItem) => void;
  onCancel: () => void;
  initialData?: HealthcareFacilityItem | null;
}

const STEPS = [
  { id: 1, label: "البيانات الأساسية", labelEn: "Basic Info", icon: Building2 },
  { id: 2, label: "الموقع والعنوان", labelEn: "Location & Address", icon: MapPin },
  { id: 3, label: "الإدارة والاتصال", labelEn: "Administration", icon: User },
  { id: 4, label: "التشغيل والسياسات", labelEn: "Operations", icon: Clock },
  { id: 5, label: "المراجعة والتأكيد", labelEn: "Review & Confirm", icon: ShieldCheck },
];

export default function Screen04_CreateFacility({
  organization,
  existingFacilities,
  onSave,
  onCancel,
  initialData,
}: CreateFacilityProps) {
  const isEdit = Boolean(initialData);
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Form State
  const [formData, setFormData] = useState<HealthcareFacilityItem>(() => {
    if (initialData) return { ...initialData };
    return {
      id: `fac-${Date.now()}`,
      code: "FAC-",
      name: "",
      nameEn: "",
      type: "clinic",
      status: "active",
      description: "",
      location: {
        country: "مصر",
        governorate: "الجيزة",
        city: "مدينة الشيخ زايد",
        district: "الحي المتميز",
        address: "شارع المحور المركزي",
        postalCode: "12588",
      },
      administration: {
        managerName: "",
        managerEmail: "",
        managerPhone: "",
        medicalDirector: "",
        adminContact: "",
      },
      operations: {
        timeZone: "Africa/Cairo (EET)",
        currency: "EGP",
        language: "العربية / English",
        is24HoursEmergency: false,
        workingDays: ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"],
        standardHours: "08:00 ص - 10:00 م",
      },
      stats: {
        departmentCount: 0,
        buildingCount: 1,
        unitCount: 0,
        roomCount: 0,
        activeServicesCount: 0,
        staffCount: 0,
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  });

  // Validation per step
  const validateStep = (step: number): boolean => {
    const newErrors: Record<string, string> = {};

    if (step === 1) {
      if (!formData.name.trim()) newErrors.name = "اسم المنشأة بالعربية مطلوب";
      if (!formData.nameEn.trim()) newErrors.nameEn = "اسم المنشأة بالإنجليزية مطلوب";
      if (!formData.code.trim()) newErrors.code = "رمز المنشأة الكودي مطلوب";
      else {
        // Unique check
        const isDuplicate = existingFacilities.some(
          (f) => f.code.toUpperCase() === formData.code.toUpperCase() && f.id !== formData.id
        );
        if (isDuplicate) newErrors.code = "رمز المنشأة مستخدم بالفعل، يرجى اختيار رمز فريد";
      }
    }

    if (step === 2) {
      if (!formData.location.city.trim()) newErrors.city = "المدينة مطلوبة";
      if (!formData.location.governorate.trim()) newErrors.governorate = "المحافظة مطلوبة";
      if (!formData.location.address.trim()) newErrors.address = "العنوان التفصيلي مطلوب";
    }

    if (step === 3) {
      if (!formData.administration.managerName.trim()) newErrors.managerName = "اسم مدير المنشأة مطلوب";
      if (!formData.administration.managerEmail.trim()) {
        newErrors.managerEmail = "البريد الإلكتروني للمدير مطلوب";
      } else if (!formData.administration.managerEmail.includes("@")) {
        newErrors.managerEmail = "صيغة البريد الإلكتروني غير صحيحة";
      }
      if (!formData.administration.managerPhone.trim()) {
        newErrors.managerPhone = "رقم هاتف المنشأة مطلوب";
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(prev + 1, 5));
    }
  };

  const handlePrev = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateStep(1) || !validateStep(2) || !validateStep(3)) {
      alert("يرجى التأكد من استكمال كافة الحقول الإلزامية في الخطوات السابقة");
      return;
    }
    onSave(formData);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-002 • مسار تهيئة الفروع
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            {isEdit ? `تعديل بيانات المنشأة: ${formData.name}` : "إضافة منشأة أو مستشفى جديد"}
          </h1>
          <p className="text-xs text-[#64748B]">
            تسجيل فرع أو مستشفى تابع لمجموعة {organization.displayName} وفق المعايير الإدارية والرقابية المعتمدة.
          </p>
        </div>

        <button
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-xs font-medium text-[#475569] hover:bg-[#F8FAFC]"
        >
          <X className="w-4 h-4" /> إلغاء وعودة
        </button>
      </div>

      {/* Stepper Wizard Progress */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-2xs">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {STEPS.map((step) => {
            const isCompleted = currentStep > step.id;
            const isCurrent = currentStep === step.id;
            return (
              <div
                key={step.id}
                onClick={() => {
                  if (step.id < currentStep) setCurrentStep(step.id);
                }}
                className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all ${
                  isCurrent
                    ? "bg-[#1E3A8A] text-white shadow-xs"
                    : isCompleted
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : "bg-[#F8FAFC] text-[#64748B] opacity-60"
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                    isCurrent
                      ? "bg-white text-[#1E3A8A]"
                      : isCompleted
                      ? "bg-emerald-600 text-white"
                      : "bg-[#E2E8F0] text-[#475569]"
                  }`}
                >
                  {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : step.id}
                </div>
                <div className="truncate">
                  <div className="text-xs font-bold truncate">{step.label}</div>
                  <div className="text-[10px] opacity-80 truncate">{step.labelEn}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Form Container */}
      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-[#E2E8F0] p-6 shadow-2xs space-y-6">
        {/* STEP 1: Basic Information */}
        {currentStep === 1 && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="border-b border-[#F1F5F9] pb-3">
              <h2 className="text-base font-bold text-[#0F172A] flex items-center gap-2">
                <Building2 className="w-4 h-4 text-[#1E3A8A]" /> الخطوة 1: البيانات التعريفية والتصنيف
              </h2>
              <p className="text-xs text-[#64748B]">حدد الاسم الرسمي للمنشأة، الرمز الكودي الفريد ونوع المرفق الصحي.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  اسم المنشأة بالعربية <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="مثال: مستشفى الشفاء التخصصي"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={`w-full text-xs p-2.5 rounded-lg border ${
                    errors.name ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                />
                {errors.name && <p className="text-[11px] text-red-600 mt-1">{errors.name}</p>}
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  اسم المنشأة بالإنجليزية <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Al-Shefa Specialized Hospital"
                  value={formData.nameEn}
                  onChange={(e) => setFormData({ ...formData, nameEn: e.target.value })}
                  className={`w-full text-xs p-2.5 rounded-lg border ${
                    errors.nameEn ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                  dir="ltr"
                />
                {errors.nameEn && <p className="text-[11px] text-red-600 mt-1">{errors.nameEn}</p>}
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  الرمز الكودي للمنشأة (Facility Code) <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. FAC-CENTRAL-01"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  className={`w-full text-xs font-mono p-2.5 rounded-lg border ${
                    errors.code ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                  dir="ltr"
                />
                <p className="text-[10px] text-[#64748B] mt-1">يُستخدم في ترقيم ملفات المرضى وتوليد السجلات الطبية.</p>
                {errors.code && <p className="text-[11px] text-red-600 mt-1">{errors.code}</p>}
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  تصنيف المرفق الصحي (Facility Type) <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value as FacilityType })}
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                >
                  <option value="hospital">🏥 مستشفى عام / تخصصي (Hospital)</option>
                  <option value="medical_center">🏛️ مجمع عيادات ومراكز طبية (Medical Center)</option>
                  <option value="clinic">🩺 عيادة خارجية مستقلة (Outpatient Clinic)</option>
                  <option value="diagnostic_center">🔬 مركز أشعة وتحاليل تشخيصي (Diagnostic Center)</option>
                  <option value="specialized_center">⚡ مركز رعاية تخصصي (Specialized Center)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  حالة التشغيل الحالية <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value as FacilityStatus })}
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                >
                  <option value="active">🟢 قيد التشغيل والخدمة الكاملة (Active)</option>
                  <option value="under_construction">🟡 قيد التجهيز والإنشاء (Under Construction)</option>
                  <option value="inactive">⚪ غير نشط مؤقتاً (Inactive)</option>
                  <option value="suspended">🔴 معلق لأسباب رقابية (Suspended)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  المنظمة المالكة (Parent Organization)
                </label>
                <input
                  type="text"
                  disabled
                  value={`${organization.displayName} (${organization.code})`}
                  className="w-full text-xs p-2.5 rounded-lg border border-[#E2E8F0] bg-[#F1F5F9] text-[#64748B]"
                />
              </div>

              <div className="md:col-span-2">
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  نبذة وصفية عن المنشأة والخدمات الرئيسية
                </label>
                <textarea
                  rows={3}
                  placeholder="أدخل ملخصاً عن الطاقة الاستيعابية والتخصصات الأساسية للمنشأة..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: Location & Address */}
        {currentStep === 2 && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="border-b border-[#F1F5F9] pb-3">
              <h2 className="text-base font-bold text-[#0F172A] flex items-center gap-2">
                <MapPin className="w-4 h-4 text-[#1E3A8A]" /> الخطوة 2: الموقع الجغرافي والعنوان الرسمي
              </h2>
              <p className="text-xs text-[#64748B]">تحديد النطاق الإداري للمنشأة وتفاصيل الوصول للمرضى وفرق الطوارئ.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">الدولة</label>
                <input
                  type="text"
                  value={formData.location.country}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      location: { ...formData.location, country: e.target.value },
                    })
                  }
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  المحافظة / الإمارة <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="مثال: الجيزة / القاهرة"
                  value={formData.location.governorate}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      location: { ...formData.location, governorate: e.target.value },
                    })
                  }
                  className={`w-full text-xs p-2.5 rounded-lg border ${
                    errors.governorate ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                />
                {errors.governorate && <p className="text-[11px] text-red-600 mt-1">{errors.governorate}</p>}
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  المدينة <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="مثال: مدينة الشيخ زايد"
                  value={formData.location.city}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      location: { ...formData.location, city: e.target.value },
                    })
                  }
                  className={`w-full text-xs p-2.5 rounded-lg border ${
                    errors.city ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                />
                {errors.city && <p className="text-[11px] text-red-600 mt-1">{errors.city}</p>}
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">الحي / المنطقة</label>
                <input
                  type="text"
                  placeholder="مثال: الحي المتميز / التجمع الخامس"
                  value={formData.location.district}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      location: { ...formData.location, district: e.target.value },
                    })
                  }
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div className="md:col-span-2">
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  العنوان التفصيلي واسم الشارع <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="مثال: تقاطع شارع المحور المركزي مع طريق الشباب، بجوار مجمع البنوك"
                  value={formData.location.address}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      location: { ...formData.location, address: e.target.value },
                    })
                  }
                  className={`w-full text-xs p-2.5 rounded-lg border ${
                    errors.address ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                />
                {errors.address && <p className="text-[11px] text-red-600 mt-1">{errors.address}</p>}
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">الرمز البريدي</label>
                <input
                  type="text"
                  placeholder="12588"
                  value={formData.location.postalCode}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      location: { ...formData.location, postalCode: e.target.value },
                    })
                  }
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">المنطقة الزمنية (Time Zone)</label>
                <input
                  type="text"
                  disabled
                  value={formData.operations.timeZone}
                  className="w-full text-xs p-2.5 rounded-lg border border-[#E2E8F0] bg-[#F1F5F9] text-[#64748B]"
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Administration */}
        {currentStep === 3 && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="border-b border-[#F1F5F9] pb-3">
              <h2 className="text-base font-bold text-[#0F172A] flex items-center gap-2">
                <User className="w-4 h-4 text-[#1E3A8A]" /> الخطوة 3: القيادة الإدارية والطبية وقنوات التواصل
              </h2>
              <p className="text-xs text-[#64748B]">
                تعيين مدير المنشأة، المدير الطبي، ومسؤول التنسيق الإداري للطوارئ.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  اسم مدير المنشأة (Facility Director) <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="د. حسام عثمان"
                  value={formData.administration.managerName}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      administration: { ...formData.administration, managerName: e.target.value },
                    })
                  }
                  className={`w-full text-xs p-2.5 rounded-lg border ${
                    errors.managerName ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                />
                {errors.managerName && <p className="text-[11px] text-red-600 mt-1">{errors.managerName}</p>}
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  المدير الطبي (Medical Director)
                </label>
                <input
                  type="text"
                  placeholder="أ.د. شريف الجمال"
                  value={formData.administration.medicalDirector}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      administration: { ...formData.administration, medicalDirector: e.target.value },
                    })
                  }
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  البريد الإلكتروني للإدارة <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  placeholder="director@mizan-health.eg"
                  value={formData.administration.managerEmail}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      administration: { ...formData.administration, managerEmail: e.target.value },
                    })
                  }
                  className={`w-full text-xs p-2.5 rounded-lg border ${
                    errors.managerEmail ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                  dir="ltr"
                />
                {errors.managerEmail && <p className="text-[11px] text-red-600 mt-1">{errors.managerEmail}</p>}
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  هاتف المنشأة الرئيسي <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="+20 2 3855 0100"
                  value={formData.administration.managerPhone}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      administration: { ...formData.administration, managerPhone: e.target.value },
                    })
                  }
                  className={`w-full text-xs p-2.5 rounded-lg border ${
                    errors.managerPhone ? "border-red-500 bg-red-50/20" : "border-[#CBD5E1]"
                  } focus:outline-none focus:border-[#1E3A8A]`}
                  dir="ltr"
                />
                {errors.managerPhone && <p className="text-[11px] text-red-600 mt-1">{errors.managerPhone}</p>}
              </div>

              <div className="md:col-span-2">
                <label className="text-xs font-bold text-[#334155] block mb-1">
                  مسؤول التنسيق الإداري والطوارئ 24/7
                </label>
                <input
                  type="text"
                  placeholder="أ. سارة فهمي — منسق العمليات الإدارية (+20 100 892 4110)"
                  value={formData.administration.adminContact}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      administration: { ...formData.administration, adminContact: e.target.value },
                    })
                  }
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: Operations & Policies */}
        {currentStep === 4 && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="border-b border-[#F1F5F9] pb-3">
              <h2 className="text-base font-bold text-[#0F172A] flex items-center gap-2">
                <Clock className="w-4 h-4 text-[#1E3A8A]" /> الخطوة 4: السياسات التشغيلية والمالية
              </h2>
              <p className="text-xs text-[#64748B]">إعدادات العملات، الطوارئ وساعات استقبال المراجعين الرسمية.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">العملة الافتراضية للفوترة</label>
                <select
                  value={formData.operations.currency}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      operations: { ...formData.operations, currency: e.target.value },
                    })
                  }
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] bg-white focus:outline-none focus:border-[#1E3A8A]"
                >
                  <option value="EGP">جنيه مصري (EGP)</option>
                  <option value="SAR">ريال سعودي (SAR)</option>
                  <option value="AED">درهم إماراتي (AED)</option>
                  <option value="USD">دولار أمريكي (USD)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-bold text-[#334155] block mb-1">ساعات العمل القياسية</label>
                <input
                  type="text"
                  placeholder="08:00 ص - 10:00 م"
                  value={formData.operations.standardHours}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      operations: { ...formData.operations, standardHours: e.target.value },
                    })
                  }
                  className="w-full text-xs p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div className="md:col-span-2 p-4 rounded-xl border border-teal-200 bg-teal-50/50 flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold text-teal-900">تشغيل قسم الطوارئ والاستقبال على مدار 24 ساعة</div>
                  <div className="text-[11px] text-teal-700 mt-0.5">
                    تفعيل هذا الخيار يتيح استقبال الحالات الطارئة وجدولة ورديات التمريض على مدار الساعة دون انقطاع.
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.operations.is24HoursEmergency}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        operations: { ...formData.operations, is24HoursEmergency: e.target.checked },
                      })
                    }
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* STEP 5: Review & Confirm */}
        {currentStep === 5 && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="border-b border-[#F1F5F9] pb-3">
              <h2 className="text-base font-bold text-[#0F172A] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" /> الخطوة 5: مراجعة واعتماد بيانات المنشأة
              </h2>
              <p className="text-xs text-[#64748B]">تأكد من صحة كافة البيانات المدخلة قبل الحفظ وبدء ربط الأقسام والخدمات.</p>
            </div>

            <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-5 space-y-4">
              <div className="flex items-start justify-between border-b border-[#E2E8F0] pb-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-xl bg-blue-100 text-[#1E3A8A] font-bold">
                    <Hospital className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-[#0F172A]">{formData.name}</h3>
                    <div className="text-xs text-[#64748B] flex items-center gap-2 mt-0.5">
                      <span className="font-mono">{formData.code}</span>
                      <span>•</span>
                      <span>{formData.nameEn}</span>
                      <span>•</span>
                      <span className="font-semibold text-teal-700">{formData.type}</span>
                    </div>
                  </div>
                </div>

                <span className="px-2.5 py-1 rounded text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                  {formData.status === "active" ? "جاهز للتفعيل" : "حالة مخصصة"}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <div className="text-[#64748B] font-semibold mb-1">الموقع الجغرافي</div>
                  <div className="text-[#0F172A] font-medium leading-relaxed">
                    {formData.location.governorate}، {formData.location.city}
                    <br />
                    {formData.location.address}
                  </div>
                </div>

                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <div className="text-[#64748B] font-semibold mb-1">الإدارة المسؤولة</div>
                  <div className="text-[#0F172A] font-medium leading-relaxed">
                    المدير: {formData.administration.managerName}
                    <br />
                    هاتف: {formData.administration.managerPhone}
                    <br />
                    إيميل: {formData.administration.managerEmail}
                  </div>
                </div>

                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <div className="text-[#64748B] font-semibold mb-1">التشغيل وساعات العمل</div>
                  <div className="text-[#0F172A] font-medium leading-relaxed">
                    العملة: {formData.operations.currency}
                    <br />
                    الساعات: {formData.operations.standardHours}
                    <br />
                    طوارئ 24/7: {formData.operations.is24HoursEmergency ? "نعم مفعّل" : "غير مفعّل"}
                  </div>
                </div>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-blue-600 shrink-0" />
              <span>
                عند الحفظ، سيتم إنشاء المنشأة في الهيكل المؤسسي وإتاحة إضافة المباني، الطوابق، والأقسام الطبية التابعة لها مباشرة.
              </span>
            </div>
          </div>
        )}

        {/* Wizard Controls */}
        <div className="flex items-center justify-between border-t border-[#F1F5F9] pt-4">
          <div>
            {currentStep > 1 && (
              <button
                type="button"
                onClick={handlePrev}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[#CBD5E1] bg-white text-xs font-semibold text-[#475569] hover:bg-[#F8FAFC]"
              >
                <ArrowRight className="w-4 h-4" /> الخطوة السابقة
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 rounded-lg border border-[#CBD5E1] bg-white text-xs font-semibold text-[#475569] hover:bg-[#F8FAFC]"
            >
              إلغاء
            </button>

            {currentStep < 5 ? (
              <button
                type="button"
                onClick={handleNext}
                className="inline-flex items-center gap-1.5 px-5 py-2 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF] shadow-xs"
              >
                الخطوة التالية <ArrowLeft className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="submit"
                className="inline-flex items-center gap-1.5 px-6 py-2 rounded-lg bg-emerald-700 text-white text-xs font-bold hover:bg-emerald-800 shadow-xs"
              >
                <Save className="w-4 h-4" /> {isEdit ? "حفظ التعديلات" : "اعتماد وحفظ المنشأة"}
              </button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
