import { Link, useParams } from "react-router-dom";
import { Button, ErrorBanner, formatMoney } from "../../components/ui";
import { useClients } from "../bdc/hooks";
import { useCompanies } from "../fin/hooks";
import { useMaterialItems } from "../inv/hooks";
import { useSalesOrder, useSalesSettings } from "./hooks";

const num = (v: string) => Number(v);
const cell = { padding: "6px 8px", borderBottom: "1px solid #ddd", fontSize: 13, textAlign: "left" as const };
const right = { ...cell, textAlign: "right" as const };

/** A print-ready invoice or delivery note. Uses the browser's print dialog
 * (Save as PDF works from there); the app menu is hidden when printing. */
export default function SalesDocumentPage({ kind }: { kind: "invoice" | "delivery" }) {
  const { orderId, docId } = useParams();
  const { data: order, isLoading, isError } = useSalesOrder(orderId);
  const { data: clients } = useClients();
  const { data: items } = useMaterialItems();
  const { data: settings } = useSalesSettings();
  const { data: companies } = useCompanies();

  if (isLoading) return null;
  const doc: any =
    kind === "invoice" ? order?.invoices.find((i) => i.id === docId) : order?.deliveries.find((d) => d.id === docId);
  if (isError || !order || !doc) {
    return <ErrorBanner title="Document not found" detail="It may belong to another order, or may have been removed." />;
  }

  const client = clients?.find((c) => c.id === order.client_id);
  const company = companies?.find((c: any) => c.id === settings?.company_id);
  const item = (id: string) => items?.find((i: any) => i.id === id);
  const isInvoice = kind === "invoice";

  return (
    <div>
      <div className="sf-no-print" style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <Button onClick={() => window.print()}>Print / save as PDF</Button>
        <Link to="/sales/orders"><Button variant="secondary">Back to orders</Button></Link>
      </div>

      <article aria-label={isInvoice ? "Invoice" : "Delivery note"} style={{ background: "#fff", color: "#111", padding: 32, border: "1px solid #ddd", maxWidth: 800 }}>
        <header style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 22, margin: 0 }}>{company?.name ?? "Your company"}</h1>
          </div>
          <div style={{ textAlign: "right" }}>
            <h2 style={{ fontSize: 18, margin: 0 }}>{isInvoice ? "INVOICE" : "DELIVERY NOTE"}</h2>
            <div style={{ fontSize: 13 }}>{doc.number}</div>
            <div style={{ fontSize: 13 }}>Order {order.number}</div>
            <div style={{ fontSize: 13 }}>Date: {isInvoice ? doc.invoice_date : doc.delivered_at}</div>
            {isInvoice && doc.due_date && <div style={{ fontSize: 13 }}>Due: {doc.due_date}</div>}
          </div>
        </header>

        <section style={{ marginBottom: 24, fontSize: 13 }}>
          <strong>{isInvoice ? "Bill to" : "Deliver to"}</strong>
          <div>{client?.name ?? "Client"}</div>
          {client?.billing_address && <div style={{ whiteSpace: "pre-line" }}>{client.billing_address}</div>}
          {client?.billing_email && <div>{client.billing_email}</div>}
        </section>

        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 16 }}>
          <thead>
            <tr>
              <th style={cell}>Item</th>
              <th style={right}>Quantity</th>
              {isInvoice && <th style={right}>Unit price</th>}
              {isInvoice && <th style={right}>Amount</th>}
            </tr>
          </thead>
          <tbody>
            {doc.lines.map((l: any, idx: number) => {
              const it = item(l.material_item_id);
              return (
                <tr key={idx}>
                  <td style={cell}>{it ? `${it.code} — ${it.description}` : "Item"}</td>
                  <td style={right}>{num(l.quantity)}{it?.unit ? ` ${it.unit}` : ""}</td>
                  {isInvoice && <td style={right}>{formatMoney(l.unit_price)}</td>}
                  {isInvoice && <td style={right}>{formatMoney(l.line_total)}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>

        {isInvoice ? (
          <div style={{ marginLeft: "auto", width: 260, fontSize: 13 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}><span>Subtotal</span><span>{formatMoney(doc.net_amount)}</span></div>
            <div style={{ display: "flex", justifyContent: "space-between" }}><span>VAT ({num(order.vat_percent)}%)</span><span>{formatMoney(doc.vat_amount)}</span></div>
            <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, borderTop: "1px solid #111", marginTop: 4, paddingTop: 4 }}>
              <span>Total due</span><span>{formatMoney(doc.amount)}</span>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 48, marginTop: 48, fontSize: 13 }}>
            <div style={{ flex: 1, borderTop: "1px solid #111", paddingTop: 4 }}>Delivered by (name and signature)</div>
            <div style={{ flex: 1, borderTop: "1px solid #111", paddingTop: 4 }}>Received by (name and signature)</div>
          </div>
        )}
        {doc.notes && <p style={{ fontSize: 12, marginTop: 24 }}>{doc.notes}</p>}
      </article>
    </div>
  );
}
