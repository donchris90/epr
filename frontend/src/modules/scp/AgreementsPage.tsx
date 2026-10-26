import { Link } from "react-router-dom";
import { Badge, Card, EmptyState, ErrorBanner, formatMoney, Table, Td, Th } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useMyAgreements } from "./hooks";
import { toneFor } from "./format";

export default function AgreementsPage() {
  const { data, isLoading, error } = useMyAgreements();

  if (isLoading) return <p>Loading…</p>;
  if (error) return <ErrorBanner title="Couldn't load agreements" detail={getErrorMessage(error)} />;
  if (!data?.length) return <EmptyState title="No agreements" hint="Subcontract agreements issued to your organization appear here." />;

  return (
    <Card>
      <Table>
        <thead>
          <tr><Th>Agreement</Th><Th>Value</Th><Th>Retention</Th><Th>Payment terms</Th><Th>Status</Th></tr>
        </thead>
        <tbody>
          {data.map((a) => (
            <tr key={a.id}>
              <Td mono><Link to={`/subcontractor-portal/agreements/${a.id}`}>{a.agreement_number}</Link></Td>
              <Td mono>{formatMoney(a.value, a.currency)}</Td>
              <Td mono>{parseFloat(a.retention_percentage)}%</Td>
              <Td style={{ maxWidth: 280 }}>{a.payment_terms_summary || "—"}</Td>
              <Td><Badge tone={toneFor(a.status)}>{a.status}</Badge></Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}
