/**
 * PAGE CONTRACT
 * Page: شاشة المطبخ ونظام إدارة الطلبات التفاعلي (KDS) (/restaurant/kitchen)
 * Archetype: High-Contrast Kitchen Display System with Tactile Bump Bar
 * User: الشيف العمومي، طهاة المحطات (شواية، فرن، تجهيز)، ومساعدي المطبخ
 * Purpose: عرض تذاكر الطهي الحية فور صدورها من الكاشير أو الطاولات مع عدادات الوقت ومحطات العمل
 */
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ChefHat,
  Clock,
  CheckCircle2,
  Flame,
  Volume2,
  VolumeX,
  Maximize2,
  Minimize2,
  RotateCcw,
  LayoutGrid,
} from "lucide-react";
import { Button } from "@/components/kit/button";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { sound } from "@/lib/sound";
import { useToast } from "@/components/ui";

interface KitchenOrderItem {
  name: string;
  qty: number;
  notes?: string;
}

interface KDSTicket {
  id: string;
  order_number: string;
  table: string;
  waiter: string;
  status: "pending" | "cooking" | "ready";
  elapsed_minutes: number;
  items: KitchenOrderItem[];
}

export default function KitchenDisplayPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [activeTab, setActiveTab] = useState<"active" | "completed">("active");

  // Fetch live kitchen tickets with auto-polling every 10 seconds
  const { data: tickets = [], isLoading, refetch } = useQuery<KDSTicket[]>({
    queryKey: ["kds_live_tickets"],
    queryFn: async () => {
      try {
        const res = await api.get<KDSTicket[]>("/kitchen-orders");
        return res || [];
      } catch {
        const fallback = await api.get<KDSTicket[]>("/modules/restaurant/kitchen-orders");
        return fallback || [];
      }
    },
    refetchInterval: 10000,
  });

  // Toggle fullscreen mode for kitchen monitors
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  // Mutation to bump / update ticket status
  const bumpTicketMutation = useMutation({
    mutationFn: async ({ id, newStatus }: { id: string; newStatus: "cooking" | "ready" | "served" }) => {
      try {
        return await api.post(`/kitchen-orders/${id}/status`, { status: newStatus });
      } catch {
        return await api.post(`/modules/restaurant/kitchen-orders/${id}/status`, { status: newStatus });
      }
    },
    onSuccess: (_, { newStatus }) => {
      if (soundEnabled) {
        sound.success();
      }
      toast(
        "success",
        newStatus === "cooking"
          ? "بدأ تحضير التذكرة في محطة الطهي"
          : newStatus === "ready"
          ? "تم إنجاز الطلب وهو جاهز للتقديم للعميل!"
          : "تم تسليم الطلب للصالون"
      );
      queryClient.invalidateQueries({ queryKey: ["kds_live_tickets"] });
      queryClient.invalidateQueries({ queryKey: ["restaurant-kds"] });
    },
    onError: () => {
      if (soundEnabled) sound.error();
      toast("error", "تعذر تحديث حالة التذكرة");
    },
  });

  const activeTickets = tickets.filter((t) => t.status !== "ready");
  const readyTickets = tickets.filter((t) => t.status === "ready");

  const displayedTickets = activeTab === "active" ? activeTickets : readyTickets;

  // Sound chime when new pending tickets arrive
  useEffect(() => {
    const hasUrgent = activeTickets.some((t) => (t.elapsed_minutes || 0) > 20);
    if (hasUrgent && soundEnabled) {
      sound.error();
    }
  }, [tickets, soundEnabled]);

  return (
    <div
      className="-mx-4 -my-6 md:-mx-6 md:-my-6 lg:-mx-8 p-4 md:p-6 lg:p-8 min-h-[calc(100vh-4rem)] text-[#F3F4F6] flex flex-col gap-6 selection:bg-amber-500/30"
      style={{ backgroundColor: "#101114", color: "#F3F4F6" }}
      dir="rtl"
    >
      {/* ── Top Kitchen Navigation & Controls ── */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[#27272A] pb-4">
        <div className="flex items-center gap-3">
          <div className="size-11 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-md">
            <ChefHat className="size-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl md:text-2xl font-black tracking-tight text-white font-serif">
                شاشة عرض المطبخ الحية (Kitchen Display - KDS)
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">
                مباشر LIVE
              </span>
            </div>
            <p className="text-xs text-[#A1A1AA] mt-0.5">
              إدارة تذاكر محطات الطهي، مراقبة أزمنة الانتظار، والتسليم اللحظي للصالة
            </p>
          </div>
        </div>

        {/* Operational Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Station Filter */}
          <div className="flex items-center rounded-xl bg-[#18181B] border border-[#27272A] p-1 text-xs font-semibold">
            <button
              onClick={() => setActiveTab("active")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === "active"
                  ? "bg-amber-500 text-black font-bold shadow-xs"
                  : "text-[#A1A1AA] hover:text-white"
              }`}
            >
              طلبات قيد التحضير ({activeTickets.length})
            </button>
            <button
              onClick={() => setActiveTab("completed")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === "completed"
                  ? "bg-emerald-600 text-white font-bold shadow-xs"
                  : "text-[#A1A1AA] hover:text-white"
              }`}
            >
              جاهزة للتسليم ({readyTickets.length})
            </button>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setSoundEnabled(!soundEnabled)}
            className="h-9 px-3 bg-[#18181B] border-[#27272A] text-white hover:bg-[#27272A] gap-1.5 text-xs"
          >
            {soundEnabled ? (
              <>
                <Volume2 className="size-4 text-emerald-400" />
                <span className="hidden sm:inline">التنبيهات الصوتية</span>
              </>
            ) : (
              <>
                <VolumeX className="size-4 text-rose-400" />
                <span className="hidden sm:inline">كتم الصوت</span>
              </>
            )}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={toggleFullscreen}
            className="h-9 px-3 bg-[#18181B] border-[#27272A] text-white hover:bg-[#27272A] gap-1.5 text-xs"
          >
            {isFullscreen ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
            <span className="hidden sm:inline">شاشة كاملة</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="h-9 px-3 bg-[#18181B] border-[#27272A] text-white hover:bg-[#27272A] gap-1.5 text-xs"
          >
            <RotateCcw className="size-4" />
            <span className="hidden sm:inline">تحديث</span>
          </Button>

          <Link
            to="/restaurant/tables"
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border border-[#27272A] bg-[#18181B] hover:bg-[#27272A] text-xs font-semibold text-white transition-colors"
          >
            <LayoutGrid className="size-3.5 text-amber-400" />
            <span>خريطة الصالة والطاولات</span>
          </Link>
        </div>
      </header>

      {/* ── Status Banner & Kitchen Workload ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="rounded-xl border border-[#27272A] bg-[#18181B] p-3 flex items-center justify-between">
          <span className="text-[#A1A1AA]">إجمالي التذاكر النشطة:</span>
          <span className="num font-black text-lg text-white">{activeTickets.length}</span>
        </div>
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 flex items-center justify-between">
          <span className="text-amber-400 font-medium">قيد الطهي الآن:</span>
          <span className="num font-black text-lg text-amber-400">
            {activeTickets.filter((t) => t.status === "cooking").length}
          </span>
        </div>
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-3 flex items-center justify-between">
          <span className="text-rose-400 font-medium">متأخر (&gt; 15 دقيقة):</span>
          <span className="num font-black text-lg text-rose-400">
            {activeTickets.filter((t) => (t.elapsed_minutes || 0) > 15).length}
          </span>
        </div>
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 flex items-center justify-between">
          <span className="text-emerald-400 font-medium">جاهز للتقديم للصالة:</span>
          <span className="num font-black text-lg text-emerald-400">{readyTickets.length}</span>
        </div>
      </div>

      {/* ── Ticket Grid (The Heart of KDS) ── */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-64 rounded-2xl bg-[#1C1C1F]" />
          ))}
        </div>
      ) : displayedTickets.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 text-center border-2 border-dashed border-[#27272A] rounded-2xl bg-[#18181B]/50">
          <div className="size-16 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400 mb-3">
            <CheckCircle2 className="size-8" />
          </div>
          <h2 className="text-lg font-bold text-white">المطبخ هادئ — لا توجد تذاكر معلقة حالياً</h2>
          <p className="text-xs text-[#A1A1AA] mt-1 max-w-sm">
            كافة الطلبات تم طهيها وتسليمها لخدمة الصالة والتيك أواي بنجاح تام.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {displayedTickets.map((ticket) => {
            const isCooking = ticket.status === "cooking";
            const isReady = ticket.status === "ready";
            const elapsed = ticket.elapsed_minutes || 0;
            const isOverdue = elapsed > 15;
            const isCriticallyLate = elapsed > 25;

            return (
              <div
                key={ticket.id}
                style={{
                  backgroundColor: isReady
                    ? "#141C16"
                    : isCriticallyLate
                    ? "#261315"
                    : isOverdue
                    ? "#241812"
                    : "#18191E",
                  borderColor: isReady
                    ? "rgba(16, 185, 129, 0.4)"
                    : isCriticallyLate
                    ? "rgba(244, 63, 94, 0.6)"
                    : isOverdue
                    ? "rgba(245, 158, 11, 0.5)"
                    : "#2E3038",
                }}
                className={`rounded-2xl border transition-all flex flex-col justify-between overflow-hidden relative shadow-xl ${
                  isCriticallyLate ? "ring-1 ring-rose-500/50" : ""
                }`}
              >
                {/* Header Ticket Bar */}
                <div
                  className={`p-3.5 border-b flex items-center justify-between ${
                    isReady
                      ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
                      : isCriticallyLate
                      ? "bg-rose-950/60 border-rose-500/40 text-rose-300"
                      : isOverdue
                      ? "bg-amber-950/60 border-amber-500/40 text-amber-300"
                      : "bg-[#222226] border-[#2E2E33] text-white"
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-base font-black tracking-wider text-white">
                        {ticket.order_number}
                      </span>
                      <span className="font-bold text-xs px-2 py-0.5 rounded-md bg-black/40 border border-white/10">
                        {ticket.table}
                      </span>
                    </div>
                    <span className="text-[11px] text-[#A1A1AA] mt-0.5 block">الويتر: {ticket.waiter || "كاشير"}</span>
                  </div>

                  {/* Elapsed Timer Gauge */}
                  <div className="flex items-center gap-1.5 text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-black/50 border border-white/10">
                    <Clock
                      className={`size-3.5 ${
                        isCriticallyLate
                          ? "text-rose-400 animate-spin"
                          : isOverdue
                          ? "text-amber-400"
                          : "text-emerald-400"
                      }`}
                    />
                    <span
                      className={
                        isCriticallyLate
                          ? "text-rose-400 font-black text-sm"
                          : isOverdue
                          ? "text-amber-400"
                          : "text-white"
                      }
                    >
                      {elapsed} د
                    </span>
                  </div>
                </div>

                {/* Items Checklist */}
                <div className="p-4 space-y-3 flex-1 overflow-y-auto max-h-72 divide-y divide-[#27272A]">
                  {ticket.items.map((item, idx) => (
                    <div key={idx} className="pt-2 first:pt-0 flex items-start gap-3">
                      <span className="num size-7 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center justify-center font-bold text-sm shrink-0">
                        {item.qty}×
                      </span>
                      <div className="flex-1">
                        <p className="font-bold text-sm text-white leading-snug">{item.name}</p>
                        {item.notes && (
                          <p className="text-[11px] font-medium text-amber-300/90 bg-amber-500/10 px-2 py-0.5 rounded mt-1 border border-amber-500/20 inline-block">
                            ⚠️ {item.notes}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Bump Bar Action Buttons */}
                <div className="p-3 bg-[#141416] border-t border-[#27272A] flex items-center gap-2">
                  {!isCooking && !isReady && (
                    <Button
                      onClick={() =>
                        bumpTicketMutation.mutate({
                          id: ticket.id,
                          newStatus: "cooking",
                        })
                      }
                      disabled={bumpTicketMutation.isPending}
                      className="flex-1 h-10 bg-amber-600 hover:bg-amber-500 text-black font-bold text-xs gap-1.5 rounded-xl shadow-md"
                    >
                      <Flame className="size-4" />
                      بدء الطهي الآن
                    </Button>
                  )}

                  {isCooking && (
                    <Button
                      onClick={() =>
                        bumpTicketMutation.mutate({
                          id: ticket.id,
                          newStatus: "ready",
                        })
                      }
                      disabled={bumpTicketMutation.isPending}
                      className="flex-1 h-11 bg-emerald-600 hover:bg-emerald-500 text-white font-black text-sm gap-2 rounded-xl shadow-lg"
                    >
                      <CheckCircle2 className="size-5" />
                      تم الطهي — جاهز للتقديم!
                    </Button>
                  )}

                  {isReady && (
                    <Button
                      onClick={() =>
                        bumpTicketMutation.mutate({
                          id: ticket.id,
                          newStatus: "served",
                        })
                      }
                      disabled={bumpTicketMutation.isPending}
                      className="flex-1 h-10 bg-[#27272A] hover:bg-[#3F3F46] text-white font-bold text-xs gap-1.5 rounded-xl border border-white/10"
                    >
                      <CheckCircle2 className="size-4 text-emerald-400" />
                      تسليم الطلب (أرشفة)
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
