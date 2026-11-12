/**
 * Owner accounts (#73): who owns which workspaces, and support actions on them. The v47 backfill
 * gave each pre-existing workspace its own owner account, so one person may have two: merge them.
 */
import { useState } from "react";
import { Search } from "lucide-react";
import { actions, useAction, useOwner, useOwners, type OwnerRow } from "@app/lib/data";
import { ago, errorText, money, planLabel } from "@app/lib/format";
import {
  Badge,
  Button,
  Confirm,
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
  Skeleton,
  Table,
  Td,
  WorkspaceLink,
} from "@app/ui";

function OwnerDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const q = useOwner(id);
  const [password, setPassword] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<"reset" | "disable" | "delete" | null>(null);
  const [mergeInto, setMergeInto] = useState("");
  const [mergeError, setMergeError] = useState<string | null>(null);
  const others = useOwners({ q: mergeInto.trim() || undefined });
  const reset = useAction(actions.resetOwnerPassword, { success: () => "Password reset" });
  const active = useAction(actions.setOwnerActive, { success: (v) => (v.active ? "Owner enabled" : "Owner disabled") });
  const merge = useAction(actions.mergeOwner, { success: () => "Owners merged", then: () => onClose() });
  const remove = useAction(actions.deleteOwner, { success: () => "Owner deleted", then: () => onClose() });

  const o = q.data;
  const target = (others.data?.items ?? []).find((x) => x.login === mergeInto.trim().toLowerCase() && x.id !== id);

  return (
    <Modal open onClose={onClose} title={o ? o.full_name : "Owner"} description={o ? <span className="code">@{o.login}</span> : undefined} wide>
      {q.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : q.isError ? (
        <LoadError error={q.error} retry={() => q.refetch()} />
      ) : (
        o && (
          <div className="grid gap-5">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <dt className="text-mute">Email</dt><dd className="code">{o.email ?? "—"}</dd>
              <dt className="text-mute">Phone</dt><dd className="code">{o.phone ?? "—"}</dd>
              <dt className="text-mute">Last sign-in</dt><dd>{o.last_login_at ? ago(o.last_login_at) : "never"}</dd>
              <dt className="text-mute">Paid in total</dt><dd>{money(o.paid_egp)}</dd>
              <dt className="text-mute">Status</dt><dd>{o.is_active ? <Badge tone="ok">Active</Badge> : <Badge tone="bad">Disabled</Badge>}</dd>
            </dl>

            <div>
              <h3 className="mb-2 text-sm font-semibold text-ink">Workspaces ({o.workspaces.length})</h3>
              {o.workspaces.length ? (
                <ul className="divide-y divide-line-soft rounded-lg border border-line">
                  {o.workspaces.map((w) => (
                    <li key={w.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                      <WorkspaceLink id={w.id} name={w.name} />
                      <span className="text-mute">{planLabel(w.plan)}{w.status === "suspended" && " · suspended"}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-mute">None. This account can be deleted.</p>
              )}
            </div>

            {password && (
              <div className="rounded-lg border border-line bg-paper px-3 py-2.5 text-sm">
                Temporary password, shown once: <span className="code select-all font-semibold text-ink">{password}</span>
                <div className="mt-1 text-xs text-mute">Give it to the owner; they change it in their panel under حسابي. Their sessions have ended.</div>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => setConfirm("reset")}>Reset password</Button>
              {o.is_active ? (
                <Button size="sm" onClick={() => setConfirm("disable")}>Disable</Button>
              ) : (
                <Button size="sm" busy={active.isPending} onClick={() => active.mutate({ id, active: true })}>Enable</Button>
              )}
              {!o.workspaces.length && <Button size="sm" variant="danger" onClick={() => setConfirm("delete")}>Delete account</Button>}
            </div>

            <div className="border-t border-line-soft pt-4">
              <h3 className="text-sm font-semibold text-ink">Merge into another owner</h3>
              <p className="mt-0.5 text-xs text-mute">Moves every workspace of this account to the other one, then deletes this account.</p>
              <div className="mt-2 flex flex-wrap items-end gap-2">
                <Field label="The other owner's username">
                  <Input value={mergeInto} onChange={(e) => setMergeInto(e.target.value)} className="code w-64" placeholder="login" />
                </Field>
                <Button size="sm" disabled={!target} busy={merge.isPending}
                        onClick={() => { setMergeError(null); merge.mutateAsync({ id, into: target!.id }).catch((e) => setMergeError(errorText(e))); }}>
                  Merge into {target ? target.full_name : "…"}
                </Button>
              </div>
              {mergeInto.trim() && !target && !others.isPending && <p className="mt-1 text-xs text-mute">No other owner with that username.</p>}
              {mergeError && <ErrorNote>{mergeError}</ErrorNote>}
            </div>
          </div>
        )
      )}
      <ModalActions>
        <Button onClick={onClose}>Close</Button>
      </ModalActions>

      <Confirm open={confirm === "reset"} onClose={() => setConfirm(null)} title="Reset this owner's password?"
               body="They get a new temporary password and are signed out everywhere." confirmLabel="Reset password"
               onConfirm={() => reset.mutateAsync(id).then((r) => setPassword(r.password))} />
      <Confirm open={confirm === "disable"} onClose={() => setConfirm(null)} title="Disable this owner account?" danger
               body="They can't sign in to the owner panel and are signed out. Their workspaces keep running." confirmLabel="Disable"
               onConfirm={() => active.mutateAsync({ id, active: false })} />
      <Confirm open={confirm === "delete"} onClose={() => setConfirm(null)} title="Delete this owner account?" danger
               body="It has no workspaces left. This can't be undone." confirmLabel="Delete"
               onConfirm={() => remove.mutateAsync(id)} />
    </Modal>
  );
}

export default function Owners() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<"all" | "empty">("all");
  const [open, setOpen] = useState<string | null>(null);
  const list = useOwners({ q: q.trim() || undefined, without_workspaces: filter === "empty" });

  return (
    <>
      <PageHeader title="Owners" description="Owner accounts: they sign in to the owner panel, own workspaces and pay for them." />
      <Panel
        flush
        title={
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-mute" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, username, email, phone" className="w-72 pl-8" aria-label="Search owners" />
            </div>
            <Segmented value={filter} onChange={setFilter} items={[{ value: "all", label: "All" }, { value: "empty", label: "No workspaces" }]} />
          </div>
        }
      >
        {list.isPending ? (
          <div className="grid gap-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        ) : list.isError ? (
          <LoadError error={list.error} retry={() => list.refetch()} />
        ) : !list.data.items.length ? (
          <Empty title={q || filter === "empty" ? "No owners match." : "No owners yet."} />
        ) : (
          <Table head={["Owner", "Contact", "Workspaces", "Paid", "Last sign-in", ""]}>
            {list.data.items.map((o: OwnerRow) => (
              <tr key={o.id} className="cursor-pointer hover:bg-paper/60" onClick={() => setOpen(o.id)}>
                <Td>
                  <div className="font-semibold text-ink"><span className="bidi">{o.full_name}</span></div>
                  <div className="code text-xs text-mute">@{o.login}</div>
                </Td>
                <Td className="text-xs text-ink-2">
                  <div className="code">{o.email ?? "—"}</div>
                  <div className="code">{o.phone ?? ""}</div>
                </Td>
                <Td className="data">{o.workspace_count}</Td>
                <Td className="data">{money(o.paid_egp)}</Td>
                <Td className="text-ink-2">{o.last_login_at ? ago(o.last_login_at) : "never"}</Td>
                <Td>{!o.is_active && <Badge tone="bad">Disabled</Badge>}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
      {open && <OwnerDialog id={open} onClose={() => setOpen(null)} />}
    </>
  );
}
