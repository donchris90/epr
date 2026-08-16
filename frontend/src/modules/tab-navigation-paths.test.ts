import { describe, it, expect } from "vitest";
import prcSource from "../modules/prc/index.tsx?raw";
import bdcSource from "../modules/bdc/index.tsx?raw";
import plnSource from "../modules/pln/index.tsx?raw";
import exeSource from "../modules/exe/index.tsx?raw";
import finSource from "../modules/fin/index.tsx?raw";
import bilSource from "../modules/bil/index.tsx?raw";
import invSource from "../modules/inv/index.tsx?raw";
import fuelSource from "../modules/fuel/index.tsx?raw";
import wfmSource from "../modules/wfm/index.tsx?raw";
import qmsSource from "../modules/qms/index.tsx?raw";
import hseSource from "../modules/hse/index.tsx?raw";
import aiSource from "../modules/ai/index.tsx?raw";

/**
 * Regression coverage for a real, user-reported bug: navigating
 * between a module's tabs (e.g. Procurement) produced URLs like
 * /procurement/vendors/requests/vendors/vendors/vendors -- the path
 * accumulating a new segment on every click instead of replacing it.
 *
 * Root cause: this app uses a plain declarative <BrowserRouter>
 * (not a data router), which resolves a relative `to` prop (no
 * leading slash) against the CURRENT FULL URL PATH, not against the
 * route's own fixed mount point -- a well-documented React Router
 * gotcha. Every module's tab bar used relative `to` values
 * (`to: "vendors"`), so clicking a tab while already a few segments
 * deep kept appending rather than replacing.
 *
 * Fixed by making every tab link and index-redirect absolute (a
 * leading slash), which always resolves to a fixed destination
 * regardless of the current URL depth -- verified across all 12
 * modules that use this same tab-bar pattern, not just the one
 * reported (Procurement).
 */
const MODULES = [
  ["prc", prcSource],
  ["bdc", bdcSource],
  ["pln", plnSource],
  ["exe", exeSource],
  ["fin", finSource],
  ["bil", bilSource],
  ["inv", invSource],
  ["fuel", fuelSource],
  ["wfm", wfmSource],
  ["qms", qmsSource],
  ["hse", hseSource],
  ["ai", aiSource],
] as const;

describe("every module's tab navigation uses absolute paths, not relative ones", () => {
  for (const [name, source] of MODULES) {
    it(`${name}/index.tsx: no relative "to:" value in its TABS array`, () => {
      const relativeToMatches = [...source.matchAll(/\{ to: "([^"]+)"/g)].map((m) => m[1]);
      for (const value of relativeToMatches) {
        expect(value.startsWith("/"), `TABS to: "${value}" must be absolute (start with "/")`).toBe(true);
      }
      // Every module in this list genuinely has a TABS array -- if this
      // is ever empty, the regex above stopped matching real content
      // (e.g. the tab bar was refactored) and this test needs updating,
      // not silently passing on nothing.
      expect(relativeToMatches.length).toBeGreaterThan(0);
    });

    it(`${name}/index.tsx: its index-route <Navigate> target is absolute`, () => {
      const navigateMatches = [...source.matchAll(/<Navigate to="([^"]+)"/g)].map((m) => m[1]);
      expect(navigateMatches.length).toBeGreaterThan(0);
      for (const value of navigateMatches) {
        expect(value.startsWith("/"), `<Navigate to="${value}"> must be absolute (start with "/")`).toBe(true);
      }
    });
  }
});
