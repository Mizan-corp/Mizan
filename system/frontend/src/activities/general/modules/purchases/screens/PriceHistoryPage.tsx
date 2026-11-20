// Purchase prices (PUR-4): a product's last 50 purchase costs (each receipt, with its supplier and
// order) and the suppliers' listed prices for it, cheapest first.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { History, X } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { date as fmtDate, money } from "@/lib/format";
import { Empty, ErrorBox } from "@/components/ui";
import type { ProductRow } from "@activities/general/modules/inventory/api";
import { ProductPicker } from "@activities/general/modules/inventory/components/ProductPicker";
import { PurchasePrices } from "@activities/general/modules/inventory/components/ProductDetail";
import { PurchasesHeader } from "../components/PurchasesHeader";

interface SupplierPrice { id: string; supplier_name: string; price: string; currency: string; min_qty: string; last_purchase_date: string | null; notes: string | null }

export default function PriceHistoryPage() {
  const [product, setProduct] = useState<ProductRow | null>(null);
  return (
    <div className="flex flex-col gap-6">
      <PurchasesHeader title="سجل أسعار الشراء" subtitle="تكلفة الصنف في كل استلام، وأسعار الموردين المسجلة له" />
      {product ? (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-line bg-card px-4 py-3">
          <span className="font-bold">{product.name}</span>
          <button type="button" className="flex items-center gap-1 text-xs text-primary" onClick={() => setProduct(null)}>
            <X className="size-3.5" /> صنف آخر
          </button>
        </div>
      ) : (
        <div className="max-w-xl"><ProductPicker onPick={setProduct} /></div>
      )}
      {!product ? (
        <Empty text="اختر صنفاً" hint="ابحث بالاسم أو الكود أو الباركود لترى تكاليف شرائه." icon={<History className="size-10" />} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <section className="flex flex-col gap-3 lg:col-span-2">
            <h2 className="text-base font-bold">تكلفة كل استلام</h2>
            <PurchasePrices productId={product.id} />
          </section>
          <section className="flex flex-col gap-3">
            <h2 className="text-base font-bold">أسعار الموردين</h2>
            <SupplierPrices productId={product.id} />
          </section>
        </div>
      )}
    </div>
  );
}

function SupplierPrices({ productId }: { productId: string }) {
  const q = useQuery({
    queryKey: ["purchases", "supplier-prices", productId],
    queryFn: () => api.get<{ suppliers: SupplierPrice[] }>(`/purchases/supplier-prices/product/${productId}`),
  });
  if (q.isLoading) return <Skeleton className="h-24 w-full" />;
  if (q.isError) return <ErrorBox message={(q.error as Error).message} onRetry={() => q.refetch()} />;
  if (!q.data?.suppliers.length) return <Empty text="لا أسعار مسجلة للموردين" hint="تُسجَّل من شاشة الموردين." />;
  return (
    <ul className="divide-y divide-line/60 rounded-xl border border-line bg-card text-sm">
      {q.data.suppliers.map((s, i) => (
        <li key={s.id} className="flex items-center justify-between gap-2 px-3 py-2">
          <span className="min-w-0">
            <span className="block truncate font-semibold">{s.supplier_name}{i === 0 && <span className="ms-2 text-[10px] text-success">الأرخص</span>}</span>
            {s.last_purchase_date && <span className="text-[11px] text-muted">آخر شراء {fmtDate(s.last_purchase_date)}</span>}
          </span>
          <span className="num font-bold">{money(s.price)}</span>
        </li>
      ))}
    </ul>
  );
}
