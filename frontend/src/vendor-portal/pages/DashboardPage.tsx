import { Link } from "react-router-dom";
import { PageHeader, Card, Badge } from "../../components/ui";
import { useVendorProfile, usePurchaseOrders } from "../hooks";
import type { PurchaseOrder } from "../types";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "issued" || status === "acknowledged") return "amber";
  if (status === "completed" || status === "delivered") return "green";
  if (status === "cancelled") return "brick";
  return "neutral";
}

function PurchaseOrderCard({ order }: { order: PurchaseOrder }) {
  return (
    <Link to={`/vendor/purchase-orders/${order.id}`} style={{ textDecoration: "none", color: "inherit" }}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--sf-navy-900)" }}>{order.po_number}</div>
          <Badge tone={statusTone(order.status)}>{order.status}</Badge>
        </div>
        <div style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>
          Value: <span className="sf-mono">{order.currency} {Number(order.total_value).toLocaleString()}</span>
        </div>
        {order.is_blanket && (
          <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 4 }}>Blanket order</div>
        )}
      </Card>
    </Link>
  );
}

/** Real dashboard, backed by GET /v1/vnp/vendor-users/<id>/purchase-orders
 * (built alongside this frontend -- a real, previously missing gap,
 * see docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md). No cross-order
 * "payment-related information" or "notifications" summary here --
 * neither has any real backend aggregation to show honestly (no
 * notification triggers exist for this flow at all, confirmed
 * directly against app/modules/vnp/services.py, and there is no
 * real payment-status field anywhere on InvoiceUpload beyond its own
 * internal review status). The Invoices page has the real,
 * per-invoice status data instead. */
export default function DashboardPage() {
  const { profile } = useVendorProfile();
  const { orders, error, loading } = usePurchaseOrders();

  return (
    <div>
      <PageHeader eyebrow="Welcome" title={profile?.email ?? "Your Dashboard"} />

      {loading ? (
        <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
      ) : error ? (
        <div style={{ color: "var(--sf-brick)", fontSize: 13 }}>{error}</div>
      ) : !orders || orders.length === 0 ? (
        <Card>
          <p style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>
            No purchase orders yet. Your procurement contact will issue one, and it will appear here.
          </p>
        </Card>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
          {orders.map((o) => (
            <PurchaseOrderCard key={o.id} order={o} />
          ))}
        </div>
      )}
    </div>
  );
}
