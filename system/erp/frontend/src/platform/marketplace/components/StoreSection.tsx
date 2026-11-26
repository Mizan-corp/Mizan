/**
 * The store in the module centre (ADR-007 milestone 2, #105): developers' modules and themes the
 * Mizan team reviewed. Installing one shows the same review as installing from a file.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Blocks, Download, Palette, Search, Store } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { Badge } from "@/components/kit/badge";
import { Button, Empty, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { PackageReview, type Summary } from "@app/platform/community/components/CommunityModules";
import { Preview } from "@app/platform/themes/components/ThemesSection";

type Kind = "community" | "theme";

interface Listing {
  id: string; kind: Kind; name: string; name_en: string | null; description: string | null;
  version: string; installs: number; developer: string; installed_version: string | null;
}

interface ThemeDetail {
  id: string; name: string; description: string; version: string; developer: string;
  swatches: string[]; radius?: string; fonts: { body?: string; display?: string }; installed_version: string | null;
}

const FILTERS: [Kind | "", string][] = [["", "الكل"], ["community", "وحدات"], ["theme", "مظاهر"]];

/** "تثبيت واحد", "تثبيتان", "3 تثبيتات", "11 تثبيتًا". */
function installsText(n: number): string {
  if (n === 0) return "جديد";
  if (n === 1) return "تثبيت واحد";
  if (n === 2) return "تثبيتان";
  if (n % 100 >= 3 && n % 100 <= 10) return `${n} تثبيتات`;
  return `${n} تثبيتًا`;
}

function StoreItem({ id, onClose }: { id: string; onClose: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [agreed, setAgreed] = useState(false);
  const q = useQuery({
    queryKey: ["store-item", id],
    queryFn: () => api.get<{ item: Listing; detail: Summary | ThemeDetail }>(`/modules/store/${encodeURIComponent(id)}`),
  });
  const install = useMutation({
    mutationFn: (scopes: string[]) => api.post(`/modules/store/${encodeURIComponent(id)}/install`, { approved_scopes: scopes }),
    onSuccess: () => {
      const it = q.data!.item;
      toast("success", it.kind === "theme" ? `ثُبّت «${it.name}»؛ اختره من قسم المظاهر` : `تم تثبيت «${it.name}»`);
      qc.invalidateQueries();
      onClose();
    },
    onError: (e) => toast("error", e instanceof ApiError ? e.message : "تعذر التثبيت"),
  });

  const item = q.data?.item;
  const updating = !!item?.installed_version && item.installed_version !== item.version;
  const upToDate = !!item?.installed_version && item.installed_version === item.version;
  return (
    <Modal open onClose={onClose} title={item ? (updating ? `تحديث «${item.name}»` : `«${item.name}»`) : "…"}>
      {q.isPending && <div className="flex justify-center p-8"><Spinner /></div>}
      {q.isError && <ErrorBox message={q.error instanceof ApiError ? q.error.message : "تعذر تحميل الإضافة"} onRetry={() => q.refetch()} />}
      {item && q.data && (
        <div className="space-y-4 text-sm">
          {item.kind === "theme" ? (
            (() => {
              const t = q.data.detail as ThemeDetail;
              return (
                <>
                  <div className="overflow-hidden rounded-xl border border-line"><Preview swatches={t.swatches} radius={t.radius} /></div>
                  <p className="text-muted-foreground">
                    المطور <span className="code" dir="ltr">{t.developer}</span> · <span className="code" dir="ltr">v{t.version}</span>
                    {t.fonts.body && <> · الخط {t.fonts.body}</>}
                  </p>
                  {t.description && <p>{t.description}</p>}
                  <p className="text-xs text-muted-foreground">المظهر لا يصل إلى أي من بياناتك. التثبيت لا يغيّر مظهرك حتى تختاره.</p>
                </>
              );
            })()
          ) : (
            <PackageReview summary={q.data.detail as Summary} agreed={agreed} onAgree={setAgreed} />
          )}
          <div className="flex gap-2">
            <Button
              disabled={upToDate || install.isPending || (item.kind === "community" && !agreed)}
              onClick={() => install.mutate(item.kind === "community" ? (q.data!.detail as Summary).scopes.map((s) => s.id) : [])}
            >
              {install.isPending ? <Spinner /> : <Download />} {upToDate ? "مثبّت" : updating ? "تحديث" : "تثبيت"}
            </Button>
            <Button variant="outline" onClick={onClose}>إغلاق</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

export function StoreSection() {
  const can = useAuth((s) => s.can);
  const [kind, setKind] = useState<Kind | "">("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const allowed = can("community.manage") || can("themes.manage");
  const list = useQuery({
    queryKey: ["store", kind, q.trim()],
    queryFn: () => api.get<{ items: Listing[] }>("/modules/store", { kind: kind || undefined, q: q.trim() || undefined }),
    enabled: allowed,
  });
  if (!allowed) return null;
  const items = list.data?.items ?? [];

  return (
    <section className="flex flex-col gap-3" aria-label="المتجر">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-1.5 text-sm font-bold text-foreground"><Store className="size-4 text-primary" /> المتجر</h2>
          <p className="text-xs text-muted-foreground">وحدات ومظاهر من مطورين، راجعها فريق ميزان قبل نشرها.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-line p-0.5" role="radiogroup" aria-label="النوع">
            {FILTERS.map(([v, label]) => (
              <button key={v || "all"} role="radio" aria-checked={kind === v} onClick={() => setKind(v)}
                      className={`h-7 rounded-md px-3 text-xs font-semibold ${kind === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}>
                {label}
              </button>
            ))}
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute start-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ابحث في المتجر" aria-label="ابحث في المتجر" className="h-8 w-48 ps-8 text-xs" />
          </div>
        </div>
      </div>

      {list.isPending ? (
        <div className="flex justify-center p-6"><Spinner /></div>
      ) : list.isError ? (
        <ErrorBox message="تعذر تحميل المتجر" onRetry={() => list.refetch()} />
      ) : !items.length ? (
        <Empty text={q.trim() ? "لم يتم العثور على نتائج تطابق بحثك" : "لا توجد إضافات في المتجر بعد"}
               hint={q.trim() ? undefined : "تظهر هنا وحدات ومظاهر المطورين بعد مراجعتها."} icon={<Store className="size-6" />} />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((it) => {
            const Icon = it.kind === "theme" ? Palette : Blocks;
            const update = it.installed_version && it.installed_version !== it.version;
            return (
              <li key={it.id}>
                <button onClick={() => setOpen(it.id)}
                        className="flex h-full w-full flex-col gap-2 rounded-xl border border-line bg-card p-3 text-start transition-colors hover:border-primary/50 focus-visible:outline-2 focus-visible:outline-primary">
                  <span className="flex items-start justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2">
                      <Icon className="size-4 shrink-0 text-primary" />
                      <span className="truncate text-sm font-bold text-foreground">{it.name}</span>
                    </span>
                    {update ? <Badge variant="warning">تحديث متاح</Badge> : it.installed_version ? <Badge variant="success">مثبّت</Badge> : null}
                  </span>
                  {it.description && <span className="line-clamp-2 text-xs text-muted-foreground">{it.description}</span>}
                  <span className="mt-auto text-[11px] text-muted-foreground">
                    <span className="code" dir="ltr">{it.developer}</span> · <span className="code" dir="ltr">v{it.version}</span> · {installsText(it.installs)} · مجاني
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {open && <StoreItem id={open} onClose={() => setOpen(null)} />}
    </section>
  );
}
