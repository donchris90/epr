import { useParams } from "react-router-dom";
import { Table, Th, Td, Badge, formatMoney } from "../../../components/ui";
import { useClientInvoices } from "../../hooks";
import { QueryState } from "../../components/QueryState";

interface Invoice {
  id: string;
  certificate_id: string;
  certificate_number: string;
  status: string;
  due_date: string | null;
  net_payable: string;
  paid_amount: string | null;
}

function statusTone(status: string): "green" | "amber" | "brick" | "neutral" {
  if (status === "paid") return "green";
  if (status === "overdue") return "brick";
  if (status === "certified") return "amber";
  return "neutral";
}

/** Invoices (item 11) + Payments (item 12): there is no separate
 * "invoice" entity anywhere in this codebase -- a submitted
 * ProgressCertificate IS the invoice, and Module 18's PaymentTracking
 * is its payment status. See services.get_client_invoices and
 * docs/CLIENT_PORTAL_GAPS.md. */
export default function InvoicesTab() {
  const { projectId } = useParams<{ projectId: string }>();
  const invoices = useClientInvoices(projectId);

  return (
    <QueryState query={invoices} emptyTitle="No invoices yet" emptyHint="Once a certificate is approved, its payment status will appear here.">
      {(data: Invoice[]) => (
        <Table>
          <thead>
            <tr>
              <Th>Certificate</Th>
              <Th>Due date</Th>
              <Th>Amount</Th>
              <Th>Paid</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((inv) => (
              <tr key={inv.id}>
                <Td mono>{inv.certificate_number}</Td>
                <Td mono>{inv.due_date ?? "—"}</Td>
                <Td>{formatMoney(inv.net_payable)}</Td>
                <Td>{inv.paid_amount != null ? formatMoney(inv.paid_amount) : "—"}</Td>
                <Td>
                  <Badge tone={statusTone(inv.status)}>{inv.status}</Badge>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </QueryState>
  );
}
