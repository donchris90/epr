import { describe, it, expect } from "vitest";
import { timeAgo, deepLinkFor, categoryFor } from "./notifications";

describe("timeAgo", () => {
  it("shows 'just now' for a real timestamp under a minute old", () => {
    expect(timeAgo(new Date().toISOString())).toBe("just now");
  });

  it("shows real minutes for a timestamp under an hour old", () => {
    const iso = new Date(Date.now() - 5 * 60000).toISOString();
    expect(timeAgo(iso)).toBe("5m ago");
  });

  it("shows real hours for a timestamp under a day old", () => {
    const iso = new Date(Date.now() - 3 * 3600000).toISOString();
    expect(timeAgo(iso)).toBe("3h ago");
  });

  it("shows real days for a timestamp a day or more old", () => {
    const iso = new Date(Date.now() - 2 * 86400000).toISOString();
    expect(timeAgo(iso)).toBe("2d ago");
  });
});

describe("deepLinkFor", () => {
  it("returns a real, known route for a real, recognized entity type", () => {
    expect(deepLinkFor({ entity_type: "purchase_order", entity_id: "po-1" })).toBe("/procurement/orders/po-1");
  });

  it("returns null for an entity type with no known real route, rather than guessing", () => {
    expect(deepLinkFor({ entity_type: "unknown_thing", entity_id: "x" })).toBeNull();
  });

  it("returns null when data is genuinely absent", () => {
    expect(deepLinkFor(null)).toBeNull();
  });

  it("returns null when entity_id is missing even if entity_type is present", () => {
    expect(deepLinkFor({ entity_type: "purchase_order" })).toBeNull();
  });
});

describe("categoryFor", () => {
  it("maps the real workflow.* prefix to approvals", () => {
    expect(categoryFor("workflow.approval_requested")).toBe("approvals");
    expect(categoryFor("workflow.instance_approved")).toBe("approvals");
  });

  it("maps the real clp.* prefix to projects", () => {
    expect(categoryFor("clp.request_resolved")).toBe("projects");
  });

  it("maps the real hse.* prefix to hse", () => {
    expect(categoryFor("hse.incident_raised")).toBe("hse");
  });

  it("maps an unrecognized prefix to system, honestly, rather than guessing", () => {
    expect(categoryFor("something.unexpected")).toBe("system");
  });

  it("maps a type with no dot at all to system", () => {
    expect(categoryFor("no_dot_here")).toBe("system");
  });
});
