import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, Hotel, LogIn, LogOut, Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { Input } from "@/components/kit/input";

export default function HotelPmsView() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [filterFloor] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [showNewReservationModal, setShowNewReservationModal] = useState(false);

  const [resForm, setResForm] = useState({
    guest_name: "",
    guest_phone: "",
    guest_passport: "",
    room_number: "",
    check_in_date: new Date().toISOString().split("T")[0],
    check_out_date: new Date(Date.now() + 86400000).toISOString().split("T")[0],
    nights: 1,
    room_rate: 1800,
    paid_amount: 0,
  });

  const { data: rooms = [] } = useQuery<any[]>({
    queryKey: ["hotel_pms_rooms"],
    queryFn: async () => {
      try {
        const res = await api.get<any[]>("/hospitality/pms/rooms");
        return res || [];
      } catch {
        const fallback = await api.get<any[]>("/hospitality/rooms");
        return fallback || [];
      }
    },
  });

  const { data: reservations = [] } = useQuery<any[]>({
    queryKey: ["hotel_pms_reservations"],
    queryFn: async () => {
      try {
        const res = await api.get<any[]>("/hospitality/pms/reservations");
        return res || [];
      } catch {
        const fallback = await api.get<any[]>("/hospitality/reservations");
        return fallback || [];
      }
    },
  });

  const handleCreateReservation = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      try {
        await api.post("/hospitality/pms/reservations", resForm);
      } catch {
        await api.post("/hospitality/reservations", resForm);
      }
      toast("success", "تم تأكيد الحجز بنجاح");
      setShowNewReservationModal(false);
      queryClient.invalidateQueries({ queryKey: ["hotel_pms_reservations"] });
      queryClient.invalidateQueries({ queryKey: ["hotel_pms_rooms"] });
    } catch (err: any) {
      toast("error", `تعذر تسجيل الحجز: ${err.message || ""}`);
    }
  };

  const handleCheckin = async (resId: string) => {
    try {
      try {
        await api.post(`/hospitality/pms/reservations/${resId}/checkin`, { initial_deposit: 0 });
      } catch {
        await api.post(`/hospitality/reservations/${resId}/checkin`, { initial_deposit: 0 });
      }
      toast("success", "تم تسكين النزيل وتسليم المفتاح بنجاح");
      queryClient.invalidateQueries({ queryKey: ["hotel_pms_reservations"] });
      queryClient.invalidateQueries({ queryKey: ["hotel_pms_rooms"] });
    } catch (err: any) {
      toast("error", `فشل التسكين: ${err.message || ""}`);
    }
  };

  const handleCheckout = async (resId: string) => {
    try {
      try {
        await api.post(`/hospitality/pms/reservations/${resId}/checkout`, { settle_all: true });
      } catch {
        await api.post(`/hospitality/reservations/${resId}/checkout`, { settle_all: true });
      }
      toast("success", "تمت مغادرة النزيل وإحالة الغرفة للنظافة");
      queryClient.invalidateQueries({ queryKey: ["hotel_pms_reservations"] });
      queryClient.invalidateQueries({ queryKey: ["hotel_pms_rooms"] });
    } catch (err: any) {
      toast("error", `فشل تسجيل المغادرة: ${err.message || ""}`);
    }
  };

  const filteredRooms = rooms.filter((r) => {
    if (filterFloor !== "all" && r.floor !== filterFloor) return false;
    if (filterStatus !== "all" && r.status !== filterStatus) return false;
    return true;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "vacant_clean":
        return <Badge className="bg-emerald-50 text-emerald-800 border border-emerald-300">شاغرة ونظيفة</Badge>;
      case "occupied":
        return <Badge className="bg-[#651E2C]/10 text-[#651E2C] border border-[#651E2C]/30 font-semibold">مشغولة (نزيل)</Badge>;
      case "vacant_dirty":
        return <Badge className="bg-amber-50 text-amber-800 border border-amber-300">بحاجة لتنظيف</Badge>;
      case "out_of_order":
        return <Badge className="bg-rose-50 text-rose-800 border border-rose-300">خارج الخدمة (صيانة)</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6 text-[#262321]" dir="rtl">
      {/* Top Header Card */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-l from-[#651E2C]/5 via-[#FAF6F0] to-[#FAF6F0] border border-[#651E2C]/15 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[#651E2C] text-[#FAF6F0] flex items-center justify-center shadow-md">
            <Hotel className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold font-serif text-[#262321]">إدارة الغرف والتسكين (Hotel PMS)</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[#651E2C]/10 text-[#651E2C] font-mono font-bold">HOT-PMS</span>
            </div>
            <p className="text-xs text-[#262321]/70 mt-0.5">خريطة الغرف التفاعلية، الحجوزات، تسكين ومغادرة النزلاء (Check-in / Check-out)</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={() => {
              setResForm((prev) => ({ ...prev, room_number: "" }));
              setShowNewReservationModal(true);
            }}
            className="bg-[#651E2C] hover:bg-[#521824] text-[#FAF6F0] text-xs font-semibold px-4 py-2 rounded-xl shadow transition"
          >
            <Plus className="w-4 h-4 ml-1.5" />
            حجز غرفة جديد
          </Button>
        </div>
      </div>

      {/* Filter Chips */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-[#FAF6F0] rounded-xl border border-[#651E2C]/10 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[#262321]/70">تصفية الحالة:</span>
          {["all", "vacant_clean", "occupied", "vacant_dirty", "out_of_order"].map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-3 py-1 rounded-lg transition font-medium ${
                filterStatus === st
                  ? "bg-[#651E2C] text-[#FAF6F0] shadow-xs"
                  : "bg-white text-[#262321]/80 hover:bg-[#651E2C]/5 border border-[#651E2C]/10"
              }`}
            >
              {st === "all" ? "جميع الغرف" : st === "vacant_clean" ? "نظيفة وشاغرة" : st === "occupied" ? "مشغولة" : st === "vacant_dirty" ? "بحاجة تنظيف" : "صيانة"}
            </button>
          ))}
        </div>
        <div className="text-xs text-[#262321]/60 font-medium">
          إجمالي الغرف المعروضة: <span className="num font-bold text-[#651E2C]">{filteredRooms.length}</span>
        </div>
      </div>

      {/* Interactive Room Grid / Rack */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {filteredRooms.map((r) => (
          <div
            key={r.id}
            className={`p-4 rounded-xl border transition-all duration-200 bg-white relative hover:shadow-md ${
              r.status === "occupied"
                ? "border-[#651E2C]/30 bg-gradient-to-b from-[#651E2C]/5 to-transparent"
                : r.status === "vacant_dirty"
                ? "border-amber-200 bg-amber-50/20"
                : "border-[#651E2C]/10"
            }`}
          >
            <div className="flex items-start justify-between">
              <div>
                <span className="num text-xl font-bold font-serif text-[#262321]">{r.room_number}</span>
                <p className="text-xs text-[#262321]/70 font-medium mt-0.5">{r.room_type}</p>
              </div>
              <div>{getStatusBadge(r.status)}</div>
            </div>

            <div className="mt-3 pt-3 border-t border-[#651E2C]/5 text-xs text-[#262321]/70 space-y-1">
              <div className="flex justify-between">
                <span>الطابق:</span>
                <span className="font-semibold text-[#262321]">{r.floor}</span>
              </div>
              <div className="flex justify-between">
                <span>السعر اليومي:</span>
                <span className="num font-bold text-[#651E2C]">{r.base_rate?.toLocaleString()} ج.م</span>
              </div>
              <div className="flex justify-between">
                <span>السرير:</span>
                <span className="font-medium text-[#262321]/80">{r.bed_type}</span>
              </div>
            </div>

            <div className="mt-4 pt-2 flex items-center justify-end gap-1.5 border-t border-[#651E2C]/5">
              {r.status === "vacant_clean" && (
                <Button
                  size="sm"
                  onClick={() => {
                    setResForm((prev) => ({
                      ...prev,
                      room_number: r.room_number,
                      room_rate: r.base_rate,
                    }));
                    setShowNewReservationModal(true);
                  }}
                  className="bg-[#651E2C] hover:bg-[#521824] text-white text-xs py-1 px-2.5 h-auto rounded-lg"
                >
                  <LogIn className="w-3.5 h-3.5 ml-1" />
                  حجز وتسكين
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Active Reservations Table */}
      <Card className="p-5 border-[#651E2C]/15 bg-white shadow-sm rounded-2xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold font-serif text-[#262321] flex items-center gap-2">
            <Calendar className="w-4 h-4 text-[#651E2C]" />
            حجوزات وتسكينات النزلاء النشطة
          </h3>
          <span className="text-xs px-2.5 py-1 rounded-full bg-[#651E2C]/5 text-[#651E2C] font-semibold">
            {reservations.length} حجز مسجل
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-right border-collapse">
            <thead>
              <tr className="border-b border-[#651E2C]/10 bg-[#FAF6F0] text-[#262321]/80">
                <th className="py-2.5 px-3 font-semibold">رقم الحجز</th>
                <th className="py-2.5 px-3 font-semibold">النزيل</th>
                <th className="py-2.5 px-3 font-semibold">الغرفة</th>
                <th className="py-2.5 px-3 font-semibold">تاريخ الوصول</th>
                <th className="py-2.5 px-3 font-semibold">المغادرة</th>
                <th className="py-2.5 px-3 font-semibold">الإجمالي</th>
                <th className="py-2.5 px-3 font-semibold">الحالة</th>
                <th className="py-2.5 px-3 font-semibold text-center">الإجراءات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#651E2C]/5">
              {reservations.map((res) => (
                <tr key={res.id} className="hover:bg-[#FAF6F0]/50 transition">
                  <td className="py-2.5 px-3 num font-mono font-bold text-[#651E2C]">{res.reservation_ref}</td>
                  <td className="py-2.5 px-3 font-semibold text-[#262321]">
                    {res.guest_name}
                    <div className="text-[10px] text-[#262321]/60 font-mono">{res.guest_phone}</div>
                  </td>
                  <td className="py-2.5 px-3 num font-bold">{res.room_number}</td>
                  <td className="py-2.5 px-3 num text-[#262321]/70">{res.check_in_date}</td>
                  <td className="py-2.5 px-3 num text-[#262321]/70">{res.check_out_date}</td>
                  <td className="py-2.5 px-3 num font-bold text-[#651E2C]">{res.total_charges?.toLocaleString()} ج.م</td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        res.status === "checked_in"
                          ? "bg-emerald-100 text-emerald-800"
                          : res.status === "confirmed"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {res.status === "checked_in" ? "مسكن حالياً" : res.status === "confirmed" ? "مؤكد مسبقاً" : res.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    {res.status === "confirmed" && (
                      <Button
                        size="sm"
                        onClick={() => handleCheckin(res.id)}
                        className="bg-emerald-700 hover:bg-emerald-800 text-white text-[11px] py-1 px-2.5 h-auto rounded-lg"
                      >
                        <LogIn className="w-3 h-3 ml-1" />
                        تسكين (Check-in)
                      </Button>
                    )}
                    {res.status === "checked_in" && (
                      <Button
                        size="sm"
                        onClick={() => handleCheckout(res.id)}
                        className="bg-[#651E2C] hover:bg-[#521824] text-white text-[11px] py-1 px-2.5 h-auto rounded-lg"
                      >
                        <LogOut className="w-3 h-3 ml-1" />
                        مغادرة (Check-out)
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal: New Reservation */}
      {showNewReservationModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#651E2C]/20 shadow-2xl max-w-md w-full p-6 text-right space-y-4">
            <div className="flex items-center justify-between border-b border-[#651E2C]/10 pb-3">
              <h3 className="font-bold font-serif text-lg text-[#262321]">تسجيل حجز وتسكين نزيل</h3>
              <button onClick={() => setShowNewReservationModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateReservation} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium mb-1 text-[#262321]">اسم النزيل الكامل:</label>
                <Input
                  required
                  value={resForm.guest_name}
                  onChange={(e) => setResForm({ ...resForm, guest_name: e.target.value })}
                  placeholder="مثال: أحمد عبد الرحمن الشريف"
                  className="text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">رقم الهاتف:</label>
                  <Input
                    required
                    value={resForm.guest_phone}
                    onChange={(e) => setResForm({ ...resForm, guest_phone: e.target.value })}
                    placeholder="01012345678"
                    className="text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">رقم الهوية / الجواز:</label>
                  <Input
                    required
                    value={resForm.guest_passport}
                    onChange={(e) => setResForm({ ...resForm, guest_passport: e.target.value })}
                    placeholder="A12345678"
                    className="text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">رقم الغرفة:</label>
                  <Input
                    required
                    value={resForm.room_number}
                    onChange={(e) => setResForm({ ...resForm, room_number: e.target.value })}
                    placeholder="101"
                    className="text-xs font-mono font-bold"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">عدد الليالي:</label>
                  <Input
                    type="number"
                    min="1"
                    required
                    value={resForm.nights}
                    onChange={(e) => setResForm({ ...resForm, nights: parseInt(e.target.value) || 1 })}
                    className="text-xs num"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">تاريخ الوصول:</label>
                  <Input
                    type="date"
                    required
                    value={resForm.check_in_date}
                    onChange={(e) => setResForm({ ...resForm, check_in_date: e.target.value })}
                    className="text-xs num"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">تاريخ المغادرة:</label>
                  <Input
                    type="date"
                    required
                    value={resForm.check_out_date}
                    onChange={(e) => setResForm({ ...resForm, check_out_date: e.target.value })}
                    className="text-xs num"
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-[#651E2C]/10 flex items-center justify-between text-sm">
                <span className="font-semibold text-[#262321]/70">إجمالي التكلفة المقدرة:</span>
                <span className="num font-bold text-lg text-[#651E2C]">{(resForm.nights * resForm.room_rate).toLocaleString()} ج.م</span>
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setShowNewReservationModal(false)} className="text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="bg-[#651E2C] hover:bg-[#521824] text-white text-xs font-semibold px-4">
                  تأكيد وحفظ الحجز
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
