import { useState } from "react";
import { useWebsiteAnalytics } from "@app/lib/data";
import { date, num } from "@app/lib/format";
import { Empty, Figures, LoadError, PageHeader, PageSkeleton, Panel, Segmented, Table, Td } from "@app/ui";

const EVENT_LABEL: Record<string, string> = {
  whatsapp_click: "WhatsApp clicks",
  phone_click: "Phone clicks",
  contact_submit: "Contact form sent",
  demo_request: "Demo requests",
  signup_start: "Signups started",
  signup_complete: "Signups completed",
};

type Range = "7" | "30" | "90";

/**
 * The public website's own visit counters (ADR-016): cookieless, counts only, no visitor data.
 * Google Analytics, when it's configured, has its own reports.
 */
export default function Website() {
  const [range, setRange] = useState<Range>("30");
  const q = useWebsiteAnalytics(Number(range));

  const header = (
    <PageHeader
      title="Website"
      description="Page views and actions on allmizan.live, counted without cookies or personal data. Crawlers aren't counted."
      actions={
        <Segmented
          value={range}
          onChange={setRange}
          items={[
            { value: "7", label: "7 days" },
            { value: "30", label: "30 days" },
            { value: "90", label: "90 days" },
          ]}
        />
      }
    />
  );
  if (q.isPending) return <>{header}<PageSkeleton /></>;
  if (q.isError) return <>{header}<LoadError error={q.error} retry={() => q.refetch()} /></>;
  const d = q.data;
  const event = (name: string) => d.events.find((e) => e.name === name)?.count ?? 0;
  const max = Math.max(1, ...d.by_day.map((r) => r.views));
  const en = d.languages.find((l) => l.lang === "en")?.views ?? 0;

  return (
    <>
      {header}
      <Figures
        items={[
          { label: "Page views", value: num(d.page_views), hint: `since ${date(d.since)}` },
          { label: "WhatsApp and phone", value: num(event("whatsapp_click") + event("phone_click")) },
          { label: "Demo requests", value: num(event("demo_request")), hint: `${num(event("contact_submit"))} other messages` },
          { label: "Signups", value: `${num(event("signup_complete"))} / ${num(event("signup_start"))}`, hint: "completed / started" },
          { label: "English pages", value: d.page_views ? `${Math.round((en / d.page_views) * 100)}%` : "—" },
        ]}
      />

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Page views per day">
          {d.by_day.length === 0 ? (
            <Empty title="No visits counted yet" />
          ) : (
            <ul className="space-y-1.5" aria-label="Page views per day">
              {d.by_day.map((r) => (
                <li key={r.day} className="grid grid-cols-[88px_1fr_56px] items-center gap-3 text-[13px]">
                  <span className="text-mute">{date(r.day)}</span>
                  <span className="h-2 rounded-full bg-line-soft">
                    <span className="block h-2 rounded-full bg-ox" style={{ width: `${(r.views / max) * 100}%` }} />
                  </span>
                  <span className="data text-right text-ink">{num(r.views)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Actions" flush>
          {d.event_pages.length === 0 ? (
            <Empty title="No actions yet" />
          ) : (
            <Table head={["Action", "Page", "Count"]}>
              {d.event_pages.map((r) => (
                <tr key={`${r.name} ${r.path}`}>
                  <Td>{EVENT_LABEL[r.name] ?? r.name}</Td>
                  <Td className="code text-[13px]">{r.path}</Td>
                  <Td className="data">{num(r.count)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>

        <Panel title="Pages" flush>
          {d.pages.length === 0 ? (
            <Empty title="No pages yet" />
          ) : (
            <Table head={["Page", "Views"]}>
              {d.pages.map((r) => (
                <tr key={r.path}>
                  <Td className="code text-[13px]">{r.path}</Td>
                  <Td className="data">{num(r.views)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>

        <Panel title="Where visitors came from" flush>
          {d.referrers.length === 0 ? (
            <Empty title="No referring sites yet">Visits typed in, bookmarked or from apps don't name a site.</Empty>
          ) : (
            <Table head={["Site", "Visits"]}>
              {d.referrers.map((r) => (
                <tr key={r.host}>
                  <Td className="code text-[13px]">{r.host}</Td>
                  <Td className="data">{num(r.views)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>
      </div>
    </>
  );
}
