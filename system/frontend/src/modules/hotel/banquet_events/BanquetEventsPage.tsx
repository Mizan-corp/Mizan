import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Users, X } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { Button } from "@/components/kit/button";
import { Input } from "@/components/kit/input";

export default function BanquetEventsView() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [showNewModal, setShowNewModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const [form, setForm] = useState({
    hall_name: "قاعة اللؤلؤة الكبرى (Grand Pearl Ballroom)",
    client_name: "",
    client_phone: "",
    event_type: "حفل زفاف ملكي (Wedding Gala)",
    event_date: new Date(Date.now() + 86400000 * 7).toISOString().split("T")[0],
    start_time: "19:00",
    end_time: "01:00",
    guest_count: 200,
    catering_package: "بوفيه مفتوح ملكي VIP مع مشروبات ترحيبية",
    total_amount: 85000,
    deposit_amount: 30000,
  });

  const { data: events = [] } = useQuery<any[]>({
    queryKey: ["hotel_banquet_events"],
    queryFn: async () => {
      try {
        const res = await api.get<any[]>("/hospitality/banquet/events");
        return res || [];
      } catch {
        return [];
      }
    },
  });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/hospitality/banquet/events", form);
      toast("success", "تم تأكيد حجز القاعة والفعالية بنجاح");
      setShowNewModal(false);
      setForm({
        hall_name: "قاعة اللؤلؤة الكبرى (Grand Pearl Ballroom)",
        client_name: "",
        client_phone: "",
        event_type: "حفل زفاف ملكي (Wedding Gala)",
        event_date: new Date(Date.now() + 86400000 * 7).toISOString().split("T")[0],
        start_time: "19:00",
        end_time: "01:00",
        guest_count: 200,
        catering_package: "بوفيه مفتوح ملكي VIP مع مشروبات ترحيبية",
        total_amount: 85000,
        deposit_amount: 30000,
      });
      queryClient.invalidateQueries({ queryKey: ["hotel_banquet_events"] });
    } catch (err: any) {
      toast("error", `فشل الحجز: ${err.message || ""}`);
    }
  };

  const handleStatusChange = async (eventId: string, status: string) => {
    try {
      await api.post(`/hospitality/banquet/events/${eventId}/status`, { status });
      toast("success", "تم تحديث حالة الفعالية");
      queryClient.invalidateQueries({ queryKey: ["hotel_banquet_events"] });
    } catch (err: any) {
      toast("error", `فشل التحديث: ${err.message || ""}`);
    }
  };

  const filteredEvents = events.filter((e) => {
    if (filterStatus !== "all" && e.status !== filterStatus) return false;
    return true;
  });

  return (
    <div className="space-y-6 text-[#262321]" dir="rtl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-l from-[#651E2C]/5 via-[#FAF6F0] to-[#FAF6F0] border border-[#651E2C]/15 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[#651E2C] text-[#FAF6F0] flex items-center justify-center shadow-md">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold font-serif text-[#262321]">الحفلات والمؤتمرات والقاعات (Banquets)</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[#651E2C]/10 text-[#651E2C] font-mono font-bold">HOT-BNQ</span>
            </div>
            <p className="text-xs text-[#262321]/70 mt-0.5">حجوزات القاعات الكبرى والاجتماعات، تنسيق برامج البوفيه والضيافة، وتتبع الحضور</p>
          </div>
        </div>

        <Button
          onClick={() => setShowNewModal(true)}
          className="bg-[#651E2C] hover:bg-[#521824] text-[#FAF6F0] text-xs font-semibold px-4 py-2 rounded-xl shadow transition"
        >
          <Plus className="w-4 h-4 ml-1.5" />
          حجز قاعة وفعالية جديدة
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between gap-3 p-3 bg-[#FAF6F0] rounded-xl border border-[#651E2C]/10 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[#262321]/70">تصفية الحالة:</span>
          {["all", "confirmed", "in_progress", "completed", "cancelled"].map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-3 py-1 rounded-lg transition font-medium ${
                filterStatus === st
                  ? "bg-[#651E2C] text-[#FAF6F0] shadow-xs"
                  : "bg-white text-[#262321]/80 hover:bg-[#651E2C]/5 border border-[#651E2C]/10"
              }`}
            >
              {st === "all" ? "كافة الفعاليات" : st === "confirmed" ? "مؤكدة" : st === "in_progress" ? "جارية حالياً" : st === "completed" ? "منتهية" : "ملغاة"}
            </button>
          ))}
        </div>
        <div className="text-xs text-[#262321]/60 font-medium">
          إجمالي الفعاليات: <span className="num font-bold text-[#651E2C]">{filteredEvents.length}</span>
        </div>
      </div>

      {/* Events Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredEvents.map((ev) => (
          <div
            key={ev.id}
            className="p-5 rounded-2xl border border-[#651E2C]/15 bg-white shadow-xs hover:shadow-md transition space-y-3"
          >
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] font-mono font-bold text-[#651E2C] px-2 py-0.5 rounded-md bg-[#651E2C]/10">
                  {ev.booking_ref}
                </span>
                <h4 className="text-sm font-bold text-[#262321] mt-1.5">{ev.hall_name}</h4>
              </div>
              <span
                className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full ${
                  ev.status === "confirmed"
                    ? "bg-blue-100 text-blue-800"
                    : ev.status === "in_progress"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-gray-100 text-gray-700"
                }`}
              >
                {ev.status === "confirmed" ? "حجز مؤكد" : ev.status === "in_progress" ? "جارية" : ev.status}
              </span>
            </div>

            <div className="space-y-1.5 text-xs text-[#262321]/70 border-y border-[#651E2C]/10 py-2.5">
              <div className="flex justify-between">
                <span>العميل:</span>
                <span className="font-semibold text-[#262321]">{ev.client_name} ({ev.client_phone})</span>
              </div>
              <div className="flex justify-between">
                <span>المناسبة:</span>
                <span className="font-medium text-[#262321]">{ev.event_type}</span>
              </div>
              <div className="flex justify-between">
                <span>التاريخ والوقت:</span>
                <span className="num font-medium text-[#262321]">{ev.event_date} ({ev.start_time} - {ev.end_time})</span>
              </div>
              <div className="flex justify-between">
                <span>عدد الحضور:</span>
                <span className="num font-bold text-[#651E2C]">{ev.guest_count} فرد</span>
              </div>
              <div className="flex justify-between">
                <span>باقة الضيافة:</span>
                <span className="text-[11px] text-[#262321]/80">{ev.catering_package}</span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs pt-1">
              <div>
                <span className="text-[10px] text-[#262321]/60 block">المبلغ الإجمالي</span>
                <span className="num font-bold text-sm text-[#651E2C]">{ev.total_amount?.toLocaleString()} ج.م</span>
              </div>
              <div className="text-left">
                <span className="text-[10px] text-[#262321]/60 block">العربون المسدد</span>
                <span className="num font-bold text-xs text-emerald-700">{ev.deposit_amount?.toLocaleString()} ج.م</span>
              </div>
            </div>

            <div className="pt-2 flex items-center justify-end gap-1.5 border-t border-[#651E2C]/5">
              {ev.status === "confirmed" && (
                <Button
                  size="sm"
                  onClick={() => handleStatusChange(ev.id, "in_progress")}
                  className="bg-emerald-700 hover:bg-emerald-800 text-white text-[11px] py-1 px-2.5 h-auto rounded-lg"
                >
                  بدء الفعالية
                </Button>
              )}
              {ev.status === "in_progress" && (
                <Button
                  size="sm"
                  onClick={() => handleStatusChange(ev.id, "completed")}
                  className="bg-[#651E2C] hover:bg-[#521824] text-white text-[11px] py-1 px-2.5 h-auto rounded-lg"
                >
                  إغلاق الفعالية
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Modal: New Banquet Booking */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#651E2C]/20 shadow-2xl max-w-lg w-full p-6 text-right space-y-4">
            <div className="flex items-center justify-between border-b border-[#651E2C]/10 pb-3">
              <h3 className="font-bold font-serif text-lg text-[#262321]">حجز قاعة وتنظيم فعالية</h3>
              <button onClick={() => setShowNewModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium mb-1 text-[#262321]">القاعة المختارة:</label>
                <select
                  value={form.hall_name}
                  onChange={(e) => setForm({ ...form, hall_name: e.target.value })}
                  className="w-full text-xs p-2 rounded-lg border border-[#651E2C]/20 bg-white"
                >
                  <option value="قاعة اللؤلؤة الكبرى (Grand Pearl Ballroom)">قاعة اللؤلؤة الكبرى (Grand Pearl Ballroom - سعة 500)</option>
                  <option value="قاعة النيل للمؤتمرات (Nile Conference Hall)">قاعة النيل للمؤتمرات (Nile Conference Hall - سعة 200)</option>
                  <option value="جناح كبار الزوار التنفيذي (VIP Boardroom)">جناح كبار الزوار التنفيذي (VIP Boardroom - سعة 40)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">اسم العميل / الجهة:</label>
                  <Input
                    required
                    value={form.client_name}
                    onChange={(e) => setForm({ ...form, client_name: e.target.value })}
                    placeholder="اسم العميل أو المؤسسة"
                    className="text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">رقم الهاتف للتواصل:</label>
                  <Input
                    required
                    value={form.client_phone}
                    onChange={(e) => setForm({ ...form, client_phone: e.target.value })}
                    placeholder="010XXXXXXXX"
                    className="text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">تاريخ الفعالية:</label>
                  <Input
                    type="date"
                    required
                    value={form.event_date}
                    onChange={(e) => setForm({ ...form, event_date: e.target.value })}
                    className="text-xs num"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">من:</label>
                  <Input
                    type="time"
                    required
                    value={form.start_time}
                    onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                    className="text-xs num"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">إلى:</label>
                  <Input
                    type="time"
                    required
                    value={form.end_time}
                    onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                    className="text-xs num"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">نوع المناسبة:</label>
                  <Input
                    required
                    value={form.event_type}
                    onChange={(e) => setForm({ ...form, event_type: e.target.value })}
                    placeholder="حفل زفاف، مؤتمر سنوي، ورشة عمل"
                    className="text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">عدد الحضور المتوقع:</label>
                  <Input
                    type="number"
                    min="10"
                    required
                    value={form.guest_count}
                    onChange={(e) => setForm({ ...form, guest_count: parseInt(e.target.value) || 50 })}
                    className="text-xs num"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium mb-1 text-[#262321]">باقة الضيافة والطعام:</label>
                <Input
                  required
                  value={form.catering_package}
                  onChange={(e) => setForm({ ...form, catering_package: e.target.value })}
                  placeholder="بوفيه مفتوح ملكي، استراحة قهوة، عشاء كوكتيل"
                  className="text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">إجمالي تكلفة العقد:</label>
                  <Input
                    type="number"
                    required
                    value={form.total_amount}
                    onChange={(e) => setForm({ ...form, total_amount: parseFloat(e.target.value) || 0 })}
                    className="text-xs num font-bold text-[#651E2C]"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">العربون المدفوع مقدماً:</label>
                  <Input
                    type="number"
                    required
                    value={form.deposit_amount}
                    onChange={(e) => setForm({ ...form, deposit_amount: parseFloat(e.target.value) || 0 })}
                    className="text-xs num text-emerald-700 font-semibold"
                  />
                </div>
              </div>

              <div className="pt-3 flex justify-end gap-2 border-t border-[#651E2C]/10">
                <Button type="button" variant="outline" onClick={() => setShowNewModal(false)} className="text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="bg-[#651E2C] hover:bg-[#521824] text-white text-xs font-semibold px-4">
                  تثبيت الحجز والعقد
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
