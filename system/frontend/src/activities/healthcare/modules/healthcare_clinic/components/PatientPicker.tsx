import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { CLINIC_KEYS } from "../useClinicData";
import { useDebounced } from "../useDebounced";
import type { Page, Patient, PatientRef } from "../types";
import { labelClass, selectClass } from "./formStyles";
import { InlineRetry } from "./QueryState";
import { errorMessage } from "../useClinicActions";

const PICKER_SIZE = 20;

// Picks a registered patient through the server's search (#39): name, MRN, national id or phone.
export default function PatientPicker({
  id,
  value,
  onChange,
  label = "المريض *",
}: {
  id: string;
  value: PatientRef | null;
  onChange: (patient: PatientRef | null) => void;
  label?: string;
}) {
  const [query, setQuery] = useState("");
  const search = useDebounced(query.trim(), 300);
  const { data, isFetching, isError, error, refetch } = useQuery<Page<Patient>>({
    queryKey: [...CLINIC_KEYS.patients, "picker", search],
    queryFn: () => api.get("/clinic/patients", { search: search || undefined, page: 1, page_size: PICKER_SIZE }),
  });
  const found = data?.items ?? [];
  const options: PatientRef[] = value && !found.some((p) => p.id === value.id) ? [value, ...found] : found;

  return (
    <div>
      <label htmlFor={id} className={labelClass}>{label}</label>
      <div className="relative mb-1.5">
        <Search className="size-3.5 absolute right-2.5 top-2.5 text-muted-foreground" />
        <Input
          type="search"
          aria-label="ابحث عن المريض بالاسم أو رقم الملف أو الرقم القومي أو الهاتف"
          placeholder="ابحث بالاسم أو رقم الملف أو الرقم القومي أو الهاتف..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-8 pr-8 text-xs"
        />
      </div>
      <select
        id={id}
        required
        value={value?.id ?? ""}
        onChange={(e) => onChange(options.find((p) => p.id === e.target.value) ?? null)}
        className={selectClass}
      >
        <option value="">
          {isError ? "تعذر البحث في ملفات المرضى" : isFetching ? "جارٍ البحث..." : found.length ? "اختر ملف المريض" : "لا يوجد مريض يطابق البحث"}
        </option>
        {options.map((p) => (
          <option key={p.id} value={p.id}>{p.full_name}{p.patient_mrn ? ` — ${p.patient_mrn}` : ""}</option>
        ))}
      </select>
      {isError && (
        <InlineRetry message={errorMessage(error, "تعذر البحث في ملفات المرضى")} onRetry={() => void refetch()} />
      )}
      {data && data.total > found.length && (
        <p className="text-[10px] text-muted-foreground mt-1">
          تظهر أول <span className="num">{found.length}</span> من <span className="num">{data.total}</span> نتيجة؛ اكتب للتضييق.
        </p>
      )}
    </div>
  );
}
