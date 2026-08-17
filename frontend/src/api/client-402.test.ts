import { describe, it, expect } from "vitest";
import clientSource from "./client.ts?raw";

/**
 * Regression coverage for real subscription enforcement handling: a
 * 402 from the backend (backend/app/middleware/tenant_context.py's
 * real enforcement) must redirect to the subscription-expired page,
 * not be silently swallowed or treated the same as an ordinary 401.
 *
 * Deliberately does NOT clear stored auth tokens the way the 401
 * handler does -- a 402 means this tenant's access is paused, not
 * that this login is invalid; the subscription-expired page still
 * needs that same token to load the (exempt) billing endpoints.
 */
describe("api client handles 402 (subscription expired) correctly", () => {
  it("checks for status 402 explicitly, separately from 401", () => {
    expect(clientSource).toMatch(/error\.response\?\.status === 402/);
  });

  it("redirects to /subscription-expired on 402", () => {
    expect(clientSource).toMatch(/redirectToSubscriptionExpired/);
    expect(clientSource).toMatch(/\/subscription-expired/);
  });

  it("does not clear stored tokens on 402 the way it does on 401", () => {
    const fn = clientSource.match(/function redirectToSubscriptionExpired\(\)[\s\S]*?\n}/)?.[0] ?? "";
    expect(fn).not.toMatch(/removeItem\("access_token"\)/);
    expect(fn).not.toMatch(/removeItem\("refresh_token"\)/);
  });
});
