import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { Button } from "@/components/kit/button";
import { Input } from "@/components/kit/input";

export default function HousekeepingView() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [showNewTaskModal, setShowNewTaskModal] = useState(false);
  const [taskForm, setTaskForm] = useState({
    room_number: "",
    task_type: "تنظيف مغادرة (Checkout Clean)",
    priority: "normal",
    assigned_to: "فريق الإشراف الداخلي A",
    notes: "",
  });

  const { data: tasks = [] } = useQuery<any[]>({
    queryKey: ["housekeeping_tasks"],
    queryFn: async () => {
      try {
        const res = await api.get<any[]>("/hospitality/housekeeping/tasks");
        return res || [];
      } catch {
        const fallback = await api.get<any[]>("/hospitality/housekeeping");
        return fallback || [];
      }
    },
  });

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      try {
        await api.post("/hospitality/housekeeping/tasks", taskForm);
      } catch {
        await api.post("/hospitality/housekeeping", taskForm);
      }
      toast("success", "تم إنشاء أمر التدبير المنزلي بنجاح");
      setShowNewTaskModal(false);
      setTaskForm({
        room_number: "",
        task_type: "تنظيف مغادرة (Checkout Clean)",
        priority: "normal",
        assigned_to: "فريق الإشراف الداخلي A",
        notes: "",
      });
      queryClient.invalidateQueries({ queryKey: ["housekeeping_tasks"] });
    } catch (err: any) {
      toast("error", `فشل إنشاء المهمة: ${err.message || ""}`);
    }
  };

  const handleCompleteTask = async (taskId: string) => {
    try {
      try {
        await api.post(`/hospitality/housekeeping/tasks/${taskId}/complete`, { notes: "تم الفحص والتعقيم" });
      } catch {
        await api.post(`/hospitality/housekeeping/${taskId}/complete`, { notes: "تم الفحص والتعقيم" });
      }
      toast("success", "تم تأكيد تنظيف الغرفة وإعادتها لحالة شاغرة ونظيفة");
      queryClient.invalidateQueries({ queryKey: ["housekeeping_tasks"] });
      queryClient.invalidateQueries({ queryKey: ["hotel_pms_rooms"] });
    } catch (err: any) {
      toast("error", `فشل إتمام المهمة: ${err.message || ""}`);
    }
  };

  const filteredTasks = tasks.filter((t) => {
    if (filterStatus !== "all" && t.status !== filterStatus) return false;
    return true;
  });

  return (
    <div className="space-y-6 text-[#262321]" dir="rtl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-l from-[#651E2C]/5 via-[#FAF6F0] to-[#FAF6F0] border border-[#651E2C]/15 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[#651E2C] text-[#FAF6F0] flex items-center justify-center shadow-md">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold font-serif text-[#262321]">التدبير المنزلي ونظافة الغرف (Housekeeping)</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[#651E2C]/10 text-[#651E2C] font-mono font-bold">HOT-HK</span>
            </div>
            <p className="text-xs text-[#262321]/70 mt-0.5">جدولة وتنفيذ مهام النظافة والتعقيم، تسليم الغرف الجاهزة، ومتابعة فرق العمل</p>
          </div>
        </div>

        <Button
          onClick={() => setShowNewTaskModal(true)}
          className="bg-[#651E2C] hover:bg-[#521824] text-[#FAF6F0] text-xs font-semibold px-4 py-2 rounded-xl shadow transition"
        >
          <Plus className="w-4 h-4 ml-1.5" />
          أمر تنظيف جديد
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between gap-3 p-3 bg-[#FAF6F0] rounded-xl border border-[#651E2C]/10 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[#262321]/70">تصفية المهام:</span>
          {["all", "pending", "in_progress", "completed"].map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-3 py-1 rounded-lg transition font-medium ${
                filterStatus === st
                  ? "bg-[#651E2C] text-[#FAF6F0] shadow-xs"
                  : "bg-white text-[#262321]/80 hover:bg-[#651E2C]/5 border border-[#651E2C]/10"
              }`}
            >
              {st === "all" ? "جميع المهام" : st === "pending" ? "قيد الانتظار" : st === "in_progress" ? "جاري العمل" : "مكتملة"}
            </button>
          ))}
        </div>
        <div className="text-xs text-[#262321]/60 font-medium">
          إجمالي المهام: <span className="num font-bold text-[#651E2C]">{filteredTasks.length}</span>
        </div>
      </div>

      {/* Task Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredTasks.map((t) => (
          <div
            key={t.id}
            className={`p-4 rounded-xl border transition-all duration-200 bg-white hover:shadow-md ${
              t.status === "completed"
                ? "border-emerald-200 bg-emerald-50/10"
                : t.priority === "urgent"
                ? "border-rose-300 bg-rose-50/20"
                : "border-[#651E2C]/10"
            }`}
          >
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-md bg-[#651E2C]/10 text-[#651E2C]">
                  غرفة {t.room_number}
                </span>
                <h4 className="text-sm font-bold text-[#262321] mt-1.5">{t.task_type}</h4>
              </div>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  t.priority === "urgent"
                    ? "bg-rose-100 text-rose-800 border border-rose-300"
                    : t.priority === "high"
                    ? "bg-amber-100 text-amber-800"
                    : "bg-gray-100 text-gray-700"
                }`}
              >
                {t.priority === "urgent" ? "عاجل جداً" : t.priority === "high" ? "أولوية مرتفعة" : "عادي"}
              </span>
            </div>

            <div className="mt-3 text-xs text-[#262321]/70 space-y-1">
              <div className="flex justify-between">
                <span>المسؤول المكلف:</span>
                <span className="font-semibold text-[#262321]">{t.assigned_to}</span>
              </div>
              {t.notes && (
                <div className="text-[11px] text-[#262321]/60 bg-[#FAF6F0] p-1.5 rounded-lg border border-[#651E2C]/5">
                  {t.notes}
                </div>
              )}
            </div>

            <div className="mt-4 pt-2.5 border-t border-[#651E2C]/10 flex items-center justify-between">
              <span
                className={`text-[11px] font-semibold ${
                  t.status === "completed" ? "text-emerald-700" : "text-amber-700"
                }`}
              >
                {t.status === "completed" ? "تم الإنجاز والتعقيم" : "قيد المعالجة"}
              </span>

              {t.status !== "completed" && (
                <Button
                  size="sm"
                  onClick={() => handleCompleteTask(t.id)}
                  className="bg-emerald-700 hover:bg-emerald-800 text-white text-xs py-1 px-2.5 h-auto rounded-lg"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 ml-1" />
                  اكتمال التنظيف
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Modal: New Housekeeping Task */}
      {showNewTaskModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-[#651E2C]/20 shadow-2xl max-w-md w-full p-6 text-right space-y-4">
            <div className="flex items-center justify-between border-b border-[#651E2C]/10 pb-3">
              <h3 className="font-bold font-serif text-lg text-[#262321]">تكليف مهمة تنظيف جديدة</h3>
              <button onClick={() => setShowNewTaskModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium mb-1 text-[#262321]">رقم الغرفة:</label>
                <Input
                  required
                  value={taskForm.room_number}
                  onChange={(e) => setTaskForm({ ...taskForm, room_number: e.target.value })}
                  placeholder="مثال: 204"
                  className="text-xs font-mono font-bold"
                />
              </div>

              <div>
                <label className="block font-medium mb-1 text-[#262321]">نوع المهمة:</label>
                <select
                  value={taskForm.task_type}
                  onChange={(e) => setTaskForm({ ...taskForm, task_type: e.target.value })}
                  className="w-full text-xs p-2 rounded-lg border border-[#651E2C]/20 bg-white"
                >
                  <option value="تنظيف مغادرة (Checkout Clean)">تنظيف مغادرة كامل وتغيير مفارش (Checkout Clean)</option>
                  <option value="تنظيف يومي (Stayover Clean)">تنظيف دوري أثناء الإقامة (Stayover Clean)</option>
                  <option value="تنظيف عميق وتعقيم (Deep Clean)">تنظيف عميق وتعقيم شامل (Deep Clean)</option>
                  <option value="فحص جودة وتجهيز VIP">فحص جودة وتجهيز VIP</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">الأولوية:</label>
                  <select
                    value={taskForm.priority}
                    onChange={(e) => setTaskForm({ ...taskForm, priority: e.target.value })}
                    className="w-full text-xs p-2 rounded-lg border border-[#651E2C]/20 bg-white"
                  >
                    <option value="urgent">عاجل جداً (نزيل قادم)</option>
                    <option value="high">مرتفعة</option>
                    <option value="normal">عادية</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium mb-1 text-[#262321]">المسؤول المكلف:</label>
                  <Input
                    required
                    value={taskForm.assigned_to}
                    onChange={(e) => setTaskForm({ ...taskForm, assigned_to: e.target.value })}
                    placeholder="اسم الموظف أو الفريق"
                    className="text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium mb-1 text-[#262321]">ملاحظات إضافية:</label>
                <Input
                  value={taskForm.notes}
                  onChange={(e) => setTaskForm({ ...taskForm, notes: e.target.value })}
                  placeholder="مثال: تزويد المناشف الإضافية وفحص الميني بار"
                  className="text-xs"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2 border-t border-[#651E2C]/10">
                <Button type="button" variant="outline" onClick={() => setShowNewTaskModal(false)} className="text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="bg-[#651E2C] hover:bg-[#521824] text-white text-xs font-semibold px-4">
                  إرسال التكليف
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
