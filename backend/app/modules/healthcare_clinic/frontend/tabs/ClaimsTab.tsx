import { Badge } from "@/components/kit/badge";
import { ShieldCheck } from "lucide-react";
import { useClinic } from "../ClinicContext";

const moneyEGP = (amount: number) =>
  `${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ج.م`;

export default function ClaimsTab() {
  const c = useClinic();
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <ShieldCheck className="size-4 text-primary" />
            مطالبات التأمين الطبي (Insurance Claims)
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            تقديم ومتابعة مطالبات شركات التأمين (Copay، موافقة، رفض، وصرف)
          </p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border/70 bg-card/80 shadow-xs">
        <table className="w-full text-xs">
          <thead className="bg-muted/30 border-b border-border/60">
            <tr>
              <th className="text-start py-2.5 px-3 font-semibold">رقم المطالبة</th>
              <th className="text-start py-2.5 px-3 font-semibold">المريض</th>
              <th className="text-start py-2.5 px-3 font-semibold">شركة التأمين</th>
              <th className="text-start py-2.5 px-3 font-semibold">المبلغ المطالب</th>
              <th className="text-start py-2.5 px-3 font-semibold">المعتمد</th>
              <th className="text-start py-2.5 px-3 font-semibold">الحالة</th>
            </tr>
          </thead>
          <tbody>
            {c.claimsData.map((cl: any) => (
              <tr key={cl.id} className="border-t border-border/40 hover:bg-primary/[0.03] transition-colors">
                <td className="py-2.5 px-3 num font-bold text-foreground">{cl.claim_ref}</td>
                <td className="py-2.5 px-3 font-medium text-foreground">{cl.patient_name}</td>
                <td className="py-2.5 px-3">{cl.insurance_provider}</td>
                <td className="py-2.5 px-3 num font-semibold">{moneyEGP(cl.claimed_amount)}</td>
                <td className="py-2.5 px-3 num font-semibold text-primary">{moneyEGP(cl.approved_amount)}</td>
                <td className="py-2.5 px-3">
                  <Badge variant={cl.status === "approved" || cl.status === "paid" ? "success" : cl.status === "rejected" ? "destructive" : "outline"} className="text-[10px]">{cl.status}</Badge>
                </td>
              </tr>
            ))}
            {c.claimsData.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-muted-foreground">
                  لا توجد مطالبات تأمين بعد.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}