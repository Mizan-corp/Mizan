/**
 * PAGE CONTRACT
 * Page: المبيعات (/sales)
 * User: مدير أو محاسب أو كاشير يراجع الفواتير وعروض الأسعار والمسودات ويتعامل مع حالة واحدة
 * Outcome: الوصول لمستند محدد وتنفيذ إجراء واحد عليه (تأكيد، تعديل، حذف، إلغاء، مرتجع، طباعة، إرسال)
 * Primary information: رقم المستند + تاريخه، العميل، الإجمالي/المتبقي، الحالة
 * Data: كل تصفية (التبويب، التاريخ، البحث) على الخادم قبل التقسيم إلى صفحات (/sales/page مع العدد الكلي)؛
 *       البطاقات من /sales/summary: صافي بعد المرتجعات وبدون الضريبة كما تحسبها التقارير.
 * Permissions: كل إجراء يظهر لمن يملك صلاحيته فقط (lib.ts saleActions)؛ الحذف والإلغاء والمرتجع بعد تأكيد.
 * Required states: loading (skeleton), error (retry), filtered-empty (reset), first-use-empty, populated
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCheck, Download, FilePenLine, Mail, MoreHorizontal, Printer, Receipt, Send, ShoppingCart, Trash2, Undo2, Wallet, XCircle,
} from "lucide-react";
import { api, downloadExport, openPrintDoc } from "@/lib/api";
import { dateTime, formatDateTime, moneyEGP } from "@/lib/format";
import { ListState, Money, Num, PageHeader, SearchField, StatCard, StatusBadge, TablePagination, TableShell } from "@/components/app/shared";
import { Button } from "@/components/kit/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/kit/dropdown-menu";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/kit/sheet";
import { Skeleton } from "@/components/kit/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/kit/tabs";
import { ConfirmDialog, ErrorBox, Input, Modal, useToast } from "@/components/ui";
import { useAuth } from "@/stores/auth";
import type { SaleDetail, SaleRow, SalesPage as Paged, SalesSummary } from "../api";
import { fullyReturned, PERM, pagesOf, paymentLabel, returnItems, saleActions, statusLabel } from "../lib";
import { ConfirmDocumentDialog } from "../components/ConfirmDocumentDialog";
import { EditDocumentModal } from "../components/EditDocumentModal";

type View = "invoices" | "quotations";
type Pending =
  | { kind: "cancel"; sale: SaleRow }
  | { kind: "full-return"; sale: SaleRow }
  | { kind: "partial-return"; sale: SaleRow; items: { product_id: string; qty: number }[] }
  | { kind: "delete"; sale: SaleRow };

/** The search waits for the typing to stop before asking the server. */
function useDebounced(value: string, ms = 300): string {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function SalesPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const can = useAuth((s) => s.can);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [view, setView] = useState<View>("invoices");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);
  const [returnQty, setReturnQty] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState<SaleRow | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [emailFor, setEmailFor] = useState<SaleRow | null>(null);
  const [targetEmail, setTargetEmail] = useState("");

  useEffect(() => setPage(1), [search, view, from, to]);
  useEffect(() => setReturnQty({}), [detailId]);

  const filters = { search: search || undefined, from_date: from || undefined, to_date: to || undefined };
  const list = useQuery({
    queryKey: ["sales", "page", view, page, pageSize, filters],
    queryFn: () => api.get<Paged>("/sales/page", { kind: view, page, page_size: pageSize, ...filters }),
    placeholderData: keepPreviousData,
  });
  const summary = useQuery({
    queryKey: ["sales-summary", filters],
    queryFn: () => api.get<SalesSummary>("/sales/summary", filters),
  });
  const detail = useQuery({
    queryKey: ["sale", detailId],
    queryFn: () => api.get<SaleDetail>(`/sales/${detailId}`),
    enabled: !!detailId,
  });

  const refresh = () => {
    for (const key of ["sales", "sale", "sales-summary", "shift", "customers"]) qc.invalidateQueries({ queryKey: [key] });
  };
  const onFail = (e: unknown) => toast("error", (e as Error).message);

  const act = useMutation({
    mutationFn: async (p: Pending): Promise<{ doc_number?: string; detail?: string } | undefined> => {
      const id = p.sale.id;
      if (p.kind === "cancel") return api.put(`/sales/${id}/cancel`);
      if (p.kind === "full-return") return api.post(`/sales/${id}/return`);
      if (p.kind === "partial-return") return api.post(`/sales/${id}/partial-return`, { items: p.items });
      await api.del(`/sales/${id}`);
      return undefined;
    },
    onSuccess: (res, p) => {
      const msg = p.kind === "cancel" ? "تم إلغاء الفاتورة"
        : p.kind === "delete" ? `حُذف ${p.sale.status === "quotation" ? "عرض السعر" : "المستند"} ${p.sale.invoice_number}`
        : res?.doc_number ? `تم تسجيل المرتجع ${res.doc_number}` : "تم تسجيل المرتجع";
      toast("success", msg);
      if (p.kind === "partial-return") setReturnQty({});
      setPending(null);
      refresh();
    },
    onError: (e) => {
      setPending(null);
      onFail(e);
    },
  });

  const sendEmail = useMutation({
    mutationFn: (args: { id: string; email: string }) =>
      api.post<{ ok: boolean; message: string }>(`/invoices/${args.id}/send`, { email: args.email }),
    onSuccess: (data) => {
      toast("success", data.message || "تم إرسال الفاتورة بالبريد");
      setEmailFor(null);
      setTargetEmail("");
    },
  });

  function downloadPdf(row: Pick<SaleRow, "id" | "invoice_number">) {
    downloadExport(`/invoices/${row.id}/pdf`, undefined, `invoice-${row.invoice_number}.pdf`).catch(onFail);
  }

  const rows = list.data?.items ?? [];
  const pages = pagesOf(list.data?.total ?? 0, pageSize);
  const filtered = !!(search || from || to);
  const s = summary.data;
  const d = detail.data;
  const dActions = d ? saleActions(d, can) : null;
  const returnTyped = returnItems(returnQty);
  // The dialogs open over the page, not over the detail sheet: the sheet closes first.
  const fromSheet = (open: () => void) => { setDetailId(null); open(); };
  const pendingItems = pending?.kind === "partial-return" ? pending.items : [];

  const pendingText: Record<Pending["kind"], { title: string; message: string; label: string }> = {
    cancel: {
      title: `إلغاء الفاتورة ${pending?.sale.invoice_number ?? ""}`,
      message: "يعود المخزون، ويُرد المبلغ من درج ورديتك أو المحفظة أو يُخصم من حساب العميل، وتُعكس القيود. لا يمكن التراجع عن الإلغاء.",
      label: "إلغاء الفاتورة",
    },
    "full-return": {
      title: `مرتجع ${pending && Number(pending.sale.returns_total ?? 0) > 0 ? "باقي" : "كامل"} للفاتورة ${pending?.sale.invoice_number ?? ""}`,
      message: "يُسجَّل مستند مرتجع بكل ما لم يُرتجع بعد، ويعود المخزون، ويُرد النقدي من درج ورديتك المفتوحة في فرع الفاتورة.",
      label: "تسجيل المرتجع",
    },
    "partial-return": {
      title: `مرتجع جزئي للفاتورة ${pending?.sale.invoice_number ?? ""}`,
      message: `يُسجَّل مرتجع بـ ${pendingItems.length} ${pendingItems.length === 1 ? "صنف" : "أصناف"} (${pendingItems.map((i) => i.qty).join(" + ")} وحدة)، ويُرد النقدي من درج ورديتك المفتوحة في فرع الفاتورة.`,
      label: "تسجيل المرتجع",
    },
    delete: {
      title: `حذف ${pending?.sale.status === "quotation" ? "عرض السعر" : "المسودة"} ${pending?.sale.invoice_number ?? ""}`,
      message: "يُحذف المستند نهائياً. لم يُخصم به مخزون ولم يُدفع به مال.",
      label: "حذف",
    },
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="المبيعات"
        description="الفواتير والمرتجعات وعروض الأسعار والمسودات"
        actions={
          <div className="flex items-center gap-2">
            {can(PERM.export) && (
              <Button variant="outline" size="sm" className="gap-1.5 text-xs"
                      onClick={() => downloadExport("/export/sales", { from_date: from || undefined, to_date: to || undefined }, "sales.xlsx").catch(onFail)}>
                <Download className="size-3.5" />
                تصدير
              </Button>
            )}
            {can("pos") && (
              <Button nativeButton={false} render={<Link to="/pos" />} size="sm" className="gap-1.5 text-xs font-bold shadow-xs">
                <ShoppingCart className="size-3.5" />
                <span>فاتورة جديدة</span>
              </Button>
            )}
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {summary.isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)
        ) : summary.isError ? (
          <div className="sm:col-span-2 lg:col-span-4">
            <ErrorBox message={(summary.error as Error).message} onRetry={() => summary.refetch()} />
          </div>
        ) : s && (
          <>
            <StatCard label="صافي المبيعات" value={<Money value={Number(s.net_sales)} />} icon={Receipt}
                      hint="بعد المرتجعات ودون ضريبة القيمة المضافة" />
            <StatCard label="المرتجعات" value={<Money value={Number(s.returns_total)} />} icon={Undo2}
                      hint={<><Num value={s.returns_count} /> مستند مرتجع</>} />
            <StatCard label="مستحقات آجلة" value={<Money value={Number(s.outstanding)} />} icon={Wallet} tone="warning"
                      hint="المتبقي على فواتير الآجل" />
            <StatCard label="عدد الفواتير" value={<Num value={s.invoice_count} />} icon={CheckCheck}
                      hint={<><Num value={s.quotation_count} /> عرض سعر · <Num value={s.draft_count} /> مسودة</>} />
          </>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <SearchField value={searchInput} onChange={setSearchInput} placeholder="رقم المستند أو اسم العميل" />
        <div>
          <label htmlFor="sales-from" className="mb-1 block text-xs font-medium text-muted-foreground">من تاريخ</label>
          <Input id="sales-from" type="date" className="w-40" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div>
          <label htmlFor="sales-to" className="mb-1 block text-xs font-medium text-muted-foreground">إلى تاريخ</label>
          <Input id="sales-to" type="date" className="w-40" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
        <Tabs value={view} onValueChange={(v) => setView(v as View)}>
          <TabsList>
            <TabsTrigger value="invoices">الفواتير</TabsTrigger>
            <TabsTrigger value="quotations">عروض الأسعار والمسودات</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <ListState
        status={list.isLoading ? "loading" : list.isError ? "error" : "ready"}
        isEmpty={rows.length === 0}
        onRetry={() => list.refetch()}
        emptyIcon={Receipt}
        emptyTitle={filtered ? "لا توجد نتائج" : view === "invoices" ? "لا توجد فواتير بعد" : "لا توجد عروض أسعار أو مسودات"}
        emptyDescription={filtered ? "لا توجد مستندات تطابق البحث أو الفترة — وسّع التصفية أو امسحها." : "ستظهر المستندات هنا بمجرد تسجيلها من نقطة البيع."}
        emptyAction={filtered ? (
          <Button variant="outline" onClick={() => { setSearchInput(""); setFrom(""); setTo(""); }}>مسح التصفية</Button>
        ) : can("pos") ? (
          <Button nativeButton={false} render={<Link to="/pos" />}>
            <ShoppingCart data-icon="inline-start" />
            ابدأ البيع
          </Button>
        ) : undefined}
      >
        <TableShell>
          <Table>
            <TableHeader>
              <TableRow className="border-b border-border/80 bg-muted/40 text-[11px] font-semibold text-muted-foreground">
                <TableHead className="w-[180px] whitespace-nowrap">المستند والتاريخ</TableHead>
                <TableHead>العميل</TableHead>
                <TableHead className="hidden lg:table-cell">طريقة الدفع</TableHead>
                <TableHead className="hidden xl:table-cell">بواسطة</TableHead>
                <TableHead>الإجمالي</TableHead>
                <TableHead className="hidden sm:table-cell">الحالة</TableHead>
                <TableHead className="w-12 text-center"><span className="sr-only">إجراءات</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((inv) => {
                const a = saleActions(inv, can);
                const owed = Number(inv.net_total) - Number(inv.returns_total ?? 0) - Number(inv.paid_amount ?? 0);
                return (
                  <TableRow key={inv.id} className="cursor-pointer" onClick={() => setDetailId(inv.id)}>
                    <TableCell className="w-[180px] whitespace-nowrap">
                      <div className="flex flex-col gap-0.5">
                        <span className="num font-mono font-bold text-foreground">{inv.invoice_number}</span>
                        <span className="num whitespace-nowrap font-mono text-xs text-muted-foreground">{formatDateTime(inv.created_at)}</span>
                      </div>
                    </TableCell>
                    <TableCell className="w-full max-w-0 truncate">{inv.customer_name ?? "عميل نقدي"}</TableCell>
                    <TableCell className="hidden lg:table-cell">{paymentLabel(inv)}</TableCell>
                    <TableCell className="hidden xl:table-cell text-xs text-muted-foreground">{inv.created_by_name || "—"}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <Money value={Number(inv.net_total)} className="font-medium" />
                        {inv.is_credit && inv.status === "confirmed" && owed > 0 && (
                          <span className="text-xs text-warning-ink">متبقي <Money value={owed} currency={false} /></span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell"><StatusBadge status={statusLabel(inv)} /></TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="size-8" aria-label={`إجراءات ${inv.invoice_number}`} />}>
                          <MoreHorizontal />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuGroup>
                            <DropdownMenuItem onClick={() => setDetailId(inv.id)}>عرض التفاصيل</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openPrintDoc(`/print/sale/${inv.id}`).catch(onFail)}>
                              <Printer /> طباعة
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => downloadPdf(inv)}><Download /> تحميل PDF</DropdownMenuItem>
                            {a.email && (
                              <DropdownMenuItem onClick={() => { setEmailFor(inv); setTargetEmail(""); }}><Mail /> إرسال بالبريد</DropdownMenuItem>
                            )}
                          </DropdownMenuGroup>
                          {(a.confirm || a.edit || a.remove) && (
                            <>
                              <DropdownMenuSeparator />
                              <DropdownMenuGroup>
                                {a.confirm && (
                                  <DropdownMenuItem onClick={() => setConfirming(inv)}>
                                    <CheckCheck /> {inv.status === "quotation" ? "تحويل لفاتورة" : "تأكيد المسودة"}
                                  </DropdownMenuItem>
                                )}
                                {a.edit && <DropdownMenuItem onClick={() => setEditingId(inv.id)}><FilePenLine /> تعديل</DropdownMenuItem>}
                                {a.remove && (
                                  <DropdownMenuItem variant="destructive" onClick={() => setPending({ kind: "delete", sale: inv })}>
                                    <Trash2 /> حذف
                                  </DropdownMenuItem>
                                )}
                              </DropdownMenuGroup>
                            </>
                          )}
                          {(a.returnSale || a.cancel) && (
                            <>
                              <DropdownMenuSeparator />
                              <DropdownMenuGroup>
                                {a.returnSale && (
                                  <DropdownMenuItem onClick={() => setPending({ kind: "full-return", sale: inv })}>
                                    <Undo2 /> {Number(inv.returns_total ?? 0) > 0 ? "إرجاع المتبقي" : "مرتجع كامل"}
                                  </DropdownMenuItem>
                                )}
                                {a.cancel && (
                                  <DropdownMenuItem variant="destructive" onClick={() => setPending({ kind: "cancel", sale: inv })}>
                                    <XCircle /> إلغاء الفاتورة
                                  </DropdownMenuItem>
                                )}
                              </DropdownMenuGroup>
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableShell>
      </ListState>

      {!list.isLoading && !list.isError && rows.length > 0 && (
        <div className="flex flex-col gap-1">
          <TablePagination page={page} pages={pages} onPage={setPage} pageSize={pageSize}
                           onPageSize={(n) => { setPageSize(n); setPage(1); }} />
          <p className="text-xs text-muted-foreground">
            <Num value={list.data?.total ?? 0} /> مستند {view === "invoices" ? "(فواتير ومرتجعات وملغاة)" : "(عروض أسعار ومسودات)"}
          </p>
        </div>
      )}

      <Sheet open={!!detailId} onOpenChange={(o) => !o && setDetailId(null)}>
        <SheetContent side="left" className="w-full overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle className="num">
              {d?.status === "returned" ? "مرتجع" : d?.status === "quotation" ? "عرض سعر" : d?.status === "draft" ? "مسودة" : "فاتورة"} {d?.invoice_number ?? ""}
            </SheetTitle>
            <SheetDescription>
              {d ? `${d.sale_mode === "wholesale" ? "جملة" : "تجزئة"} · ${dateTime(d.created_at)}` : ""}
            </SheetDescription>
          </SheetHeader>
          {detail.isLoading ? (
            <div className="flex flex-col gap-3 p-4">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : detail.isError ? (
            <div className="p-4"><ErrorBox message={(detail.error as Error).message} onRetry={() => detail.refetch()} /></div>
          ) : d && dActions && (
            <div className="flex flex-col gap-4 p-4">
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">الإجمالي</p>
                  <p className="num text-sm font-semibold">{moneyEGP(d.net_total ?? d.total)}</p>
                  {Number(d.tax_amount ?? 0) > 0 && (
                    <p className="num text-[11px] text-muted-foreground">منها ضريبة {moneyEGP(d.tax_amount ?? 0)}</p>
                  )}
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">المدفوع</p>
                  <p className="num text-sm font-semibold">{moneyEGP(d.paid_amount ?? 0)}</p>
                  {Number(d.remaining ?? 0) > 0 && <p className="num text-[11px] text-warning-ink">متبقي {moneyEGP(d.remaining ?? 0)}</p>}
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">الحالة</p>
                  <StatusBadge status={statusLabel(d)} />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {d.customer_name ?? "عميل نقدي"} · {paymentLabel(d)}{d.notes ? ` · ${d.notes}` : ""}
              </p>

              <div className="overflow-hidden rounded-xl border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>الصنف</TableHead>
                      <TableHead>الكمية</TableHead>
                      <TableHead className="text-end">السعر</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(d.items ?? []).map((it, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-medium">{it.product_name}</TableCell>
                        <TableCell className="num">{Number(it.qty)}</TableCell>
                        <TableCell className="num text-end">{moneyEGP(it.unit_price)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {d.status === "returned" && d.return_of && (
                <div className="flex items-center justify-between gap-2 rounded-xl border p-3 text-sm">
                  <span className="text-muted-foreground">مرتجع من الفاتورة</span>
                  <button type="button" className="num font-mono font-semibold text-primary hover:underline"
                          onClick={() => setDetailId(d.return_of ?? null)}>
                    {d.return_of_number ?? "—"}
                  </button>
                </div>
              )}

              {(d.returns ?? []).length > 0 && (
                <div className="rounded-xl border p-3">
                  <p className="mb-2 flex items-center gap-2 text-sm font-semibold">
                    <Undo2 className="size-4" /> المرتجعات
                    <span className="num ms-auto text-xs font-normal text-muted-foreground">الإجمالي {moneyEGP(d.returns_total ?? 0)}</span>
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {(d.returns ?? []).map((r) => (
                      <button key={r.id} type="button" onClick={() => setDetailId(r.id)}
                              className="flex items-center justify-between gap-2 rounded-md px-1.5 py-1 text-sm hover:bg-muted/60">
                        <span className="num font-mono">{r.invoice_number}</span>
                        <span className="num text-muted-foreground">{moneyEGP(r.net_total)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {dActions.returnSale && (
                <div className="rounded-xl border p-3">
                  <p className="mb-2 flex items-center gap-2 text-sm font-semibold"><Undo2 className="size-4" /> مرتجع جزئي</p>
                  <div className="flex flex-col gap-2">
                    {(d.items ?? []).map((it, i) => {
                      const left = Number(it.qty) - Number(it.returned_qty ?? 0);
                      return (
                        <div key={i} className="flex items-center justify-between gap-2 text-sm">
                          <span className="min-w-0 flex-1 truncate">
                            {it.product_name}{" "}
                            <span className="num text-muted-foreground">
                              (مبيع {Number(it.qty)}{Number(it.returned_qty ?? 0) > 0 ? ` · مرتجع ${it.returned_qty}` : ""})
                            </span>
                          </span>
                          <input
                            className="num w-20 rounded-md border bg-transparent p-1.5 text-center disabled:opacity-50"
                            inputMode="decimal"
                            placeholder="0"
                            disabled={left <= 0}
                            value={returnQty[it.product_id] ?? ""}
                            onChange={(e) => setReturnQty((r) => ({ ...r, [it.product_id]: e.target.value }))}
                            aria-label={`كمية مرتجع ${it.product_name} (المتبقي ${left})`}
                          />
                        </div>
                      );
                    })}
                  </div>
                  <Button variant="outline" className="mt-3 w-full" disabled={act.isPending || !returnTyped.length}
                          onClick={() => fromSheet(() => setPending({ kind: "partial-return", sale: d, items: returnTyped }))}>
                    تنفيذ المرتجع الجزئي
                  </Button>
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Button onClick={() => openPrintDoc(`/print/sale/${d.id}`).catch(onFail)}>
                  <Printer data-icon="inline-start" /> طباعة
                </Button>
                <Button variant="outline" className="gap-1.5" onClick={() => downloadPdf(d)}>
                  <Download className="size-4" /> PDF
                </Button>
                {dActions.email && (
                  <Button variant="outline" className="gap-1.5" onClick={() => fromSheet(() => { setEmailFor(d); setTargetEmail(""); })}>
                    <Mail className="size-4" /> إرسال بريد
                  </Button>
                )}
                {dActions.confirm && (
                  <Button variant="outline" onClick={() => fromSheet(() => setConfirming(d))}>
                    <CheckCheck className="size-4" /> {d.status === "quotation" ? "تحويل لفاتورة" : "تأكيد المسودة"}
                  </Button>
                )}
                {dActions.edit && (
                  <Button variant="outline" onClick={() => fromSheet(() => setEditingId(d.id))}><FilePenLine className="size-4" /> تعديل</Button>
                )}
                {dActions.remove && (
                  <Button variant="destructive" onClick={() => fromSheet(() => setPending({ kind: "delete", sale: d }))}><Trash2 className="size-4" /> حذف</Button>
                )}
                {dActions.returnSale && (
                  <Button variant="outline" disabled={act.isPending} onClick={() => fromSheet(() => setPending({ kind: "full-return", sale: d }))}>
                    {Number(d.returns_total ?? 0) > 0 ? "إرجاع المتبقي" : "مرتجع كامل"}
                  </Button>
                )}
                {dActions.cancel && (
                  <Button variant="destructive" disabled={act.isPending} onClick={() => fromSheet(() => setPending({ kind: "cancel", sale: d }))}>
                    إلغاء الفاتورة
                  </Button>
                )}
              </div>
              {fullyReturned(d) && <p className="text-xs text-muted-foreground">أُرجعت الفاتورة بالكامل.</p>}
            </div>
          )}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={!!pending}
        onClose={() => setPending(null)}
        onConfirm={() => pending && !act.isPending && act.mutate(pending)}
        title={pending ? pendingText[pending.kind].title : ""}
        message={pending ? pendingText[pending.kind].message : ""}
        confirmLabel={pending ? pendingText[pending.kind].label : "تأكيد"}
      />
      <ConfirmDocumentDialog doc={confirming} onClose={() => setConfirming(null)} />
      <EditDocumentModal docId={editingId} onClose={() => setEditingId(null)} />

      <Modal open={!!emailFor} onClose={() => setEmailFor(null)} title={`إرسال ${emailFor?.invoice_number ?? ""} بالبريد`}>
        <form
          className="space-y-4 p-1"
          onSubmit={(e) => {
            e.preventDefault();
            if (emailFor && targetEmail.trim() && !sendEmail.isPending) sendEmail.mutate({ id: emailFor.id, email: targetEmail.trim() });
          }}
        >
          <p className="text-xs text-muted-foreground">يُرفق المستند بصيغة PDF بهوية المنشأة ويُرسل إلى العنوان المكتوب.</p>
          <div className="space-y-1.5">
            <label htmlFor="customer-invoice-email" className="text-xs font-semibold">البريد الإلكتروني</label>
            <Input id="customer-invoice-email" type="email" dir="ltr" placeholder="customer@example.com" maxLength={254}
                   value={targetEmail} onChange={(e) => setTargetEmail(e.target.value)} className="font-mono text-xs" />
          </div>
          {sendEmail.isError && <ErrorBox message={(sendEmail.error as Error).message} />}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setEmailFor(null)}>إلغاء</Button>
            <Button type="submit" size="sm" disabled={sendEmail.isPending || !targetEmail.trim()} className="gap-1.5 font-bold">
              <Send className="size-3.5" />
              {sendEmail.isPending ? "جارٍ الإرسال…" : "إرسال"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
