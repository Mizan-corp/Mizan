export type PersistenceState = {
  current: string;
  baseline: string;
  browserSaved: string | null;
  backendSaved: string | null;
  backendConnected: boolean;
  busy: boolean;
};
export function shouldWarnBeforeLeave(state: PersistenceState): boolean {
  if (state.busy) return true;
  // Reload prefers the backend when connected. A browser-only save does not make
  // unsaved backend edits safe to leave: the server copy may replace them on load.
  if (state.backendConnected) return state.backendSaved === null ? state.current !== state.baseline : state.current !== state.backendSaved;
  return state.current !== state.baseline && state.current !== state.browserSaved;
}
export function browserSaveLabel(current: string, saved: string | null): string {
  return current === saved ? 'Browser copy saved' : 'Browser copy not saved';
}
export function backendSaveLabel(current: string, saved: string | null, connected: boolean): string {
  if (!connected) return 'Backend saving unavailable';
  return current === saved ? 'Backend snapshot saved' : 'Backend changes not saved';
}
