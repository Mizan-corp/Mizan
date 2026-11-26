import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { sound } from "@/lib/sound";
import { CLINIC_KEYS } from "./useClinicData";
import type { AppointmentStatus, Invoice } from "./types";

type ClinicKey = keyof typeof CLINIC_KEYS;

/** The server's Arabic `detail` (ApiError.message), or a fallback. */
export function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

/** Refetch the given clinic lists. */
export function useClinicRefresh() {
  const queryClient = useQueryClient();
  return (...keys: ClinicKey[]) => {
    for (const k of keys) queryClient.invalidateQueries({ queryKey: CLINIC_KEYS[k] });
  };
}

/** One clinic change: a request, a success toast and the lists to refetch, or the server's error. */
export function useClinicMutation() {
  const { toast } = useToast();
  const refresh = useClinicRefresh();
  return async (request: () => Promise<unknown>, success: string, failure: string, keys: ClinicKey[]): Promise<boolean> => {
    sound.click();
    try {
      await request();
      toast("success", success);
      refresh(...keys);
      return true;
    } catch (err) {
      toast("error", errorMessage(err, failure));
      return false;
    }
  };
}

/** A dialog's submit: the mutation plus a busy flag (the submit button waits). */
export function useDialogMutation() {
  const run = useClinicMutation();
  const [busy, setBusy] = useState(false);
  return {
    busy,
    run: async (...args: Parameters<typeof run>) => {
      setBusy(true);
      try {
        return await run(...args);
      } finally {
        setBusy(false);
      }
    },
  };
}

/** Row actions on the clinic's lists (queue, pharmacy, ward, billing). */
export function useClinicActions() {
  const run = useClinicMutation();
  return {
    updateAppointmentStatus: (apptId: string, status: AppointmentStatus) =>
      run(() => api.post(`/clinic/appointments/${apptId}/status`, { status }),
        "تم تحديث حالة الموعد الطبي بنجاح", "تعذر تحديث حالة الموعد على الخادم",
        ["appointments", "summary", "invoices"]),
    billAppointment: (apptId: string) =>
      run(() => api.post(`/clinic/appointments/${apptId}/bill`, {}),
        "تم إصدار فاتورة الكشف بنجاح", "تعذر إصدار الفاتورة", ["invoices"]),
    dispensePrescription: (rxId: string) =>
      run(() => api.post(`/clinic/prescriptions/${rxId}/dispense`, {}),
        "تم صرف الروشتة الطبية من الصيدلية بنجاح", "تعذر اعتماد صرف الروشتة على الخادم", ["prescriptions"]),
    dischargeBed: (bedId: string) =>
      run(() => api.post(`/clinic/beds/${bedId}/discharge`, {}),
        "تم خروج المريض بنجاح واحتساب الفاتورة وتحويل السرير للتعقيم", "تعذر إخلاء السرير",
        ["beds", "summary", "invoices"]),
    cleanBed: (bedId: string) =>
      run(() => api.post(`/clinic/beds/${bedId}/clean`, {}),
        "تم اعتماد تعقيم السرير وجاهزيته للاستقبال", "تعذر اعتماد تعقيم السرير على الخادم", ["beds", "summary"]),
    payInvoice: (inv: Invoice) => {
      const remaining = inv.patient_amount - inv.paid_amount;
      const amt = window.prompt(`المبلغ للدفع (المتبقي: ${remaining}):`, String(remaining));
      if (!amt) return Promise.resolve(false);
      return run(() => api.post(`/clinic/invoices/${inv.id}/pay`, { amount: parseFloat(amt), payment_method: "cash" }),
        "تم تسجيل الدفع بنجاح", "تعذر تسجيل الدفع", ["invoices"]);
    },
  };
}

export type ClinicActions = ReturnType<typeof useClinicActions>;
