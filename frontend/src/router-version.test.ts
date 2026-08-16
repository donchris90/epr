import { describe, it, expect } from "vitest";
import packageJsonSource from "../package.json?raw";

/**
 * Regression coverage for the react-router v6 -> v7 upgrade, deferred
 * repeatedly throughout this project's history before finally being
 * tackled -- see README.md's session notes for the full reasoning.
 *
 * Deliberately stayed on the react-router-dom package name rather
 * than migrating to the bare react-router package: react-router-dom
 * continues to exist specifically as a compatibility layer through
 * v7 (re-exporting everything so v6 apps need zero import changes) --
 * confirmed true for this codebase specifically, which uses only
 * plain declarative routing (BrowserRouter/Routes/Route/Navigate/
 * Link/NavLink/Outlet/useNavigate/useParams), none of the v7 data-
 * router APIs (createBrowserRouter, loaders, actions) that would
 * have forced real code changes. It's only fully dropped at v8, a
 * separate, newer major not part of this migration's scope. `npx
 * tsc -b`, the full production build, and the full test suite all
 * passed with zero source changes required -- this guards the
 * dependency version specifically, so a future accidental downgrade
 * (e.g. a careless `npm install react-router-dom@6`) fails loudly.
 */
describe("react-router-dom is on v7, not the vulnerable v6 range", () => {
  it("package.json pins react-router-dom to v7", () => {
    const pkg = JSON.parse(packageJsonSource);
    const version = pkg.dependencies["react-router-dom"];
    expect(version).toMatch(/^\^?7\./);
  });
});
