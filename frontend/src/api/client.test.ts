import { describe, it, expect } from "vitest";
// Vite's native ?raw import -- reads the file as a plain string at
// build/test time, no Node built-ins (fs/path/url) required. Those
// broke the production `tsc -b` build, since this frontend's
// tsconfig.json has no "node" lib/types (browser-only app, correctly)
// -- Vitest's own tsconfig happily resolved them, but the real build
// script (tsc -b && vite build) does not, and doesn't exclude test
// files from that check. This avoids the problem rather than working
// around it.
import clientSource from "./client.ts?raw";

/**
 * Regression coverage for a real production bug: performRefresh()
 * (the automatic access-token-refresh flow triggered on any 401)
 * hardcoded its request URL as the bare relative path
 * "/v1/auth/refresh" instead of using API_BASE_URL like every other
 * request in this client.
 *
 * That only worked by accident in local dev, where vite.config.ts's
 * dev-server proxy makes a bare "/v1" path resolve to the backend
 * anyway. Once frontend and backend are genuinely separate origins
 * (as in any real deployment), the bare path hit the frontend's own
 * domain instead -- which has no such route, so Render's (or any
 * static host's) SPA fallback rule served back index.html rather
 * than a 404. That HTML got destructured as {access_token,
 * refresh_token}, both silently came out undefined, and
 * localStorage.setItem stringified undefined to the literal text
 * "undefined" -- which every subsequent request then sent as
 * `Authorization: Bearer undefined`, a token with zero
 * dot-separated segments. The backend's real error for that
 * ("Not enough segments") is what actually surfaced in production,
 * looking unrelated to its real cause.
 *
 * A full behavioral test here would need mocking axios's interceptor
 * internals, which is disproportionately heavy for what this checks.
 * Testing the actual source directly is a deliberate, pragmatic
 * choice: it fails loudly and specifically if this exact hardcoded-
 * path regression is ever reintroduced, which is the failure mode
 * that actually happened and the one worth guarding against here.
 */
describe("api client token refresh URL construction", () => {
  it("does not hardcode a bare '/v1/auth/refresh' path for the refresh call", () => {
    // The exact regression: a literal string passed directly as
    // axios.post's first argument, bypassing API_BASE_URL entirely.
    expect(clientSource).not.toMatch(/axios\.post\(\s*["']\/v1\/auth\/refresh["']/);
  });

  it("builds the refresh URL from API_BASE_URL instead", () => {
    expect(clientSource).toMatch(/axios\.post\(\s*`\$\{API_BASE_URL\}\/auth\/refresh`/);
  });

  it("validates the refresh response contains real token strings before storing them", () => {
    // The defense-in-depth half of the fix: even if some future
    // change causes a malformed refresh response again, storage
    // should never silently receive non-string/undefined "tokens".
    expect(clientSource).toMatch(/typeof access_token !== "string"/);
    expect(clientSource).toMatch(/typeof refresh_token !== "string"/);
  });
});
