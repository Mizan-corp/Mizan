import type { ComponentType } from "react";

/** A module's kind (ADR-006): business modules, the platform's own, and connectors. */
export type ModuleKind = "business" | "platform" | "integration";

/** `planned`: described (SRS) and laid out, not built; not mounted or offered to workspaces. */
export type ModuleStatus = "active" | "planned";

/** A navigation entry a module offers; the active role decides which are shown (phase 5). */
export interface ModuleNavEntry {
  to: string;
  label: string;
  perm?: string;
  icon?: ComponentType<{ className?: string }>;
}

/**
 * What a module provides to the app (its `index.ts`). Screen and widget ids resolve through the
 * workspace's variant, so the same role can see a different screen per activity (ADR-006 D4).
 */
export interface ModuleDefinition {
  id: string;
  activity: string;
  kind: ModuleKind;
  status: ModuleStatus;
  screens: Record<string, ComponentType>;
  widgets: Record<string, ComponentType>;
  nav: ModuleNavEntry[];
}
