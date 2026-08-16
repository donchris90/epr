import { describe, it, expect } from "vitest";
import hooksSource from "./hooks.ts?raw";
import clientsPageSource from "./ClientsPage.tsx?raw";
import leadsPageSource from "./LeadsPage.tsx?raw";
import opportunitiesPageSource from "./OpportunitiesPage.tsx?raw";

/**
 * Regression coverage for a real (if low-severity) gap found in a
 * frontend type-safety audit: every one of this module's API calls
 * returned untyped data (axios's default `AxiosResponse<any>` when no
 * generic type argument is given), so every consumer had to either
 * accept `any` implicitly or annotate it explicitly -- 6 separate
 * `: any` annotations across 3 page components, all stemming from the
 * same single root cause rather than 6 independent problems.
 *
 * Fixed by adding real types (./types.ts, mirroring
 * backend/app/modules/bdc/schemas.py) and giving every apiClient
 * call in hooks.ts an explicit generic type argument, so the real
 * shape flows through to every consumer automatically. `npx tsc -b`
 * confirmed this compiles cleanly with zero errors -- these tests
 * guard the source pattern specifically, not re-run tsc, so a future
 * change that reintroduces `any` here fails loudly and locally rather
 * than only being caught by the next full build.
 *
 * BDC is the first of 25 modules given this treatment -- the same
 * pattern (an untyped apiClient.get/post call, consumers annotating
 * `: any` to work around it) exists in the other ~46 remaining files;
 * see README.md's session notes for the honest accounting of what's
 * done and what's still tracked, not silently claimed as complete.
 */
describe("BDC module has real response types, not any", () => {
  it("hooks.ts gives every apiClient call an explicit generic type argument", () => {
    expect(hooksSource).toMatch(/apiClient\.get<\{ data: Client\[\] \}>\("\/bdc\/clients"\)/);
    expect(hooksSource).toMatch(/apiClient\.get<\{ data: Lead\[\] \}>\("\/bdc\/leads"\)/);
    expect(hooksSource).toMatch(/apiClient\.get<\{ data: Opportunity\[\] \}>\("\/bdc\/opportunities"\)/);
  });

  it("hooks.ts imports the real types rather than leaving them implicit", () => {
    expect(hooksSource).toMatch(/import type \{ Client, Lead, Opportunity \} from "\.\/types"/);
  });

  it("no page component in this module annotates a mapped item as any", () => {
    for (const [name, source] of [
      ["ClientsPage.tsx", clientsPageSource],
      ["LeadsPage.tsx", leadsPageSource],
      ["OpportunitiesPage.tsx", opportunitiesPageSource],
    ] as const) {
      expect(source, `${name} should not contain a ": any" annotation`).not.toMatch(/:\s*any\b/);
    }
  });
});
