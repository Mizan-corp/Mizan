import { useState } from "react";
import { actions, type Listing, type Submission, useAction, useListings, useSubmission, useSubmissions } from "@app/lib/data";
import { ago, date, num, plural } from "@app/lib/format";
import {
  Badge,
  Button,
  Confirm,
  Empty,
  ErrorNote,
  Field,
  LoadError,
  Modal,
  ModalActions,
  PageHeader,
  Panel,
  Skeleton,
  Table,
  Tabs,
  Td,
  Textarea,
} from "@app/ui";

const KIND = { community: "Module", theme: "Theme", activity: "Activity" } as const;
const STATUS: Record<Submission["status"], { label: string; tone: "warn" | "ok" | "bad" | "mute" }> = {
  in_review: { label: "In review", tone: "warn" },
  approved: { label: "Approved", tone: "ok" },
  rejected: { label: "Rejected", tone: "bad" },
  withdrawn: { label: "Withdrawn", tone: "mute" },
};

const kb = (n: number) => (n < 1024 ? `${num(n)} B` : `${(n / 1024).toFixed(1)} KB`);

/** Review a developer's package version (#105): approving countersigns it and lists it in the store. */
export function SubmissionReview({ id, open, onClose }: { id: string; open: boolean; onClose: () => void }) {
  const q = useSubmission(id, open);
  const [note, setNote] = useState("");
  const approve = useAction(actions.approveSubmission, { success: () => "Approved and listed", then: onClose });
  const reject = useAction(actions.rejectSubmission, { success: () => "Submission rejected", then: onClose });
  const s = q.data;

  return (
    <Modal
      open={open}
      onClose={onClose}
      wide
      title={s ? `${s.name_en || s.name || s.item_id} ${s.version}` : "Submission"}
      description={
        s ? (
          <>
            {KIND[s.kind]} from <span className="code">{s.developer}</span> · {ago(s.submitted_at)} ·{" "}
            {s.listed_version ? <>listed version <span className="code">{s.listed_version}</span></> : "new listing"}
          </>
        ) : undefined
      }
    >
      {q.isPending && <Skeleton className="h-32" />}
      {q.isError && <ErrorNote>Couldn't load the submission.</ErrorNote>}
      {s && (
        <div className="grid gap-3 text-[13px]">
          {s.verify_error && <ErrorNote>The package no longer verifies: {s.verify_error}</ErrorNote>}
          {s.manifest.description && <p className="bidi text-ink-2">{s.manifest.description}</p>}
          {s.summary && (
            <>
              <div className="rounded-lg bg-paper px-3.5 py-2.5">
                <p className="font-semibold text-ink">Adds</p>
                {s.summary.entities.length ? (
                  <ul className="mt-0.5 flex flex-wrap gap-x-3 text-ink-2">
                    {s.summary.entities.map((e) => (
                      <li key={e.id}>
                        <bdi className="font-semibold">{e.name}</bdi> records, {plural(e.fields, "field")}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-0.5 text-ink-2">No records</p>
                )}
              </div>
              <div className="rounded-lg bg-warn/10 px-3.5 py-2.5">
                <p className="font-semibold text-ink">May access</p>
                {s.summary.scopes.length ? (
                  <ul className="mt-1 flex flex-wrap gap-1.5">
                    {s.summary.scopes.map((x) => (
                      <li key={x.id} className="flex items-center gap-1 text-ink-2">
                        {x.text_en} <span className="code text-mute">({x.id})</span>
                        {x.new && <Badge tone="warn">New</Badge>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-0.5 text-ink-2">Nothing in the workspace</p>
                )}
                {s.summary.sends_to && (
                  <p className="mt-1 text-ink-2">
                    Sends events to <span className="code">{s.summary.sends_to}</span>
                  </p>
                )}
              </div>
              {!!s.manifest.permissions?.length && (
                <p className="text-ink-2">
                  Permissions: {s.manifest.permissions.map((p) => p.name_en).join(", ")}
                </p>
              )}
            </>
          )}
          {s.theme && (
            <div className="flex items-center gap-3 rounded-lg bg-paper px-3.5 py-2.5">
              <div className="flex overflow-hidden rounded-md border border-line" aria-label="Theme colours">
                {s.theme.swatches.map((c, i) => (
                  <span key={i} className="size-6" style={{ background: c }} title={c} />
                ))}
              </div>
              <p className="text-ink-2">
                {s.theme.fonts.body ?? "Default font"}
                {s.theme.radius && <> · radius <span className="code">{s.theme.radius}</span></>}
                {s.theme.motion && <> · motion {s.theme.motion}</>}
              </p>
            </div>
          )}
          {s.activity && (
            <>
              <div className="rounded-lg bg-paper px-3.5 py-2.5">
                <p className="font-semibold text-ink">
                  A {s.activity.family} activity · {plural(s.activity.menu_groups, "menu group")} · home <span className="code">{s.activity.home ?? "—"}</span>
                </p>
                <p className="mt-0.5 text-ink-2">Runs Mizan's {s.activity.modules.map((m) => m.name).join(", ")}</p>
                {s.activity.optional.length > 0 && <p className="text-ink-2">Optional: {s.activity.optional.map((m) => m.name).join(", ")}</p>}
                {s.activity.variants.length > 0 && (
                  <p className="text-ink-2">
                    Adapts {s.activity.variants.map((v) => `${v.module} (${plural(v.fields, "field")}, ${plural(v.terms, "term")}, ${plural(v.settings, "setting")})`).join(", ")}
                  </p>
                )}
                {s.activity.positions.length > 0 && <p className="text-ink-2">Positions: {s.activity.positions.join(", ")}</p>}
                {s.activity.themes.length > 0 && <p className="text-ink-2">Themes: {s.activity.themes.map((t) => t.name).join(", ")}</p>}
              </div>
              {s.activity.own_modules.map((m) => (
                <div key={m.id} className="rounded-lg bg-warn/10 px-3.5 py-2.5">
                  <p className="font-semibold text-ink">
                    Its module <bdi>{m.name}</bdi> <span className="code text-mute">{m.id}</span> · {plural(m.entities, "record type")}
                  </p>
                  <p className="mt-0.5 text-ink-2">
                    May access {m.scopes.length ? m.scopes.map((x) => <span key={x} className="code">{x} </span>) : "nothing else"}
                    {m.sends_to && <> · sends events to <span className="code">{m.sends_to}</span></>}
                  </p>
                </div>
              ))}
              {!!s.workspaces && (
                <p className="rounded-lg bg-info/10 px-3.5 py-2.5 text-ink-2">
                  {plural(s.workspaces, "workspace")} run this activity: approving updates them at once (new modules join; nothing leaves).
                </p>
              )}
            </>
          )}
          <details className="rounded-lg border border-line-soft px-3.5 py-2.5">
            <summary className="cursor-pointer font-semibold text-ink">
              {plural(s.files.length, "file")} · {kb(s.size)} · <span className="code font-normal text-mute">sha256 {s.sha256.slice(0, 16)}…</span>
            </summary>
            <ul className="mt-2 grid gap-0.5">
              {s.files.map((f) => (
                <li key={f.name} className="flex justify-between gap-3">
                  <span className="code truncate">{f.name}</span>
                  <span className="data text-mute">{kb(f.size)}</span>
                </li>
              ))}
            </ul>
            <pre className="code mt-2 max-h-64 overflow-auto rounded bg-paper p-2 text-[12px]" dir="ltr">
              {JSON.stringify(s.manifest, null, 2)}
            </pre>
          </details>
          {s.status === "in_review" ? (
            <Field label="Note" hint="Required to reject: the developer sees it.">
              <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000} />
            </Field>
          ) : (
            <p className="text-mute">
              {STATUS[s.status].label} {s.reviewed_at && ago(s.reviewed_at)}
              {s.review_note && <> · “{s.review_note}”</>}
            </p>
          )}
          {(approve.isError || reject.isError) && <ErrorNote>{String((approve.error ?? reject.error) as Error)}</ErrorNote>}
        </div>
      )}
      <ModalActions>
        <Button variant="ghost" onClick={onClose}>Close</Button>
        {s?.status === "in_review" && (
          <>
            <Button busy={reject.isPending} disabled={!note.trim()} onClick={() => reject.mutate({ id, note: note.trim() })}>
              Reject
            </Button>
            <Button variant="primary" busy={approve.isPending} disabled={!!s.verify_error} onClick={() => approve.mutate({ id, note: note.trim() || undefined })}>
              Approve and list
            </Button>
          </>
        )}
      </ModalActions>
    </Modal>
  );
}

function Submissions({ status }: { status: string }) {
  const q = useSubmissions(status);
  const [open, setOpen] = useState<string | null>(null);
  if (q.isPending) return <Skeleton className="m-4 h-24" />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  if (!q.data.items.length)
    return <Empty title={status === "in_review" ? "Nothing to review." : "No submissions here."}>Developers send packages from the portal or with mizan publish.</Empty>;
  return (
    <>
      <Table head={["Package", "Version", "Kind", "Developer", "Sent", "Status", ""]}>
        {q.data.items.map((s) => (
          <tr key={s.id}>
            <Td>
              <span className="bidi font-semibold">{s.name_en || s.name}</span>
              <div className="code text-xs text-mute">{s.item_id}</div>
            </Td>
            <Td className="code text-[13px]">{s.version}</Td>
            <Td className="text-ink-2">{KIND[s.kind]}</Td>
            <Td className="code text-[13px] text-ink-2">{s.developer}</Td>
            <Td className="text-ink-2">{ago(s.submitted_at)}</Td>
            <Td>
              <Badge tone={STATUS[s.status].tone}>{STATUS[s.status].label}</Badge>
            </Td>
            <Td className="text-right">
              <Button size="sm" variant={s.status === "in_review" ? "primary" : "ghost"} onClick={() => setOpen(s.id)}>
                {s.status === "in_review" ? "Review" : "View"}
              </Button>
            </Td>
          </tr>
        ))}
      </Table>
      {open && <SubmissionReview id={open} open onClose={() => setOpen(null)} />}
    </>
  );
}

function Listings() {
  const q = useListings();
  const relist = useAction(actions.setListed, { success: (v) => `${v.id} is back in the store` });
  const delist = useAction(actions.setListed, { success: (v) => `${v.id} was removed from the store` });
  const [delisting, setDelisting] = useState<Listing | null>(null);
  if (q.isPending) return <Skeleton className="m-4 h-24" />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  if (!q.data.items.length) return <Empty title="Nothing is listed yet.">Approved submissions appear here.</Empty>;
  return (
    <>
      <Table head={["Listing", "Version", "Kind", "Developer", "Installs", "Updated", "Status", ""]}>
        {q.data.items.map((it) => (
          <tr key={it.id}>
            <Td>
              <span className="bidi font-semibold">{it.name_en || it.name}</span>
              <div className="code text-xs text-mute">{it.id}</div>
            </Td>
            <Td className="code text-[13px]">{it.version}</Td>
            <Td className="text-ink-2">{KIND[it.kind]}</Td>
            <Td className="code text-[13px] text-ink-2">{it.developer}</Td>
            <Td className="data">{num(it.installs)}</Td>
            <Td className="text-ink-2">{date(it.updated_at)}</Td>
            <Td>
              {it.status === "listed" ? <Badge tone="ok">Listed</Badge> : <Badge tone="bad">Delisted</Badge>}
              {it.status_note && it.status === "delisted" && <div className="bidi mt-0.5 text-xs text-mute">{it.status_note}</div>}
            </Td>
            <Td className="text-right">
              {it.status === "listed" ? (
                <Button size="sm" variant="ghost" onClick={() => setDelisting(it)}>Delist</Button>
              ) : (
                <Button size="sm" busy={relist.isPending && relist.variables?.id === it.id} onClick={() => relist.mutate({ id: it.id, listed: true })}>
                  Relist
                </Button>
              )}
            </Td>
          </tr>
        ))}
      </Table>
      <Confirm
        open={!!delisting}
        onClose={() => setDelisting(null)}
        title={`Delist ${delisting?.name_en || delisting?.name}?`}
        body="It disappears from the store and can't be installed. Workspaces that installed it keep it."
        confirmLabel="Delist"
        danger
        withReason
        onConfirm={(reason) => delist.mutateAsync({ id: delisting!.id, listed: false, note: reason })}
      />
    </>
  );
}

type Tab = "in_review" | "approved" | "rejected" | "listings";

export default function Marketplace() {
  const [tab, setTab] = useState<Tab>("in_review");
  const pending = useSubmissions("in_review");
  return (
    <>
      <PageHeader
        title="Marketplace"
        description="Developers' modules and themes. Approving a version countersigns it and puts it in every workspace's store."
      />
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { value: "in_review", label: "In review", count: pending.data?.items.length },
          { value: "approved", label: "Approved" },
          { value: "rejected", label: "Rejected" },
          { value: "listings", label: "Listings" },
        ]}
      />
      <Panel flush>{tab === "listings" ? <Listings /> : <Submissions key={tab} status={tab} />}</Panel>
    </>
  );
}
