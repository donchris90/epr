import { useEffect, useState } from "react";
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

export default function PlatformAdminTenantsPage() {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Tracks which tenant row currently has a suspend/reactivate request
  // in flight, so only that row's button shows a busy state instead of
  // freezing the whole table.
  const [pendingId, setPendingId] = useState<string | null>(null);

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
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
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
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
