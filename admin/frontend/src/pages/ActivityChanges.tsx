import { useState } from "react";
import { actions, useAction, useActivityChange } from "@app/lib/data";
import { ago, num, plural, sectorLabel } from "@app/lib/format";
import { Button, ErrorNote, Field, Modal, ModalActions, Skeleton, Textarea } from "@app/ui";

function ModuleList({ title, items, tone }: { title: string; items: { name_en: string; name: string }[]; tone: string }) {
  if (!items.length) return null;
  return (
    <div className={`rounded-lg px-3.5 py-2.5 ${tone}`}>
      <p className="text-[13px] font-semibold text-ink">{title}</p>
      <p className="mt-0.5 text-[13px] text-ink-2">{items.map((m) => m.name_en || m.name).join(", ")}</p>
    </div>
  );
}

/** Review an owner's request to change a workspace's activity (#107): approving applies it at once. */
export function ActivityChangeReview({ id, open, onClose }: { id: string; open: boolean; onClose: () => void }) {
  const q = useActivityChange(id, open);
  const [note, setNote] = useState("");
  const approve = useAction(actions.approveActivityChange, { success: () => "Activity changed", then: onClose });
  const reject = useAction(actions.rejectActivityChange, { success: () => "Request rejected", then: onClose });
  const c = q.data;
  const p = c?.preview;
  const withData = (p?.data ?? []).filter((d) => !d.kept_always);

  return (
    <Modal open={open} onClose={onClose} wide title="Change of activity"
           description={c ? <>{c.tenant_name} asks to go from <b>{sectorLabel(c.from.id, c.from.name)}</b> to <b>{sectorLabel(c.to.id, c.to.name)}</b> · {ago(c.created_at)}</> : undefined}>
      {q.isPending && <Skeleton className="h-32" />}
      {q.isError && <ErrorNote>Couldn't load the request.</ErrorNote>}
      {c && (
        <div className="grid gap-3">
          {c.note && <p className="rounded-lg bg-paper px-3.5 py-2.5 text-[13px] text-ink-2">“{c.note}”</p>}
          {c.preview_error && <ErrorNote>{c.preview_error}</ErrorNote>}
          {p && (
            <>
              <ModuleList title="Leaves (not run by the new activity)" items={p.leaving} tone="bg-bad/8" />
              <ModuleList title="Joins" items={p.joining} tone="bg-ok/10" />
              <ModuleList title="Works the new activity's way" items={p.variants_changed} tone="bg-paper" />
              {p.package && (
                <div className="rounded-lg border border-line px-3.5 py-2.5 text-[13px]">
                  <p className="font-semibold text-ink">
                    A developer's activity: <span className="code">{c.to.id}</span> v{p.package.version} by <span className="code">{p.package.developer}</span>
                  </p>
                  {p.own_joining.map((m) => (
                    <p key={m.id} className="mt-1 text-ink-2">
                      Installs <b>{m.name_en || m.name}</b> ({plural(m.entities.length, "record type")}) · may access{" "}
                      {m.scopes.length ? m.scopes.map((x) => x.text_en).join(", ") : "nothing else"}
                      {m.sends_to && <> · sends events to <span className="code">{m.sends_to}</span></>}
                    </p>
                  ))}
                  {p.package.themes.length > 0 && <p className="mt-1 text-ink-2">Themes: {p.package.themes.map((t) => t.name).join(", ")}</p>}
                </div>
              )}
              {p.own_leaving.length > 0 && (
                <ModuleList title="The old activity's own modules leave (records kept hidden)" items={p.own_leaving} tone="bg-bad/8" />
              )}
              {!p.leaving.length && !p.joining.length && !p.variants_changed.length && !p.own_joining.length && (
                <p className="text-[13px] text-mute">No module changes; menus and terms follow the new activity.</p>
              )}
              <p className="text-[13px] text-ink-2">
                Data of leaving modules:{" "}
                {withData.length
                  ? <>{withData.map((d) => `${d.name_en || d.name} (${num(d.rows)} records)`).join(", ")} — the owner chose to{" "}
                      <b>{c.data_mode === "delete" ? "delete it (after an export)" : `keep it hidden ${p.keep_days} days`}</b>.</>
                  : "none."}
              </p>
              {p.theme && <p className="text-[13px] text-ink-2">The workspace's theme belongs to the old activity; it switches to <span className="code">{p.theme.to}</span>.</p>}
            </>
          )}
          {c.status === "requested" ? (
            <Field label="Note" hint="Required to reject: the owner sees it.">
              <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} />
            </Field>
          ) : (
            <p className="text-[13px] text-mute">Already {c.status}.</p>
          )}
          {(approve.isError || reject.isError) && <ErrorNote>{String((approve.error ?? reject.error) as Error)}</ErrorNote>}
        </div>
      )}
      <ModalActions>
        <Button variant="ghost" onClick={onClose}>Close</Button>
        {c?.status === "requested" && (
          <>
            <Button busy={reject.isPending} disabled={!note.trim()} onClick={() => reject.mutate({ id, note: note.trim() })}>Reject</Button>
            <Button variant="primary" busy={approve.isPending} disabled={!p} onClick={() => approve.mutate({ id, note: note.trim() || undefined })}>
              Approve and apply
            </Button>
          </>
        )}
      </ModalActions>
    </Modal>
  );
}
