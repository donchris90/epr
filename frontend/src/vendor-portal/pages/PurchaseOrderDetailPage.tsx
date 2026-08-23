import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Badge, Button, Input, Field, ErrorBanner, Table, Th, Td } from "../../components/ui";
import { usePurchaseOrders, acknowledgeOrder, useInvoices } from "../hooks";
import { getVendorPortalErrorMessage } from "../api/client";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "issued" || status === "acknowledged") return "amber";
  if (status === "completed" || status === "delivered") return "green";
  if (status === "cancelled") return "brick";
  return "neutral";
}

/** Real purchase order detail -- no dedicated single-PO GET endpoint
 * exists (only the real list endpoint added alongside this
 * frontend), so this finds the matching order client-side from the
 * already vendor-scoped list rather than adding another backend
 * route for a realistically small result set. Real "acknowledge
 * order" action (POST /v1/vnp/vendor-users/<id>/acknowledge-order,
 * already existing, real backend capability), and the real invoices
 * already submitted against this specific PO. */
export default function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { orders, loading } = usePurchaseOrders();
  const { invoices } = useInvoices();

  const [expectedDelivery, setExpectedDelivery] = useState("");
  const [acknowledging, setAcknowledging] = useState(false);
  const [ackError, setAckError] = useState<string | null>(null);
  const [ackSuccess, setAckSuccess] = useState(false);

  const order = orders?.find((o) => o.id === id);
  const relatedInvoices = invoices?.filter((inv) => inv.purchase_order_id === id) ?? [];

  async function handleAcknowledge() {
    if (!id) return;
    setAckError(null);
    setAcknowledging(true);
    try {
      await acknowledgeOrder(id, expectedDelivery || undefined);
      setAckSuccess(true);
    } catch (err: any) {
      setAckError(getVendorPortalErrorMessage(err));
    } finally {
      setAcknowledging(false);
    }
  }

  if (loading) return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  if (!order) return <ErrorBanner title="Purchase order not found" detail="This order doesn't exist or doesn't belong to your account." />;

  return (
    <div>
      <PageHeader
        eyebrow={`${order.currency} ${Number(order.total_value).toLocaleString()}`}
        title={order.po_number}
        action={<Badge tone={statusTone(order.status)}>{order.status}</Badge>}
      />

      <Card>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Order details</h3>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Total value</div>
            <div className="sf-mono">{order.currency} {Number(order.total_value).toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Type</div>
            <div>{order.is_blanket ? "Blanket order" : "Standard order"}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Status</div>
            <Badge tone={statusTone(order.status)}>{order.status}</Badge>
          </div>
        </div>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Acknowledge this order</h3>
        {ackSuccess ? (
          <p style={{ fontSize: 13, color: "var(--sf-green)" }}>Order acknowledged.</p>
        ) : (
          <>
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
              Confirm receipt of this order, and optionally commit to an expected delivery date.
            </p>
            <Field label="Expected delivery date (optional)">
              <Input type="date" value={expectedDelivery} onChange={(e) => setExpectedDelivery(e.target.value)} />
            </Field>
            {ackError && <ErrorBanner title="Could not acknowledge order" detail={ackError} onDismiss={() => setAckError(null)} />}
            <Button onClick={handleAcknowledge} disabled={acknowledging}>
              {acknowledging ? "Acknowledging…" : "Acknowledge order"}
            </Button>
          </>
        )}
      </Card>

      <div style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Invoices for this order</h3>
        <Card style={{ padding: 0 }}>
          {relatedInvoices.length === 0 ? (
            <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>No invoices submitted for this order yet.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Invoice number</Th>
                  <Th>Amount</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {relatedInvoices.map((inv) => (
                  <tr key={inv.id}>
                    <Td>{inv.invoice_number}</Td>
                    <Td mono>{Number(inv.amount).toLocaleString()}</Td>
                    <Td>
                      <Badge tone={statusTone(inv.status)}>{inv.status}</Badge>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      </div>
    </div>
  );
}
