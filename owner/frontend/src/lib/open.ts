import { useState } from "react";
import { toast } from "sonner";
import { openErpWithSession } from "@/lib/handoff";
import { erpUrl } from "@/lib/urls";
import { actions, type Workspace } from "@app/lib/data";
import { errorText } from "@app/lib/format";

/** Where a workspace's staff sign in (they never use the owner panel). */
export const staffLoginUrl = (slug: string) => erpUrl(slug, "/login");

/** Open a workspace in the app, signed in as the owner. */
export function useOpenWorkspace() {
  const [opening, setOpening] = useState<string | null>(null);
  async function open(w: Pick<Workspace, "id">, path = "/") {
    setOpening(w.id);
    try {
      const r = await actions.open(w.id);
      openErpWithSession(r.slug, path, r.access_token);
    } catch (e) {
      toast.error(errorText(e));
      setOpening(null);
    }
  }
  return { open, opening };
}

