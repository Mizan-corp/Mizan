/**
 * Website tab published-products summary (user decision 2026-11-25 17:33): the
 * Website tab shows which products are published to the site and under which
 * website attributes. Read-only by design: Inventory stays the product/stock
 * source of truth and the consent/policy edits stay in the settings section
 * below (no duplicated catalog).
 */
import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ListState } from "@/components/app/shared";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";

type CardsPolicy = {
  products: string[];
  show_price: boolean;
  show_image: boolean;
  show_description: boolean;
  currency: string | null;
};

type Choices = {
  products: { items: { id: string; name: string }[]; truncated: boolean };
};

async function getJson<T>(apiBase: string, path: string): Promise<T> {
  const res = await fetch(`${apiBase}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(`request failed: ${res.status}`);
  return (await res.json()) as T;
}

export default function WebsitePublishedProducts({ apiBase }: { apiBase: string }) {
  const [policy, setPolicy] = useState<CardsPolicy | null>(null);
  const [names, setNames] = useState<Map<string, string>>(new Map());
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const [cards, choices] = await Promise.all([
        getJson<{ value: CardsPolicy }>(apiBase, "/site/module-settings/inventory/cards"),
        getJson<Choices>(apiBase, "/site/module-settings/inventory/choices"),
      ]);
      setPolicy(cards.value);
      setNames(new Map(choices.products.items.map((p) => [p.id, p.name])));
      setStatus("ready");
    } catch {
      setPolicy(null);
      setStatus("error");
    }
  }, [apiBase]);

  useEffect(() => {
    void load();
  }, [load]);

  const published = policy?.products ?? [];

  return (
    <section aria-label="المنتجات المنشورة على الموقع" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">المنتجات المنشورة على الموقع</h2>
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
        isEmpty={status === "ready" && published.length === 0}
        onRetry={() => void load()}
        emptyTitle="لسه مفيش منتجات منشورة"
        emptyDescription="اختار المنتجات اللي تظهر على الموقع من إعدادات بيانات الموقع تحت."
      >
        {policy && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default">{published.length} منتج</Badge>
              <Badge variant={policy.show_price ? "default" : "secondary"}>
                {policy.show_price ? "السعر ظاهر" : "السعر مخفي"}
              </Badge>
              <Badge variant={policy.show_image ? "default" : "secondary"}>
                {policy.show_image ? "الصورة ظاهرة" : "الصورة مخفية"}
              </Badge>
              <Badge variant={policy.show_description ? "default" : "secondary"}>
                {policy.show_description ? "الوصف ظاهر" : "الوصف مخفي"}
              </Badge>
              {policy.currency && <Badge variant="secondary">{policy.currency}</Badge>}
            </div>
            <ul className="website-published-products">
              {published.map((id) => (
                <li key={id}>{names.get(id) ?? id}</li>
              ))}
            </ul>
          </div>
        )}
      </ListState>
    </section>
  );
}
