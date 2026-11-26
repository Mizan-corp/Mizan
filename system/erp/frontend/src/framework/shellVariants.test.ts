// Step 5 guard: classic stays exactly as it was; every layout mode the UI store can save has a variant.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CLASSIC_SHELL, SHELL_VARIANTS } from "./shellVariants";

const ui = readFileSync(join(__dirname, "../../../../core/frontend/src/stores/ui.ts"), "utf8");
const modes = (ui.match(/export type LayoutMode = ([^;]+);/)![1].match(/"(\w+)"/g) ?? []).map((m) => m.replace(/"/g, ""));

describe("shell variants", () => {
  it("covers every LayoutMode, no more", () => {
    expect(Object.keys(SHELL_VARIANTS).sort()).toEqual([...modes].sort());
  });
  it("has exactly one classic variant and it is the default", () => {
    const classic = Object.values(SHELL_VARIANTS).filter((v) => v.classic);
    expect(classic.map((v) => v.id)).toEqual([CLASSIC_SHELL]);
  });
  it("classic keeps the pre-refactor sidebar markup classes", () => {
    expect(SHELL_VARIANTS.sidebar.nav).toEqual({ kind: "aside", className: "no-print sticky top-0 hidden h-svh w-64 shrink-0 lg:block" });
    expect(SHELL_VARIANTS.rail.nav).toEqual({ kind: "aside", className: "no-print sticky top-0 hidden h-svh w-16 shrink-0 lg:block" });
  });
  it("AppShell has no hard-coded layout branches left", () => {
    const shell = readFileSync(join(__dirname, "../components/AppShell.tsx"), "utf8");
    expect(shell).not.toMatch(/layoutMode === "sidebar" &&|layoutMode === "topnav" &&/);
  });
  it("a personal choice wins over the activity's shell, which wins over classic", () => {
    const shell = readFileSync(join(__dirname, "../components/AppShell.tsx"), "utf8");
    expect(shell).toContain('!hasOwnChoice && activityShell');
    expect(shell).toContain('localStorage.getItem("mizan.layout")');
  });
});
