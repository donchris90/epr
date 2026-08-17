import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { PageHeader, Card, Button, Badge, ErrorBanner, formatMoney } from "../components/ui";

interface Plan {
  id: string;
  code: string;
  name: string;
  monthly_price_ngn: string;
  annual_price_ngn: string;
  seat_limit: number | null;
}

interface Subscription {
  plan: Plan | null;
  billing_cycle: string;
  status: string;
  trial_ends_at: string | null;
  current_period_end: string | null;
  is_active: boolean;
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

/** Real subscription management -- lists actual plans
 * (GET /v1/billing/plans), shows the tenant's real current status
 * (GET /v1/billing/subscription), and a real Subscribe button that
 * calls POST /v1/billing/subscription/checkout and redirects the
 * browser to the real Paystack authorization_url it returns. Shown
 * both at the ordinary /billing route and embedded in
 * SubscriptionExpiredPage -- the same real functionality either way,
 * just different framing around it. */
export default function BillingPage() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");
  const [error, setError] = useState<string | null>(null);
  const [subscribingCode, setSubscribingCode] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [plansRes, subRes] = await Promise.all([
        apiClient.get("/billing/plans"),
        apiClient.get("/billing/subscription").catch((err) => (err.response?.status === 404 ? null : Promise.reject(err))),
      ]);
      setPlans(plansRes.data.data);
      setSubscription(subRes ? subRes.data : null);
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubscribe(planCode: string) {
    setSubscribingCode(planCode);
    setError(null);
    try {
      const res = await apiClient.post("/billing/subscription/checkout", { plan_code: planCode, billing_cycle: billingCycle });
      window.location.href = res.data.authorization_url;
    } catch (err: any) {
      setError(getErrorMessage(err));
      setSubscribingCode(null);
    }
  }

  const daysLeftInTrial = (() => {
    if (!subscription?.trial_ends_at) return null;
    const ms = new Date(subscription.trial_ends_at).getTime() - Date.now();
    return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
  })();

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader eyebrow="Account" title="Billing" />

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      {subscription && (
        <Card style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>Current plan</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>{subscription.plan?.name ?? "—"}</div>
              {subscription.status === "trialing" && daysLeftInTrial !== null && (
                <div style={{ fontSize: 13, marginTop: 4 }}>
                  {daysLeftInTrial > 0 ? `${daysLeftInTrial} day${daysLeftInTrial === 1 ? "" : "s"} left in trial` : "Trial has ended"}
                </div>
              )}
            </div>
            <Badge tone={subscription.is_active ? "green" : "brick"}>{subscription.is_active ? "Active" : "Inactive"}</Badge>
          </div>
        </Card>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <Button variant={billingCycle === "monthly" ? "primary" : "secondary"} onClick={() => setBillingCycle("monthly")}>
          Monthly
        </Button>
        <Button variant={billingCycle === "annual" ? "primary" : "secondary"} onClick={() => setBillingCycle("annual")}>
          Annual
        </Button>
      </div>

      {plans === null ? (
        <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
          {plans.map((plan) => {
            const price = billingCycle === "monthly" ? plan.monthly_price_ngn : plan.annual_price_ngn;
            const isCurrent = subscription?.plan?.code === plan.code && subscription.is_active;
            return (
              <Card key={plan.id}>
                <div style={{ fontSize: 16, fontWeight: 600 }}>{plan.name}</div>
                <div style={{ fontSize: 24, fontWeight: 700, margin: "8px 0" }}>
                  {formatMoney(price)}
                  <span style={{ fontSize: 13, fontWeight: 400, color: "var(--sf-navy-400)" }}>
                    {" "}
                    / {billingCycle === "monthly" ? "mo" : "yr"}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: "var(--sf-navy-400)", marginBottom: 16 }}>
                  {plan.seat_limit ? `Up to ${plan.seat_limit} users` : "Unlimited users"}
                </div>
                <Button
                  variant={isCurrent ? "secondary" : "primary"}
                  disabled={isCurrent || subscribingCode === plan.code}
                  onClick={() => handleSubscribe(plan.code)}
                  style={{ width: "100%" }}
                >
                  {isCurrent ? "Current plan" : subscribingCode === plan.code ? "Redirecting…" : "Subscribe"}
                </Button>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
