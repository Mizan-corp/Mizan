// Find a product by name, code or barcode (the server searches; at most 8 shown) and pick it.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { Input, Spinner } from "@/components/ui";
import type { Paged, ProductRow } from "../api";

export function ProductPicker({ id, onPick, placeholder = "ابحث عن صنف بالاسم أو الكود أو الباركود…", exclude = [], showCost = false }: {
  id?: string; onPick: (p: ProductRow) => void; placeholder?: string; exclude?: string[]; showCost?: boolean;
}) {
  const [typed, setTyped] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(typed.trim()), 250);
    return () => clearTimeout(t);
  }, [typed]);
  const found = useQuery({
    queryKey: ["product-picker", q],
    queryFn: () => api.get<Paged<ProductRow>>("/products", { search: q, page: 1, page_size: 8 }),
    enabled: q.length > 1,
  });
  const rows = (found.data?.items ?? []).filter((p) => !exclude.includes(p.id));
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute start-3 top-1/2 size-3.5 -translate-y-1/2 text-muted" aria-hidden />
      <Input id={id} className="ps-9" placeholder={placeholder} value={typed} onChange={(e) => setTyped(e.target.value)}
             aria-label="بحث عن صنف" autoComplete="off" />
      {q.length > 1 && (
        <div className="mt-1 grid gap-0.5 rounded-lg border border-line bg-card p-1 shadow-sm">
          {found.isLoading ? (
            <div className="grid place-items-center p-2"><Spinner /></div>
          ) : found.isError ? (
            <p className="p-2 text-xs text-destructive">{(found.error as Error).message}</p>
          ) : !rows.length ? (
            <p className="p-2 text-xs text-muted">لا يوجد صنف يطابق «{q}»</p>
          ) : rows.map((p) => (
            <button key={p.id} type="button"
                    className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-start text-sm hover:bg-elevated"
                    onClick={() => { onPick(p); setTyped(""); setQ(""); }}>
              <span className="min-w-0 truncate font-semibold">{p.name}</span>
              <span className="num shrink-0 text-xs text-muted" dir="ltr">
                {p.code ?? p.barcode ?? ""}{showCost && p.cost_price != null ? ` · ${money(p.cost_price)}` : ""}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
