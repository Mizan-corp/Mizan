// Client for the Website tab's orders API (/site/orders, app/platform/site/orders.py).
// Site-origin orders are managed here while the records stay in the storefront
// module's tables; the suspended public commerce routes are untouched.
import { SiteApiError, siteRequestHeaders } from "@app/features/studio/sitePages";

export type SiteOrderItem = {
  product_name: string;
  unit_price: number;
  quantity: number;
  total_price: number;
  notes: string | null;
};

export type SiteOrder = {
  id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string | null;
  delivery_type: string;
  delivery_address: string | null;
  table_number: string | null;
  notes: string | null;
  subtotal: number;
  delivery_fee: number;
  discount_amount: number;
  coupon_code: string | null;
  total_amount: number;
  status: string;
  payment_method: string;
  payment_status: string;
  created_at: string | null;
  items: SiteOrderItem[];
};

export type SiteOrdersList = {
  items: SiteOrder[];
  page: number;
  page_size: number;
  statuses: string[];
};

async function request<T>(baseUrl: string, method: string, path: string, body?: unknown): Promise<T> {
  const headers = siteRequestHeaders(baseUrl, method, body !== undefined, typeof document === "undefined" ? "" : document.cookie);
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    credentials: "include",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = "";
    try {
      const data: unknown = await response.json();
      if (data && typeof data === "object" && typeof (data as { detail?: unknown }).detail === "string") {
        detail = (data as { detail: string }).detail;
      }
    } catch { /* non-JSON error body: keep the generic message */ }
    throw new SiteApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function createSiteOrdersClient({ baseUrl }: { baseUrl: string }) {
  return {
    listOrders: () => request<SiteOrdersList>(baseUrl, "GET", "/site/orders"),
    updateStatus: (orderId: string, status: string) =>
      request<{ ok: boolean; status: string; payment_status: string }>(baseUrl, "POST", `/site/orders/${orderId}/status`, { status }),
  };
}
