// The payroll rules (HR-12): typed settings, today's former fixed values as defaults. They apply
// from the next calculation; an approved month keeps what it was approved with.
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { api } from "@/lib/api";
import { sound } from "@/lib/sound";
import { Button, ErrorBox, Input, Select, Spinner, useToast } from "@/components/ui";
import { type HrSettings, NUMBER_SETTINGS, settingsPayload, WEEKDAYS } from "../lib";
import { Rows } from "./common";

type Form = Record<string, string | boolean>;
const FLAGS: { key: keyof HrSettings; label: string }[] = [
  { key: "weekend_paid", label: "يوم العطلة الأسبوعية مدفوع (لا يُحسب غياباً)" },
  { key: "overtime_enabled", label: "احتساب العمل الإضافي" },
  { key: "apply_missing_checkout_penalty", label: "خصم نسيان بصمة الانصراف" },
];

const toForm = (s: HrSettings): Form =>
  Object.fromEntries(Object.entries(s).map(([k, v]) => [k, typeof v === "boolean" ? v : String(v)]));

export function SettingsTab() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const q = useQuery({ queryKey: ["hr-settings"], queryFn: () => api.get<HrSettings>("/hr/settings") });
  const [form, setForm] = useState<Form | null>(null);
  useEffect(() => {
    if (q.data && !form) setForm(toForm(q.data));
  }, [q.data, form]);
  const payload = form ? settingsPayload(form) : null;
  const save = useMutation({
    mutationFn: () => api.put<HrSettings>("/hr/settings", { settings: payload }),
    onSuccess: (s) => {
      sound.success();
      toast("success", "حُفظت إعدادات الرواتب");
      setForm(toForm(s));
      qc.setQueryData(["hr-settings"], s);
    },
    onError: () => sound.error(),
  });

  if (q.isLoading || (!form && !q.isError)) return <Rows n={4} />;
  if (q.isError) return <ErrorBox message={(q.error as Error).message} onRetry={() => q.refetch()} />;
  const f = form!;
  return (
    <form className="flex max-w-3xl flex-col gap-5" onSubmit={(e) => { e.preventDefault(); if (payload && !save.isPending) save.mutate(); }}>
      <p className="text-xs text-muted">تُطبق من الحساب التالي للرواتب؛ الشهر المعتمد يبقى كما اعتُمد.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="set-weekend" className="mb-1 block text-xs font-semibold text-muted">يوم العطلة الأسبوعية</label>
          <Select id="set-weekend" value={String(f.weekend_day)} onChange={(e) => setForm({ ...f, weekend_day: e.target.value })}>
            {WEEKDAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
          </Select>
        </div>
        {NUMBER_SETTINGS.map((s) => (
          <div key={s.key}>
            <label htmlFor={`set-${s.key}`} className="mb-1 block text-xs font-semibold text-muted">{s.label}</label>
            <Input id={`set-${s.key}`} type="number" className="num" min={s.min} max={s.max} step={s.step ?? 1}
                   value={String(f[s.key] ?? "")} onChange={(e) => setForm({ ...f, [s.key]: e.target.value })} />
            <p className="mt-1 text-[11px] text-muted">{s.hint}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {FLAGS.map((x) => (
          <label key={x.key} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={Boolean(f[x.key])} onChange={(e) => setForm({ ...f, [x.key]: e.target.checked })} /> {x.label}
          </label>
        ))}
      </div>
      {!payload && <ErrorBox message="قيمة خارج الحدود المسموحة: راجع الحقول (أرقام صحيحة إلا المضاعف والساعات)" />}
      {save.isError && <ErrorBox message={(save.error as Error).message} />}
      <div>
        <Button type="submit" disabled={!payload || save.isPending}>{save.isPending ? <Spinner /> : <><Save className="size-4" /> حفظ الإعدادات</>}</Button>
      </div>
    </form>
  );
}
