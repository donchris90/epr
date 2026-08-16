import { describe, it, expect } from "vitest";
import hooksSource from "./hooks.ts?raw";
import poDetailSource from "./PurchaseOrderDetailPage.tsx?raw";
import poListSource from "./PurchaseOrdersPage.tsx?raw";
import prListSource from "./PurchaseRequestsPage.tsx?raw";
import vendorsSource from "./VendorsPage.tsx?raw";

/**
 * Regression coverage for the same class of gap fixed in BDC
 * (src/modules/bdc/hooks.test.ts) -- every apiClient call in this
 * module returned untyped data by default, so every consumer either
 * inherited `any` silently or annotated it explicitly. Second module
 * given this treatment; see README.md's session notes for the rest
 * still on the untyped pattern.
 *
 * Fixing this for real caught one genuine bug worth noting: a
 * closure-narrowing TypeScript error at
 * PurchaseOrderDetailPage.tsx's exception-approval button --
 * `po.latest_match && (...)` narrows the outer JSX correctly, but
 * that narrowing doesn't carry into a nested `onClick` closure (a
 * well-known TS limitation, not a bug in the type definitions).
 * Fixed by capturing the id into a local const before the closure.
 */
describe("PRC module has real response types, not any", () => {
  it("hooks.ts imports the real types rather than leaving them implicit", () => {
    expect(hooksSource).toMatch(
      /import type \{\s*Vendor,\s*PurchaseRequest,\s*PurchaseOrder,\s*PurchaseOrderDetail,\s*POApprovalStep,\s*GoodsReceiptNote,\s*InvoiceMatch,?\s*\} from "\.\/types"/
    );
  });

  it("hooks.ts gives the list-returning apiClient calls an explicit generic type argument", () => {
    expect(hooksSource).toMatch(/apiClient\.get<\{ data: Vendor\[\] \}>\("\/prc\/vendors"\)/);
    expect(hooksSource).toMatch(/apiClient\.get<\{ data: PurchaseRequest\[\] \}>\("\/prc\/purchase-requests"/);
    expect(hooksSource).toMatch(/apiClient\.get<\{ data: PurchaseOrder\[\] \}>\("\/prc\/purchase-orders"/);
    expect(hooksSource).toMatch(/apiClient\.get<PurchaseOrderDetail>\(`\/prc\/purchase-orders\/\$\{poId\}`\)/);
  });

  it("no page component in this module annotates a mapped item as any", () => {
    for (const [name, source] of [
      ["PurchaseOrderDetailPage.tsx", poDetailSource],
      ["PurchaseOrdersPage.tsx", poListSource],
      ["PurchaseRequestsPage.tsx", prListSource],
      ["VendorsPage.tsx", vendorsSource],
    ] as const) {
      expect(source, `${name} should not contain a ": any" annotation`).not.toMatch(/:\s*any\b/);
    }
  });
});
