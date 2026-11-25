/** Connected-data re-approval gating for the publish dialog.
 *
 * Disabling public access keeps the approved source set on the activation row
 * for audit, so `connected_data` stays true after any prior approval. Without
 * this predicate the "approve the wider set" action was unreachable whenever a
 * page already had an approval, making widened pages impossible to re-approve
 * from the UI even though the backend requires exactly that before publishing.
 */
export interface ConnectedAccessView {
  connected_data: boolean;
  sources?: string[];
}

export function needsWiderApproval(publishedSources: string[], access: ConnectedAccessView | null): boolean {
  if (!access || access.connected_data !== true) return false;
  const approved = new Set(access.sources ?? []);
  return publishedSources.some((s) => !approved.has(s));
}
