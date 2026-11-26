import { describe, expect, it } from "vitest";
import { newLocalId, withLocalId } from "../offline";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("offline sale ids (SAL-2)", () => {
  it("makes UUIDs the server accepts", () => {
    const a = newLocalId();
    expect(a).toMatch(UUID);
    expect(newLocalId()).not.toBe(a);
  });

  it("keeps a sale's local_id and gives one to a payload without", () => {
    const kept = withLocalId({ local_id: "11111111-1111-4111-8111-111111111111", items: [] });
    expect(kept.local_id).toBe("11111111-1111-4111-8111-111111111111");
    expect(withLocalId({ items: [] }).local_id).toMatch(UUID);
  });
});
