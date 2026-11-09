import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { actions, type Person, useAction, useTeam } from "@app/lib/data";
import { ago, date, errorText } from "@app/lib/format";
import { Badge, Button, Confirm, Empty, ErrorNote, Input, LoadError, Modal, PageHeader, PageSkeleton, Panel, Table, Td } from "@app/ui";

function AddTeammate({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Person[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const grant = useAction(actions.grant, { success: () => "Access given" });

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults(null);
      return;
    }
    const t = setTimeout(() => {
      api
        .get<{ items: Person[] }>("/admoon/team/candidates", { q: q.trim() })
        .then((r) => setResults(r.items))
        .catch((e) => setError(errorText(e)));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const close = () => {
    setQ("");
    setResults(null);
    setError(null);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={close}
      wide
      title="Add a teammate"
      description="Find their Mizan account. They sign in here with the same username and password."
    >
      <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by username or name" />
      {error && <ErrorNote>{error}</ErrorNote>}
      <div className="mt-3 max-h-80 overflow-y-auto">
        {results === null ? (
          <p className="px-1 py-3 text-[13px] text-mute">Type at least 2 characters.</p>
        ) : results.length ? (
          <ul className="divide-y divide-line-soft">
            {results.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <div className="bidi truncate text-sm font-semibold">{p.full_name}</div>
                  <div className="truncate text-xs text-mute">
                    <span className="code">@{p.username}</span>
                    {p.workspace && <span className="bidi"> · {p.workspace}</span>}
                  </div>
                </div>
                {p.is_staff ? (
                  <Badge tone="ok">Already on the team</Badge>
                ) : (
                  <Button
                    size="sm"
                    busy={grant.isPending && grant.variables === p.id}
                    onClick={() =>
                      grant.mutateAsync(p.id).then(close, (e) => setError(errorText(e)))
                    }
                  >
                    Give access
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-1 py-3 text-[13px] text-mute">No accounts match “{q}”.</p>
        )}
      </div>
    </Modal>
  );
}

export default function Team() {
  const q = useTeam();
  const revoke = useAction(actions.revoke, { success: () => "Access removed" });
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Person | null>(null);

  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;

  return (
    <>
      <PageHeader
        title="Team"
        description="People who can sign in to this admin panel and act on every workspace."
        actions={
          <Button variant="primary" onClick={() => setAdding(true)}>
            Add teammate
          </Button>
        }
      />
      <Panel flush>
        {q.data.items.length ? (
          <Table head={["Name", "Username", "Home workspace", "Last action here", "Added", ""]}>
            {q.data.items.map((p) => (
              <tr key={p.id}>
                <Td>
                  <span className="bidi font-semibold">{p.full_name}</span>
                  {p.id === q.data.me && <Badge className="ml-2">You</Badge>}
                </Td>
                <Td className="code text-[13px] text-ink-2">@{p.username}</Td>
                <Td className="bidi text-ink-2">{p.workspace ?? "—"}</Td>
                <Td className="text-ink-2">{p.last_action_at ? ago(p.last_action_at) : "No actions yet"}</Td>
                <Td className="text-ink-2">{date(p.created_at)}</Td>
                <Td className="text-right">
                  {p.id !== q.data.me && (
                    <Button size="sm" variant="ghost" onClick={() => setRemoving(p)}>
                      Remove access
                    </Button>
                  )}
                </Td>
              </tr>
            ))}
          </Table>
        ) : (
          <Empty title="No teammates." />
        )}
      </Panel>

      <AddTeammate open={adding} onClose={() => setAdding(false)} />
      <Confirm
        open={!!removing}
        onClose={() => setRemoving(null)}
        title={`Remove ${removing?.full_name}'s access?`}
        body="They can no longer sign in to the admin panel. Their account in their own workspace stays as it is."
        confirmLabel="Remove access"
        danger
        onConfirm={() => revoke.mutateAsync(removing!.id)}
      />
    </>
  );
}
