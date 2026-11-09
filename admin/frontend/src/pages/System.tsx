import { CheckCircle2, AlertTriangle } from "lucide-react";
import { useSystem } from "@app/lib/data";
import { num } from "@app/lib/format";
import { Badge, Figures, LoadError, PageHeader, PageSkeleton, Panel } from "@app/ui";

function uptime(s: number) {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
}

function Check({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2.5 py-2 text-sm">
      {ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />}
      <span className={ok ? "text-ink-2" : "text-ink"}>{children}</span>
    </li>
  );
}

export default function System() {
  const q = useSystem();
  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const { database: db, migrations, records, service } = q.data;
  const connPct = Math.round((db.connections / db.max_connections) * 100);

  return (
    <>
      <PageHeader
        title="System"
        description="Live readings from the database and this API. Refreshes every 30 seconds."
        actions={<Badge tone={service.environment === "production" ? "ox" : "info"}>{service.environment}</Badge>}
      />

      <Figures
        items={[
          { label: "Database response", value: `${db.latency_ms} ms` },
          { label: "Database size", value: `${num(db.size_mb)} MB` },
          { label: "Connections", value: `${db.connections} / ${db.max_connections}`, hint: `${connPct}% of the limit` },
          { label: "Migrations", value: `${migrations.applied} / ${migrations.total}` },
        ]}
      />

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Checks">
          <ul className="divide-y divide-line-soft">
            <Check ok={migrations.pending.length === 0}>
              {migrations.pending.length === 0 ? (
                "Every migration is applied."
              ) : (
                <>
                  {migrations.pending.length} migration{migrations.pending.length === 1 ? " is" : "s are"} not applied:{" "}
                  <span className="code text-[13px]">{migrations.pending.join(", ")}</span>. Run{" "}
                  <span className="code text-[13px]">python manage.py db migrate</span>.
                </>
              )}
            </Check>
            <Check ok={db.tenant_tables_without_rls === 0}>
              {db.tenant_tables_without_rls === 0
                ? "Row-level security is on for every table that holds workspace data."
                : `${db.tenant_tables_without_rls} tables with workspace data have row-level security off.`}
            </Check>
            <Check ok={connPct < 80}>
              {connPct < 80 ? "Plenty of database connections left." : "The database is close to its connection limit."}
            </Check>
          </ul>
        </Panel>

        <Panel title="What's stored">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            {Object.entries(records).map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between border-b border-line-soft pb-2">
                <dt className="text-mute capitalize">{k}</dt>
                <dd className="data text-ink">{num(v)}</dd>
              </div>
            ))}
            <div className="flex items-baseline justify-between border-b border-line-soft pb-2">
              <dt className="text-mute">Tables</dt>
              <dd className="data text-ink">{num(db.tables)}</dd>
            </div>
          </dl>
        </Panel>

        <Panel title="This API">
          <dl className="grid gap-2 text-sm">
            {[
              ["Running on", { vercel: "Vercel", docker: "Docker", local: "This machine" }[service.host] ?? service.host],
              ["Up for", uptime(service.uptime_seconds)],
              ["Python", service.python],
              ["PostgreSQL", db.version],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-line-soft pb-2">
                <dt className="text-mute">{k}</dt>
                <dd className="data text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>
    </>
  );
}
