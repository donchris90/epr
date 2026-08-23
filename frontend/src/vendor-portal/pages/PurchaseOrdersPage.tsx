import { Link } from "react-router-dom";
import { PageHeader, Card, Table, Th, Td, Badge } from "../../components/ui";
import { usePurchaseOrders } from "../hooks";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "issued" || status === "acknowledged") return "amber";
  if (status === "completed" || status === "delivered") return "green";
  if (status === "cancelled") return "brick";
  return "neutral";
}

export default function PurchaseOrdersPage() {
  const { orders, error, loading } = usePurchaseOrders();

  return (
    <div>
      <PageHeader eyebrow="Vendor Portal" title="Purchase Orders" />

      {error && <div style={{ color: "var(--sf-brick)", fontSize: 13, marginBottom: 16 }}>{error}</div>}

      <Card style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : !orders || orders.length === 0 ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>No purchase orders yet.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>PO number</Th>
                <Th>Value</Th>
                <Th>Type</Th>
                <Th>Status</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <Td>{o.po_number}</Td>
                  <Td mono>{o.currency} {Number(o.total_value).toLocaleString()}</Td>
                  <Td>{o.is_blanket ? "Blanket" : "Standard"}</Td>
                  <Td>
                    <Badge tone={statusTone(o.status)}>{o.status}</Badge>
                  </Td>
                  <Td style={{ textAlign: "right" }}>
                    <Link to={`/vendor/purchase-orders/${o.id}`}>View</Link>
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
