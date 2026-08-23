import { useState } from "react";
import { PageHeader, Card, Table, Th, Td, Badge, Button, Input, Field, Select, ErrorBanner, formatMoney } from "../../components/ui";
import { useInvoices, uploadInvoice, usePurchaseOrders } from "../hooks";
import { getVendorPortalErrorMessage } from "../api/client";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "approved" || status === "paid") return "green";
  if (status === "rejected") return "brick";
  return "amber";
}

/** Real invoice list + submission, backed by the existing real
 * POST/GET /v1/vnp/vendor-users/<id>/invoices. Deliberately no
 * document-attachment field here despite UploadInvoiceSchema
 * accepting an invoice_document_id -- confirmed directly that
 * uploading a real document requires the documents:write permission,
 * which a vendor-portal token does not and should not have (tenant-
 * wide, far broader than "attach this one invoice's own file"). See
 * docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md. */
export default function InvoicesPage() {
  const { invoices, error, reload } = useInvoices();
  const { orders } = usePurchaseOrders();

  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [purchaseOrderId, setPurchaseOrderId] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      await uploadInvoice({
        invoice_number: invoiceNumber,
        amount,
        purchase_order_id: purchaseOrderId || undefined,
      });
      setInvoiceNumber("");
      setAmount("");
      setPurchaseOrderId("");
      reload();
    } catch (err: any) {
      setSubmitError(getVendorPortalErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Vendor Portal" title="Invoices" />

      <Card style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Submit a new invoice</h3>
        <form onSubmit={handleSubmit}>
          <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <Field label="Invoice number">
              <Input required value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} placeholder="e.g. INV-2026-001" />
            </Field>
            <Field label="Amount">
              <Input required type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
            </Field>
          </div>
          <Field label="Related purchase order (optional)">
            <Select value={purchaseOrderId} onChange={(e) => setPurchaseOrderId(e.target.value)}>
              <option value="">No specific purchase order</option>
              {orders?.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.po_number}
                </option>
              ))}
            </Select>
          </Field>
          {submitError && <ErrorBanner title="Could not submit invoice" detail={submitError} onDismiss={() => setSubmitError(null)} />}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Submitting…" : "Submit invoice"}
          </Button>
        </form>
      </Card>

      {error && <ErrorBanner title="Something went wrong" detail={error} />}

      <Card style={{ padding: 0 }}>
        {!invoices ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : invoices.length === 0 ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>No invoices submitted yet.</div>
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
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <Td>{inv.invoice_number}</Td>
                  <Td mono>{formatMoney(inv.amount)}</Td>
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
  );
}
