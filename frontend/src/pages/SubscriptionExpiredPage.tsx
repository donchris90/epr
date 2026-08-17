import BillingPage from "./BillingPage";

/** Shown after a real 402 from the backend (see
 * api/client.ts's redirectToSubscriptionExpired, triggered by
 * backend/app/middleware/tenant_context.py's real enforcement) --
 * deliberately reuses BillingPage directly rather than duplicating
 * its plan-listing and Subscribe logic, so there's exactly one real
 * implementation of "pick a plan and pay" in this app, not two that
 * could quietly drift apart. */
export default function SubscriptionExpiredPage() {
  return (
    <div>
      <div
        style={{
          background: "var(--sf-brick-dim)",
          borderBottom: "1px solid var(--sf-brick)",
          padding: "16px 24px",
          textAlign: "center",
        }}
      >
        <div style={{ fontWeight: 600, color: "var(--sf-brick)" }}>Your trial or subscription has ended</div>
        <div style={{ fontSize: 13, marginTop: 4 }}>
          Choose a plan below to keep using SiteForge -- your data is safe and waiting.
        </div>
      </div>
      <BillingPage />
    </div>
  );
}
