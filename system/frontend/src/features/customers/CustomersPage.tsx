import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  HandCoins,
  Plus,
  Power,
  Search,
  ShieldAlert,
  UserCheck,
  Users,
} from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { Badge } from "@/components/kit/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { api } from "@/lib/api";
import { D, dateTime, moneyEGP } from "@/lib/format";
import { Button, Card, Empty, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { sound } from "@/lib/sound";
import { RecordFormFields, cleanExtra, missingRequired, useRecordForm, type ExtraValues } from "@app/framework/forms";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";

interface Customer {
  id: string;
  name: string;
  phone: string | null;
  balance: string;
  credit_limit: string | null;
  is_active: boolean;
}

/** One line of GET /customers/{id}/ledger (the last element is a pagination marker). */
interface LedgerEntry {
  type: "invoice" | "return" | "payment" | "opening" | "adjustment";
  ref: string;
  amount: number;
  date: string;
  note?: string | null;
}

const LEDGER_LABEL: Record<LedgerEntry["type"], string> = {
  invoice: "فاتورة آجلة",
  return: "مرتجع",
  payment: "دفعة",
  opening: "رصيد افتتاحي",
  adjustment: "تسوية رصيد",
};

/** Whether a ledger line raises (debit) or lowers (credit) what the customer owes, and by how much. */
function ledgerSides(l: LedgerEntry): { debit: number | null; credit: number | null } {
  if (l.type === "invoice") return { debit: l.amount, credit: null };
  if (l.type === "return" || l.type === "payment") return { debit: null, credit: l.amount };
  return l.amount >= 0 ? { debit: l.amount, credit: null } : { debit: null, credit: -l.amount };
}

export default function CustomersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", credit_limit: "", address: "" });
  const [extra, setExtra] = useState<ExtraValues>({});
  const layout = useRecordForm("customer");
  const missing = missingRequired(layout.data, extra);
  const [ledgerFor, setLedgerFor] = useState<Customer | null>(null);
  const [payFor, setPayFor] = useState<Customer | null>(null);
  const [payAmount, setPayAmount] = useState("");
  const [paySource, setPaySource] = useState("");
  const [showInactive, setShowInactive] = useState(false);

  const list = useQuery({
    queryKey: ["customers", search, showInactive],
    queryFn: () =>
      api.get<Customer[]>("/customers", { search: search.trim() || undefined, include_inactive: showInactive ? "true" : undefined }),
  });

  const ledger = useQuery({
    queryKey: ["customer-ledger", ledgerFor?.id],
    queryFn: async () => {
      const rows = await api.get<(LedgerEntry | { __pagination: unknown })[]>(`/customers/${ledgerFor!.id}/ledger`);
      return rows.filter((r): r is LedgerEntry => !("__pagination" in r));
    },
    enabled: !!ledgerFor,
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/customers", {
        name: form.name,
        phone: form.phone || null,
        credit_limit: form.credit_limit ? D(form.credit_limit).toNumber() : null,
        address: form.address.trim() || null,
        extra: cleanExtra(extra),
      }),
    onSuccess: () => {
      sound.success();
      setCreating(false);
      setForm({ name: "", phone: "", credit_limit: "", address: "" });
      setExtra({});
      qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: () => sound.error(),
  });

  const { toast } = useToast();
  const pay = useMutation({
    mutationFn: () =>
      api.post(`/customers/${payFor!.id}/payments`, { amount: D(payAmount).toNumber(), method: "cash", ...sourceFields(paySource) }),
    onSuccess: () => {
      sound.success();
      setPayFor(null);
      setPayAmount("");
      setPaySource("");
      qc.invalidateQueries({ queryKey: ["safes"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
      toast("success", "تم تسجيل دفعة العميل بنجاح");
      qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: () => sound.error(),
  });

  const setActive = useMutation({
    mutationFn: (c: Customer) => api.post(`/customers/${c.id}/${c.is_active ? "deactivate" : "activate"}`),
    onSuccess: (_d, c) => {
      sound.success();
      toast("success", c.is_active ? "تم إيقاف العميل" : "تمت إعادة تفعيل العميل");
      qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (e) => {
      sound.error();
      toast("error", (e as Error).message);
    },
  });

  // Calculate Accounts Receivable (AR) KPIs
  const customers = list.data ?? [];
  const totalMarketDebt = customers.reduce(
    (acc, c) => acc + Math.max(0, parseFloat(c.balance || "0")),
    0,
  );
  const debtorCount = customers.filter((c) => parseFloat(c.balance || "0") > 0).length;
  const overLimitCount = customers.filter((c) => {
    const bal = parseFloat(c.balance || "0");
    const lim = parseFloat(c.credit_limit || "0");
    return lim > 0 && bal > lim;
  }).length;
  const totalCustomers = customers.length;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight">
            <Users className="size-6 text-primary" aria-hidden />
            العملاء والذمم المدينة (AR)
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            إدارة الحسابات الجارية للعملاء، متابعة المديونيات، وتحصيل الدفعات
          </p>
        </div>

        <Button
          onClick={() => {
            sound.click();
            setCreating(true);
          }}
          className="gap-2 font-semibold"
        >
          <Plus className="size-4" />
          عميل جديد
        </Button>
      </div>

      {/* AR Financial Summary Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-4">
          <p className="text-[11px] font-medium text-muted-foreground">إجمالي مديونيات السوق</p>
          <p className="num mt-1 text-xl font-bold tracking-tight text-destructive-ink">
            {moneyEGP(totalMarketDebt)}
          </p>
          <p className="mt-1 text-[10px] text-muted-foreground/80">مستحقات آجلة لدى العملاء</p>
        </Card>

        <Card className="p-4">
          <p className="text-[11px] font-medium text-muted-foreground">العملاء المدينون</p>
          <div className="mt-1 flex items-baseline gap-1.5">
            <p className="num text-xl font-bold tracking-tight text-foreground">
              {debtorCount}
            </p>
            <span className="text-[11px] text-muted-foreground">
              من أصل <span className="num font-semibold">{totalCustomers}</span>
            </span>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground/80">عليهم أرصدة قائمة للدفع</p>
        </Card>

        <Card className={`p-4 ${overLimitCount > 0 ? "border-amber-500/40 bg-amber-500/5 dark:bg-amber-500/10" : ""}`}>
          <p className="text-[11px] font-medium text-muted-foreground">تجاوز الحد الائتماني</p>
          <div className="mt-1 flex items-center gap-2">
            <p className={`num text-xl font-bold tracking-tight ${overLimitCount > 0 ? "text-amber-600 dark:text-amber-400" : "text-foreground"}`}>
              {overLimitCount}
            </p>
            {overLimitCount > 0 && (
              <Badge variant="warning" className="h-5 px-1.5 text-[10px] font-bold">
                تنبيه مخاطر
              </Badge>
            )}
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground/80">تخطوا سقف الائتمان المسموح</p>
        </Card>

        <Card className="p-4">
          <p className="text-[11px] font-medium text-muted-foreground">إجمالي العملاء المسجلين</p>
          <p className="num mt-1 text-xl font-bold tracking-tight text-foreground">
            {totalCustomers}
          </p>
          <p className="mt-1 flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
            <UserCheck className="size-3" />
            بيانات جهات الاتصال مكتملة
          </p>
        </Card>
      </div>

      {/* Search Bar */}
      <div className="flex flex-wrap items-center gap-3">
      <div className="relative flex-1 rounded-xl border border-border/80 bg-card p-2.5 shadow-xs">
        <Search className="absolute start-5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="ابحث باسم العميل أو رقم الهاتف…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ps-10 text-xs border-0 bg-transparent shadow-none focus-visible:ring-0"
        />
        {search && (
          <button
            onClick={() => {
              sound.click();
              setSearch("");
            }}
            className="absolute end-4 top-1/2 -translate-y-1/2 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="مسح البحث"
          >
            ✕
          </button>
        )}
      </div>
      <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
        إظهار العملاء الموقوفين
      </label>
      </div>

      {/* Customers List Table */}
      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
          <Skeleton className="h-10 w-full rounded-lg" />
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : customers.length === 0 ? (
        <Empty
          text="لا يوجد عملاء مطابقون"
          hint={search ? "جرّب البحث بكلمة أخرى" : "اضغط على «عميل جديد» لإضافة أول عميل إلى دليلك"}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-xs">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-b border-border/80 bg-muted/40 text-[11px] font-semibold text-muted-foreground">
                  <TableHead className="p-3 text-start">العميل</TableHead>
                  <TableHead className="p-3 text-start">الهاتف</TableHead>
                  <TableHead className="p-3 text-start">الرصيد القائم (مدين)</TableHead>
                  <TableHead className="hidden p-3 text-start sm:table-cell">الحد الائتماني</TableHead>
                  <TableHead className="p-3 text-center">حالة الائتمان</TableHead>
                  <TableHead className="p-3 text-end">الإجراءات</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {customers.map((c) => {
                  const bal = parseFloat(c.balance || "0");
                  const lim = parseFloat(c.credit_limit || "0");
                  const isOver = lim > 0 && bal > lim;
                  const isDue = bal > 0;

                  return (
                    <TableRow
                      key={c.id}
                      className="border-b border-border/40 text-xs transition-colors hover:bg-muted/30 last:border-0"
                    >
                      <TableCell className="p-3 font-semibold text-foreground">
                        <span className="flex items-center gap-2">
                          {c.name}
                          {!c.is_active && (
                            <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">موقوف</Badge>
                          )}
                        </span>
                      </TableCell>

                      <TableCell className="num p-3 text-xs text-muted-foreground" dir="ltr">
                        {c.phone ?? "—"}
                      </TableCell>

                      <TableCell className="num p-3 font-bold">
                        <span className={isDue ? "text-destructive-ink" : "text-muted-foreground"}>
                          {moneyEGP(c.balance)}
                        </span>
                      </TableCell>

                      <TableCell className="num hidden p-3 text-xs text-muted-foreground sm:table-cell">
                        {c.credit_limit ? moneyEGP(c.credit_limit) : "غير محدد"}
                      </TableCell>

                      <TableCell className="p-3 text-center">
                        {isOver ? (
                          <Badge variant="destructive" className="h-5 gap-1 px-2 text-[10px] font-bold">
                            <ShieldAlert className="size-3" />
                            تجاوز السقف
                          </Badge>
                        ) : isDue ? (
                          <Badge variant="warning" className="h-5 px-2 text-[10px] font-medium">
                            عليه مستحق
                          </Badge>
                        ) : (
                          <Badge variant="success" className="h-5 px-2 text-[10px] font-medium">
                            خالص
                          </Badge>
                        )}
                      </TableCell>

                      <TableCell className="p-3 text-end">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            className="h-8 gap-1.5 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                            onClick={() => {
                              sound.click();
                              setLedgerFor(c);
                            }}
                          >
                            <FileText className="size-3.5" />
                            كشف حساب
                          </Button>

                          <Button
                            variant="ghost"
                            className="h-8 gap-1.5 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                            onClick={() => setActive.mutate(c)}
                            disabled={setActive.isPending}
                            aria-label={c.is_active ? `إيقاف ${c.name}` : `تفعيل ${c.name}`}
                          >
                            <Power className="size-3.5" />
                            {c.is_active ? "إيقاف" : "تفعيل"}
                          </Button>

                          {isDue ? (
                            <Button
                              size="sm"
                              className="h-8 gap-1.5 px-2.5 text-xs font-semibold shadow-xs"
                              onClick={() => {
                                sound.click();
                                setPayFor(c);
                                setPayAmount(bal > 0 ? c.balance : "");
                              }}
                            >
                              <HandCoins className="size-3.5" />
                              تحصيل دفعة
                            </Button>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 gap-1.5 px-2.5 text-xs text-muted-foreground hover:text-foreground"
                              onClick={() => {
                                sound.click();
                                setPayFor(c);
                                setPayAmount("");
                              }}
                            >
                              <HandCoins className="size-3.5" />
                              دفعة مقدمة
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

      {/* Create Customer Dialog */}
      <Modal open={creating} onClose={() => setCreating(false)} title="إضافة عميل جديد">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!create.isPending && form.name && !missing.length) create.mutate();
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
                <Input
                  id="f-customer-name"
                  autoFocus
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="مثال: شركة النصر للمقاولات أو الأستاذ محمد علي"
                  required
                />
              ),
              phone: (
                <Input id="f-customer-phone" className="num text-xs" dir="ltr" placeholder="01012345678" value={form.phone}
                       onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              ),
              credit_limit: (
                <Input id="f-customer-credit_limit" className="num text-xs" inputMode="decimal" placeholder="مثال: 50000" value={form.credit_limit}
                       onChange={(e) => setForm({ ...form, credit_limit: e.target.value })} />
              ),
              address: <Input id="f-customer-address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />,
            }}
          />
          {missing.length > 0 && <p className="text-xs text-muted-foreground">حقول مطلوبة: {missing.join("، ")}</p>}

          {create.isError && <ErrorBox message={(create.error as Error).message} />}

          <Button
            type="submit"
            className="w-full h-10 font-bold"
            disabled={create.isPending || !form.name.trim() || missing.length > 0}
          >
            {create.isPending ? <Spinner /> : "حفظ العميل"}
          </Button>
        </form>
      </Modal>

      {/* Collect Payment Dialog */}
      <Modal open={!!payFor} onClose={() => setPayFor(null)} title={`تحصيل دفعة — ${payFor?.name ?? ""}`}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!pay.isPending && payAmount) pay.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <div className="rounded-xl border border-border/80 bg-muted/30 p-3 text-xs">
            <span className="text-muted-foreground">الرصيد المستحق القائم: </span>
            <strong className="num text-sm font-bold text-destructive-ink">
              {moneyEGP(payFor?.balance ?? 0)}
            </strong>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-foreground">
              المبلغ المحصّل (ج.م) *
            </label>
            <Input
              autoFocus
              className="num text-lg font-bold"
              inputMode="decimal"
              placeholder="0.00"
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              required
            />
          </div>

          <div>
            <label htmlFor="pay-source" className="mb-1.5 block text-xs font-semibold text-foreground">
              استُلم المبلغ في
            </label>
            <PaySourceSelect
              id="pay-source"
              value={paySource}
              onChange={setPaySource}
              emptyLabel="درج ورديتي المفتوحة (نقدي)"
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              بدون وردية مفتوحة اختر الخزنة أو الحساب البنكي أو المحفظة التي استلمت المبلغ.
            </p>
          </div>

          {pay.isError && <ErrorBox message={(pay.error as Error).message} />}

          <Button
            type="submit"
            className="w-full h-10 font-bold"
            disabled={pay.isPending || !payAmount}
          >
            {pay.isPending ? <Spinner /> : "تأكيد تسجيل الدفعة"}
          </Button>
        </form>
      </Modal>

      {/* Customer Account Ledger Dialog */}
      <Modal
        open={!!ledgerFor}
        onClose={() => setLedgerFor(null)}
        title={`كشف حساب العميل — ${ledgerFor?.name ?? ""}`}
        wide
      >
        {ledger.isLoading ? (
          <div className="grid place-items-center p-8">
            <Spinner />
          </div>
        ) : ledger.isError ? (
          <ErrorBox message={(ledger.error as Error).message} />
        ) : !ledger.data?.length ? (
          <Empty text="لا توجد حركات مسجلة" hint="لم تتم حركات بيع أو دفعات لهذا العميل بعد" />
        ) : (
          <div className="overflow-hidden rounded-xl border border-border/80">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-b border-border/80 bg-muted/40 text-[11px] font-semibold text-muted-foreground">
                    <TableHead className="p-3 text-start">التاريخ والوقت</TableHead>
                    <TableHead className="p-3 text-start">البيان / الفاتورة</TableHead>
                    <TableHead className="p-3 text-start">مدين (+)</TableHead>
                    <TableHead className="p-3 text-start">دائن / مسدد (−)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ledger.data.map((l, i) => {
                    const { debit, credit } = ledgerSides(l);
                    return (
                      <TableRow
                        key={`${l.type}-${l.ref}-${i}`}
                        className="border-b border-border/40 text-xs hover:bg-muted/30 last:border-0"
                      >
                        <TableCell className="num p-3 text-xs text-muted-foreground">
                          {dateTime(l.date)}
                        </TableCell>
                        <TableCell className="p-3 font-medium text-foreground">
                          {LEDGER_LABEL[l.type] ?? l.type} <span className="num text-muted-foreground">#{l.ref}</span>
                          {l.note ? <span className="text-muted-foreground"> — {l.note}</span> : null}
                        </TableCell>
                        <TableCell className="num p-3 font-bold text-destructive-ink">
                          {debit != null ? moneyEGP(debit) : "—"}
                        </TableCell>
                        <TableCell className="num p-3 font-bold text-emerald-600 dark:text-emerald-400">
                          {credit != null ? moneyEGP(credit) : "—"}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
