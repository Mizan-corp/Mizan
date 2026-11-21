/**
 * PAGE CONTRACT
 * Page: التقارير (/reports)
 * User: المدير والمحاسب (reports؛ التقارير المالية بصلاحية reports:finance)
 * Purpose: المبيعات (يومي، شهري، الأكثر مبيعاً، حسب الكاشير، حسب حقل مخصص)، دفتر اليوم والدفتر الدوري،
 * والتقارير المالية: الأرباح، التدفق النقدي، أعمار الديون، ونظرة عامة على الشركة. كلها بفلاتر الفترة والفرع
 * (حيث يأخذها التقرير)، وتصدير وطباعة.
 */
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { CalendarRange, Download, Printer, Receipt } from "lucide-react";
import { api } from "@/lib/api";
import { downloadFile, printDocument } from "@app/lib/documents";
import { qty as fq } from "@/lib/format";
import { Money, Num, PageHeader, StatCard, TableShell } from "@/components/app/shared";
import { Button } from "@/components/kit/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/kit/card";
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/kit/chart";
import { Input, Select } from "@/components/ui";
import { Skeleton } from "@/components/kit/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/kit/tabs";
import { Empty, ErrorBox } from "@/components/ui";
import { useAuth } from "@/stores/auth";
import type { Range } from "@activities/general/modules/accounting/components/shared";
import { AgingView, CashFlowView, OverviewView, ProfitView } from "@activities/general/modules/reporting/components/FinanceReports";
import { DailyItemsView, PeriodicLedgerView } from "@activities/general/modules/reporting/components/LedgerReports";
import { monthToDate } from "@activities/general/modules/reporting/lib";
import { CustomFieldReport } from "./CustomFieldReport";

interface Warehouse { id: string; name: string }
// Sales figures are after every discount, without VAT, less the returns made in the period. Money
// comes as decimal strings (REP-15).
interface SalesTotals { total_sales: string; gross_sales: string; returns_total: string; invoice_count: number; returns_count: number }
interface DailyRow extends SalesTotals { date: string }
interface MonthlyRow extends SalesTotals { year: number; month: number }
interface TopProduct { product_id: string; product_name: string; unit: string | null; qty: number; revenue: string }
interface CashierRow { cashier_id: string; cashier_name: string; invoice_count: number; gross_sales: string; returns_total: string; total_sales: string }

const chartConfig = { revenue: { label: "الإيراد", color: "var(--chart-1)" } } satisfies ChartConfig;

// The local calendar day (toISOString would give the UTC day, wrong after midnight in Cairo).
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d); };

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

const TABS = [
  { key: "daily", label: "يومي", perm: "reports" },
  { key: "monthly", label: "شهري", perm: "reports" },
  { key: "top", label: "الأكثر مبيعاً", perm: "reports" },
  { key: "cashier", label: "حسب الكاشير", perm: "reports" },
  { key: "fields", label: "حسب حقل مخصص", perm: "reports" },
  { key: "items", label: "دفتر اليوم", perm: "reports" },
  { key: "periodic", label: "الدفتر الدوري", perm: "reports" },
  { key: "profit", label: "الأرباح", perm: "reports:finance" },
  { key: "cashflow", label: "التدفق النقدي", perm: "reports:finance" },
  { key: "aging", label: "أعمار الديون", perm: "reports:finance" },
  { key: "overview", label: "نظرة عامة", perm: "reports:finance", allBranches: true },
] as const;

export default function ReportsPage() {
  const [params, setParams] = useSearchParams();
  const can = useAuth((s) => s.can);
  const now = new Date();
  const [targetDate, setTargetDate] = useState(iso(now));
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [from, setFrom] = useState(daysAgo(13));
  const [to, setTo] = useState(iso(now));
  const [wid, setWid] = useState("");
  // Without "supervise" (or reports:finance) the server limits every report to the user's own branches.
  const allBranches = useAuth((s) => Boolean(s.user?.is_manager) || s.can("supervise") || s.can("reports:finance"));
  const tabs = TABS.filter((t) => can(t.perm) && (!("allBranches" in t) || allBranches));
  const tab = tabs.find((t) => t.key === params.get("tab"))?.key ?? "daily";
  const setTab = (key: string) => setParams((p) => { p.set("tab", key); return p; }, { replace: true });
  const [range, setRange] = useState<Range>(() => ({ ...monthToDate(), warehouse_id: "" }));
  const [itemsDay, setItemsDay] = useState(iso(now));

  const wh = useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<Warehouse[]>("/stock/warehouses") });

  const daily = useQuery({
    queryKey: ["rep-daily", targetDate, wid],
    queryFn: () => api.get<DailyRow>("/reports/sales/daily", { target_date: targetDate, warehouse_id: wid || undefined }),
    enabled: tab === "daily",
  });
  const monthly = useQuery({
    queryKey: ["rep-monthly", year, month, wid],
    queryFn: () => api.get<MonthlyRow>("/reports/sales/monthly", { year, month, warehouse_id: wid || undefined }),
    enabled: tab === "monthly",
  });
  const top = useQuery({
    queryKey: ["rep-top", from, to, wid],
    queryFn: () => api.get<TopProduct[]>("/reports/sales/top-products", { from_date: from, to_date: to, limit: 12, warehouse_id: wid || undefined }),
    enabled: tab === "top",
  });
  const byCashier = useQuery({
    queryKey: ["rep-cashier", from, to, wid],
    queryFn: () => api.get<CashierRow[]>("/reports/sales/by-cashier", { from_date: from, to_date: to, warehouse_id: wid || undefined }),
    enabled: tab === "cashier",
  });

  const branchSelect = (
    <Select className="w-auto min-w-36" value={wid} onChange={(e) => setWid(e.target.value)}>
      <option value="">{allBranches ? "كل الفروع" : "فروعي"}</option>
      {wh.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
    </Select>
  );

  const printWid = wid || wh.data?.[0]?.id;
  const printInventory = () => {
    if (!printWid) return;
    void printDocument("/reports/inventory/print", { warehouse_id: printWid });
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="التقارير"
        description="المبيعات والدفاتر والأرباح والتدفق النقدي والديون"
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void downloadFile("/export/sales", { from_date: from, to_date: to, warehouse_id: wid || undefined }, "sales.xlsx")}>
              <Download data-icon="inline-start" />
              تصدير المبيعات (Excel)
            </Button>
            <Button variant="outline" disabled={!printWid} onClick={printInventory}>
              <Printer data-icon="inline-start" />
              تقرير الجرد
            </Button>
          </div>
        }
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="h-auto flex-wrap">
          {tabs.map((t) => <TabsTrigger key={t.key} value={t.key}>{t.label}</TabsTrigger>)}
        </TabsList>
      </Tabs>

      {tab === "daily" && (
        <div className="flex flex-col gap-6">
          <Card className="flex flex-wrap items-end gap-3 p-4">
            <Field label="اليوم">
              <Input type="date" className="num w-44" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
            </Field>
            <Field label="الفرع">{branchSelect}</Field>
          </Card>
          {daily.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}</div>
          ) : daily.isError ? (
            <ErrorBox message={(daily.error as Error).message} onRetry={() => daily.refetch()} />
          ) : (
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard label="صافي المبيعات" icon={Receipt} value={<Money value={Number(daily.data?.total_sales ?? 0)} />} />
              <StatCard label="عدد الفواتير" icon={CalendarRange} value={<Num value={daily.data?.invoice_count ?? 0} />} />
              <StatCard label="المرتجعات" icon={CalendarRange} value={<Money value={Number(daily.data?.returns_total ?? 0)} />} />
            </div>
          )}
        </div>
      )}

      {tab === "monthly" && (
        <div className="flex flex-col gap-6">
          <Card className="flex flex-wrap items-end gap-3 p-4">
            <Field label="السنة">
              <Input className="num w-28" inputMode="numeric" value={year} onChange={(e) => setYear(Number(e.target.value) || now.getFullYear())} />
            </Field>
            <Field label="الشهر">
              <Select className="w-auto" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{m}</option>)}
              </Select>
            </Field>
            <Field label="الفرع">{branchSelect}</Field>
          </Card>
          {monthly.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}</div>
          ) : monthly.isError ? (
            <ErrorBox message={(monthly.error as Error).message} onRetry={() => monthly.refetch()} />
          ) : (
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard label="صافي مبيعات الشهر" icon={CalendarRange} value={<Money value={Number(monthly.data?.total_sales ?? 0)} />} />
              <StatCard label="عدد الفواتير" icon={Receipt} value={<Num value={monthly.data?.invoice_count ?? 0} />} />
              <StatCard label="المرتجعات" icon={Receipt} value={<Money value={Number(monthly.data?.returns_total ?? 0)} />} />
            </div>
          )}
        </div>
      )}

      {tab === "top" && (
        <div className="flex flex-col gap-6">
          <Card className="flex flex-wrap items-end gap-3 p-4">
            <Field label="من">
              <Input type="date" className="num w-40" value={from} onChange={(e) => setFrom(e.target.value)} />
            </Field>
            <Field label="إلى">
              <Input type="date" className="num w-40" value={to} onChange={(e) => setTo(e.target.value)} />
            </Field>
            <Field label="الفرع">{branchSelect}</Field>
          </Card>
          {top.isLoading ? (
            <Skeleton className="h-72 rounded-xl" />
          ) : top.isError ? (
            <ErrorBox message={(top.error as Error).message} onRetry={() => top.refetch()} />
          ) : !top.data?.length ? (
            <Empty text="لا توجد مبيعات في هذه الفترة" />
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>الأكثر مبيعاً — الإيراد</CardTitle>
                  <CardDescription>أعلى 12 صنفاً في الفترة المحددة (بعد الخصومات وخصم المرتجعات، بدون الضريبة)</CardDescription>
                </CardHeader>
                <CardContent>
                  <ChartContainer config={chartConfig} className="aspect-auto h-80 w-full" dir="ltr">
                    <BarChart data={top.data.map((p, i) => ({ name: p.product_name.slice(0, 18), rank: i + 1, revenue: Number(p.revenue) }))} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <CartesianGrid horizontal={false} />
                      <XAxis type="number" tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v / 1000}k`} />
                      <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} width={130} orientation="right" />
                      <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
                      <Bar dataKey="revenue" fill="var(--color-revenue)" radius={4} barSize={18} />
                    </BarChart>
                  </ChartContainer>
                </CardContent>
              </Card>
              <TableShell>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>#</TableHead>
                      <TableHead>المنتج</TableHead>
                      <TableHead className="text-end">الكمية</TableHead>
                      <TableHead className="text-end">الإيراد</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {top.data.map((p, i) => (
                      <TableRow key={p.product_id}>
                        <TableCell className="num text-muted-foreground">{i + 1}</TableCell>
                        <TableCell className="w-full max-w-0 truncate font-medium">{p.product_name}</TableCell>
                        <TableCell className="num text-end">{fq(p.qty)} {p.unit ?? ""}</TableCell>
                        <TableCell className="num text-end font-semibold">
                          <Money value={Number(p.revenue)} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableShell>
            </>
          )}
        </div>
      )}

      {tab === "cashier" && (
        <div className="flex flex-col gap-6">
          <Card className="flex flex-wrap items-end gap-3 p-4">
            <Field label="من">
              <Input type="date" className="num w-40" value={from} onChange={(e) => setFrom(e.target.value)} />
            </Field>
            <Field label="إلى">
              <Input type="date" className="num w-40" value={to} onChange={(e) => setTo(e.target.value)} />
            </Field>
            <Field label="الفرع">{branchSelect}</Field>
          </Card>
          {byCashier.isLoading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-10 w-full" />
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : byCashier.isError ? (
            <ErrorBox message={(byCashier.error as Error).message} onRetry={() => byCashier.refetch()} />
          ) : !byCashier.data?.length ? (
            <Empty text="لا توجد بيانات" />
          ) : (
            <TableShell>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>الكاشير</TableHead>
                    <TableHead className="text-end">عدد الفواتير</TableHead>
                    <TableHead className="text-end">المبيعات</TableHead>
                    <TableHead className="text-end">المرتجعات</TableHead>
                    <TableHead className="text-end">الصافي</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {byCashier.data.map((c) => (
                    <TableRow key={c.cashier_id}>
                      <TableCell className="w-full max-w-0 truncate font-medium">{c.cashier_name}</TableCell>
                      <TableCell className="num text-end">{c.invoice_count}</TableCell>
                      <TableCell className="num text-end"><Money value={Number(c.gross_sales)} /></TableCell>
                      <TableCell className="num text-end"><Money value={Number(c.returns_total)} /></TableCell>
                      <TableCell className="num text-end font-semibold">
                        <Money value={Number(c.total_sales)} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableShell>
          )}
        </div>
      )}

      {tab === "fields" && <CustomFieldReport from={from} to={to} onFrom={setFrom} onTo={setTo} Field={Field} />}
      {tab === "items" && <DailyItemsView day={itemsDay} onDay={setItemsDay} />}
      {tab === "periodic" && <PeriodicLedgerView />}
      {tab === "profit" && <ProfitView range={range} onRange={setRange} />}
      {tab === "cashflow" && <CashFlowView range={range} onRange={setRange} />}
      {tab === "aging" && <AgingView range={range} onRange={setRange} />}
      {tab === "overview" && <OverviewView range={range} onRange={setRange} />}
    </div>
  );
}
