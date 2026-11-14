import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { type ChartConfig, ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/kit/chart";
import type { VitalsHistory, VitalsPoint } from "../types";
import QueryState from "./QueryState";

type Key = "bp_systolic" | "bp_diastolic" | "heart_rate" | "spo2" | "temperature" | "blood_glucose";

const config = {
  bp_systolic: { label: "الانقباضي", color: "var(--chart-1)" },
  bp_diastolic: { label: "الانبساطي", color: "var(--chart-2)" },
  heart_rate: { label: "النبض", color: "var(--chart-3)" },
  spo2: { label: "الأكسجين SpO2", color: "var(--chart-4)" },
  temperature: { label: "الحرارة", color: "var(--chart-5)" },
  blood_glucose: { label: "سكر الدم (الكشف)", color: "var(--chart-1)" },
  lab_glucose: { label: "سكر الدم (المختبر)", color: "var(--chart-3)" },
} satisfies ChartConfig;

const SPARKS: { key: Key; label: string; unit: string; pair?: Key }[] = [
  { key: "bp_systolic", pair: "bp_diastolic", label: "ضغط الدم", unit: "mmHg" },
  { key: "heart_rate", label: "النبض", unit: "bpm" },
  { key: "spo2", label: "الأكسجين", unit: "%" },
  { key: "temperature", label: "الحرارة", unit: "°C" },
  { key: "blood_glucose", label: "سكر الدم", unit: "mg/dL" },
];

const last = (points: VitalsPoint[], key: Key) => [...points].reverse().find((p) => p[key] !== null)?.[key] ?? null;

function Sparkline({ points, spec }: { points: VitalsPoint[]; spec: (typeof SPARKS)[number] }) {
  const data = points.filter((p) => p[spec.key] !== null);
  const value = last(points, spec.key);
  const pair = spec.pair ? last(points, spec.pair) : null;
  return (
    <div className="rounded-lg border border-border/60 bg-muted/10 p-2.5">
      <div className="text-[10px] text-muted-foreground">{spec.label}</div>
      <div className="num text-sm font-bold text-foreground">
        {value === null ? "—" : spec.pair ? `${value}/${pair ?? "—"}` : value}
        {value !== null && <span className="text-[10px] font-normal text-muted-foreground"> {spec.unit}</span>}
      </div>
      {data.length > 1 ? (
        <ChartContainer config={config} className="aspect-auto h-8 w-full mt-1" dir="ltr" aria-hidden="true">
          <LineChart data={data} margin={{ top: 2, bottom: 2, left: 2, right: 2 }}>
            <Line dataKey={spec.key} stroke={`var(--color-${spec.key})`} strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ChartContainer>
      ) : (
        <div className="h-8 mt-1 text-[10px] text-muted-foreground flex items-center">{data.length ? "قراءة واحدة" : "لا قراءات"}</div>
      )}
    </div>
  );
}

type Row = { date: string } & Partial<Record<keyof typeof config, number | null>>;

function Trend({ title, data, lines, domain }: {
  title: string;
  data: readonly Row[];
  lines: (keyof typeof config)[];
  domain?: [number | "auto", number | "auto"];
}) {
  const has = data.some((d) => lines.some((l) => d[l] != null));
  return (
    <div className="rounded-lg border border-border/60 p-3">
      <h4 className="text-xs font-bold text-foreground mb-2">{title}</h4>
      {has ? (
        <ChartContainer config={config} className="aspect-auto h-48 w-full" dir="ltr">
          <LineChart data={[...data]} margin={{ left: 0, right: 8, top: 4 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={10} minTickGap={16} />
            <YAxis tickLine={false} axisLine={false} fontSize={10} width={32} domain={domain ?? ["auto", "auto"]} />
            <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
            {lines.length > 1 && <ChartLegend content={<ChartLegendContent />} />}
            {lines.map((l) => (
              <Line key={l} dataKey={l} type="monotone" stroke={`var(--color-${l})`} strokeWidth={2} connectNulls
                dot={{ r: 3 }} activeDot={{ r: 5 }} />
            ))}
          </LineChart>
        </ChartContainer>
      ) : (
        <p className="h-48 flex items-center justify-center text-xs text-muted-foreground">لا توجد قراءات مسجلة.</p>
      )}
    </div>
  );
}

// Vitals across visits (#42): the latest value of each with a sparkline, then trend charts.
export default function VitalsPanel({ patientId }: { patientId: string }) {
  const query = useQuery<VitalsHistory>({
    queryKey: ["clinic-vitals", patientId],
    queryFn: () => api.get(`/clinic/patients/${patientId}/vitals-history`),
  });
  const points = query.data?.points ?? [];
  const labs = query.data?.glucose_labs ?? [];
  const glucose = [
    ...points.filter((p) => p.blood_glucose !== null).map((p) => ({ date: p.date, blood_glucose: p.blood_glucose, lab_glucose: null })),
    ...labs.map((l) => ({ date: l.date, blood_glucose: null, lab_glucose: l.value })),
  ].sort((a, b) => a.date.localeCompare(b.date));
  return (
    <QueryState query={query} what="العلامات الحيوية" className="">
      {points.length === 0 && labs.length === 0 ? (
        <p className="py-10 text-center text-xs text-muted-foreground rounded-xl border border-dashed border-border">
          لا توجد كشوفات بعلامات حيوية لهذا المريض بعد.
        </p>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {SPARKS.map((s) => <Sparkline key={s.key} points={points} spec={s} />)}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Trend title="ضغط الدم (mmHg)" data={points} lines={["bp_systolic", "bp_diastolic"]} />
            <Trend title="النبض (bpm)" data={points} lines={["heart_rate"]} />
            <Trend title="سكر الدم (mg/dL)" data={glucose} lines={["blood_glucose", "lab_glucose"]} />
            <Trend title="الأكسجين SpO2 (%)" data={points} lines={["spo2"]} domain={[80, 100]} />
          </div>
          <p className="text-[10px] text-muted-foreground"><span className="num">{points.length}</span> كشف · يُسجَّل الاطلاع في سجل الوصول.</p>
        </div>
      )}
    </QueryState>
  );
}
