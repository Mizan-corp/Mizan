// Records counted (and sales totalled) by the value of one of the workspace's custom fields
// (ADR-006 phase 5: custom fields are usable in reports). /reports/fields/{record}/{key}.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Money, Num, TableShell } from "@/components/app/shared";
import { Card } from "@/components/kit/card";
import { Skeleton } from "@/components/kit/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import { Empty, ErrorBox, Input, Select } from "@/components/ui";
import { useWorkspaceProfile } from "@app/lib/workspace";

const RECORDS: Record<string, string> = { product: "المنتجات", customer: "العملاء", supplier: "الموردون", sale: "المبيعات" };

interface FieldReport {
  field: { key: string; label: string | null; type: string };
  rows: { value: string | null; count: number; total?: string | number }[];
}

function show(value: string | null, type: string): string {
  if (value === null || value === "") return "بدون قيمة";
  if (type === "boolean") return value === "true" ? "نعم" : "لا";
  return value;
}

export function CustomFieldReport({ from, to, onFrom, onTo, Field }: {
  from: string; to: string; onFrom: (v: string) => void; onTo: (v: string) => void;
  Field: (p: { label: string; children: React.ReactNode }) => React.ReactNode;
}) {
  const profile = useWorkspaceProfile();
  const [record, setRecord] = useState("product");
  const [key, setKey] = useState("");
  const fields = profile.data?.fields[record] ?? [];
  const current = fields.some((f) => f.key === key) ? key : fields[0]?.key ?? "";
  const isSale = record === "sale";

  const report = useQuery({
    queryKey: ["rep-field", record, current, isSale ? from : "", isSale ? to : ""],
    queryFn: () => api.get<FieldReport>(`/reports/fields/${record}/${current}`,
      isSale ? { from_date: from, to_date: to } : undefined),
    enabled: !!current,
  });
  const totalCount = (report.data?.rows ?? []).reduce((s, r) => s + r.count, 0);

  return (
    <div className="flex flex-col gap-6">
      <Card className="flex flex-wrap items-end gap-3 p-4">
        <Field label="السجل">
          <Select className="w-auto min-w-36" value={record} onChange={(e) => { setRecord(e.target.value); setKey(""); }}>
            {Object.entries(RECORDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </Field>
        <Field label="الحقل">
          <Select className="w-auto min-w-44" value={current} onChange={(e) => setKey(e.target.value)} disabled={!fields.length}>
            {fields.length ? fields.map((f) => <option key={f.key} value={f.key}>{f.label || f.key}</option>)
              : <option value="">لا توجد حقول مخصصة</option>}
          </Select>
        </Field>
        {isSale && (
          <>
            <Field label="من"><Input type="date" className="num w-40" value={from} onChange={(e) => onFrom(e.target.value)} /></Field>
            <Field label="إلى"><Input type="date" className="num w-40" value={to} onChange={(e) => onTo(e.target.value)} /></Field>
          </>
        )}
      </Card>

      {profile.isLoading || (report.isLoading && !!current) ? (
        <div className="flex flex-col gap-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
      ) : profile.isError ? (
        <ErrorBox message={(profile.error as Error).message} onRetry={() => profile.refetch()} />
      ) : !current ? (
        <Empty text={`لا توجد حقول مخصصة على ${RECORDS[record]}`} hint="أضف حقولًا من مصمم الشاشات والنماذج لتظهر هنا." />
      ) : report.isError ? (
        <ErrorBox message={(report.error as Error).message} onRetry={() => report.refetch()} />
      ) : !report.data?.rows.length ? (
        <Empty text="لا توجد بيانات" />
      ) : (
        <TableShell>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{report.data.field.label || report.data.field.key}</TableHead>
                <TableHead className="text-end">العدد</TableHead>
                <TableHead className="text-end">النسبة</TableHead>
                {isSale && <TableHead className="text-end">صافي المبيعات</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.data.rows.map((r) => (
                <TableRow key={r.value ?? "—"}>
                  <TableCell className={r.value === null ? "text-muted-foreground" : "font-medium"}>{show(r.value, report.data!.field.type)}</TableCell>
                  <TableCell className="num text-end"><Num value={r.count} /></TableCell>
                  <TableCell className="num text-end text-muted-foreground">{totalCount ? ((r.count / totalCount) * 100).toFixed(1) : "0"}%</TableCell>
                  {isSale && <TableCell className="num text-end font-semibold"><Money value={Number(r.total ?? 0)} /></TableCell>}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableShell>
      )}
    </div>
  );
}
