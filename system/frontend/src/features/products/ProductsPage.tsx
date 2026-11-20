/**
 * PAGE CONTRACT
 * Page: الأصناف (/products)
 * User: أمين مخزن أو مدير يدير الكتالوج (إضافة/تعديل/إيقاف صنف، باركودات، صورة، سجل الحركة)
 * Outcome: العثور على صنف وفتح بطاقته، أو إضافة صنف جديد
 * Primary information: الاسم، الكود، التصنيف، أسعار التجزئة/الجملة، الرصيد، حالة النشاط
 * Primary action (per state): populated → فتح بطاقة الصنف (الصف)؛ filtered-empty → «مسح البحث»؛ first-empty → «منتج جديد»؛ error → «إعادة المحاولة»
 * Secondary action: «صنف جديد» دائمًا في رأس الصفحة؛ عرض الأصناف الموقوفة
 * Required states: loading (skeleton), error (retry), filtered-empty (reset), first-use-empty, populated
 * Responsive: 1440 جدول كامل؛ 768 إخفاء الجملة/الشركة؛ 390 كود + اسم مقصوص + تجزئة + حالة
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { money, qty as fq } from "@/lib/format";
import { Button, Empty, ErrorBox, Modal, Select, Spinner, Input, useToast } from "@/components/ui";
import { SearchField, TablePagination, TableShell } from "@/components/app/shared";
import { Badge as KitBadge } from "@/components/kit/badge";
import { Skeleton } from "@/components/kit/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { RecordFormFields, cleanExtra, missingRequired, useRecordForm, type ExtraValues } from "@app/framework/forms";
import { useVat, type TaxCode } from "@app/lib/vat";
import { type ProductRow, useCategories, useSubcategories } from "@activities/general/modules/inventory/api";
import { InventoryHeader } from "@activities/general/modules/inventory/components/InventoryHeader";
import { ProductDetailModal } from "@activities/general/modules/inventory/components/ProductDetail";
import { groupSubcategories } from "@activities/general/modules/inventory/lib";

interface Product extends ProductRow {
  size?: string | null; extra?: ExtraValues; tax_code?: TaxCode;
}
type Status = "active" | "inactive";
const PAGE = 25;
const EMPTY_FORM = { name: "", barcode: "", unit: "قطعة", retail_price: "", wholesale_price: "", cost_price: "", subcategory_id: "", tax_code: "standard" as TaxCode };

export default function ProductsPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<Status>("active");
  const [categoryId, setCategoryId] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Partial<Product> | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [extra, setExtra] = useState<ExtraValues>({});
  const layout = useRecordForm("product");
  const vat = useVat();
  const missing = missingRequired(layout.data, extra);
  const cats = useCategories();
  const subs = useSubcategories();
  const groups = groupSubcategories(cats.data ?? [], subs.data ?? []);
  const subName = new Map((subs.data ?? []).map((s) => [s.id, s.name]));

  const list = useQuery({
    queryKey: ["products", search, status, categoryId, page],
    queryFn: () => api.get<{ items: Product[]; total: number; pages: number }>("/products", {
      search: search || undefined, status, category_id: categoryId || undefined, page, page_size: PAGE,
    }),
  });

  function openNew() {
    setForm(EMPTY_FORM);
    setExtra({});
    setEditing({});
  }
  function openEdit(p: Product) {
    setForm({
      name: p.name, barcode: p.barcode ?? "", unit: p.unit,
      retail_price: p.retail_price, wholesale_price: p.wholesale_price,
      cost_price: p.cost_price ?? "", subcategory_id: p.subcategory_id ?? "", tax_code: p.tax_code ?? "standard",
    });
    setExtra(p.extra ?? {});
    setEditing(p);
  }

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        name: form.name, barcode: form.barcode || null, unit: form.unit,
        retail_price: form.retail_price, wholesale_price: form.wholesale_price || "0",
        subcategory_id: form.subcategory_id || null, tax_code: form.tax_code,
        extra: cleanExtra(extra),
      };
      if (form.cost_price !== "") body.cost_price = form.cost_price;
      if (editing?.id && !form.subcategory_id) body.clear_subcategory = true;
      return editing?.id ? api.put(`/products/${editing.id}`, body) : api.post("/products", body);
    },
    onSuccess: () => {
      toast("success", editing?.id ? "حُفظ الصنف" : "أُضيف الصنف");
      if (editing?.id) qc.invalidateQueries({ queryKey: ["product", editing.id] });
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["products"] });
    },
  });

  const totalPages = list.data?.pages ?? 1;
  const total = list.data?.total ?? 0;
  const filtered = !!search || !!categoryId;

  return (
    <div className="flex flex-col gap-6">
      <InventoryHeader
        title="الأصناف"
        subtitle={`${total} صنف ${status === "active" ? "نشط" : "موقوف"}`}
        actions={<Button onClick={openNew}><Plus size={16} /> صنف جديد</Button>}
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-64 flex-1">
          <SearchField value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="ابحث بالاسم أو الكود أو الباركود…" />
        </div>
        <Select className="w-44" value={categoryId} onChange={(e) => { setCategoryId(e.target.value); setPage(1); }} aria-label="التصنيف">
          <option value="">كل التصنيفات</option>
          {(cats.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select className="w-36" value={status} onChange={(e) => { setStatus(e.target.value as Status); setPage(1); }} aria-label="الحالة">
          <option value="active">النشطة</option>
          <option value="inactive">الموقوفة</option>
        </Select>
      </div>

      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data!.items.length ? (
        <Empty
          text={filtered ? "لا توجد نتائج" : status === "inactive" ? "لا توجد أصناف موقوفة" : "لا توجد منتجات بعد"}
          hint={filtered ? "لا يوجد صنف يطابق البحث أو التصنيف — امسح التصفية وحاول مجددًا." : status === "inactive" ? undefined : "أضف أول منتج لتبدأ الكتالوج."}
          action={filtered ? (
            <Button variant="outline" onClick={() => { setSearch(""); setCategoryId(""); setPage(1); }}>مسح التصفية</Button>
          ) : status === "active" ? (
            <Button onClick={openNew}><Plus size={16} /> صنف جديد</Button>
          ) : undefined}
        />
      ) : (
        <TableShell>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>الكود</TableHead>
                <TableHead>الاسم</TableHead>
                <TableHead className="hidden md:table-cell">التصنيف</TableHead>
                <TableHead className="text-end">تجزئة</TableHead>
                <TableHead className="hidden sm:table-cell text-end">جملة</TableHead>
                <TableHead className="hidden lg:table-cell text-end">الرصيد</TableHead>
                <TableHead>الحالة</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.data!.items.map((p) => (
                <TableRow key={p.id} className="cursor-pointer" onClick={() => setOpenId(p.id)}>
                  <TableCell className="num text-xs text-muted-foreground" dir="ltr">{p.code ?? "—"}</TableCell>
                  <TableCell className="w-full max-w-0 truncate font-medium">{p.name}</TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground">{(p.subcategory_id && subName.get(p.subcategory_id)) ?? "—"}</TableCell>
                  <TableCell className="num text-end font-semibold">{money(p.retail_price)}</TableCell>
                  <TableCell className="num hidden sm:table-cell text-end">{money(p.wholesale_price)}</TableCell>
                  <TableCell className="num hidden lg:table-cell text-end">{p.current_qty != null ? `${fq(p.current_qty)} ${p.unit}` : "—"}</TableCell>
                  <TableCell>
                    <KitBadge variant={p.is_active ? "success" : "secondary"}>{p.is_active ? "نشط" : "موقوف"}</KitBadge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableShell>
      )}

      <TablePagination page={page} pages={totalPages} onPage={(p) => setPage(p)} pageSize={PAGE} onPageSize={() => setPage(1)} />

      <ProductDetailModal productId={openId} onClose={() => setOpenId(null)} onEdit={(p) => openEdit(p as Product)} />

      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing?.id ? "تعديل صنف" : "صنف جديد"}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!save.isPending && form.name && form.retail_price && !missing.length) save.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <RecordFormFields
            record="product"
            required={["name", "retail_price"]}
            extra={extra}
            onExtra={setExtra}
            builtin={{
              name: <Input id="f-product-name" autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />,
              barcode: <Input id="f-product-barcode" className="num" dir="ltr" value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value })} />,
              unit: <Input id="f-product-unit" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />,
              retail_price: <Input id="f-product-retail_price" className="num" inputMode="decimal" value={form.retail_price} onChange={(e) => setForm({ ...form, retail_price: e.target.value })} />,
              wholesale_price: <Input id="f-product-wholesale_price" className="num" inputMode="decimal" value={form.wholesale_price} onChange={(e) => setForm({ ...form, wholesale_price: e.target.value })} />,
              cost_price: <Input id="f-product-cost_price" className="num" inputMode="decimal" value={form.cost_price} onChange={(e) => setForm({ ...form, cost_price: e.target.value })} />,
              tax_code: (
                <Select id="f-product-tax_code" value={form.tax_code} onChange={(e) => setForm({ ...form, tax_code: e.target.value as TaxCode })}>
                  {(vat.data?.codes ?? [{ code: "standard", label: "خاضع للضريبة (14%)" }, { code: "zero", label: "خاضع بنسبة صفر" },
                    { code: "exempt", label: "معفى من الضريبة" }]).map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                </Select>
              ),
              subcategory_id: (
                <Select id="f-product-subcategory_id" value={form.subcategory_id} onChange={(e) => setForm({ ...form, subcategory_id: e.target.value })}>
                  <option value="">— بدون تصنيف —</option>
                  {groups.filter((g) => g.subcategories.length).map((g) => (
                    <optgroup key={g.category.id} label={g.category.name}>
                      {g.subcategories.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </optgroup>
                  ))}
                </Select>
              ),
            }}
          />
          {!subs.isLoading && !subs.data?.length && (
            <p className="text-xs text-muted-foreground">لا توجد تصنيفات بعد: يُحفظ الصنف بلا تصنيف، ويمكن إنشاء التصنيفات من «التصنيفات».</p>
          )}
          {missing.length > 0 && <p className="text-xs text-muted-foreground">حقول مطلوبة: {missing.join("، ")}</p>}
          {save.isError && <ErrorBox message={(save.error as Error).message} />}
          <Button
            type="submit"
            className="w-full h-10 font-bold"
            disabled={save.isPending || !form.name || !form.retail_price || missing.length > 0}
          >
            {save.isPending ? <Spinner /> : "حفظ الصنف"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}
