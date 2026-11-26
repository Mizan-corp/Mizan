/**
 * Website tab orders section (user decision 2026-11-25 17:33): site-origin orders are
 * managed from the Website module instead of the suspended storefront module. The
 * records stay in the storefront tables; this is a read/lifecycle surface over
 * /site/orders. No public commerce route is revived by this panel.
 */
import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ListState } from "@/components/app/shared";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/kit/table";
import { createSiteOrdersClient, type SiteOrder } from "./siteOrders";

const STATUS_LABELS: Record<string, string> = {
  pending: "جديد",
  confirmed: "مؤكد",
  preparing: "بيتحضّر",
  out_for_delivery: "في الطريق",
  completed: "مكتمل",
  cancelled: "ملغي",
};

const PAYMENT_LABELS: Record<string, string> = {
  cod: "عند الاستلام",
  fawry: "فوري",
  instapay: "إنستاباي",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function orderDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" });
}

function money(amount: number): string {
  return `${amount.toLocaleString("ar-EG", { maximumFractionDigits: 2 })} ج.م`;
}

export default function WebsiteOrders({ apiBase }: { apiBase: string }) {
  const [orders, setOrders] = useState<SiteOrder[] | null>(null);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [savingId, setSavingId] = useState<string | null>(null);
  const api = createSiteOrdersClient({ baseUrl: apiBase });

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const out = await api.listOrders();
      setOrders(out.items);
      setStatuses(out.statuses);
      setStatus("ready");
    } catch {
      setOrders(null);
      setStatus("error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  useEffect(() => {
    void load();
  }, [load]);

  const changeStatus = async (order: SiteOrder, next: string) => {
    if (next === order.status) return;
    setSavingId(order.id);
    try {
      const out = await api.updateStatus(order.id, next);
      setOrders((prev) =>
        (prev ?? []).map((o) =>
          o.id === order.id ? { ...o, status: out.status, payment_status: out.payment_status } : o,
        ),
      );
    } catch {
      // Keep the visible value; the next refresh reconciles.
    } finally {
      setSavingId(null);
    }
  };

  return (
    <section aria-label="طلبات الموقع" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">الطلبات</h2>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => void load()}
          disabled={status === "loading"}
        >
          <RefreshCw data-icon="inline-start" />
          تحديث
        </Button>
      </div>
      <ListState
        status={status}
        isEmpty={status === "ready" && !orders?.length}
        onRetry={() => void load()}
        emptyTitle="لسه مفيش طلبات"
        emptyDescription="أول ما عميل يطلب من الموقع، الطلب هيظهر هنا."
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>الطلب</TableHead>
              <TableHead>العميل</TableHead>
              <TableHead>الإجمالي</TableHead>
              <TableHead>الدفع</TableHead>
              <TableHead>التاريخ</TableHead>
              <TableHead className="text-end">الحالة</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(orders ?? []).map((o) => (
              <TableRow key={o.id}>
                <TableCell className="font-medium" dir="ltr">
                  {o.order_number}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span>{o.customer_name}</span>
                    <span className="text-muted-foreground text-sm" dir="ltr">
                      {o.customer_phone}
                    </span>
                  </div>
                </TableCell>
                <TableCell>{money(o.total_amount)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span>{PAYMENT_LABELS[o.payment_method] ?? o.payment_method}</span>
                    <Badge variant={o.payment_status === "paid" ? "default" : "secondary"}>
                      {o.payment_status === "paid" ? "مدفوع" : "غير مدفوع"}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell>{orderDate(o.created_at)}</TableCell>
                <TableCell className="text-end">
                  <select
                    aria-label={`حالة الطلب ${o.order_number}`}
                    className="website-order-status"
                    value={o.status}
                    disabled={savingId === o.id}
                    onChange={(e) => void changeStatus(o, e.target.value)}
                  >
                    {statuses.map((s) => (
                      <option key={s} value={s}>
                        {statusLabel(s)}
                      </option>
                    ))}
                  </select>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ListState>
    </section>
  );
}
