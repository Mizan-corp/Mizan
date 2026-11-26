// Migration step 5: the shell (navigation placement) is chosen from a registry instead of
// hard-coded branches in AppShell. "sidebar" is the classic look and must stay identical:
// its aside classes are exactly the ones AppShell used before this step. New variants are
// added here (after a mockup the owner approved), never by editing AppShell's markup.
import type { LayoutMode } from "@/stores/ui";

export interface ShellVariant {
  id: LayoutMode;
  /** The classic look. Exactly one variant is classic and it is the default. */
  classic?: true;
  /** Where the navigation sits: a side column (with its Tailwind classes) or a bar under the topbar. */
  nav: { kind: "aside"; className: string } | { kind: "topbar" };
}

export const SHELL_VARIANTS: Record<LayoutMode, ShellVariant> = {
  sidebar: { id: "sidebar", classic: true, nav: { kind: "aside", className: "no-print sticky top-0 hidden h-svh w-64 shrink-0 lg:block" } },
  rail: { id: "rail", nav: { kind: "aside", className: "no-print sticky top-0 hidden h-svh w-16 shrink-0 lg:block" } },
  topnav: { id: "topnav", nav: { kind: "topbar" } },
};

export const CLASSIC_SHELL: LayoutMode = "sidebar";
