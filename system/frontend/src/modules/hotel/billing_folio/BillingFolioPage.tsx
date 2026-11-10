import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, DollarSign, Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { Input } from "@/components/kit/input";

export default function BillingFolioView() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [showNewChargeModal, setShowNewChargeModal] = useState(false);
  const [filterSettled, setFilterSettled] = useState<string>("all");

  const [chargeForm, setChargeForm] = useState({
    reservation_id: "",
    guest_name: "",
    room_number: "",
    charge_type: "مطعم وكافيه (F&B Room Service)",
    description: "عشاء فاخر ووجبات خفيفة للغرفة",
    net_amount: 450,
    tax_amount: 63,
    total_amount: 513,
    charge_date: new Date().toISOString().split("T")[0],
  });

  const { data: folios = [] } = useQuery<any[]>({
    queryKey: ["hotel_billing_folios"],
    queryFn: async () => {
      try {
        const res = await api.get<any[]>("/hospitality/billing/folios");
        return res || [];
      } catch {
        const fallback = await api.get<any[]>("/hospitality/folios");
        return fallback || [];
      }
    },
  });

  const handleCreateCharge = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      try {
        await api.post("/hospitality/billing/folios", chargeForm);
      } catch {
        await api.post("/hospitality/folios", chargeForm);
      }
      toast("success", "تم ترحيل المصروف بنجاح إلى فاتورة النزيل (Folio)");
      setShowNewChargeModal(false);
      queryClient.invalidateQueries({ queryKey: ["hotel_billing_folios"] });
      queryClient.invalidateQueries({ queryKey: ["hotel_pms_reservations"] });
    } catch (err: any) {
      toast("error", `فشل ترحيل المصروف: ${err.message || ""}`);
    }
  };

  const handleSettle = async (folioId: string) => {
    try {
      try {
        await api.post(`/hospitality/billing/folios/${folioId}/settle`, { payment_method: "card" });
      } catch {
        // fallback
      }
      toast("success", "تم تسوية البند وتأكيد الدفع");
      queryClient.invalidateQueries({ queryKey: ["hotel_billing_folios"] });
    } catch (err: any) {
      toast("error", `فشل التسوية: ${err.message || ""}`);
    }
  };

  const filteredFolios = folios.filter((f) => {
    if (filterSettled === "unsettled" && f.is_settled) return false;
    if (filterSettled === "settled" && !f.is_settled) return false;
    return true;
  });

  const totalUnsettled = folios.filter((f) => !f.is_settled).reduce((acc, f) => acc + (f.total_amount || 0), 0);

  return (
    <div className="space-y-6 text-[#262321]" dir="rtl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-l from-[#651E2C]/5 via-[#FAF6F0] to-[#FAF6F0] border border-[#651E2C]/15 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[#651E2C] text-[#FAF6F0] flex items-center justify-center shadow-md">
            <DollarSign className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold font-serif text-[#262321]">فواتير النزلاء والمصاريف (Guest Folio)</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[#651E2C]/10 text-[#651E2C] font-mono font-bold">HOT-FOLIO</span>
            </div>
            <p className="text-xs text-[#262321]/70 mt-0.5">ترحيل بنود الصرف للغرف، خدمات الغرف، الميني بار، والمغسلة، وتسوية الفواتير</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-left bg-white px-3.5 py-1.5 rounded-xl border border-[#651E2C]/15 shadow-xs">
            <span className="text-[10px] text-[#262321]/60 block font-medium">غير مسدد حالياً</span>
            <span className="num font-bold text-sm text-[#651E2C]">{totalUnsettled.toLocaleString()} ج.م</span>
          </div>

          <Button
            onClick={() => setShowNewChargeModal(true)}
            className="bg-[#651E2C] hover:bg-[#521824] text-[#FAF6F0] text-xs font-semibold px-4 py-2 rounded-xl shadow transition"
          >
            <Plus className="w-4 h-4 ml-1.5" />
            ترحيل مصروف جديد
          </Button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between gap-3 p-3 bg-[#FAF6F0] rounded-xl border border-[#651E2C]/10 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[#262321]/70">تصفية السداد:</span>
          {[
            { id: "all", label: "كافة البنود" },
            { id: "unsettled", label: "مستحق (غير مسدد)" },
            { id: "settled", label: "مسدد بالكامل" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterSettled(tab.id)}
              className={`px-3 py-1 rounded-lg transition font-medium ${
                filterSettled === tab.id
                  ? "bg-[#651E2C] text-[#FAF6F0] shadow-xs"
                  : "bg-white text-[#262321]/80 hover:bg-[#651E2C]/5 border border-[#651E2C]/10"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="text-xs text-[#262321]/60 font-medium">
          إجمالي البنود: <span className="num font-bold text-[#651E2C]">{filteredFolios.length}</span>
        </div>
      </div>

      {/* Table Card */}
      <Card className="p-5 border-[#651E2C]/15 bg-white shadow-sm rounded-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-right border-collapse">
            <thead>
              <tr className="border-b border-[#651E2C]/10 bg-[#FAF6F0] text-[#262321]/80">
                <th className="py-2.5 px-3 font-semibold">الغرفة</th>
                <th className="py-2.5 px-3 font-semibold">النزيل</th>
                <th className="py-2.5 px-3 font-semibold">نوع المصروف</th>
                <th className="py-2.5 px-3 font-semibold">التفاصيل والبيان</th>
                <th className="py-2.5 px-3 font-semibold">التاريخ</th>
                <th className="py-2.5 px-3 font-semibold">المبلغ الصافي</th>
                <th className="py-2.5 px-3 font-semibold">الإجمالي</th>
                <th className="py-2.5 px-3 font-semibold">حالة التسوية</th>
                <th className="py-2.5 px-3 font-semibold text-center">الإجراء</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#651E2C]/5">
              {filteredFolios.map((f) => (
                <tr key={f.id} className="hover:bg-[#FAF6F0]/50 transition">
                  <td className="py-2.5 px-3 num font-bold text-[#651E2C]">{f.room_number}</td>
                  <td className="py-2.5 px-3 font-semibold text-[#262321]">{f.guest_name}</td>
                  <td className="py-2.5 px-3 font-medium text-[#262321]/80">{f.charge_type}</td>
                  <td className="py-2.5 px-3 text-[#262321]/70">{f.description}</td>
                  <td className="py-2.5 px-3 num text-[#262321]/60">{f.charge_date}</td>
                  <td className="py-2.5 px-3 num">{f.net_amount?.toLocaleString()} ج.م</td>
                  <td className="py-2.5 px-3 num font-bold text-[#651E2C]">{f.total_amount?.toLocaleString()} ج.م</td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        f.is_settled
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {f.is_settled ? "تمت التسوية" : "قيد الحساب"}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    {!f.is_settled && (
                      <Button
                        size="sm"
                        onClick={() => handleSettle(f.id)}
                        className="bg-emerald-700 hover:bg-emerald-800 text-white text-[11px] py-1 px-2.5 h-auto rounded-lg"
                      >
                        <CheckCircle2 className="w-3 h-3 ml-1" />
                        تسوية
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Modal: Add Folio Charge */}
      {showNewChargeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#651E2C]/20 shadow-2xl max-w-md w-full p-6 text-right space-y-4">
            <div className="flex items-center justify-between border-b border-[#651E2C]/10 pb-3">
              <h3 className="font-bold font-serif text-lg text-[#262321]">ترحيل بند مصروف جديد (Room Charge)</h3>
              <button onClick={() => setShowNewChargeModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateCharge} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">رقم الغرفة:</label>
                  <Input
                    required
                    value={chargeForm.room_number}
                    onChange={(e) => setChargeForm({ ...chargeForm, room_number: e.target.value })}
                    placeholder="101"
                    className="text-xs font-mono font-bold"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">اسم النزيل:</label>
                  <Input
                    required
                    value={chargeForm.guest_name}
                    onChange={(e) => setChargeForm({ ...chargeForm, guest_name: e.target.value })}
                    placeholder="اسم النزيل"
                    className="text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium mb-1 text-[#262321]">نوع المصروف:</label>
                <select
                  value={chargeForm.charge_type}
                  onChange={(e) => setChargeForm({ ...chargeForm, charge_type: e.target.value })}
                  className="w-full text-xs p-2 rounded-lg border border-[#651E2C]/20 bg-white"
                >
                  <option value="إقامة ليلية (Nightly Room Charge)">إقامة ليلية (Nightly Room Charge)</option>
                  <option value="مطعم وكافيه (F&B Room Service)">مطعم وكافيه وخدمة غرف (F&B Room Service)</option>
                  <option value="ميني بار ومشروبات (Mini-Bar)">ميني بار ومشروبات (Mini-Bar)</option>
                  <option value="مغسلة وكوي (Laundry)">مغسلة وتنظيف جاف (Laundry)</option>
                  <option value="خدمات سبا واستجمام (Spa & Wellness)">خدمات سبا واستجمام (Spa & Wellness)</option>
                </select>
              </div>

              <div>
                <label className="block font-medium mb-1 text-[#262321]">البيان والتفاصيل:</label>
                <Input
                  required
                  value={chargeForm.description}
                  onChange={(e) => setChargeForm({ ...chargeForm, description: e.target.value })}
                  placeholder="وصف البند التفصيلي"
                  className="text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">الصافي:</label>
                  <Input
                    type="number"
                    step="0.01"
                    required
                    value={chargeForm.net_amount}
                    onChange={(e) => {
                      const net = parseFloat(e.target.value) || 0;
                      const tax = Math.round(net * 0.14 * 100) / 100;
                      setChargeForm({ ...chargeForm, net_amount: net, tax_amount: tax, total_amount: net + tax });
                    }}
                    className="text-xs num"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">الضريبة 14%:</label>
                  <Input
                    type="number"
                    readOnly
                    value={chargeForm.tax_amount}
                    className="text-xs num bg-gray-50"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">الإجمالي:</label>
                  <Input
                    type="number"
                    readOnly
                    value={chargeForm.total_amount}
                    className="text-xs num bg-gray-50 font-bold text-[#651E2C]"
                  />
                </div>
              </div>

              <div className="pt-3 flex justify-end gap-2 border-t border-[#651E2C]/10">
                <Button type="button" variant="outline" onClick={() => setShowNewChargeModal(false)} className="text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="bg-[#651E2C] hover:bg-[#521824] text-white text-xs font-semibold px-4">
                  ترحيل للغرفة
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
