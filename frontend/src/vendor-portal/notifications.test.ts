import { describe, it, expect } from "vitest";
import { notificationLink } from "./notifications";

const n = (type: string, data: Record<string, unknown> | null = null) => ({ id: "1", type, title: "t", body: null, data, read_at: null, created_at: "2026-10-01T00:00:00Z" });

describe("vendor notificationLink", () => {
  it("opens the issued purchase order", () => {
    expect(notificationLink(n("vnp.po_issued", { entity_type: "purchase_order", entity_id: "po1" }))).toBe("/vendor/purchase-orders/po1");
  });
  it("has no link for a PO notification without an id", () => {
    expect(notificationLink(n("vnp.po_issued"))).toBeNull();
  });
  it("keeps the existing links", () => {
    expect(notificationLink(n("vnp.rfq_invited"))).toBe("/vendor/rfqs");
    expect(notificationLink(n("vnp.banking_change_approved"))).toBe("/vendor/profile");
  });
});
