import { useState } from "react";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { FileText, Printer } from "lucide-react";
import { useClinic } from "../ClinicContext";
import QueryState from "../components/QueryState";
import { moneyEGP } from "../format";
import { ClinicInvoiceReceiptModal, type ClinicInvoiceReceiptData } from "@app/features/modules/SpecializedReceiptModals";


export default function BillingTab() {
  const c = useClinic();
  const [printData, setPrintData] = useState<ClinicInvoiceReceiptData | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <FileText className="size-4 text-primary" />
            فواتير الكشوفات والتحصيل (Billing &amp; Invoices)
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            إصدار فواتير الكشوفات، احتساب نسب التحمل (Copay)، وتسجيل المدفوعات وطباعة الإيصالات
          </p>
        </div>
      </div>

      <QueryState query={c.data.queries.invoices} what="الفواتير" className="">
      <div className="overflow-x-auto rounded-xl border border-border/70 bg-card/80 shadow-xs">
        <table className="w-full text-xs">
          <thead className="bg-muted/30 border-b border-border/60">
            <tr>
              <th className="text-start py-2.5 px-3 font-semibold">رقم الفاتورة</th>
              <th className="text-start py-2.5 px-3 font-semibold">المريض</th>
              <th className="text-start py-2.5 px-3 font-semibold">المجموع</th>
              <th className="text-start py-2.5 px-3 font-semibold">تحمل التأمين</th>
              <th className="text-start py-2.5 px-3 font-semibold">تحمل المريض</th>
              <th className="text-start py-2.5 px-3 font-semibold">المدفوع</th>
              <th className="text-start py-2.5 px-3 font-semibold">الحالة</th>
              <th className="text-start py-2.5 px-3 font-semibold">إجراء</th>
            </tr>
          </thead>
          <tbody>
            {c.data.invoices.map((inv) => (
              <tr key={inv.id} className="border-t border-border/40 hover:bg-primary/[0.03] transition-colors">
                <td className="py-2.5 px-3 num font-bold text-foreground">{inv.invoice_ref}</td>
                <td className="py-2.5 px-3 font-medium text-foreground">{inv.patient_name}</td>
                <td className="py-2.5 px-3 num font-semibold">{moneyEGP(inv.total)}</td>
                <td className="py-2.5 px-3 num text-muted-foreground">{moneyEGP(inv.insurance_amount)}</td>
                <td className="py-2.5 px-3 num font-semibold text-primary">{moneyEGP(inv.patient_amount)}</td>
                <td className="py-2.5 px-3 num font-semibold text-emerald-700 dark:text-emerald-400">{moneyEGP(inv.paid_amount)}</td>
                <td className="py-2.5 px-3">
                  <Badge variant={inv.status === "paid" ? "success" : "outline"} className="text-[10px]">{inv.status}</Badge>
                </td>
                <td className="py-2.5 px-3">
                  <div className="flex items-center gap-1.5">
                    {inv.status !== "paid" && (
                      <Button size="sm" onClick={() => c.actions.payInvoice(inv)} className="text-xs h-7 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold">
                        تسجيل دفع
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setPrintData({
                          invoice_no: inv.invoice_ref || `INV-${String(inv.id).slice(0, 8)}`,
                          patient_name: inv.patient_name || "مريض عام",
                          doctor_name: "د. استشاري العيادة",
                          copay_percentage: inv.insurance_amount > 0 && inv.total > 0 ? Math.round((inv.patient_amount / inv.total) * 100) : 100,
                          items: [
                            {
                              description: "كشف واستشارة طبية سريرية",
                              qty: 1,
                              unit_price: Number(inv.total),
                              total: Number(inv.total),
                            },
                          ],
                          total_amount: Number(inv.total),
                          insurance_covered: Number(inv.insurance_amount || 0),
                          patient_paid: Number(inv.paid_amount || inv.patient_amount || 0),
                        });
                      }}
                      className="text-xs h-7 gap-1 font-semibold"
                    >
                      <Printer className="size-3" />
                      طباعة
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
            {c.data.invoices.length === 0 && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-muted-foreground">
                  لا توجد فواتير. استخدم زر "إصدار فاتورة" في تبويب المواعيد.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      </QueryState>

      <ClinicInvoiceReceiptModal
        open={!!printData}
        onClose={() => setPrintData(null)}
        data={printData}
      />
    </div>
  );
}