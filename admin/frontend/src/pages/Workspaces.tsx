import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { actions, useAction, useWorkspaces, type WorkspaceRow } from "@app/lib/data";
import { ago, date, errorText, money, num, PLANS, planLabel, pulse, SECTOR_OPTIONS, sectorLabel, trialText, MODES } from "@app/lib/format";
import {
  Badge,
  Button,
  Dot,
  Empty,
  ErrorNote,
  Field,
  Input,
  LoadError,
  Modal,
  ModalActions,
  PageHeader,
  Panel,
  Segmented,
  Select,
  Skeleton,
  StatusBadge,
  Table,
  Td,
} from "@app/ui";

type StatusFilter = "all" | "trial" | "paying" | "suspended";

export function PlanCell({ w }: { w: Pick<WorkspaceRow, "plan" | "trial_days_left"> }) {
  if (w.plan !== "trial") return <Badge tone="ox">{planLabel(w.plan)}</Badge>;
  const t = trialText(w.trial_days_left);
  return <Badge tone={t.tone}>{t.text}</Badge>;
}

function NewWorkspace({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const create = useAction(actions.create, { success: (v) => `${String(v.company_name)} created` });
  const empty = {
    company_name: "",
    sector: "retail",
    scale: "small",
    plan: "trial",
    trial_days: 14,
    owner_full_name: "",
    owner_username: "",
    owner_password: "",
    demo_data: true,
    deployment_mode: "cloud_saas",
  };
  const [form, setForm] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof typeof empty>(k: K, v: (typeof empty)[K]) => setForm((f) => ({ ...f, [k]: v }));
  const close = () => {
    setForm(empty);
    setError(null);
    onClose();
  };

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutateAsync(form).then(
      (r) => {
        close();
        navigate(`/workspaces/${r.id}`);
      },
      (err) => setError(errorText(err)),
    );
  }

  return (
    <Modal open={open} onClose={close} wide title="New workspace" description="For customers you onboard yourself. Self-serve signups create their own.">
      <form onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Company name">
              <Input required minLength={2} value={form.company_name} onChange={(e) => set("company_name", e.target.value)} className="bidi" />
            </Field>
          </div>
          <Field label="Business type">
            <Select value={form.sector} onChange={(e) => set("sector", e.target.value)}>
              {SECTOR_OPTIONS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Size">
            <Select value={form.scale} onChange={(e) => set("scale", e.target.value)}>
              <option value="small">One branch</option>
              <option value="medium">2–3 branches</option>
              <option value="large">4 or more branches</option>
            </Select>
          </Field>
          <Field label="How it runs" hint={form.deployment_mode === "cloud_saas" ? undefined : "Registered here with a licence; the owner downloads the installer from their panel."}>
            <Select value={form.deployment_mode} onChange={(e) => set("deployment_mode", e.target.value)}>
              {Object.entries(MODES).map(([v, m]) => (
                <option key={v} value={v}>
                  {m.label}
                </option>
              ))}
            </Select>
          </Field>
          <div />
          <Field label="Plan">
            <Select value={form.plan} onChange={(e) => set("plan", e.target.value)}>
              {Object.entries(PLANS).map(([v, p]) => (
                <option key={v} value={v}>
                  {p.label}
                  {p.price ? ` — EGP ${p.price}/month` : ""}
                </option>
              ))}
            </Select>
          </Field>
          {form.plan === "trial" ? (
            <Field label="Trial length (days)">
              <Input type="number" min={1} max={365} value={form.trial_days} onChange={(e) => set("trial_days", Number(e.target.value))} />
            </Field>
          ) : (
            <div />
          )}
          <div className="sm:col-span-2 mt-1 border-t border-line-soft pt-4 text-[13px] font-bold text-ink">Owner account</div>
          <Field label="Full name">
            <Input required minLength={2} value={form.owner_full_name} onChange={(e) => set("owner_full_name", e.target.value)} className="bidi" />
          </Field>
          <Field label="Username">
            <Input required minLength={3} pattern="[\w.\-]+" value={form.owner_username} onChange={(e) => set("owner_username", e.target.value)} />
          </Field>
          <Field label="Temporary password" hint="At least 8 characters. Share it with the owner privately.">
            <Input required minLength={8} type="text" autoComplete="off" value={form.owner_password} onChange={(e) => set("owner_password", e.target.value)} />
          </Field>
          <label className="flex items-start gap-2 self-end pb-1 text-sm text-ink-2">
            <input type="checkbox" className="mt-0.5 accent-ox" checked={form.demo_data} onChange={(e) => set("demo_data", e.target.checked)} />
            Fill with sample data for this business type
          </label>
        </div>
        {error && <ErrorNote>{error}</ErrorNote>}
        <ModalActions>
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" busy={create.isPending}>
            Create workspace
          </Button>
        </ModalActions>
      </form>
    </Modal>
  );
}

export default function Workspaces() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [q, setQ] = useState(search);
  const status = (params.get("status") as StatusFilter) || "all";
  const sector = params.get("sector") || "";
  const creating = params.get("new") === "1";

  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 250);
    return () => clearTimeout(t);
  }, [search]);

  const all = useWorkspaces({});
  const list = useWorkspaces({ q: q || undefined, status: status === "all" ? undefined : status, sector: sector || undefined });

  const counts = useMemo(() => {
    const items = all.data?.items ?? [];
    return {
      all: items.length,
      trial: items.filter((w) => w.plan === "trial" && w.status !== "suspended").length,
      paying: items.filter((w) => w.plan !== "trial" && w.status === "active").length,
      suspended: items.filter((w) => w.status === "suspended").length,
    };
  }, [all.data]);

  const update = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };

  return (
    <>
      <PageHeader
        title="Workspaces"
        description="Every company using Mizan. Open one to change its plan, modules or status, or to see it as its owner does."
        actions={
          <Button variant="primary" onClick={() => update("new", "1")}>
            New workspace
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented
          value={status}
          onChange={(v) => update("status", v === "all" ? "" : v)}
          items={[
            { value: "all", label: "All", count: counts.all },
            { value: "trial", label: "On trial", count: counts.trial },
            { value: "paying", label: "Paying", count: counts.paying },
            { value: "suspended", label: "Suspended", count: counts.suspended },
          ]}
        />
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-mute" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name or URL name" className="pl-9" aria-label="Search workspaces" />
        </div>
        <Select value={sector} onChange={(e) => update("sector", e.target.value)} className="w-auto min-w-44" aria-label="Business type">
          <option value="">All business types</option>
          {SECTOR_OPTIONS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>

      {list.isError ? (
        <LoadError error={list.error} retry={() => list.refetch()} />
      ) : (
        <Panel flush>
          {list.isPending ? (
            <div className="grid gap-3 p-4">
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            </div>
          ) : list.data.items.length ? (
            <Table head={["Workspace", "Business type", "Plan", "People", "Sales", "Activity", "Created"]}>
              {list.data.items.map((w) => {
                const p = pulse(w.last_sale_at);
                return (
                  <tr
                    key={w.id}
                    onClick={() => navigate(`/workspaces/${w.id}`)}
                    onKeyDown={(e) => e.key === "Enter" && navigate(`/workspaces/${w.id}`)}
                    tabIndex={0}
                    className="cursor-pointer hover:bg-paper/70 focus-visible:bg-paper"
                  >
                    <Td>
                      <div className="bidi font-semibold text-ink">{w.name}</div>
                      <div className="code text-xs text-mute">{w.slug ?? "—"}</div>
                    </Td>
                    <Td className="text-ink-2">
                      {sectorLabel(w.sector)}
                      {w.deployment_mode !== "cloud_saas" && <Badge tone="info" className="ml-1.5">{MODES[w.deployment_mode]?.short}</Badge>}
                    </Td>
                    <Td>
                      <div className="flex flex-wrap gap-1.5">
                        <PlanCell w={w} />
                        {w.status === "suspended" && <StatusBadge status="suspended" />}
                      </div>
                    </Td>
                    <Td className="data">{num(w.users_count)}</Td>
                    <Td>
                      <div className="data">{money(w.sales_volume_egp)}</div>
                      <div className="text-xs text-mute">{num(w.sales_count)} sales</div>
                    </Td>
                    <Td>
                      <Dot tone={p.tone} label={p.label} />
                    </Td>
                    <Td className="text-ink-2" title={date(w.created_at)}>
                      {ago(w.created_at)}
                    </Td>
                  </tr>
                );
              })}
            </Table>
          ) : (
            <Empty title={q || sector || status !== "all" ? "No workspaces match these filters." : "No workspaces yet."}>
              {q || sector || status !== "all" ? "Clear the search or pick another filter." : "Create one, or wait for the first signup from the website."}
            </Empty>
          )}
        </Panel>
      )}

      <NewWorkspace open={creating} onClose={() => update("new", "")} />
    </>
  );
}
