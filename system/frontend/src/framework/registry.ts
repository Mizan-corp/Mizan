import type { ComponentType } from "react";
import type { ModuleDefinition } from "./types";

// Every module's definition (activities/<activity>/modules/<module>/index.ts, platform/*, integrations/*).
const found = import.meta.glob<{ default: ModuleDefinition }>(
  ["../activities/*/modules/*/index.ts", "../platform/*/index.ts", "../integrations/*/index.ts"],
  { eager: true },
);

/** Built modules only; planned ones are laid out but not offered. */
export const moduleDefinitions: ModuleDefinition[] = Object.values(found)
  .map((m) => m.default)
  .filter((m) => m.status === "active");

export function moduleDefinition(id: string): ModuleDefinition | undefined {
  return moduleDefinitions.find((m) => m.id === id);
}

/** The component for a widget id the backend's dashboard lists ("<module>.<name>"). */
export function widgetComponent(id: string): ComponentType | undefined {
  const module = id.split(".")[0];
  return moduleDefinition(module)?.widgets[id];
}
