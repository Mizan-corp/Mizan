import { afterEach, describe, expect, it, vi } from "vitest";
import { days, money, paidState, trialState } from "@app/lib/format";

describe("Arabic day counts", () => {
  it.each([
    [1, "يوم واحد"],
    [2, "يومان"],
    [3, "3 أيام"],
    [10, "10 أيام"],
    [11, "11 يومًا"],
    [30, "30 يومًا"],
    [-3, "3 أيام"],
  ])("%i → %s", (n, text) => expect(days(n)).toBe(text));
});

describe("trial states", () => {
  it("unknown, ended, today, few days left, plenty left", () => {
    expect(trialState(null)).toEqual({ text: "فترة تجريبية", tone: "info" });
    expect(trialState(-2)).toEqual({ text: "انتهت التجربة منذ يومان", tone: "bad" });
    expect(trialState(0)).toEqual({ text: "التجربة تنتهي اليوم", tone: "warn" });
    expect(trialState(3)).toEqual({ text: "متبقٍ 3 أيام من التجربة", tone: "warn" });
    expect(trialState(12).tone).toBe("info");
  });
});

describe("paid period", () => {
  afterEach(() => vi.useRealTimers());

  it("nothing to say until the last week; read-only once ended", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-12T10:00:00Z"));
    expect(paidState(null)).toBeNull();
    expect(paidState("2026-12-30T00:00:00Z")).toBeNull();
    expect(paidState("2026-11-17T12:00:00Z")).toMatchObject({ tone: "warn", ended: false });
    expect(paidState("2026-11-17T12:00:00Z")?.text).toContain("ينتهي الاشتراك خلال");
    expect(paidState("2026-11-12T20:00:00Z")).toMatchObject({ text: "ينتهي الاشتراك اليوم", ended: false });
    expect(paidState("2026-11-11T00:00:00Z")).toMatchObject({ tone: "bad", ended: true });
  });
});

describe("money", () => {
  it("whole pounds, Latin digits", () => {
    expect(money(1250.4)).toBe("1,250 ج.م");
    expect(money(null)).toBe("0 ج.م");
  });
});
