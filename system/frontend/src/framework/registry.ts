import type { ModuleDefinition } from "./types";

// Every module's definition (modules/<activity>/<module>/index.ts, platform/*, integrations/*).
// Not used by the app shell yet: App.tsx and lib/nav.ts still list screens by hand (ADR-006 phase 5).
const found = import.meta.glob<{ default: ModuleDefinition }>(
  ["../modules/*/*/index.ts", "../platform/*/index.ts", "../integrations/*/index.ts"],
  { eager: true },
);

/** Built modules only; planned ones are laid out but not offered. */
export const moduleDefinitions: ModuleDefinition[] = Object.values(found)
  .map((m) => m.default)
  .filter((m) => m.status === "active");

export function moduleDefinition(id: string): ModuleDefinition | undefined {
  return moduleDefinitions.find((m) => m.id === id);
}
