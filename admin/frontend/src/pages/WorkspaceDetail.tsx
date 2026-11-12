import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ExternalLink, LogIn } from "lucide-react";
import { toast } from "sonner";
import { openWithSession, openWorkspaceWithSession } from "@/lib/handoff";
import { workspaceUrl } from "@/lib/urls";
import { actions, type Module, useAction, useModules, useWorkspace, type WorkspaceDetail as Detail } from "@app/lib/data";
import { ago, categoryLabel, date, dateTime, errorText, moduleLabel, modeLabel, money, num, PLANS, planLabel, plural, pulse, sectorLabel, trialText } from "@app/lib/format";
import {
  ActivityList,
  Badge,
  Button,
  Confirm,
  Dot,
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
  Select,
  StatusBadge,
  Table,
  Tabs,
  Td,
  Textarea,
} from "@app/ui";
import { InvoiceTable } from "@app/pages/Billing";
import { PlanCell } from "@app/pages/Workspaces";

type Tab = "summary" | "plan" | "licence" | "modules" | "people" | "activity" | "settings";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 text-sm">
      <dt className="text-mute">{label}</dt>
      <dd className="text-right text-ink">{children}</dd>
    </div>
  );
}

// ─── Summary ───────────────────────────────────────────────────────────────

function Summary({ d }: { d: Detail }) {
  const w = d.workspace;
  const p = pulse(d.stats.last_sale_at);
  return (
    <div className="grid gap-6">
      <Figures
        items={[
          { label: "Sales", value: money(d.stats.sales_volume_egp), hint: plural(d.stats.sales, "sale") },
          { label: "Products", value: num(d.stats.products) },
          { label: "People", value: num(d.stats.users) },
          { label: "Branches", value: num(d.stats.branches) },
        ]}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Workspace">
          <dl className="divide-y divide-line-soft">
            <Row label="Business type">{sectorLabel(w.sector)}</Row>
            <Row label="Size">{{ small: "One branch", medium: "2–3 branches", large: "4 or more branches" }[w.scale] ?? w.scale}</Row>
            <Row label="Owner">
              {d.owner ? (
                <>
                  <span className="bidi">{d.owner.full_name}</span> <span className="code text-mute">@{d.owner.username}</span>
                </>
              ) : (
                "—"
              )}
            </Row>
            <Row label="Last sale">
              <Dot tone={p.tone} label={p.label} />
            </Row>
            <Row label="Created">{dateTime(w.created_at)}</Row>
          </dl>
        </Panel>
        <Panel title="Branches" aside={plural(d.branches.length, "branch", "branches")} flush>
          {d.branches.length ? (
            <ul className="divide-y divide-line-soft">
              {d.branches.map((b) => (
                <li key={b.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                  <span className="bidi">{b.name}</span>
                  {!b.is_active && <Badge>Closed</Badge>}
                </li>
              ))}
            </ul>
          ) : (
            <Empty title="No branches yet." />
          )}
        </Panel>
      </div>
    </div>
  );
}

// ─── Plan & billing ────────────────────────────────────────────────────────

function PlanTab({ d }: { d: Detail }) {
  const w = d.workspace;
  const [plan, setPlan] = useState(w.plan);
  const [confirming, setConfirming] = useState(false);
  const setPlanM = useAction(actions.setPlan, { success: (v) => `Moved to ${planLabel(v.plan)}` });
  const extend = useAction(actions.extendTrial, { success: (v) => `Trial extended by ${v.days} days` });
  const trial = trialText(w.trial_days_left);

  return (
    <div className="grid gap-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Current plan">
          <div className="flex items-baseline justify-between">
            <div className="text-2xl font-bold tracking-[-0.02em] text-ink">{planLabel(w.plan)}</div>
            <div className="data text-sm text-mute">{w.monthly_price_egp ? `${money(w.monthly_price_egp)}/month` : "Free"}</div>
          </div>
          {w.plan === "trial" && (
            <div className="mt-3">
              <Badge tone={trial.tone}>{trial.text}</Badge>
              {w.trial_ends_at && <span className="ml-2 text-[13px] text-mute">Ends {date(w.trial_ends_at)}</span>}
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-[13px] text-ink-2">Extend by</span>
                {[7, 14, 30].map((days) => (
                  <Button
                    key={days}
                    size="sm"
                    busy={extend.isPending && extend.variables?.days === days}
                    onClick={() => extend.mutate({ id: w.id, days })}
                  >
                    {days} days
                  </Button>
                ))}
              </div>
            </div>
          )}
        </Panel>
        <Panel title="Change plan">
          <p className="mb-3 text-[13px] text-mute">
            Applies the plan's limits now, without an invoice. Use it for agreed deals; paid upgrades should go through an invoice.
          </p>
          <div className="flex gap-2">
            <Select value={plan} onChange={(e) => setPlan(e.target.value)} aria-label="Plan">
              {Object.entries(PLANS).map(([v, p]) => (
                <option key={v} value={v}>
                  {p.label}
                  {p.price ? ` — EGP ${p.price}/month` : " — 14 days"}
                </option>
              ))}
            </Select>
            <Button variant="primary" disabled={plan === w.plan} onClick={() => setConfirming(true)}>
              Change
            </Button>
          </div>
        </Panel>
      </div>

      <Panel title="Invoices" flush>
        <InvoiceTable invoices={d.invoices.map((i) => ({ ...i, tenant_id: w.id, tenant_name: w.name }))} />
      </Panel>


      <Confirm
        open={confirming}
        onClose={() => setConfirming(false)}
        title={`Move ${w.name} to ${planLabel(plan)}?`}
        body={
          plan === "trial"
            ? "It goes back to a fresh 14-day trial with trial limits."
            : `Its limits change to ${planLabel(plan)} now and any trial ends. No invoice is created.`
        }
        confirmLabel={`Move to ${planLabel(plan)}`}
        withReason
        onConfirm={(reason) => setPlanM.mutateAsync({ id: w.id, plan, reason: reason || undefined })}
      />
    </div>
  );
}

// ─── Modules ───────────────────────────────────────────────────────────────

function ModulesTab({ d }: { d: Detail }) {
  const catalog = useModules();
  const save = useAction(actions.setModules, { success: () => "Modules saved" });
  const initial = d.workspace.active_modules;
  const [selected, setSelected] = useState<Set<string>>(new Set(initial));
  const [filter, setFilter] = useState("");
  const dirty = selected.size !== initial.length || initial.some((m) => !selected.has(m));
  const groups = useMemo(() => {
    const by: Record<string, Module[]> = {};
    const f = filter.trim().toLowerCase();
    for (const m of catalog.data?.items ?? []) {
      if (f && !`${moduleLabel(m)} ${m.id}`.toLowerCase().includes(f)) continue;
      (by[categoryLabel(m.category)] ??= []).push(m);
    }
    return Object.entries(by).sort(([a], [b]) => a.localeCompare(b));
  }, [catalog.data, filter]);
  const core = initial.filter((m) => !catalog.data?.items.some((c) => c.id === m));

  if (catalog.isPending) return <PageSkeleton />;
  if (catalog.isError) return <LoadError error={catalog.error} retry={() => catalog.refetch()} />;

  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  return (
    <div className="grid gap-6">
      <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Find a module" className="max-w-sm" aria-label="Find a module" />
      <p className="-mt-2 text-sm text-ink-2">
        <span className="font-semibold text-ink">{selected.size} on.</span> Turn industry modules on or off for this workspace. People in the workspace see the change the next time they open it.
        {core.length > 0 && (
          <>
            {" "}
            Always on: <span className="code text-[13px]">{core.join(", ")}</span>.
          </>
        )}
      </p>
      {!groups.length && <Empty title={`No module matches “${filter}”.`} />}
      <div className="grid gap-4 md:grid-cols-2">
        {groups.map(([group, mods]) => (
          <Panel key={group} title={group}>
            <ul className="grid gap-1">
              {mods.map((m) => (
                <li key={m.id}>
                  <label className="flex cursor-pointer items-center gap-2.5 rounded px-1.5 py-1.5 text-sm hover:bg-paper">
                    <input type="checkbox" className="size-4 accent-ox" checked={selected.has(m.id)} onChange={() => toggle(m.id)} />
                    <span className="flex-1 text-ink">{moduleLabel(m)}</span>
                    <span className="code text-[11px] text-mute">{m.id}</span>
                  </label>
                </li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>
      {dirty && (
        <div className="sticky bottom-4 flex items-center justify-between gap-4 rounded-lg border border-line bg-ink px-4 py-3 text-sm text-white shadow-lg">
          <span>Unsaved changes to modules</span>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" className="text-white hover:bg-card/10 hover:text-white" onClick={() => setSelected(new Set(initial))}>
              Discard
            </Button>
            <Button
              size="sm"
              variant="primary"
              busy={save.isPending}
              onClick={() =>
                save
                  .mutateAsync({ id: d.workspace.id, modules: [...core, ...[...selected].filter((m) => !core.includes(m))] })
                  .catch((e) => toast.error(errorText(e)))
              }
            >
              Save modules
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── People ────────────────────────────────────────────────────────────────

const ROLE: Record<string, string> = {
  admin: "Owner / admin",
  manager: "Manager",
  cashier: "Cashier",
  accountant: "Accountant",
  storekeeper: "Storekeeper",
  superadmin: "Platform admin",
};

function PeopleTab({ d }: { d: Detail }) {
  return (
    <Panel flush>
      <Table head={["Name", "Username", "Role", "Status", "Added"]}>
        {d.users.map((u) => (
          <tr key={u.id}>
            <Td className="bidi font-semibold">{u.full_name}</Td>
            <Td className="code text-[13px] text-ink-2">@{u.username}</Td>
            <Td className="text-ink-2">{ROLE[u.role] ?? u.role}</Td>
            <Td>{u.is_active ? <Badge tone="ok">Active</Badge> : <Badge>Disabled</Badge>}</Td>
            <Td className="text-ink-2">{date(u.created_at)}</Td>
          </tr>
        ))}
      </Table>
    </Panel>
  );
}

// ─── Settings ──────────────────────────────────────────────────────────────

function SettingsTab({ d }: { d: Detail }) {
  const navigate = useNavigate();
  const w = d.workspace;
  const [name, setName] = useState(w.name);
  const [slug, setSlug] = useState(w.slug ?? "");
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [typed, setTyped] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const update = useAction(actions.update, { success: () => "Saved" });
  const qc = useQueryClient();
  const remove = useAction(actions.remove, {
    success: () => `${w.name} deleted`,
    then: (v) => {
      qc.removeQueries({ queryKey: ["workspace", v.id] });
      navigate("/workspaces");
    },
  });
  const confirmWord = w.slug ?? w.id;

  return (
    <div className="grid gap-6">
      <Panel title="Name and address">
        <form
          className="grid max-w-xl gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            update
              .mutateAsync({ id: w.id, name: name.trim() !== w.name ? name.trim() : undefined, slug: slug !== w.slug ? slug : undefined })
              .catch((err) => setError(errorText(err)));
          }}
        >
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} className="bidi" minLength={2} required />
          </Field>
          <Field label="URL name" hint={<span className="code">{workspaceUrl(slug || "…").replace(/\/$/, "")}</span>}>
            <Input value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase())} pattern="[a-z0-9\-]{3,48}" className="code" required />
          </Field>
          {slug !== w.slug && (
            <p className="text-[13px] text-warn">Changing the URL name breaks bookmarks and links people already use for this workspace.</p>
          )}
          {error && <ErrorNote>{error}</ErrorNote>}
          <div>
            <Button type="submit" variant="primary" busy={update.isPending} disabled={name.trim() === w.name && slug === w.slug}>
              Save changes
            </Button>
          </div>
        </form>
      </Panel>

      <section className="rounded-lg border border-bad/30 bg-card">
        <div className="border-b border-bad/20 px-4 py-3">
          <h2 className="text-sm font-bold text-bad">Delete workspace</h2>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-4 p-4">
          <p className="max-w-xl text-sm text-ink-2">
            Permanently deletes the workspace with its {plural(d.stats.users, "person", "people")}, {plural(d.stats.products, "product")},{" "}
            {plural(d.stats.sales, "sale")} and invoices. This can't be undone. Suspending keeps the data.
          </p>
          <Button variant="danger" onClick={() => setDeleting(true)}>
            Delete workspace
          </Button>
        </div>
      </section>

      <Modal
        open={deleting}
        onClose={() => {
          setDeleting(false);
          setTyped("");
          setDeleteError(null);
        }}
        title={`Delete ${w.name}?`}
        description="Everything in this workspace is deleted permanently."
      >
        <Field label={`Type ${confirmWord} to confirm`}>
          <Input value={typed} onChange={(e) => setTyped(e.target.value)} className="code" autoComplete="off" />
        </Field>
        {deleteError && <ErrorNote>{deleteError}</ErrorNote>}
        <ModalActions>
          <Button variant="ghost" onClick={() => setDeleting(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={typed !== confirmWord}
            busy={remove.isPending}
            onClick={() =>
              remove.mutateAsync({ id: w.id, confirm: typed }).catch((e) => setDeleteError(errorText(e)))
            }
          >
            Delete permanently
          </Button>
        </ModalActions>
      </Modal>
    </div>
  );
}

// ─── Licence (single-device and LAN workspaces) ───────────────────────────

const LICENCE_TONE = { active: "ok", expired: "bad", revoked: "bad" } as const;

function LicenceTab({ d }: { d: Detail }) {
  const lic = d.licence!;
  const w = d.workspace;
  const [days, setDays] = useState(30);
  const [reason, setReason] = useState("");
  const [revoking, setRevoking] = useState(false);
  const [key, setKey] = useState<string | null>(null);
  const extend = useAction(actions.extendLicence, { success: (v) => `Licence extended by ${v.days} days` });
  const revoke = useAction(actions.revokeLicence, { success: (v) => (v.revoked ? "Licence revoked" : "Licence restored") });
  const issue = useAction(actions.licenceKey, { then: (_, r) => setKey(r.licence_key) });

  return (
    <div className="grid gap-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Licence">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={LICENCE_TONE[lic.status]}>{lic.status === "active" ? "Active" : lic.status === "expired" ? "Expired" : "Revoked"}</Badge>
            <span className="text-sm text-ink-2">{modeLabel(lic.mode)}</span>
          </div>
          <dl className="mt-4 divide-y divide-line-soft">
            <Row label="Valid until">{dateTime(lic.valid_until)}</Row>
            {lic.revoked_at && <Row label="Revoked">{dateTime(lic.revoked_at)}</Row>}
            <Row label="Installs">{num(d.installations.length)}</Row>
          </dl>
          <p className="mt-3 text-[13px] text-mute">
            Paying an invoice moves the end date to the end of the paid period. Installs pick up the new date when they check in.
          </p>
        </Panel>
        <Panel title="Extend">
          <div className="grid gap-3">
            <Field label="Days to add" hint="Counted from today if the licence has already ended.">
              <Input type="number" min={1} max={3660} value={days} onChange={(e) => setDays(Number(e.target.value))} />
            </Field>
            <Field label="Reason (optional)">
              <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. paid by bank transfer" />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" busy={extend.isPending} disabled={days < 1}
                onClick={() => extend.mutate({ id: w.id, days, reason: reason.trim() || undefined })}>
                Extend licence
              </Button>
              <Button busy={issue.isPending} onClick={() => issue.mutate(w.id)}>
                Issue offline key
              </Button>
              <Button variant={lic.status === "revoked" ? "primary" : "danger"} onClick={() => setRevoking(true)}>
                {lic.status === "revoked" ? "Restore licence" : "Revoke licence"}
              </Button>
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="Installations" flush>
        {d.installations.length ? (
          <Table head={["Computer", "System", "Version", "Last seen", "Last backup", "First seen"]}>
            {d.installations.map((i) => (
              <tr key={i.id}>
                <Td>
                  <div className="code text-[13px] text-ink">{i.hostname ?? "—"}</div>
                  <div className="code text-[11px] text-mute">{i.last_ip ?? ""}</div>
                </Td>
                <Td className="text-ink-2">{i.os ?? "—"}</Td>
                <Td className="code text-[13px]">{i.app_version ?? "—"}</Td>
                <Td className="text-ink-2">{ago(i.last_seen_at)}</Td>
                <Td className="text-ink-2">{i.last_backup_at ? ago(i.last_backup_at) : "Never"}</Td>
                <Td className="text-ink-2">{date(i.first_seen_at)}</Td>
              </tr>
            ))}
          </Table>
        ) : (
          <Empty title="Not installed yet.">Installs appear here when they first check in with Mizan.</Empty>
        )}
      </Panel>

      <Confirm
        open={revoking}
        onClose={() => setRevoking(false)}
        title={lic.status === "revoked" ? `Restore ${w.name}'s licence?` : `Revoke ${w.name}'s licence?`}
        body={
          lic.status === "revoked"
            ? "Installs become writable again when they next check in (or with a new key)."
            : "Installs become read-only when they next check in. Installs that never go online keep working until their key ends."
        }
        confirmLabel={lic.status === "revoked" ? "Restore" : "Revoke licence"}
        danger={lic.status !== "revoked"}
        withReason
        onConfirm={(r) => revoke.mutateAsync({ id: w.id, revoked: lic.status !== "revoked", reason: r || undefined })}
      />
      <Modal open={!!key} onClose={() => setKey(null)} title="Offline licence key" description="For an install that never goes online: paste it in the app (licence banner → Enter licence key). Logged in Activity." wide>
        <Textarea readOnly value={key ?? ""} className="code h-32 text-[11px]" onFocus={(e) => e.currentTarget.select()} />
        <ModalActions>
          <Button onClick={() => navigator.clipboard.writeText(key ?? "").then(() => toast.success("Key copied"))}>Copy key</Button>
        </ModalActions>
      </Modal>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────

export default function WorkspaceDetail() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "summary";
  const q = useWorkspace(id);
  const setStatus = useAction(actions.setStatus, { success: (v) => (v.status === "suspended" ? "Suspended" : "Reactivated") });
  const [statusOpen, setStatusOpen] = useState(false);
  const [opening, setOpening] = useState(false);

  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  const w = d.workspace;
  const suspended = w.status === "suspended";

  async function openAsOwner() {
    setOpening(true);
    try {
      const r = await actions.impersonate(w.id);
      toast.success(`Opening as ${r.as_user}`);
      if (r.slug) openWorkspaceWithSession(r.slug, "/", r.access_token);
      else openWithSession("system", "/", r.access_token);
    } catch (e) {
      toast.error(errorText(e));
      setOpening(false);
    }
  }

  return (
    <>
      <PageHeader
        crumb={
          <Link to="/workspaces" className="hover:text-ink">
            Workspaces
          </Link>
        }
        title={<span className="bidi">{w.name}</span>}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={w.status} />
            <PlanCell w={w} />
            {w.deployment_mode !== "cloud_saas" && <Badge tone="info">{modeLabel(w.deployment_mode)}</Badge>}
            {w.slug && (
              <a href={workspaceUrl(w.slug)} target="_blank" rel="noreferrer" className="code inline-flex items-center gap-1 text-[13px] text-mute hover:text-ox">
                /c/{w.slug} <ExternalLink className="size-3" />
              </a>
            )}
          </span>
        }
        actions={
          <>
            <Button variant={suspended ? "primary" : "secondary"} onClick={() => setStatusOpen(true)}>
              {suspended ? "Reactivate" : "Suspend"}
            </Button>
            {w.deployment_mode === "cloud_saas" && (
              <Button variant="primary" busy={opening} onClick={openAsOwner} disabled={suspended} title={suspended ? "Reactivate it first" : undefined}>
                <LogIn /> Open as owner
              </Button>
            )}
          </>
        }
      />

      <Tabs
        value={tab}
        onChange={(t) => setParams(t === "summary" ? {} : { tab: t }, { replace: true })}
        items={[
          { value: "summary", label: "Summary" },
          { value: "plan", label: "Plan & billing", count: d.invoices.filter((i) => i.status === "pending").length || undefined },
          { value: "modules", label: "Modules", count: w.active_modules.length },
          { value: "people", label: "People", count: d.users.length },
          { value: "activity", label: "Activity" },
          ...(d.licence ? [{ value: "licence" as Tab, label: "Licence", count: d.installations.length || undefined }] : []),
          { value: "settings", label: "Settings" },
        ]}
      />

      {tab === "summary" && <Summary d={d} />}
      {tab === "plan" && <PlanTab d={d} />}
      {tab === "modules" && <ModulesTab key={w.active_modules.join()} d={d} />}
      {tab === "people" && <PeopleTab d={d} />}
      {tab === "activity" && (
        <Panel flush>
          <ActivityList items={d.activity} empty="No admin actions on this workspace yet." />
        </Panel>
      )}
      {tab === "licence" && d.licence && <LicenceTab d={d} />}
      {tab === "settings" && <SettingsTab d={d} />}

      <Confirm
        open={statusOpen}
        onClose={() => setStatusOpen(false)}
        title={suspended ? `Reactivate ${w.name}?` : `Suspend ${w.name}?`}
        body={
          suspended
            ? "Its people can sign in and work again."
            : "Its people are blocked from the app until you reactivate it. Nothing is deleted."
        }
        confirmLabel={suspended ? "Reactivate" : "Suspend workspace"}
        danger={!suspended}
        withReason
        onConfirm={(reason) => setStatus.mutateAsync({ id: w.id, status: suspended ? "active" : "suspended", reason: reason || undefined })}
      />
    </>
  );
}
