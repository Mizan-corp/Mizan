// Parts every accounting screen uses: the header with the module's own tabs and the opening-entry
// reminder, the chart / branches / state queries, filters, pickers and the export buttons.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, CalendarCheck, ChartColumn, Download, ListTree, Printer, Sparkles } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Button, Input, Select } from "@/components/ui";
import { useTenantNav } from "@app/lib/tenant";
import type { AccountingState, AccountNode, Branch, PartyType } from "../api";
import { type AccountInfo, type Cell, type ChartRow, downloadCsv, flattenChart, openPrint, TYPE_LABEL } from "../lib";

export const PERM = {
  view: "accounting:view",
  journal: "accounting:journal",
  close: "accounting:close",
  settings: "accounting:settings",
} as const;

const TABS = [
  { path: "/accounting/journal", label: "دفتر اليومية", icon: BookOpen, perm: `${PERM.view}|${PERM.journal}` },
  { path: "/accounting/accounts", label: "دليل الحسابات", icon: ListTree, perm: PERM.view },
  { path: "/accounting/reports", label: "التقارير المحاسبية", icon: ChartColumn, perm: PERM.view },
  { path: "/accounting/periods", label: "إقفال الفترات والسنة", icon: CalendarCheck, perm: `${PERM.close}|${PERM.settings}` },
];

export function useAccountingState() {
  const can = useAuth((s) => s.can);
  return useQuery({
    queryKey: ["accounting", "state"],
    queryFn: () => api.get<AccountingState>("/accounting/settings"),
    enabled: can(PERM.view),
  });
}

/** The chart: the tree, every account as rows (code order) and a lookup by id for the checks. */
export function useChart() {
  const q = useQuery({ queryKey: ["accounting", "accounts"], queryFn: () => api.get<AccountNode[]>("/accounting/accounts") });
  const rows = useMemo(() => flattenChart(q.data ?? []), [q.data]);
  const byId = useMemo(() => new Map<string, AccountInfo & ChartRow>(rows.map((r) => [r.id, r])), [rows]);
  return { ...q, rows, byId };
}

export function useBranches() {
  return useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<Branch[]>("/stock/warehouses") });
}

export function AccountingHeader({ title, subtitle, actions }: { title: string; subtitle: string; actions?: ReactNode }) {
  const can = useAuth((s) => s.can);
  const { tenantTo } = useTenantNav();
  const location = useLocation();
  const state = useAccountingState();
  const needsOpening = state.data && !state.data.opening_entry && !location.pathname.endsWith("/accounting/opening");
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-0.5 text-xs text-muted">{subtitle}</p>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <nav className="no-print flex flex-wrap gap-2" aria-label="أقسام المحاسبة">
        {TABS.filter((t) => can(t.perm)).map((t) => {
          const Icon = t.icon;
          const active = location.pathname.endsWith(t.path);
          return (
            <Link
              key={t.path}
              to={tenantTo(t.path)}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                active ? "bg-primary text-primary-foreground shadow-sm shadow-primary/25" : "border border-line/80 bg-card text-muted hover:bg-elevated hover:text-ink"
              }`}
            >
              <Icon className="size-4" />
              {t.label}
            </Link>
          );
        })}
      </nav>
      {needsOpening && (
        <div className="no-print flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm">
          <span className="flex items-center gap-2">
            <Sparkles className="size-4 shrink-0" />
            لم يُسجَّل القيد الافتتاحي بعد: تبدأ الدفاتر من أرصدة العملاء والموردين والخزائن والمخزون الحالية، وحتى تسجيله
            تظهر فروق في المطابقة.
          </span>
          {can(PERM.settings) ? (
            <Button asChild>
              <Link to={tenantTo("/accounting/opening")} className="inline-flex h-9 items-center rounded-md px-4 text-sm font-medium">
                تسجيل القيد الافتتاحي
              </Link>
            </Button>
          ) : (
            <span className="text-xs text-muted">يسجله من يملك صلاحية إعداد الحسابات</span>
          )}
        </div>
      )}
    </div>
  );
}

export function Money({ value, className = "" }: { value: number | string | null | undefined; className?: string }) {
  const n = Number(value ?? 0);
  return <span className={`num ${n < 0 ? "text-destructive" : ""} ${className}`}>{money(n)}</span>;
}

export interface Range {
  from: string;
  to: string;
  warehouse_id: string;
}

/** From / to dates and a branch. `single`: one date only ("as of", the balance sheet). */
export function RangeFilters({ value, onChange, single = false, branch = true, children }: {
  value: Range; onChange: (r: Range) => void; single?: boolean; branch?: boolean; children?: ReactNode;
}) {
  const branches = useBranches();
  return (
    <div className="no-print flex flex-wrap items-end gap-3 rounded-xl border border-line bg-card p-3">
      {!single && (
        <div>
          <label htmlFor="acc-from" className="mb-1 block text-xs font-medium text-muted">من تاريخ</label>
          <Input id="acc-from" type="date" className="w-40" value={value.from} onChange={(e) => onChange({ ...value, from: e.target.value })} />
        </div>
      )}
      <div>
        <label htmlFor="acc-to" className="mb-1 block text-xs font-medium text-muted">{single ? "في تاريخ" : "إلى تاريخ"}</label>
        <Input id="acc-to" type="date" className="w-40" value={value.to} onChange={(e) => onChange({ ...value, to: e.target.value })} />
      </div>
      {branch && (
        <div>
          <label htmlFor="acc-branch" className="mb-1 block text-xs font-medium text-muted">الفرع</label>
          <Select id="acc-branch" className="w-44" value={value.warehouse_id} onChange={(e) => onChange({ ...value, warehouse_id: e.target.value })}>
            <option value="">كل الفروع</option>
            {branches.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </Select>
        </div>
      )}
      {children}
    </div>
  );
}

export function ExportButtons({ filename, title, subtitle, columns, rows, disabled }: {
  filename: string; title: string; subtitle: string; columns: string[]; rows: Cell[][]; disabled?: boolean;
}) {
  return (
    <div className="no-print flex gap-2">
      <Button variant="outline" size="sm" disabled={disabled || !rows.length} onClick={() => downloadCsv(filename, columns, rows)}>
        <Download className="size-4" /> CSV
      </Button>
      <Button variant="outline" size="sm" disabled={disabled || !rows.length} onClick={() => openPrint(title, subtitle, columns, rows)}>
        <Printer className="size-4" /> طباعة
      </Button>
    </div>
  );
}

/** A select of accounts grouped by type. `rows` decides which accounts are offered. */
export function AccountSelect({ id, value, onChange, rows, placeholder = "— اختر الحساب —", className = "" }: {
  id?: string; value: string; onChange: (id: string) => void; rows: ChartRow[]; placeholder?: string; className?: string;
}) {
  const groups = (Object.keys(TYPE_LABEL) as (keyof typeof TYPE_LABEL)[])
    .map((type) => ({ type, items: rows.filter((r) => r.type === type) }))
    .filter((g) => g.items.length);
  return (
    <Select id={id} className={className} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{placeholder}</option>
      {groups.map((g) => (
        <optgroup key={g.type} label={TYPE_LABEL[g.type]}>
          {g.items.map((r) => (
            <option key={r.id} value={r.id}>{`${r.code} — ${r.name}${r.is_group ? " (تجميعي)" : ""}`}</option>
          ))}
        </optgroup>
      ))}
    </Select>
  );
}

interface PartyRow { id: string; name: string }

/** The customers, suppliers or employees matching a search, from the server (/accounting/parties:
 * at most 20, by name), plus the one already chosen (`id`) so its name shows. */
export function useParties(type: PartyType | "", q = "", id = "") {
  return useQuery({
    queryKey: ["accounting", "parties", type, q, id],
    enabled: !!type,
    staleTime: 60_000,
    placeholderData: (prev) => prev,
    queryFn: () => api.get<PartyRow[]>("/accounting/parties", { type, q: q || undefined, id: id || undefined, limit: 20 }),
  });
}

/** A search box and the matching parties: typing narrows the list on the server. */
export function PartySelect({ id, type, value, onChange, className = "" }: {
  id?: string; type: PartyType; value: string; onChange: (id: string) => void; className?: string;
}) {
  const [typed, setTyped] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(typed.trim()), 300);
    return () => clearTimeout(t);
  }, [typed]);
  const parties = useParties(type, q, value);
  const label = { customer: "العميل", supplier: "المورد", employee: "الموظف" }[type];
  const empty = parties.isSuccess && !parties.data.length;
  return (
    <div className={`flex gap-1 ${className}`}>
      <Input className="w-28 text-xs" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="بحث…"
             aria-label={`بحث عن ${label}`} />
      <Select id={id} className="min-w-0 flex-1" value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}
              disabled={parties.isLoading}>
        <option value="">
          {parties.isLoading ? "جارٍ التحميل…" : parties.isError ? "تعذر التحميل" : empty ? "لا نتائج" : `— ${label} —`}
        </option>
        {parties.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </Select>
    </div>
  );
}

export function SkeletonRows({ n = 6 }: { n?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
      {Array.from({ length: n }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
    </div>
  );
}
