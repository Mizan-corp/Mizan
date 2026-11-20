// Confirming a draft or a quotation. A draft's money goes into the user's own open shift in its
// branch, as it was saved (cash, wallet or credit); a quotation's goes where the user chooses:
// that drawer, a safe, a wallet, or the customer's account.
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { moneyEGP } from "@/lib/format";
import { Button, ErrorBox, Modal, Spinner, useToast } from "@/components/ui";
import { PaySourceSelect } from "@app/components/PaySourceSelect";
import type { SaleRow } from "../api";
import { confirmBody, paymentLabel } from "../lib";

type Choice = "drawer" | "source" | "credit";

export function ConfirmDocumentDialog({ doc, onClose }: { doc: SaleRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [choice, setChoice] = useState<Choice>("drawer");
  const [source, setSource] = useState("");
  const isQuote = doc?.status === "quotation";

  useEffect(() => {
    setChoice("drawer");
    setSource("");
  }, [doc?.id]);

  const shift = useQuery({
    queryKey: ["shift", "current", doc?.warehouse_id],
    queryFn: () => api.get<{ id: string } | null>("/shifts/current", { warehouse_id: doc!.warehouse_id }),
    enabled: !!doc,
    retry: false,
  });
  const noShift = shift.isSuccess && !shift.data;

  const confirm = useMutation({
    mutationFn: () =>
      isQuote
        ? api.post<SaleRow>(`/sales/${doc!.id}/confirm-quotation`, confirmBody(choice, source))
        : api.put<SaleRow>(`/sales/${doc!.id}/confirm`),
    onSuccess: (r) => {
      toast("success", `تم التأكيد — فاتورة ${r.invoice_number}`);
      for (const key of ["sales", "sale", "sales-summary", "safes", "wallets", "shift"]) qc.invalidateQueries({ queryKey: [key] });
      onClose();
    },
  });

  const needsShift = isQuote ? choice === "drawer" : doc?.payment_method === "cash" && !doc?.is_credit;
  const blocked =
    confirm.isPending || (isQuote && choice === "source" && !source) || (isQuote && choice === "credit" && !doc?.customer_id);

  return (
    <Modal open={!!doc} onClose={onClose} title={isQuote ? `تحويل عرض السعر ${doc?.invoice_number ?? ""} إلى فاتورة` : `تأكيد المسودة ${doc?.invoice_number ?? ""}`}>
      {doc && (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!blocked) confirm.mutate();
          }}
        >
          <div className="flex items-center justify-between rounded-xl border border-line bg-secondary/30 p-3 text-sm">
            <span className="text-muted-foreground">{doc.customer_name ?? "عميل نقدي"}</span>
            <span className="num font-bold">{moneyEGP(doc.net_total)}</span>
          </div>
          <p className="text-xs text-muted-foreground">يُخصم المخزون من فرع المستند ويُعطى رقم فاتورة جديد.</p>

          {isQuote ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1 text-xs font-semibold text-muted-foreground">أين يذهب المبلغ؟</legend>
              {([
                ["drawer", "درج ورديتي المفتوحة في هذا الفرع"],
                ["source", "خزنة أو محفظة"],
                ["credit", "على حساب العميل (آجل)"],
              ] as const).map(([key, label]) => (
                <label key={key} className={`flex cursor-pointer items-center gap-2 rounded-lg border p-2.5 text-sm ${choice === key ? "border-primary bg-primary/5" : "border-line"}`}>
                  <input
                    type="radio"
                    name="destination"
                    value={key}
                    checked={choice === key}
                    disabled={key === "credit" && !doc.customer_id}
                    onChange={() => setChoice(key)}
                  />
                  <span>{label}</span>
                  {key === "credit" && !doc.customer_id && <span className="ms-auto text-xs text-muted-foreground">يحتاج عميلاً</span>}
                </label>
              ))}
              {choice === "source" && (
                <div>
                  <label htmlFor="confirm-source" className="mb-1 block text-xs font-semibold text-muted-foreground">الخزنة أو المحفظة *</label>
                  <PaySourceSelect id="confirm-source" value={source} onChange={setSource} />
                </div>
              )}
            </fieldset>
          ) : (
            <p className="rounded-lg border border-line p-2.5 text-sm">
              طريقة الدفع المحفوظة: <strong>{paymentLabel(doc)}</strong>
              {needsShift && " — يدخل المبلغ درج ورديتك المفتوحة في فرع المسودة."}
            </p>
          )}

          {needsShift && noShift && (
            <p role="alert" className="rounded-lg border border-warning/40 bg-warning/10 p-2.5 text-xs text-warning-ink">
              لا توجد وردية مفتوحة لك في فرع هذا المستند — افتح وردية من شاشة الورديات أو اختر وجهة أخرى.
            </p>
          )}
          {confirm.isError && <ErrorBox message={(confirm.error as Error).message} />}
          <div className="flex gap-2">
            <Button type="submit" className="h-10 flex-1 font-bold" disabled={blocked}>
              {confirm.isPending ? <Spinner /> : "تأكيد الفاتورة"}
            </Button>
            <Button type="button" variant="ghost" className="h-10 flex-1" onClick={onClose}>إلغاء</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
