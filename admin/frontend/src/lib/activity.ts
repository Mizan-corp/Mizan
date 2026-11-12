import type { ActivityItem } from "@app/lib/data";
import { money, plural, planLabel } from "@app/lib/format";

type Part = string | { workspace: string; id: string | null };

/** An audit entry as a sentence: parts are plain text or a workspace link. */
export function describe(a: ActivityItem): Part[] {
  const d = a.details as Record<string, unknown>;
  const ws: Part = { workspace: a.tenant_name ?? "a deleted workspace", id: a.tenant_id };
  const s = (k: string) => String(d[k] ?? "");
  switch (a.action) {
    case "tenant_created":
      return ["Created ", ws, ` on ${planLabel(s("plan"))}`];
    case "tenant_updated":
      return ["Updated the name or URL of ", ws];
    case "tenant_status_change":
      return [s("new_status") === "suspended" ? "Suspended " : "Reactivated ", ws, d.reason ? ` — “${s("reason")}”` : ""];
    case "tenant_plan_updated":
      return ["Moved ", ws, ` from ${planLabel(s("old_plan"))} to ${planLabel(s("new_plan"))}`];
    case "trial_extended":
      return ["Extended the trial of ", ws, ` by ${plural(Number(d.days), "day")}`];
    case "tenant_modules_updated": {
      const added = (d.added as string[] | undefined) ?? [];
      const removed = (d.removed as string[] | undefined) ?? [];
      const change = [...added.map((m) => `+${m}`), ...removed.map((m) => `−${m}`)].join(", ");
      return ["Changed modules for ", ws, change ? ` (${change})` : ""];
    }
    case "tenant_impersonated":
      return ["Opened ", ws, ` as ${s("as_user")}`];
    case "tenant_deleted":
      return ["Deleted ", { workspace: s("name") || "a workspace", id: null }];
    case "invoice_marked_paid":
      return [`Marked invoice ${s("invoice")} paid (${money(Number(d.amount_egp))}) for `, ws];
    case "invoice_checked_with_paymob":
      return [`Checked invoice ${s("invoice")} with Paymob (${s("status")}) for `, ws];
    case "invoice_paid_online":
      return [`${planLabel(s("plan"))} paid online via Paymob (${money(Number(d.amount_egp))}, ${s("invoice")}) by `, ws];
    case "invoice_refunded_online":
      return [`Invoice ${s("invoice")} refunded in Paymob for `, ws];
    case "licence_extended":
      return [`Extended the licence of `, ws, ` by ${plural(Number(d.days), "day")}`, d.reason ? ` — “${s("reason")}”` : ""];
    case "licence_revoked":
      return ["Revoked the licence of ", ws, d.reason ? ` — “${s("reason")}”` : ""];
    case "licence_restored":
      return ["Restored the licence of ", ws];
    case "licence_key_issued":
      return ["Issued an offline licence key for ", ws];
    case "upgrade_request_dismissed":
      return [`Dismissed an upgrade request to ${planLabel(s("plan"))} from `, ws];
    case "owner_password_reset":
      return [`Reset the password of owner @${s("owner")}`];
    case "owner_disabled":
      return [`Disabled owner @${s("owner")}`];
    case "owner_enabled":
      return [`Enabled owner @${s("owner")}`];
    case "workspace_owner_changed":
      return ["Gave ", ws, ` to owner @${s("owner")}`, d.previous_owner ? ` (was @${s("previous_owner")})` : ""];
    case "owners_merged":
      return [`Merged owner @${s("merged")} into @${s("owner")} (${plural(Number(d.workspaces), "workspace")})`];
    case "owner_deleted":
      return [`Deleted owner account @${s("owner")}`];
    case "platform_access_granted":
      return [`Gave ${s("user")} access to the admin panel`];
    case "platform_access_revoked":
      return [`Removed ${s("user")}'s access to the admin panel`];
    default: {
      const words = a.action.replace(/_/g, " ");
      return a.tenant_id || a.tenant_name ? [words[0].toUpperCase() + words.slice(1) + " · ", ws] : [words];
    }
  }
}

export const ACTION_FILTERS: { value: string; label: string }[] = [
  { value: "tenant_created", label: "Workspace created" },
  { value: "tenant_impersonated", label: "Opened as owner" },
  { value: "tenant_plan_updated", label: "Plan changed" },
  { value: "trial_extended", label: "Trial extended" },
  { value: "tenant_status_change", label: "Suspended or reactivated" },
  { value: "tenant_modules_updated", label: "Modules changed" },
  { value: "invoice_marked_paid", label: "Invoice marked paid" },
  { value: "invoice_paid_online", label: "Paid online" },
  { value: "licence_extended", label: "Licence extended" },
  { value: "licence_revoked", label: "Licence revoked" },
  { value: "tenant_deleted", label: "Workspace deleted" },
  { value: "platform_access_granted", label: "Access granted" },
  { value: "platform_access_revoked", label: "Access removed" },
];
