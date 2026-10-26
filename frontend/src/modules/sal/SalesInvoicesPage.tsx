import { PageHeader, Card, Table, Th, Td, EmptyState, formatMoney } from "../../components/ui";
import { useSalesInvoices, useSalesOrders } from "./hooks";

export default function SalesInvoicesPage() {
  const { data: invoices, isLoading } = useSalesInvoices();
  const { data: orders } = useSalesOrders();
  const orderNumber = (id: string) => orders?.find((o) => o.id === id)?.number ?? "—";

  return (
    <div>
      <PageHeader eyebrow="Sales" title="Invoices" />
      {isLoading ? null : !invoices?.length ? (
        <EmptyState title="No invoices yet" hint="Deliver goods on a sales order, then invoice what has gone out." />
      ) : (
        <Card>
          <Table ariaLabel="Sales invoices">
            <thead>
              <tr><Th>Invoice</Th><Th>Order</Th><Th>Date</Th><Th>Due</Th><Th>Net</Th><Th>VAT</Th><Th>Total</Th></tr>
            </thead>
            <tbody>
              {invoices.map((i) => (
                <tr key={i.id}>
                  <Td mono>{i.number}</Td>
                  <Td mono>{orderNumber(i.order_id)}</Td>
                  <Td mono>{i.invoice_date}</Td>
                  <Td mono>{i.due_date ?? "—"}</Td>
                  <Td mono>{formatMoney(i.net_amount)}</Td>
                  <Td mono>{formatMoney(i.vat_amount)}</Td>
                  <Td mono>{formatMoney(i.amount)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
