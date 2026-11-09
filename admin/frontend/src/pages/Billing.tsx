import { useState } from "react";
import { actions, type Invoice, useAction, useBilling } from "@app/lib/data";
import { ago, date, errorText, money, num, planLabel } from "@app/lib/format";
import {
  Badge,
  Button,
  Confirm,
  Empty,
  ErrorNote,
  Field,
  Figures,
  Input,
  LoadError,
  Modal,
  ModalActions,
  PageHeader,
  PageSkeleton,
  Panel,
  Segmented,
  Table,
  Tabs,
  Td,
  Textarea,
  WorkspaceLink,
} from "@app/ui";

const METHOD: Record<string, string> = {
  paymob: "Paymob (online)",
  card: "Card",
  instapay: "InstaPay",
  vodafone_cash: "Vodafone Cash",
  fawry: "Fawry",
  bank: "Bank transfer",
  bank_transfer: "Bank transfer",
};

export function InvoiceStatus({ status }: { status: string }) {
  const map: Record<string, ["ok" | "warn" | "bad" | "mute", string]> = {
    paid: ["ok", "Paid"],
    pending: ["warn", "Unpaid"],
    failed: ["bad", "Failed"],
    refunded: ["mute", "Refunded"],
    cancelled: ["mute", "Abandoned checkout"],
  };
  const [tone, label] = map[status] ?? ["mute", status];
  return <Badge tone={tone}>{label}</Badge>;
}

export function MarkPaidDialog({
  open,
  onClose,
  invoiceRef,
  amount,
}: {
  open: boolean;
  onClose: () => void;
  invoiceRef: string;
  amount: number;
}) {
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mark = useAction(actions.markPaid, { success: (v) => `${v.ref} marked paid` });
  const close = () => {
    setReference("");
    setNote("");
    setError(null);
    onClose();
  };
  return (
    <Modal
      open={open}
      onClose={close}
      title={`Mark ${invoiceRef} paid`}
      description={
        <>
          Only after you've seen <span className="data font-semibold text-ink">{money(amount)}</span> arrive. The workspace moves to
          this plan immediately and its trial ends.
        </>
      }
    >
      <div className="grid gap-4">
        <Field label="Transfer reference" hint="From the bank, InstaPay or Vodafone Cash receipt.">
          <Input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="e.g. FT26113045" />
        </Field>
        <Field label="Note (optional)">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      <ModalActions>
        <Button variant="ghost" onClick={close}>
          Cancel
        </Button>
        <Button
          variant="primary"
          busy={mark.isPending}
          onClick={() =>
            mark
              .mutateAsync({ ref: invoiceRef, reference: reference.trim() || undefined, note: note.trim() || undefined })
              .then(close, (e) => setError(errorText(e)))
          }
        >
          Mark paid
        </Button>
      </ModalActions>
    </Modal>
  );
}

export function InvoiceTable({ invoices, showWorkspace }: { invoices: Invoice[]; showWorkspace?: boolean }) {
  const [paying, setPaying] = useState<Invoice | null>(null);
  if (!invoices.length) return <Empty title="No invoices yet.">Invoices appear when a workspace starts a checkout.</Empty>;
  return (
    <>
      <Table head={["Invoice", ...(showWorkspace ? ["Workspace"] : []), "Plan", "Amount", "Method", "Status", "Issued", ""]}>
        {invoices.map((i) => (
          <tr key={i.ref} className="hover:bg-paper/60">
            <Td className="code text-[13px]">{i.ref}</Td>
            {showWorkspace && (
              <Td>
                <WorkspaceLink id={i.tenant_id ?? null} name={i.tenant_name ?? "Deleted workspace"} />
              </Td>
            )}
            <Td>
              {planLabel(i.plan)} <span className="text-mute">· {i.cycle === "annual" ? "yearly" : "monthly"}</span>
            </Td>
            <Td className="data">{money(i.amount_egp)}</Td>
            <Td className="text-ink-2">{METHOD[i.method] ?? i.method}</Td>
            <Td>
              <InvoiceStatus status={i.status} />
              {i.paid_at && <div className="mt-0.5 text-xs text-mute">{date(i.paid_at)}</div>}
            </Td>
            <Td className="text-ink-2" title={i.created_at}>
              {ago(i.created_at)}
            </Td>
            <Td className="text-right">
              {i.status === "pending" && (
                <Button size="sm" onClick={() => setPaying(i)}>
                  Mark paid
                </Button>
              )}
            </Td>
          </tr>
        ))}
      </Table>
      {paying && <MarkPaidDialog open onClose={() => setPaying(null)} invoiceRef={paying.ref} amount={paying.amount_egp} />}
    </>
  );
}

export default function Billing() {
  const [tab, setTab] = useState<"invoices" | "requests">("invoices");
  const [status, setStatus] = useState<"all" | "pending" | "paid" | "failed">("all");
  const q = useBilling(status === "all" ? undefined : status);
  const dismiss = useAction(actions.dismissRequest, { success: () => "Request dismissed" });
  const [dismissing, setDismissing] = useState<string | null>(null);

  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const { summary, invoices, requests } = q.data;

  return (
    <>
      <PageHeader title="Billing" description="Invoices from checkouts and upgrade requests from workspace owners." />
      <Figures
        items={[
          { label: "Monthly revenue", value: money(summary.mrr_egp), hint: "From paid invoices; yearly plans ÷ 12" },
          { label: "Paying workspaces", value: num(summary.paying), hint: summary.complimentary ? `+${summary.complimentary} on a paid plan for free` : undefined },
          { label: "Waiting for payment", value: money(summary.pending_egp), hint: `${num(summary.pending_count)} unpaid invoices` },
          { label: "Collected this month", value: money(summary.collected_this_month_egp) },
        ]}
      />

      <div className="mt-7">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { value: "invoices", label: "Invoices", count: summary.pending_count || undefined },
            { value: "requests", label: "Upgrade requests", count: requests.length || undefined },
          ]}
        />
        {tab === "invoices" ? (
          <Panel
            flush
            title={
              <Segmented
                value={status}
                onChange={setStatus}
                items={[
                  { value: "all", label: "All" },
                  { value: "pending", label: "Unpaid" },
                  { value: "paid", label: "Paid" },
                  { value: "failed", label: "Failed" },
                ]}
              />
            }
          >
            <InvoiceTable invoices={invoices} showWorkspace />
          </Panel>
        ) : (
          <Panel flush>
            {requests.length ? (
              <Table head={["Workspace", "Wants", "Phone", "Asked", ""]}>
                {requests.map((r) => (
                  <tr key={r.id}>
                    <Td>
                      <WorkspaceLink id={r.tenant_id ?? null} name={r.tenant_name ?? "Deleted workspace"} />
                    </Td>
                    <Td>{planLabel(r.plan)}</Td>
                    <Td className="code">{r.phone ?? "—"}</Td>
                    <Td className="text-ink-2">{ago(r.created_at)}</Td>
                    <Td className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => setDismissing(r.id)}>
                        Dismiss
                      </Button>
                    </Td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Empty title="No open upgrade requests.">Owners ask to upgrade from the pricing page inside the app.</Empty>
            )}
          </Panel>
        )}
      </div>

      <Confirm
        open={!!dismissing}
        onClose={() => setDismissing(null)}
        title="Dismiss this request?"
        body="It disappears from this list. The workspace keeps its current plan."
        confirmLabel="Dismiss request"
        onConfirm={() => dismiss.mutateAsync(dismissing!)}
      />
    </>
  );
}
