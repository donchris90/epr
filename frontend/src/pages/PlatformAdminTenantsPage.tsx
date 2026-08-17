import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { platformAdminClient, getPlatformAdminErrorMessage } from "../api/platformAdminClient";
import { clearPlatformAdminToken } from "../lib/platformAdminAuth";
import { useNavigate } from "react-router-dom";
import {
  PageHeader,
  Button,
  Card,
  Table,
  Th,
  Td,
  Badge,
  ErrorBanner,
  EmptyState,
  Input,
  Select,
  Field,
} from "../components/ui";

interface Tenant {
  id: string;
  name: string;
  region: string | null;
  is_suspended: boolean;
  created_at: string;
  user_count: number;
  subscription_status: string | null;
  subscription_plan_code: string | null;
}

/** A small, self-contained overlay -- this app has no shared Modal
 * component yet, and one screen's worth of real usage isn't reason
 * enough to invent a generic one; this stays local to this file. */
function Overlay({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(11, 18, 27, 0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ width: 380 }}>
        <Card>{children}</Card>
      </div>
    </div>
  );
}

/** Real admin action -- POST /platform-admin/tenants/:id/extend-trial.
 * See backend/app/platform_admin/routes.py's own extend_trial for
 * exactly what this does: pushes trial_ends_at forward by a real
 * number of days from whichever is later, now or the existing date. */
function ExtendTrialModal({ tenant, onClose, onDone }: { tenant: Tenant; onClose: () => void; onDone: () => void }) {
  const [days, setDays] = useState("14");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    const parsed = parseInt(days, 10);
    if (!Number.isInteger(parsed) || parsed <= 0) {
      setError("Enter a whole number of days greater than 0.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await platformAdminClient.post(`/platform-admin/tenants/${tenant.id}/extend-trial`, { days: parsed });
      onDone();
    } catch (err: any) {
      setError(getPlatformAdminErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Overlay onClose={onClose}>
      <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>Extend trial</div>
      <div style={{ fontSize: 13, color: "var(--sf-navy-400)", marginBottom: 16 }}>{tenant.name}</div>
      <Field label="Days to add">
        <Input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} />
      </Field>
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 8 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <Button variant="secondary" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Extending…" : "Extend"}
        </Button>
      </div>
    </Overlay>
  );
}

/** Real admin action -- POST /platform-admin/tenants/:id/grant-subscription.
 * Activates a tenant with no Paystack charge at all: an offline
 * payment, a comp account, or covering a provider outage. Leaving
 * "period_days" blank grants indefinitely (see
 * backend/app/billing/services.py:grant_subscription's own docstring
 * on what a null current_period_end means), matching what a real comp
 * account actually is. */
function GrantSubscriptionModal({ tenant, onClose, onDone }: { tenant: Tenant; onClose: () => void; onDone: () => void }) {
  const [planCode, setPlanCode] = useState("starter");
  const [billingCycle, setBillingCycle] = useState("monthly");
  const [periodDays, setPeriodDays] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      await platformAdminClient.post(`/platform-admin/tenants/${tenant.id}/grant-subscription`, {
        plan_code: planCode,
        billing_cycle: billingCycle,
        period_days: periodDays.trim() ? parseInt(periodDays, 10) : undefined,
      });
      onDone();
    } catch (err: any) {
      setError(getPlatformAdminErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Overlay onClose={onClose}>
      <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>Grant subscription</div>
      <div style={{ fontSize: 13, color: "var(--sf-navy-400)", marginBottom: 16 }}>
        {tenant.name} -- no Paystack charge, e.g. an offline payment or comp account
      </div>
      <Field label="Plan">
        <Select value={planCode} onChange={(e) => setPlanCode(e.target.value)}>
          <option value="starter">Starter</option>
          <option value="growth">Growth</option>
          <option value="enterprise">Enterprise</option>
        </Select>
      </Field>
      <Field label="Billing cycle">
        <Select value={billingCycle} onChange={(e) => setBillingCycle(e.target.value)}>
          <option value="monthly">Monthly</option>
          <option value="annual">Annual</option>
        </Select>
      </Field>
      <Field label="Period (days) -- leave blank for no expiry">
        <Input type="number" min={1} value={periodDays} onChange={(e) => setPeriodDays(e.target.value)} placeholder="No expiry" />
      </Field>
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 8 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <Button variant="secondary" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Granting…" : "Grant"}
        </Button>
      </div>
    </Overlay>
  );
}

export default function PlatformAdminTenantsPage() {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Tracks which tenant row currently has a suspend/reactivate request
  // in flight, so only that row's button shows a busy state instead of
  // freezing the whole table.
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [extendTarget, setExtendTarget] = useState<Tenant | null>(null);
  const [grantTarget, setGrantTarget] = useState<Tenant | null>(null);

  async function loadTenants() {
    setError(null);
    try {
      const res = await platformAdminClient.get("/platform-admin/tenants");
      setTenants(res.data.data);
    } catch (err: any) {
      setError(getPlatformAdminErrorMessage(err));
    }
  }

  useEffect(() => {
    loadTenants();
  }, []);

  async function toggleSuspend(tenant: Tenant) {
    setPendingId(tenant.id);
    setError(null);
    const action = tenant.is_suspended ? "reactivate" : "suspend";
    try {
      const res = await platformAdminClient.post(`/platform-admin/tenants/${tenant.id}/${action}`);
      setTenants((prev) =>
        prev
          ? prev.map((t) => (t.id === tenant.id ? { ...t, is_suspended: res.data.is_suspended } : t))
          : prev
      );
    } catch (err: any) {
      setError(getPlatformAdminErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  function handleSignOut() {
    clearPlatformAdminToken();
    navigate("/platform-admin/login");
  }

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow="Platform Admin"
        title="Tenants"
        action={
          <Button variant="secondary" onClick={handleSignOut}>
            Sign out
          </Button>
        }
      />

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      <Card style={{ padding: 0 }}>
        {tenants === null ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : tenants.length === 0 ? (
          <EmptyState title="No tenants yet" />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Region</Th>
                <Th>Users</Th>
                <Th>Subscription</Th>
                <Th>Status</Th>
                <Th>Created</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {tenants.map((tenant) => (
                <tr key={tenant.id}>
                  <Td>{tenant.name}</Td>
                  <Td mono>{tenant.region || "—"}</Td>
                  <Td mono>{tenant.user_count}</Td>
                  <Td>
                    {tenant.subscription_plan_code
                      ? `${tenant.subscription_plan_code} (${tenant.subscription_status})`
                      : "—"}
                  </Td>
                  <Td>
                    {tenant.is_suspended ? (
                      <Badge tone="brick">Suspended</Badge>
                    ) : (
                      <Badge tone="green">Active</Badge>
                    )}
                  </Td>
                  <Td mono>{new Date(tenant.created_at).toLocaleDateString()}</Td>
                  <Td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <Button variant="ghost" onClick={() => setExtendTarget(tenant)}>
                        Extend trial
                      </Button>
                      <Button variant="ghost" onClick={() => setGrantTarget(tenant)}>
                        Grant plan
                      </Button>
                      <Button
                        variant={tenant.is_suspended ? "secondary" : "danger"}
                        disabled={pendingId === tenant.id}
                        onClick={() => toggleSuspend(tenant)}
                      >
                        {pendingId === tenant.id
                          ? "Working…"
                          : tenant.is_suspended
                          ? "Reactivate"
                          : "Suspend"}
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {extendTarget && (
        <ExtendTrialModal
          tenant={extendTarget}
          onClose={() => setExtendTarget(null)}
          onDone={() => {
            setExtendTarget(null);
            loadTenants();
          }}
        />
      )}
      {grantTarget && (
        <GrantSubscriptionModal
          tenant={grantTarget}
          onClose={() => setGrantTarget(null)}
          onDone={() => {
            setGrantTarget(null);
            loadTenants();
          }}
        />
      )}
    </div>
  );
}
