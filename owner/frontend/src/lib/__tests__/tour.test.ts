import { describe, expect, it, vi } from "vitest";

vi.mock("@app/lib/data", () => ({ actions: {} }));

describe("tour card placement", () => {
  it("centres the card when the step's target is missing", async () => {
    const { cardPlacement } = await import("@app/Tour");
    expect(cardPlacement(null, 1200, 800, 200)).toEqual({ top: 300, left: 420, width: 360 });
  });

  it("goes under the target, or above it near the bottom, and stays on screen", async () => {
    const { cardPlacement } = await import("@app/Tour");
    const under = cardPlacement({ top: 100, bottom: 140, left: 50, width: 100 }, 1200, 800, 200);
    expect(under.top).toBe(140 + 8 + 12);
    expect(under.left).toBe(12); // would start off-screen to the left
    const above = cardPlacement({ top: 700, bottom: 740, left: 500, width: 100 }, 1200, 800, 200);
    expect(above.top).toBe(700 - 8 - 12 - 200);
    expect(cardPlacement(null, 320, 600, 200).width).toBe(296); // narrow phones
  });
});
