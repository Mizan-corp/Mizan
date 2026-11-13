import { useState } from "react";
import {
  Clock, Plus, Save, CheckCircle2,
  CalendarDays, Trash2, X, GitFork, ShieldCheck
} from "lucide-react";
import {
  OperatingDaySchedule,
  HolidayException,
  HealthcareFacilityItem,
  DepartmentItem
} from "../types";

interface OperatingScheduleProps {
  schedule: OperatingDaySchedule[];
  holidays: HolidayException[];
  facilities: HealthcareFacilityItem[];
  departments: DepartmentItem[];
  currentFacilityId: string | "all";
  onUpdateSchedule: (newSchedule: OperatingDaySchedule[]) => void;
  onAddHoliday: (holiday: HolidayException) => void;
  onDeleteHoliday: (id: string) => void;
}

export default function Screen10_OperatingSchedule({
  schedule: initialSchedule,
  holidays: initialHolidays,
  facilities,
  departments,
  currentFacilityId,
  onUpdateSchedule,
  onAddHoliday,
  onDeleteHoliday,
}: OperatingScheduleProps) {
  const [schedule, setSchedule] = useState<OperatingDaySchedule[]>(initialSchedule);
  const [holidays, setHolidays] = useState<HolidayException[]>(initialHolidays);
  const [is24HoursEmergency, setIs24HoursEmergency] = useState(true);
  const [activeTab, setActiveTab] = useState<"weekly_matrix" | "holidays" | "dept_overrides">("weekly_matrix");
  const [showAddHolidayModal, setShowAddHolidayModal] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // New Holiday Form State
  const [holTitle, setHolTitle] = useState("");
  const [holStartDate, setHolStartDate] = useState("2026-04-10");
  const [holEndDate, setHolEndDate] = useState("2026-04-13");
  const [holReason, setHolReason] = useState("إجازة رسمية معتمدة");
  const [holIsFullClosure, setHolIsFullClosure] = useState(true);
  const [holAppliesToAll, setHolAppliesToAll] = useState(true);

  // Toggle Day Open/Close
  const toggleDay = (dayIndex: number) => {
    const updated = [...schedule];
    updated[dayIndex].isOpen = !updated[dayIndex].isOpen;
    setSchedule(updated);
    setHasUnsavedChanges(true);
  };

  // Update shift times
  const updateShift = (
    dayIndex: number,
    shiftIndex: number,
    field: "startTime" | "endTime" | "breakStartTime" | "breakEndTime",
    value: string
  ) => {
    const updated = [...schedule];
    updated[dayIndex].shifts[shiftIndex] = {
      ...updated[dayIndex].shifts[shiftIndex],
      [field]: value,
    };
    setSchedule(updated);
    setHasUnsavedChanges(true);
  };

  const handleSaveSchedule = () => {
    onUpdateSchedule(schedule);
    setHasUnsavedChanges(false);
    alert("تم حفظ وتعميم مصفوفة ساعات العمل الأسبوعية بنجاح.");
  };

  const handleCreateHoliday = (e: React.FormEvent) => {
    e.preventDefault();
    if (!holTitle) return;

    const newHol: HolidayException = {
      id: `hol-${Date.now()}`,
      facilityId: currentFacilityId !== "all" ? currentFacilityId : facilities[0]?.id || "",
      title: holTitle,
      startDate: holStartDate,
      endDate: holEndDate,
      isFullClosure: holIsFullClosure,
      reason: holReason,
      appliesToAllDepartments: holAppliesToAll,
      affectedDepartmentIds: holAppliesToAll ? undefined : [departments[0]?.id || ""],
    };

    onAddHoliday(newHol);
    setHolidays([...holidays, newHol]);
    setShowAddHolidayModal(false);
    setHolTitle("");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
              HLT-01-004 • الجدولة التشغيلية
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            ساعات العمل، المناوبات والعطلات الرسمية
          </h1>
          <p className="text-xs text-[#64748B]">
            ضبط مصفوفة أوقات تقديم الخدمات، المناوبات الصباحية والمسائية، استثناءات العطلات، والتشغيل المستمر للطوارئ.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {hasUnsavedChanges && (
            <button
              onClick={handleSaveSchedule}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-700 text-white text-xs font-bold hover:bg-emerald-800 shadow-xs"
            >
              <Save className="w-4 h-4" /> حفظ التغييرات
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-[#E2E8F0] pb-2">
        <button
          onClick={() => setActiveTab("weekly_matrix")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === "weekly_matrix"
              ? "bg-[#1E3A8A] text-white shadow-xs"
              : "text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9]"
          }`}
        >
          <Clock className="w-4 h-4" /> مصفوفة العمل الأسبوعية (Weekly Matrix)
        </button>
        <button
          onClick={() => setActiveTab("holidays")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === "holidays"
              ? "bg-[#1E3A8A] text-white shadow-xs"
              : "text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9]"
          }`}
        >
          <CalendarDays className="w-4 h-4" /> العطلات والاستثناءات الرسمية ({holidays.length})
        </button>
        <button
          onClick={() => setActiveTab("dept_overrides")}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === "dept_overrides"
              ? "bg-[#1E3A8A] text-white shadow-xs"
              : "text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9]"
          }`}
        >
          <GitFork className="w-4 h-4" /> استثناءات الأقسام (Department Overrides)
        </button>
      </div>

      {/* ─── TAB 1: WEEKLY MATRIX ────────────────────────────────────────── */}
      {activeTab === "weekly_matrix" && (
        <div className="space-y-6">
          {/* Emergency 24/7 Banner Card */}
          <div className="rounded-xl border border-teal-200 bg-teal-50/60 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-teal-600 text-white font-bold">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-teal-950">
                  خدمة طوارئ واستقبال الحالات الحرجة 24/7
                </h3>
                <p className="text-xs text-teal-700 mt-0.5">
                  عند تفعيل هذا الخيار، تظل أقسام الطوارئ والحوادث وبنك الدم والأشعة العاجلة مفتوحة على مدار 24 ساعة يومياً بصرف النظر عن مواعيد العيادات.
                </p>
              </div>
            </div>

            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={is24HoursEmergency}
                onChange={(e) => setIs24HoursEmergency(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-12 h-6 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
            </label>
          </div>

          {/* Days Matrix Table */}
          <div className="rounded-xl border border-[#E2E8F0] bg-white overflow-hidden shadow-2xs">
            <table className="w-full text-right text-xs">
              <thead className="bg-[#F8FAFC] text-[#475569] font-bold border-b border-[#E2E8F0]">
                <tr>
                  <th className="py-3 px-4 w-32">اليوم</th>
                  <th className="py-3 px-4 w-28 text-center">الحالة</th>
                  <th className="py-3 px-4">الوردية الأولى (الصباحية)</th>
                  <th className="py-3 px-4">فترة الاستراحة / الصلاة</th>
                  <th className="py-3 px-4">الوردية الثانية (المسائية)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {schedule.map((dayItem, dIdx) => (
                  <tr key={dayItem.day} className={`hover:bg-[#F8FAFC] ${!dayItem.isOpen ? "bg-slate-50/50 opacity-60" : ""}`}>
                    <td className="py-3 px-4">
                      <div className="font-bold text-[#0F172A]">{dayItem.dayNameAr}</div>
                      <div className="text-[11px] text-[#64748B]">{dayItem.dayNameEn}</div>
                    </td>

                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => toggleDay(dIdx)}
                        className={`px-3 py-1 rounded-full text-[10px] font-bold transition-colors ${
                          dayItem.isOpen
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : "bg-slate-200 text-slate-700"
                        }`}
                      >
                        {dayItem.isOpen ? "مفتوح" : "مغلق"}
                      </button>
                    </td>

                    {/* Shift 1 */}
                    <td className="py-3 px-4">
                      {dayItem.isOpen && dayItem.shifts[0] ? (
                        <div className="flex items-center gap-1.5 font-mono">
                          <input
                            type="time"
                            value={dayItem.shifts[0].startTime}
                            onChange={(e) => updateShift(dIdx, 0, "startTime", e.target.value)}
                            className="p-1 border border-[#CBD5E1] rounded bg-white text-xs"
                          />
                          <span>-</span>
                          <input
                            type="time"
                            value={dayItem.shifts[0].endTime}
                            onChange={(e) => updateShift(dIdx, 0, "endTime", e.target.value)}
                            className="p-1 border border-[#CBD5E1] rounded bg-white text-xs"
                          />
                        </div>
                      ) : (
                        <span className="text-[#94A3B8]">عطلة أسبوعية</span>
                      )}
                    </td>

                    {/* Break */}
                    <td className="py-3 px-4">
                      {dayItem.isOpen && dayItem.shifts[0]?.breakStartTime ? (
                        <div className="flex items-center gap-1.5 font-mono text-[#64748B]">
                          <input
                            type="time"
                            value={dayItem.shifts[0].breakStartTime}
                            onChange={(e) => updateShift(dIdx, 0, "breakStartTime", e.target.value)}
                            className="p-1 border border-[#CBD5E1] rounded bg-white text-xs"
                          />
                          <span>-</span>
                          <input
                            type="time"
                            value={dayItem.shifts[0].breakEndTime || "13:30"}
                            onChange={(e) => updateShift(dIdx, 0, "breakEndTime", e.target.value)}
                            className="p-1 border border-[#CBD5E1] rounded bg-white text-xs"
                          />
                        </div>
                      ) : (
                        <span className="text-[#94A3B8]">—</span>
                      )}
                    </td>

                    {/* Shift 2 */}
                    <td className="py-3 px-4">
                      {dayItem.isOpen && dayItem.shifts[1] ? (
                        <div className="flex items-center gap-1.5 font-mono">
                          <input
                            type="time"
                            value={dayItem.shifts[1].startTime}
                            onChange={(e) => updateShift(dIdx, 1, "startTime", e.target.value)}
                            className="p-1 border border-[#CBD5E1] rounded bg-white text-xs"
                          />
                          <span>-</span>
                          <input
                            type="time"
                            value={dayItem.shifts[1].endTime}
                            onChange={(e) => updateShift(dIdx, 1, "endTime", e.target.value)}
                            className="p-1 border border-[#CBD5E1] rounded bg-white text-xs"
                          />
                        </div>
                      ) : (
                        <span className="text-[#94A3B8]">لا توجد وردية ثانية</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── TAB 2: HOLIDAYS & EXCEPTIONS ────────────────────────────────── */}
      {activeTab === "holidays" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-[#0F172A]">
              سجل العطلات الرسمية والإغلاقات المجدولة ({holidays.length})
            </h3>
            <button
              onClick={() => setShowAddHolidayModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1E3A8A] text-white text-xs font-semibold hover:bg-[#1E40AF]"
            >
              <Plus className="w-3.5 h-3.5" /> إضافة عطلة أو استثناء
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {holidays.map((hol) => (
              <div
                key={hol.id}
                className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-2xs space-y-3 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-bold text-sm text-[#0F172A]">{hol.title}</h4>
                      <div className="text-xs text-[#64748B] flex items-center gap-2 mt-0.5">
                        <span className="font-mono">{hol.startDate}</span>
                        <span>إلى</span>
                        <span className="font-mono">{hol.endDate}</span>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                      {hol.isFullClosure ? "إغلاق كامل للعيادات" : "ساعات مخفضة"}
                    </span>
                  </div>

                  <p className="text-xs text-[#475569] mt-2 bg-[#F8FAFC] p-2.5 rounded-lg border border-[#E2E8F0]">
                    السبب: {hol.reason}
                  </p>

                  <div className="text-[11px] text-[#64748B] mt-2 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
                    <span>
                      {hol.appliesToAllDepartments
                        ? "يسري على جميع الأقسام مع استمرار الطوارئ 24/7"
                        : "يسري على عيادات مختارة فقط"}
                    </span>
                  </div>
                </div>

                <div className="pt-3 border-t border-[#F1F5F9] flex justify-end">
                  <button
                    onClick={() => onDeleteHoliday(hol.id)}
                    className="text-xs font-medium text-red-600 hover:text-red-800 flex items-center gap-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> حذف الاستثناء
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── TAB 3: DEPT OVERRIDES ───────────────────────────────────────── */}
      {activeTab === "dept_overrides" && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900">
            يمكن لكل قسم طبي تخصيص ساعات عمل تختلف عن ساعات المنشأة العامة (مثل أقسام الغسيل الكلوي التي تبدأ في 06:00 صباحاً أو مراكز الأشعة التداخلية).
          </div>

          <div className="rounded-xl border border-[#E2E8F0] bg-white overflow-hidden shadow-2xs">
            <table className="w-full text-right text-xs">
              <thead className="bg-[#F8FAFC] text-[#475569] font-bold border-b border-[#E2E8F0]">
                <tr>
                  <th className="py-2.5 px-4">القسم الطبي</th>
                  <th className="py-2.5 px-4">التصنيف</th>
                  <th className="py-2.5 px-4">ساعات العمل المخصصة</th>
                  <th className="py-2.5 px-4 text-center">إجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {departments.map((d) => (
                  <tr key={d.id} className="hover:bg-[#F8FAFC]">
                    <td className="py-2.5 px-4 font-bold text-[#0F172A]">{d.name}</td>
                    <td className="py-2.5 px-4 text-[#64748B]">{d.category}</td>
                    <td className="py-2.5 px-4 font-mono font-medium text-teal-800">{d.operatingHours}</td>
                    <td className="py-2.5 px-4 text-center">
                      <button className="px-2.5 py-1 text-xs rounded bg-white border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC]">
                        تعديل الساعات
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── MODAL: ADD HOLIDAY ──────────────────────────────────────────── */}
      {showAddHolidayModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="font-bold text-base text-[#0F172A] flex items-center gap-2">
                <CalendarDays className="w-5 h-5 text-[#1E3A8A]" /> إضافة عطلة رسمية أو استثناء إغلاق
              </h3>
              <button onClick={() => setShowAddHolidayModal(false)} className="text-[#64748B] hover:text-[#0F172A]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateHoliday} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-[#334155] block mb-1">مناسبة العطلة أو الاستثناء *</label>
                <input
                  type="text"
                  placeholder="مثال: إجازة عيد الفطر المبارك"
                  value={holTitle}
                  onChange={(e) => setHolTitle(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-[#334155] block mb-1">تاريخ البدء</label>
                  <input
                    type="date"
                    value={holStartDate}
                    onChange={(e) => setHolStartDate(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  />
                </div>
                <div>
                  <label className="font-bold text-[#334155] block mb-1">تاريخ الانتهاء</label>
                  <input
                    type="date"
                    value={holEndDate}
                    onChange={(e) => setHolEndDate(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-[#334155] block mb-1">السبب أو القرار الإداري</label>
                <input
                  type="text"
                  value={holReason}
                  onChange={(e) => setHolReason(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-[#CBD5E1] focus:outline-none focus:border-[#1E3A8A]"
                />
              </div>

              <div className="p-3 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0] space-y-2">
                <label className="flex items-center gap-2 cursor-pointer font-bold text-[#334155]">
                  <input
                    type="checkbox"
                    checked={holIsFullClosure}
                    onChange={(e) => setHolIsFullClosure(e.target.checked)}
                    className="rounded text-[#1E3A8A]"
                  />
                  <span>إغلاق كامل للعيادات الخارجية والمكاتب الإدارية</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer font-bold text-[#334155]">
                  <input
                    type="checkbox"
                    checked={holAppliesToAll}
                    onChange={(e) => setHolAppliesToAll(e.target.checked)}
                    className="rounded text-[#1E3A8A]"
                  />
                  <span>يسري على جميع الأقسام مع بقاء الطوارئ 24/7 مفتوحة</span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[#F1F5F9] pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddHolidayModal(false)}
                  className="px-4 py-2 rounded-lg border border-[#CBD5E1] text-[#475569] hover:bg-[#F8FAFC]"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-[#1E3A8A] text-white font-bold hover:bg-[#1E40AF]"
                >
                  حفظ الاستثناء
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
