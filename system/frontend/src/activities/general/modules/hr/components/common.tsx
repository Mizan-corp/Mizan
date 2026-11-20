// Parts the HR screens share: the employees query, a list's skeleton and its pager.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { Button } from "@/components/ui";
import type { Paged } from "../lib";

export interface Employee {
  id: string;
  emp_code: string | null;
  name: string;
  position: string | null;
  monthly_salary: string;
  shift_schedule: string | null;
  shift_id: string | null;
  shift_name?: string | null;
  hire_date: string | null;
  is_active: boolean;
  ignore_lateness: boolean | null;
  max_lateness_before_overtime_cancellation: number | null;
}

export interface Shift {
  id: string;
  name: string;
  start_time: string;
  end_time: string;
  description: string | null;
  is_active: boolean;
  employees: number;
}

export const EMPLOYEES_PAGE = 50;
/** The largest page the server gives: the pickers list the first this many active employees by name. */
export const EMPLOYEE_OPTIONS_MAX = 200;

/** One page of the employees list (the server pages it, HR-13), searched by name or code. */
export function useEmployees(includeInactive = false, page = 1, q = "") {
  return useQuery({
    queryKey: ["hr-employees", { all: includeInactive, page, q }],
    queryFn: () => api.get<Paged<Employee>>("/hr/employees", {
      include_inactive: includeInactive ? "true" : undefined, page, page_size: EMPLOYEES_PAGE, q: q.trim() || undefined,
    }),
    placeholderData: keepPreviousData,
  });
}

/** The active employees for a picker (attendance, advances): the first EMPLOYEE_OPTIONS_MAX by name. */
export function useEmployeeOptions() {
  return useQuery({
    queryKey: ["hr-employees", "options"],
    queryFn: async () => (await api.get<Paged<Employee>>("/hr/employees", { page_size: EMPLOYEE_OPTIONS_MAX })).items,
  });
}

export function useShifts() {
  return useQuery({ queryKey: ["hr-shifts"], queryFn: () => api.get<Shift[]>("/hr/shifts") });
}

export function Rows({ n = 6 }: { n?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
      <Skeleton className="h-10 w-full" />
      {Array.from({ length: n }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
    </div>
  );
}

export function Pager({ page, pages, total, unit, busy, onPage }: {
  page: number; pages: number; total: number; unit: string; busy?: boolean; onPage: (p: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted">
      <span className="num">{total} {unit}</span>
      {pages > 1 && (
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1 || busy} onClick={() => onPage(page - 1)}>السابق</Button>
          <span className="num">صفحة {page} من {pages}</span>
          <Button variant="outline" size="sm" disabled={page >= pages || busy} onClick={() => onPage(page + 1)}>التالي</Button>
        </div>
      )}
    </div>
  );
}
