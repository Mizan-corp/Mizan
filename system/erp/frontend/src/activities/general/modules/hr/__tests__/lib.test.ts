import { describe, expect, it } from "vitest";
import { clockOf, currentMonth, settingsPayload, shiftHours } from "../lib";

const form = {
  days_in_month: "26", paid_leave_days: "4", grace_period_minutes: "10", late_penalty_multiplier: "2", missing_checkout_penalty_hours: "2",
  day_start_hour: "5", default_shift_start_hour: "9", default_shift_end_hour: "21", weekend_day: "4",
  apply_missing_checkout_penalty: true, overtime_enabled: true, weekend_paid: false,
};

describe("settingsPayload", () => {
  it("types the form as the server takes it", () => {
    expect(settingsPayload(form)).toEqual({
      days_in_month: 26, paid_leave_days: 4, grace_period_minutes: 10, late_penalty_multiplier: "2", missing_checkout_penalty_hours: "2",
      day_start_hour: 5, default_shift_start_hour: 9, default_shift_end_hour: 21, weekend_day: 4,
      apply_missing_checkout_penalty: true, overtime_enabled: true, weekend_paid: false,
    });
  });
  it("refuses values out of range or not whole", () => {
    expect(settingsPayload({ ...form, days_in_month: "32" })).toBeNull();
    expect(settingsPayload({ ...form, paid_leave_days: "1.5" })).toBeNull();
    expect(settingsPayload({ ...form, day_start_hour: "" })).toBeNull();
    expect(settingsPayload({ ...form, weekend_day: "7" })).toBeNull();
    expect(settingsPayload({ ...form, late_penalty_multiplier: "1.5" })).not.toBeNull();
  });
});

describe("shiftHours", () => {
  it("counts whole hours as the payroll does, overnight shifts included", () => {
    expect(shiftHours("09:00", "17:00")).toBe(8);
    expect(shiftHours("09:30", "17:00")).toBe(8);
    expect(shiftHours("22:00", "06:00")).toBe(8);
    expect(shiftHours("09:00", "09:00")).toBe(24);
  });
});

describe("dates", () => {
  it("reads the stored wall-clock time", () => {
    expect(clockOf("2025-02-03T08:30:00+00:00")).toBe("08:30");
    expect(clockOf(null)).toBe("—");
  });
  it("takes the month in Egypt", () => {
    expect(currentMonth(new Date("2026-01-31T23:30:00Z"))).toBe("2026-02");
  });
});
