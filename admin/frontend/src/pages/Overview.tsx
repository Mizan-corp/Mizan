import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { useAuth } from "@/stores/auth";
import { actions, type AttentionItem, useAction, useOverview } from "@app/lib/data";
import { ago, date, money, num, plural, planLabel, sectorLabel } from "@app/lib/format";
import { ActivityList, Badge, Button, Figures, LoadError, PageHeader, PageSkeleton, Panel, WorkspaceLink } from "@app/ui";
import { MarkPaidDialog } from "@app/pages/Billing";
import { ActivityChangeReview } from "@app/pages/ActivityChanges";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

const KIND: Record<AttentionItem["kind"], { label: string; tone: "bad" | "warn" | "info" | "ox" }> = {
  trial_expired: { label: "Trial ended", tone: "bad" },
  invoice_pending: { label: "Unpaid", tone: "warn" },
  trial_ending: { label: "Trial ending", tone: "info" },
  paid_ended: { label: "Read-only", tone: "bad" },
  paid_ending: { label: "Renewal due", tone: "warn" },
  activity_change: { label: "Activity change", tone: "ox" },
};

function AttentionRow({ item }: { item: AttentionItem }) {
  const navigate = useNavigate();
  const extend = useAction(actions.extendTrial, { success: (v) => `Trial extended by ${v.days} days` });
  const [paying, setPaying] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const name = <WorkspaceLink id={item.tenant_id} name={item.tenant_name ?? "Unknown workspace"} />;

  let sentence;
  let action;
  switch (item.kind) {
    case "trial_expired":
      sentence = <>The trial for {name} ended {item.days === 0 ? "today" : `${plural(item.days, "day")} ago`}.</>;
      action = (
        <Button
          size="sm"
          busy={extend.isPending}
          onClick={() => extend.mutate({ id: item.tenant_id, days: 7 })}
        >
          Extend 7 days
        </Button>
      );
      break;
    case "trial_ending":
      sentence = <>The trial for {name} ends {item.days === 0 ? "today" : `in ${plural(item.days, "day")}`}.</>;
      action = (
        <Button size="sm" variant="ghost" onClick={() => navigate(`/workspaces/${item.tenant_id}?tab=plan`)}>
          Review plan
        </Button>
      );
      break;
    case "paid_ended":
    case "paid_ending":
      sentence =
        item.kind === "paid_ended" ? (
          <>The paid period for {name} ended {item.days === 0 ? "today" : `${plural(item.days, "day")} ago`}; it is read-only until renewed.</>
        ) : (
          <>The paid period for {name} ends {item.days === 0 ? "today" : `in ${plural(item.days, "day")}`}.</>
        );
      action = (
        <Button size="sm" variant="ghost" onClick={() => navigate(`/workspaces/${item.tenant_id}?tab=plan`)}>
          Review plan
        </Button>
      );
      break;
    case "invoice_pending":
      sentence = (
        <>
          {name} has an unpaid {planLabel(item.plan)} invoice for <span className="data">{money(item.amount_egp)}</span>{" "}
          <span className="code text-mute">({item.ref})</span>.
        </>
      );
      action = (
        <>
          <Button size="sm" onClick={() => setPaying(true)}>
            Mark paid
          </Button>
          <MarkPaidDialog open={paying} onClose={() => setPaying(false)} invoiceRef={item.ref} amount={item.amount_egp} />
        </>
      );
      break;
    case "activity_change":
      sentence = <>{name} asks to change its activity from {sectorLabel(item.from_activity)} to {sectorLabel(item.to_activity)}.</>;
      action = (
        <>
          <Button size="sm" onClick={() => setReviewing(true)}>
            Review
          </Button>
          <ActivityChangeReview id={item.change_id} open={reviewing} onClose={() => setReviewing(false)} />
        </>
      );
      break;
  }

  const kind = KIND[item.kind];
  return (
    <li className="grid grid-cols-[96px_1fr] items-center gap-x-3 gap-y-2 px-4 py-3 sm:grid-cols-[110px_1fr_auto]">
      <Badge tone={kind.tone} className="justify-self-start">
        {kind.label}
      </Badge>
      <p className="text-sm text-ink-2">
        {sentence}
        {!["trial_expired", "trial_ending", "paid_ended", "paid_ending"].includes(item.kind) && <span className="text-xs text-mute"> {ago(item.at)}</span>}
      </p>
      <div className="col-span-2 flex gap-2 sm:col-span-1 sm:justify-end">{action}</div>
    </li>
  );
}

function SignupBars({ data }: { data: { week: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div>
      <div className="flex h-28 items-end gap-1.5" role="img" aria-label="New workspaces per week, last 12 weeks">
        {data.map((d, i) => (
          <div key={d.week} className="group relative flex h-full flex-1 flex-col justify-end">
            <div
              className={i === data.length - 1 ? "rounded-sm bg-ox" : "rounded-sm bg-ox/30 group-hover:bg-ox/60"}
              style={{ height: `${Math.max(d.count ? 6 : 2, (d.count / max) * 100)}%` }}
            />
            <span className="data pointer-events-none absolute -top-5 left-1/2 hidden -translate-x-1/2 text-[11px] text-ink group-hover:block">
              {d.count}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-mute">
        <span>Week of {date(data[0]?.week)}</span>
        <span>This week</span>
      </div>
    </div>
  );
}

export default function Overview() {
  const user = useAuth((s) => s.user);
  const q = useOverview();
  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const o = q.data;
  const firstName = (user?.full_name || user?.username || "").split(" ")[0];

  return (
    <>
      <PageHeader
        crumb={new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long" }).format(new Date())}
        title={`${greeting()}${firstName && !/[\u0600-\u06FF]/.test(firstName) ? `, ${firstName}` : ""}.`}
        description={
          o.attention.length
            ? `${plural(o.attention.length, "thing")} need${o.attention.length === 1 ? "s" : ""} you today.`
            : "Nothing needs you today."
        }
        actions={
          <Link to="/workspaces?new=1">
            <Button variant="primary">New workspace</Button>
          </Link>
        }
      />

      <Figures
        items={[
          { label: "Workspaces", value: num(o.counts.workspaces), hint: `${num(o.counts.suspended)} suspended` },
          { label: "On trial", value: num(o.counts.on_trial) },
          { label: "Paying", value: num(o.revenue.paying), hint: o.revenue.complimentary ? `+${o.revenue.complimentary} complimentary` : undefined },
          { label: "Monthly revenue", value: money(o.revenue.mrr_egp), hint: "From paid invoices" },
          { label: "People using Mizan", value: num(o.counts.users) },
        ]}
      />

      <Panel className="mt-6" title="Needs you" aside={o.attention.length ? plural(o.attention.length, "item") : undefined} flush>
        {o.attention.length ? (
          <ul className="divide-y divide-line-soft">
            {o.attention.map((a, i) => (
              <AttentionRow key={`${a.kind}-${i}`} item={a} />
            ))}
          </ul>
        ) : (
          <div className="flex items-center gap-3 px-4 py-6 text-sm text-ink-2">
            <CheckCircle2 className="size-5 text-ok" />
            No ended trials or unpaid invoices. Trials ending within 7 days will show up here.
          </div>
        )}
      </Panel>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.15fr]">
        <Panel title="New workspaces" aside={`${num(o.signups_last_30_days)} in the last 30 days`}>
          <SignupBars data={o.signups} />
          <ul className="mt-4 divide-y divide-line-soft border-t border-line-soft">
            {o.newest.map((w) => (
              <li key={w.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="min-w-0 truncate">
                  <WorkspaceLink id={w.id} name={w.name} /> <span className="text-mute">· {sectorLabel(w.sector)}</span>
                </span>
                <span className="shrink-0 text-xs text-mute">
                  {planLabel(w.plan)} · {ago(w.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel
          title="Recent activity"
          aside={
            <Link to="/activity" className="font-semibold text-ox hover:underline">
              All activity
            </Link>
          }
          flush
        >
          <ActivityList items={o.activity} empty="No admin actions yet." />
        </Panel>
      </div>
    </>
  );
}
