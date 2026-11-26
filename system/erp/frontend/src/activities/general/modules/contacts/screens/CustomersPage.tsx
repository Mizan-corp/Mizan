import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  HandCoins,
  Pencil,
  Plus,
  Power,
  Scale,
  Search,
  ShieldAlert,
  Trash2,
  Undo2,
  Users,
} from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { Badge } from "@/components/kit/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { api } from "@/lib/api";
import { D, dateTime, moneyEGP } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Button, Card, ConfirmDialog, Empty, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { sound } from "@/lib/sound";
import { RecordFormFields, cleanExtra, missingRequired, useRecordForm, type ExtraValues } from "@app/framework/forms";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";
import { newClientId } from "@activities/general/modules/finance/api";

interface Customer {
  id: string;
  name: string;
  phone: string | null;
  address: string | null;
  balance: string;
  credit_limit: string | null;
  is_active: boolean;
  extra?: ExtraValues;
}

/** GET /customers/summary: the cards, over every customer of the filter. */
interface Summary {
  total: number;
  debtors: number;
  total_due: string;
  over_limit: number;
}

/** One line of GET /customers/{id}/ledger, with the balance after it. */
interface LedgerLine {
  id: string;
  type: "invoice" | "return" | "payment" | "payment_reversal" | "opening" | "adjustment";
  ref: string;
  note: string | null;
  date: string;
  debit: number;
  credit: number;
  balance: number;
  can_reverse: boolean;
}

interface LedgerPage {
  items: LedgerLine[];
  total: number;
  page: number;
  pages: number;
}

const LEDGER_LABEL: Record<LedgerLine["type"], string> = {
  invoice: "فاتورة آجلة",
  return: "مرتجع",
  payment: "دفعة",
  payment_reversal: "عكس دفعة",
  opening: "رصيد افتتاحي",
  adjustment: "تسوية رصيد",
};

const PAGE_SIZE = 50;
const LEDGER_PAGE = 50;
const emptyForm = { name: "", phone: "", credit_limit: "", address: "" };

export default function CustomersPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const can = useAuth((s) => s.can);
  const isManager = useAuth((s) => !!s.user?.is_manager);
  const manageMoney = can("finance") || isManager;   // write-offs, stopping and removing customers
  const canReverse = can("finance");

  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(0);
  const [formFor, setFormFor] = useState<"new" | Customer | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [extra, setExtra] = useState<ExtraValues>({});
  const layout = useRecordForm("customer");
  const missing = missingRequired(layout.data, extra);
  const [ledgerFor, setLedgerFor] = useState<Customer | null>(null);
  const [ledgerPage, setLedgerPage] = useState(1);
  const [payFor, setPayFor] = useState<Customer | null>(null);
  const [payAmount, setPayAmount] = useState("");
  const [paySource, setPaySource] = useState("");
  const [payClientId, setPayClientId] = useState("");
  const [balanceFor, setBalanceFor] = useState<Customer | null>(null);
  const [newBalance, setNewBalance] = useState("");
  const [balanceNote, setBalanceNote] = useState("");
  const [removing, setRemoving] = useState<Customer | null>(null);
  const [reversing, setReversing] = useState<LedgerLine | null>(null);
  const [reverseReason, setReverseReason] = useState("");

  const filter = { search: search.trim() || undefined, include_inactive: showInactive ? "true" : undefined };
  const list = useQuery({
    queryKey: ["customers", search, showInactive, page],
    queryFn: () => api.get<Customer[]>("/customers", { ...filter, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  });
  const summary = useQuery({
    queryKey: ["customers", "summary", search, showInactive],
    queryFn: () => api.get<Summary>("/customers/summary", filter),
    enabled: can("customers"),
  });
  const ledger = useQuery({
    queryKey: ["customer-ledger", ledgerFor?.id, ledgerPage],
    queryFn: () => api.get<LedgerPage>(`/customers/${ledgerFor!.id}/ledger`,
                                       { page: ledgerPage, page_size: LEDGER_PAGE, newest_first: "true" }),
    enabled: !!ledgerFor,
  });

  const refreshCustomers = () => qc.invalidateQueries({ queryKey: ["customers"] });
  const openForm = (target: "new" | Customer) => {
    sound.click();
    setFormFor(target);
    if (target === "new") {
      setForm(emptyForm);
      setExtra({});
    } else {
      setForm({ name: target.name, phone: target.phone ?? "", credit_limit: target.credit_limit ?? "", address: target.address ?? "" });
      setExtra(target.extra ?? {});
    }
  };

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        name: form.name.trim(),
        phone: form.phone.trim() || null,
        credit_limit: form.credit_limit ? D(form.credit_limit).toFixed(2) : null,
        address: form.address.trim() || null,
        extra: cleanExtra(extra),
      };
      // A new customer without a limit typed gets the workspace's default credit limit (contacts setting).
      if (formFor === "new" && !form.credit_limit) delete body.credit_limit;
      return formFor === "new" ? api.post("/customers", body) : api.put(`/customers/${(formFor as Customer).id}`, body);
    },
    onSuccess: () => {
      sound.success();
      toast("success", formFor === "new" ? "أُضيف العميل" : "حُفظت بيانات العميل");
      setFormFor(null);
      refreshCustomers();
    },
    onError: () => sound.error(),
  });

  const pay = useMutation({
    mutationFn: () =>
      api.post(`/customers/${payFor!.id}/payments`, {
        amount: D(payAmount).toFixed(2), method: "cash", ...sourceFields(paySource), client_id: payClientId,
      }),
    onSuccess: () => {
      sound.success();
      setPayFor(null);
      qc.invalidateQueries({ queryKey: ["safes"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
      qc.invalidateQueries({ queryKey: ["customer-ledger"] });
      toast("success", "تم تسجيل دفعة العميل بنجاح");
      refreshCustomers();
    },
    onError: () => sound.error(),
  });

  const setBalance = useMutation({
    mutationFn: () => api.put(`/customers/${balanceFor!.id}/balance`, { balance: D(newBalance || "0").toFixed(2), note: balanceNote || null }),
    onSuccess: () => {
      sound.success();
      toast("success", "سُجّلت تسوية الرصيد");
      setBalanceFor(null);
      qc.invalidateQueries({ queryKey: ["customer-ledger"] });
      refreshCustomers();
    },
    onError: () => sound.error(),
  });

  const setActive = useMutation({
    mutationFn: (c: Customer) => api.post(`/customers/${c.id}/${c.is_active ? "deactivate" : "activate"}`),
    onSuccess: (_d, c) => {
      sound.success();
      toast("success", c.is_active ? "تم إيقاف العميل" : "تمت إعادة تفعيل العميل");
      refreshCustomers();
    },
    onError: (e) => {
      sound.error();
      toast("error", (e as Error).message);
    },
  });

  const remove = useMutation({
    mutationFn: (c: Customer) => api.del(`/customers/${c.id}`),
    onSuccess: () => {
      sound.success();
      toast("success", "حُذف العميل");
      setRemoving(null);
      refreshCustomers();
    },
    onError: (e) => {
      sound.error();
      setRemoving(null);
      toast("error", (e as Error).message);
    },
  });

  const reverse = useMutation({
    mutationFn: () => api.post(`/customers/payments/${reversing!.id}/reverse`, { reason: reverseReason.trim() }),
    onSuccess: () => {
      sound.success();
      toast("success", "عُكست الدفعة وعاد المبلغ إلى رصيد العميل");
      setReversing(null);
      qc.invalidateQueries({ queryKey: ["customer-ledger"] });
      qc.invalidateQueries({ queryKey: ["safes"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
      refreshCustomers();
    },
    onError: () => sound.error(),
  });

  const customers = list.data ?? [];
  const s = summary.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight">
            <Users className="size-6 text-primary" aria-hidden />
            العملاء والذمم المدينة
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            الحسابات الجارية للعملاء، متابعة المديونيات، وتحصيل الدفعات
          </p>
        </div>
        {can("customers") && (
          <Button onClick={() => openForm("new")} className="gap-2 font-semibold">
            <Plus className="size-4" />
            عميل جديد
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-4">
          <p className="text-[11px] font-medium text-muted-foreground">إجمالي المديونيات</p>
          <p className="num mt-1 text-xl font-bold tracking-tight text-destructive-ink">{s ? moneyEGP(s.total_due) : "—"}</p>
          <p className="mt-1 text-[10px] text-muted-foreground/80">مستحقات آجلة لدى العملاء</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11px] font-medium text-muted-foreground">العملاء المدينون</p>
          <div className="mt-1 flex items-baseline gap-1.5">
            <p className="num text-xl font-bold tracking-tight text-foreground">{s?.debtors ?? "—"}</p>
            <span className="text-[11px] text-muted-foreground">
              من أصل <span className="num font-semibold">{s?.total ?? "—"}</span>
            </span>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground/80">عليهم أرصدة قائمة للدفع</p>
        </Card>
        <Card className={`p-4 ${s && s.over_limit > 0 ? "border-amber-500/40 bg-amber-500/5 dark:bg-amber-500/10" : ""}`}>
          <p className="text-[11px] font-medium text-muted-foreground">تجاوز الحد الائتماني</p>
          <div className="mt-1 flex items-center gap-2">
            <p className={`num text-xl font-bold tracking-tight ${s && s.over_limit > 0 ? "text-amber-600 dark:text-amber-400" : "text-foreground"}`}>
              {s?.over_limit ?? "—"}
            </p>
            {!!s?.over_limit && <Badge variant="warning" className="h-5 px-1.5 text-[10px] font-bold">تنبيه مخاطر</Badge>}
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground/80">تخطوا سقف الائتمان المسموح</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11px] font-medium text-muted-foreground">العملاء المسجلون</p>
          <p className="num mt-1 text-xl font-bold tracking-tight text-foreground">{s?.total ?? "—"}</p>
          <p className="mt-1 text-[10px] text-muted-foreground/80">{showInactive ? "مع الموقوفين" : "النشطون فقط"}</p>
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 rounded-xl border border-border/80 bg-card p-2.5 shadow-xs">
          <Search className="absolute start-5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="ابحث باسم العميل أو رقم الهاتف…"
            value={search}
            maxLength={128}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            className="ps-10 text-xs border-0 bg-transparent shadow-none focus-visible:ring-0"
          />
        </div>
        <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <input type="checkbox" checked={showInactive} onChange={(e) => { setShowInactive(e.target.checked); setPage(0); }} />
          إظهار العملاء الموقوفين
        </label>
      </div>

      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : customers.length === 0 ? (
        <Empty text="لا يوجد عملاء مطابقون" hint={search ? "جرّب البحث بكلمة أخرى" : "اضغط على «عميل جديد» لإضافة أول عميل"} />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-xs">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-b border-border/80 bg-muted/40 text-[11px] font-semibold text-muted-foreground">
                  <TableHead className="p-3 text-start">العميل</TableHead>
                  <TableHead className="p-3 text-start">الهاتف</TableHead>
                  <TableHead className="p-3 text-start">الرصيد القائم</TableHead>
                  <TableHead className="hidden p-3 text-start sm:table-cell">الحد الائتماني</TableHead>
                  <TableHead className="p-3 text-center">حالة الائتمان</TableHead>
                  <TableHead className="p-3 text-end">الإجراءات</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {customers.map((c) => {
                  const bal = D(c.balance || "0");
                  const isOver = !!c.credit_limit && D(c.credit_limit).gt(0) && bal.gt(D(c.credit_limit));
                  const isDue = bal.gt(0);
                  return (
                    <TableRow key={c.id} className="border-b border-border/40 text-xs transition-colors hover:bg-muted/30 last:border-0">
                      <TableCell className="p-3 font-semibold text-foreground">
                        <span className="flex items-center gap-2">
                          {c.name}
                          {!c.is_active && <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">موقوف</Badge>}
                        </span>
                      </TableCell>
                      <TableCell className="num p-3 text-xs text-muted-foreground" dir="ltr">{c.phone ?? "—"}</TableCell>
                      <TableCell className="num p-3 font-bold">
                        <span className={isDue ? "text-destructive-ink" : "text-muted-foreground"}>{moneyEGP(c.balance)}</span>
                      </TableCell>
                      <TableCell className="num hidden p-3 text-xs text-muted-foreground sm:table-cell">
                        {c.credit_limit ? moneyEGP(c.credit_limit) : "غير محدد"}
                      </TableCell>
                      <TableCell className="p-3 text-center">
                        {isOver ? (
                          <Badge variant="destructive" className="h-5 gap-1 px-2 text-[10px] font-bold">
                            <ShieldAlert className="size-3" /> تجاوز السقف
                          </Badge>
                        ) : isDue ? (
                          <Badge variant="warning" className="h-5 px-2 text-[10px] font-medium">عليه مستحق</Badge>
                        ) : (
                          <Badge variant="success" className="h-5 px-2 text-[10px] font-medium">خالص</Badge>
                        )}
                      </TableCell>
                      <TableCell className="p-3 text-end">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" className="h-8 gap-1.5 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                                  onClick={() => { sound.click(); setLedgerFor(c); setLedgerPage(1); }}>
                            <FileText className="size-3.5" /> كشف حساب
                          </Button>
                          {can("customers") && (
                            <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل ${c.name}`} onClick={() => openForm(c)}>
                              <Pencil className="size-3.5" />
                            </Button>
                          )}
                          {manageMoney && (
                            <>
                              <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تسوية رصيد ${c.name}`}
                                      onClick={() => { setBalanceFor(c); setNewBalance(c.balance); setBalanceNote(""); }}>
                                <Scale className="size-3.5" />
                              </Button>
                              <Button variant="ghost" size="icon" className="size-8 px-0!" disabled={setActive.isPending}
                                      onClick={() => setActive.mutate(c)} aria-label={c.is_active ? `إيقاف ${c.name}` : `تفعيل ${c.name}`}>
                                <Power className="size-3.5" />
                              </Button>
                              <Button variant="ghost" size="icon" className="size-8 px-0! text-rose-500" aria-label={`حذف ${c.name}`}
                                      onClick={() => setRemoving(c)}>
                                <Trash2 className="size-3.5" />
                              </Button>
                            </>
                          )}
                          {can("customers") && c.is_active && (
                            <Button size="sm" variant={isDue ? "default" : "outline"} className="h-8 gap-1.5 px-2.5 text-xs font-semibold"
                                    onClick={() => {
                                      sound.click();
                                      setPayFor(c);
                                      setPayAmount(isDue ? c.balance : "");
                                      setPaySource("");
                                      setPayClientId(newClientId());
                                    }}>
                              <HandCoins className="size-3.5" /> {isDue ? "تحصيل دفعة" : "دفعة مقدمة"}
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {(page > 0 || customers.length === PAGE_SIZE) && (
        <div className="flex items-center justify-center gap-3 text-xs">
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="الصفحة السابقة">
            <ChevronRight className="size-4" />
          </Button>
          <span className="num text-muted-foreground">
            صفحة {page + 1}{s ? ` من ${Math.max(1, Math.ceil(s.total / PAGE_SIZE))}` : ""}
          </span>
          <Button variant="outline" size="sm" disabled={customers.length < PAGE_SIZE} onClick={() => setPage(page + 1)} aria-label="الصفحة التالية">
            <ChevronLeft className="size-4" />
          </Button>
        </div>
      )}

      {/* Create / edit */}
      <Modal open={!!formFor} onClose={() => setFormFor(null)} title={formFor === "new" ? "إضافة عميل جديد" : "تعديل بيانات العميل"}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!save.isPending && form.name.trim() && !missing.length) save.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <RecordFormFields
            record="customer"
            required={["name"]}
            wide={["address"]}
            extra={extra}
            onExtra={setExtra}
            builtin={{
              name: (
                <Input id="f-customer-name" autoFocus maxLength={128} value={form.name}
                       onChange={(e) => setForm({ ...form, name: e.target.value })}
                       placeholder="مثال: شركة النصر للمقاولات أو الأستاذ محمد علي" required />
              ),
              phone: (
                <Input id="f-customer-phone" className="num text-xs" dir="ltr" maxLength={32} placeholder="01012345678" value={form.phone}
                       onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              ),
              credit_limit: (
                <Input id="f-customer-credit_limit" className="num text-xs" inputMode="decimal" placeholder={formFor === "new" ? "فارغ: الحد الافتراضي للمنشأة" : "فارغ: بلا حد"} value={form.credit_limit}
                       onChange={(e) => setForm({ ...form, credit_limit: e.target.value })} />
              ),
              address: <Input id="f-customer-address" maxLength={500} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />,
            }}
          />
          {missing.length > 0 && <p className="text-xs text-muted-foreground">حقول مطلوبة: {missing.join("، ")}</p>}
          {formFor === "new" && manageMoney && (
            <p className="text-[11px] text-muted-foreground">الرصيد الافتتاحي يُسجَّل بعد الحفظ من زر «تسوية الرصيد».</p>
          )}
          {save.isError && <ErrorBox message={(save.error as Error).message} />}
          <Button type="submit" className="w-full h-10 font-bold" disabled={save.isPending || !form.name.trim() || missing.length > 0}>
            {save.isPending ? <Spinner /> : "حفظ"}
          </Button>
        </form>
      </Modal>

      {/* Opening balance or correction */}
      <Modal open={!!balanceFor} onClose={() => setBalanceFor(null)} title={`تسوية رصيد — ${balanceFor?.name ?? ""}`}>
        <form className="flex flex-col gap-4"
              onSubmit={(e) => { e.preventDefault(); if (!setBalance.isPending && newBalance !== "") setBalance.mutate(); }}>
          <p className="text-xs text-muted-foreground leading-relaxed">
            أدخل الرصيد الصحيح للعميل. يُسجَّل الفرق تسويةً (أو رصيداً افتتاحياً لعميل بلا حركات) ويظهر في كشف الحساب، ولا يُستبدل الرصيد
            دون أثر. تخفيض الرصيد إعدام لدين.
          </p>
          <div className="rounded-xl border border-border/80 bg-muted/30 p-3 text-xs">
            الرصيد الحالي: <strong className="num">{moneyEGP(balanceFor?.balance ?? 0)}</strong>
          </div>
          <div>
            <label htmlFor="new-balance" className="mb-1.5 block text-xs font-semibold">الرصيد الصحيح (ج.م) *</label>
            <Input id="new-balance" className="num text-lg font-bold" inputMode="decimal" value={newBalance} onChange={(e) => setNewBalance(e.target.value)} />
          </div>
          <div>
            <label htmlFor="balance-note" className="mb-1.5 block text-xs font-semibold">السبب</label>
            <Input id="balance-note" maxLength={500} value={balanceNote} onChange={(e) => setBalanceNote(e.target.value)} />
          </div>
          {setBalance.isError && <ErrorBox message={(setBalance.error as Error).message} />}
          <Button type="submit" className="w-full h-10 font-bold" disabled={setBalance.isPending || newBalance === ""}>
            {setBalance.isPending ? <Spinner /> : "تسجيل التسوية"}
          </Button>
        </form>
      </Modal>

      {/* Collect a payment */}
      <Modal open={!!payFor} onClose={() => setPayFor(null)} title={`تحصيل دفعة — ${payFor?.name ?? ""}`}>
        <form onSubmit={(e) => { e.preventDefault(); if (!pay.isPending && payAmount) pay.mutate(); }} className="flex flex-col gap-4">
          <div className="rounded-xl border border-border/80 bg-muted/30 p-3 text-xs">
            <span className="text-muted-foreground">الرصيد المستحق القائم: </span>
            <strong className="num text-sm font-bold text-destructive-ink">{moneyEGP(payFor?.balance ?? 0)}</strong>
          </div>
          <div>
            <label htmlFor="pay-amount" className="mb-1.5 block text-xs font-semibold text-foreground">المبلغ المحصّل (ج.م) *</label>
            <Input id="pay-amount" autoFocus className="num text-lg font-bold" inputMode="decimal" placeholder="0.00" value={payAmount}
                   onChange={(e) => setPayAmount(e.target.value)} required />
          </div>
          <div>
            <label htmlFor="pay-source" className="mb-1.5 block text-xs font-semibold text-foreground">استُلم المبلغ في</label>
            <PaySourceSelect id="pay-source" value={paySource} onChange={setPaySource} emptyLabel="درج ورديتي المفتوحة (نقدي)" />
            <p className="mt-1 text-[11px] text-muted-foreground">بدون وردية مفتوحة اختر الخزنة أو الحساب البنكي أو المحفظة التي استلمت المبلغ.</p>
          </div>
          {pay.isError && <ErrorBox message={(pay.error as Error).message} />}
          <Button type="submit" className="w-full h-10 font-bold" disabled={pay.isPending || !payAmount}>
            {pay.isPending ? <Spinner /> : "تأكيد تسجيل الدفعة"}
          </Button>
        </form>
      </Modal>

      {/* Statement */}
      <Modal open={!!ledgerFor} onClose={() => setLedgerFor(null)} title={`كشف حساب العميل — ${ledgerFor?.name ?? ""}`} wide>
        {ledger.isLoading ? (
          <div className="grid place-items-center p-8"><Spinner /></div>
        ) : ledger.isError ? (
          <ErrorBox message={(ledger.error as Error).message} onRetry={() => ledger.refetch()} />
        ) : !ledger.data?.items.length ? (
          <Empty text="لا توجد حركات مسجلة" hint="لم تتم حركات بيع آجل أو دفعات لهذا العميل بعد" />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="overflow-hidden rounded-xl border border-border/80">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-b border-border/80 bg-muted/40 text-[11px] font-semibold text-muted-foreground">
                      <TableHead className="p-3 text-start">التاريخ والوقت</TableHead>
                      <TableHead className="p-3 text-start">البيان</TableHead>
                      <TableHead className="p-3 text-start">مدين (+)</TableHead>
                      <TableHead className="p-3 text-start">دائن (−)</TableHead>
                      <TableHead className="p-3 text-start">الرصيد</TableHead>
                      {canReverse && <TableHead className="p-3" />}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {ledger.data.items.map((l) => (
                      <TableRow key={l.id} className="border-b border-border/40 text-xs hover:bg-muted/30 last:border-0">
                        <TableCell className="num p-3 text-xs text-muted-foreground">{dateTime(l.date)}</TableCell>
                        <TableCell className="p-3 font-medium text-foreground">
                          {LEDGER_LABEL[l.type] ?? l.type} <span className="num text-muted-foreground">#{l.ref}</span>
                          {l.note ? <span className="text-muted-foreground"> — {l.note}</span> : null}
                        </TableCell>
                        <TableCell className="num p-3 font-bold text-destructive-ink">{l.debit ? moneyEGP(l.debit) : "—"}</TableCell>
                        <TableCell className="num p-3 font-bold text-emerald-600 dark:text-emerald-400">{l.credit ? moneyEGP(l.credit) : "—"}</TableCell>
                        <TableCell className="num p-3 font-bold">{moneyEGP(l.balance)}</TableCell>
                        {canReverse && (
                          <TableCell className="p-3 text-end">
                            {l.can_reverse && (
                              <Button variant="ghost" size="sm" className="h-7 gap-1 text-[11px] text-rose-600"
                                      onClick={() => { setReversing(l); setReverseReason(""); reverse.reset(); }}>
                                <Undo2 className="size-3.5" /> عكس
                              </Button>
                            )}
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
            {ledger.data.pages > 1 && (
              <div className="flex items-center justify-center gap-3 text-xs">
                <Button variant="outline" size="sm" disabled={ledgerPage <= 1} onClick={() => setLedgerPage(ledgerPage - 1)} aria-label="الأحدث">
                  <ChevronRight className="size-4" />
                </Button>
                <span className="num text-muted-foreground">صفحة {ledgerPage} من {ledger.data.pages} ({ledger.data.total} حركة)</span>
                <Button variant="outline" size="sm" disabled={ledgerPage >= ledger.data.pages} onClick={() => setLedgerPage(ledgerPage + 1)} aria-label="الأقدم">
                  <ChevronLeft className="size-4" />
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Reverse a receipt into a safe or wallet */}
      <Modal open={!!reversing} onClose={() => setReversing(null)} title="عكس دفعة">
        <form className="flex flex-col gap-4"
              onSubmit={(e) => { e.preventDefault(); if (!reverse.isPending && reverseReason.trim().length >= 3) reverse.mutate(); }}>
          <p className="text-xs text-muted-foreground leading-relaxed">
            يخرج مبلغ <strong className="num text-foreground">{moneyEGP(reversing?.credit ?? 0)}</strong> من الخزنة أو المحفظة التي استلمته،
            ويعود مستحقاً على العميل، ويُعكس قيده. تبقى الدفعة وعكسها في الكشف.
          </p>
          <div>
            <label htmlFor="reverse-reason" className="mb-1.5 block text-xs font-semibold">السبب *</label>
            <Input id="reverse-reason" autoFocus maxLength={500} value={reverseReason} onChange={(e) => setReverseReason(e.target.value)} />
          </div>
          {reverse.isError && <ErrorBox message={(reverse.error as Error).message} />}
          <Button type="submit" variant="danger" className="w-full h-10 font-bold" disabled={reverse.isPending || reverseReason.trim().length < 3}>
            {reverse.isPending ? <Spinner /> : "تأكيد العكس"}
          </Button>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing)}
        title={`حذف ${removing?.name ?? ""}`}
        message="يُحذف العميل فقط إذا لم تكن له أي حركة. العميل الذي له حركات يُوقف بدلاً من حذفه."
        confirmLabel="حذف"
      />
    </div>
  );
}
