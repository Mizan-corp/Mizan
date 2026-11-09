import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ACTION_FILTERS } from "@app/lib/activity";
import { type ActivityItem, useActivity } from "@app/lib/data";
import { ActivityList, Button, LoadError, PageHeader, PageSkeleton, Panel, Select } from "@app/ui";

export default function Activity() {
  const [action, setAction] = useState("");
  const q = useActivity({ action: action || undefined });
  const [more, setMore] = useState<ActivityItem[]>([]);
  const [cursor, setCursor] = useState<string | null | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const qc = useQueryClient();

  if (q.isPending) return <PageSkeleton />;
  if (q.isError) return <LoadError error={q.error} retry={() => q.refetch()} />;
  const next = cursor === undefined ? q.data.next_before : cursor;

  return (
    <>
      <PageHeader
        title="Activity"
        description="Every change made from this panel, who made it and when. Entries can't be edited or removed."
        actions={
          <Select
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setMore([]);
              setCursor(undefined);
              qc.removeQueries({ queryKey: ["activity"] });
            }}
            className="w-56"
            aria-label="Filter by action"
          >
            <option value="">All actions</option>
            {ACTION_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
        }
      />
      <Panel flush>
        <ActivityList items={[...q.data.items, ...more]} empty={action ? "Nothing of this kind yet." : "No admin actions yet."} />
        {next && (
          <div className="border-t border-line-soft p-3 text-center">
            <Button
              size="sm"
              busy={loading}
              onClick={async () => {
                setLoading(true);
                try {
                  const r = await api.get<{ items: ActivityItem[]; next_before: string | null }>("/admoon/activity", {
                    limit: 100,
                    action: action || undefined,
                    before: next,
                  });
                  setMore((m) => [...m, ...r.items]);
                  setCursor(r.next_before);
                } finally {
                  setLoading(false);
                }
              }}
            >
              Show older
            </Button>
          </div>
        )}
      </Panel>
    </>
  );
}
