// Single-editor operation guard. Not an API transaction or cross-session lock.
export function createOperationGate() {
  let active = false;
  return {
    start() { if (active) return false; active = true; return true; },
    finish() { active = false; },
    get active() { return active; },
  };
}
export function snapshotKey(value: unknown): string { return JSON.stringify(value); }
export function saveResultNotice(saved: string, current: string): string {
  return saved === current
    ? 'Draft and site settings saved to the local test backend (not the public site).'
    : 'Earlier snapshot saved to the local test backend. Newer local changes are NOT saved. Save again before publishing.';
}
