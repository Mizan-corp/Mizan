import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** A field the activity's variants or the workspace add to a record (ADR-006 phase 4). */
export interface FieldDef {
  key: string;
  label?: string;
  label_en?: string;
  type: "text" | "number" | "date" | "boolean" | "select";
  required?: boolean;
  options?: string[];
  readonly?: boolean;
  searchable?: boolean;
}

/** What the app adapts to: the workspace's activity, its variants, words and fields. */
export interface WorkspaceProfile {
  activity: string | null;
  activity_name: string | null;
  variants: Record<string, string>;
  terms: Record<string, string>;
  fields: Record<string, FieldDef[]>;
}

export function useWorkspaceProfile() {
  return useQuery({
    queryKey: ["workspace-profile"],
    queryFn: () => api.get<WorkspaceProfile>("/settings/workspace-profile"),
    staleTime: 5 * 60_000,
  });
}

/** The variant of a module this workspace runs ("standard" when the activity has none). */
export function variantOf(profile: WorkspaceProfile | undefined, module: string): string {
  return profile?.variants?.[module] ?? "standard";
}
