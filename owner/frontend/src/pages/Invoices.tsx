import { Link } from "react-router-dom";
import { type Invoice, useInvoices } from "@app/lib/data";
import { date, INVOICE_STATUS, METHOD_LABEL, money, planLabel } from "@app/lib/format";
import { Badge, Empty, LoadError, PageHeader, PageSkeleton, Panel, Money } from "@app/ui";

export function InvoiceTable({ invoices, showWorkspace }: { invoices: Invoice[]; showWorkspace?: boolean }) {
  if (!invoices.length) return <Empty title="لا توجد فواتير بعد.">تظهر الفاتورة هنا عند الاشتراك أو التجديد.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-start text-xs font-semibold text-mute">
            <th className="px-5 py-3 text-start font-semibold">الفاتورة</th>
            {showWorkspace && <th className="px-5 py-3 text-start font-semibold">مساحة العمل</th>}
            <th className="px-5 py-3 text-start font-semibold">الباقة</th>
            <th className="px-5 py-3 text-start font-semibold">المدة</th>
            <th className="px-5 py-3 text-start font-semibold">المبلغ</th>
            <th className="px-5 py-3 text-start font-semibold">الحالة</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line-soft">
          {invoices.map((i) => {
            const s = INVOICE_STATUS[i.status] ?? { label: i.status, tone: "mute" as const };
            return (
              <tr key={i.ref}>
                <td className="px-5 py-3.5">
                  <div className="code text-[13px] text-ink">{i.ref}</div>
                  <div className="mt-0.5 text-xs text-mute">{date(i.created_at)}</div>
                </td>
                {showWorkspace && (
                  <td className="px-5 py-3.5">
                    <Link to={`/workspaces/${i.workspace_id}`} className="font-semibold text-ink hover:text-wine hover:underline">
                      {i.workspace_name ?? "—"}
                    </Link>
                  </td>
                )}
                <td className="px-5 py-3.5">
                  {planLabel(i.plan)} <span className="text-mute">· {i.cycle === "annual" ? "سنوي" : "شهري"}</span>
                </td>
                <td className="px-5 py-3.5 text-ink-2">
                  {date(i.period_start)} ← {date(i.period_end)}
                </td>
                <td className="px-5 py-3.5 font-semibold text-ink"><Money value={i.amount_egp} /></td>
                <td className="px-5 py-3.5">
                  <Badge tone={s.tone}>{s.label}</Badge>
                  <div className="mt-0.5 text-xs text-mute">{i.paid_at ? date(i.paid_at) : METHOD_LABEL[i.method] ?? i.method}</div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function Invoices() {
  const q = useInvoices();
  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const paid = q.data.items.filter((i) => i.status === "paid").reduce((s, i) => s + i.amount_egp, 0);
  return (
    <>
      <PageHeader title="الفواتير" description={paid ? `إجمالي ما دفعته: ${money(paid)}` : "فواتير كل مساحات العمل في مكان واحد."} />
      <Panel flush>
        <InvoiceTable invoices={q.data.items} showWorkspace />
      </Panel>
    </>
  );
}
