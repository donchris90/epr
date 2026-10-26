import { describe, it, expect } from "vitest";
import { notificationLink } from "./notifications";

const n = (type: string, data: Record<string, unknown> | null = null) => ({ id: "1", type, title: "t", body: null, data, read_at: null, created_at: "2026-10-01T00:00:00Z" });

describe("subcontractor notificationLink", () => {
  it.each(["scp.certificate_issued", "scp.progress_verified", "scp.retention_released"])("%s opens its agreement", (type) => {
    expect(notificationLink(n(type, { agreement_id: "a1" }))).toBe("/subcontractor/agreements/a1");
  });
  it("has no link without an agreement id", () => {
    expect(notificationLink(n("scp.progress_verified"))).toBeNull();
  });
  it("keeps the claim links", () => {
    expect(notificationLink(n("scp.claim_approved"))).toBe("/subcontractor/claims");
  });
});
