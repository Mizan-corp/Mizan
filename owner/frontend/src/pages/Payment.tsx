import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { actions } from "@app/lib/data";
import { useOpenWorkspace } from "@app/lib/open";
import { date, planLabel } from "@app/lib/format";
import { Button, LoadError, PageSkeleton, Money } from "@app/ui";

const WAIT_MS = 90_000;

/**
 * Where Paymob sends the owner after paying. The query string from Paymob is
 * ignored: only the invoice status (set by the verified callback) counts.
 */
export default function Payment() {
  const { ref = "" } = useParams();
  const qc = useQueryClient();
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(Date.now());
  const { open, opening } = useOpenWorkspace();
  const declined = new URLSearchParams(window.location.search).get("success") === "false";

  const q = useQuery({
    queryKey: ["invoice", ref],
    queryFn: () => actions.invoice(ref),
    refetchInterval: (query) => (query.state.data?.status === "pending" && Date.now() - startedAt < WAIT_MS ? 2500 : false),
  });

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (q.data?.status === "paid") void qc.invalidateQueries({ queryKey: ["workspaces"] });
  }, [q.data?.status, qc]);

  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const inv = q.data;
  const waitedOut = now - startedAt >= WAIT_MS;

  let icon, title, body;
  if (inv.status === "paid") {
    icon = <CheckCircle2 className="size-12 text-ok" />;
    title = "تم الدفع وتفعيل الاشتراك";
    body = (
      <>
        {inv.workspace_name} الآن على باقة {planLabel(inv.plan)} حتى {date(inv.period_end)}. شكرًا لك.
      </>
    );
  } else if (inv.status === "pending" && !waitedOut && !declined) {
    icon = <Clock className="size-12 animate-pulse text-warn" />;
    title = "نؤكّد الدفع مع Paymob…";
    body = <>يستغرق هذا عادة ثوانٍ. لا تغلق الصفحة.</>;
  } else {
    icon = <XCircle className="size-12 text-bad" />;
    title = declined ? "لم يتم الدفع" : "لم يصلنا تأكيد الدفع بعد";
    body = declined ? (
      <>رفضت جهة الدفع العملية ولم يُخصم شيء. يمكنك المحاولة مرة أخرى ببطاقة أو محفظة أخرى.</>
    ) : (
      <>إن كان المبلغ قد خُصم، سيتفعّل الاشتراك تلقائيًا خلال دقائق عندما يصلنا التأكيد. يمكنك متابعة الحالة من صفحة الفواتير.</>
    );
  }

  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-line bg-card shadow-xs px-6 py-10 text-center">
      <div className="flex justify-center">{icon}</div>
      <h1 className="title mt-4 text-2xl text-ink">{title}</h1>
      <p className="mt-2 leading-7 text-ink-2">{body}</p>
      <dl className="mx-auto mt-6 grid max-w-sm grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-start text-mute">الفاتورة</dt>
        <dd className="code text-end whitespace-nowrap text-ink">{inv.ref}</dd>
        <dt className="text-start text-mute">المبلغ</dt>
        <dd className="text-end text-ink"><Money value={inv.amount_egp} /></dd>
      </dl>
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        {inv.status === "paid" ? (
          <Button variant="primary" busy={opening === inv.workspace_id} onClick={() => open({ id: inv.workspace_id })}>
            افتح {inv.workspace_name}
          </Button>
        ) : (
          <Link to={`/workspaces/${inv.workspace_id}?plan=${inv.plan}&cycle=${inv.cycle}`}>
            <Button variant="primary">حاول مرة أخرى</Button>
          </Link>
        )}
        <Link to="/invoices">
          <Button>الفواتير</Button>
        </Link>
      </div>
    </div>
  );
}
