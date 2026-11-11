/**
 * Pharmacy: the formulary, batches and expiry, prescriptions and the controlled-drug register.
 *
 * One system with the rest of the ERP (ADR-006 phase 4): drugs are products with the pharmacy's
 * fields, their stock is kept in batches (first expiry first out), and dispensing is a sale at
 * the POS, which records the prescription and the controlled-drug log.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, FileText, Pill, Plus, ShieldAlert, ShoppingCart, Truck } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { dateTime, money } from "@/lib/format";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { useTenantNav } from "@app/lib/tenant";

interface Summary {
  drugs: number; prescription_only: number; controlled: number;
  expired_batches: number; expiring_batches: number; prescriptions_today: number;
}
interface Drug {
  id: string; trade_name: string; scientific_name: string | null; dosage_form: string | null; strength: string | null;
  unit_price: string; requires_prescription: boolean; is_controlled: boolean;
  sellable_qty: string; stock_qty: string; nearest_expiry: string | null;
}
interface Lot {
  id: string; product_id: string; trade_name: string; scientific_name: string | null; warehouse_name: string;
  batch_number: string; expiry_date: string | null; quantity_on_hand: string; status: "active" | "quarantined";
  days_left: number | null;
}
interface Prescription {
  id: string; rx_number: string; patient_name: string; doctor_name: string; total_amount: number;
  dispensed_at: string; invoice_number: string | null;
}
interface ControlledEntry {
  id: string; logged_at: string; trade_name: string | null; batch_number: string; quantity: number;
  patient_name: string; patient_national_id: string; prescriber_doctor: string; invoice_number: string | null;
}
interface Warehouse { id: string; name: string }

type Tab = "formulary" | "batches" | "prescriptions" | "controlled";
const TABS: { key: Tab; label: string }[] = [
  { key: "formulary", label: "الدليل الدوائي" },
  { key: "batches", label: "التشغيلات والصلاحية" },
  { key: "prescriptions", label: "الروشتات" },
  { key: "controlled", label: "سجل الأدوية المراقبة" },
];
const FORMS = ["أقراص", "كبسولات", "شراب", "حقن", "مرهم", "قطرة", "بخاخ", "لبوس", "أكياس", "أخرى"];

function DrugBadges({ d }: { d: { requires_prescription: boolean; is_controlled: boolean } }) {
  if (d.is_controlled) return <Badge tone="danger"><ShieldAlert size={11} aria-hidden /> مراقب</Badge>;
  if (d.requires_prescription) return <Badge tone="warning"><FileText size={11} aria-hidden /> روشتة</Badge>;
  return null;
}

function ExpiryCell({ date, days }: { date: string | null; days?: number | null }) {
  if (!date) return <span className="text-muted-foreground">—</span>;
  // Whole calendar days, like the server's (expiry_date - CURRENT_DATE).
  const today = new Date().toISOString().slice(0, 10);
  const left = days ?? Math.round((Date.parse(date) - Date.parse(today)) / 86_400_000);
  const tone = left < 0 ? "text-destructive font-bold" : left <= 90 ? "text-warning font-bold" : "";
  return (
    <span className={`num ${tone}`}>
      {date}
      {left < 0 ? " · منتهية" : left <= 90 ? ` · ${left} يوم` : ""}
    </span>
  );
}

function TableSkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
      {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-11 w-full" />)}
    </div>
  );
}

export default function PharmacyPage() {
  const [tab, setTab] = useState<Tab>("formulary");
  const navigate = useNavigate();
  const { tenantTo } = useTenantNav();
  const summary = useQuery({ queryKey: ["pharmacy", "summary"], queryFn: () => api.get<Summary>("/pharmacy/summary") });
  const s = summary.data;

  const cards = [
    { label: "أدوية في الدليل", value: s?.drugs, icon: Pill },
    { label: "تُصرف بروشتة", value: s?.prescription_only, icon: FileText },
    { label: "مراقبة (جدول)", value: s?.controlled, icon: ShieldAlert },
    { label: "تشغيلات منتهية", value: s?.expired_batches, icon: AlertTriangle, danger: !!s?.expired_batches },
    { label: "تنتهي خلال 90 يومًا", value: s?.expiring_batches, icon: AlertTriangle, warn: !!s?.expiring_batches },
    { label: "روشتات اليوم", value: s?.prescriptions_today, icon: FileText },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">الصيدلية</h1>
          <p className="text-sm text-muted-foreground">الصرف يتم من نقطة البيع: الدواء يُخصم من الأقرب انتهاءً، وتُسجَّل الروشتة مع الفاتورة.</p>
        </div>
        <Button onClick={() => navigate(tenantTo("/pos"))}><ShoppingCart size={16} /> صرف من نقطة البيع</Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {cards.map((c) => (
          <div key={c.label} className={`rounded-xl border p-3 ${c.danger ? "border-destructive/40 bg-destructive/5" : c.warn ? "border-warning/40 bg-warning/5" : "border-line bg-card"}`}>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground"><c.icon size={14} aria-hidden /> {c.label}</div>
            <div className="num mt-1 text-2xl font-bold">{summary.isLoading ? <Skeleton className="h-7 w-10" /> : (c.value ?? 0)}</div>
          </div>
        ))}
      </div>

      <div role="tablist" aria-label="أقسام الصيدلية" className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${tab === t.key ? "bg-primary text-primary-foreground" : "border border-line text-muted-foreground hover:text-foreground"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "formulary" && <Formulary />}
      {tab === "batches" && <Batches />}
      {tab === "prescriptions" && <Prescriptions />}
      {tab === "controlled" && <Controlled />}
    </div>
  );
}

function Formulary() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [search, setSearch] = useState("");
  const [altFor, setAltFor] = useState<Drug | null>(null);
  const [adding, setAdding] = useState(false);
  const empty = { trade_name: "", scientific_name: "", dosage_form: "أقراص", strength: "", barcode: "", unit_price: "", requires_prescription: false, is_controlled: false };
  const [form, setForm] = useState(empty);
  const drugs = useQuery({ queryKey: ["pharmacy", "drugs", search], queryFn: () => api.get<Drug[]>("/pharmacy/drugs", { search: search || undefined }) });
  const alts = useQuery({
    queryKey: ["pharmacy", "alts", altFor?.id],
    queryFn: () => api.get<{ alternatives: Drug[] }>(`/pharmacy/drugs/${altFor!.id}/alternatives`),
    enabled: !!altFor,
  });
  const create = useMutation({
    mutationFn: () => api.post("/pharmacy/drugs", { ...form, unit_price: form.unit_price || "0" }),
    onSuccess: () => {
      setAdding(false); setForm(empty); toast("success", "تمت إضافة الدواء");
      qc.invalidateQueries({ queryKey: ["pharmacy"] });
    },
  });

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="بحث في الدليل"
          placeholder="ابحث بالاسم التجاري أو العلمي أو الباركود"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <Button variant="outline" onClick={() => setAdding(true)}><Plus size={16} /> دواء جديد</Button>
      </div>
      {drugs.isLoading ? <TableSkeleton /> : drugs.isError ? (
        <ErrorBox message={(drugs.error as Error).message} onRetry={() => drugs.refetch()} />
      ) : !drugs.data?.length ? (
        <Empty text={search ? "لا توجد نتائج" : "لا توجد أدوية في الدليل بعد"} hint="الأدوية أصناف بتفاصيل دوائية (الاسم العلمي، التركيز، الروشتة)." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line bg-secondary/30 text-xs text-muted-foreground">
              <th className="p-3 text-start">الدواء</th>
              <th className="hidden p-3 text-start md:table-cell">الاسم العلمي</th>
              <th className="p-3 text-start">متاح للبيع</th>
              <th className="hidden p-3 text-start sm:table-cell">أقرب صلاحية</th>
              <th className="hidden p-3 text-start sm:table-cell">السعر</th>
              <th className="p-3" />
            </tr></thead>
            <tbody>
              {drugs.data.map((d) => {
                const blocked = Number(d.stock_qty) - Number(d.sellable_qty);
                return (
                  <tr key={d.id} className="border-b border-line/60 last:border-0 hover:bg-secondary/20">
                    <td className="p-3">
                      <div className="font-bold">{d.trade_name}</div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                        {[d.strength, d.dosage_form].filter(Boolean).join(" · ")} <DrugBadges d={d} />
                      </div>
                    </td>
                    <td className="hidden p-3 md:table-cell" dir="ltr">{d.scientific_name ?? "—"}</td>
                    <td className="p-3">
                      <span className="num font-bold">{Number(d.sellable_qty)}</span>
                      {blocked > 0 && <span className="num ms-1 text-xs text-destructive">(+{blocked} منتهي/محجوز)</span>}
                    </td>
                    <td className="hidden p-3 sm:table-cell"><ExpiryCell date={d.nearest_expiry} /></td>
                    <td className="num hidden p-3 sm:table-cell">{money(d.unit_price)}</td>
                    <td className="p-3">
                      <Button variant="outline" disabled={!d.scientific_name} onClick={() => setAltFor(d)}>البدائل</Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={!!altFor} onClose={() => setAltFor(null)} title={`بدائل ${altFor?.trade_name ?? ""}`}>
        <p className="mb-3 text-sm text-muted-foreground" dir="auto">نفس المادة الفعالة: {altFor?.scientific_name}</p>
        {alts.isLoading ? <TableSkeleton /> : !alts.data?.alternatives.length ? (
          <Empty text="لا توجد بدائل بنفس المادة الفعالة" />
        ) : (
          <ul className="divide-y divide-line">
            {alts.data.alternatives.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                <div><div className="font-bold">{a.trade_name}</div><div className="text-xs text-muted-foreground">{a.strength}</div></div>
                <div className="text-end">
                  <div className="num font-bold">{money(a.unit_price)}</div>
                  <div className="num text-xs text-muted-foreground">متاح {Number(a.sellable_qty)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Modal>

      <Modal open={adding} onClose={() => setAdding(false)} title="دواء جديد">
        <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (form.trade_name && !create.isPending) create.mutate(); }}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="text-sm">الاسم التجاري *<Input autoFocus value={form.trade_name} onChange={(e) => setForm({ ...form, trade_name: e.target.value })} /></label>
            <label className="text-sm">الاسم العلمي<Input dir="ltr" value={form.scientific_name} onChange={(e) => setForm({ ...form, scientific_name: e.target.value })} /></label>
            <label className="text-sm">الشكل الدوائي
              <Select value={form.dosage_form} onChange={(e) => setForm({ ...form, dosage_form: e.target.value })}>
                {FORMS.map((f) => <option key={f}>{f}</option>)}
              </Select>
            </label>
            <label className="text-sm">التركيز<Input dir="ltr" value={form.strength} onChange={(e) => setForm({ ...form, strength: e.target.value })} /></label>
            <label className="text-sm">الباركود<Input dir="ltr" value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value })} /></label>
            <label className="text-sm">سعر البيع<Input dir="ltr" inputMode="decimal" value={form.unit_price} onChange={(e) => setForm({ ...form, unit_price: e.target.value })} /></label>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.requires_prescription} onChange={(e) => setForm({ ...form, requires_prescription: e.target.checked })} /> يُصرف بروشتة
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.is_controlled} onChange={(e) => setForm({ ...form, is_controlled: e.target.checked })} /> مادة مراقبة (جدول): تتطلب الرقم القومي للمريض وترخيص الطبيب
          </label>
          {create.isError && <ErrorBox message={(create.error as Error).message} />}
          <Button type="submit" disabled={!form.trade_name || create.isPending}>{create.isPending ? <Spinner /> : "إضافة"}</Button>
        </form>
      </Modal>
    </section>
  );
}

function Batches() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [show, setShow] = useState<"all" | "attention">("attention");
  const [receiving, setReceiving] = useState(false);
  const lots = useQuery({ queryKey: ["pharmacy", "batches"], queryFn: () => api.get<Lot[]>("/pharmacy/batches") });
  const drugs = useQuery({ queryKey: ["pharmacy", "drugs", ""], queryFn: () => api.get<Drug[]>("/pharmacy/drugs"), enabled: receiving });
  const warehouses = useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<Warehouse[]>("/stock/warehouses"), enabled: receiving });
  const empty = { product_id: "", warehouse_id: "", batch_number: "", expiry_date: "", quantity: "", purchase_cost: "" };
  const [form, setForm] = useState(empty);
  const status = useMutation({
    mutationFn: (l: Lot) => api.post(`/modules/batches/${l.id}/status`, { status: l.status === "active" ? "quarantined" : "active" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pharmacy"] }),
  });
  const receive = useMutation({
    mutationFn: () => api.post("/pharmacy/batches", { ...form, purchase_cost: form.purchase_cost || "0" }),
    onSuccess: () => {
      setReceiving(false); setForm(empty); toast("success", "تم استلام التشغيلة");
      qc.invalidateQueries({ queryKey: ["pharmacy"] });
    },
  });
  const rows = (lots.data ?? []).filter((l) => show === "all" || (l.days_left ?? 9999) <= 90 || l.status !== "active");

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="radiogroup" aria-label="عرض التشغيلات" className="flex gap-2 text-sm">
          {([["attention", "تحتاج انتباهًا"], ["all", "كل التشغيلات"]] as const).map(([k, l]) => (
            <button key={k} role="radio" aria-checked={show === k} onClick={() => setShow(k)}
              className={`rounded-lg px-3 py-1.5 ${show === k ? "bg-secondary font-bold" : "text-muted-foreground"}`}>{l}</button>
          ))}
        </div>
        <Button variant="outline" onClick={() => setReceiving(true)}><Truck size={16} /> استلام تشغيلة</Button>
      </div>
      {lots.isLoading ? <TableSkeleton /> : lots.isError ? (
        <ErrorBox message={(lots.error as Error).message} onRetry={() => lots.refetch()} />
      ) : !rows.length ? (
        <Empty text={show === "attention" ? "لا توجد تشغيلات منتهية أو قريبة الانتهاء" : "لا توجد تشغيلات"} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line bg-secondary/30 text-xs text-muted-foreground">
              <th className="p-3 text-start">الدواء</th>
              <th className="p-3 text-start">التشغيلة</th>
              <th className="p-3 text-start">الصلاحية</th>
              <th className="p-3 text-start">الكمية</th>
              <th className="hidden p-3 text-start md:table-cell">الفرع</th>
              <th className="p-3" />
            </tr></thead>
            <tbody>
              {rows.map((l) => (
                <tr key={l.id} className="border-b border-line/60 last:border-0">
                  <td className="p-3 font-bold">{l.trade_name}</td>
                  <td className="num p-3" dir="ltr">{l.batch_number}</td>
                  <td className="p-3"><ExpiryCell date={l.expiry_date} days={l.days_left} /></td>
                  <td className="num p-3">{Number(l.quantity_on_hand)}</td>
                  <td className="hidden p-3 md:table-cell">{l.warehouse_name}</td>
                  <td className="p-3">
                    <Button variant="outline" disabled={status.isPending} onClick={() => status.mutate(l)}>
                      {l.status === "active" ? "حجز" : "إلغاء الحجز"}
                    </Button>
                    {l.status !== "active" && <span className="ms-2"><Badge tone="danger">محجوزة</Badge></span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={receiving} onClose={() => setReceiving(false)} title="استلام تشغيلة">
        <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (!receive.isPending) receive.mutate(); }}>
          <label className="text-sm">الدواء *
            <Select value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })} required>
              <option value="">— اختر —</option>
              {drugs.data?.map((d) => <option key={d.id} value={d.id}>{d.trade_name}</option>)}
            </Select>
          </label>
          <label className="text-sm">الفرع *
            <Select value={form.warehouse_id} onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })} required>
              <option value="">— اختر —</option>
              {warehouses.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </Select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm">رقم التشغيلة *<Input dir="ltr" value={form.batch_number} onChange={(e) => setForm({ ...form, batch_number: e.target.value })} required /></label>
            <label className="text-sm">تاريخ الصلاحية *<Input type="date" dir="ltr" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} required /></label>
            <label className="text-sm">الكمية *<Input dir="ltr" inputMode="decimal" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required /></label>
            <label className="text-sm">تكلفة الوحدة<Input dir="ltr" inputMode="decimal" value={form.purchase_cost} onChange={(e) => setForm({ ...form, purchase_cost: e.target.value })} /></label>
          </div>
          {receive.isError && <ErrorBox message={(receive.error as Error).message} />}
          <Button type="submit" disabled={receive.isPending || !form.product_id || !form.warehouse_id || !form.batch_number || !form.expiry_date || !form.quantity}>
            {receive.isPending ? <Spinner /> : "استلام"}
          </Button>
        </form>
      </Modal>
    </section>
  );
}

function Prescriptions() {
  const list = useQuery({ queryKey: ["pharmacy", "prescriptions"], queryFn: () => api.get<Prescription[]>("/pharmacy/prescriptions") });
  if (list.isLoading) return <TableSkeleton />;
  if (list.isError) return <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />;
  if (!list.data?.length) return <Empty text="لا توجد روشتات مصروفة بعد" hint="تُسجَّل الروشتة تلقائيًا عند بيع دواء يُصرف بروشتة من نقطة البيع." />;
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line bg-secondary/30 text-xs text-muted-foreground">
          <th className="p-3 text-start">الروشتة</th><th className="p-3 text-start">المريض</th>
          <th className="hidden p-3 text-start sm:table-cell">الطبيب</th><th className="p-3 text-start">الفاتورة</th>
          <th className="hidden p-3 text-start md:table-cell">التاريخ</th>
        </tr></thead>
        <tbody>
          {list.data.map((r) => (
            <tr key={r.id} className="border-b border-line/60 last:border-0">
              <td className="num p-3 font-bold" dir="ltr">{r.rx_number}</td>
              <td className="p-3">{r.patient_name}</td>
              <td className="hidden p-3 sm:table-cell">{r.doctor_name}</td>
              <td className="num p-3" dir="ltr">{r.invoice_number ?? "—"}</td>
              <td className="num hidden p-3 md:table-cell">{dateTime(r.dispensed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Controlled() {
  const list = useQuery({ queryKey: ["pharmacy", "controlled"], queryFn: () => api.get<ControlledEntry[]>("/pharmacy/controlled-log") });
  if (list.isLoading) return <TableSkeleton />;
  if (list.isError) return <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />;
  if (!list.data?.length) return <Empty text="لا توجد عمليات صرف لأدوية مراقبة" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line bg-secondary/30 text-xs text-muted-foreground">
          <th className="p-3 text-start">التاريخ</th><th className="p-3 text-start">الدواء</th>
          <th className="p-3 text-start">التشغيلة</th><th className="p-3 text-start">الكمية</th>
          <th className="p-3 text-start">المريض</th><th className="hidden p-3 text-start md:table-cell">الرقم القومي</th>
          <th className="hidden p-3 text-start md:table-cell">الطبيب</th><th className="hidden p-3 text-start sm:table-cell">الفاتورة</th>
        </tr></thead>
        <tbody>
          {list.data.map((c) => (
            <tr key={c.id} className="border-b border-line/60 last:border-0">
              <td className="num p-3">{dateTime(c.logged_at)}</td>
              <td className="p-3 font-bold">{c.trade_name ?? "—"}</td>
              <td className="num p-3" dir="ltr">{c.batch_number}</td>
              <td className="num p-3">{c.quantity}</td>
              <td className="p-3">{c.patient_name}</td>
              <td className="num hidden p-3 md:table-cell" dir="ltr">{c.patient_national_id}</td>
              <td className="hidden p-3 md:table-cell">{c.prescriber_doctor}</td>
              <td className="num hidden p-3 sm:table-cell" dir="ltr">{c.invoice_number ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
