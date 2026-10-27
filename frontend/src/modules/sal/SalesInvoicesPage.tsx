import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner, formatMoney } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useChartOfAccounts } from "../fin/hooks";
import { useRecordPayment, useSalesInvoices, useSalesOrders, useSalesSettings, type SalesInvoice } from "./hooks";

const selectStyle = { padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" };
const TONE = { unpaid: "brick", partially_paid: "amber", paid: "green" } as const;
const LABEL = { unpaid: "Unpaid", partially_paid: "Part paid", paid: "Paid" } as const;

function PaymentPanel({ invoice, onClose }: { invoice: SalesInvoice; onClose: () => void }) {
  const record = useRecordPayment();
  const { data: settings } = useSalesSettings();
  const { data: accounts } = useChartOfAccounts();
  const [form, setForm] = useState({ amount: String(Number(invoice.balance)), method: "transfer", reference: "", deposit_account_id: "" });
  const [error, setError] = useState<string | null>(null);
  const needsAccount = !settings?.receipt_account_id;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await record.mutateAsync({
        invoiceId: invoice.id,
        amount: form.amount,
        method: form.method,
        reference: form.reference || null,
        deposit_account_id: form.deposit_account_id || null,
      });
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Record payment for {invoice.number}</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        Balance due {formatMoney(invoice.balance)}. The money is posted to the bank or cash account and taken off what the customer owes.
      </p>
      {error && <ErrorBanner title="Couldn't record the payment" detail={error} onDismiss={() => setError(null)} />}
      <form onSubmit={submit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 2fr", gap: 12 }}>
        <Field label="Amount received">
          <Input required inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
        </Field>
        <Field label="Method">
          <select aria-label="Method" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} style={selectStyle}>
            <option value="transfer">Bank transfer</option>
            <option value="cash">Cash</option>
            <option value="cheque">Cheque</option>
            <option value="card">Card</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Reference">
          <Input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} placeholder="Transfer ref, cheque no." />
        </Field>
        <Field label={needsAccount ? "Paid into (bank / cash account)" : "Paid into (default if left blank)"}>
          <select aria-label="Paid into" required={needsAccount} value={form.deposit_account_id} onChange={(e) => setForm({ ...form, deposit_account_id: e.target.value })} style={selectStyle}>
            <option value="">{needsAccount ? "Select account…" : "Default account"}</option>
            {accounts?.map((a: any) => (
              <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
            ))}
          </select>
        </Field>
        <div style={{ display: "flex", gap: 8 }}>
          <Button type="submit" disabled={record.isPending}>Record payment</Button>
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

export default function SalesInvoicesPage() {
  const { data: invoices, isLoading } = useSalesInvoices();
  const { data: orders } = useSalesOrders();
  const [paying, setPaying] = useState<SalesInvoice | null>(null);
  const orderNumber = (id: string) => orders?.find((o) => o.id === id)?.number ?? "—";

  return (
    <div>
      <PageHeader eyebrow="Sales" title="Invoices" />
      {paying && <PaymentPanel invoice={paying} onClose={() => setPaying(null)} />}
      {isLoading ? null : !invoices?.length ? (
        <EmptyState title="No invoices yet" hint="Deliver goods on a sales order, then invoice what has gone out." />
      ) : (
        <Card>
          <Table ariaLabel="Sales invoices">
            <thead>
              <tr><Th>Invoice</Th><Th>Order</Th><Th>Due</Th><Th>Total</Th><Th>Paid</Th><Th>Balance</Th><Th>Status</Th><Th></Th></tr>
            </thead>
            <tbody>
              {invoices.map((i) => (
                <tr key={i.id}>
                  <Td mono>{i.number}</Td>
                  <Td mono>{orderNumber(i.order_id)}</Td>
                  <Td mono>{i.due_date ?? "—"}</Td>
                  <Td mono>{formatMoney(i.amount)}</Td>
                  <Td mono>{formatMoney(i.amount_paid)}</Td>
                  <Td mono>{formatMoney(i.balance)}</Td>
                  <Td><Badge tone={TONE[i.payment_status]}>{LABEL[i.payment_status]}</Badge></Td>
                  <Td>
                    {i.payment_status !== "paid" && (
                      <Button variant="secondary" onClick={() => setPaying(i)}>Record payment</Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
